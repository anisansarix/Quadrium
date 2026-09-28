# Research Starter

This starter kit is designed for a quadrium RL trading platform built with Google Antigravity.

Start here:

1. `AGENTS.md`
2. `PLAN.md`
3. `ARCHITECTURE.md`
4. `EVALUATION_PROTOCOL.md`
5. `RESEARCH_MAP.md`
6. `notebooklm-research-prompt.md`

Antigravity-specific guidance lives under:

```text
.agents/
  rules/
  skills/
```

Recommended first task in Antigravity:

```text
Read AGENTS.md, PLAN.md, ARCHITECTURE.md, EVALUATION_PROTOCOL.md,
and RESEARCH_MAP.md.

Then audit the current repository state and produce an implementation
backlog for Phase 0 only. Do not write the trading engine yet.
```

Recommended next task:

```text
Perform a source-grounded architecture review using the research-evidence
skill. Compare gym-mtsim, TradeMaster, FinRL-X, rl_trading, and
mt5-rl-trader for this project's Phase 1 to Phase 3 requirements.
Do not rank them. Produce an ADR-style recommendation and list the
evidence behind each decision.
```
