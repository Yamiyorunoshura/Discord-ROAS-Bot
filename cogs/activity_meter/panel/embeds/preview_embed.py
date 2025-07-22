"""
活躍度系統預覽面板嵌入生成器
- 生成排行榜預覽的嵌入
- 支援PRD v1.71的進度條風格預覽功能
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
        title="👀 進度條風格預覽",
        description="預覽當前設定的進度條風格效果",
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
    
    # 獲取當前進度條風格設定
    try:
        progress_style = await db.get_progress_style(guild.id)
    except:
        progress_style = "classic"
    
    # 風格名稱映射
    style_names = {
        "classic": "經典",
        "modern": "現代", 
        "neon": "霓虹",
        "minimal": "極簡",
        "gradient": "漸層"
    }
    current_style_name = style_names.get(progress_style, "經典")
    
    # 顯示當前風格
    embed.add_field(
        name="🎨 當前風格",
        value=f"**{current_style_name}** ({progress_style})",
        inline=True
    )
    
    # 顯示預覽說明
    embed.add_field(
        name="📋 預覽說明",
        value=(
            "• 點擊「預覽進度條風格」按鈕查看實際效果\n"
            "• 預覽圖片將顯示75%進度的示例\n"
            "• 包含邊框、背景、進度條和文字效果"
        ),
        inline=False
    )
    
    # 顯示風格特點
    style_features = {
        "classic": "傳統風格，適合大多數場景",
        "modern": "現代設計，簡潔大方",
        "neon": "霓虹效果，視覺衝擊力強",
        "minimal": "極簡風格，清爽簡潔",
        "gradient": "漸層效果，色彩豐富"
    }
    
    embed.add_field(
        name="✨ 風格特點",
        value=style_features.get(progress_style, "經典風格，適合大多數場景"),
        inline=False
    )
    
    # 顯示設定說明
    embed.add_field(
        name="🔧 如何變更",
        value=(
            "• 切換到「設定」頁面\n"
            "• 使用「進度條風格」下拉選單選擇新風格\n"
            "• 點擊「套用設定」保存變更\n"
            "• 返回此頁面查看新風格效果"
        ),
        inline=False
    )
    
    embed.set_footer(text=f"活躍度系統 • 預覽面板 v1.71 • {datetime.now(config.TW_TZ).strftime('%Y-%m-%d')}")
    
    return embed 