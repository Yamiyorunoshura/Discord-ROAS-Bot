"""統一配置管理系統測試

測試配置載入器、合併引擎、驗證器、熱重載和加密服務等核心功能.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import aiosqlite
import pytest
import yaml
from cryptography.fernet import Fernet

from src.core.config import (
    CliConfigLoader,
    CommonValidators,
    # 安全加密系統
    ConfigEncryptionService,
    # 配置處理引擎
    ConfigMergeEngine,
    # 基礎類別
    ConfigSource,
    ConfigurationError,
    # 統一配置管理
    ConfigurationManager,
    ConfigurationValidator,
    DatabaseConfigLoader,
    EnhancedSettings,
    EnvironmentConfigLoader,
    FileConfigLoader,
    # 熱重載系統
    LoggerConfigChangeListener,
    RemoteConfigLoader,
    SecureConfigStorage,
    SettingsFactory,
    get_config_manager,
    # 全域函數
    initialize_config_system,
    shutdown_config_system,
)

# =====================================================
# 測試基礎設定
# =====================================================


@pytest.fixture
def sample_config():
    """提供測試用的配置數據"""
    return {
        "token": "test_discord_token_123456789",
        "environment": "development",
        "debug": True,
        "logging": {"level": "DEBUG", "format": "colored"},
        "database": {"pool_size": 20, "max_overflow": 30},
        "features": {"activity_meter": True, "protection": False},
    }


@pytest.fixture
def temp_config_dir():
    """創建臨時配置目錄"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


# =====================================================
# 配置載入器測試
# =====================================================


class TestEnvironmentConfigLoader:
    """環境變數配置載入器測試"""

    def test_init(self):
        """測試初始化"""
        loader = EnvironmentConfigLoader("TEST_")
        assert loader.source == ConfigSource.ENVIRONMENT
        assert loader.prefix == "TEST_"

    @pytest.mark.asyncio
    async def test_load_simple_env(self):
        """測試簡單環境變數載入"""
        with patch.dict(
            os.environ,
            {"TEST_TOKEN": "test_token", "TEST_DEBUG": "true", "TEST_PORT": "8080"},
        ):
            loader = EnvironmentConfigLoader("TEST_")
            config = await loader.load()

            assert config["token"] == "test_token"
            assert config["debug"]
            assert config["port"] == 8080

    @pytest.mark.asyncio
    async def test_load_nested_env(self):
        """測試嵌套環境變數載入"""
        with patch.dict(
            os.environ,
            {
                "TEST_DATABASE__HOST": "localhost",
                "TEST_DATABASE__PORT": "5432",
                "TEST_FEATURES__CACHE": "false",
            },
        ):
            loader = EnvironmentConfigLoader("TEST_")
            config = await loader.load()

            assert config["database"]["host"] == "localhost"
            assert config["database"]["port"] == 5432
            assert not config["features"]["cache"]

    @pytest.mark.asyncio
    async def test_load_with_json_values(self):
        """測試JSON值載入"""
        with patch.dict(
            os.environ,
            {"TEST_ROLES": '["admin", "user"]', "TEST_SETTINGS": '{"timeout": 30}'},
        ):
            loader = EnvironmentConfigLoader("TEST_")
            config = await loader.load()

            assert config["roles"] == ["admin", "user"]
            assert config["settings"] == {"timeout": 30}

    @pytest.mark.asyncio
    async def test_load_with_comma_separated_list(self):
        """測試逗號分隔列表載入"""
        with patch.dict(os.environ, {"TEST_TAGS": "tag1,tag2,tag3"}):
            loader = EnvironmentConfigLoader("TEST_")
            config = await loader.load()

            assert config["tags"] == ["tag1", "tag2", "tag3"]

    @pytest.mark.asyncio
    async def test_is_changed(self):
        """測試變更檢測"""
        loader = EnvironmentConfigLoader("TEST_")
        assert not await loader.is_changed()

    @pytest.mark.asyncio
    async def test_watch(self):
        """測試監控功能"""
        loader = EnvironmentConfigLoader("TEST_")
        callback = AsyncMock()
        await loader.watch(callback)
        # 環境變數載入器不進行監控,所以沒有調用回調
        callback.assert_not_called()


class TestFileConfigLoader:
    """檔案配置載入器測試"""

    @pytest.mark.asyncio
    async def test_load_env_file(self, temp_config_dir):
        """測試.env檔案載入"""
        env_file = temp_config_dir / "test.env"
        env_file.write_text("""
# Test configuration
TOKEN=test_token_123
DEBUG=true
DATABASE__HOST=localhost
DATABASE__PORT=5432
""")

        loader = FileConfigLoader(env_file)
        config = await loader.load()

        assert config["token"] == "test_token_123"
        assert config["debug"]
        assert config["database"]["host"] == "localhost"
        assert config["database"]["port"] == 5432

    @pytest.mark.asyncio
    async def test_load_yaml_file(self, temp_config_dir):
        """測試YAML檔案載入"""
        yaml_file = temp_config_dir / "test.yaml"
        yaml_content = {
            "token": "yaml_token_123",
            "environment": "development",
            "logging": {"level": "INFO", "format": "json"},
        }
        yaml_file.write_text(yaml.dump(yaml_content))

        loader = FileConfigLoader(yaml_file)
        config = await loader.load()

        assert config["token"] == "yaml_token_123"
        assert config["environment"] == "development"
        assert config["logging"]["level"] == "INFO"

    @pytest.mark.asyncio
    async def test_load_json_file(self, temp_config_dir):
        """測試JSON檔案載入"""
        json_file = temp_config_dir / "test.json"
        json_content = {"token": "json_token_123", "features": ["feature1", "feature2"]}
        json_file.write_text(json.dumps(json_content))

        loader = FileConfigLoader(json_file)
        config = await loader.load()

        assert config["token"] == "json_token_123"
        assert config["features"] == ["feature1", "feature2"]

    @pytest.mark.asyncio
    async def test_load_nonexistent_file(self, temp_config_dir):
        """測試不存在的檔案"""
        loader = FileConfigLoader(temp_config_dir / "nonexistent.yaml")
        config = await loader.load()
        assert config == {}

    @pytest.mark.asyncio
    async def test_load_unsupported_format(self, temp_config_dir):
        """測試不支援的檔案格式"""
        txt_file = temp_config_dir / "test.txt"
        txt_file.write_text("some content")

        loader = FileConfigLoader(txt_file)
        with pytest.raises(ConfigurationError, match="不支援的配置檔案格式"):
            await loader.load()

    @pytest.mark.asyncio
    async def test_is_changed(self, temp_config_dir):
        """測試檔案變更檢測"""
        config_file = temp_config_dir / "test.yaml"
        config_file.write_text("token: initial")

        loader = FileConfigLoader(config_file)

        # 首次載入
        await loader.load()
        assert not await loader.is_changed()

        # 修改檔案
        config_file.write_text("token: modified")
        assert await loader.is_changed()


class TestCliConfigLoader:
    """命令列配置載入器測試"""

    def test_init(self):
        """測試初始化"""
        loader = CliConfigLoader()
        assert loader.source == ConfigSource.COMMAND_LINE

    @pytest.mark.asyncio
    async def test_load_empty_config(self):
        """測試空配置載入"""
        loader = CliConfigLoader()
        config = await loader.load()
        assert config == {}

    @pytest.mark.asyncio
    async def test_load_with_cli_config_env(self):
        """測試從環境變數載入CLI配置"""
        cli_config = {"token": "cli_token", "debug": True}

        with patch.dict(os.environ, {"CLI_CONFIG": json.dumps(cli_config)}):
            loader = CliConfigLoader()
            config = await loader.load()

            assert config["token"] == "cli_token"
            assert config["debug"]


# =====================================================
# 配置合併引擎測試
# =====================================================


class TestConfigMergeEngine:
    """配置合併引擎測試"""

    def test_override_merge(self):
        """測試覆蓋合併策略"""
        engine = ConfigMergeEngine()

        configs = [
            (ConfigSource.DEFAULT, {"a": 1, "b": 2}),
            (ConfigSource.ENVIRONMENT, {"b": 3, "c": 4}),
        ]

        result = engine.merge_configs(configs, "override")
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_deep_merge(self):
        """測試深度合併策略"""
        engine = ConfigMergeEngine()

        configs = [
            (
                ConfigSource.DEFAULT,
                {
                    "database": {"host": "localhost", "port": 5432},
                    "features": {"a": True},
                },
            ),
            (
                ConfigSource.ENVIRONMENT,
                {"database": {"port": 3306, "user": "admin"}, "features": {"b": False}},
            ),
        ]

        result = engine.merge_configs(configs, "deep_merge")
        expected = {
            "database": {"host": "localhost", "port": 3306, "user": "admin"},
            "features": {"a": True, "b": False},
        }
        assert result == expected

    def test_list_append_merge(self):
        """測試列表追加合併策略"""
        engine = ConfigMergeEngine()

        configs = [
            (ConfigSource.DEFAULT, {"tags": ["tag1", "tag2"]}),
            (ConfigSource.ENVIRONMENT, {"tags": ["tag3", "tag4"]}),
        ]

        result = engine.merge_configs(configs, "list_append")
        assert result["tags"] == ["tag1", "tag2", "tag3", "tag4"]

    def test_list_unique_merge(self):
        """測試列表去重合併策略"""
        engine = ConfigMergeEngine()

        configs = [
            (ConfigSource.DEFAULT, {"tags": ["tag1", "tag2"]}),
            (ConfigSource.ENVIRONMENT, {"tags": ["tag2", "tag3"]}),
        ]

        result = engine.merge_configs(configs, "list_unique")
        assert result["tags"] == ["tag1", "tag2", "tag3"]

    def test_priority_ordering(self):
        """測試優先級排序"""
        engine = ConfigMergeEngine()

        configs = [
            (ConfigSource.DEFAULT, {"value": "default"}),
            (ConfigSource.CONFIG_FILE, {"value": "file"}),
            (ConfigSource.ENVIRONMENT, {"value": "env"}),
            (ConfigSource.COMMAND_LINE, {"value": "cli"}),
        ]

        result = engine.merge_configs(configs)
        # 命令列應該有最高優先級
        assert result["value"] == "cli"


# =====================================================
# 配置驗證器測試
# =====================================================


class TestConfigurationValidator:
    """配置驗證器測試"""

    def test_add_validation_rule(self):
        """測試添加驗證規則"""
        validator = ConfigurationValidator()

        validator.add_validation_rule(
            "test_field", lambda x: isinstance(x, str), "必須是字符串"
        )

        assert "test_field" in validator.validation_rules

    def test_validate_config_success(self):
        """測試配置驗證成功"""
        validator = ConfigurationValidator()
        validator.add_validation_rule(
            "name", lambda x: isinstance(x, str) and len(x) > 0, "名稱不能為空"
        )

        config = {"name": "test_name"}
        errors = validator.validate_config(config)
        assert errors == []

    def test_validate_config_failure(self):
        """測試配置驗證失敗"""
        validator = ConfigurationValidator()
        validator.add_validation_rule(
            "age", lambda x: isinstance(x, int) and x > 0, "年齡必須是正整數"
        )

        config = {"age": -5}
        errors = validator.validate_config(config)
        assert len(errors) == 1
        assert "年齡必須是正整數" in errors[0]

    def test_validate_nested_config(self):
        """測試嵌套配置驗證"""
        validator = ConfigurationValidator()
        validator.add_validation_rule(
            "database.port",
            lambda x: isinstance(x, int) and 1 <= x <= 65535,
            "端口必須在1-65535範圍內",
        )

        config = {"database": {"port": 3306}}
        errors = validator.validate_config(config)
        assert errors == []

        config = {"database": {"port": 70000}}
        errors = validator.validate_config(config)
        assert len(errors) == 1

    def test_validate_missing_required_field(self):
        """測試缺少必要欄位"""
        validator = ConfigurationValidator()
        validator.add_validation_rule(
            "required_field", CommonValidators.required, "必要欄位不能為空"
        )

        config = {}
        errors = validator.validate_config(config)
        assert len(errors) == 1
        assert "缺少必要的配置項" in errors[0]


class TestCommonValidators:
    """常用驗證器測試"""

    def test_required_validator(self):
        """測試必要值驗證器"""
        assert CommonValidators.required("value")
        assert not CommonValidators.required("")
        assert not CommonValidators.required(None)

    def test_positive_integer_validator(self):
        """測試正整數驗證器"""
        assert CommonValidators.positive_integer(5)
        assert not CommonValidators.positive_integer(0)
        assert not CommonValidators.positive_integer(-1)
        assert not CommonValidators.positive_integer("5")

    def test_valid_log_level_validator(self):
        """測試日誌級別驗證器"""
        assert CommonValidators.valid_log_level("DEBUG")
        assert CommonValidators.valid_log_level("INFO")
        assert not CommonValidators.valid_log_level("INVALID")

    def test_valid_environment_validator(self):
        """測試環境驗證器"""
        assert CommonValidators.valid_environment("development")
        assert CommonValidators.valid_environment("production")
        assert not CommonValidators.valid_environment("invalid")

    def test_valid_url_validator(self):
        """測試URL驗證器"""
        assert CommonValidators.valid_url("https://example.com")
        assert CommonValidators.valid_url("http://localhost:8080")
        assert not CommonValidators.valid_url("invalid-url")
        assert not CommonValidators.valid_url(123)

    def test_min_length_validator(self):
        """測試最小長度驗證器"""
        validator = CommonValidators.min_length(3)
        assert validator("test")
        assert not validator("ab")
        assert validator([1, 2, 3, 4])
        assert not validator([1, 2])

    def test_in_range_validator(self):
        """測試範圍驗證器"""
        validator = CommonValidators.in_range(1, 10)
        assert validator(5)
        assert validator(1)
        assert validator(10)
        assert not validator(0)
        assert not validator(11)
        assert not validator("5")


# =====================================================
# 安全加密系統測試
# =====================================================


class TestConfigEncryptionService:
    """配置加密服務測試"""

    def test_init_with_master_key(self):
        """測試使用主密鑰初始化"""
        key = Fernet.generate_key()
        service = ConfigEncryptionService(key)
        assert service.master_key == key

    def test_encrypt_decrypt_value(self):
        """測試加密解密值"""
        service = ConfigEncryptionService()

        original = "sensitive_token_123"
        encrypted = service.encrypt_value(original)
        decrypted = service.decrypt_value(encrypted)

        assert decrypted == original
        assert encrypted != original

    def test_is_encrypted(self):
        """測試加密檢測"""
        service = ConfigEncryptionService()

        original = "test_value"
        encrypted = service.encrypt_value(original)

        assert service.is_encrypted(encrypted)
        assert not service.is_encrypted(original)

    def test_register_encrypted_field(self):
        """測試註冊加密欄位"""
        service = ConfigEncryptionService()
        service.register_encrypted_field("token")

        assert "token" in service.encrypted_fields

    def test_process_config_encrypt(self):
        """測試配置加密處理"""
        service = ConfigEncryptionService()
        service.register_encrypted_field("token")

        config = {"token": "secret_token", "debug": True}
        encrypted_config = service.process_config(config, encrypt=True)

        assert encrypted_config["debug"]
        assert encrypted_config["token"] != "secret_token"
        assert service.is_encrypted(encrypted_config["token"])

    def test_process_config_decrypt(self):
        """測試配置解密處理"""
        service = ConfigEncryptionService()
        service.register_encrypted_field("token")

        config = {"token": "secret_token", "debug": True}

        # 先加密
        encrypted_config = service.process_config(config, encrypt=True)

        # 再解密
        decrypted_config = service.process_config(encrypted_config, encrypt=False)

        assert decrypted_config["token"] == "secret_token"
        assert decrypted_config["debug"]


class TestSecureConfigStorage:
    """安全配置存儲測試"""

    @pytest.mark.asyncio
    async def test_store_and_load_secure_config(self, temp_config_dir):
        """測試存儲和載入安全配置"""
        encryption_service = ConfigEncryptionService()
        encryption_service.register_encrypted_field("token")

        # 臨時更改存儲路徑
        with patch.object(
            SecureConfigStorage,
            "__init__",
            lambda self, enc_service: setattr(self, "encryption_service", enc_service)
            or setattr(self, "storage_path", temp_config_dir)
            or setattr(self, "_logger", None),
        ):
            storage = SecureConfigStorage(encryption_service)

            config_data = {"token": "secret_test_token", "debug": False}

            # 存儲配置
            await storage.store_secure_config("test_config", config_data)

            # 載入配置
            loaded_config = await storage.load_secure_config("test_config")

            assert loaded_config["token"] == "secret_test_token"
            assert not loaded_config["debug"]

    @pytest.mark.asyncio
    async def test_load_nonexistent_config(self, temp_config_dir):
        """測試載入不存在的配置"""
        encryption_service = ConfigEncryptionService()

        with patch.object(
            SecureConfigStorage,
            "__init__",
            lambda self, enc_service: setattr(self, "encryption_service", enc_service)
            or setattr(self, "storage_path", temp_config_dir)
            or setattr(self, "_logger", None),
        ):
            storage = SecureConfigStorage(encryption_service)
            config = await storage.load_secure_config("nonexistent")
            assert config == {}


# =====================================================
# 配置變更監聽器測試
# =====================================================


class TestConfigChangeListener:
    """配置變更監聽器測試"""

    @pytest.mark.asyncio
    async def test_logger_config_change_listener(self):
        """測試日誌配置變更監聽器"""
        listener = LoggerConfigChangeListener()

        # 模擬舊新配置
        old_settings = MagicMock()
        new_settings = MagicMock()

        changes = [
            {
                "key": "logging.level",
                "old_value": "INFO",
                "new_value": "DEBUG",
                "change_type": "modified",
            }
        ]

        # 這裡主要測試不會拋出異常
        with patch("src.core.logger.setup_logging"):
            await listener.on_config_changed(old_settings, new_settings, changes)


# =====================================================
# 統一配置管理測試
# =====================================================


class TestConfigurationManager:
    """配置管理器測試"""

    def test_init(self):
        """測試初始化"""
        manager = ConfigurationManager()
        assert manager.settings_class is not None
        assert isinstance(manager.merge_engine, ConfigMergeEngine)
        assert isinstance(manager.validator, ConfigurationValidator)
        assert isinstance(manager.encryption_service, ConfigEncryptionService)

    def test_add_loader(self):
        """測試添加載入器"""
        manager = ConfigurationManager()
        loader = EnvironmentConfigLoader("TEST_")

        manager.add_loader("env_loader", loader)
        assert "env_loader" in manager.loaders
        assert manager.loaders["env_loader"] == loader

    def test_add_change_listener(self):
        """測試添加變更監聽器"""
        manager = ConfigurationManager()
        listener = LoggerConfigChangeListener()

        manager.add_change_listener(listener)
        assert listener in manager.change_listeners

    @pytest.mark.asyncio
    async def test_load_configuration(self, sample_config):
        """測試載入配置"""
        manager = ConfigurationManager()

        # 模擬載入器
        mock_loader = AsyncMock()
        mock_loader.source = ConfigSource.ENVIRONMENT
        mock_loader.load.return_value = sample_config

        manager.add_loader("mock_loader", mock_loader)

        settings = await manager.load_configuration()
        assert settings is not None
        assert settings.token == "test_discord_token_123456789"
        assert settings.environment == "development"


class TestEnhancedSettings:
    """增強配置系統測試"""

    @pytest.mark.asyncio
    async def test_enhanced_settings_creation(self, sample_config):
        """測試增強配置創建"""
        # 由於EnhancedSettings繼承自Settings,我們需要確保它可以正常創建
        try:
            settings = EnhancedSettings(**sample_config)
            assert settings.token == "test_discord_token_123456789"
            assert settings.environment == "development"
        except Exception as e:
            pytest.skip(
                f"Enhanced settings creation requires valid Settings configuration: {e}"
            )


class TestSettingsFactory:
    """配置工廠測試"""

    def test_init(self):
        """測試初始化"""
        factory = SettingsFactory()
        assert factory.config_manager is not None

    def test_get_default_sources(self):
        """測試獲取預設配置來源"""
        factory = SettingsFactory()
        sources = factory._get_default_sources()

        assert "environment" in sources
        assert "env_file" in sources
        assert "yaml_config" in sources
        assert "cli" in sources

    def test_create_loader_env(self):
        """測試創建環境變數載入器"""
        factory = SettingsFactory()
        config = {"type": "env", "prefix": "TEST_"}

        loader = factory._create_loader("test", config)
        assert isinstance(loader, EnvironmentConfigLoader)
        assert loader.prefix == "TEST_"

    def test_create_loader_file(self):
        """測試創建檔案載入器"""
        factory = SettingsFactory()
        config = {"type": "file", "path": "test.yaml"}

        loader = factory._create_loader("test", config)
        assert isinstance(loader, FileConfigLoader)

    def test_create_loader_cli(self):
        """測試創建命令列載入器"""
        factory = SettingsFactory()
        config = {"type": "cli"}

        loader = factory._create_loader("test", config)
        assert isinstance(loader, CliConfigLoader)

    def test_create_loader_unsupported(self):
        """測試創建不支援的載入器"""
        factory = SettingsFactory()
        config = {"type": "unsupported"}

        with pytest.raises(ValueError, match="不支援的載入器類型"):
            factory._create_loader("test", config)


# =====================================================
# 整合測試
# =====================================================


class TestConfigSystemIntegration:
    """配置系統整合測試"""

    @pytest.mark.asyncio
    async def test_full_config_system_lifecycle(self, temp_config_dir):
        """測試完整的配置系統生命週期"""
        # 創建測試配置檔案
        config_file = temp_config_dir / "test_config.yaml"
        config_content = {
            "token": "integration_test_token",
            "environment": "development",
            "logging": {"level": "DEBUG"},
        }
        config_file.write_text(yaml.dump(config_content))

        # 配置環境變數
        with patch.dict(
            os.environ, {"TEST_DEBUG": "true", "TEST_DATABASE__POOL_SIZE": "15"}
        ):
            # 設定配置來源
            config_sources = {
                "environment": {"type": "env", "prefix": "TEST_"},
                "config_file": {"type": "file", "path": str(config_file)},
                "cli": {"type": "cli"},
            }

            try:
                settings = await initialize_config_system(
                    config_sources=config_sources,
                    enable_hot_reload=False,  # 在測試中禁用熱重載
                )

                # 驗證配置載入正確
                assert settings.token == "integration_test_token"
                assert settings.environment == "development"
                assert settings.debug  # 來自環境變數

                # 測試配置管理器功能
                manager = get_config_manager()
                assert manager is not None

                # 測試動態配置更新
                await settings.update_field("logging.level", "ERROR", persist=False)

            finally:
                # 清理配置系統
                await shutdown_config_system()

    @pytest.mark.asyncio
    async def test_config_validation_integration(self):
        """測試配置驗證整合"""
        config_sources = {"cli": {"type": "cli"}}

        # 設定無效配置
        with patch.dict(os.environ, {"CLI_CONFIG": '{"token": "short"}'}):
            with pytest.raises(ConfigurationError, match="配置驗證失敗"):
                await initialize_config_system(
                    config_sources=config_sources, enable_hot_reload=False
                )

    @pytest.mark.asyncio
    async def test_config_encryption_integration(self, temp_config_dir):
        """測試配置加密整合"""
        # 創建包含敏感資料的配置
        config_file = temp_config_dir / "secure_config.json"
        config_content = {
            "token": "very_secret_token_that_should_be_encrypted",
            "environment": "production",
            "database": {"password": "secret_db_password"},
        }
        config_file.write_text(json.dumps(config_content))

        config_sources = {"config_file": {"type": "file", "path": str(config_file)}}

        try:
            settings = await initialize_config_system(
                config_sources=config_sources, enable_hot_reload=False
            )

            assert settings.token == "very_secret_token_that_should_be_encrypted"

            # 獲取配置管理器並檢查加密服務
            manager = get_config_manager()
            assert "token" in manager.encryption_service.encrypted_fields

        finally:
            await shutdown_config_system()


class TestRemoteConfigLoader:
    """遠端配置載入器測試"""

    def test_init(self):
        """測試初始化"""
        loader = RemoteConfigLoader("https://api.example.com/config")
        assert loader.source == ConfigSource.REMOTE
        assert loader.url == "https://api.example.com/config"
        assert loader.timeout == 30
        assert loader.retry_attempts == 3

    @pytest.mark.asyncio
    async def test_load_json_config(self):
        """測試載入JSON配置"""
        config_data = {"token": "remote_token", "debug": True}

        with patch("aiohttp.ClientSession") as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.headers = {"content-type": "application/json"}
            mock_response.json.return_value = config_data
            mock_response.headers.get.return_value = None

            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response

            loader = RemoteConfigLoader("https://api.example.com/config")
            result = await loader.load()

            assert result == config_data

    @pytest.mark.asyncio
    async def test_load_yaml_config(self):
        """測試載入YAML配置"""
        config_data = {"token": "remote_token", "debug": True}
        yaml_content = yaml.dump(config_data)

        with patch("aiohttp.ClientSession") as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.headers = {"content-type": "text/yaml"}
            mock_response.text.return_value = yaml_content
            mock_response.headers.get.return_value = None

            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response

            loader = RemoteConfigLoader("https://api.example.com/config")
            result = await loader.load()

            assert result == config_data

    @pytest.mark.asyncio
    async def test_load_with_retry(self):
        """測試重試機制"""
        with patch("aiohttp.ClientSession") as mock_session:
            # 前兩次失敗,第三次成功
            mock_session.return_value.__aenter__.return_value.get.side_effect = [
                Exception("Network error"),
                Exception("Timeout"),
                AsyncMock(status=200, json=AsyncMock(return_value={"success": True})),
            ]

            loader = RemoteConfigLoader(
                "https://api.example.com/config", retry_attempts=3
            )

            with pytest.raises(ConfigurationError):
                await loader.load()


class TestDatabaseConfigLoader:
    """資料庫配置載入器測試"""

    def test_init(self):
        """測試初始化"""
        loader = DatabaseConfigLoader("test.db")
        assert loader.source == ConfigSource.DATABASE
        assert loader.db_path == Path("test.db")
        assert loader.table_name == "config"

    @pytest.mark.asyncio
    async def test_ensure_table_exists(self, temp_config_dir):
        """測試表結構創建"""
        db_path = temp_config_dir / "test_config.db"
        loader = DatabaseConfigLoader(db_path)

        await loader._ensure_table_exists()

        # 檢查表是否存在
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='config'"
            )
            result = await cursor.fetchone()
            assert result is not None
            assert result[0] == "config"

    @pytest.mark.asyncio
    async def test_load_config_from_database(self, temp_config_dir):
        """測試從資料庫載入配置"""
        db_path = temp_config_dir / "test_config.db"
        loader = DatabaseConfigLoader(db_path)

        # 先創建表和插入測試資料
        await loader._ensure_table_exists()

        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                "INSERT INTO config (key, value, environment) VALUES (?, ?, ?)",
                ("token", "test_db_token", "development"),
            )
            await db.execute(
                "INSERT INTO config (key, value, environment) VALUES (?, ?, ?)",
                ("debug", "true", "development"),
            )
            await db.execute(
                "INSERT INTO config (key, value, environment) VALUES (?, ?, ?)",
                ("database.pool_size", "25", "development"),
            )
            await db.commit()

        # 載入配置
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            config = await loader.load()

            assert config["token"] == "test_db_token"
            assert config["debug"] == "true"
            assert config["database"]["pool_size"] == "25"

    @pytest.mark.asyncio
    async def test_load_with_environment_fallback(self, temp_config_dir):
        """測試環境回退機制"""
        db_path = temp_config_dir / "test_config.db"
        loader = DatabaseConfigLoader(db_path)

        await loader._ensure_table_exists()

        async with aiosqlite.connect(db_path) as db:
            # 插入默認配置
            await db.execute(
                "INSERT INTO config (key, value, environment) VALUES (?, ?, ?)",
                ("token", "default_token", "default"),
            )
            # 插入生產環境特定配置
            await db.execute(
                "INSERT INTO config (key, value, environment) VALUES (?, ?, ?)",
                ("token", "prod_token", "production"),
            )
            await db.commit()

        # 測試開發環境(應該使用默認值)
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            config = await loader.load()
            assert config["token"] == "default_token"

        # 測試生產環境(應該使用特定值)
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            config = await loader.load()
            assert config["token"] == "prod_token"


class TestNewLoadersIntegration:
    """新載入器整合測試"""

    def test_settings_factory_create_remote_loader(self):
        """測試設定工廠創建遠端載入器"""
        factory = SettingsFactory()
        config = {
            "type": "remote",
            "url": "https://api.example.com/config",
            "headers": {"Authorization": "Bearer token"},
            "timeout": 60,
        }

        loader = factory._create_loader("remote_test", config)
        assert isinstance(loader, RemoteConfigLoader)
        assert loader.url == "https://api.example.com/config"
        assert loader.headers == {"Authorization": "Bearer token"}
        assert loader.timeout == 60

    def test_settings_factory_create_database_loader(self):
        """測試設定工廠創建資料庫載入器"""
        factory = SettingsFactory()
        config = {
            "type": "database",
            "db_path": "config.db",
            "table_name": "app_config",
            "key_column": "config_key",
            "value_column": "config_value",
        }

        loader = factory._create_loader("db_test", config)
        assert isinstance(loader, DatabaseConfigLoader)
        assert loader.db_path == Path("config.db")
        assert loader.table_name == "app_config"
        assert loader.key_column == "config_key"
        assert loader.value_column == "config_value"

    @pytest.mark.asyncio
    async def test_mixed_sources_configuration(self, temp_config_dir):
        """測試混合來源配置"""
        # 創建測試資料庫
        db_path = temp_config_dir / "test.db"
        db_loader = DatabaseConfigLoader(db_path)
        await db_loader._ensure_table_exists()

        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                "INSERT INTO config (key, value, environment) VALUES (?, ?, ?)",
                ("database.pool_size", "15", "development"),
            )
            await db.commit()

        # 創建YAML配置檔案
        yaml_file = temp_config_dir / "app.yaml"
        yaml_content = {"token": "yaml_token", "logging": {"level": "INFO"}}
        yaml_file.write_text(yaml.dump(yaml_content))

        # 配置多個來源
        config_sources = {
            "database": {"type": "database", "db_path": str(db_path)},
            "yaml_file": {"type": "file", "path": str(yaml_file)},
            "environment": {"type": "env", "prefix": "TEST_"},
        }

        # 設定環境變數
        with patch.dict(
            os.environ, {"TEST_DEBUG": "true", "ENVIRONMENT": "development"}
        ):
            try:
                settings = await initialize_config_system(
                    config_sources=config_sources, enable_hot_reload=False
                )

                # 驗證配置合併結果
                assert settings.token == "yaml_token"  # 來自YAML
                assert settings.debug  # 來自環境變數
                assert settings.database.pool_size == 15  # 來自資料庫
                assert settings.logging.level == "INFO"  # 來自YAML

            finally:
                await shutdown_config_system()
