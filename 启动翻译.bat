@echo off
chcp 65001 >nul
title 翻译工具 - 一键启动

setlocal enabledelayedexpansion

echo ════════════════════════════════════
echo       翻译工具 - 一键启动
echo ════════════════════════════════════
echo.

:: ═══════════════════════════════════════════
:: 自定义配置区
:: ═══════════════════════════════════════════
::
:: Python 路径（如果 Python 在非标准位置，就填这里）
:: 留空则自动从系统 PATH 查找
::
:: 示例:
::   set PYTHON_PATH=C:\MyPython\python.exe
::   set PYTHON_PATH=D:\Tools\Python311\python.exe
::
set PYTHON_PATH=
::
:: ═══════════════════════════════════════════

:: ── 1. 找 Python ──
echo [1/3] 检查 Python...

if not "%PYTHON_PATH%"=="" (
    if exist "%PYTHON_PATH%" (
        set PY_EXE=%PYTHON_PATH%
        goto :python_found
    ) else (
        echo    ⚠ 自定义路径不存在: %PYTHON_PATH%
        echo    将尝试从系统环境变量查找...
    )
)

:: 自动查找
where python >nul 2>nul
if errorlevel 1 (
    echo ❌ 未找到 Python！
    echo.
    echo 请安装 Python: https://www.python.org/downloads/
    echo 安装时务必勾选 ☑ "Add Python to PATH"
    echo.
    echo 如果已安装但不在 PATH 中，请修改本文件顶部
    echo set PYTHON_PATH=^<你的Python路径^>
    echo.
    pause
    exit /b
)
set PY_EXE=python

:python_found
for /f "tokens=2" %%i in ('"%PY_EXE%" --version 2^>^&1') do echo   检测到 Python %%i ✓
echo.

:: ── 2. 安装依赖 ──
echo [2/3] 安装依赖（只需首次运行）...
"%PY_EXE%" -m pip install --upgrade pip -q
"%PY_EXE%" -m pip install -r "%~dp0requirements.txt" -q
if errorlevel 1 (
    echo ❌ 依赖安装失败，请检查网络连接
    pause
    exit /b
)
echo   依赖就绪 ✓
echo.

:: ── 3. 启动 ──
echo [3/3] 启动翻译工具...
echo.
echo   💡 复制文本后按快捷键翻译（默认 Ctrl+T）
echo   💡 点击弹窗中的译文即可复制
echo   💡 关闭小窗口即隐藏到系统托盘
echo.
start "" "%PY_EXE%" "%~dp0main.py"
echo ✅ 启动成功
timeout /t 3 /nobreak >nul
