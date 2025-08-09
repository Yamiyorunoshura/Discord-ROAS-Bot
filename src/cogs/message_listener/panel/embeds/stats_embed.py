"""

- 
"""

from typing import Any

import discord


async def _get_message_stats(cog, guild_id: int | None) -> dict[str, Any]:
    """"""
    db = cog.db
    stats = {"total": 0, "daily": 0, "weekly": 0, "monthly": 0}

    if guild_id:
        stats["total"] = await db.get_message_count(guild_id=guild_id)
        stats["daily"] = await db.get_message_count(guild_id=guild_id, days=1)
        stats["weekly"] = await db.get_message_count(guild_id=guild_id, days=7)
        stats["monthly"] = await db.get_message_count(guild_id=guild_id, days=30)
    else:
        stats["total"] = await db.get_message_count()
        stats["daily"] = await db.get_message_count(days=1)
        stats["weekly"] = await db.get_message_count(days=7)
        stats["monthly"] = await db.get_message_count(days=30)

    return stats


async def _get_channel_stats(cog, guild_id: int | None) -> list[tuple[int, int]]:
    """"""
    db = cog.db

    if guild_id:
        return await db.get_top_channels(guild_id=guild_id, limit=10)
    else:
        return await db.get_top_channels(limit=10)


def _add_stats_fields(embed: discord.Embed, stats: dict[str, Any]) -> None:
    """"""
    embed.add_field(name=" ", value=f"{stats['total']:,}", inline=True)
    embed.add_field(name=" ", value=f"{stats['daily']:,}", inline=True)
    embed.add_field(name=" ", value=f"{stats['weekly']:,}", inline=True)
    embed.add_field(name=" ", value=f"{stats['monthly']:,}", inline=True)


def _add_channel_fields(
    embed: discord.Embed, channels: list[tuple[int, int]], bot: Any
) -> None:
    """"""
    if not channels:
        embed.add_field(name=" ", value="", inline=False)
        return

    channel_text = []
    for i, (channel_id, count) in enumerate(channels):
        channel = bot.get_channel(channel_id)
        if channel:
            channel_text.append(f"{i + 1}. {channel.mention}: {count:,} ")
        else:
            channel_text.append(f"{i + 1}.  ({channel_id}): {count:,} ")

    embed.add_field(
        name="  (10)",
        value="\n".join(channel_text),
        inline=False,
    )


async def _get_message_counts(cog, guild_id: int | None = None) -> tuple[int, int]:
    """"""
    if guild_id:
        total_messages = await cog.db.select(
            "SELECT COUNT(*) as count FROM messages WHERE guild_id = ?", (guild_id,)
        )
        deleted_messages = await cog.db.select(
            "SELECT COUNT(*) as count FROM messages WHERE guild_id = ? AND deleted = 1",
            (guild_id,),
        )
    else:
        total_messages = await cog.db.select("SELECT COUNT(*) as count FROM messages")
        deleted_messages = await cog.db.select(
            "SELECT COUNT(*) as count FROM messages WHERE deleted = 1"
        )

    total_count = total_messages[0]["count"] if total_messages else 0
    deleted_count = deleted_messages[0]["count"] if deleted_messages else 0

    return total_count, deleted_count


async def _get_guild_count(cog) -> int:
    """"""
    guilds_count = await cog.db.select(
        "SELECT COUNT(DISTINCT guild_id) as count FROM messages"
    )
    return guilds_count[0]["count"] if guilds_count else 0


async def _add_channel_stats(
    cog, embed: discord.Embed, guild_id: int | None = None
) -> None:
    """"""
    if guild_id:
        channels_stats = await cog.db.select(
            """
            SELECT channel_id, COUNT(*) as count
            FROM messages
            WHERE guild_id = ?
            GROUP BY channel_id
            ORDER BY count DESC
            LIMIT 5
            """,
            (guild_id,),
        )
    else:
        channels_stats = await cog.db.select(
            """
            SELECT channel_id, COUNT(*) as count
            FROM messages
            GROUP BY channel_id
            ORDER BY count DESC
            LIMIT 5
            """
        )

    if channels_stats:
        channels_text = []
        for i, row in enumerate(channels_stats):
            channel_id = row["channel_id"]
            count = row["count"]

            channel = cog.bot.get_channel(channel_id)
            if channel and isinstance(channel, discord.TextChannel):
                channel_name = f"#{channel.name}"
            else:
                channel_name = f" {channel_id}"

            channels_text.append(f"{i + 1}. {channel_name}: {count:,} ")

        embed.add_field(
                            name="",
            value="\n".join(channels_text) if channels_text else "",
            inline=False,
        )


async def _add_user_stats(
    cog, embed: discord.Embed, guild_id: int | None = None
) -> None:
    """"""
    if guild_id:
        users_stats = await cog.db.select(
            """
            SELECT author_id, COUNT(*) as count
            FROM messages
            WHERE guild_id = ?
            GROUP BY author_id
            ORDER BY count DESC
            LIMIT 5
            """,
            (guild_id,),
        )
    else:
        users_stats = await cog.db.select(
            """
            SELECT author_id, COUNT(*) as count
            FROM messages
            GROUP BY author_id
            ORDER BY count DESC
            LIMIT 5
            """
        )

    if users_stats:
        users_text = []
        for i, row in enumerate(users_stats):
            author_id = row["author_id"]
            count = row["count"]

            user = cog.bot.get_user(author_id)
            user_name = user.display_name if user else f" {author_id}"

            users_text.append(f"{i + 1}. {user_name}: {count:,} ")

        embed.add_field(
            name=" ",
            value="\n".join(users_text) if users_text else "",
            inline=False,
        )


async def stats_embed(cog, guild_id: int | None = None) -> discord.Embed:
    """
    

    Args:
        cog: MessageListenerCog 
        guild_id:  ID()

    Returns:
        discord.Embed: 
    """
    embed = discord.Embed(
        title=" ",
        description="",
        color=discord.Color.blue(),
        timestamp=discord.utils.utcnow(),
    )

    try:
        total_count, deleted_count = await _get_message_counts(cog, guild_id)

        if guild_id:
            guild = cog.bot.get_guild(guild_id)
            guild_name = guild.name if guild else f" {guild_id}"
            embed.title = f" {guild_name} "
        else:
            guilds_num = await _get_guild_count(cog)
            embed.add_field(name=" ", value=f"{guilds_num}", inline=True)

        embed.add_field(name=" ", value=f"{total_count:,}", inline=True)

        embed.add_field(
            name=" ",
            value=f"{deleted_count:,} ({deleted_count / total_count * 100:.1f}% )"
            if total_count > 0
            else "0",
            inline=True,
        )

        await _add_channel_stats(cog, embed, guild_id)
        await _add_user_stats(cog, embed, guild_id)

        retention_days = int(await cog.get_setting("retention_days", "30"))
        embed.set_footer(
            text=f" {retention_days}  • : {discord.utils.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
        )

    except Exception as exc:
        embed.description = f" : {exc}"

    return embed
