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
    --add-data "config.json;." ^
    --add-data "farm_plan.json;." ^
    --hidden-import win32timezone ^
    route_planner_gui.py

if not exist "dist\%APP_NAME%\_internal\templates\general\chest_blue.png" (
    echo.
    echo ERROR: template files were not copied into the app build.
    echo Missing: dist\%APP_NAME%\_internal\templates\general\chest_blue.png
    pause
    exit /b 1
)

copy /y "config.json" "dist\%APP_NAME%\config.json" >nul
copy /y "farm_plan.json" "dist\%APP_NAME%\farm_plan.json" >nul

if not exist "dist\%APP_NAME%\config.json" (
    echo.
    echo ERROR: config.json was not copied beside the app executable.
    pause
    exit /b 1
)

if not exist "dist\%APP_NAME%\farm_plan.json" (
    echo.
    echo ERROR: farm_plan.json was not copied beside the app executable.
    pause
    exit /b 1
)

if exist "dist\%APP_NAME%.zip" del /q "dist\%APP_NAME%.zip"

set ZIP_OK=0
for /L %%I in (1,1,3) do (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path 'dist\%APP_NAME%\*' -DestinationPath 'dist\%APP_NAME%.zip' -Force"
    if exist "dist\%APP_NAME%.zip" (
        set ZIP_OK=1
        goto zip_done
    )
    echo Zip attempt %%I failed; waiting before retry...
    timeout /t 2 /nobreak >nul
)

:zip_done
if not "%ZIP_OK%"=="1" (
    echo.
    echo ERROR: failed to create dist\%APP_NAME%.zip.
    pause
    exit /b 1
)

echo.
echo Build complete. Test locally:
echo dist\%APP_NAME%\%APP_NAME%.exe
echo.
echo Send this file to other users:
echo dist\%APP_NAME%.zip
echo.
echo They must extract the zip first, then run %APP_NAME%.exe inside the extracted folder.
pause
