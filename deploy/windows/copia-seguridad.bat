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
REM Los prompts viven al lado de las skills, salvo que digas otra cosa.
if not defined SKILLSBOOK_PROMPTS (
  for %%D in ("%ORIGEN%\..") do set "SKILLSBOOK_PROMPTS=%%~fD\prompts"
)

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

REM Los prompts van en su propio zip: asi el de las skills se sigue
REM restaurando igual que siempre, descomprimiendolo dentro de su carpeta.
set "HAY_PROMPTS="
if exist "%SKILLSBOOK_PROMPTS%" dir /b "%SKILLSBOOK_PROMPTS%" 2>nul | findstr /r /c:"." >nul && set "HAY_PROMPTS=1"
if defined HAY_PROMPTS (
  powershell -NoProfile -Command ^
    "Compress-Archive -Path '%SKILLSBOOK_PROMPTS%\*' -DestinationPath '%DESTINO%\skillsbook-prompts-%SELLO%.zip' -Force"
  if errorlevel 1 (
    echo [ERROR] No se pudo copiar la carpeta de prompts.
    exit /b 1
  )
  echo Copia de los prompts: %DESTINO%\skillsbook-prompts-%SELLO%.zip
)

REM Rotacion: deja solo las 14 copias mas recientes de cada serie.
powershell -NoProfile -Command ^
  "Get-ChildItem '%DESTINO%\skillsbook-*.zip' -Exclude 'skillsbook-prompts-*' | Sort-Object LastWriteTime -Descending | Select-Object -Skip 14 | Remove-Item -Force"
powershell -NoProfile -Command ^
  "Get-ChildItem '%DESTINO%\skillsbook-prompts-*.zip' | Sort-Object LastWriteTime -Descending | Select-Object -Skip 14 | Remove-Item -Force"
exit /b 0
