# MT5 Data Acceptance

Initial profile:
- USD account
- EURUSD
- M1
- M5
- read-only

Acceptance requirements:
- account currency USD
- broker/server captured
- symbol metadata captured
- UTC timestamps
- valid OHLC
- no unexpected gaps
- no duplicates
- deterministic dataset hash
- manifest saved
- Parquet saved
- DuckDB catalog registration
- quality report PASS

Note: For production multi-year ingestion, move to partitioned Parquet and streaming merge instead of pd.concat in-memory merge.
