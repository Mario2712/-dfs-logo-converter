@echo off
REM Baut eine einzelne DFS-Logo-Converter.exe (kein Python auf dem Ziel-PC noetig).
REM Voraussetzung: Python 3.10+ von python.org (mit "tcl/tk" - ist Standard).
setlocal
cd /d "%~dp0"

if not exist .venv (
    python -m venv .venv || goto :error
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -e .[dev] || goto :error

pyinstaller --noconfirm --onefile --windowed ^
    --name "DFS-Logo-Converter" ^
    --collect-all tkinterdnd2 ^
    --collect-all imagequant ^
    --collect-all resvg_py ^
    --hidden-import PIL._tkinter_finder ^
    run_gui.py || goto :error

echo.
echo Fertig: dist\DFS-Logo-Converter.exe
goto :eof

:error
echo Build fehlgeschlagen.
exit /b 1
