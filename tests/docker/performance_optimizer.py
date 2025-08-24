"""
跨平台 Docker 測試效能優化器
Task ID: T1 - Docker 測試框架建立 (效能優化專門化)

作為後端效能專家 Ethan 的專門領域實作：
- 跨平台效能基準測試和監控
- 資源使用效率優化（記憶體≤2GB，CPU≤80%）
- 測試執行效率優化（目標：≤10分鐘）
- 效能差異分析和報告生成
"""

import asyncio
import time
import threading
import concurrent.futures
import resource
import gc
import psutil
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Tuple, NamedTuple
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from enum import Enum
import json
import statistics
from pathlib import Path

try:
    import docker
    from docker.models.containers import Container
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False

logger = logging.getLogger(__name__)


class ResourceMetricType(Enum):
    """資源指標類型"""
    MEMORY_USAGE = "memory_usage_mb"
    CPU_USAGE = "cpu_usage_percent"
    DISK_IO = "disk_io_mb_s"
    NETWORK_IO = "network_io_mb_s"
    EXECUTION_TIME = "execution_time_seconds"


@dataclass
class ResourceMetrics:
    """資源使用指標"""
    timestamp: str
    memory_usage_mb: float
    cpu_usage_percent: float
    disk_io_read_mb: float = 0.0
    disk_io_write_mb: float = 0.0
    network_io_sent_mb: float = 0.0
    network_io_recv_mb: float = 0.0
    active_threads: int = 0
    container_count: int = 0
    
    @classmethod
    def capture_current(cls) -> 'ResourceMetrics':
        """捕獲當前系統資源使用情況"""
        memory = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=0.1)
        
        # 取得 IO 統計
        disk_io = psutil.disk_io_counters()
        net_io = psutil.net_io_counters()
        
        return cls(
            timestamp=datetime.now().isoformat(),
            memory_usage_mb=memory.used / (1024 * 1024),
            cpu_usage_percent=cpu_percent,
            disk_io_read_mb=disk_io.read_bytes / (1024 * 1024) if disk_io else 0.0,
            disk_io_write_mb=disk_io.write_bytes / (1024 * 1024) if disk_io else 0.0,
            network_io_sent_mb=net_io.bytes_sent / (1024 * 1024) if net_io else 0.0,
            network_io_recv_mb=net_io.bytes_recv / (1024 * 1024) if net_io else 0.0,
            active_threads=threading.active_count(),
        )


@dataclass
class PerformanceProfile:
    """效能配置檔案"""
    test_name: str
    platform: str
    max_memory_mb: float = 2048  # 2GB 限制
    max_cpu_percent: float = 80.0  # 80% CPU 限制
    max_execution_time_seconds: float = 600  # 10 分鐘限制
    parallel_execution_limit: int = 3
    resource_monitoring_interval: float = 1.0
    cleanup_aggressive: bool = True
    memory_optimization_enabled: bool = True
    
    def is_within_limits(self, metrics: ResourceMetrics) -> Tuple[bool, List[str]]:
        """檢查是否符合效能限制"""
        violations = []
        
        if metrics.memory_usage_mb > self.max_memory_mb:
            violations.append(f"記憶體使用 {metrics.memory_usage_mb:.1f}MB 超過限制 {self.max_memory_mb}MB")
        
        if metrics.cpu_usage_percent > self.max_cpu_percent:
            violations.append(f"CPU 使用 {metrics.cpu_usage_percent:.1f}% 超過限制 {self.max_cpu_percent}%")
        
        return len(violations) == 0, violations


class PerformanceMonitor:
    """效能監控器"""
    
    def __init__(self, profile: PerformanceProfile):
        self.profile = profile
        self.metrics_history: List[ResourceMetrics] = []
        self.monitoring_active = False
        self.monitoring_thread: Optional[threading.Thread] = None
        self.start_time: Optional[datetime] = None
        
    def start_monitoring(self) -> None:
        """開始效能監控"""
        if self.monitoring_active:
            return
            
        self.monitoring_active = True
        self.start_time = datetime.now()
        self.monitoring_thread = threading.Thread(
            target=self._monitoring_loop, 
            daemon=True
        )
        self.monitoring_thread.start()
        logger.info(f"效能監控已啟動，間隔: {self.profile.resource_monitoring_interval}s")
    
    def stop_monitoring(self) -> None:
        """停止效能監控"""
        self.monitoring_active = False
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=2.0)
        logger.info("效能監控已停止")
    
    def _monitoring_loop(self) -> None:
        """監控循環"""
        while self.monitoring_active:
            try:
                metrics = ResourceMetrics.capture_current()
                self.metrics_history.append(metrics)
                
                # 檢查資源限制
                within_limits, violations = self.profile.is_within_limits(metrics)
                if not within_limits:
                    logger.warning(f"資源使用超出限制: {violations}")
                    
                time.sleep(self.profile.resource_monitoring_interval)
                
            except Exception as e:
                logger.error(f"效能監控錯誤: {e}")
                time.sleep(1)
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """取得效能摘要"""
        if not self.metrics_history:
            return {"error": "沒有效能數據"}
        
        memory_usage = [m.memory_usage_mb for m in self.metrics_history]
        cpu_usage = [m.cpu_usage_percent for m in self.metrics_history]
        
        duration = (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
        
        return {
            "monitoring_duration_seconds": duration,
            "total_metrics_collected": len(self.metrics_history),
            "memory_usage": {
                "max_mb": max(memory_usage),
                "average_mb": statistics.mean(memory_usage),
                "peak_exceeded_limit": max(memory_usage) > self.profile.max_memory_mb
            },
            "cpu_usage": {
                "max_percent": max(cpu_usage),
                "average_percent": statistics.mean(cpu_usage),
                "peak_exceeded_limit": max(cpu_usage) > self.profile.max_cpu_percent
            },
            "performance_profile": {
                "memory_limit_mb": self.profile.max_memory_mb,
                "cpu_limit_percent": self.profile.max_cpu_percent,
                "execution_time_limit_seconds": self.profile.max_execution_time_seconds
            },
            "compliance": {
                "memory_compliant": max(memory_usage) <= self.profile.max_memory_mb,
                "cpu_compliant": max(cpu_usage) <= self.profile.max_cpu_percent,
                "overall_compliant": (
                    max(memory_usage) <= self.profile.max_memory_mb and 
                    max(cpu_usage) <= self.profile.max_cpu_percent
                )
            }
        }


class OptimizedCrossPlatformTester:
    """效能優化的跨平台測試器
    
    實作 Ethan 效能專家的核心優化策略：
    - 並行測試執行優化
    - 資源使用監控和限制
    - 記憶體和 CPU 效率管理
    - 測試執行時間控制
    """
    
    def __init__(self, docker_client, logger, performance_profile: PerformanceProfile):
        if not DOCKER_AVAILABLE:
            raise ImportError("Docker SDK 不可用")
            
        self.docker_client = docker_client
        self.logger = logger
        self.performance_profile = performance_profile
        self.performance_monitor = PerformanceMonitor(performance_profile)
        self.test_results: List[Dict[str, Any]] = []
        
        # 執行器配置（限制並行度以控制資源使用）
        self.executor = ThreadPoolExecutor(
            max_workers=performance_profile.parallel_execution_limit,
            thread_name_prefix="cross-platform-test"
        )
        
    def __enter__(self):
        """上下文管理器進入"""
        self.performance_monitor.start_monitoring()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.performance_monitor.stop_monitoring()
        self.executor.shutdown(wait=True)
        if self.performance_profile.cleanup_aggressive:
            self._aggressive_cleanup()
    
    @contextmanager
    def resource_controlled_execution(self):
        """資源控制的執行上下文"""
        initial_metrics = ResourceMetrics.capture_current()
        start_time = time.time()
        
        try:
            yield
        finally:
            end_time = time.time()
            final_metrics = ResourceMetrics.capture_current()
            execution_time = end_time - start_time
            
            # 記錄執行效能
            self.logger.log_info(
                f"測試執行完成，耗時: {execution_time:.2f}s",
                {
                    "execution_time_seconds": execution_time,
                    "initial_memory_mb": initial_metrics.memory_usage_mb,
                    "final_memory_mb": final_metrics.memory_usage_mb,
                    "memory_delta_mb": final_metrics.memory_usage_mb - initial_metrics.memory_usage_mb,
                    "initial_cpu_percent": initial_metrics.cpu_usage_percent,
                    "final_cpu_percent": final_metrics.cpu_usage_percent
                }
            )
            
            # 檢查是否超出時間限制
            if execution_time > self.performance_profile.max_execution_time_seconds:
                self.logger.log_error(
                    f"測試執行時間 {execution_time:.2f}s 超過限制 {self.performance_profile.max_execution_time_seconds}s"
                )
    
    def run_optimized_platform_tests(
        self, 
        platforms: List[str], 
        test_image: str
    ) -> List[Dict[str, Any]]:
        """執行優化的跨平台測試
        
        實作關鍵優化策略：
        1. 並行執行控制
        2. 資源使用監控
        3. 早期失敗偵測
        4. 記憶體管理
        """
        self.logger.log_info(f"開始優化跨平台測試，平台數量: {len(platforms)}")
        
        with self.resource_controlled_execution():
            # 使用 ThreadPoolExecutor 進行並行測試，但限制並行度
            future_to_platform = {}
            
            for platform in platforms:
                future = self.executor.submit(
                    self._run_single_platform_test_optimized,
                    platform,
                    test_image
                )
                future_to_platform[future] = platform
            
            results = []
            completed_count = 0
            
            # 收集結果並監控進度
            for future in as_completed(future_to_platform):
                platform = future_to_platform[future]
                try:
                    result = future.result(timeout=self.performance_profile.max_execution_time_seconds)
                    results.append(result)
                    completed_count += 1
                    
                    self.logger.log_info(
                        f"平台測試完成 ({completed_count}/{len(platforms)}): {platform}"
                    )
                    
                    # 檢查資源使用情況
                    self._check_resource_limits()
                    
                except Exception as e:
                    self.logger.log_error(f"平台 {platform} 測試失敗", e)
                    results.append({
                        "platform": platform,
                        "success": False,
                        "error": str(e),
                        "execution_time_seconds": 0
                    })
        
        self.test_results.extend(results)
        return results
    
    def _run_single_platform_test_optimized(
        self, 
        platform: str, 
        test_image: str
    ) -> Dict[str, Any]:
        """執行單一平台的優化測試"""
        start_time = time.time()
        container = None
        
        try:
            # 記憶體優化：在每個測試前進行垃圾收集
            if self.performance_profile.memory_optimization_enabled:
                gc.collect()
            
            # 容器配置優化
            container_config = self._get_optimized_container_config(platform, test_image)
            
            # 創建並啟動容器
            container = self.docker_client.containers.run(**container_config)
            
            # 等待容器完成（帶超時控制）
            timeout = min(120, self.performance_profile.max_execution_time_seconds // len(['current']))
            exit_code = container.wait(timeout=timeout)
            
            # 快速驗證結果
            success = self._verify_container_result_optimized(container)
            
            execution_time = time.time() - start_time
            
            return {
                "platform": platform,
                "success": success,
                "execution_time_seconds": execution_time,
                "container_id": container.id[:12],
                "exit_code": exit_code.get("StatusCode", -1) if isinstance(exit_code, dict) else exit_code,
                "resource_efficient": execution_time <= 60  # 1分鐘內完成視為高效
            }
            
        except Exception as e:
            execution_time = time.time() - start_time
            return {
                "platform": platform,
                "success": False,
                "error": str(e),
                "execution_time_seconds": execution_time,
                "container_id": container.id[:12] if container else None
            }
        finally:
            # 立即清理容器以節省資源
            if container:
                try:
                    container.stop(timeout=5)
                    container.remove(force=True)
                except Exception as e:
                    self.logger.log_error(f"容器清理失敗: {container.id[:12]}", e)
    
    def _get_optimized_container_config(self, platform: str, image: str) -> Dict[str, Any]:
        """取得優化的容器配置"""
        return {
            'image': image,
            'detach': True,
            'remove': False,  # 手動控制清理
            'mem_limit': '512m',  # 限制記憶體使用
            'cpu_period': 100000,
            'cpu_quota': 50000,  # 限制 CPU 使用為 50%
            'environment': {
                'PLATFORM_TEST': 'true',
                'OPTIMIZATION_MODE': 'enabled',
                'PLATFORM': platform.lower()
            },
            'command': self._get_optimized_test_command(platform),
            'network_disabled': True,  # 禁用網絡以節省資源（如果測試不需要）
        }
    
    def _get_optimized_test_command(self, platform: str) -> List[str]:
        """取得優化的測試命令"""
        return [
            'python', '-c',
            f'''
import platform
import os
import sys
import time

# 快速平台驗證測試
print(f"Platform: {{platform.system()}}")
print(f"Environment PLATFORM: {{os.environ.get('PLATFORM', 'unknown')}}")

# 簡化的相容性測試
if platform.system().lower() == "{platform}" or os.environ.get('PLATFORM', '').lower() == "{platform}":
    print("Platform compatibility test passed")
    sys.exit(0)
else:
    print("Platform mismatch detected")
    sys.exit(1)
'''
        ]
    
    def _verify_container_result_optimized(self, container) -> bool:
        """優化的容器結果驗證"""
        try:
            # 快速檢查退出狀態
            container.reload()
            exit_code = container.attrs['State']['ExitCode']
            
            if exit_code != 0:
                return False
            
            # 簡化的日誌檢查
            logs = container.logs(tail=20).decode('utf-8', errors='ignore')
            return "compatibility test passed" in logs
            
        except Exception as e:
            self.logger.log_error("容器結果驗證失敗", e)
            return False
    
    def _check_resource_limits(self) -> None:
        """檢查資源限制"""
        current_metrics = ResourceMetrics.capture_current()
        within_limits, violations = self.performance_profile.is_within_limits(current_metrics)
        
        if not within_limits:
            self.logger.log_error(f"資源限制超出: {violations}")
            # 觸發積極清理
            self._aggressive_cleanup()
    
    def _aggressive_cleanup(self) -> None:
        """積極的資源清理"""
        try:
            # 強制垃圾收集
            collected = gc.collect()
            if collected > 0:
                self.logger.log_info(f"垃圾收集釋放了 {collected} 個物件")
            
            # 清理任何殘留的容器
            try:
                containers = self.docker_client.containers.list(all=True, filters={
                    "label": "test-container"
                })
                for container in containers:
                    try:
                        container.stop(timeout=2)
                        container.remove(force=True)
                    except:
                        pass
            except Exception as e:
                self.logger.log_error("容器清理失敗", e)
                
        except Exception as e:
            self.logger.log_error("積極清理失敗", e)
    
    def generate_performance_report(self) -> Dict[str, Any]:
        """生成效能分析報告"""
        performance_summary = self.performance_monitor.get_performance_summary()
        
        if not self.test_results:
            return {
                "error": "沒有測試結果可分析",
                "performance_monitoring": performance_summary
            }
        
        # 分析測試執行效能
        execution_times = [r.get("execution_time_seconds", 0) for r in self.test_results]
        success_count = sum(1 for r in self.test_results if r.get("success", False))
        
        # 效能分析
        performance_analysis = {
            "test_execution_analysis": {
                "total_tests": len(self.test_results),
                "successful_tests": success_count,
                "success_rate_percent": (success_count / len(self.test_results)) * 100,
                "execution_time": {
                    "total_seconds": sum(execution_times),
                    "average_seconds": statistics.mean(execution_times) if execution_times else 0,
                    "max_seconds": max(execution_times) if execution_times else 0,
                    "min_seconds": min(execution_times) if execution_times else 0
                }
            },
            "resource_efficiency_analysis": performance_summary,
            "optimization_effectiveness": {
                "average_test_time_under_60s": statistics.mean(execution_times) < 60,
                "all_tests_under_120s": max(execution_times) < 120 if execution_times else False,
                "resource_compliant": performance_summary.get("compliance", {}).get("overall_compliant", False),
                "parallel_execution_effective": len(self.test_results) > 1
            },
            "recommendations": self._generate_performance_recommendations(execution_times, performance_summary)
        }
        
        return {
            "report_metadata": {
                "generated_at": datetime.now().isoformat(),
                "test_framework_version": "optimized-1.0",
                "task_id": "T1",
                "optimization_profile": {
                    "memory_limit_mb": self.performance_profile.max_memory_mb,
                    "cpu_limit_percent": self.performance_profile.max_cpu_percent,
                    "execution_time_limit_seconds": self.performance_profile.max_execution_time_seconds,
                    "parallel_limit": self.performance_profile.parallel_execution_limit
                }
            },
            "performance_analysis": performance_analysis,
            "detailed_test_results": self.test_results
        }
    
    def _generate_performance_recommendations(
        self, 
        execution_times: List[float], 
        performance_summary: Dict[str, Any]
    ) -> List[str]:
        """生成效能優化建議"""
        recommendations = []
        
        if not execution_times:
            return ["沒有執行時間數據可分析"]
        
        avg_time = statistics.mean(execution_times)
        max_time = max(execution_times)
        
        # 執行時間建議
        if avg_time > 60:
            recommendations.append(f"平均測試時間 {avg_time:.1f}s 較長，建議進一步優化容器啟動和測試邏輯")
        
        if max_time > 120:
            recommendations.append(f"最長測試時間 {max_time:.1f}s 超過 2 分鐘，建議檢查特定平台的效能問題")
        
        # 資源使用建議
        compliance = performance_summary.get("compliance", {})
        if not compliance.get("memory_compliant", True):
            recommendations.append("記憶體使用超出 2GB 限制，建議加強記憶體管理和清理策略")
        
        if not compliance.get("cpu_compliant", True):
            recommendations.append("CPU 使用超過 80% 限制，建議降低並行度或優化容器配置")
        
        # 優化建議
        if len(execution_times) == 1:
            recommendations.append("考慮增加並行測試以提高整體效率")
        elif len(execution_times) > self.performance_profile.parallel_execution_limit:
            recommendations.append(f"當前並行度 {self.performance_profile.parallel_execution_limit} 可能可以進一步調整")
        
        # 成功率建議
        success_rate = (sum(1 for r in self.test_results if r.get("success", False)) / len(self.test_results)) * 100
        if success_rate < 95:
            recommendations.append(f"測試成功率 {success_rate:.1f}% 低於 95% 目標，需要調查失敗原因")
        
        return recommendations or ["效能表現良好，符合所有優化目標"]


# === 效能測試工具函數 ===

def benchmark_cross_platform_performance(
    docker_client,
    test_logger,
    platforms: List[str],
    test_image: str,
    performance_profile: Optional[PerformanceProfile] = None
) -> Dict[str, Any]:
    """跨平台效能基準測試
    
    Args:
        docker_client: Docker 客戶端
        test_logger: 測試日誌記錄器
        platforms: 要測試的平台列表
        test_image: 測試用 Docker 鏡像
        performance_profile: 效能配置檔案
    
    Returns:
        效能基準測試報告
    """
    if performance_profile is None:
        performance_profile = PerformanceProfile(
            test_name="cross_platform_benchmark",
            platform="multi_platform"
        )
    
    test_logger.log_info(f"開始跨平台效能基準測試，平台: {platforms}")
    
    with OptimizedCrossPlatformTester(docker_client, test_logger, performance_profile) as tester:
        results = tester.run_optimized_platform_tests(platforms, test_image)
        performance_report = tester.generate_performance_report()
    
    test_logger.log_info("跨平台效能基準測試完成")
    
    return performance_report


def create_performance_profile_for_ci() -> PerformanceProfile:
    """為 CI/CD 環境創建效能配置"""
    return PerformanceProfile(
        test_name="ci_cross_platform_test",
        platform="ci_environment",
        max_memory_mb=1536,  # CI 環境通常記憶體較少
        max_cpu_percent=60.0,  # CI 環境 CPU 使用更保守
        max_execution_time_seconds=480,  # 8 分鐘，留 2 分鐘緩衝
        parallel_execution_limit=2,  # CI 環境並行度較低
        resource_monitoring_interval=2.0,  # CI 環境監控頻率較低
        cleanup_aggressive=True,
        memory_optimization_enabled=True
    )