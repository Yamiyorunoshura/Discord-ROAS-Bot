"""
資料同步面板按鈕組件
- 定義各種功能按鈕
- 處理用戶交互
- 提供統一的按鈕樣式
"""

from typing import TYPE_CHECKING

import discord
from discord import ui

if TYPE_CHECKING:
    from ...main.main import SyncDataCog

from .settings_modal import AutoSyncSettingsModal, SyncRangeModal


class SyncButton(ui.Button):
    """同步按鈕"""

    def __init__(self, sync_type: str, label: str, row: int = 0):
        super().__init__(
            style=discord.ButtonStyle.primary,
            label=label,
            custom_id=f"sync_{sync_type}",
            row=row,
        )
        self.sync_type = sync_type

    async def callback(self, interaction: discord.Interaction):
        """同步按鈕回調"""
        view = self.view
        if hasattr(view, "execute_sync"):
            await view.execute_sync(interaction, self.sync_type)
        else:
            await interaction.response.send_message(
                "❌ 無法執行同步操作.", ephemeral=True
            )


class HistoryButton(ui.Button):
    """歷史記錄按鈕"""

    def __init__(self, row: int = 0):
        super().__init__(
            style=discord.ButtonStyle.secondary, label="同步歷史", row=row
        )

    async def callback(self, interaction: discord.Interaction):
        """歷史按鈕回調"""
        view = self.view
        if hasattr(view, "show_history"):
            await view.show_history(interaction)
        else:
            await interaction.response.send_message(
                "❌ 無法載入歷史記錄.", ephemeral=True
            )


class SettingsButton(ui.Button):
    """設定按鈕"""

    def __init__(self, row: int = 0):
        super().__init__(
            style=discord.ButtonStyle.secondary, label="同步設定", row=row
        )

    async def callback(self, interaction: discord.Interaction):
        """設定按鈕回調"""
        # 創建設定選擇視圖
        view = SettingsSelectView(self.view.cog)

        embed = discord.Embed(
            title="⚙️ 同步設定選項",
            description="請選擇要配置的設定類型",
            color=discord.Color.blue(),
        )

        embed.add_field(
            name="🔄 自動同步設定", value="配置自動同步間隔、類型和通知", inline=False
        )

        embed.add_field(
            name="📋 同步範圍設定", value="配置同步的角色和頻道範圍", inline=False
        )

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class AutoSyncButton(ui.Button):
    """自動同步設定按鈕"""

    def __init__(self, cog: "SyncDataCog"):
        super().__init__(
            style=discord.ButtonStyle.primary, label="自動同步設定", row=0
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        """自動同步設定回調"""
        modal = AutoSyncSettingsModal(self.cog)
        await interaction.response.send_modal(modal)


class SyncRangeButton(ui.Button):
    """同步範圍設定按鈕"""

    def __init__(self, cog: "SyncDataCog"):
        super().__init__(
            style=discord.ButtonStyle.primary, label="同步範圍設定", row=0
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        """同步範圍設定回調"""
        modal = SyncRangeModal(self.cog)
        await interaction.response.send_modal(modal)


class SettingsSelectView(ui.View):
    """設定選擇視圖"""

    def __init__(self, cog: "SyncDataCog"):
        super().__init__(timeout=300)
        self.cog = cog

        # 添加設定按鈕
        self.add_item(AutoSyncButton(cog))
        self.add_item(SyncRangeButton(cog))
        self.add_item(SettingsInfoButton())
        self.add_item(CloseSettingsButton())


class SettingsInfoButton(ui.Button):
    """設定資訊按鈕"""

    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.secondary, label="當前設定", row=1
        )

    async def callback(self, interaction: discord.Interaction):
        """設定資訊回調"""
        view = self.view
        cog = getattr(view, "cog", None)

        embed = discord.Embed(
            title="📊 當前同步設定",
            description="以下是目前的同步配置",
            color=discord.Color.green(),
        )

        try:
            # 顯示自動同步設定
            auto_config = getattr(cog, "auto_sync_config", {})
            if auto_config:
                embed.add_field(
                    name="🔄 自動同步",
                    value=(
                        f"狀態:{'啟用' if auto_config.get('auto_sync_enabled') else '停用'}\n"
                        f"間隔:{auto_config.get('sync_interval', 'N/A')} 分鐘\n"
                        f"類型:{auto_config.get('sync_type', 'N/A')}\n"
                        f"重試:{auto_config.get('retry_count', 'N/A')} 次"
                    ),
                    inline=True,
                )
            else:
                embed.add_field(name="🔄 自動同步", value="尚未設定", inline=True)

            # 顯示範圍設定
            range_config = getattr(cog, "sync_range_config", {})
            if range_config:
                role_filters = range_config.get("role_filters", [])
                channel_filters = range_config.get("channel_filters", [])

                embed.add_field(
                    name="📋 同步範圍",
                    value=(
                        f"排除角色:{len(role_filters)} 個\n"
                        f"排除頻道:{len(channel_filters)} 個\n"
                        f"選項:{range_config.get('sync_options', 'N/A')}"
                    ),
                    inline=True,
                )
            else:
                embed.add_field(name="📋 同步範圍", value="使用預設範圍", inline=True)

        except Exception as e:
            embed.add_field(name="❌ 錯誤", value=f"無法載入設定:{e!s}", inline=False)

        await interaction.response.edit_message(embed=embed, view=view)


class CloseSettingsButton(ui.Button):
    """關閉設定按鈕"""

    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.secondary, label="關閉", row=1
        )

    async def callback(self, interaction: discord.Interaction):
        """關閉設定回調"""
        embed = discord.Embed(
            title="設定面板已關閉",
            description="感謝使用同步設定功能!",
            color=discord.Color.green(),
        )

        await interaction.response.edit_message(embed=embed, view=None)


class RefreshButton(ui.Button):
    """刷新按鈕"""

    def __init__(self, row: int = 0):
        super().__init__(
            style=discord.ButtonStyle.secondary, label="刷新", row=row
        )

    async def callback(self, interaction: discord.Interaction):
        """刷新按鈕回調"""
        view = self.view
        if hasattr(view, "refresh_data"):
            await view.refresh_data(interaction)
        else:
            await interaction.response.send_message("❌ 無法刷新資料.", ephemeral=True)


class CloseButton(ui.Button):
    """關閉面板按鈕"""

    def __init__(self, row: int = 0):
        super().__init__(
            style=discord.ButtonStyle.secondary, label="關閉", row=row
        )

    async def callback(self, interaction: discord.Interaction):
        """關閉按鈕回調"""
        embed = discord.Embed(
            title="面板已關閉",
            description="感謝使用資料同步系統!",
            color=discord.Color.green(),
        )

        # 禁用所有組件
        view = self.view
        if view:
            for item in view.children:
                if hasattr(item, "disabled"):
                    item.disabled = True

        await interaction.response.edit_message(embed=embed, view=view)
