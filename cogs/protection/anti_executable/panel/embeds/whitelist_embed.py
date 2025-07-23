"""
反可執行檔案保護模組 - 白名單面板 Embed 生成器
"""

import discord
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from ...main.main import AntiExecutable

class WhitelistEmbed:
    """白名單面板 Embed 生成器"""
    
    def __init__(self, cog: AntiExecutable, guild_id: int):
        """
        初始化白名單面板 Embed 生成器
        
        Args:
            cog: 反可執行檔案模組實例
            guild_id: 伺服器ID
        """
        self.cog = cog
        self.guild_id = guild_id
        self.items_per_page = 10  # 每頁顯示的項目數
    
    async def create_embed(self, page: int = 0) -> discord.Embed:
        """
        創建白名單面板 Embed
        
        Args:
            page: 頁碼
            
        Returns:
            白名單面板的 Embed
        """
        try:
            # 獲取白名單資料
            whitelist = await self.cog.get_whitelist(self.guild_id)
            
            # 創建基礎 Embed
            embed = discord.Embed(
                title="📋 白名單管理",
                description="管理允許的檔案格式和網域",
                color=discord.Color.green()
            )
            
            # 計算分頁
            total_items = len(whitelist)
            total_pages = max(1, (total_items + self.items_per_page - 1) // self.items_per_page)
            current_page = min(page, total_pages - 1)
            
            start_index = current_page * self.items_per_page
            end_index = min(start_index + self.items_per_page, total_items)
            
            # 顯示白名單項目
            if whitelist:
                whitelist_text = ""
                for i, item in enumerate(whitelist[start_index:end_index], start=start_index + 1):
                    whitelist_text += f"{i}. `{item}`\n"
                
                embed.add_field(
                    name=f"📝 白名單項目 ({start_index + 1}-{end_index}/{total_items})",
                    value=whitelist_text,
                    inline=False
                )
            else:
                embed.add_field(
                    name="📝 白名單項目",
                    value="目前沒有白名單項目",
                    inline=False
                )
            
            # 分頁資訊
            if total_pages > 1:
                embed.add_field(
                    name="📄 分頁資訊",
                    value=f"第 {current_page + 1} 頁，共 {total_pages} 頁",
                    inline=True
                )
            
            # 操作說明
            embed.add_field(
                name="ℹ️ 操作說明",
                value="• 點擊「新增項目」按鈕添加新的白名單項目\n• 點擊「移除項目」按鈕移除指定項目\n• 點擊「清空白名單」按鈕清空所有項目",
                inline=False
            )
            
            # 設定頁尾
            embed.set_footer(
                text="白名單中的項目將不會被攔截",
                icon_url="https://cdn.discordapp.com/emojis/1234567890.png"
            )
            
            return embed
            
        except Exception as exc:
            # 錯誤處理
            embed = discord.Embed(
                title="❌ 載入失敗",
                description=f"載入白名單面板時發生錯誤：{exc}",
                color=discord.Color.red()
            )
            return embed 