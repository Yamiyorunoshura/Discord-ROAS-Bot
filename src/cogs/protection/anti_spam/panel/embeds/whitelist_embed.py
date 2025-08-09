"""

- 
- 
- /
"""

from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from ...main.main import AntiSpam

MAX_DISPLAY_ITEMS = 10


async def create_whitelist_embed(
    cog: "AntiSpam", guild: discord.Guild, whitelist_type: str = "user"
) -> discord.Embed:
    """
    

    Args:
        cog: AntiSpam 
        guild: Discord 
        whitelist_type:  ("user"  "role")

    Returns:
        discord.Embed: 
    """

    if whitelist_type == "user":
        return await _create_user_whitelist_embed(cog, guild)
    elif whitelist_type == "role":
        return await _create_role_whitelist_embed(cog, guild)
    else:
        return await _create_overview_embed(cog, guild)


async def _create_overview_embed(
    cog: "AntiSpam", guild: discord.Guild
) -> discord.Embed:
    """"""
    embed = discord.Embed(
        title=" ",
        description=f":{guild.name}",
        color=discord.Color.green(),
    )

    user_whitelist = await _get_user_whitelist(cog, guild.id)
    role_whitelist = await _get_role_whitelist(cog, guild.id)

    embed.add_field(
        name=" ", value=f" {len(user_whitelist)} ", inline=True
    )

    embed.add_field(
        name=" ", value=f" {len(role_whitelist)} ", inline=True
    )

    embed.add_field(
        name="i ",
        value="",
        inline=False,
    )

    embed.add_field(
        name=" ",
        value=(
            "•  **** \n"
            "•  **** \n"
            "• "
        ),
        inline=False,
    )

    embed.set_footer(text="")
    return embed


async def _create_user_whitelist_embed(
    cog: "AntiSpam", guild: discord.Guild
) -> discord.Embed:
    """"""
    embed = discord.Embed(
        title=" ",
        description="",
        color=discord.Color.blue(),
    )

    user_whitelist = await _get_user_whitelist(cog, guild.id)

    if user_whitelist:
        user_list = []
        for user_id in user_whitelist[:10]:  # 10
            try:
                user = guild.get_member(int(user_id))
                if user:
                    user_list.append(f"• {user.display_name} (`{user.id}`)")
                else:
                    user_list.append(f"•  (`{user_id}`)")
            except Exception:
                user_list.append(f"•  (`{user_id}`)")

        embed.add_field(
            name=f"  ({len(user_whitelist)} )",
            value="\n".join(user_list) if user_list else "",
            inline=False,
        )

        if len(user_whitelist) > MAX_DISPLAY_ITEMS:
            embed.add_field(
                name=" ",
                value=f" {len(user_whitelist) - MAX_DISPLAY_ITEMS} ",
                inline=False,
            )
    else:
        embed.add_field(
            name=" ", value="", inline=False
        )

    embed.add_field(
        name=" ",
        value=(
            "•  `/antispam whitelist add user @` \n"
            "•  `/antispam whitelist remove user @` \n"
            "• "
        ),
        inline=False,
    )

    embed.set_footer(text="")
    return embed


async def _create_role_whitelist_embed(
    cog: "AntiSpam", guild: discord.Guild
) -> discord.Embed:
    """"""
    embed = discord.Embed(
        title=" ",
        description="",
        color=discord.Color.purple(),
    )

    role_whitelist = await _get_role_whitelist(cog, guild.id)

    if role_whitelist:
        role_list = []
        for role_id in role_whitelist[:10]:  # 10
            try:
                role = guild.get_role(int(role_id))
                if role:
                    role_list.append(f"• {role.name} (`{role.id}`)")
                else:
                    role_list.append(f"•  (`{role_id}`)")
            except Exception:
                role_list.append(f"•  (`{role_id}`)")

        embed.add_field(
            name=f"  ({len(role_whitelist)} )",
            value="\n".join(role_list) if role_list else "",
            inline=False,
        )

        if len(role_whitelist) > MAX_DISPLAY_ITEMS:
            embed.add_field(
                name=" ",
                value=f" {len(role_whitelist) - MAX_DISPLAY_ITEMS} ",
                inline=False,
            )
    else:
        embed.add_field(
            name=" ", value="", inline=False
        )

    embed.add_field(
        name=" ",
        value=(
            "•  `/antispam whitelist add role @` \n"
            "•  `/antispam whitelist remove role @` \n"
            "• "
        ),
        inline=False,
    )

    embed.add_field(
        name="",
        value=(
            "• \n"
            "• \n"
            "• "
        ),
        inline=False,
    )

    embed.set_footer(text="")
    return embed


async def _get_user_whitelist(cog: "AntiSpam", guild_id: int) -> list[str]:
    """
    

    Args:
        cog: AntiSpam 
        guild_id:  ID

    Returns:
        List[str]:  ID 
    """
    try:
        #
        #  get_whitelist
        whitelist_data = await cog.get_cfg(guild_id, "user_whitelist", "")
        if whitelist_data:
            return whitelist_data.split(",")
        return []
    except Exception:
        return []


async def _get_role_whitelist(cog: "AntiSpam", guild_id: int) -> list[str]:
    """
    

    Args:
        cog: AntiSpam 
        guild_id:  ID

    Returns:
        List[str]:  ID 
    """
    try:
        #
        #  get_whitelist
        whitelist_data = await cog.get_cfg(guild_id, "role_whitelist", "")
        if whitelist_data:
            return whitelist_data.split(",")
        return []
    except Exception:
        return []


async def create_whitelist_management_embed(
    cog: "AntiSpam",
    guild: discord.Guild,
    action: str,
    target_type: str,
    target_id: int | None = None,
    success: bool = True,
    error_msg: str | None = None,
) -> discord.Embed:
    """
    

    Args:
        cog: AntiSpam 
        guild: Discord 
        action:  ("add"  "remove")
        target_type:  ("user"  "role")
        target_id:  ID
        success: 
        error_msg: 

    Returns:
        discord.Embed: 
    """

    if success:
        color = discord.Color.green()
        title = " "

        if action == "add":
            description = f" {target_type} "
        else:
            description = f" {target_type} "
    else:
        color = discord.Color.red()
        title = " "
        description = error_msg or ","

    embed = discord.Embed(title=title, description=description, color=color)

    if success and target_id:
        if target_type == "user":
            user = guild.get_member(target_id)
            if user:
                embed.add_field(
                    name="",
                    value=f"****: {user.display_name}\n**ID**: {user.id}",
                    inline=False,
                )
        elif target_type == "role":
            role = guild.get_role(target_id)
            if role:
                embed.add_field(
                    name=" ",
                    value=f"****: {role.name}\n**ID**: {role.id}",
                    inline=False,
                )

    embed.set_footer(text="")
    return embed
