"""真實的成就系統管理服務實現.

此模組提供真實的管理功能，替換原有的模擬實現：
- 用戶成就管理
- 批量操作
- 數據重置
- 統計查詢
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from ..database.models import Achievement, AchievementProgress, UserAchievement
from ..database.repository import AchievementRepository

logger = logging.getLogger(__name__)


class RealAdminService:
    """真實的管理服務實現."""

    def __init__(self, repository: AchievementRepository):
        """初始化管理服務.
        
        Args:
            repository: 成就系統資料存取層
        """
        self.repository = repository

    async def get_user_achievements(self, user_id: int) -> list[UserAchievement]:
        """獲取用戶成就列表."""
        try:
            return await self.repository.get_user_achievements(user_id)
        except Exception as e:
            logger.error(f"獲取用戶 {user_id} 成就失敗: {e}")
            return []

    async def get_user_progress(self, user_id: int) -> list[AchievementProgress]:
        """獲取用戶進度列表."""
        try:
            return await self.repository.get_user_progress(user_id)
        except Exception as e:
            logger.error(f"獲取用戶 {user_id} 進度失敗: {e}")
            return []

    async def get_user_stats(self, user_id: int) -> dict[str, Any]:
        """獲取用戶統計資料."""
        try:
            achievements = await self.get_user_achievements(user_id)
            progress = await self.get_user_progress(user_id)
            
            total_points = sum(ach.points for ach in achievements if hasattr(ach, 'points'))
            
            return {
                'total_achievements': len(achievements),
                'total_progress': len(progress),
                'total_points': total_points,
                'join_date': None,  # 需要從其他服務獲取
                'last_active': None,  # 需要從其他服務獲取
                'total_messages': 0,  # 需要從其他服務獲取
            }
        except Exception as e:
            logger.error(f"獲取用戶 {user_id} 統計失敗: {e}")
            return {}

    async def reset_user_achievements(self, user_id: int) -> bool:
        """重置用戶所有成就."""
        try:
            await self.repository.delete_user_achievements(user_id)
            logger.info(f"用戶 {user_id} 成就重置完成")
            return True
        except Exception as e:
            logger.error(f"重置用戶 {user_id} 成就失敗: {e}")
            return False

    async def reset_user_progress(self, user_id: int) -> bool:
        """重置用戶所有進度."""
        try:
            await self.repository.delete_user_progress(user_id)
            logger.info(f"用戶 {user_id} 進度重置完成")
            return True
        except Exception as e:
            logger.error(f"重置用戶 {user_id} 進度失敗: {e}")
            return False

    async def reset_user_category_data(self, user_id: int, category_id: int) -> bool:
        """重置用戶特定分類的資料."""
        try:
            # 獲取該分類下的所有成就
            achievements = await self.repository.get_achievements_by_category(category_id)
            achievement_ids = [ach.id for ach in achievements if ach.id]
            
            # 刪除用戶在該分類下的成就和進度
            for achievement_id in achievement_ids:
                await self.repository.delete_user_achievement(user_id, achievement_id)
                await self.repository.delete_user_progress(user_id, achievement_id)
            
            logger.info(f"用戶 {user_id} 分類 {category_id} 資料重置完成")
            return True
        except Exception as e:
            logger.error(f"重置用戶 {user_id} 分類 {category_id} 資料失敗: {e}")
            return False

    async def grant_achievement(self, user_id: int, achievement_id: int, admin_user_id: int) -> bool:
        """授予用戶成就."""
        try:
            # 檢查用戶是否已有此成就
            has_achievement = await self.repository.has_user_achievement(user_id, achievement_id)
            if has_achievement:
                logger.warning(f"用戶 {user_id} 已擁有成就 {achievement_id}")
                return False
            
            # 創建成就記錄
            user_achievement = UserAchievement(
                user_id=user_id,
                achievement_id=achievement_id,
                earned_at=datetime.utcnow(),
                notified=False
            )
            
            await self.repository.create_user_achievement(user_achievement)
            logger.info(f"管理員 {admin_user_id} 為用戶 {user_id} 授予成就 {achievement_id}")
            return True
            
        except Exception as e:
            logger.error(f"授予成就失敗: {e}")
            return False

    async def revoke_achievement(self, user_id: int, achievement_id: int, admin_user_id: int) -> bool:
        """撤銷用戶成就."""
        try:
            await self.repository.delete_user_achievement(user_id, achievement_id)
            logger.info(f"管理員 {admin_user_id} 撤銷用戶 {user_id} 的成就 {achievement_id}")
            return True
        except Exception as e:
            logger.error(f"撤銷成就失敗: {e}")
            return False

    async def update_user_progress(self, user_id: int, achievement_id: int, new_value: float, admin_user_id: int) -> bool:
        """更新用戶成就進度."""
        try:
            # 獲取現有進度
            progress = await self.repository.get_user_progress_by_achievement(user_id, achievement_id)
            
            if progress:
                # 更新現有進度
                progress.current_value = new_value
                progress.last_updated = datetime.utcnow()
                await self.repository.update_user_progress(progress)
            else:
                # 創建新進度記錄
                achievement = await self.repository.get_achievement_by_id(achievement_id)
                if not achievement:
                    logger.error(f"成就 {achievement_id} 不存在")
                    return False
                
                # 從成就條件中獲取目標值
                target_value = achievement.criteria.get('target_value', 100.0)
                
                new_progress = AchievementProgress(
                    user_id=user_id,
                    achievement_id=achievement_id,
                    current_value=new_value,
                    target_value=target_value,
                    last_updated=datetime.utcnow()
                )
                await self.repository.create_user_progress(new_progress)
            
            logger.info(f"管理員 {admin_user_id} 更新用戶 {user_id} 成就 {achievement_id} 進度為 {new_value}")
            return True
            
        except Exception as e:
            logger.error(f"更新進度失敗: {e}")
            return False

    async def get_system_stats(self) -> dict[str, Any]:
        """獲取系統統計資料."""
        try:
            # 獲取基本統計
            total_achievements = await self.repository.count_achievements()
            total_categories = await self.repository.count_categories()
            total_users_with_achievements = await self.repository.count_users_with_achievements()
            
            return {
                'total_achievements': total_achievements,
                'total_categories': total_categories,
                'total_users': total_users_with_achievements,
                'active_achievements': await self.repository.count_active_achievements(),
                'total_awarded': await self.repository.count_total_awarded_achievements(),
            }
        except Exception as e:
            logger.error(f"獲取系統統計失敗: {e}")
            return {}

    async def search_users(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """搜尋用戶."""
        try:
            # 這裡需要與 Discord 用戶資料整合
            # 暫時返回空列表，需要在後續實現中整合用戶服務
            logger.warning("用戶搜尋功能需要整合用戶服務")
            return []
        except Exception as e:
            logger.error(f"搜尋用戶失敗: {e}")
            return []

    async def get_achievement_usage_stats(self, achievement_id: int) -> dict[str, Any]:
        """獲取成就使用統計."""
        try:
            # 獲取成就基本資訊
            achievement = await self.repository.get_achievement_by_id(achievement_id)
            if not achievement:
                return {}
            
            # 獲取獲得此成就的用戶數
            user_count = await self.repository.count_users_with_achievement(achievement_id)
            
            # 獲取進度中的用戶數
            progress_count = await self.repository.count_users_with_progress(achievement_id)
            
            return {
                'achievement': achievement,
                'users_earned': user_count,
                'users_in_progress': progress_count,
                'completion_rate': (user_count / (user_count + progress_count)) * 100 if (user_count + progress_count) > 0 else 0
            }
        except Exception as e:
            logger.error(f"獲取成就 {achievement_id} 統計失敗: {e}")
            return {}
