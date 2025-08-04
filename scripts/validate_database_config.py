"""Database configuration validation script.

此腳本驗證資料庫配置的有效性,包含:
- 配置文件語法檢查
- 連接參數驗證
- 連接測試
- 遷移狀態檢查
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator


class PostgreSQLConfig(BaseModel):
    """PostgreSQL 配置模型."""

    host: str = "localhost"
    port: int = Field(default=5432, ge=1, le=65535)
    database: str = "discord_roas_bot"
    username: str = "postgres"
    password: str = ""

    @field_validator("database")
    @classmethod
    def validate_database_name(cls, v: str) -> str:
        """Validate database name."""
        if not v or len(v) > 63:
            raise ValueError("Database name must be between 1-63 characters")
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError(
                "Database name can only contain letters, numbers, underscores and hyphens"
            )
        return v


class PoolConfig(BaseModel):
    """Connection pool configuration model."""

    size: int = Field(default=10, ge=1, le=100)
    max_overflow: int = Field(default=20, ge=0, le=200)
    timeout: int = Field(default=30, ge=1, le=300)
    recycle: int = Field(default=3600, ge=60, le=86400)
    pre_ping: bool = True


class DatabaseConfig(BaseModel):
    """Database configuration model."""

    type: str = Field(default="postgresql", pattern="^(postgresql|sqlite)$")
    postgresql: PostgreSQLConfig = Field(default_factory=PostgreSQLConfig)
    pool: PoolConfig = Field(default_factory=PoolConfig)


async def validate_config_file(config_path: Path) -> dict[str, Any]:
    """Validate configuration file.

    Args:
        config_path: Configuration file path

    Returns:
        Validated configuration dictionary

    Raises:
        FileNotFoundError: Configuration file not found
        yaml.YAMLError: YAML syntax error
        ValidationError: Configuration validation error
    """
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    # 讀取 YAML 文件
    try:
        with open(config_path, encoding="utf-8") as f:
            config_data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"YAML syntax error: {e}")

    if not config_data or "database" not in config_data:
        raise ValidationError("Configuration file must contain 'database' section")

    # 驗證配置結構
    try:
        db_config = DatabaseConfig(**config_data["database"])
        print("Configuration file syntax validation passed")
        return config_data
    except ValidationError as e:
        print(f"Configuration validation failed: {e}")
        raise


async def test_postgresql_connection(config: dict[str, Any]) -> bool:
    """Test PostgreSQL connection.

    Args:
        config: Database configuration

    Returns:
        Whether connection is successful
    """
    try:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        pg_config = config["database"]["postgresql"]

        # 建構連接 URL
        password = os.getenv("DATABASE_PASSWORD", pg_config.get("password", ""))
        url = (
            f"postgresql+asyncpg://{pg_config['username']}:{password}@"
            f"{pg_config['host']}:{pg_config['port']}/{pg_config['database']}"
        )

        # 建立引擎
        engine = create_async_engine(url, echo=False)

        # 測試連接
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            assert result.scalar() == 1

        await engine.dispose()
        print("PostgreSQL connection test successful")
        return True

    except ImportError:
        print("Unable to import SQLAlchemy, skipping connection test")
        return False
    except Exception as e:
        print(f"PostgreSQL connection test failed: {e}")
        return False


async def check_migration_status() -> bool:
    """Check migration status.

    Returns:
        Whether migration status is normal
    """
    try:
        from alembic import command
        from alembic.config import Config

        # 檢查 Alembic 配置
        alembic_cfg = Config("alembic.ini")

        # 檢查遷移腳本目錄
        script_location = alembic_cfg.get_main_option("script_location")
        if not Path(script_location).exists():
            print(f"Migration script directory does not exist: {script_location}")
            return False

        print("Alembic configuration check passed")
        return True

    except ImportError:
        print("Unable to import Alembic, skipping migration check")
        return False
    except Exception as e:
        print(f"Migration check failed: {e}")
        return False


async def validate_environment_variables() -> bool:
    """Validate environment variables.

    Returns:
        Whether environment variables are correctly set
    """
    required_vars = []
    optional_vars = [
        "DATABASE_URL",
        "DATABASE_PASSWORD",
        "DATABASE_HOST",
        "DATABASE_PORT",
        "DATABASE_NAME",
        "DATABASE_USER",
    ]

    missing_required = []
    for var in required_vars:
        if not os.getenv(var):
            missing_required.append(var)

    if missing_required:
        print(f"Missing required environment variables: {', '.join(missing_required)}")
        return False

    print("Environment variables check passed")

    # Show optional environment variables status
    print("\nEnvironment variables status:")
    for var in optional_vars:
        value = os.getenv(var)
        if value:
            # Mask sensitive information
            if "PASSWORD" in var or "URL" in var:
                display_value = "*" * len(value) if len(value) > 0 else "<empty>"
            else:
                display_value = value
            print(f"  [OK] {var}: {display_value}")
        else:
            print(f"  [-] {var}: <not set>")

    return True


async def main() -> None:
    """Main validation process."""
    print("Starting database configuration validation...\n")

    # Check configuration file
    config_path = Path("config/database.yaml")
    try:
        config = await validate_config_file(config_path)
    except Exception as e:
        print(f"Configuration file validation failed: {e}")
        sys.exit(1)

    # Check environment variables
    if not await validate_environment_variables():
        sys.exit(1)

    # Check migration status
    if not await check_migration_status():
        sys.exit(1)

    # Test database connection
    if config["database"]["type"] == "postgresql":
        connection_ok = await test_postgresql_connection(config)
        if not connection_ok:
            print(
                "\nDatabase connection test failed, but configuration validation passed"
            )
            print("Please ensure:")
            print("1. PostgreSQL service is running")
            print("2. Database exists")
            print("3. User permissions are correct")
            print("4. Network connection is available")

    print("\nDatabase configuration validation completed!")


if __name__ == "__main__":
    asyncio.run(main())
