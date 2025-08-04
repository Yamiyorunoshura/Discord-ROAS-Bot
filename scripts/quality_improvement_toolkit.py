#!/usr/bin/env python3
"""
Discord ADR Bot 品質改進工具包
支援PRD-1.64.1-optimized的執行
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


class QualityImprovementToolkit:
    """品質改進工具包"""

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.reports_dir = self.project_root / "reports"
        self.reports_dir.mkdir(exist_ok=True)

        # 初始化報告
        self.report = {
            "timestamp": datetime.now().isoformat(),
            "stages": {},
            "metrics": {},
            "issues": [],
        }

    def log_progress(self, stage: str, task: str, status: str = "completed"):
        """記錄進度"""
        if stage not in self.report["stages"]:
            self.report["stages"][stage] = {}

        self.report["stages"][stage][task] = {
            "status": status,
            "timestamp": datetime.now().isoformat(),
        }

        print(f"[{datetime.now().strftime('%H:%M:%S')}] {stage}: {task} - {status}")

    def run_security_scan(self) -> dict:
        """執行安全掃描"""
        print("🔍 執行安全掃描...")

        try:
            # 執行Bandit掃描
            result = subprocess.run(
                [
                    "bandit",
                    "-r",
                    "cogs/",
                    "-f",
                    "json",
                    "-o",
                    "reports/security_scan.json",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                with open("reports/security_scan.json") as f:
                    security_data = json.load(f)

                high_risk = len(
                    [
                        issue
                        for issue in security_data.get("results", [])
                        if issue.get("issue_severity") == "HIGH"
                    ]
                )
                medium_risk = len(
                    [
                        issue
                        for issue in security_data.get("results", [])
                        if issue.get("issue_severity") == "MEDIUM"
                    ]
                )
                low_risk = len(
                    [
                        issue
                        for issue in security_data.get("results", [])
                        if issue.get("issue_severity") == "LOW"
                    ]
                )

                self.report["metrics"]["security"] = {
                    "high_risk": high_risk,
                    "medium_risk": medium_risk,
                    "low_risk": low_risk,
                    "total": high_risk + medium_risk + low_risk,
                }

                self.log_progress("security", "bandit_scan")
                return self.report["metrics"]["security"]
            else:
                self.report["issues"].append(f"安全掃描失敗: {result.stderr}")
                return {"error": "安全掃描失敗"}

        except FileNotFoundError:
            print("⚠️  Bandit未安裝,請執行: pip install bandit")
            return {"error": "Bandit未安裝"}

    def run_type_check(self) -> dict:
        """執行類型檢查"""
        print("🔍 執行類型檢查...")

        try:
            result = subprocess.run(
                ["mypy", "cogs/", "--strict"],
                check=False,
                capture_output=True,
                text=True,
            )

            # 分析MyPy輸出
            error_lines = [
                line
                for line in result.stdout.split("\n")
                if "error:" in line and "cogs/" in line
            ]

            # 統計錯誤類型
            error_types = {}
            for line in error_lines:
                if "Union" in line:
                    error_types["union"] = error_types.get("union", 0) + 1
                elif "type annotation" in line:
                    error_types["annotation"] = error_types.get("annotation", 0) + 1
                elif "incompatible" in line:
                    error_types["incompatible"] = error_types.get("incompatible", 0) + 1
                else:
                    error_types["other"] = error_types.get("other", 0) + 1

            self.report["metrics"]["type_check"] = {
                "total_errors": len(error_lines),
                "error_types": error_types,
                "files_with_errors": len(
                    set(line.split(":")[0] for line in error_lines)
                ),
            }

            self.log_progress("type_check", "mypy_analysis")
            return self.report["metrics"]["type_check"]

        except FileNotFoundError:
            print("⚠️  MyPy未安裝,請執行: pip install mypy")
            return {"error": "MyPy未安裝"}

    def run_test_coverage(self) -> dict:
        """執行測試覆蓋率檢查"""
        print("🔍 執行測試覆蓋率檢查...")

        try:
            result = subprocess.run(
                [
                    "pytest",
                    "--cov=cogs",
                    "--cov-report=json",
                    "--cov-report=term-missing",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            if os.path.exists("coverage.json"):
                with open("coverage.json") as f:
                    coverage_data = json.load(f)

                total_coverage = coverage_data["totals"]["percent_covered"]
                missing_lines = coverage_data["totals"]["missing_lines"]

                self.report["metrics"]["test_coverage"] = {
                    "total_coverage": total_coverage,
                    "missing_lines": missing_lines,
                    "files_covered": len(coverage_data["files"]),
                }

                self.log_progress("test_coverage", "pytest_coverage")
                return self.report["metrics"]["test_coverage"]
            else:
                return {"error": "coverage.json未生成"}

        except FileNotFoundError:
            print("⚠️  pytest或pytest-cov未安裝")
            return {"error": "pytest工具未安裝"}

    def fix_md5_usage(self) -> int:
        """自動修復MD5使用"""
        print("🔧 修復MD5使用...")

        fixed_count = 0
        md5_pattern = re.compile(r"hashlib\.md5\(([^)]+)\)")

        for py_file in self.project_root.glob("cogs/**/*.py"):
            try:
                with open(py_file, encoding="utf-8") as f:
                    content = f.read()

                if "hashlib.md5" in content:
                    # 替換MD5為SHA256
                    new_content = md5_pattern.sub(r"hashlib.sha256(\1)", content)

                    # 確保導入了hashlib
                    if (
                        "import hashlib" not in new_content
                        and "from hashlib import" not in new_content
                    ):
                        new_content = "import hashlib\n" + new_content

                    with open(py_file, "w", encoding="utf-8") as f:
                        f.write(new_content)

                    fixed_count += 1
                    print(f"  修復: {py_file}")

            except Exception as e:
                self.report["issues"].append(f"修復{py_file}時發生錯誤: {e}")

        self.log_progress("security", "md5_fix", f"修復{fixed_count}個檔案")
        return fixed_count

    def fix_sql_injection(self) -> int:
        """修復SQL注入風險"""
        print("🔧 修復SQL注入風險...")

        fixed_count = 0
        # 常見的SQL注入模式
        patterns = [
            (r'f"SELECT.*?{.*?}"', "使用參數化查詢"),
            (r'f"INSERT.*?{.*?}"', "使用參數化查詢"),
            (r'f"UPDATE.*?{.*?}"', "使用參數化查詢"),
            (r'f"DELETE.*?{.*?}"', "使用參數化查詢"),
        ]

        for py_file in self.project_root.glob("cogs/**/database/*.py"):
            try:
                with open(py_file, encoding="utf-8") as f:
                    content = f.read()

                for pattern, suggestion in patterns:
                    matches = re.findall(pattern, content)
                    if matches:
                        self.report["issues"].append(
                            f"SQL注入風險 in {py_file}: {suggestion}"
                        )
                        fixed_count += len(matches)

            except Exception as e:
                self.report["issues"].append(f"檢查{py_file}時發生錯誤: {e}")

        self.log_progress("security", "sql_injection_check", f"發現{fixed_count}個風險")
        return fixed_count

    def create_test_fixtures(self):
        """創建測試夾具"""
        print("🔧 創建測試夾具...")

        fixtures_dir = self.project_root / "tests" / "fixtures"
        fixtures_dir.mkdir(parents=True, exist_ok=True)

        # Discord mocks
        discord_mocks = '''
import pytest
from unittest.mock import AsyncMock, MagicMock
import discord

@pytest.fixture
def mock_bot():
    """模擬Discord Bot"""
    bot = MagicMock()
    bot.user = MagicMock()
    bot.user.id = 123456789
    bot.user.name = "TestBot"
    bot.get_guild = MagicMock()
    bot.guilds = []
    return bot

@pytest.fixture
def mock_guild():
    """模擬Discord Guild"""
    guild = MagicMock()
    guild.id = 987654321
    guild.name = "Test Guild"
    guild.members = []
    guild.channels = []
    return guild

@pytest.fixture
def mock_channel():
    """模擬Discord Channel"""
    channel = MagicMock()
    channel.id = 111222333
    channel.name = "test-channel"
    channel.send = AsyncMock()
    return channel

@pytest.fixture
def mock_member():
    """模擬Discord Member"""
    member = MagicMock()
    member.id = 444555666
    member.name = "TestUser"
    member.display_name = "Test User"
    member.avatar = None
    return member

@pytest.fixture
def mock_database():
    """模擬資料庫"""
    db = AsyncMock()
    db.fetch_one = AsyncMock()
    db.fetch_all = AsyncMock()
    db.execute = AsyncMock()
    db.executemany = AsyncMock()
    return db
'''

        with open(fixtures_dir / "discord_mocks.py", "w") as f:
            f.write(discord_mocks)

        self.log_progress("test_infrastructure", "create_fixtures")

    def setup_pytest_config(self):
        """設置pytest配置"""
        print("🔧 設置pytest配置...")

        pytest_config = """
[tool.pytest.ini_options]
asyncio_mode = "auto"
timeout = 30
testpaths = ["tests"]
python_files = "test_*.py"
python_classes = "Test*"
python_functions = "test_*"
addopts = "--cov=cogs --cov-report=html --cov-report=term-missing --cov-fail-under=70"
markers = [
    "unit: 單元測試",
    "integration: 整合測試", 
    "slow: 慢速測試",
    "security: 安全測試"
]
"""

        # 檢查是否已有pyproject.toml
        pyproject_path = self.project_root / "pyproject.toml"
        if pyproject_path.exists():
            with open(pyproject_path) as f:
                content = f.read()

            if "[tool.pytest.ini_options]" not in content:
                with open(pyproject_path, "a") as f:
                    f.write("\n" + pytest_config)
        else:
            with open(pyproject_path, "w") as f:
                f.write(pytest_config)

        self.log_progress("test_infrastructure", "setup_pytest")

    def generate_daily_report(self, stage: str) -> str:
        """生成每日報告"""
        report_path = (
            self.reports_dir
            / f"daily_report_{stage}_{datetime.now().strftime('%Y%m%d')}.json"
        )

        with open(report_path, "w") as f:
            json.dump(self.report, f, indent=2, ensure_ascii=False)

        # 生成可讀性報告
        readable_report = f"""
# 每日品質改進報告 - {stage}
生成時間: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## 階段進度
"""

        for stage_name, tasks in self.report["stages"].items():
            readable_report += f"\n### {stage_name}\n"
            for task, info in tasks.items():
                status_emoji = "✅" if info["status"] == "completed" else "🔄"
                readable_report += f"- {status_emoji} {task}: {info['status']}\n"

        if self.report["metrics"]:
            readable_report += "\n## 品質指標\n"
            for metric_name, values in self.report["metrics"].items():
                readable_report += f"\n### {metric_name}\n"
                for key, value in values.items():
                    readable_report += f"- {key}: {value}\n"

        if self.report["issues"]:
            readable_report += "\n## 發現問題\n"
            for issue in self.report["issues"]:
                readable_report += f"- ⚠️ {issue}\n"

        readable_path = (
            self.reports_dir
            / f"daily_report_{stage}_{datetime.now().strftime('%Y%m%d')}.md"
        )
        with open(readable_path, "w", encoding="utf-8") as f:
            f.write(readable_report)

        return str(readable_path)

    def run_stage_1_security_fixes(self):
        """執行階段1:安全修復"""
        print("🚀 開始階段1:安全修復")

        # 安全掃描
        security_metrics = self.run_security_scan()

        # 修復MD5使用
        md5_fixed = self.fix_md5_usage()

        # 檢查SQL注入
        sql_risks = self.fix_sql_injection()

        # 生成報告
        report_path = self.generate_daily_report("stage1_security")
        print(f"📊 階段1報告已生成: {report_path}")

        return {
            "security_metrics": security_metrics,
            "md5_fixed": md5_fixed,
            "sql_risks": sql_risks,
            "report_path": report_path,
        }

    def run_stage_2_type_fixes(self):
        """執行階段2:類型修復"""
        print("🚀 開始階段2:類型修復")

        # 類型檢查
        type_metrics = self.run_type_check()

        # 生成報告
        report_path = self.generate_daily_report("stage2_types")
        print(f"📊 階段2報告已生成: {report_path}")

        return {"type_metrics": type_metrics, "report_path": report_path}

    def run_stage_3_test_infrastructure(self):
        """執行階段3:測試基礎設施"""
        print("🚀 開始階段3:測試基礎設施")

        # 設置測試環境
        self.setup_pytest_config()

        # 創建測試夾具
        self.create_test_fixtures()

        # 執行測試覆蓋率
        coverage_metrics = self.run_test_coverage()

        # 生成報告
        report_path = self.generate_daily_report("stage3_tests")
        print(f"📊 階段3報告已生成: {report_path}")

        return {"coverage_metrics": coverage_metrics, "report_path": report_path}

    def run_full_assessment(self):
        """執行完整評估"""
        print("🔍 執行完整品質評估...")

        # 執行所有檢查
        security_metrics = self.run_security_scan()
        type_metrics = self.run_type_check()
        coverage_metrics = self.run_test_coverage()

        # 計算整體分數
        security_score = max(
            0,
            100
            - (
                security_metrics.get("high_risk", 0) * 10
                + security_metrics.get("medium_risk", 0) * 5
                + security_metrics.get("low_risk", 0) * 2
            ),
        )

        type_score = max(0, 100 - type_metrics.get("total_errors", 0) * 1.5)
        coverage_score = coverage_metrics.get("total_coverage", 0)

        overall_score = (security_score + type_score + coverage_score) / 3

        self.report["metrics"]["overall"] = {
            "security_score": security_score,
            "type_score": type_score,
            "coverage_score": coverage_score,
            "overall_score": overall_score,
            "grade": self.get_grade(overall_score),
        }

        # 生成完整報告
        report_path = self.generate_daily_report("full_assessment")
        print(f"📊 完整評估報告已生成: {report_path}")

        return self.report["metrics"]["overall"]

    def get_grade(self, score: float) -> str:
        """根據分數計算等級"""
        if score >= 90:
            return "A"
        elif score >= 85:
            return "A-"
        elif score >= 80:
            return "B+"
        elif score >= 75:
            return "B"
        elif score >= 70:
            return "B-"
        elif score >= 65:
            return "C+"
        elif score >= 60:
            return "C"
        else:
            return "D"


def main():
    """主函數"""
    toolkit = QualityImprovementToolkit()

    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python quality_improvement_toolkit.py assessment  # 完整評估")
        print("  python quality_improvement_toolkit.py stage1     # 階段1:安全修復")
        print("  python quality_improvement_toolkit.py stage2     # 階段2:類型修復")
        print(
            "  python quality_improvement_toolkit.py stage3     # 階段3:測試基礎設施"
        )
        return

    command = sys.argv[1]

    if command == "assessment":
        result = toolkit.run_full_assessment()
        print(
            f"\n🎯 整體品質評分: {result['overall_score']:.1f}/100 ({result['grade']})"
        )

    elif command == "stage1":
        result = toolkit.run_stage_1_security_fixes()
        print(f"\n✅ 階段1完成 - 修復了 {result['md5_fixed']} 個MD5使用")

    elif command == "stage2":
        result = toolkit.run_stage_2_type_fixes()
        print(
            f"\n✅ 階段2完成 - 發現 {result['type_metrics'].get('total_errors', 0)} 個類型錯誤"
        )

    elif command == "stage3":
        result = toolkit.run_stage_3_test_infrastructure()
        print(
            f"\n✅ 階段3完成 - 測試覆蓋率: {result['coverage_metrics'].get('total_coverage', 0):.1f}%"
        )

    else:
        print(f"未知命令: {command}")


if __name__ == "__main__":
    main()
