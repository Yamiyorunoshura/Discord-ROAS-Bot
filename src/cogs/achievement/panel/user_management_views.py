"""用戶成就管理視圖組件.

此模組包含用戶成就管理的專用視圖：
- 用戶搜尋結果顯示
- 用戶成就管理操作介面
- 確認對話框和操作結果顯示
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import discord
from discord import ui

from src.cogs.core.base_cog import StandardEmbedBuilder

if TYPE_CHECKING:
    from .admin_panel import AdminPanel

logger = logging.getLogger(__name__)


class UserSearchResultView(ui.View):
    """用戶搜尋結果視圖."""

    def __init__(
        self,
        admin_panel: AdminPanel,
        search_results: list[dict[str, Any]],
        search_query: str,
        action: str = "general"
    ):
        """初始化用戶搜尋結果視圖.

        Args:
            admin_panel: 管理面板控制器
            search_results: 搜尋結果列表
            search_query: 搜尋查詢
            action: 操作類型
        """
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.search_results = search_results
        self.search_query = search_query
        self.action = action

        # 動態添加用戶選擇按鈕
        self._add_user_buttons()

    def _add_user_buttons(self):
        """動態添加用戶選擇按鈕."""
        if not self.search_results:
            return

        # 最多顯示前 5 個結果
        for i, user_data in enumerate(self.search_results[:5]):
            member = user_data["user"]

            # 創建用戶選擇按鈕
            button = ui.Button(
                label=f"{member.display_name}",
                emoji="👤",
                style=discord.ButtonStyle.primary,
                custom_id=f"select_user_{i}",
                row=i // 5  # 每行最多 5 個按鈕
            )

            # 動態創建回調函數
            async def button_callback(interaction: discord.Interaction, user_index: int = i):
                await self._handle_user_selection(interaction, user_index)

            button.callback = button_callback
            self.add_item(button)

    async def _handle_user_selection(self, interaction: discord.Interaction, user_index: int):
        """處理用戶選擇."""
        try:
            if user_index >= len(self.search_results):
                await interaction.response.send_message("❌ 無效的用戶選擇", ephemeral=True)
                return

            selected_user = self.search_results[user_index]

            # 根據操作類型顯示不同的管理界面
            if self.action == "bulk":
                # 批量操作 - 顯示批量用戶選擇界面
                await self._show_bulk_user_selection(interaction, selected_user)
            else:
                # 單個用戶操作 - 顯示用戶管理界面
                await self._show_user_management(interaction, selected_user)

        except Exception as e:
            logger.error(f"處理用戶選擇失敗: {e}")
            await interaction.response.send_message("❌ 處理用戶選擇時發生錯誤", ephemeral=True)

    async def _show_user_management(self, interaction: discord.Interaction, user_data: dict[str, Any]):
        """顯示單個用戶管理界面."""
        try:
            # 獲取用戶成就摘要
            from ..services.simple_container import ServiceContainer
            from ..services.user_admin_service import UserSearchService

            container = ServiceContainer()
            repository = await container.get_repository()

            search_service = UserSearchService(self.admin_panel.bot)
            user_summary = await search_service.get_user_achievement_summary(
                user_data["user_id"], repository
            )

            # 創建用戶詳情 Embed
            embed = self._create_user_detail_embed(user_data, user_summary)

            # 創建用戶管理操作視圖
            management_view = UserDetailManagementView(self.admin_panel, user_data, self.action)

            await interaction.response.edit_message(
                embed=embed,
                view=management_view
            )

        except Exception as e:
            logger.error(f"顯示用戶管理界面失敗: {e}")
            await interaction.response.send_message("❌ 載入用戶管理界面時發生錯誤", ephemeral=True)

    async def _show_bulk_user_selection(self, interaction: discord.Interaction, user_data: dict[str, Any]):
        """顯示批量用戶選擇界面."""
        # 創建批量操作選擇界面
        embed = StandardEmbedBuilder.info(
            title="👥 批量用戶操作",
            description="選擇要執行批量操作的用戶群組"
        )

        # 添加用戶統計信息
        total_users = len(user_data.get("users", []))
        active_users = len([u for u in user_data.get("users", []) if u.get("active", False)])

        embed.add_field(
            name="📊 用戶統計",
            value=f"• 總用戶數: {total_users}\n• 活躍用戶: {active_users}\n• 非活躍用戶: {total_users - active_users}",
            inline=False
        )

        # 創建操作選擇視圖
        view = BulkOperationSelectionView(user_data)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class BulkOperationSelectionView(ui.View):
    """批量操作選擇視圖."""

    def __init__(self, user_data: dict[str, Any]):
        super().__init__(timeout=300)
        self.user_data = user_data

    @ui.select(
        placeholder="選擇批量操作類型...",
        options=[
            discord.SelectOption(
                label="批量授予成就",
                description="為選定用戶批量授予特定成就",
                emoji="🏆",
                value="grant_achievement"
            ),
            discord.SelectOption(
                label="批量重置進度",
                description="重置選定用戶的成就進度",
                emoji="🔄",
                value="reset_progress"
            ),
            discord.SelectOption(
                label="批量導出數據",
                description="導出選定用戶的成就數據",
                emoji="📤",
                value="export_data"
            )
        ]
    )
    async def operation_select(self, interaction: discord.Interaction, select: ui.Select):
        """處理批量操作選擇."""
        operation_type = select.values[0]

        if operation_type == "grant_achievement":
            await self._handle_bulk_grant(interaction)
        elif operation_type == "reset_progress":
            await self._handle_bulk_reset(interaction)
        elif operation_type == "export_data":
            await self._handle_bulk_export(interaction)

    async def _handle_bulk_grant(self, interaction: discord.Interaction):
        """處理批量成就授予."""
        embed = StandardEmbedBuilder.info(
            title="🏆 批量授予成就",
            description="此功能將在完整實作時提供用戶選擇和成就選擇界面"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_bulk_reset(self, interaction: discord.Interaction):
        """處理批量進度重置."""
        embed = StandardEmbedBuilder.warning(
            title="🔄 批量重置進度",
            description="此功能將在完整實作時提供重置選項和確認對話框"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _handle_bulk_export(self, interaction: discord.Interaction):
        """處理批量數據導出."""
        embed = StandardEmbedBuilder.info(
            title="📤 批量導出數據",
            description="此功能將在完整實作時提供數據格式選擇和導出選項"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    def _create_user_detail_embed(self, user_data: dict[str, Any], user_summary: dict[str, Any]) -> discord.Embed:
        """創建用戶詳情 Embed."""
        member = user_data["user"]

        embed = StandardEmbedBuilder.create_info_embed(
            f"👤 用戶詳情 - {member.display_name}",
            f"管理 {member.mention} 的成就資料"
        )

        # 基本資訊
        embed.add_field(
            name="👤 基本資訊",
            value=f"**用戶名**: {member.name}\n"
                  f"**暱稱**: {member.nick or '無'}\n"
                  f"**用戶 ID**: `{member.id}`\n"
                  f"**加入時間**: {discord.utils.format_dt(member.joined_at, 'R') if member.joined_at else '未知'}",
            inline=True
        )

        # 成就統計
        embed.add_field(
            name="🏆 成就統計",
            value=f"**總成就**: {user_summary['total_achievements']}\n"
                  f"**已獲得**: {user_summary['earned_achievements']}\n"
                  f"**進行中**: {user_summary['in_progress_achievements']}\n"
                  f"**完成率**: {user_summary['completion_rate']}%",
            inline=True
        )

        # 積分資訊
        embed.add_field(
            name="⭐ 積分資訊",
            value=f"**總積分**: {user_summary['total_points']}\n"
                  f"**最後成就**: {discord.utils.format_dt(user_summary['last_achievement'], 'R') if user_summary['last_achievement'] else '無'}",
            inline=True
        )

        if member.avatar:
            embed.set_thumbnail(url=member.avatar.url)

        embed.color = 0xFF6B35
        embed.set_footer(text="選擇下方操作來管理此用戶的成就")

        return embed

    @ui.button(label="🔍 重新搜尋", style=discord.ButtonStyle.secondary)
    async def search_again_button(self, interaction: discord.Interaction, button: ui.Button):
        """重新搜尋按鈕."""
        try:
            from .admin_panel import UserSearchModal
            modal = UserSearchModal(self.admin_panel, self.action)
            await interaction.response.send_modal(modal)
        except Exception as e:
            logger.error(f"重新搜尋失敗: {e}")
            await interaction.response.send_message("❌ 開啟搜尋時發生錯誤", ephemeral=True)

    @ui.button(label="🔙 返回", style=discord.ButtonStyle.secondary)
    async def back_button(self, interaction: discord.Interaction, button: ui.Button):
        """返回用戶管理主頁面."""
        try:
            from .admin_panel import AdminPanelState
            await self.admin_panel.handle_navigation(interaction, AdminPanelState.USERS)
        except Exception as e:
            logger.error(f"返回失敗: {e}")
            await interaction.response.send_message("❌ 返回時發生錯誤", ephemeral=True)


class UserDetailManagementView(ui.View):
    """用戶詳情管理視圖."""

    def __init__(self, admin_panel: AdminPanel, user_data: dict[str, Any], action: str = "general"):
        """初始化用戶詳情管理視圖.

        Args:
            admin_panel: 管理面板控制器
            user_data: 用戶資料
            action: 操作類型
        """
        super().__init__(timeout=600)
        self.admin_panel = admin_panel
        self.user_data = user_data
        self.action = action

    @ui.select(
        placeholder="選擇要執行的操作...",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(
                label="🎁 授予成就",
                value="grant",
                description="手動授予用戶特定成就",
                emoji="🎁"
            ),
            discord.SelectOption(
                label="❌ 撤銷成就",
                value="revoke",
                description="撤銷用戶已獲得的成就",
                emoji="❌"
            ),
            discord.SelectOption(
                label="📈 調整進度",
                value="adjust",
                description="調整用戶成就進度",
                emoji="📈"
            ),
            discord.SelectOption(
                label="🔄 重置資料",
                value="reset",
                description="重置用戶成就資料",
                emoji="🔄"
            ),
            discord.SelectOption(
                label="📋 查看詳情",
                value="details",
                description="查看用戶成就詳細資料",
                emoji="📋"
            ),
        ]
    )
    async def operation_select(self, interaction: discord.Interaction, select: ui.Select):
        """處理操作選擇."""
        try:
            operation = select.values[0]
            self.user_data["user_id"]

            if operation == "grant":
                await self._handle_grant_achievement(interaction)
            elif operation == "revoke":
                await self._handle_revoke_achievement(interaction)
            elif operation == "adjust":
                await self._handle_adjust_progress(interaction)
            elif operation == "reset":
                await self._handle_reset_data(interaction)
            elif operation == "details":
                await self._handle_view_details(interaction)
            else:
                await interaction.response.send_message("❌ 無效的操作選擇", ephemeral=True)

        except Exception as e:
            logger.error(f"處理操作選擇失敗: {e}")
            await interaction.response.send_message("❌ 處理操作時發生錯誤", ephemeral=True)

    async def _handle_grant_achievement(self, interaction: discord.Interaction):
        """處理授予成就操作."""
        try:
            # 顯示成就選擇界面
            grant_view = GrantAchievementView(self.admin_panel, self.user_data)
            embed = await grant_view.create_achievement_selection_embed()

            await interaction.response.edit_message(embed=embed, view=grant_view)

        except Exception as e:
            logger.error(f"處理授予成就操作失敗: {e}")
            await interaction.response.send_message("❌ 開啟成就授予時發生錯誤", ephemeral=True)

    async def _handle_revoke_achievement(self, interaction: discord.Interaction):
        """處理撤銷成就操作."""
        try:
            # 顯示成就撤銷界面
            from .revoke_views import RevokeAchievementView
            revoke_view = RevokeAchievementView(self.admin_panel, self.user_data)
            embed = await revoke_view.create_user_achievements_embed()

            await interaction.response.edit_message(embed=embed, view=revoke_view)

        except Exception as e:
            logger.error(f"處理撤銷成就操作失敗: {e}")
            await interaction.response.send_message("❌ 開啟成就撤銷時發生錯誤", ephemeral=True)

    async def _handle_adjust_progress(self, interaction: discord.Interaction):
        """處理調整進度操作."""
        try:
            # 顯示進度調整界面
            from .progress_views import AdjustProgressView
            adjust_view = AdjustProgressView(self.admin_panel, self.user_data)
            embed = await adjust_view.create_progress_list_embed()

            await interaction.response.edit_message(embed=embed, view=adjust_view)

        except Exception as e:
            logger.error(f"處理調整進度操作失敗: {e}")
            await interaction.response.send_message("❌ 開啟進度調整時發生錯誤", ephemeral=True)

    async def _handle_reset_data(self, interaction: discord.Interaction):
        """處理重置資料操作."""
        try:
            # 顯示資料重置界面
            from .reset_views import ResetDataView
            reset_view = ResetDataView(self.admin_panel, self.user_data)
            embed = await reset_view.create_reset_options_embed()

            await interaction.response.edit_message(embed=embed, view=reset_view)

        except Exception as e:
            logger.error(f"處理重置資料操作失敗: {e}")
            await interaction.response.send_message("❌ 開啟資料重置時發生錯誤", ephemeral=True)

    async def _handle_view_details(self, interaction: discord.Interaction):
        """處理查看詳情操作."""
        try:
            # 顯示用戶成就詳細列表
            details_view = UserAchievementDetailsView(self.admin_panel, self.user_data)
            embed = await details_view.create_details_embed()

            await interaction.response.edit_message(embed=embed, view=details_view)

        except Exception as e:
            logger.error(f"查看用戶詳情失敗: {e}")
            await interaction.response.send_message("❌ 載入用戶詳情時發生錯誤", ephemeral=True)

    @ui.button(label="🔍 搜尋其他用戶", style=discord.ButtonStyle.secondary)
    async def search_other_button(self, interaction: discord.Interaction, button: ui.Button):
        """搜尋其他用戶."""
        try:
            from .admin_panel import UserSearchModal
            modal = UserSearchModal(self.admin_panel, self.action)
            await interaction.response.send_modal(modal)
        except Exception as e:
            logger.error(f"搜尋其他用戶失敗: {e}")
            await interaction.response.send_message("❌ 開啟搜尋時發生錯誤", ephemeral=True)

    @ui.button(label="🔙 返回用戶管理", style=discord.ButtonStyle.secondary)
    async def back_to_user_management(self, interaction: discord.Interaction, button: ui.Button):
        """返回用戶管理."""
        try:
            from .admin_panel import AdminPanelState
            await self.admin_panel.handle_navigation(interaction, AdminPanelState.USERS)
        except Exception as e:
            logger.error(f"返回用戶管理失敗: {e}")
            await interaction.response.send_message("❌ 返回時發生錯誤", ephemeral=True)


class UserAchievementDetailsView(ui.View):
    """用戶成就詳情視圖."""

    def __init__(self, admin_panel: AdminPanel, user_data: dict[str, Any]):
        """初始化用戶成就詳情視圖.

        Args:
            admin_panel: 管理面板控制器
            user_data: 用戶資料
        """
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.user_data = user_data
        self.current_page = 0
        self.items_per_page = 5

    async def create_details_embed(self) -> discord.Embed:
        """創建用戶成就詳情 Embed."""
        try:
            from ..services.simple_container import ServiceContainer

            container = ServiceContainer()
            repository = await container.get_repository()

            user_id = self.user_data["user_id"]
            member = self.user_data["user"]

            # 獲取用戶成就和進度
            user_achievements = await repository.get_user_achievements(user_id)
            user_progress = await repository.get_user_progress(user_id)

            embed = StandardEmbedBuilder.create_info_embed(
                f"📋 {member.display_name} 的成就詳情",
                "詳細的成就和進度資料"
            )

            # 已獲得成就
            if user_achievements:
                achievement_list = []
                start_idx = self.current_page * self.items_per_page
                end_idx = start_idx + self.items_per_page

                for i, (user_ach, achievement) in enumerate(user_achievements[start_idx:end_idx], start_idx + 1):
                    earned_date = discord.utils.format_dt(user_ach.earned_at, 'R')
                    achievement_list.append(f"{i}. **{achievement.name}** ({achievement.points}pt) - {earned_date}")

                if achievement_list:
                    embed.add_field(
                        name=f"🏆 已獲得成就 ({len(user_achievements)} 個)",
                        value="\n".join(achievement_list),
                        inline=False
                    )

            # 進行中的成就
            in_progress = [p for p in user_progress if p.current_value < p.target_value]
            if in_progress:
                progress_list = []
                for progress in in_progress[:5]:  # 最多顯示 5 個
                    # 獲取成就名稱（需要查詢）
                    achievement = await repository.get_achievement(progress.achievement_id)
                    if achievement:
                        percentage = (progress.current_value / progress.target_value * 100) if progress.target_value > 0 else 0
                        progress_list.append(f"**{achievement.name}**: {progress.current_value}/{progress.target_value} ({percentage:.1f}%)")

                if progress_list:
                    embed.add_field(
                        name=f"📈 進行中的成就 ({len(in_progress)} 個)",
                        value="\n".join(progress_list),
                        inline=False
                    )

            # 分頁資訊
            if len(user_achievements) > self.items_per_page:
                total_pages = (len(user_achievements) - 1) // self.items_per_page + 1
                embed.set_footer(text=f"頁面 {self.current_page + 1}/{total_pages} | 使用按鈕翻頁")
            else:
                embed.set_footer(text="使用下方按鈕返回或執行其他操作")

            embed.color = 0x3498DB

            return embed

        except Exception as e:
            logger.error(f"創建詳情 Embed 失敗: {e}")
            return StandardEmbedBuilder.create_error_embed(
                "載入失敗", "無法載入用戶成就詳情"
            )

    @ui.button(label="◀️", style=discord.ButtonStyle.secondary, disabled=True)
    async def previous_page(self, interaction: discord.Interaction, button: ui.Button):
        """上一頁."""
        if self.current_page > 0:
            self.current_page -= 1
            embed = await self.create_details_embed()
            self._update_page_buttons()
            await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="▶️", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: ui.Button):
        """下一頁."""
        try:
            from ..services.simple_container import ServiceContainer

            container = ServiceContainer()
            repository = await container.get_repository()

            user_achievements = await repository.get_user_achievements(self.user_data["user_id"])
            total_pages = (len(user_achievements) - 1) // self.items_per_page + 1

            if self.current_page < total_pages - 1:
                self.current_page += 1
                embed = await self.create_details_embed()
                self._update_page_buttons()
                await interaction.response.edit_message(embed=embed, view=self)

        except Exception as e:
            logger.error(f"翻頁失敗: {e}")
            await interaction.response.send_message("❌ 翻頁時發生錯誤", ephemeral=True)

    @ui.button(label="🔄 重新整理", style=discord.ButtonStyle.secondary)
    async def refresh_button(self, interaction: discord.Interaction, button: ui.Button):
        """重新整理資料."""
        try:
            embed = await self.create_details_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        except Exception as e:
            logger.error(f"重新整理失敗: {e}")
            await interaction.response.send_message("❌ 重新整理時發生錯誤", ephemeral=True)

    @ui.button(label="🔙 返回", style=discord.ButtonStyle.secondary)
    async def back_button(self, interaction: discord.Interaction, button: ui.Button):
        """返回用戶管理界面."""
        try:
            management_view = UserDetailManagementView(self.admin_panel, self.user_data)

            # 重新創建用戶摘要 embed
            from ..services.simple_container import ServiceContainer
            from ..services.user_admin_service import UserSearchService

            container = ServiceContainer()
            repository = await container.get_repository()

            search_service = UserSearchService(self.admin_panel.bot)
            user_summary = await search_service.get_user_achievement_summary(
                self.user_data["user_id"], repository
            )

            embed = UserSearchResultView(
                self.admin_panel, [self.user_data], "", "general"
            )._create_user_detail_embed(self.user_data, user_summary)

            await interaction.response.edit_message(embed=embed, view=management_view)

        except Exception as e:
            logger.error(f"返回失敗: {e}")
            await interaction.response.send_message("❌ 返回時發生錯誤", ephemeral=True)

    def _update_page_buttons(self):
        """更新分頁按鈕狀態."""
        # 這個方法需要在實際使用時根據總頁數動態調整按鈕狀態
        pass


class ConfirmationModal(ui.Modal):
    """確認操作模態框."""

    def __init__(self, title: str, operation_name: str, confirmation_text: str = "CONFIRM"):
        """初始化確認模態框.

        Args:
            title: 模態框標題
            operation_name: 操作名稱
            confirmation_text: 確認文字
        """
        super().__init__(title=title)
        self.operation_name = operation_name
        self.confirmation_text = confirmation_text
        self.confirmed = False

        # 確認輸入框
        self.confirm_input = ui.TextInput(
            label=f"輸入 '{confirmation_text}' 以確認{operation_name}",
            placeholder=confirmation_text,
            max_length=20,
            required=True
        )
        self.add_item(self.confirm_input)

    async def on_submit(self, interaction: discord.Interaction):
        """處理模態框提交."""
        if self.confirm_input.value.upper() == self.confirmation_text.upper():
            self.confirmed = True
            await interaction.response.send_message(f"✅ 已確認{self.operation_name}", ephemeral=True)
        else:
            await interaction.response.send_message(
                f"❌ 確認文字不正確，{self.operation_name}已取消", ephemeral=True
            )


class GrantAchievementView(ui.View):
    """授予成就視圖."""

    def __init__(self, admin_panel: AdminPanel, user_data: dict[str, Any]):
        """初始化授予成就視圖.

        Args:
            admin_panel: 管理面板控制器
            user_data: 用戶資料
        """
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.user_data = user_data
        self.current_page = 0
        self.items_per_page = 5
        self.available_achievements = []

    async def create_achievement_selection_embed(self) -> discord.Embed:
        """創建成就選擇 Embed."""
        try:
            from ..services.simple_container import ServiceContainer

            container = ServiceContainer()
            repository = await container.get_repository()

            user_id = self.user_data["user_id"]
            member = self.user_data["user"]

            # 獲取所有可用成就（用戶尚未擁有的）
            all_achievements = await repository.get_achievements(is_active=True)
            user_achievements = await repository.get_user_achievements(user_id)
            user_achievement_ids = {ach.achievement_id for ach, _ in user_achievements}

            # 篩選出用戶尚未擁有的成就
            self.available_achievements = [
                ach for ach in all_achievements
                if ach.id not in user_achievement_ids
            ]

            embed = StandardEmbedBuilder.create_info_embed(
                f"🎁 授予成就 - {member.display_name}",
                f"選擇要授予給 {member.mention} 的成就"
            )

            if not self.available_achievements:
                embed.add_field(
                    name="📋 成就狀態",
                    value="🎉 此用戶已獲得所有可用成就！",
                    inline=False
                )
                embed.color = 0x00FF00
                return embed

            # 顯示可用成就列表（分頁）
            start_idx = self.current_page * self.items_per_page
            end_idx = start_idx + self.items_per_page
            page_achievements = self.available_achievements[start_idx:end_idx]

            achievement_list = []
            for i, achievement in enumerate(page_achievements, start_idx + 1):
                # 獲取分類資訊
                try:
                    category = await repository.get_category(achievement.category_id)
                    category_name = category.name if category else "未知分類"
                except:
                    category_name = "未知分類"

                achievement_list.append(
                    f"{i}. **{achievement.name}** ({achievement.points}pt)\n"
                    f"   📁 {category_name} | {achievement.description[:50]}{'...' if len(achievement.description) > 50 else ''}"
                )

            embed.add_field(
                name=f"🏆 可授予成就 ({len(self.available_achievements)} 個)",
                value="\n\n".join(achievement_list) or "無可用成就",
                inline=False
            )

            # 分頁資訊
            if len(self.available_achievements) > self.items_per_page:
                total_pages = (len(self.available_achievements) - 1) // self.items_per_page + 1
                embed.set_footer(text=f"頁面 {self.current_page + 1}/{total_pages} | 選擇成就後點擊「授予」按鈕")
            else:
                embed.set_footer(text="選擇成就後點擊「授予」按鈕")

            # 動態創建成就選擇下拉選單
            self._update_achievement_select()

            embed.color = 0xFF6B35
            return embed

        except Exception as e:
            logger.error(f"創建成就選擇 Embed 失敗: {e}")
            return StandardEmbedBuilder.create_error_embed(
                "載入失敗", "無法載入可用成就列表"
            )

    def _update_achievement_select(self):
        """更新成就選擇下拉選單."""
        # 清除現有的選擇項目
        for item in self.children[:]:
            if isinstance(item, ui.Select):
                self.remove_item(item)

        if not self.available_achievements:
            return

        # 創建當前頁面的成就選項
        start_idx = self.current_page * self.items_per_page
        end_idx = start_idx + self.items_per_page
        page_achievements = self.available_achievements[start_idx:end_idx]

        options = []
        for _i, achievement in enumerate(page_achievements):
            # 限制選項標籤和描述長度
            label = achievement.name[:100] if len(achievement.name) <= 100 else achievement.name[:97] + "..."
            description = achievement.description[:100] if len(achievement.description) <= 100 else achievement.description[:97] + "..."

            options.append(
                discord.SelectOption(
                    label=label,
                    value=str(achievement.id),
                    description=description,
                    emoji="🏆"
                )
            )

        if options:
            select = ui.Select(
                placeholder="選擇要授予的成就...",
                options=options,
                min_values=1,
                max_values=1
            )

            async def select_callback(interaction: discord.Interaction):
                await self._handle_achievement_selection(interaction, select)

            select.callback = select_callback
            self.add_item(select)

    async def _handle_achievement_selection(self, interaction: discord.Interaction, select: ui.Select):
        """處理成就選擇."""
        try:
            achievement_id = int(select.values[0])

            # 查找選中的成就
            selected_achievement = None
            for achievement in self.available_achievements:
                if achievement.id == achievement_id:
                    selected_achievement = achievement
                    break

            if not selected_achievement:
                await interaction.response.send_message("❌ 找不到選中的成就", ephemeral=True)
                return

            # 顯示授予確認界面
            confirm_view = GrantConfirmationView(
                self.admin_panel,
                self.user_data,
                selected_achievement
            )

            embed = confirm_view.create_confirmation_embed()
            await interaction.response.edit_message(embed=embed, view=confirm_view)

        except Exception as e:
            logger.error(f"處理成就選擇失敗: {e}")
            await interaction.response.send_message("❌ 處理成就選擇時發生錯誤", ephemeral=True)

    @ui.button(label="◀️", style=discord.ButtonStyle.secondary)
    async def previous_page(self, interaction: discord.Interaction, button: ui.Button):
        """上一頁."""
        if self.current_page > 0:
            self.current_page -= 1
            embed = await self.create_achievement_selection_embed()
            await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="▶️", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: ui.Button):
        """下一頁."""
        total_pages = (len(self.available_achievements) - 1) // self.items_per_page + 1
        if self.available_achievements and self.current_page < total_pages - 1:
            self.current_page += 1
            embed = await self.create_achievement_selection_embed()
            await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="🔄 重新整理", style=discord.ButtonStyle.secondary)
    async def refresh_button(self, interaction: discord.Interaction, button: ui.Button):
        """重新整理成就列表."""
        try:
            self.current_page = 0
            embed = await self.create_achievement_selection_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        except Exception as e:
            logger.error(f"重新整理失敗: {e}")
            await interaction.response.send_message("❌ 重新整理時發生錯誤", ephemeral=True)

    @ui.button(label="🔙 返回", style=discord.ButtonStyle.secondary)
    async def back_button(self, interaction: discord.Interaction, button: ui.Button):
        """返回用戶管理界面."""
        try:
            management_view = UserDetailManagementView(self.admin_panel, self.user_data)

            # 重新創建用戶摘要 embed
            from ..services.simple_container import ServiceContainer
            from ..services.user_admin_service import UserSearchService

            container = ServiceContainer()
            repository = await container.get_repository()

            search_service = UserSearchService(self.admin_panel.bot)
            user_summary = await search_service.get_user_achievement_summary(
                self.user_data["user_id"], repository
            )

            embed = UserSearchResultView(
                self.admin_panel, [self.user_data], "", "general"
            )._create_user_detail_embed(self.user_data, user_summary)

            await interaction.response.edit_message(embed=embed, view=management_view)

        except Exception as e:
            logger.error(f"返回失敗: {e}")
            await interaction.response.send_message("❌ 返回時發生錯誤", ephemeral=True)


class GrantConfirmationView(ui.View):
    """授予成就確認視圖."""

    def __init__(self, admin_panel: AdminPanel, user_data: dict[str, Any], achievement):
        """初始化授予確認視圖.

        Args:
            admin_panel: 管理面板控制器
            user_data: 用戶資料
            achievement: 要授予的成就
        """
        super().__init__(timeout=180)
        self.admin_panel = admin_panel
        self.user_data = user_data
        self.achievement = achievement

    def create_confirmation_embed(self) -> discord.Embed:
        """創建確認 Embed."""
        member = self.user_data["user"]

        embed = StandardEmbedBuilder.create_info_embed(
            "⚠️ 確認授予成就",
            f"即將授予成就給 {member.mention}"
        )

        embed.add_field(
            name="👤 目標用戶",
            value=f"**用戶**: {member.display_name}\n"
                  f"**ID**: `{member.id}`",
            inline=True
        )

        embed.add_field(
            name="🏆 成就資訊",
            value=f"**名稱**: {self.achievement.name}\n"
                  f"**積分**: {self.achievement.points}pt\n"
                  f"**描述**: {self.achievement.description[:100]}{'...' if len(self.achievement.description) > 100 else ''}",
            inline=True
        )

        embed.add_field(
            name="⚙️ 授予設定",
            value="請選擇授予選項：\n"
                  "• 是否通知用戶\n"
                  "• 授予原因",
            inline=False
        )

        embed.color = 0xFFA500
        embed.set_footer(text="點擊「設定」按鈕進行詳細配置，或直接點擊「授予」使用預設設定")

        return embed

    @ui.button(label="⚙️ 設定", style=discord.ButtonStyle.primary)
    async def settings_button(self, interaction: discord.Interaction, button: ui.Button):
        """打開設定模態框."""
        try:
            modal = GrantSettingsModal(self._execute_grant)
            await interaction.response.send_modal(modal)
        except Exception as e:
            logger.error(f"打開設定模態框失敗: {e}")
            await interaction.response.send_message("❌ 打開設定時發生錯誤", ephemeral=True)

    @ui.button(label="🎁 直接授予", style=discord.ButtonStyle.success)
    async def direct_grant_button(self, interaction: discord.Interaction, button: ui.Button):
        """直接授予（使用預設設定）."""
        try:
            await self._execute_grant(True, "Manual grant by admin", interaction)
        except Exception as e:
            logger.error(f"直接授予失敗: {e}")
            await interaction.response.send_message("❌ 授予成就時發生錯誤", ephemeral=True)

    @ui.button(label="❌ 取消", style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, button: ui.Button):
        """取消授予."""
        try:
            # 返回成就選擇界面
            grant_view = GrantAchievementView(self.admin_panel, self.user_data)
            embed = await grant_view.create_achievement_selection_embed()

            await interaction.response.edit_message(embed=embed, view=grant_view)
        except Exception as e:
            logger.error(f"取消授予失敗: {e}")
            await interaction.response.send_message("❌ 取消操作時發生錯誤", ephemeral=True)

    async def _execute_grant(self, notify_user: bool, reason: str, interaction: discord.Interaction):
        """執行成就授予."""
        try:
            await interaction.response.defer(ephemeral=True)

            # 從服務容器獲取用戶管理服務
            from src.core.database import get_database_pool

            from ..services.service_container import AchievementServiceContainer

            pool = await get_database_pool("achievement")
            async with AchievementServiceContainer(pool, self.admin_panel.bot) as container:
                user_admin_service = container.user_admin_service

                # 執行授予操作
                success, message, user_achievement = await user_admin_service.grant_achievement_to_user(
                    admin_user_id=self.admin_panel.admin_user_id,
                    target_user_id=self.user_data["user_id"],
                    achievement_id=self.achievement.id,
                    notify_user=notify_user,
                    reason=reason
                )

                if success:
                    # 顯示授予成功結果
                    result_view = GrantResultView(
                        self.admin_panel,
                        self.user_data,
                        self.achievement,
                        user_achievement,
                        notify_user
                    )

                    embed = result_view.create_success_embed()
                    await interaction.edit_original_response(embed=embed, view=result_view)

                    # 如果需要通知用戶，發送私訊
                    if notify_user:
                        await self._send_user_notification(user_achievement)

                else:
                    # 顯示授予失敗結果
                    embed = StandardEmbedBuilder.create_error_embed(
                        "❌ 授予失敗",
                        f"無法授予成就「{self.achievement.name}」給用戶。\n\n**錯誤原因**: {message}"
                    )

                    # 返回成就選擇界面的按鈕
                    back_view = ui.View(timeout=60)
                    back_button = ui.Button(label="🔙 返回選擇", style=discord.ButtonStyle.primary)

                    async def back_callback(back_interaction):
                        grant_view = GrantAchievementView(self.admin_panel, self.user_data)
                        embed = await grant_view.create_achievement_selection_embed()
                        await back_interaction.response.edit_message(embed=embed, view=grant_view)

                    back_button.callback = back_callback
                    back_view.add_item(back_button)

                    await interaction.edit_original_response(embed=embed, view=back_view)

        except Exception as e:
            logger.error(f"執行成就授予失敗: {e}")
            try:
                embed = StandardEmbedBuilder.create_error_embed(
                    "❌ 系統錯誤",
                    f"執行成就授予時發生系統錯誤: {e!s}"
                )
                await interaction.edit_original_response(embed=embed, view=None)
            except:
                pass

    async def _send_user_notification(self, user_achievement):
        """發送用戶通知."""
        try:
            member = self.user_data["user"]

            # 創建通知 Embed
            embed = StandardEmbedBuilder.create_success_embed(
                "🎉 恭喜！您獲得了新成就！",
                f"您在伺服器中獲得了成就「**{self.achievement.name}**」"
            )

            embed.add_field(
                name="🏆 成就詳情",
                value=f"**名稱**: {self.achievement.name}\n"
                      f"**描述**: {self.achievement.description}\n"
                      f"**積分**: +{self.achievement.points}pt",
                inline=False
            )

            embed.add_field(
                name="📅 獲得時間",
                value=discord.utils.format_dt(user_achievement.earned_at, 'F'),
                inline=True
            )

            embed.set_footer(text=f"來自 {member.guild.name}")

            # 發送私訊
            try:
                await member.send(embed=embed)
                logger.info(f"成功發送成就通知給用戶 {member.id}")
            except discord.Forbidden:
                logger.warning(f"無法發送私訊給用戶 {member.id}，可能關閉了私訊")
            except Exception as e:
                logger.error(f"發送用戶通知失敗: {e}")

        except Exception as e:
            logger.error(f"處理用戶通知時發生錯誤: {e}")


class GrantSettingsModal(ui.Modal):
    """授予設定模態框."""

    def __init__(self, callback_func):
        """初始化授予設定模態框.

        Args:
            callback_func: 回調函數
        """
        super().__init__(title="🎁 成就授予設定")
        self.callback_func = callback_func

        # 通知設定
        self.notify_input = ui.TextInput(
            label="是否通知用戶？",
            placeholder="輸入 yes/no 或 是/否",
            default="yes",
            max_length=10,
            required=True
        )
        self.add_item(self.notify_input)

        # 授予原因
        self.reason_input = ui.TextInput(
            label="授予原因",
            placeholder="請輸入授予此成就的原因...",
            default="Manual grant by admin",
            max_length=200,
            required=True
        )
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        """處理設定提交."""
        try:
            notify_text = self.notify_input.value.strip().lower()
            notify_user = notify_text in ["yes", "y", "是", "true", "1"]
            grant_reason = self.reason_input.value.strip()

            if not grant_reason:
                await interaction.response.send_message(
                    "❌ 授予原因不能為空", ephemeral=True
                )
                return

            await self.callback_func(notify_user, grant_reason, interaction)

        except Exception as e:
            logger.error(f"處理設定提交失敗: {e}")
            await interaction.response.send_message(
                "❌ 處理設定時發生錯誤", ephemeral=True
            )


class GrantResultView(ui.View):
    """授予結果視圖."""

    def __init__(
        self,
        admin_panel: AdminPanel,
        user_data: dict[str, Any],
        achievement,
        user_achievement,
        notified: bool = False
    ):
        """初始化授予結果視圖.

        Args:
            admin_panel: 管理面板控制器
            user_data: 用戶資料
            achievement: 授予的成就
            user_achievement: 用戶成就記錄
            notified: 是否已通知用戶
        """
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.user_data = user_data
        self.achievement = achievement
        self.user_achievement = user_achievement
        self.notified = notified

    def create_success_embed(self) -> discord.Embed:
        """創建成功結果 Embed."""
        member = self.user_data["user"]

        embed = StandardEmbedBuilder.create_success_embed(
            "✅ 成就授予成功！",
            f"已成功授予成就給 {member.mention}"
        )

        embed.add_field(
            name="👤 用戶資訊",
            value=f"**用戶**: {member.display_name}\n"
                  f"**ID**: `{member.id}`",
            inline=True
        )

        embed.add_field(
            name="🏆 成就資訊",
            value=f"**名稱**: {self.achievement.name}\n"
                  f"**積分**: +{self.achievement.points}pt\n"
                  f"**通知狀態**: {'✅ 已通知' if self.notified else '❌ 未通知'}",
            inline=True
        )

        embed.add_field(
            name="📅 授予時間",
            value=discord.utils.format_dt(self.user_achievement.earned_at, 'F'),
            inline=False
        )

        embed.set_footer(text="操作已記錄到審計日誌 | 使用下方按鈕繼續操作")

        return embed

    @ui.button(label="🎁 繼續授予", style=discord.ButtonStyle.primary)
    async def continue_grant_button(self, interaction: discord.Interaction, button: ui.Button):
        """繼續授予其他成就."""
        try:
            grant_view = GrantAchievementView(self.admin_panel, self.user_data)
            embed = await grant_view.create_achievement_selection_embed()

            await interaction.response.edit_message(embed=embed, view=grant_view)
        except Exception as e:
            logger.error(f"繼續授予失敗: {e}")
            await interaction.response.send_message("❌ 開啟成就選擇時發生錯誤", ephemeral=True)

    @ui.button(label="👤 管理此用戶", style=discord.ButtonStyle.secondary)
    async def manage_user_button(self, interaction: discord.Interaction, button: ui.Button):
        """返回用戶管理界面."""
        try:
            management_view = UserDetailManagementView(self.admin_panel, self.user_data)

            # 重新創建用戶摘要 embed
            from ..services.simple_container import ServiceContainer
            from ..services.user_admin_service import UserSearchService

            container = ServiceContainer()
            repository = await container.get_repository()

            search_service = UserSearchService(self.admin_panel.bot)
            user_summary = await search_service.get_user_achievement_summary(
                self.user_data["user_id"], repository
            )

            embed = UserSearchResultView(
                self.admin_panel, [self.user_data], "", "general"
            )._create_user_detail_embed(self.user_data, user_summary)

            await interaction.response.edit_message(embed=embed, view=management_view)

        except Exception as e:
            logger.error(f"返回用戶管理失敗: {e}")
            await interaction.response.send_message("❌ 返回用戶管理時發生錯誤", ephemeral=True)

    @ui.button(label="🔍 搜尋其他用戶", style=discord.ButtonStyle.secondary)
    async def search_other_button(self, interaction: discord.Interaction, button: ui.Button):
        """搜尋其他用戶."""
        try:
            from .admin_panel import UserSearchModal
            modal = UserSearchModal(self.admin_panel, "grant")
            await interaction.response.send_modal(modal)
        except Exception as e:
            logger.error(f"搜尋其他用戶失敗: {e}")
            await interaction.response.send_message("❌ 開啟搜尋時發生錯誤", ephemeral=True)

    @ui.button(label="🔙 返回用戶管理", style=discord.ButtonStyle.secondary)
    async def back_to_user_management(self, interaction: discord.Interaction, button: ui.Button):
        """返回用戶管理主頁面."""
        try:
            from .admin_panel import AdminPanelState
            await self.admin_panel.handle_navigation(interaction, AdminPanelState.USERS)
        except Exception as e:
            logger.error(f"返回用戶管理失敗: {e}")
            await interaction.response.send_message("❌ 返回時發生錯誤", ephemeral=True)
