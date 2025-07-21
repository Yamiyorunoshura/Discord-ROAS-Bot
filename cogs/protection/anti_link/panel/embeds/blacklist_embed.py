"""
反惡意連結保護模組 - 黑名單面板Embed生成器
"""

from __future__ import annotations
import discord
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...main.main import AntiLink

class BlacklistEmbed:
    """黑名單面板Embed生成器"""
    
    def __init__(self, cog: AntiLink, guild_id: int):
        """
        初始化黑名單面板Embed生成器
        
        Args:
            cog: 反惡意連結模組實例
            guild_id: 伺服器ID
        """
        self.cog = cog
        self.guild_id = guild_id
    
    async def create_embed(self, page: int = 0) -> discord.Embed:
        """
        創建黑名單面板Embed
        
        Args:
            page: 頁碼
            
        Returns:
            黑名單面板的Embed
        """
        try:
            embed = discord.Embed(
                title="🚫 惡意連結黑名單",
                description="管理惡意連結黑名單",
                color=discord.Color.red()
            )
            
            # 遠端黑名單資訊
            remote_count = len(getattr(self.cog, '_remote_blacklist', set()))
            embed.add_field(
                name="🌐 遠端黑名單",
                value=f"威脅情資來源: {remote_count} 個網域",
                inline=False
            )
            
            # 手動黑名單資訊
            manual_blacklist = getattr(self.cog, '_manual_blacklist', {}).get(self.guild_id, set())
            manual_count = len(manual_blacklist)
            
            if manual_count > 0:
                # 分頁顯示
                items_per_page = 10
                start_idx = page * items_per_page
                end_idx = start_idx + items_per_page
                
                manual_list = list(manual_blacklist)
                page_items = manual_list[start_idx:end_idx]
                
                if page_items:
                    manual_text = "\n".join([f"• {domain}" for domain in page_items])
                    embed.add_field(
                        name=f"📝 手動黑名單 (第 {page + 1} 頁)",
                        value=manual_text,
                        inline=False
                    )
                
                # 頁碼資訊
                total_pages = (manual_count - 1) // items_per_page + 1
                embed.set_footer(text=f"頁碼: {page + 1}/{total_pages} | 總計: {manual_count} 個網域")
            else:
                embed.add_field(
                    name="📝 手動黑名單",
                    value="目前沒有手動添加的黑名單",
                    inline=False
                )
            
            return embed
            
        except Exception as exc:
            embed = discord.Embed(
                title="❌ 載入失敗",
                description=f"載入黑名單面板時發生錯誤：{exc}",
                color=discord.Color.red()
            )
            return embed 