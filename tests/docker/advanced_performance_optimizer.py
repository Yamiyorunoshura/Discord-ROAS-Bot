"""
進階Docker測試效能優化器
Task ID: T1 - Docker 測試框架建立 (Ethan效能專家特化實作)

實作核心優化策略：
- 智能並行測試執行
- 容器生命週期優化
- 資源使用監控和限制
- 執行時間控制和優化
- 動態負載平衡
"""

import asyncio
import concurrent.futures
import time
import threading
import queue
import gc
import psutil
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Tuple, Callable
from dataclasses import dataclass, field
from contextlib import contextmanager, asynccontextmanager
from enum import Enum
import json
import statistics
from pathlib import Path
import weakref

try:
    import docker
    from docker.models.containers import Container
    from docker.errors import DockerException, APIError
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False

logger = logging.getLogger(__name__)


class OptimizationLevel(Enum):
    """優化級別"""
    CONSERVATIVE = "conservative"  # 保守模式，穩定優先
    BALANCED = "balanced"        # 平衡模式，兼顧速度和穩定性
    AGGRESSIVE = "aggressive"    # 積極模式，速度優先


@dataclass
class PerformanceConstraints:
    """效能約束條件"""
    max_memory_mb: float = 2048  # 2GB 記憶體限制
    max_cpu_percent: float = 80.0  # 80% CPU 限制
    max_execution_time_seconds: float = 600  # 10 分鐘時間限制
    max_parallel_containers: int = 3  # 最大並行容器數
    container_startup_timeout: float = 30.0  # 容器啟動超時
    container_stop_timeout: float = 10.0  # 容器停止超時
    resource_monitoring_interval: float = 1.0  # 資源監控間隔
    
    def is_compliant(self, current_metrics: Dict[str, float]) -> Tuple[bool, List[str]]:
        """檢查是否符合約束條件"""
        violations = []
        
        memory_usage = current_metrics.get('memory_mb', 0)
        cpu_usage = current_metrics.get('cpu_percent', 0)
        execution_time = current_metrics.get('execution_time', 0)
        
        if memory_usage > self.max_memory_mb:
            violations.append(f"記憶體使用 {memory_usage:.1f}MB > 限制 {self.max_memory_mb}MB")
        
        if cpu_usage > self.max_cpu_percent:
            violations.append(f"CPU使用 {cpu_usage:.1f}% > 限制 {self.max_cpu_percent}%")
        
        if execution_time > self.max_execution_time_seconds:
            violations.append(f"執行時間 {execution_time:.1f}s > 限制 {self.max_execution_time_seconds}s")
        
        return len(violations) == 0, violations


class ResourceTracker:
    """資源使用追蹤器"""
    
    def __init__(self, constraints: PerformanceConstraints):
        self.constraints = constraints
        self.metrics_history: List[Dict[str, Any]] = []
        self.tracking_active = False
        self.tracking_thread: Optional[threading.Thread] = None
        self.start_time: Optional[float] = None
        
    def start_tracking(self) -> None:
        """開始資源追蹤"""
        if self.tracking_active:
            return
            
        self.tracking_active = True
        self.start_time = time.time()
        self.tracking_thread = threading.Thread(
            target=self._tracking_loop,
            daemon=True,
            name="ResourceTracker"
        )
        self.tracking_thread.start()
        logger.info("資源追蹤已啟動")
    
    def stop_tracking(self) -> Dict[str, Any]:
        """停止資源追蹤並返回統計"""
        self.tracking_active = False
        if self.tracking_thread and self.tracking_thread.is_alive():
            self.tracking_thread.join(timeout=2.0)
        
        return self._generate_statistics()
    
    def _tracking_loop(self) -> None:
        """資源追蹤循環"""
        while self.tracking_active:
            try:
                # 收集系統指標
                memory = psutil.virtual_memory()
                cpu_percent = psutil.cpu_percent(interval=0.1)
                
                metrics = {
                    'timestamp': time.time(),
                    'memory_mb': memory.used / (1024 * 1024),
                    'memory_percent': memory.percent,
                    'cpu_percent': cpu_percent,
                    'active_threads': threading.active_count(),
                    'execution_time': time.time() - self.start_time if self.start_time else 0
                }
                
                self.metrics_history.append(metrics)
                
                # 檢查約束違反
                compliant, violations = self.constraints.is_compliant(metrics)
                if not compliant:
                    logger.warning(f"資源約束違反: {violations}")
                
                time.sleep(self.constraints.resource_monitoring_interval)
                
            except Exception as e:
                logger.error(f"資源追蹤錯誤: {e}")
                time.sleep(1)
    
    def _generate_statistics(self) -> Dict[str, Any]:
        """生成統計資料"""
        if not self.metrics_history:
            return {"error": "沒有追蹤資料"}
        
        memory_usage = [m['memory_mb'] for m in self.metrics_history]
        cpu_usage = [m['cpu_percent'] for m in self.metrics_history]
        
        return {
            "tracking_duration": time.time() - self.start_time if self.start_time else 0,
            "total_samples": len(self.metrics_history),
            "memory": {
                "max_mb": max(memory_usage),
                "avg_mb": statistics.mean(memory_usage),
                "min_mb": min(memory_usage),
                "exceeded_limit": any(m > self.constraints.max_memory_mb for m in memory_usage)
            },
            "cpu": {
                "max_percent": max(cpu_usage),
                "avg_percent": statistics.mean(cpu_usage),
                "min_percent": min(cpu_usage),
                "exceeded_limit": any(c > self.constraints.max_cpu_percent for c in cpu_usage)
            },
            "compliance": {
                "memory_compliant": all(m <= self.constraints.max_memory_mb for m in memory_usage),
                "cpu_compliant": all(c <= self.constraints.max_cpu_percent for c in cpu_usage)
            }
        }


class OptimizedContainerManager:
    """優化的容器管理器"""
    
    def __init__(self, docker_client, constraints: PerformanceConstraints, 
                 optimization_level: OptimizationLevel = OptimizationLevel.BALANCED):
        self.docker_client = docker_client
        self.constraints = constraints
        self.optimization_level = optimization_level
        self.active_containers: weakref.WeakSet = weakref.WeakSet()
        self.container_pool_lock = threading.Lock()
        
    @contextmanager
    def optimized_container(self, config: Dict[str, Any]):
        """優化的容器上下文管理器"""
        container = None
        start_time = time.time()
        
        try:
            # 應用優化配置
            optimized_config = self._apply_optimizations(config)
            
            # 創建容器
            container = self._create_container_optimized(optimized_config)
            self.active_containers.add(container)
            
            yield container
            
        except Exception as e:
            logger.error(f"容器操作失敗: {e}")
            raise
        finally:
            # 清理容器
            if container:
                cleanup_time = time.time()
                self._cleanup_container_optimized(container)
                cleanup_duration = time.time() - cleanup_time
                total_duration = time.time() - start_time
                
                logger.debug(f"容器 {container.id[:12]} 生命週期: {total_duration:.2f}s (清理: {cleanup_duration:.2f}s)")
    
    def _apply_optimizations(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """應用優化配置"""
        optimized = config.copy()
        
        # 基本資源限制
        optimized.setdefault('mem_limit', '512m')
        optimized.setdefault('cpu_period', 100000)
        optimized.setdefault('cpu_quota', 50000)  # 50% CPU
        
        # 根據優化級別調整
        if self.optimization_level == OptimizationLevel.AGGRESSIVE:
            # 積極模式：更低的資源限制，更快的超時
            optimized['mem_limit'] = '256m'
            optimized['cpu_quota'] = 25000  # 25% CPU
            optimized['stop_timeout'] = 5
        elif self.optimization_level == OptimizationLevel.CONSERVATIVE:
            # 保守模式：更高的資源限制，更長的超時
            optimized['mem_limit'] = '1g'
            optimized['cpu_quota'] = 75000  # 75% CPU
            optimized['stop_timeout'] = 15
        
        # 效能優化環境變數
        env = optimized.setdefault('environment', {})
        env.update({
            'PYTHONOPTIMIZE': '2',
            'PYTHONDONTWRITEBYTECODE': '1',
            'PYTHONUNBUFFERED': '1',
            'PERFORMANCE_MODE': 'optimized'
        })
        
        return optimized
    
    def _create_container_optimized(self, config: Dict[str, Any]) -> Container:
        """優化的容器創建"""
        try:
            # 預檢查資源可用性
            self._check_resource_availability()
            
            # 創建容器
            container = self.docker_client.containers.create(**config)
            
            # 啟動容器
            start_time = time.time()
            container.start()
            
            # 等待容器準備就緒
            self._wait_for_container_ready(container)
            
            startup_time = time.time() - start_time
            if startup_time > self.constraints.container_startup_timeout:
                logger.warning(f"容器啟動時間過長: {startup_time:.2f}s")
            
            logger.debug(f"容器 {container.id[:12]} 啟動完成: {startup_time:.2f}s")
            return container
            
        except Exception as e:
            logger.error(f"容器創建失敗: {e}")
            raise
    
    def _cleanup_container_optimized(self, container: Container) -> None:
        """優化的容器清理"""
        try:
            with self.container_pool_lock:
                # 停止容器
                if container.status in ['running', 'paused']:
                    timeout = getattr(container, 'stop_timeout', self.constraints.container_stop_timeout)
                    container.stop(timeout=int(timeout))
                
                # 移除容器
                try:
                    container.remove(force=True)
                except Exception as e:
                    logger.debug(f"容器移除失敗: {e}")
                
                # 從活動容器列表移除
                if container in self.active_containers:
                    self.active_containers.discard(container)
                    
        except Exception as e:
            logger.warning(f"容器清理失敗: {e}")
    
    def _check_resource_availability(self) -> None:
        """檢查資源可用性"""
        memory = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=0.1)
        
        if memory.percent > 90:
            # 觸發記憶體清理
            gc.collect()
            
        if cpu_percent > self.constraints.max_cpu_percent:
            raise ResourceError(f"CPU使用率過高: {cpu_percent:.1f}%")
        
        # 檢查活動容器數量
        active_count = len(self.active_containers)
        if active_count >= self.constraints.max_parallel_containers:
            raise ResourceError(f"活動容器數量達到限制: {active_count}")
    
    def _wait_for_container_ready(self, container: Container, timeout: float = None) -> None:
        """等待容器準備就緒"""
        timeout = timeout or self.constraints.container_startup_timeout
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                container.reload()
                if container.status == 'running':
                    return
                elif container.status in ['exited', 'dead']:
                    raise ContainerError(f"容器異常退出: {container.status}")
            except Exception as e:
                logger.debug(f"容器狀態檢查錯誤: {e}")
            
            time.sleep(0.5)
        
        raise TimeoutError(f"容器啟動超時 ({timeout}s)")


class ParallelTestExecutor:
    """並行測試執行器"""
    
    def __init__(self, docker_client, constraints: PerformanceConstraints,
                 optimization_level: OptimizationLevel = OptimizationLevel.BALANCED):
        self.docker_client = docker_client
        self.constraints = constraints
        self.optimization_level = optimization_level
        self.container_manager = OptimizedContainerManager(
            docker_client, constraints, optimization_level
        )
        self.resource_tracker = ResourceTracker(constraints)
        self.test_results: List[Dict[str, Any]] = []
        
        # 執行器配置
        self.executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=min(constraints.max_parallel_containers, 3),
            thread_name_prefix="ParallelTest"
        )
    
    def __enter__(self):
        self.resource_tracker.start_tracking()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        resource_stats = self.resource_tracker.stop_tracking()
        self.executor.shutdown(wait=True)
        logger.info(f"並行測試執行器關閉，資源統計: {resource_stats}")
    
    def execute_parallel_tests(self, test_configs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """執行並行測試"""
        logger.info(f"開始並行測試，測試數量: {len(test_configs)}")
        
        # 根據優化級別分組測試
        test_groups = self._group_tests_for_optimization(test_configs)
        all_results = []
        
        for group_name, group_tests in test_groups.items():
            logger.info(f"執行測試群組: {group_name} ({len(group_tests)} 個測試)")
            group_results = self._execute_test_group(group_tests)
            all_results.extend(group_results)
        
        self.test_results.extend(all_results)
        return all_results
    
    def _group_tests_for_optimization(self, test_configs: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """為優化分組測試"""
        groups = {
            "fast": [],      # 快速測試（< 5秒）
            "medium": [],    # 中等測試（5-30秒）
            "slow": []       # 慢速測試（> 30秒）
        }
        
        for config in test_configs:
            expected_duration = config.get('expected_duration', 10)
            
            if expected_duration < 5:
                groups["fast"].append(config)
            elif expected_duration < 30:
                groups["medium"].append(config)
            else:
                groups["slow"].append(config)
        
        return groups
    
    def _execute_test_group(self, test_configs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """執行測試群組"""
        future_to_config = {}
        
        # 提交測試任務
        for config in test_configs:
            future = self.executor.submit(self._execute_single_test, config)
            future_to_config[future] = config
        
        results = []
        # 收集結果
        for future in concurrent.futures.as_completed(future_to_config):
            config = future_to_config[future]
            try:
                result = future.result(timeout=self.constraints.max_execution_time_seconds)
                results.append(result)
            except Exception as e:
                logger.error(f"測試執行失敗 {config.get('name', 'unknown')}: {e}")
                results.append({
                    "test_name": config.get('name', 'unknown'),
                    "success": False,
                    "error": str(e),
                    "execution_time": 0
                })
        
        return results
    
    def _execute_single_test(self, test_config: Dict[str, Any]) -> Dict[str, Any]:
        """執行單個測試"""
        test_name = test_config.get('name', 'unknown')
        start_time = time.time()
        
        try:
            # 記憶體優化：測試前清理
            if self.optimization_level == OptimizationLevel.AGGRESSIVE:
                gc.collect()
            
            # 使用優化的容器管理器
            with self.container_manager.optimized_container(test_config) as container:
                # 執行測試邏輯
                result = self._run_test_logic(container, test_config)
                
            execution_time = time.time() - start_time
            
            return {
                "test_name": test_name,
                "success": result.get("success", True),
                "execution_time": execution_time,
                "details": result,
                "optimized": True
            }
            
        except Exception as e:
            execution_time = time.time() - start_time
            return {
                "test_name": test_name,
                "success": False,
                "error": str(e),
                "execution_time": execution_time,
                "optimized": False
            }
    
    def _run_test_logic(self, container: Container, test_config: Dict[str, Any]) -> Dict[str, Any]:
        """執行測試邏輯"""
        test_type = test_config.get('test_type', 'basic')
        
        if test_type == 'startup':
            return self._test_container_startup(container)
        elif test_type == 'health_check':
            return self._test_container_health_check(container)
        elif test_type == 'resource_limits':
            return self._test_container_resource_limits(container)
        else:
            return self._test_container_basic(container)
    
    def _test_container_startup(self, container: Container) -> Dict[str, Any]:
        """測試容器啟動"""
        container.reload()
        return {
            "success": container.status == 'running',
            "status": container.status,
            "test_type": "startup"
        }
    
    def _test_container_health_check(self, container: Container) -> Dict[str, Any]:
        """測試容器健康檢查"""
        container.reload()
        health = container.attrs.get('State', {}).get('Health', {})
        health_status = health.get('Status', 'none')
        
        return {
            "success": health_status in ['healthy', 'none'],
            "health_status": health_status,
            "test_type": "health_check"
        }
    
    def _test_container_resource_limits(self, container: Container) -> Dict[str, Any]:
        """測試容器資源限制"""
        container.reload()
        host_config = container.attrs.get('HostConfig', {})
        
        memory_limit = host_config.get('Memory', 0)
        cpu_quota = host_config.get('CpuQuota', 0)
        cpu_period = host_config.get('CpuPeriod', 0)
        
        return {
            "success": memory_limit > 0 and cpu_quota > 0,
            "memory_limit": memory_limit,
            "cpu_quota": cpu_quota,
            "cpu_period": cpu_period,
            "test_type": "resource_limits"
        }
    
    def _test_container_basic(self, container: Container) -> Dict[str, Any]:
        """基本容器測試"""
        container.reload()
        return {
            "success": container.status == 'running',
            "status": container.status,
            "test_type": "basic"
        }
    
    def generate_performance_report(self) -> Dict[str, Any]:
        """生成效能報告"""
        resource_stats = self.resource_tracker.stop_tracking() if self.resource_tracker.tracking_active else {}
        
        if not self.test_results:
            return {
                "error": "沒有測試結果",
                "resource_stats": resource_stats
            }
        
        # 計算測試統計
        total_tests = len(self.test_results)
        successful_tests = sum(1 for r in self.test_results if r.get("success", False))
        execution_times = [r.get("execution_time", 0) for r in self.test_results]
        
        return {
            "report_metadata": {
                "generated_at": datetime.now().isoformat(),
                "optimization_level": self.optimization_level.value,
                "task_id": "T1",
                "test_framework": "advanced_performance_optimizer"
            },
            "test_statistics": {
                "total_tests": total_tests,
                "successful_tests": successful_tests,
                "success_rate": (successful_tests / total_tests * 100) if total_tests > 0 else 0,
                "execution_time": {
                    "total_seconds": sum(execution_times),
                    "average_seconds": statistics.mean(execution_times) if execution_times else 0,
                    "max_seconds": max(execution_times) if execution_times else 0,
                    "min_seconds": min(execution_times) if execution_times else 0
                }
            },
            "performance_analysis": {
                "resource_efficiency": resource_stats,
                "optimization_effectiveness": {
                    "avg_test_time_under_30s": statistics.mean(execution_times) < 30 if execution_times else False,
                    "all_tests_under_60s": all(t < 60 for t in execution_times) if execution_times else False,
                    "meets_10min_target": sum(execution_times) <= 600,
                    "parallel_execution_benefit": total_tests > 1
                }
            },
            "recommendations": self._generate_recommendations(execution_times, resource_stats),
            "detailed_results": self.test_results
        }
    
    def _generate_recommendations(self, execution_times: List[float], resource_stats: Dict[str, Any]) -> List[str]:
        """生成優化建議"""
        recommendations = []
        
        if not execution_times:
            return ["沒有測試執行時間資料可分析"]
        
        total_time = sum(execution_times)
        avg_time = statistics.mean(execution_times)
        max_time = max(execution_times)
        
        # 時間相關建議
        if total_time > 600:  # 10分鐘
            recommendations.append(f"總執行時間 {total_time:.1f}s 超過 10 分鐘目標，建議進一步優化")
        
        if avg_time > 30:
            recommendations.append(f"平均測試時間 {avg_time:.1f}s 較長，考慮優化測試邏輯")
        
        if max_time > 60:
            recommendations.append(f"最長測試時間 {max_time:.1f}s，檢查特定測試的效能問題")
        
        # 資源相關建議
        memory_stats = resource_stats.get("memory", {})
        cpu_stats = resource_stats.get("cpu", {})
        
        if memory_stats.get("exceeded_limit", False):
            recommendations.append("記憶體使用超過限制，建議加強記憶體管理")
        
        if cpu_stats.get("exceeded_limit", False):
            recommendations.append("CPU 使用超過限制，建議降低並行度或優化容器配置")
        
        # 優化建議
        if len(execution_times) == 1:
            recommendations.append("考慮增加測試並行度以提高效率")
        
        if not recommendations:
            recommendations.append("效能表現良好，符合所有優化目標")
        
        return recommendations


# 異常類
class ResourceError(Exception):
    """資源相關錯誤"""
    pass


class ContainerError(Exception):
    """容器相關錯誤"""
    pass


# 便利函數
def create_test_config(name: str, test_type: str, image: str, 
                      expected_duration: float = 10, **kwargs) -> Dict[str, Any]:
    """創建測試配置"""
    config = {
        'name': name,
        'test_type': test_type,
        'image': image,
        'expected_duration': expected_duration,
        'detach': True,
        **kwargs
    }
    return config


def run_optimized_docker_tests(docker_client, test_configs: List[Dict[str, Any]], 
                              optimization_level: OptimizationLevel = OptimizationLevel.BALANCED) -> Dict[str, Any]:
    """運行優化的Docker測試"""
    constraints = PerformanceConstraints()
    
    with ParallelTestExecutor(docker_client, constraints, optimization_level) as executor:
        results = executor.execute_parallel_tests(test_configs)
        performance_report = executor.generate_performance_report()
    
    return performance_report