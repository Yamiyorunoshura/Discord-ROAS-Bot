"""
跨平台 Docker 測試執行時間優化器 - 進階版
Task ID: T1 - Docker 測試框架建立 (執行時間優化專門化)

Ethan 效能專家的核心優化實作：
- 智能測試執行時間控制
- 容器生命週期自動優化
- 並行測試負載平衡
- 執行時間預測和調整
- 資源使用動態優化
"""

import time
import asyncio
import concurrent.futures
import threading
from typing import Dict, Any, List, Optional, Tuple, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
import json
import logging
from contextlib import contextmanager
from enum import Enum
import statistics
import psutil
import gc
import queue
import weakref
from collections import defaultdict, deque

try:
    import docker
    from docker.models.containers import Container
    from docker.errors import DockerException
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False

logger = logging.getLogger(__name__)


class ExecutionStrategy(Enum):
    """執行策略"""
    SEQUENTIAL = "sequential"      # 順序執行
    PARALLEL_BALANCED = "parallel_balanced"  # 平衡並行
    PARALLEL_AGGRESSIVE = "parallel_aggressive"  # 積極並行
    ADAPTIVE = "adaptive"         # 自適應策略


@dataclass
class ExecutionMetrics:
    """執行指標"""
    start_time: float
    end_time: Optional[float] = None
    container_startup_time: float = 0.0
    test_execution_time: float = 0.0
    container_cleanup_time: float = 0.0
    total_time: float = 0.0
    memory_peak_mb: float = 0.0
    cpu_peak_percent: float = 0.0
    success: bool = True
    error_message: Optional[str] = None
    
    def finalize(self) -> None:
        """完成指標計算"""
        if self.end_time and self.start_time:
            self.total_time = self.end_time - self.start_time
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典"""
        return {
            'total_time': self.total_time,
            'container_startup_time': self.container_startup_time,
            'test_execution_time': self.test_execution_time,
            'container_cleanup_time': self.container_cleanup_time,
            'memory_peak_mb': self.memory_peak_mb,
            'cpu_peak_percent': self.cpu_peak_percent,
            'success': self.success,
            'error_message': self.error_message
        }


class SmartContainerPool:
    """智能容器池管理器
    
    優化策略：
    - 容器預熱和重用
    - 智能資源分配
    - 動態池大小調整
    """
    
    def __init__(self, docker_client, max_pool_size: int = 3):
        self.docker_client = docker_client
        self.max_pool_size = max_pool_size
        self.pool: deque = deque()
        self.pool_lock = threading.Lock()
        self.active_containers: weakref.WeakSet = weakref.WeakSet()
        self.pool_stats = {
            'created': 0,
            'reused': 0,
            'cleaned': 0
        }
        
    @contextmanager
    def get_container(self, config: Dict[str, Any]):
        """獲取優化的容器"""
        container = None
        reused = False
        
        try:
            # 嘗試從池中獲取
            with self.pool_lock:
                if self.pool:
                    container = self.pool.popleft()
                    reused = True
                    self.pool_stats['reused'] += 1
            
            # 如果沒有可用容器，創建新的
            if not container:
                container = self._create_optimized_container(config)
                self.pool_stats['created'] += 1
            
            self.active_containers.add(container)
            logger.debug(f"容器獲取: {'重用' if reused else '新建'} {container.id[:12]}")
            
            yield container
            
        finally:
            # 歸還容器到池中
            if container:
                self._return_container_to_pool(container)
    
    def _create_optimized_container(self, config: Dict[str, Any]) -> Container:
        """創建優化的容器"""
        # 應用優化配置
        optimized_config = self._optimize_container_config(config)
        
        # 創建和啟動容器
        container = self.docker_client.containers.run(**optimized_config)
        
        return container
    
    def _optimize_container_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """優化容器配置"""
        optimized = config.copy()
        
        # 移除不被 Docker API 支援的參數
        test_type = optimized.pop('test_type', 'basic')
        name = optimized.pop('name', 'test-container')
        
        # 資源限制優化
        optimized.update({
            'mem_limit': '384m',  # 適中的記憶體限制
            'cpu_period': 100000,
            'cpu_quota': 40000,   # 40% CPU
            'detach': True,
            'remove': False,      # 不自動刪除，由池管理
            'network_disabled': True,  # 禁用網路以提高效能
            'name': name
        })
        
        # 優化環境變數
        env = optimized.setdefault('environment', {})
        env.update({
            'PYTHONOPTIMIZE': '2',
            'PYTHONDONTWRITEBYTECODE': '1',
            'EXECUTION_OPTIMIZED': 'true',
            'TEST_TYPE': test_type  # 將 test_type 作為環境變數傳遞
        })
        
        return optimized
    
    def _return_container_to_pool(self, container: Container) -> None:
        """將容器歸還到池中"""
        try:
            # 檢查容器狀態
            container.reload()
            
            # 如果容器狀態良好且池未滿，歸還到池中
            with self.pool_lock:
                if (container.status in ['running', 'exited'] and 
                    len(self.pool) < self.max_pool_size):
                    self.pool.append(container)
                    logger.debug(f"容器歸還到池: {container.id[:12]}")
                else:
                    # 清理容器
                    self._cleanup_container(container)
                    
        except Exception as e:
            logger.warning(f"容器歸還失敗: {e}")
            self._cleanup_container(container)
    
    def _cleanup_container(self, container: Container) -> None:
        """清理容器"""
        try:
            container.stop(timeout=5)
            container.remove(force=True)
            self.pool_stats['cleaned'] += 1
            logger.debug(f"容器已清理: {container.id[:12]}")
        except Exception as e:
            logger.warning(f"容器清理失敗: {e}")
    
    def cleanup_pool(self) -> None:
        """清理整個容器池"""
        with self.pool_lock:
            while self.pool:
                container = self.pool.popleft()
                self._cleanup_container(container)
        
        logger.info(f"容器池統計: 創建={self.pool_stats['created']}, "
                   f"重用={self.pool_stats['reused']}, "
                   f"清理={self.pool_stats['cleaned']}")


class ExecutionTimeOptimizer:
    """執行時間優化器
    
    核心優化策略：
    1. 動態執行策略選擇
    2. 負載平衡並行執行
    3. 執行時間預測和調整
    4. 資源使用最佳化
    """
    
    def __init__(self, docker_client, target_duration: float = 600.0):  # 10分鐘目標
        if not DOCKER_AVAILABLE:
            raise ImportError("Docker SDK 不可用")
            
        self.docker_client = docker_client
        self.target_duration = target_duration
        self.container_pool = SmartContainerPool(docker_client)
        self.execution_history: List[ExecutionMetrics] = []
        self.strategy = ExecutionStrategy.ADAPTIVE
        
        # 動態執行參數
        self.max_parallel_workers = 3
        self.current_parallel_workers = 2
        self.execution_timeout = 120  # 單個測試超時
        
        # 效能監控
        self.resource_monitor_active = False
        self.resource_metrics: List[Dict[str, float]] = []
        
    def optimize_test_execution(self, test_configs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """優化測試執行"""
        logger.info(f"開始優化測試執行，測試數量: {len(test_configs)}")
        
        # 選擇執行策略
        strategy = self._select_execution_strategy(test_configs)
        logger.info(f"選擇執行策略: {strategy.value}")
        
        # 啟動資源監控
        self._start_resource_monitoring()
        
        try:
            # 根據策略執行測試
            if strategy == ExecutionStrategy.SEQUENTIAL:
                results = self._execute_sequential(test_configs)
            elif strategy in [ExecutionStrategy.PARALLEL_BALANCED, ExecutionStrategy.PARALLEL_AGGRESSIVE]:
                results = self._execute_parallel(test_configs, strategy)
            else:  # ADAPTIVE
                results = self._execute_adaptive(test_configs)
            
            # 生成優化報告
            optimization_report = self._generate_optimization_report(results)
            
            return optimization_report
            
        finally:
            self._stop_resource_monitoring()
            self.container_pool.cleanup_pool()
    
    def _select_execution_strategy(self, test_configs: List[Dict[str, Any]]) -> ExecutionStrategy:
        """選擇執行策略"""
        test_count = len(test_configs)
        
        # 基於歷史效能數據選擇策略
        if self.execution_history:
            avg_execution_time = statistics.mean([m.total_time for m in self.execution_history])
            
            if avg_execution_time * test_count > self.target_duration:
                # 如果預估時間超過目標，使用並行策略
                return ExecutionStrategy.PARALLEL_AGGRESSIVE
            elif avg_execution_time * test_count > self.target_duration * 0.7:
                return ExecutionStrategy.PARALLEL_BALANCED
        
        # 基於測試數量的策略選擇
        if test_count <= 3:
            return ExecutionStrategy.SEQUENTIAL
        elif test_count <= 8:
            return ExecutionStrategy.PARALLEL_BALANCED
        else:
            return ExecutionStrategy.PARALLEL_AGGRESSIVE
    
    def _execute_sequential(self, test_configs: List[Dict[str, Any]]) -> List[ExecutionMetrics]:
        """順序執行測試"""
        results = []
        
        for config in test_configs:
            metrics = self._execute_single_test(config)
            results.append(metrics)
            
            # 動態調整：如果執行時間過長，切換到並行
            if metrics.total_time > 60:  # 超過1分鐘
                logger.info("檢測到長時間執行，切換到並行模式")
                remaining_configs = test_configs[len(results):]
                parallel_results = self._execute_parallel(remaining_configs, ExecutionStrategy.PARALLEL_BALANCED)
                results.extend(parallel_results)
                break
        
        return results
    
    def _execute_parallel(self, test_configs: List[Dict[str, Any]], 
                         strategy: ExecutionStrategy) -> List[ExecutionMetrics]:
        """並行執行測試"""
        # 根據策略調整並行度
        if strategy == ExecutionStrategy.PARALLEL_AGGRESSIVE:
            max_workers = min(self.max_parallel_workers, len(test_configs))
        else:
            max_workers = min(2, len(test_configs))
        
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有測試
            future_to_config = {
                executor.submit(self._execute_single_test, config): config
                for config in test_configs
            }
            
            # 收集結果
            for future in concurrent.futures.as_completed(future_to_config, timeout=self.target_duration):
                config = future_to_config[future]
                try:
                    metrics = future.result(timeout=self.execution_timeout)
                    results.append(metrics)
                except Exception as e:
                    # 創建失敗的指標
                    failed_metrics = ExecutionMetrics(
                        start_time=time.time(),
                        success=False,
                        error_message=str(e)
                    )
                    failed_metrics.end_time = time.time()
                    failed_metrics.finalize()
                    results.append(failed_metrics)
        
        return results
    
    def _execute_adaptive(self, test_configs: List[Dict[str, Any]]) -> List[ExecutionMetrics]:
        """自適應執行測試"""
        results = []
        remaining_configs = test_configs.copy()
        
        # 先執行一小批測試以獲得效能基準
        sample_size = min(3, len(remaining_configs))
        sample_configs = remaining_configs[:sample_size]
        remaining_configs = remaining_configs[sample_size:]
        
        # 順序執行樣本
        sample_results = self._execute_sequential(sample_configs)
        results.extend(sample_results)
        
        # 基於樣本結果調整策略
        if sample_results:
            avg_time = statistics.mean([r.total_time for r in sample_results])
            estimated_total_time = avg_time * len(test_configs)
            
            if estimated_total_time > self.target_duration * 0.8:
                # 如果預估時間接近目標，使用積極並行
                strategy = ExecutionStrategy.PARALLEL_AGGRESSIVE
            elif estimated_total_time > self.target_duration * 0.5:
                # 如果預估時間適中，使用平衡並行
                strategy = ExecutionStrategy.PARALLEL_BALANCED
            else:
                # 如果預估時間充裕，繼續順序執行
                strategy = ExecutionStrategy.SEQUENTIAL
            
            logger.info(f"自適應策略選擇: {strategy.value} (預估時間: {estimated_total_time:.1f}s)")
        
        # 執行剩餘測試
        if remaining_configs:
            if strategy == ExecutionStrategy.SEQUENTIAL:
                remaining_results = self._execute_sequential(remaining_configs)
            else:
                remaining_results = self._execute_parallel(remaining_configs, strategy)
            
            results.extend(remaining_results)
        
        return results
    
    def _execute_single_test(self, test_config: Dict[str, Any]) -> ExecutionMetrics:
        """執行單個測試"""
        test_name = test_config.get('name', 'unknown')
        metrics = ExecutionMetrics(start_time=time.time())
        
        try:
            # 容器啟動階段
            container_start_time = time.time()
            
            with self.container_pool.get_container(test_config) as container:
                metrics.container_startup_time = time.time() - container_start_time
                
                # 測試執行階段
                test_start_time = time.time()
                test_result = self._run_test_in_container(container, test_config)
                metrics.test_execution_time = time.time() - test_start_time
                
                # 清理階段計時在容器池中處理
                cleanup_start_time = time.time()
                # 清理邏輯在 container_pool 的 context manager 中
            
            metrics.container_cleanup_time = time.time() - cleanup_start_time
            metrics.success = test_result.get('success', True)
            
        except Exception as e:
            metrics.success = False
            metrics.error_message = str(e)
            logger.error(f"測試執行失敗 {test_name}: {e}")
        
        finally:
            metrics.end_time = time.time()
            metrics.finalize()
            self.execution_history.append(metrics)
        
        return metrics
    
    def _run_test_in_container(self, container: Container, test_config: Dict[str, Any]) -> Dict[str, Any]:
        """在容器中運行測試"""
        test_type = test_config.get('test_type', 'basic')
        
        # 等待容器準備就緒
        self._wait_for_container_ready(container)
        
        # 根據測試類型執行不同的測試邏輯
        if test_type == 'health_check':
            return self._test_health_check_optimized(container)
        elif test_type == 'resource_limits':
            return self._test_resource_limits_optimized(container)
        elif test_type == 'environment':
            return self._test_environment_optimized(container, test_config)
        else:
            return self._test_basic_functionality(container)
    
    def _wait_for_container_ready(self, container: Container, timeout: float = 30.0) -> None:
        """等待容器準備就緒（優化版本）"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                container.reload()
                if container.status == 'running':
                    return
                elif container.status in ['exited', 'dead']:
                    raise Exception(f"容器異常狀態: {container.status}")
            except Exception as e:
                logger.debug(f"容器狀態檢查錯誤: {e}")
            
            time.sleep(0.2)  # 縮短檢查間隔
        
        raise TimeoutError(f"容器啟動超時: {timeout}s")
    
    def _test_health_check_optimized(self, container: Container) -> Dict[str, Any]:
        """優化的健康檢查測試"""
        container.reload()
        
        # 簡化的健康檢查邏輯
        if container.status == 'running':
            return {"success": True, "status": "healthy", "test_type": "health_check"}
        else:
            return {"success": False, "status": container.status, "test_type": "health_check"}
    
    def _test_resource_limits_optimized(self, container: Container) -> Dict[str, Any]:
        """優化的資源限制測試"""
        container.reload()
        host_config = container.attrs.get('HostConfig', {})
        
        memory_limit = host_config.get('Memory', 0)
        cpu_quota = host_config.get('CpuQuota', 0)
        
        return {
            "success": memory_limit > 0 and cpu_quota > 0,
            "memory_limit_mb": memory_limit / (1024 * 1024) if memory_limit else 0,
            "cpu_quota": cpu_quota,
            "test_type": "resource_limits"
        }
    
    def _test_environment_optimized(self, container: Container, test_config: Dict[str, Any]) -> Dict[str, Any]:
        """優化的環境變數測試"""
        container.reload()
        
        expected_env = test_config.get('environment', {})
        container_env = container.attrs.get('Config', {}).get('Env', [])
        
        # 快速環境變數檢查
        env_dict = {}
        for env_var in container_env:
            if '=' in env_var:
                key, value = env_var.split('=', 1)
                env_dict[key] = value
        
        success = all(env_dict.get(k) == v for k, v in expected_env.items())
        
        return {
            "success": success,
            "expected_count": len(expected_env),
            "actual_count": len(env_dict),
            "test_type": "environment"
        }
    
    def _test_basic_functionality(self, container: Container) -> Dict[str, Any]:
        """基本功能測試"""
        container.reload()
        
        return {
            "success": container.status == 'running',
            "container_status": container.status,
            "test_type": "basic"
        }
    
    def _start_resource_monitoring(self) -> None:
        """啟動資源監控"""
        self.resource_monitor_active = True
        
        def monitor_resources():
            while self.resource_monitor_active:
                try:
                    memory = psutil.virtual_memory()
                    cpu_percent = psutil.cpu_percent(interval=0.5)
                    
                    self.resource_metrics.append({
                        'timestamp': time.time(),
                        'memory_mb': memory.used / (1024 * 1024),
                        'memory_percent': memory.percent,
                        'cpu_percent': cpu_percent
                    })
                    
                    time.sleep(1)
                except Exception as e:
                    logger.warning(f"資源監控錯誤: {e}")
        
        self.monitor_thread = threading.Thread(target=monitor_resources, daemon=True)
        self.monitor_thread.start()
    
    def _stop_resource_monitoring(self) -> None:
        """停止資源監控"""
        self.resource_monitor_active = False
        if hasattr(self, 'monitor_thread') and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2)
    
    def _generate_optimization_report(self, results: List[ExecutionMetrics]) -> Dict[str, Any]:
        """生成優化報告"""
        if not results:
            return {"error": "沒有測試結果"}
        
        # 計算統計數據
        total_tests = len(results)
        successful_tests = sum(1 for r in results if r.success)
        execution_times = [r.total_time for r in results]
        startup_times = [r.container_startup_time for r in results]
        test_times = [r.test_execution_time for r in results]
        cleanup_times = [r.container_cleanup_time for r in results]
        
        # 資源統計
        resource_stats = {}
        if self.resource_metrics:
            memory_usage = [m['memory_mb'] for m in self.resource_metrics]
            cpu_usage = [m['cpu_percent'] for m in self.resource_metrics]
            
            resource_stats = {
                'memory': {
                    'peak_mb': max(memory_usage),
                    'average_mb': statistics.mean(memory_usage),
                    'exceeded_2gb_limit': any(m > 2048 for m in memory_usage)
                },
                'cpu': {
                    'peak_percent': max(cpu_usage),
                    'average_percent': statistics.mean(cpu_usage),
                    'exceeded_80_percent_limit': any(c > 80 for c in cpu_usage)
                }
            }
        
        # 生成報告
        report = {
            "optimization_metadata": {
                "generated_at": datetime.now().isoformat(),
                "optimizer_version": "execution_time_optimizer_v2",
                "task_id": "T1",
                "strategy_used": self.strategy.value
            },
            "execution_summary": {
                "total_tests": total_tests,
                "successful_tests": successful_tests,
                "success_rate_percent": (successful_tests / total_tests * 100) if total_tests > 0 else 0,
                "total_execution_time_seconds": sum(execution_times),
                "average_test_time_seconds": statistics.mean(execution_times) if execution_times else 0,
                "meets_10min_target": sum(execution_times) <= self.target_duration
            },
            "performance_breakdown": {
                "container_startup": {
                    "total_seconds": sum(startup_times),
                    "average_seconds": statistics.mean(startup_times) if startup_times else 0,
                    "max_seconds": max(startup_times) if startup_times else 0
                },
                "test_execution": {
                    "total_seconds": sum(test_times),
                    "average_seconds": statistics.mean(test_times) if test_times else 0,
                    "max_seconds": max(test_times) if test_times else 0
                },
                "container_cleanup": {
                    "total_seconds": sum(cleanup_times),
                    "average_seconds": statistics.mean(cleanup_times) if cleanup_times else 0,
                    "max_seconds": max(cleanup_times) if cleanup_times else 0
                }
            },
            "resource_efficiency": resource_stats,
            "optimization_effectiveness": {
                "container_pool_stats": self.container_pool.pool_stats,
                "execution_strategy_optimal": sum(execution_times) <= self.target_duration * 0.8,
                "startup_time_optimized": statistics.mean(startup_times) < 10 if startup_times else False,
                "cleanup_time_optimized": statistics.mean(cleanup_times) < 5 if cleanup_times else False
            },
            "recommendations": self._generate_optimization_recommendations(results, resource_stats),
            "detailed_results": [r.to_dict() for r in results]
        }
        
        return report
    
    def _generate_optimization_recommendations(self, results: List[ExecutionMetrics], 
                                            resource_stats: Dict[str, Any]) -> List[str]:
        """生成優化建議"""
        recommendations = []
        
        execution_times = [r.total_time for r in results]
        startup_times = [r.container_startup_time for r in results]
        cleanup_times = [r.container_cleanup_time for r in results]
        
        total_time = sum(execution_times)
        avg_startup = statistics.mean(startup_times) if startup_times else 0
        avg_cleanup = statistics.mean(cleanup_times) if cleanup_times else 0
        
        # 總時間建議
        if total_time > self.target_duration:
            recommendations.append(
                f"總執行時間 {total_time:.1f}s 超過目標 {self.target_duration}s，"
                "建議增加並行度或進一步優化容器配置"
            )
        elif total_time <= self.target_duration * 0.5:
            recommendations.append(
                f"總執行時間 {total_time:.1f}s 表現優秀，"
                "可考慮增加更多測試案例或提高測試複雜度"
            )
        
        # 啟動時間建議
        if avg_startup > 15:
            recommendations.append(
                f"平均容器啟動時間 {avg_startup:.1f}s 較長，"
                "建議優化 Docker 鏡像大小或使用容器預熱策略"
            )
        
        # 清理時間建議
        if avg_cleanup > 10:
            recommendations.append(
                f"平均容器清理時間 {avg_cleanup:.1f}s 較長，"
                "建議優化容器停止策略或使用更積極的清理配置"
            )
        
        # 資源使用建議
        if resource_stats:
            memory_stats = resource_stats.get('memory', {})
            cpu_stats = resource_stats.get('cpu', {})
            
            if memory_stats.get('exceeded_2gb_limit', False):
                recommendations.append(
                    "記憶體使用超過 2GB 限制，建議減少並行度或優化記憶體使用"
                )
            
            if cpu_stats.get('exceeded_80_percent_limit', False):
                recommendations.append(
                    "CPU 使用超過 80% 限制，建議調整並行配置或優化測試邏輯"
                )
        
        # 成功率建議
        success_rate = (sum(1 for r in results if r.success) / len(results) * 100) if results else 0
        if success_rate < 95:
            recommendations.append(
                f"測試成功率 {success_rate:.1f}% 低於 95% 目標，"
                "需要調查失敗原因並提高測試穩定性"
            )
        
        # 如果沒有問題，給出肯定建議
        if not recommendations:
            recommendations.append(
                "所有效能指標都表現優秀！測試執行時間、資源使用和成功率都達到了最佳狀態。"
            )
        
        return recommendations


# 便利函數
def create_optimized_test_config(name: str, test_type: str, image: str, **kwargs) -> Dict[str, Any]:
    """創建優化的測試配置"""
    return {
        'name': name,
        'test_type': test_type,
        'image': image,
        'detach': True,
        'remove': False,  # 由容器池管理
        **kwargs
    }


def run_optimized_execution_tests(docker_client, test_configs: List[Dict[str, Any]], 
                                 target_duration: float = 600.0) -> Dict[str, Any]:
    """運行優化執行時間的測試"""
    optimizer = ExecutionTimeOptimizer(docker_client, target_duration)
    return optimizer.optimize_test_execution(test_configs)