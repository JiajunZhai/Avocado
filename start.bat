@echo off
title Avocado Workspace Matrix Server
color 0A

:: Start Backend
echo [1/3] Initiating Avocado Backend Engine (Uvicorn - Port 8000)...
start "Avocado Backend" cmd /c "cd backend && uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

:: Give backend a slight head start
timeout /t 2 /nobreak > NUL

:: Start Frontend
echo [2/3] Initiating Avocado Frontend Matrix (Vite - Port 5173)...
start "Avocado Frontend" cmd /c "cd frontend && npm run dev"

:: Wait for services to mount
echo [3/3] Waiting for matrix to mount...
timeout /t 4 /nobreak > NUL

:: Launch Browser
echo Launching Avocado Workspace Hub...
start http://localhost:5173

echo.
echo ========================================================
echo Avocado Matrix is now online.
echo Do NOT close this window if you want to see status logs.
echo ========================================================
pause
