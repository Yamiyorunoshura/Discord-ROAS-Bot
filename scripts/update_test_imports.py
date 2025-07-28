#!/usr/bin/env python3
"""
Discord ROAS Bot 測試Import路徑更新腳本
自動更新所有測試檔案中的import路徑,從舊架構遷移到新架構

遷移規則:
- cogs.core.* → src.core.*
- cogs.activity_meter.* → src.cogs.activity_meter.*
- cogs.message_listener.* → src.cogs.message_listener.*
- cogs.protection.* → src.cogs.protection.*
- cogs.welcome.* → src.cogs.welcome.*
- cogs.sync_data.* → src.cogs.sync_data.*
"""

import re
from pathlib import Path

# 定義轉換規則
IMPORT_MAPPINGS = {
    # 核心模組映射
    r"from cogs\.core\.dependency_container import": "from src.core.container import",
    r"from cogs\.core\.database_pool import": "from src.core.database import",
    r"from cogs\.core\.cache_manager import": "from src.core.container import",
    r"from cogs\.core\.event_bus import": "from src.core.bot import",
    r"from cogs\.core\.error_handler import": "from src.core.bot import",
    r"from cogs\.core\.health_checker import": "from src.core.container import",
    r"from cogs\.core\.performance_dashboard import": "from src.core.monitor import",
    r"from cogs\.core\.logger import": "from src.core.logger import",
    r"from cogs\.core\.permission_system import": "from src.core.bot import",
    r"from cogs\.core\.startup import": "from src.core.bot import",
    r"from cogs\.core\.venv_manager import": "from src.core.compat import",
    r"from cogs\.core\.api_standard import": "from src.core.compat import",
    r"from cogs\.core\.base_cog import": "from src.core.compat import",
    # 功能模組映射
    r"from cogs\.activity_meter": "from src.cogs.activity_meter",
    r"from cogs\.message_listener": "from src.cogs.message_listener",
    r"from cogs\.protection": "from src.cogs.protection",
    r"from cogs\.welcome": "from src.cogs.welcome",
    r"from cogs\.sync_data": "from src.cogs.sync_data",
    r"import cogs\.core\.dependency_container": "import src.core.container",
    r"import cogs\.core\.database_pool": "import src.core.database",
    r"import cogs\.core\.cache_manager": "import src.core.container",
    r"import cogs\.core\.event_bus": "import src.core.bot",
    r"import cogs\.core\.logger": "import src.core.logger",
    r"import cogs\.activity_meter": "import src.cogs.activity_meter",
    r"import cogs\.message_listener": "import src.cogs.message_listener",
    r"import cogs\.protection": "import src.cogs.protection",
    r"import cogs\.welcome": "import src.cogs.welcome",
    r"import cogs\.sync_data": "import src.cogs.sync_data",
}


def update_file_imports(file_path: Path) -> bool:
    """更新單個檔案的import路徑"""
    try:
        with file_path.open(encoding="utf-8") as f:
            content = f.read()

        changes_made = False

        # 應用所有轉換規則
        for old_pattern, new_replacement in IMPORT_MAPPINGS.items():
            new_content = re.sub(old_pattern, new_replacement, content)
            if new_content != content:
                changes_made = True
                content = new_content
                print(f"  - 更新: {old_pattern} → {new_replacement}")

        # 如果有變更,寫回檔案
        if changes_made:
            with file_path.open("w", encoding="utf-8") as f:
                f.write(content)
            return True

        return False

    except Exception as e:
        print(f"更新檔案失敗 {file_path}: {e}")
        return False


def main():
    """主要執行函數"""
    print("開始更新Discord ROAS Bot測試檔案import路徑...")

    # 取得專案根目錄
    project_root = Path(__file__).parent.parent
    tests_dir = project_root / "tests"

    if not tests_dir.exists():
        print("找不到tests目錄")
        return

    # 尋找所有Python測試檔案
    test_files = list(tests_dir.rglob("*.py"))
    print(f"找到 {len(test_files)} 個測試檔案")

    updated_files = 0
    failed_files = 0

    for test_file in test_files:
        print(f"\n處理: {test_file.relative_to(project_root)}")

        if update_file_imports(test_file):
            updated_files += 1
            print(f"已更新: {test_file.name}")
        else:
            print(f"無需更新: {test_file.name}")

    # 輸出總結
    print("\n更新總結:")
    print(f"  總檔案數: {len(test_files)}")
    print(f"  已更新: {updated_files}")
    print(f"  失敗: {failed_files}")
    print(f"  無需更新: {len(test_files) - updated_files - failed_files}")

    if updated_files > 0:
        print("\n測試檔案import路徑更新完成!")
        print("建議執行測試確認更新是否成功:")
        print("   pytest tests/ -v")
    else:
        print("\n所有測試檔案的import路徑都已是最新版本")


if __name__ == "__main__":
    main()
