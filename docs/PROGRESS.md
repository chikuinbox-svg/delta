# Development progress

## Phase 1
Implemented public-route-only client, bounded retries, paginated product catalogue,
500-bar download windows, checkpoints, incremental merges, compressed Parquet,
DuckDB reads, UTC quality checks, catalogue observation history, progress and data UI.
Validation: six synthetic/mocked tests passed on 2026-11-03 (pytest, 0.73 seconds).
External gate remains open: official documentation and real historical sample are
blocked by network policy. Volume units, contract metadata and coverage are unverified.
Offline implementation can progress, but Phase 1 is not live-integration validated.

## Phase 2 — offline signal and engine implementation
Implemented validated strategy versions, Wilder RSI and fresh crossings, prior-bar
median volume, turnover proxies, pending triggers, expiry and chronological 3m
multi-symbol orchestration. Baseline initial-stop rules require explicit confirmation.
No exact bot-replica claim. Required formula reconciliation is still outstanding.

## Phase 3 — research execution and accounting
Implemented deterministic candle fill scenarios, tick and lot rounding, shared
capital/margin, position caps, taker costs/GST, assumed spread/slippage/funding,
estimated volume participation, protective stops, single-stage completed-close
research trailing, daily IST halts, simplified liquidation and restart/disconnect
stress modes. Phase 2/3 checkpoint: 22 tests passed in 1.00 second.
Subsequent fixes reserve opening-bar capacity so exits observed later within a
candle cannot finance an entry at that candle's open. Full bot stop recovery,
actual trade-event fills, historical funding and exchange liquidation tiers remain
unimplemented; current mechanisms are explicitly research alternatives.

## Phase 4 — dashboard and reports
All nine pages implemented, including candlestick replay, stop events, entry/exit
markers, MFE/MAE observations, recovery, cost and entry-quality associations,
strategy comparison, configuration versions, CSV/JSON exports and provenance.
AppTest exposed a mixed int/float Streamlit widget error; validating model defaults
fixed it. Automated UI tests cover empty pages and pages populated with synthetic
simulated trades. No synthetic results were inserted into user-facing reports.
Exact intrabar excursion timing remains censored; causal explanations are not claimed.

## Phase 5 — research and validation
Implemented bounded parameter grids, rolling train-only selection, explicit embargo,
flat-state fold boundaries, disjoint unseen test windows, no-trade selection handling,
configuration and source hashes, exact input Parquet copies, package versions,
state serialization/restart and disconnect stress tests. Comparison keeps data and
execution assumptions fixed. True historical-universe bias prevention requires a
listing/delisting dataset unavailable here. No automatic final untouched holdout,
statistical significance inference, queue model, or OS-crash engine checkpoint.

## Latest executed validation — 2026-11-03
- `python -m pytest -q`: **32 passed, 1 skipped** in 1.82 seconds.
- Skipped: real public historical sample integration; explicit opt-in required and
  external API policy access/documentation verification unresolved.
- `python -m pip check`: no broken requirements.
- `python -m compileall -q delta_lab app.py`: passed.
- Running Streamlit on loopback port 8501: health endpoint returned `ok`; root HTML
  request succeeded. A sandbox socket restriction required approved execution
  outside the command sandbox; no system service was installed.
- Windows batch launchers inspected, not executed on this Linux host.

## External gates and next work
1. Review/save the draft allowing `docs.delta.exchange`,
   `docs.india.delta.exchange`, and `api.india.delta.exchange` in environment settings,
   then publish as prompted. GitHub/package-manager presets were preserved.
2. Verify current official API docs and the candidate schema in API_CONTRACT.md;
   run the opt-in ten-candle real integration and correct any contract differences.
3. Reconcile sanitized bot strategy formulas (no credentials, no access to the live
   bot). Implement those separately before calling this an exact strategy backtest.
4. Obtain historical universe, dated specifications, FX/funding and microstructure
   observations for exchange-realistic estimates; test the launchers on Windows.

The offline application is runnable; live data readiness, exact-bot validation,
Windows runtime behavior and fresh published-environment restoration are not claimed.

Additional audits verify checkpoint recovery after data deletion, saved-run input
hash integrity and exact event/equity/trade reproduction, and prevent same-bar
reuse of an intrabar exit’s future freed position capacity.

The exact saved cloud install script was rerun successfully: 32 passed, 1 skipped
in 1.75 seconds, with no broken installed requirements. Installation and startup
instructions were persisted in the environment draft; saving does not publish or
validate restoration in a new task.

## Follow-up validation attempt

The explicit public integration test was attempted on 2026-11-03 and **failed**
in 16.62 seconds with `httpx.ProxyError: 403 Forbidden`. The documentation request
also returned HTTP 403. The observed enforced runtime policy still has no Delta
domains, despite the saved draft. The 32-test offline suite passed again (1.92s);
its opt-in network test remains skipped in the default suite. These outcomes are
distinct; the live integration has not passed.

Windows launchers now support noninteractive validation, a configurable test port,
and dashboard exit-status propagation. A Windows-only PowerShell smoke script
and manual GitHub Actions workflow exercise the actual three batch files and
record HTTP health/HTML evidence. Neither has been executed on Windows here.
No Windows runtime is available, and no emulator/system tool was installed.
A reconciliation checklist was added; original bot formulas remain unavailable.

## Windows installation repair

A user screenshot showed pip unpacking a DuckDB source distribution under a very
long nested Windows project/temp path and failing with missing-path/Long Path
errors. The old launcher selected any latest Python and allowed source fallback.
Setup now selects 64-bit Python 3.12, falling back to 3.11; checks existing venv
compatibility; rejects project paths longer than 80 characters; uses prebuilt
packages only; and preserves package-install failures. No Windows registry or
global Python changes are made. The manual Windows workflow now covers both
supported Python versions.

Validation: 32 offline tests passed, 1 skipped (1.48 seconds). Cross-platform pip
resolution/download of all pinned direct requirements and their dependencies
succeeded for Windows amd64 CPython 3.11 and 3.12 using wheels only. This confirms package
availability, not successful execution on Windows. Actual Windows launch testing
remains outstanding.
