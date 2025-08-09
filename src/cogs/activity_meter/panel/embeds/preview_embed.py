"""

- 
- PRD v1.71
"""

import logging
from datetime import datetime

import discord

from ...config import config
from ...database.database import ActivityDatabase
from ...main.embed_optimizer import optimize_embed, validate_embed

logger = logging.getLogger("activity_meter")


async def create_preview_embed(
    _bot: discord.Client, guild: discord.Guild | None, db: ActivityDatabase
) -> discord.Embed:
    """
    

    Args:
        _bot: Discord  ()
        guild: Discord 
        db: 

    Returns:
        discord.Embed: 
    """
    embed = discord.Embed(
        title=" ",
        description="",
        color=discord.Color.green(),
    )

    if guild:
        embed.set_author(
            name=guild.name, icon_url=guild.icon.url if guild.icon else None
        )

    if not guild:
        embed.add_field(name="", value="", inline=False)
        return embed

    try:
        progress_style = await db.get_progress_style(guild.id)
    except Exception:
        progress_style = "classic"

    style_names = {
        "classic": "",
        "modern": "",
        "neon": "",
        "minimal": "",
        "gradient": "",
    }
    current_style_name = style_names.get(progress_style, "")

    embed.add_field(
        name=" ",
        value=f"**{current_style_name}** ({progress_style})",
        inline=True,
    )

    embed.add_field(
        name=" ",
        value=(
            "• \n"
            "• 75%\n"
            "• "
        ),
        inline=False,
    )

    style_features = {
        "classic": ",",
        "modern": ",",
        "neon": ",",
        "minimal": ",",
        "gradient": ",",
    }

    embed.add_field(
                        name="",
        value=style_features.get(progress_style, ","),
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

    embed.set_footer(
        text=f" •  v1.71 • {datetime.now(config.TW_TZ).strftime('%Y-%m-%d')}"
    )

    #  embed
    validation_result = validate_embed(embed)
    if not validation_result["is_valid"]:
        logger.warning(f"Preview embed : {validation_result['issues']}")
        embed = optimize_embed(embed)
        logger.info(f"Preview embed , : {validation_result['char_count']}")

    return embed
