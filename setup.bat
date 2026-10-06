```bat
@echo off

cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Khong tim thay Python trong venv
    echo Path: %~dp0venv\Scripts\python.exe
    pause
    exit /b 1
)

echo Starting Uvicorn...
echo.

venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8087

if errorlevel 1 (
    echo.
    echo [ERROR] Uvicorn stopped with error.
    pause
)

exit /b %errorlevel%
```
