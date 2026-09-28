---
name: project-core
description: Persistent engineering rules for the RL FX and XAUUSD research platform.
always_on: true
---

# Project Core Rule

Use `@AGENTS.md` as the source of persistent architecture and safety invariants.

Important:
- risk rules are hard constraints
- RL never sends broker orders directly
- live trading is opt-in and isolated
- all timestamps are UTC internally
- no future information in observations or features
- final test data stays sealed
- every experiment records data, code, config, and seed identity
- all broker integration is adapter-based
- use tests for accounting, risk, and execution boundaries

When in doubt, stop at the safer layer and request explicit project direction in the task artifact rather than silently weakening a safety invariant.
