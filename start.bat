@echo off
echo Starting Kalshi Arbitrage Scanner...
echo.

:: Get the directory where this script is located
set "PROJECT_DIR=%~dp0"
:: Remove trailing backslash
set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"

:: Check if Windows Terminal is available
where wt >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo Using Windows Terminal with tabs...
    
    :: Open Windows Terminal with two tabs
    :: The semicolon must be escaped with ^ in batch files
    start "" wt -w 0 -d "%PROJECT_DIR%" --title Backend cmd /k "python -m uvicorn backend.main:app --reload --port 8000" ^; new-tab -d "%PROJECT_DIR%\frontend" --title Frontend cmd /k "npm run dev"
    
    echo.
    echo Both servers starting in Windows Terminal tabs...
) else (
    echo Windows Terminal not found, using separate windows...
    
    :: Start backend in new terminal window
    echo Starting backend server on port 8000...
    start "Kalshi Backend" cmd /k "cd /d %PROJECT_DIR% && python -m uvicorn backend.main:app --reload --port 8000"
    
    :: Give backend a moment to start
    timeout /t 2 /nobreak >nul
    
    :: Start frontend in new terminal window
    echo Starting frontend dev server...
    start "Kalshi Frontend" cmd /k "cd /d %PROJECT_DIR%\frontend && npm run dev"
    
    echo.
    echo Both servers starting in separate windows...
)

echo.
echo Backend:  http://localhost:8001
echo Frontend: http://localhost:5173
echo API Docs: http://localhost:8000/docs
echo.

:: Wait for servers to initialize
timeout /t 3 /nobreak >nul

:: Open browser to frontend
echo Opening browser...
start http://localhost:5173