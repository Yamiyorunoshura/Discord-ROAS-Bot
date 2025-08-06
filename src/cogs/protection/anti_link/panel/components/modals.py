"""
反惡意連結保護模組 - 對話框元件
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import ui

if TYPE_CHECKING:
    from ..main_view import AntiLinkMainView


class WhitelistModal(ui.Modal):
    """白名單添加對話框"""

    def __init__(self, view: AntiLinkMainView):
        super().__init__(title="添加白名單網域")
        self.main_view = view

        # 網域輸入框
        self.domain_input = ui.TextInput(
            label="網域名稱",
            placeholder="例如: example.com 或 *.example.com",
            max_length=100,
            required=True,
        )
        self.add_item(self.domain_input)

        # 備註輸入框
        self.note_input = ui.TextInput(
            label="備註 (選填)",
            placeholder="添加此網域的原因",
            max_length=200,
            required=False,
            style=discord.TextStyle.paragraph,
        )
        self.add_item(self.note_input)

    async def on_submit(self, interaction: discord.Interaction):
        """提交處理"""
        domain = self.domain_input.value.strip().lower()
        self.note_input.value.strip()

        if not domain:
            await interaction.response.send_message(
                "❌ 請輸入有效的網域名稱", ephemeral=True
            )
            return

        # 這裡應該調用實際的添加功能
        await interaction.response.send_message(
            f"✅ 已添加白名單網域:{domain}", ephemeral=True
        )


class BlacklistModal(ui.Modal):
    """黑名單添加對話框"""

    def __init__(self, view: AntiLinkMainView):
        super().__init__(title="添加黑名單網域")
        self.main_view = view

        # 網域輸入框
        self.domain_input = ui.TextInput(
            label="網域名稱",
            placeholder="例如: malicious.com",
            max_length=100,
            required=True,
        )
        self.add_item(self.domain_input)

        # 原因輸入框
        self.reason_input = ui.TextInput(
            label="封鎖原因",
            placeholder="為什麼要封鎖此網域",
            max_length=200,
            required=True,
            style=discord.TextStyle.paragraph,
        )
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        """提交處理"""
        domain = self.domain_input.value.strip().lower()
        reason = self.reason_input.value.strip()

        if not domain or not reason:
            await interaction.response.send_message("❌ 請填寫完整資訊", ephemeral=True)
            return

        # 這裡應該調用實際的添加功能
        await interaction.response.send_message(
            f"✅ 已添加黑名單網域:{domain}", ephemeral=True
        )


class RemoveModal(ui.Modal):
    """移除網域對話框"""

    def __init__(self, view: AntiLinkMainView, list_type: str):
        super().__init__(title=f"移除{list_type}網域")
        self.main_view = view
        self.list_type = list_type

        # 網域輸入框
        self.domain_input = ui.TextInput(
            label="網域名稱",
            placeholder="要移除的網域名稱",
            max_length=100,
            required=True,
        )
        self.add_item(self.domain_input)

    async def on_submit(self, interaction: discord.Interaction):
        """提交處理"""
        domain = self.domain_input.value.strip().lower()

        if not domain:
            await interaction.response.send_message(
                "❌ 請輸入有效的網域名稱", ephemeral=True
            )
            return

        # 這裡應該調用實際的移除功能
        await interaction.response.send_message(
            f"✅ 已移除{self.list_type}網域:{domain}", ephemeral=True
        )
