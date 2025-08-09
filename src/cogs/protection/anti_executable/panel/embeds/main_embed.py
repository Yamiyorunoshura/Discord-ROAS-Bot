"""
 -  Embed 
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from ...main.main import AntiExecutable

MAX_DISPLAY_FORMATS = 10


class MainEmbed:
    """ Embed """

    def __init__(self, cog: AntiExecutable, guild_id: int):
        """
         Embed 

        Args:
            cog: 
            guild_id: ID
        """
        self.cog = cog
        self.guild_id = guild_id

    async def create_embed(self) -> discord.Embed:
        """
         Embed

        Returns:
             Embed
        """
        try:
            config = await self.cog.get_config(self.guild_id)

            # 創建主要 Embed
            embed = discord.Embed(
                title="🛡️ 防可執行檔案保護系統",
                description="自動檢測並阻擋可疑的可執行檔案和惡意連結，保護伺服器安全。",
                color=(
                    discord.Color.blue()
                    if config.get("enabled", False)
                    else discord.Color.red()
                ),
            )

            status = "🟢 已啟用" if config.get("enabled", False) else "🔴 已停用"
            embed.add_field(name="📊 系統狀態", value=status, inline=True)

            delete_message = "✅ 已啟用" if config.get("delete_message", True) else "❌ 已停用"
            notify_admin = "✅ 已啟用" if config.get("notify_admin", True) else "❌ 已停用"
            warn_user = "✅ 已啟用" if config.get("warn_user", True) else "❌ 已停用"

            embed.add_field(
                name="⚙️ 處理動作",
                value=f"🗑️ 刪除檔案: {delete_message}\n🔔 通知管理員: {notify_admin}\n⚠️ 警告用戶: {warn_user}",
                inline=True,
            )

            try:
                stats = await self.cog.get_stats(self.guild_id)
                total_blocked = stats.get("total_blocked", 0)
                files_blocked = stats.get("files_blocked", 0)
                links_blocked = stats.get("links_blocked", 0)

                embed.add_field(
                    name="📈 保護統計",
                    value=f"🚫 總阻擋: {total_blocked}\n📁 檔案阻擋: {files_blocked}\n🔗 連結阻擋: {links_blocked}",
                    inline=True,
                )
            except Exception:
                embed.add_field(
                    name="📈 保護統計", value="❌ 無法載入統計資料", inline=True
                )

            try:
                whitelist = await self.cog.get_whitelist(self.guild_id)
                blacklist = await self.cog.get_blacklist(self.guild_id)

                embed.add_field(
                    name="📋 清單管理",
                    value=f"✅ 白名單: {len(whitelist)} 項目\n❌ 黑名單: {len(blacklist)} 項目",
                    inline=True,
                )
            except Exception:
                embed.add_field(
                    name="📋 清單管理", value="❌ 無法載入清單資料", inline=True
                )

            try:
                formats = config.get("blocked_formats", [])
                formats_text = ", ".join(formats[:MAX_DISPLAY_FORMATS])
                if len(formats) > MAX_DISPLAY_FORMATS:
                    formats_text += f"... (共 {len(formats)} 個格式)"

                embed.add_field(
                    name="🚫 封鎖的檔案格式",
                    value=formats_text if formats_text else "未設定任何格式限制",
                    inline=False,
                )
            except Exception:
                embed.add_field(
                    name="🚫 封鎖的檔案格式", value="❌ 無法載入格式清單", inline=False
                )

            embed.set_footer(
                text="防可執行檔案保護系統 | 版本 2.3.1",
                icon_url="https://cdn.discordapp.com/emojis/1234567890.png",
            )

            return embed

        except Exception as exc:
            embed = discord.Embed(
                title="❌ 系統錯誤",
                description=f"載入防可執行檔案保護系統時發生錯誤: {exc}",
                color=discord.Color.red(),
            )
            return embed
