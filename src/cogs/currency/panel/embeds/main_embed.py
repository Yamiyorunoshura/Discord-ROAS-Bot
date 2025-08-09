"""Main Panel Embed Renderer.

 Embed ,:
- 
- 
- 
- 
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import discord

logger = logging.getLogger(__name__)

WEALTH_LEVEL_RICH = 100000
WEALTH_LEVEL_WEALTHY = 10000
WEALTH_LEVEL_AVERAGE = 1000
RANK_TOP_THREE = 3


class MainEmbedRenderer:
    """ Embed """

    def __init__(
        self,
        user_balance: int,
        user_rank_info: dict[str, Any],
        guild_stats: dict[str, Any],
        user_id: int,
        guild_id: int,
    ):
        """
        

        Args:
            user_balance: 
            user_rank_info: 
            guild_stats: 
            user_id: ID
            guild_id: ID
        """
        self.user_balance = user_balance
        self.user_rank_info = user_rank_info or {}
        self.guild_stats = guild_stats or {}
        self.user_id = user_id
        self.guild_id = guild_id
        self.logger = logger

    async def render(self) -> discord.Embed:
        """
         Embed

        Returns:
            discord.Embed: 
        """
        try:
            embed = discord.Embed(
                title=" ",
                description="",
                color=discord.Color.gold(),
                timestamp=datetime.utcnow(),
            )

            self._add_balance_info(embed)

            self._add_rank_info(embed)

            self._add_guild_stats(embed)

            self._add_operation_guide(embed)

            embed.set_footer(
                text=f" ID: {self.user_id} • ",
                icon_url="https://cdn.discordapp.com/emojis/749358574832967832.png",
            )

            return embed

        except Exception as e:
            self.logger.error(f" Embed : {e}")

            error_embed = discord.Embed(
                title=" ",
                description=",",
                color=discord.Color.red(),
            )
            return error_embed

    def _add_balance_info(self, embed: discord.Embed):
        """"""
        try:
            balance_display = f"**{self.user_balance:,}** "

            if self.user_balance >= WEALTH_LEVEL_RICH:
                balance_emoji = ""
            elif self.user_balance >= WEALTH_LEVEL_WEALTHY:
                balance_emoji = ""
            elif self.user_balance >= WEALTH_LEVEL_AVERAGE:
                balance_emoji = ""
            else:
                balance_emoji = ""

            embed.add_field(
                name=f"{balance_emoji} ", value=balance_display, inline=True
            )

        except Exception as e:
            self.logger.warning(f": {e}")
            embed.add_field(name=" ", value="...", inline=True)

    def _add_rank_info(self, embed: discord.Embed):
        """"""
        try:
            rank = self.user_rank_info.get("rank", 0)
            total_users = self.user_rank_info.get("total_users", 0)
            percentile = self.user_rank_info.get("percentile", 0)

            if rank > 0 and total_users > 0:
                if rank <= RANK_TOP_THREE:
                    rank_emoji = ["", "", ""][rank - 1]
                    rank_display = f"{rank_emoji}  **{rank}** "
                else:
                    rank_display = f"  **{rank}** "

                embed.add_field(
                    name=" ",
                    value=f"{rank_display}\n"
                    + f" **{percentile:.1f}%** •  {total_users:,} ",
                    inline=True,
                )
            else:
                embed.add_field(
                    name=" ",
                    value="\n!",
                    inline=True,
                )

        except Exception as e:
            self.logger.warning(f": {e}")
            embed.add_field(name=" ", value="...", inline=True)

    def _add_guild_stats(self, embed: discord.Embed):
        """"""
        try:
            total_currency = self.guild_stats.get("total_currency", 0)
            total_users = self.guild_stats.get("total_users", 0)
            average_balance = self.guild_stats.get("average_balance", 0)

            if total_currency > 0:
                stats_text = (
                    f" : **{total_currency:,}**\n"
                    f" : **{total_users:,}** \n"
                    f" : **{average_balance:,.1f}**"
                )
            else:
                stats_text = "..."

            embed.add_field(name=" ", value=stats_text, inline=False)

        except Exception as e:
            self.logger.warning(f": {e}")
            embed.add_field(name=" ", value="...", inline=False)

    def _add_operation_guide(self, embed: discord.Embed):
        """"""
        try:
            guide_text = (
                " **** - \n"
                " **** - \n"
                " **** - \n"
                " **** - "
            )

            embed.add_field(name=" ", value=guide_text, inline=False)

        except Exception as e:
            self.logger.warning(f": {e}")
            # ,
