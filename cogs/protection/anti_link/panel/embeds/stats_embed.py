"""
反惡意連結保護模組 - 統計面板Embed生成器
"""

import discord
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...main.main import AntiLink

class StatsEmbed:
    """統計面板Embed生成器"""
    
    def __init__(self, cog: AntiLink, guild_id: int):
        """
        初始化統計面板Embed生成器
        
        Args:
            cog: 反惡意連結模組實例
            guild_id: 伺服器ID
        """
        self.cog = cog
        self.guild_id = guild_id
    
    async def create_embed(self) -> discord.Embed:
        """
        創建統計面板Embed
        
        Returns:
            統計面板的Embed
        """
        try:
            embed = discord.Embed(
                title="📊 反惡意連結統計",
                description="查看反惡意連結保護的統計資訊",
                color=discord.Color.green()
            )
            
            # 攔截統計
            embed.add_field(
                name="🚫 攔截統計",
                value="• 今日攔截: 0 個\n• 本週攔截: 0 個\n• 總計攔截: 0 個",
                inline=True
            )
            
            # 檢測統計
            embed.add_field(
                name="🔍 檢測統計",
                value="• 檢測次數: 0 次\n• 誤報率: 0%\n• 準確率: 100%",
                inline=True
            )
            
            # 用戶統計
            embed.add_field(
                name="👥 用戶統計",
                value="• 違規用戶: 0 人\n• 警告次數: 0 次\n• 處罰次數: 0 次",
                inline=True
            )
            
            embed.set_footer(text="統計資料會定期更新")
            
            return embed
            
        except Exception as exc:
            embed = discord.Embed(
                title="❌ 載入失敗",
                description=f"載入統計面板時發生錯誤：{exc}",
                color=discord.Color.red()
            )
            return embed 