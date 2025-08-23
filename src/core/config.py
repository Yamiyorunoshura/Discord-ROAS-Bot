"""
Configuration Management System
Task ID: T2 - App architecture baseline and scaffolding

This module provides centralized configuration management for the roas-bot application.
It supports environment variables, configuration files, and environment-specific settings.
"""

import os
import json
import yaml
from typing import Any, Dict, Optional, Union, Type
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum

from .errors import ConfigurationError


class Environment(Enum):
    """Application environment types"""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class DatabaseConfig:
    """Database configuration settings"""
    url: str = "sqlite:///dbs/main.db"
    message_db_url: str = "sqlite:///dbs/message.db"
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    echo: bool = False


@dataclass 
class DiscordConfig:
    """Discord bot configuration settings"""
    token: str = ""
    command_prefix: str = "!"
    case_insensitive: bool = True
    strip_after_prefix: bool = True
    intents_message_content: bool = True
    intents_guilds: bool = True
    intents_members: bool = True
    activity_type: str = "playing"
    activity_name: str = "ROAS Bot v2.4.1"


@dataclass
class LoggingConfig:
    """Logging configuration settings"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_handler_enabled: bool = True
    console_handler_enabled: bool = True
    log_directory: str = "logs"
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    
    # Service-specific log files
    main_log_file: str = "main.log"
    error_log_file: str = "error.log"
    database_log_file: str = "database.log"
    achievement_log_file: str = "achievement.log"
    economy_log_file: str = "economy.log"
    government_log_file: str = "government.log"


@dataclass
class SecurityConfig:
    """Security configuration settings"""
    secret_key: str = ""
    encrypt_logs: bool = False
    sensitive_data_patterns: list = field(default_factory=lambda: [
        r'token',
        r'password',
        r'secret',
        r'key',
        r'auth'
    ])
    max_request_size: int = 1024 * 1024  # 1MB


@dataclass
class PerformanceConfig:
    """Performance tuning configuration"""
    cache_enabled: bool = True
    cache_ttl: int = 300  # 5 minutes
    max_concurrent_operations: int = 50
    request_timeout: int = 30
    retry_attempts: int = 3
    retry_delay: float = 1.0


@dataclass
class TestingConfig:
    """Testing configuration settings"""
    test_database_url: str = "sqlite:///:memory:"
    test_guild_id: Optional[int] = None
    test_user_id: Optional[int] = None
    cleanup_test_data: bool = True
    test_timeout: int = 60


@dataclass
class AppConfig:
    """Main application configuration"""
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False
    version: str = "2.4.1"
    
    # Component configurations
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    discord: DiscordConfig = field(default_factory=DiscordConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    testing: TestingConfig = field(default_factory=TestingConfig)


class ConfigManager:
    """
    Configuration manager for loading and managing application settings
    
    Supports multiple configuration sources in order of precedence:
    1. Environment variables
    2. Configuration files (JSON/YAML)
    3. Default values
    """
    
    def __init__(self, 
                 config_dir: Optional[Path] = None,
                 env_prefix: str = "ROAS_"):
        """
        Initialize the configuration manager
        
        Args:
            config_dir: Directory containing configuration files
            env_prefix: Prefix for environment variables
        """
        self.config_dir = config_dir or Path.cwd()
        self.env_prefix = env_prefix
        self._config: Optional[AppConfig] = None
        
    def load_config(self, 
                   environment: Optional[str] = None,
                   config_file: Optional[str] = None) -> AppConfig:
        """
        Load configuration from all sources
        
        Args:
            environment: Target environment (development, testing, production)
            config_file: Specific configuration file to load
            
        Returns:
            Loaded application configuration
        """
        if self._config is not None:
            return self._config
            
        try:
            # Start with default configuration
            config = AppConfig()
            
            # Determine environment
            env_name = (environment or 
                       os.getenv(f"{self.env_prefix}ENVIRONMENT", "development"))
            
            try:
                config.environment = Environment(env_name.lower())
            except ValueError:
                raise ConfigurationError(
                    "environment",
                    f"Invalid environment: {env_name}"
                )
            
            # Load from configuration file if specified or found
            config_file_path = self._find_config_file(config_file, config.environment)
            if config_file_path:
                file_config = self._load_config_file(config_file_path)
                config = self._merge_config(config, file_config)
                
            # Override with environment variables
            config = self._load_from_environment(config)
            
            # Validate configuration
            self._validate_config(config)
            
            # Cache the loaded configuration
            self._config = config
            
            return config
            
        except Exception as e:
            if isinstance(e, ConfigurationError):
                raise
            raise ConfigurationError(
                "config_loading",
                f"Failed to load configuration: {str(e)}",
                cause=e
            )
            
    def _find_config_file(self, 
                         config_file: Optional[str],
                         environment: Environment) -> Optional[Path]:
        """Find the appropriate configuration file"""
        if config_file:
            path = Path(config_file)
            if not path.is_absolute():
                path = self.config_dir / path
            return path if path.exists() else None
            
        # Look for environment-specific config files
        possible_files = [
            f"config.{environment.value}.json",
            f"config.{environment.value}.yml",
            f"config.{environment.value}.yaml",
            "config.json",
            "config.yml", 
            "config.yaml",
        ]
        
        for filename in possible_files:
            path = self.config_dir / filename
            if path.exists():
                return path
                
        return None
        
    def _load_config_file(self, config_file: Path) -> Dict[str, Any]:
        """Load configuration from a file"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                if config_file.suffix.lower() in ['.yml', '.yaml']:
                    return yaml.safe_load(f) or {}
                elif config_file.suffix.lower() == '.json':
                    return json.load(f) or {}
                else:
                    raise ConfigurationError(
                        "config_file_format",
                        f"Unsupported configuration file format: {config_file.suffix}"
                    )
        except Exception as e:
            raise ConfigurationError(
                "config_file_read",
                f"Failed to read configuration file {config_file}: {str(e)}",
                cause=e
            )
            
    def _merge_config(self, base_config: AppConfig, file_config: Dict[str, Any]) -> AppConfig:
        """Merge file configuration into base configuration"""
        # This is a simplified merge - in production you might want more sophisticated merging
        for key, value in file_config.items():
            if hasattr(base_config, key):
                if isinstance(value, dict) and hasattr(getattr(base_config, key), '__dict__'):
                    # Merge nested configuration objects
                    nested_config = getattr(base_config, key)
                    for nested_key, nested_value in value.items():
                        if hasattr(nested_config, nested_key):
                            setattr(nested_config, nested_key, nested_value)
                else:
                    setattr(base_config, key, value)
                    
        return base_config
        
    def _load_from_environment(self, config: AppConfig) -> AppConfig:
        """Load configuration values from environment variables"""
        env_mappings = {
            # Database configuration
            f"{self.env_prefix}DATABASE_URL": ("database", "url"),
            f"{self.env_prefix}MESSAGE_DB_URL": ("database", "message_db_url"),
            f"{self.env_prefix}DB_POOL_SIZE": ("database", "pool_size", int),
            f"{self.env_prefix}DB_ECHO": ("database", "echo", bool),
            
            # Discord configuration
            f"{self.env_prefix}DISCORD_TOKEN": ("discord", "token"),
            f"{self.env_prefix}COMMAND_PREFIX": ("discord", "command_prefix"),
            f"{self.env_prefix}ACTIVITY_NAME": ("discord", "activity_name"),
            
            # Logging configuration
            f"{self.env_prefix}LOG_LEVEL": ("logging", "level"),
            f"{self.env_prefix}LOG_DIRECTORY": ("logging", "log_directory"),
            f"{self.env_prefix}LOG_FILE_ENABLED": ("logging", "file_handler_enabled", bool),
            f"{self.env_prefix}LOG_CONSOLE_ENABLED": ("logging", "console_handler_enabled", bool),
            
            # Security configuration
            f"{self.env_prefix}SECRET_KEY": ("security", "secret_key"),
            f"{self.env_prefix}ENCRYPT_LOGS": ("security", "encrypt_logs", bool),
            
            # Performance configuration
            f"{self.env_prefix}CACHE_ENABLED": ("performance", "cache_enabled", bool),
            f"{self.env_prefix}CACHE_TTL": ("performance", "cache_ttl", int),
            f"{self.env_prefix}MAX_CONCURRENT_OPERATIONS": ("performance", "max_concurrent_operations", int),
            
            # General settings
            f"{self.env_prefix}DEBUG": ("debug", None, bool),
            f"{self.env_prefix}VERSION": ("version", None),
        }
        
        for env_var, mapping in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                try:
                    # Parse the mapping
                    if len(mapping) == 2:
                        section, attr = mapping
                        converter = str
                    else:
                        section, attr, converter = mapping
                        
                    # Convert the value
                    if converter == bool:
                        converted_value = value.lower() in ('true', '1', 'yes', 'on')
                    elif converter == int:
                        converted_value = int(value)
                    else:
                        converted_value = value
                        
                    # Set the configuration value
                    if attr is None:
                        # Direct attribute on config
                        setattr(config, section, converted_value)
                    else:
                        # Nested attribute
                        nested_config = getattr(config, section)
                        setattr(nested_config, attr, converted_value)
                        
                except (ValueError, AttributeError) as e:
                    raise ConfigurationError(
                        env_var,
                        f"Invalid value for environment variable {env_var}: {value}",
                        cause=e
                    )
                    
        return config
        
    def _validate_config(self, config: AppConfig) -> None:
        """Validate the loaded configuration"""
        validations = [
            # Discord token is required for production
            (
                config.environment == Environment.PRODUCTION and not config.discord.token,
                "discord.token",
                "Discord token is required for production environment"
            ),
            
            # Secret key is required for production
            (
                config.environment == Environment.PRODUCTION and not config.security.secret_key,
                "security.secret_key",
                "Secret key is required for production environment"
            ),
            
            # Log directory should be writable
            (
                not os.path.exists(config.logging.log_directory) and 
                not self._create_directory(config.logging.log_directory),
                "logging.log_directory",
                f"Cannot create log directory: {config.logging.log_directory}"
            ),
        ]
        
        for condition, field, message in validations:
            if condition:
                raise ConfigurationError(field, message)
                
    def _create_directory(self, directory: str) -> bool:
        """Try to create a directory"""
        try:
            os.makedirs(directory, exist_ok=True)
            return True
        except (OSError, PermissionError):
            return False
            
    def get_config(self) -> AppConfig:
        """Get the current configuration"""
        if self._config is None:
            raise ConfigurationError(
                "config_not_loaded",
                "Configuration not loaded. Call load_config() first."
            )
        return self._config
        
    def reload_config(self) -> AppConfig:
        """Reload configuration from sources"""
        self._config = None
        return self.load_config()


# Global configuration manager instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """Get the global configuration manager instance"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def get_config() -> AppConfig:
    """Get the current application configuration"""
    return get_config_manager().get_config()


def load_config(**kwargs) -> AppConfig:
    """Load application configuration with optional parameters"""
    return get_config_manager().load_config(**kwargs)