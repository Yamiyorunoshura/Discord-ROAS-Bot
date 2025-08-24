"""
Docker 測試框架進階資源監控和管理系統
Task ID: T1 - 效能優化專門化

Ethan 效能專家的資源管理核心實作：
- 即時資源監控和告警
- 動態資源限制調整
- 記憶體和CPU使用優化
- 容器資源隔離管理
- 資源洩漏檢測和防護
"""

import time
import threading
import psutil
import logging
import gc
import weakref
from typing import Dict, Any, List, Optional, Callable, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from contextlib import contextmanager
from collections import deque, defaultdict
from enum import Enum
import json
import os

try:
    import docker
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False

logger = logging.getLogger(__name__)


class ResourceAlertLevel(Enum):
    """資源告警等級"""
    INFO = "info"
    WARNING = "warning"  
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class ResourceType(Enum):
    """資源類型"""
    MEMORY = "memory"
    CPU = "cpu"
    DISK = "disk"
    NETWORK = "network"
    CONTAINERS = "containers"


@dataclass
class ResourceThresholds:
    """資源閾值配置"""
    memory_warning_percent: float = 70.0
    memory_critical_percent: float = 85.0
    memory_emergency_percent: float = 95.0
    
    cpu_warning_percent: float = 60.0
    cpu_critical_percent: float = 80.0
    cpu_emergency_percent: float = 95.0
    
    max_containers: int = 10
    max_memory_mb: int = 2048
    max_cpu_cores: int = 4
    
    # Docker 特定限制
    container_memory_limit_mb: int = 512
    container_cpu_limit: float = 1.0
    
    @classmethod
    def for_ci_environment(cls) -> 'ResourceThresholds':
        """CI 環境的保守配置"""
        return cls(
            memory_warning_percent=60.0,
            memory_critical_percent=75.0,
            memory_emergency_percent=90.0,
            cpu_warning_percent=50.0,
            cpu_critical_percent=70.0,
            cpu_emergency_percent=85.0,
            max_containers=6,
            max_memory_mb=1800,
            container_memory_limit_mb=300,
            container_cpu_limit=0.5
        )


@dataclass 
class ResourceSnapshot:
    """資源快照"""
    timestamp: float
    memory_percent: float
    memory_used_mb: float
    memory_available_mb: float
    cpu_percent: float
    active_containers: int
    disk_usage_percent: float = 0.0
    network_io_mb: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp,
            'memory_percent': self.memory_percent,
            'memory_used_mb': self.memory_used_mb,
            'memory_available_mb': self.memory_available_mb,
            'cpu_percent': self.cpu_percent,
            'active_containers': self.active_containers,
            'disk_usage_percent': self.disk_usage_percent,
            'network_io_mb': self.network_io_mb
        }


@dataclass
class ResourceAlert:
    """資源告警"""
    alert_id: str
    resource_type: ResourceType
    alert_level: ResourceAlertLevel
    message: str
    timestamp: float
    current_value: float
    threshold_value: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'alert_id': self.alert_id,
            'resource_type': self.resource_type.value,
            'alert_level': self.alert_level.value,
            'message': self.message,
            'timestamp': self.timestamp,
            'current_value': self.current_value,
            'threshold_value': self.threshold_value
        }


class AdaptiveResourceLimiter:
    """自適應資源限制器
    
    動態調整資源限制以確保系統穩定性：
    - 基於實際使用情況調整限制
    - 預防性資源控制
    - 智能負載削峰
    """
    
    def __init__(self, thresholds: ResourceThresholds):
        self.thresholds = thresholds
        self.current_limits = {
            'memory_mb': thresholds.max_memory_mb,
            'cpu_percent': 100.0,
            'max_containers': thresholds.max_containers
        }
        self.adjustment_history: List[Dict[str, Any]] = []
        
    def adjust_limits_based_on_usage(self, resource_snapshot: ResourceSnapshot) -> Dict[str, float]:
        """基於使用情況調整限制"""
        adjustments = {}
        
        # 記憶體動態限制
        if resource_snapshot.memory_percent > self.thresholds.memory_critical_percent:
            # 減少記憶體限制
            new_memory_limit = max(
                self.thresholds.max_memory_mb * 0.7,
                self.current_limits['memory_mb'] * 0.9
            )
            if new_memory_limit != self.current_limits['memory_mb']:
                adjustments['memory_mb'] = new_memory_limit
                self.current_limits['memory_mb'] = new_memory_limit
                
        elif resource_snapshot.memory_percent < self.thresholds.memory_warning_percent:
            # 可以增加記憶體限制
            new_memory_limit = min(
                self.thresholds.max_memory_mb,
                self.current_limits['memory_mb'] * 1.05
            )
            if new_memory_limit != self.current_limits['memory_mb']:
                adjustments['memory_mb'] = new_memory_limit
                self.current_limits['memory_mb'] = new_memory_limit
        
        # CPU 動態限制
        if resource_snapshot.cpu_percent > self.thresholds.cpu_critical_percent:
            # 減少並行度
            new_max_containers = max(2, self.current_limits['max_containers'] - 1)
            if new_max_containers != self.current_limits['max_containers']:
                adjustments['max_containers'] = new_max_containers
                self.current_limits['max_containers'] = new_max_containers
                
        elif resource_snapshot.cpu_percent < self.thresholds.cpu_warning_percent:
            # 可以增加並行度
            new_max_containers = min(
                self.thresholds.max_containers,
                self.current_limits['max_containers'] + 1
            )
            if new_max_containers != self.current_limits['max_containers']:
                adjustments['max_containers'] = new_max_containers
                self.current_limits['max_containers'] = new_max_containers
        
        # 記錄調整歷史
        if adjustments:
            self.adjustment_history.append({
                'timestamp': time.time(),
                'adjustments': adjustments.copy(),
                'trigger_snapshot': resource_snapshot.to_dict()
            })
            
            logger.info(f"資源限制調整: {adjustments}")
        
        return adjustments
    
    def get_container_resource_limits(self) -> Dict[str, Any]:
        """獲取容器資源限制"""
        return {
            'memory': f"{self.thresholds.container_memory_limit_mb}m",
            'cpus': str(self.thresholds.container_cpu_limit),
            'pids_limit': 100,
            'ulimits': [
                docker.types.Ulimit(name='nofile', soft=1024, hard=2048)
            ]
        }


class ResourceLeakDetector:
    """資源洩漏檢測器
    
    監控和檢測潛在的資源洩漏：
    - 長時間運行的容器
    - 記憶體使用持續增長
    - 未正常清理的資源
    """
    
    def __init__(self, monitoring_window_minutes: int = 10):
        self.monitoring_window = monitoring_window_minutes * 60  # 轉為秒
        self.resource_history: deque = deque(maxlen=100)
        self.container_lifetime: Dict[str, float] = {}
        self.detected_leaks: List[Dict[str, Any]] = []
        
    def check_for_leaks(self, resource_snapshot: ResourceSnapshot) -> List[Dict[str, Any]]:
        """檢查資源洩漏"""
        self.resource_history.append(resource_snapshot)
        current_time = time.time()
        leaks_detected = []
        
        # 記憶體洩漏檢測
        memory_leak = self._detect_memory_leak()
        if memory_leak:
            leaks_detected.append(memory_leak)
        
        # 長時間運行容器檢測
        long_running_containers = self._detect_long_running_containers(current_time)
        if long_running_containers:
            leaks_detected.extend(long_running_containers)
        
        return leaks_detected
    
    def _detect_memory_leak(self) -> Optional[Dict[str, Any]]:
        """檢測記憶體洩漏"""
        if len(self.resource_history) < 10:
            return None
        
        # 檢查記憶體使用趨勢
        recent_snapshots = list(self.resource_history)[-10:]
        memory_usage = [s.memory_used_mb for s in recent_snapshots]
        
        # 計算趨勢
        if len(memory_usage) >= 5:
            # 簡單線性趨勢檢測
            x = list(range(len(memory_usage)))
            y = memory_usage
            
            # 計算斜率
            n = len(x)
            sum_x = sum(x)
            sum_y = sum(y)
            sum_xy = sum(xi * yi for xi, yi in zip(x, y))
            sum_x2 = sum(xi * xi for xi in x)
            
            if n * sum_x2 - sum_x * sum_x != 0:
                slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
                
                # 如果記憶體使用持續增長超過閾值
                if slope > 10:  # 每個樣本點增長超過10MB
                    return {
                        'type': 'memory_leak',
                        'severity': 'critical',
                        'trend_slope': slope,
                        'current_usage_mb': memory_usage[-1],
                        'message': f'檢測到記憶體洩漏，增長速度: {slope:.2f} MB/snapshot'
                    }
        
        return None
    
    def _detect_long_running_containers(self, current_time: float) -> List[Dict[str, Any]]:
        """檢測長時間運行的容器"""
        long_running = []
        max_lifetime = 600  # 10分鐘
        
        for container_id, start_time in self.container_lifetime.items():
            runtime = current_time - start_time
            if runtime > max_lifetime:
                long_running.append({
                    'type': 'long_running_container',
                    'severity': 'warning',
                    'container_id': container_id,
                    'runtime_seconds': runtime,
                    'message': f'容器運行時間過長: {runtime:.0f}秒'
                })
        
        return long_running
    
    def register_container_start(self, container_id: str) -> None:
        """註冊容器啟動"""
        self.container_lifetime[container_id] = time.time()
    
    def register_container_stop(self, container_id: str) -> None:
        """註冊容器停止"""
        self.container_lifetime.pop(container_id, None)


class AdvancedResourceMonitor:
    """進階資源監控器
    
    Ethan 效能專家的核心資源監控實作：
    - 多層級資源監控和告警
    - 自適應資源限制調整
    - 資源洩漏檢測和防護
    - 即時效能優化建議
    """
    
    def __init__(self, 
                 thresholds: Optional[ResourceThresholds] = None,
                 monitoring_interval: float = 1.0,
                 alert_callbacks: Optional[List[Callable]] = None):
        
        self.thresholds = thresholds or ResourceThresholds()
        self.monitoring_interval = monitoring_interval
        self.alert_callbacks = alert_callbacks or []
        
        # 監控狀態
        self.monitoring_active = False
        self.monitoring_thread: Optional[threading.Thread] = None
        
        # 資源數據
        self.resource_history: deque = deque(maxlen=1000)
        self.active_alerts: Dict[str, ResourceAlert] = {}
        self.alert_history: List[ResourceAlert] = []
        
        # 組件
        self.limiter = AdaptiveResourceLimiter(self.thresholds)
        self.leak_detector = ResourceLeakDetector()
        
        # 容器管理
        self.active_containers: weakref.WeakSet = weakref.WeakSet()
        self.container_resources: Dict[str, Dict[str, Any]] = {}
        
        # Docker 客戶端
        if DOCKER_AVAILABLE:
            try:
                self.docker_client = docker.from_env()
            except Exception as e:
                logger.warning(f"無法連接 Docker: {e}")
                self.docker_client = None
        else:
            self.docker_client = None
    
    def start_monitoring(self) -> None:
        """啟動資源監控"""
        if self.monitoring_active:
            logger.warning("資源監控已在運行")
            return
        
        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        logger.info("資源監控已啟動")
    
    def stop_monitoring(self) -> None:
        """停止資源監控"""
        if not self.monitoring_active:
            return
        
        self.monitoring_active = False
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=5.0)
        
        logger.info("資源監控已停止")
    
    def _monitoring_loop(self) -> None:
        """監控循環"""
        logger.info(f"資源監控循環啟動，間隔: {self.monitoring_interval}s")
        
        while self.monitoring_active:
            try:
                # 收集資源數據
                snapshot = self._collect_resource_snapshot()
                self.resource_history.append(snapshot)
                
                # 檢查告警條件
                self._check_alert_conditions(snapshot)
                
                # 動態調整資源限制
                self.limiter.adjust_limits_based_on_usage(snapshot)
                
                # 檢查資源洩漏
                leaks = self.leak_detector.check_for_leaks(snapshot)
                for leak in leaks:
                    self._handle_resource_leak(leak)
                
                time.sleep(self.monitoring_interval)
                
            except Exception as e:
                logger.error(f"資源監控錯誤: {e}")
                time.sleep(self.monitoring_interval * 2)
    
    def _collect_resource_snapshot(self) -> ResourceSnapshot:
        """收集資源快照"""
        # 系統資源
        memory = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=0.1)
        
        # Docker 容器數量
        active_containers = 0
        if self.docker_client:
            try:
                containers = self.docker_client.containers.list()
                active_containers = len(containers)
                
                # 更新容器資源使用
                self._update_container_resources(containers)
            except Exception as e:
                logger.warning(f"無法獲取容器信息: {e}")
        
        # 磁盤使用
        disk_usage = 0.0
        try:
            disk = psutil.disk_usage('/')
            disk_usage = (disk.used / disk.total) * 100
        except Exception:
            pass
        
        return ResourceSnapshot(
            timestamp=time.time(),
            memory_percent=memory.percent,
            memory_used_mb=memory.used / (1024 * 1024),
            memory_available_mb=memory.available / (1024 * 1024),
            cpu_percent=cpu_percent,
            active_containers=active_containers,
            disk_usage_percent=disk_usage
        )
    
    def _update_container_resources(self, containers) -> None:
        """更新容器資源使用"""
        for container in containers:
            try:
                stats = container.stats(stream=False)
                container_id = container.id[:12]
                
                # 計算記憶體使用
                memory_usage = 0
                if 'memory' in stats:
                    memory_stats = stats['memory']
                    if 'usage' in memory_stats:
                        memory_usage = memory_stats['usage'] / (1024 * 1024)  # MB
                
                # 計算 CPU 使用
                cpu_percent = 0.0
                if 'cpu_stats' in stats and 'precpu_stats' in stats:
                    cpu_stats = stats['cpu_stats']
                    precpu_stats = stats['precpu_stats']
                    
                    cpu_delta = cpu_stats['cpu_usage']['total_usage'] - precpu_stats['cpu_usage']['total_usage']
                    system_delta = cpu_stats['system_cpu_usage'] - precpu_stats['system_cpu_usage']
                    
                    if system_delta > 0:
                        cpu_percent = (cpu_delta / system_delta) * 100.0
                
                self.container_resources[container_id] = {
                    'memory_mb': memory_usage,
                    'cpu_percent': cpu_percent,
                    'status': container.status,
                    'last_updated': time.time()
                }
                
            except Exception as e:
                logger.debug(f"無法獲取容器 {container.id[:12]} 資源: {e}")
    
    def _check_alert_conditions(self, snapshot: ResourceSnapshot) -> None:
        """檢查告警條件"""
        current_time = time.time()
        
        # 記憶體告警
        self._check_memory_alerts(snapshot, current_time)
        
        # CPU 告警
        self._check_cpu_alerts(snapshot, current_time)
        
        # 容器數量告警
        self._check_container_alerts(snapshot, current_time)
        
        # 清理過期告警
        self._cleanup_expired_alerts(current_time)
    
    def _check_memory_alerts(self, snapshot: ResourceSnapshot, current_time: float) -> None:
        """檢查記憶體告警"""
        memory_percent = snapshot.memory_percent
        
        # 確定告警等級
        alert_level = None
        if memory_percent >= self.thresholds.memory_emergency_percent:
            alert_level = ResourceAlertLevel.EMERGENCY
        elif memory_percent >= self.thresholds.memory_critical_percent:
            alert_level = ResourceAlertLevel.CRITICAL
        elif memory_percent >= self.thresholds.memory_warning_percent:
            alert_level = ResourceAlertLevel.WARNING
        
        if alert_level:
            alert_id = f"memory_{alert_level.value}"
            
            # 避免重複告警
            if alert_id not in self.active_alerts:
                alert = ResourceAlert(
                    alert_id=alert_id,
                    resource_type=ResourceType.MEMORY,
                    alert_level=alert_level,
                    message=f"記憶體使用達到 {memory_percent:.1f}%",
                    timestamp=current_time,
                    current_value=memory_percent,
                    threshold_value=getattr(self.thresholds, f'memory_{alert_level.value}_percent')
                )
                
                self._trigger_alert(alert)
        else:
            # 清理記憶體相關的活躍告警
            memory_alerts = [k for k in self.active_alerts.keys() if k.startswith('memory_')]
            for alert_id in memory_alerts:
                self._clear_alert(alert_id)
    
    def _check_cpu_alerts(self, snapshot: ResourceSnapshot, current_time: float) -> None:
        """檢查 CPU 告警"""
        cpu_percent = snapshot.cpu_percent
        
        alert_level = None
        if cpu_percent >= self.thresholds.cpu_emergency_percent:
            alert_level = ResourceAlertLevel.EMERGENCY
        elif cpu_percent >= self.thresholds.cpu_critical_percent:
            alert_level = ResourceAlertLevel.CRITICAL
        elif cpu_percent >= self.thresholds.cpu_warning_percent:
            alert_level = ResourceAlertLevel.WARNING
        
        if alert_level:
            alert_id = f"cpu_{alert_level.value}"
            
            if alert_id not in self.active_alerts:
                alert = ResourceAlert(
                    alert_id=alert_id,
                    resource_type=ResourceType.CPU,
                    alert_level=alert_level,
                    message=f"CPU 使用達到 {cpu_percent:.1f}%",
                    timestamp=current_time,
                    current_value=cpu_percent,
                    threshold_value=getattr(self.thresholds, f'cpu_{alert_level.value}_percent')
                )
                
                self._trigger_alert(alert)
        else:
            cpu_alerts = [k for k in self.active_alerts.keys() if k.startswith('cpu_')]
            for alert_id in cpu_alerts:
                self._clear_alert(alert_id)
    
    def _check_container_alerts(self, snapshot: ResourceSnapshot, current_time: float) -> None:
        """檢查容器數量告警"""
        container_count = snapshot.active_containers
        
        if container_count >= self.thresholds.max_containers:
            alert_id = "containers_limit"
            
            if alert_id not in self.active_alerts:
                alert = ResourceAlert(
                    alert_id=alert_id,
                    resource_type=ResourceType.CONTAINERS,
                    alert_level=ResourceAlertLevel.WARNING,
                    message=f"容器數量達到上限: {container_count}/{self.thresholds.max_containers}",
                    timestamp=current_time,
                    current_value=float(container_count),
                    threshold_value=float(self.thresholds.max_containers)
                )
                
                self._trigger_alert(alert)
        else:
            self._clear_alert("containers_limit")
    
    def _trigger_alert(self, alert: ResourceAlert) -> None:
        """觸發告警"""
        self.active_alerts[alert.alert_id] = alert
        self.alert_history.append(alert)
        
        logger.warning(f"資源告警: {alert.message}")
        
        # 呼叫告警回調函數
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"告警回調失敗: {e}")
        
        # 緊急情況自動處理
        if alert.alert_level == ResourceAlertLevel.EMERGENCY:
            self._handle_emergency_alert(alert)
    
    def _clear_alert(self, alert_id: str) -> None:
        """清除告警"""
        if alert_id in self.active_alerts:
            del self.active_alerts[alert_id]
            logger.info(f"告警已清除: {alert_id}")
    
    def _cleanup_expired_alerts(self, current_time: float) -> None:
        """清理過期告警"""
        expiry_time = 300  # 5分鐘
        expired_alerts = [
            alert_id for alert_id, alert in self.active_alerts.items()
            if current_time - alert.timestamp > expiry_time
        ]
        
        for alert_id in expired_alerts:
            self._clear_alert(alert_id)
    
    def _handle_emergency_alert(self, alert: ResourceAlert) -> None:
        """處理緊急告警"""
        logger.critical(f"緊急資源告警: {alert.message}")
        
        if alert.resource_type == ResourceType.MEMORY:
            # 強制記憶體清理
            self._emergency_memory_cleanup()
        elif alert.resource_type == ResourceType.CPU:
            # 強制降低並行度
            self._emergency_cpu_throttling()
    
    def _emergency_memory_cleanup(self) -> None:
        """緊急記憶體清理"""
        logger.warning("執行緊急記憶體清理")
        
        # 強制垃圾回收
        gc.collect()
        
        # 停止非關鍵容器
        if self.docker_client:
            try:
                containers = self.docker_client.containers.list()
                for container in containers[-2:]:  # 停止最後啟動的2個容器
                    try:
                        container.stop(timeout=5)
                        logger.info(f"緊急停止容器: {container.id[:12]}")
                    except Exception as e:
                        logger.error(f"緊急停止容器失敗: {e}")
            except Exception as e:
                logger.error(f"緊急記憶體清理失敗: {e}")
    
    def _emergency_cpu_throttling(self) -> None:
        """緊急 CPU 節流"""
        logger.warning("執行緊急 CPU 節流")
        
        # 減少資源限制
        self.limiter.current_limits['max_containers'] = max(1, self.limiter.current_limits['max_containers'] // 2)
        
        # 暫停非關鍵測試
        time.sleep(2)
    
    def _handle_resource_leak(self, leak: Dict[str, Any]) -> None:
        """處理資源洩漏"""
        logger.warning(f"檢測到資源洩漏: {leak['message']}")
        
        if leak['type'] == 'memory_leak':
            # 強制垃圾回收
            gc.collect()
            
            # 記錄洩漏事件
            self.leak_detector.detected_leaks.append({
                **leak,
                'timestamp': time.time(),
                'action_taken': 'forced_gc'
            })
            
        elif leak['type'] == 'long_running_container':
            # 嘗試停止長時間運行的容器
            container_id = leak['container_id']
            if self.docker_client:
                try:
                    container = self.docker_client.containers.get(container_id)
                    container.stop(timeout=10)
                    logger.info(f"停止長時間運行的容器: {container_id}")
                except Exception as e:
                    logger.error(f"停止容器失敗: {e}")
    
    @contextmanager
    def resource_controlled_execution(self, test_name: str):
        """資源控制的執行上下文"""
        start_time = time.time()
        initial_snapshot = self._collect_resource_snapshot()
        
        # 檢查資源是否足夠
        if not self._check_resource_availability():
            raise RuntimeError("系統資源不足，無法執行測試")
        
        try:
            logger.debug(f"開始資源控制執行: {test_name}")
            yield
            
        finally:
            end_time = time.time()
            final_snapshot = self._collect_resource_snapshot()
            
            # 記錄資源使用統計
            self._record_execution_statistics(test_name, start_time, end_time, initial_snapshot, final_snapshot)
            
            logger.debug(f"完成資源控制執行: {test_name}, 耗時: {end_time - start_time:.2f}s")
    
    def _check_resource_availability(self) -> bool:
        """檢查資源可用性"""
        if not self.resource_history:
            return True
        
        latest_snapshot = self.resource_history[-1]
        
        # 檢查記憶體
        if latest_snapshot.memory_percent > self.thresholds.memory_critical_percent:
            logger.warning("記憶體使用過高，拒絕執行")
            return False
        
        # 檢查 CPU
        if latest_snapshot.cpu_percent > self.thresholds.cpu_critical_percent:
            logger.warning("CPU 使用過高，拒絕執行")
            return False
        
        # 檢查容器數量
        if latest_snapshot.active_containers >= self.thresholds.max_containers:
            logger.warning("容器數量達到上限，拒絕執行")
            return False
        
        return True
    
    def _record_execution_statistics(self, test_name: str, start_time: float, end_time: float,
                                   initial_snapshot: ResourceSnapshot, final_snapshot: ResourceSnapshot) -> None:
        """記錄執行統計"""
        duration = end_time - start_time
        memory_delta = final_snapshot.memory_used_mb - initial_snapshot.memory_used_mb
        cpu_avg = (initial_snapshot.cpu_percent + final_snapshot.cpu_percent) / 2
        
        stats = {
            'test_name': test_name,
            'duration_seconds': duration,
            'memory_delta_mb': memory_delta,
            'cpu_average_percent': cpu_avg,
            'initial_resources': initial_snapshot.to_dict(),
            'final_resources': final_snapshot.to_dict()
        }
        
        logger.debug(f"執行統計: {test_name} - 時間: {duration:.2f}s, 記憶體變化: {memory_delta:.1f}MB")
    
    def get_monitoring_summary(self) -> Dict[str, Any]:
        """獲取監控摘要"""
        if not self.resource_history:
            return {'error': '無監控數據'}
        
        recent_snapshots = list(self.resource_history)[-60:]  # 最近60個樣本
        
        return {
            'monitoring_status': 'active' if self.monitoring_active else 'inactive',
            'total_samples': len(self.resource_history),
            'monitoring_duration_minutes': (time.time() - self.resource_history[0].timestamp) / 60 if self.resource_history else 0,
            'current_resources': recent_snapshots[-1].to_dict() if recent_snapshots else None,
            'resource_averages': {
                'memory_percent': sum(s.memory_percent for s in recent_snapshots) / len(recent_snapshots),
                'cpu_percent': sum(s.cpu_percent for s in recent_snapshots) / len(recent_snapshots),
                'active_containers': sum(s.active_containers for s in recent_snapshots) / len(recent_snapshots)
            } if recent_snapshots else None,
            'active_alerts_count': len(self.active_alerts),
            'total_alerts': len(self.alert_history),
            'resource_limits': self.limiter.current_limits,
            'detected_leaks': len(self.leak_detector.detected_leaks)
        }
    
    def export_monitoring_data(self, output_file: Optional[str] = None) -> str:
        """導出監控數據"""
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"resource_monitoring_data_{timestamp}.json"
        
        data = {
            'export_metadata': {
                'timestamp': datetime.now().isoformat(),
                'total_samples': len(self.resource_history),
                'monitoring_duration_seconds': (time.time() - self.resource_history[0].timestamp) if self.resource_history else 0
            },
            'resource_snapshots': [s.to_dict() for s in self.resource_history],
            'alert_history': [a.to_dict() for a in self.alert_history],
            'resource_limits': self.limiter.current_limits,
            'adjustment_history': self.limiter.adjustment_history,
            'detected_leaks': self.leak_detector.detected_leaks,
            'monitoring_summary': self.get_monitoring_summary()
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"監控數據已導出: {output_file}")
        return output_file


# 使用範例和工廠函數
def create_ci_resource_monitor() -> AdvancedResourceMonitor:
    """創建 CI 環境的資源監控器"""
    thresholds = ResourceThresholds.for_ci_environment()
    
    def alert_handler(alert: ResourceAlert):
        print(f"🚨 資源告警: {alert.message} (等級: {alert.alert_level.value})")
    
    monitor = AdvancedResourceMonitor(
        thresholds=thresholds,
        monitoring_interval=0.5,  # CI 環境更頻繁監控
        alert_callbacks=[alert_handler]
    )
    
    return monitor


def create_development_resource_monitor() -> AdvancedResourceMonitor:
    """創建開發環境的資源監控器"""
    return AdvancedResourceMonitor(
        thresholds=ResourceThresholds(),
        monitoring_interval=1.0
    )