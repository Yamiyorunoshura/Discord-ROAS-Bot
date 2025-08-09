"""Admin Panel Embed Renderer.

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


class AdminEmbedRenderer:
    """ Embed """

    def __init__(
        self,
        guild_stats: dict[str, Any],
        total_users: int,
        total_transactions: int,
        admin_id: int,
        guild_id: int,
    ):
        """
        

        Args:
            guild_stats: 
            total_users: 
            total_transactions: 
            admin_id: ID
            guild_id: ID
        """
        self.guild_stats = guild_stats or {}
        self.total_users = total_users
        self.total_transactions = total_transactions
        self.admin_id = admin_id
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
                color=discord.Color.red(),
                timestamp=datetime.utcnow(),
            )

            self._add_system_overview(embed)

            self._add_quick_stats(embed)

            self._add_admin_features(embed)

            self._add_security_notice(embed)

            embed.set_footer(
                text=f": {self.admin_id} • ",
                icon_url="https://cdn.discordapp.com/emojis/.png",
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

    def _add_system_overview(self, embed: discord.Embed):
        """"""
        try:
            total_currency = self.guild_stats.get("total_currency", 0)
            active_users = self.guild_stats.get("total_users", 0)

            overview_text = (
                f" ****: {total_currency:,}\n"
                f" ****: {active_users:,} \n"
                f" ****: {self.total_users:,} \n"
                f" ****: {self.total_transactions:,} "
            )

            embed.add_field(name=" ", value=overview_text, inline=True)

        except Exception as e:
            self.logger.warning(f": {e}")
            embed.add_field(name=" ", value="...", inline=True)

    def _add_quick_stats(self, embed: discord.Embed):
        """"""
        try:
            max_balance = self.guild_stats.get("max_balance", 0)
            min_balance = self.guild_stats.get("min_balance", 0)
            average_balance = self.guild_stats.get("average_balance", 0)

            stats_text = (
                f" ****: {average_balance:,.1f}\n"
                f" ****: {max_balance:,}\n"
                f" ****: {min_balance:,}\n"
                f" ****: "
            )

            embed.add_field(name=" ", value=stats_text, inline=True)

        except Exception as e:
            self.logger.warning(f": {e}")
            embed.add_field(name=" ", value="...", inline=True)

    def _add_admin_features(self, embed: discord.Embed):
        """"""
        try:
            features_text = (
                " **** - \n"
                " **** - \n"
                " **** - \n"
                " **** - \n"
                " **** - \n"
                " **** - "
            )

            embed.add_field(name=" ", value=features_text, inline=False)

        except Exception as e:
            self.logger.warning(f": {e}")

    def _add_security_notice(self, embed: discord.Embed):
        """"""
        try:
            security_text = (
                " ****\n"
                " ****\n"
                " ****"
            )

            embed.add_field(name=" ", value=security_text, inline=False)

        except Exception as e:
            self.logger.warning(f": {e}")
