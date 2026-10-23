@echo off
:: Runs CMD Helper directly from source (needs Python 3 installed).
cd /d "%~dp0"
python -m pip install -q -r requirements.txt
start "" pythonw cmd_helper.py
