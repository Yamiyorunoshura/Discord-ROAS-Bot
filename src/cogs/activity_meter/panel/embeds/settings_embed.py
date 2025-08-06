"""
活躍度系統設定面板嵌入生成器
- 生成設定面板的嵌入
- 支援PRD v1.71的新設定選項
"""

import logging

import discord

from ...main.embed_optimizer import optimize_embed, validate_embed

logger = logging.getLogger("activity_meter")


async def create_settings_embed(
    guild: discord.Guild | None,
    channel_id: int | None,
    progress_style: str = "classic",
    announcement_time: int = 21,
) -> discord.Embed:
    """
    創建活躍度系統設定面板嵌入

    Args:
        guild: Discord 伺服器
        channel_id: 目前設定的頻道 ID
        progress_style: 進度條風格
        announcement_time: 公告時間(小時)

    Returns:
        discord.Embed: 設定面板嵌入
    """
    embed = discord.Embed(
        title="活躍度系統設定",
        description="您可以在此設定活躍度系統的各項參數",
        color=discord.Color.blue(),
    )

    # 顯示伺服器資訊
    if guild:
        embed.set_author(
            name=guild.name, icon_url=guild.icon.url if guild.icon else None
        )

    # 顯示進度條風格設定
    style_names = {
        "classic": "經典",
        "modern": "現代",
        "neon": "霓虹",
        "minimal": "極簡",
        "gradient": "漸層",
    }
    current_style = style_names.get(progress_style, "經典")

    embed.add_field(
        name="🎨 進度條風格",
        value=f"**{current_style}** ({progress_style})",
        inline=True,
    )

    # 顯示公告頻道設定
    embed.add_field(
        name="📢 公告頻道",
        value=f"<#{channel_id}>" if channel_id else "尚未設定",
        inline=True,
    )

    # 顯示公告時間設定
    embed.add_field(
        name="⏰ 公告時間", value=f"**{announcement_time:02d}:00**", inline=True
    )

    # 設定說明
    embed.add_field(
        name="⚙️ 如何設定",
        value=(
            "• 使用上方下拉選單選擇進度條風格\n"
            "• 選擇公告頻道和公告時間\n"
            "• 點擊「套用設定」保存變更\n"
            "• 使用「預覽效果」查看風格效果"
        ),
        inline=False,
    )

    # 功能說明
    embed.add_field(
        name="⚙️ 系統功能",
        value=(
            "• 自動計算用戶活躍度分數\n"
            "• 每日排行榜自動播報\n"
            "• 支援多種進度條風格\n"
            "• 可自定義播報時間"
        ),
        inline=False,
    )

    embed.set_footer(text="活躍度系統 • 設定面板 v1.71")

    # 驗證和優化 embed
    validation_result = validate_embed(embed)
    if not validation_result["is_valid"]:
        logger.warning(f"Settings embed 驗證失敗: {validation_result['issues']}")
        embed = optimize_embed(embed)
        logger.info(f"Settings embed 已優化, 字符數: {validation_result['char_count']}")

    return embed
