@echo off
:: Builds a single portable CMD-Helper.exe in the "dist" folder.
:: Needs Python 3 from python.org (tick "Add python.exe to PATH" when installing).
cd /d "%~dp0"
python -m pip install --upgrade pyinstaller || goto :error
python -m PyInstaller --noconfirm --onefile --windowed --name CMD-Helper --add-data "commands.json;." cmd_helper.py || goto :error
echo.
echo Done! Your portable program is: %~dp0dist\CMD-Helper.exe
pause
exit /b 0
:error
echo.
echo Build failed - see the messages above.
pause
exit /b 1
