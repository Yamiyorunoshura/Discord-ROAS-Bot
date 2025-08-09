"""
 - Embed
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from ...main.main import AntiLink


class WhitelistEmbed:
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

    async def create_embed(self, page: int = 0) -> discord.Embed:
        """
        Embed

        Args:
            page: 

        Returns:
            Embed
        """
        try:
            embed = discord.Embed(
                title=" ",
                description="",
                color=discord.Color.green(),
            )

            whitelist = getattr(self.cog, "_whitelist_cache", {}).get(
                self.guild_id, set()
            )
            whitelist_count = len(whitelist)

            if whitelist_count > 0:
                items_per_page = 10
                start_idx = page * items_per_page
                end_idx = start_idx + items_per_page

                whitelist_list = list(whitelist)
                page_items = whitelist_list[start_idx:end_idx]

                if page_items:
                    whitelist_text = "\n".join([f"• {domain}" for domain in page_items])
                    embed.add_field(
                        name=f"  ( {page + 1} )",
                        value=whitelist_text,
                        inline=False,
                    )

                total_pages = (whitelist_count - 1) // items_per_page + 1
                embed.set_footer(
                    text=f": {page + 1}/{total_pages} | : {whitelist_count} "
                )
            else:
                embed.add_field(
                    name=" ",
                    value="\n",
                    inline=False,
                )
                embed.set_footer(text="")

            embed.add_field(
                name="",
                value="• \n•  (*) \n• ",
                inline=False,
            )

            return embed

        except Exception as exc:
            embed = discord.Embed(
                title=" ",
                description=f":{exc}",
                color=discord.Color.red(),
            )
            return embed
