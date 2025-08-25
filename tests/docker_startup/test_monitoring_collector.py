"""
監控收集器單元測試套件
Task ID: 1 - ROAS Bot v2.4.3 Docker啟動系統修復

測試目標：F-4 監控和健康檢查系統
- 實作系統資源和服務狀態監控
- 配置健康檢查策略和告警機制
- 收集關鍵性能指標並生成報告
- 支援可配置的監控間隔和閾值

基於知識庫最佳實踐BP-003: 資料完整性保障模式
"""

import asyncio
import os
import json
import time
import psutil
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, NamedTuple
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import pytest
from dataclasses import dataclass, asdict
from enum import Enum


class AlertLevel(Enum):
    """告警級別"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ServiceStatus:
    """服務狀態數據類"""
    name: str
    status: str
    uptime: float
    response_time_ms: Optional[float] = None
    error_count: int = 0
    last_error: Optional[str] = None
    last_check: datetime = None
    
    def __post_init__(self):
        if self.last_check is None:
            self.last_check = datetime.now()


@dataclass
class SystemMetrics:
    """系統指標數據類"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_available_mb: float
    disk_usage_percent: float
    disk_free_mb: float
    network_io: Dict[str, int]
    process_count: int
    load_average: List[float]
    
    def to_dict(self):
        """轉換為字典格式"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'cpu_percent': self.cpu_percent,
            'memory_percent': self.memory_percent,
            'memory_available_mb': self.memory_available_mb,
            'disk_usage_percent': self.disk_usage_percent,
            'disk_free_mb': self.disk_free_mb,
            'network_io': self.network_io,
            'process_count': self.process_count,
            'load_average': self.load_average
        }


@dataclass
class MonitoringReport:
    """監控報告數據類"""
    report_id: str
    timestamp: datetime
    duration_seconds: float
    system_metrics: SystemMetrics
    service_statuses: List[ServiceStatus]
    alerts: List[Dict[str, Any]]
    summary: Dict[str, Any]
    
    def to_dict(self):
        """轉換為字典格式"""
        return {
            'report_id': self.report_id,
            'timestamp': self.timestamp.isoformat(),
            'duration_seconds': self.duration_seconds,
            'system_metrics': self.system_metrics.to_dict(),
            'service_statuses': [asdict(status) for status in self.service_statuses],
            'alerts': self.alerts,
            'summary': self.summary
        }


class MonitoringCollector:
    """監控收集器 - 收集系統和服務的監控數據，提供實時狀態報告"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        
        # 監控配置
        self.collection_interval = self.config.get('collection_interval', 30)  # 秒
        self.retention_hours = self.config.get('retention_hours', 24)
        self.alert_thresholds = self.config.get('alert_thresholds', {
            'cpu_percent': 80.0,
            'memory_percent': 85.0,
            'disk_usage_percent': 90.0,
            'response_time_ms': 5000,
            'error_rate': 0.05  # 5%
        })
        
        # 監控服務列表
        self.monitored_services = self.config.get('monitored_services', [
            'discord-bot', 'redis', 'nginx', 'prometheus', 'grafana'
        ])
        
        # 資料存儲
        self.metrics_history: List[SystemMetrics] = []
        self.service_history: Dict[str, List[ServiceStatus]] = {}
        self.alerts_history: List[Dict[str, Any]] = []
        
        # 運行狀態
        self.is_running = False
        self.last_collection_time = None
        
    async def collect_metrics(self) -> Dict[str, Any]:
        """
        收集系統和服務指標
        
        返回:
            Dict[str, Any]: 包含系統指標和服務狀態的完整指標數據
        """
        collection_start_time = datetime.now()
        
        try:
            # 收集系統指標
            system_metrics = await self._collect_system_metrics()
            
            # 收集服務狀態
            service_statuses = await self._collect_service_statuses()
            
            # 生成告警
            alerts = await self._generate_alerts(system_metrics, service_statuses)
            
            # 存儲歷史數據
            await self._store_metrics(system_metrics, service_statuses, alerts)
            
            # 清理過期數據
            await self._cleanup_expired_data()
            
            collection_end_time = datetime.now()
            collection_duration = (collection_end_time - collection_start_time).total_seconds()
            
            self.last_collection_time = collection_end_time
            
            return {
                'collection_time': collection_end_time.isoformat(),
                'collection_duration_ms': collection_duration * 1000,
                'system_metrics': system_metrics.to_dict(),
                'service_statuses': [asdict(status) for status in service_statuses],
                'alerts': alerts,
                'summary': {
                    'total_services': len(service_statuses),
                    'healthy_services': len([s for s in service_statuses if s.status == 'healthy']),
                    'alerts_count': len(alerts),
                    'system_health': self._calculate_system_health(system_metrics, alerts)
                }
            }
            
        except Exception as e:
            # 生成錯誤告警
            error_alert = {
                'id': f"collection_error_{int(time.time())}",
                'timestamp': datetime.now().isoformat(),
                'level': AlertLevel.ERROR.value,
                'source': 'MonitoringCollector',
                'message': f"指標收集失敗: {str(e)}",
                'details': {'exception_type': type(e).__name__}
            }
            self.alerts_history.append(error_alert)
            raise
    
    async def check_service_health(self, service: str) -> ServiceStatus:
        """
        檢查單個服務的健康狀態
        
        參數:
            service: 服務名稱
            
        返回:
            ServiceStatus: 服務狀態對象
        """
        check_start_time = time.time()
        
        try:
            # 根據服務類型執行不同的健康檢查
            if service in ['discord-bot', 'redis', 'nginx']:
                # Docker容器健康檢查
                status_info = await self._check_docker_service_health(service)
            elif service in ['prometheus', 'grafana']:
                # HTTP健康檢查
                status_info = await self._check_http_service_health(service)
            else:
                # 通用進程檢查
                status_info = await self._check_process_health(service)
            
            response_time = (time.time() - check_start_time) * 1000  # 毫秒
            
            service_status = ServiceStatus(
                name=service,
                status=status_info.get('status', 'unknown'),
                uptime=status_info.get('uptime', 0.0),
                response_time_ms=response_time,
                error_count=status_info.get('error_count', 0),
                last_error=status_info.get('last_error'),
                last_check=datetime.now()
            )
            
            return service_status
            
        except Exception as e:
            return ServiceStatus(
                name=service,
                status='error',
                uptime=0.0,
                response_time_ms=None,
                error_count=1,
                last_error=str(e),
                last_check=datetime.now()
            )
    
    async def generate_report(self, hours: int = 1) -> MonitoringReport:
        """
        生成監控報告
        
        參數:
            hours: 報告時間範圍（小時）
            
        返回:
            MonitoringReport: 監控報告對象
        """
        report_start_time = datetime.now()
        report_id = f"report_{report_start_time.strftime('%Y%m%d_%H%M%S')}"
        
        # 獲取時間範圍內的數據
        cutoff_time = report_start_time - timedelta(hours=hours)
        
        # 篩選歷史數據
        recent_metrics = [m for m in self.metrics_history if m.timestamp >= cutoff_time]
        recent_alerts = [a for a in self.alerts_history 
                        if datetime.fromisoformat(a['timestamp']) >= cutoff_time]
        
        # 收集最新的系統指標和服務狀態
        latest_system_metrics = recent_metrics[-1] if recent_metrics else await self._collect_system_metrics()
        latest_service_statuses = []
        
        for service in self.monitored_services:
            service_status = await self.check_service_health(service)
            latest_service_statuses.append(service_status)
        
        # 計算報告摘要
        summary = {
            'report_period_hours': hours,
            'data_points_count': len(recent_metrics),
            'total_alerts': len(recent_alerts),
            'alert_breakdown': self._get_alert_breakdown(recent_alerts),
            'average_cpu_usage': self._calculate_average_cpu(recent_metrics),
            'average_memory_usage': self._calculate_average_memory(recent_metrics),
            'service_availability': self._calculate_service_availability(hours),
            'system_health_score': self._calculate_system_health(latest_system_metrics, recent_alerts)
        }
        
        report_end_time = datetime.now()
        duration = (report_end_time - report_start_time).total_seconds()
        
        return MonitoringReport(
            report_id=report_id,
            timestamp=report_end_time,
            duration_seconds=duration,
            system_metrics=latest_system_metrics,
            service_statuses=latest_service_statuses,
            alerts=recent_alerts,
            summary=summary
        )
    
    async def start_monitoring(self) -> None:
        """開始監控循環"""
        if self.is_running:
            return
            
        self.is_running = True
        
        try:
            while self.is_running:
                await self.collect_metrics()
                await asyncio.sleep(self.collection_interval)
        except asyncio.CancelledError:
            self.is_running = False
            raise
        except Exception as e:
            self.is_running = False
            raise
    
    def stop_monitoring(self) -> None:
        """停止監控循環"""
        self.is_running = False
    
    def get_current_status(self) -> Dict[str, Any]:
        """獲取當前監控狀態"""
        return {
            'is_running': self.is_running,
            'last_collection_time': self.last_collection_time.isoformat() if self.last_collection_time else None,
            'metrics_history_size': len(self.metrics_history),
            'alerts_count': len(self.alerts_history),
            'monitored_services': self.monitored_services,
            'collection_interval': self.collection_interval
        }
    
    async def _collect_system_metrics(self) -> SystemMetrics:
        """收集系統指標"""
        try:
            # CPU使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # 記憶體使用情況
            memory = psutil.virtual_memory()
            memory_available_mb = memory.available / (1024 * 1024)
            
            # 磁盤使用情況
            disk = psutil.disk_usage('/')
            disk_free_mb = disk.free / (1024 * 1024)
            disk_usage_percent = (disk.used / disk.total) * 100
            
            # 網路I/O
            network_io = psutil.net_io_counters()
            network_stats = {
                'bytes_sent': network_io.bytes_sent,
                'bytes_recv': network_io.bytes_recv,
                'packets_sent': network_io.packets_sent,
                'packets_recv': network_io.packets_recv
            }
            
            # 進程數量
            process_count = len(psutil.pids())
            
            # 系統負載
            try:
                load_average = list(psutil.getloadavg())
            except AttributeError:
                # Windows系統不支援getloadavg
                load_average = [0.0, 0.0, 0.0]
            
            return SystemMetrics(
                timestamp=datetime.now(),
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_available_mb=memory_available_mb,
                disk_usage_percent=disk_usage_percent,
                disk_free_mb=disk_free_mb,
                network_io=network_stats,
                process_count=process_count,
                load_average=load_average
            )
            
        except Exception as e:
            # 返回預設值，避免監控完全失敗
            return SystemMetrics(
                timestamp=datetime.now(),
                cpu_percent=0.0,
                memory_percent=0.0,
                memory_available_mb=0.0,
                disk_usage_percent=0.0,
                disk_free_mb=0.0,
                network_io={},
                process_count=0,
                load_average=[0.0, 0.0, 0.0]
            )
    
    async def _collect_service_statuses(self) -> List[ServiceStatus]:
        """收集所有服務狀態"""
        service_statuses = []
        
        # 並發檢查所有服務
        tasks = [self.check_service_health(service) for service in self.monitored_services]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # 如果檢查失敗，創建錯誤狀態
                service_name = self.monitored_services[i]
                error_status = ServiceStatus(
                    name=service_name,
                    status='error',
                    uptime=0.0,
                    error_count=1,
                    last_error=str(result),
                    last_check=datetime.now()
                )
                service_statuses.append(error_status)
            else:
                service_statuses.append(result)
        
        return service_statuses
    
    async def _check_docker_service_health(self, service: str) -> Dict[str, Any]:
        """檢查Docker服務健康狀態"""
        try:
            # 執行docker inspect命令
            cmd = ['docker', 'inspect', f'{service}', '--format', '{{.State.Status}}']
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                status = stdout.decode().strip()
                uptime = 0.0  # 簡化處理
                
                return {
                    'status': 'healthy' if status == 'running' else 'unhealthy',
                    'uptime': uptime,
                    'error_count': 0
                }
            else:
                return {
                    'status': 'error',
                    'uptime': 0.0,
                    'error_count': 1,
                    'last_error': stderr.decode().strip()
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'uptime': 0.0,
                'error_count': 1,
                'last_error': str(e)
            }
    
    async def _check_http_service_health(self, service: str) -> Dict[str, Any]:
        """檢查HTTP服務健康狀態"""
        service_urls = {
            'prometheus': 'http://localhost:9090/-/healthy',
            'grafana': 'http://localhost:3000/api/health'
        }
        
        url = service_urls.get(service)
        if not url:
            return {'status': 'unknown', 'uptime': 0.0, 'error_count': 0}
        
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as response:
                    if response.status == 200:
                        return {
                            'status': 'healthy',
                            'uptime': 0.0,  # 簡化處理
                            'error_count': 0
                        }
                    else:
                        return {
                            'status': 'unhealthy',
                            'uptime': 0.0,
                            'error_count': 1,
                            'last_error': f'HTTP {response.status}'
                        }
                        
        except Exception as e:
            return {
                'status': 'error',
                'uptime': 0.0,
                'error_count': 1,
                'last_error': str(e)
            }
    
    async def _check_process_health(self, service: str) -> Dict[str, Any]:
        """檢查進程健康狀態"""
        try:
            # 簡化的進程檢查
            for proc in psutil.process_iter(['pid', 'name', 'create_time']):
                if service.lower() in proc.info['name'].lower():
                    uptime = time.time() - proc.info['create_time']
                    return {
                        'status': 'healthy',
                        'uptime': uptime,
                        'error_count': 0
                    }
            
            return {
                'status': 'stopped',
                'uptime': 0.0,
                'error_count': 0
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'uptime': 0.0,
                'error_count': 1,
                'last_error': str(e)
            }
    
    async def _generate_alerts(self, system_metrics: SystemMetrics, service_statuses: List[ServiceStatus]) -> List[Dict[str, Any]]:
        """生成告警"""
        alerts = []
        timestamp = datetime.now().isoformat()
        
        # 系統資源告警
        if system_metrics.cpu_percent > self.alert_thresholds['cpu_percent']:
            alerts.append({
                'id': f"cpu_high_{int(time.time())}",
                'timestamp': timestamp,
                'level': AlertLevel.WARNING.value,
                'source': 'system_metrics',
                'message': f'CPU使用率過高: {system_metrics.cpu_percent:.1f}%',
                'details': {'threshold': self.alert_thresholds['cpu_percent'], 'current': system_metrics.cpu_percent}
            })
        
        if system_metrics.memory_percent > self.alert_thresholds['memory_percent']:
            alerts.append({
                'id': f"memory_high_{int(time.time())}",
                'timestamp': timestamp,
                'level': AlertLevel.WARNING.value,
                'source': 'system_metrics',
                'message': f'記憶體使用率過高: {system_metrics.memory_percent:.1f}%',
                'details': {'threshold': self.alert_thresholds['memory_percent'], 'current': system_metrics.memory_percent}
            })
        
        if system_metrics.disk_usage_percent > self.alert_thresholds['disk_usage_percent']:
            alerts.append({
                'id': f"disk_high_{int(time.time())}",
                'timestamp': timestamp,
                'level': AlertLevel.CRITICAL.value,
                'source': 'system_metrics',
                'message': f'磁盤使用率過高: {system_metrics.disk_usage_percent:.1f}%',
                'details': {'threshold': self.alert_thresholds['disk_usage_percent'], 'current': system_metrics.disk_usage_percent}
            })
        
        # 服務狀態告警
        for service in service_statuses:
            if service.status in ['error', 'unhealthy', 'stopped']:
                level = AlertLevel.CRITICAL.value if service.status == 'error' else AlertLevel.WARNING.value
                alerts.append({
                    'id': f"service_{service.name}_{service.status}_{int(time.time())}",
                    'timestamp': timestamp,
                    'level': level,
                    'source': 'service_status',
                    'message': f'服務 {service.name} 狀態異常: {service.status}',
                    'details': {'service': service.name, 'status': service.status, 'last_error': service.last_error}
                })
            
            if (service.response_time_ms and 
                service.response_time_ms > self.alert_thresholds['response_time_ms']):
                alerts.append({
                    'id': f"response_time_{service.name}_{int(time.time())}",
                    'timestamp': timestamp,
                    'level': AlertLevel.WARNING.value,
                    'source': 'service_performance',
                    'message': f'服務 {service.name} 回應時間過長: {service.response_time_ms:.0f}ms',
                    'details': {'threshold': self.alert_thresholds['response_time_ms'], 'current': service.response_time_ms}
                })
        
        return alerts
    
    async def _store_metrics(self, system_metrics: SystemMetrics, service_statuses: List[ServiceStatus], alerts: List[Dict[str, Any]]) -> None:
        """存儲指標數據"""
        # 存儲系統指標
        self.metrics_history.append(system_metrics)
        
        # 存儲服務狀態
        for service_status in service_statuses:
            if service_status.name not in self.service_history:
                self.service_history[service_status.name] = []
            self.service_history[service_status.name].append(service_status)
        
        # 存儲告警
        self.alerts_history.extend(alerts)
    
    async def _cleanup_expired_data(self) -> None:
        """清理過期數據"""
        cutoff_time = datetime.now() - timedelta(hours=self.retention_hours)
        
        # 清理系統指標歷史
        self.metrics_history = [m for m in self.metrics_history if m.timestamp >= cutoff_time]
        
        # 清理服務狀態歷史
        for service_name in self.service_history:
            self.service_history[service_name] = [
                s for s in self.service_history[service_name] 
                if s.last_check >= cutoff_time
            ]
        
        # 清理告警歷史
        self.alerts_history = [
            a for a in self.alerts_history 
            if datetime.fromisoformat(a['timestamp']) >= cutoff_time
        ]
    
    def _calculate_system_health(self, system_metrics: SystemMetrics, alerts: List[Dict[str, Any]]) -> float:
        """計算系統健康分數 (0-100)"""
        score = 100.0
        
        # CPU懲罰
        if system_metrics.cpu_percent > 90:
            score -= 30
        elif system_metrics.cpu_percent > 70:
            score -= 15
        elif system_metrics.cpu_percent > 50:
            score -= 5
        
        # 記憶體懲罰
        if system_metrics.memory_percent > 95:
            score -= 25
        elif system_metrics.memory_percent > 80:
            score -= 10
        elif system_metrics.memory_percent > 60:
            score -= 3
        
        # 磁盤懲罰
        if system_metrics.disk_usage_percent > 95:
            score -= 20
        elif system_metrics.disk_usage_percent > 85:
            score -= 8
        
        # 告警懲罰
        critical_alerts = len([a for a in alerts if a['level'] == AlertLevel.CRITICAL.value])
        warning_alerts = len([a for a in alerts if a['level'] == AlertLevel.WARNING.value])
        
        score -= critical_alerts * 15
        score -= warning_alerts * 5
        
        return max(0.0, score)
    
    def _get_alert_breakdown(self, alerts: List[Dict[str, Any]]) -> Dict[str, int]:
        """獲取告警分類統計"""
        breakdown = {level.value: 0 for level in AlertLevel}
        for alert in alerts:
            level = alert.get('level', AlertLevel.INFO.value)
            if level in breakdown:
                breakdown[level] += 1
        return breakdown
    
    def _calculate_average_cpu(self, metrics: List[SystemMetrics]) -> float:
        """計算平均CPU使用率"""
        if not metrics:
            return 0.0
        return sum(m.cpu_percent for m in metrics) / len(metrics)
    
    def _calculate_average_memory(self, metrics: List[SystemMetrics]) -> float:
        """計算平均記憶體使用率"""
        if not metrics:
            return 0.0
        return sum(m.memory_percent for m in metrics) / len(metrics)
    
    def _calculate_service_availability(self, hours: int) -> Dict[str, float]:
        """計算服務可用性百分比"""
        availability = {}
        
        for service_name, statuses in self.service_history.items():
            if not statuses:
                availability[service_name] = 0.0
                continue
                
            # 簡化計算：健康狀態的比例
            healthy_count = len([s for s in statuses if s.status in ['healthy', 'running']])
            total_count = len(statuses)
            availability[service_name] = (healthy_count / total_count) * 100 if total_count > 0 else 0.0
        
        return availability


class TestMonitoringCollector:
    """監控收集器測試類"""
    
    @pytest.fixture
    def monitoring_collector(self):
        """測試固件：創建監控收集器實例"""
        config = {
            'collection_interval': 10,
            'retention_hours': 1,
            'alert_thresholds': {
                'cpu_percent': 80.0,
                'memory_percent': 85.0,
                'disk_usage_percent': 90.0,
                'response_time_ms': 5000,
                'error_rate': 0.05
            },
            'monitored_services': ['test-service-1', 'test-service-2']
        }
        return MonitoringCollector(config)
    
    @pytest.fixture
    def sample_system_metrics(self):
        """測試固件：示例系統指標"""
        return SystemMetrics(
            timestamp=datetime.now(),
            cpu_percent=45.5,
            memory_percent=60.2,
            memory_available_mb=2048.0,
            disk_usage_percent=75.8,
            disk_free_mb=5120.0,
            network_io={'bytes_sent': 1024, 'bytes_recv': 2048},
            process_count=150,
            load_average=[0.5, 0.8, 1.2]
        )
    
    @pytest.fixture
    def sample_service_status(self):
        """測試固件：示例服務狀態"""
        return ServiceStatus(
            name='test-service',
            status='healthy',
            uptime=3600.0,
            response_time_ms=120.5,
            error_count=0,
            last_check=datetime.now()
        )
    
    class TestMetricsCollection:
        """指標收集測試"""
        
        @pytest.mark.asyncio
        async def test_collect_metrics_success(self, monitoring_collector, sample_system_metrics):
            """測試：成功收集指標"""
            with patch.object(monitoring_collector, '_collect_system_metrics', 
                            return_value=sample_system_metrics), \
                 patch.object(monitoring_collector, '_collect_service_statuses',
                            return_value=[]), \
                 patch.object(monitoring_collector, '_generate_alerts',
                            return_value=[]), \
                 patch.object(monitoring_collector, '_store_metrics'), \
                 patch.object(monitoring_collector, '_cleanup_expired_data'):
                
                result = await monitoring_collector.collect_metrics()
                
                assert 'collection_time' in result
                assert 'system_metrics' in result
                assert 'service_statuses' in result
                assert 'alerts' in result
                assert 'summary' in result
                assert result['summary']['system_health'] >= 0
        
        @pytest.mark.asyncio
        async def test_collect_metrics_with_alerts(self, monitoring_collector, sample_system_metrics):
            """測試：收集指標並生成告警"""
            test_alerts = [{
                'id': 'test_alert',
                'level': AlertLevel.WARNING.value,
                'message': 'Test alert'
            }]
            
            with patch.object(monitoring_collector, '_collect_system_metrics',
                            return_value=sample_system_metrics), \
                 patch.object(monitoring_collector, '_collect_service_statuses',
                            return_value=[]), \
                 patch.object(monitoring_collector, '_generate_alerts',
                            return_value=test_alerts), \
                 patch.object(monitoring_collector, '_store_metrics'), \
                 patch.object(monitoring_collector, '_cleanup_expired_data'):
                
                result = await monitoring_collector.collect_metrics()
                
                assert len(result['alerts']) == 1
                assert result['alerts'][0]['id'] == 'test_alert'
                assert result['summary']['alerts_count'] == 1
        
        @pytest.mark.asyncio
        async def test_collect_metrics_exception_handling(self, monitoring_collector):
            """測試：收集指標時異常處理"""
            with patch.object(monitoring_collector, '_collect_system_metrics',
                            side_effect=Exception("Collection failed")):
                
                with pytest.raises(Exception, match="Collection failed"):
                    await monitoring_collector.collect_metrics()
                
                # 檢查是否生成了錯誤告警
                assert len(monitoring_collector.alerts_history) > 0
                error_alert = monitoring_collector.alerts_history[-1]
                assert error_alert['level'] == AlertLevel.ERROR.value
                assert 'Collection failed' in error_alert['message']
    
    class TestSystemMetricsCollection:
        """系統指標收集測試"""
        
        @pytest.mark.asyncio
        async def test_collect_system_metrics_success(self, monitoring_collector):
            """測試：成功收集系統指標"""
            with patch('psutil.cpu_percent', return_value=50.0), \
                 patch('psutil.virtual_memory') as mock_memory, \
                 patch('psutil.disk_usage') as mock_disk, \
                 patch('psutil.net_io_counters') as mock_network, \
                 patch('psutil.pids', return_value=list(range(100))), \
                 patch('psutil.getloadavg', return_value=(0.5, 1.0, 1.5)):
                
                # 配置mock對象
                mock_memory.return_value = Mock(percent=60.0, available=2048*1024*1024)
                mock_disk.return_value = Mock(used=1024*1024*1024, total=10*1024*1024*1024, free=9*1024*1024*1024)
                mock_network.return_value = Mock(bytes_sent=1000, bytes_recv=2000, packets_sent=10, packets_recv=20)
                
                metrics = await monitoring_collector._collect_system_metrics()
                
                assert metrics.cpu_percent == 50.0
                assert metrics.memory_percent == 60.0
                assert metrics.memory_available_mb == 2048.0
                assert metrics.process_count == 100
                assert metrics.load_average == [0.5, 1.0, 1.5]
        
        @pytest.mark.asyncio
        async def test_collect_system_metrics_exception(self, monitoring_collector):
            """測試：系統指標收集異常時返回預設值"""
            with patch('psutil.cpu_percent', side_effect=Exception("CPU error")):
                
                metrics = await monitoring_collector._collect_system_metrics()
                
                # 應該返回預設值而不是拋出異常
                assert metrics.cpu_percent == 0.0
                assert metrics.memory_percent == 0.0
                assert metrics.disk_usage_percent == 0.0
    
    class TestServiceHealthCheck:
        """服務健康檢查測試"""
        
        @pytest.mark.asyncio
        async def test_check_docker_service_health_running(self, monitoring_collector):
            """測試：Docker服務正在運行"""
            with patch('asyncio.create_subprocess_exec') as mock_subprocess:
                mock_proc = AsyncMock()
                mock_proc.communicate.return_value = (b'running\n', b'')
                mock_proc.returncode = 0
                mock_subprocess.return_value = mock_proc
                
                result = await monitoring_collector._check_docker_service_health('test-service')
                
                assert result['status'] == 'healthy'
                assert result['error_count'] == 0
        
        @pytest.mark.asyncio
        async def test_check_docker_service_health_stopped(self, monitoring_collector):
            """測試：Docker服務已停止"""
            with patch('asyncio.create_subprocess_exec') as mock_subprocess:
                mock_proc = AsyncMock()
                mock_proc.communicate.return_value = (b'exited\n', b'')
                mock_proc.returncode = 0
                mock_subprocess.return_value = mock_proc
                
                result = await monitoring_collector._check_docker_service_health('test-service')
                
                assert result['status'] == 'unhealthy'
                assert result['error_count'] == 0
        
        @pytest.mark.asyncio
        async def test_check_docker_service_health_error(self, monitoring_collector):
            """測試：Docker服務檢查出錯"""
            with patch('asyncio.create_subprocess_exec') as mock_subprocess:
                mock_proc = AsyncMock()
                mock_proc.communicate.return_value = (b'', b'container not found\n')
                mock_proc.returncode = 1
                mock_subprocess.return_value = mock_proc
                
                result = await monitoring_collector._check_docker_service_health('test-service')
                
                assert result['status'] == 'error'
                assert result['error_count'] == 1
                assert 'container not found' in result['last_error']
        
        @pytest.mark.asyncio
        async def test_check_service_health_integration(self, monitoring_collector):
            """測試：服務健康檢查整合測試"""
            with patch.object(monitoring_collector, '_check_docker_service_health',
                            return_value={'status': 'healthy', 'uptime': 3600, 'error_count': 0}):
                
                service_status = await monitoring_collector.check_service_health('test-service')
                
                assert service_status.name == 'test-service'
                assert service_status.status == 'healthy'
                assert service_status.uptime == 3600
                assert service_status.response_time_ms is not None
                assert service_status.response_time_ms >= 0
        
        @pytest.mark.asyncio
        async def test_check_service_health_exception(self, monitoring_collector):
            """測試：服務健康檢查異常處理"""
            with patch.object(monitoring_collector, '_check_docker_service_health',
                            side_effect=Exception("Health check failed")):
                
                service_status = await monitoring_collector.check_service_health('test-service')
                
                assert service_status.name == 'test-service'
                assert service_status.status == 'error'
                assert service_status.error_count == 1
                assert 'Health check failed' in service_status.last_error
        
        @pytest.mark.asyncio
        async def test_collect_service_statuses_success(self, monitoring_collector):
            """測試：收集所有服務狀態成功"""
            test_status = ServiceStatus(
                name='test-service',
                status='healthy',
                uptime=100.0
            )
            
            with patch.object(monitoring_collector, 'check_service_health',
                            return_value=test_status):
                
                statuses = await monitoring_collector._collect_service_statuses()
                
                assert len(statuses) == 2  # config中有2個服務
                assert all(s.status == 'healthy' for s in statuses)
        
        @pytest.mark.asyncio
        async def test_collect_service_statuses_with_exception(self, monitoring_collector):
            """測試：收集服務狀態時部分異常"""
            def side_effect(service):
                if service == 'test-service-1':
                    return ServiceStatus(name=service, status='healthy', uptime=100.0)
                else:
                    raise Exception("Service check failed")
            
            with patch.object(monitoring_collector, 'check_service_health',
                            side_effect=side_effect):
                
                statuses = await monitoring_collector._collect_service_statuses()
                
                assert len(statuses) == 2
                assert statuses[0].status == 'healthy'
                assert statuses[1].status == 'error'
    
    class TestAlertGeneration:
        """告警生成測試"""
        
        @pytest.mark.asyncio
        async def test_generate_alerts_cpu_threshold(self, monitoring_collector):
            """測試：CPU閾值告警"""
            high_cpu_metrics = SystemMetrics(
                timestamp=datetime.now(),
                cpu_percent=95.0,  # 超過80%閾值
                memory_percent=50.0,
                memory_available_mb=1000.0,
                disk_usage_percent=50.0,
                disk_free_mb=1000.0,
                network_io={},
                process_count=100,
                load_average=[1.0, 1.0, 1.0]
            )
            
            alerts = await monitoring_collector._generate_alerts(high_cpu_metrics, [])
            
            cpu_alerts = [a for a in alerts if 'CPU使用率過高' in a['message']]
            assert len(cpu_alerts) > 0
            assert cpu_alerts[0]['level'] == AlertLevel.WARNING.value
        
        @pytest.mark.asyncio
        async def test_generate_alerts_memory_threshold(self, monitoring_collector):
            """測試：記憶體閾值告警"""
            high_memory_metrics = SystemMetrics(
                timestamp=datetime.now(),
                cpu_percent=50.0,
                memory_percent=95.0,  # 超過85%閾值
                memory_available_mb=100.0,
                disk_usage_percent=50.0,
                disk_free_mb=1000.0,
                network_io={},
                process_count=100,
                load_average=[1.0, 1.0, 1.0]
            )
            
            alerts = await monitoring_collector._generate_alerts(high_memory_metrics, [])
            
            memory_alerts = [a for a in alerts if '記憶體使用率過高' in a['message']]
            assert len(memory_alerts) > 0
            assert memory_alerts[0]['level'] == AlertLevel.WARNING.value
        
        @pytest.mark.asyncio
        async def test_generate_alerts_disk_critical(self, monitoring_collector):
            """測試：磁盤使用率關鍵告警"""
            high_disk_metrics = SystemMetrics(
                timestamp=datetime.now(),
                cpu_percent=50.0,
                memory_percent=50.0,
                memory_available_mb=1000.0,
                disk_usage_percent=95.0,  # 超過90%閾值
                disk_free_mb=100.0,
                network_io={},
                process_count=100,
                load_average=[1.0, 1.0, 1.0]
            )
            
            alerts = await monitoring_collector._generate_alerts(high_disk_metrics, [])
            
            disk_alerts = [a for a in alerts if '磁盤使用率過高' in a['message']]
            assert len(disk_alerts) > 0
            assert disk_alerts[0]['level'] == AlertLevel.CRITICAL.value
        
        @pytest.mark.asyncio
        async def test_generate_alerts_service_error(self, monitoring_collector):
            """測試：服務錯誤告警"""
            error_service = ServiceStatus(
                name='error-service',
                status='error',
                uptime=0.0,
                error_count=1,
                last_error='Connection failed'
            )
            
            normal_metrics = SystemMetrics(
                timestamp=datetime.now(),
                cpu_percent=50.0,
                memory_percent=50.0,
                memory_available_mb=1000.0,
                disk_usage_percent=50.0,
                disk_free_mb=1000.0,
                network_io={},
                process_count=100,
                load_average=[1.0, 1.0, 1.0]
            )
            
            alerts = await monitoring_collector._generate_alerts(normal_metrics, [error_service])
            
            service_alerts = [a for a in alerts if 'error-service' in a['message']]
            assert len(service_alerts) > 0
            assert service_alerts[0]['level'] == AlertLevel.CRITICAL.value
        
        @pytest.mark.asyncio
        async def test_generate_alerts_response_time(self, monitoring_collector):
            """測試：回應時間告警"""
            slow_service = ServiceStatus(
                name='slow-service',
                status='healthy',
                uptime=100.0,
                response_time_ms=6000.0,  # 超過5000ms閾值
                error_count=0
            )
            
            normal_metrics = SystemMetrics(
                timestamp=datetime.now(),
                cpu_percent=50.0,
                memory_percent=50.0,
                memory_available_mb=1000.0,
                disk_usage_percent=50.0,
                disk_free_mb=1000.0,
                network_io={},
                process_count=100,
                load_average=[1.0, 1.0, 1.0]
            )
            
            alerts = await monitoring_collector._generate_alerts(normal_metrics, [slow_service])
            
            response_alerts = [a for a in alerts if '回應時間過長' in a['message']]
            assert len(response_alerts) > 0
            assert response_alerts[0]['level'] == AlertLevel.WARNING.value
    
    class TestReportGeneration:
        """報告生成測試"""
        
        @pytest.mark.asyncio
        async def test_generate_report_success(self, monitoring_collector, sample_system_metrics):
            """測試：成功生成監控報告"""
            # 準備測試數據
            monitoring_collector.metrics_history = [sample_system_metrics]
            monitoring_collector.alerts_history = [{
                'timestamp': datetime.now().isoformat(),
                'level': AlertLevel.WARNING.value,
                'message': 'Test alert'
            }]
            
            with patch.object(monitoring_collector, 'check_service_health') as mock_health_check:
                mock_health_check.return_value = ServiceStatus(
                    name='test-service',
                    status='healthy',
                    uptime=100.0
                )
                
                report = await monitoring_collector.generate_report(hours=1)
                
                assert report.report_id.startswith('report_')
                assert report.system_metrics is not None
                assert len(report.service_statuses) == 2  # config中的兩個服務
                assert len(report.alerts) > 0
                assert 'report_period_hours' in report.summary
                assert report.summary['report_period_hours'] == 1
        
        @pytest.mark.asyncio
        async def test_generate_report_empty_history(self, monitoring_collector, sample_system_metrics):
            """測試：生成報告時歷史數據為空"""
            with patch.object(monitoring_collector, '_collect_system_metrics',
                            return_value=sample_system_metrics), \
                 patch.object(monitoring_collector, 'check_service_health') as mock_health_check:
                
                mock_health_check.return_value = ServiceStatus(
                    name='test-service',
                    status='healthy',
                    uptime=100.0
                )
                
                report = await monitoring_collector.generate_report(hours=24)
                
                assert report.summary['data_points_count'] == 0
                assert report.summary['total_alerts'] == 0
                assert report.system_metrics is not None
        
        def test_report_to_dict(self, sample_system_metrics):
            """測試：報告轉換為字典"""
            report = MonitoringReport(
                report_id='test_report',
                timestamp=datetime.now(),
                duration_seconds=1.5,
                system_metrics=sample_system_metrics,
                service_statuses=[],
                alerts=[],
                summary={}
            )
            
            report_dict = report.to_dict()
            
            assert report_dict['report_id'] == 'test_report'
            assert 'timestamp' in report_dict
            assert 'system_metrics' in report_dict
            assert 'service_statuses' in report_dict
            assert isinstance(report_dict['system_metrics'], dict)
    
    class TestMonitoringLoop:
        """監控循環測試"""
        
        @pytest.mark.asyncio
        async def test_start_monitoring_loop(self, monitoring_collector):
            """測試：啟動監控循環"""
            collect_count = 0
            
            async def mock_collect():
                nonlocal collect_count
                collect_count += 1
                if collect_count >= 2:
                    monitoring_collector.stop_monitoring()
                return {}
            
            with patch.object(monitoring_collector, 'collect_metrics', side_effect=mock_collect), \
                 patch('asyncio.sleep'):
                
                await monitoring_collector.start_monitoring()
                
                assert collect_count >= 2
                assert monitoring_collector.is_running is False
        
        @pytest.mark.asyncio
        async def test_start_monitoring_already_running(self, monitoring_collector):
            """測試：監控已在運行時再次啟動"""
            monitoring_collector.is_running = True
            
            # 應該立即返回，不執行監控循環
            await monitoring_collector.start_monitoring()
            
            assert monitoring_collector.is_running is True
        
        @pytest.mark.asyncio
        async def test_monitoring_loop_exception_handling(self, monitoring_collector):
            """測試：監控循環異常處理"""
            with patch.object(monitoring_collector, 'collect_metrics',
                            side_effect=Exception("Collection error")):
                
                with pytest.raises(Exception, match="Collection error"):
                    await monitoring_collector.start_monitoring()
                
                assert monitoring_collector.is_running is False
        
        def test_stop_monitoring(self, monitoring_collector):
            """測試：停止監控"""
            monitoring_collector.is_running = True
            monitoring_collector.stop_monitoring()
            assert monitoring_collector.is_running is False
    
    class TestUtilityMethods:
        """工具方法測試"""
        
        def test_get_current_status(self, monitoring_collector):
            """測試：獲取當前監控狀態"""
            monitoring_collector.is_running = True
            monitoring_collector.last_collection_time = datetime.now()
            
            status = monitoring_collector.get_current_status()
            
            assert status['is_running'] is True
            assert 'last_collection_time' in status
            assert status['monitored_services'] == ['test-service-1', 'test-service-2']
            assert status['collection_interval'] == 10
        
        def test_calculate_system_health_perfect(self, monitoring_collector):
            """測試：計算完美系統健康分數"""
            perfect_metrics = SystemMetrics(
                timestamp=datetime.now(),
                cpu_percent=20.0,
                memory_percent=40.0,
                memory_available_mb=4000.0,
                disk_usage_percent=50.0,
                disk_free_mb=5000.0,
                network_io={},
                process_count=100,
                load_average=[0.5, 0.5, 0.5]
            )
            
            health_score = monitoring_collector._calculate_system_health(perfect_metrics, [])
            assert health_score == 100.0
        
        def test_calculate_system_health_with_issues(self, monitoring_collector):
            """測試：計算有問題的系統健康分數"""
            poor_metrics = SystemMetrics(
                timestamp=datetime.now(),
                cpu_percent=95.0,  # 高CPU
                memory_percent=98.0,  # 高記憶體
                memory_available_mb=100.0,
                disk_usage_percent=98.0,  # 高磁盤使用率
                disk_free_mb=100.0,
                network_io={},
                process_count=500,
                load_average=[3.0, 3.0, 3.0]
            )
            
            critical_alerts = [{
                'level': AlertLevel.CRITICAL.value,
                'message': 'Critical issue'
            }]
            
            health_score = monitoring_collector._calculate_system_health(poor_metrics, critical_alerts)
            assert health_score < 50.0  # 應該是很低的分數
        
        def test_get_alert_breakdown(self, monitoring_collector):
            """測試：獲取告警分類統計"""
            test_alerts = [
                {'level': AlertLevel.CRITICAL.value},
                {'level': AlertLevel.WARNING.value},
                {'level': AlertLevel.WARNING.value},
                {'level': AlertLevel.INFO.value}
            ]
            
            breakdown = monitoring_collector._get_alert_breakdown(test_alerts)
            
            assert breakdown[AlertLevel.CRITICAL.value] == 1
            assert breakdown[AlertLevel.WARNING.value] == 2
            assert breakdown[AlertLevel.INFO.value] == 1
            assert breakdown[AlertLevel.ERROR.value] == 0
        
        def test_calculate_average_cpu_empty(self, monitoring_collector):
            """測試：空指標列表的平均CPU計算"""
            assert monitoring_collector._calculate_average_cpu([]) == 0.0
        
        def test_calculate_average_cpu_with_data(self, monitoring_collector):
            """測試：有數據的平均CPU計算"""
            metrics = [
                SystemMetrics(datetime.now(), 50.0, 0, 0, 0, 0, {}, 0, []),
                SystemMetrics(datetime.now(), 60.0, 0, 0, 0, 0, {}, 0, []),
                SystemMetrics(datetime.now(), 70.0, 0, 0, 0, 0, {}, 0, [])
            ]
            
            avg_cpu = monitoring_collector._calculate_average_cpu(metrics)
            assert avg_cpu == 60.0
        
        def test_calculate_service_availability(self, monitoring_collector):
            """測試：計算服務可用性"""
            # 準備測試數據
            monitoring_collector.service_history = {
                'service1': [
                    ServiceStatus('service1', 'healthy', 100),
                    ServiceStatus('service1', 'healthy', 100),
                    ServiceStatus('service1', 'error', 0)
                ],
                'service2': [
                    ServiceStatus('service2', 'healthy', 100),
                    ServiceStatus('service2', 'healthy', 100)
                ]
            }
            
            availability = monitoring_collector._calculate_service_availability(1)
            
            assert availability['service1'] == pytest.approx(66.67, rel=0.1)  # 2/3 健康
            assert availability['service2'] == 100.0  # 全部健康
    
    class TestDataManagement:
        """數據管理測試"""
        
        @pytest.mark.asyncio
        async def test_store_metrics(self, monitoring_collector, sample_system_metrics, sample_service_status):
            """測試：存儲指標數據"""
            test_alerts = [{'id': 'test_alert', 'message': 'test'}]
            
            await monitoring_collector._store_metrics(
                sample_system_metrics, 
                [sample_service_status], 
                test_alerts
            )
            
            assert len(monitoring_collector.metrics_history) == 1
            assert sample_service_status.name in monitoring_collector.service_history
            assert len(monitoring_collector.service_history[sample_service_status.name]) == 1
            assert len(monitoring_collector.alerts_history) == 1
        
        @pytest.mark.asyncio
        async def test_cleanup_expired_data(self, monitoring_collector):
            """測試：清理過期數據"""
            # 添加一些過期的測試數據
            old_time = datetime.now() - timedelta(hours=25)  # 超過retention_hours(1小時)
            recent_time = datetime.now() - timedelta(minutes=30)  # 未過期
            
            # 過期的系統指標
            old_metrics = SystemMetrics(old_time, 50, 50, 1000, 50, 1000, {}, 100, [1,1,1])
            recent_metrics = SystemMetrics(recent_time, 60, 60, 1000, 60, 1000, {}, 100, [1,1,1])
            monitoring_collector.metrics_history = [old_metrics, recent_metrics]
            
            # 過期的服務狀態
            old_service = ServiceStatus('test', 'healthy', 100, last_check=old_time)
            recent_service = ServiceStatus('test', 'healthy', 100, last_check=recent_time)
            monitoring_collector.service_history['test'] = [old_service, recent_service]
            
            # 過期的告警
            old_alert = {'timestamp': old_time.isoformat(), 'message': 'old'}
            recent_alert = {'timestamp': recent_time.isoformat(), 'message': 'recent'}
            monitoring_collector.alerts_history = [old_alert, recent_alert]
            
            await monitoring_collector._cleanup_expired_data()
            
            # 檢查只保留未過期的數據
            assert len(monitoring_collector.metrics_history) == 1
            assert monitoring_collector.metrics_history[0].timestamp == recent_time
            
            assert len(monitoring_collector.service_history['test']) == 1
            assert monitoring_collector.service_history['test'][0].last_check == recent_time
            
            assert len(monitoring_collector.alerts_history) == 1
            assert monitoring_collector.alerts_history[0]['message'] == 'recent'
    
    class TestConfiguration:
        """配置測試"""
        
        def test_default_configuration(self):
            """測試：預設配置"""
            collector = MonitoringCollector()
            
            assert collector.collection_interval == 30
            assert collector.retention_hours == 24
            assert 'cpu_percent' in collector.alert_thresholds
            assert 'discord-bot' in collector.monitored_services
        
        def test_custom_configuration(self):
            """測試：自定義配置"""
            config = {
                'collection_interval': 60,
                'retention_hours': 48,
                'alert_thresholds': {'cpu_percent': 90.0},
                'monitored_services': ['custom-service']
            }
            
            collector = MonitoringCollector(config)
            
            assert collector.collection_interval == 60
            assert collector.retention_hours == 48
            assert collector.alert_thresholds['cpu_percent'] == 90.0
            assert collector.monitored_services == ['custom-service']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])