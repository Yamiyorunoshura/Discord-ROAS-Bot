"""

- 
- 
- 
"""

import datetime as dt
from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from ...main.main import SyncDataCog

SECONDS_PER_HOUR = 3600
SECONDS_PER_MINUTE = 60
DAYS_THRESHOLD_FOR_OUTDATED = 7


async def create_status_embed(
    cog: "SyncDataCog", guild: discord.Guild
) -> discord.Embed:
    """
    

    Args:
        cog: SyncDataCog 
        guild: Discord 

    Returns:
        discord.Embed: 
    """
    embed = discord.Embed(
        title=" ",
        description=f":**{guild.name}**",
        color=discord.Color.blue(),
    )

    try:
        last_sync = await cog.db.get_last_sync_record(guild.id)

        if last_sync:
            sync_time = last_sync.get("start_time", last_sync.get("sync_start_time"))
            if sync_time:
                if isinstance(sync_time, str):
                    try:
                        if "T" in sync_time:
                            sync_time = dt.datetime.fromisoformat(
                                sync_time.replace("Z", "+00:00")
                            )
                        else:
                            sync_time = dt.datetime.strptime(
                                sync_time, "%Y-%m-%d %H:%M:%S"
                            )
                    except ValueError:
                        sync_time = dt.datetime.utcnow()
                elif not isinstance(sync_time, dt.datetime):
                    sync_time = dt.datetime.utcnow()
            else:
                sync_time = dt.datetime.utcnow()

            now = dt.datetime.utcnow()
            time_ago = now - sync_time

            if time_ago.days > 0:
                time_str = f"{time_ago.days} "
            elif time_ago.seconds > SECONDS_PER_HOUR:
                hours = time_ago.seconds // SECONDS_PER_HOUR
                time_str = f"{hours} "
            elif time_ago.seconds > SECONDS_PER_MINUTE:
                minutes = time_ago.seconds // SECONDS_PER_MINUTE
                time_str = f"{minutes} "
            else:
                time_str = ""

            status_icon = "" if last_sync.get("status") == "success" else ""

            embed.add_field(
                name=" ",
                value=(
                    f"{status_icon} {time_str}\n"
                    f":{_get_sync_type_name(last_sync.get('sync_type', 'unknown'))}\n"
                    f":{last_sync.get('duration', 0):.2f} "
                ),
                inline=True,
            )

            roles_count = last_sync.get("roles_processed", 0)
            channels_count = last_sync.get("channels_processed", 0)

            embed.add_field(
                name=" ",
                value=(
                    f":{roles_count} \n"
                    f":{channels_count} \n"
                    f":{_get_status_name(last_sync.get('status', 'unknown'))}"
                ),
                inline=True,
            )
        else:
            embed.add_field(name=" ", value="", inline=True)

            embed.add_field(name=" ", value="", inline=True)

        embed.add_field(
            name=" ",
            value=(
                f":{len(guild.roles)} \n"
                f":{len(guild.channels)} \n"
                f":{guild.member_count} "
            ),
            inline=True,
        )

        try:
            db_roles = await cog.db.get_guild_roles(guild.id)
            db_channels = await cog.db.get_guild_channels(guild.id)

            embed.add_field(
                name=" ",
                value=(
                    f":{len(db_roles)} \n"
                    f":{len(db_channels)} \n"
                    f":{_calculate_sync_rate(guild, db_roles, db_channels)}"
                ),
                inline=True,
            )
        except Exception:
            embed.add_field(name=" ", value="", inline=True)

        if not last_sync:
            embed.add_field(
                name="", value="", inline=False
            )
        elif last_sync.get("status") != "success":
            embed.add_field(
                name="", value=",", inline=False
            )
        elif time_ago.days > DAYS_THRESHOLD_FOR_OUTDATED:
            embed.add_field(
                name="", value=",", inline=False
            )

        embed.timestamp = dt.datetime.utcnow()
        embed.set_footer(text="")

    except Exception as e:
        embed.add_field(
            name=" ", value=f":{str(e)[:100]}", inline=False
        )

    return embed


def _get_sync_type_name(sync_type: str) -> str:
    """"""
    type_names = {"full": "", "roles": "", "channels": ""}
    return type_names.get(sync_type, "")


def _get_status_name(status: str) -> str:
    """"""
    status_names = {"success": "", "failed": "", "running": ""}
    return status_names.get(status, "")


def _calculate_sync_rate(
    guild: discord.Guild, db_roles: list, db_channels: list
) -> str:
    """"""
    try:
        role_rate = len(db_roles) / len(guild.roles) * 100 if guild.roles else 0
        channel_rate = (
            len(db_channels) / len(guild.channels) * 100 if guild.channels else 0
        )
        avg_rate = (role_rate + channel_rate) / 2
        return f"{avg_rate:.1f}%"
    except (ZeroDivisionError, TypeError, AttributeError):
        return ""
