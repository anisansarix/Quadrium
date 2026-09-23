"""Custom exception types for Quadrium."""

from __future__ import annotations


class QuadriumError(Exception):
    """Base exception for all Quadrium errors."""

    def __init__(self, message: str, *, detail: str | None = None) -> None:
        super().__init__(message)
        self.detail = detail


class DataError(QuadriumError):
    """Error related to data operations (fetch, parse, store)."""


class DatasetError(QuadriumError):
    """Error related to dataset creation or versioning."""


class TrainingError(QuadriumError):
    """Error related to ML training operations."""


class BacktestError(QuadriumError):
    """Error related to backtesting operations."""


class RiskError(QuadriumError):
    """Error in risk calculation or evaluation."""


class MT5Error(QuadriumError):
    """Error related to MetaTrader 5 integration."""


class MT5ConnectionError(MT5Error):
    """MT5 terminal connection failure."""


class ConfigurationError(QuadriumError):
    """Error in application configuration."""


class ExperimentNotFoundError(QuadriumError):
    """Requested experiment does not exist."""


class StrategyGenerationError(QuadriumError):
    """Error generating Pine Script or MQL5 artifacts."""
