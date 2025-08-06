"""成就管理服務模組.

此模組提供成就系統的管理功能,包含:
- 成就 CRUD 操作
- 批量操作支援
- 資料驗證和完整性檢查
- 依賴關係分析
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from ..constants import (
    ACHIEVEMENT_DESCRIPTION_MAX_LENGTH,
    ACHIEVEMENT_NAME_MAX_LENGTH,
    ACHIEVEMENT_POINTS_MAX,
    ACHIEVEMENT_ROLE_REWARD_MAX_LENGTH,
    CATEGORY_DESCRIPTION_MAX_LENGTH,
    CATEGORY_ICON_MAX_LENGTH,
    CATEGORY_NAME_MAX_LENGTH,
    HOUR_IN_SECONDS,
)
from ..database.models import AchievementCategory
from ..database.query_builder import QueryBuilder

if TYPE_CHECKING:
    from ..database.models import Achievement

logger = logging.getLogger(__name__)


@dataclass
class BulkOperationResult:
    """批量操作結果."""

    success_count: int = 0
    failed_count: int = 0
    errors: list[str] = field(default_factory=list)
    affected_achievements: list[Achievement] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def add_success(self, achievement: Achievement, message: str | None = None):
        """添加成功結果."""
        self.success_count += 1
        self.affected_achievements.append(achievement)
        if message:
            self.details[f"success_{achievement.id}"] = message

    def add_error(self, error_message: str):
        """添加錯誤結果."""
        self.failed_count += 1
        self.errors.append(error_message)

    @property
    def total_count(self) -> int:
        """總處理數量."""
        return self.success_count + self.failed_count

    @property
    def success_rate(self) -> float:
        """成功率."""
        if self.total_count == 0:
            return 0.0
        return (self.success_count / self.total_count) * 100


@dataclass
class ValidationResult:
    """驗證結果."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, error: str):
        """添加錯誤."""
        self.errors.append(error)
        self.is_valid = False

    def add_warning(self, warning: str):
        """添加警告."""
        self.warnings.append(warning)


class AchievementAdminService:
    """成就管理服務.

    提供成就系統的完整管理功能,包括 CRUD 操作、
    批量處理、資料驗證和依賴關係管理.
    """

    def __init__(self, repository, permission_service, cache_service=None):
        """初始化成就管理服務.

        Args:
            repository: 成就資料庫倉庫
            permission_service: 權限檢查服務
            cache_service: 快取服務(可選)
        """
        self.repository = repository
        self.permission_service = permission_service
        self.cache_service = cache_service

    async def create_achievement(
        self, achievement_data: dict[str, Any], admin_user_id: int
    ) -> tuple[Achievement | None, ValidationResult]:
        """創建新成就.

        Args:
            achievement_data: 成就資料
            admin_user_id: 管理員用戶 ID

        Returns:
            (成就物件, 驗證結果) 元組
        """
        try:
            # 資料驗證
            validation = await self._validate_achievement_data(achievement_data)
            if not validation.is_valid:
                return None, validation

            # 檢查名稱唯一性
            name_check = await self._check_name_uniqueness(achievement_data["name"])
            if not name_check.is_valid:
                validation.errors.extend(name_check.errors)
                return None, validation

            # 創建成就
            achievement = await self.repository.create_achievement(achievement_data)

            # 清除相關快取
            await self._invalidate_achievement_cache()

            # 記錄審計日誌
            await self._log_admin_action(
                action="achievement_create",
                user_id=admin_user_id,
                achievement_id=achievement.id,
                details={"name": achievement.name},
            )

            logger.info(f"成就創建成功: {achievement.name} (ID: {achievement.id})")
            return achievement, validation

        except Exception as e:
            logger.error(f"創建成就失敗: {e}")
            validation.add_error(f"創建成就時發生錯誤: {e!s}")
            return None, validation

    async def update_achievement(
        self, achievement_id: int, updates: dict[str, Any], admin_user_id: int
    ) -> tuple[Achievement | None, ValidationResult]:
        """更新成就.

        Args:
            achievement_id: 成就 ID
            updates: 更新資料
            admin_user_id: 管理員用戶 ID

        Returns:
            (更新後成就物件, 驗證結果) 元組
        """
        try:
            # 檢查成就是否存在
            existing = await self.repository.get_achievement_by_id(achievement_id)
            if not existing:
                validation = ValidationResult(is_valid=False)
                validation.add_error(f"成就 {achievement_id} 不存在")
                return None, validation

            # 驗證更新資料
            validation = await self._validate_achievement_updates(
                updates, achievement_id
            )
            if not validation.is_valid:
                return None, validation

            # 執行更新
            achievement = await self.repository.update_achievement(
                achievement_id, updates
            )

            # 清除相關快取
            await self._invalidate_achievement_cache(achievement_id)

            # 記錄審計日誌
            await self._log_admin_action(
                action="achievement_update",
                user_id=admin_user_id,
                achievement_id=achievement_id,
                details={"updates": updates},
            )

            logger.info(f"成就更新成功: {achievement.name} (ID: {achievement_id})")
            return achievement, validation

        except Exception as e:
            logger.error(f"更新成就失敗: {e}")
            validation = ValidationResult(is_valid=False)
            validation.add_error(f"更新成就時發生錯誤: {e!s}")
            return None, validation

    async def delete_achievement(
        self, achievement_id: int, admin_user_id: int, force: bool = False
    ) -> tuple[bool, ValidationResult]:
        """刪除成就.

        Args:
            achievement_id: 成就 ID
            admin_user_id: 管理員用戶 ID
            force: 是否強制刪除(忽略依賴關係)

        Returns:
            (是否成功, 驗證結果) 元組
        """
        try:
            # 檢查成就是否存在
            achievement = await self.repository.get_achievement_by_id(achievement_id)
            if not achievement:
                validation = ValidationResult(is_valid=False)
                validation.add_error(f"成就 {achievement_id} 不存在")
                return False, validation

            # ========== 檢查依賴關係(除非強制刪除) ==========
            validation = ValidationResult(is_valid=True)
            if not force:
                dependency_check = await self._check_achievement_dependencies(
                    achievement_id
                )
                if dependency_check["has_dependencies"]:
                    validation.add_error(
                        f"成就存在依賴關係: {dependency_check['description']}"
                    )
                    return False, validation

            # 執行刪除
            success = await self.repository.delete_achievement(achievement_id)

            if success:
                # 清除相關快取
                await self._invalidate_achievement_cache(achievement_id)

                # 記錄審計日誌
                await self._log_admin_action(
                    action="achievement_delete",
                    user_id=admin_user_id,
                    achievement_id=achievement_id,
                    details={"name": achievement.name, "force": force},
                )

                logger.info(
                    f"成就刪除成功: {achievement.name} (ID: {achievement_id}), 強制: {force}"
                )

            return success, validation

        except Exception as e:
            logger.error(f"刪除成就失敗: {e}")
            validation = ValidationResult(is_valid=False)
            validation.add_error(f"刪除成就時發生錯誤: {e!s}")
            return False, validation

    async def bulk_update_status(
        self, achievement_ids: list[int], is_active: bool, admin_user_id: int
    ) -> BulkOperationResult:
        """批量更新成就狀態.

        Args:
            achievement_ids: 成就 ID 列表
            is_active: 目標狀態
            admin_user_id: 管理員用戶 ID

        Returns:
            批量操作結果
        """
        result = BulkOperationResult()
        action = "啟用" if is_active else "停用"

        try:
            for achievement_id in achievement_ids:
                try:
                    # 獲取成就
                    achievement = await self.repository.get_achievement_by_id(
                        achievement_id
                    )
                    if not achievement:
                        result.add_error(f"成就 {achievement_id} 不存在")
                        continue

                    # 檢查是否需要更新
                    if achievement.is_active == is_active:
                        result.add_success(
                            achievement, f"成就 {achievement.name} 已經是{action}狀態"
                        )
                        continue

                    # 執行狀態更新
                    updated_achievement = await self.repository.update_achievement(
                        achievement_id,
                        {"is_active": is_active, "updated_at": datetime.utcnow()},
                    )

                    result.add_success(
                        updated_achievement,
                        f"成就 {updated_achievement.name} {action}成功",
                    )

                except Exception as e:
                    result.add_error(f"處理成就 {achievement_id} 時發生錯誤: {e!s}")

            # 清除快取
            await self._invalidate_achievement_cache()

            # 記錄審計日誌
            await self._log_admin_action(
                action="bulk_status_update",
                user_id=admin_user_id,
                affected_count=result.success_count,
                details={
                    "is_active": is_active,
                    "achievement_ids": achievement_ids,
                    "result": {
                        "success": result.success_count,
                        "failed": result.failed_count,
                    },
                },
            )

            logger.info(
                f"批量{action}完成: {result.success_count}/{len(achievement_ids)} 成功"
            )

        except Exception as e:
            logger.error(f"批量{action}操作失敗: {e}")
            result.add_error(f"批量操作執行失敗: {e!s}")

        return result

    async def bulk_delete(
        self, achievement_ids: list[int], admin_user_id: int, force: bool = False
    ) -> BulkOperationResult:
        """批量刪除成就.

        Args:
            achievement_ids: 成就 ID 列表
            admin_user_id: 管理員用戶 ID
            force: 是否強制刪除

        Returns:
            批量操作結果
        """
        result = BulkOperationResult()

        try:
            for achievement_id in achievement_ids:
                try:
                    # 獲取成就
                    achievement = await self.repository.get_achievement_by_id(
                        achievement_id
                    )
                    if not achievement:
                        result.add_error(f"成就 {achievement_id} 不存在")
                        continue

                    # Check dependencies unless force delete
                    if not force:
                        dependency_check = await self._check_achievement_dependencies(
                            achievement_id
                        )
                        if dependency_check["has_dependencies"]:
                            result.add_error(
                                f"成就 {achievement.name} 存在依賴關係: {dependency_check['description']}"
                            )
                            continue

                    # 執行刪除
                    success = await self.repository.delete_achievement(achievement_id)

                    if success:
                        result.add_success(
                            achievement, f"成就 {achievement.name} 刪除成功"
                        )
                    else:
                        result.add_error(f"刪除成就 {achievement.name} 失敗")

                except Exception as e:
                    result.add_error(f"處理成就 {achievement_id} 時發生錯誤: {e!s}")

            # 清除快取
            await self._invalidate_achievement_cache()

            # 記錄審計日誌
            await self._log_admin_action(
                action="bulk_delete",
                user_id=admin_user_id,
                affected_count=result.success_count,
                details={
                    "force": force,
                    "achievement_ids": achievement_ids,
                    "result": {
                        "success": result.success_count,
                        "failed": result.failed_count,
                    },
                },
            )

            logger.info(
                f"批量刪除完成: {result.success_count}/{len(achievement_ids)} 成功,強制模式: {force}"
            )

        except Exception as e:
            logger.error(f"批量刪除操作失敗: {e}")
            result.add_error(f"批量刪除執行失敗: {e!s}")

        return result

    async def bulk_update_category(
        self, achievement_ids: list[int], target_category_id: int, admin_user_id: int
    ) -> BulkOperationResult:
        """批量更新成就分類.

        Args:
            achievement_ids: 成就 ID 列表
            target_category_id: 目標分類 ID
            admin_user_id: 管理員用戶 ID

        Returns:
            批量操作結果
        """
        result = BulkOperationResult()
        result.details["operation_type"] = "batch_category_change"
        result.details["target_category_id"] = target_category_id

        try:
            # 驗證目標分類存在
            target_category = await self._get_achievement_category(target_category_id)
            if not target_category:
                result.add_error(f"目標分類 {target_category_id} 不存在")
                return result

            result.details["target_category_name"] = target_category.name

            for achievement_id in achievement_ids:
                try:
                    # 獲取成就
                    achievement = await self.repository.get_achievement_by_id(
                        achievement_id
                    )
                    if not achievement:
                        result.add_error(f"成就 {achievement_id} 不存在")
                        continue

                    # 檢查是否需要更新
                    if achievement.category_id == target_category_id:
                        result.add_success(
                            achievement,
                            f"成就「{achievement.name}」已在目標分類中,無需變更",
                        )
                        continue

                    # 記錄原分類
                    original_category = await self._get_achievement_category(
                        achievement.category_id
                    )
                    original_category_name = (
                        original_category.name if original_category else "未知分類"
                    )

                    # 更新分類
                    update_data = {"category_id": target_category_id}
                    updated_achievement = await self.repository.update_achievement(
                        achievement_id, update_data
                    )

                    if updated_achievement:
                        result.add_success(
                            updated_achievement,
                            f"成就「{achievement.name}」從「{original_category_name}」移動到「{target_category.name}」",
                        )

                        # 記錄操作詳情
                        result.details[f"change_{achievement_id}"] = {
                            "original_category_id": achievement.category_id,
                            "original_category_name": original_category_name,
                            "target_category_id": target_category_id,
                            "target_category_name": target_category.name,
                        }
                    else:
                        result.add_error(f"更新成就 {achievement_id} 分類失敗")

                except Exception as e:
                    logger.error(f"更新成就 {achievement_id} 分類失敗: {e}")
                    result.add_error(f"成就 {achievement_id}: {e!s}")

            # 記錄審計日誌
            await self._log_admin_action(
                "bulk_category_change",
                admin_user_id,
                affected_count=result.success_count,
                details={
                    "target_category_id": target_category_id,
                    "target_category_name": target_category.name,
                    "achievement_ids": achievement_ids,
                    "success_count": result.success_count,
                    "failed_count": result.failed_count,
                },
            )

            # 清除相關快取
            await self._invalidate_achievement_cache()

            logger.info(
                f"批量分類變更完成 - 成功: {result.success_count}, 失敗: {result.failed_count}"
            )

        except Exception as e:
            logger.error(f"批量分類變更操作失敗: {e}")
            result.add_error(f"批量分類變更執行失敗: {e!s}")

        return result

    async def get_achievement_with_details(
        self, achievement_id: int
    ) -> dict[str, Any] | None:
        """獲取成就詳細資訊.

        Args:
            achievement_id: 成就 ID

        Returns:
            包含成就和統計資訊的字典
        """
        try:
            achievement = await self.repository.get_achievement_by_id(achievement_id)
            if not achievement:
                return None

            # 獲取統計資訊
            statistics = await self._get_achievement_statistics(achievement_id)

            # 獲取分類資訊
            category = await self._get_achievement_category(achievement.category_id)

            return {
                "achievement": achievement,
                "statistics": statistics,
                "category": category,
            }

        except Exception as e:
            logger.error(f"獲取成就詳細資訊失敗: {e}")
            return None

    async def _validate_achievement_data(
        self, data: dict[str, Any]
    ) -> ValidationResult:
        """驗證成就資料."""
        validation = ValidationResult(is_valid=True)

        # 名稱驗證
        name = data.get("name", "").strip()
        if not name:
            validation.add_error("成就名稱不能為空")
        elif len(name) > ACHIEVEMENT_NAME_MAX_LENGTH:
            validation.add_error(f"成就名稱不能超過 {ACHIEVEMENT_NAME_MAX_LENGTH} 字元")

        # 描述驗證
        description = data.get("description", "").strip()
        if not description:
            validation.add_error("成就描述不能為空")
        elif len(description) > ACHIEVEMENT_DESCRIPTION_MAX_LENGTH:
            validation.add_error(
                f"成就描述不能超過 {ACHIEVEMENT_DESCRIPTION_MAX_LENGTH} 字元"
            )

        # 點數驗證
        points = data.get("points")
        if points is None:
            validation.add_error("成就點數不能為空")
        elif (
            not isinstance(points, int) or points < 0 or points > ACHIEVEMENT_POINTS_MAX
        ):
            validation.add_error(f"成就點數必須為 0-{ACHIEVEMENT_POINTS_MAX} 的整數")

        # 類型驗證
        achievement_type = data.get("type")
        valid_types = ["counter", "milestone", "time_based", "conditional"]
        if not achievement_type:
            validation.add_error("成就類型不能為空")
        elif achievement_type not in valid_types:
            validation.add_error(f"無效的成就類型,有效值: {', '.join(valid_types)}")

        # 分類驗證
        category_id = data.get("category_id")
        if category_id is None:
            validation.add_error("成就分類不能為空")

        # 條件驗證
        criteria = data.get("criteria")
        if criteria is not None and not isinstance(criteria, dict):
            validation.add_error("成就條件必須為字典格式")

        # 徽章 URL 驗證(可選)
        badge_url = data.get("badge_url")
        if (
            badge_url is not None
            and badge_url.strip()
            and not badge_url.startswith(("http://", "https://"))
        ):
            validation.add_error("徽章 URL 格式無效")

        # ========== 獎勵身分組驗證(可選) ==========
        role_reward = data.get("role_reward")
        if role_reward is not None:
            if not isinstance(role_reward, str):
                validation.add_error("獎勵身分組必須為字串格式")
            elif len(role_reward.strip()) > ACHIEVEMENT_ROLE_REWARD_MAX_LENGTH:
                validation.add_error(
                    f"獎勵身分組名稱不能超過 {ACHIEVEMENT_ROLE_REWARD_MAX_LENGTH} 字元"
                )

        # ========== 隱藏成就驗證(可選) ==========
        is_hidden = data.get("is_hidden")
        if is_hidden is not None and not isinstance(is_hidden, bool):
            validation.add_error("隱藏成就設定必須為布林值")

        return validation

    async def _validate_achievement_updates(
        self, updates: dict[str, Any], achievement_id: int
    ) -> ValidationResult:
        """驗證成就更新資料."""
        validation = ValidationResult(is_valid=True)

        # 如果更新名稱,檢查唯一性
        if "name" in updates:
            name_check = await self._check_name_uniqueness(
                updates["name"], achievement_id
            )
            if not name_check.is_valid:
                validation.errors.extend(name_check.errors)

        # 對更新資料執行基本驗證
        await self._validate_achievement_data(updates)

        # 只檢查實際存在的欄位
        for field_name, value in updates.items():
            if field_name in [
                "name",
                "description",
                "points",
                "type",
                "badge_url",
                "role_reward",
                "is_hidden",
            ]:
                # 重用現有驗證邏輯
                temp_data = {field_name: value}
                field_validation = await self._validate_achievement_data(temp_data)
                if not field_validation.is_valid:
                    validation.errors.extend(field_validation.errors)

        return validation

    async def _check_name_uniqueness(
        self, name: str, exclude_id: int | None = None
    ) -> ValidationResult:
        """檢查成就名稱唯一性."""
        validation = ValidationResult(is_valid=True)

        try:
            existing = await self.repository.get_achievement_by_name(name)
            if existing and (exclude_id is None or existing.id != exclude_id):
                validation.add_error(f"成就名稱「{name}」已存在")
        except Exception as e:
            logger.error(f"檢查名稱唯一性失敗: {e}")
            validation.add_error("檢查名稱唯一性時發生錯誤")

        return validation

    async def _check_achievement_dependencies(
        self, achievement_id: int
    ) -> dict[str, Any]:
        """檢查成就依賴關係."""
        try:
            # 這裡應該檢查實際的用戶成就記錄
            # 暫時使用模擬數據
            user_count = await self._get_user_achievement_count(achievement_id)

            return {
                "has_dependencies": user_count > 0,
                "user_achievement_count": user_count,
                "description": f"{user_count} 個用戶已獲得此成就"
                if user_count > 0
                else "無依賴關係",
            }
        except Exception as e:
            logger.error(f"檢查成就依賴關係失敗: {e}")
            return {
                "has_dependencies": True,
                "user_achievement_count": -1,
                "description": "檢查依賴關係時發生錯誤",
            }

    async def _get_user_achievement_count(self, achievement_id: int) -> int:
        """獲取獲得此成就的用戶數量."""
        try:
            query = (
                QueryBuilder("user_achievements")
                .count()
                .where("achievement_id", "=", achievement_id)
            )
            sql, params = query.to_select_sql()

            row = await self.repository.execute_query(sql, params, fetch_one=True)
            return row[0] if row else 0
        except Exception as e:
            logger.error(f"獲取用戶成就數量失敗: {e}")
            return -1

    async def _get_achievement_statistics(self, achievement_id: int) -> dict[str, Any]:
        """獲取成就統計資訊."""
        try:
            # 獲得此成就的用戶數量
            earned_count_query = (
                QueryBuilder("user_achievements")
                .count()
                .where("achievement_id", "=", achievement_id)
            )
            earned_sql, earned_params = earned_count_query.to_select_sql()
            earned_row = await self.repository.execute_query(
                earned_sql, earned_params, fetch_one=True
            )
            earned_count = earned_row[0] if earned_row else 0

            # 獲取總用戶數來計算完成率
            total_users_query = QueryBuilder("user_achievements").select(
                "COUNT(DISTINCT user_id) as count"
            )
            total_sql, total_params = total_users_query.to_select_sql()
            total_row = await self.repository.execute_query(
                total_sql, total_params, fetch_one=True
            )
            total_users = total_row[0] if total_row else 1

            completion_rate = (
                (earned_count / total_users * 100) if total_users > 0 else 0.0
            )

            # 獲取本月獲得數量
            month_start = datetime.now().replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            monthly_query = (
                QueryBuilder("user_achievements")
                .count()
                .where("achievement_id", "=", achievement_id)
                .where("earned_at", ">=", month_start)
            )
            monthly_sql, monthly_params = monthly_query.to_select_sql()
            monthly_row = await self.repository.execute_query(
                monthly_sql, monthly_params, fetch_one=True
            )
            monthly_earned = monthly_row[0] if monthly_row else 0

            # Get achievement ranking by earned count
            rank_query = (
                QueryBuilder("user_achievements", "ua")
                .select("a.id", "COUNT(ua.id) as count")
                .inner_join("achievements a", "a.id = ua.achievement_id")
                .group_by("a.id")
                .order_by("count", "DESC")
            )
            rank_sql, rank_params = rank_query.to_select_sql()
            rank_rows = await self.repository.execute_query(
                rank_sql, rank_params, fetch_all=True
            )

            popular_rank = 1
            for i, row in enumerate(rank_rows or [], 1):
                if row[0] == achievement_id:
                    popular_rank = i
                    break

            return {
                "earned_count": earned_count,
                "completion_rate": round(completion_rate, 1),
                "average_completion_time": "即時" if earned_count > 0 else "未知",
                "popular_rank": popular_rank,
                "monthly_earned": monthly_earned,
                "trend": "穩定" if monthly_earned > 0 else "無活動",
            }
        except Exception as e:
            logger.error(f"獲取成就統計失敗: {e}")
            return {
                "earned_count": 0,
                "completion_rate": 0.0,
                "average_completion_time": "未知",
                "popular_rank": 0,
                "monthly_earned": 0,
                "trend": "無數據",
            }

    async def _get_achievement_category(self, category_id: int):
        """獲取成就分類資訊."""
        try:
            # 使用 repository 的真實查詢方法
            return await self.repository.get_category_by_id(category_id)
        except Exception as e:
            logger.error(f"獲取成就分類失敗: {e}")
            return None

    async def _invalidate_achievement_cache(self, achievement_id: int | None = None):
        """清除成就快取."""
        if self.cache_service:
            try:
                if achievement_id:
                    # 清除特定成就的快取
                    await self.cache_service.delete(
                        f"achievement:detail:{achievement_id}"
                    )

                # 清除列表快取
                await self.cache_service.delete_pattern("achievements:list:*")
                await self.cache_service.delete_pattern("achievements:count:*")

                logger.debug(f"已清除成就快取,ID: {achievement_id or '全部'}")
            except Exception as e:
                logger.error(f"清除快取失敗: {e}")

    # === 分類管理功能 ===

    async def create_category(
        self, category_data: dict[str, Any], admin_user_id: int
    ) -> tuple[Any | None, ValidationResult]:
        """創建新成就分類.

        Args:
            category_data: 分類資料
            admin_user_id: 管理員用戶 ID

        Returns:
            (分類物件, 驗證結果) 元組
        """
        try:
            # 資料驗證
            validation = await self._validate_category_data(category_data)
            if not validation.is_valid:
                return None, validation

            # 檢查名稱唯一性
            name_check = await self._check_category_name_uniqueness(
                category_data["name"]
            )
            if not name_check.is_valid:
                validation.errors.extend(name_check.errors)
                return None, validation

            # 創建分類
            category = await self._create_category_in_db(category_data)

            # 清除相關快取
            await self._invalidate_category_cache()

            # 記錄審計日誌
            await self._log_admin_action(
                action="category_create",
                user_id=admin_user_id,
                details={
                    "name": category.name,
                    "display_order": category.display_order,
                },
            )

            logger.info(f"分類創建成功: {category.name} (ID: {category.id})")
            return category, validation

        except Exception as e:
            logger.error(f"創建分類失敗: {e}")
            validation = ValidationResult(is_valid=False)
            validation.add_error(f"創建分類時發生錯誤: {e!s}")
            return None, validation

    async def update_category(
        self, category_id: int, updates: dict[str, Any], admin_user_id: int
    ) -> tuple[Any | None, ValidationResult]:
        """更新成就分類.

        Args:
            category_id: 分類 ID
            updates: 更新資料
            admin_user_id: 管理員用戶 ID

        Returns:
            (更新後分類物件, 驗證結果) 元組
        """
        try:
            # 檢查分類是否存在
            existing = await self._get_achievement_category(category_id)
            if not existing:
                validation = ValidationResult(is_valid=False)
                validation.add_error(f"分類 {category_id} 不存在")
                return None, validation

            # 驗證更新資料
            validation = await self._validate_category_updates(updates, category_id)
            if not validation.is_valid:
                return None, validation

            # 執行更新
            category = await self._update_category_in_db(category_id, updates)

            # 清除相關快取
            await self._invalidate_category_cache()

            # 記錄審計日誌
            await self._log_admin_action(
                action="category_update",
                user_id=admin_user_id,
                details={"category_id": category_id, "updates": updates},
            )

            logger.info(f"分類更新成功: {category.name} (ID: {category_id})")
            return category, validation

        except Exception as e:
            logger.error(f"更新分類失敗: {e}")
            validation = ValidationResult(is_valid=False)
            validation.add_error(f"更新分類時發生錯誤: {e!s}")
            return None, validation

    async def delete_category(
        self,
        category_id: int,
        admin_user_id: int,
        target_category_id: int | None = None,
    ) -> tuple[bool, ValidationResult]:
        """刪除成就分類.

        Args:
            category_id: 要刪除的分類 ID
            admin_user_id: 管理員用戶 ID
            target_category_id: 成就重新分配的目標分類 ID(可選)

        Returns:
            (是否成功, 驗證結果) 元組
        """
        try:
            # 檢查分類是否存在
            category = await self._get_achievement_category(category_id)
            if not category:
                validation = ValidationResult(is_valid=False)
                validation.add_error(f"分類 {category_id} 不存在")
                return False, validation

            # 檢查分類使用情況
            usage_info = await self._check_category_usage(category_id)
            validation = ValidationResult(is_valid=True)

            # 如果分類有成就,需要重新分配
            if usage_info["has_achievements"]:
                if target_category_id is None:
                    validation.add_error(
                        f"分類中有 {usage_info['achievement_count']} 個成就,需要指定重新分配的目標分類"
                    )
                    return False, validation

                # 驗證目標分類存在
                target_category = await self._get_achievement_category(
                    target_category_id
                )
                if not target_category:
                    validation.add_error(f"目標分類 {target_category_id} 不存在")
                    return False, validation

                # 重新分配成就
                reassign_result = await self._reassign_category_achievements(
                    category_id, target_category_id
                )
                if not reassign_result["success"]:
                    validation.add_error(
                        f"重新分配成就失敗: {reassign_result['error']}"
                    )
                    return False, validation

                logger.info(
                    f"成功重新分配 {reassign_result['count']} 個成就到分類 {target_category_id}"
                )

            # 執行刪除
            success = await self._delete_category_from_db(category_id)

            if success:
                # 清除相關快取
                await self._invalidate_category_cache()
                await self._invalidate_achievement_cache()

                # 記錄審計日誌
                await self._log_admin_action(
                    action="category_delete",
                    user_id=admin_user_id,
                    details={
                        "category_name": category.name,
                        "achievement_count": usage_info["achievement_count"],
                        "target_category_id": target_category_id,
                    },
                )

                logger.info(f"分類刪除成功: {category.name} (ID: {category_id})")

            return success, validation

        except Exception as e:
            logger.error(f"刪除分類失敗: {e}")
            validation = ValidationResult(is_valid=False)
            validation.add_error(f"刪除分類時發生錯誤: {e!s}")
            return False, validation

    async def get_all_categories(self, include_stats: bool = False) -> list[Any]:
        """獲取所有成就分類.

        Args:
            include_stats: 是否包含統計資訊

        Returns:
            分類列表
        """
        try:
            categories = await self._get_all_categories_from_db()

            if include_stats:
                for category in categories:
                    stats = await self._get_category_statistics(category.id)
                    category.stats = stats

            return categories

        except Exception as e:
            logger.error(f"獲取分類列表失敗: {e}")
            return []

    async def get_category_with_details(
        self, category_id: int
    ) -> dict[str, Any] | None:
        """獲取分類詳細資訊.

        Args:
            category_id: 分類 ID

        Returns:
            包含分類和統計資訊的字典
        """
        try:
            category = await self._get_achievement_category(category_id)
            if not category:
                return None

            # 獲取統計資訊
            statistics = await self._get_category_statistics(category_id)
            usage_info = await self._check_category_usage(category_id)

            return {
                "category": category,
                "statistics": statistics,
                "usage_info": usage_info,
            }

        except Exception as e:
            logger.error(f"獲取分類詳細資訊失敗: {e}")
            return None

    async def reorder_categories(
        self, category_orders: list[dict[str, int]], admin_user_id: int
    ) -> BulkOperationResult:
        """重新排序分類.

        Args:
            category_orders: 分類順序列表 [{"id": int, "display_order": int}, ...]
            admin_user_id: 管理員用戶 ID

        Returns:
            批量操作結果
        """
        result = BulkOperationResult()
        result.details["operation_type"] = "category_reorder"

        try:
            for order_data in category_orders:
                try:
                    category_id = order_data["id"]
                    new_order = order_data["display_order"]

                    # 檢查分類是否存在
                    category = await self._get_achievement_category(category_id)
                    if not category:
                        result.add_error(f"分類 {category_id} 不存在")
                        continue

                    # 如果順序沒有變化,跳過
                    if category.display_order == new_order:
                        result.add_success(
                            category, f"分類「{category.name}」順序無變化"
                        )
                        continue

                    # 更新順序
                    updated_category = await self._update_category_in_db(
                        category_id, {"display_order": new_order}
                    )

                    if updated_category:
                        result.add_success(
                            updated_category,
                            f"分類「{category.name}」順序從 {category.display_order} 更新為 {new_order}",
                        )
                    else:
                        result.add_error(f"更新分類 {category_id} 順序失敗")

                except Exception as e:
                    result.add_error(f"處理分類排序失敗: {e!s}")

            # 清除快取
            await self._invalidate_category_cache()

            # 記錄審計日誌
            await self._log_admin_action(
                action="category_reorder",
                user_id=admin_user_id,
                affected_count=result.success_count,
                details={
                    "reorder_data": category_orders,
                    "success_count": result.success_count,
                    "failed_count": result.failed_count,
                },
            )

            logger.info(
                f"分類重排序完成: {result.success_count}/{len(category_orders)} 成功"
            )

        except Exception as e:
            logger.error(f"分類重排序操作失敗: {e}")
            result.add_error(f"分類重排序執行失敗: {e!s}")

        return result

    # === 分類管理內部方法 ===

    async def _validate_category_data(self, data: dict[str, Any]) -> ValidationResult:
        """驗證分類資料."""
        validation = ValidationResult(is_valid=True)

        # 名稱驗證
        name = data.get("name", "").strip()
        if not name:
            validation.add_error("分類名稱不能為空")
        elif len(name) > CATEGORY_NAME_MAX_LENGTH:
            validation.add_error(f"分類名稱不能超過 {CATEGORY_NAME_MAX_LENGTH} 字元")

        # 描述驗證
        description = data.get("description", "").strip()
        if not description:
            validation.add_error("分類描述不能為空")
        elif len(description) > CATEGORY_DESCRIPTION_MAX_LENGTH:
            validation.add_error(
                f"分類描述不能超過 {CATEGORY_DESCRIPTION_MAX_LENGTH} 字元"
            )

        # 顯示順序驗證
        display_order = data.get("display_order")
        if display_order is not None and (
            not isinstance(display_order, int) or display_order < 0
        ):
            validation.add_error("顯示順序必須為非負整數")

        # Validate icon emoji if provided
        icon_emoji = data.get("icon_emoji")
        if icon_emoji is not None and len(icon_emoji) > CATEGORY_ICON_MAX_LENGTH:
            validation.add_error(f"圖示長度不能超過 {CATEGORY_ICON_MAX_LENGTH} 字元")

        return validation

    async def _validate_category_updates(
        self, updates: dict[str, Any], category_id: int
    ) -> ValidationResult:
        """驗證分類更新資料."""
        validation = ValidationResult(is_valid=True)

        # 如果更新名稱,檢查唯一性
        if "name" in updates:
            name_check = await self._check_category_name_uniqueness(
                updates["name"], category_id
            )
            if not name_check.is_valid:
                validation.errors.extend(name_check.errors)

        # 對更新資料執行基本驗證
        for field_name, value in updates.items():
            if field_name in ["name", "description", "display_order", "icon_emoji"]:
                temp_data = {field_name: value}
                field_validation = await self._validate_category_data(temp_data)
                if not field_validation.is_valid:
                    validation.errors.extend(field_validation.errors)

        return validation

    async def _check_category_name_uniqueness(
        self, name: str, exclude_id: int | None = None
    ) -> ValidationResult:
        """檢查分類名稱唯一性."""
        validation = ValidationResult(is_valid=True)

        try:
            existing = await self._get_category_by_name(name)
            if existing and (exclude_id is None or existing.id != exclude_id):
                validation.add_error(f"分類名稱「{name}」已存在")
        except Exception as e:
            logger.error(f"檢查分類名稱唯一性失敗: {e}")
            validation.add_error("檢查名稱唯一性時發生錯誤")

        return validation

    async def _check_category_usage(self, category_id: int) -> dict[str, Any]:
        """檢查分類使用情況."""
        try:
            # 獲取該分類下的成就數量
            achievement_count = await self._get_category_achievement_count(category_id)

            return {
                "has_achievements": achievement_count > 0,
                "achievement_count": achievement_count,
                "description": f"分類中有 {achievement_count} 個成就"
                if achievement_count > 0
                else "分類為空",
            }
        except Exception as e:
            logger.error(f"檢查分類使用情況失敗: {e}")
            return {
                "has_achievements": False,
                "achievement_count": 0,
                "description": "無法確定使用情況",
            }

    async def _get_category_statistics(self, category_id: int) -> dict[str, Any]:
        """獲取分類統計資訊."""
        try:
            # 獲取分類下的成就數量
            achievement_count = await self._get_category_achievement_count(category_id)

            # 獲取活躍成就數量
            active_query = (
                QueryBuilder("achievements")
                .count()
                .where("category_id", "=", category_id)
                .where("is_active", "=", True)
            )
            active_sql, active_params = active_query.to_select_sql()
            active_row = await self.repository.execute_query(
                active_sql, active_params, fetch_one=True
            )
            active_achievements = active_row[0] if active_row else 0

            # 獲取用戶進度數量
            progress_query = (
                QueryBuilder("achievement_progress", "ap")
                .select("COUNT(DISTINCT ap.user_id) as count")
                .inner_join("achievements a", "a.id = ap.achievement_id")
                .where("a.category_id", "=", category_id)
            )
            progress_sql, progress_params = progress_query.to_select_sql()
            progress_row = await self.repository.execute_query(
                progress_sql, progress_params, fetch_one=True
            )
            user_progress_count = progress_row[0] if progress_row else 0

            # 計算完成率
            if user_progress_count > 0:
                completed_query = (
                    QueryBuilder("achievement_progress", "ap")
                    .select("COUNT(*) as count")
                    .inner_join("achievements a", "a.id = ap.achievement_id")
                    .where("a.category_id", "=", category_id)
                    .where("ap.current_value", ">=", "ap.target_value")
                )
                completed_sql, completed_params = completed_query.to_select_sql()
                completed_row = await self.repository.execute_query(
                    completed_sql, completed_params, fetch_one=True
                )
                completed_count = completed_row[0] if completed_row else 0
                completion_rate = (
                    (completed_count / user_progress_count * 100)
                    if user_progress_count > 0
                    else 0.0
                )
            else:
                completion_rate = 0.0

            # 獲取本月創建的成就數量
            month_start = datetime.now().replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )
            monthly_query = (
                QueryBuilder("achievements")
                .count()
                .where("category_id", "=", category_id)
                .where("created_at", ">=", month_start)
            )
            monthly_sql, monthly_params = monthly_query.to_select_sql()
            monthly_row = await self.repository.execute_query(
                monthly_sql, monthly_params, fetch_one=True
            )
            created_achievements_this_month = monthly_row[0] if monthly_row else 0

            # 獲取最後活動時間
            last_activity_query = (
                QueryBuilder("user_achievements", "ua")
                .select("MAX(ua.earned_at) as last_activity")
                .inner_join("achievements a", "a.id = ua.achievement_id")
                .where("a.category_id", "=", category_id)
            )
            last_activity_sql, last_activity_params = (
                last_activity_query.to_select_sql()
            )
            last_activity_row = await self.repository.execute_query(
                last_activity_sql, last_activity_params, fetch_one=True
            )

            last_activity = "無活動"
            if last_activity_row and last_activity_row[0]:
                last_time = last_activity_row[0]
                if isinstance(last_time, str):
                    last_time = datetime.fromisoformat(last_time.replace("Z", "+00:00"))
                time_diff = datetime.now() - last_time.replace(tzinfo=None)

                if time_diff.days > 0:
                    last_activity = f"{time_diff.days} 天前"
                elif time_diff.seconds > HOUR_IN_SECONDS:
                    hours = time_diff.seconds // HOUR_IN_SECONDS
                    last_activity = f"{hours} 小時前"
                else:
                    minutes = time_diff.seconds // 60
                    last_activity = f"{minutes} 分鐘前"

            return {
                "achievement_count": achievement_count,
                "active_achievements": active_achievements,
                "inactive_achievements": achievement_count - active_achievements,
                "user_progress_count": user_progress_count,
                "completion_rate": round(completion_rate, 1),
                "created_achievements_this_month": created_achievements_this_month,
                "last_activity": last_activity,
            }
        except Exception as e:
            logger.error(f"獲取分類統計失敗: {e}")
            return {
                "achievement_count": 0,
                "active_achievements": 0,
                "inactive_achievements": 0,
                "user_progress_count": 0,
                "completion_rate": 0.0,
                "created_achievements_this_month": 0,
                "last_activity": "無數據",
            }

    async def _get_category_achievement_count(self, category_id: int) -> int:
        """獲取分類下的成就數量."""
        try:
            query = (
                QueryBuilder("achievements")
                .count()
                .where("category_id", "=", category_id)
            )
            sql, params = query.to_select_sql()

            row = await self.repository.execute_query(sql, params, fetch_one=True)
            return row[0] if row else 0
        except Exception as e:
            logger.error(f"獲取分類成就數量失敗: {e}")
            return 0

    async def _reassign_category_achievements(
        self, source_category_id: int, target_category_id: int
    ) -> dict[str, Any]:
        """重新分配分類中的成就."""
        try:
            # 1. 獲取需要重新分配的成就數量
            achievement_count = await self._get_category_achievement_count(
                source_category_id
            )

            if achievement_count == 0:
                # 沒有成就需要重新分配
                return {"success": True, "count": 0, "error": None}

            # 2. 獲取該分類下的所有成就 ID
            # 實際實作中應該查詢資料庫,這裡使用模擬邏輯
            achievement_ids = await self._get_category_achievement_ids(
                source_category_id
            )

            if not achievement_ids:
                logger.warning(f"分類 {source_category_id} 下沒有找到成就")
                return {"success": True, "count": 0, "error": None}

            # 3. 使用批量更新功能重新分配成就
            admin_user_id = 0  # 系統操作,使用特殊 ID
            result = await self.bulk_update_category(
                achievement_ids, target_category_id, admin_user_id
            )

            # 4. 記錄操作詳情
            success_count = result.success_count
            failed_count = result.failed_count

            logger.info(
                f"成就重新分配完成: 成功 {success_count}, 失敗 {failed_count}, "
                f"從分類 {source_category_id} 到 {target_category_id}"
            )

            return {
                "success": success_count > 0,
                "count": success_count,
                "failed_count": failed_count,
                "error": None if success_count > 0 else "沒有成就成功重新分配",
            }

        except Exception as e:
            logger.error(f"重新分配成就失敗: {e}")
            return {"success": False, "count": 0, "error": str(e)}

    async def _get_category_achievement_ids(self, category_id: int) -> list[int]:
        """獲取分類下的所有成就 ID."""
        try:
            query = (
                QueryBuilder("achievements")
                .select("id")
                .where("category_id", "=", category_id)
            )
            sql, params = query.to_select_sql()

            rows = await self.repository.execute_query(sql, params, fetch_all=True)
            return [row[0] for row in rows] if rows else []
        except Exception as e:
            logger.error(f"獲取分類成就 ID 失敗: {e}")
            return []

    # === 分類資料庫操作方法 ===

    async def _create_category_in_db(self, category_data: dict[str, Any]):
        """在資料庫中創建分類."""
        try:
            category = AchievementCategory(
                name=category_data["name"],
                description=category_data["description"],
                display_order=category_data.get("display_order", 0),
                icon_emoji=category_data.get("icon_emoji"),
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

            return await self.repository.create_category(category)
        except Exception as e:
            logger.error(f"創建分類失敗: {e}")
            raise

    async def _update_category_in_db(self, category_id: int, updates: dict[str, Any]):
        """在資料庫中更新分類."""
        try:
            # 使用 repository 的真實更新方法
            return await self.repository.update_category(category_id, updates)
        except Exception as e:
            logger.error(f"更新分類失敗: {e}")
            return None

    async def _delete_category_from_db(self, category_id: int) -> bool:
        """從資料庫中刪除分類."""
        try:
            # 使用 repository 的真實刪除方法
            return await self.repository.delete_category(category_id)
        except Exception as e:
            logger.error(f"刪除分類失敗: {e}")
            return False

    async def _get_all_categories_from_db(self):
        """從資料庫獲取所有分類."""
        try:
            # 使用 repository 的真實查詢方法
            return await self.repository.list_categories(active_only=False)
        except Exception as e:
            logger.error(f"獲取分類列表失敗: {e}")
            return []

    async def _get_category_by_name(self, name: str):
        """根據名稱獲取分類."""
        try:
            # 使用 repository 的真實查詢方法
            return await self.repository.get_category_by_name(name)
        except Exception as e:
            logger.error(f"根據名稱獲取分類失敗: {e}")
            return None

    async def _log_admin_action(
        self,
        action: str,
        user_id: int,
        achievement_id: int | None = None,
        affected_count: int | None = None,
        details: dict | None = None,
    ):
        """記錄管理操作審計日誌."""
        try:
            log_data = {
                "action": action,
                "user_id": user_id,
                "achievement_id": achievement_id,
                "affected_count": affected_count or 1,
                "details": details or {},
                "timestamp": datetime.utcnow(),
                "ip_address": None,  # 如果有的話可以從 request 獲取
            }

            # 這裡應該將日誌保存到審計日誌表
            logger.info(f"管理操作審計: {action} by {user_id}", extra=log_data)

        except Exception as e:
            logger.error(f"記錄審計日誌失敗: {e}")
