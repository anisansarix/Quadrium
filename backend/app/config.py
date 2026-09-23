"""Application configuration loaded from TOML files and environment variables."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve project root (two levels up from this file: backend/app/config.py → project root)
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _BACKEND_DIR.parent


def _load_toml(path: Path) -> dict[str, Any]:
    """Load a TOML file and return its contents as a dict."""
    if not path.exists():
        return {}
    with open(path, "rb") as f:
        return tomllib.load(f)


class APISettings(BaseSettings):
    """API server configuration."""

    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: list[str] = ["http://localhost:5173"]
    docs_enabled: bool = True


class DatabaseSettings(BaseSettings):
    """Database paths configuration."""

    sqlite_path: str = "data/quadrium.db"
    duckdb_path: str = "data/quadrium_analytics.duckdb"

    def get_sqlite_url(self) -> str:
        """Get full SQLite connection URL."""
        abs_path = _PROJECT_ROOT / self.sqlite_path
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite+aiosqlite:///{abs_path}"

    def get_duckdb_path(self) -> Path:
        """Get absolute DuckDB file path."""
        abs_path = _PROJECT_ROOT / self.duckdb_path
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        return abs_path


class GPUSettings(BaseSettings):
    """GPU/CUDA configuration tuned for RTX 3050 Laptop (4GB VRAM)."""

    device: str = "auto"  # "auto", "cuda", "cpu"
    mixed_precision: bool = True
    pin_memory: bool = True
    num_workers: int = 4


class TrainingSettings(BaseSettings):
    """Default ML training configuration."""

    default_batch_size: int = 32
    default_learning_rate: float = 0.0003
    default_total_timesteps: int = 100_000
    replay_buffer_device: str = "cpu"
    gradient_checkpointing: bool = False


class MT5Settings(BaseSettings):
    """MetaTrader 5 integration configuration."""

    model_config = SettingsConfigDict(env_prefix="MT5_")

    enabled: bool = False
    login: str = ""
    password: str = ""
    server: str = ""
    path: str = r"C:\Program Files\MetaTrader 5\terminal64.exe"
    account_type: str = "demo"
    connection_timeout_seconds: int = 10
    retry_attempts: int = 3
    retry_delay_seconds: int = 5
    circuit_breaker_threshold: int = 3
    circuit_breaker_recovery_seconds: int = 60


class Settings(BaseSettings):
    """Root application settings, combining all sub-configs."""

    model_config = SettingsConfigDict(
        env_prefix="QUADRIUM_",
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App metadata
    app_name: str = "Quadrium"
    version: str = "0.1.0"
    env: str = "development"
    log_level: str = "INFO"

    # Sub-configurations
    api: APISettings = Field(default_factory=APISettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    gpu: GPUSettings = Field(default_factory=GPUSettings)
    training: TrainingSettings = Field(default_factory=TrainingSettings)
    mt5: MT5Settings = Field(default_factory=MT5Settings)

    # Paths (relative to project root)
    data_raw_dir: str = "data/raw"
    data_processed_dir: str = "data/processed"
    models_dir: str = "models"
    strategies_dir: str = "strategies"
    logs_dir: str = "logs"
    config_dir: str = "config"

    @property
    def project_root(self) -> Path:
        return _PROJECT_ROOT

    def resolve_path(self, relative: str) -> Path:
        """Resolve a config-relative path to an absolute path."""
        return _PROJECT_ROOT / relative


def load_settings() -> Settings:
    """Load and return application settings."""
    # Load TOML defaults first (future: merge TOML values into Settings)
    config_path = _PROJECT_ROOT / "config" / "default.toml"
    _toml_defaults = _load_toml(config_path)

    # Pydantic settings reads from env vars and .env file
    return Settings()


# Singleton-style access (created on first import of the module)
settings = load_settings()
