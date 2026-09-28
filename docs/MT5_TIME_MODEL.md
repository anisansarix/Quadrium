# MT5 Time Translation Model

## Abstract

The MetaTrader 5 Python API behaves non-standardly concerning time zones, particularly when converting request parameters and interpreting returned data from broker servers. Quadrium implements an explicit, deterministic Time Translation Layer to fully abstract and correct these behaviors without relying on the local machine's timezone.

## Source Timestamp Semantics

Raw MT5 bar/tick timestamps (e.g. 	ime, 	ime_msc) do **not** represent true Unix time (seconds since 1970 UTC). They represent seconds since 1970 **Server Time**. 
- If a server is running at UTC+3 (EEST), the raw integer 1790208000 does not mean 2026-09-24 00:00:00 UTC. It means 2026-09-24 00:00:00 Server Time (which is 2026-09-23 21:00:00 UTC).
- We designate this domain as SERVER-OFFSET-LIKE.

## Canonical UTC Semantics

Quadrium internally uses strict, timezone-aware UTC timestamps for all indexing, querying, and storage. All dataset manifests, gap reports, and canonical Parquet files express 	ime in absolute UTC.

## Request Transformation

When requesting historical data (copy_rates_range, copy_ticks_range), the MT5 Python API expects request boundaries formatted as naive datetimes. However, if timezone-aware datetimes are passed, the API strips the timezone, assumes the naive values represent the host machine's local time, and silently shifts the request before sending integer epochs to the MT5 terminal. 

To eliminate local timezone side-effects:
1. Quadrium receives a canonical UTC [start, end) request.
2. The exact integer Unix epochs for start and end are calculated.
3. The configured profile's offset is **added** to these epochs.
4. The explicitly shifted integers are passed directly into the MT5 API, natively targeting the SERVER_WALLCLOCK_LIKE domain expected by the terminal.

## Return Transformation

When historical data is returned, the raw 	ime integers representing Server Time are parsed. The configured profile's offset is **subtracted** from the integers. The resulting integers perfectly represent canonical UTC Unix epochs, which are then natively converted to Pandas UTC datetimes.

## Profile Provenance

Time translation is driven by explicit TimeProfile models (e.g., metaquotes_demo_eurusd_phase1_v1). A profile captures the broker, server, symbol, and an explicit transition schedule of UTC offsets. The specific profile ID and the source_time_basis used to interpret the raw MT5 data are persistently recorded in the Dataset Manifest's source_metadata.

## Current MetaQuotes-Demo Phase-1 Limitation

The MetaQuotes-Demo EURUSD server currently runs at UTC+3 (EEST). We explicitly lock the Phase-1 profile to a static +3.0 hour offset. Because DST transitions historically shift broker offsets (e.g., to UTC+2 in winter), future historical ingestion will require mapping the complete DST schedule within the TimeProfile.

## Why Local Machine Timezone is Never Used

If Quadrium relied on Python's implicit MT5 library localization, backtests run on a server in London (UTC) would yield different data bounds and timestamps than those run by developers in India (UTC+5:30) or New York (UTC-4). The explicit translation layer completely severs this dependency by dealing entirely in mechanical epoch integer arithmetic.

## Why Old Datasets Are Superseded

All real MT5 datasets ingested prior to the implementation of this Time Translation Layer incorrectly conflated Server Time with true UTC (a 3-hour misalignment). They cannot be reliably used for modeling, feature engineering, or RL training, as aligning them against external real-world UTC data feeds would introduce forward-looking bias or latency.
