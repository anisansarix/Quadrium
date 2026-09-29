# Gym Environment Contract (Phase 3)

## 3.1 Environment Boundary
The QuadriumEnv wraps the deterministic PolicySimulator and DeterministicRiskEngine.
It adheres strictly to the gymnasium.Env interface, mapping canonical market data into vectors and routing model actions down into the risk/simulator layers.

## 3.2 Action Space
Continuous target exposure space:
Box(low=-1.0, high=1.0, shape=(1,), dtype=np.float32)
The single float controls the absolute normalized target weight applied via the risk engine to the simulator.

## 3.3 Observation Space
Vectorized space capturing strictly the causal feature values emitted by the simulator state corresponding to the latest resolved market bar. Future feature values and execution-bar bounds are strictly obscured.
Shape: (len(feature_cols),)

## 3.4 Warmup Behavior
Initial rows labeled FeatureState.WARMUP do not generate stepping actions or observations for the agent. The environment implicitly advances the simulator through the warmup span during eset(), stopping exactly at the first valid action-taking sequence.

## 3.5 Invalid Data Behavior
When a step encounters FeatureState.INVALID, the environment blocks action passing, allows the simulator to execute its deterministic flatten response, and promptly yields 	erminated=True accompanied by info['reason'] = 'INVALID_DATA'.

## 3.6 Reset
eset(seed=...) deterministically restores the observation index and purges simulator balances to original initialization. Seeding is natively respected where Gym standards apply, yet does not induce synthetic noise into the underlying data engine.

## 3.7 Termination
- **Terminated**: True upon END_OF_DATA or INVALID_DATA.
- **Truncated**: False (reserved for explicit time-limit horizons externally).
