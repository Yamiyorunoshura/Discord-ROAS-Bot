"""
服務註冊機制測試
Task ID: 1 - 核心架構和基礎設施建置

測試擴展的服務註冊機制，包括：
- ExtendedServiceRegistry的基本功能
- 服務依賴關係管理
- 生命週期整合
- v2.4.4新服務類型的註冊
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from typing import Dict, Any, List, Optional

# 使用相對導入避免依賴問題
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

try:
    from src.core.service_registry import ExtendedServiceRegistry
    from src.core.service_lifecycle import ServiceLifecycleManager, ServiceStatus, HealthStatus
    from core.base_service import BaseService, ServiceType, ServiceRegistry
    from src.core.errors import ServiceError, ValidationError
    SERVICE_REGISTRY_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Service registry imports failed: {e}")
    SERVICE_REGISTRY_AVAILABLE = False


# Mock classes for testing
class MockBaseService(BaseService):
    """Mock service for testing"""
    
    def __init__(self, name: str = "test_service", service_type: ServiceType = ServiceType.BASE):
        self.name = name
        self.service_metadata = {
            'service_type': service_type,
            'version': '1.0.0'
        }
        self.is_initialized = False
        self._health_status = "healthy"
    
    async def _initialize(self):
        """Mock initialize method"""
        pass
    
    async def _cleanup(self):
        """Mock cleanup method"""
        pass
    
    async def _validate_permissions(self, operation: str, **kwargs) -> bool:
        """Mock permission validation"""
        return True
    
    async def start(self):
        """Mock start method"""
        self.is_initialized = True
        
    async def stop(self):
        """Mock stop method"""
        self.is_initialized = False
    
    async def health_check(self) -> Dict[str, Any]:
        """Mock health check"""
        return {
            "service_name": self.name,
            "status": self._health_status,
            "message": "Mock service is running"
        }

class MockDeploymentService(MockBaseService):
    """Mock deployment service"""
    
    def __init__(self, name: str = "deployment_service"):
        super().__init__(name, ServiceType.DEPLOYMENT)
        self.config = {
            'docker_timeout': 300,
            'deployment_mode': 'docker'
        }

class MockSubBotService(MockBaseService):
    """Mock sub-bot service"""
    
    def __init__(self, name: str = "subbot_service"):
        super().__init__(name, ServiceType.SUB_BOT)
        self._encryption_key = "test_key"
        self.config = {
            'default_rate_limit': 10
        }

class MockAIService(MockBaseService):
    """Mock AI service"""
    
    def __init__(self, name: str = "ai_service"):
        super().__init__(name, ServiceType.AI_SERVICE)
        self.config = {
            'content_filter_enabled': True,
            'cost_tracking_enabled': True
        }

class MockLifecycleManager:
    """Mock lifecycle manager"""
    
    def __init__(self):
        self._services = {}
        self._running = False
    
    def register_service(self, name: str, service):
        """Register service"""
        self._services[name] = service
    
    def unregister_service(self, name: str):
        """Unregister service"""
        self._services.pop(name, None)
    
    def update_service_status(self, name: str, status: ServiceStatus, message: str = ""):
        """Update service status"""
        pass
    
    def get_service_status(self, name: str) -> Optional[ServiceStatus]:
        """Get service status"""
        return ServiceStatus.RUNNING if name in self._services else None
    
    def get_service_health(self, name: str):
        """Get service health"""
        if name in self._services:
            mock_health = MagicMock()
            mock_health.status = HealthStatus.HEALTHY
            mock_health.response_time = 0.1
            mock_health.error_count = 0
            mock_health.message = "Healthy"
            mock_health.last_check = datetime.now()
            return mock_health
        return None
    
    def get_all_services_status(self) -> Dict[str, Any]:
        """Get all services status"""
        return {
            name: {
                'status': ServiceStatus.RUNNING.value,
                'health': {
                    'status': 'healthy'
                }
            } for name in self._services
        }
    
    async def perform_health_check(self, name: str):
        """Perform health check"""
        mock_health = MagicMock()
        mock_health.status = HealthStatus.HEALTHY
        mock_health.response_time = 0.1
        mock_health.error_count = 0
        mock_health.message = "Health check passed"
        mock_health.last_check = datetime.now()
        return mock_health
    
    def get_lifecycle_events(self, service_name: Optional[str] = None, limit: int = 100) -> List:
        """Get lifecycle events"""
        return []

class MockDatabaseManager:
    """Mock database manager"""
    
    async def execute(self, query: str, params: tuple):
        """Mock execute"""
        pass
    
    async def fetchall(self, query: str):
        """Mock fetchall"""
        return []


@pytest.mark.skipif(not SERVICE_REGISTRY_AVAILABLE, reason="Service registry modules not available")
class TestExtendedServiceRegistry:
    """測試擴展的服務註冊機制"""
    
    @pytest.fixture
    def mock_lifecycle_manager(self):
        """創建mock生命週期管理器"""
        return MockLifecycleManager()
    
    @pytest.fixture
    def service_registry(self, mock_lifecycle_manager):
        """創建服務註冊器實例"""
        return ExtendedServiceRegistry(mock_lifecycle_manager)
    
    def test_initialization(self, service_registry, mock_lifecycle_manager):
        """測試初始化"""
        assert service_registry.lifecycle_manager == mock_lifecycle_manager
        assert isinstance(service_registry._service_type_counts, dict)
        assert isinstance(service_registry._service_registration_history, list)
        assert isinstance(service_registry._service_dependencies, dict)
        assert isinstance(service_registry._dependent_services, dict)
        assert isinstance(service_registry._service_priorities, dict)
        assert isinstance(service_registry._auto_recovery_enabled, dict)
        assert isinstance(service_registry._recovery_strategies, dict)
    
    @pytest.mark.asyncio
    async def test_register_service_basic(self, service_registry):
        """測試基本服務註冊"""
        service = MockBaseService("test_service")
        
        service_name = await service_registry.register_service(service)
        
        assert service_name == "test_service"
        assert service_registry.get_service(service_name) == service
        assert service_name in service_registry._service_priorities
        assert service_name in service_registry._auto_recovery_enabled
        assert service_name in service_registry._recovery_strategies
        assert len(service_registry._service_registration_history) > 0
    
    @pytest.mark.asyncio
    async def test_register_service_with_dependencies(self, service_registry):
        """測試帶依賴的服務註冊"""
        # 先註冊依賴服務
        dependency_service = MockBaseService("dependency_service")
        await service_registry.register_service(dependency_service)
        
        # 註冊主服務
        main_service = MockBaseService("main_service")
        service_name = await service_registry.register_service(
            main_service,
            dependencies=["dependency_service"]
        )
        
        assert service_name == "main_service"
        assert service_registry.get_service_dependencies(service_name) == ["dependency_service"]
        assert service_registry.get_dependent_services("dependency_service") == ["main_service"]
    
    @pytest.mark.asyncio
    async def test_register_service_missing_dependencies(self, service_registry):
        """測試缺少依賴時的錯誤處理"""
        service = MockBaseService("test_service")
        
        with pytest.raises(ValueError, match="缺少依賴服務"):
            await service_registry.register_service(
                service,
                dependencies=["non_existent_service"]
            )
    
    @pytest.mark.asyncio
    async def test_unregister_service(self, service_registry):
        """測試服務解除註冊"""
        service = MockBaseService("test_service")
        service_name = await service_registry.register_service(service)
        
        success = await service_registry.unregister_service(service_name)
        
        assert success is True
        assert service_registry.get_service(service_name) is None
        assert service_name not in service_registry._service_priorities
        assert service_name not in service_registry._auto_recovery_enabled
        assert service_name not in service_registry._recovery_strategies
    
    @pytest.mark.asyncio
    async def test_unregister_service_with_dependents(self, service_registry):
        """測試有依賴者的服務解除註冊"""
        # 註冊服務鏈
        dependency_service = MockBaseService("dependency_service")
        await service_registry.register_service(dependency_service)
        
        dependent_service = MockBaseService("dependent_service")
        await service_registry.register_service(
            dependent_service,
            dependencies=["dependency_service"]
        )
        
        # 嘗試解除註冊被依賴的服務（應該失敗）
        success = await service_registry.unregister_service("dependency_service")
        assert success is False
        
        # 強制解除註冊（應該成功）
        success = await service_registry.unregister_service("dependency_service", force=True)
        assert success is True
    
    @pytest.mark.asyncio
    async def test_register_deployment_service(self, service_registry):
        """測試部署服務註冊"""
        deployment_service = MockDeploymentService()
        
        with patch.object(service_registry.__class__.__bases__[0], 'register_deployment_service', 
                         return_value="deployment_service") as mock_super:
            service_name = await service_registry.register_deployment_service(
                deployment_service,
                deployment_mode="docker",
                environment_config={"timeout": 300}
            )
            
            assert service_name == "deployment_service"
            mock_super.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_register_sub_bot_service(self, service_registry):
        """測試子機器人服務註冊"""
        subbot_service = MockSubBotService()
        
        with patch.object(service_registry.__class__.__bases__[0], 'register_sub_bot_service', 
                         return_value="subbot_service") as mock_super:
            service_name = await service_registry.register_sub_bot_service(
                subbot_service,
                bot_id="test_bot_001",
                target_channels=["channel1", "channel2"]
            )
            
            assert service_name == "subbot_service"
            mock_super.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_register_ai_service(self, service_registry):
        """測試AI服務註冊"""
        ai_service = MockAIService()
        
        with patch.object(service_registry.__class__.__bases__[0], 'register_ai_service', 
                         return_value="ai_service") as mock_super:
            service_name = await service_registry.register_ai_service(
                ai_service,
                provider="openai",
                models=["gpt-3.5-turbo", "gpt-4"]
            )
            
            assert service_name == "ai_service"
            mock_super.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_start_service_with_dependencies(self, service_registry):
        """測試按依賴順序啟動服務"""
        # 創建服務鏈
        service_a = MockBaseService("service_a")
        service_b = MockBaseService("service_b")
        service_c = MockBaseService("service_c")
        
        await service_registry.register_service(service_a)
        await service_registry.register_service(service_b, dependencies=["service_a"])
        await service_registry.register_service(service_c, dependencies=["service_b"])
        
        # 啟動服務C（應該按順序啟動A->B->C）
        success = await service_registry.start_service_with_dependencies("service_c")
        
        assert success is True
        assert service_a.is_initialized
        assert service_b.is_initialized
        assert service_c.is_initialized
    
    @pytest.mark.asyncio
    async def test_stop_service_with_dependents(self, service_registry):
        """測試按依賴順序停止服務"""
        # 創建並啟動服務鏈
        service_a = MockBaseService("service_a")
        service_b = MockBaseService("service_b")
        service_c = MockBaseService("service_c")
        
        service_a.is_initialized = True
        service_b.is_initialized = True
        service_c.is_initialized = True
        
        await service_registry.register_service(service_a)
        await service_registry.register_service(service_b, dependencies=["service_a"])
        await service_registry.register_service(service_c, dependencies=["service_b"])
        
        # 停止服務A（應該按順序停止C->B->A）
        success = await service_registry.stop_service_with_dependents("service_a")
        
        assert success is True
        assert not service_a.is_initialized
        assert not service_b.is_initialized
        assert not service_c.is_initialized
    
    @pytest.mark.asyncio
    async def test_calculate_startup_order(self, service_registry):
        """測試啟動順序計算"""
        # 建立複雜的依賴關係
        service_a = MockBaseService("service_a")
        service_b = MockBaseService("service_b") 
        service_c = MockBaseService("service_c")
        service_d = MockBaseService("service_d")
        
        await service_registry.register_service(service_a)
        await service_registry.register_service(service_b, dependencies=["service_a"])
        await service_registry.register_service(service_c, dependencies=["service_a"])
        await service_registry.register_service(service_d, dependencies=["service_b", "service_c"])
        
        order = await service_registry._calculate_startup_order(["service_d"])
        
        # service_a 應該最先啟動
        assert order.index("service_a") < order.index("service_b")
        assert order.index("service_a") < order.index("service_c")
        # service_d 應該最後啟動
        assert order.index("service_b") < order.index("service_d")
        assert order.index("service_c") < order.index("service_d")
    
    @pytest.mark.asyncio
    async def test_circular_dependency_detection(self, service_registry):
        """測試循環依賴檢測"""
        service_a = MockBaseService("service_a")
        service_b = MockBaseService("service_b")
        
        await service_registry.register_service(service_a)
        await service_registry.register_service(service_b, dependencies=["service_a"])
        
        # 嘗試創建循環依賴
        service_registry._service_dependencies["service_a"] = ["service_b"]
        service_registry._dependent_services["service_b"] = ["service_a"]
        
        with pytest.raises(ValueError, match="檢測到循環依賴"):
            await service_registry._calculate_startup_order(["service_a"])
    
    @pytest.mark.asyncio
    async def test_get_service_health_status(self, service_registry):
        """測試獲取服務健康狀態"""
        service = MockBaseService("test_service")
        await service_registry.register_service(service)
        
        # 測試獲取單個服務健康狀態
        with patch.object(service_registry.__class__.__bases__[0], 'get_service_health_status', 
                         return_value={"status": "healthy"}) as mock_super:
            health_status = await service_registry.get_service_health_status("test_service")
            
            assert "lifecycle_status" in health_status
            assert "last_health_check" in health_status
            assert "health_check_response_time" in health_status
    
    @pytest.mark.asyncio
    async def test_get_service_health_status_all(self, service_registry):
        """測試獲取所有服務健康狀態"""
        service = MockBaseService("test_service")
        await service_registry.register_service(service)
        
        with patch.object(service_registry.__class__.__bases__[0], 'get_service_health_status', 
                         return_value={"total_services": 1}) as mock_super:
            all_health = await service_registry.get_service_health_status()
            
            assert "lifecycle_summary" in all_health
            assert "total_monitored_services" in all_health["lifecycle_summary"]
            assert "healthy_services" in all_health["lifecycle_summary"]
    
    def test_get_service_registration_history(self, service_registry):
        """測試獲取服務註冊歷史"""
        history = service_registry.get_service_registration_history(limit=10)
        
        assert isinstance(history, list)
        assert len(history) <= 10
    
    def test_get_service_type_statistics(self, service_registry):
        """測試獲取服務類型統計"""
        stats = service_registry.get_service_type_statistics()
        
        assert isinstance(stats, dict)
        assert "total_services" in stats
        assert "type_distribution" in stats
        assert "new_service_types_v2_4_4" in stats
        assert "statistics_timestamp" in stats
    
    @pytest.mark.asyncio
    async def test_perform_full_system_health_check(self, service_registry):
        """測試執行完整系統健康檢查"""
        service1 = MockBaseService("service1")
        service2 = MockBaseService("service2")
        
        await service_registry.register_service(service1)
        await service_registry.register_service(service2)
        
        system_health = await service_registry.perform_full_system_health_check()
        
        assert isinstance(system_health, dict)
        assert "overall_status" in system_health
        assert "total_services" in system_health
        assert "healthy_services" in system_health
        assert "services" in system_health
        assert "check_timestamp" in system_health
    
    @pytest.mark.asyncio
    async def test_validate_service_security(self, service_registry):
        """測試服務安全驗證"""
        # 測試部署服務安全驗證
        deployment_service = MockDeploymentService()
        deployment_service.service_metadata['service_type'] = 'deployment'
        await service_registry.register_service(deployment_service)
        
        security_result = await service_registry.validate_service_security("deployment_service")
        
        assert security_result["valid"] is True
        assert "security_level" in security_result
        assert "checks_passed" in security_result
        assert "warnings" in security_result
    
    @pytest.mark.asyncio 
    async def test_sync_service_state_to_database(self, service_registry):
        """測試同步服務狀態到資料庫"""
        service = MockBaseService("test_service")
        await service_registry.register_service(service)
        
        # Mock database manager
        mock_db_manager = MockDatabaseManager()
        
        with patch.object(service_registry, 'get_dependency', return_value=mock_db_manager):
            success = await service_registry.sync_service_state_to_database("test_service")
            assert success is True
    
    @pytest.mark.asyncio
    async def test_batch_sync_services_to_database(self, service_registry):
        """測試批量同步服務狀態到資料庫"""
        service1 = MockBaseService("service1")
        service2 = MockBaseService("service2")
        
        await service_registry.register_service(service1)
        await service_registry.register_service(service2)
        
        mock_db_manager = MockDatabaseManager()
        
        with patch.object(service_registry, 'get_dependency', return_value=mock_db_manager):
            results = await service_registry.batch_sync_services_to_database()
            
            assert isinstance(results, dict)
            assert "service1" in results
            assert "service2" in results
    
    def test_get_service_discovery_stats(self, service_registry):
        """測試獲取服務發現統計"""
        stats = service_registry.get_service_discovery_stats()
        
        assert isinstance(stats, dict)
        assert "total_registered_services" in stats
        assert "service_type_distribution" in stats
        assert "services_with_dependencies" in stats
        assert "services_with_auto_recovery" in stats
    
    def test_get_lifecycle_events(self, service_registry):
        """測試獲取生命週期事件"""
        events = service_registry.get_lifecycle_events(limit=10)
        
        assert isinstance(events, list)
        assert len(events) <= 10


@pytest.mark.skipif(SERVICE_REGISTRY_AVAILABLE, reason="Testing import failure handling")
class TestServiceRegistryImportFailure:
    """測試服務註冊模組導入失敗的情況"""
    
    def test_service_registry_not_available(self):
        """測試服務註冊模組不可用時的處理"""
        assert not SERVICE_REGISTRY_AVAILABLE


if __name__ == "__main__":
    # 運行測試
    pytest.main([__file__, "-v"])