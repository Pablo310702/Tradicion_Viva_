@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" manage.py respaldo_diario
) else if exist ".venv-1\Scripts\python.exe" (
  ".venv-1\Scripts\python.exe" manage.py respaldo_diario
) else (
  echo No se encontro el entorno virtual de Python.
  exit /b 1
)

endlocal
