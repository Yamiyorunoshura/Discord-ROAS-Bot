"""
服務生命週期管理器
Task ID: 1 - 核心架構和基礎設施建置

專門用於管理服務的生命週期，包括：
- 服務狀態監控
- 健康檢查調度
- 服務恢復機制
- 生命週期事件記錄
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Callable, Any, Tuple
from enum import Enum
import weakref
from dataclasses import dataclass, field

logger = logging.getLogger('core.service_lifecycle')


class ServiceStatus(Enum):
    """服務狀態枚舉"""
    CREATED = "created"              # 服務已創建，尚未初始化
    INITIALIZING = "initializing"    # 正在初始化
    RUNNING = "running"              # 運行中
    PAUSED = "paused"               # 暫停
    STOPPING = "stopping"           # 正在停止
    STOPPED = "stopped"             # 已停止
    ERROR = "error"                 # 錯誤狀態
    DEGRADED = "degraded"           # 降級運行


class HealthStatus(Enum):
    """健康狀態枚舉"""
    HEALTHY = "healthy"
    DEGRADED = "degraded" 
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ServiceHealthInfo:
    """服務健康信息"""
    service_name: str
    status: HealthStatus
    last_check: datetime
    response_time: float
    error_count: int = 0
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LifecycleEvent:
    """生命週期事件"""
    service_name: str
    event_type: str
    timestamp: datetime
    old_status: Optional[ServiceStatus] = None
    new_status: Optional[ServiceStatus] = None
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class ServiceLifecycleManager:
    """
    服務生命週期管理器
    
    負責管理所有服務的生命週期，包括：
    - 狀態追蹤和轉換
    - 健康檢查調度
    - 服務恢復
    - 事件記錄
    """
    
    def __init__(self, check_interval: int = 30):
        """
        初始化生命週期管理器
        
        參數：
            check_interval: 健康檢查間隔（秒）
        """
        self.check_interval = check_interval
        self._service_statuses: Dict[str, ServiceStatus] = {}
        self._health_info: Dict[str, ServiceHealthInfo] = {}
        self._lifecycle_events: List[LifecycleEvent] = []
        self._event_listeners: Dict[str, List[Callable]] = {}
        self._health_check_tasks: Dict[str, asyncio.Task] = {}
        self._services: weakref.WeakValueDictionary = weakref.WeakValueDictionary()
        self._running = False
        self._health_check_task: Optional[asyncio.Task] = None
        self.max_events = 1000  # 最多保存1000個事件
        
    async def start(self):
        """啟動生命週期管理器"""
        if self._running:
            return
            
        self._running = True
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        logger.info(f"服務生命週期管理器已啟動（檢查間隔: {self.check_interval}秒）")
        
    async def stop(self):
        """停止生命週期管理器"""
        if not self._running:
            return
            
        self._running = False
        
        # 取消健康檢查任務
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
                
        # 取消所有服務的健康檢查任務
        for task in self._health_check_tasks.values():
            task.cancel()
            
        await asyncio.gather(*self._health_check_tasks.values(), return_exceptions=True)
        self._health_check_tasks.clear()
        
        logger.info("服務生命週期管理器已停止")
        
    def register_service(self, service_name: str, service_instance):
        """
        註冊服務到生命週期管理器
        
        參數：
            service_name: 服務名稱
            service_instance: 服務實例
        """
        self._services[service_name] = service_instance
        self._service_statuses[service_name] = ServiceStatus.CREATED
        self._health_info[service_name] = ServiceHealthInfo(
            service_name=service_name,
            status=HealthStatus.UNKNOWN,
            last_check=datetime.now(),
            response_time=0.0
        )
        
        self._record_event(
            service_name, 
            "service_registered",
            new_status=ServiceStatus.CREATED,
            message="服務已註冊到生命週期管理器"
        )
        
        logger.info(f"服務 {service_name} 已註冊到生命週期管理器")
        
    def unregister_service(self, service_name: str):
        """
        從生命週期管理器取消註冊服務
        
        參數：
            service_name: 服務名稱
        """
        # 取消健康檢查任務
        if service_name in self._health_check_tasks:
            self._health_check_tasks[service_name].cancel()
            del self._health_check_tasks[service_name]
            
        # 清理狀態信息
        self._service_statuses.pop(service_name, None)
        self._health_info.pop(service_name, None)
        
        # 服務實例會自動從弱引用字典中移除
        
        self._record_event(
            service_name,
            "service_unregistered", 
            message="服務已從生命週期管理器取消註冊"
        )
        
        logger.info(f"服務 {service_name} 已從生命週期管理器取消註冊")
        
    def update_service_status(
        self, 
        service_name: str, 
        new_status: ServiceStatus,
        message: str = ""
    ):
        """
        更新服務狀態
        
        參數：
            service_name: 服務名稱
            new_status: 新狀態
            message: 狀態變更訊息
        """
        old_status = self._service_statuses.get(service_name)
        
        if old_status != new_status:
            self._service_statuses[service_name] = new_status
            
            self._record_event(
                service_name,
                "status_changed",
                old_status=old_status,
                new_status=new_status,
                message=message or f"狀態從 {old_status.value if old_status else 'None'} 變更為 {new_status.value}"
            )
            
            # 觸發狀態變更事件
            self._trigger_event("status_changed", service_name, {
                "old_status": old_status,
                "new_status": new_status,
                "message": message
            })
            
            logger.info(f"服務 {service_name} 狀態更新: {old_status} -> {new_status}")
            
    async def perform_health_check(self, service_name: str) -> ServiceHealthInfo:
        """
        執行服務健康檢查（增強版）
        
        參數：
            service_name: 服務名稱
            
        返回：
            健康檢查結果
        """
        service = self._services.get(service_name)
        if not service:
            health_info = ServiceHealthInfo(
                service_name=service_name,
                status=HealthStatus.UNKNOWN,
                last_check=datetime.now(),
                response_time=0.0,
                message="服務實例不存在"
            )
            self._health_info[service_name] = health_info
            return health_info
            
        start_time = datetime.now()
        
        try:
            # 檢查服務類型，對不同類型的服務使用不同的健康檢查策略
            service_type = getattr(service, 'service_metadata', {}).get('service_type')
            health_data = {}
            
            if hasattr(service, 'health_check'):
                health_data = await service.health_check()
            elif hasattr(service, 'is_initialized'):
                health_data = {'initialized': service.is_initialized}
            else:
                health_data = {'initialized': True}  # 預設為已初始化
            
            # 根據服務類型執行特定的健康檢查
            if service_type == 'deployment':
                health_status, message = await self._check_deployment_service_health(service, health_data)
            elif service_type == 'sub_bot':
                health_status, message = await self._check_sub_bot_service_health(service, health_data)
            elif service_type == 'ai_service':
                health_status, message = await self._check_ai_service_health(service, health_data)
            else:
                # 一般服務的健康檢查
                if health_data.get("initialized", False):
                    health_status = HealthStatus.HEALTHY
                    message = "服務運行正常"
                else:
                    health_status = HealthStatus.UNHEALTHY
                    message = "服務未初始化"
                    
            response_time = (datetime.now() - start_time).total_seconds()
            
            health_info = ServiceHealthInfo(
                service_name=service_name,
                status=health_status,
                last_check=datetime.now(),
                response_time=response_time,
                message=message,
                metadata=health_data
            )
            
            # 重置錯誤計數
            if health_status == HealthStatus.HEALTHY:
                health_info.error_count = 0
            
        except Exception as e:
            response_time = (datetime.now() - start_time).total_seconds()
            
            # 增加錯誤計數
            old_health = self._health_info.get(service_name)
            error_count = (old_health.error_count + 1) if old_health else 1
            
            health_info = ServiceHealthInfo(
                service_name=service_name,
                status=HealthStatus.UNHEALTHY,
                last_check=datetime.now(),
                response_time=response_time,
                error_count=error_count,
                message=f"健康檢查失敗: {str(e)}"
            )
            
            logger.warning(f"服務 {service_name} 健康檢查失敗: {e}")
            
            # 如果錯誤計數過高，嘗試自動恢復
            if error_count >= 3:
                await self._attempt_service_recovery(service_name)
            
        self._health_info[service_name] = health_info
        
        # 觸發健康檢查完成事件
        self._trigger_event("health_check_completed", service_name, {
            "health_status": health_info.status,
            "response_time": health_info.response_time,
            "error_count": health_info.error_count
        })
        
        return health_info
    # ========== 新服務類型的專門健康檢查方法 ==========
    
    async def _check_deployment_service_health(
        self, 
        service, 
        health_data: Dict[str, Any]
    ) -> Tuple[HealthStatus, str]:
        """
        檢查部署服務的健康狀態
        
        Args:
            service: 部署服務實例
            health_data: 健康檢查数據
            
        Returns:
            (健康狀態, 狀態訊息)
        """
        try:
            # 檢查基本初始化狀態
            if not health_data.get('initialized', False):
                return HealthStatus.UNHEALTHY, "部署服務未初始化"
            
            # 檢查部署狀態
            deployment_status = getattr(service, 'deployment_status', None)
            if deployment_status:
                if deployment_status.value == 'running':
                    return HealthStatus.HEALTHY, "部署服務正在運行"
                elif deployment_status.value == 'failed':
                    return HealthStatus.UNHEALTHY, "部署失敗"
                elif deployment_status.value in ['installing', 'configuring', 'starting']:
                    return HealthStatus.DEGRADED, f"部署狀態: {deployment_status.value}"
            
            # 檢查環境狀態
            if hasattr(service, 'detect_environment'):
                try:
                    env_info = await asyncio.wait_for(service.detect_environment(), timeout=5.0)
                    if not env_info.get('python_executable'):
                        return HealthStatus.UNHEALTHY, "缺少Python執行環境"
                except asyncio.TimeoutError:
                    return HealthStatus.DEGRADED, "環境檢測超時"
            
            return HealthStatus.HEALTHY, "部署服務健康"
            
        except Exception as e:
            return HealthStatus.UNHEALTHY, f"部署服務健康檢查錯誤: {str(e)}"
    
    async def _check_sub_bot_service_health(
        self, 
        service, 
        health_data: Dict[str, Any]
    ) -> Tuple[HealthStatus, str]:
        """
        檢查子機器人服務的健康狀態
        
        Args:
            service: 子機器人服務實例
            health_data: 健康檢查數據
            
        Returns:
            (健康狀態, 狀態訊息)
        """
        try:
            # 檢查基本初始化狀態
            if not health_data.get('initialized', False):
                return HealthStatus.UNHEALTHY, "子機器人服務未初始化"
            
            # 檢查活躍連線數量
            active_connections = getattr(service, 'active_connections', {})
            registered_bots = getattr(service, 'registered_bots', {})
            
            if not registered_bots:
                return HealthStatus.DEGRADED, "沒有註冊的子機器人"
            
            online_count = len(active_connections)
            total_count = len(registered_bots)
            
            if online_count == 0:
                return HealthStatus.UNHEALTHY, f"所有子機器人都離線 (0/{total_count})"
            elif online_count < total_count:
                return HealthStatus.DEGRADED, f"部分子機器人離線 ({online_count}/{total_count})"
            else:
                return HealthStatus.HEALTHY, f"所有子機器人都在線 ({online_count}/{total_count})"
                
        except Exception as e:
            return HealthStatus.UNHEALTHY, f"子機器人服務健康檢查錯誤: {str(e)}"
    
    async def _check_ai_service_health(
        self, 
        service, 
        health_data: Dict[str, Any]
    ) -> Tuple[HealthStatus, str]:
        """
        檢查AI服務的健康狀態
        
        Args:
            service: AI服務實例
            health_data: 健康檢查數據
            
        Returns:
            (健康狀態, 狀態訊息)
        """
        try:
            # 檢查基本初始化狀態
            if not health_data.get('initialized', False):
                return HealthStatus.UNHEALTHY, "AI服務未初始化"
            
            # 檢查AI提供商狀態
            providers = getattr(service, 'providers', {})
            if not providers:
                return HealthStatus.UNHEALTHY, "沒有可用的AI提供商"
            
            # 檢查默認提供商
            default_provider = getattr(service, 'default_provider', None)
            if default_provider and default_provider not in providers:
                return HealthStatus.DEGRADED, f"默認提供商 {default_provider} 不可用"
            
            # 檢查速率限制狀態
            rate_limit_tracker = getattr(service, 'rate_limit_tracker', {})
            if len(rate_limit_tracker) > 1000:  # 如果追蹤的用戶太多，可能需要清理
                return HealthStatus.DEGRADED, f"AI服務負載較高，追蹤 {len(rate_limit_tracker)} 個用戶"
            
            return HealthStatus.HEALTHY, f"AI服務健康，支援 {len(providers)} 個提供商"
            
        except Exception as e:
            return HealthStatus.UNHEALTHY, f"AI服務健康檢查錯誤: {str(e)}"
    
    async def _attempt_service_recovery(self, service_name: str) -> bool:
        """
        嘗試自動恢復服務
        
        Args:
            service_name: 服務名稱
            
        Returns:
            是否恢復成功
        """
        try:
            service = self._services.get(service_name)
            if not service:
                return False
            
            logger.info(f"嘗試自動恢復服務: {service_name}")
            
            # 檢查服務是否支援重啟
            if hasattr(service, 'restart'):
                await service.restart()
                self.update_service_status(
                    service_name,
                    ServiceStatus.RUNNING,
                    "服務已自動恢復"
                )
                logger.info(f"服務 {service_name} 自動恢復成功")
                return True
            elif hasattr(service, 'stop') and hasattr(service, 'start'):
                await service.stop()
                await asyncio.sleep(2)  # 等待一下
                await service.start()
                self.update_service_status(
                    service_name,
                    ServiceStatus.RUNNING,
                    "服務已自動重啟"
                )
                logger.info(f"服務 {service_name} 自動重啟成功")
                return True
            else:
                logger.warning(f"服務 {service_name} 不支援自動恢復")
                return False
                
        except Exception as e:
            logger.error(f"自動恢復服務 {service_name} 失敗: {e}")
            return False
    
    def get_service_status(self, service_name: str) -> Optional[ServiceStatus]:
        """獲取服務狀態"""
        return self._service_statuses.get(service_name)
        
    def get_service_health(self, service_name: str) -> Optional[ServiceHealthInfo]:
        """獲取服務健康信息"""
        return self._health_info.get(service_name)
        
    def get_all_services_status(self) -> Dict[str, Dict[str, Any]]:
        """獲取所有服務的狀態和健康信息"""
        result = {}
        
        for service_name in self._services.keys():
            status = self._service_statuses.get(service_name)
            health = self._health_info.get(service_name)
            
            result[service_name] = {
                "status": status.value if status else "unknown",
                "health": {
                    "status": health.status.value if health else "unknown",
                    "last_check": health.last_check.isoformat() if health else None,
                    "response_time": health.response_time if health else None,
                    "error_count": health.error_count if health else 0,
                    "message": health.message if health else ""
                }
            }
            
        return result
        
    def get_lifecycle_events(
        self, 
        service_name: Optional[str] = None,
        limit: int = 100
    ) -> List[LifecycleEvent]:
        """
        獲取生命週期事件
        
        參數：
            service_name: 服務名稱，如果為 None 則返回所有服務的事件
            limit: 返回事件的最大數量
            
        返回：
            事件列表
        """
        events = self._lifecycle_events
        
        if service_name:
            events = [e for e in events if e.service_name == service_name]
            
        # 按時間倒序排序，返回最近的事件
        events = sorted(events, key=lambda e: e.timestamp, reverse=True)
        
        return events[:limit]
        
    def add_event_listener(self, event_type: str, callback: Callable):
        """
        添加事件監聽器
        
        參數：
            event_type: 事件類型
            callback: 回調函數
        """
        if event_type not in self._event_listeners:
            self._event_listeners[event_type] = []
            
        self._event_listeners[event_type].append(callback)
        logger.debug(f"為事件類型 {event_type} 添加監聽器")
        
    def remove_event_listener(self, event_type: str, callback: Callable):
        """
        移除事件監聽器
        
        參數：
            event_type: 事件類型  
            callback: 回調函數
        """
        if event_type in self._event_listeners:
            try:
                self._event_listeners[event_type].remove(callback)
                logger.debug(f"為事件類型 {event_type} 移除監聽器")
            except ValueError:
                pass
                
    async def _health_check_loop(self):
        """健康檢查循環"""
        while self._running:
            try:
                # 為所有註冊的服務執行健康檢查
                check_tasks = []
                for service_name in list(self._services.keys()):
                    task = asyncio.create_task(
                        self.perform_health_check(service_name)
                    )
                    check_tasks.append(task)
                    
                if check_tasks:
                    await asyncio.gather(*check_tasks, return_exceptions=True)
                    
                await asyncio.sleep(self.check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"健康檢查循環發生錯誤: {e}")
                await asyncio.sleep(self.check_interval)
                
    def _record_event(
        self,
        service_name: str,
        event_type: str,
        old_status: Optional[ServiceStatus] = None,
        new_status: Optional[ServiceStatus] = None,
        message: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ):
        """記錄生命週期事件"""
        event = LifecycleEvent(
            service_name=service_name,
            event_type=event_type,
            timestamp=datetime.now(),
            old_status=old_status,
            new_status=new_status,
            message=message,
            metadata=metadata or {}
        )
        
        self._lifecycle_events.append(event)
        
        # 限制事件數量
        if len(self._lifecycle_events) > self.max_events:
            self._lifecycle_events = self._lifecycle_events[-self.max_events:]
            
    def _trigger_event(self, event_type: str, service_name: str, data: Dict[str, Any]):
        """觸發事件監聽器"""
        if event_type in self._event_listeners:
            for callback in self._event_listeners[event_type]:
                try:
                    callback(service_name, data)
                except Exception as e:
                    logger.error(f"事件監聽器執行失敗 ({event_type}): {e}")


# 全域生命週期管理器實例
lifecycle_manager = ServiceLifecycleManager()