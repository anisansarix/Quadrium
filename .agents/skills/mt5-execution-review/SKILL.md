---
name: mt5-execution-review
description: Reviews MT5 data and execution integration for symbol metadata, order semantics, reconciliation, safety, and simulator parity. Use when changing broker integration or moving from research toward demo/live execution.
---

# MT5 Execution Review

## Review data access

Check:
- symbol selection
- symbol aliases
- timezone handling
- timeframe mapping
- current quote semantics
- historical bar semantics
- missing data
- broker-specific properties

## Review order flow

Expected:

```text
Policy proposal
  -> RiskEngine
  -> ApprovedOrder
  -> ExecutionAdapter
  -> MT5
  -> Broker response
  -> Reconciliation
  -> Ledger
```

Never bypass RiskEngine.

## Review order fields

Validate as applicable:
- action
- symbol
- volume
- order type
- price
- stop loss
- take profit
- deviation
- magic number
- comment
- filling mode
- time policy

## Failure handling

Explicitly test:
- rejected order
- requote or price change
- disconnected terminal
- stale quote
- unavailable symbol
- invalid volume
- invalid stop distance
- partial execution where applicable
- restart/recovery
- duplicate submission prevention

## Simulator parity

For each MT5 behavior used in production, document the simulator equivalent and the known gap.

## Output

Produce a checklist with:
- pass
- fail
- unknown
- evidence
- remediation
