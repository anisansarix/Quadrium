# RESEARCH_MAP.md

## Core platforms

### gym-mtsim
MetaTrader 5 simulator plus Gym environment. Useful as a reference for MT5-style trading mechanics and a possible simulator foundation.

https://github.com/AminHP/gym-mtsim

### TradeMaster
RL-oriented quantitative trading platform with market simulators, preprocessing, multiple RL algorithms, evaluation, and an FX tutorial.

https://github.com/TradeMaster-NTU/TradeMaster

### FinRL
Original FinRL research/education framework. The repository now points production-focused work toward FinRL-X / FinRL-Trading.

https://github.com/AI4Finance-Foundation/FinRL
https://github.com/AI4Finance-Foundation/FinRL-Trading

### IvanKolesn/rl_trading
FX-focused Gymnasium + Ray RLlib research environment with transaction fees and stochastic slippage.

https://github.com/IvanKolesn/rl_trading

### mt5-rl-trader
Practical MT5 + Gymnasium + Stable-Baselines3 reference project with a custom simulator.

https://github.com/DanNgobe/mt5-rl-trader

### Reinforcement-Learning-for-Gold-Trading
XAUUSD-focused PPO research example.

https://github.com/JonusNattapong/Reinforcement-Learning-for-Gold-Trading

### DRL-XAUUSD-Bot
XAUUSD SAC project with walk-forward training and an MT5 execution bridge.

https://github.com/kennycornellius-collab/DRL-XAUUSD-Bot

### Reinforcement_Trading_Part_2
Useful XAUUSD research reference emphasizing walk-forward testing, sealed holdout evaluation, pessimistic SL/TP ordering, and risk-based sizing.

https://github.com/ZiadFrancis/Reinforcement_Trading_Part_2

## Official execution and environment docs

### MetaTrader 5 Python integration
https://www.mql5.com/en/docs/python_metatrader5

### order_send
https://www.mql5.com/en/docs/python_metatrader5/mt5ordersend_py

### copy_rates_from_pos
https://www.mql5.com/en/docs/python_metatrader5/mt5copyratesfrompos_py

### Gymnasium custom environments
https://gymnasium.farama.org/main/tutorials/environment_creation/

### Gymnasium third-party environments
https://gymnasium.farama.org/main/environments/third_party_environments/

### Stable-Baselines3
https://stable-baselines3.readthedocs.io/

### Ray RLlib
https://docs.ray.io/en/latest/rllib/

## Research and backtesting infrastructure

### Optuna
Hyperparameter optimization and pruning.

https://optuna.readthedocs.io/en/stable/

### MLflow
Experiment tracking, artifact logging, and model registry.

https://mlflow.org/docs/latest/ml/tracking
https://mlflow.org/docs/latest/ml/model-registry/

### DVC
Data and pipeline versioning.

https://dvc.org/doc

### Great Expectations
Data validation and expectations.

https://docs.greatexpectations.io/

### Evidently
ML/data evaluation and monitoring.

https://docs.evidentlyai.com/

### Hydra
Hierarchical configuration and multi-run job management.

https://hydra.cc/docs/intro/

### VectorBT
Fast vectorized portfolio simulation and analysis. Useful for baselines and exploratory research, not a substitute for the MT5-oriented execution simulator.

https://vectorbt.dev/
https://vectorbt.pro/

### QuantConnect LEAN
Event-driven backtesting and live-trading engine, useful as an architecture reference.

https://github.com/QuantConnect/Lean

## Antigravity

### IDE
https://antigravity.google/docs/ide/overview/

### Agent
https://antigravity.google/docs/agent

### Rules
https://antigravity.google/docs/rules/

### Agent Skills
https://antigravity.google/docs/skills

### MCP
https://antigravity.google/docs/mcp

### Workflows to Skills migration
https://antigravity.google/docs/migration/workflows-to-skills/

### Official Google skills repository
https://github.com/google/skills

## NotebookLM / Gemini Notebook

NotebookLM was renamed Gemini Notebook in July 2026, while remaining a standalone research product.

https://blog.google/innovation-and-ai/products/gemini-notebook/notebooklm-gemini-notebook/

Research improvements and source-grounded web research:
https://blog.google/innovation-and-ai/products/notebooklm/better-research-notebooklm/

Discover Sources:
https://blog.google/innovation-and-ai/models-and-research/google-labs/notebooklm-discover-sources/

Deep Research:
https://blog.google/innovation-and-ai/models-and-research/google-labs/notebooklm-deep-research-file-types/

## Research quality and overfitting

### Deflated Sharpe Ratio
https://doi.org/10.2139/ssrn.2460551

### Search-adjusted DSR, 2026 working paper
https://doi.org/10.2139/ssrn.7198158

### Probability of Backtest Overfitting
https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf

### RL survey
https://arxiv.org/abs/2106.00123

### Recent advances in RL in finance
https://arxiv.org/abs/2112.04553

### Critical survey of DRL for trading
https://doi.org/10.3390/data6110119

### Recent quantitative finance RL survey
https://doi.org/10.1145/3733714
