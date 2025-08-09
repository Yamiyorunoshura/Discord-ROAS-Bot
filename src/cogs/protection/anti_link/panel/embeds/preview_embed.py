"""
 - Embed
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from ...main.main import AntiLink


class PreviewEmbed:
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
            settings = await self.cog.db.get_settings(self.guild_id)

            # Embed
            embed = discord.Embed(
                title=" ",
                description="",
                color=discord.Color.blue(),
            )

            status = "🟢 " if settings.get("enabled", False) else " "
            embed.add_field(name=" ", value=status, inline=True)

            stats = await self.cog.db.get_stats(self.guild_id)
            total_blocked = stats.get("total_blocked", 0)
            embed.add_field(
                name=" ",
                value=f" {total_blocked} ",
                inline=True,
            )

            whitelist_count = await self.cog.db.get_whitelist_count(self.guild_id)
            embed.add_field(
                name=" ", value=f"{whitelist_count} ", inline=True
            )

            remote_count = len(self.cog._remote_blacklist)
            manual_count = len(self.cog._manual_blacklist.get(self.guild_id, set()))
            embed.add_field(
                name=" ",
                value=f": {remote_count} \n: {manual_count} ",
                inline=True,
            )

            delete_msg = "" if settings.get("delete_message", True) else ""
            notify_admins = "" if settings.get("notify_admins", True) else ""
            embed.add_field(
                name=" ",
                value=f": {delete_msg}\n: {notify_admins}",
                inline=True,
            )

            if hasattr(self.cog, "_last_update"):
                embed.add_field(
                    name=" ",
                    value=f"<t:{int(self.cog._last_update)}:R>",
                    inline=True,
                )

            embed.set_thumbnail(
                url="https://cdn.discordapp.com/emojis/1234567890123456789.png"
            )

            embed.set_footer(
                text=" | ",
                icon_url="https://cdn.discordapp.com/emojis/1234567890123456789.png",
            )

            return embed

        except Exception as exc:
            embed = discord.Embed(
                title=" ",
                description=f":{exc}",
                color=discord.Color.red(),
            )
            return embed
