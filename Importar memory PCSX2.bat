@echo off
setlocal
cd /d "%~dp0"

set "extra=--import-card-select"
if not "%~1"=="" set extra=--import-card "%~1"

where py >nul 2>nul
if not errorlevel 1 (
    py -3 competitive_loader.py %extra%
    goto :end
)

where python >nul 2>nul
if not errorlevel 1 (
    python competitive_loader.py %extra%
    goto :end
)

if exist "C:\Users\Admin\Documents\Codex\2026-10-11\ho\work\build-venv\bin\python.exe" (
    "C:\Users\Admin\Documents\Codex\2026-10-11\ho\work\build-venv\bin\python.exe" competitive_loader.py %extra%
    goto :end
)

echo.
echo No se encontro Python 3. Instala Python desde python.org y vuelve a intentarlo.

:end
echo.
pause
