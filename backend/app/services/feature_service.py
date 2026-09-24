import pandas as pd
import pandas_ta as ta

from app.core.exceptions import DataError
from app.core.logging import get_logger

log = get_logger(__name__)

class FeatureService:
    """
    Service for applying technical indicators and feature engineering 
    on market data DataFrames.
    """

    AVAILABLE_FEATURES = {
        "rsi", "macd", "bollinger_bands", "atr", "ema", "sma",
        "stochastic", "obv", "adx"
    }

    @classmethod
    def apply_features(cls, df: pd.DataFrame, features: list[str]) -> pd.DataFrame:
        """
        Apply requested features to the dataframe.
        Expects columns: Open, High, Low, Close, Volume (or lowercase versions).
        """
        if df.empty:
            raise DataError("Cannot apply features to an empty DataFrame.")

        # Ensure column names are standardized for pandas-ta
        # (pandas-ta expects lowercase or uppercase, but standardizing helps)
        # We will map standard names if they exist
        rename_map = {}
        for col in df.columns:
            if col.lower() in ["open", "high", "low", "close", "volume", "tick_volume"]:
                rename_map[col] = col.capitalize()

        df_working = df.rename(columns=rename_map).copy()

        # Verify required columns exist
        required_cols = {"Open", "High", "Low", "Close"}
        missing = required_cols - set(df_working.columns)
        if missing:
            raise DataError(f"Missing required columns for feature engineering: {missing}")

        added_columns = []
        for feature in features:
            f_lower = feature.lower()
            if f_lower not in cls.AVAILABLE_FEATURES:
                log.warning("Unknown feature requested", feature=feature)
                continue

            try:
                # Apply features using pandas-ta
                if f_lower == "rsi":
                    res = df_working.ta.rsi(length=14, append=True)
                    if res is not None: added_columns.extend(res.columns if isinstance(res, pd.DataFrame) else [res.name])
                elif f_lower == "macd":
                    res = df_working.ta.macd(fast=12, slow=26, signal=9, append=True)
                    if res is not None: added_columns.extend(res.columns)
                elif f_lower == "bollinger_bands":
                    res = df_working.ta.bbands(length=20, std=2, append=True)
                    if res is not None: added_columns.extend(res.columns)
                elif f_lower == "atr":
                    res = df_working.ta.atr(length=14, append=True)
                    if res is not None: added_columns.extend(res.columns if isinstance(res, pd.DataFrame) else [res.name])
                elif f_lower == "ema":
                    res = df_working.ta.ema(length=20, append=True)
                    res2 = df_working.ta.ema(length=50, append=True)
                    res3 = df_working.ta.ema(length=200, append=True)
                    # Note: we don't strictly track names of all added columns for now, just logging
                elif f_lower == "sma":
                    res = df_working.ta.sma(length=20, append=True)
                    res2 = df_working.ta.sma(length=50, append=True)
                elif f_lower == "stochastic":
                    res = df_working.ta.stoch(append=True)
                elif f_lower == "obv":
                    if "Volume" in df_working.columns:
                        res = df_working.ta.obv(append=True)
                elif f_lower == "adx":
                    res = df_working.ta.adx(length=14, append=True)
            except Exception as e:
                log.error("Failed to compute feature", feature=feature, error=str(e))
                raise DataError(f"Failed to compute feature {feature}: {e}")

        # Drop NaN values introduced by rolling windows
        df_working.dropna(inplace=True)

        # Reset index if needed, though typically we want to preserve it
        return df_working

    @classmethod
    def get_available_features(cls) -> list[str]:
        return sorted(list(cls.AVAILABLE_FEATURES))
