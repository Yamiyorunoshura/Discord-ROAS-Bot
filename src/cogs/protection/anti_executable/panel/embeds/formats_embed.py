"""
 -  Embed 
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from ...main.main import AntiExecutable


class FormatsEmbed:
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
            config = await self.cog.get_config(self.guild_id)
            blocked_formats = config.get("blocked_formats", [])

            #  Embed
            embed = discord.Embed(
                title=" ",
                description="",
                color=discord.Color.orange(),
            )

            if blocked_formats:
                executable_formats = []
                archive_formats = []
                script_formats = []
                other_formats = []

                for fmt in blocked_formats:
                    if fmt.lower() in ["exe", "msi", "bat", "cmd", "com", "scr", "pif"]:
                        executable_formats.append(fmt)
                    elif fmt.lower() in ["zip", "rar", "7z", "tar", "gz", "bz2"]:
                        archive_formats.append(fmt)
                    elif fmt.lower() in ["js", "vbs", "ps1", "sh", "py", "pl"]:
                        script_formats.append(fmt)
                    else:
                        other_formats.append(fmt)

                if executable_formats:
                    embed.add_field(
                        name=" ",
                        value=f"`{', '.join(executable_formats)}`",
                        inline=False,
                    )

                if archive_formats:
                    embed.add_field(
                        name=" ",
                        value=f"`{', '.join(archive_formats)}`",
                        inline=False,
                    )

                if script_formats:
                    embed.add_field(
                        name=" ",
                        value=f"`{', '.join(script_formats)}`",
                        inline=False,
                    )

                if other_formats:
                    embed.add_field(
                        name=" ",
                        value=f"`{', '.join(other_formats)}`",
                        inline=False,
                    )

                embed.add_field(
                    name=" ",
                    value=f" {len(blocked_formats)} ",
                    inline=True,
                )
            else:
                embed.add_field(
                    name=" ", value="", inline=False
                )

            default_formats = [
                "exe",
                "msi",
                "bat",
                "cmd",
                "com",
                "scr",
                "pif",
                "zip",
                "rar",
                "7z",
                "tar",
                "gz",
                "js",
                "vbs",
                "ps1",
                "sh",
            ]

            embed.add_field(
                name="",
                value=f"`{', '.join(default_formats)}`",
                inline=False,
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
                text=",",
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
