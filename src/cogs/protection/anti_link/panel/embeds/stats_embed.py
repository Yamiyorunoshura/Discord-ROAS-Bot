"""
 - Embed
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from ...main.main import AntiLink


class StatsEmbed:
    """Embed"""

    def __init__(self, cog: AntiLink, guild_id: int):
        """
        Embed

        Args:
            cog: 
            guild_id: ID
        """
        self.cog = cog
        self.guild_id = guild_id

    async def create_embed(self) -> discord.Embed:
        """
        Embed

        Returns:
            Embed
        """
        try:
            embed = discord.Embed(
                title=" ",
                description="",
                color=discord.Color.green(),
            )

            embed.add_field(
                name=" ",
                value="• : 0 \n• : 0 \n• : 0 ",
                inline=True,
            )

            embed.add_field(
                name=" ",
                value="• : 0 \n• : 0%\n• : 100%",
                inline=True,
            )

            embed.add_field(
                name=" ",
                value="• : 0 \n• : 0 \n• : 0 ",
                inline=True,
            )

            embed.set_footer(text="")

            return embed

        except Exception as exc:
            embed = discord.Embed(
                title=" ",
                description=f":{exc}",
                color=discord.Color.red(),
            )
            return embed
