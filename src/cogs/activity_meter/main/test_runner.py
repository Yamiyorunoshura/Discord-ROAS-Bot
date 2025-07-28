"""
活躍度測試系統執行器
用於運行完整的活躍度測試系統,直接調用實際程式邏輯進行測試
"""

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# 使用統一的核心模塊
from ...core import create_error_handler, setup_module_logger

# 導入測試模塊
from .activity_test_module import ActivityTestModule, TestReport
from .logic_apis import LogicAPIError

# 設置模塊日誌記錄器
logger = setup_module_logger("activity_test_runner")
error_handler = create_error_handler("activity_test_runner", logger)


class ActivityTestRunner:
    """
    活躍度測試系統執行器
    負責運行完整的活躍度測試系統,直接調用實際程式邏輯進行測試
    """

    def __init__(self):
        """初始化測試執行器"""
        self.logger = logger.getChild("test_runner")
        self.test_module = ActivityTestModule()

        # 測試結果存儲路徑
        self.results_dir = Path("test_results")
        self.results_dir.mkdir(exist_ok=True)

    async def run_complete_test_suite(self) -> TestReport:
        """
        運行完整的測試套件
        執行所有類型的測試,包括功能測試、性能測試、錯誤處理測試

        Returns:
            TestReport: 完整的測試報告
        """
        try:
            self.logger.info("開始運行完整的活躍度測試套件")
            start_time = time.time()

            # 1. 運行基本功能測試
            self.logger.info("執行基本功能測試...")
            functional_test_config = {
                "test_types": [
                    "calculation",
                    "rendering",
                    "settings",
                    "panel",
                    "database",
                ],
                "test_count": 5,
                "timeout": 30,
            }

            functional_report = await self.test_module.test_real_logic(
                functional_test_config
            )

            # 2. 運行性能測試
            self.logger.info("執行性能測試...")
            performance_results = {}

            performance_endpoints = [
                "calculate_activity_score",
                "get_unified_activity_api",
                "integrate_renderer_api",
            ]

            for endpoint in performance_endpoints:
                try:
                    performance_data = (
                        await self.test_module.test_real_logic_response_time(endpoint)
                    )
                    performance_results[endpoint] = performance_data
                except Exception as e:
                    self.logger.error(f"性能測試 {endpoint} 失敗: {e}")
                    performance_results[endpoint] = {"error": str(e)}

            # 3. 運行錯誤處理測試
            self.logger.info("執行錯誤處理測試...")
            error_scenarios = [
                {
                    "name": "無效的請求類型",
                    "test_data": {"request_type": "invalid_type"},
                    "expected_error": "未知的請求類型",
                },
                {
                    "name": "缺少必要參數",
                    "test_data": {"request_type": "get_activity_score"},
                    "expected_error": "缺少必要字段",
                },
                {
                    "name": "無效的數據格式",
                    "test_data": {
                        "request_type": "calculate_activity_score",
                        "parameters": "invalid",
                    },
                    "expected_error": "必須是字典格式",
                },
            ]

            try:
                error_handling_results = (
                    await self.test_module.test_real_logic_error_handling(
                        error_scenarios
                    )
                )
            except Exception as e:
                self.logger.error(f"錯誤處理測試失敗: {e}")
                error_handling_results = {"error": str(e)}

            # 4. 生成綜合測試報告
            end_time = time.time()
            total_execution_time = end_time - start_time

            # 合併所有測試結果
            all_test_results = functional_report.test_results

            # 統計綜合結果
            total_tests = functional_report.total_tests
            passed_tests = functional_report.passed_tests
            failed_tests = functional_report.failed_tests
            error_tests = functional_report.error_tests

            # 檢查性能測試結果
            performance_passed = all(
                result.get("passed", False)
                for result in performance_results.values()
                if "passed" in result
            )

            # 檢查錯誤處理測試結果
            error_handling_passed = error_handling_results.get("success_rate", 0) >= 80

            # 生成綜合報告
            comprehensive_report = TestReport(
                report_id=f"comprehensive_test_{int(time.time())}",
                timestamp=time.time(),
                total_tests=total_tests,
                passed_tests=passed_tests,
                failed_tests=failed_tests,
                error_tests=error_tests,
                timeout_tests=0,
                total_execution_time=total_execution_time,
                average_execution_time=functional_report.average_execution_time,
                test_results=all_test_results,
                coverage_data=functional_report.coverage_data,
                performance_summary={
                    "performance_results": performance_results,
                    "performance_passed": performance_passed,
                    "error_handling_results": error_handling_results,
                    "error_handling_passed": error_handling_passed,
                },
            )

            # 保存測試報告
            await self._save_test_report(comprehensive_report)

            self.logger.info(
                f"完整測試套件執行完成: 總時間 {total_execution_time:.2f}秒"
            )
            return comprehensive_report

        except Exception as e:
            self.logger.error(f"運行完整測試套件時發生錯誤: {e}")
            raise LogicAPIError("E3001", f"完整測試套件執行失敗: {e!s}")

    async def run_functional_tests(self) -> TestReport:
        """
        運行功能測試
        測試活躍度系統的基本功能

        Returns:
            TestReport: 功能測試報告
        """
        try:
            self.logger.info("開始運行功能測試")

            test_config = {
                "test_types": [
                    "calculation",
                    "rendering",
                    "settings",
                    "panel",
                    "database",
                ],
                "test_count": 5,
                "timeout": 30,
            }

            test_report = await self.test_module.test_real_logic(test_config)

            # 保存功能測試報告
            await self._save_test_report(test_report, "functional")

            self.logger.info(
                f"功能測試完成: {test_report.passed_tests}/{test_report.total_tests} 通過"
            )
            return test_report

        except Exception as e:
            self.logger.error(f"運行功能測試時發生錯誤: {e}")
            raise LogicAPIError("E3002", f"功能測試執行失敗: {e!s}")

    async def run_performance_tests(self) -> dict[str, Any]:
        """
        運行性能測試
        測試活躍度系統的性能表現

        Returns:
            Dict[str, Any]: 性能測試結果
        """
        try:
            self.logger.info("開始運行性能測試")

            performance_results = {}

            # 測試各個端點的性能
            endpoints = [
                "calculate_activity_score",
                "get_unified_activity_api",
                "integrate_renderer_api",
                "integrate_settings_api",
                "integrate_panel_api",
            ]

            for endpoint in endpoints:
                try:
                    performance_data = (
                        await self.test_module.test_real_logic_response_time(endpoint)
                    )
                    performance_results[endpoint] = performance_data
                    self.logger.info(f"端點 {endpoint} 性能測試完成")
                except Exception as e:
                    self.logger.error(f"端點 {endpoint} 性能測試失敗: {e}")
                    performance_results[endpoint] = {"error": str(e)}

            # 保存性能測試結果
            await self._save_performance_results(performance_results)

            # 統計性能測試結果
            successful_tests = len(
                [r for r in performance_results.values() if "error" not in r]
            )
            total_tests = len(performance_results)

            self.logger.info(f"性能測試完成: {successful_tests}/{total_tests} 成功")
            return performance_results

        except Exception as e:
            self.logger.error(f"運行性能測試時發生錯誤: {e}")
            raise LogicAPIError("E3003", f"性能測試執行失敗: {e!s}")

    async def run_error_handling_tests(self) -> dict[str, Any]:
        """
        運行錯誤處理測試
        測試活躍度系統的錯誤處理能力

        Returns:
            Dict[str, Any]: 錯誤處理測試結果
        """
        try:
            self.logger.info("開始運行錯誤處理測試")

            # 定義錯誤測試場景
            error_scenarios = [
                {
                    "name": "無效的請求類型",
                    "test_data": {"request_type": "invalid_type"},
                    "expected_error": "未知的請求類型",
                },
                {
                    "name": "缺少必要參數",
                    "test_data": {"request_type": "get_activity_score"},
                    "expected_error": "缺少必要字段",
                },
                {
                    "name": "無效的數據格式",
                    "test_data": {
                        "request_type": "calculate_activity_score",
                        "parameters": "invalid",
                    },
                    "expected_error": "必須是字典格式",
                },
                {
                    "name": "無效的活躍度分數",
                    "test_data": {
                        "request_type": "render_activity",
                        "user_name": "測試用戶",
                        "activity_score": 150,  # 超出範圍
                    },
                    "expected_error": "活躍度分數必須在0-100範圍內",
                },
                {
                    "name": "無效的用戶ID",
                    "test_data": {
                        "request_type": "get_activity_score",
                        "guild_id": "invalid",
                        "user_id": "invalid",
                    },
                    "expected_error": "必須是數字",
                },
            ]

            error_handling_results = (
                await self.test_module.test_real_logic_error_handling(error_scenarios)
            )

            # 保存錯誤處理測試結果
            await self._save_error_handling_results(error_handling_results)

            self.logger.info(
                f"錯誤處理測試完成: {error_handling_results.get('passed_error_tests', 0)}/{error_handling_results.get('total_error_tests', 0)} 通過"
            )
            return error_handling_results

        except Exception as e:
            self.logger.error(f"運行錯誤處理測試時發生錯誤: {e}")
            raise LogicAPIError("E3004", f"錯誤處理測試執行失敗: {e!s}")

    async def run_coverage_analysis(self) -> dict[str, Any]:
        """
        運行覆蓋率分析
        分析測試對實際程式邏輯的覆蓋率

        Returns:
            Dict[str, Any]: 覆蓋率分析結果
        """
        try:
            self.logger.info("開始運行覆蓋率分析")

            # 運行基本測試以獲取測試結果
            test_config = {
                "test_types": [
                    "calculation",
                    "rendering",
                    "settings",
                    "panel",
                    "database",
                ],
                "test_count": 5,
                "timeout": 30,
            }

            test_report = await self.test_module.test_real_logic(test_config)

            # 分析覆蓋率
            coverage_data = await self.test_module.analyze_test_coverage(
                test_report.test_results
            )

            # 保存覆蓋率分析結果
            await self._save_coverage_results(coverage_data)

            self.logger.info(
                f"覆蓋率分析完成: 模塊覆蓋率 {coverage_data.get('module_coverage', 0):.1f}%, API覆蓋率 {coverage_data.get('api_coverage', 0):.1f}%"
            )
            return coverage_data

        except Exception as e:
            self.logger.error(f"運行覆蓋率分析時發生錯誤: {e}")
            raise LogicAPIError("E3005", f"覆蓋率分析執行失敗: {e!s}")

    async def _save_test_report(
        self, test_report: TestReport, report_type: str = "comprehensive"
    ):
        """保存測試報告"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{report_type}_test_report_{timestamp}.json"
            filepath = self.results_dir / filename

            # 轉換測試報告為可序列化的格式
            report_data = {
                "report_id": test_report.report_id,
                "timestamp": test_report.timestamp,
                "total_tests": test_report.total_tests,
                "passed_tests": test_report.passed_tests,
                "failed_tests": test_report.failed_tests,
                "error_tests": test_report.error_tests,
                "timeout_tests": test_report.timeout_tests,
                "total_execution_time": test_report.total_execution_time,
                "average_execution_time": test_report.average_execution_time,
                "coverage_data": test_report.coverage_data,
                "performance_summary": test_report.performance_summary,
                "test_results": [
                    {
                        "test_id": result.test_id,
                        "test_name": result.test_name,
                        "status": result.status.value,
                        "execution_time": result.execution_time,
                        "error_message": result.error_message,
                    }
                    for result in test_report.test_results
                ],
            }

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(report_data, f, ensure_ascii=False, indent=2)

            self.logger.info(f"測試報告已保存: {filepath}")

        except Exception as e:
            self.logger.error(f"保存測試報告時發生錯誤: {e}")

    async def _save_performance_results(self, performance_results: dict[str, Any]):
        """保存性能測試結果"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"performance_results_{timestamp}.json"
            filepath = self.results_dir / filename

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(performance_results, f, ensure_ascii=False, indent=2)

            self.logger.info(f"性能測試結果已保存: {filepath}")

        except Exception as e:
            self.logger.error(f"保存性能測試結果時發生錯誤: {e}")

    async def _save_error_handling_results(
        self, error_handling_results: dict[str, Any]
    ):
        """保存錯誤處理測試結果"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"error_handling_results_{timestamp}.json"
            filepath = self.results_dir / filename

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(error_handling_results, f, ensure_ascii=False, indent=2)

            self.logger.info(f"錯誤處理測試結果已保存: {filepath}")

        except Exception as e:
            self.logger.error(f"保存錯誤處理測試結果時發生錯誤: {e}")

    async def _save_coverage_results(self, coverage_results: dict[str, Any]):
        """保存覆蓋率分析結果"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"coverage_results_{timestamp}.json"
            filepath = self.results_dir / filename

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(coverage_results, f, ensure_ascii=False, indent=2)

            self.logger.info(f"覆蓋率分析結果已保存: {filepath}")

        except Exception as e:
            self.logger.error(f"保存覆蓋率分析結果時發生錯誤: {e}")

    async def close(self):
        """關閉測試執行器,清理資源"""
        try:
            await self.test_module.close()
            self.logger.info("活躍度測試執行器已關閉")
        except Exception as e:
            self.logger.error(f"關閉活躍度測試執行器時發生錯誤: {e}")


# 異步主函數,用於直接運行測試
async def main():
    """主函數,用於直接運行活躍度測試系統"""
    runner = ActivityTestRunner()

    try:
        print("🚀 開始運行 Discord ADR Bot 活躍度測試系統")
        print("=" * 60)

        # 運行完整測試套件
        print("📋 執行完整測試套件...")
        comprehensive_report = await runner.run_complete_test_suite()

        print("✅ 測試完成!")
        print("📊 測試統計:")
        print(f"   - 總測試數: {comprehensive_report.total_tests}")
        print(f"   - 通過測試: {comprehensive_report.passed_tests}")
        print(f"   - 失敗測試: {comprehensive_report.failed_tests}")
        print(f"   - 錯誤測試: {comprehensive_report.error_tests}")
        print(f"   - 總執行時間: {comprehensive_report.total_execution_time:.2f}秒")
        print(f"   - 平均執行時間: {comprehensive_report.average_execution_time:.2f}秒")

        if comprehensive_report.coverage_data:
            coverage = comprehensive_report.coverage_data
            print("📈 覆蓋率分析:")
            print(f"   - 模塊覆蓋率: {coverage.get('module_coverage', 0):.1f}%")
            print(f"   - API覆蓋率: {coverage.get('api_coverage', 0):.1f}%")

        if comprehensive_report.performance_summary:
            perf_summary = comprehensive_report.performance_summary
            print("⚡ 性能測試:")
            if "performance_results" in perf_summary:
                for endpoint, result in perf_summary["performance_results"].items():
                    if "avg_response_time" in result:
                        print(f"   - {endpoint}: {result['avg_response_time']:.3f}秒")

        print("=" * 60)
        print("🎉 活躍度測試系統運行完成!")

    except Exception as e:
        print(f"❌ 測試執行失敗: {e}")
        logger.error(f"測試執行失敗: {e}")

    finally:
        await runner.close()


if __name__ == "__main__":
    # 運行測試系統
    asyncio.run(main())
