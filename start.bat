@echo off
echo Starting Kalshi Trading Platform...

set "PROJECT_DIR=%~dp0"
set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"

if not exist "%PROJECT_DIR%\logs" mkdir "%PROJECT_DIR%\logs"
if not exist "%PROJECT_DIR%\data" mkdir "%PROJECT_DIR%\data"

:: Kill anything on our ports first
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8001 ^| findstr LISTENING 2^>nul') do taskkill /PID %%a /F 2>nul
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5173 ^| findstr LISTENING 2^>nul') do taskkill /PID %%a /F 2>nul
timeout /t 2 /nobreak >nul

where wt >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    start "" wt -w 0 ^
        -d "%PROJECT_DIR%\frontend" --title "Frontend" cmd /k "npm run dev" ^; ^
        new-tab -d "%PROJECT_DIR%" --title "API" cmd /k "python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8001" ^; ^
        new-tab -d "%PROJECT_DIR%" --title "Scanners" cmd /k "python run_scanners.py" ^; ^
        new-tab -d "%PROJECT_DIR%" --title "Logs" cmd /k "python run_logs.py"
) else (
    start "Frontend" cmd /k "cd /d %PROJECT_DIR%\frontend && npm run dev"
    timeout /t 2 /nobreak >nul
    start "API" cmd /k "cd /d %PROJECT_DIR% && python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8001"
    timeout /t 3 /nobreak >nul
    start "Scanners" cmd /k "cd /d %PROJECT_DIR% && python run_scanners.py"
    start "Logs" cmd /k "cd /d %PROJECT_DIR% && python run_logs.py"
)

echo.
echo   Frontend:  http://localhost:5173
echo   Backend:   http://localhost:8001
echo.
timeout /t 5 /nobreak >nul
start http://localhost:5173
