"""SQL 查詢建構器模組.

此模組提供一個簡單的 SQL 查詢建構器,用於動態建構查詢語句.
"""

from __future__ import annotations

from typing import Any


class QueryBuilder:
    """SQL 查詢建構器類別."""

    def __init__(self, table: str, alias: str | None = None):
        """初始化查詢建構器.

        Args:
            table: 表格名稱
            alias: 表格別名
        """
        self.table = table
        self.alias = alias
        self._select_fields: list[str] = []
        self._where_conditions: list[tuple[str, str, Any]] = []
        self._count_mode = False
        self._joins: list[str] = []
        self._group_by: list[str] = []
        self._having_conditions: list[tuple[str, str, Any]] = []
        self._order_by: list[str] = []
        self._limit_value: int | None = None

    def select(self, *fields: str) -> QueryBuilder:
        """設定 SELECT 欄位.

        Args:
            *fields: 要選擇的欄位

        Returns:
            QueryBuilder 實例以支援鏈式調用
        """
        self._select_fields.extend(fields)
        return self

    def count(self) -> QueryBuilder:
        """設定為 COUNT 查詢.

        Returns:
            QueryBuilder 實例以支援鏈式調用
        """
        self._count_mode = True
        return self

    def where(self, field: str, operator: str, value: Any) -> QueryBuilder:
        """添加 WHERE 條件.

        Args:
            field: 欄位名稱
            operator: 操作符 (=, !=, >, <, >=, <=, LIKE 等)
            value: 比較值

        Returns:
            QueryBuilder 實例以支援鏈式調用
        """
        self._where_conditions.append((field, operator, value))
        return self

    def join(
        self, table: str, condition: str, join_type: str = "INNER"
    ) -> QueryBuilder:
        """添加 JOIN 子句.

        Args:
            table: 要連接的表格
            condition: 連接條件
            join_type: 連接類型 (INNER, LEFT, RIGHT, FULL)

        Returns:
            QueryBuilder 實例以支援鏈式調用
        """
        self._joins.append(f"{join_type} JOIN {table} ON {condition}")
        return self

    def group_by(self, *fields: str) -> QueryBuilder:
        """添加 GROUP BY 子句.

        Args:
            *fields: 分組欄位

        Returns:
            QueryBuilder 實例以支援鏈式調用
        """
        self._group_by.extend(fields)
        return self

    def having(self, field: str, operator: str, value: Any) -> QueryBuilder:
        """添加 HAVING 條件.

        Args:
            field: 欄位名稱
            operator: 操作符
            value: 比較值

        Returns:
            QueryBuilder 實例以支援鏈式調用
        """
        self._having_conditions.append((field, operator, value))
        return self

    def order_by(self, field: str, direction: str = "ASC") -> QueryBuilder:
        """添加 ORDER BY 子句.

        Args:
            field: 排序欄位
            direction: 排序方向 (ASC, DESC)

        Returns:
            QueryBuilder 實例以支援鏈式調用
        """
        self._order_by.append(f"{field} {direction}")
        return self

    def limit(self, count: int) -> QueryBuilder:
        """設定 LIMIT 子句.

        Args:
            count: 限制數量

        Returns:
            QueryBuilder 實例以支援鏈式調用
        """
        self._limit_value = count
        return self

    def to_select_sql(self) -> tuple[str, list[Any]]:
        """建構 SELECT SQL 語句.

        Returns:
            包含 SQL 語句和參數的元組
        """
        table_name = f"{self.table} {self.alias}" if self.alias else self.table

        if self._count_mode:
            sql_parts = [f"SELECT COUNT(*) FROM {table_name}"]
        elif self._select_fields:
            fields = ", ".join(self._select_fields)
            sql_parts = [f"SELECT {fields} FROM {table_name}"]
        else:
            sql_parts = [f"SELECT * FROM {table_name}"]

        # 添加 JOIN 子句
        for join_clause in self._joins:
            sql_parts.append(join_clause)

        # 添加 WHERE 子句
        params = []
        if self._where_conditions:
            where_parts = []
            for field, operator, value in self._where_conditions:
                where_parts.append(f"{field} {operator} ?")
                params.append(value)
            sql_parts.append(f"WHERE {' AND '.join(where_parts)}")

        # 添加 GROUP BY 子句
        if self._group_by:
            sql_parts.append(f"GROUP BY {', '.join(self._group_by)}")

        # 添加 HAVING 子句
        if self._having_conditions:
            having_parts = []
            for field, operator, value in self._having_conditions:
                having_parts.append(f"{field} {operator} ?")
                params.append(value)
            sql_parts.append(f"HAVING {' AND '.join(having_parts)}")

        # 添加 ORDER BY 子句
        if self._order_by:
            sql_parts.append(f"ORDER BY {', '.join(self._order_by)}")

        # 添加 LIMIT 子句
        if self._limit_value is not None:
            sql_parts.append(f"LIMIT {self._limit_value}")

        return " ".join(sql_parts), params

    def to_insert_sql(self, data: dict[str, Any]) -> tuple[str, list[Any]]:
        """建構 INSERT SQL 語句.

        Args:
            data: 要插入的資料

        Returns:
            包含 SQL 語句和參數的元組
        """
        fields = list(data.keys())
        values = list(data.values())
        placeholders = ", ".join(["?" for _ in fields])

        sql = f"INSERT INTO {self.table} ({', '.join(fields)}) VALUES ({placeholders})"
        return sql, values

    def to_update_sql(self, data: dict[str, Any]) -> tuple[str, list[Any]]:
        """建構 UPDATE SQL 語句.

        Args:
            data: 要更新的資料

        Returns:
            包含 SQL 語句和參數的元組
        """
        set_parts = []
        params = []

        for field, value in data.items():
            set_parts.append(f"{field} = ?")
            params.append(value)

        sql_parts = [f"UPDATE {self.table} SET {', '.join(set_parts)}"]

        # 添加 WHERE 子句
        if self._where_conditions:
            where_parts = []
            for field, operator, value in self._where_conditions:
                where_parts.append(f"{field} {operator} ?")
                params.append(value)
            sql_parts.append(f"WHERE {' AND '.join(where_parts)}")

        return " ".join(sql_parts), params

    def to_delete_sql(self) -> tuple[str, list[Any]]:
        """建構 DELETE SQL 語句.

        Returns:
            包含 SQL 語句和參數的元組
        """
        sql_parts = [f"DELETE FROM {self.table}"]
        params = []

        # 添加 WHERE 子句
        if self._where_conditions:
            where_parts = []
            for field, operator, value in self._where_conditions:
                where_parts.append(f"{field} {operator} ?")
                params.append(value)
            sql_parts.append(f"WHERE {' AND '.join(where_parts)}")

        return " ".join(sql_parts), params
