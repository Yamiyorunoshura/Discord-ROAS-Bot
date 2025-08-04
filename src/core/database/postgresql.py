"""PostgreSQL database management for Discord ROAS Bot v2.0.

此模組提供 PostgreSQL 資料庫連接和 SQLAlchemy ORM 管理功能, 支援:
- 非同步 PostgreSQL 連接池
- SQLAlchemy 2.0 ORM 支援
- Alembic 遷移管理
- 連接生命週期管理
- 錯誤處理和重試機制
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.core.config import Settings, get_settings
from src.core.logger import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

class DatabaseError(Exception):
    """基礎資料庫錯誤."""

    pass

class ConnectionError(DatabaseError):
    """連接錯誤."""

    pass

class MigrationError(DatabaseError):
    """遷移錯誤."""

    pass

class PostgreSQLManager:
    """PostgreSQL 資料庫管理器.

    提供完整的 PostgreSQL 資料庫管理功能, 包含:
    - 非同步連接池管理
    - SQLAlchemy ORM 會話管理
    - 自動連接檢查和重連
    - 錯誤處理和重試
    """

    def __init__(self, settings: Settings | None = None):
        """初始化 PostgreSQL 管理器.

        Args:
            settings: 應用程式設定, 如未提供則使用預設設定
        """
        self.settings = settings or get_settings()
        self.logger = get_logger("postgresql", self.settings)

        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None
        self._initialized = False

    @property
    def database_url(self) -> str:
        """取得資料庫連接 URL."""
        # 優先使用環境變數
        if url := os.getenv("DATABASE_URL"):
            return url

        # 從設定中建構 URL
        host = getattr(self.settings, "database_host", "localhost")
        port = getattr(self.settings, "database_port", 5432)
        name = getattr(self.settings, "database_name", "discord_roas_bot")
        user = getattr(self.settings, "database_user", "postgres")
        password = getattr(self.settings, "database_password", "")

        return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}"

    async def initialize(self) -> None:
        """初始化資料庫連接池和會話工廠."""
        if self._initialized:
            return

        try:
            # 建立非同步引擎
            self._engine = create_async_engine(
                self.database_url,
                echo=getattr(self.settings, "database_echo", False),
                pool_size=getattr(self.settings, "database_pool_size", 10),
                max_overflow=getattr(self.settings, "database_max_overflow", 20),
                pool_timeout=getattr(self.settings, "database_pool_timeout", 30),
                pool_recycle=3600,  # 1 小時回收連接
                pool_pre_ping=True,  # 連接前 ping 檢查
                isolation_level="READ_COMMITTED",
            )

            # 設定連接池事件監聽器
            self._setup_engine_events()

            # 建立會話工廠
            self._session_factory = async_sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )

            # 測試連接
            await self._test_connection()

            self._initialized = True
            self.logger.info("PostgreSQL 資料庫管理器初始化成功")

        except Exception as e:
            self.logger.error(f"PostgreSQL 初始化失敗: {e}")
            raise ConnectionError(f"無法初始化 PostgreSQL 連接: {e}") from e

    def _setup_engine_events(self) -> None:
        """設定引擎事件監聽器."""
        if not self._engine:
            return

        @event.listens_for(self._engine.sync_engine, "connect")
        def set_postgresql_connection_params(dbapi_connection, _connection_record) -> None:
            """設定 PostgreSQL 連接參數."""
            # 設定 PostgreSQL 連接參數
            dbapi_connection.set_session(autocommit=False)

        @event.listens_for(self._engine.sync_engine, "checkout")
        def receive_checkout(_dbapi_connection, _connection_record, _connection_proxy) -> None:
            """連接檢出事件."""
            self.logger.debug("資料庫連接檢出")

        @event.listens_for(self._engine.sync_engine, "checkin")
        def receive_checkin(_dbapi_connection, _connection_record) -> None:
            """連接歸還事件."""
            self.logger.debug("資料庫連接歸還")

    async def _test_connection(self) -> None:
        """測試資料庫連接."""
        if not self._engine:
            raise ConnectionError("引擎未初始化")

        try:
            async with self._engine.begin() as conn:
                result = await conn.execute(text("SELECT 1"))
                assert result.scalar() == 1
                self.logger.debug("資料庫連接測試成功")
        except Exception as e:
            self.logger.error(f"資料庫連接測試失敗: {e}")
            raise ConnectionError(f"資料庫連接測試失敗: {e}") from e

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """取得資料庫會話.

        使用上下文管理器確保會話正確關閉.

        Yields:
            AsyncSession: 資料庫會話

        Raises:
            ConnectionError: 當無法建立會話時
        """
        if not self._initialized:
            await self.initialize()

        if not self._session_factory:
            raise ConnectionError("會話工廠未初始化")

        session = self._session_factory()
        try:
            yield session
        except Exception as e:
            await session.rollback()
            self.logger.error(f"會話執行錯誤, 已回滾: {e}")
            raise
        finally:
            await session.close()

    @asynccontextmanager
    async def get_engine(self) -> AsyncGenerator[AsyncEngine, None]:
        """取得資料庫引擎.

        用於需要直接使用引擎的場景, 如執行 DDL 操作.

        Yields:
            AsyncEngine: 資料庫引擎
        """
        if not self._initialized:
            await self.initialize()

        if not self._engine:
            raise ConnectionError("引擎未初始化")

        yield self._engine

    async def execute_raw_sql(
        self, sql: str, parameters: dict[str, Any] | None = None
    ) -> Any:
        """執行原始 SQL 語句.

        Args:
            sql: SQL 語句
            parameters: SQL 參數

        Returns:
            查詢結果
        """
        async with self.get_engine() as engine, engine.begin() as conn:
            result = await conn.execute(text(sql), parameters or {})
            return result

    async def check_health(self) -> dict[str, Any]:
        """檢查資料庫健康狀態.

        Returns:
            包含健康狀態資訊的字典
        """
        health_info = {
            "status": "unhealthy",
            "initialized": self._initialized,
            "engine_available": self._engine is not None,
            "connection_test": False,
            "pool_info": {},
        }

        try:
            if self._engine:
                # 測試連接
                await self._test_connection()
                health_info["connection_test"] = True

                # 取得連接池資訊
                pool_info = self._engine.pool
                health_info["pool_info"] = {
                    "size": getattr(pool_info, "size", lambda: 0)(),
                    "checked_in": getattr(pool_info, "checkedin", lambda: 0)(),
                    "checked_out": getattr(pool_info, "checkedout", lambda: 0)(),
                }

                health_info["status"] = "healthy"

        except Exception as e:
            health_info["error"] = str(e)
            self.logger.warning(f"健康檢查失敗: {e}")

        return health_info

    async def close(self) -> None:
        """關閉資料庫連接."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            self._initialized = False
            self.logger.info("PostgreSQL 連接已關閉")

    async def run_migrations(self, target: str = "head") -> None:
        """執行資料庫遷移.

        Args:
            target: 遷移目標版本, 預設為最新版本

        Raises:
            MigrationError: 當遷移執行失敗時
        """
        try:
            # Import here to avoid circular imports
            from alembic import command  # noqa: PLC0415
            from alembic.config import Config  # noqa: PLC0415

            # 設定 Alembic 配置
            config = Config("alembic.ini")
            config.set_main_option("sqlalchemy.url", self.database_url)

            # 執行遷移
            command.upgrade(config, target)
            self.logger.info(f"資料庫遷移至 {target} 完成")

        except Exception as e:
            self.logger.error(f"資料庫遷移失敗: {e}")
            raise MigrationError(f"遷移執行失敗: {e}") from e

    def __repr__(self) -> str:
        """字串表示."""
        return f"PostgreSQLManager(initialized={self._initialized})"

# 全域 PostgreSQL 管理器實例
_postgresql_manager: PostgreSQLManager | None = None

async def get_postgresql_manager(settings: Settings | None = None) -> PostgreSQLManager:
    """取得 PostgreSQL 管理器實例.

    使用單例模式確保只有一個管理器實例.

    Args:
        settings: 應用程式設定

    Returns:
        PostgreSQL 管理器實例
    """
    global _postgresql_manager  # noqa: PLW0603

    if _postgresql_manager is None:
        _postgresql_manager = PostgreSQLManager(settings)
        await _postgresql_manager.initialize()

    return _postgresql_manager

async def close_postgresql_manager() -> None:
    """關閉全域 PostgreSQL 管理器."""
    global _postgresql_manager  # noqa: PLW0603

    if _postgresql_manager:
        await _postgresql_manager.close()
        _postgresql_manager = None

# 便利函數
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """取得資料庫會話的便利函數."""
    manager = await get_postgresql_manager()
    async with manager.get_session() as session:
        yield session

# Repository 基礎類別
class BaseRepository:
    """Repository 基礎類別.

    提供基本的 CRUD 操作和查詢功能.
    """

    def __init__(self, session: AsyncSession):
        """初始化 Repository.

        Args:
            session: 資料庫會話
        """
        self.session = session
        self.logger = get_logger(f"repo_{self.__class__.__name__}")

    async def commit(self) -> None:
        """提交事務."""
        await self.session.commit()

    async def rollback(self) -> None:
        """回滾事務."""
        await self.session.rollback()

    async def flush(self) -> None:
        """刷新會話."""
        await self.session.flush()

    async def refresh(self, instance: Any) -> None:
        """重新載入實例."""
        await self.session.refresh(instance)

__all__ = [
    "BaseRepository",
    "ConnectionError",
    "DatabaseError",
    "MigrationError",
    "PostgreSQLManager",
    "close_postgresql_manager",
    "get_db_session",
    "get_postgresql_manager",
]
