"""
統計嵌入訊息模組
- 生成訊息統計的嵌入訊息
"""

import discord
from typing import Dict, Any, List, Optional

async def stats_embed(cog, guild_id: int | None = None) -> discord.Embed:
    """
    生成訊息統計的嵌入訊息
    
    Args:
        cog: MessageListenerCog 實例
        guild_id: 伺服器 ID（可選）
        
    Returns:
        discord.Embed: 統計嵌入訊息
    """
    # 創建嵌入訊息
    embed = discord.Embed(
        title="📊 訊息統計",
        description="訊息監聽系統統計資訊",
        color=discord.Color.blue(),
        timestamp=discord.utils.utcnow()
    )
    
    try:
        # 獲取基本統計資訊
        if guild_id:
            # 特定伺服器的統計資訊
            total_messages = await cog.db.select(
                "SELECT COUNT(*) as count FROM messages WHERE guild_id = ?",
                (guild_id,)
            )
            total_count = total_messages[0]["count"] if total_messages and len(total_messages) > 0 else 0
            
            deleted_messages = await cog.db.select(
                "SELECT COUNT(*) as count FROM messages WHERE guild_id = ? AND deleted = 1",
                (guild_id,)
            )
            deleted_count = deleted_messages[0]["count"] if deleted_messages and len(deleted_messages) > 0 else 0
            
            # 獲取伺服器名稱
            guild = cog.bot.get_guild(guild_id)
            guild_name = guild.name if guild else f"伺服器 {guild_id}"
            
            embed.title = f"📊 {guild_name} 訊息統計"
        else:
            # 全域統計資訊
            total_messages = await cog.db.select("SELECT COUNT(*) as count FROM messages")
            total_count = total_messages[0]["count"] if total_messages and len(total_messages) > 0 else 0
            
            deleted_messages = await cog.db.select("SELECT COUNT(*) as count FROM messages WHERE deleted = 1")
            deleted_count = deleted_messages[0]["count"] if deleted_messages and len(deleted_messages) > 0 else 0
            
            # 獲取伺服器數量
            guilds_count = await cog.db.select("SELECT COUNT(DISTINCT guild_id) as count FROM messages")
            guilds_num = guilds_count[0]["count"] if guilds_count and len(guilds_count) > 0 else 0
            
            embed.add_field(
                name="📈 伺服器數量",
                value=f"{guilds_num}",
                inline=True
            )
        
        # 添加基本統計資訊
        embed.add_field(
            name="📝 總訊息數",
            value=f"{total_count:,}",
            inline=True
        )
        
        embed.add_field(
            name="🗑️ 已刪除訊息",
            value=f"{deleted_count:,} ({deleted_count / total_count * 100:.1f}% 的訊息)" if total_count > 0 else "0",
            inline=True
        )
        
        # 獲取頻道統計
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
                (guild_id,)
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
        
        # 添加頻道統計
        if channels_stats and len(channels_stats) > 0:
            channels_text = []
            for i, row in enumerate(channels_stats):
                channel_id = row["channel_id"]
                count = row["count"]
                
                channel = cog.bot.get_channel(channel_id)
                if channel and isinstance(channel, discord.TextChannel):
                    channel_name = f"#{channel.name}"
                else:
                    channel_name = f"頻道 {channel_id}"
                
                channels_text.append(f"{i+1}. {channel_name}: {count:,} 條")
            
            embed.add_field(
                name="🔝 最活躍頻道",
                value="\n".join(channels_text) if channels_text else "無資料",
                inline=False
            )
        
        # 獲取用戶統計
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
                (guild_id,)
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
        
        # 添加用戶統計
        if users_stats and len(users_stats) > 0:
            users_text = []
            for i, row in enumerate(users_stats):
                author_id = row["author_id"]
                count = row["count"]
                
                user = cog.bot.get_user(author_id)
                if user:
                    user_name = user.display_name
                else:
                    user_name = f"用戶 {author_id}"
                
                users_text.append(f"{i+1}. {user_name}: {count:,} 條")
            
            embed.add_field(
                name="👑 最活躍用戶",
                value="\n".join(users_text) if users_text else "無資料",
                inline=False
            )
        
        # 獲取保留設定
        retention_days = int(await cog.get_setting("retention_days", "30"))
        embed.set_footer(text=f"訊息保留 {retention_days} 天 • 統計時間: {discord.utils.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
    
    except Exception as exc:
        # 處理錯誤
        embed.description = f"❌ 獲取統計資訊時發生錯誤: {exc}"
    
    return embed 