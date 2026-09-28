import json
import os
import sys
from datetime import UTC, datetime, time
from pathlib import Path

from app.data.catalog import DatasetCatalog
from app.data.coverage import ConfigurableCalendar, ConfigurableCalendarConfig, SessionWindow
from app.data.datasets import DatasetManager
from app.data.downloader import MT5Downloader
from app.data.mt5_validation import MarginModel, validate_calculations
from app.data.providers.mt5 import MT5Provider
from app.data.providers.mt5_client import RealMT5Client


def main():
    print("Starting MT5 Smoke Test...")
    
    login = os.environ.get("QUADRIUM_MT5_LOGIN")
    password = os.environ.get("QUADRIUM_MT5_PASSWORD")
    server = os.environ.get("QUADRIUM_MT5_SERVER")
    path = os.environ.get("QUADRIUM_MT5_PATH")
    
    start_ts = datetime(2026, 9, 24, 0, 0, tzinfo=UTC)
    end_ts = datetime(2026, 9, 25, 0, 0, tzinfo=UTC)
    
    calendar_config = ConfigurableCalendarConfig(
        sessions=[SessionWindow(start_day=6, start_time=time(22, 0), end_day=4, end_time=time(22, 0))]
    )
    calendar = ConfigurableCalendar(calendar_config)
    
    print("Initializing RealMT5Client...")
    client = RealMT5Client()
    try:
        kwargs = {}
        if path: kwargs["path"] = path
        if login: kwargs["login"] = int(login)
        if password: kwargs["password"] = password
        if server: kwargs["server"] = server
        
        if not client.initialize(**kwargs):
            err = client.last_error()
            print(f"FAIL: MT5 initialize failed: {err}")
            sys.exit(1)
            
        provider = MT5Provider(client=client)
        provider.connect()
    except Exception as e:  # noqa: BLE001
        print(f"FAIL: MT5Provider connect failed: {e}")
        sys.exit(1)
        
    try:
        account = client.account_info()
        if not account:
            print("FAIL: Failed to get account info")
            sys.exit(1)
            
        print("\n--- Account Info ---")
        print(f"Currency: {account.currency}")
        print(f"Company: {account.company}")
        print(f"Server: {account.server}")
        print(f"Leverage: {account.leverage}")
        print(f"Trade Mode: {account.trade_mode}")
        
        if account.currency != "USD":
            print(f"FAIL: Account currency is not USD: {account.currency}")
            sys.exit(1)
            
        print("\n--- Instrument Metadata ---")
        symbol = "EURUSD"
        if not client.symbol_select(symbol, True):
            print(f"FAIL: Failed to select symbol {symbol}")
            sys.exit(1)
            
        sym_info = client.symbol_info(symbol)
        if not sym_info:
            print(f"FAIL: Failed to get symbol info for {symbol}")
            sys.exit(1)
            
        print(f"Name: {sym_info.name}")
        print(f"Digits: {sym_info.digits}")
        print(f"Point: {sym_info.point}")
        print(f"Tick Size: {sym_info.trade_tick_size}")
        print(f"Tick Value: {sym_info.trade_tick_value}")
        print(f"Contract Size: {sym_info.trade_contract_size}")
        print(f"Min/Max/Step Volume: {sym_info.volume_min} / {sym_info.volume_max} / {sym_info.volume_step}")
        print(f"Margin Currency: {sym_info.currency_margin}")
        print(f"Profit Currency: {sym_info.currency_profit}")
        print(f"Calc Mode: {sym_info.trade_calc_mode}")
        
        if sym_info.trade_calc_mode != 0:
            print(f"FAIL: Trade calc mode is not FOREX (0), got {sym_info.trade_calc_mode}")
            sys.exit(1)
            
        spec = provider.get_instrument_spec(symbol)
            
        print(f"\n--- Downloading M1 Data ({start_ts} to {end_ts}) ---")
        data_dir = Path("backend/data")
        data_dir.mkdir(parents=True, exist_ok=True)
        manager = DatasetManager(data_dir)
        catalog = DatasetCatalog(data_dir / "catalog.duckdb")
        
        downloader = MT5Downloader(provider, manager, catalog, calendar)
        
        artifact = None
        error_msg = None
        try:
            artifact = downloader.download_bars(symbol, "M1", start_ts, end_ts)
        except Exception as e:  # noqa: BLE001
            error_msg = str(e)
            print(f"FAIL: Dataset ingestion failed: {e}")
            
        print("\n--- Acceptance Summary ---")
        print(f"Requested Start: {start_ts}")
        print(f"Requested End: {end_ts}")
        
        report_status = "FAIL" if error_msg else "PASS"
        date_str = datetime.now(UTC).strftime('%Y%m%d_%H%M%S')
        report_path = Path(f"docs/MT5_SMOKE_TEST_{date_str}.md")
        report_path.parent.mkdir(exist_ok=True, parents=True)
        
        report = "# MT5 Smoke Test Report (" + date_str + ")\n\n"
        report += "## Terminal/Broker Metadata\n"
        report += f"- **Company**: {account.company}\n"
        report += f"- **Server**: {account.server}\n"
        report += f"- **Account Currency**: {account.currency}\n"
        report += f"- **Leverage**: {account.leverage}\n\n"
        
        report += "## Symbol Metadata (EURUSD)\n"
        report += f"- **Digits**: {sym_info.digits}\n"
        report += f"- **Point**: {sym_info.point}\n"
        report += f"- **Tick Size**: {sym_info.trade_tick_size}\n"
        report += f"- **Tick Value**: {sym_info.trade_tick_value}\n"
        report += f"- **Contract Size**: {sym_info.trade_contract_size}\n"
        report += f"- **Calc Mode**: {sym_info.trade_calc_mode}\n\n"
        
        report += "## Ingestion Details\n"
        report += f"- **Requested Interval**: {start_ts} to {end_ts}\n"
        report += f"- **Calendar Configuration**: {json.dumps(calendar_config.model_dump(), default=str)}\n"
        
        if artifact:
            df_canonical = manager.load_canonical(artifact.dataset_id)
            print(f"Canonical Start: {df_canonical['timestamp'].min()}")
            print(f"Canonical End: {df_canonical['timestamp'].max()}")
            print(f"Observed Bars: {artifact.quality_report.observed_bars}")
            print(f"Expected Bars: {artifact.quality_report.expected_bars}")
            print(f"Unexpected Missing: {artifact.quality_report.unexpected_missing_bars}")
            print(f"Known Closure: {artifact.quality_report.known_closure_bars}")
            print(f"Duplicate Bars: {artifact.quality_report.duplicate_bars}")
            print(f"Coverage Status: {artifact.quality_report.coverage_status}")
            print(f"Quality Status: {artifact.quality_report.quality_status}")
            print(f"Dataset ID: {artifact.dataset_id}")
            print(f"Dataset Hash: {artifact.dataset_hash}")
            print(f"Canonical Path: {artifact.canonical_path}")
            
            report += f"- **Canonical Start**: {df_canonical['timestamp'].min()}\n"
            report += f"- **Canonical End**: {df_canonical['timestamp'].max()}\n"
            report += f"- **Dataset ID**: {artifact.dataset_id}\n"
            report += f"- **Dataset Hash**: {artifact.dataset_hash}\n"
            report += f"- **Canonical Path**: {artifact.canonical_path}\n"
            report += "- **Data Quality Report**:\n`json\n"
            report += artifact.quality_report.model_dump_json(indent=2)
            report += "\n`\n"

            print("\n--- Calculation Validation ---")
            margin_model = MarginModel(
                leverage=float(account.leverage),
                account_currency=account.currency,
                margin_calculation_mode=str(sym_info.trade_calc_mode)
            )
            
            val_report = validate_calculations(client, symbol, spec, margin_model)
            print(f"All calculations passed: {val_report.all_passed}")
            
            report += "\n## Calculation Validation\n"
            report += f"- **Margin Model**: {json.dumps(margin_model.model_dump())}\n"
            report += f"- **All Passed**: {val_report.all_passed}\n"
        else:
            report += f"\n## Error\nIngestion failed: {error_msg}\n"
            
        report += f"\n## Status\n**{report_status}**\n"
        
        report_path.write_text(report)
        print(f"\nReport written to {report_path}")
        
        if report_status == "FAIL":
            sys.exit(1)
        else:
            print("\nPASS: MT5 Smoke Test completed successfully.")
            
    finally:
        provider.disconnect()

if __name__ == "__main__":
    main()


