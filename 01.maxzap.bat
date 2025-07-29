REM cd "C:\__Projects\__dev_Massimo\maxzap"

@echo off
REM -- 1. Spostati nella cartella del batch (dove risiede lo script)
cd /d "%~dp0"

REM -- 2. Attiva il virtualenv (assumendo .venv nella cartella del progetto)
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
) else (
    echo Virtualenv non trovato in %~dp0\env
    pause
    exit /b 1
)

REM -- 3. Esegui lo script Python
REM    Modifica i parametri -d e -o a piacere:
REM python -m pyzap.cli run config.json --log-level DEBUG --step

REM Individual components can be tested via pytest. For example:
REM This isolates the Gmail polling logic using stubbed Google APIs.
REM pytest tests/test_trigger.py::test_gmail_poll_success
REM python -m pyzap.cli run config.json --log-level DEBUG --step

python -m pyzap.cli run azienda.agricola.json

REM -- 4. Mantieni aperta la finestra per leggere eventuali messaggi
echo.
echo Premere un tasto per chiudere...
REM pause