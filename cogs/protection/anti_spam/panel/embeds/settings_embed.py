"""
反垃圾訊息設定面板嵌入生成器
- 生成各種設定視圖的嵌入
- 支援分類和總覽顯示
- 格式化設定值和說明
"""

import discord
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ...main.main import AntiSpam

from ...config.config import CONFIG_CATEGORIES, DEFAULTS, CH_NAMES

async def create_settings_embed(cog: "AntiSpam", guild: discord.Guild, category: str = "all") -> discord.Embed:
    """
    創建設定嵌入
    
    Args:
        cog: AntiSpam 模組實例
        guild: Discord 伺服器物件
        category: 要顯示的分類 ("all" 或分類ID)
        
    Returns:
        discord.Embed: 設定嵌入
    """
    
    if category == "all":
        return await _create_overview_embed(cog, guild)
    else:
        return await _create_category_embed(cog, guild, category)

async def _create_overview_embed(cog: "AntiSpam", guild: discord.Guild) -> discord.Embed:
    """創建總覽嵌入"""
    embed = discord.Embed(
        title="🛡️ 反垃圾訊息保護設定",
        description=f"伺服器：{guild.name}",
        color=discord.Color.blue()
    )
    
    # 檢查模組是否啟用
    enabled = await cog.get_cfg(guild.id, "enabled", "true")
    status_emoji = "✅" if enabled and enabled.lower() == "true" else "❌"
    embed.add_field(
        name="📊 系統狀態",
        value=f"{status_emoji} 模組狀態：{'啟用' if enabled and enabled.lower() == 'true' else '停用'}",
        inline=False
    )
    
    # 顯示主要設定摘要
    freq_limit = await cog.get_cfg(guild.id, "spam_freq_limit", str(DEFAULTS["spam_freq_limit"]))
    freq_window = await cog.get_cfg(guild.id, "spam_freq_window", str(DEFAULTS["spam_freq_window"]))
    identical_limit = await cog.get_cfg(guild.id, "spam_identical_limit", str(DEFAULTS["spam_identical_limit"]))
    timeout_minutes = await cog.get_cfg(guild.id, "spam_timeout_minutes", str(DEFAULTS["spam_timeout_minutes"]))
    
    embed.add_field(
        name="⚡ 頻率限制",
        value=f"{freq_limit or DEFAULTS['spam_freq_limit']} 訊息 / {freq_window or DEFAULTS['spam_freq_window']} 秒",
        inline=True
    )
    
    embed.add_field(
        name="🔄 重複限制",
        value=f"{identical_limit or DEFAULTS['spam_identical_limit']} 次重複",
        inline=True
    )
    
    embed.add_field(
        name="⚔️ 禁言時間",
        value=f"{timeout_minutes or DEFAULTS['spam_timeout_minutes']} 分鐘",
        inline=True
    )
    
    # 通知設定
    notify_channel = await cog.get_cfg(guild.id, "spam_notify_channel", "")
    if notify_channel:
        try:
            channel = guild.get_channel(int(notify_channel))
            channel_name = channel.name if channel else "已刪除的頻道"
        except:
            channel_name = "無效頻道"
    else:
        channel_name = "未設定"
    
    embed.add_field(
        name="📢 通知設定",
        value=f"通知頻道：{channel_name}",
        inline=False
    )
    
    # 分類說明
    embed.add_field(
        name="📋 設定分類",
        value=(
            "⚡ **頻率限制** - 訊息發送頻率控制\n"
            "🔄 **重複/相似** - 重複和相似內容檢測\n"
            "😀 **貼圖限制** - 貼圖使用頻率控制\n"
            "⚔️ **處理動作** - 違規處理和通知設定"
        ),
        inline=False
    )
    
    embed.set_footer(text="選擇上方的分類進行詳細設定")
    return embed

async def _create_category_embed(cog: "AntiSpam", guild: discord.Guild, category_id: str) -> discord.Embed:
    """創建分類設定嵌入"""
    category = CONFIG_CATEGORIES.get(category_id)
    if not category:
        # 回退到總覽
        return await _create_overview_embed(cog, guild)
    
    # 分類圖標
    category_emojis = {
        "frequency": "⚡",
        "repeat": "🔄",
        "sticker": "😀",
        "action": "⚔️"
    }
    
    emoji = category_emojis.get(category_id, "⚙️")
    
    embed = discord.Embed(
        title=f"{emoji} {category['name']} 設定",
        description=category['desc'],
        color=discord.Color.blue()
    )
    
    # 顯示該分類的所有設定項
    for item in category['items']:
        key = item['key']
        current_value = await cog.get_cfg(guild.id, key, str(DEFAULTS[key]))
        
        # 格式化值顯示
        display_value = _format_config_value(key, current_value or str(DEFAULTS[key]), guild)
        
        embed.add_field(
            name=f"🔧 {item['name']}",
            value=(
                f"**當前值**: {display_value}\n"
                f"**說明**: {item['desc']}\n"
                f"**建議**: {item['recommend']}"
            ),
            inline=False
        )
    
    embed.set_footer(text="點擊下方按鈕進行設定或查看其他功能")
    return embed

def _format_config_value(key: str, value: str, guild: discord.Guild) -> str:
    """格式化設定值顯示"""
    try:
        if key == "spam_notify_channel":
            if not value or value == "":
                return "未設定"
            try:
                channel = guild.get_channel(int(value))
                return f"#{channel.name}" if channel else "無效頻道"
            except:
                return "無效頻道"
        
        elif key in ["spam_response_enabled"]:
            return "啟用" if value.lower() == "true" else "停用"
        
        elif key in ["spam_freq_limit", "spam_identical_limit", "spam_similar_limit", "spam_sticker_limit"]:
            return f"{value} 次"
        
        elif key in ["spam_freq_window", "spam_identical_window", "spam_similar_window", "spam_sticker_window"]:
            return f"{value} 秒"
        
        elif key == "spam_timeout_minutes":
            return f"{value} 分鐘"
        
        elif key == "spam_similar_threshold":
            return f"{float(value):.1%}"
        
        elif key == "spam_response_message":
            return f'"{value}"' if value else "預設訊息"
        
        else:
            return value
            
    except:
        return value 