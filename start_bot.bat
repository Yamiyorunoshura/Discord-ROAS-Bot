@echo off
REM Discord ADR Bot - Windows 批次啟動腳本
REM 自動檢測並創建虛擬環境，兼容 Windows 系統

setlocal enabledelayedexpansion

:: 設定控制台代碼頁為 UTF-8
chcp 65001 >nul

:: 顏色設定
set "RED=91"
set "GREEN=92" 
set "YELLOW=93"
set "BLUE=94"
set "CYAN=96"
set "WHITE=97"

:: 顯示橫幅
echo.
echo [%CYAN%m╔══════════════════════════════════════════════════════════════╗[0m
echo [%CYAN%m║              Discord ADR Bot - Windows                       ║[0m
echo [%CYAN%m║                智能啟動腳本 (批次版本)                        ║[0m
echo [%CYAN%m║             支援自動虛擬環境檢測與創建 (Windows)              ║[0m
echo [%CYAN%m╚══════════════════════════════════════════════════════════════╝[0m
echo.

:: 檢查 Python 是否安裝
echo [%BLUE%m[1/5] 檢查 Python 安裝...[0m
python --version >nul 2>&1
if errorlevel 1 (
    echo [%RED%m❌ Python 未安裝或不在 PATH 中[0m
    echo [%YELLOW%m請從 https://python.org 下載並安裝 Python 3.10+[0m
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo [%GREEN%m✅ Python 版本: %PYTHON_VERSION%[0m

:: 檢查 uv 是否安裝
echo [%BLUE%m[2/5] 檢查 uv 包管理器...[0m
uv --version >nul 2>&1
if errorlevel 1 (
    echo [%YELLOW%m⚠️  uv 未安裝，正在安裝...[0m
    
    :: 使用 PowerShell 安裝 uv
    powershell -Command "& {Invoke-RestMethod -Uri https://astral.sh/uv/install.ps1 | Invoke-Expression}" >nul 2>&1
    if errorlevel 1 (
        echo [%RED%m❌ uv 安裝失敗[0m
        echo [%YELLOW%m請手動安裝 uv: https://docs.astral.sh/uv/getting-started/installation/[0m
        pause
        exit /b 1
    )
    
    :: 重新檢查
    uv --version >nul 2>&1
    if errorlevel 1 (
        echo [%RED%m❌ uv 安裝後仍無法使用[0m
        echo [%YELLOW%m請重新啟動命令提示字元或手動將 uv 添加到 PATH[0m
        pause
        exit /b 1
    )
)

for /f "tokens=*" %%i in ('uv --version 2^>^&1') do set UV_VERSION=%%i
echo [%GREEN%m✅ uv 版本: %UV_VERSION%[0m

:: 檢查虛擬環境
echo [%BLUE%m[3/5] 檢查虛擬環境...[0m
set "VENV_FOUND=0"

:: 檢查常見的虛擬環境目錄
if exist ".venv\Scripts\python.exe" (
    set "VENV_PATH=.venv"
    set "VENV_FOUND=1"
) else if exist "venv\Scripts\python.exe" (
    set "VENV_PATH=venv"
    set "VENV_FOUND=1"
) else if exist ".env\Scripts\python.exe" (
    set "VENV_PATH=.env"
    set "VENV_FOUND=1"
) else if exist "env\Scripts\python.exe" (
    set "VENV_PATH=env"
    set "VENV_FOUND=1"
)

if !VENV_FOUND! == 1 (
    echo [%GREEN%m✅ 找到虛擬環境: %VENV_PATH%[0m
) else (
    echo [%YELLOW%m⚠️  未找到虛擬環境，正在創建...[0m
    
    :: 使用 uv 創建虛擬環境
    uv venv .venv
    if errorlevel 1 (
        echo [%RED%m❌ 創建虛擬環境失敗[0m
        pause
        exit /b 1
    )
    
    set "VENV_PATH=.venv"
    echo [%GREEN%m✅ 虛擬環境創建成功: %VENV_PATH%[0m
)

:: 啟動虛擬環境
echo [%BLUE%m[4/5] 啟動虛擬環境...[0m
call "%VENV_PATH%\Scripts\activate.bat"
if errorlevel 1 (
    echo [%RED%m❌ 啟動虛擬環境失敗[0m
    pause
    exit /b 1
)
echo [%GREEN%m✅ 虛擬環境已啟動[0m

:: 安裝依賴
echo [%BLUE%m[5/5] 檢查並安裝依賴...[0m
if exist "pyproject.toml" (
    echo [%BLUE%m正在同步依賴套件...[0m
    uv sync
    if errorlevel 1 (
        echo [%RED%m❌ 依賴安裝失敗[0m
        pause
        exit /b 1
    )
    echo [%GREEN%m✅ 依賴套件已同步[0m
) else (
    echo [%YELLOW%m⚠️  未找到 pyproject.toml，跳過依賴安裝[0m
)

:: 啟動機器人
echo.
echo [%GREEN%m🚀 正在啟動 Discord ADR Bot...[0m
echo [%YELLOW%m按 Ctrl+C 停止機器人[0m
echo.

:: 檢查主程式是否存在
if not exist "src\main.py" (
    echo [%RED%m❌ 找不到主程式 src\main.py[0m
    pause
    exit /b 1
)

:: 使用 uv run 啟動機器人
uv run python -m src.main run

:: 機器人停止後的清理
echo.
echo [%GREEN%m✅ 機器人已停止運行[0m
echo [%BLUE%m正在停用虛擬環境...[0m
call deactivate >nul 2>&1

echo [%GREEN%m👋 感謝使用 Discord ADR Bot![0m
pause