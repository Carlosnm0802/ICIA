@echo off
setlocal
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
  echo [ICIA] No existe .venv. Crea el entorno virtual con Python 3.12 antes de compilar.
  exit /b 1
)

echo [ICIA] Instalando dependencias de ejecucion y de compilacion...
".venv\Scripts\python.exe" -m pip install -r requirements.txt -r requirements-build.txt
if errorlevel 1 (
  echo [ICIA] No se pudieron instalar las dependencias.
  exit /b 1
)

echo [ICIA] Compilando paquete con PyInstaller...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean packaging\icia.spec
if errorlevel 1 (
  echo [ICIA] La compilacion fallo.
  exit /b 1
)

copy /Y run_app.bat dist\ >nul
copy /Y iniciar_icia.vbs dist\ >nul
copy /Y detener_icia.bat dist\ >nul
copy /Y packaging\crear_acceso_directo.vbs dist\ >nul

echo.
echo [ICIA] Paquete listo en dist\.
echo [ICIA] 1. Copia la carpeta dist\ completa a C:\ICIA (no a Program Files).
echo [ICIA] 2. Abre C:\ICIA\crear_acceso_directo.vbs para crear el acceso directo.
echo [ICIA] 3. Usa el acceso directo ICIA del Escritorio para iniciar el sistema.
exit /b 0
