"""

- 
"""

import builtins
import contextlib

import discord

from ...config.config import MAX_CHANNELS_DISPLAY


async def settings_embed(cog) -> discord.Embed:
    """
    

    Args:
        cog: MessageListenerCog 

    Returns:
        discord.Embed: 
    """
    log_channel_id = await cog.get_setting("log_channel_id")
    log_edits = await cog.get_setting("log_edits", "false")
    log_deletes = await cog.get_setting("log_deletes", "false")
    batch_size = await cog.get_setting("batch_size", "10")
    batch_time = await cog.get_setting("batch_time", "600")

    embed = discord.Embed(
        title=" ",
        description=".",
        color=discord.Color.blue(),
    )

    log_channel = None
    if log_channel_id:
        with contextlib.suppress(builtins.BaseException):
            log_channel = cog.bot.get_channel(int(log_channel_id))

    embed.add_field(
        name=" ",
        value=f"{log_channel.mention if log_channel else ''}",
        inline=True,
    )

    monitored_channels = await cog.db.get_monitored_channels()
    monitored_count = len(monitored_channels)

    if monitored_count > 0:
        channels_text = []
        for _i, channel_id in enumerate(monitored_channels[:5]):
            channel = cog.bot.get_channel(channel_id)
            if channel:
                channels_text.append(channel.mention)
            else:
                channels_text.append(f" ({channel_id})")

        if monitored_count > MAX_CHANNELS_DISPLAY:
            channels_text.append(
                f"... {monitored_count - MAX_CHANNELS_DISPLAY} "
            )

        monitored_value = "\n".join(channels_text)
    else:
        monitored_value = ""

    embed.add_field(
        name=f"  ({monitored_count})", value=monitored_value, inline=True
    )

    embed.add_field(
        name=" ",
        value=(
            f"• : {batch_size} \n• : {int(batch_time) // 60} "
        ),
        inline=False,
    )

    embed.add_field(
        name=" ",
        value=(
            f"• : {' ' if log_edits == 'true' else ' '}\n"
            f"• : {' ' if log_deletes == 'true' else ' '}"
        ),
        inline=False,
    )

    embed.set_footer(text=" • ")

    return embed
