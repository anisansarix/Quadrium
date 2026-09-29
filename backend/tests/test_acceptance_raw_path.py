
def test_acceptance_script_locates_raw_correctly():
    script_path = "backend/scripts/mt5_time_translation_acceptance.py"
    with open(script_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    # The script should not hardcode the nested raw path that DatasetManager doesn't use.
    assert 'temp_dir / "raw" / "mt5" / "EURUSD" / "M1"' not in content
    
    # It must locate it dynamically using manager.raw_dir
    assert "raw_path = manager.raw_dir" in content
