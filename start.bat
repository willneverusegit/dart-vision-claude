@echo off
REM Dart-Vision Startskript fuer Windows
REM Aktiviert venv und startet den Server auf Port 8000

echo ========================================
echo   Dart-Vision - Starte System...
echo ========================================
echo.

REM Pruefen ob Python verfuegbar ist
python --version >nul 2>&1
if errorlevel 1 (
    echo [FEHLER] Python nicht gefunden. Bitte Python 3.10+ installieren.
    echo          https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Pruefen ob venv existiert
if not exist ".venv\Scripts\activate.bat" (
    echo [INFO] Erstelle virtuelle Umgebung...
    python -m venv .venv
    if errorlevel 1 (
        echo [FEHLER] Konnte venv nicht erstellen.
        pause
        exit /b 1
    )
)

REM venv aktivieren
call .venv\Scripts\activate.bat

REM Pruefen ob Abhaengigkeiten installiert sind
python -c "import cv2" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installiere Abhaengigkeiten...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [FEHLER] Abhaengigkeiten konnten nicht installiert werden.
        pause
        exit /b 1
    )
)

REM Diagnose ausfuehren
echo.
echo [INFO] Systemdiagnose...
python -m src.diagnose
echo.

REM Server starten
echo [INFO] Starte Server auf http://localhost:8000
echo [INFO] Zum Beenden: Ctrl+C
echo.
uvicorn src.main:app --host 0.0.0.0 --port 8000

pause
