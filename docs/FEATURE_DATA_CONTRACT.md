# Canonical Feature/Data Contract

## 1. Input: Canonical Market Data Schema
All features MUST be derived from the strictly defined canonical market data representation. 
The input canonical dataset MUST contain exactly the following fields:
* `timestamp` (timezone-aware UTC, referencing the start of the bar)
* `symbol` (string)
* `timeframe` (string, e.g., "M1")
* `open` (float)
* `high` (float)
* `low` (float)
* `close` (float)
* `tick_volume` (integer)
* `spread` (integer, in instrument points)
* `real_volume` (integer)

## 2. Output: Feature Dataset Schema
A feature dataset MUST NOT be merely a pandas DataFrame of numerical columns. It MUST contain:
* `timestamp` (timezone-aware UTC, matching the canonical input bar start)
* `symbol` (string)
* `timeframe` (string)
* `data_state` (string Enum: `OBSERVED`, `SOURCE_SPARSE`, `INVALID`)
* `is_valid` (boolean column indicating if the row's features are fully valid and warm-up is complete)
* `feature_columns` (one or more strictly named numerical/categorical columns)

Additionally, the dataset generation must produce a FeatureManifest containing lineage metadata:
* `feature_dataset_id` (string)
* `source_dataset_hash` (string, SHA-256 of the canonical input dataset)
* `symbol` (string)
* `source_timeframe` (string)
* `feature_timeframe` (string)
* `feature_schema_version` (string)
* `transformation_version` (string)
* `configuration_version` (string)
* `feature_fingerprint` (string, SHA-256 of the resulting feature dataset)
* `timestamp_start` (datetime UTC)
* `timestamp_end` (datetime UTC)
* `row_count` (integer)
* `created_at` (datetime UTC)
* `feature_columns` (list of strings)

## 3. Observation Timing & Causality Contract
**Rule:** No feature may use information from a bar that would not have been known at the decision timestamp.

**Timestamp Convention:** 
In the Quadrium canonical schema (inherited from MT5), `timestamp` represents the exact open/start time of the bar. For a timeframe of duration `delta` (e.g., 1 minute for M1), the bar spans `[timestamp, timestamp + delta)`.

**Observation Availability:** 
A bar is considered fully closed, and its OHLCV data becomes finalized and observable, exactly at `timestamp + delta`. 
Therefore, features derived from the bar at `timestamp` become observable at `timestamp + delta`.
The exact action timestamp associated with that observation is `timestamp + delta`.

**Example:**
* `10:00:00 UTC` : An M1 bar opens (its canonical `timestamp` is `10:00:00 UTC`).
* `10:01:00 UTC` : The M1 bar closes. Its OHLCV becomes finalized.
* `10:01:00 UTC` : Features for the `10:00:00 UTC` row are computed and become observable.
* `10:01:00 UTC` : Action decision is made using these features.

## 4. UTC Enforcement
All timestamps MUST be explicitly timezone-aware UTC.
* Naive timestamps must immediately fail closed.
* Silent repairs using `tz_localize("UTC")` during feature computation or fingerprinting are PROHIBITED. 
* Incoming timestamps that are aware but not UTC must be explicitly normalized using `tz_convert("UTC")`.

## 5. Missingness & Validity Semantics
Data falls into distinct deterministic categories represented in `data_state`:
* **`OBSERVED`**: A true canonical bar exists with `tick_volume > 0`.
* **`SOURCE_SPARSE`**: The broker provided a valid bar but it contains 0 ticks (`tick_volume == 0`). These are true zero-volume market states.
* **`INVALID`**: A gap in canonical timestamps exists (missing bars) or the data is mathematically corrupt.

**Validity Rule across Gaps (`is_valid`):**
Rolling features MUST NOT become valid merely because a pandas rolling window reaches `N` rows if the underlying timeframe contains an `INVALID` gap. If a feature requires `N` prior bars, any `INVALID` gap within the lookback window MUST invalidate the feature computation (`is_valid = False` and outputs `NaN`) until a contiguous block of `N` valid bars (`OBSERVED` or `SOURCE_SPARSE`) is re-established.
Blind forward-filling of missing observations is strictly prohibited.

## 6. Warm-up Semantics
Every rolling feature MUST define a finite warm-up period.
* During warm-up, the specific feature value MUST be `NaN`.
* The row's `is_valid` MUST be `False`.
* Warm-up values MUST NOT be forward-filled or extrapolated.
* `WARMUP` is semantically distinct from `INVALID`. A row may be `OBSERVED` (good market data) but still have `is_valid = False` because the warm-up lookback is incomplete.

## 7. Scaling & Normalization Contract
Global normalization across the entire dataset is PROHIBITED.
Any statistical transformation (z-score, quantiles, clipping bounds, running mean/std) MUST be fitted ONLY on the explicitly designated training interval. 
Validation/test/holdout data MUST be transformed using exclusively the static parameters learned from the training data. The feature pipeline MUST support serializing and loading these fitted parameters.

## 8. Timeframe & Resampling Policy
Canonical timeframes are deterministically represented as `M1`, `M5`, `M15`, `H1`. 
Pandas rule strings (e.g., `5min`) MUST be mapped to these explicit labels.

Future model timeframes (e.g., M5, M15, H1) will be **deterministic resamples** derived exclusively from the validated M1 foundation.

**Aggregation Contract:**
* `open` = first underlying open
* `high` = max of underlying highs
* `low` = min of underlying lows
* `close` = last underlying close
* `tick_volume` = sum of underlying tick_volumes
* `real_volume` = sum of underlying real_volumes (0 if not semantically provided)
* `spread` = max of underlying spreads (Conservative policy: assumes worst-case execution cost over the resampled interval)

**Incomplete Bar Policy:**
An aggregated bar MUST contain the exact expected number of underlying canonical bars (e.g., 5 M1 bars for an M5 bar).
If the bucket is incomplete (due to session open/close or internal gaps), the resulting bar is marked `INVALID` (`data_state = INVALID`) and cannot be treated as a complete observation. It MUST NOT be silently emitted as a complete bar.

**Session Boundary Policy:**
Cross-session aggregation is PROHIBITED. A resampled bar MUST NOT bridge a weekend, a designated session closure, or a non-trading interval.

## 9. Initial Feature Set (Phase 2 Baseline)
The initial feature set is restricted to a small causal baseline:
1. `ret_1` (Log return over 1 period, warmup: 1)
2. `ret_simple` (Simple return over 1 period, warmup: 1)
3. `range_pct` ((High - Low) / Open, warmup: 0)
4. `tr` (True Range, warmup: 1)
5. `vol_20` (Rolling volatility, 20-period standard deviation of `ret_1`, warmup: 20 periods of `ret_1` -> 21 bars)
6. `dist_ma_20` (Normalized distance from 20-period moving average, warmup: 20)
7. `tick_vol_change` (Rate of change of tick volume, warmup: 1)
8. `spread` (Current bar spread, warmup: 0)
9. `spread_delta` (Change in spread from prior bar, warmup: 1)
