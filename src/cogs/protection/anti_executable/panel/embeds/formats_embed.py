"""
反可執行檔案保護模組 - 格式管理面板 Embed 生成器
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from ...main.main import AntiExecutable


class FormatsEmbed:
    """格式管理面板 Embed 生成器"""

    def __init__(self, cog: AntiExecutable, guild_id: int):
        """
        初始化格式管理面板 Embed 生成器

        Args:
            cog: 反可執行檔案模組實例
            guild_id: 伺服器ID
        """
        self.cog = cog
        self.guild_id = guild_id

    async def create_embed(self) -> discord.Embed:
        """
        創建格式管理面板 Embed

        Returns:
            格式管理面板的 Embed
        """
        try:
            # 獲取配置資料
            config = await self.cog.get_config(self.guild_id)
            blocked_formats = config.get("blocked_formats", [])

            # 創建基礎 Embed
            embed = discord.Embed(
                title="📁 檔案格式管理",
                description="管理需要檢測的檔案格式",
                color=discord.Color.orange(),
            )

            # 顯示當前檢測格式
            if blocked_formats:
                # 分組顯示格式
                executable_formats = []
                archive_formats = []
                script_formats = []
                other_formats = []

                for fmt in blocked_formats:
                    if fmt.lower() in ["exe", "msi", "bat", "cmd", "com", "scr", "pif"]:
                        executable_formats.append(fmt)
                    elif fmt.lower() in ["zip", "rar", "7z", "tar", "gz", "bz2"]:
                        archive_formats.append(fmt)
                    elif fmt.lower() in ["js", "vbs", "ps1", "sh", "py", "pl"]:
                        script_formats.append(fmt)
                    else:
                        other_formats.append(fmt)

                if executable_formats:
                    embed.add_field(
                        name="🔧 可執行檔案",
                        value=f"`{', '.join(executable_formats)}`",
                        inline=False,
                    )

                if archive_formats:
                    embed.add_field(
                        name="📦 壓縮檔案",
                        value=f"`{', '.join(archive_formats)}`",
                        inline=False,
                    )

                if script_formats:
                    embed.add_field(
                        name="📜 腳本檔案",
                        value=f"`{', '.join(script_formats)}`",
                        inline=False,
                    )

                if other_formats:
                    embed.add_field(
                        name="📄 其他格式",
                        value=f"`{', '.join(other_formats)}`",
                        inline=False,
                    )

                embed.add_field(
                    name="📊 統計資訊",
                    value=f"總共檢測 {len(blocked_formats)} 種格式",
                    inline=True,
                )
            else:
                embed.add_field(
                    name="📝 檢測格式", value="目前沒有設定檢測格式", inline=False
                )

            # 預設格式建議
            default_formats = [
                "exe",
                "msi",
                "bat",
                "cmd",
                "com",
                "scr",
                "pif",
                "zip",
                "rar",
                "7z",
                "tar",
                "gz",
                "js",
                "vbs",
                "ps1",
                "sh",
            ]

            embed.add_field(
                name="💡 建議格式",
                value=f"`{', '.join(default_formats)}`",
                inline=False,
            )

            # 操作說明
            embed.add_field(
                name="i 操作說明",
                value="• 點擊「新增格式」按鈕添加新的檔案格式\n• 點擊「移除格式」按鈕移除指定格式\n• 點擊「重置格式」按鈕恢復預設設定",
                inline=False,
            )

            # 設定頁尾
            embed.set_footer(
                text="格式不區分大小寫,請勿包含點號",
                icon_url="https://cdn.discordapp.com/emojis/1234567890.png",
            )

            return embed

        except Exception as exc:
            # 錯誤處理
            embed = discord.Embed(
                title="❌ 載入失敗",
                description=f"載入格式管理面板時發生錯誤:{exc}",
                color=discord.Color.red(),
            )
            return embed
