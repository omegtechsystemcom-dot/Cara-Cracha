@echo off
setlocal
title Sistema de Crachas - IEMA
cd /d "%~dp0"

echo ============================================
echo   SISTEMA DE MONTAGEM DE CRACHAS - IEMA
echo ============================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_server.ps1" -Foreground
if errorlevel 1 (
    echo.
    echo [ERRO] Falha ao iniciar o sistema.
    pause
    exit /b 1
)

echo.
echo Sistema carregado em:
echo http://127.0.0.1:5000/
echo.
pause

endlocal
