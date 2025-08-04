"""管理面板幫助系統.

此模組提供管理面板的完整幫助文檔和使用指南:
- 功能介紹
- 使用指南
- 常見問題
- 操作教學
"""

from __future__ import annotations

import logging

import discord
from discord import ui

from src.cogs.core.base_cog import StandardEmbedBuilder

logger = logging.getLogger(__name__)

class AdminHelpSystem:
    """管理面板幫助系統."""

    def __init__(self, admin_panel):
        """初始化幫助系統.

        Args:
            admin_panel: 管理面板實例
        """
        self.admin_panel = admin_panel

    async def show_help_overview(self, interaction: discord.Interaction):
        """顯示幫助概覽."""
        try:
            view = HelpOverviewView(self)
            embed = await self._create_help_overview_embed()

            await interaction.response.send_message(
                embed=embed, view=view, ephemeral=True
            )

        except Exception as e:
            logger.error(f"顯示幫助概覽失敗: {e}")
            await interaction.response.send_message(
                "❌ 載入幫助文檔時發生錯誤", ephemeral=True
            )

    async def _create_help_overview_embed(self) -> discord.Embed:
        """創建幫助概覽 Embed."""
        embed = StandardEmbedBuilder.create_info_embed(
            "📚 管理面板使用指南",
            "歡迎使用 Discord ROAS Bot 成就系統管理面板!\n"
            "這裡提供完整的功能介紹和使用指南.",
        )

        embed.add_field(
            name="🎯 主要功能",
            value=(
                "• **成就管理** - 創建、編輯、刪除成就\n"
                "• **條件設置** - 設置成就達成條件\n"
                "• **用戶管理** - 管理用戶成就和進度\n"
                "• **批量操作** - 批量處理成就和用戶\n"
                "• **統計分析** - 查看系統統計和報表\n"
                "• **安全管理** - 權限控制和審計日誌"
            ),
            inline=False,
        )

        embed.add_field(
            name="📖 使用指南",
            value=(
                "• **快速開始** - 基本操作介紹\n"
                "• **功能詳解** - 各功能詳細說明\n"
                "• **最佳實踐** - 推薦的使用方式\n"
                "• **故障排除** - 常見問題解決\n"
                "• **安全須知** - 重要安全提醒"
            ),
            inline=False,
        )

        embed.add_field(
            name="🔧 快速操作",
            value=(
                "• 點擊下方按鈕查看詳細指南\n"
                "• 使用 `/achievement` 指令開始\n"
                "• 需要管理員權限才能使用\n"
                "• 所有操作都有詳細記錄"
            ),
            inline=False,
        )

        embed.set_footer(text="💡 提示:點擊下方按鈕查看詳細說明")
        return embed

class HelpOverviewView(ui.View):
    """幫助概覽視圖."""

    def __init__(self, help_system: AdminHelpSystem):
        """初始化幫助概覽視圖."""
        super().__init__(timeout=600)
        self.help_system = help_system

    @ui.button(label="🚀 快速開始", style=discord.ButtonStyle.primary, emoji="🚀")
    async def quick_start_guide(
        self, interaction: discord.Interaction, _button: ui.Button
    ):
        """顯示快速開始指南."""
        embed = await self._create_quick_start_embed()
        view = QuickStartView(self.help_system)
        await interaction.response.edit_message(embed=embed, view=view)

    @ui.button(label="📋 功能詳解", style=discord.ButtonStyle.primary, emoji="📋")
    async def feature_guide(self, interaction: discord.Interaction, _button: ui.Button):
        """顯示功能詳解."""
        embed = await self._create_feature_guide_embed()
        view = FeatureGuideView(self.help_system)
        await interaction.response.edit_message(embed=embed, view=view)

    @ui.button(label="💡 最佳實踐", style=discord.ButtonStyle.secondary, emoji="💡")
    async def best_practices(self, interaction: discord.Interaction, _button: ui.Button):
        """顯示最佳實踐."""
        embed = await self._create_best_practices_embed()
        view = BestPracticesView(self.help_system)
        await interaction.response.edit_message(embed=embed, view=view)

    @ui.button(label="❓ 常見問題", style=discord.ButtonStyle.secondary, emoji="❓")
    async def faq(self, interaction: discord.Interaction, _button: ui.Button):
        """顯示常見問題."""
        embed = await self._create_faq_embed()
        view = FAQView(self.help_system)
        await interaction.response.edit_message(embed=embed, view=view)

    @ui.button(label="🔒 安全須知", style=discord.ButtonStyle.danger, emoji="🔒")
    async def security_guide(self, interaction: discord.Interaction, _button: ui.Button):
        """顯示安全須知."""
        embed = await self._create_security_guide_embed()
        view = SecurityGuideView(self.help_system)
        await interaction.response.edit_message(embed=embed, view=view)

    async def _create_quick_start_embed(self) -> discord.Embed:
        """創建快速開始 Embed."""
        embed = StandardEmbedBuilder.create_info_embed(
            "🚀 快速開始指南", "歡迎使用成就系統管理面板!以下是基本操作流程:"
        )

        embed.add_field(
            name="1️⃣ 啟動管理面板",
            value=(
                "• 使用 `/achievement` 指令\n"
                "• 確保您有管理員權限\n"
                "• 面板將以私人訊息形式顯示"
            ),
            inline=False,
        )

        embed.add_field(
            name="2️⃣ 瀏覽系統概覽",
            value=("• 查看系統統計資料\n• 了解當前成就數量\n• 檢查用戶活躍度"),
            inline=False,
        )

        embed.add_field(
            name="3️⃣ 管理成就",
            value=(
                "• 點擊「成就管理」按鈕\n• 創建新成就或編輯現有成就\n• 設置成就達成條件"
            ),
            inline=False,
        )

        embed.add_field(
            name="4️⃣ 管理用戶",
            value=("• 點擊「用戶管理」按鈕\n• 搜尋特定用戶\n• 授予或撤銷成就"),
            inline=False,
        )

        embed.add_field(
            name="💡 小提示",
            value=(
                "• 所有操作都會記錄在審計日誌中\n"
                "• 重要操作需要二次確認\n"
                "• 面板會在15分鐘後自動超時"
            ),
            inline=False,
        )

        return embed

    async def _create_feature_guide_embed(self) -> discord.Embed:
        """創建功能詳解 Embed."""
        embed = StandardEmbedBuilder.create_info_embed(
            "📋 功能詳解", "詳細介紹管理面板的各項功能:"
        )

        embed.add_field(
            name="🏆 成就管理",
            value=(
                "• **創建成就** - 設定名稱、描述、點數\n"
                "• **編輯成就** - 修改現有成就資訊\n"
                "• **條件設置** - 設定達成條件\n"
                "• **批量操作** - 同時處理多個成就"
            ),
            inline=False,
        )

        embed.add_field(
            name="👥 用戶管理",
            value=(
                "• **搜尋用戶** - 按名稱或ID搜尋\n"
                "• **查看進度** - 檢視用戶成就進度\n"
                "• **授予成就** - 手動授予成就\n"
                "• **撤銷成就** - 移除用戶成就"
            ),
            inline=False,
        )

        embed.add_field(
            name="🎯 條件設置",
            value=(
                "• **訊息條件** - 設定發送訊息數量\n"
                "• **關鍵字條件** - 設定特定關鍵字\n"
                "• **時間條件** - 設定連續活躍天數\n"
                "• **複合條件** - 組合多種條件"
            ),
            inline=False,
        )

        return embed

    async def _create_best_practices_embed(self) -> discord.Embed:
        """創建最佳實踐 Embed."""
        embed = StandardEmbedBuilder.create_success_embed(
            "💡 最佳實踐建議", "遵循這些建議可以更好地使用管理面板:"
        )

        embed.add_field(
            name="🎯 成就設計",
            value=(
                "• 設定合理的達成條件\n"
                "• 避免過於簡單或困難的成就\n"
                "• 定期檢視成就完成率\n"
                "• 根據用戶反饋調整條件"
            ),
            inline=False,
        )

        embed.add_field(
            name="👥 用戶管理",
            value=(
                "• 謹慎使用手動授予功能\n"
                "• 記錄重要操作的原因\n"
                "• 定期檢查異常用戶\n"
                "• 保護用戶隱私資料"
            ),
            inline=False,
        )

        embed.add_field(
            name="🔒 安全管理",
            value=(
                "• 定期檢查審計日誌\n"
                "• 限制管理員權限範圍\n"
                "• 備份重要設定資料\n"
                "• 監控異常操作行為"
            ),
            inline=False,
        )

        return embed

    async def _create_faq_embed(self) -> discord.Embed:
        """創建常見問題 Embed."""
        embed = StandardEmbedBuilder.create_info_embed(
            "❓ 常見問題解答", "以下是使用管理面板時的常見問題:"
        )

        embed.add_field(
            name="Q: 為什麼我無法使用管理面板?",
            value=(
                "A: 請確認您具有以下條件:\n"
                "• 擁有伺服器管理員權限\n"
                "• 機器人已正確設定\n"
                "• 成就系統已啟用"
            ),
            inline=False,
        )

        embed.add_field(
            name="Q: 如何設定成就條件?",
            value=(
                "A: 操作步驟:\n"
                "• 進入成就管理 → 條件設置\n"
                "• 選擇要設定的成就\n"
                "• 根據需要設定各種條件\n"
                "• 預覽並保存設定"
            ),
            inline=False,
        )

        embed.add_field(
            name="Q: 批量操作如何使用?",
            value=(
                "A: 批量操作功能:\n"
                "• 選擇多個目標對象\n"
                "• 選擇要執行的操作\n"
                "• 確認操作詳情\n"
                "• 執行並查看結果"
            ),
            inline=False,
        )

        return embed

    async def _create_security_guide_embed(self) -> discord.Embed:
        """創建安全須知 Embed."""
        embed = StandardEmbedBuilder.create_warning_embed(
            "🔒 安全須知", "使用管理面板時請注意以下安全事項:"
        )

        embed.add_field(
            name="⚠️ 重要提醒",
            value=(
                "• 所有操作都會被記錄\n"
                "• 重要操作需要二次確認\n"
                "• 請勿濫用管理權限\n"
                "• 保護用戶隱私資料"
            ),
            inline=False,
        )

        embed.add_field(
            name="🚫 禁止行為",
            value=(
                "• 隨意授予或撤銷成就\n"
                "• 洩露用戶個人資料\n"
                "• 惡意修改系統設定\n"
                "• 繞過安全檢查機制"
            ),
            inline=False,
        )

        embed.add_field(
            name="📝 審計日誌",
            value=(
                "• 記錄所有管理操作\n"
                "• 包含操作者和時間\n"
                "• 可用於問題追蹤\n"
                "• 定期檢查異常記錄"
            ),
            inline=False,
        )

        return embed

class QuickStartView(ui.View):
    """快速開始視圖."""

    def __init__(self, help_system: AdminHelpSystem):
        super().__init__(timeout=300)
        self.help_system = help_system

    @ui.button(label="🔙 返回概覽", style=discord.ButtonStyle.secondary)
    async def back_to_overview(
        self, interaction: discord.Interaction, _button: ui.Button
    ):
        """返回幫助概覽."""
        embed = await self.help_system._create_help_overview_embed()
        view = HelpOverviewView(self.help_system)
        await interaction.response.edit_message(embed=embed, view=view)

class FeatureGuideView(ui.View):
    """功能詳解視圖."""

    def __init__(self, help_system: AdminHelpSystem):
        super().__init__(timeout=300)
        self.help_system = help_system

    @ui.select(
        placeholder="選擇要了解的功能...",
        options=[
            discord.SelectOption(
                label="🏆 成就管理",
                value="achievements",
                description="成就的創建、編輯和管理",
            ),
            discord.SelectOption(
                label="👥 用戶管理", value="users", description="用戶成就和進度管理"
            ),
            discord.SelectOption(
                label="🎯 條件設置", value="criteria", description="成就達成條件設置"
            ),
            discord.SelectOption(
                label="📦 批量操作", value="bulk", description="批量處理功能"
            ),
            discord.SelectOption(
                label="📊 統計分析", value="stats", description="系統統計和報表"
            ),
        ],
    )
    async def feature_select(self, interaction: discord.Interaction, select: ui.Select):
        """處理功能選擇."""
        feature = select.values[0]
        embed = await self._create_feature_detail_embed(feature)
        await interaction.response.edit_message(embed=embed, view=self)

    async def _create_feature_detail_embed(self, feature: str) -> discord.Embed:
        """創建功能詳細說明 Embed."""
        if feature == "achievements":
            return StandardEmbedBuilder.create_info_embed(
                "🏆 成就管理詳解",
                "成就管理是系統的核心功能,包含以下操作:\n\n"
                "**創建成就**\n"
                "• 設定成就名稱和描述\n"
                "• 選擇成就類型和分類\n"
                "• 設定獎勵點數和徽章\n"
                "• 配置是否為隱藏成就\n\n"
                "**編輯成就**\n"
                "• 修改成就基本資訊\n"
                "• 調整達成條件\n"
                "• 更新獎勵設定\n"
                "• 啟用或停用成就\n\n"
                "**批量操作**\n"
                "• 同時編輯多個成就\n"
                "• 批量啟用或停用\n"
                "• 批量分類變更\n"
                "• 批量刪除操作",
            )
        elif feature == "users":
            return StandardEmbedBuilder.create_info_embed(
                "👥 用戶管理詳解",
                "用戶管理功能幫助您管理用戶的成就和進度:\n\n"
                "**搜尋用戶**\n"
                "• 按用戶名稱搜尋\n"
                "• 按用戶ID搜尋\n"
                "• 模糊搜尋支援\n"
                "• 搜尋結果分頁顯示\n\n"
                "**查看用戶資料**\n"
                "• 已獲得的成就列表\n"
                "• 進行中的成就進度\n"
                "• 用戶統計資料\n"
                "• 活躍度分析\n\n"
                "**手動操作**\n"
                "• 授予特定成就\n"
                "• 撤銷已獲得成就\n"
                "• 調整成就進度\n"
                "• 重置用戶資料",
            )
        elif feature == "criteria":
            return StandardEmbedBuilder.create_info_embed(
                "🎯 條件設置詳解",
                "條件設置讓您靈活配置成就的達成條件:\n\n"
                "**訊息數量條件**\n"
                "• 設定目標訊息數量\n"
                "• 可選時間窗口限制\n"
                "• 支援累計或週期計算\n\n"
                "**關鍵字條件**\n"
                "• 設定特定關鍵字列表\n"
                "• 設定包含關鍵字的訊息數量\n"
                "• 支援多關鍵字組合\n\n"
                "**時間條件**\n"
                "• 設定連續活躍天數\n"
                "• 選擇活動類型\n"
                "• 支援不同時間週期\n\n"
                "**複合條件**\n"
                "• AND/OR 邏輯組合\n"
                "• 多條件同時滿足\n"
                "• 靈活的條件組合",
            )
        elif feature == "bulk":
            return StandardEmbedBuilder.create_info_embed(
                "📦 批量操作詳解",
                "批量操作功能提高管理效率:\n\n"
                "**成就批量操作**\n"
                "• 批量啟用/停用成就\n"
                "• 批量修改成就分類\n"
                "• 批量刪除成就\n"
                "• 批量匯出/匯入\n\n"
                "**用戶批量操作**\n"
                "• 批量授予成就\n"
                "• 批量撤銷成就\n"
                "• 批量重置進度\n"
                "• 批量資料匯出\n\n"
                "**安全機制**\n"
                "• 操作前預覽\n"
                "• 二次確認機制\n"
                "• 操作記錄追蹤\n"
                "• 錯誤處理和回滾",
            )
        else:  # stats
            return StandardEmbedBuilder.create_info_embed(
                "📊 統計分析詳解",
                "統計分析功能提供系統洞察:\n\n"
                "**系統統計**\n"
                "• 總成就數量\n"
                "• 活躍用戶數量\n"
                "• 成就完成率\n"
                "• 系統使用趨勢\n\n"
                "**成就統計**\n"
                "• 各成就獲得人數\n"
                "• 成就難度分析\n"
                "• 熱門成就排行\n"
                "• 完成時間分析\n\n"
                "**用戶統計**\n"
                "• 用戶活躍度排行\n"
                "• 成就獲得分佈\n"
                "• 用戶成長趨勢\n"
                "• 參與度分析",
            )

    @ui.button(label="🔙 返回概覽", style=discord.ButtonStyle.secondary)
    async def back_to_overview(
        self, interaction: discord.Interaction, _button: ui.Button
    ):
        """返回幫助概覽."""
        embed = await self.help_system._create_help_overview_embed()
        view = HelpOverviewView(self.help_system)
        await interaction.response.edit_message(embed=embed, view=view)

class BestPracticesView(ui.View):
    """最佳實踐視圖."""

    def __init__(self, help_system: AdminHelpSystem):
        super().__init__(timeout=300)
        self.help_system = help_system

    @ui.button(label="🔙 返回概覽", style=discord.ButtonStyle.secondary)
    async def back_to_overview(
        self, interaction: discord.Interaction, _button: ui.Button
    ):
        """返回幫助概覽."""
        embed = await self.help_system._create_help_overview_embed()
        view = HelpOverviewView(self.help_system)
        await interaction.response.edit_message(embed=embed, view=view)

class FAQView(ui.View):
    """常見問題視圖."""

    def __init__(self, help_system: AdminHelpSystem):
        super().__init__(timeout=300)
        self.help_system = help_system

    @ui.button(label="🔙 返回概覽", style=discord.ButtonStyle.secondary)
    async def back_to_overview(
        self, interaction: discord.Interaction, _button: ui.Button
    ):
        """返回幫助概覽."""
        embed = await self.help_system._create_help_overview_embed()
        view = HelpOverviewView(self.help_system)
        await interaction.response.edit_message(embed=embed, view=view)

class SecurityGuideView(ui.View):
    """安全須知視圖."""

    def __init__(self, help_system: AdminHelpSystem):
        super().__init__(timeout=300)
        self.help_system = help_system

    @ui.button(label="🔙 返回概覽", style=discord.ButtonStyle.secondary)
    async def back_to_overview(
        self, interaction: discord.Interaction, _button: ui.Button
    ):
        """返回幫助概覽."""
        embed = await self.help_system._create_help_overview_embed()
        view = HelpOverviewView(self.help_system)
        await interaction.response.edit_message(embed=embed, view=view)
