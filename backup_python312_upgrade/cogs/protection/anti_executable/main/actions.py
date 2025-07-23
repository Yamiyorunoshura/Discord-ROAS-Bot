"""
反可執行檔案保護模組 - 動作處理器
負責處理檢測到的違規行為
"""

from __future__ import annotations
import logging
from typing import Optional, TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from .main import AntiExecutable

logger = logging.getLogger("anti_executable")

class ExecutableActions:
    """可執行檔案動作處理器"""
    
    def __init__(self, cog: AntiExecutable):
        """
        初始化動作處理器
        
        Args:
            cog: 反可執行檔案模組實例
        """
        self.cog = cog
    
    async def handle_violation(self, message: discord.Message, filename: str, violation_type: str):
        """
        處理違規行為
        
        Args:
            message: 違規訊息
            filename: 檔案名稱
            violation_type: 違規類型 (attachment/link)
        """
        try:
            # 獲取設定
            settings = await self.cog.get_settings(message.guild.id)
            
            # 刪除訊息
            if settings.get("delete_message", True):
                await self._delete_message(message)
            
            # 發送警告
            await self._send_warning(message, filename, violation_type, settings)
            
            # 通知管理員
            if settings.get("notify_admins", True):
                await self._notify_admins(message, filename, violation_type, settings)
            
            # 記錄違規
            await self._log_violation(message, filename, violation_type)
            
        except Exception as exc:
            logger.error(f"處理違規失敗: {exc}")
    
    async def _delete_message(self, message: discord.Message):
        """
        刪除訊息
        
        Args:
            message: 要刪除的訊息
        """
        try:
            await message.delete()
            logger.info(f"已刪除違規訊息: {message.id}")
        except discord.Forbidden:
            logger.warning(f"無權限刪除訊息: {message.id}")
        except discord.NotFound:
            logger.warning(f"訊息已不存在: {message.id}")
        except Exception as exc:
            logger.error(f"刪除訊息失敗: {exc}")
    
    async def _send_warning(self, message: discord.Message, filename: str, violation_type: str, settings: dict):
        """
        發送警告訊息
        
        Args:
            message: 原始訊息
            filename: 檔案名稱
            violation_type: 違規類型
            settings: 設定
        """
        try:
            # 獲取警告訊息
            warning_msg = settings.get("delete_message", "🚫 偵測到可執行檔案，已自動刪除")
            
            # 創建警告 Embed
            embed = discord.Embed(
                title="🛡️ 可執行檔案已攔截",
                description=warning_msg,
                color=discord.Color.red()
            )
            
            embed.add_field(
                name="👤 用戶",
                value=message.author.mention,
                inline=True
            )
            
            embed.add_field(
                name="📁 檔案",
                value=filename,
                inline=True
            )
            
            embed.add_field(
                name="🔍 類型",
                value="附件檔案" if violation_type == "attachment" else "連結檔案",
                inline=True
            )
            
            # 發送到原頻道
            await message.channel.send(embed=embed, delete_after=10)
            
        except Exception as exc:
            logger.error(f"發送警告失敗: {exc}")
    
    async def _notify_admins(self, message: discord.Message, filename: str, violation_type: str, settings: dict):
        """
        通知管理員
        
        Args:
            message: 原始訊息
            filename: 檔案名稱
            violation_type: 違規類型
            settings: 設定
        """
        try:
            # 獲取通知頻道
            notify_channel_id = settings.get("notify_channel")
            if not notify_channel_id:
                return
            
            notify_channel = message.guild.get_channel(int(notify_channel_id))
            if not notify_channel:
                return
            
            # 創建通知 Embed
            embed = discord.Embed(
                title="🚨 可執行檔案攔截通知",
                description="檢測到用戶嘗試發送可執行檔案",
                color=discord.Color.orange()
            )
            
            embed.add_field(
                name="👤 用戶",
                value=f"{message.author.mention} ({message.author.id})",
                inline=True
            )
            
            embed.add_field(
                name="📍 頻道",
                value=message.channel.mention,
                inline=True
            )
            
            embed.add_field(
                name="📁 檔案",
                value=filename,
                inline=True
            )
            
            embed.add_field(
                name="🔍 類型",
                value="附件檔案" if violation_type == "attachment" else "連結檔案",
                inline=True
            )
            
            embed.add_field(
                name="⏰ 時間",
                value=f"<t:{int(message.created_at.timestamp())}:F>",
                inline=True
            )
            
            # 如果有訊息內容，添加到 Embed
            if message.content:
                content = message.content[:500] + "..." if len(message.content) > 500 else message.content
                embed.add_field(
                    name="💬 訊息內容",
                    value=f"```{content}```",
                    inline=False
                )
            
            await notify_channel.send(embed=embed)
            
        except Exception as exc:
            logger.error(f"通知管理員失敗: {exc}")
    
    async def _log_violation(self, message: discord.Message, filename: str, violation_type: str):
        """
        記錄違規行為
        
        Args:
            message: 原始訊息
            filename: 檔案名稱
            violation_type: 違規類型
        """
        try:
            # 記錄到日誌
            logger.info(
                f"可執行檔案攔截 - 用戶: {message.author.id}, "
                f"檔案: {filename}, 類型: {violation_type}, "
                f"頻道: {message.channel.id}"
            )
            
            # 這裡可以添加資料庫記錄邏輯
            # await self.cog.db.log_violation(...)
            
        except Exception as exc:
            logger.error(f"記錄違規失敗: {exc}") 