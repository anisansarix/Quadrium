import os
import sys
from datetime import UTC, datetime, timedelta

import MetaTrader5 as mt5
from app.data.providers.mt5 import MT5Provider


def run_diagnostic():
    kwargs = {}
    server = os.environ.get("QUADRIUM_MT5_SERVER")
    path = os.environ.get("QUADRIUM_MT5_PATH")
    if server: kwargs["server"] = server
    if path: kwargs["path"] = path

    provider = MT5Provider(**kwargs)
    try:
        provider.connect()
    except Exception as e:  # noqa: BLE001
        print(f"FAIL: MT5Provider connect failed: {e}")
        sys.exit(1)
        
    client = provider.client
    symbol = "EURUSD"
    if not client.symbol_select(symbol, True):
        print(f"FAIL: Failed to select {symbol}")
        sys.exit(1)
        
    term_info = mt5.terminal_info()
    acc_info = mt5.account_info()
    
    print("--- ENVIRONMENT ---")
    print(f"MetaTrader5 Python Version: {mt5.__version__}")
    print(f"Terminal Build: {getattr(term_info, 'build', 'Unknown')}")
    print(f"Company: {getattr(acc_info, 'company', 'Unknown')}")
    print(f"Server: {getattr(acc_info, 'server', 'Unknown')}")
    
    # 1. RETURN DOMAIN DIAGNOSTIC
    tick = mt5.symbol_info_tick(symbol)
    now_utc = datetime.now(UTC)
    
    if not tick:
        print(f"FAIL: No tick data for {symbol}")
        sys.exit(1)
        
    tick_time_sec = tick.time
    tick_time_msc = tick.time_msc
    tick_dt_utc = datetime.fromtimestamp(tick_time_msc / 1000.0, tz=UTC)
    
    diff = now_utc - tick_dt_utc
    diff_sec = diff.total_seconds()
    
    offset_seconds = -diff_sec
    
    if abs(diff_sec) < 300:
        return_classification = "UTC-LIKE"
    elif abs(diff_sec) > 3600:
        return_classification = "SERVER-OFFSET-LIKE"
    else:
        return_classification = "INCONCLUSIVE"
        
    rates = mt5.copy_rates_from_pos(symbol, client.map_timeframe("M1"), 0, 1)
    if rates is not None and len(rates) > 0:
        latest_bar = rates[0]
        bar_time_sec = latest_bar['time']
        bar_dt_utc = datetime.fromtimestamp(bar_time_sec, tz=UTC)
        bar_age_sec = (now_utc - bar_dt_utc).total_seconds()
    else:
        bar_time_sec = 0
        bar_dt_utc = "N/A"
        bar_age_sec = "N/A"
        
    print("\n--- RETURN DOMAIN ---")
    print(f"Python UTC now: {now_utc}")
    print(f"Observed offset from UTC: {offset_seconds / 3600.0:.2f} hours")
    print(f"Latest Tick: Raw Epoch: {tick_time_sec}, Interpreted UTC: {tick_dt_utc}, Age from UTC: {diff_sec:.1f}s")
    print(f"Latest M1 Bar: Raw Epoch: {bar_time_sec}, Interpreted UTC: {bar_dt_utc}, Age from UTC: {bar_age_sec if isinstance(bar_age_sec, str) else f'{bar_age_sec:.1f}s'}")
    print(f"Classification: {return_classification}")

    # 2. REQUEST DOMAIN DIAGNOSTIC
    window_minutes = 15
    
    # Query A: True UTC Window
    start_a = now_utc - timedelta(minutes=window_minutes)
    end_a = now_utc
    
    # Query B: Shifted Window (Assume server time domain is expected)
    start_b = start_a + timedelta(seconds=offset_seconds)
    end_b = end_a + timedelta(seconds=offset_seconds)
    
    def run_probe(start_dt, end_dt, name):
        naive_start = start_dt
        naive_end = end_dt
        
        rates = client.copy_rates_range(symbol, client.map_timeframe("M1"), naive_start, naive_end)
        ticks = client.copy_ticks_range(symbol, naive_start, naive_end, mt5.COPY_TICKS_ALL)
        
        rates_res = {"rows": 0, "first_raw": "N/A", "last_raw": "N/A", "first_utc": "N/A", "last_utc": "N/A"}
        if rates is not None and len(rates) > 0:
            rates_res["rows"] = len(rates)
            rates_res["first_raw"] = rates[0]['time']
            rates_res["last_raw"] = rates[-1]['time']
            rates_res["first_utc"] = str(datetime.fromtimestamp(rates[0]['time'], tz=UTC))
            rates_res["last_utc"] = str(datetime.fromtimestamp(rates[-1]['time'], tz=UTC))
            
        ticks_res = {"rows": 0, "first_raw": "N/A", "last_raw": "N/A", "first_utc": "N/A", "last_utc": "N/A"}
        if ticks is not None and len(ticks) > 0:
            ticks_res["rows"] = len(ticks)
            ticks_res["first_raw"] = ticks[0]['time']
            ticks_res["last_raw"] = ticks[-1]['time']
            ticks_res["first_utc"] = str(datetime.fromtimestamp(ticks[0]['time'], tz=UTC))
            ticks_res["last_utc"] = str(datetime.fromtimestamp(ticks[-1]['time'], tz=UTC))
            
        return {
            "req_start": naive_start,
            "req_end": naive_end,
            "req_start_epoch": int(start_dt.timestamp()),
            "req_end_epoch": int(end_dt.timestamp()),
            "rates": rates_res,
            "ticks": ticks_res
        }
        
    res_a = run_probe(start_a, end_a, "Probe A")
    res_b = run_probe(start_b, end_b, "Probe B")
    
    def print_probe(res, name):
        print(f"  {name}: {res['req_start']} to {res['req_end']} (Epoch: {res['req_start_epoch']} to {res['req_end_epoch']})")
        
        rt = res['rates']
        print(f"    Bars returned: {rt['rows']}")
        if rt['rows'] > 0:
            print(f"      First Raw: {rt['first_raw']} -> {rt['first_utc']}")
            print(f"      Last Raw: {rt['last_raw']} -> {rt['last_utc']}")
            
        tk = res['ticks']
        print(f"    Ticks returned: {tk['rows']}")
        if tk['rows'] > 0:
            print(f"      First Raw: {tk['first_raw']} -> {tk['first_utc']}")
            print(f"      Last Raw: {tk['last_raw']} -> {tk['last_utc']}")
            
    print("\n--- REQUEST DOMAIN ---")
    print_probe(res_a, "Probe A (True UTC)")
    print_probe(res_b, "Probe B (Shifted by offset)")
    
    # Analyze Request Domain explicitly
    rates_req_class = "INCONCLUSIVE"
    ticks_req_class = "INCONCLUSIVE"
    
    # Logic: if A returns bars close to current server time, then it's UTC absolute.
    # If B returns bars close to current server time, then it's SERVER_WALLCLOCK_LIKE.
    # But as we saw, MT5 python lib mangles timezones. The user wants the raw diagnostic matrix.
    
    if res_b['rates']['rows'] > 0 and abs(res_b['rates']['last_raw'] - bar_time_sec) <= window_minutes*60:
        rates_req_class = "SERVER_WALLCLOCK_LIKE"
    elif res_a['rates']['rows'] > 0 and abs(res_a['rates']['last_raw'] - bar_time_sec) <= window_minutes*60:
        rates_req_class = "UTC_ABSOLUTE"
    else:
        # Check if the timestamps returned by A match A's request, or B's request.
        # This occurs if local-time assumptions shift things entirely.
        if res_a['rates']['rows'] > 0:
            if abs(res_a['rates']['last_raw'] - res_a['req_end_epoch']) <= window_minutes*60:
                rates_req_class = "UTC_ABSOLUTE (raw matches req)"
            else:
                rates_req_class = f"SERVER_WALLCLOCK_LIKE (offset {res_a['rates']['last_raw'] - res_a['req_end_epoch']}s)"
        elif res_b['rates']['rows'] > 0:
            rates_req_class = "SERVER_WALLCLOCK_LIKE"

    if res_b['ticks']['rows'] > 0 and abs(res_b['ticks']['last_raw'] - tick_time_sec) <= window_minutes*60:
        ticks_req_class = "SERVER_WALLCLOCK_LIKE"
    elif res_a['ticks']['rows'] > 0 and abs(res_a['ticks']['last_raw'] - tick_time_sec) <= window_minutes*60:
        ticks_req_class = "UTC_ABSOLUTE"
    else:
        if res_a['ticks']['rows'] > 0:
            if abs(res_a['ticks']['last_raw'] - res_a['req_end_epoch']) <= window_minutes*60:
                ticks_req_class = "UTC_ABSOLUTE (raw matches req)"
            else:
                ticks_req_class = f"SERVER_WALLCLOCK_LIKE (offset {res_a['ticks']['last_raw'] - res_a['req_end_epoch']}s)"
        elif res_b['ticks']['rows'] > 0:
            ticks_req_class = "SERVER_WALLCLOCK_LIKE"
        
    print(f"\nBARS REQUEST DOMAIN CLASSIFICATION: {rates_req_class}")
    print(f"TICKS REQUEST DOMAIN CLASSIFICATION: {ticks_req_class}")
    
    print("\n--- FINAL ---")
    print(f"REQUEST DOMAIN = {rates_req_class}")
    print(f"RETURN DOMAIN = {return_classification}")

if __name__ == "__main__":
    run_diagnostic()
