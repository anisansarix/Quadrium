# Simulator Specification

## Accounting Conventions

* **Balance**: The realized cash in the account. Updates strictly on realized PnL, realized commissions, and realized swaps.
* **Equity**: `Balance + Floating PnL`. Floating PnL is net of spread (marked to market at the current closing quote: bids for longs, asks for shorts).
* **Double Counting**: Commissions and swaps are immediately deducted from `Balance` when realized. They are not deducted again from `Floating PnL`.

## Timing Semantics

### Quote / Tick Input
1. **t**: Observe current quote $q_t$.
2. **t**: Strategy decides target exposure $T_t$.
3. **t**: RiskEngine evaluates $T_t$ against current portfolio.
4. **t**: Simulator executes approved volume at $q_t$. (In reality, $t+\delta$ latency applies, modeled via `LatencyModel`, but defaults to exact $t$ for deterministic quote backtests).

### Bar Input (OHLC)
1. **t**: Observe features derived from the completed bar at $t$.
2. **t**: Strategy decides target exposure $T_t$.
3. **t**: RiskEngine evaluates $T_t$.
4. **t+1**: Simulator executes the order no earlier than the *open* of the next bar $t+1$. 
**Rule**: Do not allow a decision made on a bar's close to be executed at that same bar's close.

## End of Test Policy
When a backtest concludes, open positions must be reconciled to finalize the equity curve and metrics.
Supported policies:
* **FLATTEN_AT_END**: A forced market order is submitted at the final quote to close all positions. Realizes all PnL and final execution costs.
* **MARK_TO_MARKET**: Positions remain open. Equity is calculated at the final quote without executing closing orders or incurring closing commissions.
