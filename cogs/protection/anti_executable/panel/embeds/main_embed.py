"""
反可執行檔案保護模組 - 主要面板 Embed 生成器
"""

import discord
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...main.main import AntiExecutable

class MainEmbed:
    """主要面板 Embed 生成器"""
    
    def __init__(self, cog: AntiExecutable, guild_id: int):
        """
        初始化主要面板 Embed 生成器
        
        Args:
            cog: 反可執行檔案模組實例
            guild_id: 伺服器ID
        """
        self.cog = cog
        self.guild_id = guild_id
    
    async def create_embed(self) -> discord.Embed:
        """
        創建主要面板 Embed
        
        Returns:
            主要面板的 Embed
        """
        try:
            # 獲取模組配置
            config = await self.cog.get_config(self.guild_id)
            
            # 創建基礎 Embed
            embed = discord.Embed(
                title="🛡️ 反可執行檔案保護",
                description="防止惡意可執行檔案傳播的保護系統",
                color=discord.Color.blue() if config.get('enabled', False) else discord.Color.red()
            )
            
            # 狀態資訊
            status = "🟢 已啟用" if config.get('enabled', False) else "🔴 已停用"
            embed.add_field(
                name="📊 模組狀態",
                value=status,
                inline=True
            )
            
            # 保護設定
            delete_message = "✅ 是" if config.get('delete_message', True) else "❌ 否"
            notify_admin = "✅ 是" if config.get('notify_admin', True) else "❌ 否"
            warn_user = "✅ 是" if config.get('warn_user', True) else "❌ 否"
            
            embed.add_field(
                name="⚙️ 保護設定",
                value=f"刪除訊息：{delete_message}\n管理員通知：{notify_admin}\n用戶警告：{warn_user}",
                inline=True
            )
            
            # 統計資訊
            try:
                stats = await self.cog.get_stats(self.guild_id)
                total_blocked = stats.get('total_blocked', 0)
                files_blocked = stats.get('files_blocked', 0)
                links_blocked = stats.get('links_blocked', 0)
                
                embed.add_field(
                    name="📈 攔截統計",
                    value=f"總攔截：{total_blocked}\n檔案攔截：{files_blocked}\n連結攔截：{links_blocked}",
                    inline=True
                )
            except Exception:
                embed.add_field(
                    name="📈 攔截統計",
                    value="無法載入統計資料",
                    inline=True
                )
            
            # 白名單和黑名單數量
            try:
                whitelist = await self.cog.get_whitelist(self.guild_id)
                blacklist = await self.cog.get_blacklist(self.guild_id)
                
                embed.add_field(
                    name="📋 清單狀態",
                    value=f"白名單：{len(whitelist)} 項\n黑名單：{len(blacklist)} 項",
                    inline=True
                )
            except Exception:
                embed.add_field(
                    name="📋 清單狀態",
                    value="無法載入清單資料",
                    inline=True
                )
            
            # 檢測格式
            try:
                formats = config.get('blocked_formats', [])
                formats_text = ', '.join(formats[:10])  # 只顯示前10個
                if len(formats) > 10:
                    formats_text += f" 等 {len(formats)} 種格式"
                
                embed.add_field(
                    name="🚫 檢測格式",
                    value=formats_text if formats_text else "未設定",
                    inline=False
                )
            except Exception:
                embed.add_field(
                    name="🚫 檢測格式",
                    value="無法載入格式資料",
                    inline=False
                )
            
            # 設定頁尾
            embed.set_footer(
                text="使用下方按鈕進行操作 | 面板將在5分鐘後自動關閉",
                icon_url="https://cdn.discordapp.com/emojis/1234567890.png"
            )
            
            return embed
            
        except Exception as exc:
            # 錯誤處理
            embed = discord.Embed(
                title="❌ 載入失敗",
                description=f"載入主要面板時發生錯誤：{exc}",
                color=discord.Color.red()
            )
            return embed 