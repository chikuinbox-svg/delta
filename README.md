# Delta India Research Lab

A standalone local Python dashboard for **historical research and paper simulation**.
It has no trading execution routes, authentication code or API-key inputs. It does
not inspect, modify or run any existing bot. No sample performance is shown as real.

**Status:** runnable offline research implementation. Public API documentation and
real historical integration are not yet verified because the cloud network blocked
Delta endpoints. Synthetic tests are useful engineering evidence, not evidence of
profitability. Exact strategy replication and exchange-accurate execution are not complete.
See [progress](docs/PROGRESS.md) and [API verification](docs/API_CONTRACT.md).

## Windows: use without coding

1. Install **64-bit Python 3.12** from python.org if it is not already installed.
   Include the Python launcher (`py`). No global Python packages are needed.
2. Extract this project into a **short folder**, such as `C:\DeltaLab`, separate from your live bot. Avoid deeply nested Pictures/backup folders.
3. Double-click **setup.bat**. It creates `.venv` and installs pinned dependencies
   inside this folder. Internet access to the Python package index is required.
4. Double-click **start_dashboard.bat**. Leave its terminal open.
5. Open your browser yourself and type `http://127.0.0.1:8501`.
6. Press **Ctrl+C** in that terminal to stop the dashboard. Nothing starts at boot.

If the port is already used, stop only this project's terminal and select a free port
by editing the `--server.port` argument in `start_dashboard.bat`. Do not stop other bots
or services. These batch scripts were inspected, but cannot be executed on this Linux host.

## First research session

1. **Market Data:** refresh the public catalogue, select symbols, choose 1m or 3m,
   and download a small completed UTC interval first. Retention and listing-date
   coverage may prevent a requested period from being complete. Missing windows
   are reported, and interrupted requests resume from the last committed window.
   Select all for the catalogue observed today; this is not an historical universe.
2. **Strategy Configuration:** review baseline settings. No initial-stop or trailing
   formula is invented. Enter an explicit research initial-stop distance and, if
   desired, a single research trailing rule. Confirm these are research alternatives.
   Save a version. To match your bot, supply only a sanitized strategy excerpt in a
   separate reconciliation task; never provide credentials or access to the live bot.
3. **Backtest Runner:** select complete **3-minute** histories with the same dates.
   Enter and confirm actual contract size, tick size, lot size and volume unit from
   official exchange metadata. Provide an explicit constant quote-to-INR conversion
   assumption. Select capital, fee/GST, slippage, spread and funding estimates.
   An unchecked assumption or missing required rule blocks the run.
4. Use **Overview**, **Trade Replay** and **Loss Diagnosis** to inspect simulated
   results and their event logs. Zero trades is a valid result, not evidence of an edge.
5. **Strategy Comparison:** compare saved versions on the same data and costs.
   **Walk-Forward Research:** enter a small parameter grid, training/test lengths,
   and an embargo. Selection uses training only; unseen test windows do not overlap.
6. **Reports:** export configurations, trades and complete results. Each saved run
   contains immutable input Parquet copies, SHA-256 hashes, source hashes and installed
   package versions. Keep those files together to reproduce a result.
7. Double-click **run_tests.bat** to run the synthetic and mocked engineering tests.
   The public-network integration test is skipped by default.

Do not use results as trading advice or proof of an edge. Validate a genuinely
historical universe, dated exchange specifications, historical FX/funding and cost
sensitivity before drawing conclusions. Report unseen performance and drawdown,
including configurations that failed, rather than selecting attractive charts.

## What the simulator does

- Wilder RSI, fresh crossings only, volume relative to prior completed median;
  signals are generated at the close of a 3m bar and become eligible on later bars.
- Thirty-minute traded value uses close × candle volume × contract conversion.
  This is a candle-based proxy, **not actual trade-by-trade turnover**.
- Tick/lot rounding; pending breakout expiry; fixed notional; shared margin and
  capital; deterministic symbol tie-breaking; no same-bar reuse of future freed
  margin/position slots; optional whole-candle-volume partial-fill estimate.
- Explicit research initial stop capped by the ₹100 adverse price-move budget.
  This cap excludes fees, gaps and slippage; actual simulated loss may exceed it.
- Optional completed-close trailing activation/distance, effective next bar;
  simulated atomic protective-stop attachment; persistent stops in disconnect
  scenarios; JSON state round-trip restart scenarios.
- Taker fees, GST, signed prorated constant funding, spread and adverse slippage;
  optional simplified maintenance-margin liquidation estimate; insufficient margin
  rejection; daily loss evaluated at opens/closes using **IST** calendar days.
- Conservative same-bar entry+stop, optimistic ordering, and exclusion scenarios.
  Optimistic outcomes are explicitly labelled assumptions. Existing stops take
  precedence over later close-based trailing changes. Gap stops fill adversely.
- Net P&L, equity, drawdown, expectancy, profit factor, MFE/MAE observations,
  excursion timing, duration, follow-through flags, post-exit recovery and event logs.
  Excursions/timing on entry/exit bars are **censored**; they are not tick-accurate.
- Candidate grid comparisons and rolling train-only selection followed by disjoint
  unseen tests. Each fold starts flat, closes positions at its boundary, and uses fresh
  warmup. Training windows may overlap, test windows do not. Initial warmup trades
  are deliberately omitted. No untouched final holdout is automatically reserved.

## Material limitations and missing capabilities

- Official public API parameters, pagination, server limits, volume units and history
  retention are provisional until documentation/sample verification. No real-data
  integration result is claimed. The downloader supports only 1m and 3m OHLCV.
- Historical funding, mark prices, OI, depth, trades and spreads are not ingested.
  Candle-only runs reject historical OI/spread/depth filters rather than substitute
  current observations. Twenty-four-hour turnover is a candle proxy. True delisted
  market coverage requires an external historical universe.
- Xa, original stop and staged trailing formulas, bot-specific loss accounting,
  attached-stop failure/retry recovery and exact execution behavior remain
  **unreconciled**. The single research trailing rule is not a replacement claim.
- No historical tick/trade event replay or exchange order-book queue model. Maker
  fills are rejected for stop-market breakout entries. Partial fills are explicitly
  estimated from entire candle volume; unfilled remainder is cancelled.
- No true exchange liquidation tiers, maintenance schedules, liquidation penalties,
  historical tick-size changes or changing INR conversion. The liquidation option
  is only a simplified scenario. Bad or missing candles block simulation.
- Restart stress tests serialize state inside one process; durable engine recovery
  after an OS crash is not implemented. Downloader checkpoints do persist on disk.
  Stop-recovery failures and symbol-level exchange errors are not exchange-emulated.
- Daily protection observes candle boundaries; intrabar breaches can exceed limits.
  No automatic statistical significance or causal inference. Regime filtering uses
  an explicit 20-bar price-efficiency heuristic; it is a research assumption.
- Single dashboard/download writer per project folder. Do not start concurrent
  downloaders or dashboards against the same files.
- Windows launchers have not been run on Windows. Prepared cloud processes and
  snapshot restoration have not been validated in a fresh published task.

## Files and isolation

Everything generated by this application stays below the project root:
`.venv/`, `.cache/`, `data/`, `configs/`, `reports/`, and local logs. These are ignored
by Git. No credential is required or stored. No background service, emulator,
extension, global package install, startup setting or automatic browser launch.
Pinned direct dependencies are in `requirements.txt`; installed transitive versions
are recorded with reports and in `requirements-lock.txt` for this tested environment.

Architecture:

| Module | Responsibility |
|---|---|
| `api.py`, `download.py` | Approved read-only routes, catalogue and resumable downloads |
| `storage.py` | Parquet, DuckDB, quality checks, atomic metadata |
| `config.py`, `indicators.py`, `strategy.py` | Validated assumptions and completed-bar signals |
| `execution.py`, `portfolio.py`, `engine.py` | Fills, accounting, event orchestration, risk |
| `diagnostics.py`, `research.py`, `reporting.py` | Diagnosis, chronological evaluation, provenance |
| `dashboard.py`, `app.py` | Nine local Streamlit pages |
| `tests/` | Synthetic, mocked, dashboard and opt-in real-sample checks |

## Linux / cloud

From this checkout, using Python 3.11+:

```bash
mkdir -p .cache/tmp
export TMPDIR="$PWD/.cache/tmp" PIP_CACHE_DIR="$PWD/.cache/pip"
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest -q --basetemp=.cache/pytest-tmp
.venv/bin/python -m streamlit run app.py --server.headless=true --server.address=127.0.0.1 --browser.gatherUsageStats=false
```

After the official documentation contract has been checked and public endpoints
are reachable, explicitly exercise a ten-candle real sample:

```bash
DELTA_RUN_PUBLIC_INTEGRATION=1 .venv/bin/python -m pytest tests/test_live_public.py -q
```

This test uses only public GET routes and stores its real sample below `data/`.
Never disable TLS verification or supply a trading API key to make it pass.

To audit an exported run entirely offline (with its original input files alongside it):

```bash
.venv/bin/python -m delta_lab verify-run reports/RUN_FOLDER/result.json
```

The audit verifies input hashes, recomputes trades/equity/events and fails if they
differ. Use the recorded source and package versions when reproducing older runs.

## Validate on a real Windows machine

Open PowerShell in this extracted project folder and run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify_windows.ps1
```

This command changes execution policy only for that one PowerShell process, not
Windows settings. It runs the actual setup/test/dashboard batch launchers, uses a
free loopback port, checks HTTP responses, and stops only the process tree it
started. Evidence is written to `.cache/windows-smoke/result.json` and logs.
No browser opens. A failure is recorded and reported; it is not treated as a pass.

A manually triggered GitHub Actions workflow is also supplied in
`.github/workflows/windows-validation.yml`. It is not pushed or executed from this
cloud session. After you save this project to GitHub, use Actions → Manual Windows
validation → Run workflow, then download its evidence artifact. It needs no trading
credentials. A hosted Windows runner is external to this local application.

Exact strategy reconciliation inputs are listed in
[STRATEGY_RECONCILIATION.md](docs/STRATEGY_RECONCILIATION.md).

## Windows installation: DuckDB / long-path error

If pip reports `No such file or directory` under `pip-install-.../duckdb...`
and mentions Windows Long Path support, it was trying to unpack/build DuckDB
from source in a deeply nested folder. The updated installer avoids source builds
and selects supported 64-bit Python 3.12, falling back to 3.11. A missing compatible
wheel now fails clearly rather than starting a compiler build.

1. Download the latest project ZIP and extract it into `C:\DeltaLab`.
2. Install **Python 3.12 — Windows installer (64-bit)** from python.org. Keep the
   launcher enabled. You do not need to remove other Python versions.
3. Run the new `setup.bat`, then `start_dashboard.bat`.

Use a fresh extraction rather than copying an old `.venv` into the new folder.
Virtual environments must be created in their final folder. No registry or
system-wide long-path change is required by this fix. The installer rejects
project paths longer than 80 characters as a conservative installation guard.
