import pytest
from datetime import datetime, timezone
import pandas as pd
from unittest.mock import patch
from pathlib import Path

from app.services.data_service import DataService
from app.services.dataset_service import DatasetService
from app.core.exceptions import DataError
from app.config import settings

@pytest.mark.asyncio
@patch("app.services.fetchers.yfinance_fetcher.YFinanceFetcher.fetch_historical_data")
async def test_create_and_list_dataset(mock_fetch):
    # Mock return data large enough to drop NaNs for indicators
    dates = pd.date_range("2023-01-01", periods=100, freq="h")
    import numpy as np
    np.random.seed(42)
    mock_df = pd.DataFrame({
        "time": dates,
        "open": np.random.uniform(1.0, 1.1, 100),
        "high": np.random.uniform(1.05, 1.15, 100),
        "low": np.random.uniform(0.95, 1.05, 100),
        "close": np.random.uniform(1.0, 1.1, 100),
        "tick_volume": np.random.randint(100, 1000, 100)
    })
    mock_fetch.return_value = mock_df

    # First fetch raw data
    raw_id = await DataService.fetch_and_store(
        symbol="EURUSD=X",
        timeframe="H1",
        start=datetime(2023, 1, 1, tzinfo=timezone.utc),
        end=datetime(2023, 1, 5, tzinfo=timezone.utc),
        source="yfinance"
    )

    # Create dataset
    features = ["rsi", "sma"]
    dataset_id = DatasetService.create_dataset(
        raw_data_id=raw_id,
        version="v1.0",
        features=features
    )

    assert dataset_id is not None
    
    # List datasets
    datasets = DatasetService.list_datasets()
    assert len(datasets) > 0
    assert any(d["id"] == dataset_id for d in datasets)
    
    # Get specific dataset
    dataset = DatasetService.get_dataset(dataset_id)
    assert dataset["id"] == dataset_id
    assert dataset["version"] == "v1.0"
    assert "rsi" in dataset["features"]
    assert dataset["row_count"] < 100  # Some rows dropped due to NaN
    
    # Clean up (optional for test database if it's isolated, but good practice)
    processed_file = settings.resolve_path("data") / dataset["file_path"]
    assert processed_file.exists()
