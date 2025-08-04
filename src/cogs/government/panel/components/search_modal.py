"""Search modal component.

政府面板搜尋模態框,提供部門和成員搜尋功能.
"""

from __future__ import annotations

import discord


class SearchModal(discord.ui.Modal):
    """搜尋模態框類別."""

    def __init__(self, current_query: str = ""):
        """初始化搜尋模態框.

        Args:
            current_query: 當前搜尋查詢
        """
        super().__init__(title="🔍 政府面板搜尋", timeout=120.0)

        self.search_query: str | None = None

        # 搜尋輸入框
        self.search_input = discord.ui.TextInput(
            label="搜尋部門或成員",
            placeholder="輸入部門名稱、描述或成員名稱...",
            default=current_query,
            min_length=0,
            max_length=100,
            style=discord.TextStyle.short,
            required=False
        )
        self.add_item(self.search_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """處理模態框提交."""
        self.search_query = self.search_input.value.strip()

        await interaction.response.defer()
        self.stop()

    async def on_timeout(self) -> None:
        """模態框超時處理."""
        self.search_query = None
        self.stop()

    async def on_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        """模態框錯誤處理."""
        await interaction.response.send_message(
            f"❌ 搜尋時發生錯誤: {error!s}", ephemeral=True
        )
        self.stop()

class FilterModal(discord.ui.Modal):
    """篩選模態框類別."""

    def __init__(self, current_filter: str = "all"):
        """初始化篩選模態框.

        Args:
            current_filter: 當前篩選類型
        """
        super().__init__(title="📋 政府面板篩選", timeout=120.0)

        self.filter_type: str | None = None

        # 篩選選項說明
        filter_options = {
            "all": "全部",
            "active": "啟用部門",
            "inactive": "停用部門",
            "with_roles": "有關聯角色",
            "without_roles": "無關聯角色"
        }

        options_text = "\n".join([f"{k}: {v}" for k, v in filter_options.items()])

        # 篩選輸入框
        self.filter_input = discord.ui.TextInput(
            label="篩選類型",
            placeholder="輸入篩選類型 (all/active/inactive/with_roles/without_roles)",
            default=current_filter,
            min_length=1,
            max_length=20,
            style=discord.TextStyle.short,
            required=True
        )
        self.add_item(self.filter_input)

        # 說明文字
        self.description_input = discord.ui.TextInput(
            label="可用選項",
            default=options_text,
            style=discord.TextStyle.paragraph,
            required=False
        )
        self.description_input.disabled = True
        self.add_item(self.description_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """處理模態框提交."""
        filter_value = self.filter_input.value.strip().lower()

        # 驗證篩選類型
        valid_filters = ["all", "active", "inactive", "with_roles", "without_roles"]

        if filter_value not in valid_filters:
            await interaction.response.send_message(
                f"❌ 無效的篩選類型: {filter_value}\n"
                f"可用選項: {', '.join(valid_filters)}",
                ephemeral=True
            )
            return

        self.filter_type = filter_value
        await interaction.response.defer()
        self.stop()

    async def on_timeout(self) -> None:
        """模態框超時處理."""
        self.filter_type = None
        self.stop()

    async def on_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        """模態框錯誤處理."""
        await interaction.response.send_message(
            f"❌ 篩選時發生錯誤: {error!s}", ephemeral=True
        )
        self.stop()
