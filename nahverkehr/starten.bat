@echo off
rem Richtet MOTIS ein (beim ersten Mal: laden und importieren) und startet den Server.
rem Start per Doppelklick; beenden mit Strg+C oder durch Schließen des Fensters.
chcp 65001 >nul
cd /d "%~dp0"
python motis_einrichten.py --server
echo.
pause
