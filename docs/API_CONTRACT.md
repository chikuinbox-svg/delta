# Public-data verification status

The current cloud policy denied CONNECT to https://docs.delta.exchange/ and
https://api.india.delta.exchange on 2026-11-03. No current official documentation
or real response has been read successfully. API integration is **provisional**.
Required access domains were saved to the environment draft. No credentials are needed.

Candidate public routes, to verify before production-size downloads:
- GET https://api.india.delta.exchange/v2/products: result array; page_size and after,
  meta.after pagination; contract_type=perpetual_futures.
- GET /v2/history/candles: symbol, resolution (1m, 3m), start/end Unix seconds;
  result array with time, open/high/low/close/volume. Client uses conservative
  500-bar windows, 4 requests/sec maximum, bounded exponential retries, and filters
  end-exclusive UTC intervals. These are client choices, not verified server limits.

Not verified: API limits, retention, listing-date coverage, volume denomination,
settlement conversions, contract_size/tick_size semantics, historical funding, OI,
mark prices, spreads, trades or depth. No historical values for those are invented.
Current product observations are timestamped; they cannot reconstruct delisted
markets. Research on a current catalogue is survivorship-biased until an historical
universe is supplied. Missing windows are reported and remain resumable.

A successful real sample will verify response shape and the requested sample only,
not all historical coverage or the documentation contract.

Follow-up: explicit real-sample pytest invocation failed (not skipped) with
`httpx.ProxyError: 403 Forbidden` in 16.62 seconds. Retrying documentation returned
403. The running policy has not incorporated the saved Delta domains. No public
response or documentation contract could be verified.
