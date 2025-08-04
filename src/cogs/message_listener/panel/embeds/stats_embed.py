"""
統計嵌入訊息模組
- 生成訊息統計的嵌入訊息
"""

from typing import Any

import discord


async def _get_message_stats(cog, guild_id: int | None) -> dict[str, Any]:
    """獲取訊息統計數據"""
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
    """獲取頻道統計數據"""
    db = cog.db

    if guild_id:
        return await db.get_top_channels(guild_id=guild_id, limit=10)
    else:
        return await db.get_top_channels(limit=10)


def _add_stats_fields(embed: discord.Embed, stats: dict[str, Any]) -> None:
    """添加統計字段"""
    embed.add_field(name="📊 總訊息數", value=f"{stats['total']:,}", inline=True)
    embed.add_field(name="📅 今日", value=f"{stats['daily']:,}", inline=True)
    embed.add_field(name="📅 本週", value=f"{stats['weekly']:,}", inline=True)
    embed.add_field(name="📅 本月", value=f"{stats['monthly']:,}", inline=True)


def _add_channel_fields(embed: discord.Embed, channels: list[tuple[int, int]], bot: Any) -> None:
    """添加頻道統計字段"""
    if not channels:
        embed.add_field(name="📈 熱門頻道", value="暫無數據", inline=False)
        return

    channel_text = []
    for i, (channel_id, count) in enumerate(channels):
        channel = bot.get_channel(channel_id)
        if channel:
            channel_text.append(f"{i + 1}. {channel.mention}: {count:,} 條")
        else:
            channel_text.append(f"{i + 1}. 未知頻道 ({channel_id}): {count:,} 條")

    embed.add_field(
        name="📈 熱門頻道 (前10名)",
        value="\n".join(channel_text),
        inline=False,
    )


async def _get_message_counts(cog, guild_id: int | None = None) -> tuple[int, int]:
    """獲取訊息總數和已刪除數量"""
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
    """獲取伺服器數量"""
    guilds_count = await cog.db.select(
        "SELECT COUNT(DISTINCT guild_id) as count FROM messages"
    )
    return guilds_count[0]["count"] if guilds_count else 0


async def _add_channel_stats(cog, embed: discord.Embed, guild_id: int | None = None) -> None:
    """添加頻道統計資訊"""
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
                channel_name = f"頻道 {channel_id}"

            channels_text.append(f"{i + 1}. {channel_name}: {count:,} 條")

        embed.add_field(
            name="🔝 最活躍頻道",
            value="\n".join(channels_text) if channels_text else "無資料",
            inline=False,
        )


async def _add_user_stats(cog, embed: discord.Embed, guild_id: int | None = None) -> None:
    """添加用戶統計資訊"""
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
            user_name = user.display_name if user else f"用戶 {author_id}"

            users_text.append(f"{i + 1}. {user_name}: {count:,} 條")

        embed.add_field(
            name="👑 最活躍用戶",
            value="\n".join(users_text) if users_text else "無資料",
            inline=False,
        )


async def stats_embed(cog, guild_id: int | None = None) -> discord.Embed:
    """
    生成訊息統計的嵌入訊息

    Args:
        cog: MessageListenerCog 實例
        guild_id: 伺服器 ID(可選)

    Returns:
        discord.Embed: 統計嵌入訊息
    """
    # 創建嵌入訊息
    embed = discord.Embed(
        title="📊 訊息統計",
        description="訊息監聽系統統計資訊",
        color=discord.Color.blue(),
        timestamp=discord.utils.utcnow(),
    )

    try:
        # 獲取基本統計資訊
        total_count, deleted_count = await _get_message_counts(cog, guild_id)

        if guild_id:
            # 獲取伺服器名稱
            guild = cog.bot.get_guild(guild_id)
            guild_name = guild.name if guild else f"伺服器 {guild_id}"
            embed.title = f"📊 {guild_name} 訊息統計"
        else:
            # 添加伺服器數量統計
            guilds_num = await _get_guild_count(cog)
            embed.add_field(name="📈 伺服器數量", value=f"{guilds_num}", inline=True)

        # 添加基本統計資訊
        embed.add_field(name="📝 總訊息數", value=f"{total_count:,}", inline=True)

        embed.add_field(
            name="🗑️ 已刪除訊息",
            value=f"{deleted_count:,} ({deleted_count / total_count * 100:.1f}% 的訊息)"
            if total_count > 0
            else "0",
            inline=True,
        )

        # 添加頻道和用戶統計
        await _add_channel_stats(cog, embed, guild_id)
        await _add_user_stats(cog, embed, guild_id)

        # 獲取保留設定
        retention_days = int(await cog.get_setting("retention_days", "30"))
        embed.set_footer(
            text=f"訊息保留 {retention_days} 天 • 統計時間: {discord.utils.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
        )

    except Exception as exc:
        # 處理錯誤
        embed.description = f"❌ 獲取統計資訊時發生錯誤: {exc}"

    return embed
