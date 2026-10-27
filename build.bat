@echo off
setlocal
cd /d "%~dp0"

echo.
echo  Arma Queue Joiner - build
echo  -------------------------

if not exist .venv\Scripts\python.exe (
    echo  Creating virtual environment in .venv ...
    py -3.13 -m venv .venv 2>nul || python -m venv .venv || goto :fail
)

echo  Installing dependencies into .venv ...
.venv\Scripts\python -m pip install --upgrade pip --quiet || goto :fail
.venv\Scripts\python -m pip install -r requirements-dev.txt --quiet || goto :fail

echo  Running tests ...
.venv\Scripts\python -m pytest -q || goto :fail

echo  Building ...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
.venv\Scripts\pyinstaller ^
    --noconfirm --clean --onefile --windowed ^
    --name ArmaQueueJoiner ^
    --icon icon.ico ^
    --add-data "icon.ico;." ^
    --exclude-module tkinter ^
    --exclude-module unittest ^
    --exclude-module pydoc ^
    --exclude-module PySide6.QtQml ^
    --exclude-module PySide6.QtQuick ^
    --exclude-module PySide6.QtPdf ^
    --exclude-module PySide6.QtOpenGL ^
    app.py || goto :fail

echo.
echo  Done: dist\ArmaQueueJoiner.exe
exit /b 0

:fail
echo.
echo  Build failed.
exit /b 1
