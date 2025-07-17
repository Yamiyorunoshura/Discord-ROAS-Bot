"""
活躍度系統預覽面板嵌入生成器
- 生成排行榜預覽的嵌入
"""

import discord
from datetime import datetime
from typing import Optional, Dict, List, Any

from ...config import config
from ...database.database import ActivityDatabase

async def create_preview_embed(bot: discord.Client, guild: Optional[discord.Guild], db: ActivityDatabase) -> discord.Embed:
    """
    創建活躍度系統排行榜預覽嵌入
    
    Args:
        bot: Discord 機器人實例
        guild: Discord 伺服器
        db: 活躍度資料庫實例
        
    Returns:
        discord.Embed: 排行榜預覽嵌入
    """
    embed = discord.Embed(
        title="📊 排行榜預覽",
        description="這是自動播報排行榜的預覽效果",
        color=discord.Color.green()
    )
    
    # 顯示伺服器資訊
    if guild:
        embed.set_author(name=guild.name, icon_url=guild.icon.url if guild.icon else None)
    
    if not guild:
        embed.add_field(
            name="❌ 無法預覽",
            value="無法獲取伺服器資訊",
            inline=False
        )
        return embed
    
    # 獲取今日日期
    now = datetime.now(config.TW_TZ)
    ymd = now.strftime(config.DAY_FMT)
    ym = now.strftime(config.MONTH_FMT)
    days = int(now.strftime("%d"))
    
    # 獲取排行榜資料
    rankings = await db.get_daily_rankings(ymd, guild.id, limit=5)
    
    if not rankings:
        embed.add_field(
            name="📭 尚無資料",
            value="今天還沒有人發送訊息，無法顯示排行榜",
            inline=False
        )
        return embed
    
    # 獲取月度統計
    monthly_stats = await db.get_monthly_stats(ym, guild.id)
    
    # 生成排行榜
    lines = []
    for rank, data in enumerate(rankings, 1):
        user_id = data["user_id"]
        msg_cnt = data["msg_cnt"]
        
        mavg = monthly_stats.get(user_id, 0) / days if days else 0
        member = guild.get_member(user_id)
        name = member.display_name if member else f"<@{user_id}>"
        
        lines.append(f"`#{rank:2}` {name:<20} ‧ 今日 {msg_cnt} 則 ‧ 月均 {mavg:.1f}")
    
    embed.description = "\n".join(lines)
    
    # 獲取播報頻道設定
    report_channels = await db.get_report_channels()
    channel_id = next((ch_id for g_id, ch_id in report_channels if g_id == guild.id), None)
    
    # 顯示播報頻道資訊
    if channel_id:
        channel = guild.get_channel(channel_id)
        embed.add_field(
            name="📢 自動播報頻道",
            value=channel.mention if channel else "找不到頻道",
            inline=False
        )
    else:
        embed.add_field(
            name="📢 自動播報頻道",
            value="尚未設定，使用 `/設定排行榜頻道` 來設定",
            inline=False
        )
    
    embed.set_footer(text=f"活躍度系統 • 預覽面板 • {now.strftime('%Y-%m-%d')}")
    
    return embed 