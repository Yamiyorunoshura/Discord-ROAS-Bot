"""
 Embed 

 Embed
"""

from typing import TYPE_CHECKING, Any

import discord

if TYPE_CHECKING:
    from ...main import WelcomeCog


async def build_settings_embed(
    _cog: "WelcomeCog", guild: discord.Guild, settings: dict[str, Any]
) -> discord.Embed:
    """
     Embed

    Args:
        cog: WelcomeCog 
        guild: Discord 
        settings: 

    Returns:
        discord.Embed:  Embed
    """
    embed = discord.Embed(
        title="",
        description=",.",
        color=discord.Color.blue(),
    )

    channel_id = settings.get("channel_id")
    channel_name = ""
    if channel_id:
        channel = guild.get_channel(channel_id)
        if channel:
            channel_name = f"#{channel.name}"

    embed.add_field(name=" ", value=channel_name, inline=True)

    embed.add_field(
        name=" ", value=settings.get("title", ""), inline=True
    )

    embed.add_field(
        name=" ", value=settings.get("description", ""), inline=True
    )

    embed.add_field(
        name=" ", value=settings.get("message", ""), inline=False
    )

    embed.add_field(
        name="",
        value=f"X: {settings.get('avatar_x', 30)}, Y: {settings.get('avatar_y', 80)}",
        inline=True,
    )

    embed.add_field(
        name="",
        value=f" Y: {settings.get('title_y', 60)},  Y: {settings.get('description_y', 120)}",
        inline=True,
    )

    embed.add_field(
        name=" ",
        value=f": {settings.get('title_font_size', 36)}px, : {settings.get('desc_font_size', 22)}px",
        inline=True,
    )

    avatar_size = settings.get("avatar_size")
    avatar_size_text = f"{avatar_size}px" if avatar_size else ""
    embed.add_field(name=" ", value=avatar_size_text, inline=True)

    embed.add_field(
        name=" ",
        value=(
            ":\n"
            "`{member.name}` - \n"
            "`{member.mention}` - \n"
            "`{guild.name}` - \n"
            "`{emoji:}` - "
        ),
        inline=False,
    )

    embed.set_footer(text=f" ID: {guild.id} • ")

    return embed
