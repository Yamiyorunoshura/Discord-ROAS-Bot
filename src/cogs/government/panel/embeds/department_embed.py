"""Department embed creation utilities.

部門詳細資訊 Embed 創建功能.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import discord


def create_department_embed(
    department: dict[str, Any],
    guild: discord.Guild | None = None,
    show_details: bool = True
) -> discord.Embed:
    """創建部門詳細資訊 Embed.

    Args:
        department: 部門資料
        guild: Discord 伺服器(用於角色資訊)
        show_details: 是否顯示詳細資訊

    Returns:
        部門詳細資訊 Embed
    """
    name = department.get("name", "未知部門")
    description = department.get("description", "無描述")
    is_active = department.get("is_active", False)

    # 基礎 Embed 設置
    embed = discord.Embed(
        title=f"🏛️ {name}",
        description=description,
        color=discord.Color.green() if is_active else discord.Color.red(),
        timestamp=discord.utils.utcnow()
    )

    # 基本資訊
    MAX_ID_LENGTH = 8
    dept_id = department.get("id", "未知")
    if len(dept_id) > MAX_ID_LENGTH:
        dept_id = dept_id[:MAX_ID_LENGTH] + "..."

    embed.add_field(
        name="基本資訊",
        value=(
            f"**ID:** `{dept_id}`\n"
            f"**狀態:** {'🟢 啟用' if is_active else '🔴 停用'}\n"
            f"**成員數:** {department.get('member_count', 0)} 人"
        ),
        inline=True
    )

    # Discord 角色資訊
    role_id = department.get("role_id")
    if role_id and guild:
        role = guild.get_role(role_id)
        if role:
            embed.add_field(
                name="Discord 角色",
                value=(
                    f"**角色:** {role.mention}\n"
                    f"**顏色:** {role.color!s}\n"
                    f"**成員:** {len(role.members)} 人"
                ),
                inline=True
            )
        else:
            embed.add_field(
                name="Discord 角色",
                value="⚠️ 角色不存在或已刪除",
                inline=True
            )
    else:
        embed.add_field(
            name="Discord 角色",
            value="無關聯角色",
            inline=True
        )

    # 詳細資訊
    if show_details:
        # 階層資訊
        parent_id = department.get("parent_id")
        if parent_id:
            embed.add_field(
                name="上級部門",
                value=f"ID: `{parent_id[:8]}...`",
                inline=True
            )

        # 時間資訊
        created_at = department.get("created_at")
        if created_at:
            try:
                dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                embed.add_field(
                    name="創建時間",
                    value=f"<t:{int(dt.timestamp())}:R>",
                    inline=True
                )
            except Exception:
                embed.add_field(
                    name="創建時間",
                    value="無法解析",
                    inline=True
                )

    return embed
