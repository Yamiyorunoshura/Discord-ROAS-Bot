"""Department embed creation utilities.

 Embed .
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import discord


def create_department_embed(
    department: dict[str, Any],
    guild: discord.Guild | None = None,
    show_details: bool = True,
) -> discord.Embed:
    """ Embed.

    Args:
        department: 
        guild: Discord ()
        show_details: 

    Returns:
         Embed
    """
    name = department.get("name", "")
    description = department.get("description", "")
    is_active = department.get("is_active", False)

    #  Embed
    embed = discord.Embed(
        title=f"{name}",
        description=description,
        color=discord.Color.green() if is_active else discord.Color.red(),
        timestamp=discord.utils.utcnow(),
    )

    MAX_ID_LENGTH = 8
    dept_id = department.get("id", "")
    if len(dept_id) > MAX_ID_LENGTH:
        dept_id = dept_id[:MAX_ID_LENGTH] + "..."

    embed.add_field(
        name="",
        value=(
            f"**ID:** `{dept_id}`\n"
            f"**:** {'🟢 ' if is_active else ' '}\n"
            f"**:** {department.get('member_count', 0)} "
        ),
        inline=True,
    )

    # Discord
    role_id = department.get("role_id")
    if role_id and guild:
        role = guild.get_role(role_id)
        if role:
            embed.add_field(
                name="Discord ",
                value=(
                    f"**:** {role.mention}\n"
                    f"**:** {role.color!s}\n"
                    f"**:** {len(role.members)} "
                ),
                inline=True,
            )
        else:
            embed.add_field(
                name="Discord ", value=" ", inline=True
            )
    else:
        embed.add_field(name="Discord ", value="", inline=True)

    if show_details:
        parent_id = department.get("parent_id")
        if parent_id:
            embed.add_field(
                name="", value=f"ID: `{parent_id[:8]}...`", inline=True
            )

        created_at = department.get("created_at")
        if created_at:
            try:
                dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                embed.add_field(
                    name="", value=f"<t:{int(dt.timestamp())}:R>", inline=True
                )
            except Exception:
                embed.add_field(name="", value="", inline=True)

    return embed
