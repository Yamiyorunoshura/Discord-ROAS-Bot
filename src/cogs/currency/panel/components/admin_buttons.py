"""Currency Admin Panel Buttons.

管理員面板按鈕組件,提供:
- 餘額管理按鈕 (BalanceManageButton)
- 用戶搜尋按鈕 (UserSearchButton)
- 經濟統計按鈕 (EconomicStatsButton)
- 審計記錄按鈕 (AuditRecordsButton)
- 批量操作按鈕 (BatchOperationButton)
"""

from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING

import discord
from discord.ui import Button

from .admin_balance_modal import AdminBalanceModal

if TYPE_CHECKING:
    from ..admin_view import CurrencyAdminPanelView

logger = logging.getLogger(__name__)

class AdminCurrencyButton(Button):
    """管理員貨幣面板基礎按鈕類"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.logger = logger

class BalanceManageButton(AdminCurrencyButton):
    """餘額管理按鈕"""

    def __init__(self, **kwargs):
        kwargs.setdefault("label", "💰 餘額管理")
        kwargs.setdefault("style", discord.ButtonStyle.primary)
        super().__init__(**kwargs)

    async def callback(self, interaction: discord.Interaction):
        """餘額管理按鈕回調"""
        try:
            view: CurrencyAdminPanelView = self.view

            # 創建餘額管理 Modal
            balance_modal = AdminBalanceModal(
                currency_service=view.currency_service,
                admin_panel_view=view,
                guild_id=view.guild_id,
                admin_id=view.author_id
            )

            await interaction.response.send_modal(balance_modal)

        except Exception as e:
            self.logger.error(f"餘額管理按鈕回調失敗: {e}")
            embed = discord.Embed(
                title="❌ 錯誤",
                description="開啟餘額管理視窗時發生錯誤,請稍後再試",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

class UserSearchButton(AdminCurrencyButton):
    """用戶搜尋按鈕"""

    def __init__(self, **kwargs):
        kwargs.setdefault("label", "👥 用戶管理")
        kwargs.setdefault("style", discord.ButtonStyle.primary)
        super().__init__(**kwargs)

    async def callback(self, interaction: discord.Interaction):
        """用戶搜尋按鈕回調"""
        try:
            view: CurrencyAdminPanelView = self.view

            # 切換到用戶管理頁面
            await view.change_page(interaction, "users")

        except Exception as e:
            self.logger.error(f"用戶搜尋按鈕回調失敗: {e}")
            embed = discord.Embed(
                title="❌ 錯誤",
                description="載入用戶管理頁面時發生錯誤,請稍後再試",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

class EconomicStatsButton(AdminCurrencyButton):
    """經濟統計按鈕"""

    def __init__(self, **kwargs):
        kwargs.setdefault("label", "📊 經濟統計")
        kwargs.setdefault("style", discord.ButtonStyle.secondary)
        super().__init__(**kwargs)

    async def callback(self, interaction: discord.Interaction):
        """經濟統計按鈕回調"""
        try:
            view: CurrencyAdminPanelView = self.view

            # 切換到經濟統計頁面
            await view.change_page(interaction, "stats")

        except Exception as e:
            self.logger.error(f"經濟統計按鈕回調失敗: {e}")
            embed = discord.Embed(
                title="❌ 錯誤",
                description="載入經濟統計頁面時發生錯誤,請稍後再試",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

class AuditRecordsButton(AdminCurrencyButton):
    """審計記錄按鈕"""

    def __init__(self, **kwargs):
        kwargs.setdefault("label", "📋 審計記錄")
        kwargs.setdefault("style", discord.ButtonStyle.secondary)
        super().__init__(**kwargs)

    async def callback(self, interaction: discord.Interaction):
        """審計記錄按鈕回調"""
        try:
            view: CurrencyAdminPanelView = self.view

            # 切換到審計記錄頁面
            await view.change_page(interaction, "audit")

        except Exception as e:
            self.logger.error(f"審計記錄按鈕回調失敗: {e}")
            embed = discord.Embed(
                title="❌ 錯誤",
                description="載入審計記錄頁面時發生錯誤,請稍後再試",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

class BatchOperationButton(AdminCurrencyButton):
    """批量操作按鈕"""

    def __init__(self, **kwargs):
        kwargs.setdefault("label", "⚡ 批量操作")
        kwargs.setdefault("style", discord.ButtonStyle.danger)
        super().__init__(**kwargs)

    async def callback(self, interaction: discord.Interaction):
        """批量操作按鈕回調"""
        try:
            # TODO: 實作批量操作 Modal
            embed = discord.Embed(
                title="⚡ 批量操作",
                description="批量操作功能開發中,敬請期待!",
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            self.logger.error(f"批量操作按鈕回調失敗: {e}")
            embed = discord.Embed(
                title="❌ 錯誤",
                description="開啟批量操作時發生錯誤,請稍後再試",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

class RefreshButton(AdminCurrencyButton):
    """重新整理按鈕"""

    def __init__(self, **kwargs):
        kwargs.setdefault("label", "🔄 重新整理")
        kwargs.setdefault("style", discord.ButtonStyle.secondary)
        super().__init__(**kwargs)

    async def callback(self, interaction: discord.Interaction):
        """重新整理按鈕回調"""
        try:
            view: CurrencyAdminPanelView = self.view

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

class CloseButton(AdminCurrencyButton):
    """關閉按鈕"""

    def __init__(self, **kwargs):
        kwargs.setdefault("label", "❌ 關閉")
        kwargs.setdefault("style", discord.ButtonStyle.danger)
        super().__init__(**kwargs)

    async def callback(self, interaction: discord.Interaction):
        """關閉按鈕回調"""
        try:
            view: CurrencyAdminPanelView = self.view

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
                title="🔒 管理員面板已關閉",
                description="感謝使用貨幣管理系統!",
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
