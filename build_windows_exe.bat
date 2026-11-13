@echo off
title NEON PRO - Windows Executable (.exe) Compiler for Harish
echo ====================================================================
echo   NEON PRO: Compiling Standalone Windows .EXE for Harish
echo ====================================================================
echo [1/3] Verifying Python & Installing PyInstaller...
python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller

echo.
echo [2/3] Compiling Standalone Windows Executable (.exe)...
pyinstaller --noconsole --onefile --clean --name "NeonMobile_Windows" main.py

echo.
echo [3/3] Packaging Complete!
echo ====================================================================
echo   SUCCESS! Standalone Executable generated:
echo   .\dist\NeonMobile_Windows.exe
echo ====================================================================
pause
