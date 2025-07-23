"""
反惡意連結保護模組 - 白名單面板Embed生成器
"""

from __future__ import annotations
import discord
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...main.main import AntiLink

class WhitelistEmbed:
    """白名單面板Embed生成器"""
    
    def __init__(self, cog: AntiLink, guild_id: int):
        """
        初始化白名單面板Embed生成器
        
        Args:
            cog: 反惡意連結模組實例
            guild_id: 伺服器ID
        """
        self.cog = cog
        self.guild_id = guild_id
    
    async def create_embed(self, page: int = 0) -> discord.Embed:
        """
        創建白名單面板Embed
        
        Args:
            page: 頁碼
            
        Returns:
            白名單面板的Embed
        """
        try:
            embed = discord.Embed(
                title="📝 安全連結白名單",
                description="管理安全連結白名單",
                color=discord.Color.green()
            )
            
            # 獲取白名單資訊
            whitelist = getattr(self.cog, '_whitelist_cache', {}).get(self.guild_id, set())
            whitelist_count = len(whitelist)
            
            if whitelist_count > 0:
                # 分頁顯示
                items_per_page = 10
                start_idx = page * items_per_page
                end_idx = start_idx + items_per_page
                
                whitelist_list = list(whitelist)
                page_items = whitelist_list[start_idx:end_idx]
                
                if page_items:
                    whitelist_text = "\n".join([f"• {domain}" for domain in page_items])
                    embed.add_field(
                        name=f"✅ 白名單 (第 {page + 1} 頁)",
                        value=whitelist_text,
                        inline=False
                    )
                
                # 頁碼資訊
                total_pages = (whitelist_count - 1) // items_per_page + 1
                embed.set_footer(text=f"頁碼: {page + 1}/{total_pages} | 總計: {whitelist_count} 個網域")
            else:
                embed.add_field(
                    name="✅ 白名單",
                    value="目前沒有設定白名單\n使用按鈕添加信任的網域",
                    inline=False
                )
                embed.set_footer(text="白名單中的網域不會被檢測")
            
            # 使用說明
            embed.add_field(
                name="💡 使用說明",
                value="• 白名單中的網域會被跳過檢測\n• 支援萬用字元 (*) 匹配\n• 支援子網域匹配",
                inline=False
            )
            
            return embed
            
        except Exception as exc:
            embed = discord.Embed(
                title="❌ 載入失敗",
                description=f"載入白名單面板時發生錯誤：{exc}",
                color=discord.Color.red()
            )
            return embed 