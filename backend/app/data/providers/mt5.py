from datetime import UTC, datetime

import pandas as pd

from app.data.providers.base import CapabilityMetadata, DataProvider
from app.data.providers.mt5_client import MT5Client, RealMT5Client
from app.data.time_profile import mt5_label_to_utc, utc_to_mt5_label
from app.domain.models import InstrumentSpec


class MT5Capabilities(CapabilityMetadata):
    bid_ask = True
    spread = True
    tick_data = True
    real_volume = True
    broker_metadata = True
    execution_metadata = True
    suitable_for_execution_backtest = False

class MT5Error(Exception):
    pass

class MT5Provider(DataProvider):
    def __init__(self, 
                 path: str | None = None, 
                 login: int | None = None, 
                 password: str | None = None, 
                 server: str | None = None,
                 timeout: int = 60000,
                 client: MT5Client | None = None,
                 symbol_map: dict[str, str] | None = None,
                 time_profile = None):
        self.path = path
        self.login = login
        self.password = password
        self.server = server
        self.timeout = timeout
        
        self.client = client if client is not None else RealMT5Client()
        self.symbol_map = symbol_map or {}
        self._time_profile = time_profile
        
        self._capabilities = MT5Capabilities()
        self._connected = False

    def _get_broker_symbol(self, canonical_symbol: str) -> str:
        return self.symbol_map.get(canonical_symbol, canonical_symbol)

    def connect(self) -> None:
        if self.client.initialize(path=self.path, login=self.login, password=self.password, server=self.server, timeout=self.timeout):
            self._connected = True
            
            # Phase 1: validate account currency is USD
            account_info = self.client.account_info()
            if account_info is None:
                self.client.shutdown()
                self._connected = False
                err = self.client.last_error()
                raise MT5Error(f"Failed to fetch account info. Error {err[0]}: {err[1]}")
            if account_info.currency != "USD":
                self.client.shutdown()
                self._connected = False
                raise MT5Error(f"Unsupported account currency: {account_info.currency}. Only USD accounts are supported in this phase.")
        else:
            err = self.client.last_error()
            raise MT5Error(f"MT5 initialization failed. Error {err[0]}: {err[1]}")

    def disconnect(self) -> None:
        if self._connected:
            self.client.shutdown()
            self._connected = False
            
    def get_broker_metadata(self) -> dict[str, str]:
        if not self._connected:
            self.connect()
        acc = self.client.account_info()
        return {
            "broker": getattr(acc, "company", "unknown"),
            "server": getattr(acc, "server", "unknown")
        }

    @property
    def capabilities(self) -> CapabilityMetadata:
        return self._capabilities

    def get_instrument_spec(self, symbol: str) -> InstrumentSpec:
        if not self._connected:
            self.connect()
            
        broker_symbol = self._get_broker_symbol(symbol)
        if not self.client.symbol_select(broker_symbol, True):
            err = self.client.last_error()
            raise MT5Error(f"Symbol {broker_symbol} not found or selectable. Error {err[0]}: {err[1]}")
            
        info = self.client.symbol_info(broker_symbol)
        if info is None:
            err = self.client.last_error()
            raise MT5Error(f"Failed to fetch symbol info for {broker_symbol}. Error {err[0]}: {err[1]}")
            
        # Reject non-FX symbols in this phase (e.g. if currency is not standard FX pair length)
        # Or explicitly reject if path is not FX
        if "XAU" in broker_symbol:
            raise MT5Error("XAUUSD is not supported in this phase.")
        if info.trade_calc_mode != 0: # SYMBOL_CALC_MODE_FOREX
            raise MT5Error("Only Forex calculation mode symbols are supported in this phase.")
            
        execution_map = {0: "REQUEST", 1: "INSTANT", 2: "MARKET", 3: "EXCHANGE"}
        exec_mode = execution_map.get(info.trade_exemode, "UNKNOWN")
            
        return InstrumentSpec(
            broker_symbol=info.name,
            canonical_symbol=symbol,
            asset_class="FX",
            digits=info.digits,
            point=info.point,
            tick_size=info.trade_tick_size,
            tick_value=info.trade_tick_value,
            contract_size=info.trade_contract_size,
            volume_min=info.volume_min,
            volume_max=info.volume_max,
            volume_step=info.volume_step,
            margin_currency=info.currency_margin,
            profit_currency=info.currency_profit,
            execution_mode=exec_mode,
            trading_sessions={},
            stop_level=info.trade_stops_level
        )



    def fetch_bars(self, symbol: str, timeframe: str, start: datetime, end: datetime) -> pd.DataFrame:
        if not self._connected:
            self.connect()
            
        broker_symbol = self._get_broker_symbol(symbol)
        tf = self.client.map_timeframe(timeframe)
        
        if start.tzinfo is None:
            start = start.replace(tzinfo=UTC)
        if end.tzinfo is None:
            end = end.replace(tzinfo=UTC)
            
        start_utc = start.astimezone(UTC)
        end_utc = end.astimezone(UTC)
        
        dfs = []
        if self._time_profile:
            ranges = self._time_profile.get_subranges(start_utc, end_utc)
            for r_start, r_end, offset in ranges:
                # Use int epochs to avoid local tz mangling
                req_start = utc_to_mt5_label(r_start, offset)
                req_end = utc_to_mt5_label(r_end, offset)
                
                rates = self.client.copy_rates_range(broker_symbol, tf, req_start, req_end)
                if rates is not None and len(rates) > 0:
                    df = pd.DataFrame(rates)
                    # Convert raw 'time' back to UTC using the profile offset
                    # We create datetime objects, then convert to pd.Timestamp to ensure standard Pandas UTC format
                    df['time'] = df['time'].apply(lambda x, o=offset: pd.Timestamp(mt5_label_to_utc(x, o)))
                    dfs.append(df)
        else:
            rates = self.client.copy_rates_range(broker_symbol, tf, start_utc, end_utc)
            if rates is not None and len(rates) > 0:
                df = pd.DataFrame(rates)
                df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
                dfs.append(df)
                
        if not dfs:
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "tick_volume", "spread", "real_volume"])
            
        df = pd.concat(dfs, ignore_index=True)
        # Filter duplicates just in case ranges overlapped at boundaries
        df = df.drop_duplicates(subset=['time'])
        # Ensure we stay strictly within requested canonical [start, end)
        df = df[(df['time'] >= start_utc) & (df['time'] < end_utc)]
        
        df = df.rename(columns={
            "time": "timestamp",
            "tick_volume": "tick_volume",
            "real_volume": "real_volume"
        })
        
        expected_cols = ["timestamp", "open", "high", "low", "close", "tick_volume", "spread", "real_volume"]
        for col in expected_cols:
            if col not in df.columns:
                df[col] = 0
                
        df["symbol"] = symbol
        df["timeframe"] = timeframe
        df = df[["timestamp", "symbol", "timeframe", "open", "high", "low", "close", "tick_volume", "spread", "real_volume"]]
        return df[["timestamp", "symbol", "timeframe", "open", "high", "low", "close", "tick_volume", "spread", "real_volume"]]

    def fetch_ticks(self, symbol: str, start: datetime, end: datetime) -> pd.DataFrame:
        if not self._connected:
            self.connect()
            
        broker_symbol = self._get_broker_symbol(symbol)
        
        if start.tzinfo is None:
            start = start.replace(tzinfo=UTC)
        if end.tzinfo is None:
            end = end.replace(tzinfo=UTC)
            
        start_utc = start.astimezone(UTC)
        end_utc = end.astimezone(UTC)
        
        dfs = []
        if self._time_profile:
            import MetaTrader5 as mt5
            ranges = self._time_profile.get_subranges(start_utc, end_utc)
            for r_start, r_end, offset in ranges:
                req_start = utc_to_mt5_label(r_start, offset)
                req_end = utc_to_mt5_label(r_end, offset)
                
                ticks = self.client.copy_ticks_range(broker_symbol, req_start, req_end, mt5.COPY_TICKS_ALL)
                if ticks is not None and len(ticks) > 0:
                    df = pd.DataFrame(ticks)
                    # Convert raw 'time' (sec) and we must also construct full msc if needed.
                    # But MT5 ticks have 'time' in sec and 'time_msc' in msc.
                    # Actually wait, time_msc is the exact one we should use!
                    # For Phase 1, we just convert 'time_msc' back by subtracting offset*3600*1000
                    # And then use pd.to_datetime with unit='ms'
                    # Or we can just use mt5_label_to_utc on 'time' and add the ms.
                    df['time'] = df['time_msc'].apply(lambda x, o=offset: pd.Timestamp(mt5_label_to_utc(x / 1000.0, o)))
                    dfs.append(df)
        else:
            import MetaTrader5 as mt5
            ticks = self.client.copy_ticks_range(broker_symbol, start_utc, end_utc, mt5.COPY_TICKS_ALL)
            if ticks is not None and len(ticks) > 0:
                df = pd.DataFrame(ticks)
                df['time'] = pd.to_datetime(df['time_msc'], unit='ms', utc=True)
                dfs.append(df)
                
        if not dfs:
            return pd.DataFrame(columns=["timestamp", "bid", "ask", "last", "volume", "flags"])
            
        df = pd.concat(dfs, ignore_index=True)
        df = df.drop_duplicates(subset=['time'])
        df = df[(df['time'] >= start_utc) & (df['time'] < end_utc)]
        
        df["symbol"] = symbol
        df["spread"] = df["ask"] - df["bid"]
        df = df.rename(columns={"time": "timestamp"})
        return df[["timestamp", "symbol", "bid", "ask", "last", "volume", "flags"]][["timestamp", "symbol", "bid", "ask", "last", "volume", "flags"]]
