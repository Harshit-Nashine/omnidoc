@echo off
echo Starting OmniDoc...

echo Starting Docker services...
docker compose up -d

echo Waiting for databases to be ready...
timeout /t 15 /nobreak > nul

echo Starting API server...
start "OmniDoc API" cmd /k "cd /d D:\omnidoc && venv\Scripts\activate && uvicorn services.api.app.main:app --reload --host 0.0.0.0 --port 8000"

echo Starting Celery worker...
start "OmniDoc Celery" cmd /k "cd /d D:\omnidoc && venv\Scripts\activate && celery -A services.api.app.celery_app worker --loglevel=info --pool=solo"

echo Starting React frontend...
start "OmniDoc Frontend" cmd /k "cd /d D:\omnidoc\frontend && npm start -- --open http://localhost:3001/launchpad"

echo.
echo OmniDoc is starting up...
echo API:      http://localhost:8000
echo Frontend: http://localhost:3001 (or 3000 if Grafana not running)
echo Swagger:  http://localhost:8000/docs
echo Grafana:  http://localhost:3000
echo.
echo All services launched. Check the opened terminals for status.
pause