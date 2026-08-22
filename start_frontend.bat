@echo off
echo ============================================
echo   CIM Generator — Frontend (React + Vite)
echo ============================================
cd /d "%~dp0frontend"

echo.
echo [1/2] Installing Node dependencies...
npm install

echo.
echo [2/2] Starting React dev server on http://localhost:3000
echo.
npm run dev
pause
