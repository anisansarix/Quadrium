with open('backend/app/data/downloader.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    'canonical_path: str',
    'canonical_path: str\n    raw_paths: list[str]'
)

with open('backend/app/data/downloader.py', 'w', encoding='utf-8') as f:
    f.write(content)
