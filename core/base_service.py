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
        name: Optional[str] = None
    ) -> str:
        """
        註冊服務
        
        參數：
            service: 要註冊的服務實例
            name: 服務名稱，如果不提供則使用類別名稱
            
        返回：
            服務名稱
        """
        async with self._lock:
            service_name = name or service.__class__.__name__
            
            if service_name in self._services:
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
        if not self._initialization_order:
            return
        
        # 反向清理
        for service_name in reversed(self._initialization_order):
            if service_name in self._services:
                try:
                    await self._services[service_name].cleanup()
                    logger.info(f"服務 {service_name} 已清理")
                except Exception as e:
                    logger.error(f"清理服務 {service_name} 時發生錯誤：{e}")


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
    
    def __init__(self, name: Optional[str] = None):
        """
        初始化服務
        
        參數：
            name: 服務名稱，如果不提供則使用類別名稱
        """
        self.name = name or self.__class__.__name__
        self.logger = logging.getLogger(f'service.{self.name}')
        self._initialized = False
        self._initialization_time: Optional[datetime] = None
        self._dependencies: Dict[str, 'BaseService'] = {}
        
        # 弱引用避免循環引用
        self._dependent_services: weakref.WeakSet['BaseService'] = weakref.WeakSet()
    
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
        return {
            "service_name": self.name,
            "initialized": self._initialized,
            "initialization_time": self._initialization_time.isoformat() if self._initialization_time else None,
            "uptime_seconds": self.uptime,
            "dependencies": list(self._dependencies.keys()),
            "dependent_services": len(self._dependent_services)
        }
    
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