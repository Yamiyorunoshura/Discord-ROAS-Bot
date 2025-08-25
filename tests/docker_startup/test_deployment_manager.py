"""
部署管理器單元測試套件
Task ID: 1 - ROAS Bot v2.4.3 Docker啟動系統修復

測試目標：F-1 Docker啟動腳本修復和F-3 部署腳本重構優化
- 統一管理Docker服務的啟動、停止和狀態檢查
- 部署腳本具備完整的錯誤處理機制
- 實作詳細的結構化日誌記錄
- 支援自動重試和超時處理

基於知識庫最佳實踐BP-002: 併發資料庫優化模式中的重試策略
"""

import asyncio
import os
import tempfile
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from unittest.mock import Mock, patch, AsyncMock, MagicMock, call
import pytest
import subprocess
from enum import Enum


class ServiceStatus(Enum):
    """服務狀態枚舉"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    ERROR = "error"


class DeploymentManager:
    """部署管理器 - 統一管理Docker服務的啟動、停止和狀態檢查"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.project_root = self.config.get('project_root', os.getcwd())
        self.deployment_timeout = self.config.get('deployment_timeout', 300)  # 5分鐘
        self.health_check_timeout = self.config.get('health_check_timeout', 60)  # 1分鐘
        self.health_check_retries = self.config.get('health_check_retries', 5)
        self.retry_delay = self.config.get('retry_delay', 10)  # 秒
        
        # 支援的環境
        self.supported_environments = ['development', 'staging', 'production']
        
        # 記錄部署狀態
        self.deployment_history = []
        self.current_deployment = None
    
    async def start_services(self, environment: str = "development", detach: bool = False) -> Tuple[bool, str]:
        """
        啟動Docker服務
        
        參數:
            environment: 部署環境 (development, staging, production)
            detach: 是否在背景執行
            
        返回:
            Tuple[bool, str]: (是否成功, 錯誤訊息或成功訊息)
        """
        deployment_id = f"deploy_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        start_time = datetime.now()
        
        try:
            # 驗證環境
            if environment not in self.supported_environments:
                return False, f"不支援的環境: {environment}"
            
            # 選擇對應的compose文件
            compose_file = self._get_compose_file(environment)
            if not compose_file:
                return False, f"找不到環境 {environment} 的compose文件"
            
            # 記錄部署開始
            self.current_deployment = {
                'id': deployment_id,
                'environment': environment,
                'start_time': start_time,
                'status': 'starting',
                'compose_file': compose_file
            }
            
            # 執行部署步驟
            success = await self._execute_deployment_steps(compose_file, detach)
            
            if success:
                # 等待服務啟動並進行健康檢查
                health_success, health_message = await self._wait_for_services_healthy(compose_file)
                
                if health_success:
                    end_time = datetime.now()
                    duration = (end_time - start_time).total_seconds()
                    
                    # 更新部署狀態
                    self.current_deployment.update({
                        'status': 'completed',
                        'end_time': end_time,
                        'duration_seconds': duration,
                        'success': True
                    })
                    
                    return True, f"服務啟動成功，耗時 {duration:.2f} 秒"
                else:
                    self.current_deployment.update({
                        'status': 'failed',
                        'end_time': datetime.now(),
                        'error': health_message,
                        'success': False
                    })
                    return False, f"服務啟動失敗：{health_message}"
            else:
                self.current_deployment.update({
                    'status': 'failed',
                    'end_time': datetime.now(),
                    'error': '部署步驟執行失敗',
                    'success': False
                })
                return False, "部署步驟執行失敗"
                
        except Exception as e:
            if self.current_deployment:
                self.current_deployment.update({
                    'status': 'error',
                    'end_time': datetime.now(),
                    'error': str(e),
                    'success': False
                })
            return False, f"啟動服務時發生錯誤: {str(e)}"
        
        finally:
            # 記錄到歷史
            if self.current_deployment:
                self.deployment_history.append(self.current_deployment.copy())
    
    async def stop_services(self, environment: str = "development") -> Tuple[bool, str]:
        """
        停止Docker服務
        
        參數:
            environment: 部署環境
            
        返回:
            Tuple[bool, str]: (是否成功, 錯誤訊息或成功訊息)
        """
        try:
            compose_file = self._get_compose_file(environment)
            if not compose_file:
                return False, f"找不到環境 {environment} 的compose文件"
            
            # 執行停止命令
            cmd = ['docker-compose', '-f', compose_file, 'down']
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.project_root
            )
            
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                return True, "服務已成功停止"
            else:
                return False, f"停止服務失敗: {stderr.decode()}"
                
        except Exception as e:
            return False, f"停止服務時發生錯誤: {str(e)}"
    
    async def health_check(self, environment: str = "development") -> Dict[str, str]:
        """
        執行服務健康檢查
        
        參數:
            environment: 部署環境
            
        返回:
            Dict[str, str]: 服務名稱到狀態的映射
        """
        try:
            compose_file = self._get_compose_file(environment)
            if not compose_file:
                return {"error": f"找不到環境 {environment} 的compose文件"}
            
            # 獲取服務狀態
            cmd = ['docker-compose', '-f', compose_file, 'ps', '--format', 'json']
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.project_root
            )
            
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                return {"error": f"獲取服務狀態失敗: {stderr.decode()}"}
            
            # 解析服務狀態
            services_status = {}
            
            try:
                # Docker Compose v2 格式
                output_lines = stdout.decode().strip().split('\n')
                for line in output_lines:
                    if line:
                        service_info = json.loads(line)
                        service_name = service_info.get('Service', service_info.get('Name', 'unknown'))
                        state = service_info.get('State', service_info.get('Status', 'unknown'))
                        
                        # 統一狀態格式
                        if 'Up' in state:
                            if 'healthy' in state.lower():
                                services_status[service_name] = ServiceStatus.HEALTHY.value
                            else:
                                services_status[service_name] = ServiceStatus.RUNNING.value
                        else:
                            services_status[service_name] = ServiceStatus.STOPPED.value
                            
            except (json.JSONDecodeError, KeyError) as e:
                # 備用解析方式
                services_status = await self._parse_ps_output_fallback(stdout.decode())
            
            return services_status
            
        except Exception as e:
            return {"error": f"健康檢查時發生錯誤: {str(e)}"}
    
    async def restart_services(self, environment: str = "development") -> Tuple[bool, str]:
        """
        重啟Docker服務
        
        參數:
            environment: 部署環境
            
        返回:
            Tuple[bool, str]: (是否成功, 錯誤訊息或成功訊息)
        """
        try:
            # 先停止服務
            stop_success, stop_message = await self.stop_services(environment)
            if not stop_success:
                return False, f"重啟失敗：停止服務時出錯 - {stop_message}"
            
            # 等待一小段時間確保服務完全停止
            await asyncio.sleep(2)
            
            # 重新啟動服務
            start_success, start_message = await self.start_services(environment, detach=True)
            if not start_success:
                return False, f"重啟失敗：啟動服務時出錯 - {start_message}"
            
            return True, "服務重啟成功"
            
        except Exception as e:
            return False, f"重啟服務時發生錯誤: {str(e)}"
    
    async def get_logs(self, environment: str = "development", service: str = None, lines: int = 100) -> Tuple[bool, str]:
        """
        獲取服務日誌
        
        參數:
            environment: 部署環境
            service: 特定服務名稱（可選）
            lines: 日誌行數
            
        返回:
            Tuple[bool, str]: (是否成功, 日誌內容或錯誤訊息)
        """
        try:
            compose_file = self._get_compose_file(environment)
            if not compose_file:
                return False, f"找不到環境 {environment} 的compose文件"
            
            # 構建命令
            cmd = ['docker-compose', '-f', compose_file, 'logs', '--tail', str(lines)]
            if service:
                cmd.append(service)
            
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.project_root
            )
            
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                return True, stdout.decode()
            else:
                return False, f"獲取日誌失敗: {stderr.decode()}"
                
        except Exception as e:
            return False, f"獲取日誌時發生錯誤: {str(e)}"
    
    def get_deployment_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        獲取部署歷史記錄
        
        參數:
            limit: 返回記錄數限制
            
        返回:
            部署歷史記錄列表
        """
        return self.deployment_history[-limit:]
    
    def get_current_deployment_status(self) -> Optional[Dict[str, Any]]:
        """
        獲取當前部署狀態
        
        返回:
            當前部署狀態信息
        """
        return self.current_deployment
    
    def _get_compose_file(self, environment: str) -> Optional[str]:
        """根據環境獲取對應的compose文件"""
        compose_files = {
            'development': 'docker-compose.dev.yml',
            'staging': 'docker-compose.staging.yml', 
            'production': 'docker-compose.prod.yml'
        }
        
        compose_file = compose_files.get(environment)
        if compose_file and Path(self.project_root) / compose_file:
            return compose_file
        return None
    
    async def _execute_deployment_steps(self, compose_file: str, detach: bool) -> bool:
        """執行部署步驟"""
        try:
            # 步驟1: 拉取最新映像
            pull_cmd = ['docker-compose', '-f', compose_file, 'pull']
            result = await asyncio.create_subprocess_exec(
                *pull_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.project_root
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                # 拉取失敗不致命，可能是本地構建的映像
                pass
            
            # 步驟2: 構建映像
            build_cmd = ['docker-compose', '-f', compose_file, 'build']
            result = await asyncio.create_subprocess_exec(
                *build_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.project_root
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                return False
            
            # 步驟3: 啟動服務
            up_cmd = ['docker-compose', '-f', compose_file, 'up']
            if detach:
                up_cmd.append('-d')
            
            result = await asyncio.create_subprocess_exec(
                *up_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.project_root
            )
            stdout, stderr = await result.communicate()
            
            return result.returncode == 0
            
        except Exception:
            return False
    
    async def _wait_for_services_healthy(self, compose_file: str) -> Tuple[bool, str]:
        """等待服務變為健康狀態"""
        for attempt in range(self.health_check_retries):
            await asyncio.sleep(self.retry_delay)
            
            # 檢查服務狀態
            services_status = await self.health_check()
            
            if "error" in services_status:
                continue
            
            # 檢查所有服務是否健康
            unhealthy_services = []
            for service, status in services_status.items():
                if status not in [ServiceStatus.RUNNING.value, ServiceStatus.HEALTHY.value]:
                    unhealthy_services.append(f"{service}: {status}")
            
            if not unhealthy_services:
                return True, "所有服務已健康運行"
            
            if attempt == self.health_check_retries - 1:
                return False, f"健康檢查超時，不健康的服務: {', '.join(unhealthy_services)}"
        
        return False, "健康檢查超時"
    
    async def _parse_ps_output_fallback(self, output: str) -> Dict[str, str]:
        """備用的ps輸出解析方式"""
        services_status = {}
        lines = output.strip().split('\n')[1:]  # 跳過標題行
        
        for line in lines:
            if line.strip():
                # 簡單的解析邏輯
                parts = line.split()
                if len(parts) >= 2:
                    service_name = parts[0]
                    if 'Up' in line:
                        services_status[service_name] = ServiceStatus.RUNNING.value
                    else:
                        services_status[service_name] = ServiceStatus.STOPPED.value
        
        return services_status


class TestDeploymentManager:
    """部署管理器測試類"""
    
    @pytest.fixture
    def deployment_manager(self):
        """測試固件：創建部署管理器實例"""
        config = {
            'project_root': '/test/project',
            'deployment_timeout': 60,
            'health_check_timeout': 30,
            'health_check_retries': 3,
            'retry_delay': 5
        }
        return DeploymentManager(config)
    
    @pytest.fixture
    def mock_compose_files(self, deployment_manager):
        """測試固件：模擬compose文件存在"""
        with patch('pathlib.Path.exists', return_value=True):
            yield
    
    class TestServiceManagement:
        """服務管理測試"""
        
        @pytest.mark.asyncio
        async def test_start_services_success(self, deployment_manager, mock_compose_files):
            """測試：成功啟動服務"""
            with patch('asyncio.create_subprocess_exec') as mock_subprocess:
                # 模擬三個部署步驟都成功
                mock_proc = AsyncMock()
                mock_proc.communicate.return_value = (b'success', b'')
                mock_proc.returncode = 0
                mock_subprocess.return_value = mock_proc
                
                # 模擬健康檢查成功
                with patch.object(deployment_manager, '_wait_for_services_healthy', 
                                return_value=(True, "所有服務已健康運行")):
                    
                    success, message = await deployment_manager.start_services("development")
                    
                    assert success is True
                    assert "服務啟動成功" in message
                    assert deployment_manager.current_deployment is not None
                    assert deployment_manager.current_deployment['status'] == 'completed'
        
        @pytest.mark.asyncio
        async def test_start_services_unsupported_environment(self, deployment_manager):
            """測試：不支援的環境"""
            success, message = await deployment_manager.start_services("invalid_env")
            
            assert success is False
            assert "不支援的環境" in message
        
        @pytest.mark.asyncio
        async def test_start_services_missing_compose_file(self, deployment_manager):
            """測試：缺少compose文件"""
            with patch.object(deployment_manager, '_get_compose_file', return_value=None):
                success, message = await deployment_manager.start_services("development")
                
                assert success is False
                assert "找不到環境" in message
        
        @pytest.mark.asyncio
        async def test_start_services_deployment_steps_failure(self, deployment_manager, mock_compose_files):
            """測試：部署步驟執行失敗"""
            with patch.object(deployment_manager, '_execute_deployment_steps', return_value=False):
                success, message = await deployment_manager.start_services("development")
                
                assert success is False
                assert "部署步驟執行失敗" in message
                assert deployment_manager.current_deployment['status'] == 'failed'
        
        @pytest.mark.asyncio
        async def test_start_services_health_check_failure(self, deployment_manager, mock_compose_files):
            """測試：健康檢查失敗"""
            with patch.object(deployment_manager, '_execute_deployment_steps', return_value=True), \
                 patch.object(deployment_manager, '_wait_for_services_healthy', 
                             return_value=(False, "健康檢查超時")):
                
                success, message = await deployment_manager.start_services("development")
                
                assert success is False
                assert "服務啟動失敗" in message
                assert deployment_manager.current_deployment['status'] == 'failed'
        
        @pytest.mark.asyncio
        async def test_stop_services_success(self, deployment_manager, mock_compose_files):
            """測試：成功停止服務"""
            with patch('asyncio.create_subprocess_exec') as mock_subprocess:
                mock_proc = AsyncMock()
                mock_proc.communicate.return_value = (b'stopped', b'')
                mock_proc.returncode = 0
                mock_subprocess.return_value = mock_proc
                
                success, message = await deployment_manager.stop_services("development")
                
                assert success is True
                assert "服務已成功停止" in message
        
        @pytest.mark.asyncio
        async def test_stop_services_failure(self, deployment_manager, mock_compose_files):
            """測試：停止服務失敗"""
            with patch('asyncio.create_subprocess_exec') as mock_subprocess:
                mock_proc = AsyncMock()
                mock_proc.communicate.return_value = (b'', b'stop failed')
                mock_proc.returncode = 1
                mock_subprocess.return_value = mock_proc
                
                success, message = await deployment_manager.stop_services("development")
                
                assert success is False
                assert "停止服務失敗" in message
        
        @pytest.mark.asyncio
        async def test_restart_services_success(self, deployment_manager):
            """測試：成功重啟服務"""
            with patch.object(deployment_manager, 'stop_services', return_value=(True, "stopped")), \
                 patch.object(deployment_manager, 'start_services', return_value=(True, "started")), \
                 patch('asyncio.sleep'):
                
                success, message = await deployment_manager.restart_services("development")
                
                assert success is True
                assert "服務重啟成功" in message
        
        @pytest.mark.asyncio
        async def test_restart_services_stop_failure(self, deployment_manager):
            """測試：重啟時停止服務失敗"""
            with patch.object(deployment_manager, 'stop_services', return_value=(False, "stop failed")):
                
                success, message = await deployment_manager.restart_services("development")
                
                assert success is False
                assert "停止服務時出錯" in message
        
        @pytest.mark.asyncio
        async def test_restart_services_start_failure(self, deployment_manager):
            """測試：重啟時啟動服務失敗"""
            with patch.object(deployment_manager, 'stop_services', return_value=(True, "stopped")), \
                 patch.object(deployment_manager, 'start_services', return_value=(False, "start failed")), \
                 patch('asyncio.sleep'):
                
                success, message = await deployment_manager.restart_services("development")
                
                assert success is False
                assert "啟動服務時出錯" in message
    
    class TestHealthCheck:
        """健康檢查測試"""
        
        @pytest.mark.asyncio
        async def test_health_check_success(self, deployment_manager, mock_compose_files):
            """測試：健康檢查成功"""
            mock_output = json.dumps({
                "Service": "discord-bot",
                "State": "Up (healthy)"
            }) + "\n" + json.dumps({
                "Service": "redis", 
                "State": "Up"
            })
            
            with patch('asyncio.create_subprocess_exec') as mock_subprocess:
                mock_proc = AsyncMock()
                mock_proc.communicate.return_value = (mock_output.encode(), b'')
                mock_proc.returncode = 0
                mock_subprocess.return_value = mock_proc
                
                status = await deployment_manager.health_check("development")
                
                assert "error" not in status
                assert status["discord-bot"] == ServiceStatus.HEALTHY.value
                assert status["redis"] == ServiceStatus.RUNNING.value
        
        @pytest.mark.asyncio
        async def test_health_check_command_failure(self, deployment_manager, mock_compose_files):
            """測試：健康檢查命令執行失敗"""
            with patch('asyncio.create_subprocess_exec') as mock_subprocess:
                mock_proc = AsyncMock()
                mock_proc.communicate.return_value = (b'', b'command failed')
                mock_proc.returncode = 1
                mock_subprocess.return_value = mock_proc
                
                status = await deployment_manager.health_check("development")
                
                assert "error" in status
                assert "獲取服務狀態失敗" in status["error"]
        
        @pytest.mark.asyncio
        async def test_health_check_json_parse_error(self, deployment_manager, mock_compose_files):
            """測試：JSON解析錯誤時使用備用解析"""
            mock_output = "invalid json output"
            
            with patch('asyncio.create_subprocess_exec') as mock_subprocess:
                mock_proc = AsyncMock()
                mock_proc.communicate.return_value = (mock_output.encode(), b'')
                mock_proc.returncode = 0
                mock_subprocess.return_value = mock_proc
                
                with patch.object(deployment_manager, '_parse_ps_output_fallback', 
                                return_value={"service": "running"}) as mock_fallback:
                    
                    status = await deployment_manager.health_check("development")
                    
                    mock_fallback.assert_called_once_with(mock_output)
                    assert status == {"service": "running"}
        
        @pytest.mark.asyncio
        async def test_wait_for_services_healthy_success(self, deployment_manager):
            """測試：等待服務健康成功"""
            with patch.object(deployment_manager, 'health_check', 
                            return_value={"service": ServiceStatus.HEALTHY.value}), \
                 patch('asyncio.sleep'):
                
                success, message = await deployment_manager._wait_for_services_healthy("test.yml")
                
                assert success is True
                assert "所有服務已健康運行" in message
        
        @pytest.mark.asyncio
        async def test_wait_for_services_healthy_timeout(self, deployment_manager):
            """測試：等待服務健康超時"""
            with patch.object(deployment_manager, 'health_check', 
                            return_value={"service": ServiceStatus.STOPPED.value}), \
                 patch('asyncio.sleep'):
                
                success, message = await deployment_manager._wait_for_services_healthy("test.yml")
                
                assert success is False
                assert "健康檢查超時" in message
        
        @pytest.mark.asyncio
        async def test_wait_for_services_healthy_partial_failure(self, deployment_manager):
            """測試：部分服務不健康"""
            with patch.object(deployment_manager, 'health_check', 
                            return_value={
                                "service1": ServiceStatus.HEALTHY.value,
                                "service2": ServiceStatus.ERROR.value
                            }), \
                 patch('asyncio.sleep'):
                
                success, message = await deployment_manager._wait_for_services_healthy("test.yml")
                
                assert success is False
                assert "不健康的服務" in message
                assert "service2: error" in message
    
    class TestLogsRetrieval:
        """日誌獲取測試"""
        
        @pytest.mark.asyncio
        async def test_get_logs_all_services(self, deployment_manager, mock_compose_files):
            """測試：獲取所有服務日誌"""
            mock_logs = "2023-01-01 10:00:00 [INFO] Service started\n"
            
            with patch('asyncio.create_subprocess_exec') as mock_subprocess:
                mock_proc = AsyncMock()
                mock_proc.communicate.return_value = (mock_logs.encode(), b'')
                mock_proc.returncode = 0
                mock_subprocess.return_value = mock_proc
                
                success, logs = await deployment_manager.get_logs("development")
                
                assert success is True
                assert logs == mock_logs
                
                # 驗證命令參數
                call_args = mock_subprocess.call_args[0][0]
                assert 'logs' in call_args
                assert '--tail' in call_args
                assert '100' in call_args
        
        @pytest.mark.asyncio
        async def test_get_logs_specific_service(self, deployment_manager, mock_compose_files):
            """測試：獲取特定服務日誌"""
            with patch('asyncio.create_subprocess_exec') as mock_subprocess:
                mock_proc = AsyncMock()
                mock_proc.communicate.return_value = (b'service logs', b'')
                mock_proc.returncode = 0
                mock_subprocess.return_value = mock_proc
                
                success, logs = await deployment_manager.get_logs("development", service="discord-bot", lines=50)
                
                assert success is True
                
                # 驗證命令參數包含服務名稱
                call_args = mock_subprocess.call_args[0][0]
                assert 'discord-bot' in call_args
                assert '50' in call_args
        
        @pytest.mark.asyncio
        async def test_get_logs_command_failure(self, deployment_manager, mock_compose_files):
            """測試：獲取日誌命令失敗"""
            with patch('asyncio.create_subprocess_exec') as mock_subprocess:
                mock_proc = AsyncMock()
                mock_proc.communicate.return_value = (b'', b'logs failed')
                mock_proc.returncode = 1
                mock_subprocess.return_value = mock_proc
                
                success, logs = await deployment_manager.get_logs("development")
                
                assert success is False
                assert "獲取日誌失敗" in logs
    
    class TestDeploymentHistory:
        """部署歷史測試"""
        
        def test_get_deployment_history_empty(self, deployment_manager):
            """測試：空部署歷史"""
            history = deployment_manager.get_deployment_history()
            assert len(history) == 0
        
        def test_get_deployment_history_with_records(self, deployment_manager):
            """測試：有部署記錄的歷史"""
            # 添加測試記錄
            test_records = [
                {'id': 'deploy_1', 'status': 'completed'},
                {'id': 'deploy_2', 'status': 'failed'},
                {'id': 'deploy_3', 'status': 'completed'}
            ]
            deployment_manager.deployment_history = test_records
            
            history = deployment_manager.get_deployment_history(limit=2)
            assert len(history) == 2
            assert history[0]['id'] == 'deploy_2'  # 最近的兩個
            assert history[1]['id'] == 'deploy_3'
        
        def test_get_current_deployment_status_none(self, deployment_manager):
            """測試：無當前部署"""
            status = deployment_manager.get_current_deployment_status()
            assert status is None
        
        def test_get_current_deployment_status_exists(self, deployment_manager):
            """測試：存在當前部署"""
            test_deployment = {'id': 'current_deploy', 'status': 'starting'}
            deployment_manager.current_deployment = test_deployment
            
            status = deployment_manager.get_current_deployment_status()
            assert status == test_deployment
    
    class TestUtilityMethods:
        """工具方法測試"""
        
        def test_get_compose_file_development(self, deployment_manager):
            """測試：獲取開發環境compose文件"""
            with patch('pathlib.Path.exists', return_value=True):
                compose_file = deployment_manager._get_compose_file('development')
                assert compose_file == 'docker-compose.dev.yml'
        
        def test_get_compose_file_production(self, deployment_manager):
            """測試：獲取生產環境compose文件"""
            with patch('pathlib.Path.exists', return_value=True):
                compose_file = deployment_manager._get_compose_file('production')
                assert compose_file == 'docker-compose.prod.yml'
        
        def test_get_compose_file_not_exists(self, deployment_manager):
            """測試：compose文件不存在"""
            with patch('pathlib.Path.exists', return_value=False):
                compose_file = deployment_manager._get_compose_file('development')
                assert compose_file is None
        
        def test_get_compose_file_unsupported_environment(self, deployment_manager):
            """測試：不支援的環境"""
            compose_file = deployment_manager._get_compose_file('unsupported')
            assert compose_file is None
        
        @pytest.mark.asyncio
        async def test_execute_deployment_steps_success(self, deployment_manager):
            """測試：部署步驟執行成功"""
            with patch('asyncio.create_subprocess_exec') as mock_subprocess:
                mock_proc = AsyncMock()
                mock_proc.communicate.return_value = (b'success', b'')
                mock_proc.returncode = 0
                mock_subprocess.return_value = mock_proc
                
                success = await deployment_manager._execute_deployment_steps("test.yml", True)
                
                assert success is True
                # 應該調用三次：pull, build, up
                assert mock_subprocess.call_count == 3
        
        @pytest.mark.asyncio
        async def test_execute_deployment_steps_build_failure(self, deployment_manager):
            """測試：構建步驟失敗"""
            with patch('asyncio.create_subprocess_exec') as mock_subprocess:
                # pull成功，build失敗
                pull_proc = AsyncMock()
                pull_proc.communicate.return_value = (b'pulled', b'')
                pull_proc.returncode = 0
                
                build_proc = AsyncMock()
                build_proc.communicate.return_value = (b'', b'build failed')
                build_proc.returncode = 1
                
                mock_subprocess.side_effect = [pull_proc, build_proc]
                
                success = await deployment_manager._execute_deployment_steps("test.yml", False)
                
                assert success is False
        
        @pytest.mark.asyncio
        async def test_parse_ps_output_fallback(self, deployment_manager):
            """測試：備用ps輸出解析"""
            mock_output = """NAME          STATE
            service1      Up 2 hours
            service2      Exit 1"""
            
            result = await deployment_manager._parse_ps_output_fallback(mock_output)
            
            assert result["service1"] == ServiceStatus.RUNNING.value
            assert result["service2"] == ServiceStatus.STOPPED.value
    
    class TestErrorHandling:
        """錯誤處理測試"""
        
        @pytest.mark.asyncio
        async def test_start_services_exception_handling(self, deployment_manager):
            """測試：啟動服務時異常處理"""
            with patch.object(deployment_manager, '_get_compose_file') as mock_get_compose:
                mock_get_compose.side_effect = Exception("Unexpected error")
                
                success, message = await deployment_manager.start_services("development")
                
                assert success is False
                assert "啟動服務時發生錯誤" in message
                assert "Unexpected error" in message
        
        @pytest.mark.asyncio
        async def test_stop_services_exception_handling(self, deployment_manager):
            """測試：停止服務時異常處理"""
            with patch.object(deployment_manager, '_get_compose_file') as mock_get_compose:
                mock_get_compose.side_effect = Exception("Stop error")
                
                success, message = await deployment_manager.stop_services("development")
                
                assert success is False
                assert "停止服務時發生錯誤" in message
                assert "Stop error" in message
        
        @pytest.mark.asyncio
        async def test_health_check_exception_handling(self, deployment_manager):
            """測試：健康檢查時異常處理"""
            with patch.object(deployment_manager, '_get_compose_file') as mock_get_compose:
                mock_get_compose.side_effect = Exception("Health check error")
                
                status = await deployment_manager.health_check("development")
                
                assert "error" in status
                assert "健康檢查時發生錯誤" in status["error"]
                assert "Health check error" in status["error"]
    
    class TestConfiguration:
        """配置測試"""
        
        def test_default_configuration(self):
            """測試：預設配置"""
            manager = DeploymentManager()
            
            assert manager.deployment_timeout == 300
            assert manager.health_check_timeout == 60
            assert manager.health_check_retries == 5
            assert manager.retry_delay == 10
            assert 'development' in manager.supported_environments
        
        def test_custom_configuration(self):
            """測試：自定義配置"""
            config = {
                'deployment_timeout': 600,
                'health_check_timeout': 120,
                'health_check_retries': 10,
                'retry_delay': 5
            }
            
            manager = DeploymentManager(config)
            
            assert manager.deployment_timeout == 600
            assert manager.health_check_timeout == 120
            assert manager.health_check_retries == 10
            assert manager.retry_delay == 5


if __name__ == '__main__':
    pytest.main([__file__, '-v'])