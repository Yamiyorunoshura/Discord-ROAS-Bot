"""
反垃圾訊息統計面板嵌入生成器
- 生成統計資料視圖
- 顯示檢測和處理統計
- 提供操作日誌摘要
"""

import datetime as dt
from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from ...main.main import AntiSpam


async def create_stats_embed(cog: "AntiSpam", guild: discord.Guild) -> discord.Embed:
    """
    創建統計資料嵌入

    Args:
        cog: AntiSpam 模組實例
        guild: Discord 伺服器物件

    Returns:
        discord.Embed: 統計嵌入
    """
    embed = discord.Embed(
        title="📊 反垃圾訊息統計資料",
        description=f"伺服器:{guild.name}",
        color=discord.Color.green(),
    )

    # 取得統計資料
    stats = await cog.get_stats(guild.id)

    # 違規統計
    violation_stats = {
        "violation_頻率限制": "⚡ 頻率限制",
        "violation_重複訊息": "🔄 重複訊息",
        "violation_相似訊息": "🔍 相似訊息",
        "violation_貼圖濫用": "😀 貼圖濫用",
    }

    violation_text = []
    total_violations = 0

    for key, name in violation_stats.items():
        count = stats.get(key, 0)
        total_violations += count
        if count > 0:
            violation_text.append(f"{name}: {count} 次")

    if violation_text:
        embed.add_field(
            name="🚫 違規檢測統計",
            value="\n".join(violation_text) + f"\n\n**總計**: {total_violations} 次",
            inline=True,
        )
    else:
        embed.add_field(name="🚫 違規檢測統計", value="暫無違規記錄", inline=True)

    # 處理統計
    timeouts = stats.get("timeouts", 0)
    embed.add_field(name="⚔️ 處理統計", value=f"禁言處理: {timeouts} 次", inline=True)

    # 效率統計
    if total_violations > 0:
        success_rate = (
            (timeouts / total_violations) * 100 if total_violations > 0 else 0
        )
        embed.add_field(
            name="📈 處理效率", value=f"處理成功率: {success_rate:.1f}%", inline=True
        )

    # 最近活動
    recent_logs = await cog.get_action_logs(guild.id, 5)
    if recent_logs:
        log_text = []
        for log in recent_logs[:3]:  # 只顯示最近3條
            timestamp = dt.datetime.fromisoformat(log["timestamp"])
            time_str = timestamp.strftime("%m/%d %H:%M")
            action_desc = _format_action_description(log["action"], log["details"])
            log_text.append(f"`{time_str}` {action_desc}")

        embed.add_field(name="📝 最近活動", value="\n".join(log_text), inline=False)
    else:
        embed.add_field(name="📝 最近活動", value="暫無活動記錄", inline=False)

    # 系統狀態
    enabled = await cog.get_cfg(guild.id, "enabled", "true")
    status_emoji = "🟢" if enabled and enabled.lower() == "true" else "🔴"

    embed.add_field(
        name="🔧 系統狀態",
        value=f"{status_emoji} 模組狀態:{'運行中' if enabled and enabled.lower() == 'true' else '已停用'}",
        inline=False,
    )

    embed.set_footer(
        text=f"統計更新時間:{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    return embed


def _format_action_description(action: str, details: str) -> str:
    """格式化操作描述"""
    if action == "violation":
        return f"🚫 檢測到違規:{details}"
    elif action == "reset_settings":
        return "🔄 重置了系統設定"
    elif action == "config_change":
        return f"⚙️ 修改了設定:{details}"
    else:
        return f"📋 {action}: {details}"
