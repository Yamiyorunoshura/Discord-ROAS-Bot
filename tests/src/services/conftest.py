"""
服務模組專用測試配置
Task ID: 3 - 子機器人聊天功能和管理系統開發

專門為服務層測試提供fixture和配置
"""

import pytest
import pytest_asyncio
import asyncio
import tempfile
import logging
from unittest.mock import Mock, AsyncMock


# 配置 pytest-asyncio
pytest_plugins = ('pytest_asyncio',)


@pytest.fixture(scope="session")
def event_loop():
    """為服務測試提供事件循環"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def mock_config():
    """提供模擬配置"""
    config = Mock()
    
    # 安全配置
    security_config = Mock()
    security_config.encryption_key = "test_key_for_comprehensive_service_testing_32bytes"
    security_config.token_encryption_algorithm = "AES-GCM"
    security_config.key_rotation_enabled = True
    
    config.security = security_config
    
    return config


@pytest_asyncio.fixture
async def temp_database():
    """提供臨時測試資料庫"""
    import sqlite3
    import os
    
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_file.close()
    
    # 創建基本表結構
    conn = sqlite3.connect(temp_file.name)
    conn.execute('''
        CREATE TABLE sub_bots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bot_id VARCHAR(50) UNIQUE NOT NULL,
            name VARCHAR(100) NOT NULL,
            token_hash VARCHAR(255) NOT NULL,
            target_channels TEXT NOT NULL,
            ai_enabled BOOLEAN DEFAULT FALSE,
            ai_model VARCHAR(50),
            personality TEXT,
            rate_limit INTEGER DEFAULT 10,
            status VARCHAR(20) DEFAULT 'offline',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            owner_id INTEGER
        )
    ''')
    conn.close()
    
    yield temp_file.name
    
    # 清理
    try:
        os.unlink(temp_file.name)
    except OSError:
        pass


# 關閉警告日誌以保持測試輸出乾淨
logging.getLogger('pytest_asyncio').setLevel(logging.WARNING)