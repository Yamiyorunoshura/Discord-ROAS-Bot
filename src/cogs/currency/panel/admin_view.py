"""Currency Admin Panel View.

貨幣系統管理員面板視圖,提供:
- 用戶餘額查看與修改
- 批量餘額操作
- 經濟統計與分析
- 交易記錄查詢與審計
- 分頁瀏覽功能
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord

from src.cogs.core.base_cog import StandardEmbedBuilder, StandardPanelView

# 延遲導入按鈕組件以避免循環導入
from .components.admin_buttons import (
    AuditRecordsButton,
    BalanceManageButton,
    BatchOperationButton,
    CloseButton,
    EconomicStatsButton,
    RefreshButton,
    UserSearchButton,
)
from .embeds.admin_embed import AdminEmbedRenderer
from .embeds.stats_embed import StatsEmbedRenderer

if TYPE_CHECKING:
    from src.cogs.currency.service.currency_service import CurrencyService

logger = logging.getLogger(__name__)


class CurrencyAdminPanelView(StandardPanelView):
    """
    貨幣系統管理員面板視圖

    提供管理員全面的貨幣管理介面, 支援:
    - 用戶餘額管理與搜尋
    - 批量餘額操作
    - 經濟統計與趨勢分析
    - 交易記錄審計與導出
    """

    def __init__(
        self,
        currency_service: CurrencyService,
        *,
        timeout: float = 600.0,  # 管理員面板較長超時時間
        author_id: int,
        guild_id: int,
    ):
        """
        初始化貨幣管理員面板

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
            admin_only=True,  # 僅限管理員
        )

        self.currency_service = currency_service
        self.current_users_page = 0
        self.users_per_page = 15
        self.current_audit_page = 0
        self.audit_per_page = 10

        # 數據緩存
        self.guild_stats = None
        self.users_list = []
        self.audit_records = []
        self.total_users_count = 0
        self.total_audit_count = 0

        # 設置頁面
        self._setup_admin_pages()

    def _setup_admin_pages(self):
        """設置管理員面板頁面"""
        self.pages = {
            "main": {
                "title": "管理員主控台",
                "description": "貨幣系統管理概覽",
                "embed_builder": self.build_main_embed,
                "components": [],
            },
            "users": {
                "title": "用戶管理",
                "description": "用戶餘額管理與搜尋",
                "embed_builder": self.build_users_embed,
                "components": [],
            },
            "stats": {
                "title": "經濟統計",
                "description": "伺服器經濟分析與趨勢",
                "embed_builder": self.build_stats_embed,
                "components": [],
            },
            "audit": {
                "title": "審計記錄",
                "description": "交易記錄查詢與審計",
                "embed_builder": self.build_audit_embed,
                "components": [],
            },
        }

    def _setup_components(self):
        """設置UI組件"""
        self.clear_items()

        if self.current_page == "main":
            # 主控台組件
            self.add_item(
                UserSearchButton(
                    style=discord.ButtonStyle.primary,
                    custom_id="roas_currency_admin_users",
                )
            )
            self.add_item(
                EconomicStatsButton(
                    style=discord.ButtonStyle.secondary,
                    custom_id="roas_currency_admin_stats",
                )
            )
            self.add_item(
                AuditRecordsButton(
                    style=discord.ButtonStyle.secondary,
                    custom_id="roas_currency_admin_audit",
                )
            )
            self.add_item(
                BatchOperationButton(
                    style=discord.ButtonStyle.danger,
                    custom_id="roas_currency_admin_batch",
                )
            )

        elif self.current_page == "users":
            # 用戶管理頁面組件
            self.add_item(
                BalanceManageButton(
                    style=discord.ButtonStyle.primary,
                    custom_id="roas_currency_admin_balance",
                )
            )
            self.add_item(
                self.create_standard_button(
                    label="搜尋用戶",
                    style="secondary",
                    emoji="🔍",
                    custom_id="roas_currency_admin_search",
                    callback=self.search_user_callback,
                )
            )
            self.add_item(
                self.create_standard_button(
                    label="上一頁",
                    style="secondary",
                    emoji="⬅️",
                    disabled=self.current_users_page <= 0,
                    custom_id="roas_currency_admin_users_prev",
                    callback=self.users_prev_page_callback,
                )
            )
            self.add_item(
                self.create_standard_button(
                    label="下一頁",
                    style="secondary",
                    emoji="➡️",
                    custom_id="roas_currency_admin_users_next",
                    callback=self.users_next_page_callback,
                )
            )
            self.add_item(
                self.create_standard_button(
                    label="返回主控台",
                    style="secondary",
                    emoji="🏠",
                    custom_id="roas_currency_admin_back_main",
                    callback=self.back_to_main_callback,
                )
            )

        elif self.current_page == "stats":
            # 經濟統計頁面組件
            self.add_item(
                self.create_standard_button(
                    label="刷新統計",
                    style="primary",
                    emoji="📊",
                    custom_id="roas_currency_admin_refresh_stats",
                    callback=self.refresh_stats_callback,
                )
            )
            self.add_item(
                self.create_standard_button(
                    label="導出報告",
                    style="secondary",
                    emoji="📄",
                    custom_id="roas_currency_admin_export_stats",
                    callback=self.export_stats_callback,
                )
            )
            self.add_item(
                self.create_standard_button(
                    label="返回主控台",
                    style="secondary",
                    emoji="🏠",
                    custom_id="roas_currency_admin_back_main_stats",
                    callback=self.back_to_main_callback,
                )
            )

        elif self.current_page == "audit":
            # 審計記錄頁面組件
            self.add_item(
                self.create_standard_button(
                    label="篩選記錄",
                    style="primary",
                    emoji="🔍",
                    custom_id="roas_currency_admin_filter_audit",
                    callback=self.filter_audit_callback,
                )
            )
            self.add_item(
                self.create_standard_button(
                    label="上一頁",
                    style="secondary",
                    emoji="⬅️",
                    disabled=self.current_audit_page <= 0,
                    custom_id="roas_currency_admin_audit_prev",
                    callback=self.audit_prev_page_callback,
                )
            )
            self.add_item(
                self.create_standard_button(
                    label="下一頁",
                    style="secondary",
                    emoji="➡️",
                    custom_id="roas_currency_admin_audit_next",
                    callback=self.audit_next_page_callback,
                )
            )
            self.add_item(
                self.create_standard_button(
                    label="導出記錄",
                    style="danger",
                    emoji="📥",
                    custom_id="roas_currency_admin_export_audit",
                    callback=self.export_audit_callback,
                )
            )
            self.add_item(
                self.create_standard_button(
                    label="返回主控台",
                    style="secondary",
                    emoji="🏠",
                    custom_id="roas_currency_admin_back_main_audit",
                    callback=self.back_to_main_callback,
                )
            )

        # 所有頁面都有的通用組件
        self.add_item(
            RefreshButton(
                style=discord.ButtonStyle.secondary,
                custom_id="roas_currency_admin_refresh",
            )
        )
        self.add_item(
            CloseButton(
                style=discord.ButtonStyle.danger, custom_id="roas_currency_admin_close"
            )
        )

    async def start(self, interaction: discord.Interaction, page: str = "main"):
        """啟動面板並載入初始數據"""
        try:
            # 載入管理員數據
            await self._load_admin_data()

            # 啟動面板
            await super().start(interaction, page)

        except Exception as e:
            logger.error(f"啟動管理員面板失敗: {e}")
            await self._send_error_response(interaction, "載入管理員面板時發生錯誤")

    async def _load_admin_data(self):
        """載入管理員相關數據"""
        try:
            # 載入伺服器統計
            self.guild_stats = await self.currency_service.get_guild_statistics(
                self.guild_id
            )

            await self._load_users_page()
            await self._load_audit_page()

        except Exception as e:
            logger.error(f"載入管理員數據失敗: {e}")
            # 設置預設值
            self.guild_stats = {}
            self.users_list = []
            self.audit_records = []

    async def _load_users_page(self):
        """載入用戶頁面數據"""
        try:
            # TODO: 實作獲取所有用戶餘額的API

            # 暫時使用排行榜數據代替
            offset = self.current_users_page * self.users_per_page
            leaderboard_data = await self.currency_service.get_leaderboard(
                self.guild_id, limit=self.users_per_page, offset=offset
            )
            self.users_list = leaderboard_data.get("entries", [])
            self.total_users_count = leaderboard_data.get("total_count", 0)

        except Exception as e:
            logger.error(f"載入用戶頁面數據失敗: {e}")
            self.users_list = []
            self.total_users_count = 0

    async def _load_audit_page(self):
        """載入審計頁面數據"""
        try:
            # TODO: 實作獲取交易記錄的API

            # 暫時設置空數據
            self.audit_records = []
            self.total_audit_count = 0

        except Exception as e:
            logger.error(f"載入審計頁面數據失敗: {e}")
            self.audit_records = []
            self.total_audit_count = 0

    async def build_main_embed(self) -> discord.Embed:
        """構建管理員主控台嵌入"""
        try:
            renderer = AdminEmbedRenderer(
                guild_stats=self.guild_stats,
                total_users=self.total_users_count,
                total_transactions=self.total_audit_count,
                admin_id=self.author_id,
                guild_id=self.guild_id,
            )
            return await renderer.render()

        except Exception as e:
            logger.error(f"構建管理員主控台嵌入失敗: {e}")
            return StandardEmbedBuilder.create_error_embed(
                "載入錯誤", "無法載入管理員控台,請稍後再試"
            )

    async def build_users_embed(self) -> discord.Embed:
        """構建用戶管理嵌入"""
        try:
            embed = discord.Embed(
                title="👥 用戶餘額管理",
                description=f"第 {self.current_users_page + 1} 頁 • 共 {self.total_users_count} 位用戶",
                color=discord.Color.blue(),
            )

            if not self.users_list:
                embed.add_field(
                    name="📝 用戶列表", value="沒有找到用戶資料", inline=False
                )
            else:
                user_lines = []
                for user in self.users_list:
                    user_id = user.get("user_id", 0)
                    balance = user.get("balance", 0)
                    rank = user.get("rank", 0)

                    user_lines.append(f"**{rank}.** 用戶 {user_id}: {balance:,} 貨幣")

                embed.add_field(
                    name="📊 用戶列表", value="\n".join(user_lines), inline=False
                )

            embed.add_field(
                name="🔧 管理操作",
                value=(
                    "💰 **餘額管理** - 修改用戶餘額\n"
                    "🔍 **搜尋用戶** - 按ID或名稱搜尋\n"
                    "📄 **分頁瀏覽** - 瀏覽所有用戶"
                ),
                inline=False,
            )

            return embed

        except Exception as e:
            logger.error(f"構建用戶管理嵌入失敗: {e}")
            return StandardEmbedBuilder.create_error_embed(
                "載入錯誤", "無法載入用戶管理頁面,請稍後再試"
            )

    async def build_stats_embed(self) -> discord.Embed:
        """構建經濟統計嵌入"""
        try:
            renderer = StatsEmbedRenderer(
                guild_stats=self.guild_stats, guild_id=self.guild_id
            )
            return await renderer.render()

        except Exception as e:
            logger.error(f"構建經濟統計嵌入失敗: {e}")
            return StandardEmbedBuilder.create_error_embed(
                "載入錯誤", "無法載入經濟統計,請稍後再試"
            )

    async def build_audit_embed(self) -> discord.Embed:
        """構建審計記錄嵌入"""
        try:
            embed = discord.Embed(
                title="📋 交易記錄審計",
                description=f"第 {self.current_audit_page + 1} 頁 • 共 {self.total_audit_count} 筆記錄",
                color=discord.Color.purple(),
            )

            if not self.audit_records:
                embed.add_field(
                    name="📝 交易記錄", value="暫無交易記錄或功能開發中", inline=False
                )
            else:
                # 顯示交易記錄
                record_lines = []
                for _record in self.audit_records:
                    # 格式化交易記錄
                    record_lines.append("交易記錄格式化中...")

                embed.add_field(
                    name="📊 交易記錄", value="\n".join(record_lines), inline=False
                )

            embed.add_field(
                name="🔍 審計功能",
                value=(
                    "🔍 **篩選記錄** - 按時間、用戶、類型篩選\n"
                    "📥 **導出記錄** - 導出為CSV格式\n"
                    "📄 **分頁瀏覽** - 瀏覽所有記錄"
                ),
                inline=False,
            )

            return embed

        except Exception as e:
            logger.error(f"構建審計記錄嵌入失敗: {e}")
            return StandardEmbedBuilder.create_error_embed(
                "載入錯誤", "無法載入審計記錄,請稍後再試"
            )

    # ================== 頁面切換回調 ==================

    async def change_page(self, interaction: discord.Interaction, page: str):
        """切換頁面並重新設置組件"""
        await super().change_page(interaction, page)
        self._setup_components()

        # 重新載入當前頁面的數據
        if page == "users":
            await self._load_users_page()
        elif page == "audit":
            await self._load_audit_page()

        # 更新訊息與組件
        embed = await self.get_current_embed()
        await interaction.edit_original_response(embed=embed, view=self)

    # ================== 用戶管理回調 ==================

    async def search_user_callback(self, interaction: discord.Interaction):
        """搜尋用戶回調"""
        # TODO: 實作用戶搜尋 Modal
        await self._send_info_response(interaction, "用戶搜尋功能開發中")

    async def users_prev_page_callback(self, interaction: discord.Interaction):
        """用戶管理上一頁回調"""
        if self.current_users_page > 0:
            self.current_users_page -= 1
            await self._load_users_page()
            await self.refresh_data_and_view(interaction)
        else:
            await interaction.response.defer()

    async def users_next_page_callback(self, interaction: discord.Interaction):
        """用戶管理下一頁回調"""
        # 檢查是否還有下一頁
        max_page = (
            self.total_users_count + self.users_per_page - 1
        ) // self.users_per_page - 1
        if self.current_users_page < max_page:
            self.current_users_page += 1
            await self._load_users_page()
            await self.refresh_data_and_view(interaction)
        else:
            await interaction.response.defer()

    # ================== 統計頁面回調 ==================

    async def refresh_stats_callback(self, interaction: discord.Interaction):
        """刷新統計回調"""
        try:
            await interaction.response.defer()
            self.guild_stats = await self.currency_service.get_guild_statistics(
                self.guild_id
            )
            embed = await self.get_current_embed()
            await interaction.edit_original_response(embed=embed, view=self)
        except Exception as e:
            logger.error(f"刷新統計失敗: {e}")
            await self.on_error(interaction, e, None)

    async def export_stats_callback(self, interaction: discord.Interaction):
        """導出統計回調"""
        # TODO: 實作統計導出功能
        await self._send_info_response(interaction, "統計導出功能開發中")

    # ================== 審計頁面回調 ==================

    async def filter_audit_callback(self, interaction: discord.Interaction):
        """篩選審計記錄回調"""
        # TODO: 實作審計篩選 Modal
        await self._send_info_response(interaction, "審計篩選功能開發中")

    async def audit_prev_page_callback(self, interaction: discord.Interaction):
        """審計記錄上一頁回調"""
        if self.current_audit_page > 0:
            self.current_audit_page -= 1
            await self._load_audit_page()
            await self.refresh_data_and_view(interaction)
        else:
            await interaction.response.defer()

    async def audit_next_page_callback(self, interaction: discord.Interaction):
        """審計記錄下一頁回調"""
        max_page = (
            self.total_audit_count + self.audit_per_page - 1
        ) // self.audit_per_page - 1
        if self.current_audit_page < max_page:
            self.current_audit_page += 1
            await self._load_audit_page()
            await self.refresh_data_and_view(interaction)
        else:
            await interaction.response.defer()

    async def export_audit_callback(self, interaction: discord.Interaction):
        """導出審計記錄回調"""
        # TODO: 實作審計記錄導出功能
        await self._send_info_response(interaction, "審計記錄導出功能開發中")

    # ================== 通用回調 ==================

    async def back_to_main_callback(self, interaction: discord.Interaction):
        """返回主控台回調"""
        self.current_page = "main"
        await self.refresh_data_and_view(interaction)

    async def refresh_data_and_view(self, interaction: discord.Interaction):
        """刷新數據並更新視圖"""
        try:
            # 重新載入數據
            await self._load_admin_data()

            # 重新設置組件
            self._setup_components()

            # 更新嵌入
            embed = await self.get_current_embed()
            await interaction.response.edit_message(embed=embed, view=self)

        except Exception as e:
            logger.error(f"刷新管理員面板失敗: {e}")
            await self.on_error(interaction, e, None)
