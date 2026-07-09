@echo off
title Servidor - Tracker Oposiciones
echo ==================================================
echo   INICIANDO EL TRACKER DE OPOSICIONES (PLAN PRO)
echo ==================================================
echo.

:: 1. Entramos en la carpeta del backend
cd backend

:: 2. Abrimos el navegador (le damos la orden a Windows)
echo Abriendo el navegador en http://localhost:8000...
start http://localhost:8000

:: 3. Levantamos el servidor de FastAPI
echo Levantando el motor... (Cierra esta ventana para apagar el servidor)
echo.
python run.py

pause