"""
效能與負載測試引擎
Task ID: 10 - 建立系統整合測試

這個模組提供系統效能和負載測試功能：
- 並發操作測試
- 資料庫效能基準測試  
- 記憶體和資源使用監控
- 效能瓶頸識別
- 負載壓力測試

符合要求：
- F3: 建立效能和負載測試
- N1: 測試執行效率 - 完整測試套件執行時間<10分鐘
- 驗證系統在高負載下的穩定性和效能表現
"""

import pytest
import asyncio
import time
import statistics
import psutil
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any, Callable, Optional
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

from tests.test_infrastructure import performance_test, load_test


@dataclass
class PerformanceBenchmark:
    """效能基準定義"""
    operation_name: str
    max_duration_ms: float
    max_memory_mb: float
    min_throughput_ops_per_sec: float
    description: str


@dataclass
class LoadTestResult:
    """負載測試結果"""
    test_name: str
    concurrent_users: int
    operations_per_user: int
    total_operations: int
    successful_operations: int
    failed_operations: int
    success_rate: float
    avg_response_time_ms: float
    max_response_time_ms: float
    min_response_time_ms: float
    throughput_ops_per_sec: float
    memory_usage_mb: float
    duration_seconds: float


class PerformanceTestEngine:
    """效能測試引擎"""
    
    def __init__(self):
        self.benchmarks: Dict[str, PerformanceBenchmark] = {}
        self.results: List[Dict[str, Any]] = []
        self.setup_default_benchmarks()
    
    def setup_default_benchmarks(self):
        """設定預設效能基準"""
        # 資料庫操作基準
        self.benchmarks["database_query"] = PerformanceBenchmark(
            operation_name="資料庫查詢",
            max_duration_ms=100.0,
            max_memory_mb=50.0,
            min_throughput_ops_per_sec=100.0,
            description="單次資料庫查詢操作"
        )
        
        # 服務操作基準
        self.benchmarks["service_operation"] = PerformanceBenchmark(
            operation_name="服務操作",
            max_duration_ms=200.0,
            max_memory_mb=100.0,
            min_throughput_ops_per_sec=50.0,
            description="單次服務層操作"
        )
        
        # 跨系統操作基準
        self.benchmarks["cross_system"] = PerformanceBenchmark(
            operation_name="跨系統操作",
            max_duration_ms=500.0,
            max_memory_mb=150.0,
            min_throughput_ops_per_sec=20.0,
            description="跨系統整合操作"
        )
        
        # 並發操作基準
        self.benchmarks["concurrent_operation"] = PerformanceBenchmark(
            operation_name="並發操作",
            max_duration_ms=1000.0,
            max_memory_mb=200.0,
            min_throughput_ops_per_sec=100.0,
            description="高並發操作"
        )
    
    async def run_performance_test(
        self,
        test_func: Callable,
        benchmark_name: str,
        iterations: int = 100,
        **kwargs
    ) -> Dict[str, Any]:
        """執行效能測試"""
        if benchmark_name not in self.benchmarks:
            raise ValueError(f"未知的效能基準：{benchmark_name}")
        
        benchmark = self.benchmarks[benchmark_name]
        
        # 收集效能資料
        durations = []
        memory_usage = []
        errors = []
        
        initial_memory = self._get_memory_usage()
        start_time = time.time()
        
        for i in range(iterations):
            iteration_start = time.time()
            iteration_memory_start = self._get_memory_usage()
            
            try:
                await test_func(**kwargs)
                
                iteration_end = time.time()
                iteration_memory_end = self._get_memory_usage()
                
                duration_ms = (iteration_end - iteration_start) * 1000
                memory_delta = iteration_memory_end - iteration_memory_start
                
                durations.append(duration_ms)
                memory_usage.append(memory_delta)
                
            except Exception as e:
                errors.append(str(e))
        
        end_time = time.time()
        final_memory = self._get_memory_usage()
        
        # 計算統計資料
        if durations:
            avg_duration = statistics.mean(durations)
            p95_duration = statistics.quantiles(durations, n=20)[18]  # 95th percentile
            max_duration = max(durations)
            min_duration = min(durations)
            throughput = iterations / (end_time - start_time)
        else:
            avg_duration = p95_duration = max_duration = min_duration = 0
            throughput = 0
        
        avg_memory = statistics.mean(memory_usage) if memory_usage else 0
        total_memory_delta = final_memory - initial_memory
        
        # 建立測試結果
        result = {
            "test_name": f"performance_{benchmark_name}",
            "benchmark": benchmark_name,
            "iterations": iterations,
            "successful_operations": len(durations),
            "failed_operations": len(errors),
            "success_rate": len(durations) / iterations * 100,
            "avg_duration_ms": avg_duration,
            "p95_duration_ms": p95_duration,
            "max_duration_ms": max_duration,
            "min_duration_ms": min_duration,
            "throughput_ops_per_sec": throughput,
            "avg_memory_delta_mb": avg_memory,
            "total_memory_delta_mb": total_memory_delta,
            "errors": errors[:5],  # 只保留前5個錯誤
            "timestamp": datetime.now(),
            # 基準比較
            "meets_duration_benchmark": p95_duration <= benchmark.max_duration_ms,
            "meets_memory_benchmark": total_memory_delta <= benchmark.max_memory_mb,
            "meets_throughput_benchmark": throughput >= benchmark.min_throughput_ops_per_sec
        }
        
        self.results.append(result)
        return result
    
    def _get_memory_usage(self) -> float:
        """獲取當前記憶體使用量（MB）"""
        try:
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except:
            return 0.0
    
    def generate_performance_report(self) -> Dict[str, Any]:
        """生成效能測試報告"""
        if not self.results:
            return {"message": "沒有效能測試結果"}
        
        # 總體統計
        total_tests = len(self.results)
        successful_tests = len([r for r in self.results if r["success_rate"] > 95])
        
        # 基準達成率
        duration_passed = len([r for r in self.results if r["meets_duration_benchmark"]])
        memory_passed = len([r for r in self.results if r["meets_memory_benchmark"]])
        throughput_passed = len([r for r in self.results if r["meets_throughput_benchmark"]])
        
        return {
            "summary": {
                "total_tests": total_tests,
                "successful_tests": successful_tests,
                "success_rate": successful_tests / total_tests * 100,
                "duration_benchmark_pass_rate": duration_passed / total_tests * 100,
                "memory_benchmark_pass_rate": memory_passed / total_tests * 100,
                "throughput_benchmark_pass_rate": throughput_passed / total_tests * 100
            },
            "detailed_results": self.results,
            "recommendations": self._generate_recommendations()
        }
    
    def _generate_recommendations(self) -> List[str]:
        """生成效能優化建議"""
        recommendations = []
        
        # 分析效能瓶頸
        duration_failures = [r for r in self.results if not r["meets_duration_benchmark"]]
        memory_failures = [r for r in self.results if not r["meets_memory_benchmark"]]
        throughput_failures = [r for r in self.results if not r["meets_throughput_benchmark"]]
        
        if duration_failures:
            recommendations.append(
                f"有 {len(duration_failures)} 個測試未達到響應時間基準，建議優化演算法或資料庫查詢"
            )
        
        if memory_failures:
            recommendations.append(
                f"有 {len(memory_failures)} 個測試未達到記憶體使用基準，建議檢查記憶體洩漏或優化資料結構"
            )
        
        if throughput_failures:
            recommendations.append(
                f"有 {len(throughput_failures)} 個測試未達到吞吐量基準，建議優化並發處理或增加資源"
            )
        
        return recommendations


class LoadTestEngine:
    """負載測試引擎"""
    
    def __init__(self):
        self.test_results: List[LoadTestResult] = []
        
    async def run_load_test(
        self,
        test_func: Callable,
        test_name: str,
        concurrent_users: int = 10,
        operations_per_user: int = 5,
        ramp_up_time: float = 1.0,
        **kwargs
    ) -> LoadTestResult:
        """執行負載測試"""
        
        # 記錄開始狀態
        start_time = time.time()
        start_memory = self._get_memory_usage()
        
        # 建立任務
        tasks = []
        operation_results = []
        
        # 漸進式增加負載
        users_per_batch = max(1, concurrent_users // 10)
        batch_delay = ramp_up_time / 10
        
        for batch in range(0, concurrent_users, users_per_batch):
            batch_size = min(users_per_batch, concurrent_users - batch)
            
            for user_id in range(batch, batch + batch_size):
                for op_id in range(operations_per_user):
                    task = asyncio.create_task(
                        self._run_single_operation(
                            test_func,
                            user_id=user_id,
                            operation_id=op_id,
                            **kwargs
                        )
                    )
                    tasks.append(task)
            
            if batch_delay > 0:
                await asyncio.sleep(batch_delay)
        
        # 等待所有操作完成
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.time()
        end_memory = self._get_memory_usage()
        
        # 分析結果
        successful_ops = []
        failed_ops = []
        
        for result in results:
            if isinstance(result, Exception):
                failed_ops.append(result)
            else:
                successful_ops.append(result)
                operation_results.append(result)
        
        # 計算統計資料
        total_operations = len(tasks)
        successful_count = len(successful_ops)
        failed_count = len(failed_ops)
        success_rate = successful_count / total_operations * 100
        
        if operation_results:
            response_times = [op["duration_ms"] for op in operation_results]
            avg_response_time = statistics.mean(response_times)
            max_response_time = max(response_times)
            min_response_time = min(response_times)
        else:
            avg_response_time = max_response_time = min_response_time = 0
        
        duration_seconds = end_time - start_time
        throughput = successful_count / duration_seconds if duration_seconds > 0 else 0
        memory_usage = end_memory - start_memory
        
        # 建立測試結果
        load_result = LoadTestResult(
            test_name=test_name,
            concurrent_users=concurrent_users,
            operations_per_user=operations_per_user,
            total_operations=total_operations,
            successful_operations=successful_count,
            failed_operations=failed_count,
            success_rate=success_rate,
            avg_response_time_ms=avg_response_time,
            max_response_time_ms=max_response_time,
            min_response_time_ms=min_response_time,
            throughput_ops_per_sec=throughput,
            memory_usage_mb=memory_usage,
            duration_seconds=duration_seconds
        )
        
        self.test_results.append(load_result)
        return load_result
    
    async def _run_single_operation(self, test_func: Callable, user_id: int, operation_id: int, **kwargs):
        """執行單個負載測試操作"""
        start_time = time.time()
        
        try:
            result = await test_func(user_id=user_id, operation_id=operation_id, **kwargs)
            end_time = time.time()
            
            return {
                "user_id": user_id,
                "operation_id": operation_id,
                "duration_ms": (end_time - start_time) * 1000,
                "result": result,
                "success": True
            }
        except Exception as e:
            end_time = time.time()
            return {
                "user_id": user_id,
                "operation_id": operation_id,
                "duration_ms": (end_time - start_time) * 1000,
                "error": str(e),
                "success": False
            }
    
    def _get_memory_usage(self) -> float:
        """獲取當前記憶體使用量（MB）"""
        try:
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except:
            return 0.0
    
    def run_stress_test(
        self,
        test_func: Callable,
        max_concurrent_users: int = 100,
        increment: int = 10,
        duration_per_level: float = 30.0,
        **kwargs
    ) -> List[LoadTestResult]:
        """執行壓力測試（漸進式增加負載）"""
        stress_results = []
        
        for concurrent_users in range(increment, max_concurrent_users + 1, increment):
            print(f"壓力測試：{concurrent_users} 並發使用者")
            
            try:
                result = asyncio.run(self.run_load_test(
                    test_func=test_func,
                    test_name=f"stress_test_{concurrent_users}_users",
                    concurrent_users=concurrent_users,
                    operations_per_user=3,
                    ramp_up_time=duration_per_level * 0.2,
                    **kwargs
                ))
                
                stress_results.append(result)
                
                # 如果成功率太低，停止測試
                if result.success_rate < 80:
                    print(f"成功率降至 {result.success_rate:.1f}%，停止壓力測試")
                    break
                    
            except Exception as e:
                print(f"壓力測試在 {concurrent_users} 並發使用者時失敗：{e}")
                break
        
        return stress_results
    
    def generate_load_test_report(self) -> Dict[str, Any]:
        """生成負載測試報告"""
        if not self.test_results:
            return {"message": "沒有負載測試結果"}
        
        # 計算總體統計
        avg_success_rate = statistics.mean([r.success_rate for r in self.test_results])
        avg_throughput = statistics.mean([r.throughput_ops_per_sec for r in self.test_results])
        max_concurrent_users = max([r.concurrent_users for r in self.test_results])
        
        # 找出最佳表現的測試
        best_performance = max(self.test_results, key=lambda r: r.throughput_ops_per_sec)
        
        return {
            "summary": {
                "total_tests": len(self.test_results),
                "avg_success_rate": avg_success_rate,
                "avg_throughput_ops_per_sec": avg_throughput,
                "max_concurrent_users_tested": max_concurrent_users,
                "best_throughput_ops_per_sec": best_performance.throughput_ops_per_sec,
                "best_concurrent_users": best_performance.concurrent_users
            },
            "detailed_results": [
                {
                    "test_name": r.test_name,
                    "concurrent_users": r.concurrent_users,
                    "success_rate": r.success_rate,
                    "throughput_ops_per_sec": r.throughput_ops_per_sec,
                    "avg_response_time_ms": r.avg_response_time_ms
                }
                for r in self.test_results
            ],
            "recommendations": self._generate_load_recommendations()
        }
    
    def _generate_load_recommendations(self) -> List[str]:
        """生成負載測試建議"""
        recommendations = []
        
        if not self.test_results:
            return recommendations
        
        avg_success_rate = statistics.mean([r.success_rate for r in self.test_results])
        if avg_success_rate < 95:
            recommendations.append(f"平均成功率 {avg_success_rate:.1f}% 低於預期，建議優化錯誤處理和資源管理")
        
        high_load_tests = [r for r in self.test_results if r.concurrent_users >= 50]
        if high_load_tests:
            high_load_success = statistics.mean([r.success_rate for r in high_load_tests])
            if high_load_success < 90:
                recommendations.append("高負載下系統穩定性不足，建議增加伺服器資源或優化架構")
        
        response_times = [r.avg_response_time_ms for r in self.test_results]
        if response_times and max(response_times) > 1000:
            recommendations.append("部分測試響應時間超過1秒，建議優化效能瓶頸")
        
        return recommendations


# 測試用例類別
class TestPerformanceAndLoad:
    """效能和負載測試套件"""
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_database_performance(self, full_system_integration):
        """測試資料庫效能"""
        setup = full_system_integration
        db_manager = setup["db_manager"]
        perf_engine = PerformanceTestEngine()
        
        async def database_operation(**kwargs):
            """資料庫操作測試"""
            # 建立測試表
            await db_manager.execute("""
                CREATE TABLE IF NOT EXISTS perf_test (
                    id INTEGER PRIMARY KEY,
                    data TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 插入資料
            await db_manager.execute(
                "INSERT INTO perf_test (data) VALUES (?)",
                (f"test_data_{random.randint(1, 10000)}",)
            )
            
            # 查詢資料
            result = await db_manager.fetchone(
                "SELECT COUNT(*) as count FROM perf_test"
            )
            
            return result
        
        # 執行效能測試
        result = await perf_engine.run_performance_test(
            database_operation,
            "database_query",
            iterations=100
        )
        
        # 驗證效能基準
        assert result["meets_duration_benchmark"], f"資料庫操作平均耗時 {result['avg_duration_ms']:.2f}ms 超過基準"
        assert result["success_rate"] >= 99, f"資料庫操作成功率 {result['success_rate']:.1f}% 低於預期"
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_service_performance(self, full_system_integration):
        """測試服務層效能"""
        setup = full_system_integration
        economy_service = setup["services"]["economy"]
        perf_engine = PerformanceTestEngine()
        
        async def service_operation(**kwargs):
            """服務操作測試"""
            user_id = random.randint(100000, 999999)
            guild_id = 987654321
            
            # 建立使用者帳戶
            await economy_service.create_user_account(user_id, guild_id)
            
            # 新增貨幣
            await economy_service.add_currency(user_id, guild_id, 100, "效能測試")
            
            # 查詢餘額
            balance = await economy_service.get_user_balance(user_id, guild_id)
            
            return {"balance": balance}
        
        # 執行效能測試
        result = await perf_engine.run_performance_test(
            service_operation,
            "service_operation",
            iterations=50
        )
        
        # 驗證效能基準
        assert result["meets_duration_benchmark"], f"服務操作平均耗時 {result['avg_duration_ms']:.2f}ms 超過基準"
        assert result["success_rate"] >= 95, f"服務操作成功率 {result['success_rate']:.1f}% 低於預期"
    
    @pytest.mark.load
    @pytest.mark.asyncio
    async def test_concurrent_user_operations(self, full_system_integration):
        """測試並發使用者操作"""
        setup = full_system_integration
        economy_service = setup["services"]["economy"]
        load_engine = LoadTestEngine()
        
        async def user_operation(user_id: int, operation_id: int, **kwargs):
            """使用者操作測試"""
            guild_id = 987654321
            
            # 確保使用者帳戶存在
            try:
                await economy_service.get_user_balance(user_id, guild_id)
            except:
                await economy_service.create_user_account(user_id, guild_id)
            
            # 執行隨機操作
            operations = ["add_currency", "get_balance", "transfer"]
            operation = random.choice(operations)
            
            if operation == "add_currency":
                await economy_service.add_currency(
                    user_id, guild_id, random.randint(10, 100), f"負載測試 {operation_id}"
                )
            elif operation == "get_balance":
                await economy_service.get_user_balance(user_id, guild_id)
            elif operation == "transfer":
                # 轉移到另一個測試使用者
                target_user = random.randint(200000, 299999)
                try:
                    await economy_service.transfer_currency(
                        from_user_id=user_id,
                        to_user_id=target_user,
                        guild_id=guild_id,
                        amount=10,
                        description=f"負載測試轉移 {operation_id}"
                    )
                except:
                    # 轉移失敗是可以接受的（例如餘額不足）
                    pass
            
            return {"operation": operation, "user_id": user_id}
        
        # 執行負載測試
        result = await load_engine.run_load_test(
            user_operation,
            "concurrent_user_operations",
            concurrent_users=20,
            operations_per_user=5,
            ramp_up_time=2.0
        )
        
        # 驗證負載測試結果
        assert result.success_rate >= 90, f"並發操作成功率 {result.success_rate:.1f}% 低於預期"
        assert result.avg_response_time_ms < 1000, f"平均響應時間 {result.avg_response_time_ms:.2f}ms 過長"
        assert result.throughput_ops_per_sec >= 10, f"吞吐量 {result.throughput_ops_per_sec:.2f} ops/sec 過低"
    
    @pytest.mark.load
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_system_stress_limits(self, full_system_integration):
        """測試系統壓力極限"""
        setup = full_system_integration
        achievement_service = setup["services"]["achievement"]
        economy_service = setup["services"]["economy"]
        load_engine = LoadTestEngine()
        
        async def stress_operation(user_id: int, operation_id: int, **kwargs):
            """壓力測試操作"""
            guild_id = 987654321
            
            # 建立經濟帳戶
            try:
                await economy_service.create_user_account(user_id, guild_id)
            except:
                pass
            
            # 執行跨系統操作
            await economy_service.add_currency(user_id, guild_id, 50, f"壓力測試 {operation_id}")
            
            # 檢查成就觸發
            await achievement_service.check_and_award_achievement(
                user_id, guild_id, "MESSAGE_COUNT", 1
            )
            
            return {"user_id": user_id, "operation_id": operation_id}
        
        # 執行壓力測試（漸進式增加負載）
        stress_results = load_engine.run_stress_test(
            stress_operation,
            max_concurrent_users=50,
            increment=10,
            duration_per_level=15.0
        )
        
        # 分析壓力測試結果
        assert len(stress_results) > 0, "壓力測試沒有產生任何結果"
        
        # 找出系統極限
        max_successful_load = max([r for r in stress_results if r.success_rate >= 95], 
                                  key=lambda r: r.concurrent_users, default=None)
        
        if max_successful_load:
            print(f"系統可承受的最大負載：{max_successful_load.concurrent_users} 並發使用者")
            assert max_successful_load.concurrent_users >= 20, "系統承載能力過低"
        else:
            pytest.fail("系統無法承受任何有意義的負載")
    
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_memory_usage_monitoring(self, full_system_integration):
        """測試記憶體使用監控"""
        setup = full_system_integration
        perf_engine = PerformanceTestEngine()
        
        async def memory_intensive_operation(**kwargs):
            """記憶體密集操作測試"""
            # 建立大量資料結構
            large_data = []
            for i in range(1000):
                large_data.append({
                    "id": i,
                    "data": f"test_data_{i}" * 100,  # 大字串
                    "timestamp": datetime.now()
                })
            
            # 處理資料
            processed = [item for item in large_data if item["id"] % 2 == 0]
            
            return {"processed_count": len(processed)}
        
        # 執行記憶體測試
        result = await perf_engine.run_performance_test(
            memory_intensive_operation,
            "service_operation",  # 使用較寬鬆的基準
            iterations=10
        )
        
        # 檢查記憶體使用
        assert result["total_memory_delta_mb"] < 200, f"記憶體使用增長 {result['total_memory_delta_mb']:.2f}MB 過多"
        
        # 生成效能報告
        report = perf_engine.generate_performance_report()
        assert report["summary"]["success_rate"] >= 90, "整體效能測試成功率過低"