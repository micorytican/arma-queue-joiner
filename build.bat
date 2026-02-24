@echo off
cd /d "%~dp0"

echo ====================================================
echo   Arma Reforger Queue Joiner | by lime98
echo ====================================================
echo.

echo [1/4] Cleaning old build folders...
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist

echo [2/4] Installing / updating dependencies...
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

echo [3/4] Installing / checking PyInstaller...
pip install pyinstaller --upgrade --quiet

echo [4/4] Building executable (onefile + hidden imports)...
pyinstaller ^
    --onefile ^
    --windowed ^
    --name "ArmaQueueJoiner" ^
    --icon=icon.ico ^
    --add-data "icon.ico;." ^
    --hidden-import=mss ^
    --hidden-import=numpy ^
    --hidden-import=PIL ^
    --hidden-import=PIL.Image ^
    --hidden-import=tkinter ^
    --hidden-import=tkinter.ttk ^
    --hidden-import=keyboard ^
    --hidden-import=winsound ^
    --clean ^
    app.py

echo.
echo ====================================================
echo Build finished!
echo Executable: dist\ArmaQueueJoiner.exe
echo.
echo ====================================================
echo.
pause