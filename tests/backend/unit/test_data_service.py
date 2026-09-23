import pytest
from datetime import datetime, timezone
import pandas as pd
from unittest.mock import patch

from app.services.data_service import DataService
from app.core.exceptions import DataError

@pytest.mark.asyncio
async def test_fetch_and_store_invalid_source():
    with pytest.raises(ValueError, match="Unknown data source"):
        await DataService.fetch_and_store(
            symbol="EURUSD",
            timeframe="H1",
            start=datetime(2023, 1, 1, tzinfo=timezone.utc),
            end=datetime(2023, 1, 2, tzinfo=timezone.utc),
            source="unknown"
        )

@pytest.mark.asyncio
@patch("app.services.fetchers.yfinance_fetcher.YFinanceFetcher.fetch_historical_data")
async def test_fetch_and_store_yfinance(mock_fetch):
    # Mock return data
    mock_df = pd.DataFrame({
        "time": [pd.Timestamp("2023-01-01 00:00:00+00:00")],
        "open": [1.05],
        "high": [1.06],
        "low": [1.04],
        "close": [1.055],
        "tick_volume": [100],
        "spread": [0.0],
        "real_volume": [0]
    })
    mock_fetch.return_value = mock_df

    catalog_id = await DataService.fetch_and_store(
        symbol="EURUSD=X",
        timeframe="H1",
        start=datetime(2023, 1, 1, tzinfo=timezone.utc),
        end=datetime(2023, 1, 2, tzinfo=timezone.utc),
        source="yfinance"
    )

    assert catalog_id is not None
    assert type(catalog_id) == str

    # Verify DuckDB has it
    records = DataService.list_raw_data()
    assert len(records) > 0
    assert any(r["id"] == catalog_id for r in records)
