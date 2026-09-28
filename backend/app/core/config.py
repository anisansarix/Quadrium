
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Quadrium"
    env: str = "RESEARCH"
    
    # SQLite
    sqlite_db_url: str = "sqlite:///./quadrium.db"
    
    # DuckDB
    duckdb_path: str = "./quadrium_analytics.duckdb"
    
    # MT5
    mt5_path: str | None = None
    mt5_login: int | None = None
    mt5_password: str | None = None
    mt5_server: str | None = None
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
