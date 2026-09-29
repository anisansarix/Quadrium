with open('backend/app/data/downloader.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    'from app.data.validation import validate_dataframe',
    'from app.data.validation import validate_dataframe, validate_raw_chunk'
)

# Use it in download_bars
content = content.replace(
    '''            if not df_chunk.empty:
                # Save raw chunk to disk and free memory
                raw_path = self.dataset_manager.save_raw(df_chunk, "mt5", symbol, timeframe)
                chunk_paths.append((raw_path, current_start, current_end))''',
    '''            if not df_chunk.empty:
                validate_raw_chunk(df_chunk, symbol, timeframe)
                # Save raw chunk to disk and free memory
                raw_path = self.dataset_manager.save_raw(df_chunk, "mt5", symbol, timeframe)
                chunk_paths.append((raw_path, current_start, current_end))'''
)

# Populate DatasetArtifact.raw_paths
content = content.replace(
    '''            canonical_path=str(canonical_path),
            gap_report=gap_report,''',
    '''            canonical_path=str(canonical_path),
            raw_paths=[str(p[0]) for p in chunk_paths],
            gap_report=gap_report,'''
)

with open('backend/app/data/downloader.py', 'w', encoding='utf-8') as f:
    f.write(content)
