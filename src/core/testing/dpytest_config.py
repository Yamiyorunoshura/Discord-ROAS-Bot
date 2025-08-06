"""
🧪 dpytest 配置模組
提供 Discord.py 測試框架的配置和初始化功能
"""

import logging
from typing import TYPE_CHECKING, Any

import discord
import dpytest

if TYPE_CHECKING:
    from discord.ext.commands import Bot

# 設定 dpytest 日誌級別，避免測試期間過多的調試信息
logging.getLogger("dpytest").setLevel(logging.WARNING)


class DpytestConfig:
    """dpytest 配置管理器"""

    @staticmethod
    async def configure_bot(
        bot: "Bot",
        *,
        num_guilds: int = 1,
        num_members: int = 5,
        num_channels: int = 3,
        num_roles: int = 2,
        **kwargs: Any,
    ) -> None:
        """
        配置機器人用於測試環境

        Args:
            bot: Discord.py 機器人實例
            num_guilds: 模擬伺服器數量
            num_members: 每個伺服器的成員數量
            num_channels: 每個伺服器的頻道數量
            num_roles: 每個伺服器的角色數量
            **kwargs: 其他配置選項
        """
        # 配置 dpytest
        dpytest.configure(
            bot,
            num_guilds=num_guilds,
            num_members=num_members,
            num_channels=num_channels,
            num_roles=num_roles,
            **kwargs,
        )

        # 等待機器人就緒
        await dpytest.empty_queue()

    @staticmethod
    async def create_test_guild(
        name: str = "測試伺服器",
        *,
        owner_id: int | None = None,
        channels: list[str] | None = None,
        roles: list[str] | None = None,
    ) -> discord.Guild:
        """
        創建測試伺服器

        Args:
            name: 伺服器名稱
            owner_id: 擁有者 ID
            channels: 頻道名稱列表
            roles: 角色名稱列表

        Returns:
            創建的測試伺服器
        """
        guild = dpytest.backend.make_guild(name, owner_id or 123456789)

        # 添加頻道
        if channels:
            for channel_name in channels:
                dpytest.backend.make_text_channel(channel_name, guild)

        # 添加角色
        if roles:
            for role_name in roles:
                dpytest.backend.make_role(role_name, guild)

        return guild

    @staticmethod
    async def create_test_user(
        username: str = "測試用戶",
        *,
        discriminator: str = "0001",
        user_id: int | None = None,
        bot: bool = False,
    ) -> discord.User:
        """
        創建測試用戶

        Args:
            username: 用戶名稱
            discriminator: 用戶標識符
            user_id: 用戶 ID
            bot: 是否為機器人

        Returns:
            創建的測試用戶
        """
        return dpytest.backend.make_user(
            username, discriminator, user_id or 987654321, bot=bot
        )

    @staticmethod
    async def create_test_member(
        user: discord.User,
        guild: discord.Guild,
        *,
        roles: list[discord.Role] | None = None,
        permissions: discord.Permissions | None = None,
    ) -> discord.Member:
        """
        創建測試成員

        Args:
            user: 用戶對象
            guild: 伺服器對象
            roles: 成員角色列表
            permissions: 成員權限

        Returns:
            創建的測試成員
        """
        member = dpytest.backend.make_member(user, guild)

        # 設定角色
        if roles:
            for role in roles:
                member._roles.add(role.id)

        return member

    @staticmethod
    async def send_test_message(
        channel: discord.TextChannel,
        content: str,
        *,
        author: discord.Member | None = None,
        embed: discord.Embed | None = None,
        attachments: list[discord.Attachment] | None = None,
    ) -> discord.Message:
        """
        發送測試訊息

        Args:
            channel: 目標頻道
            content: 訊息內容
            author: 發送者（如果未提供則使用預設成員）
            embed: 嵌入訊息
            attachments: 附件列表

        Returns:
            發送的測試訊息
        """
        if author is None:
            # 使用頻道中的第一個成員作為預設發送者
            members = list(channel.guild.members)
            author = members[0] if members else None

        message = dpytest.backend.make_message(
            content, author, channel, attachments=attachments
        )

        if embed:
            message.embeds = [embed]

        return message

    @staticmethod
    async def cleanup() -> None:
        """清理測試環境"""
        await dpytest.empty_queue()
        dpytest.backend.cleanup()


# 便捷函數
async def configure_test_bot(bot: "Bot", **kwargs: Any) -> None:
    """配置機器人用於測試（便捷函數）"""
    await DpytestConfig.configure_bot(bot, **kwargs)


async def cleanup_test_environment() -> None:
    """清理測試環境（便捷函數）"""
    await DpytestConfig.cleanup()
