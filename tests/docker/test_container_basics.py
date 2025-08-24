"""
基礎 Docker 容器功能驗證測試
Task ID: T1 - Docker 測試框架建立 (基礎架構部分)

驗證 Docker 容器的基礎功能，包括：
- 容器啟動和停止
- 健康檢查機制
- 資源限制
- 網絡連接
"""

import pytest
import time
import asyncio
import logging
from typing import Dict, Any

# 嘗試導入 Docker SDK，如果失敗則跳過 Docker 測試
try:
    from docker.models.containers import Container
    from docker.errors import DockerException
    DOCKER_AVAILABLE = True
except ImportError:
    Container = None
    DockerException = Exception
    DOCKER_AVAILABLE = False

from .conftest import (
    DockerTestFixture,
    DockerTestLogger,
    DockerTestError,
    ContainerHealthCheckError,
    wait_for_container_ready,
    get_container_logs
)

logger = logging.getLogger(__name__)

@pytest.mark.docker
@pytest.mark.integration
class TestDockerContainerBasics:
    """Docker 容器基礎功能測試套件"""
    
    def test_container_startup_success(
        self,
        docker_test_fixture: DockerTestFixture,
        docker_test_logger: DockerTestLogger,
        roas_bot_image: str
    ):
        """測試容器成功啟動"""
        docker_test_logger.log_info("開始測試容器啟動功能")
        
        # 準備容器配置
        container_config = {
            'image': roas_bot_image,
            'environment': {
                'ENVIRONMENT': 'test',
                'DATABASE_URL': 'sqlite:///test.db'
            },
            'memory_limit': '512m',
            'cpu_limit': '0.5'
        }
        
        try:
            # 啟動容器
            container = docker_test_fixture.start_container(container_config)
            docker_test_logger.log_info(f"容器已啟動: {container.id[:12]}")
            
            # 驗證容器狀態
            assert container is not None, "容器物件不應該為 None"
            
            # 等待容器準備就緒
            is_ready = wait_for_container_ready(container, timeout=30)
            assert is_ready, f"容器未能在 30 秒內準備就緒，狀態: {container.status}"
            
            # 驗證容器在運行
            container.reload()
            assert container.status == 'running', f"容器狀態應為 'running'，實際: {container.status}"
            
            docker_test_logger.log_info("容器啟動測試成功完成")
            
        except Exception as e:
            docker_test_logger.log_error("容器啟動測試失敗", e)
            raise

    def test_container_stop_success(
        self,
        docker_test_fixture: DockerTestFixture,
        docker_test_logger: DockerTestLogger,
        roas_bot_image: str
    ):
        """測試容器成功停止"""
        docker_test_logger.log_info("開始測試容器停止功能")
        
        container_config = {
            'image': roas_bot_image,
            'environment': {'ENVIRONMENT': 'test'}
        }
        
        try:
            # 啟動容器
            container = docker_test_fixture.start_container(container_config)
            wait_for_container_ready(container, timeout=30)
            
            # 驗證容器正在運行
            container.reload()
            assert container.status == 'running', "容器應該在運行狀態"
            
            # 停止容器
            docker_test_fixture.stop_container(container)
            docker_test_logger.log_info(f"容器已停止: {container.id[:12]}")
            
            # 驗證容器已停止
            container.reload()
            assert container.status in ['exited', 'dead'], f"容器應該已停止，實際狀態: {container.status}"
            
            docker_test_logger.log_info("容器停止測試成功完成")
            
        except Exception as e:
            docker_test_logger.log_error("容器停止測試失敗", e)
            raise

    def test_container_health_check_pass(
        self,
        docker_test_fixture: DockerTestFixture,
        docker_test_logger: DockerTestLogger,
        roas_bot_image: str
    ):
        """測試容器健康檢查通過"""
        docker_test_logger.log_info("開始測試容器健康檢查")
        
        # 配置具有健康檢查的容器
        container_config = {
            'image': roas_bot_image,
            'environment': {'ENVIRONMENT': 'test'},
            'healthcheck': {
                'test': ['CMD', 'python', '-c', 'print("healthy")'],
                'interval': 5 * 1000000000,  # 5 秒 (納秒)
                'timeout': 3 * 1000000000,   # 3 秒
                'retries': 3,
                'start_period': 10 * 1000000000  # 10 秒
            }
        }
        
        try:
            # 啟動容器
            container = docker_test_fixture.start_container(container_config)
            wait_for_container_ready(container, timeout=30)
            
            # 驗證健康檢查
            is_healthy = docker_test_fixture.verify_container_health(container)
            assert is_healthy, "容器健康檢查應該通過"
            
            docker_test_logger.log_info("容器健康檢查測試成功完成")
            
        except Exception as e:
            docker_test_logger.log_error("容器健康檢查測試失敗", e)
            raise

    def test_container_resource_limits(
        self,
        docker_test_fixture: DockerTestFixture,
        docker_test_logger: DockerTestLogger,
        roas_bot_image: str
    ):
        """測試容器資源限制"""
        docker_test_logger.log_info("開始測試容器資源限制")
        
        container_config = {
            'image': roas_bot_image,
            'environment': {'ENVIRONMENT': 'test'},
            'memory_limit': '256m',
            'cpu_limit': '0.25'
        }
        
        try:
            # 啟動容器
            container = docker_test_fixture.start_container(container_config)
            wait_for_container_ready(container, timeout=30)
            
            # 檢查資源限制設定
            container.reload()
            host_config = container.attrs['HostConfig']
            
            # 驗證記憶體限制
            memory_limit = host_config.get('Memory', 0)
            expected_memory = 256 * 1024 * 1024  # 256MB in bytes
            assert memory_limit == expected_memory, f"記憶體限制應為 {expected_memory}，實際: {memory_limit}"
            
            # 驗證 CPU 限制
            cpu_period = host_config.get('CpuPeriod', 0)
            cpu_quota = host_config.get('CpuQuota', 0)
            if cpu_period > 0 and cpu_quota > 0:
                cpu_limit = cpu_quota / cpu_period
                expected_cpu_limit = 0.25
                assert abs(cpu_limit - expected_cpu_limit) < 0.01, \
                    f"CPU 限制應為 {expected_cpu_limit}，實際: {cpu_limit}"
            
            docker_test_logger.log_info("容器資源限制測試成功完成")
            
        except Exception as e:
            docker_test_logger.log_error("容器資源限制測試失敗", e)
            raise

    def test_container_environment_variables(
        self,
        docker_test_fixture: DockerTestFixture,
        docker_test_logger: DockerTestLogger,
        roas_bot_image: str
    ):
        """測試容器環境變數設定"""
        docker_test_logger.log_info("開始測試容器環境變數")
        
        test_env_vars = {
            'ENVIRONMENT': 'test',
            'DEBUG': 'true',
            'DATABASE_URL': 'sqlite:///test.db',
            'TEST_TOKEN': 'test_token_12345'
        }
        
        container_config = {
            'image': roas_bot_image,
            'environment': test_env_vars,
            'command': ['python', '-c', 'import os; print(f"ENV: {os.environ.get(\"ENVIRONMENT\")}, DEBUG: {os.environ.get(\"DEBUG\")}")']
        }
        
        try:
            # 啟動容器
            container = docker_test_fixture.start_container(container_config)
            
            # 等待容器執行完成
            container.wait(timeout=30)
            
            # 檢查容器配置中的環境變數
            container.reload()
            config_env = container.attrs.get('Config', {}).get('Env', [])
            
            # 將環境變數列表轉換為字典
            env_dict = {}
            for env_var in config_env:
                if '=' in env_var:
                    key, value = env_var.split('=', 1)
                    env_dict[key] = value
            
            # 驗證環境變數
            for key, expected_value in test_env_vars.items():
                actual_value = env_dict.get(key)
                assert actual_value == expected_value, \
                    f"環境變數 {key} 應為 '{expected_value}'，實際: '{actual_value}'"
            
            docker_test_logger.log_info("容器環境變數測試成功完成")
            
        except Exception as e:
            docker_test_logger.log_error("容器環境變數測試失敗", e)
            raise

    def test_container_network_connectivity(
        self,
        docker_test_fixture: DockerTestFixture,
        docker_test_logger: DockerTestLogger,
        roas_bot_image: str,
        test_network
    ):
        """測試容器網絡連接"""
        docker_test_logger.log_info("開始測試容器網絡連接")
        
        container_config = {
            'image': roas_bot_image,
            'environment': {'ENVIRONMENT': 'test'},
            'network': test_network.name,
            'command': ['python', '-c', 'import socket; print(f"Hostname: {socket.gethostname()}")']
        }
        
        try:
            # 啟動容器
            container = docker_test_fixture.start_container(container_config)
            
            # 等待容器執行完成
            container.wait(timeout=30)
            
            # 檢查網絡配置
            container.reload()
            networks = container.attrs.get('NetworkSettings', {}).get('Networks', {})
            
            # 驗證容器連接到指定網絡
            assert test_network.name in networks, f"容器應該連接到網絡 {test_network.name}"
            
            network_config = networks[test_network.name]
            assert network_config.get('IPAddress'), "容器應該有 IP 地址"
            
            docker_test_logger.log_info(f"容器 IP: {network_config.get('IPAddress')}")
            docker_test_logger.log_info("容器網絡連接測試成功完成")
            
        except Exception as e:
            docker_test_logger.log_error("容器網絡連接測試失敗", e)
            raise

    def test_container_volume_mount(
        self,
        docker_test_fixture: DockerTestFixture,
        docker_test_logger: DockerTestLogger,
        roas_bot_image: str,
        test_volume
    ):
        """測試容器卷掛載"""
        docker_test_logger.log_info("開始測試容器卷掛載")
        
        container_config = {
            'image': roas_bot_image,
            'environment': {'ENVIRONMENT': 'test'},
            'volumes': {test_volume.name: {'bind': '/app/data', 'mode': 'rw'}},
            'command': ['python', '-c', 'import os; open("/app/data/test.txt", "w").write("test data"); print("File written successfully")']
        }
        
        try:
            # 啟動容器
            container = docker_test_fixture.start_container(container_config)
            
            # 等待容器執行完成
            container.wait(timeout=30)
            
            # 檢查掛載配置
            container.reload()
            mounts = container.attrs.get('Mounts', [])
            
            # 尋找我們的卷掛載
            volume_mount = None
            for mount in mounts:
                if mount.get('Name') == test_volume.name:
                    volume_mount = mount
                    break
            
            assert volume_mount is not None, f"未找到卷 {test_volume.name} 的掛載"
            assert volume_mount.get('Destination') == '/app/data', "卷掛載目的地不正確"
            assert volume_mount.get('Mode') == 'rw', "卷掛載模式應為讀寫"
            
            docker_test_logger.log_info("容器卷掛載測試成功完成")
            
        except Exception as e:
            docker_test_logger.log_error("容器卷掛載測試失敗", e)
            raise

    def test_container_error_handling(
        self,
        docker_test_fixture: DockerTestFixture,
        docker_test_logger: DockerTestLogger
    ):
        """測試容器錯誤處理"""
        docker_test_logger.log_info("開始測試容器錯誤處理")
        
        # 使用不存在的鏡像來觸發錯誤
        container_config = {
            'image': 'nonexistent-image:latest'
        }
        
        try:
            with pytest.raises(DockerTestError):
                docker_test_fixture.start_container(container_config)
            
            docker_test_logger.log_info("容器錯誤處理測試成功完成")
            
        except AssertionError:
            # 如果沒有拋出預期的異常，測試失敗
            docker_test_logger.log_error("容器錯誤處理測試失敗：未拋出預期異常")
            raise
        except Exception as e:
            docker_test_logger.log_error("容器錯誤處理測試失敗", e)
            raise

    def test_container_logs_collection(
        self,
        docker_test_fixture: DockerTestFixture,
        docker_test_logger: DockerTestLogger,
        roas_bot_image: str
    ):
        """測試容器日誌收集"""
        docker_test_logger.log_info("開始測試容器日誌收集")
        
        test_message = "Test log message 12345"
        container_config = {
            'image': roas_bot_image,
            'command': ['python', '-c', f'print("{test_message}")']
        }
        
        try:
            # 啟動容器
            container = docker_test_fixture.start_container(container_config)
            
            # 等待容器執行完成
            container.wait(timeout=30)
            
            # 收集容器日誌
            logs = get_container_logs(container)
            
            # 驗證日誌內容
            assert logs is not None, "容器日誌不應該為 None"
            assert test_message in logs, f"容器日誌應該包含測試訊息: {test_message}"
            
            docker_test_logger.log_info(f"容器日誌收集成功，日誌長度: {len(logs)} 字符")
            docker_test_logger.log_info("容器日誌收集測試成功完成")
            
        except Exception as e:
            docker_test_logger.log_error("容器日誌收集測試失敗", e)
            raise


@pytest.mark.docker
@pytest.mark.performance
class TestDockerContainerPerformance:
    """Docker 容器效能測試套件"""
    
    def test_container_startup_time(
        self,
        docker_test_fixture: DockerTestFixture,
        docker_test_logger: DockerTestLogger,
        roas_bot_image: str
    ):
        """測試容器啟動時間"""
        docker_test_logger.log_info("開始測試容器啟動時間效能")
        
        container_config = {
            'image': roas_bot_image,
            'environment': {'ENVIRONMENT': 'test'}
        }
        
        try:
            start_time = time.time()
            
            # 啟動容器
            container = docker_test_fixture.start_container(container_config)
            wait_for_container_ready(container, timeout=60)
            
            end_time = time.time()
            startup_time = end_time - start_time
            
            # 驗證啟動時間在合理範圍內（< 30 秒）
            max_startup_time = 30.0
            assert startup_time < max_startup_time, \
                f"容器啟動時間 {startup_time:.2f} 秒超過限制 {max_startup_time} 秒"
            
            docker_test_logger.log_info(
                f"容器啟動時間: {startup_time:.2f} 秒",
                {"startup_time_seconds": startup_time}
            )
            
        except Exception as e:
            docker_test_logger.log_error("容器啟動時間測試失敗", e)
            raise

    def test_multiple_container_management(
        self,
        docker_test_fixture: DockerTestFixture,
        docker_test_logger: DockerTestLogger,
        roas_bot_image: str
    ):
        """測試多個容器管理"""
        docker_test_logger.log_info("開始測試多個容器管理")
        
        container_count = 3
        containers = []
        
        try:
            # 啟動多個容器
            for i in range(container_count):
                container_config = {
                    'image': roas_bot_image,
                    'name': f'test-multi-container-{i}',
                    'environment': {'ENVIRONMENT': 'test', 'INSTANCE_ID': str(i)},
                    'command': ['python', '-c', f'import time; print("Container {i} started"); time.sleep(10)']
                }
                
                container = docker_test_fixture.start_container(container_config)
                containers.append(container)
                docker_test_logger.log_info(f"容器 {i} 已啟動: {container.id[:12]}")
            
            # 驗證所有容器都在運行
            for i, container in enumerate(containers):
                wait_for_container_ready(container, timeout=30)
                container.reload()
                assert container.status == 'running', f"容器 {i} 應該在運行狀態"
            
            docker_test_logger.log_info(f"成功管理 {container_count} 個容器")
            
        except Exception as e:
            docker_test_logger.log_error("多個容器管理測試失敗", e)
            raise


# === 效能測試配置 ===

@pytest.fixture
def performance_test_config():
    """效能測試配置"""
    return {
        'max_startup_time': 30.0,
        'max_memory_usage': '2g',
        'max_cpu_usage': 1.0,
        'container_count_limit': 5
    }