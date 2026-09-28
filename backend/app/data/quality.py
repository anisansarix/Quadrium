from typing import Literal

from pydantic import BaseModel


class DataQualityReport(BaseModel):
    coverage_status: Literal["FULL", "PARTIAL", "EMPTY"]
    expected_bars: int
    observed_bars: int
    unexpected_missing_bars: int
    known_closure_bars: int
    duplicate_bars: int
    quality_status: Literal["PASS", "WARNING", "FAIL"]
