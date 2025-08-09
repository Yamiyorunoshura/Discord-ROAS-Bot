"""

- 
- 
- 
"""

import datetime as dt
from typing import TYPE_CHECKING, Any

import discord

if TYPE_CHECKING:
    from ...main.main import SyncDataCog


async def create_history_embed(
    cog: "SyncDataCog", guild: discord.Guild, page: int = 0
) -> discord.Embed:
    """
    

    Args:
        cog: SyncDataCog 
        guild: Discord 
        page: 

    Returns:
        discord.Embed: 
    """
    embed = discord.Embed(
        title=" ",
        description=f":**{guild.name}**",
        color=discord.Color.green(),
    )

    try:
        history_records = await _get_sync_history(cog, guild.id, page)

        if not history_records:
            embed.add_field(name=" ", value="", inline=False)
        else:
            for i, record in enumerate(history_records[:5], 1):
                status_icon = "" if record.get("status") == "success" else ""
                sync_type = _get_sync_type_name(record.get("sync_type", "unknown"))

                sync_time = record.get("sync_start_time", dt.datetime.utcnow())
                if isinstance(sync_time, str):
                    try:
                        sync_time = dt.datetime.fromisoformat(
                            sync_time.replace("Z", "+00:00")
                        )
                    except (ValueError, AttributeError):
                        sync_time = dt.datetime.utcnow()

                time_str = sync_time.strftime("%m/%d %H:%M")

                roles_count = record.get("roles_processed", 0)
                channels_count = record.get("channels_processed", 0)
                duration = record.get("duration", 0)

                value = (
                    f"{status_icon} **{sync_type}** - {time_str}\n"
                    f":{roles_count} | :{channels_count}\n"
                    f":{duration:.2f}"
                )

                if record.get("error_message"):
                    value += f"\n {record['error_message'][:50]}..."

                embed.add_field(name=f"#{i + page * 5}", value=value, inline=True)

        total_syncs = await _get_total_sync_count(cog, guild.id)
        success_syncs = await _get_success_sync_count(cog, guild.id)
        success_rate = (success_syncs / total_syncs * 100) if total_syncs > 0 else 0

        embed.add_field(
            name=" ",
            value=(
                f":{total_syncs}\n"
                f":{success_syncs}\n"
                f":{success_rate:.1f}%"
            ),
            inline=False,
        )

        total_pages = (total_syncs + 4) // 5  # 5
        if total_pages > 1:
            embed.set_footer(
                text=f" {page + 1}/{total_pages}  | "
            )
        else:
            embed.set_footer(text="")

        embed.timestamp = dt.datetime.utcnow()

    except Exception as e:
        embed.add_field(
            name=" ",
            value=f":{str(e)[:100]}",
            inline=False,
        )

    return embed


async def _get_sync_history(
    cog: "SyncDataCog", guild_id: int, page: int = 0
) -> list[dict[str, Any]]:
    """
    

    Args:
        cog: SyncDataCog 
        guild_id:  ID
        page: 

    Returns:
        List[Dict[str, Any]]: 
    """
    try:
        mock_records = [
            {
                "sync_type": "full",
                "status": "success",
                "sync_start_time": dt.datetime.utcnow() - dt.timedelta(hours=2),
                "roles_processed": 15,
                "channels_processed": 8,
                "duration": 3.45,
                "error_message": None,
            },
            {
                "sync_type": "roles",
                "status": "success",
                "sync_start_time": dt.datetime.utcnow() - dt.timedelta(days=1),
                "roles_processed": 15,
                "channels_processed": 0,
                "duration": 1.23,
                "error_message": None,
            },
            {
                "sync_type": "channels",
                "status": "failed",
                "sync_start_time": dt.datetime.utcnow() - dt.timedelta(days=2),
                "roles_processed": 0,
                "channels_processed": 0,
                "duration": 0.56,
                "error_message": "",
            },
        ]

        start_idx = page * 5
        end_idx = start_idx + 5
        return mock_records[start_idx:end_idx]

    except Exception:
        return []


async def _get_total_sync_count(cog: "SyncDataCog", guild_id: int) -> int:
    """"""
    try:
        return 3
    except Exception:
        return 0


async def _get_success_sync_count(cog: "SyncDataCog", guild_id: int) -> int:
    """"""
    try:
        return 2
    except Exception:
        return 0


def _get_sync_type_name(sync_type: str) -> str:
    """"""
    type_names = {"full": "", "roles": "", "channels": ""}
    return type_names.get(sync_type, "")
