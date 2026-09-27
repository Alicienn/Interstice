@echo off
rem Lance l'application Interstice (API + interface) puis ouvre le navigateur.
rem Fermer cette fenetre arrete l'application.
cd /d "%~dp0"
title Interstice - http://127.0.0.1:8765
start "" http://127.0.0.1:8765
uv run interstice serve --port 8765
