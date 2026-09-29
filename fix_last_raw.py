with open('backend/scripts/mt5_time_translation_acceptance.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('last_raw = df_raw[\'time\'].max()', 'last_raw = df_raw[\'time\'].max()  # noqa: F841')

with open('backend/scripts/mt5_time_translation_acceptance.py', 'w', encoding='utf-8') as f:
    f.write(content)
