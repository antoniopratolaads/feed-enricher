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
echo   http://localhost:8501
echo   Ctrl+C per fermare
echo ============================================
echo.

.venv\Scripts\python.exe -m streamlit run app.py --server.runOnSave true --browser.gatherUsageStats false

pause
