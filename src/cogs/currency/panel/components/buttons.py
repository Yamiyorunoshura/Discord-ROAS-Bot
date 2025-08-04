"""Currency Panel Buttons.

貨幣面板按鈕組件,提供:
- 轉帳按鈕 (TransferButton)
- 排行榜按鈕 (LeaderboardButton)
- 重新整理按鈕 (RefreshButton)
- 關閉按鈕 (CloseButton)
"""

from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING

import discord
from discord.ui import Button

from .transfer_modal import TransferModal

if TYPE_CHECKING:
    from ..user_view import CurrencyPanelView

logger = logging.getLogger(__name__)

class CurrencyButton(Button):
    """貨幣面板基礎按鈕類"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.logger = logger

class TransferButton(CurrencyButton):
    """轉帳按鈕"""

    def __init__(self, **kwargs):
        kwargs.setdefault("label", "💸 轉帳")
        kwargs.setdefault("style", discord.ButtonStyle.primary)
        super().__init__(**kwargs)

    async def callback(self, interaction: discord.Interaction):
        """轉帳按鈕回調"""
        try:
            # 檢查是否為面板擁有者
            view: CurrencyPanelView = self.view
            if interaction.user.id != view.author_id:
                embed = discord.Embed(
                    title="❌ 權限不足",
                    description="只有面板擁有者可以執行轉帳操作",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # 創建轉帳 Modal
            transfer_modal = TransferModal(
                currency_service=view.currency_service,
                currency_panel_view=view,
                guild_id=view.guild_id,
                from_user_id=view.author_id
            )

            await interaction.response.send_modal(transfer_modal)

        except Exception as e:
            self.logger.error(f"轉帳按鈕回調失敗: {e}")
            embed = discord.Embed(
                title="❌ 錯誤",
                description="開啟轉帳視窗時發生錯誤,請稍後再試",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

class LeaderboardButton(CurrencyButton):
    """排行榜按鈕"""

    def __init__(self, **kwargs):
        kwargs.setdefault("label", "🏆 排行榜")
        kwargs.setdefault("style", discord.ButtonStyle.secondary)
        super().__init__(**kwargs)

    async def callback(self, interaction: discord.Interaction):
        """排行榜按鈕回調"""
        try:
            view: CurrencyPanelView = self.view

            # 切換到排行榜頁面
            await view.change_page(interaction, "leaderboard")

        except Exception as e:
            self.logger.error(f"排行榜按鈕回調失敗: {e}")
            embed = discord.Embed(
                title="❌ 錯誤",
                description="載入排行榜時發生錯誤,請稍後再試",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

class RefreshButton(CurrencyButton):
    """重新整理按鈕"""

    def __init__(self, **kwargs):
        kwargs.setdefault("label", "🔄 重新整理")
        kwargs.setdefault("style", discord.ButtonStyle.secondary)
        super().__init__(**kwargs)

    async def callback(self, interaction: discord.Interaction):
        """重新整理按鈕回調"""
        try:
            view: CurrencyPanelView = self.view

            # 刷新數據和視圖
            await view.refresh_data_and_view(interaction)

        except Exception as e:
            self.logger.error(f"重新整理按鈕回調失敗: {e}")
            embed = discord.Embed(
                title="❌ 錯誤",
                description="重新整理面板時發生錯誤,請稍後再試",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

class CloseButton(CurrencyButton):
    """關閉按鈕"""

    def __init__(self, **kwargs):
        kwargs.setdefault("label", "❌ 關閉")
        kwargs.setdefault("style", discord.ButtonStyle.danger)
        super().__init__(**kwargs)

    async def callback(self, interaction: discord.Interaction):
        """關閉按鈕回調"""
        try:
            view: CurrencyPanelView = self.view

            # 檢查是否為面板擁有者
            if interaction.user.id != view.author_id:
                embed = discord.Embed(
                    title="❌ 權限不足",
                    description="只有面板擁有者可以關閉面板",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # 創建關閉嵌入
            embed = discord.Embed(
                title="💰 貨幣面板已關閉",
                description="感謝使用貨幣系統!",
                color=discord.Color.blue()
            )

            # 禁用所有組件
            for item in view.children:
                if hasattr(item, "disabled"):
                    item.disabled = True

            # 更新訊息並停止視圖
            await interaction.response.edit_message(embed=embed, view=view)
            view.stop()

        except Exception as e:
            self.logger.error(f"關閉按鈕回調失敗: {e}")
            # 如果發生錯誤, 至少嘗試停止視圖
            with contextlib.suppress(Exception):
                self.view.stop()
