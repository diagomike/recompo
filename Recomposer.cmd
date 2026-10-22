@echo off
rem Starts the Recomposer studio (http://127.0.0.1:8770) and opens it in the browser.
rem Optional: start the local hub too with  Recomposer.cmd hub
rem or the hub for your other PCs on this network with  Recomposer.cmd hub-lan  (Windows asks to allow the port once)
cd /d "%~dp0"
if /i "%1"=="hub" start "Recomposer hub" .venv\Scripts\python.exe -m hub --port 8790
if /i "%1"=="hub-lan" start "Recomposer hub (LAN)" .venv\Scripts\python.exe -m hub --host 0.0.0.0 --port 8790
start "" http://127.0.0.1:8770
.venv\Scripts\recomp.exe serve --port 8770
