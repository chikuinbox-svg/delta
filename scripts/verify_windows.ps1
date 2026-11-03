# Windows-only validation. Installs only this project's Python dependencies.
# Calls the actual batch launchers. No API keys, trading bot, browser or service.
$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $PSScriptRoot
Set-Location $project
$evidence = Join-Path $project '.cache\windows-smoke'
New-Item -ItemType Directory -Force $evidence | Out-Null
$stamp = (Get-Date).ToUniversalTime().ToString('o')
$server = $null
try {
    & cmd.exe /d /c 'call setup.bat --no-pause'
    if ($LASTEXITCODE -ne 0) { throw 'setup.bat failed' }
    & cmd.exe /d /c 'call run_tests.bat --no-pause'
    if ($LASTEXITCODE -ne 0) { throw 'run_tests.bat failed' }
    # Allocate a free loopback test port, leaving existing services untouched.
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
    $listener.Start()
    $port = $listener.LocalEndpoint.Port
    $listener.Stop()
    $env:DELTA_DASHBOARD_PORT = "$port"
    $server = Start-Process -FilePath 'cmd.exe' -ArgumentList '/d /c call start_dashboard.bat --no-pause' -WorkingDirectory $project -PassThru -RedirectStandardOutput (Join-Path $evidence 'dashboard.stdout.log') -RedirectStandardError (Join-Path $evidence 'dashboard.stderr.log')
    $healthy = $false
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        $server.Refresh()
        if ($server.HasExited) { throw 'Dashboard launcher exited before readiness; inspect logs' }
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$port/_stcore/health" -TimeoutSec 2
            if ($response.StatusCode -eq 200 -and $response.Content.Trim() -eq 'ok') { $healthy = $true; break }
        } catch { }
        Start-Sleep -Milliseconds 500
    }
    if (-not $healthy) { throw 'Dashboard did not become healthy' }
    $html = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$port/" -TimeoutSec 5
    if ($html.StatusCode -ne 200 -or $html.Content -notmatch '(?i)streamlit') { throw 'Unexpected dashboard HTML' }
    # AppTest in run_tests.bat verifies the application pages beyond the HTTP shell.
    @{ started_utc=$stamp; status='passed'; platform=[Environment]::OSVersion.VersionString; port=$port; checks=@('setup.bat','run_tests.bat','start_dashboard.bat','HTTP health','HTTP HTML') } | ConvertTo-Json | Set-Content (Join-Path $evidence 'result.json')
    Write-Host "Windows checks passed. Evidence: $evidence"
} catch {
    @{ started_utc=$stamp; status='failed'; error=$_.Exception.Message } | ConvertTo-Json | Set-Content (Join-Path $evidence 'result.json')
    throw
} finally {
    if ($null -ne $server) {
        $server.Refresh()
        if (-not $server.HasExited) {
            # Stop ONLY the process tree started by this script, never by port/name.
            & taskkill.exe /PID $server.Id /T /F | Out-Null
        }
    }
    Remove-Item Env:DELTA_DASHBOARD_PORT -ErrorAction SilentlyContinue
}
