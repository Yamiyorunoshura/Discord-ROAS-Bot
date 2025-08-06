#!/usr/bin/env python3
"""CI 品質檢查測試腳本

獨立測試腳本，用於驗證品質檢查系統是否正常運作。
"""

import asyncio
import sys
from pathlib import Path

# 添加專案根目錄到 Python 路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

try:
    from core.quality.ci_runner import CIQualityRunner
except ImportError as e:
    print(f"❌ 無法導入品質檢查模組: {e}")
    print("🔧 嘗試直接測試 ruff 和 mypy...")
    
    import subprocess
    
    # 直接測試 ruff
    try:
        result = subprocess.run(
            ["ruff", "check", "--config", "quality/ruff.toml", "src/core/quality"],
            capture_output=True,
            text=True,
            cwd=project_root
        )
        print(f"📊 Ruff 檢查結果: 返回碼 {result.returncode}")
        if result.stdout:
            print(f"輸出: {result.stdout}")
        if result.stderr:
            print(f"錯誤: {result.stderr}")
    except Exception as e:
        print(f"❌ Ruff 測試失敗: {e}")
    
    # 直接測試 mypy
    try:
        result = subprocess.run(
            ["mypy", "--config-file", "quality/mypy.ini", "src/core/quality"],
            capture_output=True,
            text=True,
            cwd=project_root
        )
        print(f"📊 Mypy 檢查結果: 返回碼 {result.returncode}")
        if result.stdout:
            print(f"輸出: {result.stdout}")
        if result.stderr:
            print(f"錯誤: {result.stderr}")
    except Exception as e:
        print(f"❌ Mypy 測試失敗: {e}")
    
    sys.exit(1)


async def test_quality_checks():
    """測試品質檢查功能"""
    print("🧪 開始品質檢查系統測試...")
    
    try:
        # 建立運行器
        runner = CIQualityRunner(project_root)
        
        # 測試一個小範圍的檢查
        success = await runner.run_full_quality_check(
            target_path="src/core/quality",
            strict_mode=False  # 先用寬鬆模式測試
        )
        
        if success:
            print("✅ 品質檢查系統測試通過！")
            return True
        else:
            print("❌ 品質檢查系統測試失敗！")
            return False
            
    except Exception as e:
        print(f"💥 品質檢查系統測試發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_quality_checks())
    sys.exit(0 if success else 1)