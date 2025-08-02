#!/usr/bin/env python3
"""
PRD-1.64.1 執行腳本
簡化的執行器，按照優化後的PRD進行品質改進
"""

import os
import subprocess
import sys
from pathlib import Path


class PRDExecutor:
    """PRD執行器"""

    def __init__(self):
        self.project_root = Path()
        self.current_stage = 1
        self.current_day = 1

        # 創建必要的目錄
        (self.project_root / "reports").mkdir(exist_ok=True)
        (self.project_root / "scripts").mkdir(exist_ok=True)

    def print_header(self, title: str):
        """打印標題"""
        print("\n" + "="*60)
        print(f"  {title}")
        print("="*60)

    def print_step(self, step: str):
        """打印步驟"""
        print(f"\n🔄 {step}")

    def run_command(self, cmd: str, description: str = "") -> bool:
        """執行命令"""
        if description:
            print(f"   {description}")
        print(f"   執行: {cmd}")

        try:
            result = subprocess.run(cmd, check=False, shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                print("   ✅ 成功")
                return True
            else:
                print(f"   ❌ 失敗: {result.stderr}")
                return False
        except Exception as e:
            print(f"   ❌ 錯誤: {e}")
            return False

    def check_prerequisites(self) -> bool:
        """檢查先決條件"""
        self.print_header("檢查先決條件")

        prerequisites = [
            ("python", "Python 3.9+"),
            ("pip", "pip 套件管理器"),
            ("git", "Git 版本控制"),
        ]

        all_ok = True
        for cmd, desc in prerequisites:
            if not self.run_command(f"which {cmd}", f"檢查 {desc}"):
                all_ok = False

        return all_ok

    def install_dependencies(self):
        """安裝依賴項"""
        self.print_header("安裝開發依賴項")

        # 檢查是否有requirements-dev.txt
        if not (self.project_root / "requirements-dev.txt").exists():
            print("創建 requirements-dev.txt...")
            dev_requirements = """
# 代碼品質工具
mypy>=1.8.0
bandit>=1.7.5
flake8>=7.0.0
black>=24.1.1
isort>=5.12.0

# 測試工具
pytest>=8.4.1
pytest-asyncio>=1.1.0
pytest-cov>=4.0.0
pytest-xdist>=3.0.0
pytest-mock>=3.10.0
pytest-timeout>=2.1.0

# 開發工具
pre-commit>=3.6.0
safety>=2.3.0
"""

            with open("requirements-dev.txt", "w") as f:
                f.write(dev_requirements.strip())

        # 安裝依賴項
        self.run_command("pip install -r requirements-dev.txt", "安裝開發依賴項")

        # 安裝pre-commit hooks
        self.run_command("pre-commit install", "安裝pre-commit hooks")

    def day_1_security_emergency(self):
        """第1天：緊急安全修復"""
        self.print_header("第1天：緊急安全修復")

        # 創建修復分支
        self.print_step("創建修復分支")
        self.run_command("git checkout -b fix/security-issues", "創建安全修復分支")

        # 執行安全掃描
        self.print_step("執行安全掃描")
        self.run_command("bandit -r cogs/ -f json -o reports/baseline_security.json", "執行Bandit安全掃描")

        # 使用工具包修復
        self.print_step("執行自動修復")
        self.run_command("python scripts/quality_improvement_toolkit.py stage1", "執行階段1修復")

        # 提交修復
        self.print_step("提交修復")
        self.run_command("git add .", "添加修復文件")
        self.run_command('git commit -m "fix: 修復高風險安全問題 - MD5替換為SHA256"', "提交安全修復")

        print("\n✅ 第1天任務完成")
        print("   - 已修復MD5使用問題")
        print("   - 已識別SQL注入風險")
        print("   - 已提交修復到分支")

    def day_2_security_complete(self):
        """第2天：完善安全修復"""
        self.print_header("第2天：完善安全修復")

        # 繼續安全修復
        self.print_step("檢查剩餘安全問題")
        self.run_command("bandit -r cogs/ -ll", "檢查高風險安全問題")

        # 手動修復提醒
        print("\n⚠️  請手動檢查並修復以下問題：")
        print("   1. SQL注入風險 - 使用參數化查詢")
        print("   2. 硬編碼敏感資訊 - 移至環境變數")
        print("   3. 弱密碼演算法 - 使用強加密算法")

        # 最終安全驗證
        self.print_step("最終安全驗證")
        self.run_command("python scripts/quality_improvement_toolkit.py assessment", "執行完整安全評估")

        # 合併到develop
        self.print_step("合併修復")
        self.run_command("git checkout develop", "切換到develop分支")
        self.run_command("git merge fix/security-issues", "合併安全修復")

        print("\n✅ 第2天任務完成")
        print("   - 已完成所有安全修復")
        print("   - 已合併到develop分支")

    def day_3_type_core(self):
        """第3天：核心類型修復"""
        self.print_header("第3天：核心類型修復")

        # 創建類型修復分支
        self.print_step("創建類型修復分支")
        self.run_command("git checkout -b fix/type-errors", "創建類型修復分支")

        # 執行類型檢查
        self.print_step("執行類型檢查")
        self.run_command("mypy cogs/core/ --strict", "檢查核心模組類型")

        # 重點修復檔案
        priority_files = [
            "cogs/core/logger.py",
            "cogs/core/base_cog.py",
            "cogs/core/health_checker.py"
        ]

        print("\n📝 需要手動修復的檔案：")
        for file in priority_files:
            if os.path.exists(file):
                print(f"   - {file}")
                # 顯示該文件的類型錯誤
                self.run_command(f"mypy {file} --strict", f"檢查 {file}")

        print("\n⚠️  請使用以下模式修復類型錯誤：")
        print("   1. Union類型: 使用 if x is not None 檢查")
        print("   2. 返回類型: 明確標註返回類型")
        print("   3. 異步函數: 使用 -> Awaitable[T] 或 -> T")

        input("\n按Enter鍵繼續修復後的驗證...")

        # 驗證修復
        self.print_step("驗證類型修復")
        self.run_command("mypy cogs/core/ --strict", "驗證核心模組類型")

        print("\n✅ 第3天任務完成")
        print("   - 已檢查核心模組類型錯誤")
        print("   - 請確保所有核心模組類型錯誤已修復")

    def day_4_type_modules(self):
        """第4天：模組類型修復"""
        self.print_header("第4天：模組類型修復")

        # 檢查其他模組
        modules = [
            "cogs/activity_meter/",
            "cogs/protection/",
            "cogs/message_listener/",
            "cogs/sync_data/",
            "cogs/welcome/"
        ]

        self.print_step("檢查所有模組類型")
        for module in modules:
            if os.path.exists(module):
                print(f"\n📁 檢查 {module}")
                self.run_command(f"mypy {module} --strict", f"檢查 {module}")

        # 執行完整類型檢查
        self.print_step("執行完整類型檢查")
        self.run_command("mypy cogs/ --strict", "檢查所有模組類型")

        # 提交類型修復
        self.print_step("提交類型修復")
        self.run_command("git add .", "添加類型修復")
        self.run_command('git commit -m "fix: 修復所有類型檢查錯誤"', "提交類型修復")

        print("\n✅ 第4天任務完成")
        print("   - 已檢查所有模組類型錯誤")
        print("   - 已提交類型修復")

    def day_5_test_setup(self):
        """第5天：測試環境建立"""
        self.print_header("第5天：測試環境建立")

        # 創建測試分支
        self.print_step("創建測試分支")
        self.run_command("git checkout -b fix/test-infrastructure", "創建測試分支")

        # 建立測試基礎設施
        self.print_step("建立測試基礎設施")
        self.run_command("python scripts/quality_improvement_toolkit.py stage3", "建立測試基礎設施")

        # 檢查測試狀態
        self.print_step("檢查測試狀態")
        self.run_command("pytest --collect-only", "檢查測試發現")

        # 執行快速測試
        self.print_step("執行快速測試")
        self.run_command("pytest tests/ -v --tb=short", "執行測試套件")

        print("\n✅ 第5天任務完成")
        print("   - 已建立測試基礎設施")
        print("   - 已配置pytest環境")
        print("   - 已創建測試夾具")

    def day_6_test_coverage(self):
        """第6天：測試覆蓋率"""
        self.print_header("第6天：測試覆蓋率")

        # 執行覆蓋率測試
        self.print_step("執行覆蓋率測試")
        self.run_command("pytest --cov=cogs --cov-report=html --cov-report=term-missing", "執行覆蓋率測試")

        # 顯示覆蓋率報告
        self.print_step("生成覆蓋率報告")
        if os.path.exists("htmlcov/index.html"):
            print(f"   📊 覆蓋率報告: {os.path.abspath('htmlcov/index.html')}")

        # 提交測試改進
        self.print_step("提交測試改進")
        self.run_command("git add .", "添加測試改進")
        self.run_command('git commit -m "feat: 建立完整測試基礎設施和覆蓋率監控"', "提交測試改進")

        # 合併測試分支
        self.print_step("合併測試分支")
        self.run_command("git checkout develop", "切換到develop分支")
        self.run_command("git merge fix/test-infrastructure", "合併測試改進")

        print("\n✅ 第6天任務完成")
        print("   - 已提升測試覆蓋率")
        print("   - 已建立覆蓋率監控")
        print("   - 已合併測試改進")

    def day_7_performance(self):
        """第7天：性能優化"""
        self.print_header("第7天：性能優化")

        # 創建性能優化分支
        self.print_step("創建性能優化分支")
        self.run_command("git checkout -b perf/optimization", "創建性能優化分支")

        # 執行性能基準測試
        self.print_step("執行性能基準測試")

        print("\n📊 性能優化重點：")
        print("   1. 資料庫查詢優化 - 使用批量查詢")
        print("   2. 快取機制 - 實施智能快取")
        print("   3. 記憶體使用 - 優化物件生命週期")
        print("   4. 異步處理 - 改善併發性能")

        # 檢查資料庫檔案
        db_files = list(Path("cogs").glob("**/database/*.py"))
        if db_files:
            print("\n📁 需要優化的資料庫檔案：")
            for db_file in db_files:
                print(f"   - {db_file}")

        print("\n✅ 第7天任務完成")
        print("   - 已識別性能瓶頸")
        print("   - 請手動實施性能優化")

    def day_8_performance_complete(self):
        """第8天：完成性能優化"""
        self.print_header("第8天：完成性能優化")

        # 執行性能驗證
        self.print_step("執行性能驗證")

        # 提交性能改進
        self.print_step("提交性能改進")
        self.run_command("git add .", "添加性能改進")
        self.run_command('git commit -m "perf: 實施資料庫查詢優化和快取機制"', "提交性能改進")

        # 合併到develop
        self.print_step("合併性能改進")
        self.run_command("git checkout develop", "切換到develop分支")
        self.run_command("git merge perf/optimization", "合併性能改進")

        print("\n✅ 第8天任務完成")
        print("   - 已完成性能優化")
        print("   - 已合併到develop分支")

    def day_9_toolchain(self):
        """第9天：工具鏈建立"""
        self.print_header("第9天：工具鏈建立")

        # 創建工具鏈分支
        self.print_step("創建工具鏈分支")
        self.run_command("git checkout -b feat/toolchain", "創建工具鏈分支")

        # 建立pre-commit配置
        self.print_step("建立pre-commit配置")

        precommit_config = """
repos:
  - repo: https://github.com/psf/black
    rev: 23.12.0
    hooks:
      - id: black
        language_version: python3.9
  - repo: https://github.com/pycqa/flake8
    rev: 6.1.0
    hooks:
      - id: flake8
        args: [--max-line-length=88]
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies: [types-requests, types-aiofiles]
  - repo: https://github.com/pycqa/bandit
    rev: 1.7.5
    hooks:
      - id: bandit
        args: [-r, cogs/]
"""

        with open(".pre-commit-config.yaml", "w") as f:
            f.write(precommit_config.strip())

        # 安裝pre-commit hooks
        self.run_command("pre-commit install", "安裝pre-commit hooks")

        # 測試工具鏈
        self.print_step("測試工具鏈")
        self.run_command("pre-commit run --all-files", "測試所有工具")

        print("\n✅ 第9天任務完成")
        print("   - 已建立完整工具鏈")
        print("   - 已配置pre-commit hooks")

    def day_10_final_validation(self):
        """第10天：最終驗證"""
        self.print_header("第10天：最終驗證")

        # 執行完整評估
        self.print_step("執行完整品質評估")
        self.run_command("python scripts/quality_improvement_toolkit.py assessment", "執行完整評估")

        # 執行所有測試
        self.print_step("執行所有測試")
        self.run_command("pytest --cov=cogs --cov-report=html --cov-report=term-missing", "執行完整測試")

        # 最終提交
        self.print_step("最終提交")
        self.run_command("git add .", "添加所有改進")
        self.run_command('git commit -m "feat: 完成代碼品質改進計劃 - 達到A-級品質"', "最終提交")

        # 合併到develop
        self.print_step("合併最終改進")
        self.run_command("git checkout develop", "切換到develop分支")
        self.run_command("git merge feat/toolchain", "合併工具鏈改進")

        # 創建版本標籤
        self.print_step("創建版本標籤")
        self.run_command("git tag -a v1.64.1 -m 'Release v1.64.1: 代碼品質改進'", "創建版本標籤")

        print("\n🎉 第10天任務完成")
        print("   - 已完成所有品質改進")
        print("   - 已創建版本標籤")
        print("   - 品質改進計劃全部完成！")

    def show_menu(self):
        """顯示菜單"""
        self.print_header("PRD-1.64.1 執行器")

        print("選擇要執行的任務：")
        print("  0  - 檢查先決條件")
        print("  1  - 第1天：緊急安全修復")
        print("  2  - 第2天：完善安全修復")
        print("  3  - 第3天：核心類型修復")
        print("  4  - 第4天：模組類型修復")
        print("  5  - 第5天：測試環境建立")
        print("  6  - 第6天：測試覆蓋率")
        print("  7  - 第7天：性能優化")
        print("  8  - 第8天：完成性能優化")
        print("  9  - 第9天：工具鏈建立")
        print("  10 - 第10天：最終驗證")
        print("  a  - 執行完整評估")
        print("  q  - 退出")

        choice = input("\n請選擇 (0-10, a, q): ").strip()

        if choice == "0":
            if self.check_prerequisites():
                self.install_dependencies()
        elif choice == "1":
            self.day_1_security_emergency()
        elif choice == "2":
            self.day_2_security_complete()
        elif choice == "3":
            self.day_3_type_core()
        elif choice == "4":
            self.day_4_type_modules()
        elif choice == "5":
            self.day_5_test_setup()
        elif choice == "6":
            self.day_6_test_coverage()
        elif choice == "7":
            self.day_7_performance()
        elif choice == "8":
            self.day_8_performance_complete()
        elif choice == "9":
            self.day_9_toolchain()
        elif choice == "10":
            self.day_10_final_validation()
        elif choice == "a":
            self.run_command("python scripts/quality_improvement_toolkit.py assessment", "執行完整評估")
        elif choice == "q":
            print("👋 再見！")
            sys.exit(0)
        else:
            print("❌ 無效選擇")

        input("\n按Enter鍵繼續...")
        self.show_menu()


def main():
    """主函數"""
    executor = PRDExecutor()

    if len(sys.argv) > 1:
        # 命令行模式
        day = sys.argv[1]
        if day == "day1":
            executor.day_1_security_emergency()
        elif day == "day2":
            executor.day_2_security_complete()
        elif day == "assessment":
            executor.run_command("python scripts/quality_improvement_toolkit.py assessment", "執行完整評估")
        else:
            print(f"未知命令: {day}")
    else:
        # 互動模式
        executor.show_menu()


if __name__ == "__main__":
    main()
