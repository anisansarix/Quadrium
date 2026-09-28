---
name: experiment-run
description: Runs a reproducible trading experiment with versioned data, configuration, seed, MLflow tracking, and evaluation artifacts. Use for RL or baseline experiments.
---

# Experiment Run Skill

## Before running

Confirm:
- dataset identity
- train/validation/test windows
- simulator configuration
- risk policy
- feature configuration
- algorithm
- hyperparameters
- seed

## Run

1. Validate data.
2. Validate environment.
3. Run baseline sanity check.
4. Train.
5. Evaluate on validation.
6. Record artifacts.
7. Do not touch final holdout unless this is an explicitly designated final evaluation.

## Track

Log:
- code SHA
- dataset hash
- config
- seed
- algorithm
- total timesteps
- environment version
- simulator costs
- risk policy ID
- metrics
- model artifact

## After run

Save:
- metrics
- trade ledger
- equity curve
- drawdown
- diagnostics
- configuration
- model
- experiment manifest

Never report a result without the corresponding experiment identity.
