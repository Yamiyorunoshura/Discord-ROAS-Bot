"""
BaseService 單元測試
Task ID: 1 - 建立核心架構基礎

測試 BaseService 抽象類別的所有功能：
- 服務註冊和發現
- 依賴注入機制
- 初始化和清理生命週期
- 權限驗證
- 錯誤處理
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from core.base_service import (
    BaseService,
    ServiceRegistry,
    service_registry,
    inject_service,
    inject_service_by_type
)
from core.exceptions import (
    ServiceError,
    ServiceInitializationError,
    ServicePermissionError
)


class MockService(BaseService):
    """測試用的模擬服務"""
    
    def __init__(self, name: str = "MockService", fail_init: bool = False, fail_permissions: bool = False):
        super().__init__(name)
        self.fail_init = fail_init
        self.fail_permissions = fail_permissions
        self.initialized_called = False
        self.cleanup_called = False
        self.permissions_called = False
    
    async def _initialize(self) -> bool:
        self.initialized_called = True
        if self.fail_init:
            return False
        return True
    
    async def _cleanup(self) -> None:
        self.cleanup_called = True
    
    async def _validate_permissions(self, user_id: int, guild_id: int, action: str) -> bool:
        self.permissions_called = True
        if self.fail_permissions:
            return False
        return True


class DependentService(BaseService):
    """有依賴的測試服務"""
    
    def __init__(self, dependency: BaseService):
        super().__init__("DependentService")
        self.add_dependency(dependency)
        self.initialized_called = False
    
    async def _initialize(self) -> bool:
        self.initialized_called = True
        return True
    
    async def _cleanup(self) -> None:
        pass
    
    async def _validate_permissions(self, user_id: int, guild_id: int, action: str) -> bool:
        return True


@pytest.fixture
def clean_registry():
    """清空服務註冊表的測試夾具"""
    original_services = service_registry._services.copy()
    original_types = service_registry._service_types.copy()
    original_deps = service_registry._dependencies.copy()
    original_order = service_registry._initialization_order.copy()
    
    service_registry._services.clear()
    service_registry._service_types.clear()
    service_registry._dependencies.clear()
    service_registry._initialization_order.clear()
    
    yield service_registry
    
    service_registry._services = original_services
    service_registry._service_types = original_types
    service_registry._dependencies = original_deps
    service_registry._initialization_order = original_order


class TestServiceRegistry:
    """ServiceRegistry 測試類別"""
    
    @pytest.mark.asyncio
    async def test_register_service(self, clean_registry):
        """測試服務註冊"""
        service = MockService()
        
        # 註冊服務
        name = await clean_registry.register_service(service)
        
        assert name == "MockService"
        assert clean_registry.get_service("MockService") == service
        assert clean_registry.get_service_by_type(MockService) == service
        assert "MockService" in clean_registry.list_services()
    
    @pytest.mark.asyncio
    async def test_register_service_custom_name(self, clean_registry):
        """測試使用自定義名稱註冊服務"""
        service = MockService()
        
        name = await clean_registry.register_service(service, "CustomName")
        
        assert name == "CustomName"
        assert clean_registry.get_service("CustomName") == service
    
    @pytest.mark.asyncio
    async def test_register_duplicate_service(self, clean_registry):
        """測試註冊重複服務"""
        service1 = MockService()
        service2 = MockService()
        
        await clean_registry.register_service(service1)
        
        with pytest.raises(ServiceError) as exc_info:
            await clean_registry.register_service(service2)
        
        assert "已經註冊" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_unregister_service(self, clean_registry):
        """測試取消註冊服務"""
        service = MockService()
        await clean_registry.register_service(service)
        
        # 初始化服務使其需要清理
        await service.initialize()
        
        # 取消註冊
        result = await clean_registry.unregister_service("MockService")
        
        assert result is True
        assert clean_registry.get_service("MockService") is None
        assert service.cleanup_called is True
    
    @pytest.mark.asyncio
    async def test_unregister_nonexistent_service(self, clean_registry):
        """測試取消註冊不存在的服務"""
        result = await clean_registry.unregister_service("NonExistent")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_unregister_service_with_dependents(self, clean_registry):
        """測試取消註冊有依賴的服務"""
        service1 = MockService("Service1")
        service2 = MockService("Service2")
        
        await clean_registry.register_service(service1, "Service1")
        await clean_registry.register_service(service2, "Service2")
        
        # 在註冊表中記錄依賴關係
        clean_registry.add_dependency("Service2", "Service1")
        
        with pytest.raises(ServiceError) as exc_info:
            await clean_registry.unregister_service("Service1")
        
        assert "依賴它" in str(exc_info.value)
    
    def test_add_dependency(self, clean_registry):
        """測試添加依賴關係"""
        clean_registry.add_dependency("ServiceA", "ServiceB")
        
        assert "ServiceB" in clean_registry._dependencies["ServiceA"]
    
    def test_get_initialization_order(self, clean_registry):
        """測試獲取初始化順序"""
        # 設定依賴關係：B 依賴 A，C 依賴 B
        clean_registry._services = {"A": None, "B": None, "C": None}
        clean_registry._dependencies = {
            "A": set(),
            "B": {"A"},
            "C": {"B"}
        }
        
        order = clean_registry.get_initialization_order()
        
        assert order == ["A", "B", "C"]
    
    def test_get_initialization_order_circular_dependency(self, clean_registry):
        """測試循環依賴檢測"""
        clean_registry._services = {"A": None, "B": None}
        clean_registry._dependencies = {
            "A": {"B"},
            "B": {"A"}
        }
        
        with pytest.raises(ServiceError) as exc_info:
            clean_registry.get_initialization_order()
        
        assert "循環依賴" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_initialize_all_services(self, clean_registry):
        """測試初始化所有服務"""
        service1 = MockService("Service1")
        service2 = DependentService(service1)
        
        await clean_registry.register_service(service1)
        await clean_registry.register_service(service2)
        
        result = await clean_registry.initialize_all_services()
        
        assert result is True
        assert service1.initialized_called is True
        assert service2.initialized_called is True
    
    @pytest.mark.asyncio
    async def test_initialize_all_services_failure(self, clean_registry):
        """測試服務初始化失敗"""
        service1 = MockService("InitFailService1", fail_init=True)
        service2 = MockService("InitFailService2")
        
        await clean_registry.register_service(service1, "InitFailService1")
        await clean_registry.register_service(service2, "InitFailService2")
        
        result = await clean_registry.initialize_all_services()
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_cleanup_all_services(self, clean_registry):
        """測試清理所有服務"""
        service1 = MockService("CleanupService1")
        service2 = MockService("CleanupService2")
        
        await clean_registry.register_service(service1, "CleanupService1")
        await clean_registry.register_service(service2, "CleanupService2")
        await clean_registry.initialize_all_services()
        
        await clean_registry.cleanup_all_services()
        
        assert service1.cleanup_called is True
        assert service2.cleanup_called is True


class TestBaseService:
    """BaseService 測試類別"""
    
    def test_service_creation(self):
        """測試服務建立"""
        service = MockService("TestService")
        
        assert service.name == "TestService"
        assert service.is_initialized is False
        assert service.initialization_time is None
        assert service.uptime is None
    
    @pytest.mark.asyncio
    async def test_service_register(self, clean_registry):
        """測試服務註冊"""
        service = MockService()
        
        name = await service.register()
        
        assert name == "MockService"
        assert clean_registry.get_service("MockService") == service
    
    def test_add_dependency(self):
        """測試添加依賴"""
        service1 = MockService("Service1")
        service2 = MockService("Service2")
        
        service2.add_dependency(service1)
        
        assert service2.get_dependency("Service1") == service1
        # service2 依賴 service1，所以 service2 應該在 service1 的 dependent_services 中
        assert service2 in service1._dependent_services
    
    @pytest.mark.asyncio
    async def test_service_initialization_success(self):
        """測試服務初始化成功"""
        service = MockService()
        
        result = await service.initialize()
        
        assert result is True
        assert service.is_initialized is True
        assert service.initialization_time is not None
        assert service.uptime is not None
        assert service.initialized_called is True
    
    @pytest.mark.asyncio
    async def test_service_initialization_failure(self):
        """測試服務初始化失敗"""
        service = MockService(fail_init=True)
        
        result = await service.initialize()
        
        assert result is False
        assert service.is_initialized is False
        assert service.initialization_time is None
    
    @pytest.mark.asyncio
    async def test_service_double_initialization(self):
        """測試重複初始化"""
        service = MockService()
        
        await service.initialize()
        result = await service.initialize()
        
        assert result is True
        assert service.is_initialized is True
    
    @pytest.mark.asyncio
    async def test_service_initialization_missing_dependency(self):
        """測試依賴服務未初始化"""
        service1 = MockService("Service1")
        service2 = DependentService(service1)
        
        with pytest.raises(ServiceInitializationError):
            await service2.initialize()
    
    @pytest.mark.asyncio
    async def test_service_initialization_with_dependency(self):
        """測試有依賴的服務初始化"""
        service1 = MockService("Service1")
        service2 = DependentService(service1)
        
        await service1.initialize()
        result = await service2.initialize()
        
        assert result is True
        assert service2.is_initialized is True
    
    @pytest.mark.asyncio
    async def test_service_cleanup(self):
        """測試服務清理"""
        service = MockService()
        await service.initialize()
        
        await service.cleanup()
        
        assert service.is_initialized is False
        assert service.initialization_time is None
        assert service.cleanup_called is True
    
    @pytest.mark.asyncio
    async def test_service_cleanup_not_initialized(self):
        """測試清理未初始化的服務"""
        service = MockService()
        
        # 應該不會拋出錯誤
        await service.cleanup()
        
        assert service.cleanup_called is False
    
    @pytest.mark.asyncio
    async def test_validate_permissions_success(self):
        """測試權限驗證成功"""
        service = MockService()
        
        result = await service.validate_permissions(123, 456, "test_action")
        
        assert result is True
        assert service.permissions_called is True
    
    @pytest.mark.asyncio
    async def test_validate_permissions_failure(self):
        """測試權限驗證失敗"""
        service = MockService(fail_permissions=True)
        
        with pytest.raises(ServicePermissionError):
            await service.validate_permissions(123, 456, "test_action")
    
    @pytest.mark.asyncio
    async def test_health_check(self):
        """測試健康檢查"""
        service = MockService("TestService")
        service2 = MockService("Dependency")
        service.add_dependency(service2)
        
        # 先初始化依賴服務
        await service2.initialize()
        await service.initialize()
        
        health = await service.health_check()
        
        assert health["service_name"] == "TestService"
        assert health["initialized"] is True
        assert health["initialization_time"] is not None
        assert health["uptime_seconds"] is not None
        assert "Dependency" in health["dependencies"]
        assert health["dependent_services"] == 0
    
    def test_service_repr(self):
        """測試服務字符串表示"""
        service = MockService("TestService")
        
        repr_str = repr(service)
        
        assert "TestService" in repr_str
        assert "未初始化" in repr_str


class TestDependencyInjection:
    """依賴注入測試類別"""
    
    @pytest.mark.asyncio
    async def test_inject_service_decorator(self, clean_registry):
        """測試服務注入裝飾器"""
        service = MockService("TestService")
        await clean_registry.register_service(service, "TestService")
        await service.initialize()
        
        @inject_service("TestService", registry=clean_registry)
        async def test_function(testservice=None):
            return testservice
        
        result = await test_function()
        
        assert result == service
    
    @pytest.mark.asyncio
    async def test_inject_service_not_found(self, clean_registry):
        """測試注入不存在的服務"""
        @inject_service("NonExistent")
        async def test_function(nonexistent=None):
            return nonexistent
        
        with pytest.raises(ServiceError):
            await test_function()
    
    @pytest.mark.asyncio
    async def test_inject_service_not_initialized(self, clean_registry):
        """測試注入未初始化的服務"""
        service = MockService("TestService")
        await clean_registry.register_service(service)
        
        @inject_service("TestService")
        async def test_function(testservice=None):
            return testservice
        
        with pytest.raises(ServiceError):
            await test_function()
    
    @pytest.mark.asyncio
    async def test_inject_service_by_type(self, clean_registry):
        """測試按類型注入服務"""
        service = MockService("TestService")
        await clean_registry.register_service(service)
        await service.initialize()
        
        @inject_service_by_type(MockService)
        async def test_function(mockservice=None):
            return mockservice
        
        result = await test_function()
        
        assert result == service
    
    @pytest.mark.asyncio
    async def test_inject_service_by_type_not_found(self, clean_registry):
        """測試按類型注入不存在的服務"""
        @inject_service_by_type(MockService)
        async def test_function(mockservice=None):
            return mockservice
        
        with pytest.raises(ServiceError):
            await test_function()


if __name__ == "__main__":
    pytest.main([__file__])