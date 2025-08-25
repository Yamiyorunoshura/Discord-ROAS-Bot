#!/usr/bin/env python3
"""
基礎設施模組測試
Task ID: 1 - ROAS Bot v2.4.3 Docker啟動系統修復

測試環境檢查器、部署管理器、監控收集器和錯誤處理器的功能。
"""

import pytest
import asyncio
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
import json
from datetime import datetime

# 導入被測試的模組
import sys
sys.path.append(str(Path(__file__).parent.parent))

from core.environment_validator import EnvironmentValidator, ValidationResult
from core.deployment_manager import DeploymentManager, ServiceStatus, ServiceInfo
from core.monitoring_collector import MonitoringCollector, HealthStatus, ServiceMetrics
from core.error_handler import ErrorHandler, ErrorCategory, ErrorSeverity, DeploymentError


class TestEnvironmentValidator:
    """測試環境檢查器"""
    
    @pytest.fixture
    def temp_project(self):
        """創建臨時專案目錄"""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            
            # 創建基本檔案結構
            (project_path / 'pyproject.toml').touch()
            (project_path / 'Dockerfile').touch()
            (project_path / 'docker-compose.dev.yml').write_text('''
services:
  test:
    image: test:latest
''')
            (project_path / 'docker-compose.prod.yml').touch()
            
            yield project_path
    
    @pytest.mark.asyncio
    async def test_basic_environment_validation(self, temp_project):
        """測試基本環境驗證"""
        validator = EnvironmentValidator(temp_project)
        
        with patch.dict(os.environ, {'DISCORD_TOKEN': 'test_token'}):
            passed, errors = await validator.validate_environment()
        
        # 應該有一些驗證結果
        assert len(validator.validation_results) > 0
        
        # 檢查配置檔案驗證結果
        config_results = [r for r in validator.validation_results 
                         if 'pyproject.toml' in r.name or 'Dockerfile' in r.name]
        assert len(config_results) >= 2
    
    @pytest.mark.asyncio
    async def test_missing_environment_variables(self, temp_project):
        """測試缺少環境變數的情況"""
        validator = EnvironmentValidator(temp_project)
        
        # 清除DISCORD_TOKEN環境變數
        with patch.dict(os.environ, {}, clear=True):
            passed, errors = await validator.validate_environment()
        
        # 應該有環境變數相關的錯誤
        env_errors = [error for error in errors if 'DISCORD_TOKEN' in error]
        assert len(env_errors) > 0
    
    def test_generate_report(self, temp_project):
        """測試生成驗證報告"""
        validator = EnvironmentValidator(temp_project)
        
        # 添加一些模擬驗證結果
        validator.validation_results = [
            ValidationResult("測試檢查1", True, "通過"),
            ValidationResult("測試檢查2", False, "失敗", suggestions=["修復建議"])
        ]
        
        report = validator.generate_report()
        
        assert report.overall_status is False  # 有失敗項目
        assert len(report.validation_results) == 2
        assert len(report.critical_issues) == 1
        assert len(report.recommendations) == 1


class TestDeploymentManager:
    """測試部署管理器"""
    
    @pytest.fixture
    def temp_project(self):
        """創建臨時專案目錄"""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            
            # 創建docker-compose文件
            compose_content = '''
services:
  test-service:
    image: alpine:latest
    command: sleep 30
'''
            (project_path / 'docker-compose.test.yml').write_text(compose_content)
            yield project_path
    
    @pytest.mark.asyncio
    async def test_deployment_manager_initialization(self, temp_project):
        """測試部署管理器初始化"""
        manager = DeploymentManager(temp_project, 'docker-compose.test.yml')
        
        assert manager.project_root == temp_project
        assert manager.compose_file == 'docker-compose.test.yml'
        assert manager.deployment_timeout == 300
    
    @pytest.mark.asyncio
    async def test_get_services_info_mock(self, temp_project):
        """測試獲取服務資訊（模擬）"""
        manager = DeploymentManager(temp_project, 'docker-compose.test.yml')
        
        # 模擬docker-compose ps輸出
        mock_output = '{"Name": "test-service", "ID": "abc123", "State": "running", "Health": "healthy"}\n'
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = mock_output
            
            services = await manager._get_services_info()
            
            assert len(services) == 1
            assert services[0].name == 'test-service'
            assert services[0].container_id == 'abc123'
            assert services[0].status == ServiceStatus.HEALTHY
    
    @pytest.mark.asyncio
    async def test_health_check(self, temp_project):
        """測試健康檢查功能"""
        manager = DeploymentManager(temp_project, 'docker-compose.test.yml')
        
        # 模擬健康的服務
        mock_services = [
            ServiceInfo(
                name='test-service',
                container_id='abc123',
                status=ServiceStatus.HEALTHY,
                health_status='healthy',
                ports=[],
                created_at=None,
                started_at=None
            )
        ]
        
        with patch.object(manager, '_get_services_info', return_value=mock_services):
            health_result = await manager.health_check()
            
            assert health_result['overall_healthy'] is True
            assert health_result['summary']['healthy'] == 1
            assert 'test-service' in health_result['services']


class TestMonitoringCollector:
    """測試監控收集器"""
    
    @pytest.fixture
    def temp_project(self):
        """創建臨時專案目錄"""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            (project_path / 'data').mkdir(exist_ok=True)
            yield project_path
    
    @pytest.mark.asyncio
    async def test_monitoring_collector_initialization(self, temp_project):
        """測試監控收集器初始化"""
        collector = MonitoringCollector(temp_project)
        
        assert collector.project_root == temp_project
        assert collector.check_interval == 30
        assert (temp_project / 'data' / 'monitoring.db').exists()
    
    @pytest.mark.asyncio
    async def test_system_metrics_collection(self, temp_project):
        """測試系統指標收集"""
        collector = MonitoringCollector(temp_project)
        
        system_metrics = await collector._collect_system_metrics()
        
        assert system_metrics.cpu_usage_percent >= 0
        assert system_metrics.memory_usage_percent >= 0
        assert system_metrics.memory_available_gb >= 0
        assert len(system_metrics.load_average) == 3
    
    @pytest.mark.asyncio
    async def test_service_health_check_mock(self, temp_project):
        """測試服務健康檢查（模擬）"""
        collector = MonitoringCollector(temp_project)
        
        # 模擬容器資訊
        mock_container_info = {
            'container_id': 'abc123',
            'name': 'test-service',
            'state': 'running',
            'health_status': 'healthy',
            'status': 'Up 5 minutes'
        }
        
        with patch.object(collector, '_get_container_info', return_value=mock_container_info), \
             patch.object(collector, '_get_container_resources', return_value=(10.0, 256.0)):
            
            service_metrics = await collector.check_service_health('test-service')
            
            assert service_metrics.service_name == 'test-service'
            assert service_metrics.status == HealthStatus.HEALTHY
            assert service_metrics.cpu_usage_percent == 10.0
            assert service_metrics.memory_usage_mb == 256.0
    
    @pytest.mark.asyncio
    async def test_collect_metrics_integration(self, temp_project):
        """測試完整指標收集"""
        collector = MonitoringCollector(temp_project)
        
        with patch.object(collector, '_collect_services_metrics', return_value=[]):
            metrics = await collector.collect_metrics()
            
            assert 'timestamp' in metrics
            assert 'overall_status' in metrics
            assert 'system_metrics' in metrics
            assert 'service_metrics' in metrics
            assert 'summary' in metrics


class TestErrorHandler:
    """測試錯誤處理器"""
    
    @pytest.fixture
    def temp_project(self):
        """創建臨時專案目錄"""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            (project_path / 'data').mkdir(exist_ok=True)
            yield project_path
    
    @pytest.mark.asyncio
    async def test_error_handler_initialization(self, temp_project):
        """測試錯誤處理器初始化"""
        handler = ErrorHandler(temp_project)
        
        assert handler.project_root == temp_project
        assert (temp_project / 'data' / 'errors.db').exists()
        assert len(handler.classification_rules) > 0
        assert len(handler.recovery_strategies) > 0
    
    @pytest.mark.asyncio
    async def test_error_classification(self, temp_project):
        """測試錯誤分類"""
        handler = ErrorHandler(temp_project)
        
        # 測試Docker錯誤分類
        docker_error = Exception("docker: command not found")
        category, severity = handler._classify_error(docker_error, {'operation': 'deploy'})
        assert category == ErrorCategory.DOCKER
        assert severity == ErrorSeverity.HIGH
        
        # 測試網路錯誤分類
        network_error = Exception("connection timeout")
        category, severity = handler._classify_error(network_error, {'network_operation': True})
        assert category == ErrorCategory.NETWORK
        assert severity == ErrorSeverity.MEDIUM
    
    @pytest.mark.asyncio
    async def test_handle_error_flow(self, temp_project):
        """測試錯誤處理流程"""
        handler = ErrorHandler(temp_project)
        
        test_error = Exception("Docker container failed to start")
        context = {'operation': 'start_services', 'service': 'test'}
        
        recovery_action = await handler.handle_error(test_error, context)
        
        assert recovery_action.action_type in ['restart_compose', 'restart_docker', 'manual_check']
        assert recovery_action.description is not None
        assert recovery_action.timeout_seconds > 0


# 整合測試
class TestInfrastructureIntegration:
    """基礎設施整合測試"""
    
    @pytest.fixture
    def temp_project(self):
        """創建完整的臨時專案"""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            
            # 創建完整的專案結構
            (project_path / 'pyproject.toml').write_text('[tool.poetry]\nname = "test"')
            (project_path / 'Dockerfile').write_text('FROM python:3.9\nWORKDIR /app')
            
            compose_content = '''
services:
  test-app:
    build: .
    ports:
      - "8000:8000"
  test-redis:
    image: redis:alpine
    ports:
      - "6379:6379"
'''
            (project_path / 'docker-compose.dev.yml').write_text(compose_content)
            (project_path / 'docker-compose.prod.yml').write_text(compose_content)
            
            # 創建數據目錄
            (project_path / 'data').mkdir()
            (project_path / 'logs').mkdir()
            (project_path / 'backups').mkdir()
            
            yield project_path
    
    @pytest.mark.asyncio
    async def test_full_infrastructure_workflow(self, temp_project):
        """測試完整的基礎設施工作流程"""
        # 1. 環境驗證
        validator = EnvironmentValidator(temp_project)
        
        with patch.dict(os.environ, {'DISCORD_TOKEN': 'test_token'}), \
             patch('subprocess.run') as mock_run:
            
            # 模擬Docker命令成功
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = 'Docker version 20.10.0'
            
            passed, errors = await validator.validate_environment()
            
            # 環境驗證應該大部分通過
            assert len(validator.validation_results) > 5
        
        # 2. 部署管理
        manager = DeploymentManager(temp_project, 'docker-compose.dev.yml')
        
        # 模擬部署過程（不實際執行Docker命令）
        with patch.object(manager, '_pre_deployment_check', return_value=True), \
             patch.object(manager, '_pull_images', return_value=True), \
             patch.object(manager, '_build_images', return_value=True), \
             patch.object(manager, '_start_services_internal', return_value=True), \
             patch.object(manager, '_wait_for_services', return_value=True), \
             patch.object(manager, '_comprehensive_health_check', return_value=(True, "所有服務健康")):
            
            success, message = await manager.start_services()
            assert success is True
            assert "成功" in message
        
        # 3. 監控收集
        collector = MonitoringCollector(temp_project)
        
        with patch.object(collector, '_collect_services_metrics', return_value=[]):
            metrics = await collector.collect_metrics()
            
            assert metrics['overall_status'] is not None
            assert 'system_metrics' in metrics
        
        # 4. 錯誤處理
        error_handler = ErrorHandler(temp_project)
        
        test_error = Exception("測試整合錯誤")
        context = {'integration_test': True}
        
        recovery_action = await error_handler.handle_error(test_error, context)
        assert recovery_action.action_type is not None


# 工具函數測試
class TestUtilities:
    """測試工具函數"""
    
    @pytest.mark.asyncio
    async def test_create_deployment_manager(self):
        """測試部署管理器工廠函數"""
        from core.deployment_manager import create_deployment_manager
        
        manager = create_deployment_manager('dev')
        assert manager.compose_file == 'docker-compose.dev.yml'
        
        manager = create_deployment_manager('prod')
        assert manager.compose_file == 'docker-compose.prod.yml'
    
    @pytest.mark.asyncio
    async def test_quick_health_check(self):
        """測試快速健康檢查"""
        from core.monitoring_collector import quick_health_check
        
        with patch('core.monitoring_collector.MonitoringCollector.collect_metrics') as mock_collect:
            mock_collect.return_value = {
                'overall_status': 'healthy',
                'summary': {'total_services': 2, 'healthy_services': 2}
            }
            
            result = await quick_health_check()
            assert result['overall_status'] == 'healthy'


if __name__ == '__main__':
    # 運行測試
    pytest.main([__file__, '-v', '--tb=short'])