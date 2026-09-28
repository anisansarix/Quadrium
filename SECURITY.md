# SECURITY.md

## Secrets

Never commit:
- MT5 login
- MT5 password
- broker server secrets
- API keys
- webhook secrets
- cloud credentials
- signing keys

Use environment variables or a secret manager.

## Execution safety

Research and live execution must be separated by explicit configuration.

Recommended modes:

```text
RESEARCH
BACKTEST
PAPER
MT5_DEMO
LIVE
```

Default mode must not be LIVE.

## Kill switch

A kill switch must be available outside the RL policy.

It must be able to:
- reject new orders
- flatten positions where authorized
- suspend execution
- emit an audit event

## Audit events

Log:
- proposal
- risk decision
- rejection reason
- approved order
- broker response
- reconciliation
- state transitions
- kill switch activation

Do not log secrets.

## Dependency hygiene

Pin or lock dependencies for reproducible research.

Review security advisories before production execution.

Use CI for:
- tests
- linting
- dependency checks
- secret scanning where available
