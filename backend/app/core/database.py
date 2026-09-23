"""Core database management — SQLite (OLTP) and DuckDB (OLAP)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import duckdb
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

# SQLAlchemy naming conventions for consistent constraint names
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=convention)

# --- SQLite (transactional state) ---

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Get or create the SQLite async engine."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.database.get_sqlite_url(),
            echo=(settings.env == "development"),
            pool_pre_ping=True,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create the async session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async database session with automatic cleanup."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_sqlite() -> None:
    """Initialize SQLite database and create all tables."""
    from app.models.db import Base  # noqa: F811 — deferred to avoid circular imports

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_sqlite() -> None:
    """Close the SQLite engine."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None


# --- DuckDB (analytics) ---

_duckdb_conn: duckdb.DuckDBPyConnection | None = None


def get_duckdb() -> duckdb.DuckDBPyConnection:
    """Get or create the DuckDB connection (single-writer)."""
    global _duckdb_conn
    if _duckdb_conn is None:
        db_path = settings.database.get_duckdb_path()
        _duckdb_conn = duckdb.connect(str(db_path))
        _init_duckdb_schema(_duckdb_conn)
    return _duckdb_conn


def _init_duckdb_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Create DuckDB analytics tables if they don't exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS market_data_catalog (
            id              VARCHAR PRIMARY KEY,
            instrument      VARCHAR NOT NULL,
            timeframe       VARCHAR NOT NULL,
            date_start      DATE NOT NULL,
            date_end        DATE NOT NULL,
            row_count       INTEGER NOT NULL,
            file_path       VARCHAR NOT NULL,
            file_hash       VARCHAR,
            fetched_at      TIMESTAMP DEFAULT current_timestamp,
            source          VARCHAR DEFAULT 'mt5'
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS dataset_catalog (
            id              VARCHAR PRIMARY KEY,
            version         VARCHAR NOT NULL,
            features        VARCHAR NOT NULL, /* JSON string of features */
            date_start      DATE NOT NULL,
            date_end        DATE NOT NULL,
            instrument      VARCHAR NOT NULL,
            timeframe       VARCHAR NOT NULL,
            parent_raw_id   VARCHAR NOT NULL,
            row_count       INTEGER NOT NULL,
            file_path       VARCHAR NOT NULL,
            created_at      TIMESTAMP DEFAULT current_timestamp
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS backtest_trades (
            id              VARCHAR PRIMARY KEY,
            backtest_id     VARCHAR NOT NULL,
            experiment_id   VARCHAR NOT NULL,
            instrument      VARCHAR NOT NULL,
            direction       VARCHAR NOT NULL,
            entry_time      TIMESTAMP NOT NULL,
            exit_time       TIMESTAMP,
            entry_price     DOUBLE NOT NULL,
            exit_price      DOUBLE,
            lot_size        DOUBLE NOT NULL,
            pnl             DOUBLE,
            commission      DOUBLE DEFAULT 0,
            swap            DOUBLE DEFAULT 0,
            status          VARCHAR DEFAULT 'open'
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS backtest_equity (
            backtest_id     VARCHAR NOT NULL,
            timestamp       TIMESTAMP NOT NULL,
            balance         DOUBLE NOT NULL,
            equity          DOUBLE NOT NULL,
            drawdown_pct    DOUBLE DEFAULT 0,
            PRIMARY KEY (backtest_id, timestamp)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS backtest_metrics (
            id              VARCHAR PRIMARY KEY,
            backtest_id     VARCHAR NOT NULL,
            experiment_id   VARCHAR NOT NULL,
            total_trades    INTEGER,
            win_rate        DOUBLE,
            profit_factor   DOUBLE,
            sharpe_ratio    DOUBLE,
            sortino_ratio   DOUBLE,
            max_drawdown    DOUBLE,
            max_daily_loss  DOUBLE,
            net_profit      DOUBLE,
            expectancy      DOUBLE,
            avg_r           DOUBLE,
            max_consec_loss INTEGER,
            recovery_factor DOUBLE,
            calculated_at   TIMESTAMP DEFAULT current_timestamp
        )
    """)


def close_duckdb() -> None:
    """Close the DuckDB connection."""
    global _duckdb_conn
    if _duckdb_conn is not None:
        _duckdb_conn.close()
        _duckdb_conn = None
