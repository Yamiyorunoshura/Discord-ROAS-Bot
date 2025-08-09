"""Main panel embed creation utilities.

 Embed ,.
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
    """ Embed.

    Args:
        departments: 
        hierarchy: 
        stats: 
        current_page: 
        total_pages: 
        search_query: 
        filter_type: 

    Returns:
         Embed
    """
    #  Embed
    embed = discord.Embed(
        title="",
        color=discord.Color.blue(),
        timestamp=discord.utils.utcnow(),
    )

    description_parts = []

    if search_query:
        description_parts.append(f" : `{search_query}`")

    if filter_type != "all":
        filter_names = {
            "active": "",
            "inactive": "",
            "departments": "",
            "members": "",
        }
        description_parts.append(
            f" : {filter_names.get(filter_type, filter_type)}"
        )

    if description_parts:
        embed.description = " | ".join(description_parts)

    if stats:
        embed.add_field(
            name=" ",
            value=(
                f"**:** {stats.get('total_departments', 0)} \n"
                f"**:** {stats.get('active_departments', 0)} \n"
                f"**:** {stats.get('departments_with_roles', 0)} \n"
                f"**:** {stats.get('total_members', 0)} "
            ),
            inline=True,
        )

    if hierarchy:
        hierarchy_text = _format_hierarchy_preview(hierarchy)
        embed.add_field(name=" ", value=hierarchy_text, inline=True)

    if departments:
        departments_text = _format_departments_list(departments)
        embed.add_field(
            name=f"  ( {current_page + 1}/{total_pages} )",
            value=departments_text,
            inline=False,
        )
    else:
        embed.add_field(name=" ", value="", inline=False)

    if total_pages > 1:
        embed.set_footer(
            text=f" {current_page + 1} , {total_pages}  | "
            f" {len(departments)} "
        )
    else:
        embed.set_footer(text=f" {len(departments)} ")

    return embed


def _format_hierarchy_preview(hierarchy: list[dict[str, Any]]) -> str:
    """.

    Args:
        hierarchy: 

    Returns:
        
    """
    if not hierarchy:
        return ""

    lines = []
    MAX_DISPLAY_LINES = 5
    MAX_HIERARCHY_LEVELS = 2
    MAX_CHILDREN_DISPLAY = 3

    def format_dept(dept: dict[str, Any], level: int = 0, count: int = 0) -> int:
        if count >= MAX_DISPLAY_LINES:
            return count

        indent = "" * level
        icon = "" if dept.get("children") else ""
        name = dept.get("name", "")
        member_count = dept.get("member_count", 0)

        lines.append(f"{indent}{icon} **{name}** ({member_count})")
        count += 1

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

    return "\n".join(lines) if lines else ""


def _format_departments_list(departments: list[dict[str, Any]]) -> str:
    """.

    Args:
        departments: 

    Returns:
        
    """
    if not departments:
        return ""

    lines = []

    for dept in departments:
        name = dept.get("name", "")
        description = dept.get("description", "")
        is_active = dept.get("is_active", False)
        member_count = dept.get("member_count", 0)
        role_id = dept.get("role_id")

        status_icon = "🟢" if is_active else ""

        role_mention = f"<@&{role_id}>" if role_id else ""

        MAX_DESCRIPTION_LENGTH = 30
        TRUNCATE_LENGTH = 27
        if len(description) > MAX_DESCRIPTION_LENGTH:
            description = description[:TRUNCATE_LENGTH] + "..."

        line = (
            f"{status_icon} **{name}** ({member_count} )\n"
            f"{role_mention} | {description}"
        )

        lines.append(line)

    # , Discord
    text = "\n\n".join(lines)

    MAX_TEXT_LENGTH = 1000
    SAFE_MARGIN_LENGTH = 950
    LINE_SEPARATOR_LENGTH = 2

    if len(text) > MAX_TEXT_LENGTH:
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
