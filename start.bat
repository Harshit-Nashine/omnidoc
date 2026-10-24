@echo off
echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║                  OmniDoc Demo Startup                      ║
echo ║          All services starting... please wait              ║
echo ╚════════════════════════════════════════════════════════════╝
echo.

echo Starting Docker services...
docker compose up -d

echo Waiting for databases to be ready...
timeout /t 15 /nobreak > nul

echo Starting API server...
start "OmniDoc API" cmd /k "cd /d D:\omnidoc && venv\Scripts\activate && uvicorn services.api.app.main:app --reload --host 0.0.0.0 --port 8000"

echo Starting Celery worker...
start "OmniDoc Celery" cmd /k "cd /d D:\omnidoc && venv\Scripts\activate && celery -A services.api.app.celery_app worker --loglevel=info --pool=solo"

echo Starting React frontend...
start "OmniDoc Frontend" cmd /k "cd /d D:\omnidoc\frontend && npm start"

echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║                  OmniDoc Ready!                            ║
echo ║                                                            ║
echo ║  Frontend:    http://localhost:3001                       ║
echo ║  Login:       admin@testcompany.com / SecurePass123      ║
echo ║  Grafana:     http://localhost:3000 (admin/admin)        ║
echo ║  Guide:       Open DEMO_GUIDE.md in this folder          ║
echo ║                                                            ║
echo ║  Follow DEMO_GUIDE.md for complete walkthrough           ║
echo ╚════════════════════════════════════════════════════════════╝
echo.
timeout /t 5 /nobreak > nul