"""
反惡意連結保護模組 - 設定面板Embed生成器
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from ...main.main import AntiLink


class ConfigEmbed:
    """設定面板Embed生成器"""

    def __init__(self, cog: AntiLink, guild_id: int):
        """
        初始化設定面板Embed生成器

        Args:
            cog: 反惡意連結模組實例
            guild_id: 伺服器ID
        """
        self.cog = cog
        self.guild_id = guild_id

    async def create_embed(self) -> discord.Embed:
        """
        創建設定面板Embed

        Returns:
            設定面板的Embed
        """
        try:
            embed = discord.Embed(
                title="⚙️ 反惡意連結設定",
                description="管理反惡意連結保護的詳細設定",
                color=discord.Color.orange(),
            )

            # 基本設定
            embed.add_field(
                name="🔧 基本設定",
                value="• 啟用/停用保護\n• 刪除惡意訊息\n• 通知管理員",
                inline=False,
            )

            # 檢測設定
            embed.add_field(
                name="🔍 檢測設定",
                value="• 檢測嵌入連結\n• 檢測短網址\n• 檢測可疑網域",
                inline=False,
            )

            # 動作設定
            embed.add_field(
                name="⚡ 動作設定",
                value="• 自動刪除訊息\n• 警告用戶\n• 記錄違規行為",
                inline=False,
            )

            embed.set_footer(text="使用按鈕編輯設定")

            return embed

        except Exception as exc:
            embed = discord.Embed(
                title="❌ 載入失敗",
                description=f"載入設定面板時發生錯誤:{exc}",
                color=discord.Color.red(),
            )
            return embed
