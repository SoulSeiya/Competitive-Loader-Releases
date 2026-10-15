@echo off
setlocal
cd /d "%~dp0"
if exist "%~dp0..\toolchain\msys64\ucrt64\bin\python.exe" (
    "%~dp0..\toolchain\msys64\ucrt64\bin\python.exe" local_online_test.py %*
    exit /b
)
where py >nul 2>nul
if not errorlevel 1 (
    py -3 local_online_test.py %*
    exit /b
)
python local_online_test.py %*
