"""
反可執行檔案保護模組 - 主要邏輯
"""

import asyncio
import logging
from typing import Set, Dict, Any, Optional, TYPE_CHECKING
from collections import defaultdict

import discord
from discord import app_commands
from discord.ext import commands, tasks

from ...base import ProtectionCog
from ..database.database import AntiExecutableDatabase
from ..config.config import *
from .detector import ExecutableDetector
from .actions import ExecutableActions

if TYPE_CHECKING:
    pass

logger = logging.getLogger("anti_executable")

class AntiExecutable(ProtectionCog):
    """
    反可執行檔案保護模組
    
    負責檢測和處理各種類型的可執行檔案，包括：
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
        self._whitelist_cache: Dict[int, Set[str]] = {}
        self._blacklist_cache: Dict[int, Set[str]] = {}
        self._custom_formats_cache: Dict[int, Set[str]] = {}
        
        # 統計資料
        self.stats: Dict[int, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        
    async def cog_load(self):
        """Cog 載入時的初始化"""
        try:
            await self.db.init_db()
            logger.info("【反可執行檔案】模組載入完成")
        except Exception as exc:
            logger.error(f"【反可執行檔案】模組載入失敗: {exc}")
            raise

    async def cog_unload(self):
        """Cog 卸載時的清理"""
        try:
            logger.info("【反可執行檔案】模組卸載完成")
        except Exception as exc:
            logger.error(f"【反可執行檔案】模組卸載失敗: {exc}")

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
                if await self.detector.is_dangerous_attachment(attachment, message.guild.id):
                    await self.actions.handle_violation(message, attachment.filename, "attachment")
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
            dangerous_links = await self.detector.find_dangerous_links(message.content, message.guild.id)
            if dangerous_links:
                await self.actions.handle_violation(message, dangerous_links[0], "link")
                # 記錄統計
                self.stats[message.guild.id]["links_blocked"] += 1
        except Exception as exc:
            logger.error(f"檢查連結失敗: {exc}")
    
    @app_commands.command(name="可執行檔保護面板", description="開啟反可執行檔案保護面板")
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
                "❌ 需要「管理伺服器」權限才能使用此指令",
                ephemeral=True
            )
            return
        
        try:
            # 導入面板視圖
            from ..panel.main_view import AntiExecutableMainView
            
            # 創建面板視圖
            view = AntiExecutableMainView(self, interaction.guild_id, interaction.user.id)
            
            # 獲取初始 Embed
            embed = await view.get_current_embed()
            
            # 發送帶有面板的訊息
            await interaction.response.send_message(embed=embed, view=view)
            
        except Exception as exc:
            # 如果面板載入失敗，使用簡單的 Embed
            embed = discord.Embed(
                title="🛡️ 反可執行檔案保護",
                description="保護伺服器免受惡意可執行檔案的威脅",
                color=discord.Color.red()
            )
            
            # 獲取設定
            settings = await self.db.get_settings(interaction.guild_id)
            status = "🟢 已啟用" if settings.get("enabled", False) else "🔴 已停用"
            
            embed.add_field(
                name="🔧 模組狀態",
                value=status,
                inline=True
            )
            
            # 統計資訊
            stats = self.stats.get(interaction.guild_id, {})
            embed.add_field(
                name="📊 攔截統計",
                value=f"附件: {stats.get('attachments_blocked', 0)} 個\n連結: {stats.get('links_blocked', 0)} 個",
                inline=True
            )
            
            embed.set_footer(text=f"面板載入失敗: {exc}")
            
            await interaction.response.send_message(embed=embed)
    
    async def get_settings(self, guild_id: int) -> Dict[str, Any]:
        """
        獲取伺服器設定
        
        Args:
            guild_id: 伺服器ID
            
        Returns:
            設定字典
        """
        return await self.db.get_settings(guild_id)
    
    async def update_settings(self, guild_id: int, settings: Dict[str, Any]) -> bool:
        """
        更新伺服器設定
        
        Args:
            guild_id: 伺服器ID
            settings: 設定字典
            
        Returns:
            是否成功
        """
        return await self.db.update_settings(guild_id, settings)
    
    async def get_whitelist(self, guild_id: int) -> Set[str]:
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