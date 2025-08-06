"""成就系統資料存取層 (Repository Pattern).

此模組實作成就系統的所有資料存取操作, 提供:
- 完整的 CRUD 操作
- 複雜查詢和篩選功能
- 成就進度更新邏輯
- 用戶成就獲得處理
- 統計和報表查詢

遵循 Repository Pattern 設計模式, 隔離資料存取邏輯與業務邏輯.
"""

from __future__ import annotations

import contextlib
import json
import logging
from datetime import datetime, timedelta
from typing import Any

from src.core.database import BaseRepository, DatabasePool, OrderDirection, QueryBuilder

from .models import (
    Achievement,
    AchievementCategory,
    AchievementEventData,
    AchievementProgress,
    AchievementType,
    GlobalNotificationSettings,
    NotificationEvent,
    NotificationPreference,
    UserAchievement,
)

logger = logging.getLogger(__name__)

# 業務邏輯常數
MAX_CATEGORY_LEVEL = 9  # 最大分類層級 (0-9, 共10層)


class AchievementRepository(BaseRepository):
    """成就系統資料存取庫.

    提供成就系統所有資料操作的統一介面.
    """

    def __init__(self, pool: DatabasePool):
        """初始化成就資料存取庫.

        Args:
            pool: 資料庫連線池
        """
        # 使用多表格的 Repository,這裡以主要的 achievements 表格為基礎
        super().__init__(pool, "achievements")

    def _row_to_dict(
        self, row: Any, columns: list[str] | None = None
    ) -> dict[str, Any]:
        """將資料庫行物件轉換為字典.

        Args:
            row: 資料庫行物件
            columns: 欄位名稱列表(可選)

        Returns:
            字典格式的資料
        """
        result = {}

        if row is None:
            pass  # 保持空字典
        elif hasattr(row, "keys") and hasattr(row, "__getitem__"):
            # 處理 SQLite Row 物件
            try:
                result = dict(row)
            except (TypeError, ValueError):
                result = {key: row[key] for key in row}
        elif isinstance(row, dict):
            # 處理已經是字典的情況
            result = row
        elif hasattr(row, "__iter__") and not isinstance(row, str | bytes):
            # 處理元組或列表
            if columns:
                result = dict(zip(columns, row, strict=False))
            else:
                with contextlib.suppress(TypeError, ValueError):
                    result = dict(row)

        return result

    # =============================================================================
    # Achievement Category 操作
    # =============================================================================

    async def create_category(
        self, category: AchievementCategory
    ) -> AchievementCategory:
        """建立新的成就分類.

        Args:
            category: 成就分類資料

        Returns:
            建立後的成就分類(包含 ID)

        Raises:
            DatabaseError: 資料庫操作失敗
        """
        # 如果有父分類,需要設定正確的層級
        if category.parent_id is not None:
            parent_category = await self.get_category_by_id(category.parent_id)
            if not parent_category:
                raise ValueError(f"父分類 {category.parent_id} 不存在")

            # 檢查層級限制
            if parent_category.level >= MAX_CATEGORY_LEVEL:  # 最多 10 層(0-9)
                raise ValueError("分類層級不能超過 10 層")

            category.level = parent_category.level + 1

        query = QueryBuilder("achievement_categories").insert({
            "name": category.name,
            "description": category.description,
            "parent_id": category.parent_id,
            "level": category.level,
            "display_order": category.display_order,
            "icon_emoji": category.icon_emoji,
            "is_expanded": category.is_expanded,
        })

        sql, params = query.to_insert_sql()

        async with self.pool.get_connection() as conn:
            cursor = await conn.execute(sql, params)
            await conn.commit()

            category_id = cursor.lastrowid
            return await self.get_category_by_id(category_id)

    async def get_category_by_id(self, category_id: int) -> AchievementCategory | None:
        """根據 ID 取得成就分類.

        Args:
            category_id: 分類 ID

        Returns:
            成就分類物件或 None
        """
        query = (
            QueryBuilder("achievement_categories")
            .select()
            .where("id", "=", category_id)
        )
        sql, params = query.to_select_sql()

        row = await self.execute_query(sql, params, fetch_one=True)
        if row:
            columns = [
                "id",
                "name",
                "description",
                "parent_id",
                "level",
                "display_order",
                "icon_emoji",
                "is_expanded",
                "created_at",
                "updated_at",
            ]
            row_dict = self._row_to_dict(row, columns)
            return AchievementCategory(**row_dict)
        return None

    async def get_category_by_name(self, name: str) -> AchievementCategory | None:
        """根據名稱取得成就分類.

        Args:
            name: 分類名稱

        Returns:
            成就分類物件或 None
        """
        query = QueryBuilder("achievement_categories").select().where("name", "=", name)
        sql, params = query.to_select_sql()

        row = await self.execute_query(sql, params, fetch_one=True)
        if row:
            columns = [
                "id",
                "name",
                "description",
                "parent_id",
                "level",
                "display_order",
                "icon_emoji",
                "is_expanded",
                "created_at",
                "updated_at",
            ]
            row_dict = self._row_to_dict(row, columns)
            return AchievementCategory(**row_dict)
        return None

    async def list_categories(
        self, _active_only: bool = True
    ) -> list[AchievementCategory]:
        """取得所有成就分類列表.

        Args:
            active_only: 是否只取得啟用的分類

        Returns:
            成就分類列表,按層級和 display_order 排序
        """
        query = (
            QueryBuilder("achievement_categories")
            .select()
            .order_by("level")
            .order_by("display_order")
            .order_by("name")
        )

        sql, params = query.to_select_sql()
        rows = await self.execute_query(sql, params, fetch_all=True)

        categories = []
        for row in rows or []:
            columns = [
                "id",
                "name",
                "description",
                "parent_id",
                "level",
                "display_order",
                "icon_emoji",
                "is_expanded",
                "created_at",
                "updated_at",
            ]
            row_dict = self._row_to_dict(row, columns)
            categories.append(AchievementCategory(**row_dict))

        return categories

    async def get_root_categories(self) -> list[AchievementCategory]:
        """取得所有根分類(parent_id 為 None).

        Returns:
            根分類列表,按 display_order 排序
        """
        query = (
            QueryBuilder("achievement_categories")
            .select()
            .where("parent_id", "IS", None)
            .order_by("display_order")
            .order_by("name")
        )

        sql, params = query.to_select_sql()
        rows = await self.execute_query(sql, params, fetch_all=True)

        categories = []
        for row in rows or []:
            columns = [
                "id",
                "name",
                "description",
                "parent_id",
                "level",
                "display_order",
                "icon_emoji",
                "is_expanded",
                "created_at",
                "updated_at",
            ]
            row_dict = self._row_to_dict(row, columns)
            categories.append(AchievementCategory(**row_dict))

        return categories

    async def get_child_categories(self, parent_id: int) -> list[AchievementCategory]:
        """取得指定分類的子分類.

        Args:
            parent_id: 父分類 ID

        Returns:
            子分類列表,按 display_order 排序
        """
        query = (
            QueryBuilder("achievement_categories")
            .select()
            .where("parent_id", "=", parent_id)
            .order_by("display_order")
            .order_by("name")
        )

        sql, params = query.to_select_sql()
        rows = await self.execute_query(sql, params, fetch_all=True)

        categories = []
        for row in rows or []:
            columns = [
                "id",
                "name",
                "description",
                "parent_id",
                "level",
                "display_order",
                "icon_emoji",
                "is_expanded",
                "created_at",
                "updated_at",
            ]
            row_dict = self._row_to_dict(row, columns)
            categories.append(AchievementCategory(**row_dict))

        return categories

    async def get_category_tree(
        self, root_id: int | None = None
    ) -> list[dict[str, Any]]:
        """取得分類樹結構.

        Args:
            root_id: 根分類 ID,None 表示從頂層開始

        Returns:
            包含分類和子分類的樹狀結構列表
        """
        # 遞歸構建分類樹
        if root_id is None:
            root_categories = await self.get_root_categories()
        else:
            root_categories = await self.get_child_categories(root_id)

        tree = []
        for category in root_categories:
            category_dict = {
                "category": category,
                "children": await self.get_category_tree(category.id),
                "has_children": len(await self.get_child_categories(category.id)) > 0,
                "achievement_count": await self._get_category_achievement_count(
                    category.id
                ),
            }
            tree.append(category_dict)

        return tree

    async def _get_category_achievement_count(self, category_id: int) -> int:
        """取得分類下的成就數量(包含子分類).

        Args:
            category_id: 分類 ID

        Returns:
            成就數量
        """
        # 獲取直接在此分類下的成就
        query = (
            QueryBuilder("achievements").count().where("category_id", "=", category_id)
        )
        sql, params = query.to_select_sql()
        row = await self.execute_query(sql, params, fetch_one=True)
        direct_count = row[0] if row else 0

        # 獲取子分類的成就數量
        child_categories = await self.get_child_categories(category_id)
        child_count = 0
        for child in child_categories:
            child_count += await self._get_category_achievement_count(child.id)

        return direct_count + child_count

    async def get_category_path(self, category_id: int) -> list[AchievementCategory]:
        """取得分類的完整路徑(從根到當前分類).

        Args:
            category_id: 分類 ID

        Returns:
            分類路徑列表,從根分類到當前分類
        """
        path = []
        current_id = category_id

        while current_id is not None:
            category = await self.get_category_by_id(current_id)
            if not category:
                break

            path.insert(0, category)  # 插入到開頭
            current_id = category.parent_id

        return path

    async def update_category_expansion(
        self, category_id: int, is_expanded: bool
    ) -> bool:
        """更新分類的展開狀態.

        Args:
            category_id: 分類 ID
            is_expanded: 是否展開

        Returns:
            True 如果更新成功,否則 False
        """
        query = (
            QueryBuilder("achievement_categories")
            .update({"is_expanded": is_expanded})
            .where("id", "=", category_id)
        )

        sql, params = query.to_update_sql()

        async with self.pool.get_connection() as conn:
            cursor = await conn.execute(sql, params)
            await conn.commit()
            return cursor.rowcount > 0

    async def update_category(self, category_id: int, updates: dict[str, Any]) -> bool:
        """更新成就分類.

        Args:
            category_id: 分類 ID
            updates: 要更新的欄位字典

        Returns:
            True 如果更新成功,否則 False
        """
        if not updates:
            return False

        query = (
            QueryBuilder("achievement_categories")
            .update(updates)
            .where("id", "=", category_id)
        )

        sql, params = query.to_update_sql()

        async with self.pool.get_connection() as conn:
            cursor = await conn.execute(sql, params)
            await conn.commit()
            return cursor.rowcount > 0

    async def delete_category(self, category_id: int) -> bool:
        """刪除成就分類.

        Args:
            category_id: 分類 ID

        Returns:
            True 如果刪除成功,否則 False
        """
        query = QueryBuilder("achievement_categories").where("id", "=", category_id)
        sql, params = query.to_delete_sql()

        async with self.pool.get_connection() as conn:
            cursor = await conn.execute(sql, params)
            await conn.commit()
            return cursor.rowcount > 0

    # =============================================================================
    # Achievement 操作
    # =============================================================================

    async def create_achievement(self, achievement: Achievement) -> Achievement:
        """建立新成就.

        Args:
            achievement: 成就資料

        Returns:
            建立後的成就(包含 ID)
        """
        query = QueryBuilder("achievements").insert({
            "name": achievement.name,
            "description": achievement.description,
            "category_id": achievement.category_id,
            "type": achievement.type.value,
            "criteria": achievement.get_criteria_json(),
            "points": achievement.points,
            "badge_url": achievement.badge_url,
            "role_reward": achievement.role_reward,
            "is_hidden": achievement.is_hidden,
            "is_active": achievement.is_active,
        })

        sql, params = query.to_insert_sql()

        async with self.pool.get_connection() as conn:
            cursor = await conn.execute(sql, params)
            await conn.commit()

            achievement_id = cursor.lastrowid
            return await self.get_achievement_by_id(achievement_id)

    async def get_achievement_by_id(self, achievement_id: int) -> Achievement | None:
        """根據 ID 取得成就.

        Args:
            achievement_id: 成就 ID

        Returns:
            成就物件或 None
        """
        query = QueryBuilder("achievements").select().where("id", "=", achievement_id)
        sql, params = query.to_select_sql()

        row = await self.execute_query(sql, params, fetch_one=True)
        if row:
            # 定義 achievements 表的欄位順序
            columns = [
                "id",
                "name",
                "description",
                "category_id",
                "type",
                "criteria",
                "points",
                "badge_url",
                "role_reward",
                "is_hidden",
                "is_active",
                "created_at",
                "updated_at",
            ]
            row_dict = self._row_to_dict(row, columns)

            # 解析 JSON 格式的條件
            row_dict["criteria"] = json.loads(row_dict["criteria"])
            row_dict["type"] = AchievementType(row_dict["type"])
            return Achievement(**row_dict)
        return None

    async def list_achievements(
        self,
        category_id: int | None = None,
        achievement_type: AchievementType | None = None,
        active_only: bool = True,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Achievement]:
        """取得成就列表.

        Args:
            category_id: 篩選特定分類
            achievement_type: 篩選特定類型
            active_only: 是否只取得啟用的成就
            limit: 最大返回數量
            offset: 跳過的記錄數

        Returns:
            成就列表
        """
        query = QueryBuilder("achievements").select()

        if category_id is not None:
            query = query.where("category_id", "=", category_id)

        if achievement_type is not None:
            query = query.where("type", "=", achievement_type.value)

        if active_only:
            query = query.where("is_active", "=", True)

        query = query.order_by("created_at", OrderDirection.DESC)

        if limit is not None:
            query = query.limit(limit).offset(offset)

        sql, params = query.to_select_sql()
        rows = await self.execute_query(sql, params, fetch_all=True)

        achievements = []
        for row in rows or []:
            # 定義 achievements 表的欄位順序
            columns = [
                "id",
                "name",
                "description",
                "category_id",
                "type",
                "criteria",
                "points",
                "badge_url",
                "role_reward",
                "is_hidden",
                "is_active",
                "created_at",
                "updated_at",
            ]
            row_dict = self._row_to_dict(row, columns)
            row_dict["criteria"] = json.loads(row_dict["criteria"])
            row_dict["type"] = AchievementType(row_dict["type"])
            achievements.append(Achievement(**row_dict))

        return achievements

    async def update_achievement(
        self, achievement_id: int, updates: dict[str, Any]
    ) -> bool:
        """更新成就.

        Args:
            achievement_id: 成就 ID
            updates: 要更新的欄位字典

        Returns:
            True 如果更新成功,否則 False
        """
        if not updates:
            return False

        # 處理特殊欄位
        if "criteria" in updates and isinstance(updates["criteria"], dict):
            updates["criteria"] = json.dumps(updates["criteria"], ensure_ascii=False)

        if "type" in updates and isinstance(updates["type"], AchievementType):
            updates["type"] = updates["type"].value

        query = (
            QueryBuilder("achievements")
            .update(updates)
            .where("id", "=", achievement_id)
        )

        sql, params = query.to_update_sql()

        async with self.pool.get_connection() as conn:
            cursor = await conn.execute(sql, params)
            await conn.commit()
            return cursor.rowcount > 0

    async def delete_achievement(self, achievement_id: int) -> bool:
        """刪除成就.

        Args:
            achievement_id: 成就 ID

        Returns:
            True 如果刪除成功,否則 False
        """
        query = QueryBuilder("achievements").where("id", "=", achievement_id)
        sql, params = query.to_delete_sql()

        async with self.pool.get_connection() as conn:
            cursor = await conn.execute(sql, params)
            await conn.commit()
            return cursor.rowcount > 0

    # =============================================================================
    # User Achievement 操作
    # =============================================================================

    async def award_achievement(
        self, user_id: int, achievement_id: int
    ) -> UserAchievement:
        """為用戶頒發成就.

        Args:
            user_id: 用戶 ID
            achievement_id: 成就 ID

        Returns:
            用戶成就記錄

        Raises:
            DatabaseError: 如果成就已經獲得過
        """
        # 檢查是否已經獲得過
        if await self.has_user_achievement(user_id, achievement_id):
            raise ValueError(f"用戶 {user_id} 已經獲得成就 {achievement_id}")

        query = QueryBuilder("user_achievements").insert({
            "user_id": user_id,
            "achievement_id": achievement_id,
            "earned_at": datetime.now(),
            "notified": False,
        })

        sql, params = query.to_insert_sql()

        async with self.pool.get_connection() as conn:
            cursor = await conn.execute(sql, params)
            await conn.commit()

            record_id = cursor.lastrowid
            return await self.get_user_achievement_by_id(record_id)

    async def get_user_achievement_by_id(
        self, record_id: int
    ) -> UserAchievement | None:
        """根據記錄 ID 取得用戶成就.

        Args:
            record_id: 記錄 ID

        Returns:
            用戶成就記錄或 None
        """
        query = QueryBuilder("user_achievements").select().where("id", "=", record_id)
        sql, params = query.to_select_sql()

        row = await self.execute_query(sql, params, fetch_one=True)
        if row:
            columns = ["id", "user_id", "achievement_id", "earned_at", "notified"]
            row_dict = self._row_to_dict(row, columns)
            return UserAchievement(**row_dict)
        return None

    async def has_user_achievement(self, user_id: int, achievement_id: int) -> bool:
        """檢查用戶是否已獲得特定成就.

        Args:
            user_id: 用戶 ID
            achievement_id: 成就 ID

        Returns:
            True 如果已獲得,否則 False
        """
        query = (
            QueryBuilder("user_achievements")
            .select("1")
            .where("user_id", "=", user_id)
            .where("achievement_id", "=", achievement_id)
            .limit(1)
        )

        sql, params = query.to_select_sql()
        row = await self.execute_query(sql, params, fetch_one=True)
        return row is not None

    async def get_user_achievements(
        self, user_id: int, category_id: int | None = None, limit: int | None = None
    ) -> list[tuple[UserAchievement, Achievement]]:
        """取得用戶的成就列表(含成就詳細資訊).

        Args:
            user_id: 用戶 ID
            category_id: 篩選特定分類
            limit: 最大返回數量

        Returns:
            (用戶成就記錄, 成就詳情) 的元組列表
        """
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

        query = query.order_by("ua.earned_at", OrderDirection.DESC)

        if limit is not None:
            query = query.limit(limit)

        sql, params = query.to_select_sql()
        rows = await self.execute_query(sql, params, fetch_all=True)

        results = []
        for row in rows or []:
            # 定義 JOIN 查詢的欄位順序
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
                "criteria": json.loads(row_dict["criteria"]),
                "points": row_dict["points"],
                "badge_url": row_dict["badge_url"],
                "is_active": row_dict["is_active"],
                "created_at": row_dict["a_created_at"],
                "updated_at": row_dict["a_updated_at"],
            }

            user_achievement = UserAchievement(**user_achievement_data)
            achievement = Achievement(**achievement_data)
            results.append((user_achievement, achievement))

        return results

    async def mark_achievement_notified(
        self, user_id: int, achievement_id: int
    ) -> bool:
        """標記成就通知已發送.

        Args:
            user_id: 用戶 ID
            achievement_id: 成就 ID

        Returns:
            True 如果更新成功,否則 False
        """
        query = (
            QueryBuilder("user_achievements")
            .update({"notified": True})
            .where("user_id", "=", user_id)
            .where("achievement_id", "=", achievement_id)
        )

        sql, params = query.to_update_sql()

        async with self.pool.get_connection() as conn:
            cursor = await conn.execute(sql, params)
            await conn.commit()
            return cursor.rowcount > 0

    async def get_user_achievement_stats(self, user_id: int) -> dict[str, Any]:
        """取得用戶成就統計.

        Args:
            user_id: 用戶 ID

        Returns:
            包含統計資料的字典
        """
        # 總成就數量
        total_query = (
            QueryBuilder("user_achievements").count().where("user_id", "=", user_id)
        )
        total_sql, total_params = total_query.to_select_sql()
        total_row = await self.execute_query(total_sql, total_params, fetch_one=True)
        total_achievements = total_row[0] if total_row else 0

        # 總點數
        points_query = (
            QueryBuilder("user_achievements", "ua")
            .select("SUM(a.points) as total_points")
            .inner_join("achievements a", "a.id = ua.achievement_id")
            .where("ua.user_id", "=", user_id)
        )
        points_sql, points_params = points_query.to_select_sql()
        points_row = await self.execute_query(points_sql, points_params, fetch_one=True)
        total_points = points_row[0] if points_row and points_row[0] else 0

        # 按分類統計
        category_query = (
            QueryBuilder("user_achievements", "ua")
            .select("ac.name", "COUNT(*) as count")
            .inner_join("achievements a", "a.id = ua.achievement_id")
            .inner_join("achievement_categories ac", "ac.id = a.category_id")
            .where("ua.user_id", "=", user_id)
            .group_by("ac.id", "ac.name")
        )
        category_sql, category_params = category_query.to_select_sql()
        category_rows = await self.execute_query(
            category_sql, category_params, fetch_all=True
        )

        categories = {}
        for row in category_rows or []:
            categories[row[0]] = row[1]

        return {
            "total_achievements": total_achievements,
            "total_points": total_points,
            "categories": categories,
        }

    # =============================================================================
    # Achievement Progress 操作
    # =============================================================================

    async def update_progress(
        self,
        user_id: int,
        achievement_id: int,
        current_value: float,
        progress_data: dict[str, Any] | None = None,
    ) -> AchievementProgress:
        """更新用戶成就進度.

        Args:
            user_id: 用戶 ID
            achievement_id: 成就 ID
            current_value: 當前進度值
            progress_data: 額外的進度資料

        Returns:
            更新後的進度記錄
        """
        # 先取得成就資料以獲得目標值
        achievement = await self.get_achievement_by_id(achievement_id)
        if not achievement:
            raise ValueError(f"成就 {achievement_id} 不存在")

        target_value = achievement.criteria.get("target_value", 0)

        # 檢查是否已有進度記錄
        existing_progress = await self.get_user_progress(user_id, achievement_id)

        if existing_progress:
            # 更新現有記錄
            updates = {
                "current_value": current_value,
                "target_value": target_value,
            }
            if progress_data is not None:
                updates["progress_data"] = json.dumps(progress_data, ensure_ascii=False)

            query = (
                QueryBuilder("achievement_progress")
                .update(updates)
                .where("user_id", "=", user_id)
                .where("achievement_id", "=", achievement_id)
            )

            sql, params = query.to_update_sql()

            async with self.pool.get_connection() as conn:
                await conn.execute(sql, params)
                await conn.commit()

        else:
            # 建立新記錄
            insert_data = {
                "user_id": user_id,
                "achievement_id": achievement_id,
                "current_value": current_value,
                "target_value": target_value,
            }
            if progress_data is not None:
                insert_data["progress_data"] = json.dumps(
                    progress_data, ensure_ascii=False
                )

            query = QueryBuilder("achievement_progress").insert(insert_data)
            sql, params = query.to_insert_sql()

            async with self.pool.get_connection() as conn:
                await conn.execute(sql, params)
                await conn.commit()

        # 檢查是否完成成就並自動頒發
        if current_value >= target_value and not await self.has_user_achievement(
            user_id, achievement_id
        ):
            await self.award_achievement(user_id, achievement_id)

        return await self.get_user_progress(user_id, achievement_id)

    async def get_user_progress(
        self, user_id: int, achievement_id: int
    ) -> AchievementProgress | None:
        """取得用戶特定成就的進度.

        Args:
            user_id: 用戶 ID
            achievement_id: 成就 ID

        Returns:
            進度記錄或 None
        """
        query = (
            QueryBuilder("achievement_progress")
            .select()
            .where("user_id", "=", user_id)
            .where("achievement_id", "=", achievement_id)
        )

        sql, params = query.to_select_sql()
        row = await self.execute_query(sql, params, fetch_one=True)

        if row:
            # 定義 achievement_progress 表的欄位順序
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
                row_dict["progress_data"] = json.loads(row_dict["progress_data"])
            return AchievementProgress(**row_dict)
        return None

    async def get_user_progresses(self, user_id: int) -> list[AchievementProgress]:
        """取得用戶所有成就進度.

        Args:
            user_id: 用戶 ID

        Returns:
            進度記錄列表
        """
        query = (
            QueryBuilder("achievement_progress")
            .select()
            .where("user_id", "=", user_id)
            .order_by("last_updated", OrderDirection.DESC)
        )

        sql, params = query.to_select_sql()
        rows = await self.execute_query(sql, params, fetch_all=True)

        progresses = []
        for row in rows or []:
            # 定義 achievement_progress 表的欄位順序
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
                row_dict["progress_data"] = json.loads(row_dict["progress_data"])
            progresses.append(AchievementProgress(**row_dict))

        return progresses

    async def delete_user_progress(self, user_id: int, achievement_id: int) -> bool:
        """刪除用戶成就進度.

        Args:
            user_id: 用戶 ID
            achievement_id: 成就 ID

        Returns:
            True 如果刪除成功,否則 False
        """
        query = (
            QueryBuilder("achievement_progress")
            .where("user_id", "=", user_id)
            .where("achievement_id", "=", achievement_id)
        )

        sql, params = query.to_delete_sql()

        async with self.pool.get_connection() as conn:
            cursor = await conn.execute(sql, params)
            await conn.commit()
            return cursor.rowcount > 0

    # =============================================================================
    # 統計和報表
    # =============================================================================

    async def get_global_achievement_stats(self) -> dict[str, Any]:
        """取得全域成就統計.

        Returns:
            包含全域統計的字典
        """
        # 總成就數量
        total_achievements_query = QueryBuilder("achievements").count()
        total_achievements_sql, _ = total_achievements_query.to_select_sql()
        total_achievements_row = await self.execute_query(
            total_achievements_sql, fetch_one=True
        )
        total_achievements = total_achievements_row[0] if total_achievements_row else 0

        # 活躍成就數量
        active_achievements_query = (
            QueryBuilder("achievements").count().where("is_active", "=", True)
        )
        active_achievements_sql, active_params = (
            active_achievements_query.to_select_sql()
        )
        active_achievements_row = await self.execute_query(
            active_achievements_sql, active_params, fetch_one=True
        )
        active_achievements = (
            active_achievements_row[0] if active_achievements_row else 0
        )

        # 總用戶成就獲得數
        total_user_achievements_query = QueryBuilder("user_achievements").count()
        total_user_achievements_sql, _ = total_user_achievements_query.to_select_sql()
        total_user_achievements_row = await self.execute_query(
            total_user_achievements_sql, fetch_one=True
        )
        total_user_achievements = (
            total_user_achievements_row[0] if total_user_achievements_row else 0
        )

        # 獨特用戶數
        unique_users_query = QueryBuilder("user_achievements").select(
            "COUNT(DISTINCT user_id) as count"
        )
        unique_users_sql, _ = unique_users_query.to_select_sql()
        unique_users_row = await self.execute_query(unique_users_sql, fetch_one=True)
        unique_users = unique_users_row[0] if unique_users_row else 0

        return {
            "total_achievements": total_achievements,
            "active_achievements": active_achievements,
            "total_user_achievements": total_user_achievements,
            "unique_users": unique_users,
        }

    async def get_popular_achievements(
        self, limit: int = 10
    ) -> list[tuple[Achievement, int]]:
        """取得最受歡迎的成就(按獲得人數排序).

        Args:
            limit: 返回的最大數量

        Returns:
            (成就, 獲得人數) 的元組列表
        """
        query = (
            QueryBuilder("achievements", "a")
            .select(
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
                "COUNT(ua.id) as earned_count",
            )
            .left_join("user_achievements ua", "ua.achievement_id = a.id")
            .where("a.is_active", "=", True)
            .group_by("a.id")
            .order_by("earned_count", OrderDirection.DESC)
            .limit(limit)
        )

        sql, params = query.to_select_sql()
        rows = await self.execute_query(sql, params, fetch_all=True)

        results = []
        for row in rows or []:
            # 定義包含聚合欄位的欄位順序
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
                "earned_count",
            ]
            row_dict = self._row_to_dict(row, columns)
            earned_count = row_dict.pop("earned_count", 0)

            # 構建成就物件
            row_dict["criteria"] = json.loads(row_dict["criteria"])
            row_dict["type"] = AchievementType(row_dict["type"])
            achievement = Achievement(**row_dict)

            results.append((achievement, earned_count))

        return results

    # =============================================================================
    # 通知系統相關操作
    # =============================================================================

    async def mark_user_achievement_notified(self, user_achievement_id: int) -> bool:
        """標記用戶成就為已通知.

        Args:
            user_achievement_id: 用戶成就 ID

        Returns:
            True 如果更新成功,否則 False
        """
        query = (
            QueryBuilder("user_achievements")
            .update({"notified": True})
            .where("id", "=", user_achievement_id)
        )

        sql, params = query.to_update_sql()

        async with self.pool.get_connection() as conn:
            cursor = await conn.execute(sql, params)
            await conn.commit()
            return cursor.rowcount > 0

    async def get_notification_preferences(
        self, user_id: int, guild_id: int
    ) -> NotificationPreference | None:
        """取得用戶通知偏好.

        Args:
            user_id: 用戶 ID
            guild_id: 伺服器 ID

        Returns:
            用戶通知偏好或 None
        """
        query = (
            QueryBuilder("notification_preferences")
            .select("*")
            .where("user_id", "=", user_id)
            .where("guild_id", "=", guild_id)
        )

        sql, params = query.to_select_sql()
        row = await self.execute_query(sql, params, fetch_one=True)

        if row:
            # 定義 notification_preferences 表的欄位順序
            columns = [
                "id",
                "user_id",
                "guild_id",
                "dm_notifications",
                "server_announcements",
                "notification_types",
                "created_at",
                "updated_at",
            ]
            row_dict = self._row_to_dict(row, columns)

            # 解析 JSON 格式的通知類型列表
            if row_dict.get("notification_types"):
                row_dict["notification_types"] = json.loads(
                    row_dict["notification_types"]
                )
            else:
                row_dict["notification_types"] = []

            return NotificationPreference(**row_dict)
        return None

    async def create_notification_preferences(
        self, preferences: NotificationPreference
    ) -> NotificationPreference:
        """建立用戶通知偏好.

        Args:
            preferences: 通知偏好資料

        Returns:
            建立後的通知偏好
        """
        query = QueryBuilder("notification_preferences").insert({
            "user_id": preferences.user_id,
            "guild_id": preferences.guild_id,
            "dm_notifications": preferences.dm_notifications,
            "server_announcements": preferences.server_announcements,
            "notification_types": json.dumps(preferences.notification_types),
        })

        sql, params = query.to_insert_sql()

        async with self.pool.get_connection() as conn:
            cursor = await conn.execute(sql, params)
            await conn.commit()

            preference_id = cursor.lastrowid
            return await self.get_notification_preferences_by_id(preference_id)

    async def get_notification_preferences_by_id(
        self, preference_id: int
    ) -> NotificationPreference | None:
        """根據 ID 取得通知偏好.

        Args:
            preference_id: 偏好 ID

        Returns:
            通知偏好或 None
        """
        query = (
            QueryBuilder("notification_preferences")
            .select("*")
            .where("id", "=", preference_id)
        )

        sql, params = query.to_select_sql()
        row = await self.execute_query(sql, params, fetch_one=True)

        if row:
            columns = [
                "id",
                "user_id",
                "guild_id",
                "dm_notifications",
                "server_announcements",
                "notification_types",
                "created_at",
                "updated_at",
            ]
            row_dict = self._row_to_dict(row, columns)

            # 解析 JSON 格式的通知類型列表
            if row_dict.get("notification_types"):
                row_dict["notification_types"] = json.loads(
                    row_dict["notification_types"]
                )
            else:
                row_dict["notification_types"] = []

            return NotificationPreference(**row_dict)
        return None

    async def update_notification_preferences(
        self, preferences: NotificationPreference
    ) -> bool:
        """更新用戶通知偏好.

        Args:
            preferences: 通知偏好資料

        Returns:
            True 如果更新成功,否則 False
        """
        query = (
            QueryBuilder("notification_preferences")
            .update({
                "dm_notifications": preferences.dm_notifications,
                "server_announcements": preferences.server_announcements,
                "notification_types": json.dumps(preferences.notification_types),
                "updated_at": datetime.now(),
            })
            .where("user_id", "=", preferences.user_id)
            .where("guild_id", "=", preferences.guild_id)
        )

        sql, params = query.to_update_sql()

        async with self.pool.get_connection() as conn:
            cursor = await conn.execute(sql, params)
            await conn.commit()
            return cursor.rowcount > 0

    async def get_global_notification_settings(
        self, guild_id: int
    ) -> GlobalNotificationSettings | None:
        """取得伺服器全域通知設定.

        Args:
            guild_id: 伺服器 ID

        Returns:
            全域通知設定或 None
        """
        query = (
            QueryBuilder("global_notification_settings")
            .select("*")
            .where("guild_id", "=", guild_id)
        )

        sql, params = query.to_select_sql()
        row = await self.execute_query(sql, params, fetch_one=True)

        if row:
            columns = [
                "id",
                "guild_id",
                "announcement_channel_id",
                "announcement_enabled",
                "rate_limit_seconds",
                "important_achievements_only",
                "created_at",
                "updated_at",
            ]
            row_dict = self._row_to_dict(row, columns)
            return GlobalNotificationSettings(**row_dict)
        return None

    async def create_global_notification_settings(
        self, settings: GlobalNotificationSettings
    ) -> GlobalNotificationSettings:
        """建立伺服器全域通知設定.

        Args:
            settings: 全域通知設定資料

        Returns:
            建立後的全域通知設定
        """
        query = QueryBuilder("global_notification_settings").insert({
            "guild_id": settings.guild_id,
            "announcement_channel_id": settings.announcement_channel_id,
            "announcement_enabled": settings.announcement_enabled,
            "rate_limit_seconds": settings.rate_limit_seconds,
            "important_achievements_only": settings.important_achievements_only,
        })

        sql, params = query.to_insert_sql()

        async with self.pool.get_connection() as conn:
            cursor = await conn.execute(sql, params)
            await conn.commit()

            settings_id = cursor.lastrowid
            return await self.get_global_notification_settings_by_id(settings_id)

    async def get_global_notification_settings_by_id(
        self, settings_id: int
    ) -> GlobalNotificationSettings | None:
        """根據 ID 取得全域通知設定.

        Args:
            settings_id: 設定 ID

        Returns:
            全域通知設定或 None
        """
        query = (
            QueryBuilder("global_notification_settings")
            .select("*")
            .where("id", "=", settings_id)
        )

        sql, params = query.to_select_sql()
        row = await self.execute_query(sql, params, fetch_one=True)

        if row:
            columns = [
                "id",
                "guild_id",
                "announcement_channel_id",
                "announcement_enabled",
                "rate_limit_seconds",
                "important_achievements_only",
                "created_at",
                "updated_at",
            ]
            row_dict = self._row_to_dict(row, columns)
            return GlobalNotificationSettings(**row_dict)
        return None

    async def update_global_notification_settings(
        self, settings: GlobalNotificationSettings
    ) -> bool:
        """更新伺服器全域通知設定.

        Args:
            settings: 全域通知設定資料

        Returns:
            True 如果更新成功,否則 False
        """
        query = (
            QueryBuilder("global_notification_settings")
            .update({
                "announcement_channel_id": settings.announcement_channel_id,
                "announcement_enabled": settings.announcement_enabled,
                "rate_limit_seconds": settings.rate_limit_seconds,
                "important_achievements_only": settings.important_achievements_only,
                "updated_at": datetime.now(),
            })
            .where("guild_id", "=", settings.guild_id)
        )

        sql, params = query.to_update_sql()

        async with self.pool.get_connection() as conn:
            cursor = await conn.execute(sql, params)
            await conn.commit()
            return cursor.rowcount > 0

    async def create_notification_event(
        self, event: NotificationEvent
    ) -> NotificationEvent:
        """建立通知事件記錄.

        Args:
            event: 通知事件資料

        Returns:
            建立後的通知事件
        """
        query = QueryBuilder("notification_events").insert({
            "user_id": event.user_id,
            "guild_id": event.guild_id,
            "achievement_id": event.achievement_id,
            "notification_type": event.notification_type,
            "sent_at": event.sent_at,
            "delivery_status": event.delivery_status,
            "error_message": event.error_message,
            "retry_count": event.retry_count,
        })

        sql, params = query.to_insert_sql()

        async with self.pool.get_connection() as conn:
            cursor = await conn.execute(sql, params)
            await conn.commit()

            event_id = cursor.lastrowid
            return await self.get_notification_event_by_id(event_id)

    async def get_notification_event_by_id(
        self, event_id: int
    ) -> NotificationEvent | None:
        """根據 ID 取得通知事件.

        Args:
            event_id: 事件 ID

        Returns:
            通知事件或 None
        """
        query = (
            QueryBuilder("notification_events").select("*").where("id", "=", event_id)
        )

        sql, params = query.to_select_sql()
        row = await self.execute_query(sql, params, fetch_one=True)

        if row:
            columns = [
                "id",
                "user_id",
                "guild_id",
                "achievement_id",
                "notification_type",
                "sent_at",
                "delivery_status",
                "error_message",
                "retry_count",
            ]
            row_dict = self._row_to_dict(row, columns)
            return NotificationEvent(**row_dict)
        return None

    async def get_notification_events_by_user(
        self, user_id: int, guild_id: int | None = None, limit: int = 100
    ) -> list[NotificationEvent]:
        """取得用戶的通知事件記錄.

        Args:
            user_id: 用戶 ID
            guild_id: 伺服器 ID(可選)
            limit: 最大返回數量

        Returns:
            通知事件列表
        """
        query = (
            QueryBuilder("notification_events")
            .select("*")
            .where("user_id", "=", user_id)
        )

        if guild_id:
            query = query.where("guild_id", "=", guild_id)

        query = query.order_by("sent_at", OrderDirection.DESC).limit(limit)

        sql, params = query.to_select_sql()
        rows = await self.execute_query(sql, params, fetch_all=True)

        events = []
        for row in rows or []:
            columns = [
                "id",
                "user_id",
                "guild_id",
                "achievement_id",
                "notification_type",
                "sent_at",
                "delivery_status",
                "error_message",
                "retry_count",
            ]
            row_dict = self._row_to_dict(row, columns)
            events.append(NotificationEvent(**row_dict))

        return events


class AchievementEventRepository(BaseRepository):
    """成就事件資料存取庫.

    提供成就事件系統所有資料操作的統一介面.
    """

    def __init__(self, pool: DatabasePool):
        """初始化成就事件資料存取庫.

        Args:
            pool: 資料庫連線池
        """
        super().__init__(pool, "achievement_events")

    # =============================================================================
    # 事件資料基本操作
    # =============================================================================

    async def create_event(
        self, event_data: AchievementEventData
    ) -> AchievementEventData:
        """建立新的成就事件記錄.

        Args:
            event_data: 成就事件資料

        Returns:
            建立後的成就事件(包含 ID)
        """
        try:
            sql = """
            INSERT INTO achievement_events
            (user_id, guild_id, event_type, event_data, timestamp, channel_id, processed, correlation_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """

            params = (
                event_data.user_id,
                event_data.guild_id,
                event_data.event_type,
                event_data.get_event_data_json(),
                event_data.timestamp,
                event_data.channel_id,
                event_data.processed,
                event_data.correlation_id,
            )

            result = await self.execute_query(sql, params)

            # 設置新的 ID
            event_data.id = result.lastrowid
            return event_data

        except Exception as e:
            logger.error(f"[事件資料庫]建立事件失敗: {e}")
            raise

    async def create_events_batch(
        self, events: list[AchievementEventData]
    ) -> list[AchievementEventData]:
        """批次建立多個成就事件記錄.

        Args:
            events: 成就事件資料列表

        Returns:
            建立後的成就事件列表
        """
        if not events:
            return []

        try:
            sql = """
            INSERT INTO achievement_events
            (user_id, guild_id, event_type, event_data, timestamp, channel_id, processed, correlation_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """

            params_list = []
            for event_data in events:
                params = (
                    event_data.user_id,
                    event_data.guild_id,
                    event_data.event_type,
                    event_data.get_event_data_json(),
                    event_data.timestamp,
                    event_data.channel_id,
                    event_data.processed,
                    event_data.correlation_id,
                )
                params_list.append(params)

            await self.execute_batch(sql, params_list)

            logger.info(f"[事件資料庫]批次建立事件成功: {len(events)} 個")
            return events

        except Exception as e:
            logger.error(f"[事件資料庫]批次建立事件失敗: {e}")
            raise

    async def get_event_by_id(self, event_id: int) -> AchievementEventData | None:
        """根據 ID 取得成就事件.

        Args:
            event_id: 事件 ID

        Returns:
            成就事件資料,如果不存在則返回 None
        """
        try:
            query = QueryBuilder(self.table_name).select("*").where("id", "=", event_id)

            sql, params = query.to_select_sql()
            row = await self.execute_query(sql, params, fetch_one=True)

            if not row:
                return None

            return self._row_to_event_model(row)

        except Exception as e:
            logger.error(f"[事件資料庫]取得事件失敗 {event_id}: {e}")
            return None

    async def get_events_by_user(
        self,
        user_id: int,
        event_types: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[AchievementEventData]:
        """取得用戶的成就事件.

        Args:
            user_id: 用戶 ID
            event_types: 篩選的事件類型列表(可選)
            limit: 返回的最大數量
            offset: 偏移量
            start_time: 開始時間(可選)
            end_time: 結束時間(可選)

        Returns:
            成就事件資料列表
        """
        try:
            query = (
                QueryBuilder(self.table_name).select("*").where("user_id", "=", user_id)
            )

            if event_types:
                query = query.where_in("event_type", event_types)

            if start_time:
                query = query.where("timestamp", ">=", start_time)

            if end_time:
                query = query.where("timestamp", "<=", end_time)

            query = (
                query.order_by("timestamp", OrderDirection.DESC)
                .limit(limit)
                .offset(offset)
            )

            sql, params = query.to_select_sql()
            rows = await self.execute_query(sql, params, fetch_all=True)

            return [self._row_to_event_model(row) for row in rows or []]

        except Exception as e:
            logger.error(f"[事件資料庫]取得用戶事件失敗 {user_id}: {e}")
            return []

    async def get_events_by_guild(
        self,
        guild_id: int,
        event_types: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[AchievementEventData]:
        """取得伺服器的成就事件.

        Args:
            guild_id: 伺服器 ID
            event_types: 篩選的事件類型列表(可選)
            limit: 返回的最大數量
            offset: 偏移量
            start_time: 開始時間(可選)
            end_time: 結束時間(可選)

        Returns:
            成就事件資料列表
        """
        try:
            query = (
                QueryBuilder(self.table_name)
                .select("*")
                .where("guild_id", "=", guild_id)
            )

            if event_types:
                query = query.where_in("event_type", event_types)

            if start_time:
                query = query.where("timestamp", ">=", start_time)

            if end_time:
                query = query.where("timestamp", "<=", end_time)

            query = (
                query.order_by("timestamp", OrderDirection.DESC)
                .limit(limit)
                .offset(offset)
            )

            sql, params = query.to_select_sql()
            rows = await self.execute_query(sql, params, fetch_all=True)

            return [self._row_to_event_model(row) for row in rows or []]

        except Exception as e:
            logger.error(f"[事件資料庫]取得伺服器事件失敗 {guild_id}: {e}")
            return []

    async def get_unprocessed_events(
        self, limit: int = 100, event_types: list[str] | None = None
    ) -> list[AchievementEventData]:
        """取得未處理的成就事件.

        Args:
            limit: 返回的最大數量
            event_types: 篩選的事件類型列表(可選)

        Returns:
            未處理的成就事件資料列表
        """
        try:
            query = (
                QueryBuilder(self.table_name).select("*").where("processed", "=", False)
            )

            if event_types:
                query = query.where_in("event_type", event_types)

            query = query.order_by("timestamp", OrderDirection.ASC).limit(limit)

            sql, params = query.to_select_sql()
            rows = await self.execute_query(sql, params, fetch_all=True)

            return [self._row_to_event_model(row) for row in rows or []]

        except Exception as e:
            logger.error(f"[事件資料庫]取得未處理事件失敗: {e}")
            return []

    async def mark_events_processed(self, event_ids: list[int]) -> int:
        """標記事件為已處理.

        Args:
            event_ids: 事件 ID 列表

        Returns:
            成功更新的記錄數量
        """
        if not event_ids:
            return 0

        try:
            query = (
                QueryBuilder(self.table_name)
                .update({"processed": True})
                .where_in("id", event_ids)
            )

            sql, params = query.to_update_sql()
            result = await self.execute_query(sql, params)

            updated_count = result.rowcount
            logger.debug(f"[事件資料庫]標記事件已處理: {updated_count} 個")
            return updated_count

        except Exception as e:
            logger.error(f"[事件資料庫]標記事件處理失敗: {e}")
            return 0

    # =============================================================================
    # 統計和分析查詢
    # =============================================================================

    async def get_event_stats(
        self,
        guild_id: int | None = None,
        user_id: int | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict[str, Any]:
        """取得事件統計資訊.

        Args:
            guild_id: 伺服器 ID(可選)
            user_id: 用戶 ID(可選)
            start_time: 開始時間(可選)
            end_time: 結束時間(可選)

        Returns:
            事件統計資訊字典
        """
        try:
            # 基本統計查詢
            query = QueryBuilder(self.table_name).select(
                "COUNT(*) as total_events",
                "COUNT(CASE WHEN processed = 1 THEN 1 END) as processed_events",
                "COUNT(CASE WHEN processed = 0 THEN 1 END) as unprocessed_events",
                "COUNT(DISTINCT user_id) as unique_users",
                "MIN(timestamp) as earliest_event",
                "MAX(timestamp) as latest_event",
            )

            if guild_id:
                query = query.where("guild_id", "=", guild_id)

            if user_id:
                query = query.where("user_id", "=", user_id)

            if start_time:
                query = query.where("timestamp", ">=", start_time)

            if end_time:
                query = query.where("timestamp", "<=", end_time)

            sql, params = query.to_select_sql()
            row = await self.execute_query(sql, params, fetch_one=True)

            stats = self._row_to_dict(row) if row else {}

            # 事件類型統計
            type_query = QueryBuilder(self.table_name).select(
                "event_type", "COUNT(*) as count"
            )

            if guild_id:
                type_query = type_query.where("guild_id", "=", guild_id)

            if user_id:
                type_query = type_query.where("user_id", "=", user_id)

            if start_time:
                type_query = type_query.where("timestamp", ">=", start_time)

            if end_time:
                type_query = type_query.where("timestamp", "<=", end_time)

            type_query = type_query.group_by("event_type").order_by(
                "count", OrderDirection.DESC
            )

            sql, params = type_query.to_select_sql()
            type_rows = await self.execute_query(sql, params, fetch_all=True)

            stats["event_types"] = {
                self._row_to_dict(row)["event_type"]: self._row_to_dict(row)["count"]
                for row in type_rows or []
            }

            return stats

        except Exception as e:
            logger.error(f"[事件資料庫]取得事件統計失敗: {e}")
            return {}

    # =============================================================================
    # 資料清理和歸檔
    # =============================================================================

    async def cleanup_old_events(
        self,
        older_than_days: int = 30,
        batch_size: int = 1000,
        keep_processed: bool = True,
    ) -> int:
        """清理舊的事件資料.

        Args:
            older_than_days: 保留多少天內的資料
            batch_size: 批次刪除大小
            keep_processed: 是否保留已處理的事件

        Returns:
            刪除的記錄數量
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=older_than_days)

            query = (
                QueryBuilder(self.table_name)
                .select("COUNT(*)")
                .where("timestamp", "<", cutoff_date)
            )

            if not keep_processed:
                query = query.where("processed", "=", False)

            sql, params = query.to_select_sql()
            count_result = await self.execute_query(sql, params, fetch_one=True)
            total_to_delete = (
                self._row_to_dict(count_result).get("COUNT(*)", 0)
                if count_result
                else 0
            )

            if total_to_delete == 0:
                return 0

            # 批次刪除
            deleted_count = 0
            while deleted_count < total_to_delete:
                delete_query = (
                    QueryBuilder(self.table_name)
                    .delete()
                    .where("timestamp", "<", cutoff_date)
                    .limit(batch_size)
                )

                if not keep_processed:
                    delete_query = delete_query.where("processed", "=", False)

                sql, params = delete_query.to_delete_sql()
                result = await self.execute_query(sql, params)

                batch_deleted = result.rowcount
                if batch_deleted == 0:
                    break

                deleted_count += batch_deleted
                logger.debug(f"[事件資料庫]批次清理事件: {batch_deleted} 個")

            logger.info(f"[事件資料庫]事件清理完成: 刪除 {deleted_count} 個舊事件")
            return deleted_count

        except Exception as e:
            logger.error(f"[事件資料庫]清理舊事件失敗: {e}")
            return 0

    async def archive_old_events(
        self,
        older_than_days: int = 90,
        archive_table: str = "achievement_events_archive",
    ) -> int:
        """歸檔舊的事件資料.

        Args:
            older_than_days: 歸檔多少天前的資料
            archive_table: 歸檔表名稱

        Returns:
            歸檔的記錄數量
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=older_than_days)

            # 確保歸檔表存在
            await self._ensure_archive_table_exists(archive_table)

            # 將舊資料移動到歸檔表
            sql = f"""
            INSERT INTO {archive_table}
            SELECT * FROM {self.table_name}
            WHERE timestamp < ? AND processed = 1
            """

            result = await self.execute_query(sql, (cutoff_date,))
            archived_count = result.rowcount

            if archived_count > 0:
                # 刪除已歸檔的資料
                delete_sql = f"""
                DELETE FROM {self.table_name}
                WHERE timestamp < ? AND processed = 1
                """

                await self.execute_query(delete_sql, (cutoff_date,))

            logger.info(f"[事件資料庫]事件歸檔完成: 歸檔 {archived_count} 個事件")
            return archived_count

        except Exception as e:
            logger.error(f"[事件資料庫]歸檔事件失敗: {e}")
            return 0

    async def _ensure_archive_table_exists(self, archive_table: str) -> None:
        """確保歸檔表存在."""
        sql = f"""
        CREATE TABLE IF NOT EXISTS {archive_table} (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            guild_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            event_data TEXT NOT NULL,
            timestamp DATETIME NOT NULL,
            channel_id INTEGER,
            processed BOOLEAN NOT NULL DEFAULT 0,
            correlation_id TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            archived_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """

        await self.execute_query(sql)

    def _row_to_event_model(self, row: Any) -> AchievementEventData:
        """將資料庫行轉換為 AchievementEventData 模型.

        Args:
            row: 資料庫行物件

        Returns:
            AchievementEventData 物件
        """
        row_dict = self._row_to_dict(row)

        # 解析 JSON 事件資料
        event_data = json.loads(row_dict.get("event_data", "{}"))

        return AchievementEventData(
            id=row_dict.get("id"),
            user_id=row_dict["user_id"],
            guild_id=row_dict["guild_id"],
            event_type=row_dict["event_type"],
            event_data=event_data,
            timestamp=datetime.fromisoformat(row_dict["timestamp"])
            if isinstance(row_dict["timestamp"], str)
            else row_dict["timestamp"],
            channel_id=row_dict.get("channel_id"),
            processed=bool(row_dict.get("processed", False)),
            correlation_id=row_dict.get("correlation_id"),
        )

    # =============================================================================
    # 用戶成就管理操作 (Story 4.3)
    # =============================================================================

    async def create_user_achievement(
        self, user_achievement: UserAchievement
    ) -> UserAchievement:
        """創建用戶成就記錄.

        Args:
            user_achievement: 用戶成就資料

        Returns:
            已儲存的用戶成就記錄
        """
        query = QueryBuilder("user_achievements").insert({
            "user_id": user_achievement.user_id,
            "achievement_id": user_achievement.achievement_id,
            "earned_at": user_achievement.earned_at.isoformat(),
            "notified": user_achievement.notified,
        })

        sql, params = query.to_insert_sql()
        result = await self.execute_query(sql, params, return_id=True)

        # 返回完整的用戶成就記錄
        user_achievement.id = result
        return user_achievement

    async def delete_user_achievement(self, user_id: int, achievement_id: int) -> bool:
        """刪除用戶成就記錄.

        Args:
            user_id: 用戶 ID
            achievement_id: 成就 ID

        Returns:
            是否成功刪除
        """
        query = (
            QueryBuilder("user_achievements")
            .where("user_id", user_id)
            .where("achievement_id", achievement_id)
        )

        sql, params = query.to_delete_sql()
        result = await self.execute_query(sql, params, return_changes=True)
        return result > 0

    async def get_user_progress_by_achievement(
        self, user_id: int, achievement_id: int
    ) -> AchievementProgress | None:
        """獲取用戶特定成就的進度.

        Args:
            user_id: 用戶 ID
            achievement_id: 成就 ID

        Returns:
            成就進度記錄,如果不存在則返回 None
        """
        query = (
            QueryBuilder("achievement_progress")
            .where("user_id", user_id)
            .where("achievement_id", achievement_id)
        )

        sql, params = query.to_select_sql()
        row = await self.execute_query(sql, params, fetch_one=True)

        if row:
            return self._row_to_progress_model(row)
        return None

    async def get_user_progress(
        self, user_id: int, category_id: int | None = None
    ) -> list[AchievementProgress]:
        """獲取用戶的成就進度列表.

        Args:
            user_id: 用戶 ID
            category_id: 分類 ID(可選)

        Returns:
            成就進度列表
        """
        if category_id:
            # 需要 JOIN achievements 表來篩選分類
            query = (
                QueryBuilder("achievement_progress", "ap")
                .select("ap.*")
                .join("achievements a", "ap.achievement_id = a.id")
                .where("ap.user_id", user_id)
                .where("a.category_id", category_id)
            )
        else:
            query = QueryBuilder("achievement_progress").where("user_id", user_id)

        sql, params = query.to_select_sql()
        rows = await self.execute_query(sql, params, fetch_all=True)

        return [self._row_to_progress_model(row) for row in rows]

    async def create_user_progress(
        self, progress: AchievementProgress
    ) -> AchievementProgress:
        """創建用戶成就進度記錄.

        Args:
            progress: 成就進度資料

        Returns:
            已儲存的進度記錄
        """
        query = QueryBuilder("achievement_progress").insert({
            "user_id": progress.user_id,
            "achievement_id": progress.achievement_id,
            "current_value": progress.current_value,
            "target_value": progress.target_value,
            "progress_data": json.dumps(progress.progress_data),
            "last_updated": progress.last_updated.isoformat(),
        })

        sql, params = query.to_insert_sql()
        result = await self.execute_query(sql, params, return_id=True)

        progress.id = result
        return progress

    async def update_user_progress(
        self, progress: AchievementProgress
    ) -> AchievementProgress:
        """更新用戶成就進度記錄.

        Args:
            progress: 成就進度資料

        Returns:
            已更新的進度記錄
        """
        query = (
            QueryBuilder("achievement_progress")
            .where("id", progress.id)
            .update({
                "current_value": progress.current_value,
                "target_value": progress.target_value,
                "progress_data": json.dumps(progress.progress_data),
                "last_updated": progress.last_updated.isoformat(),
            })
        )

        sql, params = query.to_update_sql()
        await self.execute_query(sql, params)
        return progress

    async def delete_user_achievements_by_category(
        self, user_id: int, category_id: int
    ) -> int:
        """刪除用戶特定分類的所有成就.

        Args:
            user_id: 用戶 ID
            category_id: 分類 ID

        Returns:
            刪除的記錄數
        """
        # 需要先查詢該分類下的所有成就 ID
        achievement_query = (
            QueryBuilder("achievements").select("id").where("category_id", category_id)
        )
        achievement_sql, achievement_params = achievement_query.to_select_sql()
        achievement_rows = await self.execute_query(
            achievement_sql, achievement_params, fetch_all=True
        )

        if not achievement_rows:
            return 0

        achievement_ids = [row[0] for row in achievement_rows]

        # 刪除用戶成就記錄
        query = (
            QueryBuilder("user_achievements")
            .where("user_id", user_id)
            .where_in("achievement_id", achievement_ids)
        )

        sql, params = query.to_delete_sql()
        return await self.execute_query(sql, params, return_changes=True)

    async def delete_user_progress_by_category(
        self, user_id: int, category_id: int
    ) -> int:
        """刪除用戶特定分類的所有進度.

        Args:
            user_id: 用戶 ID
            category_id: 分類 ID

        Returns:
            刪除的記錄數
        """
        # 需要先查詢該分類下的所有成就 ID
        achievement_query = (
            QueryBuilder("achievements").select("id").where("category_id", category_id)
        )
        achievement_sql, achievement_params = achievement_query.to_select_sql()
        achievement_rows = await self.execute_query(
            achievement_sql, achievement_params, fetch_all=True
        )

        if not achievement_rows:
            return 0

        achievement_ids = [row[0] for row in achievement_rows]

        # 刪除進度記錄
        query = (
            QueryBuilder("achievement_progress")
            .where("user_id", user_id)
            .where_in("achievement_id", achievement_ids)
        )

        sql, params = query.to_delete_sql()
        return await self.execute_query(sql, params, return_changes=True)

    async def delete_all_user_achievements(self, user_id: int) -> int:
        """刪除用戶的所有成就記錄.

        Args:
            user_id: 用戶 ID

        Returns:
            刪除的記錄數
        """
        query = QueryBuilder("user_achievements").where("user_id", user_id)
        sql, params = query.to_delete_sql()
        return await self.execute_query(sql, params, return_changes=True)

    async def delete_all_user_progress(self, user_id: int) -> int:
        """刪除用戶的所有進度記錄.

        Args:
            user_id: 用戶 ID

        Returns:
            刪除的記錄數
        """
        query = QueryBuilder("achievement_progress").where("user_id", user_id)
        sql, params = query.to_delete_sql()
        return await self.execute_query(sql, params, return_changes=True)

    async def get_achievements_count(self, category_id: int | None = None) -> int:
        """獲取成就總數.

        Args:
            category_id: 分類 ID(可選)

        Returns:
            成就總數
        """
        query = (
            QueryBuilder("achievements")
            .select("COUNT(*) as count")
            .where("is_active", True)
        )

        if category_id:
            query = query.where("category_id", category_id)

        sql, params = query.to_select_sql()
        row = await self.execute_query(sql, params, fetch_one=True)
        return row[0] if row else 0

    async def get_users_near_achievement_completion(
        self, achievement_id: int, threshold_percentage: float = 80.0
    ) -> list[tuple[int, float]]:
        """查找接近完成特定成就的用戶.

        Args:
            achievement_id: 成就 ID
            threshold_percentage: 進度閾值百分比

        Returns:
            (用戶ID, 進度百分比) 的元組列表
        """
        try:
            # 查詢指定成就的目標值
            achievement_query = (
                QueryBuilder("achievements")
                .select("target_value")
                .where("id", achievement_id)
            )

            achievement_sql, achievement_params = achievement_query.to_select_sql()
            achievement_row = await self.execute_query(
                achievement_sql, achievement_params, fetch_one=True
            )

            if not achievement_row:
                logger.warning(f"成就 {achievement_id} 不存在")
                return []

            target_value = float(achievement_row[0])
            threshold_value = target_value * (threshold_percentage / 100.0)

            # 查詢進度達到閾值的用戶
            progress_query = (
                QueryBuilder("achievement_progress")
                .select("user_id", "current_value", "target_value")
                .where("achievement_id", achievement_id)
                .where("current_value", ">=", threshold_value)
                .where("current_value", "<", target_value)
                .order_by("current_value", OrderDirection.DESC)
            )

            progress_sql, progress_params = progress_query.to_select_sql()
            progress_rows = await self.execute_query(
                progress_sql, progress_params, fetch_all=True
            )

            # 計算進度百分比
            result = []
            for row in progress_rows:
                user_id = row[0]
                current_value = float(row[1])
                target_value = float(row[2])
                percentage = (
                    (current_value / target_value * 100) if target_value > 0 else 0
                )
                result.append((user_id, percentage))

            logger.debug(
                f"找到 {len(result)} 個用戶接近完成成就 {achievement_id}",
                extra={
                    "achievement_id": achievement_id,
                    "threshold_percentage": threshold_percentage,
                    "user_count": len(result),
                },
            )

            return result

        except Exception as e:
            logger.error(f"查詢接近完成成就的用戶失敗: {e}", exc_info=True)
            return []

    async def get_achievement_progress_statistics(
        self, achievement_id: int
    ) -> dict[str, Any]:
        """獲取成就的進度統計資訊.

        Args:
            achievement_id: 成就 ID

        Returns:
            統計資訊字典
        """
        try:
            # 查詢進度統計
            stats_query = (
                QueryBuilder("achievement_progress")
                .select(
                    "COUNT(*) as total_users",
                    "AVG(current_value) as avg_progress",
                    "MIN(current_value) as min_progress",
                    "MAX(current_value) as max_progress",
                    "target_value",
                )
                .where("achievement_id", achievement_id)
                .group_by("target_value")
            )

            stats_sql, stats_params = stats_query.to_select_sql()
            stats_row = await self.execute_query(
                stats_sql, stats_params, fetch_one=True
            )

            if not stats_row:
                return {
                    "total_users": 0,
                    "avg_progress": 0.0,
                    "min_progress": 0.0,
                    "max_progress": 0.0,
                    "completion_rate": 0.0,
                    "target_value": 0.0,
                }

            total_users = stats_row[0]
            avg_progress = float(stats_row[1]) if stats_row[1] else 0.0
            min_progress = float(stats_row[2]) if stats_row[2] else 0.0
            max_progress = float(stats_row[3]) if stats_row[3] else 0.0
            target_value = float(stats_row[4]) if stats_row[4] else 0.0

            # 計算完成率
            completion_query = (
                QueryBuilder("achievement_progress")
                .select("COUNT(*) as completed_users")
                .where("achievement_id", achievement_id)
                .where("current_value", ">=", target_value)
            )

            completion_sql, completion_params = completion_query.to_select_sql()
            completion_row = await self.execute_query(
                completion_sql, completion_params, fetch_one=True
            )
            completed_users = completion_row[0] if completion_row else 0

            completion_rate = (
                (completed_users / total_users * 100) if total_users > 0 else 0.0
            )

            return {
                "total_users": total_users,
                "completed_users": completed_users,
                "avg_progress": avg_progress,
                "min_progress": min_progress,
                "max_progress": max_progress,
                "completion_rate": completion_rate,
                "target_value": target_value,
                "avg_progress_percentage": (avg_progress / target_value * 100)
                if target_value > 0
                else 0.0,
            }

        except Exception as e:
            logger.error(f"獲取成就進度統計失敗: {e}", exc_info=True)
            return {}

    def _row_to_progress_model(self, row: Any) -> AchievementProgress:
        """將資料庫行轉換為 AchievementProgress 模型.

        Args:
            row: 資料庫行物件

        Returns:
            AchievementProgress 物件
        """
        row_dict = self._row_to_dict(row)

        # 解析 JSON 進度資料
        progress_data = json.loads(row_dict.get("progress_data", "{}"))

        return AchievementProgress(
            id=row_dict.get("id"),
            user_id=row_dict["user_id"],
            achievement_id=row_dict["achievement_id"],
            current_value=float(row_dict["current_value"]),
            target_value=float(row_dict["target_value"]),
            progress_data=progress_data,
            last_updated=datetime.fromisoformat(row_dict["last_updated"])
            if isinstance(row_dict["last_updated"], str)
            else row_dict["last_updated"],
        )


__all__ = [
    "AchievementEventRepository",
    "AchievementRepository",
]
