# EVALUATION_PROTOCOL.md

## Purpose

Prevent accidental leakage, cherry-picking, and over-optimistic backtest interpretation.

## Split policy

Use time-ordered data.

Minimum:
- train
- validation
- final holdout

The final holdout must not influence:
- feature selection
- architecture selection
- reward selection
- hyperparameter choice
- checkpoint selection
- stopping rules

## Walk-forward

For adaptive research, use rolling or anchored walk-forward windows.

Record each fold:
- train start/end
- validation start/end
- test start/end
- model config
- seed
- data fingerprint
- cost assumptions

## Leakage checks

Test for:
- future shifts
- centered indicators
- future-filled missing values
- leakage from scaling
- leakage from reward computation
- event timestamps that were not public at decision time
- lookahead through resampling
- accidental reuse of post-trade information

## Costs

Run every candidate under at least:
- baseline spread
- stressed spread
- baseline slippage
- stressed slippage
- execution delay stress

## Baselines

Every RL experiment must have comparable non-RL baselines using the same simulator and costs.

## Statistical interpretation

Do not treat a high Sharpe alone as evidence of robust edge.

Track:
- number of experiments
- number of trials
- configurations tested
- seeds
- datasets
- evaluation windows

Assess selection bias and backtest overfitting.

Research resources:
- The Probability of Backtest Overfitting
- Deflated Sharpe Ratio
- recent search-adjusted DSR literature

## Acceptance framework

A model is not promoted because it has one strong backtest.

Promotion should require:
- reproducibility
- stability across seeds
- robustness to costs
- acceptable drawdown behavior
- low rule-violation rate
- acceptable degradation from validation to holdout
- clear audit trail
- successful paper/demo execution where applicable

## Required result artifact

Each evaluation should write:

```text
results/
  experiment_id/
    config.yaml
    metrics.json
    trades.parquet
    equity.parquet
    diagnostics.json
    charts/
    model/
    manifest.json
```

`manifest.json` should include:
- git SHA
- dataset hash
- config hash
- environment version
- Python version
- dependency lock reference
- seed
- evaluation windows
- simulator settings
