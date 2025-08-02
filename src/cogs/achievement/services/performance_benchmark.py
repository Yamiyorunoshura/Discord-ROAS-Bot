"""成就系統效能基準測試.

此模組提供效能基準測試功能，包含：
- 負載測試腳本
- 效能基準測試
- 回歸測試自動化
- 效能趨勢分析

根據 Story 5.1 Task 7 的要求實作。
"""

import asyncio
import logging
import random
import statistics
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from ..database.models import Achievement, AchievementType
from .performance_service import AchievementPerformanceService

logger = logging.getLogger(__name__)


class TestType(str, Enum):
    """測試類型."""
    BENCHMARK = "benchmark"
    LOAD = "load"
    STRESS = "stress"
    REGRESSION = "regression"


class TestStatus(str, Enum):
    """測試狀態."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TestScenario:
    """測試場景."""

    name: str
    """場景名稱"""

    description: str
    """場景描述"""

    test_function: Callable
    """測試函數"""

    parameters: dict[str, Any] = field(default_factory=dict)
    """測試參數"""

    expected_duration_ms: float = 1000.0
    """預期執行時間（毫秒）"""

    max_memory_mb: float = 50.0
    """最大記憶體使用（MB）"""

    iterations: int = 100
    """迭代次數"""


@dataclass
class TestResult:
    """測試結果."""

    scenario_name: str
    """場景名稱"""

    test_type: TestType
    """測試類型"""

    status: TestStatus
    """測試狀態"""

    start_time: datetime
    """開始時間"""

    end_time: datetime | None = None
    """結束時間"""

    duration_ms: float = 0.0
    """執行時間（毫秒）"""

    iterations: int = 0
    """執行迭代次數"""

    success_rate: float = 0.0
    """成功率"""

    avg_response_time_ms: float = 0.0
    """平均回應時間（毫秒）"""

    min_response_time_ms: float = 0.0
    """最小回應時間（毫秒）"""

    max_response_time_ms: float = 0.0
    """最大回應時間（毫秒）"""

    p95_response_time_ms: float = 0.0
    """95百分位回應時間（毫秒）"""

    p99_response_time_ms: float = 0.0
    """99百分位回應時間（毫秒）"""

    memory_usage_mb: float = 0.0
    """記憶體使用量（MB）"""

    errors: list[str] = field(default_factory=list)
    """錯誤列表"""

    metrics: dict[str, Any] = field(default_factory=dict)
    """額外指標"""


class PerformanceBenchmark:
    """成就系統效能基準測試器."""

    def __init__(self, performance_service: AchievementPerformanceService):
        """初始化效能基準測試器.

        Args:
            performance_service: 效能服務
        """
        self._performance_service = performance_service
        self._test_scenarios: dict[str, TestScenario] = {}
        self._test_results: list[TestResult] = []

        # 測試資料
        self._test_achievements: list[Achievement] = []
        self._test_user_ids: list[int] = []

        # 初始化測試場景
        self._initialize_test_scenarios()

        logger.info("PerformanceBenchmark 初始化完成")

    # =============================================================================
    # 測試場景初始化
    # =============================================================================

    def _initialize_test_scenarios(self) -> None:
        """初始化測試場景."""
        scenarios = [
            TestScenario(
                name="get_achievement_single",
                description="單個成就查詢效能測試",
                test_function=self._test_get_achievement_single,
                expected_duration_ms=50.0,
                max_memory_mb=5.0,
                iterations=1000
            ),
            TestScenario(
                name="get_achievement_batch",
                description="批量成就查詢效能測試",
                test_function=self._test_get_achievement_batch,
                parameters={"batch_size": 50},
                expected_duration_ms=200.0,
                max_memory_mb=10.0,
                iterations=200
            ),
            TestScenario(
                name="list_achievements_paginated",
                description="分頁成就列表查詢效能測試",
                test_function=self._test_list_achievements_paginated,
                parameters={"page_size": 20},
                expected_duration_ms=100.0,
                max_memory_mb=5.0,
                iterations=500
            ),
            TestScenario(
                name="user_achievements_query",
                description="用戶成就查詢效能測試",
                test_function=self._test_user_achievements_query,
                expected_duration_ms=150.0,
                max_memory_mb=8.0,
                iterations=300
            ),
            TestScenario(
                name="cache_performance",
                description="快取效能測試",
                test_function=self._test_cache_performance,
                expected_duration_ms=10.0,
                max_memory_mb=20.0,
                iterations=2000
            ),
            TestScenario(
                name="concurrent_operations",
                description="並發操作效能測試",
                test_function=self._test_concurrent_operations,
                parameters={"concurrency": 50},
                expected_duration_ms=300.0,
                max_memory_mb=30.0,
                iterations=100
            ),
            TestScenario(
                name="memory_stress",
                description="記憶體壓力測試",
                test_function=self._test_memory_stress,
                parameters={"data_size": 10000},
                expected_duration_ms=1000.0,
                max_memory_mb=80.0,
                iterations=50
            )
        ]

        for scenario in scenarios:
            self._test_scenarios[scenario.name] = scenario

    # =============================================================================
    # 測試資料準備
    # =============================================================================

    async def prepare_test_data(self) -> None:
        """準備測試資料."""
        logger.info("開始準備測試資料")

        # 生成測試成就
        self._test_achievements = []
        for i in range(100):
            achievement = Achievement(
                id=i + 1,
                name=f"Test Achievement {i + 1}",
                description=f"Test description for achievement {i + 1}",
                category_id=(i % 5) + 1,
                type=random.choice(list(AchievementType)),
                criteria={
                    "target_value": random.randint(10, 1000),
                    "counter_field": "test_counter"
                },
                points=random.randint(10, 100),
                is_active=True
            )
            self._test_achievements.append(achievement)

        # 生成測試用戶ID
        self._test_user_ids = list(range(1, 1001))  # 1000個測試用戶

        logger.info(f"測試資料準備完成: {len(self._test_achievements)} 個成就，{len(self._test_user_ids)} 個用戶")

    # =============================================================================
    # 測試場景實作
    # =============================================================================

    async def _test_get_achievement_single(self, **kwargs) -> float:
        """測試單個成就查詢."""
        if not self._test_achievements:
            await self.prepare_test_data()

        achievement_id = random.choice(self._test_achievements).id

        start_time = time.perf_counter()
        result = await self._performance_service.get_achievement_optimized(achievement_id)
        end_time = time.perf_counter()

        if result is None:
            raise ValueError(f"成就 {achievement_id} 未找到")

        return (end_time - start_time) * 1000

    async def _test_get_achievement_batch(self, batch_size: int = 50, **kwargs) -> float:
        """測試批量成就查詢."""
        if not self._test_achievements:
            await self.prepare_test_data()

        achievement_ids = [a.id for a in random.sample(self._test_achievements, batch_size)]

        start_time = time.perf_counter()
        results = await self._performance_service.batch_get_achievements(achievement_ids)
        end_time = time.perf_counter()

        if len(results) != len(achievement_ids):
            raise ValueError(f"批量查詢結果不匹配: 預期 {len(achievement_ids)}，實際 {len(results)}")

        return (end_time - start_time) * 1000

    async def _test_list_achievements_paginated(self, page_size: int = 20, **kwargs) -> float:
        """測試分頁成就列表查詢."""
        page = random.randint(1, 5)

        start_time = time.perf_counter()
        results, total = await self._performance_service.list_achievements_optimized(
            page=page,
            page_size=page_size
        )
        end_time = time.perf_counter()

        if not results:
            raise ValueError("分頁查詢無結果")

        return (end_time - start_time) * 1000

    async def _test_user_achievements_query(self, **kwargs) -> float:
        """測試用戶成就查詢."""
        if not self._test_user_ids:
            await self.prepare_test_data()

        user_id = random.choice(self._test_user_ids)

        start_time = time.perf_counter()
        results, total = await self._performance_service.get_user_achievements_optimized(user_id)
        end_time = time.perf_counter()

        # 這個測試允許空結果，因為測試用戶可能沒有成就
        return (end_time - start_time) * 1000

    async def _test_cache_performance(self, **kwargs) -> float:
        """測試快取效能."""
        if not self._test_achievements:
            await self.prepare_test_data()

        # 先載入一個成就到快取
        achievement_id = random.choice(self._test_achievements).id
        await self._performance_service.get_achievement_optimized(achievement_id)

        # 測試從快取讀取
        start_time = time.perf_counter()
        result = await self._performance_service.get_achievement_optimized(achievement_id)
        end_time = time.perf_counter()

        if result is None:
            raise ValueError(f"快取測試失敗: 成就 {achievement_id} 未找到")

        return (end_time - start_time) * 1000

    async def _test_concurrent_operations(self, concurrency: int = 50, **kwargs) -> float:
        """測試並發操作效能."""
        if not self._test_achievements:
            await self.prepare_test_data()

        async def single_operation():
            achievement_id = random.choice(self._test_achievements).id
            return await self._performance_service.get_achievement_optimized(achievement_id)

        start_time = time.perf_counter()

        # 並發執行多個操作
        tasks = [single_operation() for _ in range(concurrency)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        end_time = time.perf_counter()

        # 檢查是否有錯誤
        errors = [r for r in results if isinstance(r, Exception)]
        if errors:
            raise ValueError(f"並發操作中有 {len(errors)} 個錯誤")

        return (end_time - start_time) * 1000

    async def _test_memory_stress(self, data_size: int = 10000, **kwargs) -> float:
        """測試記憶體壓力."""
        # 創建大量資料來測試記憶體使用
        large_dataset = []

        start_time = time.perf_counter()

        # 生成大量測試資料
        for i in range(data_size):
            large_dataset.append({
                "id": i,
                "data": f"test_data_{i}" * 100,  # 創建較大的字串
                "timestamp": datetime.now()
            })

        # 模擬處理這些資料
        processed_count = 0
        for item in large_dataset:
            if item["id"] % 2 == 0:
                processed_count += 1

        end_time = time.perf_counter()

        # 清理資料
        large_dataset.clear()

        return (end_time - start_time) * 1000

    # =============================================================================
    # 測試執行
    # =============================================================================

    async def run_benchmark(
        self,
        scenario_names: list[str] | None = None,
        test_type: TestType = TestType.BENCHMARK
    ) -> list[TestResult]:
        """執行基準測試.

        Args:
            scenario_names: 要執行的場景名稱列表，None 表示執行所有場景
            test_type: 測試類型

        Returns:
            測試結果列表
        """
        logger.info(f"開始執行 {test_type.value} 測試")

        # 確定要測試的場景
        if scenario_names is None:
            scenarios = list(self._test_scenarios.values())
        else:
            scenarios = [self._test_scenarios[name] for name in scenario_names if name in self._test_scenarios]

        results = []

        for scenario in scenarios:
            logger.info(f"執行測試場景: {scenario.name}")

            result = TestResult(
                scenario_name=scenario.name,
                test_type=test_type,
                status=TestStatus.RUNNING,
                start_time=datetime.now()
            )

            try:
                # 執行測試
                response_times = []
                success_count = 0

                for i in range(scenario.iterations):
                    try:
                        response_time = await scenario.test_function(**scenario.parameters)
                        response_times.append(response_time)
                        success_count += 1
                    except Exception as e:
                        result.errors.append(f"迭代 {i + 1}: {e!s}")
                        logger.debug(f"測試迭代失敗: {e}")

                # 計算統計
                if response_times:
                    result.avg_response_time_ms = statistics.mean(response_times)
                    result.min_response_time_ms = min(response_times)
                    result.max_response_time_ms = max(response_times)

                    # 計算百分位數
                    sorted_times = sorted(response_times)
                    result.p95_response_time_ms = self._percentile(sorted_times, 95)
                    result.p99_response_time_ms = self._percentile(sorted_times, 99)

                result.iterations = scenario.iterations
                result.success_rate = success_count / scenario.iterations
                result.end_time = datetime.now()
                result.duration_ms = (result.end_time - result.start_time).total_seconds() * 1000
                result.status = TestStatus.COMPLETED

                # 評估測試結果
                await self._evaluate_test_result(result, scenario)

            except Exception as e:
                result.status = TestStatus.FAILED
                result.errors.append(f"測試場景執行失敗: {e!s}")
                result.end_time = datetime.now()
                logger.error(f"測試場景 {scenario.name} 執行失敗: {e}")

            results.append(result)
            self._test_results.append(result)

        logger.info(f"{test_type.value} 測試完成，共執行 {len(scenarios)} 個場景")
        return results

    def _percentile(self, data: list[float], percentile: int) -> float:
        """計算百分位數."""
        if not data:
            return 0.0

        k = (len(data) - 1) * percentile / 100
        f = int(k)
        c = k - f

        if f + 1 < len(data):
            return data[f] * (1 - c) + data[f + 1] * c
        else:
            return data[f]

    async def _evaluate_test_result(self, result: TestResult, scenario: TestScenario) -> None:
        """評估測試結果."""
        # 檢查是否符合預期
        performance_issues = []

        if result.avg_response_time_ms > scenario.expected_duration_ms:
            performance_issues.append(
                f"平均回應時間 ({result.avg_response_time_ms:.2f}ms) "
                f"超過預期 ({scenario.expected_duration_ms:.2f}ms)"
            )

        if result.success_rate < 0.95:  # 95% 成功率門檻
            performance_issues.append(f"成功率過低: {result.success_rate:.1%}")

        if result.p95_response_time_ms > scenario.expected_duration_ms * 2:
            performance_issues.append(
                f"P95回應時間 ({result.p95_response_time_ms:.2f}ms) "
                f"過高 (預期 < {scenario.expected_duration_ms * 2:.2f}ms)"
            )

        result.metrics["performance_issues"] = performance_issues
        result.metrics["meets_expectations"] = len(performance_issues) == 0

        if performance_issues:
            logger.warning(f"測試場景 {scenario.name} 有效能問題: {performance_issues}")

    # =============================================================================
    # 負載測試
    # =============================================================================

    async def run_load_test(
        self,
        duration_seconds: int = 300,
        concurrent_users: int = 50,
        ramp_up_seconds: int = 60
    ) -> TestResult:
        """執行負載測試.

        Args:
            duration_seconds: 測試持續時間（秒）
            concurrent_users: 並發用戶數
            ramp_up_seconds: 爬坡時間（秒）

        Returns:
            負載測試結果
        """
        logger.info(f"開始負載測試: {concurrent_users} 並發用戶，持續 {duration_seconds} 秒")

        result = TestResult(
            scenario_name="load_test",
            test_type=TestType.LOAD,
            status=TestStatus.RUNNING,
            start_time=datetime.now()
        )

        try:
            response_times = []
            success_count = 0
            total_requests = 0

            # 負載測試主循環
            test_start = time.time()
            user_tasks = []

            # 逐步增加並發用戶（爬坡）
            for user_id in range(concurrent_users):
                task = asyncio.create_task(
                    self._simulate_user_behavior(
                        user_id,
                        test_start,
                        duration_seconds,
                        response_times
                    )
                )
                user_tasks.append(task)

                # 爬坡延遲
                if ramp_up_seconds > 0:
                    await asyncio.sleep(ramp_up_seconds / concurrent_users)

            # 等待所有用戶完成
            user_results = await asyncio.gather(*user_tasks, return_exceptions=True)

            # 統計結果
            for user_result in user_results:
                if isinstance(user_result, Exception):
                    result.errors.append(f"用戶模擬錯誤: {user_result!s}")
                else:
                    success_count += user_result.get("success_count", 0)
                    total_requests += user_result.get("total_requests", 0)

            # 計算統計
            if response_times:
                result.avg_response_time_ms = statistics.mean(response_times)
                result.min_response_time_ms = min(response_times)
                result.max_response_time_ms = max(response_times)

                sorted_times = sorted(response_times)
                result.p95_response_time_ms = self._percentile(sorted_times, 95)
                result.p99_response_time_ms = self._percentile(sorted_times, 99)

            result.iterations = total_requests
            result.success_rate = success_count / max(total_requests, 1)
            result.end_time = datetime.now()
            result.duration_ms = (result.end_time - result.start_time).total_seconds() * 1000
            result.status = TestStatus.COMPLETED

            # 額外的負載測試指標
            result.metrics["concurrent_users"] = concurrent_users
            result.metrics["requests_per_second"] = total_requests / (duration_seconds or 1)
            result.metrics["successful_requests_per_second"] = success_count / (duration_seconds or 1)

        except Exception as e:
            result.status = TestStatus.FAILED
            result.errors.append(f"負載測試執行失敗: {e!s}")
            result.end_time = datetime.now()
            logger.error(f"負載測試執行失敗: {e}")

        self._test_results.append(result)
        logger.info("負載測試完成")
        return result

    async def _simulate_user_behavior(
        self,
        user_id: int,
        test_start: float,
        duration_seconds: int,
        response_times: list[float]
    ) -> dict[str, int]:
        """模擬用戶行為.

        Args:
            user_id: 用戶ID
            test_start: 測試開始時間
            duration_seconds: 測試持續時間
            response_times: 回應時間列表

        Returns:
            用戶操作統計
        """
        success_count = 0
        total_requests = 0

        while time.time() - test_start < duration_seconds:
            try:
                # 隨機選擇操作
                operation_type = random.choice([
                    "get_achievement",
                    "list_achievements",
                    "user_achievements"
                ])

                start_time = time.perf_counter()

                if operation_type == "get_achievement":
                    if self._test_achievements:
                        achievement_id = random.choice(self._test_achievements).id
                        await self._performance_service.get_achievement_optimized(achievement_id)

                elif operation_type == "list_achievements":
                    await self._performance_service.list_achievements_optimized(
                        page=random.randint(1, 5),
                        page_size=20
                    )

                elif operation_type == "user_achievements":
                    if self._test_user_ids:
                        user_id = random.choice(self._test_user_ids)
                        await self._performance_service.get_user_achievements_optimized(user_id)

                end_time = time.perf_counter()
                response_time_ms = (end_time - start_time) * 1000
                response_times.append(response_time_ms)
                success_count += 1

            except Exception as e:
                logger.debug(f"用戶 {user_id} 操作失敗: {e}")

            total_requests += 1

            # 用戶操作間隔
            await asyncio.sleep(random.uniform(0.1, 2.0))

        return {
            "success_count": success_count,
            "total_requests": total_requests
        }

    # =============================================================================
    # 結果分析和報告
    # =============================================================================

    def generate_performance_report(self) -> dict[str, Any]:
        """生成效能報告.

        Returns:
            效能報告字典
        """
        if not self._test_results:
            return {"error": "沒有測試結果"}

        # 按測試類型分組
        results_by_type = {}
        for result in self._test_results:
            test_type = result.test_type.value
            if test_type not in results_by_type:
                results_by_type[test_type] = []
            results_by_type[test_type].append(result)

        report = {
            "summary": {
                "total_tests": len(self._test_results),
                "test_types": list(results_by_type.keys()),
                "generation_time": datetime.now().isoformat()
            },
            "results_by_type": {},
            "performance_trends": self._analyze_performance_trends(),
            "recommendations": self._generate_recommendations()
        }

        # 生成各類型測試的摘要
        for test_type, results in results_by_type.items():
            completed_results = [r for r in results if r.status == TestStatus.COMPLETED]

            if completed_results:
                avg_response_times = [r.avg_response_time_ms for r in completed_results]
                success_rates = [r.success_rate for r in completed_results]

                report["results_by_type"][test_type] = {
                    "total_tests": len(results),
                    "completed_tests": len(completed_results),
                    "failed_tests": len([r for r in results if r.status == TestStatus.FAILED]),
                    "avg_response_time_ms": statistics.mean(avg_response_times),
                    "avg_success_rate": statistics.mean(success_rates),
                    "scenarios": [
                        {
                            "name": r.scenario_name,
                            "status": r.status.value,
                            "avg_response_time_ms": r.avg_response_time_ms,
                            "success_rate": r.success_rate,
                            "p95_response_time_ms": r.p95_response_time_ms,
                            "errors": len(r.errors),
                            "meets_expectations": r.metrics.get("meets_expectations", False)
                        }
                        for r in results
                    ]
                }

        return report

    def _analyze_performance_trends(self) -> dict[str, Any]:
        """分析效能趨勢."""
        # 這裡可以分析歷史測試結果的趨勢
        # 暫時返回基本統計
        return {
            "note": "趨勢分析需要更長期的歷史資料",
            "current_performance": "基於當前測試結果的效能狀態"
        }

    def _generate_recommendations(self) -> list[str]:
        """生成效能優化建議."""
        recommendations = []

        if not self._test_results:
            return recommendations

        # 分析完成的測試結果
        completed_results = [r for r in self._test_results if r.status == TestStatus.COMPLETED]

        if completed_results:
            # 檢查平均回應時間
            slow_tests = [r for r in completed_results if r.avg_response_time_ms > 200]
            if slow_tests:
                recommendations.append(
                    f"發現 {len(slow_tests)} 個慢測試場景，建議優化查詢效能"
                )

            # 檢查成功率
            low_success_tests = [r for r in completed_results if r.success_rate < 0.95]
            if low_success_tests:
                recommendations.append(
                    f"發現 {len(low_success_tests)} 個成功率較低的測試場景，建議檢查錯誤處理"
                )

            # 檢查P95回應時間
            high_p95_tests = [r for r in completed_results if r.p95_response_time_ms > 500]
            if high_p95_tests:
                recommendations.append(
                    f"發現 {len(high_p95_tests)} 個P95回應時間過高的測試場景，建議優化最壞情況效能"
                )

        # 失敗的測試
        failed_results = [r for r in self._test_results if r.status == TestStatus.FAILED]
        if failed_results:
            recommendations.append(
                f"有 {len(failed_results)} 個測試場景失敗，需要修復相關問題"
            )

        if not recommendations:
            recommendations.append("所有測試場景表現良好，系統效能符合預期")

        return recommendations

    def get_test_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """取得測試歷史.

        Args:
            limit: 返回的記錄數量限制

        Returns:
            測試歷史記錄列表
        """
        recent_results = self._test_results[-limit:] if len(self._test_results) > limit else self._test_results

        return [
            {
                "scenario_name": result.scenario_name,
                "test_type": result.test_type.value,
                "status": result.status.value,
                "start_time": result.start_time.isoformat(),
                "end_time": result.end_time.isoformat() if result.end_time else None,
                "duration_ms": result.duration_ms,
                "avg_response_time_ms": result.avg_response_time_ms,
                "success_rate": result.success_rate,
                "errors_count": len(result.errors)
            }
            for result in recent_results
        ]


__all__ = [
    "PerformanceBenchmark",
    "TestResult",
    "TestScenario",
    "TestStatus",
    "TestType",
]
