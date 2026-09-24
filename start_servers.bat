@echo off
echo Starting Quadrium Servers...

echo Starting FastAPI Backend...
start "Quadrium Backend" cmd /k "cd backend && .venv\Scripts\python.exe -m uvicorn app.main:app --reload"

echo Starting Vite Frontend...
start "Quadrium Frontend" cmd /k "cd frontend && npm run dev"

echo Servers are spinning up in separate windows!

