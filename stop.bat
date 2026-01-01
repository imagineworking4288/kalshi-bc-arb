@echo off
echo Stopping Kalshi services...

for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8001 ^| findstr LISTENING 2^>nul') do taskkill /PID %%a /F 2>nul
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5173 ^| findstr LISTENING 2^>nul') do taskkill /PID %%a /F 2>nul

echo Done.
pause
