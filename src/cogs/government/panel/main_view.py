"""Government Panel Main View.

政府面板主視圖,提供部門資訊顯示和管理功能.
符合 Discord UI Kit 原生體驗和統一設計規範.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

import discord

if TYPE_CHECKING:
    from discord.ext import commands

from src.cogs.government.service import GovernmentService, GovernmentServiceError

from ..constants import MAX_RECENT_ERRORS_DISPLAY, PANEL_LOAD_TIME_WARNING_MS
from .components import SearchModal
from .components.admin_controls import AdminManageModal
from .components.search_modal import FilterModal
from .embeds import create_main_panel_embed

logger = logging.getLogger(__name__)


class GovernmentPanelView(discord.ui.View):
    """政府面板主視圖類別.

    提供:
    - 部門列表和階層結構顯示
    - 搜尋和篩選功能
    - 管理員角色調整功能
    - 即時載入和效能優化(<300ms)
    """

    def __init__(
        self,
        bot: commands.Bot,
        guild_id: int,
        user_id: int,
        government_service: GovernmentService | None = None,
    ):
        """初始化政府面板視圖.

        Args:
            bot: Discord Bot 實例
            guild_id: 伺服器 ID
            user_id: 使用者 ID
            government_service: 政府服務實例(可選)
        """
        super().__init__(timeout=300.0)  # 5分鐘超時

        self.bot = bot
        self.guild_id = guild_id
        self.user_id = user_id
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # 初始化服務
        self.service = government_service or GovernmentService(bot)

        # 面板狀態
        self.current_page = 0
        self.items_per_page = 10
        self.search_query = ""
        self.filter_type = "all"  # all, departments, members
        self.selected_department_id = None

        # 快取資料
        self._departments_cache: list[dict[str, Any]] = []
        self._hierarchy_cache: list[dict[str, Any]] = []
        self._stats_cache: dict[str, Any] = {}
        self._cache_timestamp = 0
        self._cache_ttl = 60  # 1分鐘 TTL

        # 初始化按鈕組件
        self._setup_components()

    def _setup_components(self) -> None:
        """設置 UI 組件."""
        # 清空現有組件
        self.clear_items()

        # 主要功能按鈕 (Row 0)
        refresh_btn = discord.ui.Button(
            label="🔄 重新整理",
            style=discord.ButtonStyle.secondary,
            custom_id="roas_gov_refresh",
            row=0,
        )
        refresh_btn.callback = self.refresh_button
        self.add_item(refresh_btn)

        search_btn = discord.ui.Button(
            label="🔍 搜尋",
            style=discord.ButtonStyle.primary,
            custom_id="roas_gov_search",
            row=0,
        )
        search_btn.callback = self.search_button
        self.add_item(search_btn)

        filter_btn = discord.ui.Button(
            label="📋 篩選",
            style=discord.ButtonStyle.secondary,
            custom_id="roas_gov_filter",
            row=0,
        )
        filter_btn.callback = self.filter_button
        self.add_item(filter_btn)

        # 分頁控制 (Row 1)
        if self._needs_pagination():
            prev_btn = discord.ui.Button(
                label="◀️ 上一頁",
                style=discord.ButtonStyle.secondary,
                custom_id="roas_gov_prev",
                row=1,
                disabled=(self.current_page == 0),
            )
            prev_btn.callback = self.prev_button
            self.add_item(prev_btn)

            # 計算總頁數
            filtered_departments = self._apply_filters()
            total_pages = self._calculate_total_pages(filtered_departments)

            next_btn = discord.ui.Button(
                label="下一頁 ▶️",
                style=discord.ButtonStyle.secondary,
                custom_id="roas_gov_next",
                row=1,
                disabled=(self.current_page >= total_pages - 1),
            )
            next_btn.callback = self.next_button
            self.add_item(next_btn)

        # 管理員控制 (Row 2)
        if self._is_admin():
            manage_btn = discord.ui.Button(
                label="⚙️ 管理",
                style=discord.ButtonStyle.danger,
                custom_id="roas_gov_manage",
                row=2,
            )
            manage_btn.callback = self.manage_button
            self.add_item(manage_btn)

            sync_btn = discord.ui.Button(
                label="🔄 同步角色",
                style=discord.ButtonStyle.secondary,
                custom_id="roas_gov_sync_roles",
                row=2,
            )
            sync_btn.callback = self.sync_roles_button
            self.add_item(sync_btn)

    async def load_data(self, force_refresh: bool = False) -> None:
        """載入面板資料.

        Args:
            force_refresh: 是否強制重新載入

        Raises:
            GovernmentServiceError: 載入資料失敗
        """
        current_time = time.time()

        # 檢查快取是否有效
        if (
            not force_refresh
            and self._cache_timestamp
            and current_time - self._cache_timestamp < self._cache_ttl
        ):
            return

        try:
            # 並行載入資料以提升效能
            tasks = [
                self.service.get_departments_by_guild(self.guild_id),
                self.service.get_department_hierarchy(self.guild_id),
                self.service.get_department_statistics(self.guild_id),
            ]

            start_time = time.time()
            departments, hierarchy, stats = await asyncio.gather(*tasks)
            load_time = (time.time() - start_time) * 1000

            # 記錄載入時間(目標 <300ms)
            self.logger.info(f"政府面板資料載入完成,耗時: {load_time:.2f}ms")

            if load_time > PANEL_LOAD_TIME_WARNING_MS:
                self.logger.warning(
                    f"政府面板載入時間超標: {load_time:.2f}ms > {PANEL_LOAD_TIME_WARNING_MS}ms"
                )

            # 轉換部門資料為顯示格式
            self._departments_cache = [
                {
                    "id": str(dept.id),
                    "name": dept.name,
                    "description": dept.description or "無描述",
                    "parent_id": str(dept.parent_id) if dept.parent_id else None,
                    "role_id": dept.role_id,
                    "is_active": dept.is_active,
                    "member_count": getattr(dept, "member_count", 0),
                    "created_at": dept.created_at.isoformat()
                    if dept.created_at
                    else None,
                }
                for dept in departments
            ]

            self._hierarchy_cache = hierarchy
            self._stats_cache = stats
            self._cache_timestamp = current_time

        except Exception as e:
            self.logger.error(f"載入政府面板資料失敗: {e}")
            raise GovernmentServiceError(f"載入政府面板資料失敗: {e}") from e

    async def create_main_embed(self) -> discord.Embed:
        """創建主面板 Embed."""
        # 確保資料已載入
        await self.load_data()

        # 應用搜尋和篩選
        filtered_departments = self._apply_filters()

        # 分頁處理
        page_departments = self._paginate_departments(filtered_departments)

        return create_main_panel_embed(
            departments=page_departments,
            hierarchy=self._hierarchy_cache,
            stats=self._stats_cache,
            current_page=self.current_page,
            total_pages=self._calculate_total_pages(filtered_departments),
            search_query=self.search_query,
            filter_type=self.filter_type,
        )

    def _apply_filters(self) -> list[dict[str, Any]]:
        """應用搜尋和篩選條件."""
        departments = self._departments_cache.copy()

        # 搜尋篩選
        if self.search_query:
            query_lower = self.search_query.lower()
            departments = [
                dept
                for dept in departments
                if (
                    query_lower in dept["name"].lower()
                    or query_lower in dept["description"].lower()
                )
            ]

        # 類型篩選
        if self.filter_type == "active":
            departments = [dept for dept in departments if dept["is_active"]]
        elif self.filter_type == "inactive":
            departments = [dept for dept in departments if not dept["is_active"]]
        elif self.filter_type == "with_roles":
            departments = [dept for dept in departments if dept["role_id"]]
        elif self.filter_type == "without_roles":
            departments = [dept for dept in departments if not dept["role_id"]]

        return departments

    def _paginate_departments(
        self, departments: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """分頁處理部門列表."""
        start_idx = self.current_page * self.items_per_page
        end_idx = start_idx + self.items_per_page
        return departments[start_idx:end_idx]

    def _calculate_total_pages(self, departments: list[dict[str, Any]]) -> int:
        """計算總頁數."""
        return max(
            1, (len(departments) + self.items_per_page - 1) // self.items_per_page
        )

    def _needs_pagination(self) -> bool:
        """檢查是否需要分頁."""
        return len(self._departments_cache) > self.items_per_page

    def _is_admin(self) -> bool:
        """檢查當前使用者是否為管理員."""
        guild = self.bot.get_guild(self.guild_id)
        if not guild:
            return False

        member = guild.get_member(self.user_id)
        if not member:
            return False

        return member.guild_permissions.manage_guild

    # 按鈕事件處理方法
    async def refresh_button(self, interaction: discord.Interaction) -> None:
        """重新整理按鈕."""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ 只有面板開啟者可以操作此按鈕!", ephemeral=True
            )
            return

        try:
            await interaction.response.defer()

            # 強制重新載入資料
            await self.load_data(force_refresh=True)

            # 更新 Embed
            embed = await self.create_main_embed()

            # 重新設置組件
            self._setup_components()

            await interaction.edit_original_response(embed=embed, view=self)

        except Exception as e:
            self.logger.error(f"重新整理面板失敗: {e}")
            await interaction.followup.send(f"❌ 重新整理失敗: {e!s}", ephemeral=True)

    async def search_button(self, interaction: discord.Interaction) -> None:
        """搜尋按鈕."""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ 只有面板開啟者可以操作此按鈕!", ephemeral=True
            )
            return

        modal = SearchModal(current_query=self.search_query)
        await interaction.response.send_modal(modal)

        # 等待 Modal 提交
        await modal.wait()

        if modal.search_query is not None:
            self.search_query = modal.search_query
            self.current_page = 0  # 重置到第一頁

            try:
                # 更新 Embed
                embed = await self.create_main_embed()
                self._setup_components()

                await interaction.edit_original_response(embed=embed, view=self)

            except Exception as e:
                self.logger.error(f"更新搜尋結果失敗: {e}")

    async def filter_button(self, interaction: discord.Interaction) -> None:
        """篩選按鈕."""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ 只有面板開啟者可以操作此按鈕!", ephemeral=True
            )
            return

        modal = FilterModal(current_filter=self.filter_type)
        await interaction.response.send_modal(modal)

        # 等待 Modal 提交
        await modal.wait()

        if modal.filter_type is not None:
            self.filter_type = modal.filter_type
            self.current_page = 0  # 重置到第一頁

            try:
                # 更新 Embed
                embed = await self.create_main_embed()
                self._setup_components()

                await interaction.edit_original_response(embed=embed, view=self)

            except Exception as e:
                self.logger.error(f"更新篩選結果失敗: {e}")

    async def prev_button(self, interaction: discord.Interaction) -> None:
        """上一頁按鈕."""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ 只有面板開啟者可以操作此按鈕!", ephemeral=True
            )
            return

        if self.current_page > 0:
            self.current_page -= 1

            try:
                await interaction.response.defer()

                embed = await self.create_main_embed()
                self._setup_components()

                await interaction.edit_original_response(embed=embed, view=self)

            except Exception as e:
                self.logger.error(f"切換頁面失敗: {e}")
                await interaction.followup.send(
                    f"❌ 切換頁面失敗: {e!s}", ephemeral=True
                )
        else:
            await interaction.response.send_message(
                "❌ 已經是第一頁了!", ephemeral=True
            )

    async def next_button(self, interaction: discord.Interaction) -> None:
        """下一頁按鈕."""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ 只有面板開啟者可以操作此按鈕!", ephemeral=True
            )
            return

        # 計算總頁數
        filtered_departments = self._apply_filters()
        total_pages = self._calculate_total_pages(filtered_departments)

        if self.current_page < total_pages - 1:
            self.current_page += 1

            try:
                await interaction.response.defer()

                embed = await self.create_main_embed()
                self._setup_components()

                await interaction.edit_original_response(embed=embed, view=self)

            except Exception as e:
                self.logger.error(f"切換頁面失敗: {e}")
                await interaction.followup.send(
                    f"❌ 切換頁面失敗: {e!s}", ephemeral=True
                )
        else:
            await interaction.response.send_message(
                "❌ 已經是最後一頁了!", ephemeral=True
            )

    async def manage_button(self, interaction: discord.Interaction) -> None:
        """管理按鈕(管理員專用)."""
        if not self._is_admin():
            await interaction.response.send_message(
                "❌ 你沒有管理員權限!", ephemeral=True
            )
            return

        modal = AdminManageModal(
            government_service=self.service,
            guild_id=self.guild_id,
            admin_id=interaction.user.id,
        )
        await interaction.response.send_modal(modal)

    async def sync_roles_button(self, interaction: discord.Interaction) -> None:
        """同步角色按鈕(管理員專用)."""
        if not self._is_admin():
            await interaction.response.send_message(
                "❌ 你沒有管理員權限!", ephemeral=True
            )
            return

        try:
            await interaction.response.defer(ephemeral=True)

            # 執行角色同步
            results = await self.service.sync_roles_for_guild(self.guild_id)

            embed = discord.Embed(title="🔄 角色同步完成", color=discord.Color.green())

            embed.add_field(
                name="同步結果",
                value=(
                    f"**總部門數:** {results['total_departments']}\n"
                    f"**創建角色:** {results['roles_created']}\n"
                    f"**更新角色:** {results['roles_updated']}\n"
                    f"**錯誤數量:** {len(results.get('errors', []))}"
                ),
                inline=False,
            )

            if results.get("errors"):
                error_text = "\n".join(results["errors"][:MAX_RECENT_ERRORS_DISPLAY])
                if len(results["errors"]) > MAX_RECENT_ERRORS_DISPLAY:
                    error_text += f"\n... 還有 {len(results['errors']) - MAX_RECENT_ERRORS_DISPLAY} 個錯誤"

                embed.add_field(
                    name="⚠️ 錯誤詳情", value=f"```{error_text}```", inline=False
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

            # 重新載入資料以反映變更
            await self.load_data(force_refresh=True)

        except Exception as e:
            self.logger.error(f"同步角色失敗: {e}")
            await interaction.followup.send(f"❌ 同步角色失敗: {e!s}", ephemeral=True)

    async def on_timeout(self) -> None:
        """視圖超時處理."""
        self.logger.info(
            f"政府面板視圖超時 (guild: {self.guild_id}, user: {self.user_id})"
        )

        # 禁用所有按鈕
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item
    ) -> None:
        """視圖錯誤處理."""
        self.logger.error(f"政府面板視圖錯誤: {error}", exc_info=True)

        if not interaction.response.is_done():
            await interaction.response.send_message(
                f"❌ 操作失敗: {error!s}", ephemeral=True
            )
        else:
            await interaction.followup.send(f"❌ 操作失敗: {error!s}", ephemeral=True)
