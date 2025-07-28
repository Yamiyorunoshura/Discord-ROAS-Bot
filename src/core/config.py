"""Modern configuration management using Pydantic Settings.

企業級統一配置管理系統,支援:
- 多來源配置載入 (環境變數、檔案、命令列、資料庫、遠端)
- 配置熱重載機制 (檔案監控、防抖機制、變更通知)
- 配置驗證和錯誤處理
- 敏感配置加密存儲
- 配置合併引擎和多種合併策略
- 配置變更監聽和審計追蹤
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    TypeVar,
)

import yaml
from cryptography.fernet import Fernet
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_app_data_dir(app_name: str = "DiscordADRBot") -> Path:
    """獲取應用程式數據目錄，跨平台支援
    
    Windows: %APPDATA%\\AppName
    Linux: ~/.local/share/AppName  
    macOS: ~/Library/Application Support/AppName
    
    Args:
        app_name: 應用程式名稱
        
    Returns:
        應用程式數據目錄路徑
    """
    if os.name == "nt":  # Windows
        base_dir = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":  # macOS
        base_dir = Path.home() / "Library" / "Application Support"
    else:  # Linux and others
        base_dir = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    
    app_dir = base_dir / app_name
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir
from watchfiles import awatch

if TYPE_CHECKING:
    from collections.abc import Callable

# 嘗試導入toml,如果沒有則設為None
try:
    import toml
except ImportError:
    toml = None

T = TypeVar("T")


class DatabaseSettings(BaseSettings):
    """Database configuration settings."""

    model_config = SettingsConfigDict(
        env_prefix="DB_", case_sensitive=False, extra="ignore"
    )

    # SQLite settings
    sqlite_path: Path = Field(
        default_factory=lambda: get_app_data_dir() / "databases", 
        description="Directory for SQLite database files"
    )

    # Connection pool settings
    pool_size: int = Field(
        default=10, ge=1, le=50, description="Database connection pool size"
    )

    max_overflow: int = Field(
        default=20, ge=0, le=100, description="Maximum connection pool overflow"
    )

    pool_timeout: int = Field(
        default=30, ge=1, le=300, description="Connection pool timeout in seconds"
    )

    # Query settings
    query_timeout: int = Field(
        default=30, ge=1, le=300, description="Database query timeout in seconds"
    )

    enable_wal_mode: bool = Field(
        default=True, description="Enable SQLite WAL mode for better concurrency"
    )


class CacheSettings(BaseSettings):
    """Cache configuration settings."""

    model_config = SettingsConfigDict(
        env_prefix="CACHE_", case_sensitive=False, extra="ignore"
    )

    # Memory cache settings
    default_ttl: int = Field(
        default=300, ge=1, le=86400, description="Default cache TTL in seconds"
    )

    max_size: int = Field(
        default=1000, ge=10, le=100000, description="Maximum cache size"
    )

    # Redis settings (if using external cache)
    redis_url: str | None = Field(
        default=None, description="Redis URL for distributed caching"
    )

    redis_prefix: str = Field(default="adr_bot:", description="Redis key prefix")


class LoggingSettings(BaseSettings):
    """Logging configuration settings."""

    model_config = SettingsConfigDict(
        env_prefix="LOG_", case_sensitive=False, extra="ignore"
    )

    # Basic logging settings
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="Logging level"
    )

    format: Literal["json", "text", "colored"] = Field(
        default="colored", description="Log output format"
    )

    # File logging
    file_enabled: bool = Field(default=True, description="Enable file logging")

    file_path: Path = Field(
        default_factory=lambda: get_app_data_dir() / "logs", 
        description="Directory for log files"
    )

    file_max_size: int = Field(
        default=10, ge=1, le=100, description="Maximum log file size in MB"
    )

    file_backup_count: int = Field(
        default=5, ge=1, le=50, description="Number of backup log files to keep"
    )

    # Console logging
    console_enabled: bool = Field(default=True, description="Enable console logging")


class SecuritySettings(BaseSettings):
    """Security and authentication settings."""

    model_config = SettingsConfigDict(
        env_prefix="SECURITY_", case_sensitive=False, extra="ignore"
    )

    # Rate limiting
    rate_limit_enabled: bool = Field(default=True, description="Enable rate limiting")

    rate_limit_requests: int = Field(
        default=100, ge=1, le=10000, description="Rate limit requests per window"
    )

    rate_limit_window: int = Field(
        default=60, ge=1, le=3600, description="Rate limit window in seconds"
    )

    # Command permissions
    admin_role_ids: list[int] = Field(
        default_factory=list, description="List of admin role IDs"
    )

    moderator_role_ids: list[int] = Field(
        default_factory=list, description="List of moderator role IDs"
    )

    # Bot permissions
    required_permissions: int = Field(
        default=8,  # Administrator
        description="Required bot permissions",
    )


class PerformanceSettings(BaseSettings):
    """Performance and optimization settings."""

    model_config = SettingsConfigDict(
        env_prefix="PERF_", case_sensitive=False, extra="ignore"
    )

    # Async settings
    max_workers: int = Field(
        default=4, ge=1, le=32, description="Maximum number of worker threads"
    )

    event_loop_policy: Literal["default", "uvloop"] = Field(
        default="uvloop" if os.name != "nt" else "default",
        description="Event loop policy to use",
    )

    # Concurrency limits
    max_concurrent_tasks: int = Field(
        default=100, ge=1, le=1000, description="Maximum concurrent async tasks"
    )

    # Memory management
    gc_threshold: int = Field(
        default=1000, ge=100, le=10000, description="Garbage collection threshold"
    )

    # Monitoring
    metrics_enabled: bool = Field(
        default=True, description="Enable performance metrics collection"
    )

    health_check_interval: int = Field(
        default=30, ge=5, le=300, description="Health check interval in seconds"
    )


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        frozen=True,  # Make settings immutable
    )

    # Basic Discord bot settings
    token: str = Field(..., min_length=50, description="Discord bot token")

    command_prefix: str = Field(
        default="!",
        min_length=1,
        max_length=5,
        description="Command prefix for text commands",
    )

    # Environment settings
    environment: Literal["development", "staging", "production"] = Field(
        default="development", description="Application environment"
    )

    debug: bool = Field(default=False, description="Enable debug mode")

    # Application metadata
    app_name: str = Field(default="Discord ADR Bot", description="Application name")

    app_version: str = Field(default="2.0.0", description="Application version")

    # Project paths
    project_root: Path = Field(
        default_factory=lambda: Path(__file__).parent.parent.parent,
        description="Project root directory",
    )

    # 靜態資源目錄（專案內）
    assets_dir: Path = Field(
        default_factory=lambda: Path(__file__).parent.parent / "assets",
        description="Static assets directory (fonts, default backgrounds)"
    )

    # 用戶數據目錄（專案外）
    data_dir: Path = Field(
        default_factory=lambda: get_app_data_dir() / "data", 
        description="User data directory"
    )

    # Feature flags
    features: dict[str, bool] = Field(
        default_factory=lambda: {
            "activity_meter": True,
            "message_listener": True,
            "protection": True,
            "welcome": True,
            "sync_data": True,
            "performance_dashboard": True,
        },
        description="Feature flags for enabling/disabling modules",
    )

    # Nested configuration sections
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    performance: PerformanceSettings = Field(default_factory=PerformanceSettings)

    @field_validator("token")
    @classmethod
    def validate_token(cls, v: str) -> str:
        """Validate Discord bot token format."""
        if not v or len(v) < 10:
            raise ValueError("Invalid Discord bot token format")
        # Discord bot tokens typically start with MTI, OTk, MTA, MTM, etc. or Bot
        # More flexible validation: check for basic token structure
        if v.startswith("Bot "):
            # Bot token format: "Bot actual_token"
            return v
        elif "." in v and len(v.split(".")) >= 3:
            # Standard Discord token format: user_id.timestamp.hmac
            return v
        else:
            raise ValueError("Invalid Discord bot token format")
        return v

    @field_validator("project_root")
    @classmethod
    def validate_project_root(cls, v: Path) -> Path:
        """Ensure project root exists."""
        if not v.exists():
            raise ValueError(f"Project root directory does not exist: {v}")
        return v
    
    @field_validator("assets_dir")
    @classmethod
    def validate_assets_dir(cls, v: Path) -> Path:
        """Ensure assets directory exists."""
        if not v.exists():
            raise ValueError(f"Assets directory does not exist: {v}")
        return v
    
    @field_validator("data_dir")
    @classmethod
    def validate_data_dir(cls, v: Path) -> Path:
        """Ensure data directory exists."""
        v.mkdir(parents=True, exist_ok=True)
        return v

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment == "production"

    @property
    def log_level_int(self) -> int:
        """Get numeric log level."""
        import logging

        return getattr(logging, self.logging.level)

    def get_database_url(self, db_name: str) -> str:
        """Get database URL for a specific database."""
        db_path = self.database.sqlite_path / f"{db_name}.db"
        return f"sqlite:///{db_path}"
    
    def get_database_path(self, db_name: str) -> Path:
        """Get database file path for a specific database."""
        db_path = self.database.sqlite_path / f"{db_name}.db"
        # 確保資料庫目錄存在
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return db_path

    def get_log_file_path(self, log_name: str) -> Path:
        """Get log file path for a specific logger."""
        return self.logging.file_path / f"{log_name}.log"

    def is_feature_enabled(self, feature: str) -> bool:
        """Check if a feature is enabled."""
        return self.features.get(feature, False)
    
    def get_font_path(self, font_name: str) -> Path:
        """Get font file path from assets directory."""
        return self.assets_dir / "fonts" / font_name
    
    def get_default_background_path(self, bg_name: str) -> Path:
        """Get default background path from assets directory."""
        return self.assets_dir / "backgrounds" / bg_name


# Global settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """Reload settings from environment."""
    global _settings
    _settings = Settings()
    return _settings


# =====================================================
# 配置來源系統 (Config Sources System)
# =====================================================


class ConfigSource(Enum):
    """配置來源優先級 (數字越小優先級越高)"""

    COMMAND_LINE = 1  # 最高優先級
    ENVIRONMENT = 2  # 環境變數
    CONFIG_FILE = 3  # 設定檔案
    DATABASE = 4  # 資料庫配置
    REMOTE = 5  # 遠端配置
    DEFAULT = 6  # 預設值


class ConfigurationError(Exception):
    """配置錯誤異常"""

    pass


class ConfigLoader(ABC):
    """配置載入器抽象基類

    所有配置載入器都應繼承此類並實作相應方法.
    提供統一的配置載入、變更檢測和監控介面.
    """

    def __init__(self, source: ConfigSource):
        """初始化配置載入器

        Args:
            source: 配置來源類型
        """
        self.source = source
        self.last_modified = 0
        self.checksum = ""
        self._logger = None

    @property
    def logger(self):
        """延遲載入logger"""
        if self._logger is None:
            # 避免循環導入,延遲載入logger
            try:
                from src.core.logger import get_logger

                self._logger = get_logger(f"config_loader_{self.source.name.lower()}")
            except ImportError:
                import logging

                self._logger = logging.getLogger(
                    f"config_loader_{self.source.name.lower()}"
                )
        return self._logger

    @abstractmethod
    async def load(self) -> dict[str, Any]:
        """載入配置資料

        Returns:
            配置資料字典

        Raises:
            ConfigurationError: 配置載入失敗
        """
        pass

    @abstractmethod
    async def is_changed(self) -> bool:
        """檢查配置是否已變更

        Returns:
            如果配置已變更返回True
        """
        pass

    @abstractmethod
    async def watch(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """監控配置變更

        Args:
            callback: 配置變更時的回調函數
        """
        pass


class EnvironmentConfigLoader(ConfigLoader):
    """環境變數配置載入器

    支援嵌套配置結構,使用雙底線 (__) 作為分隔符.
    例如:BOT_DATABASE__POOL_SIZE -> {"database": {"pool_size": value}}
    """

    def __init__(self, prefix: str = ""):
        """初始化環境變數載入器

        Args:
            prefix: 環境變數前綴,如 "BOT_"
        """
        super().__init__(ConfigSource.ENVIRONMENT)
        self.prefix = prefix

    async def load(self) -> dict[str, Any]:
        """載入環境變數配置"""
        config = {}

        try:
            for key, value in os.environ.items():
                if self.prefix and not key.startswith(self.prefix):
                    continue

                # 移除前綴
                clean_key = key[len(self.prefix) :] if self.prefix else key
                clean_key = clean_key.lower()

                # 轉換嵌套結構
                self._set_nested_value(config, clean_key, self._convert_value(value))

            self.logger.debug(
                f"載入環境變數配置:{len(config)} 項 (前綴: {self.prefix or 'None'})"
            )
            return config

        except Exception as e:
            raise ConfigurationError(f"載入環境變數配置失敗: {e}")

    def _set_nested_value(self, config: dict, key: str, value: Any):
        """設定嵌套配置值"""
        parts = key.split("__")  # 使用 __ 作為嵌套分隔符
        current = config

        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            elif not isinstance(current[part], dict):
                # 如果已存在非字典值,跳過
                return
            current = current[part]

        current[parts[-1]] = value

    def _convert_value(self, value: str) -> Any:
        """轉換配置值類型"""
        if not isinstance(value, str):
            return value

        # 布林值
        if value.lower() in ("true", "false"):
            return value.lower() == "true"

        # 數字
        try:
            if "." in value:
                return float(value)
            return int(value)
        except ValueError:
            pass

        # JSON 值
        if value.startswith(("{", "[")):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                pass

        # 逗號分隔的列表
        if "," in value and not value.startswith(("{", "[", '"', "'")):
            return [item.strip() for item in value.split(",")]

        return value

    async def is_changed(self) -> bool:
        """環境變數變更檢測 (簡化實作)"""
        # 環境變數在程序運行期間通常不變
        return False

    async def watch(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """環境變數監控 (簡化實作)"""
        # 環境變數通常不需要監控
        pass


class FileConfigLoader(ConfigLoader):
    """檔案配置載入器

    支援多種檔案格式:.env, .yaml, .yml, .json, .toml
    提供檔案變更檢測和監控功能.
    """

    def __init__(self, file_path: Path):
        """初始化檔案配置載入器

        Args:
            file_path: 配置檔案路徑
        """
        super().__init__(ConfigSource.CONFIG_FILE)
        self.file_path = Path(file_path)
        self._file_loaders = {
            ".env": self._load_env,
            ".yaml": self._load_yaml,
            ".yml": self._load_yaml,
            ".json": self._load_json,
            ".toml": self._load_toml,
        }

    async def load(self) -> dict[str, Any]:
        """載入檔案配置"""
        if not self.file_path.exists():
            self.logger.debug(f"配置檔案不存在: {self.file_path}")
            return {}

        # 特殊處理 .env 文件
        if self.file_path.name == ".env":
            suffix = ".env"
        else:
            suffix = self.file_path.suffix.lower()

        loader = self._file_loaders.get(suffix)

        if not loader:
            raise ConfigurationError(f"不支援的配置檔案格式: {suffix}")

        try:
            with open(self.file_path, encoding="utf-8") as f:
                content = f.read()

            config = loader(content)

            # 更新檢查資訊
            self.last_modified = self.file_path.stat().st_mtime
            self.checksum = hashlib.md5(content.encode()).hexdigest()

            self.logger.debug(f"載入配置檔案: {self.file_path} ({len(config)} 項)")
            return config

        except Exception as e:
            raise ConfigurationError(f"載入配置檔案失敗 {self.file_path}: {e}")

    def _load_env(self, content: str) -> dict[str, Any]:
        """載入 .env 檔案"""
        config = {}
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip("\"'")

                # 嵌套結構支援
                self._set_nested_value(config, key.lower(), self._convert_value(value))

        return config

    def _load_yaml(self, content: str) -> dict[str, Any]:
        """載入 YAML 檔案"""
        return yaml.safe_load(content) or {}

    def _load_json(self, content: str) -> dict[str, Any]:
        """載入 JSON 檔案"""
        return json.loads(content)

    def _load_toml(self, content: str) -> dict[str, Any]:
        """載入 TOML 檔案"""
        if toml is None:
            raise ConfigurationError("TOML 支援需要安裝 toml 套件: pip install toml")
        return toml.loads(content)

    def _set_nested_value(self, config: dict, key: str, value: str):
        """設定嵌套配置值"""
        parts = key.split("__")
        current = config

        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            elif not isinstance(current[part], dict):
                return
            current = current[part]

        current[parts[-1]] = self._convert_value(value)

    def _convert_value(self, value: str) -> Any:
        """轉換配置值類型"""
        if not isinstance(value, str):
            return value

        if value.lower() in ("true", "false"):
            return value.lower() == "true"

        try:
            if "." in value:
                return float(value)
            return int(value)
        except ValueError:
            pass

        return value

    async def is_changed(self) -> bool:
        """檢查檔案是否已變更"""
        if not self.file_path.exists():
            return self.last_modified != 0

        try:
            current_modified = self.file_path.stat().st_mtime
            return current_modified != self.last_modified
        except OSError:
            return False

    async def watch(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """監控檔案變更"""
        if not self.file_path.exists():
            self.logger.warning(f"無法監控不存在的檔案: {self.file_path}")
            return

        try:
            async for changes in awatch(self.file_path.parent):
                for _change_type, changed_path in changes:
                    if Path(changed_path) == self.file_path:
                        try:
                            self.logger.info(f"檢測到配置檔案變更: {self.file_path}")
                            new_config = await self.load()
                            await callback(new_config)
                        except Exception as e:
                            self.logger.error(f"配置檔案重載失敗: {e}")
        except Exception as e:
            self.logger.error(f"檔案監控失敗: {e}")


class CliConfigLoader(ConfigLoader):
    """命令列參數配置載入器

    使用 Typer 框架解析命令列參數,支援嵌套配置結構.
    """

    def __init__(self):
        """初始化命令列參數載入器"""
        super().__init__(ConfigSource.COMMAND_LINE)
        self.config_data = {}
        self._parsed = False

    def parse_args(self, args: list[str] | None = None):
        """解析命令列參數

        Args:
            args: 命令列參數列表,None則使用sys.argv
        """
        if self._parsed:
            return

        # 這裡可以根據需要實作命令列參數解析
        # 簡化實作,從環境變數或其他來源獲取CLI配置
        cli_config = os.environ.get("CLI_CONFIG")
        if cli_config:
            try:
                self.config_data = json.loads(cli_config)
            except json.JSONDecodeError:
                self.logger.warning("CLI_CONFIG 格式錯誤,跳過命令列配置")

        self._parsed = True

    async def load(self) -> dict[str, Any]:
        """載入命令列配置"""
        if not self._parsed:
            self.parse_args()

        self.logger.debug(f"載入命令列配置:{len(self.config_data)} 項")
        return self.config_data.copy()

    async def is_changed(self) -> bool:
        """命令列參數不會在運行時變更"""
        return False

    async def watch(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """命令列參數不需要監控"""
        pass


class RemoteConfigLoader(ConfigLoader):
    """遠端配置載入器

    支援從HTTP API載入配置,提供重試機制和錯誤處理.
    """

    def __init__(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        timeout: int = 30,
        retry_attempts: int = 3,
    ):
        """初始化遠端配置載入器

        Args:
            url: 配置API的URL
            headers: HTTP請求標頭
            timeout: 請求超時時間(秒)
            retry_attempts: 重試次數
        """
        super().__init__(ConfigSource.REMOTE)
        self.url = url
        self.headers = headers or {}
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.last_etag = None
        self.last_modified_header = None

    async def load(self) -> dict[str, Any]:
        """載入遠端配置"""
        import aiohttp

        for attempt in range(self.retry_attempts):
            try:
                async with (
                    aiohttp.ClientSession(
                        timeout=aiohttp.ClientTimeout(total=self.timeout)
                    ) as session,
                    session.get(self.url, headers=self.headers) as response,
                ):
                    if response.status == 200:
                        # 更新快取標頭
                        self.last_etag = response.headers.get("ETag")
                        self.last_modified_header = response.headers.get(
                            "Last-Modified"
                        )

                        # 解析響應
                        content_type = response.headers.get("content-type", "").lower()

                        if "application/json" in content_type:
                            config_data = await response.json()
                        elif (
                            "application/x-yaml" in content_type
                            or "text/yaml" in content_type
                        ):
                            text = await response.text()
                            config_data = yaml.safe_load(text) or {}
                        else:
                            # 嘗試JSON解析
                            try:
                                config_data = await response.json()
                            except:
                                text = await response.text()
                                config_data = yaml.safe_load(text) or {}

                        self.logger.info(
                            f"載入遠端配置成功: {self.url} ({len(config_data)} 項)"
                        )
                        return config_data
                    elif response.status == 304:
                        # 未修改,返回空配置
                        self.logger.debug(f"遠端配置未修改: {self.url}")
                        return {}
                    else:
                        raise ConfigurationError(
                            f"遠端配置載入失敗: HTTP {response.status}"
                        )

            except Exception as e:
                if attempt == self.retry_attempts - 1:
                    self.logger.error(f"遠端配置載入失敗 (所有重試已用盡): {e}")
                    raise ConfigurationError(f"遠端配置載入失敗: {e}")
                else:
                    self.logger.warning(
                        f"遠端配置載入失敗 (嘗試 {attempt + 1}/{self.retry_attempts}): {e}"
                    )
                    await asyncio.sleep(2**attempt)  # 指數退避

        return {}

    async def is_changed(self) -> bool:
        """檢查遠端配置是否變更"""
        import aiohttp

        try:
            headers = self.headers.copy()

            # 使用快取標頭進行條件請求
            if self.last_etag:
                headers["If-None-Match"] = self.last_etag
            if self.last_modified_header:
                headers["If-Modified-Since"] = self.last_modified_header

            async with (
                aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as session,
                session.head(self.url, headers=headers) as response,
            ):
                return response.status != 304

        except Exception as e:
            self.logger.warning(f"檢查遠端配置變更失敗: {e}")
            return True  # 假設已變更,觸發重載

    async def watch(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """監控遠端配置變更(輪詢方式)"""
        while True:
            try:
                await asyncio.sleep(60)  # 每分鐘檢查一次

                if await self.is_changed():
                    self.logger.info(f"檢測到遠端配置變更: {self.url}")
                    new_config = await self.load()
                    await callback(new_config)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"遠端配置監控失敗: {e}")
                await asyncio.sleep(300)  # 錯誤後等待5分鐘


class DatabaseConfigLoader(ConfigLoader):
    """資料庫配置載入器

    支援從SQLite資料庫載入配置,提供表結構初始化和監控功能.
    """

    def __init__(
        self,
        db_path: str | Path,
        table_name: str = "config",
        key_column: str = "key",
        value_column: str = "value",
        environment_column: str = "environment",
    ):
        """初始化資料庫配置載入器

        Args:
            db_path: 資料庫文件路徑
            table_name: 配置表名稱
            key_column: 配置鍵列名
            value_column: 配置值列名
            environment_column: 環境列名
        """
        super().__init__(ConfigSource.DATABASE)
        self.db_path = Path(db_path)
        self.table_name = table_name
        self.key_column = key_column
        self.value_column = value_column
        self.environment_column = environment_column
        self.last_modified = 0

    async def _ensure_table_exists(self):
        """確保配置表存在"""
        import aiosqlite

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    {self.key_column} TEXT NOT NULL,
                    {self.value_column} TEXT NOT NULL,
                    {self.environment_column} TEXT DEFAULT 'default',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE({self.key_column}, {self.environment_column})
                )
            """)

            # 創建索引
            await db.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.table_name}_key_env
                ON {self.table_name}({self.key_column}, {self.environment_column})
            """)

            await db.commit()

    async def load(self) -> dict[str, Any]:
        """載入資料庫配置"""
        import aiosqlite

        # 確保表存在
        await self._ensure_table_exists()

        # 獲取當前環境
        current_env = os.environ.get("ENVIRONMENT", "development")

        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 載入配置(優先使用特定環境,回退到default)
                cursor = await db.execute(
                    f"""
                    SELECT {self.key_column}, {self.value_column}
                    FROM {self.table_name}
                    WHERE {self.environment_column} IN (?, 'default')
                    ORDER BY
                        CASE WHEN {self.environment_column} = ? THEN 1 ELSE 2 END,
                        {self.key_column}
                """,
                    (current_env, current_env),
                )

                rows = await cursor.fetchall()
                config = {}

                for key, value in rows:
                    # 如果鍵已存在且是特定環境的配置,跳過default值
                    if key not in config:
                        # 嘗試解析JSON值
                        try:
                            parsed_value = json.loads(value)
                        except (json.JSONDecodeError, TypeError):
                            parsed_value = value

                        # 支援嵌套配置結構
                        self._set_nested_value(config, key, parsed_value)

                # 更新最後修改時間
                cursor = await db.execute(f"""
                    SELECT MAX(updated_at) FROM {self.table_name}
                """)
                result = await cursor.fetchone()
                if result and result[0]:
                    # 轉換時間戳
                    from datetime import datetime

                    dt = datetime.fromisoformat(result[0].replace("Z", "+00:00"))
                    self.last_modified = dt.timestamp()

                self.logger.debug(
                    f"載入資料庫配置: {len(config)} 項 (環境: {current_env})"
                )
                return config

        except Exception as e:
            raise ConfigurationError(f"載入資料庫配置失敗: {e}")

    def _set_nested_value(self, config: dict[str, Any], key: str, value: Any):
        """設定嵌套配置值"""
        if "." in key:
            parts = key.split(".")
            current = config

            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                elif not isinstance(current[part], dict):
                    # 如果已存在非字典值,跳過
                    return
                current = current[part]

            current[parts[-1]] = value
        else:
            config[key] = value

    async def is_changed(self) -> bool:
        """檢查資料庫配置是否變更"""
        import aiosqlite

        try:
            if not self.db_path.exists():
                return self.last_modified != 0

            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(f"""
                    SELECT MAX(updated_at) FROM {self.table_name}
                """)
                result = await cursor.fetchone()

                if result and result[0]:
                    from datetime import datetime

                    dt = datetime.fromisoformat(result[0].replace("Z", "+00:00"))
                    current_modified = dt.timestamp()
                    return current_modified != self.last_modified

        except Exception as e:
            self.logger.warning(f"檢查資料庫配置變更失敗: {e}")

        return False

    async def watch(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """監控資料庫配置變更(輪詢方式)"""
        while True:
            try:
                await asyncio.sleep(30)  # 每30秒檢查一次

                if await self.is_changed():
                    self.logger.info(f"檢測到資料庫配置變更: {self.db_path}")
                    new_config = await self.load()
                    await callback(new_config)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"資料庫配置監控失敗: {e}")
                await asyncio.sleep(60)  # 錯誤後等待1分鐘


# =====================================================
# 配置合併引擎 (Config Merge Engine)
# =====================================================


class ConfigMergeEngine:
    """配置合併引擎

    提供多種配置合併策略,根據配置來源優先級進行智能合併.
    """

    def __init__(self):
        """初始化配置合併引擎"""
        self.merge_strategies = {
            "override": self._override_merge,
            "deep_merge": self._deep_merge,
            "list_append": self._list_append_merge,
            "list_unique": self._list_unique_merge,
        }
        self._logger = None

    @property
    def logger(self):
        """延遲載入logger"""
        if self._logger is None:
            try:
                from src.core.logger import get_logger

                self._logger = get_logger("config_merge_engine")
            except ImportError:
                import logging

                self._logger = logging.getLogger("config_merge_engine")
        return self._logger

    def merge_configs(
        self,
        configs: list[tuple[ConfigSource, dict[str, Any]]],
        strategy: str = "deep_merge",
    ) -> dict[str, Any]:
        """合併多個配置來源

        Args:
            configs: 配置來源和資料的元組列表
            strategy: 合併策略名稱

        Returns:
            合併後的配置字典
        """
        # 按優先級排序 (優先級數字越小越優先)
        sorted_configs = sorted(configs, key=lambda x: x[0].value)

        if not sorted_configs:
            return {}

        # 從最低優先級開始合併
        result = {}
        merge_func = self.merge_strategies.get(strategy, self._deep_merge)

        for source, config in reversed(sorted_configs):
            if config:  # 只合併非空配置
                result = merge_func(result, config)
                self.logger.debug(f"合併配置來源 {source.name}: {len(config)} 項")

        self.logger.info(f"配置合併完成:{len(result)} 項")
        return result

    def _override_merge(
        self, base: dict[str, Any], overlay: dict[str, Any]
    ) -> dict[str, Any]:
        """覆蓋合併策略 - 完全覆蓋基礎配置"""
        result = base.copy()
        result.update(overlay)
        return result

    def _deep_merge(
        self, base: dict[str, Any], overlay: dict[str, Any]
    ) -> dict[str, Any]:
        """深度合併策略 - 遞歸合併嵌套字典"""
        result = base.copy()

        for key, value in overlay.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    def _list_append_merge(
        self, base: dict[str, Any], overlay: dict[str, Any]
    ) -> dict[str, Any]:
        """列表追加合併策略 - 將列表值追加在一起"""
        result = base.copy()

        for key, value in overlay.items():
            if (
                key in result
                and isinstance(result[key], list)
                and isinstance(value, list)
            ):
                result[key] = result[key] + value
            else:
                result[key] = value

        return result

    def _list_unique_merge(
        self, base: dict[str, Any], overlay: dict[str, Any]
    ) -> dict[str, Any]:
        """列表去重合併策略 - 合併並去重列表元素"""
        result = base.copy()

        for key, value in overlay.items():
            if (
                key in result
                and isinstance(result[key], list)
                and isinstance(value, list)
            ):
                # 合併並去重,保持順序
                combined = result[key] + value
                result[key] = list(dict.fromkeys(combined))
            else:
                result[key] = value

        return result


# =====================================================
# 配置驗證系統 (Configuration Validation)
# =====================================================


class ConfigurationValidator:
    """配置驗證器

    提供類型驗證、範圍檢查、自訂驗證規則等功能.
    """

    def __init__(self):
        """初始化配置驗證器"""
        self.validation_rules: dict[str, dict[str, Any]] = {}
        self.custom_validators: dict[str, Callable[[Any], bool]] = {}
        self._logger = None

    @property
    def logger(self):
        """延遲載入logger"""
        if self._logger is None:
            try:
                from src.core.logger import get_logger

                self._logger = get_logger("config_validator")
            except ImportError:
                import logging

                self._logger = logging.getLogger("config_validator")
        return self._logger

    def add_validation_rule(
        self, key_path: str, validator: Callable[[Any], bool], error_message: str
    ):
        """新增驗證規則

        Args:
            key_path: 配置項路徑,如 "database.pool_size"
            validator: 驗證函數
            error_message: 驗證失敗時的錯誤訊息
        """
        self.validation_rules[key_path] = {
            "validator": validator,
            "error_message": error_message,
        }
        self.logger.debug(f"新增驗證規則: {key_path}")

    def add_custom_validator(self, name: str, validator: Callable[[Any], bool]):
        """新增自定義驗證器

        Args:
            name: 驗證器名稱
            validator: 驗證函數
        """
        self.custom_validators[name] = validator
        self.logger.debug(f"新增自定義驗證器: {name}")

    def validate_config(self, config: dict[str, Any]) -> list[str]:
        """驗證配置

        Args:
            config: 待驗證的配置字典

        Returns:
            驗證錯誤列表(空列表表示沒有錯誤)
        """
        errors = []

        for key_path, rule in self.validation_rules.items():
            try:
                value = self._get_nested_value(config, key_path)
                if not rule["validator"](value):
                    errors.append(f"{key_path}: {rule['error_message']}")
            except KeyError:
                errors.append(f"{key_path}: 缺少必要的配置項")
            except Exception as e:
                errors.append(f"{key_path}: 驗證錯誤 - {e}")

        if errors:
            self.logger.warning(f"配置驗證失敗:{len(errors)} 個錯誤")
        else:
            self.logger.debug("配置驗證通過")

        return errors

    def _get_nested_value(self, config: dict[str, Any], key_path: str) -> Any:
        """獲取嵌套配置值

        Args:
            config: 配置字典
            key_path: 配置項路徑,如 "database.pool_size"

        Returns:
            配置值

        Raises:
            KeyError: 如果配置路徑不存在
        """
        parts = key_path.split(".")
        current = config

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                raise KeyError(f"配置路徑 '{key_path}' 不存在")

        return current


class CommonValidators:
    """常用驗證器集合"""

    @staticmethod
    def required(value: Any) -> bool:
        """必要值驗證"""
        return value is not None and value != ""

    @staticmethod
    def positive_integer(value: Any) -> bool:
        """正整數驗證"""
        return isinstance(value, int) and value > 0

    @staticmethod
    def non_negative_integer(value: Any) -> bool:
        """非負整數驗證"""
        return isinstance(value, int) and value >= 0

    @staticmethod
    def positive_float(value: Any) -> bool:
        """正浮點數驗證"""
        return isinstance(value, int | float) and value > 0

    @staticmethod
    def valid_log_level(value: Any) -> bool:
        """有效日誌級別驗證"""
        return value in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

    @staticmethod
    def valid_environment(value: Any) -> bool:
        """有效環境驗證"""
        return value in ["development", "staging", "production"]

    @staticmethod
    def valid_url(value: Any) -> bool:
        """有效URL驗證"""
        if not isinstance(value, str):
            return False
        import re

        url_pattern = re.compile(
            r"^https?://"  # http:// or https://
            r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+"  # domain...
            r"[A-Z]{2,6}\.?|"  # ...
            r"localhost|"  # localhost...
            r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
            r"(?::\d+)?"  # optional port
            r"(?:/?|[/?]\S+)$",
            re.IGNORECASE,
        )
        return url_pattern.match(value) is not None

    @staticmethod
    def valid_path(value: Any) -> bool:
        """有效路徑驗證"""
        if not isinstance(value, str | Path):
            return False
        try:
            Path(value)
            return True
        except (TypeError, ValueError):
            return False

    @staticmethod
    def min_length(min_len: int) -> Callable[[Any], bool]:
        """最小長度驗證器生成函數"""

        def validator(value: Any) -> bool:
            if isinstance(value, str | list | dict):
                return len(value) >= min_len
            return False

        return validator

    @staticmethod
    def max_length(max_len: int) -> Callable[[Any], bool]:
        """最大長度驗證器生成函數"""

        def validator(value: Any) -> bool:
            if isinstance(value, str | list | dict):
                return len(value) <= max_len
            return False

        return validator

    @staticmethod
    def in_range(min_val: int | float, max_val: int | float) -> Callable[[Any], bool]:
        """範圍驗證器生成函數"""

        def validator(value: Any) -> bool:
            if isinstance(value, int | float):
                return min_val <= value <= max_val
            return False

        return validator


# =====================================================
# 配置熱重載系統 (Hot Reload System)
# =====================================================


class ConfigChangeListener(ABC):
    """配置變更監聽器介面

    所有配置變更監聽器都應繼承此類並實作相應方法.
    """

    @abstractmethod
    async def on_config_changed(
        self,
        old_settings: Settings,
        new_settings: Settings,
        changes: list[dict[str, Any]],
    ):
        """配置變更回調

        Args:
            old_settings: 舊配置
            new_settings: 新配置
            changes: 變更詳情列表
        """
        pass


class LoggerConfigChangeListener(ConfigChangeListener):
    """日誌器配置變更監聽器"""

    async def on_config_changed(
        self,
        old_settings: Settings,
        new_settings: Settings,
        changes: list[dict[str, Any]],
    ):
        """處理日誌配置變更"""
        # 檢查日誌相關配置是否變更
        log_changes = [c for c in changes if c["key"].startswith("logging")]

        if log_changes:
            try:
                # 重新配置日誌系統
                from src.core.logger import setup_logging

                setup_logging(new_settings)

                # 記錄配置變更
                from src.core.logger import get_logger

                logger = get_logger("config_change_listener")
                logger.info(f"日誌配置已更新: {len(log_changes)} 項變更")

            except Exception as e:
                print(f"重新配置日誌系統失敗: {e}")


class DatabaseConfigChangeListener(ConfigChangeListener):
    """資料庫配置變更監聽器"""

    async def on_config_changed(
        self,
        old_settings: Settings,
        new_settings: Settings,
        changes: list[dict[str, Any]],
    ):
        """處理資料庫配置變更"""
        db_changes = [c for c in changes if c["key"].startswith("database")]

        if db_changes:
            try:
                # 重新初始化資料庫連線池
                from src.core.database import close_all_pools

                await close_all_pools()
                # 新的連線池會在下次使用時自動創建

                print(f"資料庫配置已更新: {len(db_changes)} 項變更")

            except Exception as e:
                print(f"重新配置資料庫連線失敗: {e}")


class ConfigHotReloader:
    """配置熱重載器

    監控配置來源變更,自動重載配置並通知相關監聽器.
    提供防抖機制防止頻繁重載.
    """

    def __init__(self, config_manager: ConfigurationManager):
        """初始化配置熱重載器

        Args:
            config_manager: 配置管理器實例
        """
        self.config_manager = config_manager
        self.reload_tasks: dict[str, asyncio.Task] = {}
        self.reload_lock = asyncio.Lock()
        self.reload_debounce_delay = 0.5  # 500ms防抖
        self._logger = None

    @property
    def logger(self):
        """延遲載入logger"""
        if self._logger is None:
            try:
                from src.core.logger import get_logger

                self._logger = get_logger("config_hot_reloader")
            except ImportError:
                import logging

                self._logger = logging.getLogger("config_hot_reloader")
        return self._logger

    async def start_watching(self):
        """開始監控所有配置來源"""
        self.logger.info("開始配置熱重載監控")

        for source_name, loader in self.config_manager.loaders.items():
            if hasattr(loader, "watch"):
                task = asyncio.create_task(self._watch_source(source_name, loader))
                self.reload_tasks[source_name] = task

    async def stop_watching(self):
        """停止監控"""
        self.logger.info("停止配置熱重載監控")

        for task in self.reload_tasks.values():
            task.cancel()

        # 等待所有任務完成
        if self.reload_tasks:
            await asyncio.gather(*self.reload_tasks.values(), return_exceptions=True)

        self.reload_tasks.clear()

    async def _watch_source(self, source_name: str, loader: ConfigLoader):
        """監控特定配置來源"""

        async def reload_callback(new_config: dict[str, Any]):
            await self._debounced_reload(source_name, new_config)

        try:
            await loader.watch(reload_callback)
        except Exception as e:
            self.logger.error(f"監控配置來源 {source_name} 失敗: {e}")

    async def _debounced_reload(self, source_name: str, new_config: dict[str, Any]):
        """防抖重載機制"""
        # 取消之前的重載任務
        if hasattr(self, "_debounce_task"):
            self._debounce_task.cancel()

        # 創建新的延遲重載任務
        self._debounce_task = asyncio.create_task(
            self._delayed_reload(source_name, new_config)
        )

    async def _delayed_reload(self, source_name: str, new_config: dict[str, Any]):
        """延遲重載執行"""
        await asyncio.sleep(self.reload_debounce_delay)

        async with self.reload_lock:
            await self._perform_reload(source_name, new_config)

    async def _perform_reload(self, source_name: str, new_config: dict[str, Any]):
        """執行配置重載"""
        try:
            self.logger.info(f"重載配置來源: {source_name}")

            # 備份當前配置
            old_settings = self.config_manager.current_settings

            # 重新載入並合併配置
            new_settings = await self.config_manager.reload_configuration()

            # 驗證新配置
            validation_errors = self.config_manager.validator.validate_config(
                new_settings.model_dump()
            )

            if validation_errors:
                self.logger.error(f"配置驗證失敗: {validation_errors}")
                # 恢復舊配置
                self.config_manager.current_settings = old_settings
                return

            # 通知配置變更
            await self._notify_config_change(old_settings, new_settings)

            self.logger.info("配置重載完成")

        except Exception as e:
            self.logger.error(f"配置重載失敗: {e}")
            # 這裡可以實作告警機制
            await self._send_reload_failure_alert(source_name, str(e))

    async def _notify_config_change(
        self, old_settings: Settings, new_settings: Settings
    ):
        """通知配置變更"""
        changes = self._detect_changes(old_settings, new_settings)

        if changes:
            self.logger.info(f"檢測到配置變更: {len(changes)} 項")

            # 通知所有監聽器
            for listener in self.config_manager.change_listeners:
                try:
                    await listener.on_config_changed(
                        old_settings, new_settings, changes
                    )
                except Exception as e:
                    self.logger.error(f"配置變更通知失敗: {e}")

    def _detect_changes(
        self, old_settings: Settings, new_settings: Settings
    ) -> list[dict[str, Any]]:
        """檢測配置變更"""
        changes = []

        old_dict = old_settings.model_dump()
        new_dict = new_settings.model_dump()

        # 簡單的變更檢測 (可以優化為深度比較)
        for key in set(old_dict.keys()) | set(new_dict.keys()):
            old_value = old_dict.get(key)
            new_value = new_dict.get(key)

            if old_value != new_value:
                changes.append(
                    {
                        "key": key,
                        "old_value": old_value,
                        "new_value": new_value,
                        "change_type": self._get_change_type(old_value, new_value),
                    }
                )

        return changes

    def _get_change_type(self, old_value: Any, new_value: Any) -> str:
        """獲取變更類型"""
        if old_value is None:
            return "added"
        elif new_value is None:
            return "removed"
        else:
            return "modified"

    async def _send_reload_failure_alert(self, source_name: str, error: str):
        """發送重載失敗告警"""
        # 這裡可以整合告警系統
        self.logger.critical(f"配置重載失敗告警 - 來源: {source_name}, 錯誤: {error}")


# =====================================================
# 安全加密系統 (Security & Encryption)
# =====================================================


class ConfigEncryptionService:
    """配置加密服務

    使用Fernet對稱加密算法保護敏感配置數據.
    支持配置字段級別的加密和解密.
    """

    def __init__(self, master_key: bytes | None = None):
        """初始化配置加密服務

        Args:
            master_key: 主密鑰,如果為None則自動生成或讀取
        """
        self._logger = None
        self.encrypted_fields: set[str] = set()
        self.master_key = master_key or self._get_or_create_master_key()
        self.cipher = Fernet(self.master_key)

    @property
    def logger(self):
        """延遲載入logger"""
        if self._logger is None:
            try:
                from src.core.logger import get_logger

                self._logger = get_logger("config_encryption")
            except ImportError:
                import logging

                self._logger = logging.getLogger("config_encryption")
        return self._logger

    def _get_or_create_master_key(self) -> bytes:
        """獲取或創建主密鑰"""
        key_file = Path(".encryption_key")

        try:
            if key_file.exists():
                with open(key_file, "rb") as f:
                    key = f.read()
                self.logger.debug("載入現有加密密鑰")
                return key
            else:
                # 生成新密鑰
                key = Fernet.generate_key()
                with open(key_file, "wb") as f:
                    f.write(key)

                # 設定適當的檔案權限 (僅限Unix系統)
                try:
                    key_file.chmod(0o600)
                except (AttributeError, OSError):
                    # Windows系統或權限設定失敗
                    pass

                self.logger.info("生成新的加密密鑰")
                return key

        except Exception as e:
            self.logger.error(f"密鑰管理失敗: {e}")
            # 回退到內存密鑰
            return Fernet.generate_key()

    def encrypt_value(self, value: str) -> str:
        """加密配置值

        Args:
            value: 待加密的值

        Returns:
            Base64編碼的加密值
        """
        if not isinstance(value, str):
            value = str(value)

        try:
            encrypted = self.cipher.encrypt(value.encode())
            return base64.b64encode(encrypted).decode()
        except Exception as e:
            self.logger.error(f"加密失敗: {e}")
            raise ConfigurationError(f"加密失敗: {e}")

    def decrypt_value(self, encrypted_value: str) -> str:
        """解密配置值

        Args:
            encrypted_value: Base64編碼的加密值

        Returns:
            解密後的原始值
        """
        try:
            encrypted_bytes = base64.b64decode(encrypted_value.encode())
            decrypted = self.cipher.decrypt(encrypted_bytes)
            return decrypted.decode()
        except Exception as e:
            self.logger.error(f"解密失敗: {e}")
            raise ConfigurationError(f"解密失敗: {e}")

    def is_encrypted(self, value: str) -> bool:
        """檢查值是否已加密

        Args:
            value: 待檢查的值

        Returns:
            如果已加密返回True
        """
        if not isinstance(value, str):
            return False

        try:
            # 嘗試解密,如果成功則已加密
            self.decrypt_value(value)
            return True
        except:
            return False

    def register_encrypted_field(self, field_path: str):
        """註冊需要加密的欄位

        Args:
            field_path: 配置欄位路徑,如 "token" 或 "database.password"
        """
        self.encrypted_fields.add(field_path)
        self.logger.debug(f"註冊加密欄位: {field_path}")

    def process_config(
        self, config: dict[str, Any], encrypt: bool = False
    ) -> dict[str, Any]:
        """處理配置 (加密或解密)

        Args:
            config: 配置字典
            encrypt: True為加密模式,False為解密模式

        Returns:
            處理後的配置字典
        """
        result = config.copy()

        for field_path in self.encrypted_fields:
            try:
                value = self._get_nested_value(result, field_path)
                if value:
                    if encrypt and not self.is_encrypted(str(value)):
                        encrypted_value = self.encrypt_value(str(value))
                        self._set_nested_value(result, field_path, encrypted_value)
                        self.logger.debug(f"加密欄位: {field_path}")
                    elif not encrypt and self.is_encrypted(str(value)):
                        decrypted_value = self.decrypt_value(str(value))
                        self._set_nested_value(result, field_path, decrypted_value)
                        self.logger.debug(f"解密欄位: {field_path}")
            except Exception as e:
                self.logger.warning(f"處理加密欄位 {field_path} 失敗: {e}")

        return result

    def _get_nested_value(self, config: dict[str, Any], key_path: str) -> Any:
        """獲取嵌套配置值"""
        parts = key_path.split(".")
        current = config

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None

        return current

    def _set_nested_value(self, config: dict[str, Any], key_path: str, value: Any):
        """設定嵌套配置值"""
        parts = key_path.split(".")
        current = config

        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            elif not isinstance(current[part], dict):
                # 如果不是字典則跳過
                return
            current = current[part]

        current[parts[-1]] = value


class SecureConfigStorage:
    """安全配置存儲

    提供配置的安全存儲功能,包括文件權限設置和加密存儲.
    """

    def __init__(self, encryption_service: ConfigEncryptionService):
        """初始化安全配置存儲

        Args:
            encryption_service: 配置加密服務實例
        """
        self.encryption_service = encryption_service
        self.storage_path = Path("secure_config")
        self.storage_path.mkdir(exist_ok=True)
        self._logger = None

    @property
    def logger(self):
        """延遲載入logger"""
        if self._logger is None:
            try:
                from src.core.logger import get_logger

                self._logger = get_logger("secure_config_storage")
            except ImportError:
                import logging

                self._logger = logging.getLogger("secure_config_storage")
        return self._logger

    async def store_secure_config(self, config_name: str, config_data: dict[str, Any]):
        """存儲安全配置

        Args:
            config_name: 配置名稱
            config_data: 配置數據
        """
        try:
            # 加密敏感欄位
            encrypted_config = self.encryption_service.process_config(
                config_data, encrypt=True
            )

            # 存儲到檔案
            config_file = self.storage_path / f"{config_name}.json"
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(encrypted_config, f, indent=2, ensure_ascii=False)

            # 設定檔案權限 (僅限Unix系統)
            try:
                config_file.chmod(0o600)
            except (AttributeError, OSError):
                # Windows系統或權限設定失敗
                pass

            self.logger.info(f"安全配置已存儲: {config_name}")

        except Exception as e:
            self.logger.error(f"存儲安全配置失敗: {e}")
            raise ConfigurationError(f"存儲安全配置失敗: {e}")

    async def load_secure_config(self, config_name: str) -> dict[str, Any]:
        """載入安全配置

        Args:
            config_name: 配置名稱

        Returns:
            解密後的配置數據
        """
        config_file = self.storage_path / f"{config_name}.json"

        if not config_file.exists():
            self.logger.debug(f"安全配置檔案不存在: {config_name}")
            return {}

        try:
            with open(config_file, encoding="utf-8") as f:
                encrypted_config = json.load(f)

            # 解密敏感欄位
            decrypted_config = self.encryption_service.process_config(
                encrypted_config, encrypt=False
            )

            self.logger.debug(f"載入安全配置: {config_name}")
            return decrypted_config

        except Exception as e:
            self.logger.error(f"載入安全配置失敗: {e}")
            raise ConfigurationError(f"載入安全配置失敗: {e}")


# =====================================================
# 統一配置管理器 (Configuration Manager)
# =====================================================


class ConfigurationManager:
    """統一配置管理器

    企業級配置管理的核心組件,負責協調所有配置來源、
    合併策略、驗證規則、熱重載和加密服務.
    """

    def __init__(self, settings_class: type[Settings] | None = None):
        """初始化配置管理器

        Args:
            settings_class: Settings類別,如果為None則使用默認Settings類
        """
        self.settings_class = settings_class or Settings
        self.loaders: dict[str, ConfigLoader] = {}
        self.merge_engine = ConfigMergeEngine()
        self.validator = ConfigurationValidator()
        self.encryption_service = ConfigEncryptionService()
        self.hot_reloader = ConfigHotReloader(self)
        self.change_listeners: list[ConfigChangeListener] = []
        self.current_settings: Settings | None = None
        self._logger = None

        # 設定預設驗證規則
        self._setup_default_validation_rules()

        # 註冊預設監聽器
        self._register_default_listeners()

    @property
    def logger(self):
        """延遲載入logger"""
        if self._logger is None:
            try:
                from src.core.logger import get_logger

                self._logger = get_logger("config_manager")
            except ImportError:
                import logging

                self._logger = logging.getLogger("config_manager")
        return self._logger

    def add_loader(self, name: str, loader: ConfigLoader):
        """新增配置載入器

        Args:
            name: 載入器名稱
            loader: 配置載入器實例
        """
        self.loaders[name] = loader
        self.logger.debug(f"新增配置載入器: {name} ({loader.source.name})")

    def add_change_listener(self, listener: ConfigChangeListener):
        """新增配置變更監聽器

        Args:
            listener: 配置變更監聽器實例
        """
        self.change_listeners.append(listener)
        self.logger.debug(f"新增配置變更監聽器: {listener.__class__.__name__}")

    def _setup_default_validation_rules(self):
        """設定預設驗證規則"""
        # Discord Token驗證
        self.validator.add_validation_rule(
            "token",
            lambda x: isinstance(x, str) and len(x) > 50,
            "Discord token必須是有效字符串",
        )

        # 環境驗證
        self.validator.add_validation_rule(
            "environment",
            CommonValidators.valid_environment,
            "環境必須是 development, staging, 或 production",
        )

        # 日誌級別驗證
        self.validator.add_validation_rule(
            "logging.level", CommonValidators.valid_log_level, "日誌級別必須是有效值"
        )

        # 資料庫設定驗證
        self.validator.add_validation_rule(
            "database.pool_size",
            CommonValidators.positive_integer,
            "資料庫連線池大小必須是正整數",
        )

        # 新增更多驗證規則
        self.validator.add_validation_rule(
            "database.max_overflow",
            CommonValidators.non_negative_integer,
            "資料庫連線池溢出數量必須是非負整數",
        )

        self.validator.add_validation_rule(
            "cache.max_size",
            CommonValidators.positive_integer,
            "快取最大大小必須是正整數",
        )

    def _register_default_listeners(self):
        """註冊預設監聽器"""
        self.add_change_listener(LoggerConfigChangeListener())
        self.add_change_listener(DatabaseConfigChangeListener())

    async def initialize(self, enable_hot_reload: bool = True):
        """初始化配置管理器

        Args:
            enable_hot_reload: 是否啟用熱重載
        """
        self.logger.info("初始化配置管理系統")

        # 註冊加密欄位
        self.encryption_service.register_encrypted_field("token")
        self.encryption_service.register_encrypted_field("database.password")

        # 載入初始配置
        self.current_settings = await self.load_configuration()

        # 啟動熱重載
        if enable_hot_reload:
            await self.hot_reloader.start_watching()

        self.logger.info("配置管理系統初始化完成")

    async def load_configuration(self) -> Settings:
        """載入並合併所有配置來源

        Returns:
            Settings實例

        Raises:
            ConfigurationError: 配置載入或驗證失敗
        """
        configs = []

        # 載入所有配置來源
        for name, loader in self.loaders.items():
            try:
                config_data = await loader.load()
                if config_data:
                    configs.append((loader.source, config_data))
                    self.logger.debug(f"載入配置來源 {name}: {len(config_data)} 項")
            except Exception as e:
                self.logger.error(f"載入配置來源 {name} 失敗: {e}")
                # 繼續處理其他配置來源

        # 合併配置
        merged_config = self.merge_engine.merge_configs(configs)

        # 解密敏感欄位
        decrypted_config = self.encryption_service.process_config(
            merged_config, encrypt=False
        )

        # 驗證配置
        validation_errors = self.validator.validate_config(decrypted_config)
        if validation_errors:
            raise ConfigurationError(f"配置驗證失敗: {validation_errors}")

        # 創建Settings對象
        try:
            settings = self.settings_class(**decrypted_config)
            self.logger.info("配置載入完成")
            return settings
        except Exception as e:
            raise ConfigurationError(f"創建配置對象失敗: {e}")

    async def reload_configuration(self) -> Settings:
        """重新載入配置

        Returns:
            新的Settings實例
        """
        self.logger.info("重新載入配置")
        old_settings = self.current_settings

        try:
            new_settings = await self.load_configuration()
            self.current_settings = new_settings
            return new_settings
        except Exception as e:
            self.logger.error(f"配置重載失敗: {e}")
            if old_settings:
                self.current_settings = old_settings
            raise

    def get_current_settings(self) -> Settings:
        """獲取當前配置

        Returns:
            當前的Settings實例

        Raises:
            RuntimeError: 如果配置管理器未初始化
        """
        if self.current_settings is None:
            raise RuntimeError("配置管理器未初始化")
        return self.current_settings

    async def update_config_value(
        self, key_path: str, value: Any, persist: bool = True
    ):
        """更新配置值

        Args:
            key_path: 配置項路徑,如 "logging.level"
            value: 新值
            persist: 是否持久化變更
        """
        if self.current_settings is None:
            raise RuntimeError("配置管理器未初始化")

        # 更新運行時配置
        config_dict = self.current_settings.model_dump()
        self._set_nested_value(config_dict, key_path, value)

        # 重新創建Settings對象
        new_settings = self.settings_class(**config_dict)
        old_settings = self.current_settings
        self.current_settings = new_settings

        # 通知變更
        changes = [
            {
                "key": key_path,
                "old_value": self._get_nested_value(
                    old_settings.model_dump(), key_path
                ),
                "new_value": value,
                "change_type": "modified",
            }
        ]

        for listener in self.change_listeners:
            try:
                await listener.on_config_changed(old_settings, new_settings, changes)
            except Exception as e:
                self.logger.error(f"配置變更通知失敗: {e}")

        # 可選持久化
        if persist:
            await self._persist_config_change(key_path, value)

        self.logger.info(f"配置值已更新: {key_path} = {value}")

    async def _persist_config_change(self, key_path: str, value: Any):
        """持久化配置變更

        Args:
            key_path: 配置項路徑
            value: 新值
        """
        # 這裡可以實作將變更寫入配置檔案或資料庫
        self.logger.debug(f"持久化配置變更: {key_path} = {value}")
        # TODO: 根據需要實作具體的持久化邏輯

    def _get_nested_value(self, config: dict[str, Any], key_path: str) -> Any:
        """獲取嵌套配置值"""
        parts = key_path.split(".")
        current = config

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current

    def _set_nested_value(self, config: dict[str, Any], key_path: str, value: Any):
        """設定嵌套配置值"""
        parts = key_path.split(".")
        current = config

        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            elif not isinstance(current[part], dict):
                # 如果不是字典則創建新字典
                current[part] = {}
            current = current[part]

        current[parts[-1]] = value

    async def shutdown(self):
        """關閉配置管理器"""
        self.logger.info("關閉配置管理系統")
        try:
            await self.hot_reloader.stop_watching()
        except Exception as e:
            self.logger.error(f"停止熱重載監控失敗: {e}")


# =====================================================
# 增強的Settings系統 (Enhanced Settings)
# =====================================================


class EnhancedSettings(Settings):
    """增強的配置系統

    基於原有Settings類,添加配置來源追蹤、熱重載支持等功能.
    """

    # 新增配置來源追蹤
    _config_sources: dict[str, str] = {}
    _config_manager: ConfigurationManager | None = None

    class Config:
        """Pydantic配置"""

        # 保持原有配置
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"
        frozen = False  # 改為可變,支援熱重載
        use_enum_values = True

    @model_validator(mode="before")
    @classmethod
    def track_config_sources(cls, values):
        """追蹤配置來源"""
        # 這裡可以實作配置來源追蹤邏輯
        return values

    def get_config_source(self, field_name: str) -> str | None:
        """獲取配置項的來源

        Args:
            field_name: 配置項名稱

        Returns:
            配置來源名稱,如果未找到則返回None
        """
        return self._config_sources.get(field_name)

    def reload_from_manager(self, config_manager: ConfigurationManager):
        """從配置管理器重載配置

        Args:
            config_manager: 配置管理器實例
        """
        self._config_manager = config_manager
        new_settings = config_manager.get_current_settings()

        # 更新所有欄位
        for field_name, value in new_settings.model_dump().items():
            if hasattr(self, field_name):
                setattr(self, field_name, value)

    async def update_field(self, field_name: str, value: Any, persist: bool = True):
        """更新配置欄位

        Args:
            field_name: 欄位名稱
            value: 新值
            persist: 是否持久化
        """
        if self._config_manager:
            await self._config_manager.update_config_value(field_name, value, persist)
        else:
            setattr(self, field_name, value)


class SettingsFactory:
    """配置工廠

    提供便捷的配置系統創建和初始化方法.
    """

    def __init__(self):
        """初始化配置工廠"""
        self.config_manager = ConfigurationManager(EnhancedSettings)

    async def create_settings(
        self,
        config_sources: dict[str, Any] | None = None,
        enable_hot_reload: bool = True,
    ) -> EnhancedSettings:
        """創建配置實例

        Args:
            config_sources: 配置來源字典,None則使用預設
            enable_hot_reload: 是否啟用熱重載

        Returns:
            EnhancedSettings實例
        """

        # 設定預設配置來源
        if config_sources is None:
            config_sources = self._get_default_sources()

        # 註冊配置載入器
        for name, source_config in config_sources.items():
            loader = self._create_loader(name, source_config)
            self.config_manager.add_loader(name, loader)

        # 初始化配置管理器
        await self.config_manager.initialize(enable_hot_reload)

        # 創建增強的Settings實例
        settings = self.config_manager.get_current_settings()
        settings._config_manager = self.config_manager

        return settings

    def _get_default_sources(self) -> dict[str, Any]:
        """獲取預設配置來源"""
        return {
            "environment": {"type": "env", "prefix": "ADR_BOT_"},
            "env_file": {"type": "file", "path": ".env"},
            "yaml_config": {"type": "file", "path": "config.yaml"},
            "cli": {"type": "cli"},
        }

    def _create_loader(self, name: str, config: dict[str, Any]) -> ConfigLoader:
        """創建配置載入器

        Args:
            name: 載入器名稱
            config: 載入器配置

        Returns:
            ConfigLoader實例

        Raises:
            ValueError: 不支援的載入器類型
        """
        loader_type = config.get("type")

        if loader_type == "env":
            prefix = config.get("prefix", "")
            return EnvironmentConfigLoader(prefix)
        elif loader_type == "file":
            path = Path(config["path"])
            return FileConfigLoader(path)
        elif loader_type == "cli":
            return CliConfigLoader()
        elif loader_type == "remote":
            url = config["url"]
            headers = config.get("headers", {})
            timeout = config.get("timeout", 30)
            retry_attempts = config.get("retry_attempts", 3)
            return RemoteConfigLoader(url, headers, timeout, retry_attempts)
        elif loader_type == "database":
            db_path = config["db_path"]
            table_name = config.get("table_name", "config")
            key_column = config.get("key_column", "key")
            value_column = config.get("value_column", "value")
            environment_column = config.get("environment_column", "environment")
            return DatabaseConfigLoader(
                db_path, table_name, key_column, value_column, environment_column
            )
        else:
            raise ValueError(f"不支援的載入器類型: {loader_type}")


# =====================================================
# 全域配置管理實例 (Global Configuration Instances)
# =====================================================

_config_manager: ConfigurationManager | None = None
_settings: EnhancedSettings | None = None
_factory: SettingsFactory | None = None


async def initialize_config_system(
    config_sources: dict[str, Any] | None = None, enable_hot_reload: bool = True
) -> EnhancedSettings:
    """初始化配置系統

    Args:
        config_sources: 配置來源字典
        enable_hot_reload: 是否啟用熱重載

    Returns:
        EnhancedSettings實例
    """
    global _config_manager, _settings, _factory

    _factory = SettingsFactory()
    _settings = await _factory.create_settings(config_sources, enable_hot_reload)
    _config_manager = _factory.config_manager

    return _settings


def get_enhanced_settings() -> EnhancedSettings:
    """獲取增強配置實例

    Returns:
        EnhancedSettings實例

    Raises:
        RuntimeError: 如果配置系統未初始化
    """
    if _settings is None:
        raise RuntimeError("配置系統未初始化,請先調用 initialize_config_system()")
    return _settings


def get_config_manager() -> ConfigurationManager:
    """獲取配置管理器

    Returns:
        ConfigurationManager實例

    Raises:
        RuntimeError: 如果配置系統未初始化
    """
    if _config_manager is None:
        raise RuntimeError("配置系統未初始化")
    return _config_manager


async def shutdown_config_system():
    """關閉配置系統"""
    global _config_manager, _settings, _factory

    if _config_manager:
        await _config_manager.shutdown()
        _config_manager = None

    _settings = None
    _factory = None


# Export for convenient imports
__all__ = [
    "CacheSettings",
    "CliConfigLoader",
    "CommonValidators",
    # 熱重載系統
    "ConfigChangeListener",
    # 安全加密系統
    "ConfigEncryptionService",
    "ConfigHotReloader",
    "ConfigLoader",
    "ConfigMergeEngine",
    # 新增的配置管理類別
    "ConfigSource",
    "ConfigurationError",
    # 統一配置管理
    "ConfigurationManager",
    "ConfigurationValidator",
    "DatabaseConfigChangeListener",
    "DatabaseConfigLoader",
    "DatabaseSettings",
    "EnhancedSettings",
    "EnvironmentConfigLoader",
    "FileConfigLoader",
    "LoggerConfigChangeListener",
    "LoggingSettings",
    "PerformanceSettings",
    "RemoteConfigLoader",
    "SecureConfigStorage",
    "SecuritySettings",
    # 原有的類別
    "Settings",
    "SettingsFactory",
    "get_config_manager",
    "get_enhanced_settings",
    "get_settings",
    # 全域函數
    "initialize_config_system",
    "reload_settings",
    "shutdown_config_system",
]
