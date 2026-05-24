@echo off
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

python scripts\server.py

pause
