"""成就系統主面板控制器.

提供成就系統的 Discord UI 介面,包含:
- 我的成就頁面
- 成就瀏覽頁面
- 排行榜頁面
- 頁面導航系統
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import discord

from src.cogs.core.base_cog import StandardEmbedBuilder

from .components import ComponentFactory
from .views import ViewManager

if TYPE_CHECKING:
    from discord.ext import commands

    from ..services.achievement_service import AchievementService

logger = logging.getLogger(__name__)

class AchievementPanel(discord.ui.View):
    """成就系統主面板控制器.

    負責管理成就系統的 Discord UI 介面:
    - 頁面導航和狀態管理
    - 用戶互動處理
    - 資料載入和快取
    - 錯誤處理和恢復
    """

    def __init__(
        self,
        bot: commands.Bot,
        achievement_service: AchievementService,
        guild_id: int,
        user_id: int,
        *,
        timeout: float = 300.0,
    ):
        """初始化成就面板.

        Args:
            bot: Discord 機器人實例
            achievement_service: 成就服務實例
            guild_id: 伺服器 ID
            user_id: 用戶 ID
            timeout: 面板超時時間(秒)
        """
        super().__init__(timeout=timeout)

        self.bot = bot
        self.achievement_service = achievement_service
        self.guild_id = guild_id
        self.user_id = user_id

        # 初始化視圖管理器
        self.view_manager = ViewManager(
            achievement_service=achievement_service, guild_id=guild_id, user_id=user_id
        )

        # 頁面狀態
        self.current_page = "main"
        self._page_data: dict[str, Any] = {}

        # Discord 訊息參考
        self.message: discord.Message | None = None

        # 設置初始組件
        self._setup_main_components()

        logger.debug(f"[成就面板]初始化完成 - Guild: {guild_id}, User: {user_id}")

    def _setup_main_components(self) -> None:
        """設置主頁面組件."""
        # 清除所有組件
        self.clear_items()

        # 頁面選擇器
        self.add_item(ComponentFactory.create_page_selector(self))

        # 控制按鈕
        self.add_item(ComponentFactory.create_refresh_button(self))
        self.add_item(ComponentFactory.create_close_button(self))

    async def _setup_main_components_async(self) -> None:
        """設置主頁面組件(異步版本)."""
        # 清除所有組件
        self.clear_items()

        # 頁面選擇器
        self.add_item(ComponentFactory.create_page_selector(self))

        # 控制按鈕
        self.add_item(ComponentFactory.create_refresh_button(self))
        self.add_item(ComponentFactory.create_close_button(self))

    def _setup_personal_components(self) -> None:
        """設置個人成就頁面組件."""
        # 清除所有組件
        self.clear_items()

        # 獲取個人視圖
        personal_view = self.view_manager.get_view("personal")

        # 分頁按鈕
        pagination_buttons = ComponentFactory.create_pagination_buttons(
            self,
            has_prev=personal_view.has_previous_page(),
            has_next=personal_view.has_next_page(),
        )
        for button in pagination_buttons:
            self.add_item(button)

        categories = self._get_user_categories_sync()
        if categories:
            self.add_item(
                ComponentFactory.create_personal_category_selector(self, categories)
            )

        # 控制按鈕
        self.add_item(
            ComponentFactory.create_navigation_button(self, "返回主頁", "main", "📤")
        )
        self.add_item(ComponentFactory.create_refresh_button(self))
        self.add_item(ComponentFactory.create_close_button(self))

    async def _setup_personal_components_async(self) -> None:
        """設置個人成就頁面組件(異步版本)."""
        # 清除所有組件
        self.clear_items()

        # 獲取個人視圖
        personal_view = self.view_manager.get_view("personal")

        # 分頁按鈕
        pagination_buttons = ComponentFactory.create_pagination_buttons(
            self,
            has_prev=personal_view.has_previous_page(),
            has_next=personal_view.has_next_page(),
        )
        for button in pagination_buttons:
            self.add_item(button)

        categories = await self._get_user_categories_async()
        if categories:
            self.add_item(
                ComponentFactory.create_personal_category_selector(self, categories)
            )

        # 控制按鈕
        self.add_item(
            ComponentFactory.create_navigation_button(self, "返回主頁", "main", "📤")
        )
        self.add_item(ComponentFactory.create_refresh_button(self))
        self.add_item(ComponentFactory.create_close_button(self))

    def _get_user_categories_sync(self) -> list[dict[str, Any]]:
        """獲取用戶成就分類(同步版本,用於UI組件初始化).

        Returns:
            list[dict]: 分類列表
        """
        # 由於UI組件初始化需要同步數據,返回空列表
        # 實際數據將在異步方法中獲取
        logger.debug("同步方法返回空分類列表,將在異步方法中獲取真實數據")
        return []

    async def _get_user_categories_async(self) -> list[dict[str, Any]]:
        """獲取用戶成就分類(實作真實查詢).

        Returns:
            list[dict]: 分類列表
        """
        # 實作真實的分類查詢
        try:
            if hasattr(self, "achievement_service") and self.achievement_service:
                # 從成就服務獲取真實的分類數據
                categories = (
                    await self.achievement_service.get_user_achievement_categories(
                        user_id=self.user_id, guild_id=getattr(self, "guild_id", None)
                    )
                )

                # 轉換為預期格式
                result = []
                for category in categories:
                    result.append(
                        {
                            "id": category.get("id"),
                            "name": category.get("name", "未分類"),
                            "user_achievements_count": category.get(
                                "user_achievements_count", 0
                            ),
                        }
                    )

                return result if result else self._get_no_data_categories()
            else:
                logger.warning("成就服務不可用,顯示無數據提示")
                return self._get_no_data_categories()
        except Exception as e:
            logger.error(f"獲取用戶分類失敗: {e}")
            return self._get_no_data_categories()

    async def change_page(self, interaction: discord.Interaction, page: str) -> None:
        """切換頁面.

        Args:
            interaction: Discord 互動
            page: 目標頁面
        """
        try:
            # 檢查互動是否已經回應
            if interaction.response.is_done():
                logger.warning(f"[成就面板]互動已回應,無法切換到頁面: {page}")
                return

            self.current_page = page

            if page == "main":
                await self._setup_main_components_async()
                embed = await self._build_main_embed()
            elif page == "personal":
                await self._setup_personal_components_async()
                embed = await self._build_personal_embed()
            elif page == "browse":
                await self._setup_browse_components_async()
                embed = await self._build_browse_embed()
            elif page == "leaderboard":
                await self._setup_leaderboard_components()
                embed = await self._build_leaderboard_embed()
            else:
                raise ValueError(f"未知的頁面: {page}")

            await interaction.response.edit_message(embed=embed, view=self)

            logger.debug(f"[成就面板]頁面切換成功: {page}")

        except Exception as e:
            logger.error(f"[成就面板]頁面切換失敗: {e}")
            await self.on_error(interaction, e, None)

    async def _build_main_embed(self) -> discord.Embed:
        """建立主頁面 Embed."""
        main_view = self.view_manager.get_view("main")
        return await main_view.build_embed(bot=self.bot)

    async def _build_personal_embed(self) -> discord.Embed:
        """建立個人成就頁面 Embed."""
        personal_view = self.view_manager.get_view("personal")
        return await personal_view.build_embed()

    async def _build_browse_embed(self) -> discord.Embed:
        """建立成就瀏覽頁面 Embed."""
        browse_view = self.view_manager.get_view("browse")
        return await browse_view.build_embed()

    async def _build_leaderboard_embed(self) -> discord.Embed:
        """建立排行榜頁面 Embed."""
        leaderboard_view = self.view_manager.get_view("leaderboard")
        return await leaderboard_view.build_embed(bot=self.bot)

    def _setup_browse_components(self) -> None:
        """設置成就瀏覽頁面組件."""
        self.clear_items()

        # 獲取瀏覽視圖
        browse_view = self.view_manager.get_view("browse")

        categories = self._get_browse_categories_sync()
        if categories:
            self.add_item(
                ComponentFactory.create_browser_category_selector(self, categories)
            )

        # 分頁按鈕
        pagination_buttons = ComponentFactory.create_browser_pagination_buttons(
            self,
            has_prev=browse_view.has_previous_page(),
            has_next=browse_view.has_next_page(),
        )
        for button in pagination_buttons:
            self.add_item(button)

        # 控制按鈕
        self.add_item(
            ComponentFactory.create_navigation_button(self, "返回主頁", "main", "📤")
        )
        self.add_item(ComponentFactory.create_refresh_button(self))
        self.add_item(ComponentFactory.create_close_button(self))

    async def _setup_browse_components_async(self) -> None:
        """設置成就瀏覽頁面組件(異步版本)."""
        self.clear_items()

        # 獲取瀏覽視圖
        browse_view = self.view_manager.get_view("browse")

        categories = await self._get_browse_categories_async()
        if categories:
            self.add_item(
                ComponentFactory.create_browser_category_selector(self, categories)
            )

        # 分頁按鈕
        pagination_buttons = ComponentFactory.create_browser_pagination_buttons(
            self,
            has_prev=browse_view.has_previous_page(),
            has_next=browse_view.has_next_page(),
        )
        for button in pagination_buttons:
            self.add_item(button)

        # 控制按鈕
        self.add_item(
            ComponentFactory.create_navigation_button(self, "返回主頁", "main", "📤")
        )
        self.add_item(ComponentFactory.create_refresh_button(self))
        self.add_item(ComponentFactory.create_close_button(self))

    def _get_browse_categories_sync(self) -> list[dict[str, Any]]:
        """獲取瀏覽頁面分類列表(同步版本,用於UI組件初始化).

        Returns:
            list[dict]: 分類列表
        """
        # 由於UI組件初始化需要同步數據,返回空列表
        # 實際數據將在異步方法中獲取
        logger.debug("同步方法返回空分類列表,將在異步方法中獲取真實數據")
        return []

    async def _get_browse_categories_async(self) -> list[dict[str, Any]]:
        """獲取瀏覽頁面分類列表(實作真實查詢).

        Returns:
            list[dict]: 分類列表
        """
        # 實作真實的分類查詢
        try:
            if hasattr(self, "achievement_service") and self.achievement_service:
                # 從成就服務獲取所有可用分類
                categories = (
                    await self.achievement_service.get_all_achievement_categories(
                        guild_id=getattr(self, "guild_id", None)
                    )
                )

                # 轉換為瀏覽頁面需要的格式
                result = []
                for category in categories:
                    result.append(
                        {
                            "id": category.get("id"),
                            "name": category.get("name", "未分類"),
                            "count": category.get("achievement_count", 0),
                            "icon_emoji": category.get("icon_emoji", "📋"),
                        }
                    )

                return result if result else self._get_no_data_categories()
            else:
                logger.warning("成就服務不可用,顯示無數據提示")
                return self._get_no_data_categories()
        except Exception as e:
            logger.error(f"獲取瀏覽分類失敗: {e}")
            return self._get_no_data_categories()

    def _get_no_data_categories(self) -> list[dict]:
        """當無法獲取真實數據時的提示."""
        return [
            {
                "id": "no_data",
                "name": "暫無分類數據",
                "count": 0,
                "icon_emoji": "📭",
                "description": "目前沒有可用的成就分類數據",
            }
        ]

    async def _setup_leaderboard_components(self) -> None:
        """設置排行榜頁面組件."""
        self.clear_items()

        try:
            # 獲取排行榜視圖
            leaderboard_view = self.view_manager.get_view("leaderboard")

            categories = await self.achievement_service.list_categories(
                active_only=True
            )
            category_data = [
                {
                    "id": category.id,
                    "name": category.name,
                    "count": len(
                        await self.achievement_service.list_achievements(
                            category_id=category.id, active_only=True
                        )
                    ),
                }
                for category in categories[:5]  # 限制最多5個分類
            ]

            # 排行榜類型選擇器
            self.add_item(
                ComponentFactory.create_leaderboard_type_selector(self, category_data)
            )

            # 分頁按鈕
            has_prev = leaderboard_view.has_previous_page()
            has_next = leaderboard_view.has_next_page()

            pagination_buttons = ComponentFactory.create_leaderboard_pagination_buttons(
                self, has_prev, has_next
            )
            for button in pagination_buttons:
                self.add_item(button)

            # 控制按鈕
            self.add_item(
                ComponentFactory.create_navigation_button(
                    self, "返回主頁", "main", "📤"
                )
            )
            self.add_item(ComponentFactory.create_refresh_button(self))
            self.add_item(ComponentFactory.create_close_button(self))

        except Exception as e:
            logger.error(f"[排行榜]設置組件失敗: {e}", exc_info=True)
            # 退回到基本控制按鈕
            self.clear_items()
            self.add_item(
                ComponentFactory.create_navigation_button(
                    self, "返回主頁", "main", "📤"
                )
            )
            self.add_item(ComponentFactory.create_refresh_button(self))
            self.add_item(ComponentFactory.create_close_button(self))

    def get_page_data(self, page: str) -> dict[str, Any] | None:
        """獲取頁面數據.

        Args:
            page: 頁面名稱

        Returns:
            dict | None: 頁面數據或 None
        """
        return self._page_data.get(page)

    def set_page_data(self, page: str, data: dict[str, Any]) -> None:
        """設置頁面數據.

        Args:
            page: 頁面名稱
            data: 頁面數據
        """
        self._page_data[page] = data

    async def refresh_callback(self, interaction: discord.Interaction) -> None:
        """重新整理回調."""
        try:
            # 清除視圖快取
            self.view_manager.clear_all_cache()

            if self.current_page == "personal":
                await self._setup_personal_components_async()
            elif self.current_page == "browse":
                await self._setup_browse_components_async()
            elif self.current_page == "leaderboard":
                await self._setup_leaderboard_components()
            elif self.current_page == "main":
                await self._setup_main_components_async()

            # 重新載入當前頁面
            embed = await self._get_current_embed()
            await interaction.response.edit_message(embed=embed, view=self)

            logger.debug("[成就面板]重新整理完成")

        except Exception as e:
            logger.error(f"[成就面板]重新整理失敗: {e}")
            await self.on_error(interaction, e, None)

    async def close_callback(self, interaction: discord.Interaction) -> None:
        """關閉回調."""
        try:
            self.stop()

            embed = StandardEmbedBuilder.create_success_embed(
                "成就面板已關閉", "感謝使用成就系統!"
            )

            await interaction.response.edit_message(embed=embed, view=None)

            logger.debug("[成就面板]面板已關閉")

        except Exception as e:
            logger.error(f"[成就面板]關閉失敗: {e}")

    async def _get_current_embed(self) -> discord.Embed:
        """獲取當前頁面的 Embed."""
        if self.current_page == "main":
            return await self._build_main_embed()
        elif self.current_page == "personal":
            return await self._build_personal_embed()
        elif self.current_page == "browse":
            return await self._build_browse_embed()
        elif self.current_page == "leaderboard":
            return await self._build_leaderboard_embed()
        else:
            return StandardEmbedBuilder.create_error_embed(
                "頁面錯誤", f"未知的頁面: {self.current_page}"
            )

    async def start(self, interaction: discord.Interaction) -> None:
        """啟動面板."""
        try:
            embed = await self._build_main_embed()

            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, view=self, ephemeral=True)
            else:
                await interaction.response.send_message(
                    embed=embed, view=self, ephemeral=True
                )

            self.message = await interaction.original_response()

            logger.info(
                f"[成就面板]啟動完成 - Guild: {self.guild_id}, User: {self.user_id}"
            )

        except Exception as e:
            logger.error(f"[成就面板]啟動失敗: {e}")
            raise

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        _item: discord.ui.Item | None,
    ) -> None:
        """錯誤處理."""
        try:
            error_embed = StandardEmbedBuilder.create_error_embed(
                "操作失敗", f"發生錯誤,請稍後再試: {str(error)[:100]}"
            )

            if interaction.response.is_done():
                await interaction.followup.send(embed=error_embed, ephemeral=True)
            else:
                await interaction.response.send_message(
                    embed=error_embed, ephemeral=True
                )

            logger.error(f"[成就面板]操作錯誤: {error}", exc_info=True)

        except Exception as e:
            logger.error(f"[成就面板]錯誤處理失敗: {e}")
