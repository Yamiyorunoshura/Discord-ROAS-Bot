"""
🔧 依賴注入容器
Discord ADR Bot v1.6 - 統一依賴管理系統

提供企業級的依賴注入功能：
- 服務註冊與解析
- 生命週期管理
- 循環依賴檢測

作者：Discord ADR Bot 架構師
版本：v1.6
"""

import asyncio
import logging
from enum import Enum
from typing import Any, Dict, Type, TypeVar, Optional, Callable
from contextlib import asynccontextmanager

# 設置日誌
logger = logging.getLogger(__name__)

# 類型變量
T = TypeVar('T')

class ServiceLifetime(Enum):
    """服務生命週期枚舉"""
    TRANSIENT = "transient"    # 每次請求都創建新實例
    SINGLETON = "singleton"    # 整個應用程序生命週期內只有一個實例
    SCOPED = "scoped"         # 在特定範圍內是單例

class ServiceDescriptor:
    """服務描述符"""
    
    def __init__(self, service_type: Type, implementation_type: Type | None = None, 
                 factory: Callable | None = None, instance: Any | None = None,
                 lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT):
        self.service_type = service_type
        self.implementation_type = implementation_type
        self.factory = factory
        self.instance = instance
        self.lifetime = lifetime

class DependencyResolutionError(Exception):
    """依賴解析錯誤"""
    pass

class CircularDependencyError(DependencyResolutionError):
    """循環依賴錯誤"""
    pass

class ServiceNotFoundError(DependencyResolutionError):
    """服務未找到錯誤"""
    pass

class DependencyContainer:
    """
    專業級依賴注入容器
    
    提供完整的依賴管理功能：
    - 服務註冊和解析
    - 生命週期管理
    - 循環依賴檢測
    """
    
    def __init__(self):
        self._services: Dict[Type, ServiceDescriptor] = {}
        self._singletons: Dict[Type, Any] = {}
        self._scoped_instances: Dict[str, Dict[Type, Any]] = {}
        self._resolution_stack: list = []
        self._initialized = False
        self._lock = asyncio.Lock()
        
    async def initialize(self):
        """初始化容器"""
        if self._initialized:
            return
            
        async with self._lock:
            if not self._initialized:
                logger.info("【依賴容器】正在初始化...")
                
                # 註冊核心服務
                await self._register_core_services()
                
                self._initialized = True
                logger.info("【依賴容器】初始化完成")
    
    async def _register_core_services(self):
        """註冊核心服務"""
        # 註冊連接池服務
        from .database_pool import get_global_pool
        pool = await get_global_pool()
        self.register_instance(type(pool), pool)
        
        logger.info("【依賴容器】核心服務註冊完成")
    
    def register_transient(self, service_type: Type[T], implementation_type: Type[T | None] = None) -> 'DependencyContainer':
        """註冊瞬時服務（每次請求都創建新實例）"""
        return self._register_service(
            service_type, 
            implementation_type or service_type,
            ServiceLifetime.TRANSIENT
        )
    
    def register_singleton(self, service_type: Type[T], implementation_type: Type[T | None] = None) -> 'DependencyContainer':
        """註冊單例服務（整個應用程序生命週期內只有一個實例）"""
        return self._register_service(
            service_type,
            implementation_type or service_type,
            ServiceLifetime.SINGLETON
        )
    
    def register_scoped(self, service_type: Type[T], implementation_type: Type[T | None] = None) -> 'DependencyContainer':
        """註冊作用域服務（在特定範圍內是單例）"""
        return self._register_service(
            service_type,
            implementation_type or service_type,
            ServiceLifetime.SCOPED
        )
    
    def register_factory(self, service_type: Type[T], factory: Callable, lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT) -> 'DependencyContainer':
        """註冊工廠方法服務"""
        descriptor = ServiceDescriptor(
            service_type=service_type,
            factory=factory,
            lifetime=lifetime
        )
        
        self._services[service_type] = descriptor
        logger.debug(f"【依賴容器】註冊工廠服務: {service_type.__name__} ({lifetime.value})")
        return self
    
    def register_instance(self, service_type: Type[T], instance: T) -> 'DependencyContainer':
        """註冊實例服務"""
        descriptor = ServiceDescriptor(
            service_type=service_type,
            instance=instance,
            lifetime=ServiceLifetime.SINGLETON
        )
        
        self._services[service_type] = descriptor
        self._singletons[service_type] = instance
        logger.debug(f"【依賴容器】註冊實例服務: {service_type.__name__}")
        return self
    
    def _register_service(self, service_type: Type, implementation_type: Type, lifetime: ServiceLifetime) -> 'DependencyContainer':
        """內部服務註冊方法"""
        descriptor = ServiceDescriptor(
            service_type=service_type,
            implementation_type=implementation_type,
            lifetime=lifetime
        )
        
        self._services[service_type] = descriptor
        logger.debug(f"【依賴容器】註冊服務: {service_type.__name__} -> {implementation_type.__name__} ({lifetime.value})")
        return self
    
    async def resolve(self, service_type: Type[T], scope: str | None = None) -> T:
        """解析服務實例"""
        if not self._initialized:
            await self.initialize()
            
        # 檢查循環依賴
        if service_type in self._resolution_stack:
            cycle = " -> ".join([str(t.__name__) for t in self._resolution_stack]) + f" -> {service_type.__name__}"
            raise CircularDependencyError(f"檢測到循環依賴: {cycle}")
        
        # 檢查服務是否已註冊
        if service_type not in self._services:
            raise ServiceNotFoundError(f"服務未註冊: {service_type.__name__}")
        
        descriptor = self._services[service_type]
        
        # 根據生命週期返回實例
        if descriptor.lifetime == ServiceLifetime.SINGLETON:
            return await self._resolve_singleton(service_type, descriptor)
        elif descriptor.lifetime == ServiceLifetime.SCOPED:
            return await self._resolve_scoped(service_type, descriptor, scope or "default")
        else:
            return await self._resolve_transient(service_type, descriptor)
    
    async def _resolve_singleton(self, service_type: Type[T], descriptor: ServiceDescriptor) -> T:
        """解析單例服務"""
        if service_type in self._singletons:
            return self._singletons[service_type]
        
        async with self._lock:
            if service_type not in self._singletons:
                instance = await self._create_instance(descriptor)
                self._singletons[service_type] = instance
                logger.debug(f"【依賴容器】創建單例實例: {service_type.__name__}")
            
            return self._singletons[service_type]
    
    async def _resolve_scoped(self, service_type: Type[T], descriptor: ServiceDescriptor, scope: str) -> T:
        """解析作用域服務"""
        if scope not in self._scoped_instances:
            self._scoped_instances[scope] = {}
        
        scoped_dict = self._scoped_instances[scope]
        
        if service_type not in scoped_dict:
            instance = await self._create_instance(descriptor)
            scoped_dict[service_type] = instance
            logger.debug(f"【依賴容器】創建作用域實例: {service_type.__name__} (scope: {scope})")
        
        return scoped_dict[service_type]
    
    async def _resolve_transient(self, service_type: Type[T], descriptor: ServiceDescriptor) -> T:
        """解析瞬時服務"""
        instance = await self._create_instance(descriptor)
        logger.debug(f"【依賴容器】創建瞬時實例: {service_type.__name__}")
        return instance
    
    async def _create_instance(self, descriptor: ServiceDescriptor) -> Any:
        """創建服務實例"""
        # 如果已有實例，直接返回
        if descriptor.instance is not None:
            return descriptor.instance
        
        # 如果有工廠方法，使用工廠方法創建
        if descriptor.factory is not None:
            if asyncio.iscoroutinefunction(descriptor.factory):
                return await descriptor.factory()
            else:
                return descriptor.factory()
        
        # 使用構造函數創建實例
        if descriptor.implementation_type is None:
            raise DependencyResolutionError(f"服務 {descriptor.service_type.__name__} 沒有實現類型")
        
        # 簡化版本：暫時不支持自動依賴注入，需要手動註冊依賴
        try:
            instance = descriptor.implementation_type()
            
            # 如果實例有異步初始化方法，調用它
            if hasattr(instance, 'initialize') and asyncio.iscoroutinefunction(instance.initialize):
                await instance.initialize()
            
            return instance
        except Exception as e:
            raise DependencyResolutionError(f"創建實例失敗 {descriptor.implementation_type.__name__}: {e}")
    
    def clear_scope(self, scope: str):
        """清理作用域"""
        if scope in self._scoped_instances:
            del self._scoped_instances[scope]
            logger.debug(f"【依賴容器】清理作用域: {scope}")
    
    @asynccontextmanager
    async def create_scope(self, scope_name: str | None = None):
        """創建作用域上下文管理器"""
        if scope_name is None:
            scope_name = f"scope_{id(self)}"
        
        try:
            logger.debug(f"【依賴容器】創建作用域: {scope_name}")
            yield scope_name
        finally:
            self.clear_scope(scope_name)
            logger.debug(f"【依賴容器】銷毀作用域: {scope_name}")
    
    async def dispose(self):
        """釋放容器資源"""
        try:
            # 清理所有作用域
            for scope in list(self._scoped_instances.keys()):
                self.clear_scope(scope)
            
            # 清理單例實例
            for instance in self._singletons.values():
                if hasattr(instance, 'dispose') and asyncio.iscoroutinefunction(instance.dispose):
                    try:
                        await instance.dispose()
                    except Exception as e:
                        logger.warning(f"【依賴容器】釋放實例失敗: {e}")
            
            self._singletons.clear()
            self._services.clear()
            self._initialized = False
            
            logger.info("【依賴容器】已釋放所有資源")
            
        except Exception as e:
            logger.error(f"【依賴容器】釋放資源時發生錯誤: {e}")
    
    def get_service_info(self) -> Dict[str, Any]:
        """獲取服務信息"""
        return {
            "total_services": len(self._services),
            "singletons": len(self._singletons),
            "scoped_instances": {scope: len(instances) for scope, instances in self._scoped_instances.items()},
            "services": [
                {
                    "service_type": desc.service_type.__name__,
                    "implementation_type": desc.implementation_type.__name__ if desc.implementation_type else None,
                    "lifetime": desc.lifetime.value,
                    "has_factory": desc.factory is not None,
                    "has_instance": desc.instance is not None
                }
                for desc in self._services.values()
            ]
        }

# 全局依賴容器實例
_global_container: DependencyContainer | None = None
_container_lock = asyncio.Lock()

async def get_global_container() -> DependencyContainer:
    """獲取全局依賴容器實例"""
    global _global_container
    
    async with _container_lock:
        if _global_container is None:
            _global_container = DependencyContainer()
            await _global_container.initialize()
    
    return _global_container

async def dispose_global_container():
    """釋放全局依賴容器"""
    global _global_container
    
    if _global_container is not None:
        await _global_container.dispose()
        _global_container = None 