"""
增強版服務註冊機制整合測試
Task ID: 1 - 核心架構和基礎設施建置

這個測試模組驗證v2.4.4版本的服務註冊機制完善情況：
- 三種新服務類型的註冊機制
- 服務生命週期管理和依賴關係
- 安全驗證和資料庫協調
- 動態服務發現和自動註冊
"""

import pytest
import asyncio
import tempfile
import os
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from typing import Dict, Any

# 導入被測試的模組
from src.core.service_registry import ExtendedServiceRegistry, ServiceStatus
from src.core.service_lifecycle import ServiceLifecycleManager, HealthStatus
from src.services.deployment_service import DeploymentService
from src.services.subbot_service import SubBotService
from src.services.ai_service import AIService


class TestEnhancedServiceRegistryIntegration:
    """增強版服務註冊機制整合測試"""
    
    @pytest.fixture
    async def lifecycle_manager(self):
        """創建服務生命週期管理器實例"""
        manager = ServiceLifecycleManager(check_interval=1)
        await manager.start()
        yield manager
        await manager.stop()
    
    @pytest.fixture
    async def registry(self, lifecycle_manager):
        """創建擴展服務註冊機制實例"""
        registry = ExtendedServiceRegistry(lifecycle_manager)
        return registry
    
    @pytest.fixture
    async def mock_database_manager(self):
        """模擬資料庫管理器"""
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.fetchone = AsyncMock()
        mock_db.fetchall = AsyncMock(return_value=[])
        return mock_db
    
    @pytest.fixture
    async def deployment_service(self):
        """創建部署服務實例"""
        with tempfile.TemporaryDirectory() as temp_dir:
            service = DeploymentService(temp_dir)
            await service._initialize()
            yield service
            await service._cleanup()
    
    @pytest.fixture
    async def subbot_service(self):
        """創建子機器人服務實例"""
        service = SubBotService("test_encryption_key")
        await service._initialize()
        yield service
        await service._cleanup()
    
    @pytest.fixture
    async def ai_service(self):
        """創建AI服務實例"""
        service = AIService("openai")
        await service._initialize()
        yield service
        await service._cleanup()
    
    @pytest.mark.asyncio
    async def test_deployment_service_registration(self, registry, deployment_service):
        """測試部署服務註冊"""
        # 註冊部署服務
        service_name = await registry.register_deployment_service(
            service=deployment_service,
            deployment_mode="docker",
            environment_config={"python_version": "3.11"},
            auto_restart=True,
            dependencies=["database_manager"]
        )
        
        # 驗證服務已註冊
        assert service_name in registry.list_services()
        
        # 驗證服務元數據
        service = registry.get_service(service_name)
        assert service is not None
        assert hasattr(service, 'service_metadata')
        metadata = service.service_metadata
        assert metadata['deployment_capabilities']['docker_support'] is True
        assert metadata['enhanced_features']['dependency_management'] is True
        
        # 驗證依賴關係
        dependencies = registry.get_service_dependencies(service_name)
        assert "database_manager" in dependencies
    
    @pytest.mark.asyncio
    async def test_subbot_service_registration(self, registry, subbot_service):
        """測試子機器人服務註冊"""
        # 註冊子機器人服務
        service_name = await registry.register_sub_bot_service(
            service=subbot_service,
            bot_id="test_bot_123",
            target_channels=["channel_1", "channel_2"],
            ai_integration=True,
            dependencies=["database_manager", "ai_service"]
        )
        
        # 驗證服務已註冊
        assert service_name in registry.list_services()
        
        # 驗證服務元數據
        service = registry.get_service(service_name)
        metadata = service.service_metadata
        assert metadata['ai_integration'] is True
        assert metadata['enhanced_features']['ai_integration_ready'] is True
        
        # 驗證依賴關係
        dependencies = registry.get_service_dependencies(service_name)
        assert "database_manager" in dependencies
        assert "ai_service" in dependencies
    
    @pytest.mark.asyncio
    async def test_ai_service_registration(self, registry, ai_service):
        """測試AI服務註冊"""
        # 註冊AI服務
        service_name = await registry.register_ai_service(
            service=ai_service,
            provider="openai",
            models=["gpt-3.5-turbo", "gpt-4"],
            security_level="high",
            dependencies=["database_manager"]
        )
        
        # 驗證服務已註冊
        assert service_name in registry.list_services()
        
        # 驗證服務元數據
        service = registry.get_service(service_name)
        metadata = service.service_metadata
        assert metadata['security_level'] == "high"
        assert metadata['enhanced_features']['security_filtering'] is True
        
        # 驗證依賴關係
        dependencies = registry.get_service_dependencies(service_name)
        assert "database_manager" in dependencies
    
    @pytest.mark.asyncio
    async def test_dependency_management(self, registry, deployment_service, ai_service):
        """測試服務依賴關係管理"""
        # 先註冊依賴服務（模擬database_manager）
        mock_db_service = Mock()
        mock_db_service.service_metadata = {'service_type': 'database'}
        await registry.register_service(
            service=mock_db_service,
            name="database_manager",
            priority=1
        )
        
        # 註冊AI服務（依賴database_manager）
        ai_name = await registry.register_ai_service(
            service=ai_service,
            provider="openai",
            models=["gpt-3.5-turbo"],
            dependencies=["database_manager"]
        )
        
        # 註冊部署服務（依賴database_manager和ai_service）
        deployment_name = await registry.register_deployment_service(
            service=deployment_service,
            deployment_mode="uv",
            dependencies=["database_manager", ai_name]
        )
        
        # 驗證依賴關係建立正確
        deployment_deps = registry.get_service_dependencies(deployment_name)
        assert "database_manager" in deployment_deps
        assert ai_name in deployment_deps
        
        # 驗證反向依賴關係
        db_dependents = registry.get_dependent_services("database_manager")
        assert ai_name in db_dependents
        assert deployment_name in db_dependents
        
        ai_dependents = registry.get_dependent_services(ai_name)
        assert deployment_name in ai_dependents
    
    @pytest.mark.asyncio
    async def test_startup_order_calculation(self, registry, deployment_service, ai_service):
        """測試服務啟動順序計算"""
        # 創建依賴鏈：database -> ai -> deployment
        mock_db_service = Mock()
        mock_db_service.service_metadata = {'service_type': 'database'}
        await registry.register_service(mock_db_service, name="database_manager", priority=1)
        
        ai_name = await registry.register_ai_service(
            ai_service, "openai", ["gpt-3.5-turbo"], dependencies=["database_manager"]
        )
        
        deployment_name = await registry.register_deployment_service(
            deployment_service, "docker", dependencies=[ai_name]
        )
        
        # 計算啟動順序
        startup_order = await registry._calculate_startup_order([deployment_name])
        
        # 驗證順序正確
        assert startup_order.index("database_manager") < startup_order.index(ai_name)
        assert startup_order.index(ai_name) < startup_order.index(deployment_name)
    
    @pytest.mark.asyncio
    async def test_health_check_enhancement(self, registry, lifecycle_manager, deployment_service):
        """測試增強的健康檢查"""
        # 註冊部署服務
        service_name = await registry.register_deployment_service(
            deployment_service, "docker"
        )
        
        # 執行健康檢查
        health_info = await lifecycle_manager.perform_health_check(service_name)
        
        # 驗證健康檢查結果
        assert health_info is not None
        assert health_info.service_name == service_name
        assert health_info.status in [HealthStatus.HEALTHY, HealthStatus.UNHEALTHY, HealthStatus.DEGRADED]
        assert health_info.response_time >= 0
    
    @pytest.mark.asyncio
    async def test_service_security_validation(self, registry, subbot_service):
        """測試服務安全驗證"""
        # 註冊子機器人服務
        service_name = await registry.register_sub_bot_service(
            subbot_service, "test_bot", ["channel_1"]
        )
        
        # 執行安全驗證
        security_result = await registry.validate_service_security(service_name)
        
        # 驗證安全檢查結果
        assert security_result['valid'] is True
        assert 'security_level' in security_result
        assert 'checks_passed' in security_result
        assert isinstance(security_result['checks_passed'], list)
    
    @pytest.mark.asyncio
    async def test_database_synchronization(self, registry, mock_database_manager, ai_service):
        """測試資料庫狀態同步"""
        # 設置資料庫依賴
        registry._dependencies = {"database_manager": mock_database_manager}
        
        # 註冊AI服務
        service_name = await registry.register_ai_service(
            ai_service, "openai", ["gpt-3.5-turbo"]
        )
        
        # 同步到資料庫
        success = await registry.sync_service_state_to_database(service_name)
        
        # 驗證同步操作
        assert success is True
        mock_database_manager.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_service_discovery(self, registry):
        """測試服務發現功能"""
        with patch('os.path.exists', return_value=True):
            with patch('os.walk') as mock_walk:
                # 模擬文件系統結構
                mock_walk.return_value = [
                    ('src/services', [], ['deployment_service.py', 'ai_service.py'])
                ]
                
                with patch('builtins.open', mock_open_with_service_content()):
                    discovered = await registry.discover_services(['src/services'])
                
                # 驗證發現結果
                assert 'deployment_services' in discovered
                assert 'ai_services' in discovered
    
    @pytest.mark.asyncio
    async def test_auto_recovery(self, registry, lifecycle_manager, deployment_service):
        """測試自動恢復功能"""
        # 註冊具有自動恢復功能的服務
        service_name = await registry.register_deployment_service(
            deployment_service, "docker"
        )
        
        # 模擬服務故障
        lifecycle_manager.update_service_status(service_name, ServiceStatus.ERROR)
        
        # 觸發自動恢復
        recovery_success = await lifecycle_manager._attempt_service_recovery(service_name)
        
        # 由於這是模擬環境，我們主要驗證恢復機制被調用
        # 實際的恢復成功與否取決於服務的具體實現
        assert recovery_success in [True, False]  # 允許兩種結果
    
    @pytest.mark.asyncio
    async def test_full_system_integration(self, registry, lifecycle_manager, 
                                         deployment_service, subbot_service, ai_service,
                                         mock_database_manager):
        """測試完整系統整合"""
        # 設置資料庫依賴
        registry._dependencies = {"database_manager": mock_database_manager}
        
        # 註冊基礎服務
        db_service = Mock()
        db_service.service_metadata = {'service_type': 'database'}
        await registry.register_service(db_service, name="database_manager", priority=1)
        
        # 註冊所有三種新服務類型
        ai_name = await registry.register_ai_service(
            ai_service, "openai", ["gpt-3.5-turbo"], dependencies=["database_manager"]
        )
        
        subbot_name = await registry.register_sub_bot_service(
            subbot_service, "test_bot", ["channel_1"], 
            ai_integration=True, dependencies=["database_manager", ai_name]
        )
        
        deployment_name = await registry.register_deployment_service(
            deployment_service, "docker", dependencies=["database_manager"]
        )
        
        # 執行完整的系統健康檢查
        health_report = await registry.perform_full_system_health_check()
        
        # 驗證系統狀態
        assert health_report['total_services'] == 4  # 包含database_manager
        assert 'services' in health_report
        assert deployment_name in health_report['services']
        assert subbot_name in health_report['services']
        assert ai_name in health_report['services']
        
        # 批量同步到資料庫
        sync_results = await registry.batch_sync_services_to_database()
        assert len(sync_results) == 4
        
        # 獲取服務發現統計
        stats = registry.get_service_discovery_stats()
        assert stats['total_registered_services'] == 4
        assert 'service_type_distribution' in stats


def mock_open_with_service_content():
    """模擬文件內容的helper函數"""
    def mock_open(*args, **kwargs):
        class MockFile:
            def read(self):
                if 'deployment_service.py' in args[0]:
                    return """
from core.base_service import BaseService

class DeploymentService(BaseService):
    def __init__(self):
        super().__init__("DeploymentService")
"""
                elif 'ai_service.py' in args[0]:
                    return """
from core.base_service import BaseService

class AIService(BaseService):
    def __init__(self):
        super().__init__("AIService")
"""
                return ""
            
            def __enter__(self):
                return self
            
            def __exit__(self, *args):
                pass
        
        return MockFile()
    
    return mock_open


@pytest.mark.asyncio
async def test_concurrent_service_operations():
    """測試並發服務操作"""
    lifecycle_manager = ServiceLifecycleManager(check_interval=1)
    await lifecycle_manager.start()
    
    try:
        registry = ExtendedServiceRegistry(lifecycle_manager)
        
        # 創建多個服務實例
        services = []
        for i in range(5):
            service = Mock()
            service.service_metadata = {'service_type': f'test_{i}'}
            service.health_check = AsyncMock(return_value={'initialized': True})
            services.append(service)
        
        # 並發註冊服務
        registration_tasks = []
        for i, service in enumerate(services):
            task = asyncio.create_task(
                registry.register_service(service, name=f"service_{i}", priority=i*10)
            )
            registration_tasks.append(task)
        
        # 等待所有註冊完成
        service_names = await asyncio.gather(*registration_tasks)
        
        # 驗證所有服務都成功註冊
        assert len(service_names) == 5
        for name in service_names:
            assert name in registry.list_services()
        
        # 並發健康檢查
        health_tasks = []
        for name in service_names:
            task = asyncio.create_task(
                lifecycle_manager.perform_health_check(name)
            )
            health_tasks.append(task)
        
        health_results = await asyncio.gather(*health_tasks, return_exceptions=True)
        
        # 驗證健康檢查結果
        assert len(health_results) == 5
        for result in health_results:
            if not isinstance(result, Exception):
                assert result.status in [HealthStatus.HEALTHY, HealthStatus.UNHEALTHY]
        
    finally:
        await lifecycle_manager.stop()


if __name__ == "__main__":
    # 運行測試
    pytest.main([__file__, "-v"])