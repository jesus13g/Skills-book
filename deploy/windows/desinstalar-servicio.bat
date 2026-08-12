@echo off
REM  Quita la tarea programada y la regla de firewall de Skills Book.
REM  Los datos (la carpeta data\skills) NO se tocan.
REM  Ejecutar como Administrador.
setlocal enableextensions

net session >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Hace falta ejecutarlo como Administrador.
  pause
  exit /b 1
)

echo Parando y borrando la tarea "Skills Book"...
schtasks /end /tn "Skills Book" >nul 2>nul
schtasks /delete /tn "Skills Book" /f >nul 2>nul

echo Borrando la regla del firewall...
netsh advfirewall firewall delete rule name="Skills Book" >nul 2>nul

echo.
echo Hecho. Las skills siguen en data\skills.
pause
