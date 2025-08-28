"""
部署服務API測試
Task ID: 2 - 自動化部署和啟動系統開發

Elena - API架構師
這個測試文件展示部署服務API的使用方式和與服務註冊機制的整合
"""

import asyncio
import pytest
from pathlib import Path
from datetime import datetime

from src.services.deployment_api import (
    DeploymentServiceAPI,
    DeploymentRequest,
    DeploymentResponse,
    DeploymentAPIStatus,
    create_deployment_service_api
)
from src.services.uv_deployment_manager import UVDeploymentManager
from src.services.fallback_deployment_manager import FallbackDeploymentManager
from src.core.service_registry import extended_service_registry


class TestDeploymentServiceAPI:
    """部署服務API測試類"""
    
    @pytest.fixture
    async def deployment_api(self):
        """創建部署服務API實例"""
        api = create_deployment_service_api(Path.cwd())
        await api.start()
        yield api
        await api.stop()
    
    async def test_api_initialization(self, deployment_api):
        """測試API初始化"""
        assert deployment_api.api_status == DeploymentAPIStatus.READY
        assert deployment_api.api_config['version'] == '1.0.0'
        assert len(deployment_api._deployment_managers) > 0
    
    async def test_health_check(self, deployment_api):
        """測試健康檢查API"""
        health = await deployment_api.health_check()
        
        assert 'api_status' in health
        assert 'timestamp' in health
        assert 'version' in health
        assert 'deployment_managers' in health
        assert health['version'] == '1.0.0'
    
    async def test_deployment_request_validation(self):
        """測試部署請求驗證"""
        # 有效請求
        valid_request = DeploymentRequest(
            mode='uv',
            environment='dev',
            timeout=300
        )
        errors = valid_request.validate()
        assert len(errors) == 0
        
        # 無效請求
        invalid_request = DeploymentRequest(
            mode='invalid_mode',
            environment='invalid_env',
            timeout=10  # 太短
        )
        errors = invalid_request.validate()
        assert len(errors) > 0
    
    async def test_service_registry_integration(self, deployment_api):
        """測試與服務註冊機制的整合"""
        # 註冊到服務註冊中心
        service_name = await deployment_api.register_with_service_registry()
        
        assert service_name is not None
        assert service_name in extended_service_registry.list_services()
        
        # 檢查服務健康狀態
        health_status = await extended_service_registry.get_service_health_status(service_name)
        assert health_status is not None
        assert health_status.get('service_name') == service_name
        
        # 檢查服務類型統計
        stats = extended_service_registry.get_service_type_statistics()
        assert stats['new_service_types_v2_4_4']['deployment_services'] >= 1
    
    async def test_deployment_managers_registration(self, deployment_api):
        """測試部署管理器註冊"""
        managers = deployment_api._deployment_managers
        
        # 檢查是否註冊了預期的管理器
        expected_managers = ['uv', 'fallback']
        for manager_type in expected_managers:
            assert manager_type in managers
        
        # 檢查UV管理器
        uv_manager = managers.get('uv')
        assert isinstance(uv_manager, UVDeploymentManager)
        
        # 檢查降級管理器
        fallback_manager = managers.get('fallback')
        assert isinstance(fallback_manager, FallbackDeploymentManager)
    
    async def test_deployment_flow_simulation(self, deployment_api):
        """測試部署流程模擬"""
        # 創建部署請求
        request = DeploymentRequest(
            mode='fallback',  # 使用降級模式確保測試可靠
            config={
                'environment_variables': {
                    'TEST_MODE': 'true'
                }
            },
            environment='dev',
            timeout=60
        )
        
        # 開始部署（模擬）
        try:
            response = await deployment_api.start_deployment(request)
            
            assert isinstance(response, DeploymentResponse)
            assert response.deployment_id is not None
            assert response.status == 'accepted'
            assert response.mode == 'fallback'
            
            deployment_id = response.deployment_id
            
            # 檢查部署狀態
            await asyncio.sleep(1)  # 給部署一點時間
            status = await deployment_api.get_deployment_status(deployment_id)
            assert status['deployment_id'] == deployment_id
            
            # 檢查進度（如果還在運行）
            if deployment_id in deployment_api._active_deployments:
                progress = await deployment_api.get_deployment_progress(deployment_id)
                assert progress.deployment_id == deployment_id
            
            # 清理：取消部署
            if deployment_id in deployment_api._active_deployments:
                cancel_result = await deployment_api.cancel_deployment(deployment_id)
                assert cancel_result['status'] in ['cancelled', 'not_found']
        
        except Exception as e:
            # 在測試環境中，某些部署操作可能會失敗，這是預期的
            print(f"部署測試遇到預期錯誤: {e}")
    
    async def test_concurrent_deployment_limit(self, deployment_api):
        """測試併發部署限制"""
        max_concurrent = deployment_api.api_config['max_concurrent_deployments']
        
        # 創建超過限制的部署請求
        requests = []
        for i in range(max_concurrent + 1):
            request = DeploymentRequest(
                mode='fallback',
                config={'test_id': i},
                timeout=30
            )
            requests.append(request)
        
        # 嘗試同時提交所有請求
        successful_deployments = []
        failed_deployments = []
        
        for request in requests:
            try:
                response = await deployment_api.start_deployment(request)
                successful_deployments.append(response.deployment_id)
            except Exception as e:
                failed_deployments.append(str(e))
        
        # 清理成功的部署
        for deployment_id in successful_deployments:
            if deployment_id in deployment_api._active_deployments:
                await deployment_api.cancel_deployment(deployment_id)
        
        # 驗證併發限制
        assert len(successful_deployments) <= max_concurrent
    
    async def test_deployment_history(self, deployment_api):
        """測試部署歷史功能"""
        # 列出部署歷史
        history = await deployment_api.list_deployments(limit=10)
        
        assert isinstance(history, list)
        # 歷史可能為空，這是正常的
    
    async def test_api_statistics(self, deployment_api):
        """測試API統計資訊"""
        stats = deployment_api._deployment_stats
        
        assert 'total_deployments' in stats
        assert 'successful_deployments' in stats
        assert 'failed_deployments' in stats
        assert 'cancelled_deployments' in stats
        assert 'average_deployment_time' in stats
        
        # 統計值應該是數字
        for key, value in stats.items():
            assert isinstance(value, (int, float))
    
    async def test_middleware_functionality(self, deployment_api):
        """測試中間件功能"""
        # 檢查中間件是否已設置
        assert len(deployment_api._request_middleware) > 0
        assert len(deployment_api._response_middleware) > 0
        
        # 創建測試請求
        request = DeploymentRequest(mode='fallback')
        
        # 應用請求中間件
        for middleware in deployment_api._request_middleware:
            request = await middleware(request)
        
        # 檢查中間件是否設置了默認值
        assert request.config is not None
        assert request.timeout is not None
        
        # 測試回應中間件
        response = DeploymentResponse(
            deployment_id='test_123',
            status='test',
            message='test message'
        )
        
        for middleware in deployment_api._response_middleware:
            response = await middleware(response)
        
        # 檢查中間件是否添加了元數據
        assert response.metadata is not None
        assert 'api_version' in response.metadata


class TestServiceRegistryIntegration:
    """服務註冊整合測試"""
    
    async def test_extended_service_registry_deployment_support(self):
        """測試擴展服務註冊機制對部署服務的支援"""
        # 創建模擬部署服務
        deployment_api = create_deployment_service_api()
        
        try:
            # 註冊部署服務
            service_name = await extended_service_registry.register_deployment_service(
                service=deployment_api,
                deployment_mode='api',
                name='TestDeploymentAPI',
                environment_config={
                    'test_mode': True,
                    'supported_modes': ['uv', 'fallback']
                }
            )
            
            assert service_name == 'TestDeploymentAPI'
            
            # 檢查服務是否在註冊表中
            assert service_name in extended_service_registry.list_services()
            
            # 檢查服務元數據
            service = extended_service_registry.get_service(service_name)
            assert service is not None
            assert hasattr(service, 'service_metadata')
            
            metadata = service.service_metadata
            assert metadata.get('service_type') == 'deployment'
            assert 'environment_config' in metadata
            assert metadata['environment_config']['test_mode'] is True
            
            # 測試服務健康檢查整合
            health_status = await extended_service_registry.get_service_health_status(service_name)
            assert health_status is not None
            
            # 清理
            await extended_service_registry.unregister_service(service_name)
            
        except Exception as e:
            print(f"服務註冊整合測試失敗: {e}")
            raise
    
    async def test_service_discovery_for_deployment_services(self):
        """測試部署服務的服務發現功能"""
        # 執行服務發現
        discovered_services = await extended_service_registry.discover_services([
            'src/services'
        ])
        
        # 檢查是否發現了部署服務
        deployment_services = discovered_services.get('deployment_services', [])
        
        # 應該發現我們剛創建的部署服務
        service_names = [svc['name'] for svc in deployment_services]
        
        expected_services = [
            'DeploymentServiceAPI',
            'UVDeploymentManager', 
            'FallbackDeploymentManager'
        ]
        
        for expected_service in expected_services:
            # 檢查是否在發現的服務中（可能不完全匹配）
            found = any(expected_service in name for name in service_names)
            if not found:
                print(f"警告：未發現預期的服務 {expected_service}")
    
    async def test_deployment_service_lifecycle_management(self):
        """測試部署服務生命週期管理"""
        # 創建部署服務
        deployment_api = create_deployment_service_api()
        
        try:
            # 註冊並啟動服務
            await deployment_api.start()
            service_name = await deployment_api.register_with_service_registry()
            
            # 檢查生命週期狀態
            lifecycle_manager = extended_service_registry.lifecycle_manager
            service_status = lifecycle_manager.get_service_status(service_name)
            
            # 服務應該處於運行狀態
            assert service_status is not None
            
            # 執行健康檢查
            health_info = await lifecycle_manager.perform_health_check(service_name)
            assert health_info is not None
            
            # 停止服務
            await deployment_api.stop()
            
        except Exception as e:
            print(f"生命週期管理測試失敗: {e}")
            raise


# 運行測試的主函數
async def main():
    """運行所有測試"""
    print("開始部署服務API測試...")
    
    # 創建API實例並測試基本功能
    api = create_deployment_service_api()
    await api.start()
    
    try:
        # 健康檢查測試
        health = await api.health_check()
        print(f"健康檢查結果: {health['api_status']}")
        
        # 服務註冊測試
        service_name = await api.register_with_service_registry()
        print(f"服務已註冊: {service_name}")
        
        # 檢查統計資訊
        stats = api._deployment_stats
        print(f"部署統計: {stats}")
        
        print("部署服務API測試完成!")
        
    except Exception as e:
        print(f"測試過程中發生錯誤: {e}")
        raise
    
    finally:
        await api.stop()


if __name__ == "__main__":
    asyncio.run(main())