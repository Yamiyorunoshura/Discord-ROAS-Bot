"""成就系統核心業務邏輯服務.

此模組實作成就系統的核心業務邏輯,提供:
- 完整的成就 CRUD 操作
- 成就查詢和篩選功能
- 業務規則驗證和邏輯處理
- 快取策略和效能優化
- 統一的錯誤處理和日誌記錄

服務層遵循以下設計原則:
- 使用 Repository Pattern 隔離資料存取
- 支援異步操作和上下文管理
- 提供完整的型別註解和文檔
- 整合快取系統提升效能
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..database.repository import AchievementRepository

from ..database.models import (
    Achievement,
    AchievementCategory,
    AchievementType,
    UserAchievement,
)
from .cache_service import AchievementCacheService

logger = logging.getLogger(__name__)


class AchievementService:
    """成就系統核心業務邏輯服務.

    提供成就系統的所有業務邏輯操作,包含:
    - 成就和分類的 CRUD 操作
    - 用戶成就獲得和進度管理
    - 業務規則驗證和邏輯處理
    - 快取策略和效能優化
    """

    def __init__(
        self,
        repository: AchievementRepository,
        cache_service: AchievementCacheService | None = None,
    ):
        """初始化成就服務.

        Args:
            repository: 成就資料存取庫
            cache_service: 快取服務實例(可選,預設會建立新實例)
        """
        self._repository = repository
        self._cache_service = cache_service or AchievementCacheService()

        logger.info(
            "AchievementService 初始化完成",
            extra={"cache_service": "provided" if cache_service else "created"},
        )

    async def __aenter__(self) -> AchievementService:
        """異步上下文管理器進入."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """異步上下文管理器退出."""
        # 使用快取服務的清理方法
        await self._cache_service.__aexit__(exc_type, exc_val, exc_tb)

    def _get_cache_key(self, cache_type: str, *args: Any) -> str:
        """生成快取鍵值.

        Args:
            cache_type: 快取類型
            *args: 快取參數

        Returns:
            快取鍵值字串
        """
        return self._cache_service.get_cache_key(cache_type, *args)

    def _invalidate_cache_by_operation(self, operation_type: str, **kwargs) -> None:
        """根據操作類型無效化快取.

        Args:
            operation_type: 操作類型
            **kwargs: 操作相關參數
        """
        self._cache_service.invalidate_by_operation(operation_type, **kwargs)

    # =============================================================================
    # Achievement Category 業務邏輯
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
            ValueError: 分類名稱已存在或資料無效
        """
        existing_category = await self._repository.get_category_by_name(category.name)
        if existing_category:
            raise ValueError(f"分類名稱 '{category.name}' 已存在")

        try:
            created_category = await self._repository.create_category(category)

            # 無效化相關快取
            self._invalidate_cache_by_operation(
                "create_category", category_id=created_category.id
            )

            logger.info(
                "成就分類建立成功",
                extra={
                    "category_id": created_category.id,
                    "category_name": created_category.name,
                },
            )

            return created_category

        except Exception as e:
            logger.error(
                "成就分類建立失敗",
                extra={"category_name": category.name, "error": str(e)},
                exc_info=True,
            )
            raise

    async def get_category_by_id(self, category_id: int) -> AchievementCategory | None:
        """根據 ID 取得成就分類.

        Args:
            category_id: 分類 ID

        Returns:
            成就分類物件或 None
        """
        cache_key = self._get_cache_key("category", category_id)

        # 檢查快取
        cached_result = self._cache_service.get("category", cache_key)
        if cached_result is not None:
            return cached_result

        try:
            category = await self._repository.get_category_by_id(category_id)

            # 存入快取
            if category:
                self._cache_service.set("category", cache_key, category)

            return category

        except Exception as e:
            logger.error(
                "取得成就分類失敗",
                extra={"category_id": category_id, "error": str(e)},
                exc_info=True,
            )
            raise

    async def list_categories(
        self, active_only: bool = True
    ) -> list[AchievementCategory]:
        """取得所有成就分類列表.

        Args:
            active_only: 是否只取得啟用的分類

        Returns:
            成就分類列表,按 display_order 排序
        """
        cache_key = self._get_cache_key("categories", active_only)

        # 檢查快取
        cached_result = self._cache_service.get("category", cache_key)
        if cached_result is not None:
            return cached_result

        try:
            categories = await self._repository.list_categories(active_only)

            # 存入快取
            self._cache_service.set("category", cache_key, categories)

            logger.debug(
                "取得成就分類列表",
                extra={"count": len(categories), "active_only": active_only},
            )

            return categories

        except Exception as e:
            logger.error(
                "取得成就分類列表失敗",
                extra={"active_only": active_only, "error": str(e)},
                exc_info=True,
            )
            raise

    async def update_category(
        self, category_id: int, updates: dict[str, Any]
    ) -> AchievementCategory | None:
        """更新成就分類.

        Args:
            category_id: 分類 ID
            updates: 要更新的欄位字典

        Returns:
            更新後的分類物件或 None(如果分類不存在)

        Raises:
            ValueError: 更新資料無效或違反業務規則
        """
        if not updates:
            raise ValueError("更新資料不能為空")

        if "name" in updates:
            existing_category = await self._repository.get_category_by_name(
                updates["name"]
            )
            if existing_category and existing_category.id != category_id:
                raise ValueError(f"分類名稱 '{updates['name']}' 已存在")

        try:
            success = await self._repository.update_category(category_id, updates)
            if not success:
                return None

            # 無效化相關快取
            self._invalidate_cache_by_operation(
                "update_category", category_id=category_id
            )

            # 取得更新後的分類
            updated_category = await self.get_category_by_id(category_id)

            logger.info(
                "成就分類更新成功",
                extra={
                    "category_id": category_id,
                    "updated_fields": list(updates.keys()),
                },
            )

            return updated_category

        except Exception as e:
            logger.error(
                "成就分類更新失敗",
                extra={"category_id": category_id, "updates": updates, "error": str(e)},
                exc_info=True,
            )
            raise

    async def delete_category(self, category_id: int) -> bool:
        """刪除成就分類.

        Args:
            category_id: 分類 ID

        Returns:
            True 如果刪除成功,否則 False

        Raises:
            ValueError: 分類下還有成就時不能刪除
        """
        achievements = await self.list_achievements(category_id=category_id)
        if achievements:
            raise ValueError(
                f"分類 {category_id} 下還有 {len(achievements)} 個成就,無法刪除"
            )

        try:
            success = await self._repository.delete_category(category_id)

            if success:
                # 無效化相關快取
                self._invalidate_cache_by_operation(
                    "delete_category", category_id=category_id
                )

                logger.info("成就分類刪除成功", extra={"category_id": category_id})

            return success

        except Exception as e:
            logger.error(
                "成就分類刪除失敗",
                extra={"category_id": category_id, "error": str(e)},
                exc_info=True,
            )
            raise

    # =============================================================================
    # 分類樹業務邏輯
    # =============================================================================

    async def get_achievement_categories(self, _guild_id: int | None = None) -> list[AchievementCategory]:
        """取得成就分類列表(API 兼容方法).

        Args:
            guild_id: 伺服器 ID(目前未使用,保留供未來擴展)

        Returns:
            成就分類列表
        """
        return await self.list_categories(active_only=True)

    async def get_achievements_by_category(
        self, _guild_id: int | None, category: str | int
    ) -> list[Achievement]:
        """根據分類取得成就列表(API 兼容方法).

        Args:
            guild_id: 伺服器 ID(目前未使用,保留供未來擴展)
            category: 分類名稱或分類 ID

        Returns:
            成就列表
        """
        # 處理分類參數
        category_id = None
        if isinstance(category, int):
            category_id = category
        elif isinstance(category, str):
            if category.isdigit():
                category_id = int(category)
            else:
                # 根據名稱查找分類
                category_obj = await self._repository.get_category_by_name(category)
                if category_obj:
                    category_id = category_obj.id

        return await self.list_achievements(category_id=category_id, active_only=True)

    async def get_root_categories(self) -> list[AchievementCategory]:
        """取得所有根分類.

        Returns:
            根分類列表
        """
        cache_key = self._get_cache_key("root_categories")

        # 檢查快取
        cached_result = self._cache_service.get("category", cache_key)
        if cached_result is not None:
            return cached_result

        try:
            root_categories = await self._repository.get_root_categories()

            # 存入快取
            self._cache_service.set("category", cache_key, root_categories)

            logger.debug(
                "取得根分類列表",
                extra={"count": len(root_categories)},
            )

            return root_categories

        except Exception as e:
            logger.error(
                "取得根分類列表失敗",
                extra={"error": str(e)},
                exc_info=True,
            )
            raise

    async def get_child_categories(self, parent_id: int) -> list[AchievementCategory]:
        """取得子分類.

        Args:
            parent_id: 父分類 ID

        Returns:
            子分類列表
        """
        cache_key = self._get_cache_key("child_categories", parent_id)

        # 檢查快取
        cached_result = self._cache_service.get("category", cache_key)
        if cached_result is not None:
            return cached_result

        try:
            child_categories = await self._repository.get_child_categories(parent_id)

            # 存入快取
            self._cache_service.set("category", cache_key, child_categories)

            logger.debug(
                "取得子分類列表",
                extra={"parent_id": parent_id, "count": len(child_categories)},
            )

            return child_categories

        except Exception as e:
            logger.error(
                "取得子分類列表失敗",
                extra={"parent_id": parent_id, "error": str(e)},
                exc_info=True,
            )
            raise

    async def get_category_tree(self, root_id: int | None = None) -> list[dict[str, Any]]:
        """取得分類樹結構.

        Args:
            root_id: 根分類 ID,None 表示從頂層開始

        Returns:
            包含分類和子分類的樹狀結構列表
        """
        cache_key = self._get_cache_key("category_tree", root_id)

        # 檢查快取
        cached_result = self._cache_service.get("category", cache_key)
        if cached_result is not None:
            return cached_result

        try:
            category_tree = await self._repository.get_category_tree(root_id)

            # 存入快取
            self._cache_service.set("category", cache_key, category_tree)

            logger.debug(
                "取得分類樹結構",
                extra={"root_id": root_id, "tree_size": len(category_tree)},
            )

            return category_tree

        except Exception as e:
            logger.error(
                "取得分類樹結構失敗",
                extra={"root_id": root_id, "error": str(e)},
                exc_info=True,
            )
            raise

    async def get_category_path(self, category_id: int) -> list[AchievementCategory]:
        """取得分類的完整路徑.

        Args:
            category_id: 分類 ID

        Returns:
            分類路徑列表,從根分類到當前分類
        """
        cache_key = self._get_cache_key("category_path", category_id)

        # 檢查快取
        cached_result = self._cache_service.get("category", cache_key)
        if cached_result is not None:
            return cached_result

        try:
            category_path = await self._repository.get_category_path(category_id)

            # 存入快取
            self._cache_service.set("category", cache_key, category_path)

            logger.debug(
                "取得分類路徑",
                extra={"category_id": category_id, "path_length": len(category_path)},
            )

            return category_path

        except Exception as e:
            logger.error(
                "取得分類路徑失敗",
                extra={"category_id": category_id, "error": str(e)},
                exc_info=True,
            )
            raise

    async def toggle_category_expansion(self, category_id: int) -> bool:
        """切換分類的展開狀態.

        Args:
            category_id: 分類 ID

        Returns:
            新的展開狀態
        """
        try:
            # 獲取當前狀態
            category = await self.get_category_by_id(category_id)
            if not category:
                raise ValueError(f"分類 {category_id} 不存在")

            # 切換狀態
            new_state = not category.is_expanded

            # 更新資料庫
            success = await self._repository.update_category_expansion(
                category_id, new_state
            )

            if success:
                # 無效化相關快取
                self._invalidate_cache_by_operation(
                    "toggle_expansion", category_id=category_id
                )

                logger.debug(
                    "分類展開狀態已切換",
                    extra={
                        "category_id": category_id,
                        "old_state": category.is_expanded,
                        "new_state": new_state,
                    },
                )

            return new_state

        except Exception as e:
            logger.error(
                "切換分類展開狀態失敗",
                extra={"category_id": category_id, "error": str(e)},
                exc_info=True,
            )
            raise

    async def get_category_achievement_count(
        self, category_id: int, include_children: bool = True
    ) -> int:
        """取得分類下的成就數量.

        Args:
            category_id: 分類 ID
            include_children: 是否包含子分類的成就

        Returns:
            成就數量
        """
        cache_key = self._get_cache_key(
            "category_achievement_count", category_id, include_children
        )

        # 檢查快取
        cached_result = self._cache_service.get("category", cache_key)
        if cached_result is not None:
            return cached_result

        try:
            if include_children:
                count = await self._repository._get_category_achievement_count(
                    category_id
                )
            else:
                # 只計算直接在此分類下的成就
                achievements = await self.list_achievements(category_id=category_id)
                count = len(achievements)

            # 存入快取
            self._cache_service.set("category", cache_key, count)

            logger.debug(
                "取得分類成就數量",
                extra={
                    "category_id": category_id,
                    "include_children": include_children,
                    "count": count,
                },
            )

            return count

        except Exception as e:
            logger.error(
                "取得分類成就數量失敗",
                extra={
                    "category_id": category_id,
                    "include_children": include_children,
                    "error": str(e),
                },
                exc_info=True,
            )
            raise

    # =============================================================================
    # Achievement 業務邏輯
    # =============================================================================

    async def create_achievement(
        self,
        name: str,
        description: str,
        category_id: int,
        achievement_type: AchievementType,
        criteria: dict[str, Any],
        points: int = 0,
        badge_url: str | None = None,
        role_reward: str | None = None,
        is_hidden: bool = False,
        is_active: bool = True,
    ) -> Achievement:
        """建立新成就.

        Args:
            name: 成就名稱
            description: 成就描述
            category_id: 分類 ID
            achievement_type: 成就類型
            criteria: 成就條件
            points: 成就點數
            badge_url: 徽章圖片 URL
            role_reward: 角色獎勵
            is_hidden: 是否隱藏
            is_active: 是否啟用

        Returns:
            建立後的成就(包含 ID)

        Raises:
            ValueError: 成就資料無效或違反業務規則
        """
        category = await self.get_category_by_id(category_id)
        if not category:
            raise ValueError(f"分類 {category_id} 不存在")

        existing_achievements = await self.list_achievements(category_id=category_id)
        if any(a.name == name for a in existing_achievements):
            raise ValueError(f"分類內成就名稱 '{name}' 已存在")

        achievement = Achievement(
            name=name,
            description=description,
            category_id=category_id,
            achievement_type=achievement_type,
            criteria=criteria,
            points=points,
            badge_url=badge_url,
            role_reward=role_reward,
            is_hidden=is_hidden,
            is_active=is_active,
        )

        try:
            created_achievement = await self._repository.create_achievement(achievement)

            # 無效化相關快取
            self._invalidate_cache_by_operation(
                "create_achievement",
                category_id=created_achievement.category_id,
                achievement_id=created_achievement.id,
            )

            logger.info(
                "成就建立成功",
                extra={
                    "achievement_id": created_achievement.id,
                    "achievement_name": created_achievement.name,
                    "category_id": created_achievement.category_id,
                },
            )

            return created_achievement

        except Exception as e:
            logger.error(
                "成就建立失敗",
                extra={
                    "achievement_name": name,
                    "category_id": category_id,
                    "error": str(e),
                },
                exc_info=True,
            )
            raise

    async def get_achievement_by_id(self, achievement_id: int) -> Achievement | None:
        """根據 ID 取得成就.

        Args:
            achievement_id: 成就 ID

        Returns:
            成就物件或 None
        """
        cache_key = self._get_cache_key("achievement", achievement_id)

        # 檢查快取
        cached_result = self._cache_service.get("achievement", cache_key)
        if cached_result is not None:
            return cached_result

        try:
            achievement = await self._repository.get_achievement_by_id(achievement_id)

            # 存入快取
            if achievement:
                self._cache_service.set("achievement", cache_key, achievement)

            return achievement

        except Exception as e:
            logger.error(
                "取得成就失敗",
                extra={"achievement_id": achievement_id, "error": str(e)},
                exc_info=True,
            )
            raise

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
        cache_key = self._get_cache_key(
            "achievements", category_id, achievement_type, active_only, limit, offset
        )

        # 檢查快取
        cached_result = self._cache_service.get("achievement", cache_key)
        if cached_result is not None:
            return cached_result

        try:
            achievements = await self._repository.list_achievements(
                category_id=category_id,
                achievement_type=achievement_type,
                active_only=active_only,
                limit=limit,
                offset=offset,
            )

            # 存入快取
            self._cache_service.set("achievement", cache_key, achievements)

            logger.debug(
                "取得成就列表",
                extra={
                    "count": len(achievements),
                    "category_id": category_id,
                    "achievement_type": achievement_type.value
                    if achievement_type
                    else None,
                    "active_only": active_only,
                },
            )

            return achievements

        except Exception as e:
            logger.error(
                "取得成就列表失敗",
                extra={
                    "category_id": category_id,
                    "achievement_type": achievement_type.value
                    if achievement_type
                    else None,
                    "active_only": active_only,
                    "error": str(e),
                },
                exc_info=True,
            )
            raise

    async def update_achievement(
        self, achievement_id: int, updates: dict[str, Any]
    ) -> Achievement | None:
        """更新成就.

        Args:
            achievement_id: 成就 ID
            updates: 要更新的欄位字典

        Returns:
            更新後的成就物件或 None(如果成就不存在)

        Raises:
            ValueError: 更新資料無效或違反業務規則
        """
        if not updates:
            raise ValueError("更新資料不能為空")

        if "category_id" in updates:
            category = await self.get_category_by_id(updates["category_id"])
            if not category:
                raise ValueError(f"分類 {updates['category_id']} 不存在")

        try:
            success = await self._repository.update_achievement(achievement_id, updates)
            if not success:
                return None

            # 無效化相關快取
            self._invalidate_cache_by_operation(
                "update_achievement",
                achievement_id=achievement_id,
                category_id=updates.get("category_id"),
            )

            # 取得更新後的成就
            updated_achievement = await self.get_achievement_by_id(achievement_id)

            logger.info(
                "成就更新成功",
                extra={
                    "achievement_id": achievement_id,
                    "updated_fields": list(updates.keys()),
                },
            )

            return updated_achievement

        except Exception as e:
            logger.error(
                "成就更新失敗",
                extra={
                    "achievement_id": achievement_id,
                    "updates": updates,
                    "error": str(e),
                },
                exc_info=True,
            )
            raise

    async def delete_achievement(self, achievement_id: int) -> bool:
        """刪除成就.

        Args:
            achievement_id: 成就 ID

        Returns:
            True 如果刪除成功,否則 False

        Raises:
            ValueError: 有用戶已獲得此成就時不能刪除
        """
        try:
            # 檢查是否有用戶已獲得此成就
            users_with_achievement = await self._repository.get_users_with_achievement(
                achievement_id
            )
            if users_with_achievement:
                raise ValueError(
                    f"無法刪除成就 {achievement_id}:有 {len(users_with_achievement)} 個用戶已獲得此成就."
                    "請先撤銷所有用戶的此成就,或考慮將成就設為不可用而非刪除."
                )
        except AttributeError:
            # 如果 repository 還沒有實作 get_users_with_achievement 方法,記錄警告
            self._logger.warning(
                "Repository 缺少 get_users_with_achievement 方法,跳過用戶成就檢查"
            )
        except Exception as e:
            self._logger.error(f"檢查用戶成就時發生錯誤: {e}")
            # 為了安全起見,如果檢查失敗則阻止刪除
            raise ValueError(f"無法驗證成就是否可以安全刪除: {e}") from e

        try:
            success = await self._repository.delete_achievement(achievement_id)

            if success:
                # 無效化相關快取
                self._invalidate_cache_by_operation(
                    "delete_achievement", achievement_id=achievement_id
                )

                logger.info("成就刪除成功", extra={"achievement_id": achievement_id})

            return success

        except Exception as e:
            logger.error(
                "成就刪除失敗",
                extra={"achievement_id": achievement_id, "error": str(e)},
                exc_info=True,
            )
            raise

    # =============================================================================
    # User Achievement 業務邏輯
    # =============================================================================

    async def award_achievement_to_user(
        self, user_id: int, achievement_id: int
    ) -> UserAchievement:
        """為用戶頒發成就.

        Args:
            user_id: 用戶 ID
            achievement_id: 成就 ID

        Returns:
            用戶成就記錄

        Raises:
            ValueError: 成就不存在或用戶已獲得
        """
        achievement = await self.get_achievement_by_id(achievement_id)
        if not achievement:
            raise ValueError(f"成就 {achievement_id} 不存在")

        if not achievement.is_active:
            raise ValueError(f"成就 {achievement_id} 未啟用")

        try:
            user_achievement = await self._repository.award_achievement(
                user_id, achievement_id
            )

            # 無效化相關快取
            self._invalidate_cache_by_operation(
                "award_achievement", user_id=user_id, achievement_id=achievement_id
            )

            logger.info(
                "用戶成就頒發成功",
                extra={
                    "user_id": user_id,
                    "achievement_id": achievement_id,
                    "achievement_name": achievement.name,
                    "points": achievement.points,
                },
            )

            return user_achievement

        except Exception as e:
            logger.error(
                "用戶成就頒發失敗",
                extra={
                    "user_id": user_id,
                    "achievement_id": achievement_id,
                    "error": str(e),
                },
                exc_info=True,
            )
            raise

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
        cache_key = self._get_cache_key(
            "user_achievements", user_id, category_id, limit
        )

        # 檢查快取
        cached_result = self._cache_service.get("user_achievements", cache_key)
        if cached_result is not None:
            return cached_result

        try:
            user_achievements = await self._repository.get_user_achievements(
                user_id=user_id, category_id=category_id, limit=limit
            )

            # 存入快取
            self._cache_service.set("user_achievements", cache_key, user_achievements)

            logger.debug(
                "取得用戶成就列表",
                extra={
                    "user_id": user_id,
                    "count": len(user_achievements),
                    "category_id": category_id,
                },
            )

            return user_achievements

        except Exception as e:
            logger.error(
                "取得用戶成就列表失敗",
                extra={"user_id": user_id, "category_id": category_id, "error": str(e)},
                exc_info=True,
            )
            raise

    async def get_user_achievement_stats(self, user_id: int) -> dict[str, Any]:
        """取得用戶成就統計.

        Args:
            user_id: 用戶 ID

        Returns:
            包含統計資料的字典
        """
        cache_key = self._get_cache_key("user_stats", user_id)

        # 檢查快取
        cached_result = self._cache_service.get("user_progress", cache_key)
        if cached_result is not None:
            return cached_result

        try:
            stats = await self._repository.get_user_achievement_stats(user_id)

            # 存入快取
            self._cache_service.set("user_progress", cache_key, stats)

            logger.debug(
                "取得用戶成就統計",
                extra={
                    "user_id": user_id,
                    "total_achievements": stats.get("total_achievements", 0),
                    "total_points": stats.get("total_points", 0),
                },
            )

            return stats

        except Exception as e:
            logger.error(
                "取得用戶成就統計失敗",
                extra={"user_id": user_id, "error": str(e)},
                exc_info=True,
            )
            raise

    # =============================================================================
    # 批量操作業務邏輯
    # =============================================================================

    async def batch_create_achievements(
        self, achievements: list[Achievement]
    ) -> list[Achievement]:
        """批量建立成就.

        Args:
            achievements: 成就列表

        Returns:
            建立後的成就列表

        Raises:
            ValueError: 任何成就資料無效
        """
        if not achievements:
            return []

        for achievement in achievements:
            category = await self.get_category_by_id(achievement.category_id)
            if not category:
                raise ValueError(f"分類 {achievement.category_id} 不存在")

        created_achievements = []
        errors = []

        for achievement in achievements:
            try:
                created_achievement = await self.create_achievement(achievement)
                created_achievements.append(created_achievement)
            except Exception as e:
                errors.append(f"建立成就 '{achievement.name}' 失敗: {e!s}")

        if errors:
            logger.warning(
                "批量建立成就部分失敗",
                extra={
                    "total": len(achievements),
                    "success": len(created_achievements),
                    "errors": errors,
                },
            )

        logger.info(
            "批量建立成就完成",
            extra={
                "total": len(achievements),
                "success": len(created_achievements),
                "failed": len(errors),
            },
        )

        return created_achievements

    # =============================================================================
    # 統計和報表業務邏輯
    # =============================================================================

    async def get_global_achievement_stats(self) -> dict[str, Any]:
        """取得全域成就統計.

        Returns:
            包含全域統計的字典
        """
        cache_key = "global_stats"

        # 檢查快取
        cached_result = self._cache_service.get("global_stats", cache_key)
        if cached_result is not None:
            return cached_result

        try:
            stats = await self._repository.get_global_achievement_stats()

            # 存入快取
            self._cache_service.set("global_stats", cache_key, stats)

            logger.debug("取得全域成就統計", extra=stats)

            return stats

        except Exception as e:
            logger.error("取得全域成就統計失敗", extra={"error": str(e)}, exc_info=True)
            raise

    async def get_popular_achievements(
        self, limit: int = 10
    ) -> list[tuple[Achievement, int]]:
        """取得最受歡迎的成就(按獲得人數排序).

        Args:
            limit: 返回的最大數量

        Returns:
            (成就, 獲得人數) 的元組列表
        """
        cache_key = self._get_cache_key("popular_achievements", limit)

        # 檢查快取
        cached_result = self._cache_service.get("leaderboard", cache_key)
        if cached_result is not None:
            return cached_result

        try:
            popular_achievements = await self._repository.get_popular_achievements(
                limit
            )

            # 存入快取
            self._cache_service.set("leaderboard", cache_key, popular_achievements)

            logger.debug(
                "取得熱門成就列表",
                extra={"count": len(popular_achievements), "limit": limit},
            )

            return popular_achievements

        except Exception as e:
            logger.error(
                "取得熱門成就列表失敗",
                extra={"limit": limit, "error": str(e)},
                exc_info=True,
            )
            raise

    # =============================================================================
    # 排行榜業務邏輯
    # =============================================================================

    async def get_leaderboard_by_count(
        self, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        """取得成就總數排行榜.

        Args:
            limit: 最大返回數量
            offset: 跳過的記錄數

        Returns:
            排行榜資料列表,每項包含 user_id, achievement_count, rank
        """
        cache_key = self._get_cache_key("leaderboard_count", limit, offset)

        # 檢查快取
        cached_result = self._cache_service.get("leaderboard", cache_key)
        if cached_result is not None:
            return cached_result

        try:
            leaderboard = await self._repository.get_leaderboard_by_count(limit, offset)

            # 存入快取
            self._cache_service.set("leaderboard", cache_key, leaderboard)

            logger.debug(
                "取得成就總數排行榜",
                extra={"count": len(leaderboard), "limit": limit, "offset": offset},
            )

            return leaderboard

        except Exception as e:
            logger.error(
                "取得成就總數排行榜失敗",
                extra={"limit": limit, "offset": offset, "error": str(e)},
                exc_info=True,
            )
            raise

    async def get_leaderboard_by_points(
        self, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        """取得成就點數排行榜.

        Args:
            limit: 最大返回數量
            offset: 跳過的記錄數

        Returns:
            排行榜資料列表,每項包含 user_id, total_points, rank
        """
        cache_key = self._get_cache_key("leaderboard_points", limit, offset)

        # 檢查快取
        cached_result = self._cache_service.get("leaderboard", cache_key)
        if cached_result is not None:
            return cached_result

        try:
            leaderboard = await self._repository.get_leaderboard_by_points(
                limit, offset
            )

            # 存入快取
            self._cache_service.set("leaderboard", cache_key, leaderboard)

            logger.debug(
                "取得成就點數排行榜",
                extra={"count": len(leaderboard), "limit": limit, "offset": offset},
            )

            return leaderboard

        except Exception as e:
            logger.error(
                "取得成就點數排行榜失敗",
                extra={"limit": limit, "offset": offset, "error": str(e)},
                exc_info=True,
            )
            raise

    async def get_leaderboard_by_category(
        self, category_id: int, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        """取得特定分類的成就排行榜.

        Args:
            category_id: 成就分類 ID
            limit: 最大返回數量
            offset: 跳過的記錄數

        Returns:
            排行榜資料列表,每項包含 user_id, category_achievement_count, rank
        """
        cache_key = self._get_cache_key(
            "leaderboard_category", category_id, limit, offset
        )

        # 檢查快取
        cached_result = self._cache_service.get("leaderboard", cache_key)
        if cached_result is not None:
            return cached_result

        try:
            category = await self.get_category_by_id(category_id)
            if not category:
                raise ValueError(f"分類 {category_id} 不存在")

            leaderboard = await self._repository.get_leaderboard_by_category(
                category_id, limit, offset
            )

            # 存入快取
            self._cache_service.set("leaderboard", cache_key, leaderboard)

            logger.debug(
                "取得分類成就排行榜",
                extra={
                    "category_id": category_id,
                    "count": len(leaderboard),
                    "limit": limit,
                    "offset": offset,
                },
            )

            return leaderboard

        except Exception as e:
            logger.error(
                "取得分類成就排行榜失敗",
                extra={
                    "category_id": category_id,
                    "limit": limit,
                    "offset": offset,
                    "error": str(e),
                },
                exc_info=True,
            )
            raise

    async def get_user_rank(
        self, user_id: int, rank_type: str = "count"
    ) -> dict[str, Any] | None:
        """取得用戶在特定排行榜中的排名.

        Args:
            user_id: 用戶 ID
            rank_type: 排行榜類型 ("count", "points", "category_{id}")

        Returns:
            包含用戶排名資訊的字典或 None
        """
        cache_key = self._get_cache_key("user_rank", user_id, rank_type)

        # 檢查快取
        cached_result = self._cache_service.get("leaderboard", cache_key)
        if cached_result is not None:
            return cached_result

        try:
            user_rank = await self._repository.get_user_rank(user_id, rank_type)

            # 存入快取
            if user_rank:
                self._cache_service.set("leaderboard", cache_key, user_rank)

            logger.debug(
                "取得用戶排名",
                extra={
                    "user_id": user_id,
                    "rank_type": rank_type,
                    "rank": user_rank.get("rank") if user_rank else None,
                },
            )

            return user_rank

        except Exception as e:
            logger.error(
                "取得用戶排名失敗",
                extra={"user_id": user_id, "rank_type": rank_type, "error": str(e)},
                exc_info=True,
            )
            raise

    # =============================================================================
    # 快取管理業務邏輯
    # =============================================================================

    def get_cache_statistics(self) -> dict[str, dict[str, Any]]:
        """取得快取統計資料.

        Returns:
            包含所有快取統計的字典
        """
        return self._cache_service.get_cache_statistics()

    def get_cache_optimization_suggestions(self) -> list[dict[str, Any]]:
        """取得快取優化建議.

        Returns:
            優化建議列表
        """
        return self._cache_service.get_optimization_suggestions()

    def clear_cache(self, cache_type: str | None = None) -> None:
        """清除快取.

        Args:
            cache_type: 要清除的快取類型,None 表示清除所有快取
        """
        if cache_type:
            self._cache_service.clear_cache(cache_type)
            logger.info(f"已清除快取: {cache_type}")
        else:
            self._cache_service.clear_all_caches()
            logger.info("已清除所有快取")

    def update_cache_config(self, cache_type: str, **config_updates) -> bool:
        """動態更新快取配置.

        Args:
            cache_type: 快取類型
            **config_updates: 配置更新項目

        Returns:
            True 如果更新成功
        """
        success = self._cache_service.update_cache_config(cache_type, **config_updates)
        if success:
            logger.info(f"快取配置更新成功: {cache_type}", extra=config_updates)
        return success


__all__ = [
    "AchievementService",
]
