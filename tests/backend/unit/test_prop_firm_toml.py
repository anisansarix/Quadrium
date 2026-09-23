import pytest
from pathlib import Path
import tempfile
import os

from app.services.prop_firm import PropFirmSimulator

def test_load_profiles_from_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        # Write valid toml
        valid_toml = tmp_path / "valid.toml"
        valid_toml.write_text("""
[profile]
name = "FTMO Challenge"
account_sizes = [10000, 25000]

[rules]
max_overall_drawdown_pct = 0.10
drawdown_type = "static"
max_daily_loss_pct = 0.05
daily_loss_includes_floating = true
daily_reset_timezone = "Europe/Prague"

[[phases]]
name = "Phase 1"
profit_target_pct = 0.10
min_trading_days = 4
        """)
        
        # Write template (should be skipped)
        template_toml = tmp_path / "_template.toml"
        template_toml.write_text("invalid = =")
        
        profiles = PropFirmSimulator.load_profiles_from_dir(tmp_path)
        
        assert "valid" in profiles
        assert "_template" not in profiles
        p = profiles["valid"]
        assert p.name == "FTMO Challenge"
        assert float(p.account_size) == 10000.0
        assert float(p.max_overall_drawdown_pct) == 0.10
        assert len(p.phases) == 1
        assert p.phases[0].min_trading_days == 4
