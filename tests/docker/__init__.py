"""
Docker 測試框架模組
Task ID: T1 - Docker 測試框架建立 (基礎架構部分)

提供 Docker 容器測試的基礎架構支援，包括：
- 容器生命週期管理
- 健康檢查機制  
- 測試日誌記錄
- 錯誤報告機制
"""

from .conftest import (
    DockerTestFixture,
    DockerTestLogger,
    DockerTestError,
    ContainerHealthCheckError,
    DOCKER_TEST_CONFIG,
    wait_for_container_ready,
    get_container_logs
)

__version__ = "1.0.0"
__author__ = "ROAS Bot Development Team"

# 匯出公共 API
__all__ = [
    # 核心類別
    'DockerTestFixture',
    'DockerTestLogger',
    
    # 異常類別
    'DockerTestError', 
    'ContainerHealthCheckError',
    
    # 配置
    'DOCKER_TEST_CONFIG',
    
    # 工具函數
    'wait_for_container_ready',
    'get_container_logs'
]