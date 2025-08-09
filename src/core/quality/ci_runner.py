"""CI 管道品質檢查運行器

這個模組專門為 CI/CD 管道提供品質檢查功能，
整合 QualityAssuranceService 來執行完整的靜態分析。
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from . import QualityAssuranceService


class CIQualityRunner:
    """CI 品質檢查運行器"""

    def __init__(self, project_root: Path | None = None) -> None:
        """初始化 CI 運行器

        Args:
            project_root: 專案根目錄路徑
        """
        self.project_root = project_root or Path.cwd()
        self.reports_dir = self.project_root / "quality-reports"
        self.reports_dir.mkdir(exist_ok=True)

        # 初始化品質保證服務
        self.qa_service = QualityAssuranceService(
            mypy_config_path=self.project_root / "quality" / "mypy_ci.ini",
            ruff_config_path=self.project_root / "quality" / "ruff.toml"
        )

    async def run_full_quality_check(
        self,
        target_path: str = "src",
        strict_mode: bool = True
    ) -> bool:
        """執行完整品質檢查

        Args:
            target_path: 檢查目標路徑
            strict_mode: 是否使用嚴格模式

        Returns:
            是否通過品質門檻
        """
        print("🔍 開始執行 CI 品質檢查...")
        print(f"📁 檢查目標: {target_path}")
        print(f"⚙️ 嚴格模式: {'啟用' if strict_mode else '關閉'}")

        try:
            # 執行品質檢查
            results = await self.qa_service.run_quality_checks(target_path)

            # 執行測試覆蓋率檢查
            coverage_data = await self._run_coverage_check()

            # 生成包含覆蓋率的整合報告
            report = self.qa_service.generate_quality_report(results, format="json")

            # 添加覆蓋率資料到報告
            report["coverage"] = coverage_data

            # 儲存報告
            await self._save_reports(report, results)

            # 顯示結果摘要
            self._print_summary(results, coverage_data)

            # 執行品質門檻檢查（包含覆蓋率要求）
            gates_passed = self._enforce_enhanced_quality_gates(
                results, coverage_data, strict=strict_mode
            )

            if gates_passed:
                print("✅ 品質門檻檢查通過！")
                return True
            else:
                print("❌ 品質門檻檢查失敗！")
                self._print_failure_details(results, strict_mode, coverage_data)
                return False

        except Exception as e:
            print(f"💥 品質檢查執行失敗: {e}")
            return False

    async def _run_coverage_check(self) -> dict[str, Any]:
        """執行測試覆蓋率檢查

        Returns:
            覆蓋率資料
        """
        print("📊 執行測試覆蓋率檢查...")

        try:
            # 執行 pytest 並生成覆蓋率報告
            process = await asyncio.create_subprocess_exec(
                "pytest", "tests/unit",
                "--cov=src",
                "--cov-report=json:quality-reports/coverage.json",
                "--cov-report=term-missing",
                "--tb=no",
                "-q",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.project_root
            )

            stdout, stderr = await process.communicate()

            # 讀取覆蓋率 JSON 報告
            coverage_file = self.project_root / "quality-reports" / "coverage.json"
            if coverage_file.exists():
                with open(coverage_file) as f:
                    coverage_data = json.load(f)

                summary = coverage_data.get("totals", {})
                return {
                    "coverage_percentage": summary.get("percent_covered", 0.0),
                    "lines_covered": summary.get("covered_lines", 0),
                    "lines_total": summary.get("num_statements", 0),
                    "lines_missing": summary.get("missing_lines", 0),
                    "files_count": len(coverage_data.get("files", {})),
                    "test_status": "passed" if process.returncode == 0 else "failed",
                    "raw_data": coverage_data
                }
            else:
                return {
                    "coverage_percentage": 0.0,
                    "lines_covered": 0,
                    "lines_total": 0,
                    "lines_missing": 0,
                    "files_count": 0,
                    "test_status": "failed",
                    "error": "Coverage report not generated"
                }

        except Exception as e:
            return {
                "coverage_percentage": 0.0,
                "lines_covered": 0,
                "lines_total": 0,
                "lines_missing": 0,
                "files_count": 0,
                "test_status": "error",
                "error": str(e)
            }

    def _enforce_enhanced_quality_gates(
        self,
        results: Any,
        coverage_data: dict[str, Any],
        strict: bool = True
    ) -> bool:
        """增強的品質門檻檢查（包含覆蓋率）

        Args:
            results: 品質檢查結果
            coverage_data: 覆蓋率資料
            strict: 是否使用嚴格模式

        Returns:
            是否通過品質門檻
        """
        if strict:
            # 嚴格模式：零錯誤、高型別覆蓋率、充分測試覆蓋率
            return (
                results.error_count == 0 and
                results.type_coverage >= 95.0 and
                coverage_data["coverage_percentage"] >= 85.0 and
                coverage_data["test_status"] == "passed" and
                results.status.value in ["success", "warning"]
            )
        else:
            # 寬鬆模式：可容忍少量錯誤和較低覆蓋率
            return (
                results.error_count <= 10 and
                results.type_coverage >= 80.0 and
                coverage_data["coverage_percentage"] >= 70.0 and
                coverage_data["test_status"] in ["passed", "failed"] and
                results.status.value != "failed"
            )

    async def _save_reports(
        self,
        report: dict[str, Any],
        results: Any
    ) -> None:
        """儲存品質檢查報告

        Args:
            report: 品質報告
            results: 檢查結果
        """
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 儲存 JSON 報告
        json_file = self.reports_dir / f"quality_report_{timestamp}.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        # 建立最新報告連結
        latest_file = self.reports_dir / "latest.json"
        with open(latest_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        # 產生文字報告
        text_report = self.qa_service.generate_quality_report(results, format="text")
        text_file = self.reports_dir / f"quality_report_{timestamp}.txt"
        with open(text_file, 'w', encoding='utf-8') as f:
            f.write(text_report["content"])

        print("📊 報告已儲存:")
        print(f"   JSON: {json_file}")
        print(f"   文字: {text_file}")
        print(f"   最新: {latest_file}")

    def _print_summary(
        self,
        results: Any,
        coverage_data: dict[str, Any] = None
    ) -> None:
        """顯示檢查結果摘要（包含覆蓋率）

        Args:
            results: 檢查結果
            coverage_data: 覆蓋率資料
        """
        print("\n📋 品質檢查摘要:")
        print(f"   狀態: {results.status.value}")
        print(f"   型別覆蓋率: {results.type_coverage:.1f}%")
        print(f"   錯誤數量: {results.error_count}")
        print(f"   警告數量: {results.warning_count}")
        print(f"   執行時間: {results.execution_time:.2f}秒")

        if coverage_data:
            print("\n📊 測試覆蓋率:")
            print(f"   覆蓋率: {coverage_data['coverage_percentage']:.1f}%")
            print(f"   覆蓋行數: {coverage_data['lines_covered']}/{coverage_data['lines_total']}")
            print(f"   檢查檔案: {coverage_data['files_count']}")
            print(f"   測試狀態: {coverage_data['test_status']}")

        if results.mypy_errors:
            print(f"\n🔴 Mypy 錯誤 ({len(results.mypy_errors)}):")
            for error in results.mypy_errors[:5]:  # 只顯示前 5 個
                print(f"   - {error}")
            if len(results.mypy_errors) > 5:
                print(f"   ... 還有 {len(results.mypy_errors) - 5} 個錯誤")

        if results.ruff_errors:
            print(f"\n🟡 Ruff 錯誤 ({len(results.ruff_errors)}):")
            for error in results.ruff_errors[:5]:  # 只顯示前 5 個
                print(f"   - {error}")
            if len(results.ruff_errors) > 5:
                print(f"   ... 還有 {len(results.ruff_errors) - 5} 個錯誤")

    def _print_failure_details(
        self,
        results: Any,
        strict_mode: bool,
        coverage_data: dict[str, Any] = None
    ) -> None:
        """顯示失敗詳情（包含覆蓋率）

        Args:
            results: 檢查結果
            strict_mode: 是否為嚴格模式
            coverage_data: 覆蓋率資料
        """
        print("\n❌ 品質門檻失敗原因:")

        if strict_mode:
            print("   嚴格模式要求:")
            print("   - 零錯誤")
            print("   - 型別覆蓋率 ≥ 95%")
            print("   - 測試覆蓋率 ≥ 85%")
            print("   - 測試通過")

            if results.error_count > 0:
                print(f"   ❌ 發現 {results.error_count} 個錯誤 (要求: 0)")

            if results.type_coverage < 95.0:
                print(f"   ❌ 型別覆蓋率 {results.type_coverage:.1f}% (要求: ≥95%)")

            if coverage_data and coverage_data['coverage_percentage'] < 85.0:
                print(f"   ❌ 測試覆蓋率 {coverage_data['coverage_percentage']:.1f}% (要求: ≥85%)")

            if coverage_data and coverage_data['test_status'] != 'passed':
                print(f"   ❌ 測試狀態: {coverage_data['test_status']} (要求: passed)")
        else:
            print("   一般模式要求:")
            print("   - 錯誤數量 ≤ 10")
            print("   - 型別覆蓋率 ≥ 80%")
            print("   - 測試覆蓋率 ≥ 70%")

            if results.error_count > 10:
                print(f"   ❌ 發現 {results.error_count} 個錯誤 (要求: ≤10)")

            if results.type_coverage < 80.0:
                print(f"   ❌ 型別覆蓋率 {results.type_coverage:.1f}% (要求: ≥80%)")

            if coverage_data and coverage_data['coverage_percentage'] < 70.0:
                print(f"   ❌ 測試覆蓋率 {coverage_data['coverage_percentage']:.1f}% (要求: ≥70%)")


async def main() -> None:
    """主執行函數"""
    import argparse

    parser = argparse.ArgumentParser(description="CI 品質檢查運行器")
    parser.add_argument(
        "--target",
        default="src",
        help="檢查目標路徑 (預設: src)"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="啟用嚴格模式"
    )
    parser.add_argument(
        "--output-format",
        choices=["json", "text", "both"],
        default="both",
        help="輸出報告格式"
    )

    args = parser.parse_args()

    # 建立運行器並執行檢查
    runner = CIQualityRunner()
    success = await runner.run_full_quality_check(
        target_path=args.target,
        strict_mode=args.strict
    )

    # 根據結果設定退出碼
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
