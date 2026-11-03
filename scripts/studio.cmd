@echo off
setlocal
set "STUDIO=%USERPROFILE%\mba-studio"
set "BIN=%STUDIO%\bin"
if not exist "%BIN%" mkdir "%BIN%"
set "UV_PROJECT_ENVIRONMENT=%STUDIO%\.venv"
set "UV_PYTHON_INSTALL_DIR=%STUDIO%\python"
set "UV_CACHE_DIR=%STUDIO%\cache"
set "UV=%BIN%\uv.exe"
if not exist "%UV%" (
  powershell -NoProfile -Command "$zip = Join-Path $env:BIN 'uv.zip'; Invoke-WebRequest -Uri 'https://github.com/astral-sh/uv/releases/download/0.11.16/uv-x86_64-pc-windows-msvc.zip' -OutFile $zip; $hash = (Get-FileHash -Algorithm SHA256 $zip).Hash.ToLower(); if ($hash -ne 'dd9d6d6554bfab265bfa98aa8e8a406c5c3a7b97582f93de1f4d48d9154a0395') { Remove-Item $zip; exit 1 }; Expand-Archive -Path $zip -DestinationPath $env:BIN -Force"
  if errorlevel 1 exit /b 1
)
"%UV%" run --project "%~dp0.." lecture-study up
