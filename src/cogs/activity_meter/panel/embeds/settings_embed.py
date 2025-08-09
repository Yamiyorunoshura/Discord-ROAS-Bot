"""

- 
- PRD v1.71
"""

import logging

import discord

from ...main.embed_optimizer import optimize_embed, validate_embed

logger = logging.getLogger("activity_meter")


async def create_settings_embed(
    guild: discord.Guild | None,
    channel_id: int | None,
    progress_style: str = "classic",
    announcement_time: int = 21,
) -> discord.Embed:
    """
    

    Args:
        guild: Discord 
        channel_id:  ID
        progress_style: 
        announcement_time: ()

    Returns:
        discord.Embed: 
    """
    embed = discord.Embed(
        title="",
        description="",
        color=discord.Color.blue(),
    )

    if guild:
        embed.set_author(
            name=guild.name, icon_url=guild.icon.url if guild.icon else None
        )

    style_names = {
        "classic": "",
        "modern": "",
        "neon": "",
        "minimal": "",
        "gradient": "",
    }
    current_style = style_names.get(progress_style, "")

    embed.add_field(
        name=" ",
        value=f"**{current_style}** ({progress_style})",
        inline=True,
    )

    embed.add_field(
        name=" ",
        value=f"<#{channel_id}>" if channel_id else "",
        inline=True,
    )

    embed.add_field(
        name="⏰ ", value=f"**{announcement_time:02d}:00**", inline=True
    )

    embed.add_field(
        name=" ",
        value=(
            "• \n"
            "• \n"
            "• \n"
            "• "
        ),
        inline=False,
    )

    embed.add_field(
        name=" ",
        value=(
            "• \n"
            "• \n"
            "• \n"
            "• "
        ),
        inline=False,
    )

    embed.set_footer(text=" •  v1.71")

    #  embed
    validation_result = validate_embed(embed)
    if not validation_result["is_valid"]:
        logger.warning(f"Settings embed : {validation_result['issues']}")
        embed = optimize_embed(embed)
        logger.info(f"Settings embed , : {validation_result['char_count']}")

    return embed
