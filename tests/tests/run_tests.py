"""
測試運行腳本 - 統一運行新架構測試

此腳本提供完整的測試運行功能,包括:
- 單元測試執行
- 整合測試執行
- 覆蓋率報告生成
- 測試結果分析

符合 TASK-005: 測試環境建立與修復的要求
"""

import argparse
import datetime
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

# 設置標準輸出編碼為UTF-8
if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


class TestRunner:
    """測試運行器"""

    def __init__(self):
        self.src_path = Path(__file__).parent.parent
        self.project_root = self.src_path.parent
        self.coverage_file = self.project_root / ".coverage"

        # 確保Python路徑正確
        if str(self.src_path) not in sys.path:
            sys.path.insert(0, str(self.src_path))

    def run_unit_tests(
        self, verbose: bool = True, coverage: bool = True
    ) -> dict[str, Any]:
        """運行單元測試

        Args:
            verbose: 是否詳細輸出
            coverage: 是否生成覆蓋率報告

        Returns:
            測試結果
        """
        print("運行單元測試...")

        cmd = ["python", "-m", "pytest"]

        # 添加測試目錄
        cmd.extend([str(self.src_path / "tests" / "unit")])

        # 添加標記過濾
        cmd.extend(["-m", "unit"])

        # 添加詳細輸出
        if verbose:
            cmd.append("-v")

        # 添加覆蓋率
        if coverage:
            cmd.extend(
                [
                    "--cov=src",
                    "--cov-report=html",
                    "--cov-report=term",
                    "--cov-report=json",
                    f"--cov-config={self.project_root / 'pyproject.toml'}",
                ]
            )

        # 設置環境變數
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.src_path)
        env["TESTING"] = "true"

        try:
            result = subprocess.run(
                cmd,
                check=False,
                cwd=self.project_root,
                env=env,
                capture_output=True,
                text=True,
            )

            return {
                "type": "unit_tests",
                "success": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "command": " ".join(cmd),
            }

        except Exception as e:
            return {
                "type": "unit_tests",
                "success": False,
                "error": str(e),
                "command": " ".join(cmd),
            }

    def run_integration_tests(self, verbose: bool = True) -> dict[str, Any]:
        """運行整合測試

        Args:
            verbose: 是否詳細輸出

        Returns:
            測試結果
        """
        print("運行整合測試...")

        cmd = ["python", "-m", "pytest"]

        # 添加測試目錄
        cmd.extend([str(self.src_path / "tests")])

        # 添加標記過濾
        cmd.extend(["-m", "integration"])

        # 添加詳細輸出
        if verbose:
            cmd.append("-v")

        # 設置環境變數
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.src_path)
        env["TESTING"] = "true"

        try:
            result = subprocess.run(
                cmd,
                check=False,
                cwd=self.project_root,
                env=env,
                capture_output=True,
                text=True,
            )

            return {
                "type": "integration_tests",
                "success": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "command": " ".join(cmd),
            }

        except Exception as e:
            return {
                "type": "integration_tests",
                "success": False,
                "error": str(e),
                "command": " ".join(cmd),
            }

    def run_performance_tests(self, verbose: bool = True) -> dict[str, Any]:
        """運行性能測試

        Args:
            verbose: 是否詳細輸出

        Returns:
            測試結果
        """
        print("運行性能測試...")

        cmd = ["python", "-m", "pytest"]

        # 添加測試目錄
        cmd.extend([str(self.src_path / "tests")])

        # 添加標記過濾
        cmd.extend(["-m", "performance"])

        # 添加詳細輸出
        if verbose:
            cmd.append("-v")

        # 設置環境變數
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.src_path)
        env["TESTING"] = "true"

        try:
            result = subprocess.run(
                cmd,
                check=False,
                cwd=self.project_root,
                env=env,
                capture_output=True,
                text=True,
            )

            return {
                "type": "performance_tests",
                "success": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "command": " ".join(cmd),
            }

        except Exception as e:
            return {
                "type": "performance_tests",
                "success": False,
                "error": str(e),
                "command": " ".join(cmd),
            }

    def run_all_tests(
        self, include_slow: bool = False, include_integration: bool = True
    ) -> dict[str, Any]:
        """運行所有測試

        Args:
            include_slow: 是否包含慢速測試
            include_integration: 是否包含整合測試

        Returns:
            完整測試結果
        """
        print("運行完整測試套件...")

        results = {"timestamp": datetime.datetime.now().isoformat(), "tests": []}

        # 運行單元測試
        unit_result = self.run_unit_tests(verbose=True, coverage=True)
        results["tests"].append(unit_result)

        # 運行整合測試(如果啟用)
        if include_integration:
            integration_result = self.run_integration_tests(verbose=True)
            results["tests"].append(integration_result)

        # 運行性能測試
        performance_result = self.run_performance_tests(verbose=True)
        results["tests"].append(performance_result)

        # 計算整體結果
        results["overall_success"] = all(test["success"] for test in results["tests"])
        results["total_tests"] = len(results["tests"])
        results["passed_tests"] = sum(1 for test in results["tests"] if test["success"])
        results["failed_tests"] = results["total_tests"] - results["passed_tests"]

        return results

    def generate_coverage_report(self) -> dict[str, Any]:
        """生成覆蓋率報告

        Returns:
            覆蓋率報告數據
        """
        print("生成覆蓋率報告...")

        # 檢查覆蓋率數據文件是否存在
        coverage_json_path = self.project_root / "coverage.json"

        if not coverage_json_path.exists():
            return {"success": False, "error": "覆蓋率數據文件不存在"}

        try:
            with open(coverage_json_path, encoding="utf-8") as f:
                coverage_data = json.load(f)

            # 提取關鍵指標
            totals = coverage_data.get("totals", {})
            coverage_percent = totals.get("percent_covered", 0)

            # 按模組分析覆蓋率
            files_coverage = {}
            for file_path, file_data in coverage_data.get("files", {}).items():
                if "src/" in file_path:
                    module_name = (
                        file_path.replace("src/", "")
                        .replace("/", ".")
                        .replace(".py", "")
                    )
                    files_coverage[module_name] = {
                        "percent_covered": file_data.get("summary", {}).get(
                            "percent_covered", 0
                        ),
                        "num_statements": file_data.get("summary", {}).get(
                            "num_statements", 0
                        ),
                        "missing_lines": file_data.get("summary", {}).get(
                            "missing_lines", 0
                        ),
                    }

            return {
                "success": True,
                "overall_coverage": coverage_percent,
                "files_coverage": files_coverage,
                "html_report_path": str(self.project_root / "htmlcov" / "index.html"),
            }

        except Exception as e:
            return {"success": False, "error": f"生成覆蓋率報告失敗: {e}"}

    def fix_import_issues(self) -> dict[str, Any]:
        """修復導入問題

        Returns:
            修復結果
        """
        print("檢查和修復導入問題...")

        fixes_applied = []

        # 1. 檢查Python路徑
        if str(self.src_path) not in sys.path:
            sys.path.insert(0, str(self.src_path))
            fixes_applied.append("添加src目錄到Python路徑")

        # 2. 檢查__init__.py文件
        init_files_needed = [
            self.src_path / "__init__.py",
            self.src_path / "tests" / "__init__.py",
            self.src_path / "tests" / "unit" / "__init__.py",
            self.src_path / "core" / "__init__.py",
            self.src_path / "cogs" / "__init__.py",
            self.src_path / "cogs" / "welcome" / "__init__.py",
        ]

        for init_file in init_files_needed:
            if not init_file.exists():
                init_file.parent.mkdir(parents=True, exist_ok=True)
                init_file.write_text("# Python包初始化文件\n")
                fixes_applied.append(f"創建 {init_file}")

        # 3. 檢查依賴項
        try:
            import discord
            import pytest
            import pytest_asyncio
        except ImportError as e:
            fixes_applied.append(f"缺少依賴項: {e}")

        return {"success": True, "fixes_applied": fixes_applied}

    def analyze_test_failures(self, test_results: dict[str, Any]) -> dict[str, Any]:
        """分析測試失敗原因

        Args:
            test_results: 測試結果

        Returns:
            失敗分析結果
        """
        print("分析測試失敗原因...")

        analysis = {
            "failure_categories": {},
            "common_issues": [],
            "recommendations": [],
        }

        for test in test_results.get("tests", []):
            if not test.get("success", True):
                stderr = test.get("stderr", "")

                # 分析常見錯誤類型
                if "ImportError" in stderr or "ModuleNotFoundError" in stderr:
                    analysis["failure_categories"]["import_errors"] = (
                        analysis["failure_categories"].get("import_errors", 0) + 1
                    )
                    analysis["common_issues"].append("導入錯誤")

                if "AttributeError" in stderr:
                    analysis["failure_categories"]["attribute_errors"] = (
                        analysis["failure_categories"].get("attribute_errors", 0) + 1
                    )
                    analysis["common_issues"].append("屬性錯誤")

                if "TypeError" in stderr:
                    analysis["failure_categories"]["type_errors"] = (
                        analysis["failure_categories"].get("type_errors", 0) + 1
                    )
                    analysis["common_issues"].append("類型錯誤")

                if "AssertionError" in stderr:
                    analysis["failure_categories"]["assertion_errors"] = (
                        analysis["failure_categories"].get("assertion_errors", 0) + 1
                    )
                    analysis["common_issues"].append("斷言錯誤")

        # 生成建議
        if "import_errors" in analysis["failure_categories"]:
            analysis["recommendations"].append("檢查導入路徑和依賴項")

        if "attribute_errors" in analysis["failure_categories"]:
            analysis["recommendations"].append("檢查Mock對象的屬性設置")

        if "type_errors" in analysis["failure_categories"]:
            analysis["recommendations"].append("檢查函數參數類型和返回值")

        if "assertion_errors" in analysis["failure_categories"]:
            analysis["recommendations"].append("檢查測試預期和實際結果")

        return analysis

    def generate_test_report(self, test_results: dict[str, Any]) -> str:
        """生成測試報告

        Args:
            test_results: 測試結果

        Returns:
            報告文本
        """
        report_lines = []

        # 標題
        report_lines.append("=" * 60)
        report_lines.append("新架構測試執行報告")
        report_lines.append("=" * 60)
        report_lines.append("")

        # 基本信息
        report_lines.append(f"執行時間: {test_results.get('timestamp')}")
        report_lines.append(
            f"整體狀態: {'通過' if test_results.get('overall_success') else '失敗'}"
        )
        report_lines.append(f"總測試數: {test_results.get('total_tests', 0)}")
        report_lines.append(f"通過測試: {test_results.get('passed_tests', 0)}")
        report_lines.append(f"失敗測試: {test_results.get('failed_tests', 0)}")
        report_lines.append("")

        # 各測試類型結果
        for test in test_results.get("tests", []):
            test_type = test.get("type", "unknown")
            success = test.get("success", False)
            status = "通過" if success else "失敗"

            report_lines.append(f"{test_type}: {status}")

            if not success:
                if "error" in test:
                    report_lines.append(f"  錯誤: {test['error']}")
                if test.get("stderr"):
                    # 只顯示前10行錯誤信息
                    stderr_lines = test["stderr"].split("\n")[:10]
                    for line in stderr_lines:
                        if line.strip():
                            report_lines.append(f"  {line}")

            report_lines.append("")

        # 覆蓋率信息
        coverage_report = self.generate_coverage_report()
        if coverage_report.get("success"):
            report_lines.append("覆蓋率報告:")
            report_lines.append(
                f"  整體覆蓋率: {coverage_report['overall_coverage']:.1f}%"
            )

            # 顯示關鍵模組覆蓋率
            files_coverage = coverage_report.get("files_coverage", {})
            welcome_modules = {
                k: v for k, v in files_coverage.items() if "welcome" in k.lower()
            }

            if welcome_modules:
                report_lines.append("  歡迎模組覆蓋率:")
                for module, data in welcome_modules.items():
                    coverage_pct = data["percent_covered"]
                    report_lines.append(f"    {module}: {coverage_pct:.1f}%")

            report_lines.append(f"  HTML報告: {coverage_report['html_report_path']}")
            report_lines.append("")

        # 失敗分析
        if test_results.get("failed_tests", 0) > 0:
            analysis = self.analyze_test_failures(test_results)

            report_lines.append("失敗分析:")

            if analysis["failure_categories"]:
                report_lines.append("  錯誤類型統計:")
                for category, count in analysis["failure_categories"].items():
                    report_lines.append(f"    {category}: {count}")

            if analysis["recommendations"]:
                report_lines.append("  修復建議:")
                for i, rec in enumerate(analysis["recommendations"], 1):
                    report_lines.append(f"    {i}. {rec}")

            report_lines.append("")

        # 結尾
        report_lines.append("=" * 60)
        report_lines.append(f"報告生成時間: {datetime.datetime.now().isoformat()}")
        report_lines.append("=" * 60)

        return "\n".join(report_lines)


def main():
    """主函數"""
    parser = argparse.ArgumentParser(description="運行新架構測試")

    parser.add_argument(
        "test_type",
        choices=["unit", "integration", "performance", "all", "fix"],
        help="要運行的測試類型",
    )

    parser.add_argument("--verbose", action="store_true", help="詳細輸出")

    parser.add_argument("--no-coverage", action="store_true", help="跳過覆蓋率報告")

    parser.add_argument("--include-slow", action="store_true", help="包含慢速測試")

    parser.add_argument("--output", type=str, help="輸出報告文件路徑")

    args = parser.parse_args()

    runner = TestRunner()

    try:
        if args.test_type == "fix":
            # 修復導入問題
            result = runner.fix_import_issues()
            print("\n導入問題修復結果:")
            for fix in result["fixes_applied"]:
                print(f"  [已修復] {fix}")
            return

        # 運行測試
        if args.test_type == "unit":
            result = runner.run_unit_tests(
                verbose=args.verbose, coverage=not args.no_coverage
            )
        elif args.test_type == "integration":
            result = runner.run_integration_tests(verbose=args.verbose)
        elif args.test_type == "performance":
            result = runner.run_performance_tests(verbose=args.verbose)
        elif args.test_type == "all":
            result = runner.run_all_tests(
                include_slow=args.include_slow, include_integration=True
            )

        # 生成報告
        if args.test_type == "all":
            report = runner.generate_test_report(result)
        else:
            # 為單個測試類型生成簡化報告
            report = f"""
測試類型: {args.test_type}
狀態: {"通過" if result.get("success") else "失敗"}
返回碼: {result.get("returncode", "N/A")}

標準輸出:
{result.get("stdout", "無輸出")}

標準錯誤:
{result.get("stderr", "無錯誤")}
"""

        # 輸出報告
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(report)
            print(f"報告已保存至: {args.output}")
        else:
            print(report)

        # 設置退出碼
        if args.test_type == "all":
            sys.exit(0 if result.get("overall_success") else 1)
        else:
            sys.exit(0 if result.get("success") else 1)

    except Exception as e:
        print(f"執行失敗: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
