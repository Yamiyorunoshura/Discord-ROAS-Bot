"""
預覽嵌入訊息模組
- 生成訊息預覽的嵌入訊息
"""

import datetime
import json
from typing import Any

import discord

from ...config.config import MAX_ATTACHMENTS_DISPLAY


def _add_message_fields(embed: discord.Embed, message_data: dict[str, Any]) -> None:
    """添加基本訊息字段"""
    message_id = message_data.get("message_id")
    if message_id:
        embed.add_field(name="訊息 ID", value=f"`{message_id}`", inline=True)

    timestamp = message_data.get("timestamp")
    if timestamp:
        formatted_time = datetime.datetime.fromtimestamp(timestamp).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        embed.add_field(name="發送時間", value=formatted_time, inline=True)


def _parse_attachments(attachments: Any) -> list[dict]:
    """解析附件數據"""
    if not attachments:
        return []

    if isinstance(attachments, str):
        try:
            return json.loads(attachments)
        except Exception:
            return []

    return attachments if isinstance(attachments, list) else []


def _add_attachment_fields(embed: discord.Embed, message_data: dict[str, Any]) -> None:
    """添加附件字段"""
    attachments = _parse_attachments(message_data.get("attachments"))
    if not attachments:
        return

    # 添加圖片預覽
    first_attachment = attachments[0]
    if isinstance(first_attachment, dict):
        url = first_attachment.get("url")
        content_type = first_attachment.get("content_type")

        if url and content_type and content_type.startswith("image/"):
            embed.set_image(url=url)

    # 添加附件列表
    attachment_info = []
    for i, attachment in enumerate(attachments[:MAX_ATTACHMENTS_DISPLAY]):
        if isinstance(attachment, dict):
            name = attachment.get("filename", "未知檔案")
            size = attachment.get("size", 0)
            size_str = f"{size / 1024:.1f} KB" if size else "未知大小"
            attachment_info.append(f"{i + 1}. {name} ({size_str})")

    if len(attachments) > MAX_ATTACHMENTS_DISPLAY:
        attachment_info.append(
            f"...以及 {len(attachments) - MAX_ATTACHMENTS_DISPLAY} 個附件"
        )

    if attachment_info:
        embed.add_field(
            name=f"附件 ({len(attachments)})",
            value="\n".join(attachment_info),
            inline=False,
        )


def _add_channel_field(
    embed: discord.Embed, channel: Any, channel_id: int | None
) -> None:
    """添加頻道字段"""
    if channel:
        if isinstance(channel, discord.TextChannel):
            channel_value = f"{channel.mention} (`{channel.name}`)"
        else:
            channel_name = getattr(channel, "name", "未知頻道")
            channel_value = f"`{channel_name}`"
    else:
        channel_value = f"未知頻道 ({channel_id})"

    embed.add_field(name="頻道", value=channel_value, inline=True)


async def preview_embed(
    message_data: dict[str, Any], bot: discord.Client
) -> discord.Embed:
    """
    生成訊息預覽的嵌入訊息

    Args:
        message_data: 訊息資料
        bot: Discord 機器人實例

    Returns:
        discord.Embed: 預覽嵌入訊息
    """
    # 獲取基本資訊
    message_id = message_data.get("message_id") or message_data.get("id")
    channel_id = message_data.get("channel_id")
    author_id = message_data.get("author_id")
    content = message_data.get("content", "")
    deleted = message_data.get("deleted", False)

    # 獲取用戶和頻道
    user = bot.get_user(author_id) if author_id else None
    channel = bot.get_channel(channel_id) if channel_id else None

    # 創建嵌入訊息
    embed = discord.Embed(
        title=f"{'🗑️ 已刪除的訊息' if deleted else '📝 訊息預覽'}",
        description=content or "[無內容]",
        color=discord.Color.red() if deleted else discord.Color.blue(),
        timestamp=discord.utils.utcnow(),
    )

    # 添加作者資訊
    if user:
        embed.set_author(name=user.display_name, icon_url=user.display_avatar.url)
    else:
        embed.set_author(name=f"用戶 {author_id}")

    # 添加各種字段
    _add_channel_field(embed, channel, channel_id)
    _add_message_fields(embed, message_data)
    _add_attachment_fields(embed, message_data)

    # 底部提示
    embed.set_footer(text=f"訊息 ID: {message_id}")

    return embed
