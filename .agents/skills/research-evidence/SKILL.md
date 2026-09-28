---
name: research-evidence
description: Performs source-grounded technical research for trading, RL, MT5, simulation, and ML infrastructure. Use when evaluating libraries, papers, repositories, architectures, or methodology.
---

# Research Evidence Skill

## Goal

Produce implementation-relevant research with explicit evidence quality.

## Procedure

1. Start with official documentation.
2. Add primary papers or surveys.
3. Inspect repository activity, license, setup, tests, and architecture.
4. Record what is documented versus inferred.
5. Do not treat benchmark or backtest numbers as proof of profitability.
6. Record unresolved questions.
7. Save source URLs and access dates.
8. Prefer small claims with direct evidence over broad claims.
9. Distinguish:
   - documented fact
   - repository claim
   - independent evidence
   - engineering recommendation

## Output

Return:
- executive summary
- comparison table
- evidence notes
- architecture implications
- risks and unknowns
- sources

## Project-specific focus

For trading repositories inspect:
- spread
- slippage
- order lifecycle
- margin
- position accounting
- stop/TP behavior
- data leakage
- walk-forward testing
- holdout usage
- random seeds
- test coverage
- broker integration
