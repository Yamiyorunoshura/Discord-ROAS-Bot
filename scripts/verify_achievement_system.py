#!/usr/bin/env python3
"""
成就系統註冊驗證腳本
用於快速檢查成就系統是否正確註冊到機器人中
"""

import sys
from pathlib import Path

# 添加項目根目錄到 Python 路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def verify_achievement_system():
    """驗證成就系統註冊狀態"""
    print("🔍 驗證成就系統註冊狀態...")

    try:
        # 檢查模組配置
        from unittest.mock import Mock

        from src.core.bot import StartupManager
        from src.core.config import Settings

        # 創建模擬對象來檢查配置
        mock_bot = Mock()
        settings = Settings()
        startup_manager = StartupManager(mock_bot, settings)

        if "achievement" in startup_manager.module_config:
            config = startup_manager.module_config["achievement"]
            print("✅ 成就系統已註冊到機器人模組配置中")
            print(f"   優先級: {config['priority']}")
            print(f"   關鍵性: {'是' if config['critical'] else '否'}")
            print(f"   描述: {config['description']}")
        else:
            print("❌ 成就系統未在機器人模組配置中")
            return False

        # 檢查模組文件
        achievement_init = project_root / "src" / "cogs" / "achievement" / "__init__.py"
        if achievement_init.exists():
            print("✅ 成就系統 __init__.py 文件存在")
        else:
            print("❌ 成就系統 __init__.py 文件不存在")
            return False

        # 檢查配置文件
        config_file = project_root / "config" / "achievement.yaml"
        if config_file.exists():
            print("✅ 成就系統配置文件存在")
        else:
            print("⚠️  成就系統配置文件不存在(可選)")

        # 檢查主要模組導入
        try:
            from src.cogs.achievement import setup  # noqa: F401
            from src.cogs.achievement.main.main import AchievementCog  # noqa: F401

            print("✅ 成就系統模組可正常導入")
        except ImportError as e:
            print(f"❌ 成就系統模組導入失敗: {e}")
            return False

        print("\n🎉 成就系統已正確註冊並可正常使用!")
        return True

    except Exception as e:
        print(f"❌ 驗證過程中發生錯誤: {e}")
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("Discord ROAS Bot - 成就系統驗證")
    print("=" * 50)

    success = verify_achievement_system()

    print("\n" + "=" * 50)
    if success:
        print("✅ 驗證完成:成就系統已正確註冊")
        print("💡 您現在可以啟動機器人並使用 /成就 指令")
    else:
        print("❌ 驗證失敗:成就系統註冊存在問題")
    print("=" * 50)
