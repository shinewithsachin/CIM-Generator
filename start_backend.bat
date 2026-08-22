@echo off
echo ============================================
echo   CIM Generator — Backend (FastAPI)
echo ============================================
cd /d "%~dp0backend"

echo.
echo [1/2] Installing Python dependencies...
pip install -r requirements.txt

echo.
echo [2/2] Starting FastAPI server on http://localhost:8000
echo       API docs available at http://localhost:8000/docs
echo.
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
pause
