"""
歡迎系統服務
Task ID: 9 - 重構現有模組以符合新架構

提供歡迎系統的核心業務邏輯：
- 歡迎設定管理
- 圖片生成和快取
- 成員加入處理
- 背景圖片管理
"""

import os
import io
import logging
import asyncio
import contextlib
import aiohttp
from typing import Optional, Dict, Any, List
from PIL import Image, ImageDraw, ImageFont
import discord

from core.base_service import BaseService
from core.database_manager import DatabaseManager
from core.exceptions import ServiceError, handle_errors
from .models import WelcomeSettings, WelcomeImage

logger = logging.getLogger('services.welcome')


class WelcomeService(BaseService):
    """
    歡迎系統服務
    
    負責處理歡迎訊息的所有業務邏輯
    """
    
    def __init__(self, database_manager: DatabaseManager, config: Optional[Dict[str, Any]] = None):
        """
        初始化歡迎服務
        
        參數：
            database_manager: 資料庫管理器
            config: 配置參數
        """
        super().__init__("WelcomeService")
        self.db_manager = database_manager
        self.config = config or {}
        
        # 配置參數
        self.bg_dir = self.config.get('bg_dir', 'data/backgrounds')
        self.fonts_dir = self.config.get('fonts_dir', 'fonts')
        self.default_font = self.config.get('default_font', 'fonts/NotoSansCJKtc-Regular.otf')
        
        # 快取
        self._image_cache: Dict[str, WelcomeImage] = {}
        self._settings_cache: Dict[int, WelcomeSettings] = {}
        self._cache_lock = asyncio.Lock()
        
        # HTTP 會話
        self._session: Optional[aiohttp.ClientSession] = None
        
        # 確保目錄存在
        os.makedirs(self.bg_dir, exist_ok=True)
        
        # 添加資料庫依賴
        self.add_dependency(database_manager, "database")
    
    async def _initialize(self) -> bool:
        """初始化服務"""
        try:
            # 建立 HTTP 會話
            self._session = aiohttp.ClientSession()
            
            # 初始化歡迎系統資料表
            await self._init_database_tables()
            
            logger.info("歡迎服務初始化成功")
            return True
            
        except Exception as e:
            logger.error(f"歡迎服務初始化失敗：{e}")
            return False
    
    async def _cleanup(self) -> None:
        """清理資源"""
        try:
            # 關閉 HTTP 會話
            if self._session:
                await self._session.close()
                self._session = None
            
            # 清除快取
            async with self._cache_lock:
                self._image_cache.clear()
                self._settings_cache.clear()
            
            logger.info("歡迎服務已清理")
            
        except Exception as e:
            logger.error(f"清理歡迎服務時發生錯誤：{e}")
    
    async def _validate_permissions(self, user_id: int, guild_id: Optional[int], action: str) -> bool:
        """
        歡迎服務權限驗證
        
        實作基本的權限邏輯，可根據需要擴展
        """
        # 目前允許所有管理操作，可根據需要調整
        return True
    
    async def _init_database_tables(self) -> None:
        """初始化歡迎系統相關的資料表"""
        # 歡迎設定表
        await self.db_manager.execute("""
            CREATE TABLE IF NOT EXISTS welcome_settings (
                guild_id INTEGER PRIMARY KEY,
                channel_id INTEGER,
                title TEXT DEFAULT '歡迎 {member.name}!',
                description TEXT DEFAULT '很高興見到你～',
                message TEXT DEFAULT '歡迎 {member.mention} 加入 {guild.name}！',
                avatar_x INTEGER DEFAULT 30,
                avatar_y INTEGER DEFAULT 80,
                title_y INTEGER DEFAULT 60,
                description_y INTEGER DEFAULT 120,
                title_font_size INTEGER DEFAULT 36,
                desc_font_size INTEGER DEFAULT 22,
                avatar_size INTEGER DEFAULT 176
            )
        """)
        
        # 歡迎背景表
        await self.db_manager.execute("""
            CREATE TABLE IF NOT EXISTS welcome_backgrounds (
                guild_id INTEGER PRIMARY KEY,
                image_path TEXT
            )
        """)
    
    @handle_errors(log_errors=True)
    async def get_settings(self, guild_id: int) -> WelcomeSettings:
        """
        獲取伺服器的歡迎設定
        
        參數：
            guild_id: 伺服器 ID
            
        返回：
            歡迎設定
        """
        # 檢查快取
        async with self._cache_lock:
            if guild_id in self._settings_cache:
                return self._settings_cache[guild_id]
        
        try:
            # 從資料庫查詢
            row = await self.db_manager.fetchone(
                "SELECT * FROM welcome_settings WHERE guild_id = ?", 
                (guild_id,)
            )
            
            if row:
                settings = WelcomeSettings(
                    guild_id=row['guild_id'],
                    channel_id=row['channel_id'],
                    title=row['title'] or "歡迎 {member.name}!",
                    description=row['description'] or "很高興見到你～",
                    message=row['message'] or "歡迎 {member.mention} 加入 {guild.name}！",
                    avatar_x=row['avatar_x'] or 30,
                    avatar_y=row['avatar_y'] or 80,
                    title_y=row['title_y'] or 60,
                    description_y=row['description_y'] or 120,
                    title_font_size=row['title_font_size'] or 36,
                    desc_font_size=row['desc_font_size'] or 22,
                    avatar_size=row['avatar_size'] or 176
                )
            else:
                # 建立預設設定
                settings = WelcomeSettings(guild_id=guild_id)
                await self._save_settings(settings)
            
            # 獲取背景圖片
            bg_row = await self.db_manager.fetchone(
                "SELECT image_path FROM welcome_backgrounds WHERE guild_id = ?",
                (guild_id,)
            )
            if bg_row:
                settings.background_path = bg_row['image_path']
            
            # 快取設定
            async with self._cache_lock:
                self._settings_cache[guild_id] = settings
            
            return settings
            
        except Exception as e:
            logger.error(f"獲取歡迎設定失敗：{e}")
            raise ServiceError(
                f"獲取歡迎設定失敗：{str(e)}",
                service_name=self.name,
                operation="get_settings"
            )
    
    @handle_errors(log_errors=True)
    async def update_setting(self, guild_id: int, key: str, value: Any) -> bool:
        """
        更新單一歡迎設定
        
        參數：
            guild_id: 伺服器 ID
            key: 設定鍵
            value: 設定值
            
        返回：
            是否更新成功
        """
        try:
            # 確保記錄存在
            await self._ensure_settings_exist(guild_id)
            
            # 更新資料庫
            await self.db_manager.execute(
                f"UPDATE welcome_settings SET {key} = ? WHERE guild_id = ?",
                (value, guild_id)
            )
            
            # 清除快取
            async with self._cache_lock:
                if guild_id in self._settings_cache:
                    del self._settings_cache[guild_id]
                # 清除圖片快取
                cache_keys_to_remove = [k for k in self._image_cache.keys() if k.startswith(f"{guild_id}_")]
                for cache_key in cache_keys_to_remove:
                    del self._image_cache[cache_key]
            
            logger.info(f"更新歡迎設定成功：{guild_id}.{key} = {value}")
            return True
            
        except Exception as e:
            logger.error(f"更新歡迎設定失敗：{e}")
            raise ServiceError(
                f"更新歡迎設定失敗：{str(e)}",
                service_name=self.name,
                operation="update_setting"
            )
    
    @handle_errors(log_errors=True)
    async def generate_welcome_image(self, guild_id: int, member: Optional[discord.Member] = None, force_refresh: bool = False) -> WelcomeImage:
        """
        生成歡迎圖片
        
        參數：
            guild_id: 伺服器 ID
            member: 成員物件
            force_refresh: 強制重新生成
            
        返回：
            歡迎圖片
        """
        try:
            # 建立快取鍵
            cache_key = f"{guild_id}_{member.id if member else 'default'}"
            
            # 檢查快取
            if not force_refresh:
                async with self._cache_lock:
                    if cache_key in self._image_cache:
                        return self._image_cache[cache_key]
            
            # 獲取設定
            settings = await self.get_settings(guild_id)
            
            # 建立基礎圖片
            if settings.background_path:
                bg_path = os.path.join(self.bg_dir, settings.background_path)
                if os.path.exists(bg_path):
                    img = Image.open(bg_path).convert("RGBA")
                else:
                    img = Image.new("RGBA", (800, 450), (54, 57, 63, 255))
            else:
                img = Image.new("RGBA", (800, 450), (54, 57, 63, 255))
            
            width, height = img.size
            draw = ImageDraw.Draw(img, "RGBA")
            
            # 處理頭像
            if member:
                avatar_bytes = await self._fetch_avatar_bytes(member.display_avatar.url)
                if avatar_bytes:
                    avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
                    avatar_size = settings.avatar_size or int(0.22 * width)
                    avatar.thumbnail((avatar_size, avatar_size))
                    
                    # 建立圓形遮罩
                    mask = Image.new("L", avatar.size, 0)
                    ImageDraw.Draw(mask).ellipse((0, 0, avatar.size[0], avatar.size[1]), fill=255)
                    avatar.putalpha(mask)
                    
                    # 貼上頭像
                    img.paste(avatar, (settings.avatar_x, settings.avatar_y), avatar)
            
            # 載入字體
            try:
                if os.path.exists(self.default_font):
                    font_title = ImageFont.truetype(self.default_font, settings.title_font_size)
                    font_desc = ImageFont.truetype(self.default_font, settings.desc_font_size)
                else:
                    font_title = ImageFont.load_default()
                    font_desc = ImageFont.load_default()
            except OSError:
                font_title = ImageFont.load_default()
                font_desc = ImageFont.load_default()
            
            # 處理文字
            title_text = self._render_template(settings.title, member)
            desc_text = self._render_template(settings.description, member)
            
            # 計算文字寬度和位置
            avatar_center_x = settings.avatar_x + (settings.avatar_size or int(0.22 * width)) // 2
            
            try:
                title_width = font_title.getlength(title_text)
                desc_width = font_desc.getlength(desc_text)
            except AttributeError:
                # 舊版 PIL 相容性
                try:
                    title_width = font_title.getbbox(title_text)[2]
                    desc_width = font_desc.getbbox(desc_text)[2]
                except (AttributeError, IndexError):
                    title_width = len(title_text) * settings.title_font_size // 2
                    desc_width = len(desc_text) * settings.desc_font_size // 2
            
            # 繪製文字
            draw.text(
                (avatar_center_x - title_width//2, settings.title_y),
                title_text,
                fill=(255, 255, 255, 255),
                font=font_title
            )
            draw.text(
                (avatar_center_x - desc_width//2, settings.description_y),
                desc_text,
                fill=(200, 200, 200, 255),
                font=font_desc
            )
            
            # 建立 WelcomeImage
            welcome_image = WelcomeImage(
                image=img,
                guild_id=guild_id,
                member_id=member.id if member else None,
                cache_key=cache_key
            )
            
            # 快取圖片
            async with self._cache_lock:
                self._image_cache[cache_key] = welcome_image
            
            return welcome_image
            
        except Exception as e:
            logger.error(f"生成歡迎圖片失敗：{e}")
            raise ServiceError(
                f"生成歡迎圖片失敗：{str(e)}",
                service_name=self.name,
                operation="generate_welcome_image"
            )
    
    @handle_errors(log_errors=True)
    async def process_member_join(self, member: discord.Member) -> bool:
        """
        處理成員加入事件
        
        參數：
            member: 加入的成員
            
        返回：
            是否處理成功
        """
        try:
            settings = await self.get_settings(member.guild.id)
            
            # 檢查是否已設定歡迎頻道
            if not settings.channel_id:
                logger.warning(f"伺服器 {member.guild.id} 未設定歡迎頻道")
                return False
            
            # 獲取頻道
            channel = member.guild.get_channel(settings.channel_id)
            if not channel or not isinstance(channel, discord.TextChannel):
                logger.warning(f"找不到歡迎頻道或頻道類型錯誤：{settings.channel_id}")
                return False
            
            # 生成歡迎圖片
            welcome_image = await self.generate_welcome_image(member.guild.id, member)
            
            # 格式化歡迎訊息
            message_text = self._render_template(settings.message, member, channel)
            
            # 發送歡迎訊息
            image_bytes = welcome_image.to_bytes()
            file = discord.File(io.BytesIO(image_bytes), filename="welcome.png")
            
            await channel.send(content=message_text, file=file)
            
            logger.info(f"成功發送歡迎訊息：{member.guild.id} - {member.id}")
            return True
            
        except Exception as e:
            logger.error(f"處理成員加入失敗：{e}")
            return False
    
    @handle_errors(log_errors=True)
    async def update_background(self, guild_id: int, image_path: str) -> bool:
        """
        更新歡迎背景圖片
        
        參數：
            guild_id: 伺服器 ID
            image_path: 圖片路徑
            
        返回：
            是否更新成功
        """
        try:
            # 更新資料庫
            await self.db_manager.execute(
                "INSERT OR REPLACE INTO welcome_backgrounds (guild_id, image_path) VALUES (?, ?)",
                (guild_id, image_path)
            )
            
            # 清除快取
            async with self._cache_lock:
                if guild_id in self._settings_cache:
                    del self._settings_cache[guild_id]
                cache_keys_to_remove = [k for k in self._image_cache.keys() if k.startswith(f"{guild_id}_")]
                for cache_key in cache_keys_to_remove:
                    del self._image_cache[cache_key]
            
            logger.info(f"更新歡迎背景成功：{guild_id} - {image_path}")
            return True
            
        except Exception as e:
            logger.error(f"更新歡迎背景失敗：{e}")
            raise ServiceError(
                f"更新歡迎背景失敗：{str(e)}",
                service_name=self.name,
                operation="update_background"
            )
    
    def clear_cache(self, guild_id: Optional[int] = None) -> None:
        """
        清除快取
        
        參數：
            guild_id: 伺服器 ID，如果為 None 則清除所有快取
        """
        async def _clear():
            async with self._cache_lock:
                if guild_id is None:
                    self._image_cache.clear()
                    self._settings_cache.clear()
                else:
                    # 清除指定伺服器的快取
                    if guild_id in self._settings_cache:
                        del self._settings_cache[guild_id]
                    cache_keys_to_remove = [k for k in self._image_cache.keys() if k.startswith(f"{guild_id}_")]
                    for cache_key in cache_keys_to_remove:
                        del self._image_cache[cache_key]
        
        asyncio.create_task(_clear())
    
    async def _ensure_settings_exist(self, guild_id: int) -> None:
        """確保歡迎設定記錄存在"""
        existing = await self.db_manager.fetchone(
            "SELECT guild_id FROM welcome_settings WHERE guild_id = ?",
            (guild_id,)
        )
        if not existing:
            await self._save_settings(WelcomeSettings(guild_id=guild_id))
    
    async def _save_settings(self, settings: WelcomeSettings) -> None:
        """儲存歡迎設定"""
        await self.db_manager.execute("""
            INSERT OR REPLACE INTO welcome_settings 
            (guild_id, channel_id, title, description, message, avatar_x, avatar_y, 
             title_y, description_y, title_font_size, desc_font_size, avatar_size)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            settings.guild_id,
            settings.channel_id,
            settings.title,
            settings.description,
            settings.message,
            settings.avatar_x,
            settings.avatar_y,
            settings.title_y,
            settings.description_y,
            settings.title_font_size,
            settings.desc_font_size,
            settings.avatar_size
        ))
    
    async def _fetch_avatar_bytes(self, avatar_url: str) -> Optional[bytes]:
        """下載頭像圖片"""
        if not self._session:
            return None
        
        try:
            async with self._session.get(avatar_url) as response:
                if response.status == 200:
                    return await response.read()
        except Exception as e:
            logger.warning(f"下載頭像失敗：{e}")
        
        return None
    
    def _render_template(self, template: str, member: Optional[discord.Member], channel: Optional[discord.TextChannel] = None) -> str:
        """
        渲染訊息範本
        
        參數：
            template: 範本字串
            member: 成員物件
            channel: 頻道物件
            
        返回：
            渲染後的文字
        """
        result = template
        
        try:
            if member:
                result = result.replace("{member}", member.mention)
                result = result.replace("{member.name}", member.name)
                result = result.replace("{member.mention}", member.mention)
                if hasattr(member, 'display_name'):
                    result = result.replace("{member.display_name}", member.display_name)
                
                if member.guild:
                    result = result.replace("{guild}", member.guild.name)
                    result = result.replace("{guild.name}", member.guild.name)
                    
                    # 處理指定頻道
                    import re
                    for chan_id in re.findall(r"{channel:(\d+)}", result):
                        ch = member.guild.get_channel(int(chan_id))
                        result = result.replace(f"{{channel:{chan_id}}}", ch.mention if ch else f"<#{chan_id}>")
                    
                    # 處理表情
                    for emoji_name in re.findall(r"{emoji:([A-Za-z0-9_]+)}", result):
                        emoji_obj = discord.utils.get(member.guild.emojis, name=emoji_name)
                        result = result.replace(f"{{emoji:{emoji_name}}}", str(emoji_obj) if emoji_obj else f":{emoji_name}:")
            
            if channel:
                result = result.replace("{channel}", channel.mention)
                result = result.replace("{channel.name}", channel.name)
        
        except Exception as e:
            logger.warning(f"渲染範本失敗：{e}")
        
        return result