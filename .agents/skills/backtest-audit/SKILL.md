---
name: backtest-audit
description: Audits a trading backtest or RL experiment for leakage, unrealistic fills, overfitting, invalid metrics, and insufficient validation. Use before accepting research results.
---

# Backtest Audit Skill

## Audit sequence

1. Identify exact data windows.
2. Confirm temporal ordering.
3. Confirm feature availability at decision time.
4. Confirm normalization is fit only on allowed data.
5. Confirm transaction costs.
6. Confirm bid/ask treatment.
7. Confirm slippage.
8. Confirm stop/TP semantics.
9. Confirm position sizing.
10. Confirm margin/leverage assumptions.
11. Confirm train/validation/test separation.
12. Confirm walk-forward behavior.
13. Confirm final holdout was not used for tuning.
14. Count experiments and hyperparameter trials.
15. Compare against non-RL baselines.
16. Stress costs and execution assumptions.
17. Check seed sensitivity.
18. Check regime and session sensitivity.

## Hard findings

Flag as blocking:
- lookahead leakage
- final-test tuning
- missing transaction costs when execution costs are material
- live execution directly from research policy
- missing risk constraints
- non-reproducible experiment identity

## Output

Return:
- blocking issues
- material concerns
- minor concerns
- reproducibility status
- recommended reruns
