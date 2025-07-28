"""Tests for modern Python 3.12 features and architecture."""

import pytest

from src.core.compat import (
    AsyncIteratorWrapper,
    ensure_awaitable,
    safe_async_iterator,
)
from src.core.config import Settings
from src.core.container import Container
from src.core.database import BaseRepository, DatabasePool
from src.core.logger import BotLogger, get_logger


class TestConfiguration:
    """Test modern configuration system."""

    def test_settings_creation(self, tmp_path):
        """Test that settings can be created with defaults."""
        # Create temporary .env file
        env_file = tmp_path / ".env"
        env_file.write_text("TOKEN=test_token_MTI123456789\nENVIRONMENT=development")

        # Test settings loading
        settings = Settings(_env_file=str(env_file))

        assert settings.token == "test_token_MTI123456789"
        assert settings.environment == "development"
        assert settings.database.pool_size == 10
        assert settings.logging.level == "INFO"

    def test_settings_validation(self):
        """Test settings validation."""
        with pytest.raises(ValueError, match="Invalid Discord bot token"):
            Settings(token="invalid_token")


class TestStructuredLogging:
    """Test structured logging system."""

    def test_logger_creation(self):
        """Test logger creation."""
        logger = get_logger("test")
        assert isinstance(logger, BotLogger)
        assert logger.name == "test"

    def test_logger_context_binding(self):
        """Test logger context binding."""
        logger = get_logger("test")

        # Test user context binding
        user_logger = logger.with_user(12345, "testuser")
        assert isinstance(user_logger, BotLogger)

        # Test guild context binding
        guild_logger = logger.with_guild(67890, "Test Guild")
        assert isinstance(guild_logger, BotLogger)


class TestDependencyInjection:
    """Test dependency injection container."""

    def test_container_creation(self):
        """Test container creation and basic registration."""
        container = Container()

        # Test that core services are registered
        assert container.is_registered(Settings)
        assert container.is_registered(Container)

    def test_singleton_registration(self):
        """Test singleton service registration."""
        container = Container()

        class TestService:
            def __init__(self):
                self.value = "test"

        # Register singleton
        container.register_singleton(TestService)

        # Get instances
        instance1 = container.get(TestService)
        instance2 = container.get(TestService)

        # Should be the same instance
        assert instance1 is instance2
        assert instance1.value == "test"

    def test_transient_registration(self):
        """Test transient service registration."""
        container = Container()

        class TestService:
            def __init__(self):
                self.value = "test"

        # Register transient
        container.register_transient(TestService)

        # Get instances
        instance1 = container.get(TestService)
        instance2 = container.get(TestService)

        # Should be different instances
        assert instance1 is not instance2
        assert instance1.value == instance2.value == "test"


class TestAsyncCompatibility:
    """Test Python 3.12 async compatibility helpers."""

    @pytest.mark.asyncio
    async def test_safe_async_iterator_with_coroutine(self):
        """Test safe async iterator with coroutine."""

        async def mock_coroutine():
            """Mock coroutine that returns an async iterable."""

            async def async_generator():
                for i in range(3):
                    yield i

            return async_generator()

        # Test with coroutine
        results = []
        async for item in safe_async_iterator(mock_coroutine()):
            results.append(item)

        assert results == [0, 1, 2]

    @pytest.mark.asyncio
    async def test_safe_async_iterator_with_async_iterable(self):
        """Test safe async iterator with direct async iterable."""

        async def async_generator():
            for i in range(3):
                yield i

        # Test with async iterable
        results = []
        async for item in safe_async_iterator(async_generator()):
            results.append(item)

        assert results == [0, 1, 2]

    @pytest.mark.asyncio
    async def test_ensure_awaitable(self):
        """Test ensure awaitable function."""

        # Test with coroutine
        async def async_func():
            return "async_result"

        result = await ensure_awaitable(async_func())
        assert result == "async_result"

        # Test with regular value
        result = await ensure_awaitable("regular_result")
        assert result == "regular_result"

    def test_async_iterator_wrapper(self):
        """Test async iterator wrapper."""

        async def mock_async_iterable():
            for i in range(3):
                yield i

        wrapper = AsyncIteratorWrapper(mock_async_iterable())

        # Test that wrapper has correct methods
        assert hasattr(wrapper, "__aiter__")
        assert hasattr(wrapper, "__anext__")


@pytest.mark.asyncio
class TestDatabasePool:
    """Test database connection pool."""

    async def test_database_pool_creation(self, tmp_path):
        """Test database pool creation."""
        # Create test settings
        settings = Settings(
            token="test_MTI123456789",
            database__sqlite_path=tmp_path / "test_dbs",
        )

        # Create pool
        db_path = tmp_path / "test.db"
        pool = DatabasePool(db_path, settings)

        # Initialize pool
        await pool.initialize()

        # Test pool statistics
        stats = pool.get_stats()
        assert stats["max_size"] == settings.database.pool_size
        assert stats["total_connections"] >= 0

        # Cleanup
        await pool.close_all()

    async def test_database_connection_context_manager(self, tmp_path):
        """Test database connection context manager."""
        # Create test settings
        settings = Settings(
            token="test_MTI123456789",
            database__sqlite_path=tmp_path / "test_dbs",
        )

        # Create pool
        db_path = tmp_path / "test.db"
        pool = DatabasePool(db_path, settings)
        await pool.initialize()

        # Test connection context manager
        async with pool.get_connection() as conn:
            assert conn is not None

            # Test basic query
            cursor = await conn.execute("SELECT 1")
            result = await cursor.fetchone()
            assert result[0] == 1

        # Cleanup
        await pool.close_all()


class TestBaseRepository:
    """Test base repository functionality."""

    @pytest.fixture
    async def test_repository(self, tmp_path):
        """Create a test repository."""
        # Create test settings
        settings = Settings(
            token="test_MTI123456789",
            database__sqlite_path=tmp_path / "test_dbs",
        )

        # Create pool
        db_path = tmp_path / "test.db"
        pool = DatabasePool(db_path, settings)
        await pool.initialize()

        # Create test table
        async with pool.get_connection() as conn:
            await conn.execute("""
                CREATE TABLE test_table (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    value INTEGER
                )
            """)
            await conn.commit()

        # Create repository
        repo = BaseRepository(pool, "test_table")

        yield repo

        # Cleanup
        await pool.close_all()

    @pytest.mark.asyncio
    async def test_repository_basic_operations(self, test_repository):
        """Test basic repository operations."""
        repo = test_repository

        # Test count (should be 0 initially)
        count = await repo.count()
        assert count == 0

        # Test exists (should be False)
        exists = await repo.exists(name="test")
        assert not exists

        # Insert test data
        await repo.execute_query(
            "INSERT INTO test_table (name, value) VALUES (?, ?)", ("test_item", 42)
        )

        # Test count (should be 1 now)
        count = await repo.count()
        assert count == 1

        # Test exists (should be True now)
        exists = await repo.exists(name="test_item")
        assert exists

        # Test get_all
        all_items = await repo.get_all()
        assert len(all_items) == 1
        assert all_items[0]["name"] == "test_item"
        assert all_items[0]["value"] == 42


class TestModernCogExample:
    """Test modern cog implementation."""

    def test_cog_structure(self):
        """Test that the modern cog has proper structure."""
        from src.cogs.example_modern_cog import ModernExampleCog

        # Test that cog class exists and has proper methods
        assert hasattr(ModernExampleCog, "cog_load")
        assert hasattr(ModernExampleCog, "cog_unload")
        assert hasattr(ModernExampleCog, "set_example_data")
        assert hasattr(ModernExampleCog, "get_example_data")


if __name__ == "__main__":
    pytest.main([__file__])
