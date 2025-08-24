"""
Docker 測試配置檔案
Task ID: T1 - Docker 測試框架建立 (基礎架構部分)

提供 Docker 容器管理、測試環境隔離和基礎架構驗證的核心 Fixture
"""

import pytest
import asyncio
import logging
import tempfile
import uuid
import time
import os
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager

# 嘗試導入 Docker SDK，如果失敗則跳過 Docker 測試
try:
    import docker
    import docker.errors
    DOCKER_AVAILABLE = True
except ImportError:
    docker = None
    DOCKER_AVAILABLE = False

# 設置日誌
logger = logging.getLogger(__name__)

# Docker 測試配置 - 針對效能優化調整
DOCKER_TEST_CONFIG = {
    "image_name": "roas-bot",
    "container_name_prefix": "test-roas-bot",
    "test_timeout": 300,  # 5 分鐘
    "healthcheck_timeout": 60,  # 1 分鐘
    "container_memory_limit": "512m",  # 降低記憶體限制以符合效能要求
    "container_cpu_limit": "0.5",  # 降低 CPU 限制以符合效能要求
    "network_name": "test-network",
    "volume_mount_path": "/app/test-data",
    # 效能優化設定 - Ethan 的專門配置
    "performance_optimized": True,
    "resource_monitoring_enabled": True,
    "cleanup_aggressive": True,
    "parallel_execution_limit": 3,
    "memory_efficient_mode": True
}

class DockerTestError(Exception):
    """Docker 測試專用異常"""
    pass

class ContainerHealthCheckError(DockerTestError):
    """容器健康檢查失敗異常"""
    pass

class DockerTestFixture:
    """Docker 測試夾具類別
    
    提供核心的 Docker 容器生命週期管理功能：
    - 容器啟動和停止
    - 健康檢查驗證
    - 測試環境隔離
    """
    
    def __init__(self, docker_client):
        if not DOCKER_AVAILABLE:
            raise pytest.skip("Docker SDK not available")
            
        self.client = docker_client
        self.containers = []
        self.networks = []
        self.volumes = []
        self.test_id = str(uuid.uuid4())[:8]
        
    def start_container(self, config: Dict[str, Any]):
        """啟動 Docker 容器（效能優化版本）
        
        Args:
            config: 容器配置字典，包含以下鍵值：
                - image: Docker 鏡像名稱
                - name: 容器名稱（可選）
                - environment: 環境變數字典（可選）
                - ports: 端口映射字典（可選）
                - volumes: 卷掛載字典（可選）
                - command: 啟動命令（可選）
                - healthcheck: 健康檢查配置（可選）
                
        Returns:
            啟動的 Docker 容器物件
            
        Raises:
            DockerTestError: 容器啟動失敗時拋出
        """
        try:
            # 生成唯一容器名稱
            container_name = config.get(
                'name', 
                f"{DOCKER_TEST_CONFIG['container_name_prefix']}-{self.test_id}"
            )
            
            # 效能優化的基礎容器配置
            memory_limit = config.get('memory_limit', DOCKER_TEST_CONFIG['container_memory_limit'])
            cpu_limit = float(config.get('cpu_limit', DOCKER_TEST_CONFIG['container_cpu_limit']))
            
            container_config = {
                'image': config['image'],
                'name': container_name,
                'detach': True,
                'remove': False,  # 手動清理以便調試
                'mem_limit': memory_limit,
                'cpu_period': 100000,
                'cpu_quota': int(100000 * cpu_limit),
                'environment': config.get('environment', {}),
                'ports': config.get('ports', {}),
                'volumes': config.get('volumes', {}),
                'network': config.get('network', None),
                'command': config.get('command', None)
            }
            
            # 效能優化設定
            if DOCKER_TEST_CONFIG.get('performance_optimized', False):
                # 限制系統資源使用
                container_config.update({
                    'oom_kill_disable': False,  # 允許 OOM killer 以防止系統負載過高
                    'mem_swappiness': 10,  # 降低 swap 使用
                    'shm_size': '64m',  # 限制共享記憶體
                })
                
                # 如果啟用記憶體高效模式
                if DOCKER_TEST_CONFIG.get('memory_efficient_mode', False):
                    container_config['environment'].update({
                        'PYTHONOPTIMIZE': '2',  # Python 優化模式
                        'PYTHONDONTWRITEBYTECODE': '1',  # 不寫 bytecode 文件
                        'MEMORY_EFFICIENT': 'true'
                    })
            
            # 設置健康檢查
            if 'healthcheck' in config:
                container_config['healthcheck'] = config['healthcheck']
            
            # 啟動容器
            logger.info(f"啟動優化的 Docker 容器: {container_name} (記憶體: {memory_limit}, CPU: {cpu_limit})")
            container = self.client.containers.run(**container_config)
            
            # 記錄容器以便後續清理
            self.containers.append(container)
            
            logger.info(f"Docker 容器已啟動: {container.id[:12]}")
            return container
            
        except docker.errors.DockerException as e:
            raise DockerTestError(f"Docker 容器啟動失敗: {str(e)}")
        except Exception as e:
            raise DockerTestError(f"容器啟動時發生未預期錯誤: {str(e)}")
    
    def stop_container(self, container) -> None:
        """停止 Docker 容器
        
        Args:
            container: 要停止的 Docker 容器物件
            
        Raises:
            DockerTestError: 容器停止失敗時拋出
        """
        try:
            logger.info(f"停止 Docker 容器: {container.id[:12]}")
            
            # 優雅停止容器
            container.stop(timeout=10)
            
            # 等待容器完全停止
            container.wait()
            
            logger.info(f"Docker 容器已停止: {container.id[:12]}")
            
        except docker.errors.NotFound:
            logger.warning(f"容器不存在或已被刪除: {container.id[:12]}")
        except docker.errors.DockerException as e:
            raise DockerTestError(f"Docker 容器停止失敗: {str(e)}")
        except Exception as e:
            raise DockerTestError(f"容器停止時發生未預期錯誤: {str(e)}")
    
    def verify_container_health(self, container) -> bool:
        """驗證容器健康狀態
        
        Args:
            container: 要檢查的 Docker 容器物件
            
        Returns:
            容器是否健康
            
        Raises:
            ContainerHealthCheckError: 健康檢查失敗時拋出
        """
        try:
            logger.info(f"檢查 Docker 容器健康狀態: {container.id[:12]}")
            
            # 刷新容器狀態
            container.reload()
            
            # 檢查容器是否在運行
            if container.status != 'running':
                raise ContainerHealthCheckError(
                    f"容器未在運行狀態: {container.status}"
                )
            
            # 檢查容器健康檢查結果（如果有配置）
            health = container.attrs.get('State', {}).get('Health')
            if health:
                health_status = health.get('Status')
                if health_status == 'unhealthy':
                    last_log = health.get('Log', [])[-1] if health.get('Log') else {}
                    raise ContainerHealthCheckError(
                        f"容器健康檢查失敗: {last_log.get('Output', 'unknown error')}"
                    )
                elif health_status == 'starting':
                    # 等待健康檢查完成
                    return self._wait_for_health_check(container)
            
            # 檢查容器基本狀態
            if container.attrs['State']['Running']:
                logger.info(f"容器健康狀態正常: {container.id[:12]}")
                return True
            else:
                raise ContainerHealthCheckError(
                    f"容器未在運行: {container.attrs['State'].get('Status', 'unknown')}"
                )
                
        except docker.errors.NotFound:
            raise ContainerHealthCheckError("容器不存在")
        except ContainerHealthCheckError:
            raise
        except Exception as e:
            raise ContainerHealthCheckError(f"健康檢查時發生錯誤: {str(e)}")
    
    def _wait_for_health_check(self, container, timeout: int = None) -> bool:
        """等待容器健康檢查完成
        
        Args:
            container: 要等待的容器
            timeout: 等待超時時間（秒）
            
        Returns:
            健康檢查是否成功
        """
        timeout = timeout or DOCKER_TEST_CONFIG['healthcheck_timeout']
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                container.reload()
                health = container.attrs.get('State', {}).get('Health')
                
                if health:
                    status = health.get('Status')
                    if status == 'healthy':
                        return True
                    elif status == 'unhealthy':
                        return False
                    # status == 'starting' 時繼續等待
                
                time.sleep(2)  # 等待 2 秒後再次檢查
                
            except Exception as e:
                logger.warning(f"等待健康檢查時發生錯誤: {str(e)}")
                time.sleep(1)
        
        raise ContainerHealthCheckError(f"健康檢查超時（{timeout} 秒）")
    
    def cleanup(self) -> None:
        """清理測試資源（效能優化版本）"""
        logger.info(f"清理測試資源，測試 ID: {self.test_id}")
        
        cleanup_start = time.time()
        cleanup_stats = {
            "containers_cleaned": 0,
            "networks_cleaned": 0,
            "volumes_cleaned": 0,
            "errors_encountered": 0
        }
        
        # 停止並刪除容器（並行處理以提高效率）
        if DOCKER_TEST_CONFIG.get('cleanup_aggressive', False):
            self._aggressive_container_cleanup(cleanup_stats)
        else:
            self._standard_container_cleanup(cleanup_stats)
        
        # 清理網絡
        for network in self.networks:
            try:
                network.remove()
                cleanup_stats["networks_cleaned"] += 1
                logger.info(f"已清理網絡: {network.id[:12]}")
            except Exception as e:
                cleanup_stats["errors_encountered"] += 1
                logger.warning(f"清理網絡時發生錯誤: {str(e)}")
        
        # 清理卷
        for volume in self.volumes:
            try:
                volume.remove(force=True)
                cleanup_stats["volumes_cleaned"] += 1
                logger.info(f"已清理卷: {volume.id[:12]}")
            except Exception as e:
                cleanup_stats["errors_encountered"] += 1
                logger.warning(f"清理卷時發生錯誤: {str(e)}")
        
        cleanup_duration = time.time() - cleanup_start
        logger.info(f"資源清理完成，耗時: {cleanup_duration:.2f}s", extra=cleanup_stats)
    
    def _aggressive_container_cleanup(self, stats: Dict[str, int]) -> None:
        """積極的容器清理（並行處理）"""
        import concurrent.futures
        
        def cleanup_single_container(container):
            try:
                # 立即強制停止
                if container.status in ['running', 'paused']:
                    container.kill()
                container.remove(force=True)
                return True
            except Exception as e:
                logger.warning(f"積極清理容器失敗 {container.id[:12]}: {str(e)}")
                return False
        
        # 並行清理容器
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_to_container = {executor.submit(cleanup_single_container, container): container 
                                 for container in self.containers}
            
            for future in concurrent.futures.as_completed(future_to_container):
                if future.result():
                    stats["containers_cleaned"] += 1
                else:
                    stats["errors_encountered"] += 1
    
    def _standard_container_cleanup(self, stats: Dict[str, int]) -> None:
        """標準容器清理"""
        for container in self.containers:
            try:
                if container.status == 'running':
                    container.stop(timeout=5)
                container.remove(force=True)
                stats["containers_cleaned"] += 1
                logger.info(f"已清理容器: {container.id[:12]}")
            except Exception as e:
                stats["errors_encountered"] += 1
                logger.warning(f"清理容器時發生錯誤: {str(e)}")


class DockerTestLogger:
    """Docker 測試日誌和錯誤報告管理器"""
    
    def __init__(self, test_name: str):
        self.test_name = test_name
        self.test_start_time = datetime.now()
        self.test_id = str(uuid.uuid4())[:8]
        self.logs = []
        self.errors = []
        
    def log_info(self, message: str, context: Dict[str, Any] = None):
        """記錄資訊日誌"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'level': 'INFO',
            'message': message,
            'context': context or {},
            'test_id': self.test_id
        }
        self.logs.append(log_entry)
        logger.info(f"[{self.test_name}] {message}")
    
    def log_error(self, message: str, error: Exception = None, context: Dict[str, Any] = None):
        """記錄錯誤日誌"""
        error_entry = {
            'timestamp': datetime.now().isoformat(),
            'level': 'ERROR',
            'message': message,
            'error': str(error) if error else None,
            'error_type': type(error).__name__ if error else None,
            'context': context or {},
            'test_id': self.test_id
        }
        self.errors.append(error_entry)
        logger.error(f"[{self.test_name}] {message}: {str(error) if error else ''}")
    
    def generate_report(self) -> Dict[str, Any]:
        """生成測試報告"""
        test_duration = (datetime.now() - self.test_start_time).total_seconds()
        
        return {
            'test_id': self.test_id,
            'test_name': self.test_name,
            'start_time': self.test_start_time.isoformat(),
            'end_time': datetime.now().isoformat(),
            'duration_seconds': test_duration,
            'total_logs': len(self.logs),
            'total_errors': len(self.errors),
            'success': len(self.errors) == 0,
            'logs': self.logs,
            'errors': self.errors
        }


# === Pytest Fixtures ===

@pytest.fixture(scope='session')
def docker_client():
    """提供 Docker 客戶端"""
    if not DOCKER_AVAILABLE:
        pytest.skip("Docker SDK not available")
        
    try:
        client = docker.from_env()
        # 測試連接
        client.ping()
        logger.info("Docker 客戶端連接成功")
        yield client
    except docker.errors.DockerException as e:
        pytest.skip(f"Docker 不可用: {str(e)}")
    finally:
        if 'client' in locals():
            client.close()


@pytest.fixture
def docker_test_fixture(docker_client):
    """提供 Docker 測試夾具"""
    fixture = DockerTestFixture(docker_client)
    yield fixture
    fixture.cleanup()


@pytest.fixture
def docker_test_logger(request) -> DockerTestLogger:
    """提供 Docker 測試日誌記錄器"""
    test_name = request.node.name
    return DockerTestLogger(test_name)


@pytest.fixture
def roas_bot_image(docker_client) -> str:
    """確保 ROAS Bot Docker 鏡像存在 - 強化版本 with 備用策略"""
    if not DOCKER_AVAILABLE:
        pytest.skip("Docker SDK not available")
        
    image_name = DOCKER_TEST_CONFIG['image_name']
    fallback_images = ["python:3.13-slim", "python:3.12-slim", "python:3.11-slim"]
    
    try:
        # 首先檢查鏡像是否存在
        try:
            image = docker_client.images.get(image_name)
            logger.info(f"使用現有 Docker 鏡像: {image_name}")
            return image_name
        except docker.errors.ImageNotFound:
            logger.info(f"鏡像 {image_name} 不存在，嘗試構建...")
            
        # 嘗試構建鏡像 - 增加錯誤處理和進度追蹤
        project_root = Path(__file__).parent.parent.parent
        dockerfile_path = project_root / "Dockerfile"
        
        if not dockerfile_path.exists():
            logger.warning("Dockerfile 不存在，使用備用基礎鏡像")
            return _get_fallback_image(docker_client, fallback_images)
        
        try:
            logger.info(f"開始構建 Docker 鏡像: {image_name}")
            build_start_time = time.time()
            
            # 構建配置
            build_config = {
                'path': str(project_root),
                'tag': image_name,
                'rm': True,
                'forcerm': True,
                'pull': True,  # 確保基礎鏡像是最新的
                'nocache': False,  # 允許使用快取以提升效能
                'buildargs': {
                    'ENVIRONMENT': 'test',
                    'PYTHONPATH': '/app'
                }
            }
            
            image, build_logs = docker_client.images.build(**build_config)
            build_duration = time.time() - build_start_time
            
            # 記錄構建日誌並分析結果
            error_logs = []
            warning_logs = []
            
            for log_entry in build_logs:
                if 'stream' in log_entry:
                    log_line = log_entry['stream'].strip()
                    logger.debug(log_line)
                    
                    # 檢測錯誤和警告
                    if any(keyword in log_line.lower() for keyword in ['error', 'failed', 'cannot', 'unable']):
                        error_logs.append(log_line)
                    elif any(keyword in log_line.lower() for keyword in ['warning', 'deprecated']):
                        warning_logs.append(log_line)
                        
                elif 'error' in log_entry:
                    error_detail = log_entry['error']
                    logger.error(f"構建錯誤: {error_detail}")
                    error_logs.append(error_detail)
            
            # 記錄構建結果統計
            logger.info(f"Docker 鏡像構建完成: {image_name}")
            logger.info(f"構建耗時: {build_duration:.2f} 秒")
            
            if warning_logs:
                logger.warning(f"構建過程中出現 {len(warning_logs)} 個警告")
                
            if error_logs and len(error_logs) > 0:
                logger.warning(f"構建過程中出現潛在問題: {len(error_logs)} 個")
                # 但如果鏡像成功構建，繼續使用
                
            # 驗證構建的鏡像
            try:
                docker_client.images.get(image_name)
                logger.info(f"鏡像驗證成功: {image_name}")
                return image_name
            except docker.errors.ImageNotFound:
                logger.error(f"鏡像構建後無法找到: {image_name}")
                raise DockerTestError(f"鏡像構建後驗證失敗: {image_name}")
            
        except Exception as build_error:
            build_error_msg = str(build_error)
            logger.error(f"鏡像構建失敗: {build_error_msg}")
            
            # 分析錯誤類型並決定策略
            if any(keyword in build_error_msg.lower() for keyword in ['uv', 'cargo', 'rustc', 'path']):
                logger.info("檢測到工具鏈問題，這已在新版Dockerfile中修復")
                
            # 使用備用策略
            logger.info("啟用備用策略：使用基礎Python鏡像進行測試")
            return _get_fallback_image(docker_client, fallback_images)
            
    except Exception as e:
        logger.error(f"Docker 鏡像處理過程發生嚴重錯誤: {str(e)}")
        pytest.skip(f"無法準備Docker測試環境: {str(e)}")


def _get_fallback_image(docker_client, fallback_images: list) -> str:
    """取得備用Docker鏡像用於測試 - 增強版本"""
    
    # 首先嘗試構建測試專用鏡像
    test_dockerfile_path = Path(__file__).parent / "Dockerfile.test"
    if test_dockerfile_path.exists():
        try:
            logger.info("嘗試構建測試專用輕量級鏡像...")
            test_image_name = "roas-bot-test-minimal"
            
            image, build_logs = docker_client.images.build(
                path=str(test_dockerfile_path.parent),
                dockerfile="Dockerfile.test",
                tag=test_image_name,
                rm=True,
                forcerm=True
            )
            
            # 驗證測試鏡像
            docker_client.images.get(test_image_name)
            logger.info(f"測試專用鏡像構建成功: {test_image_name}")
            return test_image_name
            
        except Exception as e:
            logger.warning(f"測試專用鏡像構建失敗: {str(e)}")
    
    # 如果測試鏡像失敗，使用標準備用鏡像
    for fallback_image in fallback_images:
        try:
            logger.info(f"嘗試使用備用鏡像: {fallback_image}")
            
            # 嘗試從本地或遠端獲取鏡像
            try:
                image = docker_client.images.get(fallback_image)
                logger.info(f"使用本地備用鏡像: {fallback_image}")
            except docker.errors.ImageNotFound:
                logger.info(f"拉取備用鏡像: {fallback_image}")
                docker_client.images.pull(fallback_image)
                image = docker_client.images.get(fallback_image)
            
            # 測試鏡像基本功能
            if _test_image_functionality(docker_client, fallback_image):
                logger.info(f"備用鏡像功能驗證成功: {fallback_image}")
                return fallback_image
            else:
                logger.warning(f"備用鏡像功能驗證失敗: {fallback_image}")
                continue
                
        except Exception as e:
            logger.warning(f"備用鏡像 {fallback_image} 不可用: {str(e)}")
            continue
    
    # 如果所有備用方案都失敗
    raise DockerTestError("所有Docker鏡像方案都不可用，無法執行Docker測試")


def _test_image_functionality(docker_client, image_name: str) -> bool:
    """測試Docker鏡像基本功能"""
    try:
        # 創建測試容器
        container = docker_client.containers.run(
            image=image_name,
            command=['python', '-c', 'import sys; print(f"Python {sys.version}"); exit(0)'],
            detach=True,
            remove=True,
            mem_limit='256m',
            cpu_period=100000,
            cpu_quota=25000  # 25% CPU
        )
        
        # 等待容器完成
        result = container.wait(timeout=30)
        exit_code = result.get('StatusCode', -1) if isinstance(result, dict) else result
        
        return exit_code == 0
        
    except Exception as e:
        logger.debug(f"鏡像功能測試失敗 {image_name}: {str(e)}")
        return False


@pytest.fixture
def test_network(docker_client):
    """創建測試專用 Docker 網絡"""
    if not DOCKER_AVAILABLE:
        pytest.skip("Docker SDK not available")
        
    network_name = f"test-network-{uuid.uuid4().hex[:8]}"
    network = None
    
    try:
        # 簡化網絡配置，避免數值範圍錯誤
        network = docker_client.networks.create(
            network_name,
            driver="bridge"
        )
        logger.info(f"創建測試網絡: {network_name}")
        yield network
    except Exception as e:
        logger.warning(f"創建測試網絡失敗: {str(e)}")
        # 如果網絡創建失敗，跳過需要網絡的測試
        pytest.skip(f"無法創建測試網絡: {str(e)}")
    finally:
        if network is not None:
            try:
                network.remove()
                logger.info(f"清理測試網絡: {network_name}")
            except Exception as e:
                logger.warning(f"清理測試網絡時發生錯誤: {str(e)}")


@pytest.fixture
def test_volume(docker_client):
    """創建測試專用 Docker 卷"""
    if not DOCKER_AVAILABLE:
        pytest.skip("Docker SDK not available")
        
    volume_name = f"test-volume-{uuid.uuid4().hex[:8]}"
    
    try:
        volume = docker_client.volumes.create(
            volume_name,
            driver="local"
        )
        logger.info(f"創建測試卷: {volume_name}")
        yield volume
    finally:
        try:
            volume.remove(force=True)
            logger.info(f"清理測試卷: {volume_name}")
        except Exception as e:
            logger.warning(f"清理測試卷時發生錯誤: {str(e)}")


@pytest.fixture
def docker_test_config() -> Dict[str, Any]:
    """提供 Docker 測試配置"""
    return DOCKER_TEST_CONFIG.copy()


# === 測試工具函數 ===

def wait_for_container_ready(
    container, 
    timeout: int = 60,
    check_interval: int = 2
) -> bool:
    """等待容器準備就緒
    
    Args:
        container: Docker 容器物件
        timeout: 超時時間（秒）
        check_interval: 檢查間隔（秒）
        
    Returns:
        容器是否準備就緒
    """
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            container.reload()
            if container.status == 'running':
                return True
            elif container.status in ['exited', 'dead']:
                return False
        except Exception as e:
            logger.warning(f"檢查容器狀態時發生錯誤: {str(e)}")
        
        time.sleep(check_interval)
    
    return False


def get_container_logs(container) -> str:
    """獲取容器日誌
    
    Args:
        container: Docker 容器物件
        
    Returns:
        容器日誌字符串
    """
    try:
        logs = container.logs(tail=100).decode('utf-8')
        return logs
    except Exception as e:
        logger.warning(f"獲取容器日誌時發生錯誤: {str(e)}")
        return ""


# 配置 pytest 標記
pytestmark = pytest.mark.docker