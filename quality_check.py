#!/usr/bin/env python3
"""
Discord ADR Bot v1.6 代碼品質檢查工具
=====================================

階段5任務5.2：CI/CD流程建立的一部分
提供本地代碼品質檢查功能

作者：Assistant
版本：1.6.0
更新：2025-01-25
"""

import subprocess
import sys
import os
from pathlib import Path
import json
import time

def run_command(cmd, description):
    """運行命令並返回結果"""
    print(f"\n{'='*50}")
    print(f"🔍 {description}")
    print(f"{'='*50}")
    
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode == 0:
            print(f"✅ {description} - 通過")
            if result.stdout:
                print(result.stdout)
            return True
        else:
            print(f"❌ {description} - 失敗")
            if result.stderr:
                print(f"錯誤: {result.stderr}")
            if result.stdout:
                print(f"輸出: {result.stdout}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"⏰ {description} - 超時")
        return False
    except Exception as e:
        print(f"💥 {description} - 異常: {e}")
        return False

def check_dependencies():
    """檢查依賴項"""
    print("📦 檢查依賴項...")
    
    # 檢查Python版本
    python_version = sys.version_info
    if python_version < (3, 8):
        print(f"❌ Python版本過低: {python_version.major}.{python_version.minor}")
        return False
    else:
        print(f"✅ Python版本: {python_version.major}.{python_version.minor}.{python_version.micro}")
    
    # 檢查必要的包
    required_packages = [
        ('pytest', 'pytest'),
        ('pytest-asyncio', 'pytest_asyncio'),
        ('aiosqlite', 'aiosqlite'),
        ('discord.py', 'discord'),
        ('psutil', 'psutil'),
        ('pillow', 'PIL'),
        ('requests', 'requests')
    ]
    
    missing_packages = []
    for package_name, import_name in required_packages:
        try:
            __import__(import_name)
            print(f"✅ {package_name}")
        except ImportError:
            print(f"❌ {package_name} - 未安裝")
            missing_packages.append(package_name)
    
    if missing_packages:
        print(f"\n缺少的包: {', '.join(missing_packages)}")
        print("請運行: pip install -r requirement.txt")
        return False
    
    return True

def run_linting():
    """運行代碼檢查"""
    results = []
    
    # Flake8 基本語法檢查
    results.append(run_command(
        "python -m flake8 --select=E9,F63,F7,F82 --show-source --statistics cogs/",
        "Flake8 語法檢查 - cogs/"
    ))
    
    results.append(run_command(
        "python -m flake8 --select=E9,F63,F7,F82 --show-source --statistics main.py",
        "Flake8 語法檢查 - main.py"
    ))
    
    # 可選：MyPy 類型檢查（如果可用）
    try:
        import mypy
        results.append(run_command(
            "python -m mypy cogs/core/performance_dashboard.py --ignore-missing-imports",
            "MyPy 類型檢查 - 性能監控儀表板"
        ))
    except ImportError:
        print("ℹ️ MyPy 未安裝，跳過類型檢查")
    
    return all(results)

def run_security_scan():
    """運行安全掃描"""
    results = []
    
    # 嘗試使用bandit進行安全掃描
    try:
        import bandit
        results.append(run_command(
            "python -m bandit -r cogs/ -f txt",
            "Bandit 安全掃描"
        ))
    except ImportError:
        print("ℹ️ Bandit 未安裝，跳過安全掃描")
        print("   安裝: pip install bandit")
    
    # 嘗試使用safety檢查依賴安全性
    try:
        import safety
        results.append(run_command(
            "python -m safety check",
            "Safety 依賴安全檢查"
        ))
    except ImportError:
        print("ℹ️ Safety 未安裝，跳過依賴安全檢查")
        print("   安裝: pip install safety")
    
    return len(results) == 0 or any(results)

def run_tests():
    """運行測試套件"""
    results = []
    
    # 運行優化的測試
    results.append(run_command(
        "python run_tests_optimized.py",
        "優化測試套件"
    ))
    
    # 運行性能監控儀表板測試
    results.append(run_command(
        "python -m pytest tests/unit/test_performance_dashboard.py -v",
        "性能監控儀表板測試"
    ))
    
    # 運行覆蓋率測試
    results.append(run_command(
        "python -m pytest tests/unit/test_basic.py --cov=cogs --cov-report=term --cov-fail-under=50",
        "測試覆蓋率檢查"
    ))
    
    return all(results)

def generate_report():
    """生成品質報告"""
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "project": "Discord ADR Bot v1.6",
        "checks": {
            "dependencies": False,
            "linting": False,
            "security": False,
            "tests": False
        }
    }
    
    return report

def main():
    """主函數"""
    print("🚀 Discord ADR Bot v1.6 代碼品質檢查")
    print("=" * 60)
    
    start_time = time.time()
    report = generate_report()
    
    # 檢查依賴項
    report["checks"]["dependencies"] = check_dependencies()
    
    # 運行代碼檢查
    if report["checks"]["dependencies"]:
        report["checks"]["linting"] = run_linting()
        report["checks"]["security"] = run_security_scan()
        report["checks"]["tests"] = run_tests()
    
    # 生成摘要
    print("\n" + "=" * 60)
    print("📊 品質檢查摘要")
    print("=" * 60)
    
    total_checks = len(report["checks"])
    passed_checks = sum(1 for check in report["checks"].values() if check)
    
    for check_name, result in report["checks"].items():
        status = "✅ 通過" if result else "❌ 失敗"
        print(f"{check_name.upper()}: {status}")
    
    print(f"\n總體結果: {passed_checks}/{total_checks} 檢查通過")
    print(f"執行時間: {time.time() - start_time:.2f} 秒")
    
    # 保存報告
    try:
        with open("quality_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print("📄 品質報告已保存到 quality_report.json")
    except Exception as e:
        print(f"⚠️ 無法保存報告: {e}")
    
    # 返回退出碼
    if passed_checks == total_checks:
        print("\n🎉 所有檢查都通過！")
        sys.exit(0)
    else:
        print(f"\n⚠️ {total_checks - passed_checks} 個檢查失敗")
        sys.exit(1)

if __name__ == "__main__":
    main() 