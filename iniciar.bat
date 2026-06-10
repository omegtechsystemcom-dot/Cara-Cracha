@echo off
title Sistema de Crachás - IEMA
cd /d "%~dp0"

echo ============================================
echo   SISTEMA DE MONTAGEM DE CRACHÁS
echo   IEMA - Instituto Estadual de Educação,
echo   Ciência e Tecnologia do Maranhão
echo ============================================
echo.
echo Iniciando servidor web...
echo.

.venv\Scripts\python main.py

if %errorlevel% neq 0 (
    echo.
    echo Erro ao executar! Verifique o ambiente virtual.
    echo Tente: python -m venv .venv
    pause
)
