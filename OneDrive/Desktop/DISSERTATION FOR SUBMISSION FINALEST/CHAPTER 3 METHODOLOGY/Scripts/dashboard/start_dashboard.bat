@echo off
cd /d "%~dp0"
python -m pip install -r requirements.txt
shiny run --launch-browser dash08_import_and_records.py
pause
