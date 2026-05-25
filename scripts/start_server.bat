@echo off
setlocal

for /f "tokens=5" %%a in ('netstat -ano ^| findstr /R /C:":8000 "') do set EXISTING_PID=%%a

if defined EXISTING_PID (
    echo.
    echo Port 8000 is already in use by PID %EXISTING_PID%.
    echo Stopping the existing server...
    taskkill /PID %EXISTING_PID% /F >nul 2>&1
    timeout /t 2 /nobreak >nul
)

echo.
echo   Lebanese Laws ^& Tenders RAG System
echo   ====================================
echo.
echo   Starting API server...
echo   API Documentation : http://localhost:8000/docs
echo   Health Check       : http://localhost:8000/health
echo   Frontend           : frontend\index.html
echo.
echo   Press Ctrl+C to stop
echo.

python "%~dp0server.py"

pause
endlocal
