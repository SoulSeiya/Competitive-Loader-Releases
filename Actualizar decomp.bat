@echo off
setlocal
cd /d "%~dp0"

set "extra=--select-release"
if not "%~1"=="" set "extra=--release %1"

if exist "%~dp0..\toolchain\msys64\ucrt64\bin\python.exe" (
    "%~dp0..\toolchain\msys64\ucrt64\bin\python.exe" competitive_loader.py %extra%
    goto :end
)

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


echo.
echo No se encontro Python 3. Instala Python desde python.org y vuelve a intentarlo.

:end
echo.
pause
