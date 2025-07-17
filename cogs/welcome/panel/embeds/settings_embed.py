"""
歡迎系統設定面板 Embed 生成器

此模組負責生成歡迎系統設定面板的 Embed
"""

import discord
from typing import Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ...main import WelcomeCog


async def build_settings_embed(
    cog: "WelcomeCog", 
    guild: discord.Guild, 
    settings: Dict[str, Any]
) -> discord.Embed:
    """
    建立設定面板 Embed
    
    Args:
        cog: WelcomeCog 實例
        guild: Discord 伺服器物件
        settings: 設定值字典
        
    Returns:
        discord.Embed: 設定面板 Embed
    """
    embed = discord.Embed(
        title="🎉 歡迎訊息設定",
        description="調整歡迎訊息的各項設定，使用下方選單選擇要設定的項目。",
        color=discord.Color.blue()
    )
    
    # 取得歡迎頻道
    channel_id = settings.get("channel_id")
    channel_name = "未設定"
    if channel_id:
        channel = guild.get_channel(channel_id)
        if channel:
            channel_name = f"#{channel.name}"
    
    # 添加設定資訊
    embed.add_field(
        name="📺 歡迎頻道",
        value=channel_name,
        inline=True
    )
    
    embed.add_field(
        name="📝 圖片標題",
        value=settings.get("title", "未設定"),
        inline=True
    )
    
    embed.add_field(
        name="📄 圖片內容",
        value=settings.get("description", "未設定"),
        inline=True
    )
    
    embed.add_field(
        name="💬 歡迎訊息",
        value=settings.get("message", "未設定"),
        inline=False
    )
    
    # 添加位置設定
    embed.add_field(
        name="📍 頭像位置",
        value=f"X: {settings.get('avatar_x', 30)}, Y: {settings.get('avatar_y', 80)}",
        inline=True
    )
    
    embed.add_field(
        name="📍 文字位置",
        value=f"標題 Y: {settings.get('title_y', 60)}, 內容 Y: {settings.get('description_y', 120)}",
        inline=True
    )
    
    # 添加字體大小設定
    embed.add_field(
        name="🔤 字體大小",
        value=f"標題: {settings.get('title_font_size', 36)}px, 內容: {settings.get('desc_font_size', 22)}px",
        inline=True
    )
    
    # 添加頭像大小設定
    avatar_size = settings.get("avatar_size")
    avatar_size_text = f"{avatar_size}px" if avatar_size else "預設"
    embed.add_field(
        name="🖼️ 頭像大小",
        value=avatar_size_text,
        inline=True
    )
    
    # 添加變數說明
    embed.add_field(
        name="🔄 可用變數",
        value=(
            "在標題、內容和訊息中可使用以下變數：\n"
            "`{member.name}` - 成員名稱\n"
            "`{member.mention}` - 成員提及\n"
            "`{guild.name}` - 伺服器名稱\n"
            "`{emoji:名稱}` - 插入表情符號"
        ),
        inline=False
    )
    
    embed.set_footer(text=f"伺服器 ID: {guild.id} • 使用下方選單進行設定")
    
    return embed 