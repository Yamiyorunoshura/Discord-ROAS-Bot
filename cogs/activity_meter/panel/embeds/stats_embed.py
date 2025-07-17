"""
活躍度系統統計面板嵌入生成器
- 生成統計資訊的嵌入
"""

import discord
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any

from ...config import config
from ...database.database import ActivityDatabase

async def create_stats_embed(bot: discord.Client, guild: Optional[discord.Guild], db: ActivityDatabase) -> discord.Embed:
    """
    創建活躍度系統統計面板嵌入
    
    Args:
        bot: Discord 機器人實例
        guild: Discord 伺服器
        db: 活躍度資料庫實例
        
    Returns:
        discord.Embed: 統計面板嵌入
    """
    embed = discord.Embed(
        title="📈 活躍度系統統計",
        description="伺服器活躍度統計資訊",
        color=discord.Color.gold()
    )
    
    # 顯示伺服器資訊
    if guild:
        embed.set_author(name=guild.name, icon_url=guild.icon.url if guild.icon else None)
    
    if not guild:
        embed.add_field(
            name="❌ 無法獲取統計",
            value="無法獲取伺服器資訊",
            inline=False
        )
        return embed
    
    # 獲取今日日期
    now = datetime.now(config.TW_TZ)
    today_ymd = now.strftime(config.DAY_FMT)
    yesterday_ymd = (now - timedelta(days=1)).strftime(config.DAY_FMT)
    current_month = now.strftime(config.MONTH_FMT)
    
    # 獲取今日排行榜
    today_rankings = await db.get_daily_rankings(today_ymd, guild.id, limit=3)
    
    # 獲取昨日排行榜
    yesterday_rankings = await db.get_daily_rankings(yesterday_ymd, guild.id, limit=3)
    
    # 獲取月度統計
    monthly_stats = await db.get_monthly_stats(current_month, guild.id)
    
    # 計算總訊息數
    total_messages = sum(monthly_stats.values())
    
    # 顯示今日排行榜
    today_text = "今天還沒有人發送訊息"
    if today_rankings:
        today_lines = []
        for rank, data in enumerate(today_rankings, 1):
            user_id = data["user_id"]
            msg_cnt = data["msg_cnt"]
            
            member = guild.get_member(user_id)
            name = member.display_name if member else f"<@{user_id}>"
            
            today_lines.append(f"`#{rank}` {name} - {msg_cnt} 則")
        
        today_text = "\n".join(today_lines)
    
    embed.add_field(
        name="🔹 今日排行",
        value=today_text,
        inline=True
    )
    
    # 顯示昨日排行榜
    yesterday_text = "昨天沒有記錄"
    if yesterday_rankings:
        yesterday_lines = []
        for rank, data in enumerate(yesterday_rankings, 1):
            user_id = data["user_id"]
            msg_cnt = data["msg_cnt"]
            
            member = guild.get_member(user_id)
            name = member.display_name if member else f"<@{user_id}>"
            
            yesterday_lines.append(f"`#{rank}` {name} - {msg_cnt} 則")
        
        yesterday_text = "\n".join(yesterday_lines)
    
    embed.add_field(
        name="🔹 昨日排行",
        value=yesterday_text,
        inline=True
    )
    
    # 顯示月度統計
    days_in_month = int(now.strftime("%d"))
    daily_average = total_messages / days_in_month if days_in_month > 0 else 0
    
    embed.add_field(
        name="📅 本月統計",
        value=f"總訊息數：{total_messages} 則\n日均訊息：{daily_average:.1f} 則",
        inline=False
    )
    
    # 顯示活躍用戶數
    active_users = len([uid for uid, cnt in monthly_stats.items() if cnt > 0])
    
    embed.add_field(
        name="👥 活躍用戶",
        value=f"本月共有 {active_users} 位用戶發送過訊息",
        inline=True
    )
    
    # 顯示播報頻道設定
    report_channels = await db.get_report_channels()
    channel_id = next((ch_id for g_id, ch_id in report_channels if g_id == guild.id), None)
    
    embed.add_field(
        name="📢 自動播報",
        value=f"<#{channel_id}>" if channel_id else "尚未設定",
        inline=True
    )
    
    embed.set_footer(text=f"活躍度系統 • 統計面板 • {now.strftime('%Y-%m-%d')}")
    
    return embed 