from unittest.mock import MagicMock, patch

import pytest
from app.data.mt5_validation import ValidationReport
from app.data.quality import DataQualityReport


def setup_mocks(mock_val, mock_mgr, mock_downloader, mock_provider, all_passed=True, q_status="PASS"):
    mock_mgr_inst = MagicMock()
    mock_df = MagicMock()
    mock_df['timestamp'].min.return_value = '2023'
    mock_df['timestamp'].max.return_value = '2024'
    mock_mgr_inst.load_canonical.return_value = mock_df
    mock_mgr.return_value = mock_mgr_inst

    mock_prov_inst = MagicMock()
    mock_provider.return_value = mock_prov_inst
    
    mock_client = MagicMock()
    mock_prov_inst.client = mock_client
    
    mock_account = MagicMock()
    mock_account.currency = "USD"
    mock_account.currency_digits = 2
    mock_account.balance = 25000.0
    mock_account.leverage = 33
    mock_account.company = "Broker"
    mock_account.server = "Server"
    mock_client.account_info.return_value = mock_account
    
    mock_client.symbol_select.return_value = True
    mock_sym = MagicMock()
    mock_sym.trade_calc_mode = 0
    mock_sym.trade_contract_size = 100000.0
    mock_sym.digits = 5
    mock_sym.trade_tick_size = 0.00001
    mock_sym.trade_tick_value = 1.0
    mock_sym.currency_margin = "EUR"
    mock_sym.currency_profit = "USD"
    mock_client.symbol_info.return_value = mock_sym
    
    mock_artifact = MagicMock()
    mock_artifact.dataset_id = "test_id"
    mock_qr = DataQualityReport(
        coverage_status="SPARSE",
        expected_bars=10,
        observed_bars=10,
        source_sparse_bars=0,
        ticks_present_bar_missing=0,
        unexpected_missing_bars=0,
        known_closure_bars=0,
            unexpected_extra_bars=0,
            duplicate_bars=0,
        quality_status=q_status
    )
    mock_artifact.quality_report = mock_qr
    
    mock_dl_inst = MagicMock()
    mock_dl_inst.download_bars.return_value = mock_artifact
    mock_downloader.return_value = mock_dl_inst
    
    mock_val_report = ValidationReport(
        symbol="EURUSD",
        leverage=33.0,
        account_currency="USD",
        margin_calculation_mode="0",
        margin_rate=1.0,
        margin_rate_source="configured_phase1_profile",
        account_currency_decimals=2,
        profit_diffs=[],
        margin_diffs=[],
        all_passed=all_passed
    )
    mock_val.return_value = mock_val_report


@patch('scripts.mt5_smoke_test.MT5Provider')
@patch('scripts.mt5_smoke_test.MT5Downloader')
@patch('scripts.mt5_smoke_test.DatasetManager')
@patch('scripts.mt5_smoke_test.validate_calculations')
def test_smoke_test_gate_all_pass(mock_val, mock_mgr, mock_downloader, mock_provider):
    import scripts.mt5_smoke_test as st
    setup_mocks(mock_val, mock_mgr, mock_downloader, mock_provider, all_passed=True, q_status="PASS")
    try:
        st.main()
    except SystemExit as e:
        pytest.fail(f"main() exited with {e.code} unexpectedly")

@patch('scripts.mt5_smoke_test.MT5Provider')
@patch('scripts.mt5_smoke_test.MT5Downloader')
@patch('scripts.mt5_smoke_test.DatasetManager')
@patch('scripts.mt5_smoke_test.validate_calculations')
def test_smoke_test_gate_calc_fail(mock_val, mock_mgr, mock_downloader, mock_provider):
    import scripts.mt5_smoke_test as st
    setup_mocks(mock_val, mock_mgr, mock_downloader, mock_provider, all_passed=False, q_status="PASS")
    with pytest.raises(SystemExit) as excinfo:
        st.main()
    assert excinfo.value.code == 1

@patch('scripts.mt5_smoke_test.MT5Provider')
@patch('scripts.mt5_smoke_test.MT5Downloader')
@patch('scripts.mt5_smoke_test.DatasetManager')
@patch('scripts.mt5_smoke_test.validate_calculations')
def test_smoke_test_gate_data_fail(mock_val, mock_mgr, mock_downloader, mock_provider):
    import scripts.mt5_smoke_test as st
    setup_mocks(mock_val, mock_mgr, mock_downloader, mock_provider, all_passed=True, q_status="FAIL")
    with pytest.raises(SystemExit) as excinfo:
        st.main()
    assert excinfo.value.code == 1

