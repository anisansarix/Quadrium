
def test_acceptance_script_locates_raw_correctly():
    script_path = "backend/scripts/mt5_time_translation_acceptance.py"
    with open(script_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    assert 'temp_dir / "raw" / "mt5" / "EURUSD" / "M1"' not in content
    
    # It must locate raw chunks dynamically using the artifact
    assert "artifact.raw_chunks" in content
