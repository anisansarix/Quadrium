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
from app.data.time_profile import get_metaquotes_demo_phase1_profile


def main():
    print("Starting MT5 Smoke Test...")
    
    login = os.environ.get("QUADRIUM_MT5_LOGIN")
    password = os.environ.get("QUADRIUM_MT5_PASSWORD")
    server = os.environ.get("QUADRIUM_MT5_SERVER")
    path = os.environ.get("QUADRIUM_MT5_PATH")
    
    start_ts = datetime(2026, 9, 24, 0, 0, tzinfo=UTC)
    end_ts = datetime(2026, 9, 25, 0, 0, tzinfo=UTC)
    
    calendar_config = ConfigurableCalendarConfig(
        sessions=[SessionWindow(start_day=6, start_time=time(21, 0), end_day=4, end_time=time(21, 0))]
    )
    calendar = ConfigurableCalendar(calendar_config)
    
    print("Initializing MT5Provider...")
    kwargs = {}
    if path: kwargs["path"] = path
    if login: kwargs["login"] = int(login)
    if password: kwargs["password"] = password
    if server: kwargs["server"] = server
    
    kwargs["time_profile"] = get_metaquotes_demo_phase1_profile()
    provider = MT5Provider(**kwargs)
    try:
        provider.connect()
    except Exception as e:  # noqa: BLE001
        print(f"FAIL: MT5Provider connect failed: {e}")
        sys.exit(1)
        
    try:
        client = provider.client
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
        val_report = None
        try:
            artifact = downloader.download_bars(symbol, "M1", start_ts, end_ts)
            
            # If we get here, ingestion passed. Now do calculation validation.
            margin_model = MarginModel(
                leverage=float(account.leverage),
                account_currency=account.currency,
                margin_calculation_mode=str(sym_info.trade_calc_mode),
                margin_rate=1.0,
                margin_rate_source="configured_phase1_profile",
                account_currency_decimals=int(account.currency_digits)
            )
            val_report = validate_calculations(client, symbol, spec, margin_model)
            
        except Exception as e:  # noqa: BLE001
            error_msg = str(e)
            print(f"FAIL: Dataset ingestion or validation failed: {e}")
            
        print("\n--- Acceptance Summary ---")
        print(f"Requested Start: {start_ts}")
        print(f"Requested End: {end_ts}")
        
        # The overall gate:
        # artifact must exist, error_msg must be None, quality_status == PASS, val_report.all_passed == True
        passed_quality = artifact and artifact.quality_report.quality_status == "PASS"
        passed_calc = val_report and val_report.all_passed
        
        report_status = "PASS" if (not error_msg and passed_quality and passed_calc) else "FAIL"
        
        date_str = datetime.now(UTC).strftime('%Y%m%d_%H%M%S')
        report_path = Path(f"docs/MT5_SMOKE_TEST_{date_str}.md")
        report_path.parent.mkdir(exist_ok=True, parents=True)
        
        balance = getattr(account, 'balance', 'N/A')
        
        report = f"""# MT5 Smoke Test Report ({date_str})\n\n"""
        report += """## ACCOUNT\n"""
        report += f"""- **Balance**: {balance}\n"""
        report += f"""- **Currency**: {account.currency}\n- **Currency Digits**: {account.currency_digits}\n"""
        report += f"""- **Leverage**: {account.leverage}\n"""
        report += f"""- **Broker**: {account.company}\n"""
        report += f"""- **Server**: {account.server}\n\n"""

        report += """## INSTRUMENT\n"""
        report += f"""- **Symbol**: {symbol}\n"""
        report += f"""- **Contract Size**: {sym_info.trade_contract_size}\n"""
        report += f"""- **Digits**: {sym_info.digits}\n"""
        report += f"""- **Tick Size**: {sym_info.trade_tick_size}\n"""
        report += f"""- **Tick Value**: {sym_info.trade_tick_value}\n"""
        report += f"""- **Margin Currency**: {sym_info.currency_margin}\n"""
        report += f"""- **Profit Currency**: {sym_info.currency_profit}\n"""
        report += f"""- **Calc Mode**: {sym_info.trade_calc_mode}\n\n"""

        report += """## DATA\n"""
        report += f"""- **Requested Interval**: {start_ts} to {end_ts}\n"""
        
        if artifact:
            df_canonical = manager.load_canonical(artifact.dataset_id)
            qr = artifact.quality_report
            report += f"""- **Canonical Interval**: {df_canonical['timestamp'].min()} to {df_canonical['timestamp'].max()}\n"""
            report += f"""- **Expected Bars**: {qr.expected_bars}\n"""
            report += f"""- **Observed Bars**: {qr.observed_bars}\n"""
            report += f"""- **Sparse Bars**: {qr.source_sparse_bars}\n"""
            report += f"""- **Ticks-Present/Bar-Missing**: {qr.ticks_present_bar_missing}\n"""
            report += f"""- **Duplicates**: {qr.duplicate_bars}\n"""
            report += f"""- **Coverage**: {qr.coverage_status}\n"""
            report += f"""- **Quality**: {qr.quality_status}\n"""
        else:
            report += f"Ingestion Failed: {error_msg}\n"
            
        report += "\n## CALCULATIONS\n"
        if val_report:
            prof_pass = all(d.passed for d in val_report.profit_diffs)
            marg_pass = all(d.passed for d in val_report.margin_diffs)
            report += f"- **Profit Validation**: {'PASS' if prof_pass else 'FAIL'}\n"
            report += f"- **Margin Validation**: {'PASS' if marg_pass else 'FAIL'}\n\n"
            
            report += "### Profit Scenarios\n"
            report += "| Action | Volume | Open | Close | Quadrium | MT5 | Abs Diff | Rel Diff | Tol | Passed | Unsupported |\n"
            report += "|---|---|---|---|---|---|---|---|---|---|---|\n"
            for d in val_report.profit_diffs:
                report += f"| {d.action} | {d.volume} | {d.price_open} | {d.price_close} | {d.quadrium_val} | {d.mt5_val} | {d.diff_abs} | {d.diff_rel} | {d.tolerance} | {d.passed} | {d.unsupported} |\n"
                
            report += f"\n### Margin Scenarios (Rate Source: {val_report.margin_rate_source})\n"
            report += "| Action | Volume | Open | Close | Config Rate | Implied Rate | Rate Diff | Rate Tol | Quad Raw | Quad Norm | MT5 | Diff Norm | Prec | Tol | Passed |\n"
            report += "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
            for d in val_report.margin_diffs:
                report += f"| {d.action} | {d.volume} | {d.price_open} | {d.price_close} | {d.configured_margin_rate} | {d.implied_mt5_margin_rate} | {d.rate_diff_abs} | {d.rate_tolerance} | {d.theoretical_margin_raw} | {d.theoretical_margin_normalized} | {d.mt5_margin} | {d.diff_normalized} | {d.currency_precision} | {d.tolerance} | {d.passed} |\n"
        else:
            report += "Calculations not run due to prior failure.\n"
            
        report += f"\n## FINAL\n**{report_status}**\n"
        
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



