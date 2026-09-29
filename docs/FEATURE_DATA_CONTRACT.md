# Canonical Feature/Data Contract

## 1. Input: Canonical Market Data Schema
All features MUST be derived from the strictly defined canonical market data representation.
The input canonical dataset MUST contain exactly the following fields:
* 	imestamp (timezone-aware UTC, referencing the start of the bar)
* symbol (string)
* 	imeframe (string, e.g., "M1")
* open (float)
* high (float)
* low (float)
* close (float)
* 	ick_volume (integer)
* spread (integer, in instrument points)
*
eal_volume (integer)

Missing canonical fields MUST cause processing to fail closed. Silent assumption of defaults (e.g. timeframe = M1) is PROHIBITED.

## 2. Output: Feature Dataset Schema
A feature dataset MUST NOT be merely a pandas DataFrame of numerical columns. It MUST contain:
* 	imestamp (timezone-aware UTC, matching the canonical input bar start)
* symbol (string)
* 	imeframe (string)
* data_state (string Enum: OBSERVED, SOURCE_SPARSE, INVALID)
* eature_state (string Enum: VALID, WARMUP, INVALID)
* eature_columns (one or more strictly named numerical/categorical columns)

Additionally, the dataset generation must produce a FeatureManifest containing lineage metadata:
* eature_dataset_id (string)
* source_dataset_hash (string, SHA-256 of the canonical input dataset)
* symbol (string)
* source_timeframe (string)
* eature_timeframe (string)
* eature_schema_version (string)
* 	ransformation_version (string)
* configuration_version (string)
* eature_fingerprint (string, SHA-256 of the resulting feature dataset)
* 	imestamp_start (datetime UTC)
* 	imestamp_end (datetime UTC)
*
ow_count (integer)
* created_at (datetime UTC)
* eature_columns (list of strings)

## 3. Observation Timing & Causality Contract
**Rule:** No feature may use information from a bar that would not have been known at the decision timestamp.

**Timestamp Convention:**
In the Quadrium canonical schema (inherited from MT5), 	imestamp represents the exact open/start time of the bar. For a timeframe of duration delta (e.g., 1 minute for M1), the bar spans [timestamp, timestamp + delta).

**Observation Availability:**
A bar is considered fully closed, and its OHLCV data becomes finalized and observable, exactly at 	imestamp + delta.
Therefore, features derived from the bar at 	imestamp become observable at 	imestamp + delta.
The exact action timestamp associated with that observation is 	imestamp + delta.

**Example:**
* 10:00:00 UTC : An M1 bar opens (its canonical 	imestamp is 10:00:00 UTC).
* 10:01:00 UTC : The M1 bar closes. Its OHLCV becomes finalized.
* 10:01:00 UTC : Features for the 10:00:00 UTC row are computed and become observable.
* 10:01:00 UTC : Action decision is made using these features.

## 4. UTC Enforcement
All timestamps MUST be explicitly timezone-aware UTC.
* Naive timestamps must immediately fail closed.
* Silent repairs using 	z_localize("UTC") during feature computation or fingerprinting are PROHIBITED.
* Incoming timestamps that are aware but not UTC must be explicitly normalized using 	z_convert("UTC").

## 5. Missingness & Validity Semantics
Data falls into distinct deterministic categories representing the underlying source data (data_state):
* **OBSERVED**: A true canonical bar exists with 	ick_volume > 0.
* **SOURCE_SPARSE**: The broker provided a valid bar but it contains 0 ticks (	ick_volume == 0). These are true zero-volume market states.
* **INVALID**: An aggregated bar that is incomplete or corrupted.

**Missing-Row Semantics:**
A missing canonical bar does NOT have a dataframe row. It is conceptually absent.
A missing interval is explicitly detected when the timestamp difference between two consecutive rows exceeds the strict canonical timeframe duration (e.g. > 1 minute for M1).
A timestamp gap marks a break in contiguity.

**Session Boundaries vs Unexpected Gaps:**
Gaps are resolved into two distinct conceptual buckets by querying the calendar:
1. **Expected Session Closure:** e.g., Friday close to Monday open. This is a normal break in trading.
2. **Unexpected Missing Data:** An internal gap during an active trading session.

Regardless of the type of gap, rolling features MUST NOT aggregate or look back across the boundary.

**Validity Rule across Gaps (eature_state):**
Rolling features MUST NOT become valid merely because a pandas rolling window reaches N rows if the underlying dataframe contains a gap. Any timestamp gap within the lookback window MUST invalidate the feature computation (eature_state = INVALID, output NaN) until a contiguous block of N valid rows (OBSERVED or SOURCE_SPARSE) is re-established.

## 6. Warm-up Semantics
Every rolling feature MUST define a finite warm-up period.
* During warm-up, the specific feature value MUST be NaN.
* The row's eature_state MUST be WARMUP.
* Warm-up values MUST NOT be forward-filled or extrapolated.
* WARMUP is semantically distinct from INVALID. A row may have data_state = OBSERVED (good market data) but eature_state = WARMUP because the rolling historical lookback is incomplete (e.g. first 20 bars of a session).

## 7. Scaling & Normalization Contract
Global normalization across the entire dataset is PROHIBITED.
Any statistical transformation (z-score, quantiles, clipping bounds, running mean/std) MUST be fitted ONLY on the explicitly designated training interval.
Validation/test/holdout data MUST be transformed using exclusively the static parameters learned from the training data. The feature pipeline MUST support serializing and loading these fitted parameters.

## 8. Timeframe & Resampling Policy
Canonical timeframes are deterministically represented as M1, M5, M15, H1.
Pandas rule strings (e.g., 5min) MUST be mapped to these explicit labels.
Resampling MUST reject unknown timeframes, target timeframes shorter than the source, or target timeframes not an integer multiple of the source.

Future model timeframes (e.g., M5, M15, H1) will be **deterministic resamples** derived exclusively from the validated M1 foundation.

**Aggregation Contract:**
* open = first underlying open
* high = max of underlying highs
* low = min of underlying lows
* close = last underlying close
* 	ick_volume = sum of underlying tick_volumes
*
eal_volume = sum of underlying real_volumes (0 if not semantically provided)
* spread = max of underlying spreads (Conservative policy: assumes worst-case execution cost over the resampled interval)

**Incomplete Bar Policy:**
An aggregated bar MUST contain the exact expected number of underlying canonical bars (e.g., 5 M1 bars for an M5 bar).
If the bucket is incomplete (due to session open/close or internal gaps), the resulting bar is marked INVALID (data_state = INVALID) and cannot be treated as a complete observation. It MUST NOT be silently emitted as a complete bar.

**Session Boundary Policy:**
Cross-session aggregation is PROHIBITED. A resampled bar MUST NOT bridge a weekend, a designated session closure, or a non-trading interval.

## 9. Initial Feature Set (Phase 2 Baseline)
The initial feature set is restricted to a small causal baseline:
1.
et_1 (Log return over 1 period, warmup: 1)
2.
et_simple (Simple return over 1 period, warmup: 1)
3.
ange_pct ((High - Low) / Open, warmup: 0)
4. 	r (True Range, warmup: 1)
5. ol_20 (Rolling volatility, 20-period standard deviation of
et_1, warmup: 20 periods of
et_1 -> 21 bars)
6. dist_ma_20 (Normalized distance from 20-period moving average, warmup: 20)
7. 	ick_vol_change (Rate of change of tick volume, warmup: 1)
8. spread (Current bar spread, warmup: 0)
9. spread_delta (Change in spread from prior bar, warmup: 1)
