@echo off
REM ===================================================
REM Feed Enricher Pro — deploy droplet
REM ===================================================
REM 1. git commit + push (se ci sono modifiche)
REM 2. SSH droplet: git pull + docker-compose rebuild
REM
REM Usage: deploy.bat "commit message opzionale"

cd /d "%~dp0"

set COMMIT_MSG=%~1
if "%COMMIT_MSG%"=="" set COMMIT_MSG=update

echo.
echo ============================================
echo   Deploy su http://161.35.91.142/feed/
echo ============================================
echo.

REM -------- Fase 1: commit + push --------
git status --short
echo.
git add -A
git diff --cached --quiet
if errorlevel 1 (
    git commit -m "%COMMIT_MSG%"
    git push
    if errorlevel 1 (
        echo [X] git push fallito
        exit /b 1
    )
) else (
    echo [i] Nessuna modifica da committare — riallineo solo il droplet.
)

REM -------- Fase 2: rebuild droplet --------
echo.
echo [>] Rebuild container droplet...
ssh root@161.35.91.142 "cd /opt/feed-enricher && git pull && BASE_URL_PATH=feed docker-compose up -d --build 2>&1 | tail -5"

if errorlevel 1 (
    echo [X] Deploy droplet fallito
    exit /b 1
)

echo.
echo [OK] Deploy completato — http://161.35.91.142/feed/
echo.
pause
