"""成就系統優化資料存取層.

此模組擴展原有的 AchievementRepository, 提供效能優化功能:
- 批量查詢操作
- 索引優化查詢
- 分頁查詢支援
- 查詢效能監控

根據 Story 5.1 Task 1.2-1.3 的要求實作.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import Any

from src.core.database import DatabasePool, OrderDirection, QueryBuilder

from .models import Achievement, AchievementProgress, AchievementType, UserAchievement
from .repository import AchievementRepository

logger = logging.getLogger(__name__)

# 效能監控常數
SLOW_QUERY_THRESHOLD_MS = 200  # 慢查詢閾值(毫秒)


class OptimizedAchievementRepository(AchievementRepository):
    """優化的成就資料存取庫.

    繼承基礎 Repository 並增加效能優化功能.
    """

    def __init__(self, pool: DatabasePool, enable_monitoring: bool = True):
        """初始化優化的成就資料存取庫.

        Args:
            pool: 資料庫連線池
            enable_monitoring: 是否啟用查詢監控
        """
        super().__init__(pool)
        self._enable_monitoring = enable_monitoring
        self._query_stats = {
            "total_queries": 0,
            "slow_queries": 0,
            "avg_query_time": 0.0,
            "last_reset": datetime.now(),
        }

        logger.info("OptimizedAchievementRepository 初始化完成")

    # =============================================================================
    # 優化的成就查詢功能
    # =============================================================================

    async def list_achievements_optimized(
        self,
        category_id: int | None = None,
        achievement_type: AchievementType | None = None,
        active_only: bool = True,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        sort_order: OrderDirection = OrderDirection.DESC,
    ) -> tuple[list[Achievement], int]:
        """優化的成就列表查詢(支援分頁).

        Args:
            category_id: 篩選特定分類
            achievement_type: 篩選特定類型
            active_only: 是否只取得啟用的成就
            page: 頁數(從1開始)
            page_size: 每頁大小
            sort_by: 排序欄位
            sort_order: 排序方向

        Returns:
            (成就列表, 總數量) 的元組
        """
        start_time = time.perf_counter()

        try:
            # 計算偏移量
            offset = (page - 1) * page_size

            # 建立基礎查詢
            query = QueryBuilder("achievements", "a").select(
                "a.id",
                "a.name",
                "a.description",
                "a.category_id",
                "a.type",
                "a.criteria",
                "a.points",
                "a.badge_url",
                "a.is_active",
                "a.created_at",
                "a.updated_at",
            )

            # 添加篩選條件
            if category_id is not None:
                query = query.where("a.category_id", "=", category_id)

            if achievement_type is not None:
                query = query.where("a.type", "=", achievement_type.value)

            if active_only:
                query = query.where("a.is_active", "=", True)

            # 添加排序和分頁
            query = (
                query.order_by(f"a.{sort_by}", sort_order)
                .limit(page_size)
                .offset(offset)
            )

            # 執行查詢
            sql, params = query.to_select_sql()
            rows = await self.execute_query(sql, params, fetch_all=True)

            # 轉換為成就物件
            achievements = []
            for row in rows or []:
                columns = [
                    "id",
                    "name",
                    "description",
                    "category_id",
                    "type",
                    "criteria",
                    "points",
                    "badge_url",
                    "is_active",
                    "created_at",
                    "updated_at",
                ]
                row_dict = self._row_to_dict(row, columns)
                row_dict["criteria"] = self._parse_json_field(row_dict["criteria"])
                row_dict["type"] = AchievementType(row_dict["type"])
                achievements.append(Achievement(**row_dict))

            count_query = QueryBuilder("achievements", "a").select("COUNT(*) as total")

            if category_id is not None:
                count_query = count_query.where("a.category_id", "=", category_id)
            if achievement_type is not None:
                count_query = count_query.where("a.type", "=", achievement_type.value)
            if active_only:
                count_query = count_query.where("a.is_active", "=", True)

            count_sql, count_params = count_query.to_select_sql()
            count_row = await self.execute_query(
                count_sql, count_params, fetch_one=True
            )
            total_count = count_row[0] if count_row else 0

            execution_time = (time.perf_counter() - start_time) * 1000
            await self._record_query_stats(
                "list_achievements_optimized", execution_time
            )

            logger.debug(
                f"優化成就列表查詢完成: {len(achievements)} 項,總計 {total_count} 項,"
                f"執行時間 {execution_time:.2f}ms"
            )

            return achievements, total_count

        except Exception as e:
            logger.error(f"優化成就列表查詢失敗: {e}", exc_info=True)
            raise

    async def get_achievements_by_ids(
        self, achievement_ids: list[int]
    ) -> list[Achievement]:
        """批量取得成就(按 ID 列表).

        Args:
            achievement_ids: 成就 ID 列表

        Returns:
            成就列表
        """
        if not achievement_ids:
            return []

        start_time = time.perf_counter()

        try:
            # 使用 IN 查詢批量取得成就
            placeholders = ",".join("?" * len(achievement_ids))
            sql = f"""
            SELECT id, name, description, category_id, type, criteria,
                   points, badge_url, is_active, created_at, updated_at
            FROM achievements
            WHERE id IN ({placeholders})
            ORDER BY id
            """

            rows = await self.execute_query(sql, achievement_ids, fetch_all=True)

            achievements = []
            for row in rows or []:
                columns = [
                    "id",
                    "name",
                    "description",
                    "category_id",
                    "type",
                    "criteria",
                    "points",
                    "badge_url",
                    "is_active",
                    "created_at",
                    "updated_at",
                ]
                row_dict = self._row_to_dict(row, columns)
                row_dict["criteria"] = self._parse_json_field(row_dict["criteria"])
                row_dict["type"] = AchievementType(row_dict["type"])
                achievements.append(Achievement(**row_dict))

            execution_time = (time.perf_counter() - start_time) * 1000
            await self._record_query_stats("get_achievements_by_ids", execution_time)

            logger.debug(
                f"批量取得成就完成: {len(achievements)} 項,執行時間 {execution_time:.2f}ms"
            )

            return achievements

        except Exception as e:
            logger.error(f"批量取得成就失敗: {e}", exc_info=True)
            raise

    async def get_user_achievements_optimized(
        self,
        user_id: int,
        category_id: int | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[tuple[UserAchievement, Achievement]], int]:
        """優化的用戶成就查詢(支援分頁).

        Args:
            user_id: 用戶 ID
            category_id: 篩選特定分類
            page: 頁數(從1開始)
            page_size: 每頁大小

        Returns:
            ((用戶成就記錄, 成就詳情) 的元組列表, 總數量)
        """
        start_time = time.perf_counter()

        try:
            offset = (page - 1) * page_size

            # 使用優化的 JOIN 查詢
            query = (
                QueryBuilder("user_achievements", "ua")
                .select(
                    "ua.id as ua_id",
                    "ua.user_id",
                    "ua.achievement_id",
                    "ua.earned_at",
                    "ua.notified",
                    "a.id as a_id",
                    "a.name",
                    "a.description",
                    "a.category_id",
                    "a.type",
                    "a.criteria",
                    "a.points",
                    "a.badge_url",
                    "a.is_active",
                    "a.created_at as a_created_at",
                    "a.updated_at as a_updated_at",
                )
                .inner_join("achievements a", "a.id = ua.achievement_id")
                .where("ua.user_id", "=", user_id)
            )

            if category_id is not None:
                query = query.where("a.category_id", "=", category_id)

            query = (
                query.order_by("ua.earned_at", OrderDirection.DESC)
                .limit(page_size)
                .offset(offset)
            )

            sql, params = query.to_select_sql()
            rows = await self.execute_query(sql, params, fetch_all=True)

            results = []
            for row in rows or []:
                columns = [
                    "ua_id",
                    "user_id",
                    "achievement_id",
                    "earned_at",
                    "notified",
                    "a_id",
                    "name",
                    "description",
                    "category_id",
                    "type",
                    "criteria",
                    "points",
                    "badge_url",
                    "is_active",
                    "a_created_at",
                    "a_updated_at",
                ]
                row_dict = self._row_to_dict(row, columns)

                # 分離用戶成就和成就資料
                user_achievement_data = {
                    "id": row_dict["ua_id"],
                    "user_id": row_dict["user_id"],
                    "achievement_id": row_dict["achievement_id"],
                    "earned_at": row_dict["earned_at"],
                    "notified": row_dict["notified"],
                }

                achievement_data = {
                    "id": row_dict["a_id"],
                    "name": row_dict["name"],
                    "description": row_dict["description"],
                    "category_id": row_dict["category_id"],
                    "type": AchievementType(row_dict["type"]),
                    "criteria": self._parse_json_field(row_dict["criteria"]),
                    "points": row_dict["points"],
                    "badge_url": row_dict["badge_url"],
                    "is_active": row_dict["is_active"],
                    "created_at": row_dict["a_created_at"],
                    "updated_at": row_dict["a_updated_at"],
                }

                user_achievement = UserAchievement(**user_achievement_data)
                achievement = Achievement(**achievement_data)
                results.append((user_achievement, achievement))

            # 取得總數量
            count_query = QueryBuilder("user_achievements", "ua").select(
                "COUNT(*) as total"
            )
            count_query = count_query.inner_join(
                "achievements a", "a.id = ua.achievement_id"
            )
            count_query = count_query.where("ua.user_id", "=", user_id)

            if category_id is not None:
                count_query = count_query.where("a.category_id", "=", category_id)

            count_sql, count_params = count_query.to_select_sql()
            count_row = await self.execute_query(
                count_sql, count_params, fetch_one=True
            )
            total_count = count_row[0] if count_row else 0

            execution_time = (time.perf_counter() - start_time) * 1000
            await self._record_query_stats(
                "get_user_achievements_optimized", execution_time
            )

            logger.debug(
                f"優化用戶成就查詢完成: 用戶 {user_id},{len(results)} 項,"
                f"總計 {total_count} 項,執行時間 {execution_time:.2f}ms"
            )

            return results, total_count

        except Exception as e:
            logger.error(f"優化用戶成就查詢失敗: {e}", exc_info=True)
            raise

    async def get_user_achievements_batch(
        self, user_ids: list[int]
    ) -> list[UserAchievement]:
        """批量取得多個用戶的成就.

        Args:
            user_ids: 用戶 ID 列表

        Returns:
            用戶成就列表
        """
        if not user_ids:
            return []

        start_time = time.perf_counter()

        try:
            placeholders = ",".join("?" * len(user_ids))
            sql = f"""
            SELECT id, user_id, achievement_id, earned_at, notified
            FROM user_achievements
            WHERE user_id IN ({placeholders})
            ORDER BY user_id, earned_at DESC
            """

            rows = await self.execute_query(sql, user_ids, fetch_all=True)

            user_achievements = []
            for row in rows or []:
                columns = ["id", "user_id", "achievement_id", "earned_at", "notified"]
                row_dict = self._row_to_dict(row, columns)
                user_achievements.append(UserAchievement(**row_dict))

            execution_time = (time.perf_counter() - start_time) * 1000
            await self._record_query_stats(
                "get_user_achievements_batch", execution_time
            )

            logger.debug(
                f"批量取得用戶成就完成: {len(user_ids)} 個用戶,"
                f"{len(user_achievements)} 項成就,執行時間 {execution_time:.2f}ms"
            )

            return user_achievements

        except Exception as e:
            logger.error(f"批量取得用戶成就失敗: {e}", exc_info=True)
            raise

    async def get_user_progress_batch(
        self, user_ids: list[int], achievement_ids: list[int] | None = None
    ) -> list[AchievementProgress]:
        """批量取得用戶進度.

        Args:
            user_ids: 用戶 ID 列表
            achievement_ids: 成就 ID 列表(可選)

        Returns:
            進度記錄列表
        """
        if not user_ids:
            return []

        start_time = time.perf_counter()

        try:
            user_placeholders = ",".join("?" * len(user_ids))
            params = user_ids.copy()

            sql = f"""
            SELECT id, user_id, achievement_id, current_value, target_value,
                   progress_data, last_updated
            FROM achievement_progress
            WHERE user_id IN ({user_placeholders})
            """

            if achievement_ids:
                achievement_placeholders = ",".join("?" * len(achievement_ids))
                sql += f" AND achievement_id IN ({achievement_placeholders})"
                params.extend(achievement_ids)

            sql += " ORDER BY user_id, last_updated DESC"

            rows = await self.execute_query(sql, params, fetch_all=True)

            progresses = []
            for row in rows or []:
                columns = [
                    "id",
                    "user_id",
                    "achievement_id",
                    "current_value",
                    "target_value",
                    "progress_data",
                    "last_updated",
                ]
                row_dict = self._row_to_dict(row, columns)
                if row_dict.get("progress_data"):
                    row_dict["progress_data"] = self._parse_json_field(
                        row_dict["progress_data"]
                    )
                progresses.append(AchievementProgress(**row_dict))

            execution_time = (time.perf_counter() - start_time) * 1000
            await self._record_query_stats("get_user_progress_batch", execution_time)

            logger.debug(
                f"批量取得用戶進度完成: {len(user_ids)} 個用戶,"
                f"{len(progresses)} 項進度,執行時間 {execution_time:.2f}ms"
            )

            return progresses

        except Exception as e:
            logger.error(f"批量取得用戶進度失敗: {e}", exc_info=True)
            raise

    # =============================================================================
    # 批量操作功能
    # =============================================================================

    async def batch_insert(self, table: str, data: list[dict[str, Any]]) -> int:
        """批量插入資料.

        Args:
            table: 目標表格
            data: 要插入的資料列表

        Returns:
            插入的記錄數量
        """
        if not data:
            return 0

        start_time = time.perf_counter()

        try:
            # 取得欄位名稱
            columns = list(data[0].keys())
            placeholders = ",".join("?" * len(columns))

            sql = f"""
            INSERT INTO {table} ({",".join(columns)})
            VALUES ({placeholders})
            """

            # 準備參數
            params_list = []
            for item in data:
                params = [item.get(col) for col in columns]
                params_list.append(params)

            async with self.pool.get_connection() as conn:
                await conn.executemany(sql, params_list)
                await conn.commit()

            execution_time = (time.perf_counter() - start_time) * 1000
            await self._record_query_stats("batch_insert", execution_time)

            logger.debug(
                f"批量插入完成: {table} 表,{len(data)} 項,執行時間 {execution_time:.2f}ms"
            )

            return len(data)

        except Exception as e:
            logger.error(f"批量插入失敗: {table} 表,{e}", exc_info=True)
            raise

    async def batch_update(self, table: str, data: list[dict[str, Any]]) -> int:
        """批量更新資料.

        Args:
            table: 目標表格
            data: 要更新的資料列表(必須包含 id 欄位)

        Returns:
            更新的記錄數量
        """
        if not data:
            return 0

        start_time = time.perf_counter()

        try:
            updated_count = 0

            async with self.pool.get_connection() as conn:
                for item in data:
                    if "id" not in item:
                        continue

                    # 建立更新查詢
                    item_id = item.pop("id")
                    if not item:  # 移除 id 後沒有其他欄位
                        continue

                    set_clauses = [f"{col} = ?" for col in item]
                    sql = f"UPDATE {table} SET {','.join(set_clauses)} WHERE id = ?"

                    params = [*list(item.values()), item_id]
                    cursor = await conn.execute(sql, params)
                    updated_count += cursor.rowcount

                await conn.commit()

            execution_time = (time.perf_counter() - start_time) * 1000
            await self._record_query_stats("batch_update", execution_time)

            logger.debug(
                f"批量更新完成: {table} 表,{updated_count} 項,執行時間 {execution_time:.2f}ms"
            )

            return updated_count

        except Exception as e:
            logger.error(f"批量更新失敗: {table} 表,{e}", exc_info=True)
            raise

    async def batch_delete(self, table: str, conditions: list[dict[str, Any]]) -> int:
        """批量刪除資料.

        Args:
            table: 目標表格
            conditions: 刪除條件列表

        Returns:
            刪除的記錄數量
        """
        if not conditions:
            return 0

        start_time = time.perf_counter()

        try:
            deleted_count = 0

            async with self.pool.get_connection() as conn:
                for condition in conditions:
                    if not condition:
                        continue

                    # 建立刪除查詢
                    where_clauses = [f"{col} = ?" for col in condition]
                    sql = f"DELETE FROM {table} WHERE {' AND '.join(where_clauses)}"

                    params = list(condition.values())
                    cursor = await conn.execute(sql, params)
                    deleted_count += cursor.rowcount

                await conn.commit()

            execution_time = (time.perf_counter() - start_time) * 1000
            await self._record_query_stats("batch_delete", execution_time)

            logger.debug(
                f"批量刪除完成: {table} 表,{deleted_count} 項,執行時間 {execution_time:.2f}ms"
            )

            return deleted_count

        except Exception as e:
            logger.error(f"批量刪除失敗: {table} 表,{e}", exc_info=True)
            raise

    # =============================================================================
    # 內部工具方法
    # =============================================================================

    def _parse_json_field(self, json_str: str) -> dict[str, Any]:
        """解析 JSON 欄位."""
        if not json_str:
            return {}

        try:
            return json.loads(json_str)
        except (json.JSONDecodeError, TypeError):
            logger.warning(f"無法解析 JSON 欄位: {json_str}")
            return {}

    async def _record_query_stats(
        self, query_type: str, execution_time_ms: float
    ) -> None:
        """記錄查詢統計."""
        if not self._enable_monitoring:
            return

        self._query_stats["total_queries"] += 1

        if execution_time_ms > SLOW_QUERY_THRESHOLD_MS:  # 慢查詢門檻
            self._query_stats["slow_queries"] += 1
            logger.warning(
                f"慢查詢檢測: {query_type} 執行時間 {execution_time_ms:.2f}ms"
            )

        # 更新平均時間
        current_avg = self._query_stats["avg_query_time"]
        total_queries = self._query_stats["total_queries"]
        new_avg = (
            (current_avg * (total_queries - 1)) + execution_time_ms
        ) / total_queries
        self._query_stats["avg_query_time"] = new_avg

    def get_query_stats(self) -> dict[str, Any]:
        """取得查詢統計."""
        stats = self._query_stats.copy()
        stats["slow_query_ratio"] = stats["slow_queries"] / max(
            stats["total_queries"], 1
        )
        return stats

    def reset_query_stats(self) -> None:
        """重置查詢統計."""
        self._query_stats = {
            "total_queries": 0,
            "slow_queries": 0,
            "avg_query_time": 0.0,
            "last_reset": datetime.now(),
        }
        logger.info("查詢統計已重置")


__all__ = [
    "OptimizedAchievementRepository",
]
