@echo off
setlocal EnableDelayedExpansion

cd /d "%~dp0"

echo.
echo ======================================================
echo   Arma Reforger Queue Joiner - Build Script
echo ======================================================
echo.

echo [1/5] Cleaning old folders...
if exist build rmdir /s /q build >nul 2>&1
if exist dist  rmdir /s /q dist  >nul 2>&1
if exist *.spec del /q *.spec >nul 2>&1

echo [2/5] Updating pip and installing dependencies...
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

echo [3/5] Installing / upgrading PyInstaller...
pip install pyinstaller --upgrade --quiet

echo [4/5] Building executable...
pyinstaller ^
    --onefile ^
    --noconsole ^
    --name "ArmaQueueJoiner" ^
    --icon=icon.ico ^
    --add-data "icon.ico;." ^
    --hidden-import=mss ^
    --hidden-import=numpy ^
    --hidden-import=numpy.core ^
    --hidden-import=numpy.lib ^
    --hidden-import=tkinter ^
    --hidden-import=tkinter.ttk ^
    --hidden-import=keyboard ^
    --hidden-import=winsound ^
    --hidden-import=pkg_resources ^
    --clean ^
    app.py

if %errorlevel% neq 0 (
    echo.
    echo ERROR: PyInstaller failed.
    pause
    exit /b 1
)

echo.
echo ======================================================
echo Build finished!
echo.
echo Executable:   dist\ArmaQueueJoiner.exe
echo.
echo To test (console will stay open):
echo   cd dist
echo   ArmaQueueJoiner.exe
echo.
echo If it works → change --console to --windowed and rebuild
echo ======================================================
echo.

pause