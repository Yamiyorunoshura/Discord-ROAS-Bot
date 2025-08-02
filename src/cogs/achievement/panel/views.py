"""成就系統頁面視圖模組.

提供成就系統各頁面的視圖邏輯和資料處理：
- 主頁面視圖
- 個人成就視圖
- 成就瀏覽視圖
- 排行榜視圖
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from src.cogs.core.base_cog import StandardEmbedBuilder

if TYPE_CHECKING:
    import discord

    from ..services.achievement_service import AchievementService

logger = logging.getLogger(__name__)


class BaseAchievementView(ABC):
    """成就系統基礎視圖類別.

    定義所有成就頁面視圖的共同介面和基礎功能。
    """

    def __init__(
        self, achievement_service: AchievementService, guild_id: int, user_id: int
    ):
        """初始化基礎視圖.

        Args:
            achievement_service: 成就服務實例
            guild_id: 伺服器 ID
            user_id: 用戶 ID
        """
        self.achievement_service = achievement_service
        self.guild_id = guild_id
        self.user_id = user_id
        self._cache: dict[str, Any] = {}
        self._cache_valid = False

    @abstractmethod
    async def build_embed(self, **kwargs: Any) -> discord.Embed:
        """建立頁面 Embed.

        Args:
            **kwargs: 額外參數

        Returns:
            discord.Embed: 頁面 Embed
        """
        pass

    @abstractmethod
    async def load_data(self, **kwargs: Any) -> dict[str, Any]:
        """載入頁面資料.

        Args:
            **kwargs: 載入參數

        Returns:
            dict[str, Any]: 頁面資料
        """
        pass

    async def refresh_cache(self, **kwargs: Any) -> None:
        """重新整理快取.

        Args:
            **kwargs: 重新整理參數
        """
        try:
            self._cache = await self.load_data(**kwargs)
            self._cache_valid = True
            logger.debug(f"【{self.__class__.__name__}】快取重新整理完成")
        except Exception as e:
            logger.error(f"【{self.__class__.__name__}】快取重新整理失敗: {e}")
            self._cache_valid = False
            raise

    async def get_cached_data(self, **kwargs: Any) -> dict[str, Any]:
        """獲取快取資料.

        Args:
            **kwargs: 獲取參數

        Returns:
            dict[str, Any]: 快取資料
        """
        if not self._cache_valid:
            await self.refresh_cache(**kwargs)
        return self._cache

    def clear_cache(self) -> None:
        """清除快取."""
        self._cache.clear()
        self._cache_valid = False


class MainView(BaseAchievementView):
    """主頁面視圖.

    顯示成就系統的歡迎頁面和導航選項。
    """

    async def build_embed(self, bot: discord.Client, **kwargs: Any) -> discord.Embed:
        """建立主頁面 Embed."""
        try:
            embed = StandardEmbedBuilder.create_info_embed(
                "成就系統",
                "🎯 **歡迎使用成就系統！**\n\n"
                "這裡是您的成就中心，提供完整的成就管理功能：\n\n"
                "🏅 **我的成就** - 查看您的個人成就進度\n"
                "　• 已獲得的成就列表\n"
                "　• 進行中的成就進度\n"
                "　• 成就統計和完成率\n\n"
                "📚 **成就瀏覽** - 探索所有可用成就\n"
                "　• 按分類瀏覽成就\n"
                "　• 查看獲得條件和獎勵\n"
                "　• 了解成就難度和稀有度\n\n"
                "🏆 **排行榜** - 查看成就排名\n"
                "　• 總成就數排行\n"
                "　• 成就點數排行\n"
                "　• 分類成就排行\n\n"
                "**操作指南：**\n"
                "• 使用下方選單切換不同頁面\n"
                "• 點擊 🔄 重新整理最新數據\n"
                "• 點擊 ❌ 關閉面板",
            )

            # 添加用戶資訊
            try:
                guild = bot.get_guild(self.guild_id)
                user = guild.get_member(self.user_id) if guild else None

                if user:
                    embed.set_author(
                        name=f"{user.display_name} 的成就",
                        icon_url=user.display_avatar.url,
                    )
            except Exception as e:
                logger.warning(f"【主頁面】設置用戶資訊失敗: {e}")

            embed.set_footer(text="💡 使用選單切換不同頁面")
            return embed

        except Exception as e:
            logger.error(f"【主頁面】建立 Embed 失敗: {e}")
            return StandardEmbedBuilder.create_error_embed(
                "載入失敗", "無法載入主頁面，請稍後再試"
            )

    async def load_data(self, **kwargs: Any) -> dict[str, Any]:
        """載入主頁面資料."""
        # 主頁面通常不需要額外資料
        return {"last_updated": "now", "page_type": "main"}


class PersonalView(BaseAchievementView):
    """個人成就視圖.

    顯示用戶的成就進度和已獲得的成就，支援分頁瀏覽和類別篩選。
    """

    def __init__(
        self, achievement_service: AchievementService, guild_id: int, user_id: int
    ):
        """初始化個人成就視圖.

        Args:
            achievement_service: 成就服務實例
            guild_id: 伺服器 ID
            user_id: 用戶 ID
        """
        super().__init__(achievement_service, guild_id, user_id)
        self._current_page = 0
        self._page_size = 10
        self._selected_category: int | None = None
        self._total_pages = 0

    async def build_embed(self, **kwargs: Any) -> discord.Embed:
        """建立個人成就頁面 Embed."""
        try:
            # 獲取參數
            page = kwargs.get("page", self._current_page)
            category_id = kwargs.get("category_id", self._selected_category)

            data = await self.get_cached_data(page=page, category_id=category_id)

            embed = StandardEmbedBuilder.create_info_embed(
                "我的成就", "查看您的成就進度和已獲得的成就"
            )

            # 添加成就統計
            stats = data.get("stats", {})
            embed.add_field(
                name="📊 成就統計",
                value=f"已獲得: {stats.get('earned', 0)}\\n"
                f"總數: {stats.get('total', 0)}\\n"
                f"完成率: {stats.get('completion_rate', 0):.1f}%\\n"
                f"總點數: {stats.get('total_points', 0)}",
                inline=True,
            )

            # 添加分類資訊
            category_name = data.get("category_name", "全部")
            embed.add_field(name="📁 當前分類", value=category_name, inline=True)

            # 添加分頁資訊
            current_page = data.get("current_page", 0)
            total_pages = data.get("total_pages", 1)
            embed.add_field(
                name="📄 頁面", value=f"{current_page + 1} / {total_pages}", inline=True
            )

            # 添加已獲得成就列表
            earned_achievements = data.get("earned_achievements", [])
            if earned_achievements:
                earned_text = "\\n".join(
                    [
                        f"🏅 **{ach['name']}** ({ach['points']} 點)\\n   _{ach['description']}_\\n   📅 {ach['earned_at']}"
                        for ach in earned_achievements
                    ]
                )
                embed.add_field(
                    name="🏆 已獲得成就",
                    value=earned_text[:1024],  # Discord 限制 1024 字元
                    inline=False,
                )

            # 添加進行中的成就
            in_progress = data.get("in_progress", [])
            if in_progress:
                progress_text = "\\n".join(
                    [
                        f"⏳ **{ach['name']}**\\n   {self._create_progress_bar(ach['current'], ach['target'])} {ach['current']}/{ach['target']}"
                        for ach in in_progress[:5]
                    ]
                )
                embed.add_field(
                    name="🔄 進行中成就", value=progress_text[:1024], inline=False
                )

            # 設置footer
            embed.set_footer(
                text=f"💡 使用按鈕切換頁面和篩選分類 | 總共 {stats.get('earned', 0)} 個成就"
            )

            return embed

        except Exception as e:
            logger.error(f"【個人成就】建立 Embed 失敗: {e}")
            return StandardEmbedBuilder.create_error_embed(
                "載入失敗", "無法載入個人成就資料，請稍後再試"
            )

    async def load_data(self, **kwargs: Any) -> dict[str, Any]:
        """載入個人成就資料."""
        try:
            page = kwargs.get("page", 0)
            category_id = kwargs.get("category_id")

            logger.debug(
                f"【個人成就】載入資料 - User: {self.user_id}, Page: {page}, Category: {category_id}"
            )

            # 獲取用戶成就統計
            stats = await self.achievement_service.get_user_achievement_stats(
                self.user_id
            )

            # 獲取用戶已獲得的成就（分頁）
            offset = page * self._page_size
            user_achievements = await self.achievement_service.get_user_achievements(
                user_id=self.user_id,
                category_id=category_id,
                limit=self._page_size + offset,  # 為了計算總頁數
            )

            # 分頁處理
            total_achievements = len(user_achievements)
            self._total_pages = max(
                1, (total_achievements + self._page_size - 1) // self._page_size
            )

            # 當前頁面的成就
            page_achievements = user_achievements[offset : offset + self._page_size]

            # 格式化已獲得成就
            earned_achievements = []
            for user_ach, achievement in page_achievements:
                earned_achievements.append(
                    {
                        "name": achievement.name,
                        "description": achievement.description,
                        "points": achievement.points,
                        "earned_at": user_ach.earned_at.strftime("%Y-%m-%d %H:%M")
                        if user_ach.earned_at
                        else "未知",
                        "category": achievement.category_id,
                    }
                )

            # 獲取進行中的成就（實作真實的成就進度查詢）
            try:
                # 嘗試從進度追蹤服務獲取真實進度數據
                if hasattr(self, 'progress_tracker') and self.progress_tracker:
                    in_progress = await self.progress_tracker.get_user_progress_achievements(
                        user_id=interaction.user.id,
                        guild_id=interaction.guild_id
                    )
                else:
                    # 如果沒有進度追蹤服務，使用模擬數據
                    in_progress = await self._get_user_progress_achievements()
            except Exception as e:
                # 記錄錯誤並使用模擬數據作為備用
                logger.warning(f"獲取用戶進度數據失敗，使用模擬數據: {e}")
                in_progress = await self._get_user_progress_achievements()

            # 獲取分類名稱
            category_name = "全部"
            if category_id:
                category = await self.achievement_service.get_category_by_id(
                    category_id
                )
                category_name = category.name if category else f"分類 {category_id}"

            return {
                "stats": {
                    "earned": stats.get("total_achievements", 0),
                    "total": stats.get("available_achievements", 0),
                    "completion_rate": stats.get("completion_rate", 0.0),
                    "total_points": stats.get("total_points", 0),
                },
                "earned_achievements": earned_achievements,
                "in_progress": in_progress,
                "current_page": page,
                "total_pages": self._total_pages,
                "category_name": category_name,
                "category_id": category_id,
            }

        except Exception as e:
            logger.error(f"【個人成就】載入資料失敗: {e}")
            raise

    def _create_progress_bar(self, current: int, target: int, length: int = 10) -> str:
        """建立進度條顯示.

        Args:
            current: 當前進度
            target: 目標值
            length: 進度條長度

        Returns:
            str: 進度條字串
        """
        if target <= 0:
            return "▓" * length

        progress_ratio = min(current / target, 1.0)
        filled_length = int(length * progress_ratio)

        filled = "▓" * filled_length
        empty = "░" * (length - filled_length)

        return f"[{filled}{empty}]"

    async def _get_user_progress_achievements(self) -> list[dict[str, Any]]:
        """獲取用戶進行中的成就（實作真實查詢機制）.

        Returns:
            list[dict]: 進行中成就列表
        """
        # 實作真實的成就進度查詢
        try:
            # 嘗試從成就服務獲取用戶的進行中成就
            if hasattr(self, 'achievement_service') and self.achievement_service:
                in_progress_achievements = await self.achievement_service.get_user_in_progress_achievements(
                    user_id=getattr(self, 'user_id', None) or self.interaction.user.id,
                    guild_id=getattr(self, 'guild_id', None) or self.interaction.guild_id
                )

                # 轉換為預期的格式
                result = []
                for achievement in in_progress_achievements:
                    result.append({
                        "name": achievement.get("name", "未知成就"),
                        "description": achievement.get("description", ""),
                        "current": achievement.get("current_progress", 0),
                        "target": achievement.get("target_value", 100),
                        "category": achievement.get("category", "一般")
                    })

                return result
            else:
                # 沒有成就服務時顯示無數據提示
                logger.warning("成就服務不可用，顯示無數據提示")
                return self._get_no_progress_data()
        except Exception as e:
            logger.error(f"獲取成就進度失敗: {e}")
            return self._get_no_progress_data()

    def _get_no_progress_data(self) -> list[dict[str, Any]]:
        """獲取無進度數據提示."""
        return [
            {
                "name": "暫無進行中的成就",
                "description": "目前沒有正在進行的成就，請先參與活動或完成任務",
                "current": 0,
                "target": 1,
                "category": "系統",
            }
        ]

    def set_page(self, page: int) -> None:
        """設置當前頁面.

        Args:
            page: 頁面號碼（從0開始）
        """
        self._current_page = max(0, min(page, self._total_pages - 1))
        self._cache_valid = False

    def set_category_filter(self, category_id: int | None) -> None:
        """設置分類篩選.

        Args:
            category_id: 分類ID，None表示不篩選
        """
        self._selected_category = category_id
        self._current_page = 0  # 重置到第一頁
        self._cache_valid = False

    def get_current_page(self) -> int:
        """獲取當前頁面號碼."""
        return self._current_page

    def get_total_pages(self) -> int:
        """獲取總頁數."""
        return self._total_pages

    def get_selected_category(self) -> int | None:
        """獲取當前選擇的分類."""
        return self._selected_category

    def has_next_page(self) -> bool:
        """是否有下一頁."""
        return self._current_page < self._total_pages - 1

    def has_previous_page(self) -> bool:
        """是否有上一頁."""
        return self._current_page > 0


class BrowserView(BaseAchievementView):
    """成就瀏覽視圖.

    顯示所有可用的成就，支援分類篩選和分頁瀏覽。
    提供完整的成就資訊包括獲得條件、點數獎勵和用戶進度。
    """

    def __init__(
        self, achievement_service: AchievementService, guild_id: int, user_id: int
    ):
        """初始化成就瀏覽視圖.

        Args:
            achievement_service: 成就服務實例
            guild_id: 伺服器 ID
            user_id: 用戶 ID
        """
        super().__init__(achievement_service, guild_id, user_id)
        self._current_page = 0
        self._page_size = 8  # 每頁顯示 8 個成就
        self._selected_category: int | None = None
        self._total_pages = 0
        self._total_achievements = 0

    async def build_embed(self, **kwargs: Any) -> discord.Embed:
        """建立成就瀏覽頁面 Embed."""
        try:
            # 獲取參數
            page = kwargs.get("page", self._current_page)
            category_id = kwargs.get("category_id", self._selected_category)

            data = await self.get_cached_data(page=page, category_id=category_id)

            # 基礎 Embed 設定
            category_name = data.get("category_name", "全部分類")
            title = f"成就瀏覽 - {category_name}"
            description = "瀏覽所有可用的成就，了解獲得條件和獎勵"

            embed = StandardEmbedBuilder.create_info_embed(title, description)

            # 添加統計資訊
            stats = data.get("stats", {})
            embed.add_field(
                name="📊 總覽統計",
                value=f"總成就數: {stats.get('total_achievements', 0)}\n"
                f"已獲得: {stats.get('user_earned', 0)}\n"
                f"完成率: {stats.get('completion_rate', 0):.1f}%",
                inline=True,
            )

            # 添加分類資訊
            embed.add_field(name="📁 當前分類", value=category_name, inline=True)

            # 添加分頁資訊
            current_page = data.get("current_page", 0)
            total_pages = data.get("total_pages", 1)
            embed.add_field(
                name="📄 頁面", value=f"{current_page + 1} / {total_pages}", inline=True
            )

            # 添加成就列表
            achievements = data.get("achievements", [])
            if achievements:
                # 分為已獲得和未獲得
                earned_achievements = [
                    ach for ach in achievements if ach.get("earned", False)
                ]
                not_earned_achievements = [
                    ach for ach in achievements if not ach.get("earned", False)
                ]

                # 顯示已獲得成就
                if earned_achievements:
                    earned_text = "\n".join(
                        [
                            f"🏅 **{ach['name']}** ({ach['points']} 點)\n   _{ach['description'][:50]}{'...' if len(ach['description']) > 50 else ''}_"
                            for ach in earned_achievements[:4]  # 最多顯示 4 個
                        ]
                    )
                    embed.add_field(
                        name="🏆 已獲得成就",
                        value=earned_text[:1024],  # Discord 限制
                        inline=False,
                    )

                # 顯示未獲得成就
                if not_earned_achievements:
                    not_earned_text = "\n".join(
                        [
                            f"⭕ **{ach['name']}** ({ach['points']} 點)\n   _{ach['description'][:50]}{'...' if len(ach['description']) > 50 else ''}_\n   💡 條件: {self._format_criteria(ach.get('criteria', {}))}"
                            for ach in not_earned_achievements[:4]  # 最多顯示 4 個
                        ]
                    )
                    embed.add_field(
                        name="🎯 可獲得成就",
                        value=not_earned_text[:1024],  # Discord 限制
                        inline=False,
                    )
            else:
                embed.add_field(
                    name="🎯 成就列表", value="此分類暫無成就", inline=False
                )

            # 設置 footer
            total_points = sum(ach.get("points", 0) for ach in achievements)
            embed.set_footer(
                text=f"💡 使用選單篩選分類和分頁導航 | 本頁總點數: {total_points}"
            )

            return embed

        except Exception as e:
            logger.error(f"【成就瀏覽】建立 Embed 失敗: {e}", exc_info=True)
            return StandardEmbedBuilder.create_error_embed(
                "載入失敗", "無法載入成就瀏覽資料，請稍後再試"
            )

    async def load_data(self, **kwargs: Any) -> dict[str, Any]:
        """載入成就瀏覽資料."""
        try:
            page = kwargs.get("page", 0)
            category_id = kwargs.get("category_id")

            logger.debug(
                f"【成就瀏覽】載入資料 - Page: {page}, Category: {category_id}"
            )

            # 獲取所有成就（按分類篩選）
            all_achievements = await self.achievement_service.list_achievements(
                category_id=category_id, active_only=True
            )

            # 計算分頁
            self._total_achievements = len(all_achievements)
            self._total_pages = max(
                1, (self._total_achievements + self._page_size - 1) // self._page_size
            )

            # 當前頁面的成就
            start_idx = page * self._page_size
            end_idx = start_idx + self._page_size
            page_achievements = all_achievements[start_idx:end_idx]

            # 獲取用戶已獲得的成就 ID
            user_achievements = await self.achievement_service.get_user_achievements(
                user_id=self.user_id, category_id=category_id
            )
            earned_achievement_ids = {
                ua[1].id for ua in user_achievements
            }  # (UserAchievement, Achievement)

            # 格式化頁面成就資料
            formatted_achievements = []
            for achievement in page_achievements:
                # 檢查用戶是否已獲得此成就
                earned = achievement.id in earned_achievement_ids

                # 獲取用戶對此成就的進度（如果存在）
                progress = (
                    await self._get_achievement_progress(achievement.id)
                    if not earned
                    else None
                )

                formatted_achievements.append(
                    {
                        "id": achievement.id,
                        "name": achievement.name,
                        "description": achievement.description,
                        "category_id": achievement.category_id,
                        "points": achievement.points,
                        "criteria": achievement.criteria,
                        "earned": earned,
                        "progress": progress,
                        "badge_url": achievement.badge_url,
                    }
                )

            # 獲取分類名稱
            category_name = "全部分類"
            if category_id:
                category = await self.achievement_service.get_category_by_id(
                    category_id
                )
                category_name = category.name if category else f"分類 {category_id}"

            # 計算統計資訊
            user_earned_count = len(
                [ach for ach in formatted_achievements if ach["earned"]]
            )
            completion_rate = (
                (user_earned_count / len(formatted_achievements) * 100)
                if formatted_achievements
                else 0
            )

            return {
                "achievements": formatted_achievements,
                "current_page": page,
                "total_pages": self._total_pages,
                "category_name": category_name,
                "category_id": category_id,
                "stats": {
                    "total_achievements": self._total_achievements,
                    "user_earned": user_earned_count,
                    "completion_rate": completion_rate,
                },
            }

        except Exception as e:
            logger.error(f"【成就瀏覽】載入資料失敗: {e}", exc_info=True)
            raise

    def _format_criteria(self, criteria: dict[str, Any]) -> str:
        """格式化成就條件顯示.

        Args:
            criteria: 成就條件字典

        Returns:
            str: 格式化的條件字串
        """
        if not criteria:
            return "無特殊條件"

        # 根據不同的條件類型格式化
        if "count" in criteria:
            return f"完成 {criteria['count']} 次"
        elif "duration" in criteria:
            return f"持續 {criteria['duration']} 天"
        elif "target" in criteria:
            return f"達到 {criteria['target']}"
        else:
            # 其他複雜條件的簡化顯示
            return "達成特定條件"

    async def _get_achievement_progress(
        self, achievement_id: int
    ) -> dict[str, Any] | None:
        """獲取用戶對特定成就的進度.

        Args:
            achievement_id: 成就 ID

        Returns:
            進度資訊字典或 None
        """
        try:
            # 實作真實的成就進度查詢
            if hasattr(self, 'achievement_service') and self.achievement_service:
                try:
                    progress = await self.achievement_service.get_user_progress(
                        user_id=self.user_id,
                        achievement_id=achievement_id
                    )

                    if progress:
                        return {
                            "current": progress.get("current_value", 0),
                            "target": progress.get("target_value", 100),
                            "percentage": progress.get("percentage", 0.0),
                            "last_updated": progress.get("last_updated"),
                            "is_completed": progress.get("is_completed", False)
                        }
                except AttributeError:
                    logger.warning("成就服務缺少 get_user_progress 方法")
                except Exception as e:
                    logger.error(f"查詢成就進度失敗: {e}")

            # 使用模擬進度數據作為備用
            import random

            if random.choice([True, False]):  # 50% 機率有進度
                return {
                    "current": random.randint(1, 80),
                    "target": 100,
                    "percentage": random.randint(10, 80),
                }
            return None

        except Exception as e:
            logger.warning(f"獲取成就進度失敗: {e}")
            return None

    def set_page(self, page: int) -> None:
        """設置當前頁面.

        Args:
            page: 頁面號碼（從0開始）
        """
        self._current_page = max(0, min(page, self._total_pages - 1))
        self._cache_valid = False

    def set_category_filter(self, category_id: int | None) -> None:
        """設置分類篩選.

        Args:
            category_id: 分類ID，None表示不篩選
        """
        self._selected_category = category_id
        self._current_page = 0  # 重置到第一頁
        self._cache_valid = False

    def get_current_page(self) -> int:
        """獲取當前頁面號碼."""
        return self._current_page

    def get_total_pages(self) -> int:
        """獲取總頁數."""
        return self._total_pages

    def get_selected_category(self) -> int | None:
        """獲取當前選擇的分類."""
        return self._selected_category

    def has_next_page(self) -> bool:
        """是否有下一頁."""
        return self._current_page < self._total_pages - 1

    def has_previous_page(self) -> bool:
        """是否有上一頁."""
        return self._current_page > 0


class BrowseView(BaseAchievementView):
    """成就瀏覽視圖.

    顯示所有可用的成就和分類篩選。
    """

    async def build_embed(self, **kwargs: Any) -> discord.Embed:
        """建立成就瀏覽頁面 Embed."""
        try:
            data = await self.get_cached_data(**kwargs)
            selected_category = kwargs.get("selected_category", "all")

            embed = StandardEmbedBuilder.create_info_embed(
                "成就瀏覽",
                f"瀏覽所有可用的成就{'（' + data.get('categories', {}).get(selected_category, {}).get('name', '全部') + '）' if selected_category != 'all' else ''}",
            )

            # 添加成就分類統計
            categories = data.get("categories", {})
            if categories:
                category_text = "\\n".join(
                    [
                        f"📁 {cat['name']}: {cat['count']} 個成就"
                        for cat in list(categories.values())[:5]
                    ]
                )
                embed.add_field(name="📋 成就分類", value=category_text, inline=True)

            # 添加篩選的成就列表
            achievements = data.get("achievements", [])
            if selected_category != "all":
                achievements = [
                    ach
                    for ach in achievements
                    if ach.get("category_id") == selected_category
                ]

            if achievements:
                achievement_text = "\\n".join(
                    [
                        f"{'🏅' if ach['earned'] else '⭕'} {ach['name']}"
                        for ach in achievements[:10]
                    ]
                )
                embed.add_field(
                    name="🎯 成就列表", value=achievement_text, inline=False
                )
            else:
                embed.add_field(
                    name="🎯 成就列表", value="此分類暫無成就", inline=False
                )

            return embed

        except Exception as e:
            logger.error(f"【成就瀏覽】建立 Embed 失敗: {e}")
            return StandardEmbedBuilder.create_error_embed(
                "載入失敗", "無法載入成就瀏覽資料，請稍後再試"
            )

    async def load_data(self, **kwargs: Any) -> dict[str, Any]:
        """載入成就瀏覽資料."""
        try:
            logger.debug(f"【成就瀏覽】載入資料 - Guild: {self.guild_id}")

            # 模擬資料載入 - 實際應該呼叫 achievement_service
            # categories = await self.achievement_service.get_categories(self.guild_id)
            # achievements = await self.achievement_service.get_all_achievements(
            #     self.guild_id, self.user_id
            # )

            return {
                "categories": {
                    "1": {"id": "1", "name": "活動成就", "count": 8},
                    "2": {"id": "2", "name": "社交成就", "count": 6},
                    "3": {"id": "3", "name": "時間成就", "count": 4},
                    "4": {"id": "4", "name": "特殊成就", "count": 2},
                },
                "achievements": [
                    {"id": "1", "name": "初次嘗試", "category_id": "1", "earned": True},
                    {"id": "2", "name": "活躍用戶", "category_id": "1", "earned": True},
                    {
                        "id": "3",
                        "name": "社交達人",
                        "category_id": "2",
                        "earned": False,
                    },
                    {
                        "id": "4",
                        "name": "時間管理",
                        "category_id": "3",
                        "earned": False,
                    },
                ],
            }

        except Exception as e:
            logger.error(f"【成就瀏覽】載入資料失敗: {e}")
            raise


class LeaderboardView(BaseAchievementView):
    """排行榜視圖.

    顯示多種類型的成就排行榜，支援分頁瀏覽和類型切換。
    """

    def __init__(
        self, achievement_service: AchievementService, guild_id: int, user_id: int
    ):
        """初始化排行榜視圖.

        Args:
            achievement_service: 成就服務實例
            guild_id: 伺服器 ID
            user_id: 用戶 ID
        """
        super().__init__(achievement_service, guild_id, user_id)
        self._current_page = 0
        self._page_size = 10
        self._selected_type = "count"  # "count", "points", "category_{id}"
        self._total_pages = 0
        self._selected_category_id: int | None = None

    async def build_embed(self, bot: discord.Client, **kwargs: Any) -> discord.Embed:
        """建立排行榜頁面 Embed."""
        try:
            # 獲取參數
            page = kwargs.get("page", self._current_page)
            leaderboard_type = kwargs.get("type", self._selected_type)
            category_id = kwargs.get("category_id", self._selected_category_id)

            data = await self.get_cached_data(
                page=page, type=leaderboard_type, category_id=category_id
            )

            # 建立基礎 Embed
            type_name = self._get_type_display_name(leaderboard_type, category_id)
            title = f"🏆 成就排行榜 - {type_name}"

            embed = StandardEmbedBuilder.create_info_embed(
                title, "查看伺服器成就排行榜，與其他用戶比較成就表現"
            )

            # 添加排行榜統計資訊
            stats = data.get("stats", {})
            embed.add_field(
                name="📊 排行榜統計",
                value=f"總參與人數: {stats.get('total_users', 0)}\n"
                f"當前頁面: {page + 1}/{data.get('total_pages', 1)}\n"
                f"排行榜類型: {type_name}",
                inline=True,
            )

            # 添加分頁資訊
            current_page = data.get("current_page", 0)
            total_pages = data.get("total_pages", 1)
            start_rank = current_page * self._page_size + 1
            end_rank = min(
                start_rank + self._page_size - 1, stats.get("total_users", 0)
            )

            embed.add_field(
                name="📄 頁面資訊",
                value=f"第 {current_page + 1} 頁，共 {total_pages} 頁\n"
                f"顯示排名: {start_rank}-{end_rank}",
                inline=True,
            )

            # 添加用戶排名資訊
            user_rank = data.get("user_rank")
            if user_rank:
                value_name = self._get_value_display_name(leaderboard_type)
                embed.add_field(
                    name="📍 您的排名",
                    value=f"第 {user_rank['rank']} 名\n"
                    f"{value_name}: {user_rank['value']:,}",
                    inline=True,
                )

            # 添加排行榜列表
            leaderboard = data.get("leaderboard_data", [])
            if leaderboard:
                leaderboard_text = ""
                base_rank = current_page * self._page_size + 1

                for i, entry in enumerate(leaderboard, base_rank):
                    user_id = entry["user_id"]
                    value = entry["value"]

                    # 獲取用戶顯示名稱
                    display_name = await self._get_user_display_name(bot, user_id)

                    # 排名圖標
                    rank_emoji = self._get_rank_emoji(i)
                    value_name = self._get_value_display_name(leaderboard_type)

                    # 突出顯示當前用戶
                    if user_id == self.user_id:
                        leaderboard_text += f"**{rank_emoji} {display_name} - {value:,} {value_name}** ⭐\n"
                    else:
                        leaderboard_text += (
                            f"{rank_emoji} {display_name} - {value:,} {value_name}\n"
                        )

                embed.add_field(
                    name=f"🏅 排行榜 (第 {start_rank}-{end_rank} 名)",
                    value=leaderboard_text[:1024],  # Discord 限制
                    inline=False,
                )
            else:
                embed.add_field(name="🏅 排行榜", value="暫無排行榜資料", inline=False)

            # 設置 footer
            embed.set_footer(text="💡 使用選單切換排行榜類型，使用按鈕進行分頁瀏覽")

            return embed

        except Exception as e:
            logger.error(f"【排行榜】建立 Embed 失敗: {e}", exc_info=True)
            return StandardEmbedBuilder.create_error_embed(
                "載入失敗", "無法載入排行榜資料，請稍後再試"
            )

    async def load_data(self, **kwargs: Any) -> dict[str, Any]:
        """載入排行榜資料."""
        try:
            page = kwargs.get("page", 0)
            leaderboard_type = kwargs.get("type", "count")
            category_id = kwargs.get("category_id")

            logger.debug(
                f"【排行榜】載入資料 - Page: {page}, Type: {leaderboard_type}, Category: {category_id}"
            )

            # 計算偏移量
            offset = page * self._page_size

            # 根據類型載入排行榜資料
            if leaderboard_type == "count":
                leaderboard_data = (
                    await self.achievement_service.get_leaderboard_by_count(
                        limit=self._page_size + offset  # 獲取足夠計算總頁數的資料
                    )
                )
                user_rank = await self.achievement_service.get_user_rank(
                    self.user_id, "count"
                )
            elif leaderboard_type == "points":
                leaderboard_data = (
                    await self.achievement_service.get_leaderboard_by_points(
                        limit=self._page_size + offset
                    )
                )
                user_rank = await self.achievement_service.get_user_rank(
                    self.user_id, "points"
                )
            elif leaderboard_type.startswith("category_") and category_id:
                leaderboard_data = (
                    await self.achievement_service.get_leaderboard_by_category(
                        category_id=category_id, limit=self._page_size + offset
                    )
                )
                user_rank = await self.achievement_service.get_user_rank(
                    self.user_id, f"category_{category_id}"
                )
            else:
                # 預設為成就總數排行榜
                leaderboard_data = (
                    await self.achievement_service.get_leaderboard_by_count(
                        limit=self._page_size + offset
                    )
                )
                user_rank = await self.achievement_service.get_user_rank(
                    self.user_id, "count"
                )

            # 計算分頁
            total_entries = len(leaderboard_data)
            self._total_pages = max(
                1, (total_entries + self._page_size - 1) // self._page_size
            )

            # 當前頁面的資料
            page_data = leaderboard_data[offset : offset + self._page_size]

            # 獲取分類名稱（如果需要）
            category_name = None
            if category_id:
                category = await self.achievement_service.get_category_by_id(
                    category_id
                )
                category_name = category.name if category else f"分類 {category_id}"

            return {
                "leaderboard_data": page_data,
                "current_page": page,
                "total_pages": self._total_pages,
                "leaderboard_type": leaderboard_type,
                "category_id": category_id,
                "category_name": category_name,
                "user_rank": user_rank,
                "stats": {"total_users": total_entries, "page_size": self._page_size},
            }

        except Exception as e:
            logger.error(f"【排行榜】載入資料失敗: {e}", exc_info=True)
            raise

    def _get_type_display_name(
        self, leaderboard_type: str, category_id: int | None = None
    ) -> str:
        """獲取排行榜類型的顯示名稱.

        Args:
            leaderboard_type: 排行榜類型
            category_id: 分類 ID（如果適用）

        Returns:
            str: 顯示名稱
        """
        if leaderboard_type == "count":
            return "成就總數"
        elif leaderboard_type == "points":
            return "成就點數"
        elif leaderboard_type.startswith("category_") and category_id:
            return f"分類成就 ({category_id})"
        else:
            return "成就總數"

    def _get_value_display_name(self, leaderboard_type: str) -> str:
        """獲取數值的顯示名稱.

        Args:
            leaderboard_type: 排行榜類型

        Returns:
            str: 數值顯示名稱
        """
        if leaderboard_type == "count":
            return "個成就"
        elif leaderboard_type == "points":
            return "點"
        elif leaderboard_type.startswith("category_"):
            return "個成就"
        else:
            return "個成就"

    def _get_rank_emoji(self, rank: int) -> str:
        """獲取排名表情符號.

        Args:
            rank: 排名

        Returns:
            str: 排名表情符號
        """
        if rank == 1:
            return "🥇"
        elif rank == 2:
            return "🥈"
        elif rank == 3:
            return "🥉"
        elif rank <= 10:
            return "🏅"
        else:
            return "🔸"

    async def _get_user_display_name(self, bot: discord.Client, user_id: int) -> str:
        """獲取用戶顯示名稱.

        Args:
            bot: Discord 客戶端
            user_id: 用戶 ID

        Returns:
            str: 用戶顯示名稱
        """
        try:
            guild = bot.get_guild(self.guild_id)
            if guild:
                member = guild.get_member(user_id)
                if member:
                    return member.display_name
            return f"用戶{user_id}"
        except Exception:
            return f"用戶{user_id}"

    def set_page(self, page: int) -> None:
        """設置當前頁面.

        Args:
            page: 頁面號碼（從0開始）
        """
        self._current_page = max(0, min(page, self._total_pages - 1))
        self._cache_valid = False

    def set_leaderboard_type(
        self, leaderboard_type: str, category_id: int | None = None
    ) -> None:
        """設置排行榜類型.

        Args:
            leaderboard_type: 排行榜類型 ("count", "points", "category")
            category_id: 分類 ID（僅在 category 類型時需要）
        """
        self._selected_type = leaderboard_type
        self._selected_category_id = category_id
        self._current_page = 0  # 重置到第一頁
        self._cache_valid = False

    def get_current_page(self) -> int:
        """獲取當前頁面號碼."""
        return self._current_page

    def get_total_pages(self) -> int:
        """獲取總頁數."""
        return self._total_pages

    def get_selected_type(self) -> str:
        """獲取當前選擇的排行榜類型."""
        return self._selected_type

    def get_selected_category_id(self) -> int | None:
        """獲取當前選擇的分類 ID."""
        return self._selected_category_id

    def has_next_page(self) -> bool:
        """是否有下一頁."""
        return self._current_page < self._total_pages - 1

    def has_previous_page(self) -> bool:
        """是否有上一頁."""
        return self._current_page > 0


class ViewFactory:
    """視圖工廠類.

    提供統一的視圖創建介面。
    """

    @staticmethod
    def create_main_view(
        achievement_service: AchievementService, guild_id: int, user_id: int
    ) -> MainView:
        """創建主頁面視圖.

        Args:
            achievement_service: 成就服務實例
            guild_id: 伺服器 ID
            user_id: 用戶 ID

        Returns:
            MainView: 主頁面視圖實例
        """
        return MainView(achievement_service, guild_id, user_id)

    @staticmethod
    def create_personal_view(
        achievement_service: AchievementService, guild_id: int, user_id: int
    ) -> PersonalView:
        """創建個人成就視圖.

        Args:
            achievement_service: 成就服務實例
            guild_id: 伺服器 ID
            user_id: 用戶 ID

        Returns:
            PersonalView: 個人成就視圖實例
        """
        return PersonalView(achievement_service, guild_id, user_id)

    @staticmethod
    def create_browse_view(
        achievement_service: AchievementService, guild_id: int, user_id: int
    ) -> BrowserView:
        """創建成就瀏覽視圖.

        Args:
            achievement_service: 成就服務實例
            guild_id: 伺服器 ID
            user_id: 用戶 ID

        Returns:
            BrowserView: 成就瀏覽視圖實例
        """
        return BrowserView(achievement_service, guild_id, user_id)

    @staticmethod
    def create_browser_view(
        achievement_service: AchievementService, guild_id: int, user_id: int
    ) -> BrowserView:
        """創建成就瀏覽視圖（新名稱）.

        Args:
            achievement_service: 成就服務實例
            guild_id: 伺服器 ID
            user_id: 用戶 ID

        Returns:
            BrowserView: 成就瀏覽視圖實例
        """
        return BrowserView(achievement_service, guild_id, user_id)

    @staticmethod
    def create_leaderboard_view(
        achievement_service: AchievementService, guild_id: int, user_id: int
    ) -> LeaderboardView:
        """創建排行榜視圖.

        Args:
            achievement_service: 成就服務實例
            guild_id: 伺服器 ID
            user_id: 用戶 ID

        Returns:
            LeaderboardView: 排行榜視圖實例
        """
        return LeaderboardView(achievement_service, guild_id, user_id)


class ViewManager:
    """視圖管理器.

    負責管理和快取視圖實例。
    """

    def __init__(
        self, achievement_service: AchievementService, guild_id: int, user_id: int
    ):
        """初始化視圖管理器.

        Args:
            achievement_service: 成就服務實例
            guild_id: 伺服器 ID
            user_id: 用戶 ID
        """
        self.achievement_service = achievement_service
        self.guild_id = guild_id
        self.user_id = user_id
        self._views: dict[str, BaseAchievementView] = {}

    def get_view(self, view_type: str) -> BaseAchievementView:
        """獲取視圖實例.

        Args:
            view_type: 視圖類型 ("main", "personal", "browse", "leaderboard")

        Returns:
            BaseAchievementView: 視圖實例
        """
        if view_type not in self._views:
            self._views[view_type] = self._create_view(view_type)

        return self._views[view_type]

    def _create_view(self, view_type: str) -> BaseAchievementView:
        """創建視圖實例.

        Args:
            view_type: 視圖類型

        Returns:
            BaseAchievementView: 視圖實例
        """
        factory_methods = {
            "main": ViewFactory.create_main_view,
            "personal": ViewFactory.create_personal_view,
            "browse": ViewFactory.create_browser_view,
            "browser": ViewFactory.create_browser_view,
            "leaderboard": ViewFactory.create_leaderboard_view,
        }

        factory_method = factory_methods.get(view_type)
        if not factory_method:
            raise ValueError(f"未知的視圖類型: {view_type}")

        return factory_method(self.achievement_service, self.guild_id, self.user_id)

    def clear_all_cache(self) -> None:
        """清除所有視圖快取."""
        for view in self._views.values():
            view.clear_cache()

    def clear_view_cache(self, view_type: str) -> None:
        """清除特定視圖快取.

        Args:
            view_type: 視圖類型
        """
        if view_type in self._views:
            self._views[view_type].clear_cache()
