@echo off
echo ============================================
echo   CIM Generator — Starting All Services
echo ============================================
echo.
echo Starting backend in a new window...
start "CIM Backend" cmd /k "%~dp0start_backend.bat"

echo Waiting 5 seconds for backend to initialize...
timeout /t 5 /nobreak > nul

echo Starting frontend in a new window...
start "CIM Frontend" cmd /k "%~dp0start_frontend.bat"

echo.
echo ============================================
echo   Services starting:
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:3000
echo   API Docs: http://localhost:8000/docs
echo ============================================
echo.
echo Opening browser in 8 seconds...
timeout /t 8 /nobreak > nul
start http://localhost:3000
