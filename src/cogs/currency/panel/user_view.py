"""Currency User Panel View.

貨幣系統用戶端面板視圖,提供:
- 個人餘額顯示
- 轉帳功能
- 排行榜查看
- 伺服器經濟統計概覽
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord

from src.cogs.core.base_cog import StandardEmbedBuilder, StandardPanelView

from .components.buttons import (
    CloseButton,
    LeaderboardButton,
    RefreshButton,
    TransferButton,
)
from .embeds.leaderboard_embed import LeaderboardEmbedRenderer

# 延遲導入按鈕組件以避免循環導入
from .embeds.main_embed import MainEmbedRenderer

if TYPE_CHECKING:
    from src.cogs.currency.service.currency_service import CurrencyService

logger = logging.getLogger(__name__)

class CurrencyPanelView(StandardPanelView):
    """
    貨幣系統用戶端面板視圖

    提供用戶友善的貨幣管理介面, 支援:
    - 餘額查看與統計
    - 快速轉帳操作
    - 排行榜分頁瀏覽
    - 自己排名快速搜尋
    """

    def __init__(
        self,
        currency_service: CurrencyService,
        *,
        timeout: float = 300.0,
        author_id: int,
        guild_id: int,
    ):
        """
        初始化貨幣用戶端面板

        Args:
            currency_service: 貨幣服務實例
            timeout: 面板超時時間(秒)
            author_id: 面板擁有者ID
            guild_id: 伺服器ID
        """
        super().__init__(
            timeout=timeout,
            author_id=author_id,
            guild_id=guild_id,
        )

        self.currency_service = currency_service
        self.current_leaderboard_page = 0
        self.leaderboard_per_page = 10
        self.user_balance = 0
        self.user_rank_info = None
        self.guild_stats = None

        # 設置頁面
        self._setup_currency_pages()

    def _setup_currency_pages(self):
        """設置貨幣面板頁面"""
        self.pages = {
            "main": {
                "title": "貨幣面板",
                "description": "個人貨幣資訊與快速操作",
                "embed_builder": self.build_main_embed,
                "components": [],
            },
            "leaderboard": {
                "title": "排行榜",
                "description": "伺服器貨幣排行榜",
                "embed_builder": self.build_leaderboard_embed,
                "components": [],
            }
        }

    def _setup_components(self):
        """設置UI組件"""
        self.clear_items()

        if self.current_page == "main":
            # 主頁面組件
            self.add_item(TransferButton(
                style=discord.ButtonStyle.primary,
                custom_id="roas_currency_transfer"
            ))
            self.add_item(LeaderboardButton(
                style=discord.ButtonStyle.secondary,
                custom_id="roas_currency_leaderboard"
            ))
            self.add_item(RefreshButton(
                style=discord.ButtonStyle.secondary,
                custom_id="roas_currency_refresh"
            ))
            self.add_item(CloseButton(
                style=discord.ButtonStyle.danger,
                custom_id="roas_currency_close"
            ))

        elif self.current_page == "leaderboard":
            # 排行榜頁面組件
            self.add_item(self.create_standard_button(
                label="上一頁",
                style="secondary",
                emoji="⬅️",
                disabled=self.current_leaderboard_page <= 0,
                custom_id="roas_currency_prev_page",
                callback=self.prev_page_callback
            ))
            self.add_item(self.create_standard_button(
                label="下一頁",
                style="secondary",
                emoji="➡️",
                custom_id="roas_currency_next_page",
                callback=self.next_page_callback
            ))
            self.add_item(self.create_standard_button(
                label="我的排名",
                style="primary",
                emoji="📊",
                custom_id="roas_currency_my_rank",
                callback=self.my_rank_callback
            ))
            self.add_item(self.create_standard_button(
                label="返回主頁",
                style="secondary",
                emoji="🏠",
                custom_id="roas_currency_back_main",
                callback=self.back_to_main_callback
            ))
            self.add_item(CloseButton(
                style=discord.ButtonStyle.danger,
                custom_id="roas_currency_close_lb"
            ))

    async def start(self, interaction: discord.Interaction, page: str = "main"):
        """啟動面板並載入初始數據"""
        try:
            # 載入用戶數據
            await self._load_user_data()

            # 啟動面板
            await super().start(interaction, page)

        except Exception as e:
            logger.error(f"啟動貨幣面板失敗: {e}")
            await self._send_error_response(interaction, "載入貨幣面板時發生錯誤")

    async def _load_user_data(self):
        """載入用戶相關數據"""
        try:
            # 載入用戶餘額
            self.user_balance = await self.currency_service.get_balance(
                self.guild_id, self.author_id
            )

            # 載入用戶排名資訊
            self.user_rank_info = await self.currency_service.get_user_rank(
                self.guild_id, self.author_id
            )

            # 載入伺服器統計
            self.guild_stats = await self.currency_service.get_guild_statistics(
                self.guild_id
            )

        except Exception as e:
            logger.error(f"載入用戶數據失敗: {e}")
            # 設置預設值
            self.user_balance = 0
            self.user_rank_info = {"rank": 0, "percentile": 0, "total_users": 0}
            self.guild_stats = {}

    async def build_main_embed(self) -> discord.Embed:
        """構建主面板嵌入"""
        try:
            renderer = MainEmbedRenderer(
                user_balance=self.user_balance,
                user_rank_info=self.user_rank_info,
                guild_stats=self.guild_stats,
                user_id=self.author_id,
                guild_id=self.guild_id
            )
            return await renderer.render()

        except Exception as e:
            logger.error(f"構建主面板嵌入失敗: {e}")
            return StandardEmbedBuilder.create_error_embed(
                "載入錯誤", "無法載入貨幣面板,請稍後再試"
            )

    async def build_leaderboard_embed(self) -> discord.Embed:
        """構建排行榜嵌入"""
        try:
            # 載入排行榜數據
            offset = self.current_leaderboard_page * self.leaderboard_per_page
            leaderboard_data = await self.currency_service.get_leaderboard(
                self.guild_id,
                limit=self.leaderboard_per_page,
                offset=offset
            )

            renderer = LeaderboardEmbedRenderer(
                leaderboard_data=leaderboard_data,
                current_page=self.current_leaderboard_page,
                per_page=self.leaderboard_per_page,
                user_id=self.author_id,
                guild_id=self.guild_id
            )
            return await renderer.render()

        except Exception as e:
            logger.error(f"構建排行榜嵌入失敗: {e}")
            return StandardEmbedBuilder.create_error_embed(
                "載入錯誤", "無法載入排行榜,請稍後再試"
            )

    async def change_page(self, interaction: discord.Interaction, page: str):
        """切換頁面並重新設置組件"""
        await super().change_page(interaction, page)
        self._setup_components()

        # 更新訊息與組件
        embed = await self.get_current_embed()
        await interaction.edit_original_response(embed=embed, view=self)

    async def refresh_data_and_view(self, interaction: discord.Interaction):
        """刷新數據並更新視圖"""
        try:
            # 重新載入數據
            await self._load_user_data()

            # 重新設置組件
            self._setup_components()

            # 更新嵌入
            embed = await self.get_current_embed()
            await interaction.response.edit_message(embed=embed, view=self)

        except Exception as e:
            logger.error(f"刷新貨幣面板失敗: {e}")
            await self.on_error(interaction, e, None)

    # ================== 排行榜頁面回調 ==================

    async def prev_page_callback(self, interaction: discord.Interaction):
        """上一頁回調"""
        if self.current_leaderboard_page > 0:
            self.current_leaderboard_page -= 1
            await self.refresh_data_and_view(interaction)
        else:
            await interaction.response.defer()

    async def next_page_callback(self, interaction: discord.Interaction):
        """下一頁回調"""
        # 檢查是否還有下一頁
        offset = (self.current_leaderboard_page + 1) * self.leaderboard_per_page
        try:
            next_page_data = await self.currency_service.get_leaderboard(
                self.guild_id, limit=1, offset=offset
            )
            if next_page_data["entries"]:
                self.current_leaderboard_page += 1
                await self.refresh_data_and_view(interaction)
            else:
                await interaction.response.defer()
        except Exception as e:
            logger.error(f"檢查下一頁失敗: {e}")
            await interaction.response.defer()

    async def my_rank_callback(self, interaction: discord.Interaction):
        """我的排名回調 - 跳轉到包含自己的頁面"""
        try:
            if self.user_rank_info and self.user_rank_info["rank"] > 0:
                # 計算自己所在的頁面
                my_page = (self.user_rank_info["rank"] - 1) // self.leaderboard_per_page
                self.current_leaderboard_page = my_page
                await self.refresh_data_and_view(interaction)
            else:
                await self._send_info_response(interaction, "你尚未在排行榜中")

        except Exception as e:
            logger.error(f"跳轉到我的排名失敗: {e}")
            await self.on_error(interaction, e, None)

    async def back_to_main_callback(self, interaction: discord.Interaction):
        """返回主頁回調"""
        self.current_page = "main"
        await self.refresh_data_and_view(interaction)

    # ================== 快速刷新方法 ==================

    async def refresh_after_transfer(self, interaction: discord.Interaction):
        """轉帳後快速刷新(僅更新數據,不重新設置組件)"""
        try:
            # 僅重新載入用戶數據
            await self._load_user_data()

            # 更新當前頁面嵌入
            embed = await self.get_current_embed()

            # 如果互動尚未回應,則編輯原訊息
            if not interaction.response.is_done():
                await interaction.response.edit_message(embed=embed, view=self)
            else:
                await interaction.edit_original_response(embed=embed, view=self)

        except Exception as e:
            logger.error(f"轉帳後刷新失敗: {e}")
            # 不拋出錯誤,避免影響轉帳操作的成功回應
