"""Stats Embed Renderer.

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

GINI_EXCELLENT_THRESHOLD = 0.3
GINI_GOOD_THRESHOLD = 0.5
GINI_AVERAGE_THRESHOLD = 0.7

WEALTH_LEVEL_RICH = 100000
WEALTH_LEVEL_WEALTHY = 10000
WEALTH_LEVEL_AVERAGE = 1000


class StatsEmbedRenderer:
    """ Embed """

    def __init__(
        self,
        guild_stats: dict[str, Any],
        guild_id: int,
    ):
        """
        

        Args:
            guild_stats: 
            guild_id: ID
        """
        self.guild_stats = guild_stats or {}
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
                color=discord.Color.blue(),
                timestamp=datetime.utcnow(),
            )

            self._add_basic_stats(embed)

            self._add_user_distribution(embed)

            self._add_wealth_distribution(embed)

            self._add_transaction_stats(embed)

            self._add_trend_analysis(embed)

            embed.set_footer(
                text=f" {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC",
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

    def _add_basic_stats(self, embed: discord.Embed):
        """"""
        try:
            total_currency = self.guild_stats.get("total_currency", 0)
            total_users = self.guild_stats.get("total_users", 0)
            average_balance = self.guild_stats.get("average_balance", 0)
            total_transactions = self.guild_stats.get("total_transactions", 0)

            if total_users > 0:
                activity_rate = min(100, (total_transactions / total_users) * 10)
            else:
                activity_rate = 0

            basic_stats = (
                f" ****: {total_currency:,} \n"
                f" ****: {total_users:,} \n"
                f" ****: {average_balance:,.1f} \n"
                f" ****: {total_transactions:,} \n"
                f" ****: {activity_rate:.1f}%"
            )

            embed.add_field(name=" ", value=basic_stats, inline=True)

        except Exception as e:
            self.logger.warning(f": {e}")
            embed.add_field(name=" ", value="...", inline=True)

    def _add_user_distribution(self, embed: discord.Embed):
        """"""
        try:
            max_balance = self.guild_stats.get("max_balance", 0)
            min_balance = self.guild_stats.get("min_balance", 0)

            wealth_levels = self._calculate_wealth_distribution(max_balance)

            distribution = (
                f" **** (>100K): {wealth_levels['rich']}%\n"
                f" **** (10K-100K): {wealth_levels['wealthy']}%\n"
                f" **** (1K-10K): {wealth_levels['average']}%\n"
                f" **** (<1K): {wealth_levels['poor']}%\n"
                f" ****: {min_balance:,} - {max_balance:,}"
            )

            embed.add_field(name=" ", value=distribution, inline=True)

        except Exception as e:
            self.logger.warning(f": {e}")
            embed.add_field(name=" ", value="...", inline=True)

    def _add_wealth_distribution(self, embed: discord.Embed):
        """"""
        try:
            total_currency = self.guild_stats.get("total_currency", 0)
            total_users = self.guild_stats.get("total_users", 0)
            max_balance = self.guild_stats.get("max_balance", 0)

            if total_currency > 0 and max_balance > 0:
                wealth_concentration = (max_balance / total_currency) * 100
            else:
                wealth_concentration = 0

            gini_estimate = min(wealth_concentration / 50, 1.0)

            wealth_analysis = (
                f" ****: {max_balance:,} \n"
                f"****: {wealth_concentration:.1f}%\n"
                f"****: {gini_estimate:.2f}\n"
                f" ****: {total_currency / max(total_users, 1):,.1f}\n"
                f" ****: {self._get_economy_health(gini_estimate)}"
            )

            embed.add_field(name=" ", value=wealth_analysis, inline=False)

        except Exception as e:
            self.logger.warning(f": {e}")
            embed.add_field(name=" ", value="...", inline=False)

    def _add_transaction_stats(self, embed: discord.Embed):
        """"""
        try:
            total_transactions = self.guild_stats.get("total_transactions", 0)
            total_users = self.guild_stats.get("total_users", 0)

            if total_users > 0:
                avg_transactions_per_user = total_transactions / total_users
            else:
                avg_transactions_per_user = 0

            transaction_stats = (
                f" ****: {total_transactions:,} \n"
                f" ****: {avg_transactions_per_user:.1f} \n"
                f"****: {min(100, avg_transactions_per_user * 20):.1f}%\n"
                f" ****: \n"
                f" ****: "
            )

            embed.add_field(name=" ", value=transaction_stats, inline=True)

        except Exception as e:
            self.logger.warning(f": {e}")
            embed.add_field(name=" ", value="...", inline=True)

    def _add_trend_analysis(self, embed: discord.Embed):
        """"""
        try:
            # ,
            trend_analysis = (
                " ****: \n"
                "****: \n"
                "****: \n"
                "****: \n"
                " ****: "
            )

            embed.add_field(name=" ", value=trend_analysis, inline=True)

        except Exception as e:
            self.logger.warning(f": {e}")
            embed.add_field(name=" ", value="...", inline=True)

    def _calculate_wealth_distribution(self, max_balance: int) -> dict[str, int]:
        """()"""
        try:

            if max_balance >= WEALTH_LEVEL_RICH:
                return {"rich": 15, "wealthy": 25, "average": 35, "poor": 25}
            elif max_balance >= WEALTH_LEVEL_WEALTHY:
                return {"rich": 5, "wealthy": 20, "average": 45, "poor": 30}
            elif max_balance >= WEALTH_LEVEL_AVERAGE:
                return {"rich": 2, "wealthy": 15, "average": 43, "poor": 40}
            else:
                return {"rich": 0, "wealthy": 5, "average": 25, "poor": 70}

        except Exception as e:
            self.logger.warning(f": {e}")
            return {"rich": 0, "wealthy": 0, "average": 0, "poor": 100}

    def _get_economy_health(self, gini_coefficient: float) -> str:
        """"""
        if gini_coefficient < GINI_EXCELLENT_THRESHOLD:
            return " 🟢"
        elif gini_coefficient < GINI_GOOD_THRESHOLD:
            return " 🟡"
        elif gini_coefficient < GINI_AVERAGE_THRESHOLD:
            return " 🟠"
        else:
            return " "
