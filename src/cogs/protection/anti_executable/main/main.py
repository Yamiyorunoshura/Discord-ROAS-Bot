"""
反可執行檔案保護模組 - 主要邏輯
"""

import logging
from collections import defaultdict
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

from ...base import ProtectionCog
from ..database.database import AntiExecutableDatabase
from ..panel.main_view import AntiExecutableMainView
from .actions import ExecutableActions
from .detector import ExecutableDetector

logger = logging.getLogger("anti_executable")


class AntiExecutable(ProtectionCog):
    """
    反可執行檔案保護模組

    負責檢測和處理各種類型的可執行檔案,包括:
    - 附件檔案檢測
    - 連結檔案檢測
    - 檔案特徵檢測
    - 白名單/黑名單管理
    """

    module_name = "anti_executable"

    def __init__(self, bot: commands.Bot):
        """
        初始化反可執行檔案保護系統

        Args:
            bot: Discord 機器人實例
        """
        super().__init__(bot)
        self.db = AntiExecutableDatabase(self)
        self.detector = ExecutableDetector(self)
        self.actions = ExecutableActions(self)

        # 快取管理
        self._whitelist_cache: dict[int, set[str]] = {}
        self._blacklist_cache: dict[int, set[str]] = {}
        self._custom_formats_cache: dict[int, set[str]] = {}

        # 統計資料
        self.stats: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    async def cog_load(self):
        """Cog 載入時的初始化"""
        try:
            await self.db.init_db()
            logger.info("[反可執行檔案]模組載入完成")
        except Exception as exc:
            logger.error(f"[反可執行檔案]模組載入失敗: {exc}")
            raise

    async def cog_unload(self):
        """Cog 卸載時的清理"""
        try:
            logger.info("[反可執行檔案]模組卸載完成")
        except Exception as exc:
            logger.error(f"[反可執行檔案]模組卸載失敗: {exc}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """
        訊息事件監聽器

        Args:
            message: Discord 訊息物件
        """
        # 基本檢查
        if not message.guild or message.author.bot:
            return

        # 檢查是否啟用
        settings = await self.db.get_settings(message.guild.id)
        if not settings.get("enabled", False):
            return

        # 檢查附件
        if message.attachments:
            await self._check_attachments(message)

        # 檢查連結中的檔案
        if settings.get("check_links", True):
            await self._check_links_in_message(message)

    async def _check_attachments(self, message: discord.Message):
        """
        檢查訊息附件

        Args:
            message: Discord 訊息物件
        """
        try:
            for attachment in message.attachments:
                if await self.detector.is_dangerous_attachment(
                    attachment, message.guild.id
                ):
                    await self.actions.handle_violation(
                        message, attachment.filename, "attachment"
                    )
                    # 記錄統計
                    self.stats[message.guild.id]["attachments_blocked"] += 1
                    break  # 只需要處理一次
        except Exception as exc:
            logger.error(f"檢查附件失敗: {exc}")

    async def _check_links_in_message(self, message: discord.Message):
        """
        檢查訊息中的連結

        Args:
            message: Discord 訊息物件
        """
        try:
            dangerous_links = await self.detector.find_dangerous_links(
                message.content, message.guild.id
            )
            if dangerous_links:
                await self.actions.handle_violation(message, dangerous_links[0], "link")
                # 記錄統計
                self.stats[message.guild.id]["links_blocked"] += 1
        except Exception as exc:
            logger.error(f"檢查連結失敗: {exc}")

    @app_commands.command(
        name="可執行檔保護面板", description="開啟反可執行檔案保護面板"
    )
    @app_commands.describe()
    async def executable_panel(self, interaction: discord.Interaction):
        """
        反可執行檔案保護面板指令

        Args:
            interaction: Discord 互動物件
        """
        # 權限檢查
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ 需要「管理伺服器」權限才能使用此指令", ephemeral=True
            )
            return

        try:
            # 創建面板視圖
            view = AntiExecutableMainView(
                self, interaction.guild_id, interaction.user.id
            )

            # 獲取初始 Embed
            embed = await view.get_current_embed()

            # 發送帶有面板的訊息
            await interaction.response.send_message(embed=embed, view=view)

        except Exception as exc:
            # 如果面板載入失敗,使用簡單的 Embed
            embed = discord.Embed(
                title="🛡️ 反可執行檔案保護",
                description="保護伺服器免受惡意可執行檔案的威脅",
                color=discord.Color.red(),
            )

            # 獲取設定
            settings = await self.db.get_settings(interaction.guild_id)
            status = "🟢 已啟用" if settings.get("enabled", False) else "🔴 已停用"

            embed.add_field(name="🔧 模組狀態", value=status, inline=True)

            # 統計資訊
            stats = self.stats.get(interaction.guild_id, {})
            embed.add_field(
                name="📊 攔截統計",
                value=(
                    f"附件: {stats.get('attachments_blocked', 0)} 個\n"
                    f"連結: {stats.get('links_blocked', 0)} 個"
                ),
                inline=True,
            )

            embed.set_footer(text=f"面板載入失敗: {exc}")

            await interaction.response.send_message(embed=embed)

    async def get_config(
        self, guild_id: int, key: str | None = None, default: Any = None
    ) -> Any:
        """
        獲取配置項目 - 面板系統適配方法

        Args:
            guild_id: 伺服器 ID
            key: 配置鍵(可選,如果為 None 則返回所有配置)
            default: 預設值

        Returns:
            配置值或所有配置字典
        """
        try:
            if key is None:
                # 返回所有配置
                return await self.db.get_all_config(guild_id)
            else:
                # 返回特定配置
                return await self.db.get_config(guild_id, key, default)
        except Exception as exc:
            logger.error(f"[反可執行檔案]獲取配置失敗: {exc}")
            return default if key else {}

    async def get_settings(self, guild_id: int) -> dict[str, Any]:
        """
        獲取伺服器設定

        Args:
            guild_id: 伺服器ID

        Returns:
            設定字典
        """
        return await self.db.get_settings(guild_id)

    async def update_settings(self, guild_id: int, settings: dict[str, Any]) -> bool:
        """
        更新伺服器設定

        Args:
            guild_id: 伺服器ID
            settings: 設定字典

        Returns:
            是否成功
        """
        return await self.db.update_settings(guild_id, settings)

    async def get_whitelist(self, guild_id: int) -> set[str]:
        """
        獲取白名單

        Args:
            guild_id: 伺服器ID

        Returns:
            白名單集合
        """
        # 優先使用快取
        if guild_id in self._whitelist_cache:
            return self._whitelist_cache[guild_id]

        # 從資料庫載入
        whitelist = await self.db.get_whitelist(guild_id)
        self._whitelist_cache[guild_id] = whitelist
        return whitelist

    async def add_to_whitelist(self, guild_id: int, item: str) -> bool:
        """
        添加到白名單

        Args:
            guild_id: 伺服器ID
            item: 要添加的項目

        Returns:
            是否成功
        """
        success = await self.db.add_to_whitelist(guild_id, item)
        if success and guild_id in self._whitelist_cache:
            self._whitelist_cache[guild_id].add(item)
        return success

    async def remove_from_whitelist(self, guild_id: int, item: str) -> bool:
        """
        從白名單移除

        Args:
            guild_id: 伺服器ID
            item: 要移除的項目

        Returns:
            是否成功
        """
        success = await self.db.remove_from_whitelist(guild_id, item)
        if success and guild_id in self._whitelist_cache:
            self._whitelist_cache[guild_id].discard(item)
        return success

    async def get_blacklist(self, guild_id: int) -> set[str]:
        """
        獲取黑名單

        Args:
            guild_id: 伺服器ID

        Returns:
            黑名單集合
        """
        # 優先使用快取
        if guild_id in self._blacklist_cache:
            return self._blacklist_cache[guild_id]

        # 從資料庫載入
        blacklist = await self.db.get_blacklist(guild_id)
        self._blacklist_cache[guild_id] = blacklist
        return blacklist

    async def add_to_blacklist(self, guild_id: int, item: str) -> bool:
        """
        添加到黑名單

        Args:
            guild_id: 伺服器ID
            item: 要添加的項目

        Returns:
            是否成功
        """
        success = await self.db.add_to_blacklist(guild_id, item)
        if success and guild_id in self._blacklist_cache:
            self._blacklist_cache[guild_id].add(item)
        return success

    async def remove_from_blacklist(self, guild_id: int, item: str) -> bool:
        """
        從黑名單移除

        Args:
            guild_id: 伺服器ID
            item: 要移除的項目

        Returns:
            是否成功
        """
        success = await self.db.remove_from_blacklist(guild_id, item)
        if success and guild_id in self._blacklist_cache:
            self._blacklist_cache[guild_id].discard(item)
        return success

    async def get_stats(self, guild_id: int) -> dict[str, int]:
        """
        獲取統計資料

        Args:
            guild_id: 伺服器ID

        Returns:
            統計資料字典
        """
        # 從記憶體統計獲取
        memory_stats = self.stats.get(guild_id, {})

        # 從資料庫獲取歷史統計
        db_stats = await self.db.get_stats(guild_id)

        # 合併統計資料
        combined_stats = {
            "total_blocked": memory_stats.get("attachments_blocked", 0)
            + memory_stats.get("links_blocked", 0),
            "files_blocked": memory_stats.get("attachments_blocked", 0),
            "links_blocked": memory_stats.get("links_blocked", 0),
            **db_stats,
        }

        return combined_stats

    async def clear_stats(self, guild_id: int) -> bool:
        """
        清空統計資料

        Args:
            guild_id: 伺服器ID

        Returns:
            是否成功
        """
        try:
            # 清空記憶體統計
            if guild_id in self.stats:
                del self.stats[guild_id]

            # 清空資料庫統計
            success = await self.db.clear_stats(guild_id)
            return success
        except Exception as exc:
            logger.error(f"清空統計失敗: {exc}")
            return False

    async def enable_protection(self, guild_id: int) -> bool:
        """
        啟用保護

        Args:
            guild_id: 伺服器ID

        Returns:
            是否成功
        """
        return await self.update_settings(guild_id, {"enabled": True})

    async def disable_protection(self, guild_id: int) -> bool:
        """
        停用保護

        Args:
            guild_id: 伺服器ID

        Returns:
            是否成功
        """
        return await self.update_settings(guild_id, {"enabled": False})

    async def clear_whitelist(self, guild_id: int) -> bool:
        """
        清空白名單

        Args:
            guild_id: 伺服器ID

        Returns:
            是否成功
        """
        try:
            success = await self.db.clear_whitelist(guild_id)
            if success and guild_id in self._whitelist_cache:
                self._whitelist_cache[guild_id].clear()
            return success
        except Exception as exc:
            logger.error(f"清空白名單失敗: {exc}")
            return False

    async def reset_formats(self, guild_id: int) -> bool:
        """
        重置格式為預設值

        Args:
            guild_id: 伺服器ID

        Returns:
            是否成功
        """
        try:
            success = await self.db.reset_custom_formats(guild_id)
            if success and guild_id in self._custom_formats_cache:
                del self._custom_formats_cache[guild_id]
            return success
        except Exception as exc:
            logger.error(f"重置格式失敗: {exc}")
            return False

    async def export_stats(self, guild_id: int) -> str:
        """
        匯出統計資料

        Args:
            guild_id: 伺服器ID

        Returns:
            匯出的統計資料字串
        """
        try:
            stats = await self.get_stats(guild_id)
            # 這裡可以實現更詳細的匯出邏輯
            return f"統計資料匯出功能開發中... 目前統計: {stats}"
        except Exception as exc:
            logger.error(f"匯出統計失敗: {exc}")
            return "匯出失敗"
