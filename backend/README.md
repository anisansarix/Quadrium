# Quadrium Backend

FastAPI-based backend for the Quadrium trading research platform.

## Setup

```bash
python -m uv venv .venv
.venv\Scripts\activate
python -m uv pip install -e ".[dev]"
```

## Run

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
