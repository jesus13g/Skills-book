@echo off
REM ===================================================================
REM  Skills Book — arranque como servidor de la LAN (Windows).
REM
REM  Escucha en todas las interfaces para que cualquiera de la oficina
REM  entre por http://IP-DEL-SERVIDOR:8777/
REM
REM  Configuracion: edita servidor.env (al lado de este .bat).
REM  Uso: skillsbook-servidor.bat [--port 8777] [--dir D:\ruta\skills]
REM ===================================================================
setlocal enableextensions
cd /d "%~dp0"

REM --- Configuracion desde servidor.env (lineas CLAVE=valor, # comentario)
if exist "%~dp0servidor.env" (
  for /f "usebackq eol=# tokens=1,* delims==" %%A in ("%~dp0servidor.env") do (
    if not "%%~A"=="" if not "%%~B"=="" set "%%~A=%%~B"
  )
)

REM --- Valores por defecto (no pisan lo que ya venga del entorno)
if not defined SKILLSBOOK_HOST set "SKILLSBOOK_HOST=0.0.0.0"
if not defined SKILLSBOOK_PORT set "SKILLSBOOK_PORT=8777"
if not defined SKILLSBOOK_HOME set "SKILLSBOOK_HOME=%~dp0data\skills"
if not defined SKILLSBOOK_ALLOW_PATH_IMPORT set "SKILLSBOOK_ALLOW_PATH_IMPORT=0"
set "SKILLSBOOK_NO_BROWSER=1"
set "SKILLSBOOK_STRICT_PORT=1"

REM --- La carpeta de datos tiene que existir antes de arrancar
if not exist "%SKILLSBOOK_HOME%" mkdir "%SKILLSBOOK_HOME%" 2>nul
if not exist "%SKILLSBOOK_HOME%" (
  echo [ERROR] No se pudo crear la carpeta de la biblioteca:
  echo         %SKILLSBOOK_HOME%
  echo         Revisa la ruta o los permisos de la cuenta que ejecuta esto.
  exit /b 1
)

REM --- Primera vez: sembrar con las skills de ejemplo del repositorio
dir /b /a "%SKILLSBOOK_HOME%" 2>nul | findstr /r /c:"." >nul
if errorlevel 1 (
  if exist "%~dp0skills" (
    echo   Biblioteca vacia: copiando las skills de ejemplo.
    xcopy "%~dp0skills" "%SKILLSBOOK_HOME%" /e /i /q /y >nul
  )
)

REM --- Interprete de Python
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (where python >nul 2>nul && set "PY=python")
if not defined PY (
  echo [ERROR] No se encontro Python 3.9 o superior en el PATH.
  echo         Instalalo desde https://www.python.org/downloads/windows/
  echo         marcando "Add python.exe to PATH".
  exit /b 1
)

echo.
echo   Biblioteca : %SKILLSBOOK_HOME%
echo   Escuchando : %SKILLSBOOK_HOST%:%SKILLSBOOK_PORT%
if not defined SKILLSBOOK_TOKEN echo   [AVISO] Sin SKILLSBOOK_TOKEN: cualquiera en la red puede editar y borrar.
echo.

%PY% -m skillsbook %*
set "CODE=%errorlevel%"
if not "%CODE%"=="0" (
  echo.
  echo   Skills Book termino con codigo %CODE%.
  REM Si alguien lo lanzo con doble clic, que el error se pueda leer.
  if /i "%~1"=="" pause
)
exit /b %CODE%
