"""用戶成就撤銷功能視圖組件.

此模組包含成就撤銷相關的視圖組件.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import discord
from discord import ui

from src.cogs.core.base_cog import StandardEmbedBuilder
from src.core.database import get_database_pool

from ..services.service_container import AchievementServiceContainer

# 運行時需要的 imports
from ..services.simple_container import ServiceContainer
from ..services.user_admin_service import UserSearchService
from .admin_panel import AdminPanel, AdminPanelState
from .user_management_views import UserDetailManagementView, UserSearchResultView

logger = logging.getLogger(__name__)

# 常數定義
MAX_LABEL_LENGTH = 100  # UI 標籤最大長度
MAX_DESCRIPTION_LENGTH = 100  # 描述最大長度
TRUNCATE_SUFFIX_LENGTH = 97  # 截斷後的長度(保留3個字符給...)

class RevokeAchievementView(ui.View):
    """撤銷成就視圖."""

    def __init__(self, admin_panel: AdminPanel, user_data: dict[str, Any]):
        """初始化撤銷成就視圖.

        Args:
            admin_panel: 管理面板控制器
            user_data: 用戶資料
        """
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.user_data = user_data
        self.current_page = 0
        self.items_per_page = 5
        self.user_achievements = []

    async def create_user_achievements_embed(self) -> discord.Embed:
        """創建用戶成就列表 Embed."""
        try:
            container = ServiceContainer()
            repository = await container.get_repository()

            user_id = self.user_data["user_id"]
            member = self.user_data["user"]

            # 獲取用戶已獲得的成就
            self.user_achievements = await repository.get_user_achievements(user_id)

            embed = StandardEmbedBuilder.create_info_embed(
                f"❌ 撤銷成就 - {member.display_name}",
                f"選擇要從 {member.mention} 撤銷的成就",
            )

            if not self.user_achievements:
                embed.add_field(
                    name="📋 成就狀態", value="此用戶尚未獲得任何成就.", inline=False
                )
                embed.color = 0x999999
                return embed

            start_idx = self.current_page * self.items_per_page
            end_idx = start_idx + self.items_per_page
            page_achievements = self.user_achievements[start_idx:end_idx]

            achievement_list = []
            for i, (user_ach, achievement) in enumerate(
                page_achievements, start_idx + 1
            ):
                # 獲取分類資訊
                try:
                    category = await repository.get_category(achievement.category_id)
                    category_name = category.name if category else "未知分類"
                except Exception:
                    category_name = "未知分類"

                earned_date = discord.utils.format_dt(user_ach.earned_at, "R")
                achievement_list.append(
                    f"{i}. **{achievement.name}** ({achievement.points}pt)\n"
                    f"   📁 {category_name} | 獲得於 {earned_date}"
                )

            embed.add_field(
                name=f"🏆 已獲得成就 ({len(self.user_achievements)} 個)",
                value="\n\n".join(achievement_list) or "無成就記錄",
                inline=False,
            )

            # 分頁資訊
            if len(self.user_achievements) > self.items_per_page:
                total_pages = (
                    len(self.user_achievements) - 1
                ) // self.items_per_page + 1
                embed.set_footer(
                    text=f"頁面 {self.current_page + 1}/{total_pages} | 選擇成就後點擊「撤銷」按鈕"
                )
            else:
                embed.set_footer(text="選擇成就後點擊「撤銷」按鈕")

            # 動態創建成就選擇下拉選單
            self._update_achievement_select()

            embed.color = 0xFF4444
            return embed

        except Exception as e:
            logger.error(f"創建用戶成就列表 Embed 失敗: {e}")
            return StandardEmbedBuilder.create_error_embed(
                "載入失敗", "無法載入用戶成就列表"
            )

    def _update_achievement_select(self):
        """更新成就選擇下拉選單."""
        # 清除現有的選擇項目
        for item in self.children[:]:
            if isinstance(item, ui.Select):
                self.remove_item(item)

        if not self.user_achievements:
            return

        # 創建當前頁面的成就選項
        start_idx = self.current_page * self.items_per_page
        end_idx = start_idx + self.items_per_page
        page_achievements = self.user_achievements[start_idx:end_idx]

        options = []
        for _i, (user_ach, achievement) in enumerate(page_achievements):
            # 限制選項標籤和描述長度
            label = (
                achievement.name[:MAX_LABEL_LENGTH]
                if len(achievement.name) <= MAX_LABEL_LENGTH
                else achievement.name[:TRUNCATE_SUFFIX_LENGTH] + "..."
            )

            # 顯示獲得時間作為描述
            earned_date = discord.utils.format_dt(user_ach.earned_at, "d")
            description = f"獲得於 {earned_date} | {achievement.points}pt"
            if len(description) > MAX_DESCRIPTION_LENGTH:
                description = description[:TRUNCATE_SUFFIX_LENGTH] + "..."

            options.append(
                discord.SelectOption(
                    label=label,
                    value=str(achievement.id),
                    description=description,
                    emoji="❌",
                )
            )

        if options:
            select = ui.Select(
                placeholder="選擇要撤銷的成就...",
                options=options,
                min_values=1,
                max_values=1,
            )

            async def select_callback(interaction: discord.Interaction):
                await self._handle_achievement_selection(interaction, select)

            select.callback = select_callback
            self.add_item(select)

    async def _handle_achievement_selection(
        self, interaction: discord.Interaction, select: ui.Select
    ):
        """處理成就選擇."""
        try:
            achievement_id = int(select.values[0])

            # 查找選中的成就
            selected_user_achievement = None
            selected_achievement = None

            for user_ach, achievement in self.user_achievements:
                if achievement.id == achievement_id:
                    selected_user_achievement = user_ach
                    selected_achievement = achievement
                    break

            if not selected_user_achievement or not selected_achievement:
                await interaction.response.send_message(
                    "❌ 找不到選中的成就", ephemeral=True
                )
                return

            # 顯示撤銷確認界面
            confirm_view = RevokeConfirmationView(
                self.admin_panel,
                self.user_data,
                selected_achievement,
                selected_user_achievement,
            )

            embed = confirm_view.create_confirmation_embed()
            await interaction.response.edit_message(embed=embed, view=confirm_view)

        except Exception as e:
            logger.error(f"處理成就選擇失敗: {e}")
            await interaction.response.send_message(
                "❌ 處理成就選擇時發生錯誤", ephemeral=True
            )

    @ui.button(label="◀️", style=discord.ButtonStyle.secondary)
    async def previous_page(self, interaction: discord.Interaction, _button: ui.Button):
        """上一頁."""
        if self.current_page > 0:
            self.current_page -= 1
            embed = await self.create_user_achievements_embed()
            await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="▶️", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, _button: ui.Button):
        """下一頁."""
        total_pages = (len(self.user_achievements) - 1) // self.items_per_page + 1
        if self.user_achievements and self.current_page < total_pages - 1:
            self.current_page += 1
            embed = await self.create_user_achievements_embed()
            await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="🔄 重新整理", style=discord.ButtonStyle.secondary)
    async def refresh_button(self, interaction: discord.Interaction, _button: ui.Button):
        """重新整理成就列表."""
        try:
            self.current_page = 0
            embed = await self.create_user_achievements_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        except Exception as e:
            logger.error(f"重新整理失敗: {e}")
            await interaction.response.send_message(
                "❌ 重新整理時發生錯誤", ephemeral=True
            )

    @ui.button(label="🔙 返回", style=discord.ButtonStyle.secondary)
    async def back_button(self, interaction: discord.Interaction, _button: ui.Button):
        """返回用戶管理界面."""
        try:
            management_view = UserDetailManagementView(self.admin_panel, self.user_data)

            # 重新創建用戶摘要 embed
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

class RevokeConfirmationView(ui.View):
    """撤銷成就確認視圖."""

    def __init__(
        self,
        admin_panel: AdminPanel,
        user_data: dict[str, Any],
        achievement,
        user_achievement,
    ):
        """初始化撤銷確認視圖."""
        super().__init__(timeout=180)
        self.admin_panel = admin_panel
        self.user_data = user_data
        self.achievement = achievement
        self.user_achievement = user_achievement

    def create_confirmation_embed(self) -> discord.Embed:
        """創建確認 Embed."""
        member = self.user_data["user"]

        embed = StandardEmbedBuilder.create_warning_embed(
            "⚠️ 確認撤銷成就", f"即將撤銷 {member.mention} 的成就"
        )

        embed.add_field(
            name="👤 目標用戶",
            value=f"**用戶**: {member.display_name}\n**ID**: `{member.id}`",
            inline=True,
        )

        embed.add_field(
            name="🏆 成就資訊",
            value=f"**名稱**: {self.achievement.name}\n"
            f"**積分**: -{self.achievement.points}pt\n"
            f"**獲得時間**: {discord.utils.format_dt(self.user_achievement.earned_at, 'R')}",
            inline=True,
        )

        embed.add_field(
            name="⚠️ 撤銷說明",
            value="撤銷操作將會:\n"
            "• 移除用戶的成就記錄\n"
            "• 扣除相關積分\n"
            "• 清理相關進度資料\n"
            "• 記錄到審計日誌",
            inline=False,
        )

        embed.color = 0xFF6600
        embed.set_footer(
            text="點擊「設定」按鈕進行詳細配置,或直接點擊「撤銷」執行操作"
        )

        return embed

    @ui.button(label="⚙️ 設定", style=discord.ButtonStyle.primary)
    async def settings_button(
        self, interaction: discord.Interaction, _button: ui.Button
    ):
        """打開設定模態框."""
        try:
            modal = RevokeSettingsModal(self._execute_revoke)
            await interaction.response.send_modal(modal)
        except Exception as e:
            logger.error(f"打開設定模態框失敗: {e}")
            await interaction.response.send_message(
                "❌ 打開設定時發生錯誤", ephemeral=True
            )

    @ui.button(label="❌ 確認撤銷", style=discord.ButtonStyle.danger)
    async def confirm_revoke_button(
        self, interaction: discord.Interaction, _button: ui.Button
    ):
        """確認撤銷(需要二次確認)."""
        try:
            # 顯示二次確認模態框
            confirm_modal = RevokeDoubleConfirmModal(
                self.user_data["user"].display_name,
                self.achievement.name,
                self._execute_revoke,
            )
            await interaction.response.send_modal(confirm_modal)
        except Exception as e:
            logger.error(f"顯示二次確認失敗: {e}")
            await interaction.response.send_message(
                "❌ 顯示確認對話框時發生錯誤", ephemeral=True
            )

    @ui.button(label="🔙 取消", style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, _button: ui.Button):
        """取消撤銷."""
        try:
            # 返回成就選擇界面
            revoke_view = RevokeAchievementView(self.admin_panel, self.user_data)
            embed = await revoke_view.create_user_achievements_embed()

            await interaction.response.edit_message(embed=embed, view=revoke_view)
        except Exception as e:
            logger.error(f"取消撤銷失敗: {e}")
            await interaction.response.send_message(
                "❌ 取消操作時發生錯誤", ephemeral=True
            )

    async def _execute_revoke(self, reason: str, interaction: discord.Interaction):
        """執行成就撤銷."""
        try:
            await interaction.response.defer(ephemeral=True)

            # 從服務容器獲取用戶管理服務
            pool = await get_database_pool("achievement")
            async with AchievementServiceContainer(
                pool, self.admin_panel.bot
            ) as container:
                user_admin_service = container.user_admin_service

                # 執行撤銷操作
                (
                    success,
                    message,
                ) = await user_admin_service.revoke_achievement_from_user(
                    admin_user_id=self.admin_panel.admin_user_id,
                    target_user_id=self.user_data["user_id"],
                    achievement_id=self.achievement.id,
                    reason=reason,
                )

                if success:
                    # 顯示撤銷成功結果
                    result_view = RevokeResultView(
                        self.admin_panel,
                        self.user_data,
                        self.achievement,
                        self.user_achievement,
                    )

                    embed = result_view.create_success_embed()
                    await interaction.edit_original_response(
                        embed=embed, view=result_view
                    )

                else:
                    # 顯示撤銷失敗結果
                    embed = StandardEmbedBuilder.create_error_embed(
                        "❌ 撤銷失敗",
                        f"無法撤銷成就「{self.achievement.name}」.\n\n**錯誤原因**: {message}",
                    )

                    await interaction.edit_original_response(embed=embed, view=None)

        except Exception as e:
            logger.error(f"執行成就撤銷失敗: {e}")
            try:
                embed = StandardEmbedBuilder.create_error_embed(
                    "❌ 系統錯誤", f"執行成就撤銷時發生系統錯誤: {e!s}"
                )
                await interaction.edit_original_response(embed=embed, view=None)
            except Exception:
                pass

class RevokeSettingsModal(ui.Modal):
    """撤銷設定模態框."""

    def __init__(self, callback_func):
        """初始化撤銷設定模態框."""
        super().__init__(title="❌ 成就撤銷設定")
        self.callback_func = callback_func

        # 撤銷原因
        self.reason_input = ui.TextInput(
            label="撤銷原因",
            placeholder="請輸入撤銷此成就的原因...",
            default="Manual revoke by admin",
            max_length=200,
            required=True,
        )
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        """處理設定提交."""
        try:
            revoke_reason = self.reason_input.value.strip()

            if not revoke_reason:
                await interaction.response.send_message(
                    "❌ 撤銷原因不能為空", ephemeral=True
                )
                return

            await self.callback_func(revoke_reason, interaction)

        except Exception as e:
            logger.error(f"處理設定提交失敗: {e}")
            await interaction.response.send_message(
                "❌ 處理設定時發生錯誤", ephemeral=True
            )

class RevokeDoubleConfirmModal(ui.Modal):
    """撤銷二次確認模態框."""

    def __init__(self, user_display_name: str, achievement_name: str, callback_func):
        """初始化撤銷二次確認模態框."""
        super().__init__(title="⚠️ 危險操作確認")
        self.user_display_name = user_display_name
        self.achievement_name = achievement_name
        self.callback_func = callback_func

        # 用戶名確認
        self.user_confirm_input = ui.TextInput(
            label=f"輸入用戶名以確認: {user_display_name}",
            placeholder=user_display_name,
            max_length=100,
            required=True,
        )
        self.add_item(self.user_confirm_input)

        # 成就名確認
        self.achievement_confirm_input = ui.TextInput(
            label=f"輸入成就名以確認: {achievement_name}",
            placeholder=achievement_name,
            max_length=200,
            required=True,
        )
        self.add_item(self.achievement_confirm_input)

        # 撤銷原因
        self.reason_input = ui.TextInput(
            label="撤銷原因",
            placeholder="請輸入撤銷此成就的原因...",
            default="Manual revoke by admin - double confirmed",
            max_length=200,
            required=True,
        )
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        """處理確認提交."""
        try:
            user_input = self.user_confirm_input.value.strip()
            achievement_input = self.achievement_confirm_input.value.strip()
            reason = self.reason_input.value.strip()

            # 檢查兩個輸入是否都正確
            user_confirmed = user_input == self.user_display_name
            achievement_confirmed = achievement_input == self.achievement_name

            if user_confirmed and achievement_confirmed and reason:
                await self.callback_func(reason, interaction)
            else:
                error_msg = "❌ 確認失敗:\n"
                if not user_confirmed:
                    error_msg += "• 用戶名不匹配\n"
                if not achievement_confirmed:
                    error_msg += "• 成就名稱不匹配\n"
                if not reason:
                    error_msg += "• 撤銷原因不能為空\n"

                embed = StandardEmbedBuilder.create_error_embed(
                    "確認失敗", error_msg + "\n請確保輸入內容完全一致."
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"處理確認提交失敗: {e}")
            await interaction.response.send_message(
                "❌ 處理確認時發生錯誤", ephemeral=True
            )

class RevokeResultView(ui.View):
    """撤銷結果視圖."""

    def __init__(
        self,
        admin_panel: AdminPanel,
        user_data: dict[str, Any],
        achievement,
        user_achievement,
    ):
        """初始化撤銷結果視圖."""
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.user_data = user_data
        self.achievement = achievement
        self.user_achievement = user_achievement

    def create_success_embed(self) -> discord.Embed:
        """創建成功結果 Embed."""
        member = self.user_data["user"]

        embed = StandardEmbedBuilder.create_success_embed(
            "✅ 成就撤銷成功!", f"已成功撤銷 {member.mention} 的成就"
        )

        embed.add_field(
            name="👤 用戶資訊",
            value=f"**用戶**: {member.display_name}\n**ID**: `{member.id}`",
            inline=True,
        )

        embed.add_field(
            name="🏆 撤銷的成就",
            value=f"**名稱**: {self.achievement.name}\n"
            f"**積分**: -{self.achievement.points}pt\n"
            f"**原獲得時間**: {discord.utils.format_dt(self.user_achievement.earned_at, 'R')}",
            inline=True,
        )

        embed.add_field(
            name="📅 撤銷時間",
            value=discord.utils.format_dt(datetime.utcnow(), "F"),
            inline=False,
        )

        embed.set_footer(text="操作已記錄到審計日誌 | 使用下方按鈕繼續操作")
        return embed

    @ui.button(label="❌ 繼續撤銷", style=discord.ButtonStyle.danger)
    async def continue_revoke_button(
        self, interaction: discord.Interaction, _button: ui.Button
    ):
        """繼續撤銷其他成就."""
        try:
            revoke_view = RevokeAchievementView(self.admin_panel, self.user_data)
            embed = await revoke_view.create_user_achievements_embed()

            await interaction.response.edit_message(embed=embed, view=revoke_view)
        except Exception as e:
            logger.error(f"繼續撤銷失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟成就選擇時發生錯誤", ephemeral=True
            )

    @ui.button(label="🔙 返回用戶管理", style=discord.ButtonStyle.secondary)
    async def back_to_user_management(
        self, interaction: discord.Interaction, _button: ui.Button
    ):
        """返回用戶管理主頁面."""
        try:
            await self.admin_panel.handle_navigation(interaction, AdminPanelState.USERS)
        except Exception as e:
            logger.error(f"返回用戶管理失敗: {e}")
            await interaction.response.send_message("❌ 返回時發生錯誤", ephemeral=True)
