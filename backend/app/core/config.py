from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    app_name: str = "Quadrium"
    env: str = "RESEARCH"
    
    # SQLite
    sqlite_db_url: str = "sqlite:///./quadrium.db"
    
    # DuckDB
    duckdb_path: str = "./quadrium_analytics.duckdb"
    
    # MT5
    mt5_path: Optional[str] = None
    mt5_login: Optional[int] = None
    mt5_password: Optional[str] = None
    mt5_server: Optional[str] = None
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
