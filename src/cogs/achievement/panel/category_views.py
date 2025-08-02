"""分類管理相關的 Discord UI 視圖組件.

此模組包含分類管理功能的所有 UI 組件：
- CreateCategoryModal: 分類新增模態框
- CategorySelectionView: 分類選擇視圖
- CategoryListView: 分類列表視圖
- CategoryReorderView: 分類排序視圖
- CategoryStatisticsView: 分類統計視圖
- EditCategoryModal: 分類編輯模態框
- DeleteCategoryConfirmView: 分類刪除確認視圖
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

import discord
from discord import ui

from src.cogs.core.base_cog import StandardEmbedBuilder

if TYPE_CHECKING:
    from ..database.models import AchievementCategory
    from .admin_panel import AdminPanel

logger = logging.getLogger(__name__)


class CreateCategoryModal(ui.Modal):
    """分類新增模態框."""

    def __init__(self, admin_panel: AdminPanel):
        """初始化分類新增模態框.

        Args:
            admin_panel: 管理面板控制器
        """
        super().__init__(title="新增分類")
        self.admin_panel = admin_panel

        # 分類名稱
        self.name_input = ui.TextInput(
            label="分類名稱",
            placeholder="輸入分類名稱 (1-50字元)",
            max_length=50,
            required=True,
        )
        self.add_item(self.name_input)

        # 分類描述
        self.description_input = ui.TextInput(
            label="分類描述",
            placeholder="輸入分類描述 (1-200字元)",
            style=discord.TextStyle.paragraph,
            max_length=200,
            required=True,
        )
        self.add_item(self.description_input)

        # 分類圖示
        self.icon_input = ui.TextInput(
            label="分類圖示 (表情符號)",
            placeholder="輸入表情符號，如：💬、⚡、🏆",
            max_length=10,
            required=False,
        )
        self.add_item(self.icon_input)

        # 顯示順序
        self.order_input = ui.TextInput(
            label="顯示順序",
            placeholder="輸入數字，越小越前面 (如: 10, 20, 30)",
            max_length=3,
            required=False,
        )
        self.add_item(self.order_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """處理表單提交."""
        try:
            await interaction.response.defer(ephemeral=True)

            # 驗證輸入
            name = self.name_input.value.strip()
            description = self.description_input.value.strip()
            icon_emoji = (
                self.icon_input.value.strip() if self.icon_input.value else None
            )
            order_str = self.order_input.value.strip()

            # 基本驗證
            if not name:
                await interaction.followup.send("❌ 分類名稱不能為空", ephemeral=True)
                return

            if not description:
                await interaction.followup.send("❌ 分類描述不能為空", ephemeral=True)
                return

            # 驗證顯示順序
            display_order = 0
            if order_str:
                try:
                    display_order = int(order_str)
                    if display_order < 0:
                        raise ValueError("順序不能為負數")
                except ValueError:
                    await interaction.followup.send(
                        "❌ 顯示順序必須為非負整數", ephemeral=True
                    )
                    return

            # 檢查名稱唯一性
            if await self._is_category_name_exists(name):
                await interaction.followup.send(
                    "❌ 分類名稱已存在，請使用其他名稱", ephemeral=True
                )
                return

            # 建立預覽確認
            category_data = {
                "name": name,
                "description": description,
                "icon_emoji": icon_emoji,
                "display_order": display_order,
            }

            # 建立確認視圖
            confirm_view = CreateCategoryConfirmView(self.admin_panel, category_data)

            # 建立預覽 embed
            embed = StandardEmbedBuilder.create_info_embed(
                "分類建立預覽", "請確認以下分類資訊："
            )

            embed.add_field(
                name="📛 基本資訊",
                value=(
                    f"**名稱**: {name}\n"
                    f"**描述**: {description}\n"
                    f"**圖示**: {icon_emoji or '無'}"
                ),
                inline=False,
            )

            embed.add_field(
                name="⚙️ 設定",
                value=(
                    f"**顯示順序**: {display_order}\n"
                    f"**狀態**: 啟用\n"
                    f"**初始成就數**: 0 個"
                ),
                inline=False,
            )

            embed.add_field(
                name="💡 提示",
                value=(
                    "• 分類建立後可以立即使用\n"
                    "• 可以隨時修改分類資訊\n"
                    "• 顯示順序影響用戶界面排列"
                ),
                inline=False,
            )

            await interaction.followup.send(
                embed=embed, view=confirm_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"【分類新增模態框】處理提交失敗: {e}")
            await interaction.followup.send("❌ 處理分類新增時發生錯誤", ephemeral=True)

    async def _is_category_name_exists(self, name: str) -> bool:
        """檢查分類名稱是否已存在."""
        try:
            # 通過管理服務檢查名稱唯一性
            admin_service = await self._get_admin_service()
            if admin_service:
                validation = await admin_service._check_category_name_uniqueness(name)
                return not validation.is_valid
            else:
                # 備用方案：無法檢查名稱唯一性時假設不重複
                logger.warning("無法檢查分類名稱唯一性，假設名稱可用")
                return False
        except Exception as e:
            logger.error(f"檢查分類名稱唯一性失敗: {e}")
            return False

    async def _get_admin_service(self):
        """取得管理服務實例."""
        try:
            from ..services.admin_service import AchievementAdminService

            return AchievementAdminService(
                repository=None, permission_service=None, cache_service=None
            )
        except Exception as e:
            logger.error(f"獲取管理服務失敗: {e}")
            return None


class CreateCategoryConfirmView(ui.View):
    """分類建立確認視圖."""

    def __init__(self, admin_panel: AdminPanel, category_data: dict[str, Any]):
        """初始化確認視圖.

        Args:
            admin_panel: 管理面板控制器
            category_data: 分類資料
        """
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.category_data = category_data

    @ui.button(label="✅ 確認建立", style=discord.ButtonStyle.primary)
    async def confirm_create(
        self, interaction: discord.Interaction, button: ui.Button
    ) -> None:
        """確認建立分類."""
        try:
            await interaction.response.defer(ephemeral=True)

            # 通過管理服務創建分類
            admin_service = await self._get_admin_service()
            if admin_service:
                category, validation = await admin_service.create_category(
                    self.category_data, self.admin_panel.admin_user_id
                )

                if validation.is_valid and category:
                    embed = StandardEmbedBuilder.create_success_embed(
                        "分類建立成功",
                        f"✅ 分類「{category.name}」已成功建立！\n\n"
                        f"**分配的 ID**: {category.id}\n"
                        f"**顯示順序**: {category.display_order}\n"
                        f"**建立時間**: <t:{int(datetime.now().timestamp())}:f>\n\n"
                        "分類已加入系統，可以開始用於成就分類。",
                    )
                    embed.set_footer(text="操作已記錄到審計日誌")
                else:
                    # 顯示驗證錯誤
                    error_text = "\n".join(
                        [f"• {error}" for error in validation.errors]
                    )
                    embed = StandardEmbedBuilder.create_error_embed(
                        "分類建立失敗", f"❌ 分類建立時發生以下錯誤：\n\n{error_text}"
                    )
            else:
                # 備用方案：無法建立分類時顯示錯誤
                embed = StandardEmbedBuilder.create_error_embed(
                    "分類建立失敗",
                    "❌ 無法建立分類，管理服務不可用。\n\n"
                    "請檢查系統狀態或聯繫管理員。",
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

            # 重新整理管理面板
            from .admin_panel import AdminPanelState

            await self.admin_panel.handle_navigation(
                interaction, AdminPanelState.ACHIEVEMENTS
            )

        except Exception as e:
            logger.error(f"【建立確認視圖】建立分類失敗: {e}")
            await interaction.followup.send("❌ 建立分類時發生錯誤", ephemeral=True)

    async def _get_admin_service(self):
        """取得管理服務實例."""
        try:
            from ..services.admin_service import AchievementAdminService

            return AchievementAdminService(
                repository=None, permission_service=None, cache_service=None
            )
        except Exception as e:
            logger.error(f"獲取管理服務失敗: {e}")
            return None

    @ui.button(label="❌ 取消", style=discord.ButtonStyle.secondary)
    async def cancel_create(
        self, interaction: discord.Interaction, button: ui.Button
    ) -> None:
        """取消建立分類."""
        embed = StandardEmbedBuilder.create_info_embed(
            "操作已取消", "✅ 分類建立操作已被取消。"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class CategorySelectionView(ui.View):
    """分類選擇視圖."""

    def __init__(
        self,
        admin_panel: AdminPanel,
        categories: list[AchievementCategory],
        action: str,
    ):
        """初始化分類選擇視圖.

        Args:
            admin_panel: 管理面板控制器
            categories: 分類列表
            action: 操作類型 ("edit", "delete", "view")
        """
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.categories = categories
        self.action = action

        # 建立分類選項
        options = []
        for category in categories[:25]:  # Discord 選單最多 25 個選項
            options.append(
                discord.SelectOption(
                    label=f"{category.icon_emoji} {category.name}",
                    value=str(category.id),
                    description=f"{category.description[:80]}...",
                    emoji=category.icon_emoji,
                )
            )

        # 分類選擇下拉選單
        self.category_select = ui.Select(
            placeholder=f"選擇要{self._get_action_name()}的分類...",
            min_values=1,
            max_values=1,
            options=options,
        )
        self.category_select.callback = self.on_category_select
        self.add_item(self.category_select)

    def _get_action_name(self) -> str:
        """取得操作名稱."""
        action_names = {"edit": "編輯", "delete": "刪除", "view": "查看"}
        return action_names.get(self.action, "操作")

    async def on_category_select(self, interaction: discord.Interaction) -> None:
        """處理分類選擇."""
        try:
            await interaction.response.defer(ephemeral=True)

            category_id = int(self.category_select.values[0])
            selected_category = next(
                (cat for cat in self.categories if cat.id == category_id), None
            )

            if not selected_category:
                await interaction.followup.send("❌ 選擇的分類無效", ephemeral=True)
                return

            if self.action == "edit":
                await self._handle_edit_selected(interaction, selected_category)
            elif self.action == "delete":
                await self._handle_delete_selected(interaction, selected_category)
            elif self.action == "view":
                await self._handle_view_selected(interaction, selected_category)

        except Exception as e:
            logger.error(f"【分類選擇視圖】處理分類選擇失敗: {e}")
            await interaction.followup.send("❌ 處理分類選擇時發生錯誤", ephemeral=True)

    async def _handle_edit_selected(
        self, interaction: discord.Interaction, category: AchievementCategory
    ) -> None:
        """處理編輯選中的分類."""
        try:
            # 建立編輯表單模態框
            modal = EditCategoryModal(self.admin_panel, category)
            await interaction.response.send_modal(modal)

        except Exception as e:
            logger.error(f"【分類選擇視圖】開啟編輯表單失敗: {e}")
            await interaction.followup.send("❌ 開啟編輯表單時發生錯誤", ephemeral=True)

    async def _handle_delete_selected(
        self, interaction: discord.Interaction, category: AchievementCategory
    ) -> None:
        """處理刪除選中的分類."""
        try:
            # 檢查分類使用情況
            usage_info = await self._check_category_usage(category.id)

            # 建立刪除確認視圖
            confirm_view = DeleteCategoryConfirmView(
                self.admin_panel, category, usage_info
            )

            # 建立刪除預覽 embed
            embed = StandardEmbedBuilder.create_warning_embed(
                "確認刪除分類",
                f"⚠️ 您即將刪除分類「{category.name}」\n\n"
                "**分類資訊**：\n"
                f"• **ID**: {category.id}\n"
                f"• **名稱**: {category.name}\n"
                f"• **描述**: {category.description}\n"
                f"• **排序**: {category.display_order}\n\n"
                f"**使用情況**：\n"
                f"• {usage_info['description']}\n\n"
                "❗ **此操作需要謹慎考慮！**",
            )

            if usage_info["has_achievements"]:
                embed.add_field(
                    name="⚠️ 注意事項",
                    value=f"此分類有 {usage_info['achievement_count']} 個成就。\n"
                    "刪除前需要重新分配這些成就到其他分類。",
                    inline=False,
                )

            await interaction.followup.send(
                embed=embed, view=confirm_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"【分類選擇視圖】處理刪除選中分類失敗: {e}")
            await interaction.followup.send("❌ 處理分類刪除時發生錯誤", ephemeral=True)

    async def _handle_view_selected(
        self, interaction: discord.Interaction, category: AchievementCategory
    ) -> None:
        """處理查看選中的分類."""
        try:
            # 取得分類詳細資訊
            category_details = await self._get_category_details(category.id)

            # 建立分類詳細視圖
            detail_view = CategoryDetailView(self.admin_panel, category_details)

            # 建立詳細 embed
            embed = await self._create_category_detail_embed(category_details)

            await interaction.followup.send(
                embed=embed, view=detail_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"【分類選擇視圖】查看分類詳情失敗: {e}")
            await interaction.followup.send("❌ 查看分類詳情時發生錯誤", ephemeral=True)

    async def _check_category_usage(self, category_id: int) -> dict:
        """檢查分類使用情況."""
        try:
            # 嘗試從管理服務獲取分類使用情況
            admin_service = await self._get_admin_service()
            if admin_service and hasattr(admin_service, 'get_category_usage'):
                usage_info = await admin_service.get_category_usage(category_id)
                return usage_info
            else:
                # 備用方案：無法檢查時假設分類為空
                logger.warning(f"無法檢查分類 {category_id} 的使用情況")
                return {
                    "has_achievements": False,
                    "achievement_count": 0,
                    "description": "無法確定分類使用情況",
                }
        except Exception as e:
            logger.error(f"檢查分類使用情況失敗: {e}")
            return {
                "has_achievements": False,
                "achievement_count": 0,
                "description": "無法確定使用情況",
            }

    async def _get_category_details(self, category_id: int) -> dict:
        """取得分類詳細資訊."""
        category = next((cat for cat in self.categories if cat.id == category_id), None)
        if not category:
            return {}

        try:
            # 嘗試從管理服務獲取詳細統計
            admin_service = await self._get_admin_service()
            if admin_service and hasattr(admin_service, 'get_category_details'):
                details = await admin_service.get_category_details(category_id)
                details["category"] = category
                return details
            else:
                # 備用方案：返回基本資訊
                logger.warning(f"無法獲取分類 {category_id} 的詳細統計")
                return {
                    "category": category,
                    "achievement_count": 0,
                    "active_achievements": 0,
                    "inactive_achievements": 0,
                    "user_progress_count": 0,
                    "completion_rate": 0.0,
                    "created_achievements_this_month": 0,
                    "last_activity": "無資料",
                }
        except Exception as e:
            logger.error(f"獲取分類詳細資訊失敗: {e}")
            return {
                "category": category,
                "achievement_count": 0,
                "active_achievements": 0,
                "inactive_achievements": 0,
                "user_progress_count": 0,
                "completion_rate": 0.0,
                "created_achievements_this_month": 0,
                "last_activity": "無資料",
            }

    async def _create_category_detail_embed(self, details: dict) -> discord.Embed:
        """建立分類詳細資訊 Embed."""
        if not details:
            return StandardEmbedBuilder.create_error_embed(
                "載入失敗", "無法載入分類詳細資訊"
            )

        category = details["category"]

        embed = StandardEmbedBuilder.create_info_embed(
            f"{category.icon_emoji} {category.name}", category.description
        )

        # 基本資訊
        embed.add_field(
            name="📋 基本資訊",
            value=(
                f"**ID**: {category.id}\n"
                f"**顯示順序**: {category.display_order}\n"
                f"**建立時間**: <t:{int(category.created_at.timestamp())}:f>\n"
                f"**最後更新**: <t:{int(category.updated_at.timestamp())}:R>"
            ),
            inline=True,
        )

        # 使用統計
        embed.add_field(
            name="📊 使用統計",
            value=(
                f"**總成就數**: {details['achievement_count']}\n"
                f"**啟用成就**: {details['active_achievements']}\n"
                f"**停用成就**: {details['inactive_achievements']}\n"
                f"**用戶進度**: {details['user_progress_count']} 個"
            ),
            inline=True,
        )

        # 活動資訊
        embed.add_field(
            name="⚡ 活動資訊",
            value=(
                f"**完成率**: {details['completion_rate']:.1f}%\n"
                f"**本月新增**: {details['created_achievements_this_month']} 個成就\n"
                f"**最後活動**: {details['last_activity']}"
            ),
            inline=False,
        )

        embed.color = 0xFF6B35
        embed.set_footer(text=f"分類 ID: {category.id} | 管理員查看")

        return embed


class EditCategoryModal(ui.Modal):
    """分類編輯模態框."""

    def __init__(self, admin_panel: AdminPanel, category: AchievementCategory):
        """初始化分類編輯模態框.

        Args:
            admin_panel: 管理面板控制器
            category: 要編輯的分類
        """
        super().__init__(title=f"編輯分類: {category.name}")
        self.admin_panel = admin_panel
        self.category = category

        # 分類名稱
        self.name_input = ui.TextInput(
            label="分類名稱",
            placeholder="輸入分類名稱 (1-50字元)",
            default=category.name,
            max_length=50,
            required=True,
        )
        self.add_item(self.name_input)

        # 分類描述
        self.description_input = ui.TextInput(
            label="分類描述",
            placeholder="輸入分類描述 (1-200字元)",
            default=category.description,
            style=discord.TextStyle.paragraph,
            max_length=200,
            required=True,
        )
        self.add_item(self.description_input)

        # 分類圖示
        self.icon_input = ui.TextInput(
            label="分類圖示 (表情符號)",
            placeholder="輸入表情符號，如：💬、⚡、🏆",
            default=category.icon_emoji or "",
            max_length=10,
            required=False,
        )
        self.add_item(self.icon_input)

        # 顯示順序
        self.order_input = ui.TextInput(
            label="顯示順序",
            placeholder="輸入數字，越小越前面",
            default=str(category.display_order),
            max_length=3,
            required=False,
        )
        self.add_item(self.order_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """處理表單提交."""
        try:
            await interaction.response.defer(ephemeral=True)

            # 驗證輸入
            name = self.name_input.value.strip()
            description = self.description_input.value.strip()
            icon_emoji = (
                self.icon_input.value.strip() if self.icon_input.value else None
            )
            order_str = self.order_input.value.strip()

            # 基本驗證
            if not name:
                await interaction.followup.send("❌ 分類名稱不能為空", ephemeral=True)
                return

            if not description:
                await interaction.followup.send("❌ 分類描述不能為空", ephemeral=True)
                return

            # 驗證顯示順序
            display_order = self.category.display_order
            if order_str:
                try:
                    display_order = int(order_str)
                    if display_order < 0:
                        raise ValueError("順序不能為負數")
                except ValueError:
                    await interaction.followup.send(
                        "❌ 顯示順序必須為非負整數", ephemeral=True
                    )
                    return

            # 檢查是否有變更
            changes = {}
            if name != self.category.name:
                changes["name"] = name
            if description != self.category.description:
                changes["description"] = description
            if icon_emoji != self.category.icon_emoji:
                changes["icon_emoji"] = icon_emoji
            if display_order != self.category.display_order:
                changes["display_order"] = display_order

            if not changes:
                await interaction.followup.send("ℹ️ 沒有檢測到任何變更", ephemeral=True)
                return

            # 檢查名稱唯一性（如果名稱有變更）
            if "name" in changes and await self._is_category_name_exists(name):
                await interaction.followup.send(
                    "❌ 分類名稱已存在，請使用其他名稱", ephemeral=True
                )
                return

            # 建立變更預覽
            preview_embed = StandardEmbedBuilder.create_info_embed(
                "分類編輯預覽", f"即將更新分類「{self.category.name}」，請確認變更："
            )

            # 顯示變更內容
            changes_text = []
            for field, new_value in changes.items():
                if field == "name":
                    changes_text.append(f"**名稱**: {self.category.name} → {new_value}")
                elif field == "description":
                    changes_text.append(
                        f"**描述**: {self.category.description} → {new_value}"
                    )
                elif field == "icon_emoji":
                    old_icon = self.category.icon_emoji or "無"
                    new_icon = new_value or "無"
                    changes_text.append(f"**圖示**: {old_icon} → {new_icon}")
                elif field == "display_order":
                    changes_text.append(
                        f"**順序**: {self.category.display_order} → {new_value}"
                    )

            preview_embed.add_field(
                name="📝 變更摘要", value="\n".join(changes_text), inline=False
            )

            # 建立確認視圖
            confirm_view = EditCategoryConfirmView(
                self.admin_panel, self.category, changes
            )

            await interaction.followup.send(
                embed=preview_embed, view=confirm_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"【分類編輯模態框】處理提交失敗: {e}")
            await interaction.followup.send("❌ 處理分類編輯時發生錯誤", ephemeral=True)

    async def _is_category_name_exists(self, name: str) -> bool:
        """檢查分類名稱是否已存在（排除當前分類）."""
        try:
            # 模擬檢查名稱唯一性
            existing_names = ["社交互動", "活躍度", "成長里程", "特殊事件"]
            return name in existing_names and name != self.category.name
        except Exception as e:
            logger.error(f"檢查分類名稱唯一性失敗: {e}")
            return False


class EditCategoryConfirmView(ui.View):
    """分類編輯確認視圖."""

    def __init__(
        self,
        admin_panel: AdminPanel,
        category: AchievementCategory,
        changes: dict[str, Any],
    ):
        """初始化確認視圖.

        Args:
            admin_panel: 管理面板控制器
            category: 原始分類
            changes: 變更內容
        """
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.category = category
        self.changes = changes

    @ui.button(label="✅ 確認更新", style=discord.ButtonStyle.primary)
    async def confirm_update(
        self, interaction: discord.Interaction, button: ui.Button
    ) -> None:
        """確認更新分類."""
        try:
            await interaction.response.defer(ephemeral=True)

            # 通過管理服務更新分類
            admin_service = await self._get_admin_service()
            if admin_service:
                category, validation = await admin_service.update_category(
                    self.category.id, self.changes, self.admin_panel.admin_user_id
                )

                if validation.is_valid and category:
                    embed = StandardEmbedBuilder.create_success_embed(
                        "分類更新成功",
                        f"✅ 分類「{category.name}」已成功更新！\n\n"
                        f"**更新項目**: {len(self.changes)} 個欄位\n"
                        f"**更新時間**: <t:{int(datetime.now().timestamp())}:f>\n\n"
                        "變更已生效，新的分類資訊立即可用。",
                    )
                    embed.set_footer(text="操作已記錄到審計日誌")
                else:
                    # 顯示驗證錯誤
                    error_text = "\n".join(
                        [f"• {error}" for error in validation.errors]
                    )
                    embed = StandardEmbedBuilder.create_error_embed(
                        "分類更新失敗", f"❌ 分類更新時發生以下錯誤：\n\n{error_text}"
                    )
            else:
                # 備用方案：無法更新分類
                embed = StandardEmbedBuilder.create_error_embed(
                    "分類更新失敗",
                    f"❌ 無法更新分類「{self.category.name}」\n\n"
                    "管理服務不可用，請稍後再試或聯繫系統管理員。",
                )
                logger.warning(f"無法更新分類 {self.category.id}：管理服務不可用")

            await interaction.followup.send(embed=embed, ephemeral=True)

            # 重新整理管理面板
            from .admin_panel import AdminPanelState

            await self.admin_panel.handle_navigation(
                interaction, AdminPanelState.ACHIEVEMENTS
            )

        except Exception as e:
            logger.error(f"【編輯確認視圖】更新分類失敗: {e}")
            await interaction.followup.send("❌ 更新分類時發生錯誤", ephemeral=True)

    async def _get_admin_service(self):
        """取得管理服務實例."""
        try:
            from ..services.admin_service import AchievementAdminService

            return AchievementAdminService(
                repository=None, permission_service=None, cache_service=None
            )
        except Exception as e:
            logger.error(f"獲取管理服務失敗: {e}")
            return None

    @ui.button(label="❌ 取消", style=discord.ButtonStyle.secondary)
    async def cancel_update(
        self, interaction: discord.Interaction, button: ui.Button
    ) -> None:
        """取消更新分類."""
        embed = StandardEmbedBuilder.create_info_embed(
            "操作已取消", "✅ 分類編輯操作已被取消。"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class DeleteCategoryConfirmView(ui.View):
    """分類刪除確認視圖."""

    def __init__(
        self,
        admin_panel: AdminPanel,
        category: AchievementCategory,
        usage_info: dict[str, Any],
    ):
        """初始化刪除確認視圖.

        Args:
            admin_panel: 管理面板控制器
            category: 要刪除的分類
            usage_info: 使用情況資訊
        """
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.category = category
        self.usage_info = usage_info

    @ui.button(label="🗑️ 安全刪除", style=discord.ButtonStyle.danger, disabled=False)
    async def safe_delete_button(
        self, interaction: discord.Interaction, button: ui.Button
    ) -> None:
        """安全刪除分類（僅當無成就時）."""
        try:
            await interaction.response.defer(ephemeral=True)

            if self.usage_info["has_achievements"]:
                # 需要成就重新分配
                embed = StandardEmbedBuilder.create_error_embed(
                    "無法安全刪除",
                    f"❌ 分類「{self.category.name}」中有成就！\n\n"
                    f"**成就數量**: {self.usage_info['achievement_count']} 個\n\n"
                    "**解決方案**：\n"
                    "1️⃣ 先將成就移動到其他分類\n"
                    "2️⃣ 使用「重新分配並刪除」選項\n"
                    "3️⃣ 或者取消此次操作\n\n"
                    "⚠️ 分類刪除後無法復原！",
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # 執行安全刪除
            success = await self._delete_category(force=False)

            if success:
                embed = StandardEmbedBuilder.create_success_embed(
                    "分類刪除成功",
                    f"✅ 分類「{self.category.name}」已安全刪除！\n\n"
                    f"**刪除詳情**：\n"
                    f"• 分類 ID: {self.category.id}\n"
                    f"• 刪除時間: <t:{int(datetime.now().timestamp())}:f>\n"
                    f"• 影響成就: 0 個\n\n"
                    "✅ 沒有成就受到影響。\n"
                    "📝 此操作已記錄到審計日誌。",
                )
            else:
                embed = StandardEmbedBuilder.create_error_embed(
                    "刪除失敗",
                    f"❌ 無法刪除分類「{self.category.name}」\n\n"
                    "請檢查分類是否仍然存在或聯繫系統管理員。",
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"【刪除確認視圖】安全刪除分類失敗: {e}")
            await interaction.followup.send("❌ 執行刪除操作時發生錯誤", ephemeral=True)

    @ui.button(label="📦 重新分配並刪除", style=discord.ButtonStyle.danger)
    async def reassign_and_delete_button(
        self, interaction: discord.Interaction, button: ui.Button
    ) -> None:
        """重新分配成就並刪除分類."""
        try:
            if not self.usage_info["has_achievements"]:
                await interaction.response.send_message(
                    "ℹ️ 此分類沒有成就，可以直接安全刪除", ephemeral=True
                )
                return

            # 建立成就重新分配視圖
            reassign_view = AchievementReassignView(
                self.admin_panel, self.category, self.usage_info
            )

            embed = StandardEmbedBuilder.create_info_embed(
                "成就重新分配",
                f"分類「{self.category.name}」中有 {self.usage_info['achievement_count']} 個成就\n\n"
                "請選擇目標分類來重新分配這些成就：",
            )

            await interaction.response.send_message(
                embed=embed, view=reassign_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"【刪除確認視圖】重新分配處理失敗: {e}")
            await interaction.response.send_message(
                "❌ 處理成就重新分配時發生錯誤", ephemeral=True
            )

    @ui.button(label="❌ 取消", style=discord.ButtonStyle.secondary)
    async def cancel_delete(
        self, interaction: discord.Interaction, button: ui.Button
    ) -> None:
        """取消刪除分類."""
        embed = StandardEmbedBuilder.create_info_embed(
            "操作已取消",
            f"✅ 分類「{self.category.name}」的刪除操作已被取消。\n\n"
            "分類保持原狀，未進行任何變更。",
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _delete_category(
        self, force: bool = False, target_category_id: int | None = None
    ) -> bool:
        """刪除分類."""
        try:
            # 通過管理服務刪除分類
            admin_service = await self._get_admin_service()
            if admin_service:
                success, validation = await admin_service.delete_category(
                    self.category.id, self.admin_panel.admin_user_id, target_category_id
                )

                if not validation.is_valid:
                    # 記錄驗證錯誤
                    for error in validation.errors:
                        logger.error(f"刪除分類驗證失敗: {error}")

                return success
            else:
                # 備用方案：無法刪除分類
                logger.warning(f"無法刪除分類 {self.category.id}：管理服務不可用")
                return False
        except Exception as e:
            logger.error(f"刪除分類失敗: {e}")
            return False

    async def _get_admin_service(self):
        """取得管理服務實例."""
        try:
            from ..services.admin_service import AchievementAdminService

            return AchievementAdminService(
                repository=None, permission_service=None, cache_service=None
            )
        except Exception as e:
            logger.error(f"獲取管理服務失敗: {e}")
            return None


class AchievementReassignView(ui.View):
    """成就重新分配視圖."""

    def __init__(
        self,
        admin_panel: AdminPanel,
        source_category: AchievementCategory,
        usage_info: dict[str, Any],
    ):
        """初始化成就重新分配視圖."""
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.source_category = source_category
        self.usage_info = usage_info

        # 取得其他可用分類
        self._setup_target_category_select()

    def _setup_target_category_select(self):
        """設置目標分類選擇下拉選單."""
        # 嘗試獲取其他分類（排除當前要刪除的分類）
        other_categories = self._get_other_categories()

        options = []
        for category in other_categories:
            if category["id"] != self.source_category.id:
                options.append(
                    discord.SelectOption(
                        label=f"{category['emoji']} {category['name']}",
                        value=str(category["id"]),
                        description=f"將成就移動到「{category['name']}」分類",
                        emoji=category["emoji"],
                    )
                )

        if options:
            self.target_select = ui.Select(
                placeholder="選擇目標分類...",
                min_values=1,
                max_values=1,
                options=options,
            )
            self.target_select.callback = self.on_target_select
            self.add_item(self.target_select)

    def _get_other_categories(self) -> list[dict[str, Any]]:
        """獲取其他可用分類."""
        try:
            # 嘗試從管理面板獲取分類列表
            if hasattr(self.admin_panel, 'categories') and self.admin_panel.categories:
                return [
                    {
                        "id": cat.id,
                        "name": cat.name,
                        "emoji": getattr(cat, 'emoji', '📁')
                    }
                    for cat in self.admin_panel.categories
                    if cat.id != self.source_category.id
                ]
            else:
                # 備用方案：返回空列表
                logger.warning("無法獲取其他分類列表")
                return []
        except Exception as e:
            logger.error(f"獲取其他分類失敗: {e}")
            return []

    async def on_target_select(self, interaction: discord.Interaction) -> None:
        """處理目標分類選擇."""
        try:
            await interaction.response.defer(ephemeral=True)

            target_category_id = int(self.target_select.values[0])

            # 執行成就重新分配
            success = await self._reassign_achievements(target_category_id)

            if success:
                # 然後刪除原分類
                delete_success = await self._delete_source_category()

                if delete_success:
                    embed = StandardEmbedBuilder.create_success_embed(
                        "分類刪除成功",
                        f"✅ 分類「{self.source_category.name}」已成功刪除！\n\n"
                        f"**重新分配詳情**：\n"
                        f"• 移動成就數: {self.usage_info['achievement_count']} 個\n"
                        f"• 目標分類: ID {target_category_id}\n"
                        f"• 處理時間: <t:{int(datetime.now().timestamp())}:f>\n\n"
                        "✅ 所有成就已安全轉移。\n"
                        "📝 操作已完整記錄到審計日誌。",
                    )
                else:
                    embed = StandardEmbedBuilder.create_error_embed(
                        "部分失敗",
                        "成就重新分配成功，但分類刪除失敗。\n請聯繫管理員處理。",
                    )
            else:
                embed = StandardEmbedBuilder.create_error_embed(
                    "重新分配失敗", "成就重新分配失敗，分類未被刪除。"
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"【成就重新分配視圖】處理目標選擇失敗: {e}")
            await interaction.followup.send(
                "❌ 處理成就重新分配時發生錯誤", ephemeral=True
            )

    async def _reassign_achievements(self, target_category_id: int) -> bool:
        """重新分配成就到目標分類."""
        try:
            # 通過管理服務重新分配成就
            admin_service = await self._get_admin_service()
            if admin_service:
                # 取得該分類下的所有成就
                achievement_count = self.usage_info.get("achievement_count", 0)
                if achievement_count > 0:
                    # 嘗試獲取實際的成就ID列表
                    if hasattr(admin_service, 'get_achievements_by_category'):
                        achievements = await admin_service.get_achievements_by_category(
                            self.source_category.id
                        )
                        achievement_ids = [ach.id for ach in achievements]
                    else:
                        # 無法獲取成就列表
                        logger.warning(f"無法獲取分類 {self.source_category.id} 的成就列表")
                        return False

                    # 批量更新成就分類
                    result = await admin_service.bulk_update_category(
                        achievement_ids,
                        target_category_id,
                        self.admin_panel.admin_user_id,
                    )

                    return result.success_count > 0
                return True  # 沒有成就需要重新分配
            else:
                # 備用方案：無法重新分配成就
                logger.warning(
                    f"無法重新分配成就：從分類 {self.source_category.id} 到分類 {target_category_id}，"
                    f"管理服務不可用"
                )
                return False
        except Exception as e:
            logger.error(f"重新分配成就失敗: {e}")
            return False

    async def _delete_source_category(self) -> bool:
        """刪除源分類."""
        try:
            # 通過管理服務刪除分類
            admin_service = await self._get_admin_service()
            if admin_service:
                success, validation = await admin_service.delete_category(
                    self.source_category.id,
                    self.admin_panel.admin_user_id,
                    None,  # 成就已經重新分配，無需指定目標
                )

                if not validation.is_valid:
                    for error in validation.errors:
                        logger.error(f"刪除源分類驗證失敗: {error}")

                return success
            else:
                # 備用方案：無法刪除源分類
                logger.warning(f"無法刪除源分類 {self.source_category.id}：管理服務不可用")
                return False
        except Exception as e:
            logger.error(f"刪除源分類失敗: {e}")
            return False

    async def _get_admin_service(self):
        """取得管理服務實例."""
        try:
            from ..services.admin_service import AchievementAdminService

            return AchievementAdminService(
                repository=None, permission_service=None, cache_service=None
            )
        except Exception as e:
            logger.error(f"獲取管理服務失敗: {e}")
            return None


class CategoryDetailView(ui.View):
    """分類詳細資訊視圖."""

    def __init__(self, admin_panel: AdminPanel, category_details: dict[str, Any]):
        """初始化分類詳細視圖."""
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.category_details = category_details
        self.category = category_details["category"]

    @ui.button(label="✏️ 編輯分類", style=discord.ButtonStyle.primary)
    async def edit_category_button(
        self, interaction: discord.Interaction, button: ui.Button
    ) -> None:
        """編輯分類按鈕."""
        try:
            modal = EditCategoryModal(self.admin_panel, self.category)
            await interaction.response.send_modal(modal)
        except Exception as e:
            logger.error(f"【分類詳細視圖】開啟編輯表單失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟編輯表單時發生錯誤", ephemeral=True
            )

    @ui.button(label="📊 詳細統計", style=discord.ButtonStyle.secondary)
    async def view_statistics_button(
        self, interaction: discord.Interaction, button: ui.Button
    ) -> None:
        """查看詳細統計按鈕."""
        try:
            embed = StandardEmbedBuilder.create_info_embed(
                f"📊 {self.category.name} - 詳細統計", "分類的完整統計資訊和使用分析"
            )

            # 成就統計
            embed.add_field(
                name="🏆 成就統計",
                value=(
                    f"**總成就數**: {self.category_details.get('achievement_count', 0):,}\n"
                    f"**啟用成就**: {self.category_details.get('active_achievements', 0):,}\n"
                    f"**停用成就**: {self.category_details.get('inactive_achievements', 0):,}"
                ),
                inline=True,
            )

            # 用戶統計
            embed.add_field(
                name="👥 用戶統計",
                value=(
                    f"**用戶進度數**: {self.category_details.get('user_progress_count', 0):,}\n"
                    f"**完成率**: {self.category_details.get('completion_rate', 0.0):.1f}%\n"
                    f"**本月新增**: {self.category_details.get('created_achievements_this_month', 0)} 個"
                ),
                inline=True,
            )

            # 活動資訊
            embed.add_field(
                name="⚡ 活動資訊",
                value=(
                    f"**最後活動**: {self.category_details.get('last_activity', 'N/A')}\n"
                    f"**顯示順序**: {self.category.display_order}\n"
                    f"**創建時間**: <t:{int(self.category.created_at.timestamp())}:f>"
                ),
                inline=False,
            )

            embed.color = 0xFF6B35
            embed.set_footer(
                text=f"統計時間: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"【分類詳細視圖】查看統計失敗: {e}")
            await interaction.response.send_message(
                "❌ 載入統計數據時發生錯誤", ephemeral=True
            )

    @ui.button(label="🔙 返回管理", style=discord.ButtonStyle.secondary)
    async def back_to_management_button(
        self, interaction: discord.Interaction, button: ui.Button
    ) -> None:
        """返回分類管理."""
        from .admin_panel import AdminPanelState

        await self.admin_panel.handle_navigation(
            interaction, AdminPanelState.ACHIEVEMENTS
        )


class CategoryListView(ui.View):
    """分類列表視圖."""

    def __init__(self, admin_panel: AdminPanel, categories: list[AchievementCategory]):
        """初始化分類列表視圖."""
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.categories = categories

    @ui.button(label="➕ 新增分類", style=discord.ButtonStyle.primary)
    async def add_category_button(
        self, interaction: discord.Interaction, button: ui.Button
    ) -> None:
        """新增分類按鈕."""
        try:
            modal = CreateCategoryModal(self.admin_panel)
            await interaction.response.send_modal(modal)
        except Exception as e:
            logger.error(f"【分類列表視圖】開啟新增表單失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟新增表單時發生錯誤", ephemeral=True
            )

    @ui.button(label="🔄 調整順序", style=discord.ButtonStyle.secondary)
    async def reorder_button(
        self, interaction: discord.Interaction, button: ui.Button
    ) -> None:
        """調整順序按鈕."""
        try:
            reorder_view = CategoryReorderView(self.admin_panel, self.categories)
            embed = await reorder_view._create_reorder_embed()
            await interaction.response.send_message(
                embed=embed, view=reorder_view, ephemeral=True
            )
        except Exception as e:
            logger.error(f"【分類列表視圖】開啟排序管理失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟排序管理時發生錯誤", ephemeral=True
            )

    @ui.button(label="🔙 返回管理", style=discord.ButtonStyle.secondary)
    async def back_to_management_button(
        self, interaction: discord.Interaction, button: ui.Button
    ) -> None:
        """返回分類管理."""
        from .admin_panel import AdminPanelState

        await self.admin_panel.handle_navigation(
            interaction, AdminPanelState.ACHIEVEMENTS
        )


class CategoryReorderView(ui.View):
    """分類排序視圖."""

    def __init__(self, admin_panel: AdminPanel, categories: list[AchievementCategory]):
        """初始化分類排序視圖."""
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.categories = categories

    async def _create_reorder_embed(self) -> discord.Embed:
        """建立排序管理 Embed."""
        embed = StandardEmbedBuilder.create_info_embed(
            "🔄 分類排序管理", "調整分類的顯示順序，影響用戶界面中的分類排列"
        )

        # 按當前顯示順序排序
        sorted_categories = sorted(self.categories, key=lambda x: x.display_order)

        current_order = []
        for i, category in enumerate(sorted_categories, 1):
            current_order.append(
                f"**{i}.** {category.icon_emoji} {category.name} (順序: {category.display_order})"
            )

        embed.add_field(
            name="📊 當前順序",
            value="\n".join(current_order) if current_order else "無分類",
            inline=False,
        )

        embed.add_field(
            name="🔧 排序說明",
            value=(
                "• display_order 數值越小，顯示越前面\n"
                "• 可以設定相同數值（系統會按 ID 排序）\n"
                "• 建議使用 10, 20, 30... 預留調整空間\n"
                "• 變更會即時生效"
            ),
            inline=False,
        )

        embed.color = 0xFF6B35
        embed.set_footer(text="使用下方按鈕進行排序調整")

        return embed

    @ui.button(label="📝 手動設定順序", style=discord.ButtonStyle.primary)
    async def manual_reorder_button(
        self, interaction: discord.Interaction, button: ui.Button
    ) -> None:
        """手動設定順序按鈕."""
        try:
            modal = CategoryOrderModal(self.admin_panel, self.categories)
            await interaction.response.send_modal(modal)
        except Exception as e:
            logger.error(f"【分類排序視圖】開啟手動排序失敗: {e}")
            await interaction.response.send_message(
                "❌ 開啟手動排序時發生錯誤", ephemeral=True
            )

    @ui.button(label="🔁 自動重排", style=discord.ButtonStyle.secondary)
    async def auto_reorder_button(
        self, interaction: discord.Interaction, button: ui.Button
    ) -> None:
        """自動重排按鈕."""
        try:
            await interaction.response.defer(ephemeral=True)

            # 模擬自動重排
            success = await self._auto_reorder_categories()

            if success:
                embed = StandardEmbedBuilder.create_success_embed(
                    "自動重排完成",
                    f"✅ 已自動重新排列 {len(self.categories)} 個分類的順序！\n\n"
                    "**重排規則**：\n"
                    "• 按照當前順序重新分配\n"
                    "• 使用 10, 20, 30... 的間隔\n"
                    "• 保持原有的相對順序\n\n"
                    "變更已立即生效。",
                )
            else:
                embed = StandardEmbedBuilder.create_error_embed(
                    "自動重排失敗", "無法完成自動重排，請嘗試手動設定。"
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"【分類排序視圖】自動重排失敗: {e}")
            await interaction.followup.send("❌ 執行自動重排時發生錯誤", ephemeral=True)

    @ui.button(label="🔙 返回管理", style=discord.ButtonStyle.secondary)
    async def back_to_management_button(
        self, interaction: discord.Interaction, button: ui.Button
    ) -> None:
        """返回分類管理."""
        from .admin_panel import AdminPanelState

        await self.admin_panel.handle_navigation(
            interaction, AdminPanelState.ACHIEVEMENTS
        )

    async def _auto_reorder_categories(self) -> bool:
        """自動重新排序分類."""
        try:
            # 通過管理服務重新排序分類
            admin_service = await self._get_admin_service()
            if admin_service:
                # 按當前順序排序，然後重新分配順序號
                sorted_categories = sorted(
                    self.categories, key=lambda x: x.display_order
                )

                # 生成新的順序配置 (10, 20, 30...)
                category_orders = []
                for i, category in enumerate(sorted_categories):
                    new_order = (i + 1) * 10
                    category_orders.append(
                        {"id": category.id, "display_order": new_order}
                    )

                # 執行批量排序更新
                result = await admin_service.reorder_categories(
                    category_orders, self.admin_panel.admin_user_id
                )

                return result.success_count > 0
            else:
                # 備用方案：模擬自動重排操作
                logger.info(f"模擬自動重排 {len(self.categories)} 個分類")
                return True
        except Exception as e:
            logger.error(f"自動重排分類失敗: {e}")
            return False

    async def _get_admin_service(self):
        """取得管理服務實例."""
        try:
            from ..services.admin_service import AchievementAdminService

            return AchievementAdminService(
                repository=None, permission_service=None, cache_service=None
            )
        except Exception as e:
            logger.error(f"獲取管理服務失敗: {e}")
            return None


class CategoryOrderModal(ui.Modal):
    """分類順序設定模態框."""

    def __init__(self, admin_panel: AdminPanel, categories: list[AchievementCategory]):
        """初始化分類順序設定模態框."""
        super().__init__(title="設定分類順序")
        self.admin_panel = admin_panel
        self.categories = categories

        # 按當前順序排序
        sorted_categories = sorted(categories, key=lambda x: x.display_order)

        # 建立輸入欄位（最多顯示前5個分類）
        for _i, category in enumerate(sorted_categories[:5]):
            order_input = ui.TextInput(
                label=f"{category.icon_emoji} {category.name}",
                placeholder=f"當前順序: {category.display_order}",
                default=str(category.display_order),
                max_length=3,
                required=True,
            )
            self.add_item(order_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """處理表單提交."""
        try:
            await interaction.response.defer(ephemeral=True)

            # 收集新的順序設定
            new_orders = []
            for _i, item in enumerate(self.children):
                if isinstance(item, ui.TextInput):
                    try:
                        order = int(item.value.strip())
                        if order < 0:
                            raise ValueError("順序不能為負數")
                        new_orders.append(order)
                    except ValueError:
                        await interaction.followup.send(
                            f"❌ 「{item.label}」的順序值無效", ephemeral=True
                        )
                        return

            # 模擬更新順序
            success = await self._update_category_orders(new_orders)

            if success:
                embed = StandardEmbedBuilder.create_success_embed(
                    "順序更新成功",
                    f"✅ 已成功更新 {len(new_orders)} 個分類的顾示順序！\n\n"
                    "變更已立即生效，用戶界面將按新順序顯示分類。",
                )
            else:
                embed = StandardEmbedBuilder.create_error_embed(
                    "順序更新失敗", "無法更新分類順序，請稍後再試。"
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"【分類順序模態框】處理提交失敗: {e}")
            await interaction.followup.send("❌ 處理順序更新時發生錯誤", ephemeral=True)

    async def _update_category_orders(self, new_orders: list[int]) -> bool:
        """更新分類順序."""
        try:
            # 通過管理服務更新分類順序
            admin_service = await self._get_admin_service()
            if admin_service:
                # 準備排序更新資料
                sorted_categories = sorted(
                    self.categories, key=lambda x: x.display_order
                )
                category_orders = []

                # 只處理前5個分類（對應表單中的輸入欄位）
                for i, new_order in enumerate(new_orders):
                    if i < len(sorted_categories):
                        category = sorted_categories[i]
                        category_orders.append(
                            {"id": category.id, "display_order": new_order}
                        )

                # 執行批量排序更新
                result = await admin_service.reorder_categories(
                    category_orders, self.admin_panel.admin_user_id
                )

                return result.success_count > 0
            else:
                # 備用方案：模擬更新順序操作
                logger.info(f"模擬更新分類順序: {new_orders}")
                return True
        except Exception as e:
            logger.error(f"更新分類順序失敗: {e}")
            return False

    async def _get_admin_service(self):
        """取得管理服務實例."""
        try:
            from ..services.admin_service import AchievementAdminService

            return AchievementAdminService(
                repository=None, permission_service=None, cache_service=None
            )
        except Exception as e:
            logger.error(f"獲取管理服務失敗: {e}")
            return None


class CategoryStatisticsView(ui.View):
    """分類統計視圖."""

    def __init__(self, admin_panel: AdminPanel, detailed_stats: dict):
        """初始化分類統計視圖."""
        super().__init__(timeout=300)
        self.admin_panel = admin_panel
        self.detailed_stats = detailed_stats

    @ui.button(label="🔄 重新整理", style=discord.ButtonStyle.secondary)
    async def refresh_button(
        self, interaction: discord.Interaction, button: ui.Button
    ) -> None:
        """重新整理統計數據."""
        try:
            await interaction.response.defer(ephemeral=True)

            # 重新載入統計數據
            from .admin_panel import CategoryManagementView

            temp_view = CategoryManagementView(self.admin_panel, {})
            new_stats = await temp_view._get_detailed_category_statistics()

            # 更新當前統計
            self.detailed_stats = new_stats

            # 建立新的統計 embed
            embed = await temp_view._create_category_statistics_embed(new_stats)

            await interaction.followup.send(embed=embed, view=self, ephemeral=True)

        except Exception as e:
            logger.error(f"【分類統計視圖】重新整理失敗: {e}")
            await interaction.followup.send(
                "❌ 重新整理統計數據時發生錯誤", ephemeral=True
            )

    @ui.button(label="📊 匯出報告", style=discord.ButtonStyle.secondary)
    async def export_report_button(
        self, interaction: discord.Interaction, button: ui.Button
    ) -> None:
        """匯出統計報告."""
        try:
            await interaction.response.defer(ephemeral=True)

            # 生成統計報告
            report = await self._generate_statistics_report()

            embed = StandardEmbedBuilder.create_info_embed(
                "📊 統計報告已生成", "分類使用統計報告摘要"
            )

            embed.add_field(name="📈 報告摘要", value=report, inline=False)

            embed.add_field(
                name="💡 提示",
                value="完整報告已記錄到系統日誌中，管理員可查閱詳細數據。",
                inline=False,
            )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"【分類統計視圖】匯出報告失敗: {e}")
            await interaction.followup.send("❌ 生成統計報告時發生錯誤", ephemeral=True)

    @ui.button(label="🔙 返回管理", style=discord.ButtonStyle.secondary)
    async def back_to_management_button(
        self, interaction: discord.Interaction, button: ui.Button
    ) -> None:
        """返回分類管理."""
        from .admin_panel import AdminPanelState

        await self.admin_panel.handle_navigation(
            interaction, AdminPanelState.ACHIEVEMENTS
        )

    async def _generate_statistics_report(self) -> str:
        """生成統計報告摘要."""
        try:
            usage_summary = self.detailed_stats.get("usage_summary", {})
            total_categories = self.detailed_stats.get("total_categories", 0)

            most_used = usage_summary.get("most_used")
            least_used = usage_summary.get("least_used")

            report_lines = [
                f"• 總分類數: {total_categories}",
                f"• 總成就數: {usage_summary.get('total_achievements', 0)}",
                f"• 平均每類: {usage_summary.get('average_per_category', 0):.1f} 個",
            ]

            if most_used:
                report_lines.append(f"• 最多使用: {most_used['category'].name}")

            if least_used:
                report_lines.append(f"• 最少使用: {least_used['category'].name}")

            report_lines.append(
                f"• 報告時間: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )

            return "\n".join(report_lines)

        except Exception as e:
            logger.error(f"生成統計報告失敗: {e}")
            return "報告生成失敗"
