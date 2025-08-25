"""
環境檢查器單元測試套件
Task ID: 1 - ROAS Bot v2.4.3 Docker啟動系統修復

測試目標：F-2 環境檢查和驗證系統
- 檢查所有必要環境變數是否存在並格式正確
- 驗證Docker daemon運行狀態和版本相容性
- 檢查網路連接狀態和端口可用性
- 驗證磁盤空間和權限配置

基於知識庫最佳實踐BP-001: 測試基礎設施設計模式
"""

import asyncio
import os
import tempfile
import unittest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import pytest
import subprocess
import shutil
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

# 模擬環境檢查器類別
class EnvironmentValidator:
    """環境檢查器 - 實作完整的環境變數驗證和配置檢查功能"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.min_docker_version = self.config.get('min_docker_version', '20.10.0')
        self.min_compose_version = self.config.get('min_compose_version', '2.0.0')
        self.min_disk_space_mb = self.config.get('min_disk_space_mb', 1024)  # 1GB
        self.required_ports = self.config.get('required_ports', [6379, 8000])
        
    async def validate_environment(self) -> Tuple[bool, List[str]]:
        """
        執行完整的環境驗證
        
        返回:
            Tuple[bool, List[str]]: (是否通過, 錯誤訊息列表)
        """
        errors = []
        
        # 檢查環境變數
        env_valid, env_errors = await self.check_environment_variables()
        if not env_valid:
            errors.extend(env_errors)
            
        # 檢查Docker服務
        docker_valid, docker_error = await self.check_docker_service()
        if not docker_valid:
            errors.append(docker_error)
            
        # 檢查網路連接
        network_valid, network_errors = await self.check_network_connectivity()
        if not network_valid:
            errors.extend(network_errors)
            
        # 檢查磁盤空間
        disk_valid, disk_error = await self.check_disk_space()
        if not disk_valid:
            errors.append(disk_error)
            
        # 檢查權限
        perm_valid, perm_errors = await self.check_permissions()
        if not perm_valid:
            errors.extend(perm_errors)
            
        return len(errors) == 0, errors
    
    async def check_environment_variables(self) -> Tuple[bool, List[str]]:
        """檢查必要的環境變數"""
        required_vars = [
            'DISCORD_TOKEN',
            'ENVIRONMENT', 
            'DATABASE_URL',
            'MESSAGE_DATABASE_URL'
        ]
        
        errors = []
        for var in required_vars:
            value = os.getenv(var)
            if not value:
                errors.append(f"缺少必要環境變數: {var}")
            elif var == 'DISCORD_TOKEN' and len(value) < 50:
                errors.append(f"環境變數 {var} 格式不正確: 長度不足")
            elif var == 'ENVIRONMENT' and value not in ['development', 'staging', 'production']:
                errors.append(f"環境變數 {var} 值不合法: {value}")
                
        return len(errors) == 0, errors
    
    async def check_docker_service(self) -> Tuple[bool, str]:
        """檢查Docker daemon狀態和版本"""
        try:
            # 檢查Docker是否運行
            result = await asyncio.create_subprocess_exec(
                'docker', 'version', '--format', '{{.Server.Version}}',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                return False, f"Docker daemon未運行: {stderr.decode()}"
                
            version = stdout.decode().strip()
            if not self._is_version_compatible(version, self.min_docker_version):
                return False, f"Docker版本過舊: {version}, 最低需求: {self.min_docker_version}"
            
            # 檢查Docker Compose
            compose_result = await asyncio.create_subprocess_exec(
                'docker-compose', '--version',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            compose_stdout, compose_stderr = await compose_result.communicate()
            
            if compose_result.returncode != 0:
                return False, f"Docker Compose未安裝: {compose_stderr.decode()}"
                
            return True, ""
            
        except Exception as e:
            return False, f"檢查Docker服務時發生錯誤: {str(e)}"
    
    async def check_network_connectivity(self) -> Tuple[bool, List[str]]:
        """檢查網路連接和端口可用性"""
        errors = []
        
        # 檢查端口是否可用
        import socket
        for port in self.required_ports:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(1)
                    result = s.connect_ex(('localhost', port))
                    if result == 0:
                        errors.append(f"端口 {port} 已被占用")
            except Exception as e:
                errors.append(f"檢查端口 {port} 時發生錯誤: {str(e)}")
        
        # 檢查網路連接（可選）
        try:
            # 檢查能否連接Docker Hub
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get('https://registry-1.docker.io/v2/', timeout=5) as resp:
                    if resp.status != 200:
                        errors.append("無法連接到Docker Hub")
        except Exception as e:
            # 網路連接失敗不是致命錯誤，但記錄警告
            pass
            
        return len(errors) == 0, errors
    
    async def check_disk_space(self) -> Tuple[bool, str]:
        """檢查磁盤空間"""
        try:
            stat = shutil.disk_usage(os.getcwd())
            free_space_mb = stat.free // (1024 * 1024)
            
            if free_space_mb < self.min_disk_space_mb:
                return False, f"磁盤空間不足: {free_space_mb}MB, 最低需求: {self.min_disk_space_mb}MB"
            
            return True, ""
        except Exception as e:
            return False, f"檢查磁盤空間時發生錯誤: {str(e)}"
    
    async def check_permissions(self) -> Tuple[bool, List[str]]:
        """檢查權限配置"""
        errors = []
        
        # 檢查目錄寫入權限
        test_dirs = [
            './data', 
            './logs', 
            './backups'
        ]
        
        for dir_path in test_dirs:
            try:
                Path(dir_path).mkdir(parents=True, exist_ok=True)
                # 測試寫入權限
                test_file = Path(dir_path) / '.test_write'
                test_file.write_text('test')
                test_file.unlink()
            except Exception as e:
                errors.append(f"目錄 {dir_path} 權限不足: {str(e)}")
        
        return len(errors) == 0, errors
    
    async def validate_compose_file(self) -> Tuple[bool, List[str]]:
        """驗證Docker Compose配置文件"""
        errors = []
        
        compose_files = [
            'docker-compose.dev.yml',
            'docker-compose.prod.yml'
        ]
        
        for compose_file in compose_files:
            if not Path(compose_file).exists():
                errors.append(f"缺少Compose配置文件: {compose_file}")
                continue
                
            try:
                # 驗證YAML語法
                result = await asyncio.create_subprocess_exec(
                    'docker-compose', '-f', compose_file, 'config',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                _, stderr = await result.communicate()
                
                if result.returncode != 0:
                    errors.append(f"Compose文件 {compose_file} 語法錯誤: {stderr.decode()}")
                    
            except Exception as e:
                errors.append(f"驗證 {compose_file} 時發生錯誤: {str(e)}")
        
        return len(errors) == 0, errors
    
    def _is_version_compatible(self, current: str, minimum: str) -> bool:
        """比較版本號是否符合最低要求"""
        def version_tuple(v):
            return tuple(map(int, v.split('.')))
        
        try:
            return version_tuple(current) >= version_tuple(minimum)
        except Exception:
            return False


class TestEnvironmentValidator:
    """環境檢查器測試類 - 基於TDD最佳實踐設計"""
    
    @pytest.fixture
    def validator(self):
        """測試固件：創建環境檢查器實例"""
        return EnvironmentValidator()
        
    @pytest.fixture
    def custom_validator(self):
        """測試固件：創建自定義配置的環境檢查器"""
        config = {
            'min_docker_version': '20.10.0',
            'min_compose_version': '2.0.0',
            'min_disk_space_mb': 512,
            'required_ports': [6379, 8000, 3000]
        }
        return EnvironmentValidator(config)
    
    @pytest.fixture
    def mock_env_vars(self, monkeypatch):
        """測試固件：模擬環境變數"""
        test_env = {
            'DISCORD_TOKEN': 'test_token_' + 'x' * 50,
            'ENVIRONMENT': 'development',
            'DATABASE_URL': 'sqlite:///data/test.db',
            'MESSAGE_DATABASE_URL': 'sqlite:///data/message.db'
        }
        for key, value in test_env.items():
            monkeypatch.setenv(key, value)
        return test_env
    
    class TestEnvironmentVariables:
        """環境變數檢查測試"""
        
        @pytest.mark.asyncio
        async def test_valid_environment_variables(self, validator, mock_env_vars):
            """測試：所有必要環境變數存在且格式正確"""
            valid, errors = await validator.check_environment_variables()
            
            assert valid is True
            assert len(errors) == 0
        
        @pytest.mark.asyncio 
        async def test_missing_required_variables(self, validator, monkeypatch):
            """測試：缺少必要環境變數"""
            # 清除所有環境變數
            for var in ['DISCORD_TOKEN', 'ENVIRONMENT', 'DATABASE_URL', 'MESSAGE_DATABASE_URL']:
                monkeypatch.delenv(var, raising=False)
            
            valid, errors = await validator.check_environment_variables()
            
            assert valid is False
            assert len(errors) == 4
            assert all('缺少必要環境變數' in error for error in errors)
        
        @pytest.mark.asyncio
        async def test_invalid_token_format(self, validator, monkeypatch):
            """測試：DISCORD_TOKEN格式不正確"""
            monkeypatch.setenv('DISCORD_TOKEN', 'short_token')
            monkeypatch.setenv('ENVIRONMENT', 'development')
            monkeypatch.setenv('DATABASE_URL', 'sqlite:///data/test.db')
            monkeypatch.setenv('MESSAGE_DATABASE_URL', 'sqlite:///data/message.db')
            
            valid, errors = await validator.check_environment_variables()
            
            assert valid is False
            assert any('格式不正確' in error for error in errors)
        
        @pytest.mark.asyncio
        async def test_invalid_environment_value(self, validator, monkeypatch):
            """測試：ENVIRONMENT值不合法"""
            monkeypatch.setenv('DISCORD_TOKEN', 'valid_token_' + 'x' * 50)
            monkeypatch.setenv('ENVIRONMENT', 'invalid_env')
            monkeypatch.setenv('DATABASE_URL', 'sqlite:///data/test.db')
            monkeypatch.setenv('MESSAGE_DATABASE_URL', 'sqlite:///data/message.db')
            
            valid, errors = await validator.check_environment_variables()
            
            assert valid is False
            assert any('值不合法' in error for error in errors)
    
    class TestDockerService:
        """Docker服務檢查測試"""
        
        @pytest.mark.asyncio
        async def test_docker_service_available(self, validator):
            """測試：Docker服務可用且版本符合要求"""
            with patch('asyncio.create_subprocess_exec') as mock_subprocess:
                # 模擬Docker版本檢查
                mock_docker_proc = AsyncMock()
                mock_docker_proc.communicate.return_value = (b'20.10.5\n', b'')
                mock_docker_proc.returncode = 0
                
                # 模擬Docker Compose檢查
                mock_compose_proc = AsyncMock()
                mock_compose_proc.communicate.return_value = (b'docker-compose version 2.5.0\n', b'')
                mock_compose_proc.returncode = 0
                
                mock_subprocess.side_effect = [mock_docker_proc, mock_compose_proc]
                
                valid, error = await validator.check_docker_service()
                
                assert valid is True
                assert error == ""
        
        @pytest.mark.asyncio
        async def test_docker_daemon_not_running(self, validator):
            """測試：Docker daemon未運行"""
            with patch('asyncio.create_subprocess_exec') as mock_subprocess:
                mock_proc = AsyncMock()
                mock_proc.communicate.return_value = (b'', b'Cannot connect to the Docker daemon')
                mock_proc.returncode = 1
                
                mock_subprocess.return_value = mock_proc
                
                valid, error = await validator.check_docker_service()
                
                assert valid is False
                assert 'Docker daemon未運行' in error
        
        @pytest.mark.asyncio
        async def test_docker_version_too_old(self, validator):
            """測試：Docker版本過舊"""
            with patch('asyncio.create_subprocess_exec') as mock_subprocess:
                mock_proc = AsyncMock()
                mock_proc.communicate.return_value = (b'19.03.0\n', b'')
                mock_proc.returncode = 0
                
                mock_subprocess.return_value = mock_proc
                
                valid, error = await validator.check_docker_service()
                
                assert valid is False
                assert 'Docker版本過舊' in error
        
        @pytest.mark.asyncio
        async def test_docker_compose_not_installed(self, validator):
            """測試：Docker Compose未安裝"""
            with patch('asyncio.create_subprocess_exec') as mock_subprocess:
                # 第一次調用：Docker版本檢查成功
                mock_docker_proc = AsyncMock()
                mock_docker_proc.communicate.return_value = (b'20.10.5\n', b'')
                mock_docker_proc.returncode = 0
                
                # 第二次調用：Docker Compose檢查失敗
                mock_compose_proc = AsyncMock()
                mock_compose_proc.communicate.return_value = (b'', b'command not found: docker-compose')
                mock_compose_proc.returncode = 127
                
                mock_subprocess.side_effect = [mock_docker_proc, mock_compose_proc]
                
                valid, error = await validator.check_docker_service()
                
                assert valid is False
                assert 'Docker Compose未安裝' in error
    
    class TestNetworkConnectivity:
        """網路連接檢查測試"""
        
        @pytest.mark.asyncio
        async def test_all_ports_available(self, validator):
            """測試：所有必要端口可用"""
            with patch('socket.socket') as mock_socket:
                mock_sock = MagicMock()
                mock_sock.connect_ex.return_value = 1  # 連接失敗表示端口可用
                mock_socket.return_value.__enter__.return_value = mock_sock
                
                valid, errors = await validator.check_network_connectivity()
                
                assert valid is True
                assert len(errors) == 0
        
        @pytest.mark.asyncio
        async def test_port_occupied(self, custom_validator):
            """測試：端口被占用"""
            with patch('socket.socket') as mock_socket:
                mock_sock = MagicMock()
                # 模擬端口6379被占用，其他端口可用
                mock_sock.connect_ex.side_effect = [0, 1, 1]  # 0表示連接成功（端口被占用）
                mock_socket.return_value.__enter__.return_value = mock_sock
                
                valid, errors = await custom_validator.check_network_connectivity()
                
                assert valid is False
                assert any('端口 6379 已被占用' in error for error in errors)
        
        @pytest.mark.asyncio
        async def test_network_check_exception(self, validator):
            """測試：網路檢查時發生異常"""
            with patch('socket.socket') as mock_socket:
                mock_socket.side_effect = Exception("Network error")
                
                valid, errors = await validator.check_network_connectivity()
                
                assert valid is False
                assert any('檢查端口' in error and '時發生錯誤' in error for error in errors)
    
    class TestDiskSpace:
        """磁盤空間檢查測試"""
        
        @pytest.mark.asyncio
        async def test_sufficient_disk_space(self, validator):
            """測試：磁盤空間充足"""
            with patch('shutil.disk_usage') as mock_disk_usage:
                # 模擬2GB可用空間
                mock_usage = Mock()
                mock_usage.free = 2 * 1024 * 1024 * 1024  # 2GB
                mock_disk_usage.return_value = mock_usage
                
                valid, error = await validator.check_disk_space()
                
                assert valid is True
                assert error == ""
        
        @pytest.mark.asyncio
        async def test_insufficient_disk_space(self, validator):
            """測試：磁盤空間不足"""
            with patch('shutil.disk_usage') as mock_disk_usage:
                # 模擬512MB可用空間，低於預設1GB要求
                mock_usage = Mock()
                mock_usage.free = 512 * 1024 * 1024  # 512MB
                mock_disk_usage.return_value = mock_usage
                
                valid, error = await validator.check_disk_space()
                
                assert valid is False
                assert '磁盤空間不足' in error
        
        @pytest.mark.asyncio
        async def test_disk_check_exception(self, validator):
            """測試：磁盤檢查時發生異常"""
            with patch('shutil.disk_usage') as mock_disk_usage:
                mock_disk_usage.side_effect = Exception("Disk access error")
                
                valid, error = await validator.check_disk_space()
                
                assert valid is False
                assert '檢查磁盤空間時發生錯誤' in error
    
    class TestPermissions:
        """權限檢查測試"""
        
        @pytest.mark.asyncio
        async def test_all_directories_writable(self, validator):
            """測試：所有目錄都有寫入權限"""
            with patch('pathlib.Path.mkdir'), \
                 patch('pathlib.Path.write_text'), \
                 patch('pathlib.Path.unlink'):
                
                valid, errors = await validator.check_permissions()
                
                assert valid is True
                assert len(errors) == 0
        
        @pytest.mark.asyncio
        async def test_directory_permission_denied(self, validator):
            """測試：目錄權限不足"""
            with patch('pathlib.Path.mkdir') as mock_mkdir:
                mock_mkdir.side_effect = PermissionError("Permission denied")
                
                valid, errors = await validator.check_permissions()
                
                assert valid is False
                assert all('權限不足' in error for error in errors)
        
        @pytest.mark.asyncio
        async def test_write_permission_denied(self, validator):
            """測試：寫入權限被拒絕"""
            with patch('pathlib.Path.mkdir'), \
                 patch('pathlib.Path.write_text') as mock_write:
                mock_write.side_effect = PermissionError("Permission denied")
                
                valid, errors = await validator.check_permissions()
                
                assert valid is False
                assert all('權限不足' in error for error in errors)
    
    class TestComposeFileValidation:
        """Compose文件驗證測試"""
        
        @pytest.mark.asyncio
        async def test_valid_compose_files(self, validator):
            """測試：Compose文件語法正確"""
            with patch('pathlib.Path.exists', return_value=True), \
                 patch('asyncio.create_subprocess_exec') as mock_subprocess:
                
                mock_proc = AsyncMock()
                mock_proc.communicate.return_value = (b'valid config output', b'')
                mock_proc.returncode = 0
                mock_subprocess.return_value = mock_proc
                
                valid, errors = await validator.validate_compose_file()
                
                assert valid is True
                assert len(errors) == 0
        
        @pytest.mark.asyncio
        async def test_missing_compose_files(self, validator):
            """測試：缺少Compose文件"""
            with patch('pathlib.Path.exists', return_value=False):
                
                valid, errors = await validator.validate_compose_file()
                
                assert valid is False
                assert len(errors) == 2  # dev和prod文件都缺少
                assert all('缺少Compose配置文件' in error for error in errors)
        
        @pytest.mark.asyncio
        async def test_invalid_compose_syntax(self, validator):
            """測試：Compose文件語法錯誤"""
            with patch('pathlib.Path.exists', return_value=True), \
                 patch('asyncio.create_subprocess_exec') as mock_subprocess:
                
                mock_proc = AsyncMock()
                mock_proc.communicate.return_value = (b'', b'yaml: syntax error')
                mock_proc.returncode = 1
                mock_subprocess.return_value = mock_proc
                
                valid, errors = await validator.validate_compose_file()
                
                assert valid is False
                assert all('語法錯誤' in error for error in errors)
    
    class TestVersionComparison:
        """版本比較測試"""
        
        def test_version_comparison_equal(self, validator):
            """測試：版本相等"""
            assert validator._is_version_compatible('20.10.0', '20.10.0') is True
        
        def test_version_comparison_newer(self, validator):
            """測試：當前版本較新"""
            assert validator._is_version_compatible('20.10.5', '20.10.0') is True
            assert validator._is_version_compatible('21.0.0', '20.10.0') is True
        
        def test_version_comparison_older(self, validator):
            """測試：當前版本較舊"""
            assert validator._is_version_compatible('19.03.0', '20.10.0') is False
            assert validator._is_version_compatible('20.9.0', '20.10.0') is False
        
        def test_version_comparison_invalid_format(self, validator):
            """測試：無效版本格式"""
            assert validator._is_version_compatible('invalid', '20.10.0') is False
            assert validator._is_version_compatible('20.10.0', 'invalid') is False
    
    class TestIntegratedValidation:
        """整合驗證測試"""
        
        @pytest.mark.asyncio
        async def test_complete_validation_success(self, validator, mock_env_vars):
            """測試：完整環境驗證成功"""
            with patch.object(validator, 'check_docker_service', return_value=(True, "")), \
                 patch.object(validator, 'check_network_connectivity', return_value=(True, [])), \
                 patch.object(validator, 'check_disk_space', return_value=(True, "")), \
                 patch.object(validator, 'check_permissions', return_value=(True, [])):
                
                valid, errors = await validator.validate_environment()
                
                assert valid is True
                assert len(errors) == 0
        
        @pytest.mark.asyncio
        async def test_complete_validation_with_failures(self, validator):
            """測試：完整環境驗證失敗"""
            with patch.object(validator, 'check_environment_variables', return_value=(False, ['ENV_ERROR'])), \
                 patch.object(validator, 'check_docker_service', return_value=(False, "DOCKER_ERROR")), \
                 patch.object(validator, 'check_network_connectivity', return_value=(False, ['NETWORK_ERROR'])), \
                 patch.object(validator, 'check_disk_space', return_value=(False, "DISK_ERROR")), \
                 patch.object(validator, 'check_permissions', return_value=(False, ['PERM_ERROR'])):
                
                valid, errors = await validator.validate_environment()
                
                assert valid is False
                assert len(errors) == 5  # 每個檢查項目都有一個錯誤
                assert 'ENV_ERROR' in errors
                assert 'DOCKER_ERROR' in errors
                assert 'NETWORK_ERROR' in errors
                assert 'DISK_ERROR' in errors
                assert 'PERM_ERROR' in errors
    
    class TestEdgeCases:
        """邊界條件測試"""
        
        @pytest.mark.asyncio
        async def test_empty_configuration(self):
            """測試：空配置"""
            validator = EnvironmentValidator({})
            
            # 應該使用預設值
            assert validator.min_docker_version == '20.10.0'
            assert validator.min_compose_version == '2.0.0'
            assert validator.min_disk_space_mb == 1024
            assert validator.required_ports == [6379, 8000]
        
        @pytest.mark.asyncio
        async def test_minimal_disk_space_requirement(self):
            """測試：最小磁盤空間要求"""
            config = {'min_disk_space_mb': 1}  # 1MB最小要求
            validator = EnvironmentValidator(config)
            
            with patch('shutil.disk_usage') as mock_disk_usage:
                # 模擬2MB可用空間
                mock_usage = Mock()
                mock_usage.free = 2 * 1024 * 1024  # 2MB
                mock_disk_usage.return_value = mock_usage
                
                valid, error = await validator.check_disk_space()
                
                assert valid is True
                assert error == ""
        
        @pytest.mark.asyncio
        async def test_no_required_ports(self):
            """測試：不需要檢查端口"""
            config = {'required_ports': []}
            validator = EnvironmentValidator(config)
            
            valid, errors = await validator.check_network_connectivity()
            
            assert valid is True
            assert len(errors) == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])