"""
測試服務註冊機制和生命週期管理
Task ID: 1 - 核心架構和基礎設施建置

測試ServiceRegistry、BaseService和ServiceLifecycleManager的功能
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any

# 測試目標模組
from core.base_service import (
    ServiceRegistry, BaseService, ServiceType,
    inject_service, inject_service_by_type,
    service_registry
)
from src.core.service_lifecycle import (
    ServiceLifecycleManager, ServiceStatus, HealthStatus,
    ServiceHealthInfo, LifecycleEvent, lifecycle_manager
)
from core.exceptions import ServiceError, ServiceInitializationError


class MockService(BaseService):
    """模擬服務用於測試"""
    
    def __init__(self, name: str = None, should_fail: bool = False):
        super().__init__(name, ServiceType.BASE)
        self.should_fail = should_fail
        self.init_called = False
        self.cleanup_called = False
        
    async def _initialize(self) -> bool:
        """模擬初始化"""
        self.init_called = True
        if self.should_fail:
            raise Exception("初始化失敗")
        return True
        
    async def _cleanup(self) -> None:
        """模擬清理"""
        self.cleanup_called = True
        
    async def _validate_permissions(self, user_id: int, guild_id: int, action: str) -> bool:
        """模擬權限驗證"""
        return user_id != 999  # 假設user_id=999沒有權限


class MockDeploymentService(BaseService):
    """模擬部署服務"""
    
    def __init__(self, deployment_mode: str = "docker"):
        super().__init__("MockDeploymentService", ServiceType.DEPLOYMENT)
        self.deployment_mode = deployment_mode
        
    async def _initialize(self) -> bool:
        return True
        
    async def _cleanup(self) -> None:
        pass
        
    async def _validate_permissions(self, user_id: int, guild_id: int, action: str) -> bool:
        return True


class MockSubBotService(BaseService):
    """模擬子機器人服務"""
    
    def __init__(self, bot_id: str = "test_bot"):
        super().__init__("MockSubBotService", ServiceType.SUB_BOT)
        self.bot_id = bot_id
        
    async def _initialize(self) -> bool:
        return True
        
    async def _cleanup(self) -> None:
        pass
        
    async def _validate_permissions(self, user_id: int, guild_id: int, action: str) -> bool:
        return True


class MockAIService(BaseService):
    """模擬AI服務"""
    
    def __init__(self, provider: str = "openai"):
        super().__init__("MockAIService", ServiceType.AI_SERVICE)
        self.provider = provider
        
    async def _initialize(self) -> bool:
        return True
        
    async def _cleanup(self) -> None:
        pass
        
    async def _validate_permissions(self, user_id: int, guild_id: int, action: str) -> bool:
        return True


class TestServiceRegistry:
    """測試服務註冊表"""
    
    @pytest.fixture
    def registry(self):
        """創建測試用的註冊表"""
        return ServiceRegistry()
        
    @pytest.fixture
    def mock_service(self):
        """創建測試用的模擬服務"""
        return MockService("TestService")
    
    @pytest.mark.asyncio
    async def test_basic_service_registration(self, registry, mock_service):
        """測試基本服務註冊"""
        service_name = await registry.register_service(mock_service)
        
        assert service_name == "TestService"
        assert registry.get_service("TestService") == mock_service
        assert registry.is_registered("TestService")
        assert "TestService" in registry.list_services()
        
    @pytest.mark.asyncio
    async def test_service_registration_with_custom_name(self, registry, mock_service):
        """測試使用自定義名稱註冊服務"""
        service_name = await registry.register_service(mock_service, "CustomName")
        
        assert service_name == "CustomName"
        assert registry.get_service("CustomName") == mock_service
        
    @pytest.mark.asyncio
    async def test_duplicate_service_registration_fails(self, registry, mock_service):
        """測試重複註冊服務會失敗"""
        await registry.register_service(mock_service)
        
        duplicate_service = MockService("TestService")
        with pytest.raises(ServiceError, match="已經註冊"):
            await registry.register_service(duplicate_service)
            
    @pytest.mark.asyncio
    async def test_force_reregister_service(self, registry, mock_service):
        """測試強制重新註冊服務"""
        await registry.register_service(mock_service)
        await mock_service.initialize()
        
        new_service = MockService("TestService")
        service_name = await registry.register_service(new_service, force_reregister=True)
        
        assert service_name == "TestService"
        assert registry.get_service("TestService") == new_service
        assert mock_service.cleanup_called  # 舊服務應該被清理
        
    @pytest.mark.asyncio
    async def test_service_unregistration(self, registry, mock_service):
        """測試服務取消註冊"""
        await registry.register_service(mock_service)
        await mock_service.initialize()
        
        success = await registry.unregister_service("TestService")
        
        assert success
        assert not registry.is_registered("TestService")
        assert registry.get_service("TestService") is None
        assert mock_service.cleanup_called
        
    @pytest.mark.asyncio
    async def test_get_service_by_type(self, registry):
        """測試根據類型獲取服務"""
        service = MockService()
        await registry.register_service(service)
        
        retrieved = registry.get_service_by_type(MockService)
        assert retrieved == service
        
    @pytest.mark.asyncio
    async def test_service_initialization_order(self, registry):
        """測試服務初始化順序"""
        service1 = MockService("Service1")
        service2 = MockService("Service2")
        service3 = MockService("Service3")
        
        # 註冊服務
        await registry.register_service(service1)
        await registry.register_service(service2)  
        await registry.register_service(service3)
        
        # 設定依賴關係：Service3 -> Service2 -> Service1
        service2.add_dependency(service1, "Service1")
        service3.add_dependency(service2, "Service2")
        
        # 獲取初始化順序
        order = registry.get_initialization_order()
        
        # Service1 應該先初始化，然後是 Service2，最後是 Service3
        assert order.index("Service1") < order.index("Service2")
        assert order.index("Service2") < order.index("Service3")
        
    @pytest.mark.asyncio
    async def test_initialize_all_services(self, registry):
        """測試初始化所有服務"""
        service1 = MockService("Service1")
        service2 = MockService("Service2")
        
        await registry.register_service(service1)
        await registry.register_service(service2)
        
        success = await registry.initialize_all_services()
        
        assert success
        assert service1.init_called
        assert service2.init_called
        assert service1.is_initialized
        assert service2.is_initialized


class TestSpecificServiceRegistration:
    """測試特定服務類型的註冊方法"""
    
    @pytest.fixture
    def registry(self):
        return ServiceRegistry()
    
    @pytest.mark.asyncio
    async def test_register_deployment_service(self, registry):
        """測試註冊部署服務"""
        service = MockDeploymentService("docker")
        
        service_name = await registry.register_deployment_service(
            service, "docker", "DeploymentService"
        )
        
        assert service_name == "DeploymentService"
        assert registry.get_service("DeploymentService") == service
        assert service.service_metadata["service_type"] == ServiceType.DEPLOYMENT
        assert service.service_metadata["deployment_mode"] == "docker"
        
    @pytest.mark.asyncio
    async def test_register_sub_bot_service(self, registry):
        """測試註冊子機器人服務"""
        service = MockSubBotService("bot_123")
        target_channels = ["channel1", "channel2"]
        
        service_name = await registry.register_sub_bot_service(
            service, "bot_123", target_channels, "SubBotService"
        )
        
        assert service_name == "SubBotService"
        assert service.service_metadata["service_type"] == ServiceType.SUB_BOT
        assert service.service_metadata["bot_id"] == "bot_123"
        assert service.service_metadata["target_channels"] == target_channels
        
    @pytest.mark.asyncio
    async def test_register_ai_service(self, registry):
        """測試註冊AI服務"""
        service = MockAIService("openai")
        models = ["gpt-4", "gpt-3.5-turbo"]
        
        service_name = await registry.register_ai_service(
            service, "openai", models, "AIService"
        )
        
        assert service_name == "AIService"
        assert service.service_metadata["service_type"] == ServiceType.AI_SERVICE
        assert service.service_metadata["provider"] == "openai"
        assert service.service_metadata["models"] == models
        
    @pytest.mark.asyncio
    async def test_get_services_by_type(self, registry):
        """測試根據類型獲取服務列表"""
        # 註冊不同類型的服務
        deployment_service = MockDeploymentService()
        sub_bot_service = MockSubBotService()
        ai_service = MockAIService()
        
        await registry.register_deployment_service(deployment_service, "docker")
        await registry.register_sub_bot_service(sub_bot_service, "bot_1", ["ch1"])
        await registry.register_ai_service(ai_service, "openai", ["gpt-4"])
        
        # 測試獲取特定類型的服務
        deployment_services = registry.get_services_by_type(ServiceType.DEPLOYMENT)
        sub_bot_services = registry.get_services_by_type(ServiceType.SUB_BOT)
        ai_services = registry.get_services_by_type(ServiceType.AI_SERVICE)
        
        assert len(deployment_services) == 1
        assert len(sub_bot_services) == 1
        assert len(ai_services) == 1
        
    @pytest.mark.asyncio
    async def test_get_service_health_status_single(self, registry):
        """測試獲取單個服務的健康狀態"""
        service = MockService("HealthTestService")
        await registry.register_service(service)
        await service.initialize()
        
        health_status = await registry.get_service_health_status("HealthTestService")
        
        assert health_status["service_name"] == "HealthTestService"
        assert health_status["initialized"] == True
        assert health_status["status"] == "healthy"
        assert "service_type" in health_status
        
    @pytest.mark.asyncio
    async def test_get_service_health_status_all(self, registry):
        """測試獲取所有服務的健康狀態"""
        service1 = MockService("Service1")
        service2 = MockService("Service2")
        
        await registry.register_service(service1)
        await registry.register_service(service2)
        await service1.initialize()
        await service2.initialize()
        
        all_health = await registry.get_service_health_status()
        
        assert all_health["total_services"] == 2
        assert "Service1" in all_health["services"]
        assert "Service2" in all_health["services"]
        assert all_health["services"]["Service1"]["initialized"] == True
        assert all_health["services"]["Service2"]["initialized"] == True


class TestBaseService:
    """測試BaseService基礎服務類"""
    
    @pytest.fixture
    def service(self):
        return MockService("TestService")
    
    def test_service_initialization_properties(self, service):
        """測試服務初始化屬性"""
        assert service.name == "TestService"
        assert not service.is_initialized
        assert service.initialization_time is None
        assert service.uptime is None
        assert hasattr(service, 'service_metadata')
        assert service.service_metadata["service_type"] == ServiceType.BASE
        
    @pytest.mark.asyncio
    async def test_service_initialize_success(self, service):
        """測試服務成功初始化"""
        success = await service.initialize()
        
        assert success
        assert service.is_initialized
        assert service.initialization_time is not None
        assert service.uptime is not None
        assert service.init_called
        
    @pytest.mark.asyncio
    async def test_service_initialize_failure(self):
        """測試服務初始化失敗"""
        service = MockService("FailService", should_fail=True)
        
        with pytest.raises(ServiceInitializationError):
            await service.initialize()
            
        assert not service.is_initialized
        assert service.init_called
        
    @pytest.mark.asyncio
    async def test_service_cleanup(self, service):
        """測試服務清理"""
        await service.initialize()
        await service.cleanup()
        
        assert not service.is_initialized
        assert service.initialization_time is None
        assert service.cleanup_called
        
    @pytest.mark.asyncio
    async def test_service_health_check(self, service):
        """測試服務健康檢查"""
        await service.initialize()
        
        health = await service.health_check()
        
        assert health["service_name"] == "TestService"
        assert health["initialized"] == True
        assert health["status"] == "healthy"
        assert "uptime_seconds" in health
        assert "service_type" in health
        
    @pytest.mark.asyncio
    async def test_service_permission_validation_success(self, service):
        """測試服務權限驗證成功"""
        result = await service.validate_permissions(123, 456, "test_action")
        assert result == True
        
    @pytest.mark.asyncio
    async def test_service_permission_validation_failure(self, service):
        """測試服務權限驗證失敗"""
        from core.exceptions import ServicePermissionError
        
        with pytest.raises(ServicePermissionError):
            await service.validate_permissions(999, 456, "test_action")
            
    def test_service_dependency_management(self, service):
        """測試服務依賴管理"""
        dependency = MockService("DependencyService")
        
        service.add_dependency(dependency, "TestDependency")
        
        retrieved_dep = service.get_dependency("TestDependency")
        assert retrieved_dep == dependency


class TestServiceLifecycleManager:
    """測試服務生命週期管理器"""
    
    @pytest.fixture
    async def lifecycle_mgr(self):
        """創建生命週期管理器用於測試"""
        mgr = ServiceLifecycleManager(check_interval=1)  # 短間隔便於測試
        await mgr.start()
        yield mgr
        await mgr.stop()
    
    @pytest.mark.asyncio
    async def test_lifecycle_manager_start_stop(self):
        """測試生命週期管理器啟動和停止"""
        mgr = ServiceLifecycleManager()
        
        assert not mgr._running
        
        await mgr.start()
        assert mgr._running
        assert mgr._health_check_task is not None
        
        await mgr.stop()
        assert not mgr._running
        
    @pytest.mark.asyncio
    async def test_register_service_to_lifecycle_manager(self, lifecycle_mgr):
        """測試向生命週期管理器註冊服務"""
        service = MockService("LifecycleTestService")
        
        lifecycle_mgr.register_service("LifecycleTestService", service)
        
        assert "LifecycleTestService" in lifecycle_mgr._services
        assert lifecycle_mgr._service_statuses["LifecycleTestService"] == ServiceStatus.CREATED
        assert "LifecycleTestService" in lifecycle_mgr._health_info
        
    @pytest.mark.asyncio
    async def test_update_service_status(self, lifecycle_mgr):
        """測試更新服務狀態"""
        service = MockService("StatusTestService")
        lifecycle_mgr.register_service("StatusTestService", service)
        
        lifecycle_mgr.update_service_status("StatusTestService", ServiceStatus.RUNNING, "服務已啟動")
        
        assert lifecycle_mgr.get_service_status("StatusTestService") == ServiceStatus.RUNNING
        
    @pytest.mark.asyncio
    async def test_perform_health_check_success(self, lifecycle_mgr):
        """測試執行健康檢查成功"""
        service = MockService("HealthCheckService")
        await service.initialize()
        lifecycle_mgr.register_service("HealthCheckService", service)
        
        health_info = await lifecycle_mgr.perform_health_check("HealthCheckService")
        
        assert health_info.service_name == "HealthCheckService"
        assert health_info.status == HealthStatus.HEALTHY
        assert health_info.response_time > 0
        assert health_info.error_count == 0
        
    @pytest.mark.asyncio
    async def test_perform_health_check_unhealthy(self, lifecycle_mgr):
        """測試執行健康檢查不健康"""
        service = MockService("UnhealthyService")  # 未初始化的服務
        lifecycle_mgr.register_service("UnhealthyService", service)
        
        health_info = await lifecycle_mgr.perform_health_check("UnhealthyService")
        
        assert health_info.service_name == "UnhealthyService"
        assert health_info.status == HealthStatus.UNHEALTHY
        assert "未初始化" in health_info.message
        
    @pytest.mark.asyncio
    async def test_get_all_services_status(self, lifecycle_mgr):
        """測試獲取所有服務狀態"""
        service1 = MockService("Service1")
        service2 = MockService("Service2")
        
        await service1.initialize()
        await service2.initialize()
        
        lifecycle_mgr.register_service("Service1", service1)
        lifecycle_mgr.register_service("Service2", service2)
        
        # 執行健康檢查
        await lifecycle_mgr.perform_health_check("Service1")
        await lifecycle_mgr.perform_health_check("Service2")
        
        all_status = lifecycle_mgr.get_all_services_status()
        
        assert len(all_status) == 2
        assert "Service1" in all_status
        assert "Service2" in all_status
        assert all_status["Service1"]["status"] == "created"
        assert all_status["Service1"]["health"]["status"] == "healthy"
        
    @pytest.mark.asyncio
    async def test_lifecycle_events_recording(self, lifecycle_mgr):
        """測試生命週期事件記錄"""
        service = MockService("EventTestService")
        lifecycle_mgr.register_service("EventTestService", service)
        
        lifecycle_mgr.update_service_status("EventTestService", ServiceStatus.RUNNING)
        
        events = lifecycle_mgr.get_lifecycle_events("EventTestService")
        
        assert len(events) >= 2  # 至少有註冊和狀態變更事件
        assert any(e.event_type == "service_registered" for e in events)
        assert any(e.event_type == "status_changed" for e in events)
        
    @pytest.mark.asyncio
    async def test_event_listeners(self, lifecycle_mgr):
        """測試事件監聽器"""
        callback_called = []
        
        def test_callback(service_name, data):
            callback_called.append((service_name, data))
            
        lifecycle_mgr.add_event_listener("status_changed", test_callback)
        
        service = MockService("ListenerTestService")
        lifecycle_mgr.register_service("ListenerTestService", service)
        lifecycle_mgr.update_service_status("ListenerTestService", ServiceStatus.RUNNING)
        
        assert len(callback_called) == 1
        assert callback_called[0][0] == "ListenerTestService"


class TestDependencyInjection:
    """測試依賴注入機制"""
    
    @pytest.fixture
    def registry_with_service(self):
        """創建包含服務的註冊表"""
        registry = ServiceRegistry()
        service = MockService("InjectionTestService")
        
        # 直接添加到註冊表（模擬已註冊的服務）
        registry._services["InjectionTestService"] = service
        
        return registry, service
    
    @pytest.mark.asyncio
    async def test_inject_service_decorator(self, registry_with_service):
        """測試inject_service裝飾器"""
        registry, service = registry_with_service
        await service.initialize()  # 確保服務已初始化
        
        @inject_service("InjectionTestService", registry)
        async def test_function(injectiontestservice=None):
            return injectiontestservice
            
        result = await test_function()
        assert result == service
        
    @pytest.mark.asyncio 
    async def test_inject_service_by_type_decorator(self, registry_with_service):
        """測試inject_service_by_type裝飾器"""
        registry, service = registry_with_service
        await service.initialize()
        
        # 添加類型映射
        registry._service_types[MockService] = "InjectionTestService"
        
        @inject_service_by_type(MockService, registry)
        async def test_function(mockservice=None):
            return mockservice
            
        result = await test_function()
        assert result == service


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])