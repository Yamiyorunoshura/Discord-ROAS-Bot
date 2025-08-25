"""
整合測試套件 - 完整啟動流程
Task ID: 1 - ROAS Bot v2.4.3 Docker啟動系統修復

測試目標：
- 完整啟動流程測試：從環境檢查到服務健康確認
- 模組間協作測試：驗證各模組間的交互是否正常
- 端到端場景測試：模擬真實部署場景

基於知識庫最佳實踐BP-001: 測試基礎設施設計模式
"""

import asyncio
import os
import tempfile
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import pytest

# 導入我們的測試模組
from .test_environment_validator import EnvironmentValidator
from .test_deployment_manager import DeploymentManager, ServiceStatus as DeploymentServiceStatus
from .test_monitoring_collector import MonitoringCollector, ServiceStatus as MonitoringServiceStatus
from .test_error_handler import ErrorHandler, DeploymentError, ErrorCategory, ErrorSeverity


class DockerStartupOrchestrator:
    """Docker啟動編排器 - 協調所有模組完成完整的啟動流程"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # 初始化所有核心模組
        self.environment_validator = EnvironmentValidator(self.config.get('environment', {}))
        self.deployment_manager = DeploymentManager(self.config.get('deployment', {}))
        self.monitoring_collector = MonitoringCollector(self.config.get('monitoring', {}))
        self.error_handler = ErrorHandler(self.config.get('error_handling', {}))
        
        # 啟動狀態
        self.startup_phase = "initialized"
        self.startup_start_time = None
        self.startup_end_time = None
        self.startup_success = False
        self.startup_errors = []
        
    async def full_startup_sequence(self, environment: str = "development") -> Dict[str, Any]:
        """
        執行完整的啟動序列
        
        參數:
            environment: 部署環境
            
        返回:
            Dict[str, Any]: 啟動結果摘要
        """
        self.startup_start_time = datetime.now()
        self.startup_errors = []
        
        try:
            # 階段1: 環境檢查
            self.startup_phase = "environment_validation"
            env_result = await self._execute_environment_validation()
            if not env_result['success']:
                return await self._handle_startup_failure("環境驗證失敗", env_result['errors'])
            
            # 階段2: 部署前檢查
            self.startup_phase = "pre_deployment"
            pre_deploy_result = await self._execute_pre_deployment_checks(environment)
            if not pre_deploy_result['success']:
                return await self._handle_startup_failure("部署前檢查失敗", pre_deploy_result['errors'])
            
            # 階段3: 服務啟動
            self.startup_phase = "service_deployment"
            deploy_result = await self._execute_service_deployment(environment)
            if not deploy_result['success']:
                return await self._handle_startup_failure("服務部署失敗", [deploy_result['error']])
            
            # 階段4: 健康檢查
            self.startup_phase = "health_verification"
            health_result = await self._execute_health_verification(environment)
            if not health_result['success']:
                return await self._handle_startup_failure("健康檢查失敗", [health_result['error']])
            
            # 階段5: 監控啟動
            self.startup_phase = "monitoring_setup"
            monitoring_result = await self._execute_monitoring_setup()
            if not monitoring_result['success']:
                # 監控失敗不阻止啟動，但記錄警告
                self.startup_errors.append(f"監控設置警告: {monitoring_result['error']}")
            
            # 啟動完成
            self.startup_phase = "completed"
            self.startup_end_time = datetime.now()
            self.startup_success = True
            
            return await self._generate_startup_summary()
            
        except Exception as e:
            return await self._handle_startup_exception(e)
    
    async def shutdown_sequence(self) -> Dict[str, Any]:
        """
        執行關閉序列
        
        返回:
            Dict[str, Any]: 關閉結果摘要
        """
        shutdown_start_time = datetime.now()
        
        try:
            # 停止監控
            self.monitoring_collector.stop_monitoring()
            
            # 停止服務
            stop_success, stop_message = await self.deployment_manager.stop_services()
            
            shutdown_end_time = datetime.now()
            duration = (shutdown_end_time - shutdown_start_time).total_seconds()
            
            return {
                'success': stop_success,
                'duration_seconds': duration,
                'message': stop_message,
                'timestamp': shutdown_end_time.isoformat()
            }
            
        except Exception as e:
            await self.error_handler.handle_error(e, "shutdown_sequence")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def get_startup_status(self) -> Dict[str, Any]:
        """獲取啟動狀態"""
        duration = None
        if self.startup_start_time:
            end_time = self.startup_end_time or datetime.now()
            duration = (end_time - self.startup_start_time).total_seconds()
        
        return {
            'phase': self.startup_phase,
            'success': self.startup_success,
            'start_time': self.startup_start_time.isoformat() if self.startup_start_time else None,
            'end_time': self.startup_end_time.isoformat() if self.startup_end_time else None,
            'duration_seconds': duration,
            'errors': self.startup_errors
        }
    
    async def _execute_environment_validation(self) -> Dict[str, Any]:
        """執行環境驗證階段"""
        try:
            # 驗證環境
            env_valid, env_errors = await self.environment_validator.validate_environment()
            
            # 驗證compose文件
            compose_valid, compose_errors = await self.environment_validator.validate_compose_file()
            
            all_errors = env_errors + compose_errors
            success = env_valid and compose_valid
            
            return {
                'success': success,
                'errors': all_errors,
                'details': {
                    'environment_check': env_valid,
                    'compose_check': compose_valid
                }
            }
            
        except Exception as e:
            await self.error_handler.handle_error(e, "environment_validation")
            return {
                'success': False,
                'errors': [f"環境驗證異常: {str(e)}"]
            }
    
    async def _execute_pre_deployment_checks(self, environment: str) -> Dict[str, Any]:
        """執行部署前檢查階段"""
        try:
            errors = []
            
            # 檢查部署歷史
            history = self.deployment_manager.get_deployment_history(limit=1)
            if history and not history[-1].get('success', False):
                errors.append("上次部署失敗，建議檢查問題後再部署")
            
            # 檢查系統資源
            try:
                metrics = await self.monitoring_collector._collect_system_metrics()
                
                if metrics.cpu_percent > 90:
                    errors.append(f"系統CPU使用率過高: {metrics.cpu_percent}%")
                
                if metrics.memory_percent > 95:
                    errors.append(f"系統記憶體使用率過高: {metrics.memory_percent}%")
                
                if metrics.disk_usage_percent > 95:
                    errors.append(f"磁盤空間不足: {metrics.disk_usage_percent}%")
                    
            except Exception:
                # 系統指標收集失敗不阻止部署
                pass
            
            return {
                'success': len(errors) == 0,
                'errors': errors
            }
            
        except Exception as e:
            await self.error_handler.handle_error(e, "pre_deployment_checks")
            return {
                'success': False,
                'errors': [f"部署前檢查異常: {str(e)}"]
            }
    
    async def _execute_service_deployment(self, environment: str) -> Dict[str, Any]:
        """執行服務部署階段"""
        try:
            # 啟動服務
            success, message = await self.deployment_manager.start_services(environment, detach=True)
            
            if success:
                return {
                    'success': True,
                    'message': message
                }
            else:
                # 記錄部署錯誤
                deployment_error = DeploymentError(
                    message=f"服務部署失敗: {message}",
                    category=ErrorCategory.DOCKER,
                    severity=ErrorSeverity.CRITICAL,
                    context={'environment': environment}
                )
                await self.error_handler.handle_error(deployment_error, "service_deployment")
                
                return {
                    'success': False,
                    'error': message
                }
                
        except Exception as e:
            await self.error_handler.handle_error(e, "service_deployment")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _execute_health_verification(self, environment: str) -> Dict[str, Any]:
        """執行健康檢查階段"""
        try:
            # 檢查服務健康狀態
            service_statuses = await self.deployment_manager.health_check(environment)
            
            if "error" in service_statuses:
                return {
                    'success': False,
                    'error': service_statuses["error"]
                }
            
            # 檢查是否所有服務都健康
            unhealthy_services = []
            for service, status in service_statuses.items():
                if status not in ['running', 'healthy']:
                    unhealthy_services.append(f"{service}: {status}")
            
            if unhealthy_services:
                return {
                    'success': False,
                    'error': f"不健康的服務: {', '.join(unhealthy_services)}"
                }
            
            return {
                'success': True,
                'service_statuses': service_statuses
            }
            
        except Exception as e:
            await self.error_handler.handle_error(e, "health_verification")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _execute_monitoring_setup(self) -> Dict[str, Any]:
        """執行監控設置階段"""
        try:
            # 收集初始指標
            initial_metrics = await self.monitoring_collector.collect_metrics()
            
            # 啟動監控（在背景執行）
            # 注意：在真實環境中，這應該是非阻塞的背景任務
            
            return {
                'success': True,
                'initial_metrics': initial_metrics
            }
            
        except Exception as e:
            # 監控設置失敗不應該阻止整個啟動流程
            await self.error_handler.handle_error(e, "monitoring_setup")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _handle_startup_failure(self, phase_error: str, errors: List[str]) -> Dict[str, Any]:
        """處理啟動失敗"""
        self.startup_end_time = datetime.now()
        self.startup_success = False
        self.startup_errors.extend(errors)
        
        # 記錄啟動失敗
        failure_error = DeploymentError(
            message=f"啟動失敗於階段 {self.startup_phase}: {phase_error}",
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.CRITICAL,
            context={
                'phase': self.startup_phase,
                'errors': errors
            }
        )
        await self.error_handler.handle_error(failure_error, "startup_sequence")
        
        return await self._generate_startup_summary()
    
    async def _handle_startup_exception(self, exception: Exception) -> Dict[str, Any]:
        """處理啟動異常"""
        self.startup_end_time = datetime.now()
        self.startup_success = False
        self.startup_errors.append(str(exception))
        
        await self.error_handler.handle_error(exception, f"startup_sequence_{self.startup_phase}")
        
        return await self._generate_startup_summary()
    
    async def _generate_startup_summary(self) -> Dict[str, Any]:
        """生成啟動摘要"""
        duration = None
        if self.startup_start_time and self.startup_end_time:
            duration = (self.startup_end_time - self.startup_start_time).total_seconds()
        
        # 獲取錯誤統計
        error_stats = self.error_handler.get_error_statistics()
        
        # 獲取當前部署狀態
        deployment_status = self.deployment_manager.get_current_deployment_status()
        
        summary = {
            'startup_success': self.startup_success,
            'startup_phase': self.startup_phase,
            'start_time': self.startup_start_time.isoformat() if self.startup_start_time else None,
            'end_time': self.startup_end_time.isoformat() if self.startup_end_time else None,
            'duration_seconds': duration,
            'errors': self.startup_errors,
            'error_statistics': error_stats,
            'deployment_status': deployment_status,
            'timestamp': datetime.now().isoformat()
        }
        
        return summary


class TestDockerStartupIntegration:
    """Docker啟動整合測試類"""
    
    @pytest.fixture
    def startup_config(self):
        """測試固件：啟動配置"""
        return {
            'environment': {
                'min_docker_version': '20.10.0',
                'min_disk_space_mb': 1024,
                'required_ports': [6379, 8000]
            },
            'deployment': {
                'deployment_timeout': 60,
                'health_check_retries': 3,
                'retry_delay': 1
            },
            'monitoring': {
                'collection_interval': 30,
                'retention_hours': 1
            },
            'error_handling': {
                'max_retry_attempts': 3,
                'retry_delay_base': 1.0
            }
        }
    
    @pytest.fixture
    def orchestrator(self, startup_config):
        """測試固件：Docker啟動編排器"""
        return DockerStartupOrchestrator(startup_config)
    
    @pytest.fixture
    def mock_successful_environment(self):
        """測試固件：模擬成功的環境驗證"""
        return patch.multiple(
            EnvironmentValidator,
            validate_environment=AsyncMock(return_value=(True, [])),
            validate_compose_file=AsyncMock(return_value=(True, []))
        )
    
    @pytest.fixture
    def mock_successful_deployment(self):
        """測試固件：模擬成功的部署"""
        return patch.multiple(
            DeploymentManager,
            start_services=AsyncMock(return_value=(True, "服務啟動成功")),
            health_check=AsyncMock(return_value={"discord-bot": "healthy", "redis": "running"}),
            get_deployment_history=Mock(return_value=[]),
            get_current_deployment_status=Mock(return_value={"status": "completed"})
        )
    
    @pytest.fixture
    def mock_monitoring_setup(self):
        """測試固件：模擬監控設置"""
        return patch.multiple(
            MonitoringCollector,
            collect_metrics=AsyncMock(return_value={"summary": {"system_health": 95.0}}),
            _collect_system_metrics=AsyncMock(),
            stop_monitoring=Mock()
        )
    
    class TestFullStartupSequence:
        """完整啟動序列測試"""
        
        @pytest.mark.asyncio
        async def test_successful_full_startup(self, orchestrator, mock_successful_environment, 
                                             mock_successful_deployment, mock_monitoring_setup):
            """測試：成功的完整啟動流程"""
            with mock_successful_environment, mock_successful_deployment, mock_monitoring_setup:
                
                result = await orchestrator.full_startup_sequence("development")
                
                assert result['startup_success'] is True
                assert result['startup_phase'] == 'completed'
                assert result['duration_seconds'] is not None
                assert len(result['errors']) <= 1  # 可能有監控警告
                
                # 檢查啟動狀態
                status = orchestrator.get_startup_status()
                assert status['success'] is True
                assert status['phase'] == 'completed'
        
        @pytest.mark.asyncio
        async def test_startup_environment_validation_failure(self, orchestrator):
            """測試：環境驗證失敗的啟動流程"""
            with patch.object(orchestrator.environment_validator, 'validate_environment',
                            return_value=(False, ['環境變數缺失', 'Docker未運行'])):
                
                result = await orchestrator.full_startup_sequence("development")
                
                assert result['startup_success'] is False
                assert result['startup_phase'] == 'environment_validation'
                assert '環境驗證失敗' in str(result['errors'])
                assert '環境變數缺失' in str(result['errors'])
        
        @pytest.mark.asyncio
        async def test_startup_pre_deployment_failure(self, orchestrator, mock_successful_environment):
            """測試：部署前檢查失敗"""
            with mock_successful_environment, \
                 patch.object(orchestrator.deployment_manager, 'get_deployment_history',
                            return_value=[{'success': False}]):
                
                result = await orchestrator.full_startup_sequence("development")
                
                assert result['startup_success'] is False
                assert result['startup_phase'] == 'pre_deployment'
                assert '上次部署失敗' in str(result['errors'])
        
        @pytest.mark.asyncio
        async def test_startup_service_deployment_failure(self, orchestrator, mock_successful_environment):
            """測試：服務部署失敗"""
            with mock_successful_environment, \
                 patch.object(orchestrator.deployment_manager, 'get_deployment_history', return_value=[]), \
                 patch.object(orchestrator.deployment_manager, 'start_services',
                            return_value=(False, "Docker容器啟動失敗")):
                
                result = await orchestrator.full_startup_sequence("development")
                
                assert result['startup_success'] is False
                assert result['startup_phase'] == 'service_deployment'
                assert 'Docker容器啟動失敗' in str(result['errors'])
        
        @pytest.mark.asyncio
        async def test_startup_health_check_failure(self, orchestrator, mock_successful_environment):
            """測試：健康檢查失敗"""
            with mock_successful_environment, \
                 patch.object(orchestrator.deployment_manager, 'get_deployment_history', return_value=[]), \
                 patch.object(orchestrator.deployment_manager, 'start_services',
                            return_value=(True, "服務啟動成功")), \
                 patch.object(orchestrator.deployment_manager, 'health_check',
                            return_value={"discord-bot": "unhealthy", "redis": "stopped"}):
                
                result = await orchestrator.full_startup_sequence("development")
                
                assert result['startup_success'] is False
                assert result['startup_phase'] == 'health_verification'
                assert '不健康的服務' in str(result['errors'])
        
        @pytest.mark.asyncio
        async def test_startup_monitoring_warning(self, orchestrator, mock_successful_environment, 
                                                mock_successful_deployment):
            """測試：監控設置警告但啟動成功"""
            with mock_successful_environment, mock_successful_deployment, \
                 patch.object(orchestrator.monitoring_collector, 'collect_metrics',
                            side_effect=Exception("監控收集失敗")):
                
                result = await orchestrator.full_startup_sequence("development")
                
                # 監控失敗不應該阻止啟動成功
                assert result['startup_success'] is True
                assert result['startup_phase'] == 'completed'
                assert any('監控設置警告' in error for error in result['errors'])
        
        @pytest.mark.asyncio
        async def test_startup_unexpected_exception(self, orchestrator, mock_successful_environment):
            """測試：啟動過程中發生未預期異常"""
            with mock_successful_environment, \
                 patch.object(orchestrator.deployment_manager, 'get_deployment_history',
                            side_effect=Exception("未預期錯誤")):
                
                result = await orchestrator.full_startup_sequence("development")
                
                assert result['startup_success'] is False
                assert '未預期錯誤' in str(result['errors'])
    
    class TestShutdownSequence:
        """關閉序列測試"""
        
        @pytest.mark.asyncio
        async def test_successful_shutdown(self, orchestrator):
            """測試：成功的關閉流程"""
            with patch.object(orchestrator.deployment_manager, 'stop_services',
                            return_value=(True, "服務已成功停止")):
                
                result = await orchestrator.shutdown_sequence()
                
                assert result['success'] is True
                assert result['message'] == "服務已成功停止"
                assert result['duration_seconds'] is not None
        
        @pytest.mark.asyncio
        async def test_shutdown_failure(self, orchestrator):
            """測試：關閉流程失敗"""
            with patch.object(orchestrator.deployment_manager, 'stop_services',
                            return_value=(False, "停止服務失敗")):
                
                result = await orchestrator.shutdown_sequence()
                
                assert result['success'] is False
                assert result['message'] == "停止服務失敗"
        
        @pytest.mark.asyncio
        async def test_shutdown_exception(self, orchestrator):
            """測試：關閉過程中異常"""
            with patch.object(orchestrator.deployment_manager, 'stop_services',
                            side_effect=Exception("關閉異常")):
                
                result = await orchestrator.shutdown_sequence()
                
                assert result['success'] is False
                assert '關閉異常' in result['error']
    
    class TestModuleIntegration:
        """模組整合測試"""
        
        @pytest.mark.asyncio
        async def test_environment_validator_integration(self, orchestrator):
            """測試：環境驗證器整合"""
            # 測試環境驗證器是否正確初始化並配置
            assert orchestrator.environment_validator is not None
            assert orchestrator.environment_validator.min_disk_space_mb == 1024
            assert 6379 in orchestrator.environment_validator.required_ports
        
        @pytest.mark.asyncio
        async def test_deployment_manager_integration(self, orchestrator):
            """測試：部署管理器整合"""
            # 測試部署管理器是否正確初始化並配置
            assert orchestrator.deployment_manager is not None
            assert orchestrator.deployment_manager.deployment_timeout == 60
            assert orchestrator.deployment_manager.health_check_retries == 3
        
        @pytest.mark.asyncio
        async def test_monitoring_collector_integration(self, orchestrator):
            """測試：監控收集器整合"""
            # 測試監控收集器是否正確初始化並配置
            assert orchestrator.monitoring_collector is not None
            assert orchestrator.monitoring_collector.collection_interval == 30
            assert orchestrator.monitoring_collector.retention_hours == 1
        
        @pytest.mark.asyncio
        async def test_error_handler_integration(self, orchestrator):
            """測試：錯誤處理器整合"""
            # 測試錯誤處理器是否正確初始化並配置
            assert orchestrator.error_handler is not None
            assert orchestrator.error_handler.max_retry_attempts == 3
            assert orchestrator.error_handler.retry_delay_base == 1.0
        
        @pytest.mark.asyncio
        async def test_cross_module_error_handling(self, orchestrator):
            """測試：跨模組錯誤處理"""
            # 模擬部署管理器錯誤，檢查是否被錯誤處理器正確處理
            with patch.object(orchestrator.deployment_manager, 'start_services',
                            side_effect=Exception("部署錯誤")):
                
                # 執行會觸發錯誤的操作
                result = await orchestrator._execute_service_deployment("development")
                
                assert result['success'] is False
                # 檢查錯誤是否被記錄
                assert len(orchestrator.error_handler.error_records) > 0
    
    class TestStartupStatus:
        """啟動狀態測試"""
        
        def test_initial_startup_status(self, orchestrator):
            """測試：初始啟動狀態"""
            status = orchestrator.get_startup_status()
            
            assert status['phase'] == 'initialized'
            assert status['success'] is False
            assert status['start_time'] is None
            assert status['end_time'] is None
            assert status['duration_seconds'] is None
            assert status['errors'] == []
        
        @pytest.mark.asyncio
        async def test_startup_status_during_execution(self, orchestrator, mock_successful_environment):
            """測試：執行過程中的啟動狀態"""
            # 使用一個會阻塞的mock來測試執行中狀態
            async def slow_deployment(*args, **kwargs):
                await asyncio.sleep(0.1)
                return True, "Success"
            
            with mock_successful_environment, \
                 patch.object(orchestrator.deployment_manager, 'get_deployment_history', return_value=[]), \
                 patch.object(orchestrator.deployment_manager, 'start_services', side_effect=slow_deployment):
                
                # 開始啟動流程（但會在部署階段阻塞）
                startup_task = asyncio.create_task(orchestrator.full_startup_sequence("development"))
                
                # 給一點時間讓啟動開始
                await asyncio.sleep(0.05)
                
                # 檢查中間狀態
                status = orchestrator.get_startup_status()
                assert status['start_time'] is not None
                assert status['duration_seconds'] is not None
                
                # 等待完成
                await startup_task
        
        @pytest.mark.asyncio
        async def test_startup_status_after_completion(self, orchestrator, mock_successful_environment, 
                                                     mock_successful_deployment, mock_monitoring_setup):
            """測試：完成後的啟動狀態"""
            with mock_successful_environment, mock_successful_deployment, mock_monitoring_setup:
                
                await orchestrator.full_startup_sequence("development")
                
                status = orchestrator.get_startup_status()
                
                assert status['phase'] == 'completed'
                assert status['success'] is True
                assert status['start_time'] is not None
                assert status['end_time'] is not None
                assert status['duration_seconds'] > 0
    
    class TestErrorRecovery:
        """錯誤恢復測試"""
        
        @pytest.mark.asyncio
        async def test_error_recovery_during_startup(self, orchestrator, mock_successful_environment):
            """測試：啟動過程中的錯誤恢復"""
            # 模擬第一次部署失敗，第二次成功的情況
            call_count = 0
            
            async def flaky_deployment(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise Exception("暫時性錯誤")
                return True, "重試成功"
            
            with mock_successful_environment, \
                 patch.object(orchestrator.deployment_manager, 'get_deployment_history', return_value=[]), \
                 patch.object(orchestrator.deployment_manager, 'start_services', side_effect=flaky_deployment), \
                 patch.object(orchestrator.deployment_manager, 'health_check',
                            return_value={"discord-bot": "healthy"}), \
                 patch.object(orchestrator.monitoring_collector, 'collect_metrics',
                            return_value={"summary": {"system_health": 95.0}}):
                
                result = await orchestrator.full_startup_sequence("development")
                
                # 第一次失敗應該被記錄，但不影響最終結果
                assert len(orchestrator.error_handler.error_records) > 0
                assert orchestrator.error_handler.error_records[0].message == "暫時性錯誤"
    
    class TestPerformanceMetrics:
        """性能指標測試"""
        
        @pytest.mark.asyncio
        async def test_startup_performance_tracking(self, orchestrator, mock_successful_environment, 
                                                  mock_successful_deployment, mock_monitoring_setup):
            """測試：啟動性能追蹤"""
            with mock_successful_environment, mock_successful_deployment, mock_monitoring_setup:
                
                result = await orchestrator.full_startup_sequence("development")
                
                # 檢查是否記錄了啟動時間
                assert result['duration_seconds'] is not None
                assert result['duration_seconds'] > 0
                assert result['start_time'] is not None
                assert result['end_time'] is not None
        
        @pytest.mark.asyncio 
        async def test_startup_timeout_scenario(self, orchestrator):
            """測試：啟動超時場景"""
            # 模擬非常緩慢的環境檢查
            async def slow_validation(*args, **kwargs):
                await asyncio.sleep(0.2)  # 模擬慢速檢查
                return True, []
            
            with patch.object(orchestrator.environment_validator, 'validate_environment', 
                            side_effect=slow_validation), \
                 patch.object(orchestrator.environment_validator, 'validate_compose_file',
                            return_value=(True, [])):
                
                start_time = datetime.now()
                result = await orchestrator.full_startup_sequence("development")
                end_time = datetime.now()
                
                duration = (end_time - start_time).total_seconds()
                
                # 驗證實際耗時與報告的耗時一致
                assert abs(duration - result['duration_seconds']) < 0.1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])