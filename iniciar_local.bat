@echo off
setlocal
cd /d "%~dp0"

echo ================================================
echo   TRADICION VIVA - inicio local seguro
echo ================================================
echo.

if not exist ".venv\Scripts\python.exe" (
  echo Creando un entorno virtual aislado en .venv...
  py -3.13 -m venv .venv 2>nul
  if errorlevel 1 py -m venv .venv
  if errorlevel 1 goto :error
)

set "PYTHON=.venv\Scripts\python.exe"

if not exist ".env" (
  echo Creando la configuracion local...
  "%PYTHON%" configurar_local.py
  if errorlevel 1 goto :error
)

echo Actualizando pip dentro del entorno virtual...
"%PYTHON%" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto :error

echo Instalando dependencias del proyecto...
"%PYTHON%" -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo Aplicando migraciones...
"%PYTHON%" manage.py migrate
if errorlevel 1 goto :error

echo Verificando el proyecto...
"%PYTHON%" manage.py check
if errorlevel 1 goto :error

echo.
echo Abriendo TRADICION VIVA en http://127.0.0.1:8000/
echo Para detener el servidor presiona Ctrl+C.
"%PYTHON%" manage.py runserver
exit /b 0

:error
echo.
echo No se pudo completar el inicio.
echo Cierra otros procesos de Python y vuelve a ejecutar este archivo.
pause
exit /b 1
