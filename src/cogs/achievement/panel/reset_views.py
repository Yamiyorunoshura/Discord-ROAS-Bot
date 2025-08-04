"""用戶資料重置視圖組件.

此模組包含用戶成就資料重置的專用視圖:
- 重置範圍選擇介面
- 重置確認對話框
- 重置結果顯示
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import discord
from discord import ui

from src.cogs.core.base_cog import StandardEmbedBuilder
from src.core.database import get_database_pool

from ..services.service_container import AchievementServiceContainer

# 運行時需要的 imports
from ..services.simple_container import ServiceContainer
from ..services.user_admin_service import UserSearchService
from .admin_panel import AdminPanelState, UserSearchModal
from .user_management_views import UserDetailManagementView, UserSearchResultView

if TYPE_CHECKING:
    from .admin_panel import AdminPanel

logger = logging.getLogger(__name__)

class ResetDataView(ui.View):
    """資料重置視圖."""

    def __init__(self, admin_panel: AdminPanel, user_data: dict[str, Any]):
        """初始化資料重置視圖.

        Args:
            admin_panel: 管理面板控制器
            user_data: 用戶資料
        """
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.user_data = user_data

    async def create_reset_options_embed(self) -> discord.Embed:
        """創建重置選項 Embed."""
        try:
            container = ServiceContainer()
            repository = await container.get_repository()

            user_id = self.user_data["user_id"]
            member = self.user_data["user"]

            # 獲取用戶資料統計
            user_achievements = await repository.get_user_achievements(user_id)
            user_progress = await repository.get_user_progress(user_id)

            embed = StandardEmbedBuilder.create_warning_embed(
                f"⚠️ 重置資料 - {member.display_name}",
                f"即將重置 {member.mention} 的成就資料",
            )

            # 當前資料統計
            embed.add_field(
                name="📊 當前資料統計",
                value=f"**已獲得成就**: {len(user_achievements)} 個\n"
                f"**進度記錄**: {len(user_progress)} 個\n"
                f"**總積分**: {sum(ach.points for _, ach in user_achievements)} 點",
                inline=True,
            )

            # 重置選項說明
            embed.add_field(
                name="🔄 重置選項",
                value="• **完整重置** - 清除所有成就和進度資料\n"
                "• **分類重置** - 僅重置特定分類的資料\n"
                "• **進度重置** - 僅重置進度,保留已獲得的成就",
                inline=False,
            )

            # 安全提醒
            embed.add_field(
                name="🚨 重要提醒",
                value="• 重置操作無法撤銷!\n"
                "• 系統會自動備份資料供審計\n"
                "• 需要管理員二次確認\n"
                "• 操作將記錄到審計日誌",
                inline=False,
            )

            embed.color = 0xFF4444
            embed.set_footer(text="請謹慎選擇重置範圍 | 操作前會再次要求確認")

            return embed

        except Exception as e:
            logger.error(f"創建重置選項 Embed 失敗: {e}")
            return StandardEmbedBuilder.create_error_embed(
                "載入失敗", "無法載入用戶資料統計"
            )

    @ui.select(
        placeholder="選擇重置範圍...",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(
                label="🗑️ 完整重置",
                value="full",
                description="清除所有成就和進度資料(最危險)",
                emoji="🗑️",
            ),
            discord.SelectOption(
                label="📁 分類重置",
                value="category",
                description="僅重置特定分類的資料",
                emoji="📁",
            ),
            discord.SelectOption(
                label="📈 進度重置",
                value="progress_only",
                description="僅清除進度記錄,保留已獲得的成就",
                emoji="📈",
            ),
        ],
    )
    async def reset_type_select(
        self, interaction: discord.Interaction, select: ui.Select
    ):
        """處理重置類型選擇."""
        try:
            reset_type = select.values[0]

            if reset_type == "full":
                await self._handle_full_reset(interaction)
            elif reset_type == "category":
                await self._handle_category_reset(interaction)
            elif reset_type == "progress_only":
                await self._handle_progress_reset(interaction)
            else:
                await interaction.response.send_message(
                    "❌ 無效的重置選項", ephemeral=True
                )

        except Exception as e:
            logger.error(f"處理重置類型選擇失敗: {e}")
            await interaction.response.send_message(
                "❌ 處理重置選項時發生錯誤", ephemeral=True
            )

    async def _handle_full_reset(self, interaction: discord.Interaction):
        """處理完整重置."""
        try:
            # 顯示完整重置確認對話框
            confirmation_view = ResetConfirmationView(
                self.admin_panel, self.user_data, "full", None
            )

            embed = confirmation_view.create_confirmation_embed()
            await interaction.response.edit_message(embed=embed, view=confirmation_view)

        except Exception as e:
            logger.error(f"處理完整重置失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟完整重置確認時發生錯誤", ephemeral=True
            )

    async def _handle_category_reset(self, interaction: discord.Interaction):
        """處理分類重置."""
        try:
            # 顯示分類選擇界面
            category_view = CategoryResetView(self.admin_panel, self.user_data)
            embed = await category_view.create_category_selection_embed()

            await interaction.response.edit_message(embed=embed, view=category_view)

        except Exception as e:
            logger.error(f"處理分類重置失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟分類選擇時發生錯誤", ephemeral=True
            )

    async def _handle_progress_reset(self, interaction: discord.Interaction):
        """處理僅進度重置."""
        try:
            # 顯示進度重置確認對話框
            confirmation_view = ResetConfirmationView(
                self.admin_panel, self.user_data, "progress_only", None
            )

            embed = confirmation_view.create_confirmation_embed()
            await interaction.response.edit_message(embed=embed, view=confirmation_view)

        except Exception as e:
            logger.error(f"處理進度重置失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟進度重置確認時發生錯誤", ephemeral=True
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

class CategoryResetView(ui.View):
    """分類重置視圖."""

    def __init__(self, admin_panel: AdminPanel, user_data: dict[str, Any]):
        """初始化分類重置視圖.

        Args:
            admin_panel: 管理面板控制器
            user_data: 用戶資料
        """
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.user_data = user_data
        self.categories = []

    async def create_category_selection_embed(self) -> discord.Embed:
        """創建分類選擇 Embed."""
        try:
            container = ServiceContainer()
            repository = await container.get_repository()

            user_id = self.user_data["user_id"]
            member = self.user_data["user"]

            # 獲取用戶有資料的分類
            user_achievements = await repository.get_user_achievements(user_id)
            user_progress = await repository.get_user_progress(user_id)

            # 收集所有相關的分類 ID
            category_ids = set()
            for _user_ach, achievement in user_achievements:
                category_ids.add(achievement.category_id)

            for progress in user_progress:
                achievement = await repository.get_achievement(progress.achievement_id)
                if achievement:
                    category_ids.add(achievement.category_id)

            # 獲取分類資訊
            self.categories = []
            for category_id in category_ids:
                try:
                    category = await repository.get_category(category_id)
                    if category:
                        self.categories.append(category)
                except Exception as e:
                    logger.warning(f"獲取分類 {category_id} 失敗: {e}")

            embed = StandardEmbedBuilder.create_info_embed(
                f"📁 選擇重置分類 - {member.display_name}", "選擇要重置的成就分類"
            )

            if not self.categories:
                embed.add_field(
                    name="📋 分類狀態",
                    value="此用戶沒有任何分類的成就資料.",
                    inline=False,
                )
                embed.color = 0x999999
                return embed

            # 顯示可用分類
            category_list = []
            for i, category in enumerate(self.categories, 1):
                # 統計該分類的資料
                category_achievements = [
                    (ua, ach)
                    for ua, ach in user_achievements
                    if ach.category_id == category.id
                ]
                category_progress = [
                    p
                    for p in user_progress
                    if any(
                        ach.category_id == category.id
                        for _, ach in user_achievements
                        if ach.id == p.achievement_id
                    )
                ]

                category_list.append(
                    f"{i}. **{category.name}**\n"
                    f"   📊 成就: {len(category_achievements)} 個 | 進度: {len(category_progress)} 個"
                )

            embed.add_field(
                name=f"📁 可重置的分類 ({len(self.categories)} 個)",
                value="\n\n".join(category_list),
                inline=False,
            )

            # 動態創建分類選擇下拉選單
            self._update_category_select()

            embed.color = 0xFFAA00
            embed.set_footer(text="選擇分類後將進入確認階段")

            return embed

        except Exception as e:
            logger.error(f"創建分類選擇 Embed 失敗: {e}")
            return StandardEmbedBuilder.create_error_embed(
                "載入失敗", "無法載入分類資訊"
            )

    def _update_category_select(self):
        """更新分類選擇下拉選單."""
        # 清除現有的選擇項目
        for item in self.children[:]:
            if isinstance(item, ui.Select):
                self.remove_item(item)

        if not self.categories:
            return

        # 創建分類選項
        options = []
        for category in self.categories:
            options.append(
                discord.SelectOption(
                    label=category.name[:100],  # 限制長度
                    value=str(category.id),
                    description=f"重置分類「{category.name}」的所有資料"[:100],
                    emoji="📁",
                )
            )

        if options:
            select = ui.Select(
                placeholder="選擇要重置的分類...",
                options=options,
                min_values=1,
                max_values=1,
            )

            async def select_callback(interaction: discord.Interaction):
                await self._handle_category_selection(interaction, select)

            select.callback = select_callback
            self.add_item(select)

    async def _handle_category_selection(
        self, interaction: discord.Interaction, select: ui.Select
    ):
        """處理分類選擇."""
        try:
            category_id = int(select.values[0])

            # 查找選中的分類
            selected_category = None
            for category in self.categories:
                if category.id == category_id:
                    selected_category = category
                    break

            if not selected_category:
                await interaction.response.send_message(
                    "❌ 找不到選中的分類", ephemeral=True
                )
                return

            # 顯示分類重置確認對話框
            confirmation_view = ResetConfirmationView(
                self.admin_panel, self.user_data, "category", selected_category
            )

            embed = confirmation_view.create_confirmation_embed()
            await interaction.response.edit_message(embed=embed, view=confirmation_view)

        except Exception as e:
            logger.error(f"處理分類選擇失敗: {e}")
            await interaction.response.send_message(
                "❌ 處理分類選擇時發生錯誤", ephemeral=True
            )

    @ui.button(label="🔙 返回", style=discord.ButtonStyle.secondary)
    async def back_button(self, interaction: discord.Interaction, _button: ui.Button):
        """返回重置選項界面."""
        try:
            reset_view = ResetDataView(self.admin_panel, self.user_data)
            embed = await reset_view.create_reset_options_embed()

            await interaction.response.edit_message(embed=embed, view=reset_view)

        except Exception as e:
            logger.error(f"返回失敗: {e}")
            await interaction.response.send_message("❌ 返回時發生錯誤", ephemeral=True)

class ResetConfirmationView(ui.View):
    """重置確認視圖."""

    def __init__(
        self,
        admin_panel: AdminPanel,
        user_data: dict[str, Any],
        reset_type: str,
        category=None,
    ):
        """初始化重置確認視圖.

        Args:
            admin_panel: 管理面板控制器
            user_data: 用戶資料
            reset_type: 重置類型 (full, category, progress_only)
            category: 分類物件(僅當 reset_type 為 category 時)
        """
        super().__init__(timeout=180)
        self.admin_panel = admin_panel
        self.user_data = user_data
        self.reset_type = reset_type
        self.category = category

    def create_confirmation_embed(self) -> discord.Embed:
        """創建確認 Embed."""
        member = self.user_data["user"]

        # 根據重置類型設定標題和描述
        if self.reset_type == "full":
            title = "🚨 確認完整重置"
            description = f"將清除 {member.mention} 的**所有**成就資料"
            risk_level = "極高"
            color = 0xFF0000
        elif self.reset_type == "category":
            title = "⚠️ 確認分類重置"
            description = (
                f"將清除 {member.mention} 在分類「{self.category.name}」的所有資料"
            )
            risk_level = "中等"
            color = 0xFFAA00
        else:  # progress_only
            title = "📈 確認進度重置"
            description = f"將清除 {member.mention} 的所有進度記錄(保留已獲得的成就)"
            risk_level = "中等"
            color = 0xFFAA00

        embed = StandardEmbedBuilder.create_warning_embed(title, description)
        embed.color = color

        embed.add_field(
            name="👤 目標用戶",
            value=f"**用戶**: {member.display_name}\n**ID**: `{member.id}`",
            inline=True,
        )

        embed.add_field(
            name="🎯 重置範圍", value=self._get_reset_scope_description(), inline=True
        )

        embed.add_field(
            name="⚠️ 風險等級", value=f"**{risk_level}**\n此操作無法撤銷!", inline=True
        )

        embed.add_field(
            name="🔒 安全措施",
            value="• 自動建立資料備份\n"
            "• 記錄到審計日誌\n"
            "• 需要輸入確認碼\n"
            "• 管理員權限驗證",
            inline=False,
        )

        embed.set_footer(text="請點擊「確認設定」輸入確認碼,或點擊「取消」返回")

        return embed

    def _get_reset_scope_description(self) -> str:
        """獲取重置範圍描述."""
        if self.reset_type == "full":
            return "**所有成就資料**\n• 已獲得的成就\n• 所有進度記錄\n• 相關統計資料"
        elif self.reset_type == "category":
            return f"**分類「{self.category.name}」**\n• 該分類的成就\n• 該分類的進度\n• 相關統計資料"
        else:  # progress_only
            return "**僅進度資料**\n• 所有進度記錄\n• 保留已獲得成就\n• 保留成就統計"

    @ui.button(label="⚙️ 確認設定", style=discord.ButtonStyle.danger)
    async def confirm_settings_button(
        self, interaction: discord.Interaction, _button: ui.Button
    ):
        """打開確認設定模態框."""
        try:
            modal = ResetConfirmationModal(self._execute_reset, self.reset_type)
            await interaction.response.send_modal(modal)
        except Exception as e:
            logger.error(f"打開確認設定模態框失敗: {e}")
            await interaction.response.send_message(
                "❌ 打開確認設定時發生錯誤", ephemeral=True
            )

    @ui.button(label="❌ 取消", style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, _button: ui.Button):
        """取消重置."""
        try:
            # 返回重置選項界面
            reset_view = ResetDataView(self.admin_panel, self.user_data)
            embed = await reset_view.create_reset_options_embed()

            await interaction.response.edit_message(embed=embed, view=reset_view)
        except Exception as e:
            logger.error(f"取消重置失敗: {e}")
            await interaction.response.send_message(
                "❌ 取消操作時發生錯誤", ephemeral=True
            )

    async def _execute_reset(self, reason: str, interaction: discord.Interaction):
        """執行重置操作."""
        try:
            await interaction.response.defer(ephemeral=True)

            # 從服務容器獲取用戶管理服務
            pool = await get_database_pool("achievement")
            async with AchievementServiceContainer(
                pool, self.admin_panel.bot
            ) as container:
                user_admin_service = container.user_admin_service

                # 執行重置操作
                category_id = self.category.id if self.category else None
                (
                    success,
                    message,
                    reset_stats,
                ) = await user_admin_service.reset_user_achievements(
                    admin_user_id=self.admin_panel.admin_user_id,
                    target_user_id=self.user_data["user_id"],
                    category_id=category_id,
                    reason=reason,
                )

                if success:
                    # 顯示重置成功結果
                    result_view = ResetResultView(
                        self.admin_panel,
                        self.user_data,
                        self.reset_type,
                        self.category,
                        reset_stats,
                    )

                    embed = result_view.create_success_embed()
                    await interaction.edit_original_response(
                        embed=embed, view=result_view
                    )

                else:
                    # 顯示重置失敗結果
                    embed = StandardEmbedBuilder.create_error_embed(
                        "❌ 重置失敗", f"無法重置用戶資料.\n\n**錯誤原因**: {message}"
                    )

                    # 返回重置選項界面的按鈕
                    back_view = ui.View(timeout=60)
                    back_button = ui.Button(
                        label="🔙 返回選擇", style=discord.ButtonStyle.primary
                    )

                    async def back_callback(back_interaction):
                        reset_view = ResetDataView(self.admin_panel, self.user_data)
                        embed = await reset_view.create_reset_options_embed()
                        await back_interaction.response.edit_message(
                            embed=embed, view=reset_view
                        )

                    back_button.callback = back_callback
                    back_view.add_item(back_button)

                    await interaction.edit_original_response(
                        embed=embed, view=back_view
                    )

        except Exception as e:
            logger.error(f"執行重置操作失敗: {e}")
            try:
                embed = StandardEmbedBuilder.create_error_embed(
                    "❌ 系統錯誤", f"執行重置操作時發生系統錯誤: {e!s}"
                )
                await interaction.edit_original_response(embed=embed, view=None)
            except Exception:
                pass

class ResetConfirmationModal(ui.Modal):
    """重置確認模態框."""

    def __init__(self, callback_func, reset_type: str):
        """初始化重置確認模態框.

        Args:
            callback_func: 回調函數
            reset_type: 重置類型
        """
        super().__init__(title="🚨 重置資料確認")
        self.callback_func = callback_func
        self.reset_type = reset_type

        # 確認碼輸入
        confirmation_code = "RESET" if reset_type == "full" else "CONFIRM"
        self.confirm_input = ui.TextInput(
            label=f"輸入確認碼「{confirmation_code}」",
            placeholder=confirmation_code,
            max_length=20,
            required=True,
        )
        self.add_item(self.confirm_input)

        # 重置原因
        self.reason_input = ui.TextInput(
            label="重置原因",
            placeholder="請輸入重置資料的原因...",
            default="Manual data reset by admin",
            max_length=200,
            required=True,
        )
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        """處理確認提交."""
        try:
            confirmation_code = "RESET" if self.reset_type == "full" else "CONFIRM"

            if self.confirm_input.value.strip().upper() != confirmation_code:
                await interaction.response.send_message(
                    "❌ 確認碼錯誤,重置操作已取消", ephemeral=True
                )
                return

            reason = self.reason_input.value.strip()
            if not reason:
                await interaction.response.send_message(
                    "❌ 重置原因不能為空", ephemeral=True
                )
                return

            await self.callback_func(reason, interaction)

        except Exception as e:
            logger.error(f"處理重置確認失敗: {e}")
            await interaction.response.send_message(
                "❌ 處理確認時發生錯誤", ephemeral=True
            )

class ResetResultView(ui.View):
    """重置結果視圖."""

    def __init__(
        self,
        admin_panel: AdminPanel,
        user_data: dict[str, Any],
        reset_type: str,
        category,
        reset_stats: dict[str, Any],
    ):
        """初始化重置結果視圖.

        Args:
            admin_panel: 管理面板控制器
            user_data: 用戶資料
            reset_type: 重置類型
            category: 分類物件(可選)
            reset_stats: 重置統計
        """
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.user_data = user_data
        self.reset_type = reset_type
        self.category = category
        self.reset_stats = reset_stats

    def create_success_embed(self) -> discord.Embed:
        """創建成功結果 Embed."""
        member = self.user_data["user"]

        embed = StandardEmbedBuilder.create_success_embed(
            "✅ 資料重置成功!", f"已成功重置 {member.mention} 的成就資料"
        )

        embed.add_field(
            name="👤 用戶資訊",
            value=f"**用戶**: {member.display_name}\n**ID**: `{member.id}`",
            inline=True,
        )

        embed.add_field(
            name="🎯 重置範圍", value=self._get_reset_scope_description(), inline=True
        )

        embed.add_field(
            name="📊 重置統計",
            value=f"**清除成就**: {self.reset_stats.get('deleted_achievements', 0)} 個\n"
            f"**清除進度**: {self.reset_stats.get('deleted_progress', 0)} 個\n"
            f"**備份記錄**: {self.reset_stats.get('backup_achievements', 0)} + {self.reset_stats.get('backup_progress', 0)} 筆",
            inline=False,
        )

        embed.set_footer(text="操作已記錄到審計日誌,資料已備份 | 使用下方按鈕繼續操作")

        return embed

    def _get_reset_scope_description(self) -> str:
        """獲取重置範圍描述."""
        if self.reset_type == "full":
            return "**完整重置**\n所有成就資料"
        elif self.reset_type == "category":
            return f"**分類重置**\n{self.category.name}"
        else:  # progress_only
            return "**進度重置**\n僅進度記錄"

    @ui.button(label="🔄 繼續重置", style=discord.ButtonStyle.danger)
    async def continue_reset_button(
        self, interaction: discord.Interaction, _button: ui.Button
    ):
        """繼續其他重置操作."""
        try:
            reset_view = ResetDataView(self.admin_panel, self.user_data)
            embed = await reset_view.create_reset_options_embed()

            await interaction.response.edit_message(embed=embed, view=reset_view)
        except Exception as e:
            logger.error(f"繼續重置失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟重置選項時發生錯誤", ephemeral=True
            )

    @ui.button(label="👤 管理此用戶", style=discord.ButtonStyle.secondary)
    async def manage_user_button(
        self, interaction: discord.Interaction, _button: ui.Button
    ):
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
            logger.error(f"返回用戶管理失敗: {e}")
            await interaction.response.send_message(
                "❌ 返回用戶管理時發生錯誤", ephemeral=True
            )

    @ui.button(label="🔍 搜尋其他用戶", style=discord.ButtonStyle.secondary)
    async def search_other_button(
        self, interaction: discord.Interaction, _button: ui.Button
    ):
        """搜尋其他用戶."""
        try:
            modal = UserSearchModal(self.admin_panel, "reset")
            await interaction.response.send_modal(modal)
        except Exception as e:
            logger.error(f"搜尋其他用戶失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟搜尋時發生錯誤", ephemeral=True
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
