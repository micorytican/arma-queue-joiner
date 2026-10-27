@echo off
rem Build Arma Queue Joiner.
rem   build.bat         portable dist\ArmaQueueJoiner.exe
rem   build.bat all     portable exe + installer (needs Inno Setup 6)
rem Set DIST to build somewhere else, e.g. while the app is running from dist.
setlocal
cd /d "%~dp0"
if "%DIST%"=="" set "DIST=dist"

echo.
echo  Arma Queue Joiner - build
echo  -------------------------

if not exist .venv\Scripts\python.exe (
    echo  Creating virtual environment in .venv ...
    py -3.13 -m venv .venv 2>nul || python -m venv .venv || goto :fail
)
set "PY=.venv\Scripts\python.exe"

echo  Installing dependencies into .venv ...
%PY% -m pip install --upgrade pip --quiet || goto :fail
%PY% -m pip install -r requirements-dev.txt --quiet || goto :fail

echo  Checking code ...
%PY% -m ruff check . || goto :fail
%PY% -m pytest -q || goto :fail

for /f %%v in ('%PY% -c "import aqj; print(aqj.__version__)"') do set "VERSION=%%v"
echo  Version %VERSION%
%PY% tools\version_info.py build\version_info.txt >nul || goto :fail

set PYI_ARGS=--noconfirm --clean --windowed --icon icon.ico --version-file build\version_info.txt ^
 --add-data "icon.ico;." --add-data "aqj\ui\fonts;aqj\ui\fonts" --exclude-module tkinter --exclude-module unittest --exclude-module pydoc ^
 --exclude-module PySide6.QtQml --exclude-module PySide6.QtQuick --exclude-module PySide6.QtPdf ^
 --exclude-module PySide6.QtOpenGL --distpath "%DIST%"

echo  Building portable exe ...
%PY% -m PyInstaller %PYI_ARGS% --onefile --name ArmaQueueJoiner --workpath build\onefile app.py || goto :fail

if /i not "%1"=="all" goto :done

echo  Building installer ...
%PY% -m PyInstaller %PYI_ARGS% --onedir --name ArmaQueueJoiner --workpath build\onedir app.py || goto :fail
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
    echo  Inno Setup 6 not found. Install it from https://jrsoftware.org/isinfo.php
    goto :fail
)
"%ISCC%" /Q /DAppVersion=%VERSION% installer\ArmaQueueJoiner.iss || goto :fail

:done
echo.
echo  Done. Output is in %DIST%\
exit /b 0

:fail
echo.
echo  Build failed.
exit /b 1
