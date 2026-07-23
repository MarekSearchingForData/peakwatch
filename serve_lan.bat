@echo off
rem Serve PeakWatch on the local network (other devices reach it at
rem http://<this-PC's-IP>:8511 — Windows will ask to allow through firewall).
cd /d "%~dp0"
py -m streamlit run app.py --server.port 8511 --server.address 0.0.0.0
