@echo off
REM  Copia de seguridad de la biblioteca en un .zip con fecha.
REM
REM    deploy\windows\copia-seguridad.bat
REM    deploy\windows\copia-seguridad.bat D:\SkillsBook\data\skills \\NAS\backups
REM
REM  Programalo a diario con:
REM    schtasks /create /tn "Skills Book backup" /tr "\"%CD%\deploy\windows\copia-seguridad.bat\"" /sc daily /st 22:00 /ru SYSTEM
setlocal enableextensions
cd /d "%~dp0..\.."

set "ORIGEN=%~1"
if not defined ORIGEN set "ORIGEN=%CD%\data\skills"
set "DESTINO=%~2"
if not defined DESTINO set "DESTINO=%CD%\backups"

if not exist "%ORIGEN%" (
  echo [ERROR] No existe la biblioteca: %ORIGEN%
  exit /b 1
)
if not exist "%DESTINO%" mkdir "%DESTINO%"

REM Fecha ordenable AAAAMMDD-HHMMSS, independiente del formato regional.
for /f %%T in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set "SELLO=%%T"
set "ARCHIVO=%DESTINO%\skillsbook-%SELLO%.zip"

powershell -NoProfile -Command ^
  "Compress-Archive -Path '%ORIGEN%\*' -DestinationPath '%ARCHIVO%' -Force"
if errorlevel 1 (
  echo [ERROR] No se pudo crear la copia.
  exit /b 1
)
echo Copia creada: %ARCHIVO%

REM Rotacion: deja solo las 14 copias mas recientes.
powershell -NoProfile -Command ^
  "Get-ChildItem '%DESTINO%\skillsbook-*.zip' | Sort-Object LastWriteTime -Descending | Select-Object -Skip 14 | Remove-Item -Force"
exit /b 0
