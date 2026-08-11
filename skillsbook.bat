@echo off
REM Arranca Skills Book en Windows.  Uso: skillsbook.bat [--port 8777] [--dir ruta]
cd /d "%~dp0"
where py >nul 2>nul && (py -3 -m skillsbook %*) || (python -m skillsbook %*)
