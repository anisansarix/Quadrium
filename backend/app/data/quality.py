from typing import Literal

from pydantic import BaseModel


class DataQualityReport(BaseModel):
    coverage_status: Literal["FULL", "PARTIAL", "EMPTY"]
    expected_bars: int
    observed_bars: int
    unexpected_missing_bars: int
    known_closure_bars: int
    duplicate_bars: int
    # invalid_rows is 0 here because invalid rows (schema/OHLC errors) are precondition failures
    # that cause validation to throw before reaching DatasetArtifact generation.
    invalid_rows: int
    quality_status: Literal["PASS", "WARNING", "FAIL"]
