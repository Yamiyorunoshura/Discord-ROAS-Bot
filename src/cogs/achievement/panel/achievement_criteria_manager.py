"""成就條件動態設置管理面板.

此模組提供管理員設置成就達成條件的介面:
- 關鍵字發送次數條件
- 訊息發送次數條件
- 時間相關條件
- 複合條件設置
"""

from __future__ import annotations

import logging

import discord
from discord import ui

from src.cogs.core.base_cog import StandardEmbedBuilder

logger = logging.getLogger(__name__)


class AchievementCriteriaManager:
    """成就條件管理器."""

    def __init__(self, admin_panel, achievement_service):
        """初始化成就條件管理器.

        Args:
            admin_panel: 管理面板實例
            achievement_service: 成就服務實例
        """
        self.admin_panel = admin_panel
        self.achievement_service = achievement_service
        self.current_achievement = None
        self.current_criteria = {}

    async def start_criteria_editor(
        self, interaction: discord.Interaction, achievement_id: int
    ):
        """啟動條件編輯器.

        Args:
            interaction: Discord 互動物件
            achievement_id: 成就 ID
        """
        try:
            # 獲取成就資料
            achievement = await self.achievement_service.get_achievement_by_id(
                achievement_id
            )
            if not achievement:
                await interaction.response.send_message(
                    "❌ 找不到指定的成就", ephemeral=True
                )
                return

            self.current_achievement = achievement
            self.current_criteria = achievement.criteria.copy()

            # 創建條件編輯視圖
            view = CriteriaEditorView(self)
            embed = await self._create_criteria_overview_embed()

            await interaction.response.send_message(
                embed=embed, view=view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"啟動條件編輯器失敗: {e}")
            await interaction.response.send_message(
                "❌ 啟動條件編輯器時發生錯誤", ephemeral=True
            )

    async def _create_criteria_overview_embed(self) -> discord.Embed:
        """創建條件概覽 Embed."""
        embed = StandardEmbedBuilder.create_info_embed(
            "成就條件編輯器",
            f"**成就名稱**: {self.current_achievement.name}\n"
            f"**成就類型**: {self.current_achievement.type.value}\n"
            f"**當前條件**: {len(self.current_criteria)} 個條件",
        )

        # 顯示當前條件
        if self.current_criteria:
            criteria_text = []
            for key, value in self.current_criteria.items():
                criteria_text.append(f"• **{key}**: {value}")

            embed.add_field(
                name="📋 當前條件",
                value="\n".join(criteria_text) if criteria_text else "無條件",
                inline=False,
            )
        else:
            embed.add_field(name="📋 當前條件", value="尚未設置任何條件", inline=False)

        embed.add_field(
            name="🔧 可用操作",
            value=(
                "• 設置訊息數量條件\n"
                "• 設置關鍵字條件\n"
                "• 設置時間條件\n"
                "• 設置複合條件\n"
                "• 預覽和保存"
            ),
            inline=False,
        )

        return embed

    async def save_criteria(self) -> bool:
        """保存條件設置."""
        try:
            # 更新成就條件
            self.current_achievement.criteria = self.current_criteria

            # 調用服務保存
            success = await self.achievement_service.update_achievement(
                self.current_achievement
            )

            if success:
                logger.info(f"成就 {self.current_achievement.id} 條件更新成功")

            return success

        except Exception as e:
            logger.error(f"保存成就條件失敗: {e}")
            return False


class CriteriaEditorView(ui.View):
    """條件編輯器視圖."""

    def __init__(self, criteria_manager: AchievementCriteriaManager):
        """初始化條件編輯器視圖."""
        super().__init__(timeout=600)
        self.criteria_manager = criteria_manager

    @ui.button(label="訊息數量條件", style=discord.ButtonStyle.primary)
    async def message_count_criteria(
        self, interaction: discord.Interaction, _button: ui.Button
    ):
        """設置訊息數量條件."""
        modal = MessageCountCriteriaModal(self.criteria_manager)
        await interaction.response.send_modal(modal)

    @ui.button(label="關鍵字條件", style=discord.ButtonStyle.primary)
    async def keyword_criteria(
        self, interaction: discord.Interaction, _button: ui.Button
    ):
        """設置關鍵字條件."""
        modal = KeywordCriteriaModal(self.criteria_manager)
        await interaction.response.send_modal(modal)

    @ui.button(label="時間條件", style=discord.ButtonStyle.primary)
    async def time_criteria(self, interaction: discord.Interaction, _button: ui.Button):
        """設置時間條件."""
        modal = TimeCriteriaModal(self.criteria_manager)
        await interaction.response.send_modal(modal)

    @ui.button(label="複合條件", style=discord.ButtonStyle.secondary)
    async def complex_criteria(
        self, interaction: discord.Interaction, _button: ui.Button
    ):
        """設置複合條件."""
        view = ComplexCriteriaView(self.criteria_manager)
        embed = StandardEmbedBuilder.create_info_embed(
            "🔗 複合條件設置", "設置多個條件的組合邏輯"
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @ui.button(label="預覽並保存", style=discord.ButtonStyle.success)
    async def preview_and_save(
        self, interaction: discord.Interaction, _button: ui.Button
    ):
        """預覽並保存條件."""
        try:
            await interaction.response.defer(ephemeral=True)

            # 創建預覽 embed
            embed = await self._create_preview_embed()

            # 創建確認視圖
            confirm_view = SaveConfirmationView(self.criteria_manager)

            await interaction.followup.send(
                embed=embed, view=confirm_view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"預覽條件失敗: {e}")
            await interaction.followup.send("❌ 預覽失敗", ephemeral=True)

    async def _create_preview_embed(self) -> discord.Embed:
        """創建預覽 Embed."""
        embed = StandardEmbedBuilder.create_info_embed(
            "👀 條件預覽", f"**成就**: {self.criteria_manager.current_achievement.name}"
        )

        criteria = self.criteria_manager.current_criteria
        if criteria:
            preview_text = []
            for key, value in criteria.items():
                if key == "target_value":
                    preview_text.append(f"• 目標數值: {value}")
                elif key == "keywords":
                    preview_text.append(
                        f"• 關鍵字: {', '.join(value) if isinstance(value, list) else value}"
                    )
                elif key == "time_window":
                    preview_text.append(f"• 時間窗口: {value}")
                elif key == "consecutive_days":
                    preview_text.append(f"• 連續天數: {value}")
                else:
                    preview_text.append(f"• {key}: {value}")

            embed.add_field(
                name="📋 設置的條件", value="\n".join(preview_text), inline=False
            )
        else:
            embed.add_field(
                name="📋 設置的條件", value="尚未設置任何條件", inline=False
            )

        embed.add_field(
            name="⚠️ 注意事項",
            value=(
                "• 保存後條件將立即生效\n"
                "• 已獲得此成就的用戶不受影響\n"
                "• 進行中的進度將重新計算"
            ),
            inline=False,
        )

        return embed


class MessageCountCriteriaModal(ui.Modal):
    """訊息數量條件設置模態框."""

    def __init__(self, criteria_manager: AchievementCriteriaManager):
        super().__init__(title="設置訊息數量條件")
        self.criteria_manager = criteria_manager

        # 獲取當前設置
        current_criteria = criteria_manager.current_criteria
        current_target = current_criteria.get("target_value", "")
        current_window = current_criteria.get("time_window", "")

        self.target_value = ui.TextInput(
            label="目標訊息數量",
            placeholder="例如: 100",
            default=str(current_target) if current_target else "",
            max_length=10,
            required=True,
        )

        self.time_window = ui.TextInput(
            label="時間窗口 (可選)",
            placeholder="例如: 7d (7天), 30d (30天), 留空表示總計",
            default=str(current_window) if current_window else "",
            max_length=20,
            required=False,
        )

        self.add_item(self.target_value)
        self.add_item(self.time_window)

    async def on_submit(self, interaction: discord.Interaction):
        """提交訊息數量條件."""
        try:
            target_value = int(self.target_value.value)

            # 更新條件
            self.criteria_manager.current_criteria["target_value"] = target_value
            self.criteria_manager.current_criteria["metric"] = "message_count"

            if self.time_window.value.strip():
                self.criteria_manager.current_criteria["time_window"] = (
                    self.time_window.value.strip()
                )
            elif "time_window" in self.criteria_manager.current_criteria:
                del self.criteria_manager.current_criteria["time_window"]

            # 更新顯示
            embed = await self.criteria_manager._create_criteria_overview_embed()
            view = CriteriaEditorView(self.criteria_manager)

            await interaction.response.edit_message(embed=embed, view=view)

        except ValueError:
            await interaction.response.send_message(
                "❌ 請輸入有效的數字", ephemeral=True
            )
        except Exception as e:
            logger.error(f"設置訊息數量條件失敗: {e}")
            await interaction.response.send_message("❌ 設置失敗", ephemeral=True)


class KeywordCriteriaModal(ui.Modal):
    """關鍵字條件設置模態框."""

    def __init__(self, criteria_manager: AchievementCriteriaManager):
        super().__init__(title="設置關鍵字條件")
        self.criteria_manager = criteria_manager

        # 獲取當前設置
        current_criteria = criteria_manager.current_criteria
        current_keywords = current_criteria.get("keywords", [])
        current_count = current_criteria.get("keyword_count", "")

        self.keywords = ui.TextInput(
            label="關鍵字列表",
            placeholder="用逗號分隔,例如: 謝謝,感謝,讚",
            default=", ".join(current_keywords)
            if isinstance(current_keywords, list)
            else str(current_keywords),
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=True,
        )

        self.keyword_count = ui.TextInput(
            label="需要發送的次數",
            placeholder="例如: 10 (發送包含關鍵字的訊息10次)",
            default=str(current_count) if current_count else "",
            max_length=10,
            required=True,
        )

        self.add_item(self.keywords)
        self.add_item(self.keyword_count)

    async def on_submit(self, interaction: discord.Interaction):
        """提交關鍵字條件."""
        try:
            keywords = [
                kw.strip() for kw in self.keywords.value.split(",") if kw.strip()
            ]
            keyword_count = int(self.keyword_count.value)

            if not keywords:
                await interaction.response.send_message(
                    "❌ 請至少輸入一個關鍵字", ephemeral=True
                )
                return

            # 更新條件
            self.criteria_manager.current_criteria["keywords"] = keywords
            self.criteria_manager.current_criteria["keyword_count"] = keyword_count
            self.criteria_manager.current_criteria["metric"] = "keyword_usage"

            # 更新顯示
            embed = await self.criteria_manager._create_criteria_overview_embed()
            view = CriteriaEditorView(self.criteria_manager)

            await interaction.response.edit_message(embed=embed, view=view)

        except ValueError:
            await interaction.response.send_message(
                "❌ 請輸入有效的數字", ephemeral=True
            )
        except Exception as e:
            logger.error(f"設置關鍵字條件失敗: {e}")
            await interaction.response.send_message("❌ 設置失敗", ephemeral=True)


class TimeCriteriaModal(ui.Modal):
    """時間條件設置模態框."""

    def __init__(self, criteria_manager: AchievementCriteriaManager):
        super().__init__(title="設置時間條件")
        self.criteria_manager = criteria_manager

        # 獲取當前設置
        current_criteria = criteria_manager.current_criteria
        current_days = current_criteria.get("consecutive_days", "")
        current_activity = current_criteria.get("daily_activity_type", "")

        self.consecutive_days = ui.TextInput(
            label="連續天數",
            placeholder="例如: 7 (連續7天)",
            default=str(current_days) if current_days else "",
            max_length=10,
            required=True,
        )

        self.activity_type = ui.TextInput(
            label="活動類型",
            placeholder="例如: message (發送訊息), login (登入), reaction (反應)",
            default=str(current_activity) if current_activity else "message",
            max_length=50,
            required=True,
        )

        self.add_item(self.consecutive_days)
        self.add_item(self.activity_type)

    async def on_submit(self, interaction: discord.Interaction):
        """提交時間條件."""
        try:
            consecutive_days = int(self.consecutive_days.value)
            activity_type = self.activity_type.value.strip()

            if consecutive_days <= 0:
                await interaction.response.send_message(
                    "❌ 連續天數必須大於0", ephemeral=True
                )
                return

            # 更新條件
            self.criteria_manager.current_criteria["consecutive_days"] = (
                consecutive_days
            )
            self.criteria_manager.current_criteria["daily_activity_type"] = (
                activity_type
            )
            self.criteria_manager.current_criteria["metric"] = "consecutive_activity"

            # 更新顯示
            embed = await self.criteria_manager._create_criteria_overview_embed()
            view = CriteriaEditorView(self.criteria_manager)

            await interaction.response.edit_message(embed=embed, view=view)

        except ValueError:
            await interaction.response.send_message(
                "❌ 請輸入有效的數字", ephemeral=True
            )
        except Exception as e:
            logger.error(f"設置時間條件失敗: {e}")
            await interaction.response.send_message("❌ 設置失敗", ephemeral=True)


class ComplexCriteriaView(ui.View):
    """複合條件設置視圖."""

    def __init__(self, criteria_manager: AchievementCriteriaManager):
        super().__init__(timeout=300)
        self.criteria_manager = criteria_manager

    @ui.button(label="AND 邏輯", style=discord.ButtonStyle.primary)
    async def and_logic(self, interaction: discord.Interaction, _button: ui.Button):
        """設置 AND 邏輯條件."""
        modal = ComplexCriteriaModal(self.criteria_manager, "AND")
        await interaction.response.send_modal(modal)

    @ui.button(label="OR 邏輯", style=discord.ButtonStyle.secondary)
    async def or_logic(self, interaction: discord.Interaction, _button: ui.Button):
        """設置 OR 邏輯條件."""
        modal = ComplexCriteriaModal(self.criteria_manager, "OR")
        await interaction.response.send_modal(modal)


class ComplexCriteriaModal(ui.Modal):
    """複合條件設置模態框."""

    def __init__(self, criteria_manager: AchievementCriteriaManager, logic_type: str):
        super().__init__(title=f"設置 {logic_type} 複合條件")
        self.criteria_manager = criteria_manager
        self.logic_type = logic_type

        self.condition_description = ui.TextInput(
            label="條件描述",
            placeholder=f"描述這個 {logic_type} 條件的組合邏輯",
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=True,
        )

        self.add_item(self.condition_description)

    async def on_submit(self, interaction: discord.Interaction):
        """提交複合條件."""
        try:
            # 更新條件
            self.criteria_manager.current_criteria["logic_type"] = self.logic_type
            self.criteria_manager.current_criteria["complex_description"] = (
                self.condition_description.value
            )

            # 更新顯示
            embed = await self.criteria_manager._create_criteria_overview_embed()
            view = CriteriaEditorView(self.criteria_manager)

            await interaction.response.edit_message(embed=embed, view=view)

        except Exception as e:
            logger.error(f"設置複合條件失敗: {e}")
            await interaction.response.send_message("❌ 設置失敗", ephemeral=True)


class SaveConfirmationView(ui.View):
    """保存確認視圖."""

    def __init__(self, criteria_manager: AchievementCriteriaManager):
        super().__init__(timeout=300)
        self.criteria_manager = criteria_manager

    @ui.button(label="確認保存", style=discord.ButtonStyle.success)
    async def confirm_save(self, interaction: discord.Interaction, _button: ui.Button):
        """確認保存條件."""
        try:
            await interaction.response.defer(ephemeral=True)

            success = await self.criteria_manager.save_criteria()

            if success:
                embed = StandardEmbedBuilder.create_success_embed(
                    "✅ 條件保存成功",
                    f"成就「{self.criteria_manager.current_achievement.name}」的條件已更新",
                )
            else:
                embed = StandardEmbedBuilder.create_error_embed(
                    "❌ 保存失敗", "條件保存時發生錯誤,請稍後再試"
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"確認保存失敗: {e}")
            await interaction.followup.send("❌ 保存時發生錯誤", ephemeral=True)

    @ui.button(label="取消", style=discord.ButtonStyle.secondary)
    async def cancel_save(self, interaction: discord.Interaction, _button: ui.Button):
        """取消保存."""
        embed = StandardEmbedBuilder.create_info_embed(
            "🚫 已取消", "條件設置已取消,未進行任何更改"
        )
        await interaction.response.edit_message(embed=embed, view=None)
