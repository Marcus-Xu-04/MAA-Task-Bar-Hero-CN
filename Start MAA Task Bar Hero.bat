@echo off
setlocal
cd /d "%~dp0"

if exist "C:\ProgramData\anaconda3\python.exe" (
    "C:\ProgramData\anaconda3\python.exe" route_planner_gui.py
) else (
    py -3 route_planner_gui.py
)
