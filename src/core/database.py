"""Modern database management with Python 3.12 compatibility."""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

import aiosqlite

from src.core.compat import (
    AsyncCursorWrapper,
    fix_database_cursor,
)
from src.core.config import Settings, get_settings
from src.core.logger import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

# Constants
CONNECTION_EXPIRY_SECONDS = 3600  # 1 hour in seconds
SQL_PREVIEW_LENGTH = 100  # Maximum length for SQL preview in logs
BETWEEN_VALUES_COUNT = 2  # Required number of values for BETWEEN operator

class DatabaseError(Exception):
    """Base database error."""

    pass

class ConnectionPoolError(DatabaseError):
    """Connection pool related error."""

    pass

class DatabaseConnection:
    """Wrapper for database connection with Python 3.12 compatibility."""

    def __init__(self, connection: aiosqlite.Connection, pool: DatabasePool):
        """Initialize database connection wrapper.

        Args:
            connection: SQLite connection
            pool: Database pool that owns this connection
        """
        self._connection = connection
        self._pool = pool
        self._in_use = False
        self._created_at = time.time()

    async def execute(self, sql: str, parameters: tuple = ()) -> AsyncCursorWrapper:
        """Execute SQL statement.

        Args:
            sql: SQL statement
            parameters: SQL parameters

        Returns:
            Cursor wrapper with Python 3.12 compatibility
        """
        cursor = await self._connection.execute(sql, parameters)
        return fix_database_cursor(cursor)

    async def executemany(
        self, sql: str, parameters: list[tuple]
    ) -> AsyncCursorWrapper:
        """Execute SQL statement with multiple parameter sets.

        Args:
            sql: SQL statement
            parameters: List of parameter tuples

        Returns:
            Cursor wrapper
        """
        cursor = await self._connection.executemany(sql, parameters)
        return fix_database_cursor(cursor)

    async def commit(self) -> None:
        """Commit current transaction."""
        await self._connection.commit()

    async def rollback(self) -> None:
        """Rollback current transaction."""
        await self._connection.rollback()

    async def close(self) -> None:
        """Close the connection."""
        await self._connection.close()

    @property
    def is_expired(self) -> bool:
        """Check if connection is expired (older than 1 hour)."""
        return time.time() - self._created_at > CONNECTION_EXPIRY_SECONDS

class DatabasePool:
    """Database connection pool with Python 3.12 compatibility."""

    def __init__(self, database_path: Path, settings: Settings):
        """Initialize database pool.

        Args:
            database_path: Path to database file
            settings: Application settings
        """
        self.database_path = database_path
        self.settings = settings
        self.logger = get_logger(f"db_pool_{database_path.stem}", settings)

        # Pool configuration
        self.max_size = settings.database.pool_size
        self.max_overflow = settings.database.max_overflow
        self.timeout = settings.database.pool_timeout

        # Pool state
        self._pool: list[DatabaseConnection] = []
        self._overflow: list[DatabaseConnection] = []
        self._lock = asyncio.Lock()
        self._checked_out: set[DatabaseConnection] = set()

        # Statistics
        self._total_connections = 0
        self._total_checkouts = 0
        self._failed_checkouts = 0

    async def initialize(self) -> None:
        """Initialize the database pool."""
        self.logger.info(
            "Initializing database pool",
            database=str(self.database_path),
            max_size=self.max_size,
            max_overflow=self.max_overflow,
        )

        # Create database directory
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

        # Create initial connections
        async with self._lock:
            for _ in range(min(2, self.max_size)):  # Start with 2 connections
                try:
                    conn = await self._create_connection()
                    self._pool.append(conn)
                except Exception as e:
                    self.logger.error(
                        "Failed to create initial connection", error=str(e)
                    )

        self.logger.info(
            "Database pool initialized", initial_connections=len(self._pool)
        )

    async def _create_connection(self) -> DatabaseConnection:
        """Create a new database connection.

        Returns:
            New database connection
        """
        try:
            # Create SQLite connection
            connection = await aiosqlite.connect(
                self.database_path,
                timeout=self.settings.database.query_timeout,
                isolation_level=None,  # Autocommit mode
            )

            # Configure connection
            if self.settings.database.enable_wal_mode:
                await connection.execute("PRAGMA journal_mode=WAL")

            await connection.execute("PRAGMA foreign_keys=ON")
            await connection.execute("PRAGMA synchronous=NORMAL")
            await connection.execute("PRAGMA temp_store=MEMORY")
            await connection.execute("PRAGMA mmap_size=268435456")  # 256MB

            # Wrap connection
            db_conn = DatabaseConnection(connection, self)
            self._total_connections += 1

            self.logger.debug(
                "Created new database connection",
                total_connections=self._total_connections,
            )

            return db_conn

        except Exception as e:
            self.logger.error("Failed to create database connection", error=str(e))
            raise ConnectionPoolError(f"Failed to create connection: {e}") from e

    @asynccontextmanager
    async def get_connection(self) -> AsyncIterator[DatabaseConnection]:
        """Get a connection from the pool.

        Yields:
            Database connection

        Raises:
            ConnectionPoolError: If unable to get connection within timeout
        """
        connection = None
        start_time = time.time()

        try:
            # Get connection with timeout
            connection = await asyncio.wait_for(
                self._acquire_connection(),
                timeout=self.timeout,
            )

            self._total_checkouts += 1

            self.logger.debug(
                "Connection acquired",
                checkout_time=time.time() - start_time,
                pool_size=len(self._pool),
                checked_out=len(self._checked_out),
            )

            yield connection

        except TimeoutError:
            self._failed_checkouts += 1
            self.logger.error(
                "Connection acquisition timeout",
                timeout=self.timeout,
                pool_size=len(self._pool),
                checked_out=len(self._checked_out),
            )
            raise ConnectionPoolError(
                f"Connection acquisition timeout after {self.timeout}s"
            ) from None

        except Exception as e:
            self._failed_checkouts += 1
            self.logger.error("Connection acquisition failed", error=str(e))
            raise

        finally:
            # Return connection to pool
            if connection:
                await self._release_connection(connection)

    async def _acquire_connection(self) -> DatabaseConnection:
        """Acquire a connection from the pool."""
        async with self._lock:
            # Try to get from pool
            if self._pool:
                connection = self._pool.pop()

                # Check if connection is expired
                if connection.is_expired:
                    with suppress(Exception):
                        await connection.close()

                    # Create new connection
                    connection = await self._create_connection()

                self._checked_out.add(connection)
                return connection

            # Try to create overflow connection
            if len(self._overflow) < self.max_overflow:
                connection = await self._create_connection()
                self._overflow.append(connection)
                self._checked_out.add(connection)
                return connection

            # Wait for connection to be returned
            # This is a simplified implementation - in production you'd want
            # a proper queuing mechanism
            raise ConnectionPoolError(
                "No connections available and max overflow reached"
            )

    async def _release_connection(self, connection: DatabaseConnection) -> None:
        """Release a connection back to the pool."""
        async with self._lock:
            self._checked_out.discard(connection)

            # If it's an overflow connection, close it
            if connection in self._overflow:
                self._overflow.remove(connection)
                try:
                    await connection.close()
                except Exception as e:
                    self.logger.warning(
                        "Error closing overflow connection", error=str(e)
                    )
            else:
                # Return to main pool
                self._pool.append(connection)

    async def close_all(self) -> None:
        """Close all connections in the pool."""
        self.logger.info("Closing all database connections")

        async with self._lock:
            # Close pool connections
            for connection in self._pool:
                try:
                    await connection.close()
                except Exception as e:
                    self.logger.warning("Error closing pool connection", error=str(e))

            # Close overflow connections
            for connection in self._overflow:
                try:
                    await connection.close()
                except Exception as e:
                    self.logger.warning(
                        "Error closing overflow connection", error=str(e)
                    )

            # Close checked out connections
            for connection in self._checked_out:
                try:
                    await connection.close()
                except Exception as e:
                    self.logger.warning(
                        "Error closing checked out connection", error=str(e)
                    )

            self._pool.clear()
            self._overflow.clear()
            self._checked_out.clear()

        self.logger.info("All database connections closed")

    def get_stats(self) -> dict[str, Any]:
        """Get pool statistics.

        Returns:
            Dictionary with pool statistics
        """
        return {
            "pool_size": len(self._pool),
            "overflow_size": len(self._overflow),
            "checked_out": len(self._checked_out),
            "total_connections": self._total_connections,
            "total_checkouts": self._total_checkouts,
            "failed_checkouts": self._failed_checkouts,
            "max_size": self.max_size,
            "max_overflow": self.max_overflow,
        }

class BaseRepository:
    """Base repository class with common database operations."""

    def __init__(self, pool: DatabasePool, table_name: str):
        """Initialize repository.

        Args:
            pool: Database connection pool
            table_name: Name of the table this repository manages
        """
        self.pool = pool
        self.table_name = table_name
        self.logger = get_logger(f"repo_{table_name}", pool.settings)

    async def execute_query(
        self,
        sql: str,
        parameters: tuple = (),
        fetch_one: bool = False,
        fetch_all: bool = False,
    ) -> Any:
        """Execute a query with proper error handling.

        Args:
            sql: SQL query
            parameters: Query parameters
            fetch_one: Whether to fetch one row
            fetch_all: Whether to fetch all rows

        Returns:
            Query result or None
        """
        async with self.pool.get_connection() as conn:
            try:
                cursor = await conn.execute(sql, parameters)

                if fetch_one:
                    return await cursor.fetchone()
                elif fetch_all:
                    return await cursor.fetchall()
                else:
                    await conn.commit()
                    return cursor

            except Exception as e:
                await conn.rollback()
                self.logger.error(
                    "Query execution failed",
                    sql=sql[:SQL_PREVIEW_LENGTH] + "..." if len(sql) > SQL_PREVIEW_LENGTH else sql,
                    error=str(e),
                )
                raise DatabaseError(f"Query failed: {e}") from e

    async def get_by_id(self, id_value: int | str) -> dict[str, Any] | None:
        """Get record by ID.

        Args:
            id_value: ID value to search for

        Returns:
            Record dictionary or None if not found
        """
        sql = f"SELECT * FROM {self.table_name} WHERE id = ?"
        row = await self.execute_query(sql, (id_value,), fetch_one=True)

        if row:
            return dict(row)
        return None

    async def get_all(
        self, limit: int | None = None, offset: int = 0
    ) -> list[dict[str, Any]]:
        """Get all records with optional pagination.

        Args:
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            List of record dictionaries
        """
        sql = f"SELECT * FROM {self.table_name}"
        parameters = []

        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            parameters.extend([limit, offset])

        rows = await self.execute_query(sql, tuple(parameters), fetch_all=True)
        return [dict(row) for row in rows or []]

    async def count(self) -> int:
        """Count total records in table.

        Returns:
            Total number of records
        """
        sql = f"SELECT COUNT(*) FROM {self.table_name}"
        row = await self.execute_query(sql, fetch_one=True)
        return row[0] if row else 0

    async def exists(self, **conditions) -> bool:
        """Check if record exists with given conditions.

        Args:
            **conditions: Field-value pairs for WHERE clause

        Returns:
            True if record exists, False otherwise
        """
        if not conditions:
            return False

        where_clause = " AND ".join(f"{key} = ?" for key in conditions)
        sql = f"SELECT 1 FROM {self.table_name} WHERE {where_clause} LIMIT 1"
        parameters = tuple(conditions.values())

        row = await self.execute_query(sql, parameters, fetch_one=True)
        return row is not None

# Global database pools
_pools: dict[str, DatabasePool] = {}

async def get_database_pool(
    database_name: str, settings: Settings | None = None
) -> DatabasePool:
    """Get or create a database pool.

    Args:
        database_name: Name of the database
        settings: Optional settings instance

    Returns:
        Database pool
    """
    if settings is None:
        settings = get_settings()

    if database_name not in _pools:
        database_path = settings.database.sqlite_path / f"{database_name}.db"
        pool = DatabasePool(database_path, settings)
        await pool.initialize()
        _pools[database_name] = pool

    return _pools[database_name]

async def close_all_pools() -> None:
    """Close all database pools."""
    for pool in _pools.values():
        await pool.close_all()
    _pools.clear()

class JoinType(Enum):
    """SQL JOIN 類型列舉."""

    INNER = "INNER JOIN"
    LEFT = "LEFT JOIN"
    RIGHT = "RIGHT JOIN"
    FULL = "FULL OUTER JOIN"
    CROSS = "CROSS JOIN"

class OrderDirection(Enum):
    """排序方向列舉."""

    ASC = "ASC"
    DESC = "DESC"

@dataclass
class QueryCondition:
    """查詢條件資料類別."""

    field: str
    operator: str
    value: Any
    connector: str = "AND"  # AND 或 OR

    def to_sql(self) -> tuple[str, Any]:
        """轉換為 SQL 條件.

        Returns:
            SQL 條件字串和參數值的元組
        """
        operator_upper = self.operator.upper()

        # Handle IN operator
        if operator_upper == "IN":
            if isinstance(self.value, list | tuple):
                placeholders = ",".join(["?" for _ in self.value])
                sql_condition = f"{self.field} IN ({placeholders})"
                parameters = self.value
            else:
                sql_condition = f"{self.field} IN (?)"
                parameters = (self.value,)

        # Handle BETWEEN operator
        elif operator_upper == "BETWEEN":
            if isinstance(self.value, list | tuple) and len(self.value) == BETWEEN_VALUES_COUNT:
                sql_condition = f"{self.field} BETWEEN ? AND ?"
                parameters = self.value
            else:
                raise ValueError("BETWEEN 操作符需要包含兩個值的列表或元組")

        # Handle NULL operators
        elif operator_upper in ("IS NULL", "IS NOT NULL"):
            sql_condition = f"{self.field} {operator_upper}"
            parameters = ()

        # Handle LIKE operator
        elif operator_upper == "LIKE":
            sql_condition = f"{self.field} LIKE ?"
            parameters = (self.value,)

        # Handle standard operators
        else:
            sql_condition = f"{self.field} {self.operator} ?"
            parameters = (self.value,)

        return sql_condition, parameters

@dataclass
class JoinClause:
    """JOIN 子句資料類別."""

    join_type: JoinType
    table: str
    on_condition: str
    alias: str | None = None

    def to_sql(self) -> str:
        """轉換為 SQL JOIN 子句."""
        table_part = f"{self.table} AS {self.alias}" if self.alias else self.table
        return f"{self.join_type.value} {table_part} ON {self.on_condition}"

@dataclass
class OrderByClause:
    """ORDER BY 子句資料類別."""

    field: str
    direction: OrderDirection = OrderDirection.ASC

    def to_sql(self) -> str:
        """轉換為 SQL ORDER BY 子句."""
        return f"{self.field} {self.direction.value}"

class QueryBuilder:
    """現代化 SQL 查詢建構器.

    支援複雜查詢建構,包括:
    - SELECT, INSERT, UPDATE, DELETE 操作
    - 複雜 WHERE 條件
    - JOIN 查詢
    - 子查詢
    - 聚合函數
    - 分頁
    - 批量操作
    """

    def __init__(self, table: str, alias: str | None = None):
        """初始化查詢建構器.

        Args:
            table: 主表名稱
            alias: 表別名
        """
        self.table = table
        self.alias = alias
        self._select_fields: list[str] = []
        self._where_conditions: list[QueryCondition] = []
        self._join_clauses: list[JoinClause] = []
        self._order_by: list[OrderByClause] = []
        self._group_by: list[str] = []
        self._having_conditions: list[QueryCondition] = []
        self._limit_value: int | None = None
        self._offset_value: int = 0
        self._distinct: bool = False

        # INSERT/UPDATE 相關
        self._insert_data: dict[str, Any] = {}
        self._update_data: dict[str, Any] = {}
        self._bulk_insert_data: list[dict[str, Any]] = []

        # 子查詢支援
        self._subqueries: dict[str, QueryBuilder] = {}

    def select(self, *fields: str) -> QueryBuilder:
        """設定 SELECT 欄位.

        Args:
            *fields: 要查詢的欄位列表

        Returns:
            自身實例,支援鏈式調用
        """
        if fields:
            self._select_fields.extend(fields)
        else:
            self._select_fields = ["*"]
        return self

    def distinct(self) -> QueryBuilder:
        """設定 DISTINCT 查詢."""
        self._distinct = True
        return self

    def where(
        self, field: str, operator: str = "=", value: Any = None, connector: str = "AND"
    ) -> QueryBuilder:
        """添加 WHERE 條件.

        Args:
            field: 欄位名稱
            operator: 比較操作符
            value: 比較值
            connector: 邏輯連接符 (AND/OR)

        Returns:
            自身實例,支援鏈式調用
        """
        condition = QueryCondition(field, operator, value, connector)
        self._where_conditions.append(condition)
        return self

    def where_in(
        self, field: str, values: list[Any], connector: str = "AND"
    ) -> QueryBuilder:
        """添加 WHERE IN 條件."""
        return self.where(field, "IN", values, connector)

    def where_between(
        self, field: str, start: Any, end: Any, connector: str = "AND"
    ) -> QueryBuilder:
        """添加 WHERE BETWEEN 條件."""
        return self.where(field, "BETWEEN", [start, end], connector)

    def where_like(
        self, field: str, pattern: str, connector: str = "AND"
    ) -> QueryBuilder:
        """添加 WHERE LIKE 條件."""
        return self.where(field, "LIKE", pattern, connector)

    def where_null(self, field: str, connector: str = "AND") -> QueryBuilder:
        """添加 WHERE IS NULL 條件."""
        return self.where(field, "IS NULL", None, connector)

    def where_not_null(self, field: str, connector: str = "AND") -> QueryBuilder:
        """添加 WHERE IS NOT NULL 條件."""
        return self.where(field, "IS NOT NULL", None, connector)

    def or_where(
        self, field: str, operator: str = "=", value: Any = None
    ) -> QueryBuilder:
        """添加 OR WHERE 條件."""
        return self.where(field, operator, value, "OR")

    def join(
        self,
        table: str,
        on_condition: str,
        join_type: JoinType = JoinType.INNER,
        alias: str | None = None,
    ) -> QueryBuilder:
        """添加 JOIN 子句.

        Args:
            table: 要 JOIN 的表名
            on_condition: JOIN 條件
            join_type: JOIN 類型
            alias: 表別名

        Returns:
            自身實例,支援鏈式調用
        """
        join_clause = JoinClause(join_type, table, on_condition, alias)
        self._join_clauses.append(join_clause)
        return self

    def left_join(
        self, table: str, on_condition: str, alias: str | None = None
    ) -> QueryBuilder:
        """添加 LEFT JOIN."""
        return self.join(table, on_condition, JoinType.LEFT, alias)

    def right_join(
        self, table: str, on_condition: str, alias: str | None = None
    ) -> QueryBuilder:
        """添加 RIGHT JOIN."""
        return self.join(table, on_condition, JoinType.RIGHT, alias)

    def inner_join(
        self, table: str, on_condition: str, alias: str | None = None
    ) -> QueryBuilder:
        """添加 INNER JOIN."""
        return self.join(table, on_condition, JoinType.INNER, alias)

    def order_by(
        self, field: str, direction: OrderDirection = OrderDirection.ASC
    ) -> QueryBuilder:
        """添加 ORDER BY 子句.

        Args:
            field: 排序欄位
            direction: 排序方向

        Returns:
            自身實例,支援鏈式調用
        """
        order_clause = OrderByClause(field, direction)
        self._order_by.append(order_clause)
        return self

    def order_by_desc(self, field: str) -> QueryBuilder:
        """添加 ORDER BY DESC."""
        return self.order_by(field, OrderDirection.DESC)

    def group_by(self, *fields: str) -> QueryBuilder:
        """添加 GROUP BY 子句."""
        self._group_by.extend(fields)
        return self

    def having(
        self, field: str, operator: str = "=", value: Any = None, connector: str = "AND"
    ) -> QueryBuilder:
        """添加 HAVING 條件(用於 GROUP BY)."""
        condition = QueryCondition(field, operator, value, connector)
        self._having_conditions.append(condition)
        return self

    def limit(self, count: int) -> QueryBuilder:
        """設定 LIMIT."""
        self._limit_value = count
        return self

    def offset(self, count: int) -> QueryBuilder:
        """設定 OFFSET."""
        self._offset_value = count
        return self

    def paginate(self, page: int, per_page: int) -> QueryBuilder:
        """分頁查詢.

        Args:
            page: 頁碼(從 1 開始)
            per_page: 每頁記錄數

        Returns:
            自身實例,支援鏈式調用
        """
        offset = (page - 1) * per_page
        return self.limit(per_page).offset(offset)

    def insert(self, data: dict[str, Any]) -> QueryBuilder:
        """設定 INSERT 資料.

        Args:
            data: 要插入的資料字典

        Returns:
            自身實例,支援鏈式調用
        """
        self._insert_data = data
        return self

    def bulk_insert(self, data_list: list[dict[str, Any]]) -> QueryBuilder:
        """設定批量 INSERT 資料.

        Args:
            data_list: 要批量插入的資料列表

        Returns:
            自身實例,支援鏈式調用
        """
        self._bulk_insert_data = data_list
        return self

    def update(self, data: dict[str, Any]) -> QueryBuilder:
        """設定 UPDATE 資料.

        Args:
            data: 要更新的資料字典

        Returns:
            自身實例,支援鏈式調用
        """
        self._update_data = data
        return self

    def increment(self, field: str, amount: int = 1) -> QueryBuilder:
        """欄位遞增.

        Args:
            field: 要遞增的欄位
            amount: 遞增量

        Returns:
            自身實例,支援鏈式調用
        """
        self._update_data[field] = f"{field} + {amount}"
        return self

    def decrement(self, field: str, amount: int = 1) -> QueryBuilder:
        """欄位遞減.

        Args:
            field: 要遞減的欄位
            amount: 遞減量

        Returns:
            自身實例,支援鏈式調用
        """
        self._update_data[field] = f"{field} - {amount}"
        return self

    def count(self, field: str = "*") -> QueryBuilder:
        """COUNT 聚合函數."""
        return self.select(f"COUNT({field}) as count")

    def sum(self, field: str) -> QueryBuilder:
        """SUM 聚合函數."""
        return self.select(f"SUM({field}) as sum")

    def avg(self, field: str) -> QueryBuilder:
        """AVG 聚合函數."""
        return self.select(f"AVG({field}) as avg")

    def max(self, field: str) -> QueryBuilder:
        """MAX 聚合函數."""
        return self.select(f"MAX({field}) as max")

    def min(self, field: str) -> QueryBuilder:
        """MIN 聚合函數."""
        return self.select(f"MIN({field}) as min")

    def to_select_sql(self) -> tuple[str, list[Any]]:
        """建構 SELECT SQL 查詢.

        Returns:
            SQL 字串和參數列表的元組
        """
        # SELECT 子句
        select_fields = ", ".join(self._select_fields) if self._select_fields else "*"
        distinct_clause = "DISTINCT " if self._distinct else ""

        # FROM 子句
        table_part = f"{self.table} AS {self.alias}" if self.alias else self.table

        sql_parts = [f"SELECT {distinct_clause}{select_fields}", f"FROM {table_part}"]
        parameters: list[Any] = []

        # JOIN 子句
        for join_clause in self._join_clauses:
            sql_parts.append(join_clause.to_sql())

        # WHERE 子句
        if self._where_conditions:
            where_parts = []
            for i, condition in enumerate(self._where_conditions):
                condition_sql, condition_params = condition.to_sql()
                if i == 0:
                    where_parts.append(condition_sql)
                else:
                    where_parts.append(f"{condition.connector} {condition_sql}")

                if isinstance(condition_params, list | tuple):
                    parameters.extend(condition_params)
                elif condition_params:
                    parameters.append(condition_params)

            sql_parts.append(f"WHERE {' '.join(where_parts)}")

        # GROUP BY 子句
        if self._group_by:
            sql_parts.append(f"GROUP BY {', '.join(self._group_by)}")

        # HAVING 子句
        if self._having_conditions:
            having_parts = []
            for i, condition in enumerate(self._having_conditions):
                condition_sql, condition_params = condition.to_sql()
                if i == 0:
                    having_parts.append(condition_sql)
                else:
                    having_parts.append(f"{condition.connector} {condition_sql}")

                if isinstance(condition_params, list | tuple):
                    parameters.extend(condition_params)
                elif condition_params:
                    parameters.append(condition_params)

            sql_parts.append(f"HAVING {' '.join(having_parts)}")

        # ORDER BY 子句
        if self._order_by:
            order_parts = [order_clause.to_sql() for order_clause in self._order_by]
            sql_parts.append(f"ORDER BY {', '.join(order_parts)}")

        # LIMIT 和 OFFSET 子句
        if self._limit_value is not None:
            sql_parts.append(f"LIMIT {self._limit_value}")
            if self._offset_value > 0:
                sql_parts.append(f"OFFSET {self._offset_value}")

        return " ".join(sql_parts), parameters

    def to_insert_sql(self) -> tuple[str, list[Any]]:
        """建構 INSERT SQL 查詢.

        Returns:
            SQL 字串和參數列表的元組
        """
        if self._bulk_insert_data:
            return self._build_bulk_insert_sql()
        elif self._insert_data:
            return self._build_single_insert_sql()
        else:
            raise ValueError("沒有設定 INSERT 資料")

    def _build_single_insert_sql(self) -> tuple[str, list[Any]]:
        """建構單筆 INSERT SQL."""
        fields = list(self._insert_data.keys())
        placeholders = [",".join(["?" for _ in fields])]
        values = list(self._insert_data.values())

        sql = (
            f"INSERT INTO {self.table} ({', '.join(fields)}) VALUES ({placeholders[0]})"
        )
        return sql, values

    def _build_bulk_insert_sql(self) -> tuple[str, list[Any]]:
        """建構批量 INSERT SQL."""
        if not self._bulk_insert_data:
            raise ValueError("批量插入資料為空")

        # 使用第一筆資料的鍵作為欄位名稱
        fields = list(self._bulk_insert_data[0].keys())
        placeholders = ",".join(["?" for _ in fields])

        # 建構 VALUES 子句
        values_placeholders = []
        parameters = []

        for data in self._bulk_insert_data:
            values_placeholders.append(f"({placeholders})")
            for field in fields:
                parameters.append(data.get(field))

        sql = f"INSERT INTO {self.table} ({', '.join(fields)}) VALUES {', '.join(values_placeholders)}"
        return sql, parameters

    def to_update_sql(self) -> tuple[str, list[Any]]:
        """建構 UPDATE SQL 查詢.

        Returns:
            SQL 字串和參數列表的元組
        """
        if not self._update_data:
            raise ValueError("沒有設定 UPDATE 資料")

        # SET 子句
        set_parts = []
        parameters = []

        for field, value in self._update_data.items():
            if isinstance(value, str) and (" + " in value or " - " in value):
                # 處理遞增/遞減操作
                set_parts.append(f"{field} = {value}")
            else:
                set_parts.append(f"{field} = ?")
                parameters.append(value)

        sql = f"UPDATE {self.table} SET {', '.join(set_parts)}"

        # WHERE 子句
        if self._where_conditions:
            where_parts = []
            for i, condition in enumerate(self._where_conditions):
                condition_sql, condition_params = condition.to_sql()
                if i == 0:
                    where_parts.append(condition_sql)
                else:
                    where_parts.append(f"{condition.connector} {condition_sql}")

                if isinstance(condition_params, list | tuple):
                    parameters.extend(condition_params)
                elif condition_params:
                    parameters.append(condition_params)

            sql += f" WHERE {' '.join(where_parts)}"

        return sql, parameters

    def to_delete_sql(self) -> tuple[str, list[Any]]:
        """建構 DELETE SQL 查詢.

        Returns:
            SQL 字串和參數列表的元組
        """
        sql = f"DELETE FROM {self.table}"
        parameters: list[Any] = []

        # WHERE 子句
        if self._where_conditions:
            where_parts = []
            for i, condition in enumerate(self._where_conditions):
                condition_sql, condition_params = condition.to_sql()
                if i == 0:
                    where_parts.append(condition_sql)
                else:
                    where_parts.append(f"{condition.connector} {condition_sql}")

                if isinstance(condition_params, list | tuple):
                    parameters.extend(condition_params)
                elif condition_params:
                    parameters.append(condition_params)

            sql += f" WHERE {' '.join(where_parts)}"
        else:
            raise ValueError("DELETE 查詢必須包含 WHERE 條件以避免意外刪除所有資料")

        return sql, parameters

    def clone(self) -> QueryBuilder:
        """克隆查詢建構器.

        Returns:
            新的查詢建構器實例
        """
        new_builder = QueryBuilder(self.table, self.alias)
        new_builder._select_fields = self._select_fields.copy()
        new_builder._where_conditions = self._where_conditions.copy()
        new_builder._join_clauses = self._join_clauses.copy()
        new_builder._order_by = self._order_by.copy()
        new_builder._group_by = self._group_by.copy()
        new_builder._having_conditions = self._having_conditions.copy()
        new_builder._limit_value = self._limit_value
        new_builder._offset_value = self._offset_value
        new_builder._distinct = self._distinct
        new_builder._insert_data = self._insert_data.copy()
        new_builder._update_data = self._update_data.copy()
        new_builder._bulk_insert_data = self._bulk_insert_data.copy()
        return new_builder

    def reset(self) -> QueryBuilder:
        """重置查詢建構器.

        Returns:
            自身實例,支援鏈式調用
        """
        self._select_fields.clear()
        self._where_conditions.clear()
        self._join_clauses.clear()
        self._order_by.clear()
        self._group_by.clear()
        self._having_conditions.clear()
        self._limit_value = None
        self._offset_value = 0
        self._distinct = False
        self._insert_data.clear()
        self._update_data.clear()
        self._bulk_insert_data.clear()
        return self

    def __str__(self) -> str:
        """字串表示(返回 SELECT SQL)."""
        try:
            sql, params = self.to_select_sql()
            return f"SQL: {sql}\nParams: {params}"
        except Exception as e:
            return f"QueryBuilder Error: {e}"

    def __repr__(self) -> str:
        """詳細字串表示."""
        return f"QueryBuilder(table='{self.table}', alias='{self.alias}')"

__all__ = [
    "BaseRepository",
    "ConnectionPoolError",
    "DatabaseConnection",
    "DatabaseError",
    "DatabasePool",
    "JoinClause",
    "JoinType",
    "OrderByClause",
    "OrderDirection",
    "QueryBuilder",
    "QueryCondition",
    "close_all_pools",
    "get_database_pool",
]
