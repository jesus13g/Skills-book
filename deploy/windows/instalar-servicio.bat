@echo off
REM ===================================================================
REM  Deja Skills Book arrancado siempre en un servidor Windows:
REM    1. abre el puerto en el firewall
REM    2. crea una tarea programada que lo lanza al encender la maquina
REM
REM  Ejecutar como Administrador (boton derecho > Ejecutar como admin).
REM ===================================================================
setlocal enableextensions
cd /d "%~dp0..\.."

set "TAREA=Skills Book"
set "BAT=%CD%\skillsbook-servidor.bat"
set "PUERTO=8777"
if exist "%CD%\servidor.env" (
  for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%CD%\servidor.env") do (
    if /i "%%~A"=="SKILLSBOOK_PORT" set "PUERTO=%%~B"
  )
)

net session >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Hace falta ejecutarlo como Administrador.
  pause
  exit /b 1
)

if not exist "%BAT%" (
  echo [ERROR] No encuentro %BAT%
  pause
  exit /b 1
)

echo.
echo   Aplicacion : %BAT%
echo   Puerto     : %PUERTO%
echo.

echo [1/2] Abriendo el puerto %PUERTO% en el firewall (solo redes privadas)...
netsh advfirewall firewall delete rule name="Skills Book" >nul 2>nul
netsh advfirewall firewall add rule name="Skills Book" dir=in action=allow ^
  protocol=TCP localport=%PUERTO% profile=private,domain >nul
if errorlevel 1 (
  echo     [AVISO] No se pudo crear la regla del firewall. Abre el puerto a mano.
) else (
  echo     Hecho.
)

echo [2/2] Creando la tarea programada "%TAREA%" (arranque de la maquina)...
schtasks /create /tn "%TAREA%" /tr "\"%BAT%\"" /sc onstart /ru SYSTEM /rl HIGHEST /f >nul
if errorlevel 1 (
  echo     [ERROR] No se pudo crear la tarea.
  pause
  exit /b 1
)
echo     Hecho.

echo.
echo   Arrancando ahora...
schtasks /run /tn "%TAREA%" >nul
echo.
echo   Listo. La aplicacion responde en http://IP-DE-ESTE-SERVIDOR:%PUERTO%/
echo   Para ver la IP:  ipconfig
echo   Para pararla:    schtasks /end /tn "%TAREA%"
echo   Para quitarla:   deploy\windows\desinstalar-servicio.bat
echo.
pause
