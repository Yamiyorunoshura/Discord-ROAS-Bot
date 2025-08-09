"""
 - Embed
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from ...main.main import AntiLink


class BlacklistEmbed:
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
                color=discord.Color.red(),
            )

            remote_count = len(getattr(self.cog, "_remote_blacklist", set()))
            embed.add_field(
                name=" ",
                value=f": {remote_count} ",
                inline=False,
            )

            manual_blacklist = getattr(self.cog, "_manual_blacklist", {}).get(
                self.guild_id, set()
            )
            manual_count = len(manual_blacklist)

            if manual_count > 0:
                items_per_page = 10
                start_idx = page * items_per_page
                end_idx = start_idx + items_per_page

                manual_list = list(manual_blacklist)
                page_items = manual_list[start_idx:end_idx]

                if page_items:
                    manual_text = "\n".join([f"• {domain}" for domain in page_items])
                    embed.add_field(
                        name=f"  ( {page + 1} )",
                        value=manual_text,
                        inline=False,
                    )

                total_pages = (manual_count - 1) // items_per_page + 1
                embed.set_footer(
                    text=f": {page + 1}/{total_pages} | : {manual_count} "
                )
            else:
                embed.add_field(
                    name=" ", value="", inline=False
                )

            return embed

        except Exception as exc:
            embed = discord.Embed(
                title=" ",
                description=f":{exc}",
                color=discord.Color.red(),
            )
            return embed
