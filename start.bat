@echo off
REM ===================================================
REM Feed Enricher Pro — avvio sviluppo locale
REM ===================================================
REM Attiva venv, avvia Streamlit su http://localhost:8501
REM Hot reload: ogni modifica ai file Python ricarica la pagina

cd /d "%~dp0"

if not exist .venv\Scripts\python.exe (
    echo [!] Virtualenv non trovato. Creo con Python di sistema...
    python -m venv .venv
    .venv\Scripts\python.exe -m pip install --upgrade pip
    .venv\Scripts\python.exe -m pip install -r requirements.txt
)

echo.
echo ============================================
echo   Feed Enricher Pro — Dev Server
echo   http://localhost:8502
echo   Ctrl+C per fermare
echo ============================================
echo.

REM Skip email prompt primo avvio
if not exist "%USERPROFILE%\.streamlit" mkdir "%USERPROFILE%\.streamlit"
if not exist "%USERPROFILE%\.streamlit\credentials.toml" (
    > "%USERPROFILE%\.streamlit\credentials.toml" echo [general]
    >> "%USERPROFILE%\.streamlit\credentials.toml" echo email = ""
)

.venv\Scripts\python.exe -m streamlit run app.py --server.port 8502 --server.runOnSave true --server.headless true --browser.gatherUsageStats false

pause
