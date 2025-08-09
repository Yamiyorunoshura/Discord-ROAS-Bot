@echo off
REM Discord ROAS Bot 測試運行腳本 (Windows版本)

setlocal enabledelayedexpansion

echo 🧪 Discord ROAS Bot 測試套件
echo =================================

REM 檢查依賴
:check_dependencies
echo 檢查測試依賴...

where pytest >nul 2>&1
if errorlevel 1 (
    echo ❌ pytest 未安裝
    exit /b 1
)

where uv >nul 2>&1
if errorlevel 1 (
    echo ⚠️  建議使用 uv 作為包管理器
)

echo ✅ 依賴檢查完成
goto :eof

REM 運行快速測試
:run_fast_tests
echo 🏃‍♂️ 運行快速測試 (單元測試 + Mock)

uv run pytest -m "unit and mock and not slow" --maxfail=3 --tb=short --disable-warnings --quiet tests\unit\

if errorlevel 1 (
    echo ❌ 快速測試失敗
    exit /b 1
)

echo ✅ 快速測試完成
goto :eof

REM 運行面板測試
:run_panel_tests
echo 🎨 運行面板互動測試

uv run pytest -c pytest_panel.toml --maxfail=5 --tb=short tests\unit\cogs\*\test_*panel*.py

if errorlevel 1 (
    echo ❌ 面板測試失敗
    exit /b 1
)

echo ✅ 面板測試完成
goto :eof

REM 運行指令測試
:run_command_tests
echo ⚡ 運行指令測試

uv run pytest -m "command and mock" --maxfail=5 --tb=short tests\unit\cogs\*\test_*command*.py

if errorlevel 1 (
    echo ❌ 指令測試失敗
    exit /b 1
)

echo ✅ 指令測試完成
goto :eof

REM 運行完整測試套件
:run_full_tests
echo 🔄 運行完整測試套件

uv run pytest --cov=src --cov-report=html --cov-report=term-missing --cov-report=xml --maxfail=10 tests\

if errorlevel 1 (
    echo ❌ 完整測試失敗
    exit /b 1
)

echo ✅ 完整測試完成
echo 📊 查看覆蓋率報告: htmlcov\index.html
goto :eof

REM 運行效能測試
:run_performance_tests
echo ⚡ 運行效能測試

uv run pytest -m "performance" --benchmark-only --benchmark-sort=mean --benchmark-warmup=off tests\

if errorlevel 1 (
    echo ❌ 效能測試失敗
    exit /b 1
)

echo ✅ 效能測試完成
goto :eof

REM 運行特定模組測試
:run_module_tests
if "%2"=="" (
    echo ❌ 請指定模組名稱
    echo 可用模組: activity_meter, achievement, welcome, protection, government, currency
    exit /b 1
)

echo 🎯 運行 %2 模組測試

uv run pytest -m "%2" --tb=short tests\unit\cogs\%2\

echo ✅ %2 模組測試完成
goto :eof

REM CI/CD 測試
:run_ci_tests
echo 🏗️  運行 CI/CD 測試 (嚴格模式)

set PYTHONWARNINGS=error
set TESTING=true
set ENV=test

uv run pytest --strict-markers --strict-config --cov=src --cov-fail-under=70 --cov-report=xml --junit-xml=pytest-results.xml --maxfail=1 --tb=short -q tests\

if errorlevel 1 (
    echo ❌ CI/CD 測試失敗
    exit /b 1
)

echo ✅ CI/CD 測試完成
goto :eof

REM 生成測試報告
:generate_report
echo 📊 生成測試報告

if not exist reports mkdir reports

uv run pytest --cov=src --cov-report=html:reports\coverage --cov-report=xml:reports\coverage.xml --cov-report=json:reports\coverage.json --junit-xml=reports\pytest.xml --html=reports\pytest.html --self-contained-html tests\

if errorlevel 1 (
    echo ❌ 報告生成失敗
    exit /b 1
)

echo ✅ 測試報告生成完成
echo 📁 報告位置: reports\
goto :eof

REM 清理測試文件
:cleanup
echo 🧹 清理測試文件

REM 清理測試資料庫
for /r . %%f in (test_*.db) do del "%%f" 2>nul
for /r . %%f in (*.db-journal) do del "%%f" 2>nul

REM 清理Python緩存
for /d /r . %%d in (__pycache__) do rd /s /q "%%d" 2>nul
for /r . %%f in (*.pyc) do del "%%f" 2>nul

REM 清理pytest緩存
if exist .pytest_cache rd /s /q .pytest_cache 2>nul
if exist .coverage del .coverage* 2>nul

echo ✅ 清理完成
goto :eof

REM 顯示幫助
:show_help
echo Discord ROAS Bot 測試運行器
echo.
echo 用法: %0 [選項]
echo.
echo 選項:
echo   fast          運行快速測試 (單元測試 + Mock)
echo   panel         運行面板互動測試
echo   command       運行指令測試
echo   full          運行完整測試套件 (包含覆蓋率)
echo   performance   運行效能測試
echo   module ^<名稱^> 運行特定模組測試
echo   ci            運行 CI/CD 測試 (嚴格模式)
echo   report        生成詳細測試報告
echo   cleanup       清理測試文件
echo   help          顯示此幫助
echo.
echo 範例:
echo   %0 fast                    # 快速測試
echo   %0 module activity_meter   # 活躍度模組測試
echo   %0 panel                   # 面板測試
echo   %0 full                    # 完整測試
goto :eof

REM 主邏輯
if "%1"=="fast" (
    call :check_dependencies
    call :run_fast_tests
) else if "%1"=="panel" (
    call :check_dependencies
    call :run_panel_tests
) else if "%1"=="command" (
    call :check_dependencies
    call :run_command_tests
) else if "%1"=="full" (
    call :check_dependencies
    call :run_full_tests
) else if "%1"=="performance" (
    call :check_dependencies
    call :run_performance_tests
) else if "%1"=="module" (
    call :check_dependencies
    call :run_module_tests %1 %2
) else if "%1"=="ci" (
    call :check_dependencies
    call :run_ci_tests
) else if "%1"=="report" (
    call :check_dependencies
    call :generate_report
) else if "%1"=="cleanup" (
    call :cleanup
) else if "%1"=="help" (
    call :show_help
) else if "%1"=="" (
    call :show_help
) else (
    echo ❌ 未知選項: %1
    call :show_help
    exit /b 1
)

endlocal