"""進度調整視圖組件.

此模組包含成就進度調整的專用視圖:
- 進度列表顯示
- 進度值調整介面
- 調整結果顯示
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import discord
from discord import ui

from src.cogs.core.base_cog import StandardEmbedBuilder

# 運行時需要的 imports
from src.core.database import get_database_pool

from ..services.service_container import AchievementServiceContainer
from ..services.simple_container import ServiceContainer
from ..services.user_admin_service import UserSearchService
from .admin_panel import AdminPanelState, UserSearchModal
from .user_management_views import UserDetailManagementView, UserSearchResultView

if TYPE_CHECKING:
    from .admin_panel import AdminPanel

logger = logging.getLogger(__name__)

class AdjustProgressView(ui.View):
    """調整進度視圖."""

    def __init__(self, admin_panel: AdminPanel, user_data: dict[str, Any]):
        """初始化調整進度視圖.

        Args:
            admin_panel: 管理面板控制器
            user_data: 用戶資料
        """
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.user_data = user_data
        self.current_page = 0
        self.items_per_page = 5
        self.user_progress = []

    async def create_progress_list_embed(self) -> discord.Embed:
        """創建進度列表 Embed."""
        try:


            container = ServiceContainer()
            repository = await container.get_repository()

            user_id = self.user_data["user_id"]
            member = self.user_data["user"]

            all_progress = await repository.get_user_progress(user_id)
            self.user_progress = [
                p for p in all_progress if p.current_value < p.target_value
            ]

            embed = StandardEmbedBuilder.create_info_embed(
                f"📈 調整進度 - {member.display_name}",
                f"管理 {member.mention} 的成就進度",
            )

            if not self.user_progress:
                embed.add_field(
                    name="📋 進度狀態",
                    value="🎉 此用戶沒有進行中的成就!\n所有成就都已完成或尚未開始.",
                    inline=False,
                )
                embed.color = 0x00FF00
                return embed

            start_idx = self.current_page * self.items_per_page
            end_idx = start_idx + self.items_per_page
            page_progress = self.user_progress[start_idx:end_idx]

            progress_list = []
            for i, progress in enumerate(page_progress, start_idx + 1):
                # 獲取成就資訊
                try:
                    achievement = await repository.get_achievement(
                        progress.achievement_id
                    )
                    if achievement:
                        percentage = (
                            (progress.current_value / progress.target_value * 100)
                            if progress.target_value > 0
                            else 0
                        )

                        # 創建進度條
                        progress_bar = self._create_progress_bar(percentage)

                        progress_list.append(
                            f"{i}. **{achievement.name}** ({achievement.points}pt)\n"
                            f"   {progress_bar} {progress.current_value}/{progress.target_value} ({percentage:.1f}%)\n"
                            f"   📁 未知分類"
                        )
                except Exception as e:
                    logger.warning(f"獲取成就 {progress.achievement_id} 資訊失敗: {e}")
                    progress_list.append(
                        f"{i}. 無法載入成就資訊 (ID: {progress.achievement_id})"
                    )

            if progress_list:
                embed.add_field(
                    name=f"🔄 進行中的成就 ({len(self.user_progress)} 個)",
                    value="\n\n".join(progress_list),
                    inline=False,
                )

            # 分頁資訊
            if len(self.user_progress) > self.items_per_page:
                total_pages = (len(self.user_progress) - 1) // self.items_per_page + 1
                embed.set_footer(
                    text=f"頁面 {self.current_page + 1}/{total_pages} | 選擇成就後點擊「調整」按鈕"
                )
            else:
                embed.set_footer(text="選擇成就後點擊「調整」按鈕")

            # 動態創建進度選擇下拉選單
            self._update_progress_select()

            embed.color = 0x3498DB
            return embed

        except Exception as e:
            logger.error(f"創建進度列表 Embed 失敗: {e}")
            return StandardEmbedBuilder.create_error_embed(
                "載入失敗", "無法載入用戶進度列表"
            )

    def _create_progress_bar(self, percentage: float) -> str:
        """創建進度條."""
        filled = int(percentage / 10)  # 每10%一個方塊
        empty = 10 - filled
        return "█" * filled + "░" * empty

    def _update_progress_select(self):
        """更新進度選擇下拉選單."""
        # 清除現有的選擇項目
        for item in self.children[:]:
            if isinstance(item, ui.Select):
                self.remove_item(item)

        if not self.user_progress:
            return

        # 創建當前頁面的進度選項
        start_idx = self.current_page * self.items_per_page
        end_idx = start_idx + self.items_per_page
        page_progress = self.user_progress[start_idx:end_idx]

        options = []
        for progress in page_progress:
            # 這裡需要獲取成就名稱,暫時使用 ID
            label = f"成就 ID: {progress.achievement_id}"
            description = f"當前: {progress.current_value}/{progress.target_value}"

            options.append(
                discord.SelectOption(
                    label=label[:100],  # 限制長度
                    value=str(progress.achievement_id),
                    description=description[:100],
                    emoji="📈",
                )
            )

        if options:
            select = ui.Select(
                placeholder="選擇要調整進度的成就...",
                options=options,
                min_values=1,
                max_values=1,
            )

            async def select_callback(interaction: discord.Interaction):
                await self._handle_progress_selection(interaction, select)

            select.callback = select_callback
            self.add_item(select)

    async def _handle_progress_selection(
        self, interaction: discord.Interaction, select: ui.Select
    ):
        """處理進度選擇."""
        try:
            achievement_id = int(select.values[0])

            # 查找選中的進度記錄
            selected_progress = None
            for progress in self.user_progress:
                if progress.achievement_id == achievement_id:
                    selected_progress = progress
                    break

            if not selected_progress:
                await interaction.response.send_message(
                    "❌ 找不到選中的進度記錄", ephemeral=True
                )
                return

            # 顯示進度調整模態框
            modal = AdjustProgressModal(
                self.admin_panel, self.user_data, selected_progress
            )
            await interaction.response.send_modal(modal)

        except Exception as e:
            logger.error(f"處理進度選擇失敗: {e}")
            await interaction.response.send_message(
                "❌ 處理進度選擇時發生錯誤", ephemeral=True
            )

    @ui.button(label="◀️", style=discord.ButtonStyle.secondary)
    async def previous_page(self, interaction: discord.Interaction, _button: ui.Button):
        """上一頁."""
        if self.current_page > 0:
            self.current_page -= 1
            embed = await self.create_progress_list_embed()
            await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="▶️", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, _button: ui.Button):
        """下一頁."""
        total_pages = (len(self.user_progress) - 1) // self.items_per_page + 1
        if self.user_progress and self.current_page < total_pages - 1:
            self.current_page += 1
            embed = await self.create_progress_list_embed()
            await interaction.response.edit_message(embed=embed, view=self)

    @ui.button(label="🔄 重新整理", style=discord.ButtonStyle.secondary)
    async def refresh_button(self, interaction: discord.Interaction, _button: ui.Button):
        """重新整理進度列表."""
        try:
            self.current_page = 0
            embed = await self.create_progress_list_embed()
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

class AdjustProgressModal(ui.Modal):
    """進度調整模態框."""

    def __init__(self, admin_panel: AdminPanel, user_data: dict[str, Any], progress):
        """初始化進度調整模態框.

        Args:
            admin_panel: 管理面板控制器
            user_data: 用戶資料
            progress: 進度記錄
        """
        super().__init__(title="📈 調整成就進度")
        self.admin_panel = admin_panel
        self.user_data = user_data
        self.progress = progress

        # 當前進度值輸入
        self.progress_input = ui.TextInput(
            label=f"新的進度值 (目標: {progress.target_value})",
            placeholder=f"請輸入 0 到 {progress.target_value} 之間的數值",
            default=str(progress.current_value),
            max_length=20,
            required=True,
        )
        self.add_item(self.progress_input)

        # 調整原因
        self.reason_input = ui.TextInput(
            label="調整原因",
            placeholder="請輸入調整此進度的原因...",
            default="Manual progress adjustment by admin",
            max_length=200,
            required=True,
        )
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        """處理進度調整提交."""
        try:
            await interaction.response.defer(ephemeral=True)

            # 驗證進度值
            try:
                new_value = float(self.progress_input.value.strip())
            except ValueError:
                await interaction.followup.send(
                    "❌ 進度值必須是有效的數字", ephemeral=True
                )
                return

            if new_value < 0:
                await interaction.followup.send("❌ 進度值不能小於 0", ephemeral=True)
                return

            if new_value > self.progress.target_value:
                await interaction.followup.send(
                    f"❌ 進度值不能大於目標值 {self.progress.target_value}",
                    ephemeral=True,
                )
                return

            reason = self.reason_input.value.strip()
            if not reason:
                await interaction.followup.send("❌ 調整原因不能為空", ephemeral=True)
                return

            # 執行進度調整




            pool = await get_database_pool("achievement")
            async with AchievementServiceContainer(
                pool, self.admin_panel.bot
            ) as container:
                user_admin_service = container.user_admin_service

                (
                    success,
                    message,
                    updated_progress,
                ) = await user_admin_service.update_user_progress(
                    admin_user_id=self.admin_panel.admin_user_id,
                    target_user_id=self.user_data["user_id"],
                    achievement_id=self.progress.achievement_id,
                    new_value=new_value,
                    reason=reason,
                )

                if success:
                    # 顯示調整成功結果
                    result_view = AdjustProgressResultView(
                        self.admin_panel,
                        self.user_data,
                        self.progress,
                        updated_progress,
                        new_value,
                    )

                    embed = result_view.create_success_embed()
                    await interaction.edit_original_response(
                        embed=embed, view=result_view
                    )

                else:
                    # 顯示調整失敗結果
                    embed = StandardEmbedBuilder.create_error_embed(
                        "❌ 調整失敗", f"無法調整進度.\n\n**錯誤原因**: {message}"
                    )

                    # 返回進度選擇界面的按鈕
                    back_view = ui.View(timeout=60)
                    back_button = ui.Button(
                        label="🔙 返回選擇", style=discord.ButtonStyle.primary
                    )

                    async def back_callback(back_interaction):
                        adjust_view = AdjustProgressView(
                            self.admin_panel, self.user_data
                        )
                        embed = await adjust_view.create_progress_list_embed()
                        await back_interaction.response.edit_message(
                            embed=embed, view=adjust_view
                        )

                    back_button.callback = back_callback
                    back_view.add_item(back_button)

                    await interaction.edit_original_response(
                        embed=embed, view=back_view
                    )

        except Exception as e:
            logger.error(f"處理進度調整失敗: {e}")
            try:
                embed = StandardEmbedBuilder.create_error_embed(
                    "❌ 系統錯誤", f"執行進度調整時發生系統錯誤: {e!s}"
                )
                await interaction.edit_original_response(embed=embed, view=None)
            except Exception:
                pass

class AdjustProgressResultView(ui.View):
    """進度調整結果視圖."""

    def __init__(
        self,
        admin_panel: AdminPanel,
        user_data: dict[str, Any],
        original_progress,
        updated_progress,
        new_value: float,
    ):
        """初始化進度調整結果視圖.

        Args:
            admin_panel: 管理面板控制器
            user_data: 用戶資料
            original_progress: 原始進度記錄
            updated_progress: 更新後的進度記錄
            new_value: 新的進度值
        """
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.user_data = user_data
        self.original_progress = original_progress
        self.updated_progress = updated_progress
        self.new_value = new_value

    def create_success_embed(self) -> discord.Embed:
        """創建成功結果 Embed."""
        member = self.user_data["user"]

        embed = StandardEmbedBuilder.create_success_embed(
            "✅ 進度調整成功!", f"已成功調整 {member.mention} 的成就進度"
        )

        embed.add_field(
            name="👤 用戶資訊",
            value=f"**用戶**: {member.display_name}\n**ID**: `{member.id}`",
            inline=True,
        )

        embed.add_field(
            name="📈 進度變更",
            value=f"**原進度**: {self.original_progress.current_value}/{self.original_progress.target_value}\n"
            f"**新進度**: {self.new_value}/{self.original_progress.target_value}\n"
            f"**變更**: {self.new_value - self.original_progress.current_value:+.1f}",
            inline=True,
        )

        # 如果達成成就,顯示特別提示
        if self.new_value >= self.original_progress.target_value:
            embed.add_field(
                name="🎉 成就完成!",
                value="進度已達到目標值,成就已自動授予給用戶!",
                inline=False,
            )

        embed.add_field(
            name="📅 調整時間",
            value=discord.utils.format_dt(self.updated_progress.last_updated, "F"),
            inline=False,
        )

        embed.set_footer(text="操作已記錄到審計日誌 | 使用下方按鈕繼續操作")

        return embed

    @ui.button(label="📈 繼續調整", style=discord.ButtonStyle.primary)
    async def continue_adjust_button(
        self, interaction: discord.Interaction, _button: ui.Button
    ):
        """繼續調整其他進度."""
        try:
            adjust_view = AdjustProgressView(self.admin_panel, self.user_data)
            embed = await adjust_view.create_progress_list_embed()

            await interaction.response.edit_message(embed=embed, view=adjust_view)
        except Exception as e:
            logger.error(f"繼續調整失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟進度選擇時發生錯誤", ephemeral=True
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


            modal = UserSearchModal(self.admin_panel, "adjust")
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
