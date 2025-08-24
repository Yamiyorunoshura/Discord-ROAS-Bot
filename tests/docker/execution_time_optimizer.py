"""
跨平台 Docker 測試執行時間優化器
Task ID: T1 - Docker 測試框架建立 (執行效率優化專門化)

Ethan 效能專家的執行時間優化策略：
- 測試套件並行執行優化
- 容器啟動時間優化
- 測試流程精簡化
- 早期失敗偵測和快速回退
"""

import asyncio
import time
import threading
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Callable, Tuple
import logging
from dataclasses import dataclass
from enum import Enum
import queue
import multiprocessing as mp

logger = logging.getLogger(__name__)


class ExecutionStrategy(Enum):
    """執行策略"""
    SEQUENTIAL = "sequential"
    PARALLEL_THREADS = "parallel_threads"
    PARALLEL_PROCESSES = "parallel_processes"
    ADAPTIVE = "adaptive"


@dataclass
class ExecutionTimeTarget:
    """執行時間目標"""
    total_suite_seconds: float = 600  # 10 分鐘總目標
    single_test_seconds: float = 120   # 2 分鐘單測試目標
    container_startup_seconds: float = 30  # 30 秒容器啟動目標
    cleanup_seconds: float = 10        # 10 秒清理目標
    parallel_overhead_factor: float = 1.2  # 並行開銷係數


class ExecutionTimeOptimizer:
    """執行時間優化器
    
    實作多種並行執行策略來達成 10 分鐘內完成完整測試套件的目標
    """
    
    def __init__(self, target: ExecutionTimeTarget = None):
        self.target = target or ExecutionTimeTarget()
        self.execution_stats: List[Dict[str, Any]] = []
        
    def optimize_test_execution_plan(
        self, 
        test_functions: List[Callable],
        platform_count: int = 1,
        available_resources: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """優化測試執行計劃
        
        Args:
            test_functions: 要執行的測試函數列表
            platform_count: 平台數量
            available_resources: 可用資源信息
            
        Returns:
            優化後的執行計劃
        """
        if available_resources is None:
            available_resources = self._assess_available_resources()
        
        # 評估執行策略
        strategy = self._select_optimal_strategy(
            len(test_functions), 
            platform_count, 
            available_resources
        )
        
        # 計算最優並行度
        optimal_parallelism = self._calculate_optimal_parallelism(
            strategy, 
            available_resources
        )
        
        # 預估執行時間
        estimated_time = self._estimate_execution_time(
            len(test_functions),
            platform_count,
            strategy,
            optimal_parallelism
        )
        
        execution_plan = {
            "strategy": strategy,
            "parallelism_level": optimal_parallelism,
            "estimated_total_time_seconds": estimated_time,
            "target_compliance": estimated_time <= self.target.total_suite_seconds,
            "optimization_recommendations": self._generate_optimization_recommendations(
                estimated_time, strategy, optimal_parallelism
            ),
            "resource_allocation": {
                "max_memory_per_process": available_resources["memory_per_process"],
                "max_cpu_per_process": available_resources["cpu_per_process"],
                "max_concurrent_containers": optimal_parallelism
            }
        }
        
        logger.info(f"執行時間優化計劃: {strategy.value}, 並行度: {optimal_parallelism}, 預估時間: {estimated_time:.1f}s")
        
        return execution_plan
    
    def execute_optimized_test_suite(
        self,
        test_functions: List[Callable],
        execution_plan: Dict[str, Any],
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """執行優化後的測試套件"""
        context = context or {}
        strategy = ExecutionStrategy(execution_plan["strategy"])
        parallelism = execution_plan["parallelism_level"]
        
        start_time = time.time()
        
        try:
            if strategy == ExecutionStrategy.SEQUENTIAL:
                results = self._execute_sequential(test_functions, context)
            elif strategy == ExecutionStrategy.PARALLEL_THREADS:
                results = self._execute_parallel_threads(test_functions, parallelism, context)
            elif strategy == ExecutionStrategy.PARALLEL_PROCESSES:
                results = self._execute_parallel_processes(test_functions, parallelism, context)
            elif strategy == ExecutionStrategy.ADAPTIVE:
                results = self._execute_adaptive(test_functions, parallelism, context)
            else:
                raise ValueError(f"不支援的執行策略: {strategy}")
            
            total_time = time.time() - start_time
            
            # 記錄執行統計
            execution_stats = {
                "strategy_used": strategy.value,
                "parallelism_level": parallelism,
                "total_execution_time_seconds": total_time,
                "target_met": total_time <= self.target.total_suite_seconds,
                "performance_ratio": total_time / self.target.total_suite_seconds,
                "test_results": results,
                "optimization_effectiveness": self._evaluate_optimization_effectiveness(
                    total_time, results, execution_plan
                )
            }
            
            self.execution_stats.append(execution_stats)
            
            return execution_stats
            
        except Exception as e:
            logger.error(f"優化測試套件執行失敗: {e}")
            raise
    
    def _assess_available_resources(self) -> Dict[str, Any]:
        """評估可用資源"""
        try:
            import psutil
            
            memory_total_gb = psutil.virtual_memory().total / (1024**3)
            memory_available_gb = psutil.virtual_memory().available / (1024**3)
            cpu_count = psutil.cpu_count()
            cpu_usage = psutil.cpu_percent(interval=1)
            
            # 保守估算可用資源
            usable_memory_gb = min(memory_available_gb * 0.8, 2.0)  # 最多使用 2GB
            usable_cpu_percent = min(100 - cpu_usage, 80.0)  # 最多使用 80%
            
            return {
                "memory_total_gb": memory_total_gb,
                "memory_available_gb": memory_available_gb,
                "memory_usable_gb": usable_memory_gb,
                "cpu_count": cpu_count,
                "cpu_usage_percent": cpu_usage,
                "cpu_usable_percent": usable_cpu_percent,
                "memory_per_process": usable_memory_gb / 4,  # 假設最多 4 個並行進程
                "cpu_per_process": usable_cpu_percent / 4
            }
        except Exception as e:
            logger.warning(f"資源評估失敗，使用默認值: {e}")
            return {
                "memory_total_gb": 8.0,
                "memory_available_gb": 4.0,
                "memory_usable_gb": 2.0,
                "cpu_count": 4,
                "cpu_usage_percent": 20.0,
                "cpu_usable_percent": 60.0,
                "memory_per_process": 0.5,
                "cpu_per_process": 15.0
            }
    
    def _select_optimal_strategy(
        self, 
        test_count: int, 
        platform_count: int, 
        resources: Dict[str, Any]
    ) -> ExecutionStrategy:
        """選擇最優執行策略"""
        # 根據測試數量和資源情況選擇策略
        total_work_units = test_count * platform_count
        available_memory = resources["memory_usable_gb"]
        cpu_available = resources["cpu_usable_percent"]
        
        if total_work_units <= 2 or available_memory < 1.0:
            return ExecutionStrategy.SEQUENTIAL
        elif total_work_units <= 6 and available_memory >= 1.5 and cpu_available >= 50:
            return ExecutionStrategy.PARALLEL_THREADS
        elif total_work_units > 6 and available_memory >= 2.0 and cpu_available >= 60:
            return ExecutionStrategy.PARALLEL_PROCESSES
        else:
            return ExecutionStrategy.ADAPTIVE
    
    def _calculate_optimal_parallelism(
        self, 
        strategy: ExecutionStrategy, 
        resources: Dict[str, Any]
    ) -> int:
        """計算最優並行度"""
        if strategy == ExecutionStrategy.SEQUENTIAL:
            return 1
        
        # 基於記憶體限制計算
        memory_limited = int(resources["memory_usable_gb"] / 0.5)  # 每個進程 500MB
        
        # 基於 CPU 限制計算
        cpu_limited = max(1, int(resources["cpu_usable_percent"] / 20))  # 每個進程 20% CPU
        
        # 取較小值，但不超過 4
        optimal = min(memory_limited, cpu_limited, 4)
        
        return max(1, optimal)
    
    def _estimate_execution_time(
        self,
        test_count: int,
        platform_count: int,
        strategy: ExecutionStrategy,
        parallelism: int
    ) -> float:
        """預估執行時間"""
        # 基礎時間估算（每個測試在每個平台的預期時間）
        base_time_per_test = 45  # 秒
        total_work_time = test_count * platform_count * base_time_per_test
        
        if strategy == ExecutionStrategy.SEQUENTIAL:
            return total_work_time
        else:
            # 並行執行時間 = 總工作時間 / 並行度 * 開銷係數
            parallel_time = (total_work_time / parallelism) * self.target.parallel_overhead_factor
            return parallel_time
    
    def _execute_sequential(
        self, 
        test_functions: List[Callable], 
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """順序執行測試"""
        results = []
        for i, test_func in enumerate(test_functions):
            start_time = time.time()
            try:
                result = test_func(**context)
                success = True
                error = None
            except Exception as e:
                result = None
                success = False
                error = str(e)
            
            execution_time = time.time() - start_time
            results.append({
                "test_index": i,
                "test_name": getattr(test_func, '__name__', f'test_{i}'),
                "success": success,
                "execution_time_seconds": execution_time,
                "result": result,
                "error": error
            })
            
            logger.info(f"完成測試 {i+1}/{len(test_functions)}: {execution_time:.2f}s")
        
        return results
    
    def _execute_parallel_threads(
        self,
        test_functions: List[Callable],
        parallelism: int,
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """並行執行測試（多執行緒）"""
        results = []
        
        with ThreadPoolExecutor(max_workers=parallelism, thread_name_prefix="test-worker") as executor:
            future_to_test = {}
            
            for i, test_func in enumerate(test_functions):
                future = executor.submit(self._execute_single_test, i, test_func, context)
                future_to_test[future] = (i, test_func)
            
            for future in as_completed(future_to_test):
                test_index, test_func = future_to_test[future]
                try:
                    result = future.result(timeout=self.target.single_test_seconds)
                    results.append(result)
                    logger.info(f"完成並行測試 {test_index}: {result['execution_time_seconds']:.2f}s")
                except Exception as e:
                    logger.error(f"並行測試 {test_index} 失敗: {e}")
                    results.append({
                        "test_index": test_index,
                        "test_name": getattr(test_func, '__name__', f'test_{test_index}'),
                        "success": False,
                        "execution_time_seconds": 0,
                        "result": None,
                        "error": str(e)
                    })
        
        # 按原始順序排序結果
        results.sort(key=lambda x: x["test_index"])
        return results
    
    def _execute_parallel_processes(
        self,
        test_functions: List[Callable],
        parallelism: int,
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """並行執行測試（多進程）"""
        # 注意：多進程執行需要特殊處理，因為 Docker 客戶端不能跨進程共享
        # 這裡提供基本框架，實際使用時需要重新設計 Docker 客戶端初始化
        logger.warning("多進程執行需要特殊的 Docker 客戶端處理，回退到多執行緒執行")
        return self._execute_parallel_threads(test_functions, parallelism, context)
    
    def _execute_adaptive(
        self,
        test_functions: List[Callable],
        parallelism: int,
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """自適應執行測試"""
        # 動態調整並行度基於系統負載
        initial_parallelism = max(1, parallelism // 2)  # 開始時使用較低的並行度
        
        logger.info(f"自適應執行開始，初始並行度: {initial_parallelism}")
        
        # 分批執行測試
        batch_size = max(2, len(test_functions) // 3)
        results = []
        
        for batch_start in range(0, len(test_functions), batch_size):
            batch_end = min(batch_start + batch_size, len(test_functions))
            batch_tests = test_functions[batch_start:batch_end]
            
            batch_start_time = time.time()
            
            # 檢查系統負載並調整並行度
            current_parallelism = self._adjust_parallelism_based_on_load(initial_parallelism)
            
            logger.info(f"執行批次 {batch_start//batch_size + 1}，並行度: {current_parallelism}")
            
            batch_results = self._execute_parallel_threads(batch_tests, current_parallelism, context)
            
            # 調整測試索引
            for result in batch_results:
                result["test_index"] += batch_start
            
            results.extend(batch_results)
            
            batch_time = time.time() - batch_start_time
            logger.info(f"批次完成，耗時: {batch_time:.2f}s")
        
        return results
    
    def _execute_single_test(
        self, 
        test_index: int, 
        test_func: Callable, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """執行單一測試"""
        start_time = time.time()
        try:
            result = test_func(**context)
            success = True
            error = None
        except Exception as e:
            result = None
            success = False
            error = str(e)
        
        execution_time = time.time() - start_time
        
        return {
            "test_index": test_index,
            "test_name": getattr(test_func, '__name__', f'test_{test_index}'),
            "success": success,
            "execution_time_seconds": execution_time,
            "result": result,
            "error": error
        }
    
    def _adjust_parallelism_based_on_load(self, current_parallelism: int) -> int:
        """基於系統負載調整並行度"""
        try:
            import psutil
            cpu_usage = psutil.cpu_percent(interval=0.1)
            memory_usage = psutil.virtual_memory().percent
            
            # 如果系統負載過高，降低並行度
            if cpu_usage > 80 or memory_usage > 85:
                return max(1, current_parallelism - 1)
            elif cpu_usage < 50 and memory_usage < 60:
                return min(4, current_parallelism + 1)
            else:
                return current_parallelism
        except:
            return current_parallelism
    
    def _generate_optimization_recommendations(
        self, 
        estimated_time: float, 
        strategy: ExecutionStrategy, 
        parallelism: int
    ) -> List[str]:
        """生成優化建議"""
        recommendations = []
        
        if estimated_time > self.target.total_suite_seconds:
            recommendations.append(f"預估執行時間 {estimated_time:.1f}s 超過目標 {self.target.total_suite_seconds}s")
            
            if strategy == ExecutionStrategy.SEQUENTIAL:
                recommendations.append("考慮啟用並行執行以提高速度")
            elif parallelism < 4:
                recommendations.append("考慮增加並行度以提高執行效率")
                
        if strategy in [ExecutionStrategy.PARALLEL_PROCESSES, ExecutionStrategy.PARALLEL_THREADS]:
            recommendations.append("監控系統資源使用，避免過載")
            
        if estimated_time < self.target.total_suite_seconds * 0.5:
            recommendations.append("執行時間充裕，可以考慮增加更多測試覆蓋")
        
        return recommendations or ["執行計劃符合效能目標"]
    
    def _evaluate_optimization_effectiveness(
        self,
        actual_time: float,
        results: List[Dict[str, Any]],
        execution_plan: Dict[str, Any]
    ) -> Dict[str, Any]:
        """評估優化效果"""
        estimated_time = execution_plan["estimated_total_time_seconds"]
        success_count = sum(1 for r in results if r["success"])
        
        return {
            "time_estimation_accuracy": abs(actual_time - estimated_time) / estimated_time,
            "target_achievement": actual_time <= self.target.total_suite_seconds,
            "success_rate_percent": (success_count / len(results)) * 100 if results else 0,
            "average_test_time_seconds": sum(r["execution_time_seconds"] for r in results) / len(results) if results else 0,
            "optimization_gain_percent": ((self.target.total_suite_seconds - actual_time) / self.target.total_suite_seconds) * 100,
            "recommendations": [
                f"實際執行時間 {actual_time:.1f}s vs 預估 {estimated_time:.1f}s",
                f"成功率: {success_count}/{len(results)} ({(success_count/len(results)*100):.1f}%)" if results else "無測試結果"
            ]
        }
    
    def generate_execution_time_report(self) -> Dict[str, Any]:
        """生成執行時間分析報告"""
        if not self.execution_stats:
            return {"error": "沒有執行統計數據"}
        
        # 分析所有執行記錄
        total_executions = len(self.execution_stats)
        successful_executions = sum(1 for s in self.execution_stats if s.get("target_met", False))
        
        execution_times = [s["total_execution_time_seconds"] for s in self.execution_stats]
        avg_execution_time = sum(execution_times) / len(execution_times)
        
        return {
            "report_metadata": {
                "total_executions": total_executions,
                "successful_executions": successful_executions,
                "success_rate_percent": (successful_executions / total_executions) * 100,
                "target_time_seconds": self.target.total_suite_seconds
            },
            "performance_analysis": {
                "average_execution_time_seconds": avg_execution_time,
                "best_execution_time_seconds": min(execution_times),
                "worst_execution_time_seconds": max(execution_times),
                "target_compliance_rate_percent": (successful_executions / total_executions) * 100
            },
            "strategy_effectiveness": self._analyze_strategy_effectiveness(),
            "optimization_trends": self._analyze_optimization_trends(),
            "recommendations": self._generate_execution_time_recommendations()
        }
    
    def _analyze_strategy_effectiveness(self) -> Dict[str, Any]:
        """分析不同策略的效果"""
        strategy_stats = {}
        
        for stat in self.execution_stats:
            strategy = stat["strategy_used"]
            if strategy not in strategy_stats:
                strategy_stats[strategy] = []
            strategy_stats[strategy].append(stat["total_execution_time_seconds"])
        
        effectiveness = {}
        for strategy, times in strategy_stats.items():
            effectiveness[strategy] = {
                "average_time_seconds": sum(times) / len(times),
                "best_time_seconds": min(times),
                "execution_count": len(times)
            }
        
        return effectiveness
    
    def _analyze_optimization_trends(self) -> List[str]:
        """分析優化趨勢"""
        if len(self.execution_stats) < 2:
            return ["需要更多執行數據來分析趨勢"]
        
        trends = []
        recent_stats = self.execution_stats[-3:]  # 最近 3 次執行
        
        times = [s["total_execution_time_seconds"] for s in recent_stats]
        if len(set(times)) > 1:
            if times[-1] < times[0]:
                trends.append("執行時間呈改善趨勢")
            else:
                trends.append("執行時間需要進一步優化")
        
        return trends
    
    def _generate_execution_time_recommendations(self) -> List[str]:
        """生成執行時間優化建議"""
        if not self.execution_stats:
            return ["需要執行數據來生成建議"]
        
        recommendations = []
        latest = self.execution_stats[-1]
        
        if not latest.get("target_met", False):
            recommendations.append(f"最近執行未達成時間目標，考慮進一步優化並行策略")
        
        if latest["parallelism_level"] == 1:
            recommendations.append("考慮啟用並行執行以提高效率")
        
        optimization_effectiveness = latest.get("optimization_effectiveness", {})
        success_rate = optimization_effectiveness.get("success_rate_percent", 0)
        
        if success_rate < 95:
            recommendations.append(f"測試成功率 {success_rate:.1f}% 需要改善")
        
        return recommendations or ["執行時間優化表現良好"]