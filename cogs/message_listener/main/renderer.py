"""
訊息渲染器模組
- 負責將訊息渲染為圖片
- 支援表情符號、附件和回覆
- 實現 Discord 風格的聊天界面
基於 creative-prd2-advanced-design.md 的優化設計
"""

import os
import re
import io
import tempfile
import logging
import asyncio
import aiohttp
import datetime as dt
from typing import List, Dict, Tuple, Optional, Any, Union

import discord
from PIL import Image, ImageDraw, ImageFont, ImageColor, ImageFilter

from ..config.config import (
    CHAT_WIDTH, MAX_HEIGHT, AVATAR_SIZE, MESSAGE_PADDING, CONTENT_PADDING,
    DISCORD_COLORS, RENDER_CONFIG, DEFAULT_FONT_SIZE, USERNAME_FONT_SIZE,
    TIMESTAMP_FONT_SIZE, setup_logger
)
from . import utils

# 設定日誌記錄器
logger = setup_logger()

class EnhancedMessageRenderer:
    """
    增強版訊息渲染器類別
    
    功能：
    - 將訊息渲染為 Discord 風格圖片
    - 支援表情符號、附件和回覆
    - 處理中文字型載入和渲染
    - 實現完美的頭像處理和狀態指示器
    - 支援訊息氣泡效果和陰影
    """
    
    def __init__(self):
        """初始化訊息渲染器"""
        # 字型設定
        self.font = None
        self.username_font = None
        self.timestamp_font = None
        self.session = None
        
        # 頭像快取
        self.avatar_cache = {}
        
        # 嘗試載入字型
        self._load_fonts()
    
    def _load_fonts(self):
        """載入字型檔案"""
        try:
            # 使用 utils 中的函數尋找可用的字型檔案
            font_path = utils.find_available_font()
            
            # 載入不同大小的字型
            self.font = ImageFont.truetype(font_path, DEFAULT_FONT_SIZE)
            self.username_font = ImageFont.truetype(font_path, USERNAME_FONT_SIZE)
            self.timestamp_font = ImageFont.truetype(font_path, TIMESTAMP_FONT_SIZE)
            
            logger.info(f"【訊息監聽】成功載入字型：{font_path}")
            
            # 測試字型是否支援中文
            utils.test_font_chinese_support(font_path)
        except Exception as exc:
            logger.error(f"【訊息監聽】載入字型失敗：{exc}")
            # 使用預設字型
            self.font = ImageFont.load_default()
            self.username_font = ImageFont.load_default()
            self.timestamp_font = ImageFont.load_default()
    
    async def get_session(self) -> aiohttp.ClientSession:
        """
        獲取或創建 HTTP 會話
        
        Returns:
            aiohttp.ClientSession: HTTP 會話
        """
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def get_enhanced_avatar(self, user: discord.Member | discord.User) -> Image.Image:
        """
        獲取增強版用戶頭像 (包含狀態指示器和邊框)
        
        Args:
            user: Discord 用戶
            
        Returns:
            Image.Image: 處理後的頭像圖片
        """
        cache_key = f"{user.id}_{getattr(user, 'status', 'offline')}"
        
        # 檢查快取
        if cache_key in self.avatar_cache:
            return self.avatar_cache[cache_key].copy()
        
        try:
            # 獲取基礎頭像
            base_avatar = await self._download_avatar(user)
            
            # 創建帶邊框和狀態指示器的頭像
            enhanced_avatar = self._create_enhanced_avatar(base_avatar, user)
            
            # 快取結果
            self.avatar_cache[cache_key] = enhanced_avatar.copy()
            
            return enhanced_avatar
            
        except Exception as exc:
            logger.error(f"【訊息監聽】獲取增強頭像失敗：{exc}")
            return self._get_default_avatar()
    
    async def _download_avatar(self, user: discord.Member | discord.User) -> Image.Image:
        """
        下載用戶頭像
        
        Args:
            user: Discord 用戶
            
        Returns:
            Image.Image: 原始頭像圖片
        """
        try:
            # 獲取高品質頭像 URL
            avatar_url = user.display_avatar.replace(format="png", size=256).url
            
            # 下載頭像
            session = await self.get_session()
            async with session.get(str(avatar_url)) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    avatar = Image.open(io.BytesIO(data))
                    
                    # 確保為 RGBA 模式
                    if avatar.mode != "RGBA":
                        avatar = avatar.convert("RGBA")
                    
                    return avatar
        except Exception as exc:
            logger.error(f"【訊息監聽】下載頭像失敗：{exc}")
        
        return self._get_default_avatar()
    
    def _create_enhanced_avatar(self, avatar: Image.Image, user: discord.Member | discord.User) -> Image.Image:
        """
        創建增強版頭像 (完美圓形裁剪 + 狀態指示器)
        
        Args:
            avatar: 原始頭像圖片
            user: Discord 用戶
            
        Returns:
            Image.Image: 增強版頭像
        """
        # 調整頭像大小
        avatar = avatar.resize((AVATAR_SIZE, AVATAR_SIZE), Image.Resampling.LANCZOS)
        
        # 創建完美圓形遮罩
        mask = Image.new("L", (AVATAR_SIZE, AVATAR_SIZE), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, AVATAR_SIZE, AVATAR_SIZE), fill=255)
        
        # 應用圓形遮罩
        circular_avatar = Image.new("RGBA", (AVATAR_SIZE, AVATAR_SIZE), (0, 0, 0, 0))
        circular_avatar.paste(avatar, (0, 0))
        circular_avatar.putalpha(mask)
        
        # 添加邊框
        if RENDER_CONFIG["avatar_border_width"] > 0:
            border_color = RENDER_CONFIG["avatar_border_color"]
            bordered_avatar = self._add_avatar_border(circular_avatar, border_color)
        else:
            bordered_avatar = circular_avatar
        
        # 添加狀態指示器 (只對 Member 類型)
        if isinstance(user, discord.Member) and hasattr(user, 'status'):
            final_avatar = self._add_status_indicator(bordered_avatar, user.status)
        else:
            final_avatar = bordered_avatar
        
        return final_avatar
    
    def _add_avatar_border(self, avatar: Image.Image, border_color: Tuple[int, int, int]) -> Image.Image:
        """
        為頭像添加邊框
        
        Args:
            avatar: 頭像圖片
            border_color: 邊框顏色
            
        Returns:
            Image.Image: 帶邊框的頭像
        """
        border_width = RENDER_CONFIG["avatar_border_width"]
        size = AVATAR_SIZE + border_width * 2
        
        # 創建邊框背景
        bordered = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(bordered)
        
        # 繪製邊框圓形
        draw.ellipse(
            (0, 0, size - 1, size - 1),
            fill=border_color + (255,),
            outline=None
        )
        
        # 貼上原始頭像
        bordered.paste(avatar, (border_width, border_width), avatar)
        
        return bordered
    
    def _add_status_indicator(self, avatar: Image.Image, status: discord.Status) -> Image.Image:
        """
        為頭像添加狀態指示器
        
        Args:
            avatar: 頭像圖片
            status: 用戶狀態
            
        Returns:
            Image.Image: 帶狀態指示器的頭像
        """
        # 狀態顏色映射
        status_colors = {
            discord.Status.online: DISCORD_COLORS["online"],
            discord.Status.idle: DISCORD_COLORS["idle"],
            discord.Status.dnd: DISCORD_COLORS["dnd"],
            discord.Status.offline: DISCORD_COLORS["offline"]
        }
        
        status_color = status_colors.get(status, DISCORD_COLORS["offline"])
        indicator_size = RENDER_CONFIG["status_indicator_size"]
        
        # 計算狀態指示器位置 (右下角)
        avatar_size = avatar.size[0]
        indicator_x = avatar_size - indicator_size
        indicator_y = avatar_size - indicator_size
        
        # 在副本上繪製狀態指示器
        result = avatar.copy()
        draw = ImageDraw.Draw(result)
        
        # 繪製狀態指示器背景 (深色邊框)
        draw.ellipse(
            (indicator_x - 1, indicator_y - 1, 
             indicator_x + indicator_size + 1, indicator_y + indicator_size + 1),
            fill=DISCORD_COLORS["main_bg"] + (255,)
        )
        
        # 繪製狀態指示器
        draw.ellipse(
            (indicator_x, indicator_y, 
             indicator_x + indicator_size, indicator_y + indicator_size),
            fill=status_color + (255,)
        )
        
        return result
    
    def _get_default_avatar(self) -> Image.Image:
        """
        獲取預設頭像
        
        Returns:
            Image.Image: 預設頭像
        """
        # 創建灰色圓形預設頭像
        default = Image.new("RGBA", (AVATAR_SIZE, AVATAR_SIZE), (0, 0, 0, 0))
        draw = ImageDraw.Draw(default)
        
        # 繪製灰色圓形
        draw.ellipse(
            (0, 0, AVATAR_SIZE, AVATAR_SIZE),
            fill=(128, 128, 128, 255)
        )
        
        # 繪製預設用戶圖標 (簡化版)
        center = AVATAR_SIZE // 2
        head_radius = AVATAR_SIZE // 6
        body_width = AVATAR_SIZE // 3
        body_height = AVATAR_SIZE // 4
        
        # 頭部
        draw.ellipse(
            (center - head_radius, center - AVATAR_SIZE // 3,
             center + head_radius, center - AVATAR_SIZE // 3 + head_radius * 2),
            fill=(200, 200, 200, 255)
        )
        
        # 身體
        draw.ellipse(
            (center - body_width // 2, center - body_height // 4,
             center + body_width // 2, center + body_height),
            fill=(200, 200, 200, 255)
        )
        
        return default
    
    async def download_attachment(self, attachment: discord.Attachment) -> Image.Image | None:
        """
        下載附件圖片
        
        Args:
            attachment: Discord 附件
            
        Returns:
            Image.Image | None: 附件圖片，如果下載失敗則為 None
        """
        try:
            # 檢查是否為圖片
            if not utils.is_image_attachment(attachment):
                return None
            
            # 下載附件
            session = await self.get_session()
            async with session.get(attachment.url) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    img = Image.open(io.BytesIO(data))
                    
                    # 調整大小，保持比例
                    max_width = CHAT_WIDTH - CONTENT_PADDING - 20
                    if img.width > max_width:
                        ratio = max_width / img.width
                        new_height = int(img.height * ratio)
                        img = img.resize((max_width, new_height))
                    
                    return img
        except Exception as exc:
            utils.log_error_with_context(exc, "下載附件失敗", {"attachment_url": attachment.url})
        
        return None
    
    def format_timestamp(self, timestamp: dt.datetime) -> str:
        """
        格式化時間戳
        
        Args:
            timestamp: 時間戳
            
        Returns:
            str: 格式化後的時間戳
        """
        # 使用 utils 中的格式化函數
        return utils.format_timestamp(timestamp, "default")
    
    async def render_message(
        self, 
        draw: ImageDraw.ImageDraw, 
        message: discord.Message, 
        y_pos: int,
        show_reply: bool = True
    ) -> Tuple[int, Image.Image, Tuple[int, int], List[Tuple[Image.Image, int]]]:
        """
        渲染單個訊息
        
        Args:
            draw: PIL 繪圖物件
            message: Discord 訊息
            y_pos: 起始 Y 座標
            show_reply: 是否顯示回覆
            
        Returns:
            Tuple[int, Image.Image, Tuple[int, int], List[Tuple[Image.Image, int]]]:
                - 新的 Y 座標
                - 背景圖片
                - 頭像位置
                - 附件圖片列表
        """
        # 獲取頭像
        avatar = await self.get_enhanced_avatar(message.author)
        
        # 計算文字寬度的函數
        def get_text_width(text, font):
            return draw.textlength(text, font=font)
        
        # 處理用戶名和時間戳
        username = utils.get_user_display_name(message.author)
        timestamp = self.format_timestamp(message.created_at)
        
        # 處理回覆
        reply_height = 0
        if show_reply and message.reference and isinstance(message.reference.resolved, discord.Message):
            replied_msg = message.reference.resolved
            replied_user = replied_msg.author.display_name
            replied_content = replied_msg.content
            
            # 截斷過長的回覆內容
            if len(replied_content) > 50:
                replied_content = replied_content[:47] + "..."
            
            reply_text = f"回覆 @{replied_user}：{replied_content}"
            reply_width = get_text_width(reply_text, self.timestamp_font)
            
            # 繪製回覆線
            reply_line_start = (CONTENT_PADDING - 20, y_pos + 10)
            reply_line_mid = (CONTENT_PADDING - 10, y_pos + 10)
            reply_line_end = (CONTENT_PADDING - 10, y_pos + 25)
            draw.line([reply_line_start, reply_line_mid, reply_line_end], fill=(114, 118, 125), width=2)
            
            # 繪製回覆文字
            draw.text((CONTENT_PADDING, y_pos + 10), reply_text, fill=(114, 118, 125), font=self.timestamp_font)
            reply_height = 30
        
        # 調整 Y 座標
        y_pos += reply_height
        
        # 繪製用戶名和時間戳
        draw.text((CONTENT_PADDING, y_pos), username, fill=(255, 255, 255), font=self.username_font)
        timestamp_width = get_text_width(timestamp, self.timestamp_font)
        draw.text((CONTENT_PADDING + get_text_width(username, self.username_font) + 10, y_pos + 2), 
                timestamp, fill=(114, 118, 125), font=self.timestamp_font)
        
        # 處理訊息內容
        content = message.content
        if content:
            # 處理外部表情符號
            content = self._sanitize_external_emoji(content, message.guild)
            
            # 分行處理
            y_offset = y_pos + 25
            for line in content.split("\n"):
                draw.text((CONTENT_PADDING, y_offset), line, fill=DISCORD_COLORS["text_primary"], font=self.font)
                y_offset += DEFAULT_FONT_SIZE + 5
            
            # 更新 Y 座標
            y_pos = y_offset
        else:
            # 沒有內容，只有附件
            y_pos += 25
        
        # 處理附件
        attachments = []
        for attachment in message.attachments:
            if utils.is_image_attachment(attachment):
                img = await self.download_attachment(attachment)
                if img:
                    attachments.append((img, y_pos))
                    y_pos += img.height + 10
        
        # 返回結果
        return y_pos, avatar, (10, y_pos - avatar.height), attachments
    
    def _sanitize_external_emoji(self, text: str, guild: discord.Guild | None) -> str:
        """
        處理外部表情符號
        
        Args:
            text: 訊息文字
            guild: Discord 伺服器
            
        Returns:
            str: 處理後的文字
        """
        # 表情符號正則表達式
        pattern = r"<a?:([a-zA-Z0-9_]+):(\d+)>"
        
        def repl(m: re.Match[str]) -> str:
            emoji_name = m.group(1)
            return f":{emoji_name}:"
        
        return re.sub(pattern, repl, text)
    
    async def render_messages(self, messages: List[discord.Message]) -> str | None:
        """
        渲染多個訊息為圖片
        
        Args:
            messages: Discord 訊息列表
            
        Returns:
            str | None: 圖片檔案路徑，如果渲染失敗則為 None
        """
        if not messages:
            return None
            
        try:
            # 按時間排序
            messages = sorted(messages, key=lambda m: m.created_at)
            
            # 創建背景圖片
            bg = Image.new("RGB", (CHAT_WIDTH, MAX_HEIGHT), DISCORD_COLORS["main_bg"])
            draw = ImageDraw.Draw(bg)
            
            # 渲染每個訊息
            y_pos = 10
            avatars = []  # (image, position)
            all_attachments = []  # (image, position)
            
            for i, message in enumerate(messages):
                new_y_pos, avatar, avatar_pos, attachments = await self.render_message(
                    draw, message, y_pos, i > 0
                )
                
                # 添加頭像和附件
                avatars.append((avatar, avatar_pos))
                all_attachments.extend(attachments)
                
                # 更新 Y 座標
                y_pos = new_y_pos + MESSAGE_PADDING
            
            # 裁剪圖片
            final_height = min(y_pos, MAX_HEIGHT)
            bg = bg.crop((0, 0, CHAT_WIDTH, final_height))
            
            # 繪製頭像和附件
            for avatar, pos in avatars:
                bg.paste(avatar, pos, avatar)
            
            for attachment, pos in all_attachments:
                bg.paste(attachment, (CONTENT_PADDING, pos))
            
            # 保存圖片
            path = utils.create_temp_file(suffix=".png", prefix="msg_render_")
            if path:
                bg.save(path)
                return path
            else:
                # 如果創建臨時文件失敗，使用原來的方法
                fd, path = tempfile.mkstemp(suffix=".png")
                os.close(fd)
                bg.save(path)
                return path
        except Exception as exc:
            logger.error(f"【訊息監聽】渲染訊息失敗：{exc}")
            return None 


# 為了向後相容性，提供MessageRenderer別名
MessageRenderer = EnhancedMessageRenderer 