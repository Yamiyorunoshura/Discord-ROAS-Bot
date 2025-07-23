"""
反可執行檔案保護模組 - 檢測器
負責檢測各種類型的可執行檔案
"""

import re
import aiohttp
import logging
import discord
from typing import Set, List, Optional, TYPE_CHECKING
from urllib.parse import urlparse, unquote

from ..config.config import *

if TYPE_CHECKING:
    from .main import AntiExecutable

logger = logging.getLogger("anti_executable")

class ExecutableDetector:
    """可執行檔案檢測器"""
    
    def __init__(self, cog: 'AntiExecutable'):
        """
        初始化檢測器
        
        Args:
            cog: 反可執行檔案模組實例
        """
        self.cog = cog
        
        # URL 匹配模式
        self.url_pattern = re.compile(
            r'https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*)?(?:\?(?:[\w&=%.])*)?(?:#(?:[\w.])*)?',
            re.IGNORECASE
        )
    
    async def is_dangerous_attachment(self, attachment: discord.Attachment, guild_id: int) -> bool:
        """
        檢查附件是否為危險檔案
        
        Args:
            attachment: Discord 附件物件
            guild_id: 伺服器ID
            
        Returns:
            是否為危險檔案
        """
        try:
            filename = attachment.filename.lower()
            
            # 檢查檔案大小限制
            if attachment.size > MAX_FILE_SIZE * 1024 * 1024:
                return False
            
            # 檢查白名單
            whitelist = await self.cog.get_whitelist(guild_id)
            if any(pattern in filename for pattern in whitelist):
                return False
            
            # 檢查副檔名
            if self._is_dangerous_extension(filename, guild_id):
                return True
            
            # 檢查檔案特徵
            return await self._check_file_signature(attachment)
            
        except Exception as exc:
            logger.error(f"檢查附件失敗: {exc}")
            return False
    
    def _is_dangerous_extension(self, filename: str, guild_id: int) -> bool:
        """
        檢查副檔名是否危險
        
        Args:
            filename: 檔案名稱
            guild_id: 伺服器ID
            
        Returns:
            是否為危險副檔名
        """
        try:
            # 獲取副檔名
            if '.' not in filename:
                return False
            
            extension = filename.split('.')[-1].lower()
            
            # 檢查基本危險副檔名
            if extension in DANGEROUS_EXTENSIONS:
                return True
            
            # 檢查自定義格式
            custom_formats = self.cog._custom_formats_cache.get(guild_id, set())
            if extension in custom_formats:
                return True
            
            # 檢查嚴格模式
            settings = self.cog.db.get_settings(guild_id)  # 這裡可能需要改為異步
            if settings.get("strict_mode", False) and extension in STRICT_EXTENSIONS:
                return True
            
            return False
            
        except Exception as exc:
            logger.error(f"檢查副檔名失敗: {exc}")
            return False
    
    async def _check_file_signature(self, attachment: discord.Attachment) -> bool:
        """
        檢查檔案特徵
        
        Args:
            attachment: Discord 附件物件
            
        Returns:
            是否為可執行檔案
        """
        try:
            # 下載檔案前幾個位元組
            async with aiohttp.ClientSession() as session:
                headers = {"Range": "bytes=0-15"}
                async with session.get(attachment.url, headers=headers) as resp:
                    if resp.status not in [200, 206]:
                        return False
                    
                    content = await resp.read()
                    header = content[:8]
                    
                    # 檢查魔術數字
                    for signature in MAGIC_SIGNATURES:
                        if header.startswith(signature):
                            return True
                    
                    return False
                    
        except Exception as exc:
            logger.error(f"檢查檔案特徵失敗: {exc}")
            return False
    
    async def find_dangerous_links(self, content: str, guild_id: int) -> List[str]:
        """
        在文字中尋找危險連結
        
        Args:
            content: 訊息內容
            guild_id: 伺服器ID
            
        Returns:
            危險連結列表
        """
        try:
            dangerous_links = []
            
            # 尋找所有 URL
            urls = self.url_pattern.findall(content)
            
            for url in urls:
                if await self._is_dangerous_url(url, guild_id):
                    dangerous_links.append(url)
            
            return dangerous_links
            
        except Exception as exc:
            logger.error(f"檢查連結失敗: {exc}")
            return []
    
    async def _is_dangerous_url(self, url: str, guild_id: int) -> bool:
        """
        檢查 URL 是否指向危險檔案
        
        Args:
            url: 要檢查的 URL
            guild_id: 伺服器ID
            
        Returns:
            是否為危險 URL
        """
        try:
            # 解析 URL
            parsed = urlparse(url)
            path = unquote(parsed.path)
            
            # 提取檔案名稱
            if '/' in path:
                filename = path.split('/')[-1]
            else:
                filename = path
            
            # 移除查詢參數
            if '?' in filename:
                filename = filename.split('?')[0]
            
            if not filename or '.' not in filename:
                return False
            
            # 檢查副檔名
            return self._is_dangerous_extension(filename.lower(), guild_id)
            
        except Exception as exc:
            logger.error(f"檢查 URL 失敗: {exc}")
            return False 