from typing import Literal

from pydantic import BaseModel


class DataQualityReport(BaseModel):
    coverage_status: Literal["FULL", "SPARSE", "PARTIAL", "EMPTY"]
    expected_bars: int
    observed_bars: int
    source_sparse_bars: int
    ticks_present_bar_missing: int
    unexpected_missing_bars: int
    known_closure_bars: int
    duplicate_bars: int
    quality_status: Literal["PASS", "WARNING", "FAIL"]
