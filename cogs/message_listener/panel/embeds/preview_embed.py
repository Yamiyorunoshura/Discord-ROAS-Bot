"""
預覽嵌入訊息模組
- 生成訊息預覽的嵌入訊息
"""

import discord
from typing import Dict, Any, Optional

async def preview_embed(message_data: Dict[str, Any], bot: discord.Client) -> discord.Embed:
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
    timestamp = message_data.get("timestamp", 0)
    deleted = message_data.get("deleted", False)
    
    # 獲取用戶和頻道
    user = bot.get_user(author_id) if author_id else None
    channel = bot.get_channel(channel_id) if channel_id else None
    
    # 創建嵌入訊息
    embed = discord.Embed(
        title=f"{'🗑️ 已刪除的訊息' if deleted else '📝 訊息預覽'}",
        description=content or "[無內容]",
        color=discord.Color.red() if deleted else discord.Color.blue(),
        timestamp=discord.utils.utcnow()
    )
    
    # 添加作者資訊
    if user:
        embed.set_author(
            name=user.display_name,
            icon_url=user.display_avatar.url
        )
    else:
        embed.set_author(name=f"用戶 {author_id}")
    
    # 添加頻道資訊
    if channel:
        # 檢查頻道類型
        if isinstance(channel, discord.TextChannel):
            channel_value = f"{channel.mention} (`{channel.name}`)"
        else:
            # 處理其他頻道類型
            channel_name = getattr(channel, "name", "未知頻道")
            channel_value = f"`{channel_name}`"
    else:
        channel_value = f"未知頻道 ({channel_id})"
    
    embed.add_field(
        name="頻道",
        value=channel_value,
        inline=True
    )
    
    # 添加訊息 ID
    if message_id:
        embed.add_field(
            name="訊息 ID",
            value=f"`{message_id}`",
            inline=True
        )
    
    # 添加時間資訊
    import datetime
    if timestamp:
        formatted_time = datetime.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        embed.add_field(
            name="發送時間",
            value=formatted_time,
            inline=True
        )
    
    # 添加附件資訊
    attachments = message_data.get("attachments", [])
    if attachments:
        if isinstance(attachments, str):
            # 如果是 JSON 字串，嘗試解析
            import json
            try:
                attachments = json.loads(attachments)
            except:
                attachments = []
        
        if attachments:
            # 添加第一個附件的預覽
            first_attachment = attachments[0]
            if isinstance(first_attachment, dict):
                url = first_attachment.get("url")
                filename = first_attachment.get("filename")
                content_type = first_attachment.get("content_type")
                
                if url and content_type and content_type.startswith("image/"):
                    embed.set_image(url=url)
                
                # 添加附件資訊
                attachment_info = []
                for i, attachment in enumerate(attachments[:3]):
                    if isinstance(attachment, dict):
                        name = attachment.get("filename", "未知檔案")
                        size = attachment.get("size", 0)
                        size_str = f"{size / 1024:.1f} KB" if size else "未知大小"
                        attachment_info.append(f"{i+1}. {name} ({size_str})")
                
                if len(attachments) > 3:
                    attachment_info.append(f"...以及 {len(attachments) - 3} 個附件")
                
                if attachment_info:
                    embed.add_field(
                        name=f"附件 ({len(attachments)})",
                        value="\n".join(attachment_info),
                        inline=False
                    )
    
    # 底部提示
    embed.set_footer(text=f"訊息 ID: {message_id}")
    
    return embed 