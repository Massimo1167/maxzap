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
python -m pyzap.cli run

REM -- 4. Mantieni aperta la finestra per leggere eventuali messaggi
echo.
echo Premere un tasto per chiudere...
REM pause