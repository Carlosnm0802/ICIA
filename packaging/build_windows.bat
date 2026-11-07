@echo off
setlocal
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
  echo No existe .venv. Crea el entorno virtual antes de compilar.
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install -r requirements-build.txt
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean packaging\icia.spec
if errorlevel 1 exit /b 1
copy /Y run_app.bat dist\ >nul
copy /Y iniciar_icia.vbs dist\ >nul
copy /Y detener_icia.bat dist\ >nul
echo Paquete listo en dist\. Copia dist\ a C:\ICIA en la laptop del dueno.
exit /b 0
