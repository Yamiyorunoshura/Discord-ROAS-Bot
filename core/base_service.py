"""
核心服務基礎類別
Task ID: 1 - 建立核心架構基礎

這個模組提供了所有服務的基礎抽象類別，包含：
- 統一的服務初始化和清理機制
- 權限驗證介面
- 依賴注入支援
- 統一的日誌記錄
- 服務註冊和發現機制
"""
import asyncio
import logging
import functools
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Dict, Any, Type, TypeVar, List, Set
from datetime import datetime
import weakref

from .exceptions import (
    ServiceError, 
    ServiceInitializationError, 
    ServicePermissionError,
    handle_errors
)

# 設定日誌記錄器
logger = logging.getLogger('core.base_service')

# 泛型類型變數
T = TypeVar('T', bound='BaseService')

# 新增：服務類型枚舉，支援v2.4.4新功能
class ServiceType(Enum):
    """服務類型枚舉"""
    BASE = "base"                    # 基礎服務
    DATABASE = "database"            # 資料庫服務
    DEPLOYMENT = "deployment"        # 部署服務 (新增)
    SUB_BOT = "sub_bot"             # 子機器人服務 (新增)
    AI_SERVICE = "ai_service"        # AI服務 (新增)
    SECURITY = "security"            # 安全服務
    MONITORING = "monitoring"        # 監控服務


class ServiceRegistry:
    """
    服務註冊表
    
    管理所有已註冊的服務實例，提供服務發現和依賴注入功能
    """
    
    def __init__(self):
        self._services: Dict[str, 'BaseService'] = {}
        self._service_types: Dict[Type['BaseService'], str] = {}
        self._dependencies: Dict[str, Set[str]] = {}
        self._initialization_order: List[str] = []
        self._lock = asyncio.Lock()
    
    async def register_service(
        self, 
        service: 'BaseService', 
        name: Optional[str] = None,
        force_reregister: bool = False
    ) -> str:
        """
        註冊服務
        
        參數：
            service: 要註冊的服務實例
            name: 服務名稱，如果不提供則使用類別名稱
            force_reregister: 是否強制重新註冊（測試環境用）
            
        返回：
            服務名稱
        """
        async with self._lock:
            service_name = name or service.name
            
            if service_name in self._services:
                if force_reregister:
                    logger.warning(f"強制重新註冊服務 {service_name}")
                    # 先清理舊服務
                    old_service = self._services[service_name]
                    if old_service.is_initialized:
                        try:
                            await old_service.cleanup()
                        except Exception as e:
                            logger.error(f"清理舊服務 {service_name} 時發生錯誤：{e}")
                    
                    # 移除舊註冊
                    del self._services[service_name]
                    if service.__class__ in self._service_types:
                        del self._service_types[service.__class__]
                    if service_name in self._dependencies:
                        del self._dependencies[service_name]
                    if service_name in self._initialization_order:
                        self._initialization_order.remove(service_name)
                else:
                    raise ServiceError(
                        f"服務 {service_name} 已經註冊",
                        service_name=service_name,
                        operation="register"
                    )
            
            self._services[service_name] = service
            self._service_types[service.__class__] = service_name
            self._dependencies[service_name] = set()
            
            logger.info(f"服務 {service_name} 已註冊")
            return service_name
    
    async def unregister_service(self, name: str) -> bool:
        """
        取消註冊服務
        
        參數：
            name: 服務名稱
            
        返回：
            是否成功取消註冊
        """
        async with self._lock:
            if name not in self._services:
                return False
            
            service = self._services[name]
            
            # 檢查是否有其他服務依賴此服務
            dependents = []
            for service_name, deps in self._dependencies.items():
                if name in deps and service_name in self._services:
                    dependents.append(service_name)
            
            if dependents:
                raise ServiceError(
                    f"無法取消註冊服務 {name}，因為有其他服務依賴它：{', '.join(dependents)}",
                    service_name=name,
                    operation="unregister",
                    details={"dependents": dependents}
                )
            
            # 清理服務（只有已初始化的服務才需要清理）
            if service.is_initialized:
                try:
                    await service.cleanup()
                except Exception as e:
                    logger.error(f"清理服務 {name} 時發生錯誤：{e}")
            
            # 移除註冊
            del self._services[name]
            del self._service_types[service.__class__]
            del self._dependencies[name]
            
            if name in self._initialization_order:
                self._initialization_order.remove(name)
            
            logger.info(f"服務 {name} 已取消註冊")
            return True
    
    def get_service(self, name: str) -> Optional['BaseService']:
        """
        獲取服務實例
        
        參數：
            name: 服務名稱
            
        返回：
            服務實例，如果不存在則返回 None
        """
        return self._services.get(name)
    
    def get_service_by_type(self, service_type: Type[T]) -> Optional[T]:
        """
        根據類型獲取服務實例
        
        參數：
            service_type: 服務類型
            
        返回：
            服務實例，如果不存在則返回 None
        """
        service_name = self._service_types.get(service_type)
        if service_name:
            return self._services.get(service_name)
        return None
    
    def list_services(self) -> List[str]:
        """獲取所有已註冊的服務名稱"""
        return list(self._services.keys())
    
    def is_registered(self, name: str) -> bool:
        """檢查服務是否已註冊"""
        return name in self._services
    
    def add_dependency(self, service_name: str, dependency_name: str):
        """
        添加服務依賴關係
        
        參數：
            service_name: 服務名稱
            dependency_name: 依賴的服務名稱
        """
        if service_name not in self._dependencies:
            self._dependencies[service_name] = set()
        
        self._dependencies[service_name].add(dependency_name)
        logger.debug(f"添加依賴：{service_name} -> {dependency_name}")
    
    def get_initialization_order(self) -> List[str]:
        """
        獲取服務初始化順序（基於依賴關係的拓撲排序）
        
        返回：
            按初始化順序排列的服務名稱列表
        """
        # 簡單的拓撲排序實現
        in_degree = {name: 0 for name in self._services.keys()}
        
        # 計算入度
        for service_name, deps in self._dependencies.items():
            for dep in deps:
                if dep in in_degree:
                    in_degree[service_name] += 1
        
        # 拓撲排序
        queue = [name for name, degree in in_degree.items() if degree == 0]
        result = []
        
        while queue:
            current = queue.pop(0)
            result.append(current)
            
            # 移除當前節點的所有邊
            for service_name, deps in self._dependencies.items():
                if current in deps:
                    in_degree[service_name] -= 1
                    if in_degree[service_name] == 0:
                        queue.append(service_name)
        
        if len(result) != len(self._services):
            raise ServiceError(
                "服務依賴關係中存在循環依賴",
                service_name="ServiceRegistry",
                operation="get_initialization_order"
            )
        
        return result
    
    async def initialize_all_services(self) -> bool:
        """
        按依賴順序初始化所有服務
        
        返回：
            是否全部初始化成功
        """
        try:
            order = self.get_initialization_order()
            self._initialization_order = order.copy()
            
            for service_name in order:
                service = self._services[service_name]
                if not await service.initialize():
                    logger.error(f"服務 {service_name} 初始化失敗")
                    return False
                    
            logger.info(f"所有服務初始化完成，順序：{' -> '.join(order)}")
            return True
            
        except Exception as e:
            logger.error(f"初始化服務時發生錯誤：{e}")
            return False
    
    async def cleanup_all_services(self):
        """清理所有服務（按初始化順序的反向）"""
        async with self._lock:
            # 記錄清理前的狀態
            service_count = len(self._services)
            logger.info(f"開始清理 {service_count} 個服務")
            
            # 如果有初始化順序，按反向清理
            if self._initialization_order:
                for service_name in reversed(self._initialization_order.copy()):
                    if service_name in self._services:
                        try:
                            service = self._services[service_name]
                            if service.is_initialized:
                                await service.cleanup()
                            logger.debug(f"服務 {service_name} 已清理")
                        except Exception as e:
                            logger.error(f"清理服務 {service_name} 時發生錯誤：{e}")
            else:
                # 如果沒有初始化順序記錄，直接清理所有服務
                for service_name, service in list(self._services.items()):
                    try:
                        if service.is_initialized:
                            await service.cleanup()
                        logger.debug(f"服務 {service_name} 已清理")
                    except Exception as e:
                        logger.error(f"清理服務 {service_name} 時發生錯誤：{e}")
            
            # 強制清除所有註冊表資料
            self._services.clear()
            self._service_types.clear()
            self._dependencies.clear()
            self._initialization_order.clear()
            
            logger.info(f"全域服務註冊表已完全清除（清理了 {service_count} 個服務）")
    
    def reset_for_testing(self):
        """重置註冊表狀態，專用於測試環境"""
        # 同步版本的清理，用於測試環境快速重置
        self._services.clear()
        self._service_types.clear() 
        self._dependencies.clear()
        self._initialization_order.clear()
        logger.info("服務註冊表已重置（測試模式）")
    
    # ========== 新增：v2.4.4 特定服務註冊方法 ==========
    
    async def register_deployment_service(
        self, 
        service: 'BaseService',
        deployment_mode: str,
        name: Optional[str] = None
    ) -> str:
        """
        註冊部署服務
        
        參數：
            service: 部署服務實例
            deployment_mode: 部署模式 ('docker', 'uv', 'fallback')
            name: 服務名稱，如果不提供則使用類別名稱
            
        返回：
            服務名稱
        """
        service_name = await self.register_service(service, name)
        
        # 在服務詳情中記錄部署相關信息
        if hasattr(service, 'service_metadata'):
            service.service_metadata.update({
                'service_type': ServiceType.DEPLOYMENT,
                'deployment_mode': deployment_mode
            })
        else:
            service.service_metadata = {
                'service_type': ServiceType.DEPLOYMENT,
                'deployment_mode': deployment_mode
            }
        
        logger.info(f"部署服務 {service_name} 已註冊 (模式: {deployment_mode})")
        return service_name
    
    async def register_sub_bot_service(
        self,
        service: 'BaseService',
        bot_id: str,
        target_channels: List[str],
        name: Optional[str] = None
    ) -> str:
        """
        註冊子機器人服務
        
        參數：
            service: 子機器人服務實例
            bot_id: 子機器人ID
            target_channels: 目標頻道列表
            name: 服務名稱，如果不提供則使用類別名稱
            
        返回：
            服務名稱
        """
        service_name = await self.register_service(service, name)
        
        # 在服務詳情中記錄子機器人相關信息
        if hasattr(service, 'service_metadata'):
            service.service_metadata.update({
                'service_type': ServiceType.SUB_BOT,
                'bot_id': bot_id,
                'target_channels': target_channels
            })
        else:
            service.service_metadata = {
                'service_type': ServiceType.SUB_BOT,
                'bot_id': bot_id,
                'target_channels': target_channels
            }
        
        logger.info(f"子機器人服務 {service_name} 已註冊 (Bot ID: {bot_id}, 頻道數: {len(target_channels)})")
        return service_name
    
    async def register_ai_service(
        self,
        service: 'BaseService',
        provider: str,
        models: List[str],
        name: Optional[str] = None
    ) -> str:
        """
        註冊AI服務
        
        參數：
            service: AI服務實例
            provider: AI提供商 ('openai', 'anthropic', 'google')
            models: 支援的模型列表
            name: 服務名稱，如果不提供則使用類別名稱
            
        返回：
            服務名稱
        """
        service_name = await self.register_service(service, name)
        
        # 在服務詳情中記錄AI相關信息
        if hasattr(service, 'service_metadata'):
            service.service_metadata.update({
                'service_type': ServiceType.AI_SERVICE,
                'provider': provider,
                'models': models
            })
        else:
            service.service_metadata = {
                'service_type': ServiceType.AI_SERVICE,
                'provider': provider,
                'models': models
            }
        
        logger.info(f"AI服務 {service_name} 已註冊 (提供商: {provider}, 模型數: {len(models)})")
        return service_name
    
    async def get_service_health_status(self, service_name: Optional[str] = None) -> Dict[str, Any]:
        """
        獲取服務健康狀態
        
        參數：
            service_name: 服務名稱，如果為 None 則返回所有服務的健康狀態
            
        返回：
            健康狀態字典
        """
        if service_name:
            # 獲取特定服務的健康狀態
            service = self.get_service(service_name)
            if not service:
                return {
                    "service_name": service_name,
                    "status": "not_found",
                    "message": f"服務 {service_name} 不存在"
                }
            
            health_info = await service.health_check()
            
            # 添加服務類型信息
            if hasattr(service, 'service_metadata'):
                health_info.update(service.service_metadata)
            
            return health_info
        else:
            # 獲取所有服務的健康狀態
            all_health = {
                "timestamp": datetime.now().isoformat(),
                "total_services": len(self._services),
                "services": {}
            }
            
            for name, service in self._services.items():
                try:
                    health_info = await service.health_check()
                    
                    # 添加服務類型信息
                    if hasattr(service, 'service_metadata'):
                        health_info.update(service.service_metadata)
                    
                    all_health["services"][name] = health_info
                except Exception as e:
                    all_health["services"][name] = {
                        "service_name": name,
                        "status": "error",
                        "error": str(e)
                    }
            
            return all_health
    
    def get_services_by_type(self, service_type: ServiceType) -> List[str]:
        """
        根據服務類型獲取服務名稱列表
        
        參數：
            service_type: 服務類型
            
        返回：
            符合類型的服務名稱列表
        """
        matching_services = []
        
        for name, service in self._services.items():
            if hasattr(service, 'service_metadata'):
                metadata_type = service.service_metadata.get('service_type')
                if metadata_type == service_type:
                    matching_services.append(name)
        
        return matching_services


# 全域服務註冊表實例
service_registry = ServiceRegistry()


class BaseService(ABC):
    """
    服務基礎抽象類別
    
    所有業務服務都應該繼承此類別，提供統一的：
    - 初始化和清理生命週期
    - 權限驗證機制
    - 依賴注入支援
    - 日誌記錄
    """
    
    def __init__(self, name: Optional[str] = None, service_type: ServiceType = ServiceType.BASE):
        """
        初始化服務
        
        參數：
            name: 服務名稱，如果不提供則使用類別名稱
            service_type: 服務類型，預設為 BASE
        """
        self.name = name or self.__class__.__name__
        self.logger = logging.getLogger(f'service.{self.name}')
        self._initialized = False
        self._initialization_time: Optional[datetime] = None
        self._dependencies: Dict[str, 'BaseService'] = {}
        
        # 弱引用避免循環引用
        self._dependent_services: weakref.WeakSet['BaseService'] = weakref.WeakSet()
        
        # 新增：服務元數據，支援v2.4.4新功能
        self.service_metadata: Dict[str, Any] = {
            'service_type': service_type,
            'created_at': datetime.now().isoformat(),
            'version': '2.4.4'
        }
    
    @property
    def is_initialized(self) -> bool:
        """檢查服務是否已初始化"""
        return self._initialized
    
    @property
    def initialization_time(self) -> Optional[datetime]:
        """獲取初始化時間"""
        return self._initialization_time
    
    @property
    def uptime(self) -> Optional[float]:
        """獲取服務運行時間（秒）"""
        if self._initialization_time:
            return (datetime.now() - self._initialization_time).total_seconds()
        return None
    
    async def register(self, registry: Optional[ServiceRegistry] = None) -> str:
        """
        註冊服務到服務註冊表
        
        參數：
            registry: 服務註冊表，如果不提供則使用全域註冊表
            
        返回：
            服務名稱
        """
        registry = registry or service_registry
        return await registry.register_service(self, self.name)
    
    def add_dependency(self, dependency: 'BaseService', name: Optional[str] = None):
        """
        添加依賴服務
        
        參數：
            dependency: 依賴的服務實例
            name: 依賴名稱，如果不提供則使用服務的名稱
        """
        dep_name = name or dependency.name
        self._dependencies[dep_name] = dependency
        
        # 確保 _dependent_services 存在並正確添加
        if not hasattr(dependency, '_dependent_services') or dependency._dependent_services is None:
            dependency._dependent_services = weakref.WeakSet()
        
        dependency._dependent_services.add(self)
        
        # 在註冊表中記錄依賴關係
        service_registry.add_dependency(self.name, dep_name)
        
        self.logger.debug(f"添加依賴服務：{dep_name}")
    
    def get_dependency(self, name: str) -> Optional['BaseService']:
        """
        獲取依賴服務
        
        參數：
            name: 依賴服務名稱
            
        返回：
            依賴服務實例
        """
        return self._dependencies.get(name)
    
    @handle_errors(log_errors=True)
    async def initialize(self) -> bool:
        """
        初始化服務
        
        返回：
            是否初始化成功
        """
        if self._initialized:
            self.logger.warning(f"服務 {self.name} 已經初始化過了")
            return True
        
        try:
            self.logger.info(f"開始初始化服務 {self.name}")
            
            # 檢查依賴服務是否已初始化
            for dep_name, dep_service in self._dependencies.items():
                if not dep_service.is_initialized:
                    raise ServiceInitializationError(
                        self.name,
                        f"依賴服務 {dep_name} 尚未初始化"
                    )
            
            # 調用子類別的初始化邏輯
            success = await self._initialize()
            
            if success:
                self._initialized = True
                self._initialization_time = datetime.now()
                self.logger.info(f"服務 {self.name} 初始化成功")
            else:
                self.logger.error(f"服務 {self.name} 初始化失敗")
                
            return success
            
        except Exception as e:
            self.logger.exception(f"服務 {self.name} 初始化時發生錯誤")
            raise ServiceInitializationError(
                self.name,
                f"初始化錯誤：{str(e)}"
            )
    
    @abstractmethod
    async def _initialize(self) -> bool:
        """
        子類別實作的初始化邏輯
        
        返回：
            是否初始化成功
        """
        pass
    
    @handle_errors(log_errors=True)
    async def cleanup(self) -> None:
        """清理服務資源"""
        if not self._initialized:
            return
        
        try:
            self.logger.info(f"開始清理服務 {self.name}")
            
            # 調用子類別的清理邏輯
            await self._cleanup()
            
            self._initialized = False
            self._initialization_time = None
            
            self.logger.info(f"服務 {self.name} 已清理")
            
        except Exception as e:
            self.logger.exception(f"清理服務 {self.name} 時發生錯誤")
            raise ServiceError(
                f"清理服務 {self.name} 失敗：{str(e)}",
                service_name=self.name,
                operation="cleanup"
            )
    
    @abstractmethod
    async def _cleanup(self) -> None:
        """
        子類別實作的清理邏輯
        """
        pass
    
    @handle_errors(log_errors=True)
    async def validate_permissions(
        self, 
        user_id: int, 
        guild_id: Optional[int], 
        action: str
    ) -> bool:
        """
        驗證使用者權限
        
        參數：
            user_id: 使用者 ID
            guild_id: 伺服器 ID（可選）
            action: 要執行的動作
            
        返回：
            是否有權限
        """
        try:
            self.logger.debug(f"驗證權限：用戶 {user_id} 在 {action}")
            
            # 調用子類別的權限驗證邏輯
            has_permission = await self._validate_permissions(user_id, guild_id, action)
            
            if not has_permission:
                self.logger.warning(f"權限驗證失敗：用戶 {user_id} 嘗試執行 {action}")
                raise ServicePermissionError(
                    self.name,
                    user_id,
                    action
                )
            
            return True
            
        except ServicePermissionError:
            raise
        except Exception as e:
            self.logger.exception(f"權限驗證時發生錯誤")
            raise ServiceError(
                f"權限驗證失敗：{str(e)}",
                service_name=self.name,
                operation="validate_permissions",
                details={
                    "user_id": user_id,
                    "guild_id": guild_id,
                    "action": action
                }
            )
    
    @abstractmethod
    async def _validate_permissions(
        self, 
        user_id: int, 
        guild_id: Optional[int], 
        action: str
    ) -> bool:
        """
        子類別實作的權限驗證邏輯
        
        參數：
            user_id: 使用者 ID
            guild_id: 伺服器 ID（可選）
            action: 要執行的動作
            
        返回：
            是否有權限
        """
        pass
    
    async def health_check(self) -> Dict[str, Any]:
        """
        健康檢查
        
        返回：
            服務健康狀態信息
        """
        health_info = {
            "service_name": self.name,
            "initialized": self._initialized,
            "initialization_time": self._initialization_time.isoformat() if self._initialization_time else None,
            "uptime_seconds": self.uptime,
            "dependencies": list(self._dependencies.keys()),
            "dependent_services": len(self._dependent_services),
            "status": "healthy" if self._initialized else "not_initialized"
        }
        
        # 添加服務元數據信息
        if hasattr(self, 'service_metadata'):
            health_info.update(self.service_metadata)
        
        return health_info
    
    def __repr__(self) -> str:
        status = "已初始化" if self._initialized else "未初始化"
        return f"<{self.__class__.__name__}(name='{self.name}', status='{status}')>"


# 依賴注入裝飾器
def inject_service(service_name: str, registry: Optional[ServiceRegistry] = None):
    """
    依賴注入裝飾器
    
    自動注入指定的服務到方法中
    
    參數：
        service_name: 要注入的服務名稱
        registry: 服務註冊表，如果不提供則使用全域註冊表
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            reg = registry or service_registry
            service = reg.get_service(service_name)
            
            if not service:
                raise ServiceError(
                    f"找不到服務 {service_name}",
                    service_name=service_name,
                    operation="inject"
                )
            
            if not service.is_initialized:
                raise ServiceError(
                    f"服務 {service_name} 尚未初始化",
                    service_name=service_name,
                    operation="inject"
                )
            
            # 將服務作為參數注入
            kwargs[service_name.lower()] = service
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def inject_service_by_type(service_type: Type[T], registry: Optional[ServiceRegistry] = None):
    """
    根據類型注入服務的裝飾器
    
    參數：
        service_type: 要注入的服務類型
        registry: 服務註冊表，如果不提供則使用全域註冊表
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            reg = registry or service_registry
            service = reg.get_service_by_type(service_type)
            
            if not service:
                raise ServiceError(
                    f"找不到類型為 {service_type.__name__} 的服務",
                    service_name=service_type.__name__,
                    operation="inject"
                )
            
            if not service.is_initialized:
                raise ServiceError(
                    f"服務 {service.name} 尚未初始化",
                    service_name=service.name,
                    operation="inject"
                )
            
            # 將服務作為參數注入
            param_name = service_type.__name__.lower()
            kwargs[param_name] = service
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator