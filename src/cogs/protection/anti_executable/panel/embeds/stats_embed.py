"""
 -  Embed 
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from ...main.main import AntiExecutable

MIN_TREND_DATA_POINTS = 2


class StatsEmbed:
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

    async def create_embed(self) -> discord.Embed:
        """
         Embed

        Returns:
             Embed
        """
        try:
            stats = await self.cog.get_stats(self.guild_id)
            embed = self._create_base_embed()

            self._add_overall_stats(embed, stats)
            self._add_today_stats(embed, stats)
            self._add_week_stats(embed, stats)
            self._add_top_formats(embed, stats)
            self._add_recent_blocks(embed, stats)
            self._add_trend_analysis(embed, stats)
            self._add_last_update(embed, stats)
            self._set_embed_footer(embed)

            return embed

        except Exception as exc:
            return self._create_error_embed(exc)

    def _create_base_embed(self) -> discord.Embed:
        """ Embed"""
        return discord.Embed(
            title=" ",
            description="",
            color=discord.Color.blue(),
        )

    def _add_overall_stats(self, embed: discord.Embed, stats: dict) -> None:
        """"""
        total_blocked = stats.get("total_blocked", 0)
        files_blocked = stats.get("files_blocked", 0)
        links_blocked = stats.get("links_blocked", 0)

        embed.add_field(
            name=" ",
            value=f":{total_blocked}\n:{files_blocked}\n:{links_blocked}",
            inline=True,
        )

    def _add_today_stats(self, embed: discord.Embed, stats: dict) -> None:
        """"""
        today_stats = stats.get("today", {})
        today_blocked = today_stats.get("total", 0)
        today_files = today_stats.get("files", 0)
        today_links = today_stats.get("links", 0)

        embed.add_field(
            name=" ",
            value=f":{today_blocked}\n:{today_files}\n:{today_links}",
            inline=True,
        )

    def _add_week_stats(self, embed: discord.Embed, stats: dict) -> None:
        """"""
        week_stats = stats.get("week", {})
        week_blocked = week_stats.get("total", 0)
        week_files = week_stats.get("files", 0)
        week_links = week_stats.get("links", 0)

        embed.add_field(
            name=" ",
            value=f":{week_blocked}\n:{week_files}\n:{week_links}",
            inline=True,
        )

    def _add_top_formats(self, embed: discord.Embed, stats: dict) -> None:
        """"""
        top_formats = stats.get("top_formats", [])
        if top_formats:
            format_text = "\n".join(
                [
                    f"{i + 1}. {fmt['format']} ({fmt['count']})"
                    for i, fmt in enumerate(top_formats[:5])
                ]
            )
            embed.add_field(name="", value=format_text, inline=True)
        else:
            embed.add_field(name="", value="", inline=True)

    def _add_recent_blocks(self, embed: discord.Embed, stats: dict) -> None:
        """"""
        recent_blocks = stats.get("recent_blocks", [])
        if recent_blocks:
            recent_text = ""
            for block in recent_blocks[:3]:
                timestamp = datetime.fromisoformat(block["timestamp"])
                time_str = timestamp.strftime("%m/%d %H:%M")
                recent_text += f"• {time_str} - {block['type']}: {block['filename']}\n"
            embed.add_field(name=" ", value=recent_text, inline=True)
        else:
            embed.add_field(name=" ", value="", inline=True)

    def _add_trend_analysis(self, embed: discord.Embed, stats: dict) -> None:
        """"""
        trend_data = stats.get("trend", [])
        if trend_data and len(trend_data) >= MIN_TREND_DATA_POINTS:
            current_week = trend_data[-1]
            previous_week = trend_data[-2]

            if previous_week > 0:
                trend_percent = ((current_week - previous_week) / previous_week) * 100
                trend_icon = (
                    "" if trend_percent > 0 else "" if trend_percent < 0 else ""
                )
                trend_text = f"{trend_icon} {abs(trend_percent):.1f}%"
            else:
                trend_text = " "

            embed.add_field(
                name=" ", value=f":{trend_text}", inline=False
            )

    def _add_last_update(self, embed: discord.Embed, stats: dict) -> None:
        """"""
        last_update = stats.get("last_update")
        if last_update:
            update_time = datetime.fromisoformat(last_update)
            embed.add_field(
                name=" ",
                value=update_time.strftime("%Y/%m/%d %H:%M:%S"),
                inline=True,
            )

    def _set_embed_footer(self, embed: discord.Embed) -> None:
        """ Embed """
        embed.set_footer(
            text="",
            icon_url="https://cdn.discordapp.com/emojis/1234567890.png",
        )

    def _create_error_embed(self, exc: Exception) -> discord.Embed:
        """ Embed"""
        return discord.Embed(
            title=" ",
            description=f":{exc}",
            color=discord.Color.red(),
        )
