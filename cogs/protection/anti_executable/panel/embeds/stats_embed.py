"""
反可執行檔案保護模組 - 統計面板 Embed 生成器
"""

import discord
from typing import TYPE_CHECKING
from datetime import datetime, timedelta

if TYPE_CHECKING:
    from ...main.main import AntiExecutable

class StatsEmbed:
    """統計面板 Embed 生成器"""
    
    def __init__(self, cog: AntiExecutable, guild_id: int):
        """
        初始化統計面板 Embed 生成器
        
        Args:
            cog: 反可執行檔案模組實例
            guild_id: 伺服器ID
        """
        self.cog = cog
        self.guild_id = guild_id
    
    async def create_embed(self) -> discord.Embed:
        """
        創建統計面板 Embed
        
        Returns:
            統計面板的 Embed
        """
        try:
            # 獲取統計資料
            stats = await self.cog.get_stats(self.guild_id)
            
            # 創建基礎 Embed
            embed = discord.Embed(
                title="📊 攔截統計",
                description="反可執行檔案保護模組的詳細統計資料",
                color=discord.Color.blue()
            )
            
            # 總體統計
            total_blocked = stats.get('total_blocked', 0)
            files_blocked = stats.get('files_blocked', 0)
            links_blocked = stats.get('links_blocked', 0)
            
            embed.add_field(
                name="🛡️ 總體統計",
                value=f"總攔截次數：{total_blocked}\n檔案攔截：{files_blocked}\n連結攔截：{links_blocked}",
                inline=True
            )
            
            # 今日統計
            today_stats = stats.get('today', {})
            today_blocked = today_stats.get('total', 0)
            today_files = today_stats.get('files', 0)
            today_links = today_stats.get('links', 0)
            
            embed.add_field(
                name="📅 今日統計",
                value=f"今日攔截：{today_blocked}\n檔案攔截：{today_files}\n連結攔截：{today_links}",
                inline=True
            )
            
            # 本週統計
            week_stats = stats.get('week', {})
            week_blocked = week_stats.get('total', 0)
            week_files = week_stats.get('files', 0)
            week_links = week_stats.get('links', 0)
            
            embed.add_field(
                name="📆 本週統計",
                value=f"本週攔截：{week_blocked}\n檔案攔截：{week_files}\n連結攔截：{week_links}",
                inline=True
            )
            
            # 最常攔截的格式
            top_formats = stats.get('top_formats', [])
            if top_formats:
                format_text = "\n".join([f"{i+1}. {fmt['format']} ({fmt['count']}次)" 
                                       for i, fmt in enumerate(top_formats[:5])])
                embed.add_field(
                    name="🔝 最常攔截格式",
                    value=format_text,
                    inline=True
                )
            else:
                embed.add_field(
                    name="🔝 最常攔截格式",
                    value="暫無資料",
                    inline=True
                )
            
            # 最近攔截記錄
            recent_blocks = stats.get('recent_blocks', [])
            if recent_blocks:
                recent_text = ""
                for block in recent_blocks[:3]:
                    timestamp = datetime.fromisoformat(block['timestamp'])
                    time_str = timestamp.strftime("%m/%d %H:%M")
                    recent_text += f"• {time_str} - {block['type']}: {block['filename']}\n"
                
                embed.add_field(
                    name="🕐 最近攔截",
                    value=recent_text,
                    inline=True
                )
            else:
                embed.add_field(
                    name="🕐 最近攔截",
                    value="暫無記錄",
                    inline=True
                )
            
            # 攔截趨勢
            trend_data = stats.get('trend', [])
            if trend_data and len(trend_data) >= 2:
                current_week = trend_data[-1]
                previous_week = trend_data[-2]
                
                if previous_week > 0:
                    trend_percent = ((current_week - previous_week) / previous_week) * 100
                    trend_icon = "📈" if trend_percent > 0 else "📉" if trend_percent < 0 else "➡️"
                    trend_text = f"{trend_icon} {abs(trend_percent):.1f}%"
                else:
                    trend_text = "➡️ 無變化"
                
                embed.add_field(
                    name="📊 攔截趨勢",
                    value=f"相較上週：{trend_text}",
                    inline=False
                )
            
            # 最後更新時間
            last_update = stats.get('last_update')
            if last_update:
                update_time = datetime.fromisoformat(last_update)
                embed.add_field(
                    name="🔄 最後更新",
                    value=update_time.strftime("%Y/%m/%d %H:%M:%S"),
                    inline=True
                )
            
            # 設定頁尾
            embed.set_footer(
                text="統計資料每小時更新一次",
                icon_url="https://cdn.discordapp.com/emojis/1234567890.png"
            )
            
            return embed
            
        except Exception as exc:
            # 錯誤處理
            embed = discord.Embed(
                title="❌ 載入失敗",
                description=f"載入統計面板時發生錯誤：{exc}",
                color=discord.Color.red()
            )
            return embed 