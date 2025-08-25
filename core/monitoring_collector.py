#!/usr/bin/env python3
"""
監控收集器 - 收集系統和服務的監控數據，提供實時狀態報告
Task ID: 1 - ROAS Bot v2.4.3 Docker啟動系統修復

這個模組負責收集和分析系統監控指標，包括服務健康狀態、性能指標和資源使用情況。
"""

import asyncio
import json
import logging
import time
import subprocess
import psutil
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple
import sqlite3
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """健康狀態枚舉"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ServiceMetrics:
    """服務指標"""
    service_name: str
    status: HealthStatus
    response_time_ms: Optional[float]
    cpu_usage_percent: Optional[float]
    memory_usage_mb: Optional[float]
    error_rate: Optional[float]
    last_check: datetime
    uptime_seconds: Optional[float] = None
    restart_count: int = 0
    last_error: Optional[str] = None


@dataclass
class SystemMetrics:
    """系統指標"""
    timestamp: datetime
    cpu_usage_percent: float
    memory_usage_percent: float
    memory_available_gb: float
    disk_usage_percent: float
    disk_free_gb: float
    network_bytes_sent: int
    network_bytes_recv: int
    load_average: List[float]


@dataclass
class MonitoringReport:
    """監控報告"""
    timestamp: datetime
    overall_status: HealthStatus
    system_metrics: SystemMetrics
    service_metrics: List[ServiceMetrics]
    alerts: List[str]
    recommendations: List[str]
    summary: Dict[str, Any]


class MonitoringCollector:
    """
    監控收集器 - 收集系統和服務的監控數據，提供實時狀態報告
    
    負責：
    - 收集系統資源使用情況
    - 監控Docker容器狀態
    - 檢查服務健康狀態
    - 生成監控報告和告警
    - 存儲歷史監控數據
    """
    
    def __init__(self, project_root: Optional[Path] = None, db_path: Optional[Path] = None):
        self.project_root = project_root or Path.cwd()
        self.db_path = db_path or (self.project_root / 'data' / 'monitoring.db')
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # 監控配置
        self.check_interval = 30  # 秒
        self.alert_thresholds = {
            'cpu_usage': 80.0,      # CPU使用率 %
            'memory_usage': 85.0,   # 記憶體使用率 %
            'disk_usage': 90.0,     # 磁盘使用率 %
            'response_time': 5000,  # 響應時間 ms
            'error_rate': 5.0       # 錯誤率 %
        }
        
        self._ensure_database()
    
    def _ensure_database(self) -> None:
        """確保監控資料庫存在並初始化"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(str(self.db_path)) as conn:
            # 系統指標表
            conn.execute('''
                CREATE TABLE IF NOT EXISTS system_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    cpu_usage_percent REAL,
                    memory_usage_percent REAL,
                    memory_available_gb REAL,
                    disk_usage_percent REAL,
                    disk_free_gb REAL,
                    network_bytes_sent INTEGER,
                    network_bytes_recv INTEGER,
                    load_average_1m REAL,
                    load_average_5m REAL,
                    load_average_15m REAL
                )
            ''')
            
            # 服務指標表
            conn.execute('''
                CREATE TABLE IF NOT EXISTS service_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    service_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    response_time_ms REAL,
                    cpu_usage_percent REAL,
                    memory_usage_mb REAL,
                    error_rate REAL,
                    uptime_seconds REAL,
                    restart_count INTEGER DEFAULT 0,
                    last_error TEXT
                )
            ''')
            
            # 告警記錄表
            conn.execute('''
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    alert_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    service_name TEXT,
                    message TEXT NOT NULL,
                    resolved BOOLEAN DEFAULT FALSE,
                    resolved_at DATETIME
                )
            ''')
            
            conn.commit()
    
    async def collect_metrics(self) -> Dict[str, Any]:
        """
        收集完整的監控指標
        
        Returns:
            Dict[str, Any]: 監控指標數據
        """
        self.logger.debug("開始收集監控指標")
        
        try:
            # 並行收集系統和服務指標
            system_task = asyncio.create_task(self._collect_system_metrics())
            services_task = asyncio.create_task(self._collect_services_metrics())
            
            system_metrics, service_metrics = await asyncio.gather(
                system_task, services_task
            )
            
            # 分析整體健康狀態
            overall_status = self._analyze_overall_status(system_metrics, service_metrics)
            
            # 生成告警
            alerts = self._generate_alerts(system_metrics, service_metrics)
            
            # 生成建議
            recommendations = self._generate_recommendations(system_metrics, service_metrics)
            
            # 存儲指標到資料庫
            await self._store_metrics(system_metrics, service_metrics, alerts)
            
            # 構建結果
            result = {
                'timestamp': datetime.now(),
                'overall_status': overall_status.value,
                'system_metrics': asdict(system_metrics),
                'service_metrics': [asdict(sm) for sm in service_metrics],
                'alerts': alerts,
                'recommendations': recommendations,
                'summary': {
                    'total_services': len(service_metrics),
                    'healthy_services': len([s for s in service_metrics if s.status == HealthStatus.HEALTHY]),
                    'degraded_services': len([s for s in service_metrics if s.status == HealthStatus.DEGRADED]),
                    'unhealthy_services': len([s for s in service_metrics if s.status == HealthStatus.UNHEALTHY]),
                    'system_load': system_metrics.load_average[0] if system_metrics.load_average else 0
                }
            }
            
            self.logger.info(f"監控指標收集完成: {result['summary']}")
            return result
            
        except Exception as e:
            self.logger.error(f"監控指標收集失敗: {str(e)}", exc_info=True)
            return {
                'timestamp': datetime.now(),
                'error': str(e),
                'overall_status': HealthStatus.UNKNOWN.value
            }
    
    async def check_service_health(self, service: str) -> ServiceMetrics:
        """
        檢查特定服務的健康狀態
        
        Args:
            service: 服務名稱
            
        Returns:
            ServiceMetrics: 服務健康狀態指標
        """
        self.logger.debug(f"檢查服務健康狀態: {service}")
        
        start_time = time.time()
        
        try:
            # 檢查容器狀態
            container_info = await self._get_container_info(service)
            
            if not container_info:
                return ServiceMetrics(
                    service_name=service,
                    status=HealthStatus.UNHEALTHY,
                    response_time_ms=None,
                    cpu_usage_percent=None,
                    memory_usage_mb=None,
                    error_rate=None,
                    last_check=datetime.now(),
                    last_error="容器不存在或未運行"
                )
            
            # 計算響應時間
            response_time = (time.time() - start_time) * 1000
            
            # 獲取容器資源使用情況
            cpu_usage, memory_usage = await self._get_container_resources(container_info['container_id'])
            
            # 判斷健康狀態
            status = HealthStatus.HEALTHY
            if container_info.get('health_status') == 'unhealthy':
                status = HealthStatus.UNHEALTHY
            elif container_info.get('state') != 'running':
                status = HealthStatus.UNHEALTHY
            elif cpu_usage and cpu_usage > self.alert_thresholds['cpu_usage']:
                status = HealthStatus.DEGRADED
            elif memory_usage and memory_usage > 1000:  # 超過1GB認為異常
                status = HealthStatus.DEGRADED
            
            return ServiceMetrics(
                service_name=service,
                status=status,
                response_time_ms=response_time,
                cpu_usage_percent=cpu_usage,
                memory_usage_mb=memory_usage,
                error_rate=None,  # 需要從應用日誌分析
                last_check=datetime.now(),
                uptime_seconds=self._parse_uptime(container_info.get('status', ''))
            )
            
        except Exception as e:
            self.logger.error(f"服務 {service} 健康檢查失敗: {str(e)}")
            return ServiceMetrics(
                service_name=service,
                status=HealthStatus.UNKNOWN,
                response_time_ms=None,
                cpu_usage_percent=None,
                memory_usage_mb=None,
                error_rate=None,
                last_check=datetime.now(),
                last_error=str(e)
            )
    
    async def generate_report(self) -> MonitoringReport:
        """
        生成監控報告
        
        Returns:
            MonitoringReport: 完整的監控報告
        """
        self.logger.info("生成監控報告")
        
        metrics_data = await self.collect_metrics()
        
        # 轉換數據格式
        system_metrics_data = metrics_data.get('system_metrics', {})
        system_metrics = SystemMetrics(
            timestamp=system_metrics_data.get('timestamp', datetime.now()),
            cpu_usage_percent=system_metrics_data.get('cpu_usage_percent', 0.0),
            memory_usage_percent=system_metrics_data.get('memory_usage_percent', 0.0),
            memory_available_gb=system_metrics_data.get('memory_available_gb', 0.0),
            disk_usage_percent=system_metrics_data.get('disk_usage_percent', 0.0),
            disk_free_gb=system_metrics_data.get('disk_free_gb', 0.0),
            network_bytes_sent=system_metrics_data.get('network_bytes_sent', 0),
            network_bytes_recv=system_metrics_data.get('network_bytes_recv', 0),
            load_average=system_metrics_data.get('load_average', [0, 0, 0])
        )
        
        service_metrics = []
        for sm_data in metrics_data.get('service_metrics', []):
            service_metrics.append(ServiceMetrics(
                service_name=sm_data.get('service_name', 'unknown'),
                status=HealthStatus(sm_data.get('status', 'unknown')),
                response_time_ms=sm_data.get('response_time_ms'),
                cpu_usage_percent=sm_data.get('cpu_usage_percent'),
                memory_usage_mb=sm_data.get('memory_usage_mb'),
                error_rate=sm_data.get('error_rate'),
                last_check=sm_data.get('last_check', datetime.now()),
                uptime_seconds=sm_data.get('uptime_seconds'),
                restart_count=sm_data.get('restart_count', 0),
                last_error=sm_data.get('last_error')
            ))
        
        return MonitoringReport(
            timestamp=metrics_data.get('timestamp', datetime.now()),
            overall_status=HealthStatus(metrics_data.get('overall_status', 'unknown')),
            system_metrics=system_metrics,
            service_metrics=service_metrics,
            alerts=metrics_data.get('alerts', []),
            recommendations=metrics_data.get('recommendations', []),
            summary=metrics_data.get('summary', {})
        )
    
    async def collect_startup_performance_metrics(self) -> Dict[str, Any]:
        """
        收集啟動效能專用指標
        
        Returns:
            Dict[str, Any]: 啟動效能指標
        """
        self.logger.debug("收集啟動效能指標")
        
        try:
            startup_metrics = {
                'timestamp': datetime.now(),
                'docker_stats': await self._get_docker_startup_stats(),
                'container_ready_time': await self._measure_container_ready_time(),
                'resource_consumption': await self._get_startup_resource_consumption(),
                'health_check_performance': await self._analyze_health_check_performance(),
                'startup_bottlenecks': await self._identify_startup_bottlenecks()
            }
            
            return startup_metrics
            
        except Exception as e:
            self.logger.error(f"收集啟動效能指標失敗: {str(e)}", exc_info=True)
            return {
                'timestamp': datetime.now(),
                'error': str(e)
            }
    
    async def _get_docker_startup_stats(self) -> Dict[str, Any]:
        """獲取Docker啟動統計"""
        try:
            # 獲取所有容器的啟動時間
            result = subprocess.run(
                ['docker', 'ps', '--format', 'json'],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode != 0:
                return {'error': 'Docker命令執行失敗'}
            
            containers = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    try:
                        container_info = json.loads(line)
                        containers.append({
                            'name': container_info.get('Names', ''),
                            'status': container_info.get('Status', ''),
                            'created': container_info.get('CreatedAt', ''),
                            'state': container_info.get('State', '')
                        })
                    except json.JSONDecodeError:
                        continue
            
            return {
                'total_containers': len(containers),
                'running_containers': len([c for c in containers if 'Up' in c.get('status', '')]),
                'containers': containers
            }
            
        except Exception as e:
            self.logger.error(f"獲取Docker啟動統計失敗: {str(e)}")
            return {'error': str(e)}
    
    async def _measure_container_ready_time(self) -> Dict[str, Any]:
        """測量容器就緒時間"""
        try:
            ready_times = {}
            
            # 檢查每個主要服務的就緒時間
            services = ['discord-bot', 'redis', 'prometheus', 'grafana']
            
            for service in services:
                start_time = time.time()
                container_info = await self._get_container_info(service)
                
                if container_info:
                    # 簡化的就緒時間測量（實際應該解析容器啟動日誌）
                    ready_times[service] = {
                        'container_exists': True,
                        'state': container_info.get('state', 'unknown'),
                        'health_status': container_info.get('health_status', 'unknown'),
                        'check_duration_ms': (time.time() - start_time) * 1000
                    }
                else:
                    ready_times[service] = {
                        'container_exists': False,
                        'check_duration_ms': (time.time() - start_time) * 1000
                    }
            
            return ready_times
            
        except Exception as e:
            self.logger.error(f"測量容器就緒時間失敗: {str(e)}")
            return {'error': str(e)}
    
    async def _get_startup_resource_consumption(self) -> Dict[str, Any]:
        """獲取啟動期間資源消耗"""
        try:
            # 獲取當前系統資源使用情況
            cpu_usage = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage(str(self.project_root))
            
            # 獲取Docker容器資源使用
            container_resources = []
            
            result = subprocess.run(
                ['docker', 'stats', '--no-stream', '--format', 'json'],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line:
                        try:
                            stats = json.loads(line)
                            container_resources.append({
                                'name': stats.get('Name', ''),
                                'cpu_percent': stats.get('CPUPerc', '0%'),
                                'memory_usage': stats.get('MemUsage', '0B / 0B'),
                                'memory_percent': stats.get('MemPerc', '0%'),
                                'network_io': stats.get('NetIO', '0B / 0B'),
                                'block_io': stats.get('BlockIO', '0B / 0B')
                            })
                        except json.JSONDecodeError:
                            continue
            
            return {
                'system_cpu_percent': cpu_usage,
                'system_memory_percent': memory.percent,
                'system_memory_available_gb': memory.available / (1024**3),
                'system_disk_free_gb': disk.free / (1024**3),
                'container_resources': container_resources,
                'total_containers': len(container_resources)
            }
            
        except Exception as e:
            self.logger.error(f"獲取啟動資源消耗失敗: {str(e)}")
            return {'error': str(e)}
    
    async def _analyze_health_check_performance(self) -> Dict[str, Any]:
        """分析健康檢查效能"""
        try:
            health_performance = {}
            services = ['discord-bot', 'redis', 'prometheus', 'grafana']
            
            for service in services:
                start_time = time.time()
                service_metrics = await self.check_service_health(service)
                check_duration = (time.time() - start_time) * 1000
                
                health_performance[service] = {
                    'status': service_metrics.status.value,
                    'response_time_ms': service_metrics.response_time_ms,
                    'health_check_duration_ms': check_duration,
                    'last_error': service_metrics.last_error,
                    'is_optimal': check_duration < 5000 and service_metrics.status == HealthStatus.HEALTHY
                }
            
            # 計算整體健康檢查效能
            total_checks = len(health_performance)
            optimal_checks = sum(1 for perf in health_performance.values() if perf.get('is_optimal', False))
            
            return {
                'service_performance': health_performance,
                'overall_health_check_efficiency': (optimal_checks / total_checks) * 100 if total_checks > 0 else 0,
                'total_services_checked': total_checks,
                'optimal_services': optimal_checks
            }
            
        except Exception as e:
            self.logger.error(f"分析健康檢查效能失敗: {str(e)}")
            return {'error': str(e)}
    
    async def _identify_startup_bottlenecks(self) -> Dict[str, Any]:
        """識別啟動瓶頸"""
        try:
            bottlenecks = []
            
            # 檢查系統資源瓶頸
            cpu_usage = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage(str(self.project_root))
            
            if cpu_usage > 80:
                bottlenecks.append({
                    'type': 'cpu',
                    'severity': 'high',
                    'description': f'CPU使用率過高: {cpu_usage:.1f}%',
                    'recommendation': '考慮優化CPU密集型操作或增加CPU資源'
                })
            
            if memory.percent > 85:
                bottlenecks.append({
                    'type': 'memory',
                    'severity': 'high', 
                    'description': f'記憶體使用率過高: {memory.percent:.1f}%',
                    'recommendation': '檢查記憶體洩漏或增加記憶體容量'
                })
            
            if disk.free / (1024**3) < 2:
                bottlenecks.append({
                    'type': 'disk_space',
                    'severity': 'medium',
                    'description': f'磁盤空間不足: {disk.free / (1024**3):.1f}GB',
                    'recommendation': '清理磁盤空間或擴展存儲'
                })
            
            # 檢查Docker相關瓶頸
            try:
                result = subprocess.run(
                    ['docker', 'system', 'df'],
                    capture_output=True, text=True, timeout=30
                )
                
                if result.returncode == 0:
                    # 解析Docker空間使用情況（簡化處理）
                    if 'reclaimable' in result.stdout.lower():
                        bottlenecks.append({
                            'type': 'docker_storage',
                            'severity': 'low',
                            'description': 'Docker存在可回收空間',
                            'recommendation': '執行 docker system prune 清理未使用資源'
                        })
            except Exception:
                pass
            
            # 檢查網路相關瓶頸
            try:
                import socket
                test_ports = [6379, 8000, 3000, 9090]
                port_issues = []
                
                for port in test_ports:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        result = s.connect_ex(('localhost', port))
                        if result == 0:
                            # 端口已被佔用但不是我們的服務
                            port_issues.append(port)
                
                if port_issues:
                    bottlenecks.append({
                        'type': 'port_conflict',
                        'severity': 'medium',
                        'description': f'端口衝突: {port_issues}',
                        'recommendation': '檢查並關閉佔用端口的程序'
                    })
                    
            except Exception:
                pass
            
            return {
                'bottlenecks_found': len(bottlenecks),
                'bottlenecks': bottlenecks,
                'high_severity_count': len([b for b in bottlenecks if b['severity'] == 'high']),
                'medium_severity_count': len([b for b in bottlenecks if b['severity'] == 'medium']),
                'low_severity_count': len([b for b in bottlenecks if b['severity'] == 'low'])
            }
            
        except Exception as e:
            self.logger.error(f"識別啟動瓶頸失敗: {str(e)}")
            return {'error': str(e)}
    
    # === 內部方法 ===
    
    async def _collect_system_metrics(self) -> SystemMetrics:
        """收集系統指標"""
        try:
            # CPU使用率
            cpu_usage = psutil.cpu_percent(interval=1)
            
            # 記憶體使用情況
            memory = psutil.virtual_memory()
            memory_usage_percent = memory.percent
            memory_available_gb = memory.available / (1024**3)
            
            # 磁盤使用情況
            disk = psutil.disk_usage(str(self.project_root))
            disk_usage_percent = (disk.used / disk.total) * 100
            disk_free_gb = disk.free / (1024**3)
            
            # 網路使用情況
            network = psutil.net_io_counters()
            network_bytes_sent = network.bytes_sent
            network_bytes_recv = network.bytes_recv
            
            # 系統負載
            try:
                load_average = list(psutil.getloadavg())
            except (AttributeError, OSError):
                # Windows不支援getloadavg
                load_average = [0.0, 0.0, 0.0]
            
            return SystemMetrics(
                timestamp=datetime.now(),
                cpu_usage_percent=cpu_usage,
                memory_usage_percent=memory_usage_percent,
                memory_available_gb=memory_available_gb,
                disk_usage_percent=disk_usage_percent,
                disk_free_gb=disk_free_gb,
                network_bytes_sent=network_bytes_sent,
                network_bytes_recv=network_bytes_recv,
                load_average=load_average
            )
            
        except Exception as e:
            self.logger.error(f"系統指標收集失敗: {str(e)}")
            return SystemMetrics(
                timestamp=datetime.now(),
                cpu_usage_percent=0.0,
                memory_usage_percent=0.0,
                memory_available_gb=0.0,
                disk_usage_percent=0.0,
                disk_free_gb=0.0,
                network_bytes_sent=0,
                network_bytes_recv=0,
                load_average=[0.0, 0.0, 0.0]
            )
    
    async def _collect_services_metrics(self) -> List[ServiceMetrics]:
        """收集服務指標"""
        services = ['discord-bot', 'redis', 'prometheus', 'grafana']  # 主要服務
        service_metrics = []
        
        # 並行檢查所有服務
        tasks = [self.check_service_health(service) for service in services]
        service_metrics = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 過濾異常結果
        valid_metrics = []
        for metric in service_metrics:
            if isinstance(metric, ServiceMetrics):
                valid_metrics.append(metric)
            else:
                self.logger.warning(f"服務指標收集異常: {metric}")
        
        return valid_metrics
    
    async def _get_container_info(self, service_name: str) -> Optional[Dict[str, Any]]:
        """獲取容器資訊"""
        try:
            # 使用docker compose ps獲取容器資訊
            result = subprocess.run(
                ['docker', 'compose', 'ps', '--format', 'json', service_name],
                capture_output=True, text=True, timeout=10,
                cwd=self.project_root
            )
            
            if result.returncode != 0:
                return None
            
            for line in result.stdout.strip().split('\n'):
                if line:
                    try:
                        container_data = json.loads(line)
                        if container_data.get('Service') == service_name:
                            return {
                                'container_id': container_data.get('ID'),
                                'name': container_data.get('Name'),
                                'state': container_data.get('State'),
                                'health_status': container_data.get('Health'),
                                'status': container_data.get('Status'),
                                'ports': container_data.get('Publishers', [])
                            }
                    except json.JSONDecodeError:
                        continue
            
            return None
            
        except Exception as e:
            self.logger.error(f"獲取容器資訊失敗: {service_name}, {str(e)}")
            return None
    
    async def _get_container_resources(self, container_id: str) -> Tuple[Optional[float], Optional[float]]:
        """獲取容器資源使用情況"""
        try:
            result = subprocess.run(
                ['docker', 'stats', '--no-stream', '--format', 'json', container_id],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode != 0:
                return None, None
            
            stats_data = json.loads(result.stdout.strip())
            
            # 解析CPU使用率
            cpu_percent_str = stats_data.get('CPUPerc', '0%').rstrip('%')
            try:
                cpu_usage = float(cpu_percent_str)
            except ValueError:
                cpu_usage = None
            
            # 解析記憶體使用量
            memory_usage_str = stats_data.get('MemUsage', '0B / 0B')
            try:
                used_memory = memory_usage_str.split(' / ')[0]
                if used_memory.endswith('MiB'):
                    memory_usage = float(used_memory[:-3])
                elif used_memory.endswith('GiB'):
                    memory_usage = float(used_memory[:-3]) * 1024
                elif used_memory.endswith('KiB'):
                    memory_usage = float(used_memory[:-3]) / 1024
                else:
                    memory_usage = None
            except (ValueError, IndexError):
                memory_usage = None
            
            return cpu_usage, memory_usage
            
        except Exception as e:
            self.logger.error(f"獲取容器資源使用情況失敗: {container_id}, {str(e)}")
            return None, None
    
    def _parse_uptime(self, status: str) -> Optional[float]:
        """解析容器運行時間"""
        try:
            # 簡單解析Docker狀態字符串中的運行時間
            # 例如: "Up 2 hours", "Up 30 minutes", "Up 5 seconds"
            if 'Up' in status:
                parts = status.lower().split('up')[1].strip()
                # 這裡需要更複雜的解析邏輯
                # 簡化處理，返回None
                return None
            return None
        except Exception:
            return None
    
    def _analyze_overall_status(self, system_metrics: SystemMetrics, 
                               service_metrics: List[ServiceMetrics]) -> HealthStatus:
        """分析整體健康狀態"""
        # 檢查系統指標
        if (system_metrics.cpu_usage_percent > self.alert_thresholds['cpu_usage'] or
            system_metrics.memory_usage_percent > self.alert_thresholds['memory_usage'] or
            system_metrics.disk_usage_percent > self.alert_thresholds['disk_usage']):
            return HealthStatus.DEGRADED
        
        # 檢查服務狀態
        unhealthy_services = [s for s in service_metrics if s.status == HealthStatus.UNHEALTHY]
        degraded_services = [s for s in service_metrics if s.status == HealthStatus.DEGRADED]
        
        if unhealthy_services:
            return HealthStatus.UNHEALTHY
        elif degraded_services:
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY
    
    def _generate_alerts(self, system_metrics: SystemMetrics, 
                        service_metrics: List[ServiceMetrics]) -> List[str]:
        """生成告警"""
        alerts = []
        
        # 系統告警
        if system_metrics.cpu_usage_percent > self.alert_thresholds['cpu_usage']:
            alerts.append(f"CPU使用率過高: {system_metrics.cpu_usage_percent:.1f}%")
        
        if system_metrics.memory_usage_percent > self.alert_thresholds['memory_usage']:
            alerts.append(f"記憶體使用率過高: {system_metrics.memory_usage_percent:.1f}%")
        
        if system_metrics.disk_usage_percent > self.alert_thresholds['disk_usage']:
            alerts.append(f"磁盤使用率過高: {system_metrics.disk_usage_percent:.1f}%")
        
        # 服務告警
        for service in service_metrics:
            if service.status == HealthStatus.UNHEALTHY:
                alerts.append(f"服務不健康: {service.service_name}")
            elif service.status == HealthStatus.DEGRADED:
                alerts.append(f"服務性能下降: {service.service_name}")
            
            if service.response_time_ms and service.response_time_ms > self.alert_thresholds['response_time']:
                alerts.append(f"服務響應慢: {service.service_name} ({service.response_time_ms:.0f}ms)")
        
        return alerts
    
    def _generate_recommendations(self, system_metrics: SystemMetrics, 
                                service_metrics: List[ServiceMetrics]) -> List[str]:
        """生成優化建議"""
        recommendations = []
        
        # 系統優化建議
        if system_metrics.cpu_usage_percent > 70:
            recommendations.append("考慮優化CPU密集型操作或增加CPU資源")
        
        if system_metrics.memory_usage_percent > 80:
            recommendations.append("建議檢查記憶體洩漏或增加記憶體")
        
        if system_metrics.disk_free_gb < 5:
            recommendations.append("建議清理磁盤空間或擴展存儲")
        
        # 服務優化建議
        for service in service_metrics:
            if service.cpu_usage_percent and service.cpu_usage_percent > 50:
                recommendations.append(f"服務 {service.service_name} CPU使用率較高，考慮優化")
            
            if service.memory_usage_mb and service.memory_usage_mb > 500:
                recommendations.append(f"服務 {service.service_name} 記憶體使用較多，檢查是否正常")
        
        return recommendations
    
    async def _store_metrics(self, system_metrics: SystemMetrics, 
                           service_metrics: List[ServiceMetrics], 
                           alerts: List[str]) -> None:
        """存儲指標到資料庫"""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                # 存儲系統指標
                conn.execute('''
                    INSERT INTO system_metrics (
                        cpu_usage_percent, memory_usage_percent, memory_available_gb,
                        disk_usage_percent, disk_free_gb, network_bytes_sent, network_bytes_recv,
                        load_average_1m, load_average_5m, load_average_15m
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    system_metrics.cpu_usage_percent,
                    system_metrics.memory_usage_percent,
                    system_metrics.memory_available_gb,
                    system_metrics.disk_usage_percent,
                    system_metrics.disk_free_gb,
                    system_metrics.network_bytes_sent,
                    system_metrics.network_bytes_recv,
                    system_metrics.load_average[0],
                    system_metrics.load_average[1],
                    system_metrics.load_average[2]
                ))
                
                # 存儲服務指標
                for service in service_metrics:
                    conn.execute('''
                        INSERT INTO service_metrics (
                            service_name, status, response_time_ms, cpu_usage_percent,
                            memory_usage_mb, error_rate, uptime_seconds, restart_count, last_error
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        service.service_name,
                        service.status.value,
                        service.response_time_ms,
                        service.cpu_usage_percent,
                        service.memory_usage_mb,
                        service.error_rate,
                        service.uptime_seconds,
                        service.restart_count,
                        service.last_error
                    ))
                
                # 存儲告警
                for alert in alerts:
                    conn.execute('''
                        INSERT INTO alerts (alert_type, severity, message)
                        VALUES (?, ?, ?)
                    ''', ('system', 'warning', alert))
                
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"存儲指標失敗: {str(e)}")


# 工具函數
async def quick_health_check() -> Dict[str, Any]:
    """快速健康檢查"""
    collector = MonitoringCollector()
    return await collector.collect_metrics()


# 命令行介面
async def main():
    """主函數 - 用於獨立執行監控收集"""
    import argparse
    
    parser = argparse.ArgumentParser(description='ROAS Bot 監控收集工具')
    parser.add_argument('command', choices=['collect', 'report', 'health', 'startup-perf'],
                       help='執行的命令')
    parser.add_argument('--service', '-s', help='指定服務名稱（僅用於health命令）')
    parser.add_argument('--output', '-o', help='輸出檔案路徑')
    parser.add_argument('--verbose', '-v', action='store_true', help='詳細輸出')
    
    args = parser.parse_args()
    
    # 設置日誌
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # 創建監控收集器
    collector = MonitoringCollector()
    
    try:
        if args.command == 'collect':
            metrics = await collector.collect_metrics()
            if args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    json.dump(metrics, f, indent=2, ensure_ascii=False, default=str)
                print(f"監控數據已保存到: {args.output}")
            else:
                print(json.dumps(metrics, indent=2, ensure_ascii=False, default=str))
            return 0
            
        elif args.command == 'report':
            report = await collector.generate_report()
            print(f"\n{'='*60}")
            print("🔍 ROAS Bot v2.4.3 監控報告")
            print(f"{'='*60}")
            print(f"報告時間: {report.timestamp}")
            print(f"整體狀態: {report.overall_status.value.upper()}")
            print(f"\n系統指標:")
            print(f"  CPU使用率: {report.system_metrics.cpu_usage_percent:.1f}%")
            print(f"  記憶體使用率: {report.system_metrics.memory_usage_percent:.1f}%")
            print(f"  磁盤使用率: {report.system_metrics.disk_usage_percent:.1f}%")
            print(f"\n服務狀態:")
            for service in report.service_metrics:
                status_icon = {'healthy': '✅', 'degraded': '⚠️', 'unhealthy': '❌', 'unknown': '❓'}
                icon = status_icon.get(service.status.value, '❓')
                print(f"  {icon} {service.service_name}: {service.status.value}")
            
            if report.alerts:
                print(f"\n⚠️ 告警:")
                for alert in report.alerts:
                    print(f"  • {alert}")
            
            if report.recommendations:
                print(f"\n💡 建議:")
                for rec in report.recommendations:
                    print(f"  • {rec}")
            
            return 0 if report.overall_status == HealthStatus.HEALTHY else 1
            
        elif args.command == 'health':
            if args.service:
                metrics = await collector.check_service_health(args.service)
                status_icon = {'healthy': '✅', 'degraded': '⚠️', 'unhealthy': '❌', 'unknown': '❓'}
                icon = status_icon.get(metrics.status.value, '❓')
                print(f"{icon} {args.service}: {metrics.status.value}")
                if metrics.response_time_ms:
                    print(f"   響應時間: {metrics.response_time_ms:.0f}ms")
                if metrics.cpu_usage_percent:
                    print(f"   CPU使用率: {metrics.cpu_usage_percent:.1f}%")
                if metrics.memory_usage_mb:
                    print(f"   記憶體使用: {metrics.memory_usage_mb:.0f}MB")
                if metrics.last_error:
                    print(f"   錯誤訊息: {metrics.last_error}")
            else:
                metrics = await collector.collect_metrics()
                print(f"整體狀態: {metrics['overall_status'].upper()}")
                for service_data in metrics.get('service_metrics', []):
                    status_icon = {'healthy': '✅', 'degraded': '⚠️', 'unhealthy': '❌', 'unknown': '❓'}
                    icon = status_icon.get(service_data['status'], '❓')
                    print(f"  {icon} {service_data['service_name']}: {service_data['status']}")
            
            return 0
            
        elif args.command == 'startup-perf':
            startup_metrics = await collector.collect_startup_performance_metrics()
            
            print(f"\n{'='*60}")
            print("🚀 ROAS Bot v2.4.3 啟動效能報告")
            print(f"{'='*60}")
            print(f"報告時間: {startup_metrics.get('timestamp', 'Unknown')}")
            
            # Docker統計
            docker_stats = startup_metrics.get('docker_stats', {})
            if 'error' not in docker_stats:
                print(f"\n🐳 Docker統計:")
                print(f"  總容器數: {docker_stats.get('total_containers', 0)}")
                print(f"  運行中容器: {docker_stats.get('running_containers', 0)}")
            
            # 資源消耗
            resource_consumption = startup_metrics.get('resource_consumption', {})
            if 'error' not in resource_consumption:
                print(f"\n💾 資源使用:")
                print(f"  系統CPU: {resource_consumption.get('system_cpu_percent', 0):.1f}%")
                print(f"  系統記憶體: {resource_consumption.get('system_memory_percent', 0):.1f}%")
                print(f"  可用記憶體: {resource_consumption.get('system_memory_available_gb', 0):.1f}GB")
                print(f"  可用磁盤: {resource_consumption.get('system_disk_free_gb', 0):.1f}GB")
                print(f"  容器總數: {resource_consumption.get('total_containers', 0)}")
            
            # 健康檢查效能
            health_perf = startup_metrics.get('health_check_performance', {})
            if 'error' not in health_perf:
                print(f"\n🏥 健康檢查效能:")
                print(f"  整體效率: {health_perf.get('overall_health_check_efficiency', 0):.1f}%")
                print(f"  最佳服務: {health_perf.get('optimal_services', 0)}/{health_perf.get('total_services_checked', 0)}")
                
                service_perf = health_perf.get('service_performance', {})
                for service, perf in service_perf.items():
                    status_icon = '✅' if perf.get('is_optimal', False) else '⚠️'
                    print(f"  {status_icon} {service}: {perf.get('status', 'unknown')} ({perf.get('health_check_duration_ms', 0):.0f}ms)")
            
            # 瓶頸分析
            bottlenecks = startup_metrics.get('startup_bottlenecks', {})
            if 'error' not in bottlenecks:
                bottleneck_count = bottlenecks.get('bottlenecks_found', 0)
                print(f"\n🔍 瓶頸分析:")
                print(f"  發現瓶頸: {bottleneck_count}個")
                print(f"  高嚴重性: {bottlenecks.get('high_severity_count', 0)}")
                print(f"  中嚴重性: {bottlenecks.get('medium_severity_count', 0)}")
                print(f"  低嚴重性: {bottlenecks.get('low_severity_count', 0)}")
                
                if bottleneck_count > 0:
                    print(f"\n⚠️ 發現的瓶頸:")
                    for bottleneck in bottlenecks.get('bottlenecks', [])[:5]:  # 只顯示前5個
                        severity_icon = {'high': '🔴', 'medium': '🟡', 'low': '🔵'}
                        icon = severity_icon.get(bottleneck.get('severity', 'low'), '⚪')
                        print(f"  {icon} {bottleneck.get('description', 'Unknown issue')}")
                        print(f"     建議: {bottleneck.get('recommendation', 'No recommendation')}")
            
            if args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    json.dump(startup_metrics, f, indent=2, ensure_ascii=False, default=str)
                print(f"\n📄 詳細報告已保存: {args.output}")
            
            return 0
            
    except KeyboardInterrupt:
        print("\n操作已取消")
        return 130
    except Exception as e:
        print(f"❌ 執行失敗: {str(e)}")
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(asyncio.run(main()))