@echo off
echo Stopping OmniDoc...
docker compose down
echo Docker services stopped.
echo Close the API and Celery terminal windows manually.
pause