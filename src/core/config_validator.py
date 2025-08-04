"""配置驗證器 for Discord ROAS Bot v2.0.

此模組提供配置文件的驗證功能, 確保:
- 配置格式正確
- 必要欄位存在
- 數值範圍合理
- 依賴關係滿足
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml
from pydantic import BaseModel, ValidationError, validator

logger = logging.getLogger(__name__)

# 常數定義
# 資料庫相關常數
MIN_POOL_SIZE = 1
MAX_POOL_SIZE = 100
MIN_MAX_OVERFLOW = 0
MAX_MAX_OVERFLOW = 200
MIN_TIMEOUT = 1
MAX_QUERY_TIMEOUT = 300
MIN_PORT = 1
MAX_PORT = 65535
MAX_DATABASE_NAME_LENGTH = 63

# 快取相關常數
MIN_CACHE_DURATION = 60
MAX_CACHE_DURATION = 86400
MIN_GOVERNMENT_CACHE_DURATION = 300
MIN_BATCH_SIZE = 10
MAX_BATCH_SIZE = 1000

# 政府系統相關常數
MAX_DEPARTMENTS_PER_GUILD = 100
MAX_MEMBERS_PER_ROLE = 100
MAX_MEMBERS_PER_DEPARTMENT = 1000
MAX_ROLE_NAME_LENGTH = 50
MAX_DEPARTMENT_NAME_LENGTH = 100
MAX_DESCRIPTION_LENGTH = 500
MIN_PAYMENT_INTERVAL = 1
MAX_PAYMENT_INTERVAL = 168  # 一周
MIN_BASE_SALARY = 0
MAX_BASE_SALARY = 10000

class DatabasePoolConfig(BaseModel):
    """資料庫連接池配置."""

    size: int = 10
    max_overflow: int = 20
    timeout: int = 30
    recycle: int = 3600
    pre_ping: bool = True

    @validator("size")
    def validate_size(cls, v: int) -> int:
        if v < MIN_POOL_SIZE or v > MAX_POOL_SIZE:
            raise ValueError(f"Pool size must be between {MIN_POOL_SIZE} and {MAX_POOL_SIZE}")
        return v

    @validator("max_overflow")
    def validate_max_overflow(cls, v: int) -> int:
        if v < MIN_MAX_OVERFLOW or v > MAX_MAX_OVERFLOW:
            raise ValueError(f"Max overflow must be between {MIN_MAX_OVERFLOW} and {MAX_MAX_OVERFLOW}")
        return v

class DatabaseQueryConfig(BaseModel):
    """資料庫查詢配置."""

    timeout: int = 30
    echo: bool = False

    @validator("timeout")
    def validate_timeout(cls, v: int) -> int:
        if v < MIN_TIMEOUT or v > MAX_QUERY_TIMEOUT:
            raise ValueError(f"Query timeout must be between {MIN_TIMEOUT} and {MAX_QUERY_TIMEOUT} seconds")
        return v

class PostgreSQLConfig(BaseModel):
    """PostgreSQL 配置."""

    host: str = "localhost"
    port: int = 5432
    database: str = "discord_roas_bot"
    username: str = "postgres"
    password: str = ""
    pool: DatabasePoolConfig = DatabasePoolConfig()
    query: DatabaseQueryConfig = DatabaseQueryConfig()

    @validator("port")
    def validate_port(cls, v: int) -> int:
        if v < MIN_PORT or v > MAX_PORT:
            raise ValueError(f"Port must be between {MIN_PORT} and {MAX_PORT}")
        return v

    @validator("database")
    def validate_database_name(cls, v: str) -> str:
        if not v or len(v) > MAX_DATABASE_NAME_LENGTH:
            raise ValueError(f"Database name must be 1-{MAX_DATABASE_NAME_LENGTH} characters")
        return v

class DatabaseConfig(BaseModel):
    """資料庫配置."""

    type: str = "postgresql"
    postgresql: PostgreSQLConfig = PostgreSQLConfig()

    @validator("type")
    def validate_type(cls, v: str) -> str:
        if v not in ["postgresql", "sqlite"]:
            raise ValueError("Database type must be postgresql or sqlite")
        return v

class CurrencyModuleConfig(BaseModel):
    """貨幣模組配置."""

    table_prefix: str = "currency_"
    cache_duration: int = 600
    batch_update_size: int = 100

    @validator("cache_duration")
    def validate_cache_duration(cls, v: int) -> int:
        if v < MIN_CACHE_DURATION or v > MAX_CACHE_DURATION:
            raise ValueError(f"Cache duration must be between {MIN_CACHE_DURATION} and {MAX_CACHE_DURATION} seconds")
        return v

    @validator("batch_update_size")
    def validate_batch_size(cls, v: int) -> int:
        if v < MIN_BATCH_SIZE or v > MAX_BATCH_SIZE:
            raise ValueError(f"Batch update size must be between {MIN_BATCH_SIZE} and {MAX_BATCH_SIZE}")
        return v

class DepartmentModuleConfig(BaseModel):
    """部門模組配置."""

    table_prefix: str = "department_"
    cache_duration: int = 3600
    max_departments_per_guild: int = 50

    @validator("cache_duration")
    def validate_cache_duration(cls, v: int) -> int:
        if v < MIN_GOVERNMENT_CACHE_DURATION or v > MAX_CACHE_DURATION:
            raise ValueError(f"Cache duration must be between {MIN_GOVERNMENT_CACHE_DURATION} and {MAX_CACHE_DURATION} seconds")
        return v

    @validator("max_departments_per_guild")
    def validate_max_departments(cls, v: int) -> int:
        if v < MIN_POOL_SIZE or v > MAX_DEPARTMENTS_PER_GUILD:
            raise ValueError(f"Max departments per guild must be between {MIN_POOL_SIZE} and {MAX_DEPARTMENTS_PER_GUILD}")
        return v

class ModulesConfig(BaseModel):
    """模組配置."""

    currency: CurrencyModuleConfig = CurrencyModuleConfig()
    department: DepartmentModuleConfig = DepartmentModuleConfig()

class GovernmentRoleConfig(BaseModel):
    """政府角色配置."""

    name: str
    permissions: list[str]
    max_members: int = 1

    @validator("name")
    def validate_name(cls, v: str) -> str:
        if not v or len(v) > MAX_ROLE_NAME_LENGTH:
            raise ValueError(f"Role name must be 1-{MAX_ROLE_NAME_LENGTH} characters")
        return v

    @validator("max_members")
    def validate_max_members(cls, v: int) -> int:
        if v < MIN_POOL_SIZE or v > MAX_MEMBERS_PER_ROLE:
            raise ValueError(f"Max members must be between {MIN_POOL_SIZE} and {MAX_MEMBERS_PER_ROLE}")
        return v

class GovernmentDepartmentConfig(BaseModel):
    """政府部門配置."""

    name: str
    description: str
    roles: list[GovernmentRoleConfig]

    @validator("name")
    def validate_name(cls, v: str) -> str:
        if not v or len(v) > MAX_DEPARTMENT_NAME_LENGTH:
            raise ValueError(f"Department name must be 1-{MAX_DEPARTMENT_NAME_LENGTH} characters")
        return v

    @validator("description")
    def validate_description(cls, v: str) -> str:
        if len(v) > MAX_DESCRIPTION_LENGTH:
            raise ValueError(f"Department description must be max {MAX_DESCRIPTION_LENGTH} characters")
        return v

class GovernmentSalaryConfig(BaseModel):
    """政府薪資配置."""

    enabled: bool = True
    payment_interval_hours: int = 24
    base_salary: int = 100
    role_multipliers: dict[str, float] = {}

    @validator("payment_interval_hours")
    def validate_payment_interval(cls, v: int) -> int:
        if v < MIN_PAYMENT_INTERVAL or v > MAX_PAYMENT_INTERVAL:  # 最多一周
            raise ValueError(f"Payment interval must be between {MIN_PAYMENT_INTERVAL} and {MAX_PAYMENT_INTERVAL} hours")
        return v

    @validator("base_salary")
    def validate_base_salary(cls, v: int) -> int:
        if v < MIN_BASE_SALARY or v > MAX_BASE_SALARY:
            raise ValueError(f"Base salary must be between {MIN_BASE_SALARY} and {MAX_BASE_SALARY}")
        return v

class GovernmentConfig(BaseModel):
    """政府系統配置."""

    enabled: bool = True
    max_departments_per_guild: int = 50
    max_members_per_department: int = 100
    default_departments: list[GovernmentDepartmentConfig] = []
    salary: GovernmentSalaryConfig = GovernmentSalaryConfig()

    @validator("max_departments_per_guild")
    def validate_max_departments(cls, v: int) -> int:
        if v < MIN_POOL_SIZE or v > MAX_DEPARTMENTS_PER_GUILD:
            raise ValueError(f"Max departments per guild must be between {MIN_POOL_SIZE} and {MAX_DEPARTMENTS_PER_GUILD}")
        return v

    @validator("max_members_per_department")
    def validate_max_members(cls, v: int) -> int:
        if v < MIN_POOL_SIZE or v > MAX_MEMBERS_PER_DEPARTMENT:
            raise ValueError(f"Max members per department must be between {MIN_POOL_SIZE} and {MAX_MEMBERS_PER_DEPARTMENT}")
        return v

class ConfigValidator:
    """配置驗證器."""

    def __init__(self, config_dir: str | Path = "config"):
        """初始化驗證器.

        Args:
            config_dir: 配置目錄路徑
        """
        self.config_dir = Path(config_dir)
        self.logger = logging.getLogger(__name__)

    def validate_database_config(
        self, config_path: str | Path | None = None
    ) -> DatabaseConfig:
        """驗證資料庫配置.

        Args:
            config_path: 配置文件路徑, 預設為 config/database.yaml

        Returns:
            驗證後的配置物件

        Raises:
            ValidationError: 當配置無效時
            FileNotFoundError: 當配置文件不存在時
        """
        if config_path is None:
            config_file = self.config_dir / "database.yaml"
        else:
            config_file = Path(config_path)

        if not config_file.exists():
            raise FileNotFoundError(f"Database config file not found: {config_file}")

        try:
            with config_file.open(encoding="utf-8") as f:
                config_data = yaml.safe_load(f)

            # 提取 database 部分
            database_data = config_data.get("database", {})

            # 提取 modules 部分
            modules_data = config_data.get("modules", {})

            # 驗證資料庫配置
            database_config = DatabaseConfig(**database_data)

            # Validate modules config for consistency check
            ModulesConfig(**modules_data)

            self.logger.info(
                f"Database configuration validated successfully: {config_file}"
            )
            return database_config

        except yaml.YAMLError as e:
            raise ValidationError(f"Invalid YAML format in {config_file}: {e}") from e
        except ValidationError as e:
            self.logger.error(f"Database configuration validation failed: {e}")
            raise
        except Exception as e:
            raise ValidationError(f"Unexpected error validating database config: {e}") from e

    def validate_government_config(
        self, config_path: str | Path | None = None
    ) -> GovernmentConfig:
        """驗證政府系統配置.

        Args:
            config_path: 配置文件路徑, 預設為 config/government.yaml

        Returns:
            驗證後的配置物件

        Raises:
            ValidationError: 當配置無效時
            FileNotFoundError: 當配置文件不存在時
        """
        if config_path is None:
            config_file = self.config_dir / "government.yaml"
        else:
            config_file = Path(config_path)

        if not config_file.exists():
            raise FileNotFoundError(f"Government config file not found: {config_file}")

        try:
            with config_file.open(encoding="utf-8") as f:
                config_data = yaml.safe_load(f)

            # 提取 government 部分
            government_data = config_data.get("government", {})

            # 驗證政府配置
            government_config = GovernmentConfig(**government_data)

            self.logger.info(
                f"Government configuration validated successfully: {config_file}"
            )
            return government_config

        except yaml.YAMLError as e:
            raise ValidationError(f"Invalid YAML format in {config_file}: {e}") from e
        except ValidationError as e:
            self.logger.error(f"Government configuration validation failed: {e}")
            raise
        except Exception as e:
            raise ValidationError(f"Unexpected error validating government config: {e}") from e

    def validate_all_configs(self) -> tuple[DatabaseConfig, GovernmentConfig]:
        """驗證所有配置文件.

        Returns:
            (資料庫配置, 政府配置) 元組

        Raises:
            ValidationError: 當任何配置無效時
        """
        database_config = self.validate_database_config()
        government_config = self.validate_government_config()

        # 交叉驗證
        self._cross_validate_configs(database_config, government_config)

        self.logger.info("All configurations validated successfully")
        return database_config, government_config

    def _cross_validate_configs(
        self, database_config: DatabaseConfig, government_config: GovernmentConfig
    ) -> None:
        """交叉驗證配置一致性.

        Args:
            database_config: 資料庫配置
            government_config: 政府配置

        Raises:
            ValidationError: 當配置不一致時
        """
        # 檢查部門數量限制一致性
        if hasattr(database_config, "modules") and hasattr(
            database_config.modules, "department"
        ):
            db_max_depts = getattr(
                database_config.modules.department, "max_departments_per_guild", None
            )
            gov_max_depts = government_config.max_departments_per_guild

            if db_max_depts and db_max_depts != gov_max_depts:
                raise ValidationError(
                    f"Inconsistent max departments setting: database={db_max_depts}, "
                    f"government={gov_max_depts}"
                )

def validate_config_files(
    config_dir: str = "config",
) -> tuple[DatabaseConfig, GovernmentConfig]:
    """驗證配置文件的便利函數.

    Args:
        config_dir: 配置目錄路徑

    Returns:
        (資料庫配置, 政府配置) 元組

    Raises:
        ValidationError: 當配置無效時
    """
    validator = ConfigValidator(config_dir)
    return validator.validate_all_configs()

if __name__ == "__main__":
    # 測試驗證器
    try:
        db_config, gov_config = validate_config_files()
        print("✅ All configurations are valid!")
        print(f"Database type: {db_config.type}")
        print(f"Government enabled: {gov_config.enabled}")
        print(f"Max departments: {gov_config.max_departments_per_guild}")
    except Exception as e:
        print(f"❌ Configuration validation failed: {e}")
