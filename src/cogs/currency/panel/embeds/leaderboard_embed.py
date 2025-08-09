"""Leaderboard Embed Renderer.

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

GOLD_MEDAL_RANK = 1
SILVER_MEDAL_RANK = 2
BRONZE_MEDAL_RANK = 3
MEDAL_TIER_MAX_RANK = 10
LEADERBOARD_SPLIT_THRESHOLD = 5

logger = logging.getLogger(__name__)


class LeaderboardEmbedRenderer:
    """ Embed """

    def __init__(
        self,
        leaderboard_data: dict[str, Any],
        current_page: int,
        per_page: int,
        user_id: int,
        guild_id: int,
    ):
        """
        

        Args:
            leaderboard_data: 
            current_page: (0)
            per_page: 
            user_id: ID()
            guild_id: ID
        """
        self.leaderboard_data = leaderboard_data or {}
        self.current_page = current_page
        self.per_page = per_page
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
            entries = self.leaderboard_data.get("entries", [])
            total_count = self.leaderboard_data.get("total_count", 0)

            total_pages = max(1, (total_count + self.per_page - 1) // self.per_page)
            page_display = self.current_page + 1

            embed = discord.Embed(
                title=" ",
                description=f" {page_display}/{total_pages}  •  {total_count:,} ",
                color=discord.Color.gold(),
                timestamp=datetime.utcnow(),
            )

            if not entries:
                embed.add_field(
                    name=" ",
                    value="\n!",
                    inline=False,
                )
            else:
                await self._add_leaderboard_entries(embed, entries)

            self._add_navigation_info(embed, total_pages)

            embed.set_footer(
                text=" • ",
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

    async def _add_leaderboard_entries(self, embed: discord.Embed, entries: list[dict]):
        """"""
        try:
            rank_lines = []

            for entry in entries:
                rank = entry.get("rank", 0)
                user_id = entry.get("user_id", 0)
                balance = entry.get("balance", 0)

                rank_emoji = self._get_rank_emoji(rank)

                user_display = await self._get_user_display_name(user_id)

                if user_id == self.user_id:
                    user_display = f"**{user_display}** "

                balance_display = f"{balance:,} "

                rank_line = f"{rank_emoji} {user_display}: {balance_display}"
                rank_lines.append(rank_line)

            if rank_lines:
                # ,
                if len(rank_lines) > LEADERBOARD_SPLIT_THRESHOLD:
                    mid_point = len(rank_lines) // 2

                    embed.add_field(
                        name="  ()",
                        value="\n".join(rank_lines[:mid_point]),
                        inline=True,
                    )

                    embed.add_field(
                        name="  ()",
                        value="\n".join(rank_lines[mid_point:]),
                        inline=True,
                    )
                else:
                    embed.add_field(
                        name=" ", value="\n".join(rank_lines), inline=False
                    )

        except Exception as e:
            self.logger.error(f": {e}")
            embed.add_field(name=" ", value="", inline=False)

    def _get_rank_emoji(self, rank: int) -> str:
        """"""
        if rank == GOLD_MEDAL_RANK:
            return ""
        elif rank == SILVER_MEDAL_RANK:
            return ""
        elif rank == BRONZE_MEDAL_RANK:
            return ""
        elif rank <= MEDAL_TIER_MAX_RANK:
            return ""
        else:
            return f"**{rank}.**"

    async def _get_user_display_name(self, user_id: int) -> str:
        """"""
        try:
            #
            #  bot ,
            return f" {user_id}"

        except Exception as e:
            self.logger.warning(f" {user_id} : {e}")
            return f" {user_id}"

    def _add_navigation_info(self, embed: discord.Embed, total_pages: int):
        """"""
        try:
            start_rank = self.current_page * self.per_page + 1
            end_rank = min(
                (self.current_page + 1) * self.per_page,
                self.leaderboard_data.get("total_count", 0),
            )

            nav_info = f" {start_rank}-{end_rank}\n"

            if total_pages > 1:
                nav_info += "  |  \n"

            nav_info += " "

            embed.add_field(name=" ", value=nav_info, inline=False)

        except Exception as e:
            self.logger.warning(f": {e}")
