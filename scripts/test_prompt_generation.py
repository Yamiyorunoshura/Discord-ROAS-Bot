#!/usr/bin/env python3
"""
測試Prompt生成修復
驗證prompt文件是否正確生成在memory_bank目錄下
"""

import os
import sys
from pathlib import Path

# 添加項目根目錄到Python路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.auto_prompt_generator import AutoPromptGenerator


def test_prompt_generation():
    """測試prompt生成功能"""
    print("🧪 開始測試Prompt生成修復...")

    # 創建生成器實例
    generator = AutoPromptGenerator()

    # 檢查路徑設置
    print(f"📁 項目路徑: {generator.project_path}")
    print(f"📁 記憶庫路徑: {generator.memory_bank_path}")
    print(f"📁 Prompt文件路徑: {generator.prompt_file}")

    # 驗證路徑是否正確
    expected_prompt_path = os.path.join(
        generator.project_path, "memory_bank", "prompt.md"
    )
    if generator.prompt_file == expected_prompt_path:
        print("✅ Prompt文件路徑設置正確")
    else:
        print("❌ Prompt文件路徑設置錯誤")
        print(f"   期望: {expected_prompt_path}")
        print(f"   實際: {generator.prompt_file}")
        return False

    # 檢查記憶庫目錄是否存在
    if os.path.exists(generator.memory_bank_path):
        print("✅ 記憶庫目錄存在")
    else:
        print("❌ 記憶庫目錄不存在")
        return False

    # 檢查PRD文件
    prd_files = generator.detect_prd_files()
    if prd_files:
        print(f"✅ 找到 {len(prd_files)} 個PRD文件: {prd_files}")
    else:
        print("❌ 未找到PRD文件")
        return False

    # 測試生成流程
    print("\n🔄 測試自動生成流程...")
    success = generator.auto_generate_prompt()

    if success:
        print("✅ Prompt生成成功")

        # 檢查文件是否在正確位置
        if os.path.exists(generator.prompt_file):
            print(f"✅ Prompt文件已生成在正確位置: {generator.prompt_file}")

            # 讀取文件內容驗證
            with open(generator.prompt_file, encoding="utf-8") as f:
                content = f.read()
                if "開發提示詞" in content:
                    print("✅ Prompt文件內容正確")
                else:
                    print("❌ Prompt文件內容不正確")
                    return False
        else:
            print("❌ Prompt文件未生成")
            return False
    else:
        print("❌ Prompt生成失敗")
        return False

    print("\n🎉 所有測試通過!Prompt生成修復成功!")
    return True


if __name__ == "__main__":
    success = test_prompt_generation()
    sys.exit(0 if success else 1)
