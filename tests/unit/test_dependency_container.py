"""
🔧 依賴注入容器測試
Discord ADR Bot v1.6 - 依賴注入容器測試套件

測試範圍：
- 服務註冊測試
- 服務解析測試
- 生命週期管理測試
- 作用域測試
- 錯誤處理測試

作者：Discord ADR Bot 測試專家
版本：v1.6
"""

import pytest
import pytest_asyncio
import asyncio
from unittest.mock import Mock, AsyncMock

from cogs.core.dependency_container import (
    DependencyContainer, ServiceLifetime, ServiceDescriptor,
    DependencyResolutionError, CircularDependencyError, ServiceNotFoundError,
    get_global_container, dispose_global_container
)


class TestServiceDescriptor:
    """服務描述符測試"""
    
    def test_service_descriptor_creation(self):
        """測試服務描述符創建"""
        descriptor = ServiceDescriptor(
            service_type=str,
            implementation_type=str,
            lifetime=ServiceLifetime.SINGLETON
        )
        
        assert descriptor.service_type == str
        assert descriptor.implementation_type == str
        assert descriptor.lifetime == ServiceLifetime.SINGLETON
        assert descriptor.factory is None
        assert descriptor.instance is None
    
    def test_service_descriptor_with_factory(self):
        """測試帶工廠方法的服務描述符"""
        factory = lambda: "test"
        descriptor = ServiceDescriptor(
            service_type=str,
            factory=factory,
            lifetime=ServiceLifetime.TRANSIENT
        )
        
        assert descriptor.service_type == str
        assert descriptor.factory == factory
        assert descriptor.lifetime == ServiceLifetime.TRANSIENT


class TestDependencyContainer:
    """依賴注入容器測試"""
    
    @pytest_asyncio.fixture
    async def container(self):
        """創建測試容器"""
        container = DependencyContainer()
        await container.initialize()
        yield container
        await container.dispose()
    
    @pytest.mark.asyncio
    async def test_container_initialization(self, container):
        """測試容器初始化"""
        assert container._initialized is True
        assert len(container._services) > 0  # 應該有核心服務
    
    @pytest.mark.asyncio
    async def test_register_transient_service(self, container):
        """測試註冊瞬時服務"""
        class TestService:
            def __init__(self):
                self.value = "test"
        
        container.register_transient(TestService)
        
        # 解析兩次應該得到不同的實例
        instance1 = await container.resolve(TestService)
        instance2 = await container.resolve(TestService)
        
        assert isinstance(instance1, TestService)
        assert isinstance(instance2, TestService)
        assert instance1 is not instance2  # 不同實例
        assert instance1.value == instance2.value == "test"
    
    @pytest.mark.asyncio
    async def test_register_singleton_service(self, container):
        """測試註冊單例服務"""
        class TestService:
            def __init__(self):
                self.value = "test"
        
        container.register_singleton(TestService)
        
        # 解析兩次應該得到相同的實例
        instance1 = await container.resolve(TestService)
        instance2 = await container.resolve(TestService)
        
        assert isinstance(instance1, TestService)
        assert isinstance(instance2, TestService)
        assert instance1 is instance2  # 相同實例
        assert instance1.value == "test"
    
    @pytest.mark.asyncio
    async def test_register_scoped_service(self, container):
        """測試註冊作用域服務"""
        class TestService:
            def __init__(self):
                self.value = "test"
        
        container.register_scoped(TestService)
        
        # 在同一作用域內應該是相同實例
        instance1 = await container.resolve(TestService, scope="test_scope")
        instance2 = await container.resolve(TestService, scope="test_scope")
        assert instance1 is instance2
        
        # 在不同作用域內應該是不同實例
        instance3 = await container.resolve(TestService, scope="other_scope")
        assert instance1 is not instance3
    
    @pytest.mark.asyncio
    async def test_register_factory_service(self, container):
        """測試註冊工廠方法服務"""
        def test_factory():
            return "factory_result"
        
        container.register_factory(str, test_factory, ServiceLifetime.SINGLETON)
        
        result = await container.resolve(str)
        assert result == "factory_result"
    
    @pytest.mark.asyncio
    async def test_register_async_factory_service(self, container):
        """測試註冊異步工廠方法服務"""
        async def async_factory():
            return "async_factory_result"
        
        container.register_factory(str, async_factory, ServiceLifetime.TRANSIENT)
        
        result = await container.resolve(str)
        assert result == "async_factory_result"
    
    @pytest.mark.asyncio
    async def test_register_instance_service(self, container):
        """測試註冊實例服務"""
        test_instance = {"key": "value"}
        container.register_instance(dict, test_instance)
        
        result = await container.resolve(dict)
        assert result is test_instance
        assert result["key"] == "value"
    
    @pytest.mark.asyncio
    async def test_service_not_found_error(self, container):
        """測試服務未找到錯誤"""
        class UnregisteredService:
            pass
        
        with pytest.raises(ServiceNotFoundError) as exc_info:
            await container.resolve(UnregisteredService)
        
        assert "服務未註冊: UnregisteredService" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_circular_dependency_detection(self, container):
        """測試循環依賴檢測"""
        class ServiceA:
            pass
        
        class ServiceB:
            pass
        
        # 模擬循環依賴
        container._resolution_stack = [ServiceA]
        container.register_transient(ServiceA)
        
        with pytest.raises(CircularDependencyError) as exc_info:
            await container.resolve(ServiceA)
        
        assert "檢測到循環依賴" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_service_with_async_initialize(self, container):
        """測試帶異步初始化的服務"""
        class AsyncInitService:
            def __init__(self):
                self.initialized = False
            
            async def initialize(self):
                self.initialized = True
        
        container.register_transient(AsyncInitService)
        
        instance = await container.resolve(AsyncInitService)
        assert instance.initialized is True
    
    @pytest.mark.asyncio
    async def test_scope_management(self, container):
        """測試作用域管理"""
        class ScopedService:
            def __init__(self):
                self.value = "scoped"
        
        container.register_scoped(ScopedService)
        
        async with container.create_scope("test_scope") as scope_name:
            instance1 = await container.resolve(ScopedService, scope=scope_name)
            instance2 = await container.resolve(ScopedService, scope=scope_name)
            assert instance1 is instance2
        
        # 作用域銷毀後，應該清理實例
        assert "test_scope" not in container._scoped_instances
    
    @pytest.mark.asyncio
    async def test_clear_scope(self, container):
        """測試清理作用域"""
        class ScopedService:
            pass
        
        container.register_scoped(ScopedService)
        
        # 創建作用域實例
        await container.resolve(ScopedService, scope="test_scope")
        assert "test_scope" in container._scoped_instances
        
        # 清理作用域
        container.clear_scope("test_scope")
        assert "test_scope" not in container._scoped_instances
    
    @pytest.mark.asyncio
    async def test_service_info(self, container):
        """測試服務信息獲取"""
        class TestService:
            pass
        
        container.register_singleton(TestService)
        container.register_instance(str, "test")
        
        info = container.get_service_info()
        
        assert "total_services" in info
        assert "singletons" in info
        assert "services" in info
        assert info["total_services"] >= 2
        
        # 檢查服務詳情
        service_names = [s["service_type"] for s in info["services"]]
        assert "TestService" in service_names
        assert "str" in service_names
    
    @pytest.mark.asyncio
    async def test_container_dispose(self, container):
        """測試容器釋放"""
        class DisposableService:
            def __init__(self):
                self.disposed = False
            
            async def dispose(self):
                self.disposed = True
        
        container.register_singleton(DisposableService)
        instance = await container.resolve(DisposableService)
        
        await container.dispose()
        
        assert instance.disposed is True
        assert container._initialized is False
        assert len(container._services) == 0
        assert len(container._singletons) == 0


class TestGlobalContainer:
    """全局容器測試"""
    
    @pytest.mark.asyncio
    async def test_global_container_singleton(self):
        """測試全局容器單例模式"""
        container1 = await get_global_container()
        container2 = await get_global_container()
        
        assert container1 is container2
        
        # 清理
        await dispose_global_container()
    
    @pytest.mark.asyncio
    async def test_global_container_dispose(self):
        """測試全局容器釋放"""
        container = await get_global_container()
        assert container is not None
        
        await dispose_global_container()
        
        # 再次獲取應該是新實例
        new_container = await get_global_container()
        assert new_container is not container
        
        # 清理
        await dispose_global_container()


class TestErrorHandling:
    """錯誤處理測試"""
    
    @pytest_asyncio.fixture
    async def container(self):
        """創建測試容器"""
        container = DependencyContainer()
        await container.initialize()
        yield container
        await container.dispose()
    
    @pytest.mark.asyncio
    async def test_creation_error_handling(self, container):
        """測試創建實例時的錯誤處理"""
        class FailingService:
            def __init__(self):
                raise ValueError("Construction failed")
        
        container.register_transient(FailingService)
        
        with pytest.raises(DependencyResolutionError) as exc_info:
            await container.resolve(FailingService)
        
        assert "創建實例失敗" in str(exc_info.value)
        assert "Construction failed" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_missing_implementation_type(self, container):
        """測試缺少實現類型的錯誤"""
        # 手動創建一個沒有實現類型的描述符
        descriptor = ServiceDescriptor(
            service_type=str,
            implementation_type=None
        )
        container._services[str] = descriptor
        
        with pytest.raises(DependencyResolutionError) as exc_info:
            await container.resolve(str)
        
        assert "沒有實現類型" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 