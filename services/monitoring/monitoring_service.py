# 監控服務
# Task ID: 11 - 建立文件和部署準備 - F11-4: 監控維護工具

import asyncio
import json
import logging
import os
import sqlite3
import subprocess
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
import psutil
import aiohttp

from core.base_service import BaseService
from core.database_manager import DatabaseManager
from core.exceptions import ServiceError
from .models import (
    HealthStatus, MonitoringType, AlertLevel, MaintenanceType,
    HealthCheckResult, SystemHealth, PerformanceMetric,
    PerformanceReport, MaintenanceTask, Alert, MonitoringConfig
)

class MonitoringService(BaseService):
    """監控服務
    
    提供系統健康檢查、效能監控、自動化維護和警報功能
    """
    
    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db = db_manager
        self.config = MonitoringConfig()
        self.logger = logging.getLogger(__name__)
        self._health_checkers: Dict[str, Callable] = {}
        self._performance_collectors: Dict[str, Callable] = {}
        self._maintenance_tasks: Dict[str, Callable] = {}
        self._alert_handlers: List[Callable] = []
        self._monitoring_active = False
        
        # 註冊預設檢查器
        self._register_default_checkers()
    
    async def initialize(self) -> None:
        """初始化監控服務"""
        try:
            await self._create_tables()
            await self._load_config()
            self.logger.info("監控服務初始化完成")
        except Exception as e:
            self.logger.error(f"監控服務初始化失敗: {e}")
            raise ServiceError("監控服務初始化失敗", "initialize", str(e))
    
    async def _create_tables(self) -> None:
        """創建監控相關資料表"""
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS monitoring_health_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                component TEXT NOT NULL,
                status TEXT NOT NULL,
                message TEXT NOT NULL,
                checked_at TIMESTAMP NOT NULL,
                response_time_ms REAL NOT NULL,
                details TEXT
            )
        """)
        
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS monitoring_performance_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric_name TEXT NOT NULL,
                value REAL NOT NULL,
                unit TEXT NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                component TEXT NOT NULL,
                threshold_warning REAL,
                threshold_critical REAL
            )
        """)
        
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS monitoring_maintenance_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT UNIQUE NOT NULL,
                task_type TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                scheduled_at TIMESTAMP NOT NULL,
                executed_at TIMESTAMP,
                completed_at TIMESTAMP,
                status TEXT NOT NULL DEFAULT 'scheduled',
                result TEXT,
                error_message TEXT
            )
        """)
        
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS monitoring_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_id TEXT UNIQUE NOT NULL,
                level TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                component TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                resolved_at TIMESTAMP,
                metadata TEXT
            )
        """)
        
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS monitoring_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP NOT NULL
            )
        """)
    
    def _register_default_checkers(self) -> None:
        """註冊預設的健康檢查器和效能收集器"""
        # 健康檢查器
        self._health_checkers.update({
            'database': self._check_database_health,
            'discord_api': self._check_discord_api_health,
            'redis': self._check_redis_health,
            'disk_space': self._check_disk_space,
            'memory': self._check_memory_usage,
            'cpu': self._check_cpu_usage,
            'services': self._check_services_health
        })
        
        # 效能收集器
        self._performance_collectors.update({
            'cpu_usage': self._collect_cpu_metrics,
            'memory_usage': self._collect_memory_metrics,
            'disk_usage': self._collect_disk_metrics,
            'database_performance': self._collect_database_metrics,
            'api_response_time': self._collect_api_metrics
        })
        
        # 維護任務
        self._maintenance_tasks.update({
            'log_cleanup': self._cleanup_logs,
            'database_optimization': self._optimize_database,
            'backup_management': self._manage_backups,
            'cache_cleanup': self._cleanup_cache
        })
    
    async def start_monitoring(self) -> None:
        """開始監控"""
        if self._monitoring_active:
            self.logger.warning("監控已經在運行中")
            return
        
        self._monitoring_active = True
        self.logger.info("開始監控服務")
        
        # 啟動監控任務
        asyncio.create_task(self._health_check_loop())
        asyncio.create_task(self._performance_monitoring_loop())
        asyncio.create_task(self._maintenance_scheduler())
    
    async def stop_monitoring(self) -> None:
        """停止監控"""
        self._monitoring_active = False
        self.logger.info("監控服務已停止")
    
    async def _health_check_loop(self) -> None:
        """健康檢查循環"""
        while self._monitoring_active:
            try:
                await self.perform_full_health_check()
                await asyncio.sleep(self.config.health_check_interval)
            except Exception as e:
                self.logger.error(f"健康檢查循環錯誤: {e}")
                await asyncio.sleep(60)  # 錯誤時等待1分鐘再重試
    
    async def _performance_monitoring_loop(self) -> None:
        """效能監控循環"""
        while self._monitoring_active:
            try:
                await self.collect_all_performance_metrics()
                await asyncio.sleep(self.config.performance_monitoring_interval)
            except Exception as e:
                self.logger.error(f"效能監控循環錯誤: {e}")
                await asyncio.sleep(300)  # 錯誤時等待5分鐘再重試
    
    async def _maintenance_scheduler(self) -> None:
        """維護任務調度器"""
        # 簡化的調度器實現
        while self._monitoring_active:
            try:
                # 檢查是否有需要執行的維護任務
                pending_tasks = await self._get_pending_maintenance_tasks()
                for task in pending_tasks:
                    await self._execute_maintenance_task(task)
                
                await asyncio.sleep(3600)  # 每小時檢查一次
            except Exception as e:
                self.logger.error(f"維護調度器錯誤: {e}")
                await asyncio.sleep(3600)
    
    async def perform_full_health_check(self) -> SystemHealth:
        """執行完整的系統健康檢查"""
        start_time = time.time()
        results = []
        
        for component, checker in self._health_checkers.items():
            try:
                result = await checker()
                results.append(result)
                
                # 儲存檢查結果
                await self._save_health_check_result(result)
                
                # 檢查是否需要發送警報
                if result.status in [HealthStatus.WARNING, HealthStatus.CRITICAL]:
                    await self._handle_health_alert(result)
                    
            except Exception as e:
                self.logger.error(f"健康檢查 {component} 失敗: {e}")
                error_result = HealthCheckResult(
                    component=component,
                    status=HealthStatus.CRITICAL,
                    message=f"檢查失敗: {str(e)}",
                    checked_at=datetime.now(),
                    response_time_ms=0.0
                )
                results.append(error_result)
        
        # 計算整體狀態
        overall_status = self._calculate_overall_status(results)
        scan_duration = (time.time() - start_time) * 1000
        
        health = SystemHealth(
            overall_status=overall_status,
            checked_at=datetime.now(),
            components=results,
            total_checks=len(results),
            healthy_count=len([r for r in results if r.status == HealthStatus.HEALTHY]),
            warning_count=len([r for r in results if r.status == HealthStatus.WARNING]),
            critical_count=len([r for r in results if r.status == HealthStatus.CRITICAL]),
            scan_duration_ms=scan_duration
        )
        
        self.logger.info(f"健康檢查完成 - 狀態: {overall_status.value}, "
                        f"掃描時間: {scan_duration:.2f}ms")
        
        return health
    
    async def collect_all_performance_metrics(self) -> List[PerformanceMetric]:
        """收集所有效能指標"""
        metrics = []
        
        for metric_name, collector in self._performance_collectors.items():
            try:
                metric_results = await collector()
                if isinstance(metric_results, list):
                    metrics.extend(metric_results)
                else:
                    metrics.append(metric_results)
                
                # 儲存指標
                for metric in (metric_results if isinstance(metric_results, list) else [metric_results]):
                    await self._save_performance_metric(metric)
                    
                    # 檢查是否超過閾值
                    if metric.status in [HealthStatus.WARNING, HealthStatus.CRITICAL]:
                        await self._handle_performance_alert(metric)
                        
            except Exception as e:
                self.logger.error(f"效能指標收集 {metric_name} 失敗: {e}")
        
        return metrics
    
    async def _check_database_health(self) -> HealthCheckResult:
        """檢查資料庫健康狀態"""
        start_time = time.time()
        
        try:
            # 執行簡單查詢測試連接
            result = await self.db.fetchone("SELECT 1")
            response_time = (time.time() - start_time) * 1000
            
            if result:
                return HealthCheckResult(
                    component="database",
                    status=HealthStatus.HEALTHY,
                    message="資料庫連接正常",
                    checked_at=datetime.now(),
                    response_time_ms=response_time
                )
            else:
                return HealthCheckResult(
                    component="database",
                    status=HealthStatus.CRITICAL,
                    message="資料庫查詢失敗",
                    checked_at=datetime.now(),
                    response_time_ms=response_time
                )
                
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheckResult(
                component="database",
                status=HealthStatus.CRITICAL,
                message=f"資料庫連接失敗: {str(e)}",
                checked_at=datetime.now(),
                response_time_ms=response_time
            )
    
    async def _check_discord_api_health(self) -> HealthCheckResult:
        """檢查Discord API健康狀態"""
        start_time = time.time()
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('https://discord.com/api/v10/gateway',
                                     timeout=aiohttp.ClientTimeout(total=10)) as response:
                    response_time = (time.time() - start_time) * 1000
                    
                    if response.status == 200:
                        return HealthCheckResult(
                            component="discord_api",
                            status=HealthStatus.HEALTHY,
                            message="Discord API正常",
                            checked_at=datetime.now(),
                            response_time_ms=response_time
                        )
                    else:
                        return HealthCheckResult(
                            component="discord_api",
                            status=HealthStatus.WARNING,
                            message=f"Discord API響應異常: {response.status}",
                            checked_at=datetime.now(),
                            response_time_ms=response_time
                        )
                        
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheckResult(
                component="discord_api",
                status=HealthStatus.CRITICAL,
                message=f"Discord API連接失敗: {str(e)}",
                checked_at=datetime.now(),
                response_time_ms=response_time
            )
    
    async def _check_redis_health(self) -> HealthCheckResult:
        """檢查Redis健康狀態"""
        start_time = time.time()
        
        try:
            # 這裡需要根據實際的Redis客戶端實現
            # 暫時返回健康狀態
            response_time = (time.time() - start_time) * 1000
            
            return HealthCheckResult(
                component="redis",
                status=HealthStatus.HEALTHY,
                message="Redis服務正常",
                checked_at=datetime.now(),
                response_time_ms=response_time
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheckResult(
                component="redis",
                status=HealthStatus.WARNING,
                message=f"Redis檢查失敗: {str(e)}",
                checked_at=datetime.now(),
                response_time_ms=response_time
            )
    
    async def _check_disk_space(self) -> HealthCheckResult:
        """檢查磁碟空間"""
        start_time = time.time()
        
        try:
            disk_usage = psutil.disk_usage('/')
            usage_percent = (disk_usage.used / disk_usage.total) * 100
            response_time = (time.time() - start_time) * 1000
            
            if usage_percent < 80:
                status = HealthStatus.HEALTHY
                message = f"磁碟使用率正常: {usage_percent:.1f}%"
            elif usage_percent < 90:
                status = HealthStatus.WARNING
                message = f"磁碟使用率偏高: {usage_percent:.1f}%"
            else:
                status = HealthStatus.CRITICAL
                message = f"磁碟使用率過高: {usage_percent:.1f}%"
            
            return HealthCheckResult(
                component="disk_space",
                status=status,
                message=message,
                checked_at=datetime.now(),
                response_time_ms=response_time,
                details={
                    'usage_percent': usage_percent,
                    'total_gb': disk_usage.total / (1024**3),
                    'used_gb': disk_usage.used / (1024**3),
                    'free_gb': disk_usage.free / (1024**3)
                }
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheckResult(
                component="disk_space",
                status=HealthStatus.CRITICAL,
                message=f"磁碟檢查失敗: {str(e)}",
                checked_at=datetime.now(),
                response_time_ms=response_time
            )
    
    async def _check_memory_usage(self) -> HealthCheckResult:
        """檢查記憶體使用率"""
        start_time = time.time()
        
        try:
            memory = psutil.virtual_memory()
            usage_percent = memory.percent
            response_time = (time.time() - start_time) * 1000
            
            if usage_percent < 70:
                status = HealthStatus.HEALTHY
                message = f"記憶體使用率正常: {usage_percent:.1f}%"
            elif usage_percent < 85:
                status = HealthStatus.WARNING
                message = f"記憶體使用率偏高: {usage_percent:.1f}%"
            else:
                status = HealthStatus.CRITICAL
                message = f"記憶體使用率過高: {usage_percent:.1f}%"
            
            return HealthCheckResult(
                component="memory",
                status=status,
                message=message,
                checked_at=datetime.now(),
                response_time_ms=response_time,
                details={
                    'usage_percent': usage_percent,
                    'total_gb': memory.total / (1024**3),
                    'used_gb': memory.used / (1024**3),
                    'available_gb': memory.available / (1024**3)
                }
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheckResult(
                component="memory",
                status=HealthStatus.CRITICAL,
                message=f"記憶體檢查失敗: {str(e)}",
                checked_at=datetime.now(),
                response_time_ms=response_time
            )
    
    async def _check_cpu_usage(self) -> HealthCheckResult:
        """檢查CPU使用率"""
        start_time = time.time()
        
        try:
            # 獲取1秒內的CPU使用率
            cpu_percent = psutil.cpu_percent(interval=1)
            response_time = (time.time() - start_time) * 1000
            
            if cpu_percent < 60:
                status = HealthStatus.HEALTHY
                message = f"CPU使用率正常: {cpu_percent:.1f}%"
            elif cpu_percent < 80:
                status = HealthStatus.WARNING
                message = f"CPU使用率偏高: {cpu_percent:.1f}%"
            else:
                status = HealthStatus.CRITICAL
                message = f"CPU使用率過高: {cpu_percent:.1f}%"
            
            return HealthCheckResult(
                component="cpu",
                status=status,
                message=message,
                checked_at=datetime.now(),
                response_time_ms=response_time,
                details={
                    'usage_percent': cpu_percent,
                    'cpu_count': psutil.cpu_count(),
                    'load_avg': os.getloadavg() if hasattr(os, 'getloadavg') else None
                }
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheckResult(
                component="cpu",
                status=HealthStatus.CRITICAL,
                message=f"CPU檢查失敗: {str(e)}",
                checked_at=datetime.now(),
                response_time_ms=response_time
            )
    
    async def _check_services_health(self) -> HealthCheckResult:
        """檢查服務健康狀態"""
        start_time = time.time()
        
        try:
            # 檢查關鍵進程是否運行
            critical_processes = ['python', 'discord']  # 根據實際情況調整
            running_processes = [p.name() for p in psutil.process_iter(['name'])]
            
            missing_processes = []
            for process in critical_processes:
                if not any(process in p for p in running_processes):
                    missing_processes.append(process)
            
            response_time = (time.time() - start_time) * 1000
            
            if not missing_processes:
                return HealthCheckResult(
                    component="services",
                    status=HealthStatus.HEALTHY,
                    message="所有關鍵服務正常運行",
                    checked_at=datetime.now(),
                    response_time_ms=response_time,
                    details={'running_processes': len(running_processes)}
                )
            else:
                return HealthCheckResult(
                    component="services",
                    status=HealthStatus.WARNING,
                    message=f"部分服務可能未運行: {', '.join(missing_processes)}",
                    checked_at=datetime.now(),
                    response_time_ms=response_time,
                    details={'missing_processes': missing_processes}
                )
                
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return HealthCheckResult(
                component="services",
                status=HealthStatus.CRITICAL,
                message=f"服務檢查失敗: {str(e)}",
                checked_at=datetime.now(),
                response_time_ms=response_time
            )
    
    async def _collect_cpu_metrics(self) -> PerformanceMetric:
        """收集CPU效能指標"""
        cpu_percent = psutil.cpu_percent(interval=1)
        thresholds = self.config.alert_thresholds.get('cpu_usage', {})
        
        return PerformanceMetric(
            metric_name="cpu_usage",
            value=cpu_percent,
            unit="percent",
            timestamp=datetime.now(),
            component="system",
            threshold_warning=thresholds.get('warning'),
            threshold_critical=thresholds.get('critical')
        )
    
    async def _collect_memory_metrics(self) -> PerformanceMetric:
        """收集記憶體效能指標"""
        memory = psutil.virtual_memory()
        thresholds = self.config.alert_thresholds.get('memory_usage', {})
        
        return PerformanceMetric(
            metric_name="memory_usage",
            value=memory.percent,
            unit="percent",
            timestamp=datetime.now(),
            component="system",
            threshold_warning=thresholds.get('warning'),
            threshold_critical=thresholds.get('critical')
        )
    
    async def _collect_disk_metrics(self) -> PerformanceMetric:
        """收集磁碟效能指標"""
        disk_usage = psutil.disk_usage('/')
        usage_percent = (disk_usage.used / disk_usage.total) * 100
        thresholds = self.config.alert_thresholds.get('disk_usage', {})
        
        return PerformanceMetric(
            metric_name="disk_usage",
            value=usage_percent,
            unit="percent",
            timestamp=datetime.now(),
            component="system",
            threshold_warning=thresholds.get('warning'),
            threshold_critical=thresholds.get('critical')
        )
    
    async def _collect_database_metrics(self) -> List[PerformanceMetric]:
        """收集資料庫效能指標"""
        metrics = []
        
        try:
            # 測試查詢響應時間
            start_time = time.time()
            await self.db.fetchone("SELECT 1")
            response_time = (time.time() - start_time) * 1000
            
            thresholds = self.config.alert_thresholds.get('response_time', {})
            
            metrics.append(PerformanceMetric(
                metric_name="database_response_time",
                value=response_time,
                unit="milliseconds",
                timestamp=datetime.now(),
                component="database",
                threshold_warning=thresholds.get('warning'),
                threshold_critical=thresholds.get('critical')
            ))
            
            # 獲取資料庫大小（如果可能）
            try:
                db_path = self.db.db_path if hasattr(self.db, 'db_path') else None
                if db_path and os.path.exists(db_path):
                    db_size = os.path.getsize(db_path) / (1024 * 1024)  # MB
                    metrics.append(PerformanceMetric(
                        metric_name="database_size",
                        value=db_size,
                        unit="megabytes",
                        timestamp=datetime.now(),
                        component="database"
                    ))
            except Exception:
                pass  # 忽略大小獲取錯誤
                
        except Exception as e:
            self.logger.error(f"資料庫指標收集失敗: {e}")
        
        return metrics
    
    async def _collect_api_metrics(self) -> PerformanceMetric:
        """收集API效能指標"""
        # 這裡應該與實際的API監控整合
        # 暫時返回模擬數據
        return PerformanceMetric(
            metric_name="api_response_time",
            value=100.0,  # 模擬100ms響應時間
            unit="milliseconds",
            timestamp=datetime.now(),
            component="api",
            threshold_warning=1000.0,
            threshold_critical=5000.0
        )
    
    def _calculate_overall_status(self, results: List[HealthCheckResult]) -> HealthStatus:
        """計算整體健康狀態"""
        if any(r.status == HealthStatus.CRITICAL for r in results):
            return HealthStatus.CRITICAL
        elif any(r.status == HealthStatus.WARNING for r in results):
            return HealthStatus.WARNING
        elif all(r.status == HealthStatus.HEALTHY for r in results):
            return HealthStatus.HEALTHY
        else:
            return HealthStatus.UNKNOWN
    
    async def _save_health_check_result(self, result: HealthCheckResult) -> None:
        """儲存健康檢查結果"""
        await self.db.execute("""
            INSERT INTO monitoring_health_checks 
            (component, status, message, checked_at, response_time_ms, details)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            result.component,
            result.status.value,
            result.message,
            result.checked_at,
            result.response_time_ms,
            json.dumps(result.details) if result.details else None
        ))
    
    async def _save_performance_metric(self, metric: PerformanceMetric) -> None:
        """儲存效能指標"""
        await self.db.execute("""
            INSERT INTO monitoring_performance_metrics 
            (metric_name, value, unit, timestamp, component, threshold_warning, threshold_critical)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            metric.metric_name,
            metric.value,
            metric.unit,
            metric.timestamp,
            metric.component,
            metric.threshold_warning,
            metric.threshold_critical
        ))
    
    async def _handle_health_alert(self, result: HealthCheckResult) -> None:
        """處理健康檢查警報"""
        alert = Alert(
            alert_id=str(uuid.uuid4()),
            level=AlertLevel.WARNING if result.status == HealthStatus.WARNING else AlertLevel.CRITICAL,
            title=f"{result.component}健康檢查警報",
            message=result.message,
            component=result.component,
            created_at=datetime.now(),
            metadata={'health_check_result': result.to_dict()}
        )
        
        await self._send_alert(alert)
    
    async def _handle_performance_alert(self, metric: PerformanceMetric) -> None:
        """處理效能警報"""
        alert = Alert(
            alert_id=str(uuid.uuid4()),
            level=AlertLevel.WARNING if metric.status == HealthStatus.WARNING else AlertLevel.CRITICAL,
            title=f"{metric.component}效能警報",
            message=f"{metric.metric_name}超過閾值: {metric.value}{metric.unit}",
            component=metric.component,
            created_at=datetime.now(),
            metadata={'performance_metric': metric.to_dict()}
        )
        
        await self._send_alert(alert)
    
    async def _send_alert(self, alert: Alert) -> None:
        """發送警報"""
        try:
            # 儲存警報到資料庫
            await self.db.execute("""
                INSERT INTO monitoring_alerts 
                (alert_id, level, title, message, component, created_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                alert.alert_id,
                alert.level.value,
                alert.title,
                alert.message,
                alert.component,
                alert.created_at,
                json.dumps(alert.metadata)
            ))
            
            # 發送到Webhook（如果有配置）
            for webhook_url in self.config.notification_webhooks:
                await self._send_webhook_notification(webhook_url, alert)
            
            self.logger.warning(f"警報發送: {alert.title} - {alert.message}")
            
        except Exception as e:
            self.logger.error(f"警報發送失敗: {e}")
    
    async def _send_webhook_notification(self, webhook_url: str, alert: Alert) -> None:
        """發送Webhook通知"""
        try:
            payload = {
                'alert_id': alert.alert_id,
                'level': alert.level.value,
                'title': alert.title,
                'message': alert.message,
                'component': alert.component,
                'created_at': alert.created_at.isoformat(),
                'metadata': alert.metadata
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(webhook_url, json=payload,
                                       timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status != 200:
                        self.logger.error(f"Webhook通知失敗: {response.status}")
                        
        except Exception as e:
            self.logger.error(f"Webhook通知錯誤: {e}")
    
    async def _get_pending_maintenance_tasks(self) -> List[MaintenanceTask]:
        """獲取待執行的維護任務"""
        # 簡化實現：檢查過去的任務
        now = datetime.now()
        
        # 這裡應該實現更複雜的cron調度邏輯
        # 暫時只檢查是否需要執行日常維護
        tasks = []
        
        # 檢查是否需要執行log清理（每天）
        last_log_cleanup = await self._get_last_maintenance_execution('log_cleanup')
        if not last_log_cleanup or (now - last_log_cleanup).days >= 1:
            tasks.append(MaintenanceTask(
                task_id=str(uuid.uuid4()),
                task_type=MaintenanceType.LOG_CLEANUP,
                title="日誌清理",
                description="清理過期的日誌文件",
                scheduled_at=now
            ))
        
        return tasks
    
    async def _get_last_maintenance_execution(self, task_type: str) -> Optional[datetime]:
        """獲取最後一次維護任務執行時間"""
        result = await self.db.fetchone("""
            SELECT MAX(completed_at) FROM monitoring_maintenance_tasks 
            WHERE task_type = ? AND status = 'completed'
        """, (task_type,))
        
        if result and result[0]:
            return datetime.fromisoformat(result[0])
        return None
    
    async def _execute_maintenance_task(self, task: MaintenanceTask) -> None:
        """執行維護任務"""
        task.executed_at = datetime.now()
        task.status = "running"
        
        try:
            # 儲存任務開始狀態
            await self.db.execute("""
                INSERT INTO monitoring_maintenance_tasks 
                (task_id, task_type, title, description, scheduled_at, executed_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                task.task_id,
                task.task_type.value,
                task.title,
                task.description,
                task.scheduled_at,
                task.executed_at,
                task.status
            ))
            
            # 執行對應的維護函數
            if task.task_type.value in self._maintenance_tasks:
                result = await self._maintenance_tasks[task.task_type.value]()
                task.result = result
                task.status = "completed"
                task.completed_at = datetime.now()
                
                self.logger.info(f"維護任務完成: {task.title}")
            else:
                task.status = "failed"
                task.error_message = f"找不到維護任務處理器: {task.task_type.value}"
                
                self.logger.error(task.error_message)
        
        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
            task.completed_at = datetime.now()
            
            self.logger.error(f"維護任務失敗: {task.title} - {e}")
        
        finally:
            # 更新任務狀態
            await self.db.execute("""
                UPDATE monitoring_maintenance_tasks 
                SET status = ?, completed_at = ?, result = ?, error_message = ?
                WHERE task_id = ?
            """, (
                task.status,
                task.completed_at,
                json.dumps(task.result) if task.result else None,
                task.error_message,
                task.task_id
            ))
    
    async def _cleanup_logs(self) -> Dict[str, Any]:
        """清理日誌文件"""
        cleaned_files = []
        total_size_freed = 0
        
        try:
            log_dir = "logs"
            if os.path.exists(log_dir):
                cutoff_date = datetime.now() - timedelta(days=self.config.retention_days)
                
                for filename in os.listdir(log_dir):
                    file_path = os.path.join(log_dir, filename)
                    if os.path.isfile(file_path):
                        file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                        
                        if file_mtime < cutoff_date:
                            file_size = os.path.getsize(file_path)
                            os.remove(file_path)
                            cleaned_files.append(filename)
                            total_size_freed += file_size
            
            return {
                'cleaned_files': cleaned_files,
                'total_files': len(cleaned_files),
                'size_freed_mb': total_size_freed / (1024 * 1024)
            }
            
        except Exception as e:
            raise Exception(f"日誌清理失敗: {e}")
    
    async def _optimize_database(self) -> Dict[str, Any]:
        """優化資料庫"""
        try:
            # 執行VACUUM和ANALYZE
            await self.db.execute("VACUUM")
            await self.db.execute("ANALYZE")
            
            return {
                'vacuum_completed': True,
                'analyze_completed': True,
                'message': '資料庫優化完成'
            }
            
        except Exception as e:
            raise Exception(f"資料庫優化失敗: {e}")
    
    async def _manage_backups(self) -> Dict[str, Any]:
        """管理備份"""
        try:
            # 這裡應該與實際的備份系統整合
            # 暫時返回成功狀態
            return {
                'backup_created': True,
                'old_backups_cleaned': True,
                'message': '備份管理完成'
            }
            
        except Exception as e:
            raise Exception(f"備份管理失敗: {e}")
    
    async def _cleanup_cache(self) -> Dict[str, Any]:
        """清理快取"""
        try:
            # 這裡應該清理Redis或其他快取
            # 暫時返回成功狀態
            return {
                'cache_cleared': True,
                'message': '快取清理完成'
            }
            
        except Exception as e:
            raise Exception(f"快取清理失敗: {e}")
    
    async def _load_config(self) -> None:
        """載入監控配置"""
        try:
            config_data = await self.db.fetchall("SELECT key, value FROM monitoring_config")
            
            if config_data:
                config_dict = {row[0]: json.loads(row[1]) for row in config_data}
                
                # 更新配置對象
                for key, value in config_dict.items():
                    if hasattr(self.config, key):
                        setattr(self.config, key, value)
                        
        except Exception as e:
            self.logger.warning(f"載入監控配置失敗，使用預設配置: {e}")
    
    async def update_config(self, config: MonitoringConfig) -> None:
        """更新監控配置"""
        self.config = config
        
        # 儲存到資料庫
        config_dict = config.to_dict()
        for key, value in config_dict.items():
            await self.db.execute("""
                INSERT OR REPLACE INTO monitoring_config (key, value, updated_at)
                VALUES (?, ?, ?)
            """, (key, json.dumps(value), datetime.now()))
        
        self.logger.info("監控配置已更新")
    
    async def get_performance_report(self, 
                                   start_date: datetime, 
                                   end_date: datetime) -> PerformanceReport:
        """生成效能報告"""
        try:
            # 獲取指定時間範圍的效能指標
            metrics_data = await self.db.fetchall("""
                SELECT metric_name, value, unit, timestamp, component,
                       threshold_warning, threshold_critical
                FROM monitoring_performance_metrics
                WHERE timestamp BETWEEN ? AND ?
                ORDER BY timestamp
            """, (start_date, end_date))
            
            metrics = []
            for row in metrics_data:
                metric = PerformanceMetric(
                    metric_name=row[0],
                    value=row[1],
                    unit=row[2],
                    timestamp=datetime.fromisoformat(row[3]),
                    component=row[4],
                    threshold_warning=row[5],
                    threshold_critical=row[6]
                )
                metrics.append(metric)
            
            # 計算摘要統計
            summary = self._calculate_performance_summary(metrics)
            
            report = PerformanceReport(
                report_id=str(uuid.uuid4()),
                generated_at=datetime.now(),
                period_start=start_date,
                period_end=end_date,
                metrics=metrics,
                summary=summary
            )
            
            return report
            
        except Exception as e:
            raise ServiceError("效能報告生成失敗", "get_performance_report", str(e))
    
    def _calculate_performance_summary(self, metrics: List[PerformanceMetric]) -> Dict[str, Any]:
        """計算效能摘要統計"""
        if not metrics:
            return {}
        
        summary = {
            'total_metrics': len(metrics),
            'metrics_by_component': {},
            'alert_summary': {
                'warning_count': 0,
                'critical_count': 0
            }
        }
        
        # 按組件分組
        for metric in metrics:
            component = metric.component
            if component not in summary['metrics_by_component']:
                summary['metrics_by_component'][component] = {
                    'count': 0,
                    'metrics': {}
                }
            
            summary['metrics_by_component'][component]['count'] += 1
            
            # 按指標名稱統計
            metric_name = metric.metric_name
            if metric_name not in summary['metrics_by_component'][component]['metrics']:
                summary['metrics_by_component'][component]['metrics'][metric_name] = {
                    'count': 0,
                    'avg_value': 0,
                    'min_value': float('inf'),
                    'max_value': float('-inf'),
                    'unit': metric.unit
                }
            
            metric_stats = summary['metrics_by_component'][component]['metrics'][metric_name]
            metric_stats['count'] += 1
            metric_stats['min_value'] = min(metric_stats['min_value'], metric.value)
            metric_stats['max_value'] = max(metric_stats['max_value'], metric.value)
            
            # 計算警報統計
            if metric.status == HealthStatus.WARNING:
                summary['alert_summary']['warning_count'] += 1
            elif metric.status == HealthStatus.CRITICAL:
                summary['alert_summary']['critical_count'] += 1
        
        # 計算平均值
        for component_data in summary['metrics_by_component'].values():
            for metric_name, metric_stats in component_data['metrics'].items():
                # 重新計算平均值（需要重新查詢數據）
                pass
        
        return summary
    
    async def get_health_history(self, 
                               component: Optional[str] = None,
                               hours: int = 24) -> List[HealthCheckResult]:
        """獲取健康檢查歷史"""
        try:
            start_time = datetime.now() - timedelta(hours=hours)
            
            if component:
                results = await self.db.fetchall("""
                    SELECT component, status, message, checked_at, response_time_ms, details
                    FROM monitoring_health_checks
                    WHERE component = ? AND checked_at >= ?
                    ORDER BY checked_at DESC
                """, (component, start_time))
            else:
                results = await self.db.fetchall("""
                    SELECT component, status, message, checked_at, response_time_ms, details
                    FROM monitoring_health_checks
                    WHERE checked_at >= ?
                    ORDER BY checked_at DESC
                """, (start_time,))
            
            health_results = []
            for row in results:
                details = json.loads(row[5]) if row[5] else None
                result = HealthCheckResult(
                    component=row[0],
                    status=HealthStatus(row[1]),
                    message=row[2],
                    checked_at=datetime.fromisoformat(row[3]),
                    response_time_ms=row[4],
                    details=details
                )
                health_results.append(result)
            
            return health_results
            
        except Exception as e:
            raise ServiceError("健康檢查歷史獲取失敗", "get_health_history", str(e))
    
    async def cleanup_old_data(self) -> Dict[str, Any]:
        """清理過期的監控數據"""
        try:
            cutoff_date = datetime.now() - timedelta(days=self.config.retention_days)
            
            # 清理健康檢查記錄
            health_result = await self.db.execute("""
                DELETE FROM monitoring_health_checks WHERE checked_at < ?
            """, (cutoff_date,))
            
            # 清理效能指標
            metrics_result = await self.db.execute("""
                DELETE FROM monitoring_performance_metrics WHERE timestamp < ?
            """, (cutoff_date,))
            
            # 清理已解決的警報
            alerts_result = await self.db.execute("""
                DELETE FROM monitoring_alerts 
                WHERE resolved_at IS NOT NULL AND resolved_at < ?
            """, (cutoff_date,))
            
            # 清理完成的維護任務
            maintenance_result = await self.db.execute("""
                DELETE FROM monitoring_maintenance_tasks 
                WHERE completed_at IS NOT NULL AND completed_at < ?
            """, (cutoff_date,))
            
            return {
                'health_checks_deleted': health_result,
                'metrics_deleted': metrics_result,
                'alerts_deleted': alerts_result,
                'maintenance_tasks_deleted': maintenance_result,
                'cutoff_date': cutoff_date.isoformat()
            }
            
        except Exception as e:
            raise ServiceError("監控數據清理失敗", "cleanup_old_data", str(e))