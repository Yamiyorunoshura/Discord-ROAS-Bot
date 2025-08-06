"""
æ´»èºåº¦æ¸¬è©¦ç³»çµ±å·è¡å¨
ç¨æ¼éè¡å®æ´çæ´»èºåº¦æ¸¬è©¦ç³»çµ±,ç´æ¥èª¿ç¨å¯¦éç¨å¼éè¼¯é²è¡æ¸¬è©¦
"""

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# ä½¿ç¨çµ±ä¸çæ ¸å¿æ¨¡å¡
from ...core import create_error_handler, setup_module_logger
from ..constants import MIN_SUCCESS_RATE_THRESHOLD

# å°å¥æ¸¬è©¦æ¨¡å¡
from .activity_test_module import ActivityTestModule, TestReport
from .logic_apis import LogicAPIError

# è¨­ç½®æ¨¡å¡æ¥èªè¨éå¨
logger = setup_module_logger("activity_test_runner")
error_handler = create_error_handler("activity_test_runner", logger)


class ActivityTestRunner:
    """
    æ´»èºåº¦æ¸¬è©¦ç³»çµ±å·è¡å¨
    è² è²¬éè¡å®æ´çæ´»èºåº¦æ¸¬è©¦ç³»çµ±,ç´æ¥èª¿ç¨å¯¦éç¨å¼éè¼¯é²è¡æ¸¬è©¦
    """

    def __init__(self):
        """åå§åæ¸¬è©¦å·è¡å¨"""
        self.logger = logger.getChild("test_runner")
        self.test_module = ActivityTestModule()

        # æ¸¬è©¦çµæå­å²è·¯å¾
        self.results_dir = Path("test_results")
        self.results_dir.mkdir(exist_ok=True)

    async def run_complete_test_suite(self) -> TestReport:
        """
        éè¡å®æ´çæ¸¬è©¦å¥ä»¶
        å·è¡ææé¡åçæ¸¬è©¦,åæ¬åè½æ¸¬è©¦ãæ§è½æ¸¬è©¦ãé¯èª¤èçæ¸¬è©¦

        Returns:
            TestReport: å®æ´çæ¸¬è©¦å ±å
        """
        try:
            self.logger.info("éå§éè¡å®æ´çæ´»èºåº¦æ¸¬è©¦å¥ä»¶")
            start_time = time.time()

            # 1. éè¡åºæ¬åè½æ¸¬è©¦
            self.logger.info("å·è¡åºæ¬åè½æ¸¬è©¦...")
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

            # 2. éè¡æ§è½æ¸¬è©¦
            self.logger.info("å·è¡æ§è½æ¸¬è©¦...")
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
                    self.logger.error(f"æ§è½æ¸¬è©¦ {endpoint} å¤±æ: {e}")
                    performance_results[endpoint] = {"error": str(e)}

            # 3. éè¡é¯èª¤èçæ¸¬è©¦
            self.logger.info("å·è¡é¯èª¤èçæ¸¬è©¦...")
            error_scenarios = [
                {
                    "name": "ç¡æçè«æ±é¡å",
                    "test_data": {"request_type": "invalid_type"},
                    "expected_error": "æªç¥çè«æ±é¡å",
                },
                {
                    "name": "ç¼ºå°å¿è¦åæ¸",
                    "test_data": {"request_type": "get_activity_score"},
                    "expected_error": "ç¼ºå°å¿è¦å­æ®µ",
                },
                {
                    "name": "ç¡æçæ¸ææ ¼å¼",
                    "test_data": {
                        "request_type": "calculate_activity_score",
                        "parameters": "invalid",
                    },
                    "expected_error": "å¿é æ¯å­å¸æ ¼å¼",
                },
            ]

            try:
                error_handling_results = (
                    await self.test_module.test_real_logic_error_handling(
                        error_scenarios
                    )
                )
            except Exception as e:
                self.logger.error(f"é¯èª¤èçæ¸¬è©¦å¤±æ: {e}")
                error_handling_results = {"error": str(e)}

            # 4. çæç¶åæ¸¬è©¦å ±å
            end_time = time.time()
            total_execution_time = end_time - start_time

            # åä½µæææ¸¬è©¦çµæ
            all_test_results = functional_report.test_results

            # çµ±è¨ç¶åçµæ
            total_tests = functional_report.total_tests
            passed_tests = functional_report.passed_tests
            failed_tests = functional_report.failed_tests
            error_tests = functional_report.error_tests

            # æª¢æ¥æ§è½æ¸¬è©¦çµæ
            performance_passed = all(
                result.get("passed", False)
                for result in performance_results.values()
                if "passed" in result
            )

            # æª¢æ¥é¯èª¤èçæ¸¬è©¦çµæ
            error_handling_passed = (
                error_handling_results.get("success_rate", 0)
                >= MIN_SUCCESS_RATE_THRESHOLD
            )

            # çæç¶åå ±å
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

            # ä¿å­æ¸¬è©¦å ±å
            await self._save_test_report(comprehensive_report)

            self.logger.info(
                f"å®æ´æ¸¬è©¦å¥ä»¶å·è¡å®æ: ç¸½æé {total_execution_time:.2f}ç§"
            )
            return comprehensive_report

        except Exception as e:
            self.logger.error(f"éè¡å®æ´æ¸¬è©¦å¥ä»¶æç¼çé¯èª¤: {e}")
            raise LogicAPIError("E3001", f"å®æ´æ¸¬è©¦å¥ä»¶å·è¡å¤±æ: {e!s}") from e

    async def run_functional_tests(self) -> TestReport:
        """
        éè¡åè½æ¸¬è©¦
        æ¸¬è©¦æ´»èºåº¦ç³»çµ±çåºæ¬åè½

        Returns:
            TestReport: åè½æ¸¬è©¦å ±å
        """
        try:
            self.logger.info("éå§éè¡åè½æ¸¬è©¦")

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

            # ä¿å­åè½æ¸¬è©¦å ±å
            await self._save_test_report(test_report, "functional")

            self.logger.info(
                f"åè½æ¸¬è©¦å®æ: {test_report.passed_tests}/{test_report.total_tests} éé"
            )
            return test_report

        except Exception as e:
            self.logger.error(f"éè¡åè½æ¸¬è©¦æç¼çé¯èª¤: {e}")
            raise LogicAPIError("E3002", f"åè½æ¸¬è©¦å·è¡å¤±æ: {e!s}") from e

    async def run_performance_tests(self) -> dict[str, Any]:
        """
        éè¡æ§è½æ¸¬è©¦
        æ¸¬è©¦æ´»èºåº¦ç³»çµ±çæ§è½è¡¨ç¾

        Returns:
            Dict[str, Any]: æ§è½æ¸¬è©¦çµæ
        """
        try:
            self.logger.info("éå§éè¡æ§è½æ¸¬è©¦")

            performance_results = {}

            # æ¸¬è©¦ååç«¯é»çæ§è½
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
                    self.logger.info(f"ç«¯é» {endpoint} æ§è½æ¸¬è©¦å®æ")
                except Exception as e:
                    self.logger.error(f"ç«¯é» {endpoint} æ§è½æ¸¬è©¦å¤±æ: {e}")
                    performance_results[endpoint] = {"error": str(e)}

            # ä¿å­æ§è½æ¸¬è©¦çµæ
            await self._save_performance_results(performance_results)

            # çµ±è¨æ§è½æ¸¬è©¦çµæ
            successful_tests = len([
                r for r in performance_results.values() if "error" not in r
            ])
            total_tests = len(performance_results)

            self.logger.info(f"æ§è½æ¸¬è©¦å®æ: {successful_tests}/{total_tests} æå")
            return performance_results

        except Exception as e:
            self.logger.error(f"éè¡æ§è½æ¸¬è©¦æç¼çé¯èª¤: {e}")
            raise LogicAPIError("E3003", f"æ§è½æ¸¬è©¦å·è¡å¤±æ: {e!s}") from e

    async def run_error_handling_tests(self) -> dict[str, Any]:
        """
        éè¡é¯èª¤èçæ¸¬è©¦
        æ¸¬è©¦æ´»èºåº¦ç³»çµ±çé¯èª¤èçè½å

        Returns:
            Dict[str, Any]: é¯èª¤èçæ¸¬è©¦çµæ
        """
        try:
            self.logger.info("éå§éè¡é¯èª¤èçæ¸¬è©¦")

            # å®ç¾©é¯èª¤æ¸¬è©¦å ´æ¯
            error_scenarios = [
                {
                    "name": "ç¡æçè«æ±é¡å",
                    "test_data": {"request_type": "invalid_type"},
                    "expected_error": "æªç¥çè«æ±é¡å",
                },
                {
                    "name": "ç¼ºå°å¿è¦åæ¸",
                    "test_data": {"request_type": "get_activity_score"},
                    "expected_error": "ç¼ºå°å¿è¦å­æ®µ",
                },
                {
                    "name": "ç¡æçæ¸ææ ¼å¼",
                    "test_data": {
                        "request_type": "calculate_activity_score",
                        "parameters": "invalid",
                    },
                    "expected_error": "å¿é æ¯å­å¸æ ¼å¼",
                },
                {
                    "name": "ç¡æçæ´»èºåº¦åæ¸",
                    "test_data": {
                        "request_type": "render_activity",
                        "user_name": "æ¸¬è©¦ç¨æ¶",
                        "activity_score": 150,  # è¶åºç¯å
                    },
                    "expected_error": "æ´»èºåº¦åæ¸å¿é å¨0-100ç¯åå§",
                },
                {
                    "name": "ç¡æçç¨æ¶ID",
                    "test_data": {
                        "request_type": "get_activity_score",
                        "guild_id": "invalid",
                        "user_id": "invalid",
                    },
                    "expected_error": "å¿é æ¯æ¸å­",
                },
            ]

            error_handling_results = (
                await self.test_module.test_real_logic_error_handling(error_scenarios)
            )

            # ä¿å­é¯èª¤èçæ¸¬è©¦çµæ
            await self._save_error_handling_results(error_handling_results)

            self.logger.info(
                f"é¯èª¤èçæ¸¬è©¦å®æ: {error_handling_results.get('passed_error_tests', 0)}/{error_handling_results.get('total_error_tests', 0)} éé"
            )
            return error_handling_results

        except Exception as e:
            self.logger.error(f"éè¡é¯èª¤èçæ¸¬è©¦æç¼çé¯èª¤: {e}")
            raise LogicAPIError("E3004", f"é¯èª¤èçæ¸¬è©¦å·è¡å¤±æ: {e!s}") from e

    async def run_coverage_analysis(self) -> dict[str, Any]:
        """
        éè¡è¦èçåæ
        åææ¸¬è©¦å°å¯¦éç¨å¼éè¼¯çè¦èç

        Returns:
            Dict[str, Any]: è¦èçåæçµæ
        """
        try:
            self.logger.info("éå§éè¡è¦èçåæ")

            # éè¡åºæ¬æ¸¬è©¦ä»¥ç²åæ¸¬è©¦çµæ
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

            # åæè¦èç
            coverage_data = await self.test_module.analyze_test_coverage(
                test_report.test_results
            )

            # ä¿å­è¦èçåæçµæ
            await self._save_coverage_results(coverage_data)

            self.logger.info(
                f"è¦èçåæå®æ: æ¨¡å¡è¦èç {coverage_data.get('module_coverage', 0):.1f}%, APIè¦èç {coverage_data.get('api_coverage', 0):.1f}%"
            )
            return coverage_data

        except Exception as e:
            self.logger.error(f"éè¡è¦èçåææç¼çé¯èª¤: {e}")
            raise LogicAPIError("E3005", f"è¦èçåæå·è¡å¤±æ: {e!s}") from e

    async def _save_test_report(
        self, test_report: TestReport, report_type: str = "comprehensive"
    ):
        """ä¿å­æ¸¬è©¦å ±å"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{report_type}_test_report_{timestamp}.json"
            filepath = self.results_dir / filename

            # è½ææ¸¬è©¦å ±åçºå¯åºååçæ ¼å¼
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

            with filepath.open("w", encoding="utf-8") as f:
                json.dump(report_data, f, ensure_ascii=False, indent=2)

            self.logger.info(f"æ¸¬è©¦å ±åå·²ä¿å­: {filepath}")

        except Exception as e:
            self.logger.error(f"ä¿å­æ¸¬è©¦å ±åæç¼çé¯èª¤: {e}")

    async def _save_performance_results(self, performance_results: dict[str, Any]):
        """ä¿å­æ§è½æ¸¬è©¦çµæ"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"performance_results_{timestamp}.json"
            filepath = self.results_dir / filename

            with filepath.open("w", encoding="utf-8") as f:
                json.dump(performance_results, f, ensure_ascii=False, indent=2)

            self.logger.info(f"æ§è½æ¸¬è©¦çµæå·²ä¿å­: {filepath}")

        except Exception as e:
            self.logger.error(f"ä¿å­æ§è½æ¸¬è©¦çµææç¼çé¯èª¤: {e}")

    async def _save_error_handling_results(
        self, error_handling_results: dict[str, Any]
    ):
        """ä¿å­é¯èª¤èçæ¸¬è©¦çµæ"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"error_handling_results_{timestamp}.json"
            filepath = self.results_dir / filename

            with filepath.open("w", encoding="utf-8") as f:
                json.dump(error_handling_results, f, ensure_ascii=False, indent=2)

            self.logger.info(f"é¯èª¤èçæ¸¬è©¦çµæå·²ä¿å­: {filepath}")

        except Exception as e:
            self.logger.error(f"ä¿å­é¯èª¤èçæ¸¬è©¦çµææç¼çé¯èª¤: {e}")

    async def _save_coverage_results(self, coverage_results: dict[str, Any]):
        """ä¿å­è¦èçåæçµæ"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"coverage_results_{timestamp}.json"
            filepath = self.results_dir / filename

            with filepath.open("w", encoding="utf-8") as f:
                json.dump(coverage_results, f, ensure_ascii=False, indent=2)

            self.logger.info(f"è¦èçåæçµæå·²ä¿å­: {filepath}")

        except Exception as e:
            self.logger.error(f"ä¿å­è¦èçåæçµææç¼çé¯èª¤: {e}")

    async def close(self):
        """ééæ¸¬è©¦å·è¡å¨,æ¸çè³æº"""
        try:
            await self.test_module.close()
            self.logger.info("æ´»èºåº¦æ¸¬è©¦å·è¡å¨å·²éé")
        except Exception as e:
            self.logger.error(f"ééæ´»èºåº¦æ¸¬è©¦å·è¡å¨æç¼çé¯èª¤: {e}")


# ç°æ­¥ä¸»å½æ¸,ç¨æ¼ç´æ¥éè¡æ¸¬è©¦
async def main():
    """ä¸»å½æ¸,ç¨æ¼ç´æ¥éè¡æ´»èºåº¦æ¸¬è©¦ç³»çµ±"""
    runner = ActivityTestRunner()

    try:
        print("éå§éè¡ Discord ADR Bot æ´»èºåº¦æ¸¬è©¦ç³»çµ±")
        print("=" * 60)

        # éè¡å®æ´æ¸¬è©¦å¥ä»¶
        print("å·è¡å®æ´æ¸¬è©¦å¥ä»¶...")
        comprehensive_report = await runner.run_complete_test_suite()

        print("æ¸¬è©¦å®æ!")
        print("æ¸¬è©¦çµ±è¨:")
        print(f"   - ç¸½æ¸¬è©¦æ¸: {comprehensive_report.total_tests}")
        print(f"   - ééæ¸¬è©¦: {comprehensive_report.passed_tests}")
        print(f"   - å¤±ææ¸¬è©¦: {comprehensive_report.failed_tests}")
        print(f"   - é¯èª¤æ¸¬è©¦: {comprehensive_report.error_tests}")
        print(f"   - ç¸½å·è¡æé: {comprehensive_report.total_execution_time:.2f}ç§")
        print(f"   - å¹³åå·è¡æé: {comprehensive_report.average_execution_time:.2f}ç§")

        if comprehensive_report.coverage_data:
            coverage = comprehensive_report.coverage_data
            print(" è¦èçåæ:")
            print(f"   - æ¨¡å¡è¦èç: {coverage.get('module_coverage', 0):.1f}%")
            print(f"   - APIè¦èç: {coverage.get('api_coverage', 0):.1f}%")

        if comprehensive_report.performance_summary:
            perf_summary = comprehensive_report.performance_summary
            print("â¡ æ§è½æ¸¬è©¦:")
            if "performance_results" in perf_summary:
                for endpoint, result in perf_summary["performance_results"].items():
                    if "avg_response_time" in result:
                        print(f"   - {endpoint}: {result['avg_response_time']:.3f}ç§")

        print("=" * 60)
        print("æ´»èºåº¦æ¸¬è©¦ç³»çµ±éè¡å®æ!")

    except Exception as e:
        print(f"æ¸¬è©¦å·è¡å¤±æ: {e}")
        logger.error(f"æ¸¬è©¦å·è¡å¤±æ: {e}")

    finally:
        await runner.close()


if __name__ == "__main__":
    # éè¡æ¸¬è©¦ç³»çµ±
    asyncio.run(main())
