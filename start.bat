@echo off
echo Starting Kalshi Arbitrage Scanner...
echo.

:: Start backend in new terminal
echo Starting backend server on port 8000...
start "Kalshi Backend" cmd /k "cd /d C:\Projects\kalshi-bc-arb && python -m uvicorn backend.main:app --reload --port 8000"

:: Give backend a moment to start
timeout /t 2 /nobreak >nul

:: Start frontend in new terminal
echo Starting frontend dev server...
start "Kalshi Frontend" cmd /k "cd /d C:\Projects\kalshi-bc-arb\frontend && npm run dev"

echo.
echo Both servers starting...
echo Backend: http://localhost:8000
echo Frontend: http://localhost:5173
echo.
echo Press any key to open the frontend in your browser...
pause >nul

:: Open browser to frontend
start http://localhost:5173
