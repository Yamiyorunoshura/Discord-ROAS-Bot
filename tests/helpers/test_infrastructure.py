"""改進的測試基礎設施.

此模組提供增強的測試工具和基礎設施,包括:
- 自動化測試數據管理
- 測試環境隔離
- 效能測試工具
- 測試覆蓋率分析
- 測試報告生成
- 並行測試支援

針對 Story 5.2 的測試品質提升需求設計.
"""

import asyncio
import contextlib
import json
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, TypeVar
from unittest.mock import AsyncMock

import pytest

from src.core.config import Settings
from src.core.database import DatabasePool

T = TypeVar("T")


@dataclass
class TestContext:
    """測試上下文."""

    test_name: str
    start_time: datetime = field(default_factory=datetime.now)
    temp_files: list[Path] = field(default_factory=list)
    temp_dirs: list[Path] = field(default_factory=list)
    database_pools: list[DatabasePool] = field(default_factory=list)
    async_resources: list[Any] = field(default_factory=list)
    performance_metrics: dict[str, Any] = field(default_factory=dict)

    async def cleanup(self):
        """清理測試資源."""
        # 清理異步資源
        for resource in self.async_resources:
            if hasattr(resource, "cleanup"):
                await resource.cleanup()
            elif hasattr(resource, "close"):
                await resource.close()

        # 清理資料庫連線
        for pool in self.database_pools:
            await pool.close_all()

        # 清理臨時文件
        for temp_file in self.temp_files:
            if temp_file.exists():
                temp_file.unlink()

        # 清理臨時目錄
        for temp_dir in self.temp_dirs:
            if temp_dir.exists():
                import shutil

                shutil.rmtree(temp_dir, ignore_errors=True)


class TestDatabaseManager:
    """測試資料庫管理器."""

    def __init__(self):
        self.databases: dict[str, Path] = {}
        self.pools: dict[str, DatabasePool] = {}

    async def create_test_database(self, name: str = "test") -> DatabasePool:
        """創建測試資料庫."""
        # 創建臨時資料庫文件
        temp_db = tempfile.NamedTemporaryFile(suffix=f"_{name}.db", delete=False)
        db_path = Path(temp_db.name)
        temp_db.close()

        self.databases[name] = db_path

        # 創建資料庫連線池
        settings = Settings()
        pool = DatabasePool(db_path, settings)
        await pool.initialize()

        self.pools[name] = pool
        return pool

    async def setup_achievement_database(self, pool: DatabasePool):
        """設置成就系統資料庫結構."""
        from src.cogs.achievement.database import initialize_achievement_database

        await initialize_achievement_database(pool)

    async def cleanup_all(self):
        """清理所有測試資料庫."""
        # 關閉連線池
        for pool in self.pools.values():
            await pool.close_all()

        # 刪除臨時文件
        for db_path in self.databases.values():
            if db_path.exists():
                db_path.unlink()

        self.databases.clear()
        self.pools.clear()


class PerformanceTestUtils:
    """效能測試工具."""

    @staticmethod
    @contextlib.asynccontextmanager
    async def measure_execution_time(operation_name: str):
        """測量執行時間."""
        start_time = time.perf_counter()
        start_memory = PerformanceTestUtils._get_memory_usage()

        metrics = {
            "operation": operation_name,
            "start_time": start_time,
            "start_memory": start_memory,
        }

        try:
            yield metrics
        finally:
            end_time = time.perf_counter()
            end_memory = PerformanceTestUtils._get_memory_usage()

            metrics.update(
                {
                    "end_time": end_time,
                    "execution_time": end_time - start_time,
                    "end_memory": end_memory,
                    "memory_delta": end_memory - start_memory,
                }
            )

    @staticmethod
    def _get_memory_usage() -> float:
        """獲取當前記憶體使用量(MB)."""
        try:
            import psutil

            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except ImportError:
            return 0.0

    @staticmethod
    async def stress_test(
        coroutine_factory,
        concurrent_count: int = 10,
        iterations_per_coroutine: int = 100,
        max_execution_time: float = 30.0,
    ) -> dict[str, Any]:
        """執行壓力測試."""

        async def run_iterations():
            """執行多次迭代."""
            for _ in range(iterations_per_coroutine):
                await coroutine_factory()

        # 創建並發任務
        tasks = [run_iterations() for _ in range(concurrent_count)]

        start_time = time.perf_counter()
        start_memory = PerformanceTestUtils._get_memory_usage()

        # 執行壓力測試
        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=max_execution_time,
            )
            success = True
            error = None
        except TimeoutError:
            success = False
            error = f"測試超時(>{max_execution_time}s)"
        except Exception as e:
            success = False
            error = str(e)

        end_time = time.perf_counter()
        end_memory = PerformanceTestUtils._get_memory_usage()

        return {
            "success": success,
            "error": error,
            "total_operations": concurrent_count * iterations_per_coroutine,
            "execution_time": end_time - start_time,
            "operations_per_second": (concurrent_count * iterations_per_coroutine)
            / (end_time - start_time),
            "memory_usage": {
                "start": start_memory,
                "end": end_memory,
                "delta": end_memory - start_memory,
            },
        }


class MockServiceManager:
    """模擬服務管理器."""

    def __init__(self):
        self.mocks: dict[str, Any] = {}

    def create_repository_mock(self) -> AsyncMock:
        """創建模擬資料庫存取庫."""
        repository = AsyncMock()

        # 設置常用方法的預設回應
        repository.create_achievement = AsyncMock()
        repository.get_achievement_by_id = AsyncMock()
        repository.update_progress = AsyncMock()
        repository.get_user_achievements = AsyncMock(return_value=[])
        repository.get_user_progress = AsyncMock(return_value=None)

        self.mocks["repository"] = repository
        return repository

    def create_cache_manager_mock(self) -> AsyncMock:
        """創建模擬快取管理器."""
        cache_manager = AsyncMock()

        # 設置快取操作方法
        cache_manager.get = AsyncMock(return_value=None)
        cache_manager.set = AsyncMock()
        cache_manager.delete = AsyncMock()
        cache_manager.invalidate_pattern = AsyncMock()
        cache_manager.get_stats = AsyncMock(
            return_value={"hits": 0, "misses": 0, "hit_rate": 0.0, "size": 0}
        )

        self.mocks["cache_manager"] = cache_manager
        return cache_manager

    def create_performance_monitor_mock(self) -> AsyncMock:
        """創建模擬效能監控器."""
        monitor = AsyncMock()

        # 設置監控方法
        monitor.record_query_time = AsyncMock()
        monitor.record_cache_performance = AsyncMock()
        monitor.get_performance_metrics = AsyncMock(
            return_value={
                "avg_query_time": 50.0,
                "cache_hit_rate": 0.85,
                "memory_usage": 0.65,
            }
        )
        monitor.get_alerts = AsyncMock(return_value=[])

        self.mocks["performance_monitor"] = monitor
        return monitor

    def get_mock(self, name: str) -> Any:
        """獲取指定的模擬物件."""
        return self.mocks.get(name)

    def reset_all_mocks(self):
        """重置所有模擬物件."""
        for mock in self.mocks.values():
            if hasattr(mock, "reset_mock"):
                mock.reset_mock()


class TestDataGenerator:
    """測試資料生成器."""

    @staticmethod
    def generate_achievement_data(count: int = 1) -> list[dict[str, Any]]:
        """生成成就測試資料."""
        achievements = []

        categories = ["活動", "社交", "時間", "特殊"]
        types = ["counter", "milestone", "time_based"]

        for i in range(count):
            achievement = {
                "name": f"測試成就 {i + 1}",
                "description": f"這是第 {i + 1} 個測試成就",
                "category": categories[i % len(categories)],
                "type": types[i % len(types)],
                "criteria": {
                    "target_value": (i + 1) * 10,
                    "counter_field": "messages" if i % 2 == 0 else "interactions",
                },
                "points": (i + 1) * 100,
                "is_active": True,
            }
            achievements.append(achievement)

        return achievements

    @staticmethod
    def generate_user_data(count: int = 1) -> list[dict[str, Any]]:
        """生成用戶測試資料."""
        users = []

        for i in range(count):
            user = {
                "id": 100000000000000000 + i,
                "username": f"test_user_{i + 1}",
                "discriminator": f"{1000 + i:04d}",
                "bot": False,
                "display_name": f"測試用戶 {i + 1}",
            }
            users.append(user)

        return users

    @staticmethod
    def generate_progress_data(
        user_count: int = 5, achievement_count: int = 3
    ) -> list[dict[str, Any]]:
        """生成進度測試資料."""
        progress_records = []

        for user_i in range(user_count):
            user_id = 100000000000000000 + user_i

            for achievement_i in range(achievement_count):
                achievement_id = achievement_i + 1
                current_value = (user_i + 1) * (achievement_i + 1) * 10
                target_value = 100

                progress = {
                    "user_id": user_id,
                    "achievement_id": achievement_id,
                    "current_value": min(current_value, target_value),
                    "target_value": target_value,
                    "is_completed": current_value >= target_value,
                    "last_updated": datetime.now().isoformat(),
                }
                progress_records.append(progress)

        return progress_records


class TestReporter:
    """測試報告器."""

    def __init__(self, output_dir: Path | None = None):
        self.output_dir = output_dir or Path("test_reports")
        self.output_dir.mkdir(exist_ok=True)
        self.test_results: list[dict[str, Any]] = []
        self.performance_data: list[dict[str, Any]] = []

    def record_test_result(
        self,
        test_name: str,
        success: bool,
        execution_time: float,
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        """記錄測試結果."""
        result = {
            "test_name": test_name,
            "success": success,
            "execution_time": execution_time,
            "timestamp": datetime.now().isoformat(),
            "error": error,
            "metadata": metadata or {},
        }
        self.test_results.append(result)

    def record_performance_data(self, operation: str, metrics: dict[str, Any]):
        """記錄效能資料."""
        perf_data = {
            "operation": operation,
            "timestamp": datetime.now().isoformat(),
            **metrics,
        }
        self.performance_data.append(perf_data)

    def generate_summary_report(self) -> dict[str, Any]:
        """生成摘要報告."""
        total_tests = len(self.test_results)
        successful_tests = sum(1 for r in self.test_results if r["success"])
        failed_tests = total_tests - successful_tests

        if total_tests > 0:
            success_rate = successful_tests / total_tests
            avg_execution_time = (
                sum(r["execution_time"] for r in self.test_results) / total_tests
            )
        else:
            success_rate = 0.0
            avg_execution_time = 0.0

        summary = {
            "test_summary": {
                "total_tests": total_tests,
                "successful_tests": successful_tests,
                "failed_tests": failed_tests,
                "success_rate": success_rate,
                "average_execution_time": avg_execution_time,
            },
            "performance_summary": {
                "total_operations": len(self.performance_data),
                "operations": list(set(p["operation"] for p in self.performance_data)),
            },
            "generated_at": datetime.now().isoformat(),
        }

        return summary

    def save_reports(self):
        """保存報告到文件."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 保存測試結果
        test_results_file = self.output_dir / f"test_results_{timestamp}.json"
        with open(test_results_file, "w", encoding="utf-8") as f:
            json.dump(self.test_results, f, indent=2, ensure_ascii=False)

        # 保存效能資料
        performance_file = self.output_dir / f"performance_data_{timestamp}.json"
        with open(performance_file, "w", encoding="utf-8") as f:
            json.dump(self.performance_data, f, indent=2, ensure_ascii=False)

        # 保存摘要報告
        summary_file = self.output_dir / f"summary_report_{timestamp}.json"
        summary = self.generate_summary_report()
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        return {
            "test_results": test_results_file,
            "performance_data": performance_file,
            "summary_report": summary_file,
        }


class TestEnvironmentManager:
    """測試環境管理器."""

    def __init__(self):
        self.contexts: dict[str, TestContext] = {}
        self.db_manager = TestDatabaseManager()
        self.mock_manager = MockServiceManager()
        self.reporter = TestReporter()

    async def create_test_context(self, test_name: str) -> TestContext:
        """創建測試上下文."""
        context = TestContext(test_name=test_name)
        self.contexts[test_name] = context
        return context

    async def setup_achievement_test_environment(
        self,
        context: TestContext,
        with_cache: bool = True,
        with_performance_monitoring: bool = True,
    ) -> dict[str, Any]:
        """設置成就系統測試環境."""
        # 創建測試資料庫
        db_pool = await self.db_manager.create_test_database("achievement")
        await self.db_manager.setup_achievement_database(db_pool)

        context.database_pools.append(db_pool)

        # 創建服務模擬
        repository = self.mock_manager.create_repository_mock()
        services = {"repository": repository, "db_pool": db_pool}

        if with_cache:
            cache_manager = self.mock_manager.create_cache_manager_mock()
            services["cache_manager"] = cache_manager

        if with_performance_monitoring:
            performance_monitor = self.mock_manager.create_performance_monitor_mock()
            services["performance_monitor"] = performance_monitor

        return services

    async def cleanup_test_context(self, test_name: str):
        """清理測試上下文."""
        if test_name in self.contexts:
            context = self.contexts[test_name]
            await context.cleanup()
            del self.contexts[test_name]

    async def cleanup_all(self):
        """清理所有測試環境."""
        # 清理所有上下文
        for context in self.contexts.values():
            await context.cleanup()

        # 清理資料庫
        await self.db_manager.cleanup_all()

        # 重置模擬物件
        self.mock_manager.reset_all_mocks()

        self.contexts.clear()


# 全域測試環境管理器實例
test_env_manager = TestEnvironmentManager()


@pytest.fixture(scope="session")
def test_environment_manager():
    """測試環境管理器 fixture."""
    return test_env_manager


@pytest.fixture
async def test_context(request, test_environment_manager):
    """測試上下文 fixture."""
    test_name = request.node.name
    context = await test_environment_manager.create_test_context(test_name)

    yield context

    await test_environment_manager.cleanup_test_context(test_name)


@pytest.fixture
async def achievement_test_env(test_context, test_environment_manager):
    """成就系統測試環境 fixture."""
    services = await test_environment_manager.setup_achievement_test_environment(
        test_context, with_cache=True, with_performance_monitoring=True
    )

    yield services


# 測試裝飾器
def performance_test(
    max_execution_time: float = 5.0,
    max_memory_usage: float = 100.0,  # MB
):
    """效能測試裝飾器."""

    def decorator(func):
        async def wrapper(*args, **kwargs):
            async with PerformanceTestUtils.measure_execution_time(
                func.__name__
            ) as metrics:
                result = await func(*args, **kwargs)

            # 檢查效能指標
            if metrics["execution_time"] > max_execution_time:
                pytest.fail(
                    f"測試 {func.__name__} 執行時間過長: "
                    f"{metrics['execution_time']:.2f}s > {max_execution_time}s"
                )

            if metrics.get("memory_delta", 0) > max_memory_usage:
                pytest.fail(
                    f"測試 {func.__name__} 記憶體使用過多: "
                    f"{metrics['memory_delta']:.2f}MB > {max_memory_usage}MB"
                )

            return result

        return wrapper

    return decorator


def stress_test(
    concurrent_count: int = 10, iterations: int = 100, timeout: float = 30.0
):
    """壓力測試裝飾器."""

    def decorator(func):
        async def wrapper(*args, **kwargs):
            async def test_coroutine():
                return await func(*args, **kwargs)

            results = await PerformanceTestUtils.stress_test(
                test_coroutine,
                concurrent_count=concurrent_count,
                iterations_per_coroutine=iterations,
                max_execution_time=timeout,
            )

            if not results["success"]:
                pytest.fail(f"壓力測試失敗: {results['error']}")

            return results

        return wrapper

    return decorator
