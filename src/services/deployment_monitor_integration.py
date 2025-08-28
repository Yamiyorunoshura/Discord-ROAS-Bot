"""
部署監控整合服務
Task ID: 2 - 自動化部署和啟動系統開發

Daniel - DevOps 專家
統一整合部署監控、日誌記錄和性能指標收集
提供智能部署協調器的監控接口
"""

import asyncio
import logging
import uuid
from typing import Dict, Any, Optional, List, Callable, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

# 導入核心服務
from src.services.deployment_monitor import (
    DeploymentMonitor, DeploymentEvent, PerformanceMetric, HealthCheckResult,
    EventLevel, EventType
)
from src.services.deployment_coordinator import (
    DeploymentCoordinator, DeploymentMode, DeploymentStrategy, CoordinatorStatus
)
from src.core.errors import DeploymentError, ServiceStartupError
from src.core.config import AppConfig
from core.base_service import BaseService, ServiceType
from core.database_manager import DatabaseManager


logger = logging.getLogger('services.deployment_monitor_integration')


class MonitoringIntensity(Enum):
    """監控強度枚舉"""
    MINIMAL = "minimal"      # 最小監控：僅記錄關鍵事件
    STANDARD = "standard"    # 標準監控：事件 + 基本性能指標
    INTENSIVE = "intensive"  # 密集監控：全面監控所有指標
    DEBUG = "debug"          # 調試監控：包含調試信息


@dataclass
class MonitoringConfig:
    """監控配置"""
    intensity: MonitoringIntensity = MonitoringIntensity.STANDARD
    real_time_logging: bool = True
    database_logging: bool = True
    performance_thresholds: Dict[str, float] = field(default_factory=lambda: {
        'warning_seconds': 60.0,
        'critical_seconds': 300.0,
        'memory_warning_mb': 1024.0,
        'memory_critical_mb': 2048.0
    })
    buffer_sizes: Dict[str, int] = field(default_factory=lambda: {
        'events': 100,
        'metrics': 50,
        'health_checks': 20
    })
    flush_interval_seconds: int = 30
    enable_alerts: bool = True


@dataclass
class DeploymentMetrics:
    """部署指標摘要"""
    deployment_id: str
    total_duration_seconds: float
    steps_completed: int
    steps_total: int
    success_rate: float
    error_count: int
    warning_count: int
    performance_scores: Dict[str, float] = field(default_factory=dict)
    resource_usage: Dict[str, Any] = field(default_factory=dict)


class DeploymentMonitorIntegration(BaseService):
    """
    部署監控整合服務
    
    整合部署監控器和智能部署協調器，提供統一的監控接口
    支持實時監控、歷史分析和智能告警
    """
    
    def __init__(
        self, 
        coordinator: DeploymentCoordinator,
        config: Optional[AppConfig] = None,
        db_manager: Optional[DatabaseManager] = None,
        monitoring_config: Optional[MonitoringConfig] = None
    ):
        super().__init__()
        
        self.service_metadata = {
            'service_type': ServiceType.MONITORING,
            'service_name': 'deployment_monitor_integration',
            'version': '2.4.4',
            'capabilities': {
                'real_time_monitoring': True,
                'historical_analysis': True,
                'performance_tracking': True,
                'intelligent_alerting': True,
                'database_integration': True,
                'multi_deployment_support': True
            }
        }
        
        self.coordinator = coordinator
        self.config = config or AppConfig()
        self.db_manager = db_manager
        self.monitoring_config = monitoring_config or MonitoringConfig()
        
        # 初始化監控器
        self.monitor = DeploymentMonitor(self.config, db_manager)
        
        # 監控狀態
        self.active_deployments: Dict[str, Dict[str, Any]] = {}
        self.monitoring_tasks: Dict[str, asyncio.Task] = {}
        self.alert_callbacks: List[Callable[[DeploymentEvent], None]] = []
        
        # 性能統計
        self.deployment_stats: Dict[str, DeploymentMetrics] = {}
        self.global_stats = {
            'total_deployments': 0,
            'successful_deployments': 0,
            'failed_deployments': 0,
            'average_duration': 0.0,
            'success_rate': 0.0
        }
        
        # 監控任務
        self.stats_update_task: Optional[asyncio.Task] = None
        self.cleanup_task: Optional[asyncio.Task] = None
    
    async def start(self) -> None:
        """啟動監控整合服務"""
        try:
            logger.info("啟動部署監控整合服務...")
            
            # 啟動基礎監控服務
            await self.monitor.start_monitoring()
            
            # 註冊協調器事件監聽
            await self._setup_coordinator_monitoring()
            
            # 啟動統計更新任務
            self.stats_update_task = asyncio.create_task(self._stats_update_loop())
            
            # 啟動清理任務
            self.cleanup_task = asyncio.create_task(self._cleanup_loop())
            
            self.is_initialized = True
            logger.info("部署監控整合服務啟動完成")
            
        except Exception as e:
            logger.error(f"監控整合服務啟動失敗: {e}")
            raise ServiceStartupError(
                service_name='deployment_monitor_integration',
                startup_mode='monitoring',
                reason=str(e)
            )
    
    async def stop(self) -> None:
        """停止監控整合服務"""
        try:
            logger.info("停止部署監控整合服務...")
            
            # 停止所有監控任務
            for task in list(self.monitoring_tasks.values()):
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            self.monitoring_tasks.clear()
            
            # 停止統計和清理任務
            for task in [self.stats_update_task, self.cleanup_task]:
                if task and not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            
            # 停止基礎監控服務
            await self.monitor.stop_monitoring()
            
            self.is_initialized = False
            logger.info("部署監控整合服務已停止")
            
        except Exception as e:
            logger.error(f"停止監控整合服務失敗: {e}")
            raise
    
    # ========== 監控接口方法 ==========
    
    async def start_deployment_monitoring(
        self, 
        deployment_id: str,
        deployment_config: Dict[str, Any],
        monitoring_intensity: Optional[MonitoringIntensity] = None
    ) -> bool:
        """
        開始監控特定部署
        
        Args:
            deployment_id: 部署ID
            deployment_config: 部署配置
            monitoring_intensity: 監控強度
            
        Returns:
            監控是否成功啟動
        """
        try:
            logger.info(f"開始監控部署: {deployment_id}")
            
            # 設置監控強度
            intensity = monitoring_intensity or self.monitoring_config.intensity
            
            # 記錄部署開始事件
            self.monitor.log_event(
                deployment_id=deployment_id,
                event_type=EventType.SERVICE_STARTED,
                event_level=EventLevel.INFO,
                message=f"開始監控部署，監控強度: {intensity.value}",
                details={
                    'config': deployment_config,
                    'intensity': intensity.value,
                    'start_time': datetime.now().isoformat()
                },
                source_component='MonitorIntegration'
            )
            
            # 保存配置快照
            await self.monitor.save_deployment_config_snapshot(
                deployment_id=deployment_id,
                config_type='deployment_config',
                config_content=deployment_config
            )
            
            # 註冊活躍部署
            self.active_deployments[deployment_id] = {
                'start_time': datetime.now(),
                'config': deployment_config,
                'intensity': intensity,
                'status': 'monitoring',
                'steps_completed': 0,
                'steps_total': self._estimate_deployment_steps(deployment_config),
                'last_update': datetime.now()
            }
            
            # 啟動部署特定監控任務
            monitoring_task = asyncio.create_task(
                self._monitor_deployment_progress(deployment_id, intensity)
            )
            self.monitoring_tasks[deployment_id] = monitoring_task
            
            logger.info(f"部署 {deployment_id} 監控已啟動")
            return True
            
        except Exception as e:
            logger.error(f"啟動部署監控失敗: {e}")
            return False
    
    async def stop_deployment_monitoring(self, deployment_id: str) -> bool:
        """
        停止監控特定部署
        
        Args:
            deployment_id: 部署ID
            
        Returns:
            監控是否成功停止
        """
        try:
            logger.info(f"停止監控部署: {deployment_id}")
            
            # 停止監控任務
            if deployment_id in self.monitoring_tasks:
                task = self.monitoring_tasks[deployment_id]
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                del self.monitoring_tasks[deployment_id]
            
            # 記錄部署結束事件
            if deployment_id in self.active_deployments:
                deployment_info = self.active_deployments[deployment_id]
                duration = (datetime.now() - deployment_info['start_time']).total_seconds()
                
                self.monitor.log_event(
                    deployment_id=deployment_id,
                    event_type=EventType.SERVICE_STOPPED,
                    event_level=EventLevel.INFO,
                    message=f"停止監控部署，總耗時: {duration:.1f}秒",
                    details={
                        'duration_seconds': duration,
                        'steps_completed': deployment_info['steps_completed'],
                        'steps_total': deployment_info['steps_total']
                    },
                    source_component='MonitorIntegration'
                )
                
                # 生成部署指標摘要
                await self._generate_deployment_summary(deployment_id)
                
                # 移除活躍部署記錄
                del self.active_deployments[deployment_id]
            
            logger.info(f"部署 {deployment_id} 監控已停止")
            return True
            
        except Exception as e:
            logger.error(f"停止部署監控失敗: {e}")
            return False
    
    async def log_deployment_step(
        self, 
        deployment_id: str,
        step_name: str,
        step_status: str,
        step_details: Optional[Dict[str, Any]] = None,
        performance_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        記錄部署步驟
        
        Args:
            deployment_id: 部署ID
            step_name: 步驟名稱
            step_status: 步驟狀態 (started, completed, failed, skipped)
            step_details: 步驟詳細信息
            performance_data: 性能數據
        """
        try:
            # 確定事件等級
            event_level = EventLevel.INFO
            if step_status == 'failed':
                event_level = EventLevel.ERROR
            elif step_status == 'skipped':
                event_level = EventLevel.WARNING
            
            # 記錄步驟事件
            self.monitor.log_event(
                deployment_id=deployment_id,
                event_type=EventType.STATUS_CHANGE,
                event_level=event_level,
                message=f"部署步驟 {step_name}: {step_status}",
                details={
                    'step_name': step_name,
                    'step_status': step_status,
                    'step_details': step_details or {},
                    'timestamp': datetime.now().isoformat()
                },
                source_component='DeploymentStep'
            )
            
            # 記錄性能數據
            if performance_data:
                for metric_name, metric_value in performance_data.items():
                    if isinstance(metric_value, (int, float)):
                        self.monitor.record_performance_metric(
                            deployment_id=deployment_id,
                            metric_name=f"step_{step_name}_{metric_name}",
                            metric_value=float(metric_value),
                            metric_unit=performance_data.get(f"{metric_name}_unit", "count"),
                            additional_data={'step_name': step_name}
                        )
            
            # 更新活躍部署狀態
            if deployment_id in self.active_deployments:
                deployment_info = self.active_deployments[deployment_id]
                if step_status == 'completed':
                    deployment_info['steps_completed'] += 1
                deployment_info['last_update'] = datetime.now()
                
                # 記錄進度指標
                progress_percentage = (
                    deployment_info['steps_completed'] / deployment_info['steps_total'] * 100
                    if deployment_info['steps_total'] > 0 else 0
                )
                
                self.monitor.record_performance_metric(
                    deployment_id=deployment_id,
                    metric_name="deployment_progress",
                    metric_value=progress_percentage,
                    metric_unit="percentage"
                )
            
        except Exception as e:
            logger.error(f"記錄部署步驟失敗: {e}")
    
    async def log_deployment_error(
        self,
        deployment_id: str,
        error_type: str,
        error_message: str,
        error_details: Optional[Dict[str, Any]] = None,
        is_critical: bool = False
    ) -> None:
        """
        記錄部署錯誤
        
        Args:
            deployment_id: 部署ID
            error_type: 錯誤類型
            error_message: 錯誤訊息
            error_details: 錯誤詳細信息
            is_critical: 是否為關鍵錯誤
        """
        try:
            event_level = EventLevel.CRITICAL if is_critical else EventLevel.ERROR
            
            event = self.monitor.log_event(
                deployment_id=deployment_id,
                event_type=EventType.ERROR_OCCURRED,
                event_level=event_level,
                message=f"{error_type}: {error_message}",
                details={
                    'error_type': error_type,
                    'error_message': error_message,
                    'error_details': error_details or {},
                    'is_critical': is_critical,
                    'timestamp': datetime.now().isoformat()
                },
                source_component='DeploymentError'
            )
            
            # 觸發告警回調
            if self.monitoring_config.enable_alerts:
                await self._trigger_error_alerts(deployment_id, error_type, error_message, is_critical)
            
        except Exception as e:
            logger.error(f"記錄部署錯誤失敗: {e}")
    
    # ========== 查詢和分析方法 ==========
    
    async def get_deployment_metrics(self, deployment_id: str) -> Optional[DeploymentMetrics]:
        """獲取部署指標摘要"""
        return self.deployment_stats.get(deployment_id)
    
    async def get_active_deployments(self) -> Dict[str, Dict[str, Any]]:
        """獲取活躍部署列表"""
        return dict(self.active_deployments)
    
    async def get_global_statistics(self) -> Dict[str, Any]:
        """獲取全域統計信息"""
        return dict(self.global_stats)
    
    async def get_deployment_events(
        self, 
        deployment_id: str,
        event_types: Optional[List[EventType]] = None,
        event_levels: Optional[List[EventLevel]] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """獲取部署事件"""
        events = []
        
        for event_type in (event_types or []):
            for event_level in (event_levels or []):
                batch_events = await self.monitor.get_deployment_events(
                    deployment_id=deployment_id,
                    event_type=event_type,
                    event_level=event_level,
                    limit=limit
                )
                events.extend(batch_events)
        
        # 如果沒有指定過濾條件，獲取所有事件
        if not event_types and not event_levels:
            events = await self.monitor.get_deployment_events(
                deployment_id=deployment_id,
                limit=limit
            )
        
        # 按時間排序
        events.sort(key=lambda x: x.get('occurred_at', ''), reverse=True)
        return events[:limit]
    
    async def get_performance_metrics(
        self,
        deployment_id: str,
        metric_names: Optional[List[str]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """獲取性能指標"""
        all_metrics = []
        
        if metric_names:
            for metric_name in metric_names:
                metrics = await self.monitor.get_performance_metrics(
                    deployment_id=deployment_id,
                    metric_name=metric_name,
                    start_time=start_time,
                    end_time=end_time
                )
                all_metrics.extend(metrics)
        else:
            all_metrics = await self.monitor.get_performance_metrics(
                deployment_id=deployment_id,
                start_time=start_time,
                end_time=end_time
            )
        
        return all_metrics
    
    async def generate_deployment_report(self, deployment_id: str) -> Dict[str, Any]:
        """生成部署報告"""
        try:
            # 獲取基本信息
            deployment_info = self.active_deployments.get(deployment_id, {})
            metrics = await self.get_deployment_metrics(deployment_id)
            
            # 獲取事件統計
            events = await self.get_deployment_events(deployment_id, limit=1000)
            event_stats = {
                'total_events': len(events),
                'info_events': len([e for e in events if e.get('event_level') == 'info']),
                'warning_events': len([e for e in events if e.get('event_level') == 'warning']),
                'error_events': len([e for e in events if e.get('event_level') == 'error']),
                'critical_events': len([e for e in events if e.get('event_level') == 'critical'])
            }
            
            # 獲取性能統計
            perf_metrics = await self.get_performance_metrics(deployment_id)
            
            # 生成報告
            report = {
                'deployment_id': deployment_id,
                'deployment_info': deployment_info,
                'metrics_summary': metrics.__dict__ if metrics else {},
                'event_statistics': event_stats,
                'performance_overview': {
                    'total_metrics': len(perf_metrics),
                    'avg_response_time': self._calculate_avg_metric(perf_metrics, 'response_time'),
                    'memory_usage_peak': self._calculate_max_metric(perf_metrics, 'memory_usage')
                },
                'recent_events': events[:20],  # 最近20個事件
                'generated_at': datetime.now().isoformat(),
                'report_version': '2.4.4'
            }
            
            return report
            
        except Exception as e:
            logger.error(f"生成部署報告失敗: {e}")
            return {'error': str(e)}
    
    # ========== 內部方法 ==========
    
    async def _setup_coordinator_monitoring(self) -> None:
        """設置協調器監控"""
        # 這裡可以添加協調器事件監聽
        # 由於協調器沒有直接的事件系統，我們通過定期檢查狀態來實現
        pass
    
    async def _monitor_deployment_progress(
        self, 
        deployment_id: str, 
        intensity: MonitoringIntensity
    ) -> None:
        """監控部署進度"""
        try:
            while deployment_id in self.active_deployments:
                deployment_info = self.active_deployments[deployment_id]
                
                # 根據監控強度執行不同的監控操作
                if intensity in [MonitoringIntensity.INTENSIVE, MonitoringIntensity.DEBUG]:
                    # 密集監控：檢查資源使用情況
                    await self._check_resource_usage(deployment_id)
                
                if intensity in [MonitoringIntensity.STANDARD, MonitoringIntensity.INTENSIVE, MonitoringIntensity.DEBUG]:
                    # 標準監控：檢查部署健康狀態
                    await self._check_deployment_health(deployment_id)
                
                # 最小監控：僅檢查基本狀態
                await self._check_basic_status(deployment_id)
                
                # 監控間隔（根據強度調整）
                interval = {
                    MonitoringIntensity.MINIMAL: 60,
                    MonitoringIntensity.STANDARD: 30,
                    MonitoringIntensity.INTENSIVE: 10,
                    MonitoringIntensity.DEBUG: 5
                }.get(intensity, 30)
                
                await asyncio.sleep(interval)
                
        except asyncio.CancelledError:
            logger.debug(f"部署 {deployment_id} 監控任務被取消")
        except Exception as e:
            logger.error(f"監控部署 {deployment_id} 進度失敗: {e}")
    
    async def _check_resource_usage(self, deployment_id: str) -> None:
        """檢查資源使用情況"""
        # 這裡可以添加系統資源監控邏輯
        pass
    
    async def _check_deployment_health(self, deployment_id: str) -> None:
        """檢查部署健康狀態"""
        # 這裡可以添加部署健康檢查邏輯
        pass
    
    async def _check_basic_status(self, deployment_id: str) -> None:
        """檢查基本狀態"""
        if deployment_id in self.active_deployments:
            deployment_info = self.active_deployments[deployment_id]
            
            # 檢查是否超時
            duration = (datetime.now() - deployment_info['start_time']).total_seconds()
            if duration > 600:  # 10分鐘超時
                await self.log_deployment_error(
                    deployment_id=deployment_id,
                    error_type="TIMEOUT",
                    error_message="部署超時，超過10分鐘未完成",
                    is_critical=True
                )
    
    async def _generate_deployment_summary(self, deployment_id: str) -> None:
        """生成部署摘要"""
        try:
            if deployment_id not in self.active_deployments:
                return
            
            deployment_info = self.active_deployments[deployment_id]
            duration = (datetime.now() - deployment_info['start_time']).total_seconds()
            
            # 獲取事件統計
            events = await self.get_deployment_events(deployment_id, limit=1000)
            error_count = len([e for e in events if e.get('event_level') in ['error', 'critical']])
            warning_count = len([e for e in events if e.get('event_level') == 'warning'])
            
            # 計算成功率
            success_rate = (
                (deployment_info['steps_completed'] / deployment_info['steps_total'] * 100)
                if deployment_info['steps_total'] > 0 else 0
            )
            
            # 創建指標摘要
            metrics = DeploymentMetrics(
                deployment_id=deployment_id,
                total_duration_seconds=duration,
                steps_completed=deployment_info['steps_completed'],
                steps_total=deployment_info['steps_total'],
                success_rate=success_rate,
                error_count=error_count,
                warning_count=warning_count
            )
            
            self.deployment_stats[deployment_id] = metrics
            
        except Exception as e:
            logger.error(f"生成部署摘要失敗: {e}")
    
    async def _stats_update_loop(self) -> None:
        """統計更新循環"""
        while self.is_initialized:
            try:
                await self._update_global_stats()
                await asyncio.sleep(300)  # 每5分鐘更新一次
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"統計更新失敗: {e}")
                await asyncio.sleep(60)
    
    async def _cleanup_loop(self) -> None:
        """清理循環"""
        while self.is_initialized:
            try:
                await self._cleanup_old_data()
                await asyncio.sleep(3600)  # 每小時清理一次
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"數據清理失敗: {e}")
                await asyncio.sleep(300)
    
    async def _update_global_stats(self) -> None:
        """更新全域統計"""
        try:
            # 計算全域統計
            total_deployments = len(self.deployment_stats)
            if total_deployments > 0:
                successful_deployments = len([
                    m for m in self.deployment_stats.values()
                    if m.success_rate >= 80.0
                ])
                failed_deployments = total_deployments - successful_deployments
                average_duration = sum(
                    m.total_duration_seconds for m in self.deployment_stats.values()
                ) / total_deployments
                success_rate = successful_deployments / total_deployments * 100
                
                self.global_stats.update({
                    'total_deployments': total_deployments,
                    'successful_deployments': successful_deployments,
                    'failed_deployments': failed_deployments,
                    'average_duration': average_duration,
                    'success_rate': success_rate
                })
                
        except Exception as e:
            logger.error(f"更新全域統計失敗: {e}")
    
    async def _cleanup_old_data(self) -> None:
        """清理舊數據"""
        try:
            # 清理超過24小時的部署統計
            cutoff_time = datetime.now() - timedelta(hours=24)
            old_deployments = []
            
            for deployment_id, deployment_info in self.active_deployments.items():
                if deployment_info['start_time'] < cutoff_time:
                    old_deployments.append(deployment_id)
            
            for deployment_id in old_deployments:
                if deployment_id in self.active_deployments:
                    del self.active_deployments[deployment_id]
                if deployment_id in self.monitoring_tasks:
                    task = self.monitoring_tasks[deployment_id]
                    if not task.done():
                        task.cancel()
                    del self.monitoring_tasks[deployment_id]
                    
        except Exception as e:
            logger.error(f"數據清理失敗: {e}")
    
    async def _trigger_error_alerts(
        self, 
        deployment_id: str, 
        error_type: str, 
        error_message: str, 
        is_critical: bool
    ) -> None:
        """觸發錯誤告警"""
        try:
            for callback in self.alert_callbacks:
                # 創建告警事件
                alert_event = DeploymentEvent(
                    event_id=f"alert_{uuid.uuid4().hex[:12]}",
                    deployment_id=deployment_id,
                    event_type=EventType.ERROR_OCCURRED,
                    event_level=EventLevel.CRITICAL if is_critical else EventLevel.ERROR,
                    event_message=f"ALERT: {error_type} - {error_message}",
                    event_details={
                        'alert_type': 'deployment_error',
                        'error_type': error_type,
                        'is_critical': is_critical
                    },
                    source_component='AlertSystem'
                )
                
                try:
                    callback(alert_event)
                except Exception as e:
                    logger.warning(f"告警回調執行失敗: {e}")
                    
        except Exception as e:
            logger.error(f"觸發錯誤告警失敗: {e}")
    
    def _estimate_deployment_steps(self, config: Dict[str, Any]) -> int:
        """估計部署步驟數量"""
        # 基礎步驟數量估算
        base_steps = 5  # 環境檢查、準備、部署、驗證、完成
        
        # 根據配置調整
        if config.get('force_rebuild'):
            base_steps += 2
        if config.get('environment') == 'prod':
            base_steps += 3  # 額外的生產環境檢查
        
        return base_steps
    
    def _calculate_avg_metric(self, metrics: List[Dict], metric_name: str) -> float:
        """計算平均指標值"""
        values = [m.get('metric_value', 0) for m in metrics if m.get('metric_name') == metric_name]
        return sum(values) / len(values) if values else 0.0
    
    def _calculate_max_metric(self, metrics: List[Dict], metric_name: str) -> float:
        """計算最大指標值"""
        values = [m.get('metric_value', 0) for m in metrics if m.get('metric_name') == metric_name]
        return max(values) if values else 0.0
    
    # ========== 公開接口方法 ==========
    
    def add_alert_callback(self, callback: Callable[[DeploymentEvent], None]) -> None:
        """添加告警回調"""
        if callback not in self.alert_callbacks:
            self.alert_callbacks.append(callback)
    
    def remove_alert_callback(self, callback: Callable[[DeploymentEvent], None]) -> None:
        """移除告警回調"""
        if callback in self.alert_callbacks:
            self.alert_callbacks.remove(callback)
    
    async def health_check(self) -> Dict[str, Any]:
        """健康檢查"""
        try:
            monitor_stats = await self.monitor.get_deployment_statistics()
            
            return {
                'service_name': 'deployment_monitor_integration',
                'status': 'healthy' if self.is_initialized else 'unhealthy',
                'active_deployments': len(self.active_deployments),
                'monitoring_tasks': len(self.monitoring_tasks),
                'global_stats': self.global_stats,
                'monitor_status': monitor_stats.get('monitoring_status', {}),
                'last_check': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'service_name': 'deployment_monitor_integration',
                'status': 'error',
                'error': str(e),
                'last_check': datetime.now().isoformat()
            }


# 導出主要類別
__all__ = [
    'DeploymentMonitorIntegration',
    'MonitoringConfig',
    'MonitoringIntensity',
    'DeploymentMetrics'
]