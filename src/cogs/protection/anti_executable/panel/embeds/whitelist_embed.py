"""
 -  Embed 
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from ...main.main import AntiExecutable


class WhitelistEmbed:
    """ Embed """

    def __init__(self, cog: AntiExecutable, guild_id: int):
        """
         Embed 

        Args:
            cog: 
            guild_id: ID
        """
        self.cog = cog
        self.guild_id = guild_id
        self.items_per_page = 10

    async def create_embed(self, page: int = 0) -> discord.Embed:
        """
         Embed

        Args:
            page: 

        Returns:
             Embed
        """
        try:
            whitelist = await self.cog.get_whitelist(self.guild_id)

            #  Embed
            embed = discord.Embed(
                title=" ",
                description="",
                color=discord.Color.green(),
            )

            total_items = len(whitelist)
            total_pages = max(
                1, (total_items + self.items_per_page - 1) // self.items_per_page
            )
            current_page = min(page, total_pages - 1)

            start_index = current_page * self.items_per_page
            end_index = min(start_index + self.items_per_page, total_items)

            if whitelist:
                whitelist_text = ""
                for i, item in enumerate(
                    whitelist[start_index:end_index], start=start_index + 1
                ):
                    whitelist_text += f"{i}. `{item}`\n"

                embed.add_field(
                    name=f"  ({start_index + 1}-{end_index}/{total_items})",
                    value=whitelist_text,
                    inline=False,
                )
            else:
                embed.add_field(
                    name=" ", value="", inline=False
                )

            if total_pages > 1:
                embed.add_field(
                    name=" ",
                    value=f" {current_page + 1} , {total_pages} ",
                    inline=True,
                )

            embed.add_field(
                name="i ",
                value=(
                    "• \n"
                    "• \n"
                    "• "
                ),
                inline=False,
            )

            embed.set_footer(
                text="",
                icon_url="https://cdn.discordapp.com/emojis/1234567890.png",
            )

            return embed

        except Exception as exc:
            embed = discord.Embed(
                title=" ",
                description=f":{exc}",
                color=discord.Color.red(),
            )
            return embed
