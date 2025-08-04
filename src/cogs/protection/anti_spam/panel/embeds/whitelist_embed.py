"""
反垃圾訊息白名單管理嵌入生成器
- 生成白名單顯示視圖
- 支援用戶和角色白名單
- 提供添加/移除功能
"""

from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from ...main.main import AntiSpam

# 常數定義
MAX_DISPLAY_ITEMS = 10

async def create_whitelist_embed(
    cog: "AntiSpam", guild: discord.Guild, whitelist_type: str = "user"
) -> discord.Embed:
    """
    創建白名單嵌入

    Args:
        cog: AntiSpam 模塊實例
        guild: Discord 伺服器物件
        whitelist_type: 白名單類型 ("user" 或 "role")

    Returns:
        discord.Embed: 白名單嵌入
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
    """創建白名單總覽嵌入"""
    embed = discord.Embed(
        title="📋 反垃圾訊息白名單管理",
        description=f"伺服器:{guild.name}",
        color=discord.Color.green(),
    )

    # 獲取白名單統計
    user_whitelist = await _get_user_whitelist(cog, guild.id)
    role_whitelist = await _get_role_whitelist(cog, guild.id)

    embed.add_field(
        name="👥 用戶白名單", value=f"已添加 {len(user_whitelist)} 個用戶", inline=True
    )

    embed.add_field(
        name="🎭 角色白名單", value=f"已添加 {len(role_whitelist)} 個角色", inline=True
    )

    embed.add_field(
        name="i 說明",
        value="白名單中的用戶和角色將不受反垃圾訊息檢測影響",
        inline=False,
    )

    embed.add_field(
        name="📝 操作說明",
        value=(
            "• 點擊 **用戶白名單** 管理用戶白名單\n"
            "• 點擊 **角色白名單** 管理角色白名單\n"
            "• 白名單成員可以無限制發送訊息"
        ),
        inline=False,
    )

    embed.set_footer(text="選擇要管理的白名單類型")
    return embed

async def _create_user_whitelist_embed(
    cog: "AntiSpam", guild: discord.Guild
) -> discord.Embed:
    """創建用戶白名單嵌入"""
    embed = discord.Embed(
        title="👥 用戶白名單管理",
        description="管理反垃圾訊息用戶白名單",
        color=discord.Color.blue(),
    )

    # 獲取用戶白名單
    user_whitelist = await _get_user_whitelist(cog, guild.id)

    if user_whitelist:
        # 顯示白名單用戶
        user_list = []
        for user_id in user_whitelist[:10]:  # 最多顯示10個
            try:
                user = guild.get_member(int(user_id))
                if user:
                    user_list.append(f"• {user.display_name} (`{user.id}`)")
                else:
                    # 用戶已離開伺服器
                    user_list.append(f"• 已離開的用戶 (`{user_id}`)")
            except Exception:
                user_list.append(f"• 無效用戶 (`{user_id}`)")

        embed.add_field(
            name=f"📋 白名單用戶 ({len(user_whitelist)} 個)",
            value="\n".join(user_list) if user_list else "無",
            inline=False,
        )

        if len(user_whitelist) > MAX_DISPLAY_ITEMS:
            embed.add_field(
                name="⚠️ 注意",
                value=f"還有 {len(user_whitelist) - MAX_DISPLAY_ITEMS} 個用戶未顯示",
                inline=False,
            )
    else:
        embed.add_field(
            name="📋 白名單用戶", value="目前沒有用戶在白名單中", inline=False
        )

    embed.add_field(
        name="🔧 操作說明",
        value=(
            "• 使用 `/antispam whitelist add user @用戶` 添加用戶\n"
            "• 使用 `/antispam whitelist remove user @用戶` 移除用戶\n"
            "• 白名單用戶不受任何垃圾訊息檢測限制"
        ),
        inline=False,
    )

    embed.set_footer(text="白名單用戶可以無限制發送訊息")
    return embed

async def _create_role_whitelist_embed(
    cog: "AntiSpam", guild: discord.Guild
) -> discord.Embed:
    """創建角色白名單嵌入"""
    embed = discord.Embed(
        title="🎭 角色白名單管理",
        description="管理反垃圾訊息角色白名單",
        color=discord.Color.purple(),
    )

    # 獲取角色白名單
    role_whitelist = await _get_role_whitelist(cog, guild.id)

    if role_whitelist:
        # 顯示白名單角色
        role_list = []
        for role_id in role_whitelist[:10]:  # 最多顯示10個
            try:
                role = guild.get_role(int(role_id))
                if role:
                    role_list.append(f"• {role.name} (`{role.id}`)")
                else:
                    # 角色已被刪除
                    role_list.append(f"• 已刪除的角色 (`{role_id}`)")
            except Exception:
                role_list.append(f"• 無效角色 (`{role_id}`)")

        embed.add_field(
            name=f"📋 白名單角色 ({len(role_whitelist)} 個)",
            value="\n".join(role_list) if role_list else "無",
            inline=False,
        )

        if len(role_whitelist) > MAX_DISPLAY_ITEMS:
            embed.add_field(
                name="⚠️ 注意",
                value=f"還有 {len(role_whitelist) - MAX_DISPLAY_ITEMS} 個角色未顯示",
                inline=False,
            )
    else:
        embed.add_field(
            name="📋 白名單角色", value="目前沒有角色在白名單中", inline=False
        )

    embed.add_field(
        name="🔧 操作說明",
        value=(
            "• 使用 `/antispam whitelist add role @角色` 添加角色\n"
            "• 使用 `/antispam whitelist remove role @角色` 移除角色\n"
            "• 擁有白名單角色的用戶不受垃圾訊息檢測限制"
        ),
        inline=False,
    )

    embed.add_field(
        name="💡 建議",
        value=(
            "• 建議將管理員角色添加到白名單\n"
            "• 可以為機器人角色添加白名單\n"
            "• 謹慎添加普通用戶角色"
        ),
        inline=False,
    )

    embed.set_footer(text="擁有白名單角色的用戶可以無限制發送訊息")
    return embed

async def _get_user_whitelist(cog: "AntiSpam", guild_id: int) -> list[str]:
    """
    獲取用戶白名單

    Args:
        cog: AntiSpam 模塊實例
        guild_id: 伺服器 ID

    Returns:
        List[str]: 用戶 ID 列表
    """
    try:
        # 這裡需要根據實際的數據庫實現來獲取白名單
        # 假設有一個 get_whitelist 方法
        whitelist_data = await cog.get_cfg(guild_id, "user_whitelist", "")
        if whitelist_data:
            return whitelist_data.split(",")
        return []
    except Exception:
        return []

async def _get_role_whitelist(cog: "AntiSpam", guild_id: int) -> list[str]:
    """
    獲取角色白名單

    Args:
        cog: AntiSpam 模塊實例
        guild_id: 伺服器 ID

    Returns:
        List[str]: 角色 ID 列表
    """
    try:
        # 這裡需要根據實際的數據庫實現來獲取白名單
        # 假設有一個 get_whitelist 方法
        whitelist_data = await cog.get_cfg(guild_id, "role_whitelist", "")
        if whitelist_data:
            return whitelist_data.split(",")
        return []
    except Exception:
        return []

async def create_whitelist_management_embed(
    cog: "AntiSpam",  # noqa: ARG001
    guild: discord.Guild,
    action: str,
    target_type: str,
    target_id: int | None = None,
    success: bool = True,
    error_msg: str | None = None,
) -> discord.Embed:
    """
    創建白名單管理操作結果嵌入

    Args:
        cog: AntiSpam 模塊實例
        guild: Discord 伺服器物件
        action: 操作類型 ("add" 或 "remove")
        target_type: 目標類型 ("user" 或 "role")
        target_id: 目標 ID
        success: 操作是否成功
        error_msg: 錯誤訊息

    Returns:
        discord.Embed: 操作結果嵌入
    """

    if success:
        color = discord.Color.green()
        title = "✅ 操作成功"

        if action == "add":
            description = f"已將 {target_type} 添加到白名單"
        else:
            description = f"已將 {target_type} 從白名單中移除"
    else:
        color = discord.Color.red()
        title = "❌ 操作失敗"
        description = error_msg or "操作失敗,請稍後再試"

    embed = discord.Embed(title=title, description=description, color=color)

    if success and target_id:
        if target_type == "user":
            user = guild.get_member(target_id)
            if user:
                embed.add_field(
                    name="👤 用戶資訊",
                    value=f"**名稱**: {user.display_name}\n**ID**: {user.id}",
                    inline=False,
                )
        elif target_type == "role":
            role = guild.get_role(target_id)
            if role:
                embed.add_field(
                    name="🎭 角色資訊",
                    value=f"**名稱**: {role.name}\n**ID**: {role.id}",
                    inline=False,
                )

    embed.set_footer(text="白名單變更已生效")
    return embed
