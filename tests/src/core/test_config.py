"""
Unit tests for src.core.config module
Task ID: T2 - App architecture baseline and scaffolding
"""

import pytest
import os
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open

from src.core.config import (
    Environment, AppConfig, DatabaseConfig, DiscordConfig,
    LoggingConfig, SecurityConfig, PerformanceConfig, TestingConfig,
    ConfigManager, get_config_manager, get_config, load_config
)
from src.core.errors import ConfigurationError


class TestEnvironment:
    """Test the Environment enum"""
    
    def test_environment_values(self):
        """Test environment enum values"""
        assert Environment.DEVELOPMENT.value == "development"
        assert Environment.TESTING.value == "testing"
        assert Environment.STAGING.value == "staging"
        assert Environment.PRODUCTION.value == "production"


class TestConfigClasses:
    """Test the configuration dataclasses"""
    
    def test_database_config_defaults(self):
        """Test DatabaseConfig default values"""
        config = DatabaseConfig()
        
        assert config.url == "sqlite:///dbs/main.db"
        assert config.message_db_url == "sqlite:///dbs/message.db"
        assert config.pool_size == 10
        assert config.echo is False
        
    def test_discord_config_defaults(self):
        """Test DiscordConfig default values"""
        config = DiscordConfig()
        
        assert config.command_prefix == "!"
        assert config.case_insensitive is True
        assert config.intents_message_content is True
        
    def test_logging_config_defaults(self):
        """Test LoggingConfig default values"""
        config = LoggingConfig()
        
        assert config.level == "INFO"
        assert config.file_handler_enabled is True
        assert config.log_directory == "logs"
        assert config.main_log_file == "main.log"
        
    def test_app_config_defaults(self):
        """Test AppConfig default values"""
        config = AppConfig()
        
        assert config.environment == Environment.DEVELOPMENT
        assert config.debug is False
        assert config.version == "2.4.1"
        assert isinstance(config.database, DatabaseConfig)
        assert isinstance(config.discord, DiscordConfig)


class TestConfigManager:
    """Test the ConfigManager class"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_manager = ConfigManager(config_dir=Path(self.temp_dir))
        
    def test_initialization(self):
        """Test ConfigManager initialization"""
        manager = ConfigManager()
        
        assert manager.env_prefix == "ROAS_"
        assert manager._config is None
        
    def test_load_config_defaults(self):
        """Test loading config with defaults"""
        config = self.config_manager.load_config()
        
        assert isinstance(config, AppConfig)
        assert config.environment == Environment.DEVELOPMENT
        assert config.version == "2.4.1"
        
    @patch.dict(os.environ, {"ROAS_ENVIRONMENT": "production"})
    def test_load_config_from_environment_var(self):
        """Test loading config with environment variable"""
        config = self.config_manager.load_config()
        
        assert config.environment == Environment.PRODUCTION
        
    def test_load_config_invalid_environment(self):
        """Test loading config with invalid environment"""
        with pytest.raises(ConfigurationError) as exc_info:
            self.config_manager.load_config(environment="invalid")
            
        assert "Invalid environment" in str(exc_info.value)
        
    def test_load_config_with_json_file(self):
        """Test loading config from JSON file"""
        config_data = {
            "debug": True,
            "discord": {
                "command_prefix": "?"
            }
        }
        
        config_file = Path(self.temp_dir) / "config.json"
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
            
        config = self.config_manager.load_config()
        
        assert config.debug is True
        assert config.discord.command_prefix == "?"
        
    @patch.dict(os.environ, {
        "ROAS_DISCORD_TOKEN": "test_token",
        "ROAS_DATABASE_URL": "sqlite:///test.db",
        "ROAS_LOG_LEVEL": "DEBUG",
        "ROAS_DEBUG": "true"
    })
    def test_load_config_from_environment_variables(self):
        """Test loading config from environment variables"""
        config = self.config_manager.load_config()
        
        assert config.discord.token == "test_token"
        assert config.database.url == "sqlite:///test.db"
        assert config.logging.level == "DEBUG"
        assert config.debug is True
        
    def test_find_config_file_specific(self):
        """Test finding specific config file"""
        config_file = Path(self.temp_dir) / "custom.json"
        config_file.write_text('{"debug": true}')
        
        found_file = self.config_manager._find_config_file("custom.json", Environment.DEVELOPMENT)
        
        assert found_file == config_file
        
    def test_find_config_file_environment_specific(self):
        """Test finding environment-specific config file"""
        config_file = Path(self.temp_dir) / "config.development.json"
        config_file.write_text('{"debug": true}')
        
        found_file = self.config_manager._find_config_file(None, Environment.DEVELOPMENT)
        
        assert found_file == config_file
        
    def test_find_config_file_not_found(self):
        """Test finding non-existent config file"""
        found_file = self.config_manager._find_config_file("nonexistent.json", Environment.DEVELOPMENT)
        
        assert found_file is None
        
    def test_load_config_file_json(self):
        """Test loading JSON config file"""
        config_data = {"debug": True, "version": "test"}
        config_file = Path(self.temp_dir) / "config.json"
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f)
            
        loaded_data = self.config_manager._load_config_file(config_file)
        
        assert loaded_data == config_data
        
    def test_load_config_file_invalid_format(self):
        """Test loading config file with invalid format"""
        config_file = Path(self.temp_dir) / "config.txt"
        config_file.write_text("not a config file")
        
        with pytest.raises(ConfigurationError) as exc_info:
            self.config_manager._load_config_file(config_file)
            
        assert "Unsupported configuration file format" in str(exc_info.value)
        
    def test_load_config_file_read_error(self):
        """Test loading non-existent config file"""
        config_file = Path(self.temp_dir) / "nonexistent.json"
        
        with pytest.raises(ConfigurationError) as exc_info:
            self.config_manager._load_config_file(config_file)
            
        assert "Failed to read configuration file" in str(exc_info.value)
        
    def test_merge_config(self):
        """Test merging file config into base config"""
        base_config = AppConfig()
        file_config = {
            "debug": True,
            "discord": {
                "command_prefix": "?",
                "case_insensitive": False
            }
        }
        
        merged_config = self.config_manager._merge_config(base_config, file_config)
        
        assert merged_config.debug is True
        assert merged_config.discord.command_prefix == "?"
        assert merged_config.discord.case_insensitive is False
        # Other discord config should remain default
        assert merged_config.discord.intents_message_content is True
        
    def test_validate_config_production_missing_token(self):
        """Test config validation for production without Discord token"""
        config = AppConfig()
        config.environment = Environment.PRODUCTION
        config.discord.token = ""
        
        with pytest.raises(ConfigurationError) as exc_info:
            self.config_manager._validate_config(config)
            
        assert "Discord token is required" in str(exc_info.value)
        
    def test_validate_config_production_missing_secret(self):
        """Test config validation for production without secret key"""
        config = AppConfig()
        config.environment = Environment.PRODUCTION
        config.discord.token = "test_token"
        config.security.secret_key = ""
        
        with pytest.raises(ConfigurationError) as exc_info:
            self.config_manager._validate_config(config)
            
        assert "Secret key is required" in str(exc_info.value)
        
    def test_get_config_not_loaded(self):
        """Test getting config before loading"""
        manager = ConfigManager()
        
        with pytest.raises(ConfigurationError) as exc_info:
            manager.get_config()
            
        assert "Configuration not loaded" in str(exc_info.value)
        
    def test_reload_config(self):
        """Test reloading configuration"""
        # Load initial config
        config1 = self.config_manager.load_config()
        
        # Reload config
        config2 = self.config_manager.reload_config()
        
        # Should be different instances but same values
        assert config1 is not config2
        assert config1.version == config2.version


class TestGlobalFunctions:
    """Test the global configuration functions"""
    
    def test_get_config_manager(self):
        """Test getting global config manager"""
        manager1 = get_config_manager()
        manager2 = get_config_manager()
        
        # Should return same instance (singleton-like behavior)
        assert manager1 is manager2
        
    @patch('src.core.config._config_manager', None)
    def test_load_config_global(self):
        """Test loading config through global function"""
        config = load_config()
        
        assert isinstance(config, AppConfig)
        
    def test_get_config_global_not_loaded(self):
        """Test getting config through global function when not loaded"""
        # This might raise ConfigurationError depending on implementation
        # The exact behavior depends on how the global config manager is initialized