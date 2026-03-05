@echo off
title SEC EDGAR Filing Viewer - Launcher
echo ============================================
echo   SEC EDGAR Filing Viewer - Starting...
echo ============================================
echo.

:: Start backend API server in a new window
echo Starting Backend API on http://127.0.0.1:8000 ...
start "EDGAR API Backend" cmd /k "cd /d %~dp0 && C:\Users\sujay.palande\AppData\Local\Programs\Python\Python313\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000"

:: Wait a moment for backend to start
timeout /t 3 /nobreak >nul

:: Start frontend dev server in a new window
echo Starting Frontend on http://localhost:3000 ...
start "EDGAR Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

:: Wait for frontend to start
timeout /t 4 /nobreak >nul

:: Open browser
echo Opening browser...
start http://localhost:3000

echo.
echo ============================================
echo   Both servers are running!
echo   Backend:  http://127.0.0.1:8000
echo   Frontend: http://localhost:3000
echo ============================================
echo   Close the two CMD windows to stop.
echo ============================================
pause
