"""Main panel embed creation utilities.

政府面板主要 Embed 創建功能,提供統一的視覺設計和資訊展示.
"""

from __future__ import annotations

from typing import Any

import discord


def create_main_panel_embed(
    departments: list[dict[str, Any]],
    hierarchy: list[dict[str, Any]],
    stats: dict[str, Any],
    current_page: int = 0,
    total_pages: int = 1,
    search_query: str = "",
    filter_type: str = "all",
) -> discord.Embed:
    """創建政府面板主要 Embed.

    Args:
        departments: 部門列表資料
        hierarchy: 部門階層結構
        stats: 統計資料
        current_page: 當前頁數
        total_pages: 總頁數
        search_query: 搜尋查詢
        filter_type: 篩選類型

    Returns:
        政府面板主要 Embed
    """
    # 基礎 Embed 設置
    embed = discord.Embed(
        title="🏛️ 政府系統面板",
        color=discord.Color.blue(),
        timestamp=discord.utils.utcnow(),
    )

    description_parts = []

    if search_query:
        description_parts.append(f"🔍 搜尋: `{search_query}`")

    if filter_type != "all":
        filter_names = {
            "active": "啟用",
            "inactive": "停用",
            "departments": "部門",
            "members": "成員",
        }
        description_parts.append(
            f"📋 篩選: {filter_names.get(filter_type, filter_type)}"
        )

    if description_parts:
        embed.description = " | ".join(description_parts)

    # 統計資訊區域
    if stats:
        embed.add_field(
            name="📊 統計概覽",
            value=(
                f"**部門總數:** {stats.get('total_departments', 0)} 個\n"
                f"**啟用部門:** {stats.get('active_departments', 0)} 個\n"
                f"**關聯角色:** {stats.get('departments_with_roles', 0)} 個\n"
                f"**總成員數:** {stats.get('total_members', 0)} 人"
            ),
            inline=True,
        )

    # 階層結構簡要展示
    if hierarchy:
        hierarchy_text = _format_hierarchy_preview(hierarchy)
        embed.add_field(name="🗂️ 部門結構", value=hierarchy_text, inline=True)

    # 當前頁面部門列表
    if departments:
        departments_text = _format_departments_list(departments)
        embed.add_field(
            name=f"📋 部門列表 (第 {current_page + 1}/{total_pages} 頁)",
            value=departments_text,
            inline=False,
        )
    else:
        embed.add_field(name="📋 部門列表", value="無符合條件的部門資料", inline=False)

    # 分頁資訊
    if total_pages > 1:
        embed.set_footer(
            text=f"第 {current_page + 1} 頁,共 {total_pages} 頁 | "
            f"顯示 {len(departments)} 個部門"
        )
    else:
        embed.set_footer(text=f"顯示 {len(departments)} 個部門")

    return embed


def _format_hierarchy_preview(hierarchy: list[dict[str, Any]]) -> str:
    """格式化部門階層預覽.

    Args:
        hierarchy: 部門階層資料

    Returns:
        格式化的階層文字
    """
    if not hierarchy:
        return "無部門結構"

    lines = []
    MAX_DISPLAY_LINES = 5
    MAX_HIERARCHY_LEVELS = 2
    MAX_CHILDREN_DISPLAY = 3

    def format_dept(dept: dict[str, Any], level: int = 0, count: int = 0) -> int:
        if count >= MAX_DISPLAY_LINES:
            return count

        indent = "　" * level
        icon = "📁" if dept.get("children") else "📄"
        name = dept.get("name", "未知部門")
        member_count = dept.get("member_count", 0)

        lines.append(f"{indent}{icon} **{name}** ({member_count})")
        count += 1

        # 遞迴處理子部門
        if (
            level < MAX_HIERARCHY_LEVELS
            and dept.get("children")
            and count < MAX_DISPLAY_LINES
        ):
            for child in dept["children"][:MAX_CHILDREN_DISPLAY]:
                count = format_dept(child, level + 1, count)
                if count >= MAX_DISPLAY_LINES:
                    break

        return count

    total_count = 0
    MAX_ROOT_DEPARTMENTS = 3
    for dept in hierarchy[:MAX_ROOT_DEPARTMENTS]:
        total_count = format_dept(dept, 0, total_count)
        if total_count >= MAX_DISPLAY_LINES:
            break

    if len(hierarchy) > MAX_ROOT_DEPARTMENTS or total_count >= MAX_DISPLAY_LINES:
        lines.append("...")

    return "\n".join(lines) if lines else "無部門資料"


def _format_departments_list(departments: list[dict[str, Any]]) -> str:
    """格式化部門列表.

    Args:
        departments: 部門列表資料

    Returns:
        格式化的部門列表文字
    """
    if not departments:
        return "無部門資料"

    lines = []

    for dept in departments:
        name = dept.get("name", "未知部門")
        description = dept.get("description", "無描述")
        is_active = dept.get("is_active", False)
        member_count = dept.get("member_count", 0)
        role_id = dept.get("role_id")

        # 狀態圖示
        status_icon = "🟢" if is_active else "🔴"

        # 角色提及
        role_mention = f"<@&{role_id}>" if role_id else "無關聯角色"

        # 截斷過長的描述
        MAX_DESCRIPTION_LENGTH = 30
        TRUNCATE_LENGTH = 27
        if len(description) > MAX_DESCRIPTION_LENGTH:
            description = description[:TRUNCATE_LENGTH] + "..."

        line = (
            f"{status_icon} **{name}** ({member_count} 人)\n"
            f"　　{role_mention} | {description}"
        )

        lines.append(line)

    # 檢查總長度,避免超過 Discord 限制
    text = "\n\n".join(lines)

    MAX_TEXT_LENGTH = 1000
    SAFE_MARGIN_LENGTH = 950
    LINE_SEPARATOR_LENGTH = 2

    if len(text) > MAX_TEXT_LENGTH:
        # 截斷並添加省略號
        truncated_lines = []
        current_length = 0

        for line in lines:
            if current_length + len(line) + LINE_SEPARATOR_LENGTH > SAFE_MARGIN_LENGTH:
                truncated_lines.append("...")
                break
            truncated_lines.append(line)
            current_length += len(line) + LINE_SEPARATOR_LENGTH

        text = "\n\n".join(truncated_lines)

    return text
