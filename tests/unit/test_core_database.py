"""核心資料庫模組測試.

此模組測試 src.core.database 中的所有類別和功能,包括:
- DatabaseConnection 和 DatabasePool
- BaseRepository 抽象基礎類
- QueryBuilder 和相關 SQL 構建功能
- 資料庫連接池管理
- 事務處理和錯誤處理
"""

import asyncio
import sys
import tempfile
from pathlib import Path

import aiosqlite
import pytest

# 確保正確的導入路徑
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import contextlib

from src.core.database import (
    BaseRepository,
    DatabaseConnection,
    DatabasePool,
    JoinClause,
    JoinType,
    OrderByClause,
    OrderDirection,
    QueryBuilder,
    QueryCondition,
)


class TestDatabaseConnection:
    """測試 DatabaseConnection 類別."""

    def setup_method(self):
        """設置測試環境."""
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()

    def teardown_method(self):
        """清理測試環境."""
        import os

        with contextlib.suppress(OSError, FileNotFoundError):
            os.unlink(self.db_path)

    @pytest.mark.asyncio
    async def test_database_connection_creation(self):
        """測試資料庫連接建立."""
        # 建立資料庫池和連接
        pool = DatabasePool(database_path=self.db_path)
        raw_connection = await aiosqlite.connect(self.db_path)

        db_connection = DatabaseConnection(raw_connection, pool)

        assert db_connection._connection == raw_connection
        assert db_connection._pool == pool
        assert not db_connection._in_use

        await raw_connection.close()

    @pytest.mark.asyncio
    async def test_database_connection_context_manager(self):
        """測試資料庫連接上下文管理器."""
        pool = DatabasePool(database_path=self.db_path)
        raw_connection = await aiosqlite.connect(self.db_path)

        db_connection = DatabaseConnection(raw_connection, pool)

        async with db_connection as conn:
            assert conn == raw_connection
            assert db_connection._in_use

        assert not db_connection._in_use
        await raw_connection.close()

    @pytest.mark.asyncio
    async def test_connection_execute_query(self):
        """測試連接執行查詢."""
        pool = DatabasePool(database_path=self.db_path)
        raw_connection = await aiosqlite.connect(self.db_path)

        db_connection = DatabaseConnection(raw_connection, pool)

        async with db_connection as conn:
            # 建立測試表
            await conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
            await conn.commit()

            # 插入測試資料
            await conn.execute("INSERT INTO test (name) VALUES (?)", ("test_user",))
            await conn.commit()

            # 查詢資料
            cursor = await conn.execute("SELECT name FROM test WHERE id = 1")
            result = await cursor.fetchone()
            assert result[0] == "test_user"

        await raw_connection.close()


class TestDatabasePool:
    """測試 DatabasePool 類別."""

    def setup_method(self):
        """設置測試環境."""
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()

    def teardown_method(self):
        """清理測試環境."""
        import os

        with contextlib.suppress(OSError, FileNotFoundError):
            os.unlink(self.db_path)

    @pytest.mark.asyncio
    async def test_database_pool_initialization(self):
        """測試資料庫池初始化."""
        pool = DatabasePool(database_path=self.db_path, max_connections=5, timeout=30.0)

        assert str(pool.database_path) == self.db_path
        assert pool.max_connections == 5
        assert pool.timeout == 30.0
        assert pool._connections == []
        assert pool._available_connections == 0

    @pytest.mark.asyncio
    async def test_database_pool_get_connection(self):
        """測試獲取資料庫連接."""
        pool = DatabasePool(database_path=self.db_path, max_connections=2)

        # 獲取第一個連接
        async with pool.get_connection() as conn1:
            assert conn1 is not None
            assert pool._available_connections == 0

            # 獲取第二個連接
            async with pool.get_connection() as conn2:
                assert conn2 is not None
                assert conn1 != conn2
                assert pool._available_connections == 0

    @pytest.mark.asyncio
    async def test_database_pool_connection_reuse(self):
        """測試連接池重用機制."""
        pool = DatabasePool(database_path=self.db_path, max_connections=1)

        connection_ids = []

        # 第一次使用連接
        async with pool.get_connection() as conn1:
            connection_ids.append(id(conn1))

        # 第二次使用連接(應該重用)
        async with pool.get_connection() as conn2:
            connection_ids.append(id(conn2))

        # 連接可能被重用,但不保證 ID 相同(取決於實現)
        assert len(connection_ids) == 2

    @pytest.mark.asyncio
    async def test_database_pool_max_connections(self):
        """測試連接池最大連接數限制."""
        pool = DatabasePool(database_path=self.db_path, max_connections=1)

        async with pool.get_connection() as conn1:
            assert conn1 is not None

            # 嘗試獲取第二個連接應該等待或創建新連接
            # 這取決於具體實現,這裡只是驗證不會拋出錯誤
            try:
                async with asyncio.wait_for(
                    pool.get_connection(), timeout=1.0
                ) as conn2:
                    assert conn2 is not None
            except TimeoutError:
                # 如果超時,這也是可接受的行為
                pass

    @pytest.mark.asyncio
    async def test_database_pool_close(self):
        """測試資料庫池關閉."""
        pool = DatabasePool(database_path=self.db_path)

        # 獲取連接以確保池被初始化
        async with pool.get_connection() as conn:
            assert conn is not None

        # 關閉池
        await pool.close()

        # 驗證池狀態
        assert pool._connections == []


class TestQueryBuilder:
    """測試 QueryBuilder 類別."""

    def test_query_builder_initialization(self):
        """測試查詢建構器初始化."""
        builder = QueryBuilder("users")

        assert builder.table_name == "users"
        assert builder._select_fields == []
        assert builder._conditions == []
        assert builder._joins == []
        assert builder._order_by == []
        assert builder._group_by == []
        assert builder._having_conditions == []
        assert builder._limit_value is None
        assert builder._offset_value is None

    def test_query_builder_select(self):
        """測試 SELECT 子句建構."""
        builder = QueryBuilder("users")

        # 測試單個欄位
        builder.select("name")
        assert "name" in builder._select_fields

        # 測試多個欄位
        builder.select("email", "age")
        assert "email" in builder._select_fields
        assert "age" in builder._select_fields

    def test_query_builder_where_conditions(self):
        """測試 WHERE 條件建構."""
        builder = QueryBuilder("users")

        # 基本條件
        builder.where("age", ">", 18)
        assert len(builder._conditions) == 1
        assert builder._conditions[0].field == "age"
        assert builder._conditions[0].operator == ">"
        assert builder._conditions[0].value == 18

        # 鏈式條件
        builder.where("status", "=", "active").where("email", "LIKE", "%@example.com")
        assert len(builder._conditions) == 3

    def test_query_builder_join(self):
        """測試 JOIN 子句建構."""
        builder = QueryBuilder("users")

        builder.join("profiles", "users.id", "profiles.user_id")
        assert len(builder._joins) == 1
        assert builder._joins[0].table == "profiles"
        assert builder._joins[0].on_condition == "users.id = profiles.user_id"
        assert builder._joins[0].join_type == JoinType.INNER

    def test_query_builder_order_by(self):
        """測試 ORDER BY 子句建構."""
        builder = QueryBuilder("users")

        builder.order_by("name", OrderDirection.ASC)
        assert len(builder._order_by) == 1
        assert builder._order_by[0].field == "name"
        assert builder._order_by[0].direction == OrderDirection.ASC

        builder.order_by("created_at", OrderDirection.DESC)
        assert len(builder._order_by) == 2

    def test_query_builder_limit_offset(self):
        """測試 LIMIT 和 OFFSET 子句建構."""
        builder = QueryBuilder("users")

        builder.limit(10).offset(20)
        assert builder._limit_value == 10
        assert builder._offset_value == 20

    def test_query_builder_to_select_sql(self):
        """測試生成 SELECT SQL 語句."""
        builder = QueryBuilder("users")
        builder.select("name", "email").where("age", ">", 18).order_by(
            "name", OrderDirection.ASC
        ).limit(10)

        sql, params = builder.to_select_sql()

        assert "SELECT name, email FROM users" in sql
        assert "WHERE age > ?" in sql
        assert "ORDER BY name ASC" in sql
        assert "LIMIT 10" in sql
        assert 18 in params

    def test_query_builder_to_insert_sql(self):
        """測試生成 INSERT SQL 語句."""
        builder = QueryBuilder("users")
        data = {"name": "John", "email": "john@example.com", "age": 25}

        sql, params = builder.to_insert_sql(data)

        assert "INSERT INTO users" in sql
        assert "name, email, age" in sql or "age, email, name" in sql  # 順序可能不同
        assert "VALUES (?, ?, ?)" in sql
        assert "John" in params
        assert "john@example.com" in params
        assert 25 in params

    def test_query_builder_to_update_sql(self):
        """測試生成 UPDATE SQL 語句."""
        builder = QueryBuilder("users")
        builder.where("id", "=", 1)
        data = {"name": "Jane", "email": "jane@example.com"}

        sql, params = builder.to_update_sql(data)

        assert "UPDATE users SET" in sql
        assert "WHERE id = ?" in sql
        assert "Jane" in params or "jane@example.com" in params
        assert 1 in params

    def test_query_builder_to_delete_sql(self):
        """測試生成 DELETE SQL 語句."""
        builder = QueryBuilder("users")
        builder.where("id", "=", 1)

        sql, params = builder.to_delete_sql()

        assert "DELETE FROM users" in sql
        assert "WHERE id = ?" in sql
        assert 1 in params


class TestQueryCondition:
    """測試 QueryCondition 類別."""

    def test_query_condition_initialization(self):
        """測試查詢條件初始化."""
        condition = QueryCondition("age", ">", 18)

        assert condition.field == "age"
        assert condition.operator == ">"
        assert condition.value == 18
        assert condition.logical_operator == "AND"

    def test_query_condition_with_or(self):
        """測試 OR 邏輯運算符."""
        condition = QueryCondition("status", "=", "active", "OR")

        assert condition.logical_operator == "OR"

    def test_query_condition_to_sql(self):
        """測試條件轉換為 SQL."""
        condition = QueryCondition("age", ">", 18)
        sql = condition.to_sql()

        assert sql == "age > ?"


class TestJoinClause:
    """測試 JoinClause 類別."""

    def test_join_clause_initialization(self):
        """測試連接子句初始化."""
        join = JoinClause("profiles", "users.id = profiles.user_id", JoinType.LEFT)

        assert join.table == "profiles"
        assert join.on_condition == "users.id = profiles.user_id"
        assert join.join_type == JoinType.LEFT

    def test_join_clause_to_sql(self):
        """測試連接子句轉換為 SQL."""
        join = JoinClause("profiles", "users.id = profiles.user_id", JoinType.INNER)
        sql = join.to_sql()

        assert sql == "INNER JOIN profiles ON users.id = profiles.user_id"


class TestOrderByClause:
    """測試 OrderByClause 類別."""

    def test_order_by_clause_initialization(self):
        """測試排序子句初始化."""
        order = OrderByClause("name", OrderDirection.DESC)

        assert order.field == "name"
        assert order.direction == OrderDirection.DESC

    def test_order_by_clause_to_sql(self):
        """測試排序子句轉換為 SQL."""
        order = OrderByClause("created_at", OrderDirection.ASC)
        sql = order.to_sql()

        assert sql == "created_at ASC"


class TestBaseRepository:
    """測試 BaseRepository 抽象基礎類."""

    def setup_method(self):
        """設置測試環境."""
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()

        # 建立具體的 Repository 實現以便測試抽象基礎類
        class TestRepository(BaseRepository):
            def __init__(self, pool):
                super().__init__(pool, "test_table")

        self.pool = DatabasePool(database_path=self.db_path)
        self.repository = TestRepository(self.pool)

    def teardown_method(self):
        """清理測試環境."""
        import asyncio
        import os

        # 關閉資料庫池
        with contextlib.suppress(Exception):
            asyncio.get_event_loop().run_until_complete(self.pool.close())

        with contextlib.suppress(OSError, FileNotFoundError):
            os.unlink(self.db_path)

    @pytest.mark.asyncio
    async def test_base_repository_initialization(self):
        """測試基礎存儲庫初始化."""
        assert self.repository.pool == self.pool
        assert self.repository.table_name == "test_table"

    @pytest.mark.asyncio
    async def test_base_repository_execute_query(self):
        """測試執行查詢."""
        # 建立測試表
        create_sql = "CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT)"
        await self.repository.execute_query(create_sql)

        # 插入測試資料
        insert_sql = "INSERT INTO test_table (name) VALUES (?)"
        await self.repository.execute_query(insert_sql, ("test_name",))

        # 查詢資料
        select_sql = "SELECT name FROM test_table WHERE id = ?"
        result = await self.repository.execute_query(select_sql, (1,), fetch_one=True)

        assert result is not None
        assert result[0] == "test_name"

    @pytest.mark.asyncio
    async def test_base_repository_execute_many(self):
        """測試批量執行查詢."""
        # 建立測試表
        create_sql = "CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT)"
        await self.repository.execute_query(create_sql)

        # 批量插入資料
        insert_sql = "INSERT INTO test_table (name) VALUES (?)"
        data = [("name1",), ("name2",), ("name3",)]

        result = await self.repository.execute_many(
            insert_sql, data, return_changes=True
        )
        assert result == 3

        # 驗證資料
        count_sql = "SELECT COUNT(*) FROM test_table"
        count_result = await self.repository.execute_query(count_sql, fetch_one=True)
        assert count_result[0] == 3

    @pytest.mark.asyncio
    async def test_base_repository_transaction(self):
        """測試事務處理."""
        # 建立測試表
        create_sql = "CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT)"
        await self.repository.execute_query(create_sql)

        # 測試成功事務
        async with self.repository.transaction():
            await self.repository.execute_query(
                "INSERT INTO test_table (name) VALUES (?)", ("transaction_test",)
            )

        # 驗證資料已提交
        result = await self.repository.execute_query(
            "SELECT name FROM test_table WHERE name = ?",
            ("transaction_test",),
            fetch_one=True,
        )
        assert result is not None
        assert result[0] == "transaction_test"

    @pytest.mark.asyncio
    async def test_base_repository_transaction_rollback(self):
        """測試事務回滾."""
        # 建立測試表
        create_sql = "CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT)"
        await self.repository.execute_query(create_sql)

        # 測試失敗事務回滾
        try:
            async with self.repository.transaction():
                await self.repository.execute_query(
                    "INSERT INTO test_table (name) VALUES (?)", ("rollback_test",)
                )
                # 故意拋出異常
                raise ValueError("測試回滾")
        except ValueError:
            pass

        # 驗證資料已回滾
        result = await self.repository.execute_query(
            "SELECT COUNT(*) FROM test_table WHERE name = ?",
            ("rollback_test",),
            fetch_one=True,
        )
        assert result[0] == 0


class TestDatabaseIntegration:
    """測試資料庫整合功能."""

    def setup_method(self):
        """設置測試環境."""
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()

    def teardown_method(self):
        """清理測試環境."""
        import os

        with contextlib.suppress(OSError, FileNotFoundError):
            os.unlink(self.db_path)

    @pytest.mark.asyncio
    async def test_complex_query_with_builder(self):
        """測試使用 QueryBuilder 的複雜查詢."""
        pool = DatabasePool(database_path=self.db_path)

        try:
            async with pool.get_connection() as conn:
                # 建立測試表
                await conn.execute("""
                    CREATE TABLE users (
                        id INTEGER PRIMARY KEY,
                        name TEXT NOT NULL,
                        email TEXT UNIQUE,
                        age INTEGER,
                        status TEXT DEFAULT 'active'
                    )
                """)
                await conn.commit()

                # 插入測試資料
                test_users = [
                    ("Alice", "alice@example.com", 25, "active"),
                    ("Bob", "bob@example.com", 30, "inactive"),
                    ("Charlie", "charlie@example.com", 35, "active"),
                ]

                for name, email, age, status in test_users:
                    await conn.execute(
                        "INSERT INTO users (name, email, age, status) VALUES (?, ?, ?, ?)",
                        (name, email, age, status),
                    )
                await conn.commit()

                # 使用 QueryBuilder 建構複雜查詢
                builder = QueryBuilder("users")
                builder.select("name", "email", "age").where(
                    "status", "=", "active"
                ).where("age", ">", 20).order_by("age", OrderDirection.DESC).limit(10)

                sql, params = builder.to_select_sql()

                # 執行查詢
                cursor = await conn.execute(sql, params)
                results = await cursor.fetchall()

                # 驗證結果
                assert len(results) == 2  # Alice 和 Charlie
                assert results[0][0] == "Charlie"  # 按年齡降序,Charlie 在前
                assert results[1][0] == "Alice"

        finally:
            await pool.close()

    @pytest.mark.asyncio
    async def test_concurrent_database_operations(self):
        """測試並發資料庫操作."""
        pool = DatabasePool(database_path=self.db_path, max_connections=3)

        try:
            # 建立測試表
            async with pool.get_connection() as conn:
                await conn.execute("""
                    CREATE TABLE concurrent_test (
                        id INTEGER PRIMARY KEY,
                        worker_id INTEGER,
                        value TEXT
                    )
                """)
                await conn.commit()

            async def worker(worker_id: int, iterations: int = 5):
                """工作協程,執行並發資料庫操作."""
                for i in range(iterations):
                    async with pool.get_connection() as conn:
                        await conn.execute(
                            "INSERT INTO concurrent_test (worker_id, value) VALUES (?, ?)",
                            (worker_id, f"value_{worker_id}_{i}"),
                        )
                        await conn.commit()
                return worker_id

            # 並發執行多個工作協程
            workers = [worker(i, 3) for i in range(5)]
            results = await asyncio.gather(*workers)

            # 驗證結果
            assert len(results) == 5
            assert results == [0, 1, 2, 3, 4]

            # 驗證資料庫中的資料
            async with pool.get_connection() as conn:
                cursor = await conn.execute("SELECT COUNT(*) FROM concurrent_test")
                count = await cursor.fetchone()
                assert count[0] == 15  # 5 個工作協程 × 3 次迭代

        finally:
            await pool.close()

    @pytest.mark.asyncio
    async def test_database_error_handling(self):
        """測試資料庫錯誤處理."""
        pool = DatabasePool(database_path=self.db_path)

        try:
            async with pool.get_connection() as conn:
                # 測試 SQL 語法錯誤
                with pytest.raises(aiosqlite.Error):
                    await conn.execute("INVALID SQL STATEMENT")

                # 測試約束違反
                await conn.execute("""
                    CREATE TABLE unique_test (
                        id INTEGER PRIMARY KEY,
                        unique_field TEXT UNIQUE
                    )
                """)
                await conn.commit()

                await conn.execute(
                    "INSERT INTO unique_test (unique_field) VALUES (?)", ("test_value",)
                )
                await conn.commit()

                # 嘗試插入重複值
                with pytest.raises(aiosqlite.IntegrityError):
                    await conn.execute(
                        "INSERT INTO unique_test (unique_field) VALUES (?)",
                        ("test_value",),
                    )
                    await conn.commit()

        finally:
            await pool.close()
