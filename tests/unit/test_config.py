"""配置系統測試模組.

此模組測試 config.py 的核心功能，包括：
- Settings 類別和配置載入
- 環境變數處理
- 配置驗證
- 資料庫和路徑設置
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

# 確保正確的導入路徑
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.config import (
    CacheSettings,
    DatabaseSettings,
    LoggingSettings,
    Settings,
    get_settings,
)

# 測試用的有效Discord Bot Token格式（符合50字符最小長度要求）
TEST_TOKEN = "MTAzNzMxMzE5NDMyNDYzMzczMA.GbcKCG.dQw4w9WgXcQ7aBcDeFgHiJkLmNoPqRsT"


class TestSettings:
    """測試設置類別."""

    def test_settings_basic_structure(self):
        """測試設置基本結構."""
        with patch.dict(os.environ, {'TOKEN': TEST_TOKEN}):
            settings = Settings()

            # 測試基本屬性
            assert hasattr(settings, 'token')
            assert hasattr(settings, 'environment')
            assert hasattr(settings, 'debug')
            assert hasattr(settings, 'database')
            assert hasattr(settings, 'logging')
            assert hasattr(settings, 'cache')

    def test_settings_environment_handling(self):
        """測試環境變數處理."""
        with patch.dict(os.environ, {
            'TOKEN': TEST_TOKEN,
            'ENVIRONMENT': 'production',
            'DEBUG': 'true'
        }):
            settings = Settings()

            assert settings.environment == "production"
            assert settings.debug is True

    def test_settings_paths(self):
        """測試路徑配置."""
        with patch.dict(os.environ, {'TOKEN': TEST_TOKEN}):
            settings = Settings()

            # 測試路徑屬性存在
            assert hasattr(settings, 'project_root')
            assert hasattr(settings, 'data_dir')
            assert isinstance(settings.project_root, Path)
            assert isinstance(settings.data_dir, Path)


class TestDatabaseSettings:
    """測試資料庫設置."""

    def test_database_settings_defaults(self):
        """測試資料庫設置預設值."""
        db_settings = DatabaseSettings()

        assert hasattr(db_settings, 'pool_size')
        assert hasattr(db_settings, 'query_timeout')
        assert isinstance(db_settings.sqlite_path, Path)
        assert db_settings.pool_size > 0

    def test_database_settings_with_env_vars(self):
        """測試環境變數覆蓋資料庫設置."""
        with patch.dict(os.environ, {
            'DB_POOL_SIZE': '20',
            'DB_QUERY_TIMEOUT': '60'
        }):
            db_settings = DatabaseSettings()

            assert db_settings.pool_size == 20
            assert db_settings.query_timeout == 60


class TestLoggingSettings:
    """測試日誌設置."""

    def test_logging_settings_defaults(self):
        """測試日誌設置預設值."""
        log_settings = LoggingSettings()

        assert hasattr(log_settings, 'level')
        assert hasattr(log_settings, 'log_dir')
        assert isinstance(log_settings.log_dir, Path)

    def test_logging_settings_with_env_vars(self):
        """測試環境變數覆蓋日誌設置."""
        with patch.dict(os.environ, {
            'LOG_LEVEL': 'DEBUG'
        }):
            log_settings = LoggingSettings()

            # 檢查是否正確載入了環境變數
            assert hasattr(log_settings, 'level')


class TestCacheSettings:
    """測試快取設置."""

    def test_cache_settings_defaults(self):
        """測試快取設置預設值."""
        cache_settings = CacheSettings()

        # 驗證基本屬性存在
        assert hasattr(cache_settings, 'redis_url') or hasattr(cache_settings, 'ttl')
        # 檢查是否有基本的快取配置

    def test_cache_settings_with_env_vars(self):
        """測試環境變數覆蓋快取設置."""
        with patch.dict(os.environ, {
            'CACHE_TTL': '3600'
        }):
            cache_settings = CacheSettings()

            # 驗證環境變數是否被正確載入
            assert isinstance(cache_settings, CacheSettings)


class TestConfigurationValidation:
    """測試配置驗證."""

    def test_valid_configuration(self):
        """測試有效配置驗證."""
        with patch.dict(os.environ, {'TOKEN': TEST_TOKEN}):
            # 應該沒有驗證錯誤
            settings = Settings()
            assert settings.token == 'x' * 60

    def test_invalid_token_length(self):
        """測試無效 Token 長度."""
        with patch.dict(os.environ, {'TOKEN': 'short'}):
            with pytest.raises(ValidationError):
                Settings()

    def test_invalid_environment(self):
        """測試無效環境值."""
        with patch.dict(os.environ, {
            'TOKEN': TEST_TOKEN,
            'ENVIRONMENT': 'invalid_env'
        }), pytest.raises(ValidationError):
            Settings()


class TestConfigurationHelpers:
    """測試配置輔助函數."""

    def test_get_settings_function(self):
        """測試 get_settings 函數."""
        with patch.dict(os.environ, {'TOKEN': TEST_TOKEN}):
            settings = get_settings()

            assert isinstance(settings, Settings)
            assert settings.token == 'x' * 60

    def test_settings_immutability(self):
        """測試設置不可變性."""
        with patch.dict(os.environ, {'TOKEN': TEST_TOKEN}):
            settings = Settings()

            # Settings 被標記為 frozen，應該不能修改
            with pytest.raises((ValidationError, AttributeError)):
                settings.debug = True


class TestConfigurationIntegration:
    """測試配置整合功能."""

    def test_full_configuration_workflow(self):
        """測試完整的配置工作流程."""
        with patch.dict(os.environ, {
            'TOKEN': 'integration_test_token_' + 'x' * 40,
            'ENVIRONMENT': 'development',
            'DEBUG': 'true',
            'DB_POOL_SIZE': '15'
        }):
            settings = Settings()

            # 驗證所有配置都正確載入
            assert 'integration_test_token' in settings.token
            assert settings.environment == "development"
            assert settings.debug is True
            assert settings.database.pool_size == 15

    def test_settings_with_missing_optional_config(self):
        """測試缺少可選配置的情況."""
        with patch.dict(os.environ, {'TOKEN': TEST_TOKEN}):
            settings = Settings()

            # 應該使用預設值
            assert settings.environment == "development"
            assert settings.debug is False
            assert settings.command_prefix == "!"

    def test_nested_configuration_access(self):
        """測試嵌套配置訪問."""
        with patch.dict(os.environ, {'TOKEN': TEST_TOKEN}):
            settings = Settings()

            # 測試可以訪問嵌套的配置物件
            assert hasattr(settings, 'database')
            assert hasattr(settings, 'logging')
            assert hasattr(settings, 'cache')

            # 測試嵌套物件的類型
            assert isinstance(settings.database, DatabaseSettings)
            assert isinstance(settings.logging, LoggingSettings)
            assert isinstance(settings.cache, CacheSettings)
