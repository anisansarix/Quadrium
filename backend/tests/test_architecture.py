import ast
from pathlib import Path

import pytest
from app.domain.models import TargetPosition
from pydantic import ValidationError


def check_imports(directory: str, forbidden_module: str, allowed_files: list | None = None):
    allowed_files = allowed_files or []
    violations = []
    base_dir = Path(directory)
    for filepath in base_dir.rglob("*.py"):
        if filepath.name in allowed_files:
            continue
            
        with open(filepath, "r", encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read(), filename=str(filepath))
            except SyntaxError:
                continue
                
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split('.')[0] == forbidden_module:
                        violations.append(str(filepath))
            elif isinstance(node, ast.ImportFrom) and node.module and node.module.split('.')[0] == forbidden_module:
                violations.append(str(filepath))
                    
    return violations

def test_rl_cannot_import_mt5():
    violations = check_imports("backend/app", "MetaTrader5", allowed_files=["mt5.py"])
    assert not violations, f"Forbidden import of MetaTrader5 in: {violations}"

def test_config_default_mode_is_research():
    from app.core.config import settings
    assert settings.env == "RESEARCH", "Default environment mode must be RESEARCH"

def test_target_weight_bounds():
    with pytest.raises(ValidationError):
        TargetPosition(symbol="EURUSD", target_weight=1.5)
    with pytest.raises(ValidationError):
        TargetPosition(symbol="EURUSD", target_weight=-1.1)
        
    pos = TargetPosition(symbol="EURUSD", target_weight=0.5)
    assert pos.target_weight == 0.5
