"""

- 
- 
- 
"""

from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from ...main.main import AntiSpam

from ...config.config import CONFIG_CATEGORIES, DEFAULTS


async def create_settings_embed(
    cog: "AntiSpam", guild: discord.Guild, category: str = "all"
) -> discord.Embed:
    """
    

    Args:
        cog: AntiSpam 
        guild: Discord 
        category:  ("all" ID)

    Returns:
        discord.Embed: 
    """

    if category == "all":
        return await _create_overview_embed(cog, guild)
    else:
        return await _create_category_embed(cog, guild, category)


async def _create_overview_embed(
    cog: "AntiSpam", guild: discord.Guild
) -> discord.Embed:
    """"""
    embed = discord.Embed(
        title="🚫 防洗版系統設定",
        description=f"🏠 伺服器: {guild.name}",
        color=discord.Color.blue(),
    )

    enabled = await cog.get_cfg(guild.id, "enabled", "true")
    status_emoji = "🟢" if enabled and enabled.lower() == "true" else "🔴"
    embed.add_field(
        name="📊 系統狀態",
        value=f"{status_emoji} 狀態: {'已啟用' if enabled and enabled.lower() == 'true' else '已停用'}",
        inline=False,
    )

    freq_limit = await cog.get_cfg(
        guild.id, "spam_freq_limit", str(DEFAULTS["spam_freq_limit"])
    )
    freq_window = await cog.get_cfg(
        guild.id, "spam_freq_window", str(DEFAULTS["spam_freq_window"])
    )
    identical_limit = await cog.get_cfg(
        guild.id, "spam_identical_limit", str(DEFAULTS["spam_identical_limit"])
    )
    timeout_minutes = await cog.get_cfg(
        guild.id, "spam_timeout_minutes", str(DEFAULTS["spam_timeout_minutes"])
    )

    embed.add_field(
        name="⚡ 頻率限制",
        value=f"📊 {freq_limit or DEFAULTS['spam_freq_limit']} 則訊息 / {freq_window or DEFAULTS['spam_freq_window']} 秒",
        inline=True,
    )

    embed.add_field(
        name="🔄 重複限制",
        value=f"📝 {identical_limit or DEFAULTS['spam_identical_limit']} 則相同訊息",
        inline=True,
    )

    embed.add_field(
        name="⏰ 禁言時間",
        value=f"🔕 {timeout_minutes or DEFAULTS['spam_timeout_minutes']} 分鐘",
        inline=True,
    )

    notify_channel = await cog.get_cfg(guild.id, "spam_notify_channel", "")
    if notify_channel:
        try:
            channel = guild.get_channel(int(notify_channel))
            channel_name = channel.name if channel else ""
        except Exception:
            channel_name = ""
    else:
        channel_name = ""

    embed.add_field(name="📢 通知頻道", value=f"📺 #{channel_name}", inline=False)

    embed.add_field(
        name="🎮 快速設定",
        value=(
            "🔸 **頻率** - 控制訊息發送頻率\n"
            "🔸 **重複** - 偵測重複或相似訊息\n"
            "🔸 **貼圖** - 限制表情貼圖使用\n"
            "🔸 **動作** - 設定違規時的處理方式"
        ),
        inline=False,
    )

    embed.set_footer(text="使用下方按鈕來調整各項設定")
    return embed


async def _create_category_embed(
    cog: "AntiSpam", guild: discord.Guild, category_id: str
) -> discord.Embed:
    """"""
    category = CONFIG_CATEGORIES.get(category_id)
    if not category:
        return await _create_overview_embed(cog, guild)

    category_emojis = {
        "frequency": "",
        "repeat": "",
        "sticker": "",
        "action": "",
    }

    emoji = category_emojis.get(category_id, "")

    embed = discord.Embed(
        title=f"{emoji} {category['name']} ",
        description=category["desc"],
        color=discord.Color.blue(),
    )

    for item in category["items"]:
        key = item["key"]
        current_value = await cog.get_cfg(guild.id, key, str(DEFAULTS[key]))

        display_value = _format_config_value(
            key, current_value or str(DEFAULTS[key]), guild
        )

        embed.add_field(
            name=f" {item['name']}",
            value=(
                f"****: {display_value}\n"
                f"****: {item['desc']}\n"
                f"****: {item['recommend']}"
            ),
            inline=False,
        )

    embed.set_footer(text="")
    return embed


def _format_config_value(key: str, value: str, guild: discord.Guild) -> str:
    """"""
    try:
        formatters = {
            "spam_notify_channel": lambda v: _format_channel_value(v, guild),
            "spam_response_enabled": lambda v: ""
            if v.lower() == "true"
            else "",
            "spam_timeout_minutes": lambda v: f"{v} ",
            "spam_similar_threshold": lambda v: f"{float(v):.1%}",
            "spam_response_message": lambda v: f'"{v}"' if v else "",
        }

        limit_keys = [
            "spam_freq_limit",
            "spam_identical_limit",
            "spam_similar_limit",
            "spam_sticker_limit",
        ]
        window_keys = [
            "spam_freq_window",
            "spam_identical_window",
            "spam_similar_window",
            "spam_sticker_window",
        ]

        if key in formatters:
            return formatters[key](value)
        elif key in limit_keys:
            return f"{value} "
        elif key in window_keys:
            return f"{value} "
        else:
            return value

    except Exception:
        return value


def _format_channel_value(value: str, guild: discord.Guild) -> str:
    """"""
    if not value or value == "":
        return ""
    try:
        channel = guild.get_channel(int(value))
        return f"#{channel.name}" if channel else ""
    except Exception:
        return ""
