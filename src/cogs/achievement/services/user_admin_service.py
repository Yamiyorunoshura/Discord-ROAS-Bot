"""用戶成就管理服務.

此模組提供用戶成就管理的核心業務邏輯:
- 用戶搜尋和選擇
- 手動成就授予和撤銷
- 成就進度調整
- 用戶資料重置
- 批量用戶操作
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from ..database.models import AchievementProgress, UserAchievement

if TYPE_CHECKING:
    import discord
    from discord.ext import commands

    from ..database.repository import AchievementRepository
    from .admin_permission_service import AdminPermissionService
    from .audit_logger import AuditLogger
    from .cache_service import AchievementCacheService

logger = logging.getLogger(__name__)

# 常數定義
MAX_BATCH_USERS = 50  # 批量操作最大用戶數量


class UserSearchService:
    """用戶搜尋服務."""

    def __init__(self, bot: commands.Bot):
        """初始化用戶搜尋服務.

        Args:
            bot: Discord 機器人實例
        """
        self.bot = bot

    async def search_users(
        self, query: str, guild_id: int, limit: int = 10
    ) -> list[dict[str, Any]]:
        """搜尋用戶,支援多種搜尋方式.

        Args:
            query: 搜尋查詢(用戶 ID、用戶名、顯示名稱、暱稱)
            guild_id: 伺服器 ID
            limit: 最大返回數量

        Returns:
            用戶資料列表
        """
        try:
            guild = self.bot.get_guild(guild_id)
            if not guild:
                logger.warning(f"找不到伺服器 {guild_id}")
                return []

            matched_users = []
            query_lower = query.lower().strip()

            # 嘗試按用戶 ID 搜尋
            if query.isdigit():
                try:
                    user_id = int(query)
                    member = guild.get_member(user_id)
                    if member:
                        matched_users.append(self._format_user_data(member))
                        logger.debug(f"按 ID {user_id} 找到用戶: {member.display_name}")
                except ValueError:
                    pass

            # 按名稱搜尋
            if len(matched_users) < limit:
                for member in guild.members:
                    if len(matched_users) >= limit:
                        break

                    # 避免重複添加(如果已按 ID 找到)
                    if any(u["user_id"] == member.id for u in matched_users):
                        continue

                    # 檢查用戶名、顯示名稱、暱稱
                    if (
                        query_lower in member.name.lower()
                        or query_lower in member.display_name.lower()
                        or (member.nick and query_lower in member.nick.lower())
                    ):
                        matched_users.append(self._format_user_data(member))
                        logger.debug(f"按名稱找到用戶: {member.display_name}")

            logger.info(
                f"搜尋查詢 '{query}' 在伺服器 {guild_id} 找到 {len(matched_users)} 個用戶"
            )
            return matched_users[:limit]

        except Exception as e:
            logger.error(f"搜尋用戶時發生錯誤: {e}")
            return []

    def _format_user_data(self, member: discord.Member) -> dict[str, Any]:
        """格式化用戶資料."""
        return {
            "user_id": member.id,
            "username": member.name,
            "display_name": member.display_name,
            "nick": member.nick,
            "avatar_url": member.avatar.url
            if member.avatar
            else member.default_avatar.url,
            "joined_at": member.joined_at.isoformat() if member.joined_at else None,
            "user": member,  # 保留 member 物件供後續使用
        }

    async def get_user_achievement_summary(
        self, user_id: int, repository: AchievementRepository
    ) -> dict[str, Any]:
        """獲取用戶成就摘要統計.

        Args:
            user_id: 用戶 ID
            repository: 成就資料存取庫

        Returns:
            用戶成就摘要字典
        """
        try:
            # 獲取用戶成就資料
            user_achievements = await repository.get_user_achievements(user_id)
            user_progress = await repository.get_user_progress(user_id)
            total_achievements = await repository.get_achievements_count()

            # 計算統計資料
            earned_count = len(user_achievements)
            in_progress_count = len([
                p for p in user_progress if p.current_value < p.target_value
            ])
            total_points = sum(ach.points for _, ach in user_achievements)

            return {
                "total_achievements": total_achievements,
                "earned_achievements": earned_count,
                "in_progress_achievements": in_progress_count,
                "completion_rate": round((earned_count / total_achievements * 100), 1)
                if total_achievements > 0
                else 0,
                "total_points": total_points,
                "last_achievement": user_achievements[0].earned_at
                if user_achievements
                else None,
            }

        except Exception as e:
            logger.error(f"獲取用戶 {user_id} 成就摘要失敗: {e}")
            return {
                "total_achievements": 0,
                "earned_achievements": 0,
                "in_progress_achievements": 0,
                "completion_rate": 0,
                "total_points": 0,
                "last_achievement": None,
            }


class UserAchievementAdminService:
    """用戶成就管理服務."""

    def __init__(
        self,
        repository: AchievementRepository,
        permission_service: AdminPermissionService,
        cache_service: AchievementCacheService,
        audit_logger: AuditLogger,
    ):
        """初始化用戶成就管理服務.

        Args:
            repository: 成就資料存取庫
            permission_service: 權限檢查服務
            cache_service: 快取服務
            audit_logger: 審計日誌服務
        """
        self.repository = repository
        self.permission_service = permission_service
        self.cache_service = cache_service
        self.audit_logger = audit_logger

    async def grant_achievement_to_user(
        self,
        admin_user_id: int,
        target_user_id: int,
        achievement_id: int,
        notify_user: bool = True,
        reason: str = "Manual grant by admin",
    ) -> tuple[bool, str, UserAchievement | None]:
        """手動授予用戶成就.

        Args:
            admin_user_id: 管理員用戶 ID
            target_user_id: 目標用戶 ID
            achievement_id: 成就 ID
            notify_user: 是否通知用戶
            reason: 授予原因

        Returns:
            (是否成功, 訊息, 用戶成就記錄)
        """
        try:
            # 權限檢查
            if not await self.permission_service.has_admin_permission(admin_user_id):
                return False, "權限不足", None

            # 檢查成就是否存在且啟用
            achievement = await self.repository.get_achievement(achievement_id)
            if not achievement:
                return False, "成就不存在", None
            if not achievement.is_active:
                return False, "成就未啟用", None

            # 檢查用戶是否已擁有此成就
            has_achievement = await self.repository.has_user_achievement(
                target_user_id, achievement_id
            )
            if has_achievement:
                return False, "用戶已擁有此成就", None

            # 授予成就
            user_achievement = UserAchievement(
                id=0,  # 由資料庫生成
                user_id=target_user_id,
                achievement_id=achievement_id,
                earned_at=datetime.utcnow(),
                notified=not notify_user,  # 如果不通知,標記為已通知避免後續通知
            )

            saved_achievement = await self.repository.create_user_achievement(
                user_achievement
            )

            # 記錄審計日誌
            await self.audit_logger.log_user_achievement_operation(
                admin_id=admin_user_id,
                operation="grant_achievement",
                target_user_id=target_user_id,
                achievement_id=achievement_id,
                details={
                    "achievement_name": achievement.name,
                    "reason": reason,
                    "notify_user": notify_user,
                },
                result="success",
            )

            # 清除相關快取
            await self._invalidate_user_cache(target_user_id)

            logger.info(
                f"管理員 {admin_user_id} 成功授予用戶 {target_user_id} 成就 {achievement.name}"
            )
            return True, f"成功授予成就「{achievement.name}」", saved_achievement

        except Exception as e:
            logger.error(f"授予成就失敗: {e}")
            # 記錄失敗的審計日誌
            await self.audit_logger.log_user_achievement_operation(
                admin_id=admin_user_id,
                operation="grant_achievement",
                target_user_id=target_user_id,
                achievement_id=achievement_id,
                details={"reason": reason, "error": str(e)},
                result="failed",
            )
            return False, f"授予成就時發生錯誤: {e!s}", None

    async def revoke_achievement_from_user(
        self,
        admin_user_id: int,
        target_user_id: int,
        achievement_id: int,
        reason: str = "Manual revoke by admin",
    ) -> tuple[bool, str]:
        """撤銷用戶成就.

        Args:
            admin_user_id: 管理員用戶 ID
            target_user_id: 目標用戶 ID
            achievement_id: 成就 ID
            reason: 撤銷原因

        Returns:
            (是否成功, 訊息)
        """
        try:
            # 權限檢查
            if not await self.permission_service.has_admin_permission(admin_user_id):
                return False, "權限不足"

            # 檢查成就是否存在
            achievement = await self.repository.get_achievement(achievement_id)
            if not achievement:
                return False, "成就不存在"

            # 檢查用戶是否擁有此成就
            has_achievement = await self.repository.has_user_achievement(
                target_user_id, achievement_id
            )
            if not has_achievement:
                return False, "用戶未擁有此成就"

            success = await self.repository.delete_user_achievement(
                target_user_id, achievement_id
            )
            if not success:
                return False, "撤銷成就失敗"

            # 同時清理相關的進度記錄
            await self.repository.delete_user_progress(target_user_id, achievement_id)

            # 記錄審計日誌
            await self.audit_logger.log_user_achievement_operation(
                admin_id=admin_user_id,
                operation="revoke_achievement",
                target_user_id=target_user_id,
                achievement_id=achievement_id,
                details={"achievement_name": achievement.name, "reason": reason},
                result="success",
            )

            # 清除相關快取
            await self._invalidate_user_cache(target_user_id)

            logger.info(
                f"管理員 {admin_user_id} 成功撤銷用戶 {target_user_id} 成就 {achievement.name}"
            )
            return True, f"成功撤銷成就「{achievement.name}」"

        except Exception as e:
            logger.error(f"撤銷成就失敗: {e}")
            # 記錄失敗的審計日誌
            await self.audit_logger.log_user_achievement_operation(
                admin_id=admin_user_id,
                operation="revoke_achievement",
                target_user_id=target_user_id,
                achievement_id=achievement_id,
                details={"reason": reason, "error": str(e)},
                result="failed",
            )
            return False, f"撤銷成就時發生錯誤: {e!s}"

    async def update_user_progress(
        self,
        admin_user_id: int,
        target_user_id: int,
        achievement_id: int,
        new_value: float,
        reason: str = "Manual adjustment by admin",
    ) -> tuple[bool, str, AchievementProgress | None]:
        """調整用戶成就進度.

        Args:
            admin_user_id: 管理員用戶 ID
            target_user_id: 目標用戶 ID
            achievement_id: 成就 ID
            new_value: 新的進度值
            reason: 調整原因

        Returns:
            (是否成功, 訊息, 進度記錄)
        """
        try:
            # 權限檢查
            if not await self.permission_service.has_admin_permission(admin_user_id):
                return False, "權限不足", None

            # 檢查成就是否存在且啟用
            achievement = await self.repository.get_achievement(achievement_id)
            if not achievement:
                return False, "成就不存在", None
            if not achievement.is_active:
                return False, "成就未啟用", None

            # 檢查用戶是否已擁有此成就
            has_achievement = await self.repository.has_user_achievement(
                target_user_id, achievement_id
            )
            if has_achievement:
                return False, "用戶已擁有此成就,無法調整進度", None

            criteria = achievement.criteria or {}
            target_value = criteria.get("target", 1)

            # 驗證新進度值
            if new_value < 0:
                return False, "進度值不能小於 0", None
            if new_value > target_value:
                return False, f"進度值不能大於目標值 {target_value}", None

            # 獲取或創建進度記錄
            progress = await self.repository.get_user_progress_by_achievement(
                target_user_id, achievement_id
            )
            if progress:
                # 更新現有進度
                progress.current_value = new_value
                progress.last_updated = datetime.utcnow()
                updated_progress = await self.repository.update_user_progress(progress)
            else:
                # 創建新進度記錄
                progress = AchievementProgress(
                    id=0,  # 由資料庫生成
                    user_id=target_user_id,
                    achievement_id=achievement_id,
                    current_value=new_value,
                    target_value=target_value,
                    progress_data={},
                    last_updated=datetime.utcnow(),
                )
                updated_progress = await self.repository.create_user_progress(progress)

            # 檢查是否達成成就
            if new_value >= target_value:
                # 自動授予成就
                _, message, _ = await self.grant_achievement_to_user(
                    admin_user_id,
                    target_user_id,
                    achievement_id,
                    notify_user=True,
                    reason="Auto-granted after progress adjustment",
                )
                success_msg = f"進度已調整為 {new_value}/{target_value},並自動授予成就"
            else:
                success_msg = f"進度已調整為 {new_value}/{target_value}"

            # 記錄審計日誌
            await self.audit_logger.log_user_achievement_operation(
                admin_id=admin_user_id,
                operation="adjust_progress",
                target_user_id=target_user_id,
                achievement_id=achievement_id,
                details={
                    "achievement_name": achievement.name,
                    "previous_value": progress.current_value if progress else 0,
                    "new_value": new_value,
                    "target_value": target_value,
                    "reason": reason,
                },
                result="success",
            )

            # 清除相關快取
            await self._invalidate_user_cache(target_user_id)

            logger.info(
                f"管理員 {admin_user_id} 成功調整用戶 {target_user_id} 成就 {achievement.name} 進度至 {new_value}"
            )
            return True, success_msg, updated_progress

        except Exception as e:
            logger.error(f"調整用戶進度失敗: {e}")
            # 記錄失敗的審計日誌
            await self.audit_logger.log_user_achievement_operation(
                admin_id=admin_user_id,
                operation="adjust_progress",
                target_user_id=target_user_id,
                achievement_id=achievement_id,
                details={"reason": reason, "new_value": new_value, "error": str(e)},
                result="failed",
            )
            return False, f"調整進度時發生錯誤: {e!s}", None

    async def reset_user_achievements(
        self,
        admin_user_id: int,
        target_user_id: int,
        category_id: int | None = None,
        reason: str = "Manual reset by admin",
    ) -> tuple[bool, str, dict[str, int]]:
        """重置用戶成就資料.

        Args:
            admin_user_id: 管理員用戶 ID
            target_user_id: 目標用戶 ID
            category_id: 要重置的分類 ID(None 表示重置所有)
            reason: 重置原因

        Returns:
            (是否成功, 訊息, 重置統計)
        """
        try:
            # 權限檢查
            if not await self.permission_service.has_admin_permission(admin_user_id):
                return False, "權限不足", {}

            user_achievements = await self.repository.get_user_achievements(
                target_user_id, category_id
            )
            user_progress = await self.repository.get_user_progress(
                target_user_id, category_id
            )

            # 執行重置操作
            if category_id:
                # 重置特定分類
                deleted_achievements = (
                    await self.repository.delete_user_achievements_by_category(
                        target_user_id, category_id
                    )
                )
                deleted_progress = (
                    await self.repository.delete_user_progress_by_category(
                        target_user_id, category_id
                    )
                )
                reset_scope = f"分類 {category_id}"
            else:
                # 重置所有資料
                deleted_achievements = (
                    await self.repository.delete_all_user_achievements(target_user_id)
                )
                deleted_progress = await self.repository.delete_all_user_progress(
                    target_user_id
                )
                reset_scope = "所有"

            reset_stats = {
                "deleted_achievements": deleted_achievements,
                "deleted_progress": deleted_progress,
                "backup_achievements": len(user_achievements),
                "backup_progress": len(user_progress),
            }

            # 記錄審計日誌
            await self.audit_logger.log_user_achievement_operation(
                admin_id=admin_user_id,
                operation="reset_user_data",
                target_user_id=target_user_id,
                achievement_id=None,
                details={
                    "category_id": category_id,
                    "reset_scope": reset_scope,
                    "reason": reason,
                    "stats": reset_stats,
                },
                result="success",
            )

            # 清除相關快取
            await self._invalidate_user_cache(target_user_id)

            logger.info(
                f"管理員 {admin_user_id} 成功重置用戶 {target_user_id} 的{reset_scope}成就資料"
            )
            return True, f"成功重置{reset_scope}成就資料", reset_stats

        except Exception as e:
            logger.error(f"重置用戶資料失敗: {e}")
            # 記錄失敗的審計日誌
            await self.audit_logger.log_user_achievement_operation(
                admin_id=admin_user_id,
                operation="reset_user_data",
                target_user_id=target_user_id,
                achievement_id=None,
                details={"category_id": category_id, "reason": reason, "error": str(e)},
                result="failed",
            )
            return False, f"重置用戶資料時發生錯誤: {e!s}", {}

    async def bulk_grant_achievement(
        self,
        admin_user_id: int,
        user_ids: list[int],
        achievement_id: int,
        notify_users: bool = True,
        reason: str = "Bulk grant by admin",
    ) -> tuple[bool, str, dict[str, Any]]:
        """批量授予成就給多個用戶.

        Args:
            admin_user_id: 管理員用戶 ID
            user_ids: 目標用戶 ID 列表
            achievement_id: 成就 ID
            notify_users: 是否通知用戶
            reason: 授予原因

        Returns:
            (是否成功, 訊息, 操作結果統計)
        """
        try:
            # 權限檢查
            if not await self.permission_service.has_admin_permission(admin_user_id):
                return False, "權限不足", {}

            # 限制批量操作數量
            if len(user_ids) > MAX_BATCH_USERS:
                return False, "批量操作最多支援 50 個用戶", {}

            # 檢查成就是否存在且啟用
            achievement = await self.repository.get_achievement(achievement_id)
            if not achievement:
                return False, "成就不存在", {}
            if not achievement.is_active:
                return False, "成就未啟用", {}

            results = {
                "total_users": len(user_ids),
                "successful": 0,
                "failed": 0,
                "skipped": 0,
                "details": [],
            }

            # 批量處理
            for user_id in user_ids:
                try:
                    (
                        success,
                        message,
                        user_achievement,
                    ) = await self.grant_achievement_to_user(
                        admin_user_id, user_id, achievement_id, notify_users, reason
                    )

                    if success:
                        results["successful"] += 1
                        results["details"].append({
                            "user_id": user_id,
                            "status": "success",
                            "message": message,
                        })
                    elif "已擁有" in message:
                        results["skipped"] += 1
                        results["details"].append({
                            "user_id": user_id,
                            "status": "skipped",
                            "message": message,
                        })
                    else:
                        results["failed"] += 1
                        results["details"].append({
                            "user_id": user_id,
                            "status": "failed",
                            "message": message,
                        })

                except Exception as e:
                    results["failed"] += 1
                    results["details"].append({
                        "user_id": user_id,
                        "status": "error",
                        "message": str(e),
                    })

            # 記錄批量操作審計日誌
            await self.audit_logger.log_user_achievement_operation(
                admin_id=admin_user_id,
                operation="bulk_grant_achievement",
                target_user_id=None,
                achievement_id=achievement_id,
                details={
                    "achievement_name": achievement.name,
                    "user_count": len(user_ids),
                    "reason": reason,
                    "results": results,
                },
                result="success" if results["failed"] == 0 else "partial",
            )

            summary = f"批量授予完成: 成功 {results['successful']}, 失敗 {results['failed']}, 跳過 {results['skipped']}"
            logger.info(
                f"管理員 {admin_user_id} 執行批量授予成就 {achievement.name}: {summary}"
            )

            return True, summary, results

        except Exception as e:
            logger.error(f"批量授予成就失敗: {e}")
            return False, f"批量授予時發生錯誤: {e!s}", {}

    async def bulk_revoke_achievement(
        self,
        admin_user_id: int,
        user_ids: list[int],
        achievement_id: int,
        reason: str = "Bulk revoke by admin",
    ) -> tuple[bool, str, dict[str, Any]]:
        """批量撤銷成就從多個用戶.

        Args:
            admin_user_id: 管理員用戶 ID
            user_ids: 目標用戶 ID 列表
            achievement_id: 成就 ID
            reason: 撤銷原因

        Returns:
            (是否成功, 訊息, 操作結果統計)
        """
        try:
            # 權限檢查
            if not await self.permission_service.has_admin_permission(admin_user_id):
                return False, "權限不足", {}

            # 限制批量操作數量
            if len(user_ids) > MAX_BATCH_USERS:
                return False, "批量操作最多支援 50 個用戶", {}

            # 檢查成就是否存在
            achievement = await self.repository.get_achievement(achievement_id)
            if not achievement:
                return False, "成就不存在", {}

            results = {
                "total_users": len(user_ids),
                "successful": 0,
                "failed": 0,
                "skipped": 0,
                "details": [],
            }

            # 批量處理
            for user_id in user_ids:
                try:
                    success, message = await self.revoke_achievement_from_user(
                        admin_user_id, user_id, achievement_id, reason
                    )

                    if success:
                        results["successful"] += 1
                        results["details"].append({
                            "user_id": user_id,
                            "status": "success",
                            "message": message,
                        })
                    elif "未擁有" in message:
                        results["skipped"] += 1
                        results["details"].append({
                            "user_id": user_id,
                            "status": "skipped",
                            "message": message,
                        })
                    else:
                        results["failed"] += 1
                        results["details"].append({
                            "user_id": user_id,
                            "status": "failed",
                            "message": message,
                        })

                except Exception as e:
                    results["failed"] += 1
                    results["details"].append({
                        "user_id": user_id,
                        "status": "error",
                        "message": str(e),
                    })

            # 記錄批量操作審計日誌
            await self.audit_logger.log_user_achievement_operation(
                admin_id=admin_user_id,
                operation="bulk_revoke_achievement",
                target_user_id=None,
                achievement_id=achievement_id,
                details={
                    "achievement_name": achievement.name,
                    "user_count": len(user_ids),
                    "reason": reason,
                    "results": results,
                },
                result="success" if results["failed"] == 0 else "partial",
            )

            summary = f"批量撤銷完成: 成功 {results['successful']}, 失敗 {results['failed']}, 跳過 {results['skipped']}"
            logger.info(
                f"管理員 {admin_user_id} 執行批量撤銷成就 {achievement.name}: {summary}"
            )

            return True, summary, results

        except Exception as e:
            logger.error(f"批量撤銷成就失敗: {e}")
            return False, f"批量撤銷時發生錯誤: {e!s}", {}

    async def _invalidate_user_cache(self, user_id: int) -> None:
        """清除用戶相關的快取."""
        try:
            cache_keys = [
                f"user_achievements:{user_id}",
                f"user_progress:{user_id}",
                f"user_stats:{user_id}",
                "leaderboard:*",  # 排行榜可能受影響
            ]

            for key in cache_keys:
                await self.cache_service.delete_pattern(key)

            logger.debug(f"已清除用戶 {user_id} 的相關快取")

        except Exception as e:
            logger.warning(f"清除用戶 {user_id} 快取時發生錯誤: {e}")
