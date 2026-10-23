@echo off
:: Runs CMD Helper directly from source (needs Python 3 installed).
cd /d "%~dp0"
start "" pythonw cmd_helper.py
