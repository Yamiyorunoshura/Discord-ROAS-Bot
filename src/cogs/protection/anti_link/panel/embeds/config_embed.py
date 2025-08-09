"""
 - Embed
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from ...main.main import AntiLink


class ConfigEmbed:
    """Embed"""

    def __init__(self, cog: AntiLink, guild_id: int):
        """
        Embed

        Args:
            cog: 
            guild_id: ID
        """
        self.cog = cog
        self.guild_id = guild_id

    async def create_embed(self) -> discord.Embed:
        """
        Embed

        Returns:
            Embed
        """
        try:
            embed = discord.Embed(
                title="🔗 防惡意連結配置說明",
                description="了解如何配置防惡意連結保護系統以獲得最佳效果。",
                color=discord.Color.orange(),
            )

            embed.add_field(
                name="🎯 基本設定",
                value="• 啟用/停用系統保護\n• 設定檢測敏感度\n• 選擇處理動作",
                inline=False,
            )

            embed.add_field(
                name="📋 清單管理",
                value="• 白名單: 信任的網域和連結\n• 黑名單: 封鎖的網域和連結\n• 支援萬用字元和正則表達式",
                inline=False,
            )

            embed.add_field(
                name="⚙️ 進階選項",
                value="• 自動學習可疑連結\n• 連結預覽和分析\n• 通知和日誌記錄",
                inline=False,
            )

            embed.set_footer(text="使用下方按鈕來配置各項設定")

            return embed

        except Exception as exc:
            embed = discord.Embed(
                title="❌ 配置載入錯誤",
                description=f"防惡意連結系統配置載入時發生錯誤: {exc}",
                color=discord.Color.red(),
            )
            return embed
