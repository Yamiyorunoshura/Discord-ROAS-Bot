"""
反惡意連結保護模組 - 預覽面板Embed生成器
"""

import discord

from ...config.config import *
from ...main.main import AntiLink


class PreviewEmbed:
    """預覽面板Embed生成器"""

    def __init__(self, cog: AntiLink, guild_id: int):
        """
        初始化預覽面板Embed生成器

        Args:
            cog: 反惡意連結模組實例
            guild_id: 伺服器ID
        """
        self.cog = cog
        self.guild_id = guild_id

    async def create_embed(self) -> discord.Embed:
        """
        創建預覽面板Embed

        Returns:
            預覽面板的Embed
        """
        try:
            # 獲取設定
            settings = await self.cog.db.get_settings(self.guild_id)

            # 創建基本Embed
            embed = discord.Embed(
                title="🔗 反惡意連結保護",
                description="自動檢測並阻止惡意連結的傳播",
                color=discord.Color.blue(),
            )

            # 狀態資訊
            status = "🟢 已啟用" if settings.get("enabled", False) else "🔴 已停用"
            embed.add_field(name="🔧 模組狀態", value=status, inline=True)

            # 檢測統計
            stats = await self.cog.db.get_stats(self.guild_id)
            total_blocked = stats.get("total_blocked", 0)
            embed.add_field(
                name="📊 攔截統計",
                value=f"已攔截 {total_blocked} 個惡意連結",
                inline=True,
            )

            # 白名單數量
            whitelist_count = await self.cog.db.get_whitelist_count(self.guild_id)
            embed.add_field(
                name="📝 白名單", value=f"{whitelist_count} 個網域", inline=True
            )

            # 黑名單資訊
            remote_count = len(self.cog._remote_blacklist)
            manual_count = len(self.cog._manual_blacklist.get(self.guild_id, set()))
            embed.add_field(
                name="🚫 黑名單",
                value=f"遠端: {remote_count} 個\n手動: {manual_count} 個",
                inline=True,
            )

            # 設定資訊
            delete_msg = "是" if settings.get("delete_message", True) else "否"
            notify_admins = "是" if settings.get("notify_admins", True) else "否"
            embed.add_field(
                name="⚙️ 設定",
                value=f"刪除訊息: {delete_msg}\n通知管理員: {notify_admins}",
                inline=True,
            )

            # 最後更新時間
            if hasattr(self.cog, "_last_update"):
                embed.add_field(
                    name="🔄 最後更新",
                    value=f"<t:{int(self.cog._last_update)}:R>",
                    inline=True,
                )

            # 設定縮圖
            embed.set_thumbnail(
                url="https://cdn.discordapp.com/emojis/1234567890123456789.png"
            )

            # 設定頁腳
            embed.set_footer(
                text="使用下方選單切換面板 | 反惡意連結保護系統",
                icon_url="https://cdn.discordapp.com/emojis/1234567890123456789.png",
            )

            return embed

        except Exception as exc:
            # 錯誤處理
            embed = discord.Embed(
                title="❌ 載入失敗",
                description=f"載入預覽面板時發生錯誤:{exc}",
                color=discord.Color.red(),
            )
            return embed
