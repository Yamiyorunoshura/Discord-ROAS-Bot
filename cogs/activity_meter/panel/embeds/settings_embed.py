"""
活躍度系統設定面板嵌入生成器
- 生成設定面板的嵌入
"""

import discord
from typing import Optional

async def create_settings_embed(guild: Optional[discord.Guild], channel_id: Optional[int]) -> discord.Embed:
    """
    創建活躍度系統設定面板嵌入
    
    Args:
        guild: Discord 伺服器
        channel_id: 目前設定的頻道 ID
        
    Returns:
        discord.Embed: 設定面板嵌入
    """
    embed = discord.Embed(
        title="⚙️ 活躍度系統設定",
        description="您可以在此設定活躍度系統的各項參數",
        color=discord.Color.blue()
    )
    
    # 顯示伺服器資訊
    if guild:
        embed.set_author(name=guild.name, icon_url=guild.icon.url if guild.icon else None)
    
    # 顯示目前設定
    embed.add_field(
        name="📢 自動播報頻道",
        value=f"<#{channel_id}>" if channel_id else "尚未設定",
        inline=False
    )
    
    # 說明
    embed.add_field(
        name="🔍 如何使用",
        value=(
            "• 使用 `/活躍度` 查看自己或他人的活躍度\n"
            "• 使用 `/今日排行榜` 查看今日訊息排行\n"
            "• 使用 `/設定排行榜頻道` 設定自動播報頻道"
        ),
        inline=False
    )
    
    # 設定說明
    embed.add_field(
        name="⏰ 自動播報",
        value="系統會在每天晚上 9 點自動發送排行榜到指定頻道",
        inline=False
    )
    
    embed.set_footer(text="活躍度系統 • 設定面板")
    
    return embed 