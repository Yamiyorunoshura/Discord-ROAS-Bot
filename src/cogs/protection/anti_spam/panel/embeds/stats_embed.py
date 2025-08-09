"""

- 
- 
- 
"""

import datetime as dt
from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from ...main.main import AntiSpam


async def create_stats_embed(cog: "AntiSpam", guild: discord.Guild) -> discord.Embed:
    """
    

    Args:
        cog: AntiSpam 
        guild: Discord 

    Returns:
        discord.Embed: 
    """
    embed = discord.Embed(
        title=" ",
        description=f":{guild.name}",
        color=discord.Color.green(),
    )

    stats = await cog.get_stats(guild.id)

    violation_stats = {
        "violation_": " ",
        "violation_": " ",
        "violation_": " ",
        "violation_": " ",
    }

    violation_text = []
    total_violations = 0

    for key, name in violation_stats.items():
        count = stats.get(key, 0)
        total_violations += count
        if count > 0:
            violation_text.append(f"{name}: {count} ")

    if violation_text:
        embed.add_field(
            name=" ",
            value="\n".join(violation_text) + f"\n\n****: {total_violations} ",
            inline=True,
        )
    else:
        embed.add_field(name=" ", value="", inline=True)

    timeouts = stats.get("timeouts", 0)
    embed.add_field(name=" ", value=f": {timeouts} ", inline=True)

    if total_violations > 0:
        success_rate = (
            (timeouts / total_violations) * 100 if total_violations > 0 else 0
        )
        embed.add_field(
            name=" ", value=f": {success_rate:.1f}%", inline=True
        )

    recent_logs = await cog.get_action_logs(guild.id, 5)
    if recent_logs:
        log_text = []
        for log in recent_logs[:3]:  # 3
            timestamp = dt.datetime.fromisoformat(log["timestamp"])
            time_str = timestamp.strftime("%m/%d %H:%M")
            action_desc = _format_action_description(log["action"], log["details"])
            log_text.append(f"`{time_str}` {action_desc}")

        embed.add_field(name=" ", value="\n".join(log_text), inline=False)
    else:
        embed.add_field(name=" ", value="", inline=False)

    enabled = await cog.get_cfg(guild.id, "enabled", "true")
    status_emoji = "🟢" if enabled and enabled.lower() == "true" else ""

    embed.add_field(
        name=" ",
        value=f"{status_emoji} :{'' if enabled and enabled.lower() == 'true' else ''}",
        inline=False,
    )

    embed.set_footer(
        text=f":{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    return embed


def _format_action_description(action: str, details: str) -> str:
    """"""
    action_formats = {
        "violation": f" :{details}",
        "reset_settings": " ",
        "config_change": f" :{details}",
    }
    return action_formats.get(action, f" {action}: {details}")
