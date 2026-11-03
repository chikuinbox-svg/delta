# Exact strategy reconciliation — required input

No original bot source or sanitized formula excerpt was provided. Only this
project's research strategy exists in the checkout. No live bot directories or
credential files have been inspected. Exact matching cannot be inferred from
baseline RSI, notional, leverage and loss thresholds.

Provide a separate sanitized text file containing ONLY:
1. Adaptive Xa formula and its data inputs, units, rounding and update times.
2. Initial long/short stop calculations and exchange attachment behavior.
3. Each trailing stage: trigger, stop distance, state transitions and update timing.
4. Monetary loss computation: fees, realized/unrealized P&L, margin and currency conversion.
5. Pending expiry, entry fill rules, partial fills, restart state and daily-reset timezone.
6. Stop-attachment verification/retry/recovery and error behavior.

Include a few input/output examples if available. Remove API keys, tokens,
account details, authentication, order-sending code and personal paths. Do not
provide access to the live bot. Those sanitized formulas will be implemented
behind a distinct strategy version and verified with regression examples before
any exact-replica label is permitted. Current research alternatives remain labelled.
