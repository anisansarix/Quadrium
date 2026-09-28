# MT5 Time Translation Model

## Abstract

The official MetaTrader 5 Python API documentation states that functions like copy_rates_range expect and return UTC datetimes. However, empirical testing on the live MetaQuotes-Demo terminal demonstrates that this is not universally true. On our tested broker environment, returned timestamps represent **Broker Server Time**, not UTC, and the Python library implicitly assumes passed datetimes are in the host machine's local timezone.

Quadrium implements an explicit, deterministic Time Translation Layer to fully abstract and correct these behaviors without relying on the local machine's timezone.

## Source Timestamp Semantics

Raw MT5 bar/tick timestamps (e.g. 	ime, 	ime_msc) returned by our tested MetaQuotes-Demo terminal do **not** represent true Unix time (seconds since 1970 UTC). They represent seconds since 1970 **Server Time**. 
- For example, if the server is running at UTC+3 (EEST), the raw integer 1790208000 does not mean 2026-09-24 00:00:00 UTC. It means 2026-09-24 00:00:00 Server Time (which is 2026-09-23 21:00:00 UTC).
- We designate this observed domain as SERVER-OFFSET-LIKE.
- **Note:** Do not assume all MT5 terminals universally use this interpretation. Some broker setups or future MT5 package versions may strictly follow the API documentation. Quadrium handles this variability using explicit profiles.

## Canonical UTC Semantics

Quadrium internally uses strict, timezone-aware UTC timestamps for all indexing, querying, and storage. All dataset manifests, gap reports, and canonical Parquet files express 	ime in absolute UTC.
The raw MT5 artifact strictly preserves the source-faithful timestamp integer (e.g., 	ime and 	ime_msc) alongside metadata identifying the time domain, guaranteeing perfect auditability against the broker response.

## Request Transformation

When requesting historical data (copy_rates_range, copy_ticks_range), the MT5 Python API expects request boundaries formatted as naive datetimes. If timezone-aware datetimes are passed, the API strips the timezone, assumes the naive values represent the host machine's local time, and silently shifts the request before sending integer epochs to the MT5 terminal. 

To eliminate local timezone side-effects:
1. Quadrium receives a canonical UTC [start, end) request.
2. The exact integer Unix epochs for start and end are calculated.
3. The configured profile's offset is **added** to these epochs.
4. The explicitly shifted integers are passed directly into the MT5 API, natively targeting the SERVER_WALLCLOCK_LIKE domain expected by the terminal.

## Return Transformation

When historical data is returned, the raw 	ime integers representing Server Time are saved exactly as-is into the raw artifact. Then, the canonicalization process reads the raw data, subtracts the configured profile's offset from the integers, and produces canonical UTC Unix epochs. These perfectly represent absolute UTC datetimes in the canonical artifact.

## Profile Provenance

Time translation is driven by explicit TimeProfile models (e.g., metaquotes_demo_eurusd_phase1_v1). A profile captures the broker, server, symbol, and an explicit transition schedule of UTC offsets. The specific profile ID and the source_time_basis used to interpret the raw MT5 data are persistently recorded in the Dataset Manifest's source_metadata.

## Current MetaQuotes-Demo Phase-1 Limitation

The MetaQuotes-Demo EURUSD server currently runs at UTC+3 (EEST). We explicitly lock the Phase-1 profile to a static +3.0 hour offset. Because DST transitions historically shift broker offsets (e.g., to UTC+2 in winter), future historical ingestion will require mapping the complete DST schedule within the TimeProfile.

## Why Local Machine Timezone is Never Used

If Quadrium relied on Python's implicit MT5 library localization, backtests run on a server in London (UTC) would yield different data bounds and timestamps than those run by developers in India (UTC+5:30) or New York (UTC-4). The explicit translation layer completely severs this dependency by dealing entirely in mechanical epoch integer arithmetic.

## Session Calendar Calibration

Through empirical validation of the UTC-canonicalized data, we established that the MetaQuotes-Demo EURUSD trading session strictly opens at **Monday 00:00 Server Time** and closes at **Friday 23:59:59 Server Time**.
Under the static UTC+3 profile, this corresponds precisely to **Sunday 21:00 UTC to Friday 21:00 UTC**. The DataCalendar is configured accordingly, resulting in exactly 7,200 expected M1 bars per week.

## Why Old Datasets Are Superseded

All real MT5 datasets ingested prior to the implementation of this Time Translation Layer incorrectly conflated Server Time with true UTC (a 3-hour misalignment). They cannot be reliably used for modeling, feature engineering, or RL training, as aligning them against external real-world UTC data feeds would introduce forward-looking bias or latency.
