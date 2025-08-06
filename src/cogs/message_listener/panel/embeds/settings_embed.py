"""
設定嵌入訊息模組
- 生成設定面板的嵌入訊息
"""

import builtins
import contextlib

import discord

from ...config.config import MAX_CHANNELS_DISPLAY


async def settings_embed(cog) -> discord.Embed:
    """
    生成設定面板的嵌入訊息

    Args:
        cog: MessageListenerCog 實例

    Returns:
        discord.Embed: 設定嵌入訊息
    """
    # 獲取設定
    log_channel_id = await cog.get_setting("log_channel_id")
    log_edits = await cog.get_setting("log_edits", "false")
    log_deletes = await cog.get_setting("log_deletes", "false")
    batch_size = await cog.get_setting("batch_size", "10")
    batch_time = await cog.get_setting("batch_time", "600")

    # 創建嵌入訊息
    embed = discord.Embed(
        title="📝 訊息日誌設定",
        description="使用下方按鈕和選單來設定訊息日誌系統.",
        color=discord.Color.blue(),
    )

    # 日誌頻道
    log_channel = None
    if log_channel_id:
        with contextlib.suppress(builtins.BaseException):
            log_channel = cog.bot.get_channel(int(log_channel_id))

    embed.add_field(
        name="📺 日誌頻道",
        value=f"{log_channel.mention if log_channel else '未設定'}",
        inline=True,
    )

    # 監聽頻道
    monitored_channels = await cog.db.get_monitored_channels()
    monitored_count = len(monitored_channels)

    if monitored_count > 0:
        channels_text = []
        for _i, channel_id in enumerate(monitored_channels[:5]):
            channel = cog.bot.get_channel(channel_id)
            if channel:
                channels_text.append(channel.mention)
            else:
                channels_text.append(f"未知頻道 ({channel_id})")

        if monitored_count > MAX_CHANNELS_DISPLAY:
            channels_text.append(
                f"...以及 {monitored_count - MAX_CHANNELS_DISPLAY} 個頻道"
            )

        monitored_value = "\n".join(channels_text)
    else:
        monitored_value = "未監聽任何頻道"

    embed.add_field(
        name=f"👁️ 監聽頻道 ({monitored_count})", value=monitored_value, inline=True
    )

    # 批次處理設定
    embed.add_field(
        name="⚙️ 批次處理設定",
        value=(
            f"• 批次大小: {batch_size} 條訊息\n• 批次時間: {int(batch_time) // 60} 分鐘"
        ),
        inline=False,
    )

    # 記錄設定
    embed.add_field(
        name="📊 記錄設定",
        value=(
            f"• 編輯記錄: {'✅ 啟用' if log_edits == 'true' else '❌ 停用'}\n"
            f"• 刪除記錄: {'✅ 啟用' if log_deletes == 'true' else '❌ 停用'}"
        ),
        inline=False,
    )

    # 底部提示
    embed.set_footer(text="點擊下方按鈕進行設定 • 設定將立即生效")

    return embed
