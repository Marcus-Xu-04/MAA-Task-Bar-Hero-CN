@echo off
setlocal
cd /d "%~dp0"

set APP_NAME=MAA Task Bar Hero

if exist "C:\ProgramData\anaconda3\python.exe" (
    set PYTHON_EXE=C:\ProgramData\anaconda3\python.exe
) else (
    set PYTHON_EXE=py -3
)

%PYTHON_EXE% -m pip install -r requirements.txt
%PYTHON_EXE% -m PyInstaller ^
    --noconfirm ^
    --windowed ^
    --name "%APP_NAME%" ^
    --add-data "templates;templates" ^
    --hidden-import win32timezone ^
    route_planner_gui.py

echo.
echo Build complete. Open:
echo dist\%APP_NAME%\%APP_NAME%.exe
pause
