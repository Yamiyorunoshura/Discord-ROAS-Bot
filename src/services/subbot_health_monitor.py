"""
SubBot健康檢查和監控系統
Task ID: 3 - 子機器人聊天功能和管理系統開發

這個模組提供：
- 多層健康檢查機制
- 實時監控和指標收集
- 智能告警和通知系統
- 系統診斷和故障排查
- 性能基準測試和報告
"""

import asyncio
import logging
import time
import psutil
from typing import Dict, Any, Optional, List, Callable, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
import statistics
from abc import ABC, abstractmethod

logger = logging.getLogger('services.subbot_monitor')


class HealthStatus(Enum):
    """健康狀態"""
    HEALTHY = "healthy"         # 健康
    WARNING = "warning"         # 警告
    CRITICAL = "critical"       # 危險
    DOWN = "down"              # 停機
    UNKNOWN = "unknown"        # 未知


class AlertLevel(Enum):
    """告警級別"""
    INFO = "info"              # 信息
    WARNING = "warning"        # 警告
    ERROR = "error"           # 錯誤
    CRITICAL = "critical"     # 危險


class MetricType(Enum):
    """指標類型"""
    COUNTER = "counter"        # 計數器
    GAUGE = "gauge"           # 儀表
    HISTOGRAM = "histogram"   # 直方圖
    SUMMARY = "summary"       # 摘要


@dataclass
class HealthCheckResult:
    """健康檢查結果"""
    check_name: str
    status: HealthStatus
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    response_time: float = 0.0  # 毫秒
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典"""
        return {
            'check_name': self.check_name,
            'status': self.status.value,
            'message': self.message,
            'details': self.details,
            'timestamp': self.timestamp.isoformat(),
            'response_time': self.response_time
        }


@dataclass
class Metric:
    """指標數據"""
    name: str
    value: Union[int, float]
    metric_type: MetricType
    tags: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典"""
        return {
            'name': self.name,
            'value': self.value,
            'type': self.metric_type.value,
            'tags': self.tags,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class Alert:
    """告警數據"""
    alert_id: str
    level: AlertLevel
    title: str
    message: str
    source: str
    tags: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典"""
        return {
            'alert_id': self.alert_id,
            'level': self.level.value,
            'title': self.title,
            'message': self.message,
            'source': self.source,
            'tags': self.tags,
            'timestamp': self.timestamp.isoformat(),
            'resolved': self.resolved,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None
        }


class HealthCheck(ABC):
    """健康檢查基礎類別"""
    
    def __init__(self, name: str, timeout: int = 30):
        self.name = name
        self.timeout = timeout
        self.enabled = True
        self.logger = logging.getLogger(f'health.{name}')
    
    @abstractmethod
    async def check(self) -> HealthCheckResult:
        """執行健康檢查"""
        pass
    
    async def run_with_timeout(self) -> HealthCheckResult:
        """帶超時的健康檢查執行"""
        if not self.enabled:
            return HealthCheckResult(
                check_name=self.name,
                status=HealthStatus.UNKNOWN,
                message="健康檢查已禁用"
            )
        
        start_time = time.time()
        
        try:
            result = await asyncio.wait_for(self.check(), timeout=self.timeout)
            result.response_time = (time.time() - start_time) * 1000
            return result
            
        except asyncio.TimeoutError:
            return HealthCheckResult(
                check_name=self.name,
                status=HealthStatus.CRITICAL,
                message=f"健康檢查超時（{self.timeout}秒）",
                response_time=(time.time() - start_time) * 1000
            )
        except Exception as e:
            return HealthCheckResult(
                check_name=self.name,
                status=HealthStatus.CRITICAL,
                message=f"健康檢查異常: {str(e)}",
                response_time=(time.time() - start_time) * 1000
            )


class DatabaseHealthCheck(HealthCheck):
    """資料庫健康檢查"""
    
    def __init__(self, database_manager):
        super().__init__("database", timeout=10)
        self.db_manager = database_manager
    
    async def check(self) -> HealthCheckResult:
        """檢查資料庫連接和查詢性能"""
        try:
            # 測試連接
            start_time = time.time()
            result = await self.db_manager.fetchone("SELECT 1 as test")
            query_time = (time.time() - start_time) * 1000
            
            if result and result.get('test') == 1:
                if query_time > 1000:  # 超過1秒
                    return HealthCheckResult(
                        check_name=self.name,
                        status=HealthStatus.WARNING,
                        message=f"資料庫查詢較慢: {query_time:.2f}ms",
                        details={'query_time': query_time}
                    )
                else:
                    return HealthCheckResult(
                        check_name=self.name,
                        status=HealthStatus.HEALTHY,
                        message=f"資料庫連接正常，查詢時間: {query_time:.2f}ms",
                        details={'query_time': query_time}
                    )
            else:
                return HealthCheckResult(
                    check_name=self.name,
                    status=HealthStatus.CRITICAL,
                    message="資料庫查詢返回異常結果"
                )
                
        except Exception as e:
            return HealthCheckResult(
                check_name=self.name,
                status=HealthStatus.DOWN,
                message=f"資料庫連接失敗: {str(e)}"
            )


class SubBotInstanceHealthCheck(HealthCheck):
    """子機器人實例健康檢查"""
    
    def __init__(self, instance):
        super().__init__(f"subbot_{instance.bot_id}", timeout=15)
        self.instance = instance
    
    async def check(self) -> HealthCheckResult:
        """檢查子機器人實例狀態"""
        try:
            # 檢查實例基本狀態
            if not self.instance.is_healthy:
                return HealthCheckResult(
                    check_name=self.name,
                    status=HealthStatus.CRITICAL,
                    message="實例標記為不健康",
                    details={
                        'status': self.instance.status.value,
                        'circuit_breaker': self.instance.circuit_breaker.state.value,
                        'isolated_until': self.instance.isolation_until.isoformat() if self.instance.isolation_until else None
                    }
                )
            
            # 檢查Discord連接
            discord_status = await self._check_discord_connection()
            
            # 檢查消息處理能力
            processing_status = await self._check_message_processing()
            
            # 檢查資源使用情況
            resource_status = await self._check_resource_usage()
            
            # 綜合評估
            all_checks = [discord_status, processing_status, resource_status]
            critical_issues = [c for c in all_checks if c['status'] in [HealthStatus.CRITICAL, HealthStatus.DOWN]]
            warning_issues = [c for c in all_checks if c['status'] == HealthStatus.WARNING]
            
            if critical_issues:
                return HealthCheckResult(
                    check_name=self.name,
                    status=HealthStatus.CRITICAL,
                    message=f"檢測到 {len(critical_issues)} 個嚴重問題",
                    details={
                        'discord': discord_status,
                        'processing': processing_status,
                        'resources': resource_status,
                        'critical_count': len(critical_issues),
                        'warning_count': len(warning_issues)
                    }
                )
            elif warning_issues:
                return HealthCheckResult(
                    check_name=self.name,
                    status=HealthStatus.WARNING,
                    message=f"檢測到 {len(warning_issues)} 個警告",
                    details={
                        'discord': discord_status,
                        'processing': processing_status,
                        'resources': resource_status,
                        'warning_count': len(warning_issues)
                    }
                )
            else:
                return HealthCheckResult(
                    check_name=self.name,
                    status=HealthStatus.HEALTHY,
                    message="實例運行正常",
                    details={
                        'discord': discord_status,
                        'processing': processing_status,
                        'resources': resource_status,
                        'uptime': self.instance.uptime
                    }
                )
                
        except Exception as e:
            return HealthCheckResult(
                check_name=self.name,
                status=HealthStatus.CRITICAL,
                message=f"健康檢查異常: {str(e)}"
            )
    
    async def _check_discord_connection(self) -> Dict[str, Any]:
        """檢查Discord連接狀態"""
        try:
            if not self.instance.client:
                return {
                    'status': HealthStatus.DOWN,
                    'message': 'Discord客戶端不存在'
                }
            
            if self.instance.client.is_closed():
                return {
                    'status': HealthStatus.CRITICAL,
                    'message': 'Discord連接已關閉'
                }
            
            # 檢查延遲
            latency = self.instance.client.latency * 1000  # 轉換為毫秒
            
            if latency > 1000:
                return {
                    'status': HealthStatus.WARNING,
                    'message': f'Discord延遲較高: {latency:.2f}ms',
                    'latency': latency
                }
            elif latency > 2000:
                return {
                    'status': HealthStatus.CRITICAL,
                    'message': f'Discord延遲過高: {latency:.2f}ms',
                    'latency': latency
                }
            else:
                return {
                    'status': HealthStatus.HEALTHY,
                    'message': f'Discord連接正常，延遲: {latency:.2f}ms',
                    'latency': latency
                }
                
        except Exception as e:
            return {
                'status': HealthStatus.CRITICAL,
                'message': f'檢查Discord連接失敗: {str(e)}'
            }
    
    async def _check_message_processing(self) -> Dict[str, Any]:
        """檢查消息處理狀態"""
        try:
            queue_size = self.instance.message_queue.qsize()
            metrics = self.instance.metrics
            
            # 檢查消息佇列大小
            if queue_size > 100:
                return {
                    'status': HealthStatus.CRITICAL,
                    'message': f'消息佇列積壓嚴重: {queue_size}',
                    'queue_size': queue_size
                }
            elif queue_size > 50:
                return {
                    'status': HealthStatus.WARNING,
                    'message': f'消息佇列積壓: {queue_size}',
                    'queue_size': queue_size
                }
            
            # 檢查錯誤率
            total_messages = metrics.messages_processed
            error_rate = (metrics.errors_count / max(total_messages, 1)) * 100
            
            if error_rate > 10:
                return {
                    'status': HealthStatus.CRITICAL,
                    'message': f'錯誤率過高: {error_rate:.2f}%',
                    'error_rate': error_rate,
                    'total_messages': total_messages,
                    'errors': metrics.errors_count
                }
            elif error_rate > 5:
                return {
                    'status': HealthStatus.WARNING,
                    'message': f'錯誤率偏高: {error_rate:.2f}%',
                    'error_rate': error_rate,
                    'total_messages': total_messages,
                    'errors': metrics.errors_count
                }
            
            # 檢查回應時間
            if metrics.average_response_time > 3000:
                return {
                    'status': HealthStatus.WARNING,
                    'message': f'平均回應時間較慢: {metrics.average_response_time:.2f}ms',
                    'response_time': metrics.average_response_time
                }
            
            return {
                'status': HealthStatus.HEALTHY,
                'message': '消息處理正常',
                'queue_size': queue_size,
                'error_rate': error_rate,
                'response_time': metrics.average_response_time,
                'total_messages': total_messages
            }
            
        except Exception as e:
            return {
                'status': HealthStatus.CRITICAL,
                'message': f'檢查消息處理失敗: {str(e)}'
            }
    
    async def _check_resource_usage(self) -> Dict[str, Any]:
        """檢查資源使用情況"""
        try:
            # 檢查記憶體使用（簡化版本，實際可能需要更複雜的監控）
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            cpu_percent = process.cpu_percent()
            
            issues = []
            
            if memory_mb > 512:
                issues.append(f'記憶體使用過高: {memory_mb:.2f}MB')
            elif memory_mb > 256:
                issues.append(f'記憶體使用偏高: {memory_mb:.2f}MB')
            
            if cpu_percent > 80:
                issues.append(f'CPU使用過高: {cpu_percent:.2f}%')
            elif cpu_percent > 60:
                issues.append(f'CPU使用偏高: {cpu_percent:.2f}%')
            
            if len(issues) > 0:
                status = HealthStatus.WARNING if memory_mb <= 512 and cpu_percent <= 80 else HealthStatus.CRITICAL
                return {
                    'status': status,
                    'message': '; '.join(issues),
                    'memory_mb': memory_mb,
                    'cpu_percent': cpu_percent
                }
            else:
                return {
                    'status': HealthStatus.HEALTHY,
                    'message': '資源使用正常',
                    'memory_mb': memory_mb,
                    'cpu_percent': cpu_percent
                }
                
        except Exception as e:
            return {
                'status': HealthStatus.CRITICAL,
                'message': f'檢查資源使用失敗: {str(e)}'
            }


class SystemHealthCheck(HealthCheck):
    """系統健康檢查"""
    
    def __init__(self):
        super().__init__("system", timeout=30)
    
    async def check(self) -> HealthCheckResult:
        """檢查系統整體狀態"""
        try:
            # 檢查系統資源
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            cpu_percent = psutil.cpu_percent(interval=1)
            
            issues = []
            warnings = []
            
            # 記憶體檢查
            memory_percent = memory.percent
            if memory_percent > 90:
                issues.append(f'系統記憶體使用過高: {memory_percent:.1f}%')
            elif memory_percent > 80:
                warnings.append(f'系統記憶體使用偏高: {memory_percent:.1f}%')
            
            # 磁碟檢查
            disk_percent = disk.percent
            if disk_percent > 95:
                issues.append(f'磁碟空間不足: {disk_percent:.1f}%')
            elif disk_percent > 85:
                warnings.append(f'磁碟空間偏低: {disk_percent:.1f}%')
            
            # CPU檢查
            if cpu_percent > 95:
                issues.append(f'CPU使用率過高: {cpu_percent:.1f}%')
            elif cpu_percent > 85:
                warnings.append(f'CPU使用率偏高: {cpu_percent:.1f}%')
            
            # 檢查網絡連接
            network_status = await self._check_network()
            if network_status['status'] != HealthStatus.HEALTHY:
                if network_status['status'] == HealthStatus.CRITICAL:
                    issues.append(network_status['message'])
                else:
                    warnings.append(network_status['message'])
            
            details = {
                'memory_percent': memory_percent,
                'disk_percent': disk_percent,
                'cpu_percent': cpu_percent,
                'network': network_status
            }
            
            if issues:
                return HealthCheckResult(
                    check_name=self.name,
                    status=HealthStatus.CRITICAL,
                    message=f"系統存在嚴重問題: {'; '.join(issues)}",
                    details=details
                )
            elif warnings:
                return HealthCheckResult(
                    check_name=self.name,
                    status=HealthStatus.WARNING,
                    message=f"系統需要注意: {'; '.join(warnings)}",
                    details=details
                )
            else:
                return HealthCheckResult(
                    check_name=self.name,
                    status=HealthStatus.HEALTHY,
                    message="系統運行正常",
                    details=details
                )
                
        except Exception as e:
            return HealthCheckResult(
                check_name=self.name,
                status=HealthStatus.CRITICAL,
                message=f"系統檢查異常: {str(e)}"
            )
    
    async def _check_network(self) -> Dict[str, Any]:
        """檢查網絡連接"""
        try:
            # 檢查Discord API連接
            import aiohttp
            async with aiohttp.ClientSession() as session:
                start_time = time.time()
                async with session.get('https://discord.com/api/v10/gateway', timeout=5) as response:
                    response_time = (time.time() - start_time) * 1000
                    
                    if response.status == 200:
                        if response_time > 2000:
                            return {
                                'status': HealthStatus.WARNING,
                                'message': f'Discord API回應較慢: {response_time:.2f}ms',
                                'response_time': response_time
                            }
                        else:
                            return {
                                'status': HealthStatus.HEALTHY,
                                'message': f'網絡連接正常，Discord API回應: {response_time:.2f}ms',
                                'response_time': response_time
                            }
                    else:
                        return {
                            'status': HealthStatus.CRITICAL,
                            'message': f'Discord API回應異常: {response.status}',
                            'status_code': response.status
                        }
                        
        except asyncio.TimeoutError:
            return {
                'status': HealthStatus.CRITICAL,
                'message': '網絡連接超時'
            }
        except Exception as e:
            return {
                'status': HealthStatus.CRITICAL,
                'message': f'網絡檢查失敗: {str(e)}'
            }


class MetricCollector:
    """指標收集器"""
    
    def __init__(self, max_metrics: int = 10000):
        self.metrics: List[Metric] = []
        self.max_metrics = max_metrics
        self.collectors: Dict[str, Callable] = {}
        self.lock = asyncio.Lock()
    
    def register_collector(self, name: str, collector: Callable) -> None:
        """註冊指標收集器"""
        self.collectors[name] = collector
        logger.info(f"已註冊指標收集器: {name}")
    
    async def collect_all(self) -> List[Metric]:
        """收集所有指標"""
        collected_metrics = []
        
        for name, collector in self.collectors.items():
            try:
                if asyncio.iscoroutinefunction(collector):
                    metrics = await collector()
                else:
                    metrics = collector()
                
                if isinstance(metrics, list):
                    collected_metrics.extend(metrics)
                elif isinstance(metrics, Metric):
                    collected_metrics.append(metrics)
                    
            except Exception as e:
                logger.error(f"指標收集器 {name} 失敗: {e}")
        
        return collected_metrics
    
    async def add_metric(self, metric: Metric) -> None:
        """添加指標"""
        async with self.lock:
            self.metrics.append(metric)
            
            # 限制指標數量
            if len(self.metrics) > self.max_metrics:
                self.metrics = self.metrics[-self.max_metrics:]
    
    async def add_metrics(self, metrics: List[Metric]) -> None:
        """批量添加指標"""
        async with self.lock:
            self.metrics.extend(metrics)
            
            # 限制指標數量
            if len(self.metrics) > self.max_metrics:
                self.metrics = self.metrics[-self.max_metrics:]
    
    def get_metrics(
        self, 
        name_filter: Optional[str] = None,
        time_range: Optional[Tuple[datetime, datetime]] = None,
        limit: Optional[int] = None
    ) -> List[Metric]:
        """獲取指標數據"""
        filtered_metrics = self.metrics.copy()
        
        # 按名稱過濾
        if name_filter:
            filtered_metrics = [m for m in filtered_metrics if name_filter in m.name]
        
        # 按時間範圍過濾
        if time_range:
            start_time, end_time = time_range
            filtered_metrics = [
                m for m in filtered_metrics 
                if start_time <= m.timestamp <= end_time
            ]
        
        # 限制數量
        if limit:
            filtered_metrics = filtered_metrics[-limit:]
        
        return filtered_metrics
    
    def get_latest_value(self, metric_name: str) -> Optional[Union[int, float]]:
        """獲取指標最新值"""
        for metric in reversed(self.metrics):
            if metric.name == metric_name:
                return metric.value
        return None
    
    def get_metric_statistics(
        self, 
        metric_name: str,
        time_range: Optional[Tuple[datetime, datetime]] = None
    ) -> Dict[str, float]:
        """獲取指標統計資訊"""
        metrics = self.get_metrics(metric_name, time_range)
        
        if not metrics:
            return {}
        
        values = [m.value for m in metrics]
        
        return {
            'count': len(values),
            'min': min(values),
            'max': max(values),
            'avg': statistics.mean(values),
            'median': statistics.median(values),
            'std': statistics.stdev(values) if len(values) > 1 else 0.0
        }


class AlertManager:
    """告警管理器"""
    
    def __init__(self, max_alerts: int = 1000):
        self.alerts: List[Alert] = []
        self.max_alerts = max_alerts
        self.notification_handlers: List[Callable] = []
        self.alert_rules: Dict[str, Dict[str, Any]] = {}
        self.lock = asyncio.Lock()
    
    def add_notification_handler(self, handler: Callable) -> None:
        """添加通知處理器"""
        self.notification_handlers.append(handler)
        logger.info("已添加告警通知處理器")
    
    def add_alert_rule(
        self, 
        name: str, 
        condition: Callable,
        level: AlertLevel,
        title: str,
        message_template: str
    ) -> None:
        """添加告警規則"""
        self.alert_rules[name] = {
            'condition': condition,
            'level': level,
            'title': title,
            'message_template': message_template,
            'last_triggered': None,
            'cooldown': 300  # 5分鐘冷卻期
        }
        logger.info(f"已添加告警規則: {name}")
    
    async def check_alert_rules(self, metrics: List[Metric], health_results: List[HealthCheckResult]) -> None:
        """檢查告警規則"""
        for rule_name, rule in self.alert_rules.items():
            try:
                # 檢查冷卻期
                if (rule['last_triggered'] and 
                    (datetime.now() - rule['last_triggered']).total_seconds() < rule['cooldown']):
                    continue
                
                # 執行條件檢查
                if await self._evaluate_condition(rule['condition'], metrics, health_results):
                    alert = Alert(
                        alert_id=f"{rule_name}_{int(time.time())}",
                        level=rule['level'],
                        title=rule['title'],
                        message=rule['message_template'],
                        source=f"rule:{rule_name}"
                    )
                    
                    await self.trigger_alert(alert)
                    rule['last_triggered'] = datetime.now()
                    
            except Exception as e:
                logger.error(f"檢查告警規則 {rule_name} 失敗: {e}")
    
    async def _evaluate_condition(
        self, 
        condition: Callable,
        metrics: List[Metric],
        health_results: List[HealthCheckResult]
    ) -> bool:
        """評估告警條件"""
        try:
            if asyncio.iscoroutinefunction(condition):
                return await condition(metrics, health_results)
            else:
                return condition(metrics, health_results)
        except Exception as e:
            logger.error(f"評估告警條件失敗: {e}")
            return False
    
    async def trigger_alert(self, alert: Alert) -> None:
        """觸發告警"""
        async with self.lock:
            self.alerts.append(alert)
            
            # 限制告警數量
            if len(self.alerts) > self.max_alerts:
                self.alerts = self.alerts[-self.max_alerts:]
        
        logger.warning(f"觸發告警: {alert.title} - {alert.message}")
        
        # 發送通知
        for handler in self.notification_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(alert)
                else:
                    handler(alert)
            except Exception as e:
                logger.error(f"告警通知發送失敗: {e}")
    
    async def resolve_alert(self, alert_id: str) -> bool:
        """解決告警"""
        async with self.lock:
            for alert in self.alerts:
                if alert.alert_id == alert_id and not alert.resolved:
                    alert.resolved = True
                    alert.resolved_at = datetime.now()
                    logger.info(f"告警已解決: {alert_id}")
                    return True
        
        return False
    
    def get_active_alerts(self, level: Optional[AlertLevel] = None) -> List[Alert]:
        """獲取活躍告警"""
        active_alerts = [alert for alert in self.alerts if not alert.resolved]
        
        if level:
            active_alerts = [alert for alert in active_alerts if alert.level == level]
        
        return active_alerts
    
    def get_alert_statistics(self) -> Dict[str, Any]:
        """獲取告警統計"""
        total_alerts = len(self.alerts)
        active_alerts = len([a for a in self.alerts if not a.resolved])
        
        level_counts = {}
        for level in AlertLevel:
            level_counts[level.value] = len([
                a for a in self.alerts 
                if a.level == level and not a.resolved
            ])
        
        return {
            'total_alerts': total_alerts,
            'active_alerts': active_alerts,
            'resolved_alerts': total_alerts - active_alerts,
            'alerts_by_level': level_counts
        }


class HealthMonitor:
    """健康監控主服務"""
    
    def __init__(self, check_interval: int = 60):
        self.check_interval = check_interval
        self.health_checks: Dict[str, HealthCheck] = {}
        self.metric_collector = MetricCollector()
        self.alert_manager = AlertManager()
        
        # 運行狀態
        self.monitoring_task: Optional[asyncio.Task] = None
        self.running = False
        
        # 結果緩存
        self.latest_results: Dict[str, HealthCheckResult] = {}
        self.result_history: List[Tuple[datetime, Dict[str, HealthCheckResult]]] = []
        
        logger.info("健康監控服務已初始化")
    
    def register_health_check(self, health_check: HealthCheck) -> None:
        """註冊健康檢查"""
        self.health_checks[health_check.name] = health_check
        logger.info(f"已註冊健康檢查: {health_check.name}")
    
    def unregister_health_check(self, name: str) -> None:
        """取消註冊健康檢查"""
        if name in self.health_checks:
            del self.health_checks[name]
            logger.info(f"已取消註冊健康檢查: {name}")
    
    async def start_monitoring(self) -> None:
        """啟動監控"""
        if self.running:
            logger.warning("監控已在運行")
            return
        
        self.running = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("健康監控已啟動")
    
    async def stop_monitoring(self) -> None:
        """停止監控"""
        self.running = False
        
        if self.monitoring_task and not self.monitoring_task.done():
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        logger.info("健康監控已停止")
    
    async def _monitoring_loop(self) -> None:
        """監控循環"""
        while self.running:
            try:
                # 執行健康檢查
                await self._run_health_checks()
                
                # 收集指標
                metrics = await self.metric_collector.collect_all()
                await self.metric_collector.add_metrics(metrics)
                
                # 檢查告警規則
                health_results = list(self.latest_results.values())
                await self.alert_manager.check_alert_rules(metrics, health_results)
                
                # 等待下次檢查
                await asyncio.sleep(self.check_interval)
                
            except asyncio.CancelledError:
                logger.info("監控循環已取消")
                break
            except Exception as e:
                logger.error(f"監控循環發生錯誤: {e}")
                await asyncio.sleep(min(self.check_interval, 60))
    
    async def _run_health_checks(self) -> None:
        """執行健康檢查"""
        if not self.health_checks:
            return
        
        # 並行執行所有健康檢查
        tasks = [
            health_check.run_with_timeout()
            for health_check in self.health_checks.values()
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 處理結果
        current_results = {}
        for i, result in enumerate(results):
            check_name = list(self.health_checks.keys())[i]
            
            if isinstance(result, Exception):
                # 如果健康檢查本身出現異常
                result = HealthCheckResult(
                    check_name=check_name,
                    status=HealthStatus.CRITICAL,
                    message=f"健康檢查執行異常: {str(result)}"
                )
            
            current_results[check_name] = result
        
        # 更新結果
        self.latest_results = current_results
        self.result_history.append((datetime.now(), current_results.copy()))
        
        # 限制歷史記錄大小
        if len(self.result_history) > 1000:
            self.result_history = self.result_history[-1000:]
        
        # 記錄統計
        healthy_count = sum(1 for r in current_results.values() if r.status == HealthStatus.HEALTHY)
        warning_count = sum(1 for r in current_results.values() if r.status == HealthStatus.WARNING)
        critical_count = sum(1 for r in current_results.values() if r.status in [HealthStatus.CRITICAL, HealthStatus.DOWN])
        
        logger.debug(f"健康檢查完成: {healthy_count}正常, {warning_count}警告, {critical_count}危險")
    
    def get_system_health(self) -> Dict[str, Any]:
        """獲取系統健康狀況"""
        if not self.latest_results:
            return {
                'overall_status': HealthStatus.UNKNOWN.value,
                'message': '尚無健康檢查結果',
                'checks': {}
            }
        
        # 計算整體狀態
        statuses = [result.status for result in self.latest_results.values()]
        
        if any(status in [HealthStatus.CRITICAL, HealthStatus.DOWN] for status in statuses):
            overall_status = HealthStatus.CRITICAL
            message = "系統存在嚴重問題"
        elif any(status == HealthStatus.WARNING for status in statuses):
            overall_status = HealthStatus.WARNING
            message = "系統需要關注"
        elif all(status == HealthStatus.HEALTHY for status in statuses):
            overall_status = HealthStatus.HEALTHY
            message = "系統運行正常"
        else:
            overall_status = HealthStatus.UNKNOWN
            message = "系統狀態未知"
        
        return {
            'overall_status': overall_status.value,
            'message': message,
            'checks': {
                name: result.to_dict()
                for name, result in self.latest_results.items()
            },
            'summary': {
                'total_checks': len(self.latest_results),
                'healthy': sum(1 for r in self.latest_results.values() if r.status == HealthStatus.HEALTHY),
                'warning': sum(1 for r in self.latest_results.values() if r.status == HealthStatus.WARNING),
                'critical': sum(1 for r in self.latest_results.values() if r.status in [HealthStatus.CRITICAL, HealthStatus.DOWN]),
                'unknown': sum(1 for r in self.latest_results.values() if r.status == HealthStatus.UNKNOWN)
            },
            'last_check': max((r.timestamp for r in self.latest_results.values()), default=datetime.now()).isoformat()
        }