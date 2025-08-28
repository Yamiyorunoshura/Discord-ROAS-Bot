"""
部署監控和日誌系統
Task ID: 2 - 自動化部署和啟動系統開發

Noah Chen - 基礎設施專家
提供完整的部署過程監控、日誌記錄、性能指標收集和報告功能
整合資料庫儲存和即時監控能力
"""

import asyncio
import logging
import json
import hashlib
import uuid
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path

# 導入核心模組
from core.database_manager import DatabaseManager
from src.core.errors import DeploymentError, DatabaseError
from src.core.config import AppConfig


class EventLevel(Enum):
    """事件等級枚舉"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class EventType(Enum):
    """事件類型枚舉"""
    STATUS_CHANGE = "status_change"
    ERROR_OCCURRED = "error_occurred"
    SERVICE_STARTED = "service_started"
    SERVICE_STOPPED = "service_stopped"
    DEPENDENCY_INSTALLED = "dependency_installed"
    HEALTH_CHECK_PERFORMED = "health_check_performed"
    CONFIGURATION_CHANGED = "configuration_changed"
    PERFORMANCE_METRIC = "performance_metric"


@dataclass
class DeploymentEvent:
    """部署事件數據類"""
    event_id: str
    deployment_id: str
    event_type: EventType
    event_level: EventLevel
    event_message: str
    event_details: Dict[str, Any] = field(default_factory=dict)
    source_component: Optional[str] = None
    occurred_at: datetime = field(default_factory=datetime.now)


@dataclass 
class PerformanceMetric:
    """性能指標數據類"""
    deployment_id: str
    metric_name: str
    metric_value: float
    metric_unit: str
    measurement_time: datetime = field(default_factory=datetime.now)
    additional_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HealthCheckResult:
    """健康檢查結果數據類"""
    manager_type: str
    status: str
    response_time: float
    services_status: Dict[str, Any] = field(default_factory=dict)
    resource_usage: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    check_time: datetime = field(default_factory=datetime.now)


class DeploymentMonitor:
    """
    部署監控器
    
    負責監控部署過程、收集性能指標、記錄事件
    提供即時監控和歷史數據分析功能
    """
    
    def __init__(self, config: AppConfig, db_manager: Optional[DatabaseManager] = None):
        self.config = config
        self.db_manager = db_manager
        self.logger = logging.getLogger('DeploymentMonitor')
        
        # 事件收集器
        self.event_buffer: List[DeploymentEvent] = []
        self.metric_buffer: List[PerformanceMetric] = []
        self.health_check_buffer: List[HealthCheckResult] = []
        
        # 監控配置
        self.monitoring_config = {
            'buffer_size': 100,
            'flush_interval_seconds': 30,
            'enable_real_time_logging': True,
            'enable_database_logging': True,
            'performance_threshold_warning': 60.0,  # 60秒
            'performance_threshold_critical': 300.0  # 5分鐘
        }
        
        # 監控狀態
        self.monitoring_active = False
        self.monitoring_task: Optional[asyncio.Task] = None
        
        # 事件監聽器
        self.event_listeners: List[Callable[[DeploymentEvent], None]] = []
    
    async def start_monitoring(self) -> None:
        """啟動監控"""
        try:
            if self.monitoring_active:
                self.logger.warning("監控已經在運行中")
                return
                
            self.logger.info("啟動部署監控...")
            self.monitoring_active = True
            
            # 啟動後台監控任務
            self.monitoring_task = asyncio.create_task(self._monitoring_loop())
            
            self.logger.info("部署監控已啟動")
            
        except Exception as e:
            self.logger.error(f"啟動部署監控失敗: {e}")
            raise DeploymentError(
                message="啟動部署監控失敗",
                deployment_mode="monitor",
                details={"error": str(e)},
                cause=e
            )
    
    async def stop_monitoring(self) -> None:
        """停止監控"""
        try:
            if not self.monitoring_active:
                self.logger.info("監控未在運行")
                return
                
            self.logger.info("停止部署監控...")
            self.monitoring_active = False
            
            # 停止後台任務
            if self.monitoring_task:
                self.monitoring_task.cancel()
                try:
                    await self.monitoring_task
                except asyncio.CancelledError:
                    pass
                self.monitoring_task = None
            
            # 清空緩衝區
            await self._flush_all_buffers()
            
            self.logger.info("部署監控已停止")
            
        except Exception as e:
            self.logger.error(f"停止部署監控失敗: {e}")
    
    def log_event(self, 
                  deployment_id: str,
                  event_type: EventType,
                  event_level: EventLevel,
                  message: str,
                  details: Optional[Dict[str, Any]] = None,
                  source_component: Optional[str] = None) -> str:
        """
        記錄部署事件
        
        Args:
            deployment_id: 部署ID
            event_type: 事件類型
            event_level: 事件等級
            message: 事件訊息
            details: 事件詳細資料
            source_component: 來源組件
            
        Returns:
            事件ID
        """
        try:
            event_id = f"evt_{uuid.uuid4().hex[:12]}"
            
            event = DeploymentEvent(
                event_id=event_id,
                deployment_id=deployment_id,
                event_type=event_type,
                event_level=event_level,
                event_message=message,
                event_details=details or {},
                source_component=source_component
            )
            
            # 添加到緩衝區
            self.event_buffer.append(event)
            
            # 即時日誌記錄
            if self.monitoring_config['enable_real_time_logging']:
                log_level = {
                    EventLevel.INFO: logging.INFO,
                    EventLevel.WARNING: logging.WARNING,
                    EventLevel.ERROR: logging.ERROR,
                    EventLevel.CRITICAL: logging.CRITICAL
                }.get(event_level, logging.INFO)
                
                self.logger.log(
                    log_level, 
                    f"[{event_type.value}] {message} "
                    f"(Deployment: {deployment_id}, Source: {source_component or 'Unknown'})"
                )
            
            # 觸發事件監聽器
            for listener in self.event_listeners:
                try:
                    listener(event)
                except Exception as e:
                    self.logger.warning(f"事件監聽器執行失敗: {e}")
            
            # 檢查緩衝區大小
            if len(self.event_buffer) >= self.monitoring_config['buffer_size']:
                asyncio.create_task(self._flush_event_buffer())
            
            return event_id
            
        except Exception as e:
            self.logger.error(f"記錄事件失敗: {e}")
            return ""
    
    def record_performance_metric(self,
                                 deployment_id: str,
                                 metric_name: str,
                                 metric_value: float,
                                 metric_unit: str,
                                 additional_data: Optional[Dict[str, Any]] = None) -> None:
        """
        記錄性能指標
        
        Args:
            deployment_id: 部署ID
            metric_name: 指標名稱
            metric_value: 指標值
            metric_unit: 指標單位
            additional_data: 額外資料
        """
        try:
            metric = PerformanceMetric(
                deployment_id=deployment_id,
                metric_name=metric_name,
                metric_value=metric_value,
                metric_unit=metric_unit,
                additional_data=additional_data or {}
            )
            
            self.metric_buffer.append(metric)
            
            # 性能警告檢查
            if metric_unit == "seconds":
                if metric_value > self.monitoring_config['performance_threshold_critical']:
                    self.log_event(
                        deployment_id=deployment_id,
                        event_type=EventType.PERFORMANCE_METRIC,
                        event_level=EventLevel.CRITICAL,
                        message=f"性能指標 {metric_name} 超過臨界值: {metric_value}s",
                        details={"metric": asdict(metric)},
                        source_component="DeploymentMonitor"
                    )
                elif metric_value > self.monitoring_config['performance_threshold_warning']:
                    self.log_event(
                        deployment_id=deployment_id,
                        event_type=EventType.PERFORMANCE_METRIC,
                        event_level=EventLevel.WARNING,
                        message=f"性能指標 {metric_name} 超過警告值: {metric_value}s",
                        details={"metric": asdict(metric)},
                        source_component="DeploymentMonitor"
                    )
            
            self.logger.debug(f"記錄性能指標: {metric_name} = {metric_value} {metric_unit}")
            
            # 檢查緩衝區大小
            if len(self.metric_buffer) >= self.monitoring_config['buffer_size']:
                asyncio.create_task(self._flush_metric_buffer())
                
        except Exception as e:
            self.logger.error(f"記錄性能指標失敗: {e}")
    
    def record_health_check(self,
                           deployment_id: str,
                           manager_type: str,
                           health_result: Dict[str, Any]) -> None:
        """
        記錄健康檢查結果
        
        Args:
            deployment_id: 部署ID
            manager_type: 管理器類型
            health_result: 健康檢查結果
        """
        try:
            health_check = HealthCheckResult(
                manager_type=manager_type,
                status=health_result.get('status', 'unknown'),
                response_time=health_result.get('response_time', 0.0),
                services_status=health_result.get('services', {}),
                resource_usage=health_result.get('resources', {}),
                error_message=health_result.get('error')
            )
            
            self.health_check_buffer.append(health_check)
            
            # 記錄健康檢查事件
            event_level = EventLevel.INFO
            if health_check.status == 'unhealthy':
                event_level = EventLevel.ERROR
            elif health_check.status in ['degraded', 'warning']:
                event_level = EventLevel.WARNING
            
            self.log_event(
                deployment_id=deployment_id,
                event_type=EventType.HEALTH_CHECK_PERFORMED,
                event_level=event_level,
                message=f"{manager_type} 健康檢查: {health_check.status}",
                details={"health_check": asdict(health_check)},
                source_component=f"{manager_type}Manager"
            )
            
            self.logger.debug(f"記錄健康檢查: {manager_type} = {health_check.status}")
            
        except Exception as e:
            self.logger.error(f"記錄健康檢查失敗: {e}")
    
    def add_event_listener(self, listener: Callable[[DeploymentEvent], None]) -> None:
        """添加事件監聽器"""
        if listener not in self.event_listeners:
            self.event_listeners.append(listener)
            self.logger.debug("已添加事件監聽器")
    
    def remove_event_listener(self, listener: Callable[[DeploymentEvent], None]) -> None:
        """移除事件監聽器"""
        if listener in self.event_listeners:
            self.event_listeners.remove(listener)
            self.logger.debug("已移除事件監聽器")
    
    async def get_deployment_events(self, 
                                  deployment_id: str, 
                                  event_type: Optional[EventType] = None,
                                  event_level: Optional[EventLevel] = None,
                                  limit: int = 100) -> List[Dict[str, Any]]:
        """
        獲取部署事件
        
        Args:
            deployment_id: 部署ID
            event_type: 事件類型過濾
            event_level: 事件等級過濾
            limit: 返回記錄數限制
            
        Returns:
            事件記錄列表
        """
        try:
            if not self.db_manager:
                return []
            
            # 構建查詢條件
            query = "SELECT * FROM deployment_events WHERE deployment_id = ?"
            params = [deployment_id]
            
            if event_type:
                query += " AND event_type = ?"
                params.append(event_type.value)
                
            if event_level:
                query += " AND event_level = ?"
                params.append(event_level.value)
            
            query += " ORDER BY occurred_at DESC LIMIT ?"
            params.append(limit)
            
            results = await self.db_manager.fetchall(query, params)
            
            # 解析JSON欄位
            for result in results:
                if result.get('event_details'):
                    try:
                        result['event_details'] = json.loads(result['event_details'])
                    except json.JSONDecodeError:
                        result['event_details'] = {}
            
            return results
            
        except Exception as e:
            self.logger.error(f"獲取部署事件失敗: {e}")
            return []
    
    async def get_performance_metrics(self,
                                    deployment_id: str,
                                    metric_name: Optional[str] = None,
                                    start_time: Optional[datetime] = None,
                                    end_time: Optional[datetime] = None,
                                    limit: int = 100) -> List[Dict[str, Any]]:
        """
        獲取性能指標
        
        Args:
            deployment_id: 部署ID
            metric_name: 指標名稱過濾
            start_time: 開始時間
            end_time: 結束時間
            limit: 返回記錄數限制
            
        Returns:
            性能指標記錄列表
        """
        try:
            if not self.db_manager:
                return []
            
            # 構建查詢條件
            query = "SELECT * FROM deployment_performance_metrics WHERE deployment_id = ?"
            params = [deployment_id]
            
            if metric_name:
                query += " AND metric_name = ?"
                params.append(metric_name)
                
            if start_time:
                query += " AND measurement_time >= ?"
                params.append(start_time.isoformat())
                
            if end_time:
                query += " AND measurement_time <= ?"
                params.append(end_time.isoformat())
            
            query += " ORDER BY measurement_time DESC LIMIT ?"
            params.append(limit)
            
            results = await self.db_manager.fetchall(query, params)
            
            # 解析JSON欄位
            for result in results:
                if result.get('additional_data'):
                    try:
                        result['additional_data'] = json.loads(result['additional_data'])
                    except json.JSONDecodeError:
                        result['additional_data'] = {}
            
            return results
            
        except Exception as e:
            self.logger.error(f"獲取性能指標失敗: {e}")
            return []
    
    async def get_deployment_statistics(self) -> Dict[str, Any]:
        """
        獲取部署統計資訊
        
        Returns:
            統計資訊字典
        """
        try:
            if not self.db_manager:
                return {}
            
            # 獲取基本統計
            stats_query = """
            SELECT 
                mode,
                total_deployments,
                successful_deployments,
                failed_deployments,
                avg_duration_seconds,
                success_rate_percent
            FROM deployment_statistics
            """
            
            stats_results = await self.db_manager.fetchall(stats_query)
            
            # 獲取最近24小時的部署數量
            recent_query = """
            SELECT COUNT(*) as recent_count
            FROM deployment_logs 
            WHERE start_time >= datetime('now', '-1 day')
            """
            
            recent_result = await self.db_manager.fetchone(recent_query)
            recent_count = recent_result.get('recent_count', 0) if recent_result else 0
            
            # 獲取事件統計
            event_stats_query = """
            SELECT 
                event_level,
                COUNT(*) as event_count
            FROM deployment_events 
            WHERE occurred_at >= datetime('now', '-7 days')
            GROUP BY event_level
            """
            
            event_results = await self.db_manager.fetchall(event_stats_query)
            event_stats = {result['event_level']: result['event_count'] for result in event_results}
            
            return {
                'deployment_modes': stats_results,
                'recent_deployments_24h': recent_count,
                'event_statistics_7d': event_stats,
                'monitoring_status': {
                    'active': self.monitoring_active,
                    'buffer_sizes': {
                        'events': len(self.event_buffer),
                        'metrics': len(self.metric_buffer),
                        'health_checks': len(self.health_check_buffer)
                    }
                },
                'generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"獲取部署統計失敗: {e}")
            return {'error': str(e)}
    
    async def save_deployment_config_snapshot(self,
                                            deployment_id: str,
                                            config_type: str,
                                            config_content: Dict[str, Any]) -> bool:
        """
        保存部署配置快照
        
        Args:
            deployment_id: 部署ID
            config_type: 配置類型
            config_content: 配置內容
            
        Returns:
            保存是否成功
        """
        try:
            if not self.db_manager:
                return False
            
            # 序列化配置內容
            content_json = json.dumps(config_content, ensure_ascii=False, indent=2)
            
            # 計算哈希值
            config_hash = hashlib.sha256(content_json.encode('utf-8')).hexdigest()
            
            # 保存到資料庫
            await self.db_manager.execute("""
                INSERT INTO deployment_config_snapshots 
                (deployment_id, config_type, config_content, config_hash)
                VALUES (?, ?, ?, ?)
            """, (deployment_id, config_type, content_json, config_hash))
            
            self.logger.debug(f"已保存配置快照: {config_type} for {deployment_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"保存配置快照失敗: {e}")
            return False
    
    async def _monitoring_loop(self) -> None:
        """監控主循環"""
        while self.monitoring_active:
            try:
                await asyncio.sleep(self.monitoring_config['flush_interval_seconds'])
                
                if self.monitoring_active:
                    await self._flush_all_buffers()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"監控循環異常: {e}")
                await asyncio.sleep(5)  # 錯誤後短暫延遲
    
    async def _flush_all_buffers(self) -> None:
        """清空所有緩衝區"""
        await asyncio.gather(
            self._flush_event_buffer(),
            self._flush_metric_buffer(),
            self._flush_health_check_buffer(),
            return_exceptions=True
        )
    
    async def _flush_event_buffer(self) -> None:
        """清空事件緩衝區"""
        if not self.event_buffer or not self.db_manager or not self.monitoring_config['enable_database_logging']:
            return
            
        try:
            events_to_flush = self.event_buffer.copy()
            self.event_buffer.clear()
            
            for event in events_to_flush:
                await self.db_manager.execute("""
                    INSERT INTO deployment_events 
                    (event_id, deployment_id, event_type, event_level, event_message, 
                     event_details, source_component, occurred_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event.event_id,
                    event.deployment_id, 
                    event.event_type.value,
                    event.event_level.value,
                    event.event_message,
                    json.dumps(event.event_details, ensure_ascii=False),
                    event.source_component,
                    event.occurred_at.isoformat()
                ))
            
            self.logger.debug(f"已清空事件緩衝區，寫入 {len(events_to_flush)} 個事件")
            
        except Exception as e:
            self.logger.error(f"清空事件緩衝區失敗: {e}")
    
    async def _flush_metric_buffer(self) -> None:
        """清空性能指標緩衝區"""
        if not self.metric_buffer or not self.db_manager or not self.monitoring_config['enable_database_logging']:
            return
            
        try:
            metrics_to_flush = self.metric_buffer.copy()
            self.metric_buffer.clear()
            
            for metric in metrics_to_flush:
                await self.db_manager.execute("""
                    INSERT INTO deployment_performance_metrics 
                    (deployment_id, metric_name, metric_value, metric_unit, 
                     measurement_time, additional_data)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    metric.deployment_id,
                    metric.metric_name,
                    metric.metric_value,
                    metric.metric_unit,
                    metric.measurement_time.isoformat(),
                    json.dumps(metric.additional_data, ensure_ascii=False)
                ))
            
            self.logger.debug(f"已清空性能指標緩衝區，寫入 {len(metrics_to_flush)} 個指標")
            
        except Exception as e:
            self.logger.error(f"清空性能指標緩衝區失敗: {e}")
    
    async def _flush_health_check_buffer(self) -> None:
        """清空健康檢查緩衝區"""
        if not self.health_check_buffer or not self.db_manager or not self.monitoring_config['enable_database_logging']:
            return
            
        try:
            health_checks_to_flush = self.health_check_buffer.copy()
            self.health_check_buffer.clear()
            
            for health_check in health_checks_to_flush:
                # 這裡需要有對應的deployment_id，實際實現時需要從上下文獲取
                # 暫時跳過，因為健康檢查記錄需要與特定部署關聯
                pass
            
            self.logger.debug(f"已處理健康檢查緩衝區，共 {len(health_checks_to_flush)} 個檢查")
            
        except Exception as e:
            self.logger.error(f"清空健康檢查緩衝區失敗: {e}")


# 導出主要類別
__all__ = [
    'DeploymentMonitor',
    'DeploymentEvent',
    'PerformanceMetric',
    'HealthCheckResult',
    'EventLevel',
    'EventType'
]