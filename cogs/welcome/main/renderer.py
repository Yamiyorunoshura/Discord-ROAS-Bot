"""
歡迎系統圖片渲染模組

此模組負責生成歡迎圖片，包括背景、頭像和文字的處理
基於 creative-prd2-advanced-design.md 的設計方案重構
"""

import os
import io
import asyncio
import logging
import aiohttp
from typing import Dict, Any, Optional, Tuple, List
from PIL import Image, ImageDraw, ImageFont
import discord
from dataclasses import dataclass
from enum import Enum

from ..config.config import (
    DEFAULT_BG_SIZE,
    DEFAULT_BG_COLOR,
    DEFAULT_TEXT_COLOR,
    DEFAULT_AVATAR_SIZE,
    DEFAULT_FONT_PATH
)

logger = logging.getLogger("welcome")


class TemplateStyle(Enum):
    """歡迎模板風格枚舉"""
    DEFAULT = "default"
    MINIMAL = "minimal"
    NEON = "neon"
    ELEGANT = "elegant"
    GAMING = "gaming"


@dataclass
class LayoutConfig:
    """佈局配置數據類"""
    canvas_size: Tuple[int, int]
    avatar_position: Tuple[int, int]
    avatar_size: int
    title_position: Tuple[int, int]
    title_font_size: int
    description_position: Tuple[int, int]
    description_font_size: int
    decorative_elements: List[Dict[str, Any]]


@dataclass
class WelcomeTemplate:
    """歡迎模板基類"""
    name: str
    background_color: Tuple[int, int, int, int]
    text_color: Tuple[int, int, int, int]
    accent_color: Tuple[int, int, int, int]
    
    def get_layout(self) -> LayoutConfig:
        """獲取佈局配置"""
        raise NotImplementedError


class DefaultTemplate(WelcomeTemplate):
    """默認歡迎模板 - Discord 風格"""
    
    def __init__(self):
        super().__init__(
            name="default",
            background_color=(54, 57, 63, 255),  # Discord 深色背景
            text_color=(255, 255, 255, 255),
            accent_color=(88, 101, 242, 255)  # Discord Blurple
        )
    
    def get_layout(self) -> LayoutConfig:
        return LayoutConfig(
            canvas_size=(800, 300),
            avatar_position=(50, 50),
            avatar_size=200,
            title_position=(270, 80),
            title_font_size=36,
            description_position=(270, 130),
            description_font_size=22,
            decorative_elements=[
                {
                    "type": "line",
                    "start": (270, 110),
                    "end": (750, 110),
                    "color": self.accent_color,
                    "width": 2
                },
                {
                    "type": "circle",
                    "center": (700, 80),
                    "radius": 30,
                    "color": (*self.accent_color[:3], 76),  # 30% 透明度
                    "filled": True
                }
            ]
        )


class MinimalTemplate(WelcomeTemplate):
    """簡約歡迎模板"""
    
    def __init__(self):
        super().__init__(
            name="minimal",
            background_color=(240, 240, 240, 255),
            text_color=(51, 51, 51, 255),
            accent_color=(100, 100, 100, 255)
        )
    
    def get_layout(self) -> LayoutConfig:
        return LayoutConfig(
            canvas_size=(600, 240),
            avatar_position=(30, 30),
            avatar_size=180,
            title_position=(230, 60),
            title_font_size=28,
            description_position=(230, 100),
            description_font_size=18,
            decorative_elements=[]
        )


class NeonTemplate(WelcomeTemplate):
    """霓虹歡迎模板"""
    
    def __init__(self):
        super().__init__(
            name="neon",
            background_color=(44, 47, 51, 255),
            text_color=(255, 255, 255, 255),
            accent_color=(0, 255, 136, 255)
        )
    
    def get_layout(self) -> LayoutConfig:
        return LayoutConfig(
            canvas_size=(900, 350),
            avatar_position=(60, 60),
            avatar_size=230,
            title_position=(320, 90),
            title_font_size=42,
            description_position=(320, 150),
            description_font_size=26,
            decorative_elements=[
                {
                    "type": "glow_line",
                    "start": (320, 130),
                    "end": (850, 130),
                    "color": self.accent_color,
                    "width": 3,
                    "glow_radius": 5
                }
            ]
        )


class AvatarDownloader:
    """智能頭像下載器"""
    
    def __init__(self):
        self.session = None
        self.cache = {}
        self.retry_config = {
            "max_retries": 3,
            "backoff_factor": 2,
            "timeout": 10
        }
    
    async def get_session(self) -> aiohttp.ClientSession:
        """獲取或創建 HTTP 會話"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def get_avatar(self, user: discord.Member) -> Image.Image:
        """
        獲取用戶頭像
        
        Args:
            user: Discord 成員物件
            
        Returns:
            Image.Image: 處理後的頭像圖片
        """
        cache_key = f"avatar_{user.id}_{user.avatar.key if user.avatar else 'default'}"
        
        if cache_key in self.cache:
            return self.cache[cache_key].copy()
        
        # 嘗試下載頭像
        for attempt in range(self.retry_config["max_retries"]):
            try:
                # 嘗試不同格式和大小的頭像
                avatar_urls = [
                    user.display_avatar.replace(format="png", size=256).url,
                    user.display_avatar.replace(format="jpg", size=256).url,
                    user.display_avatar.replace(format="webp", size=256).url,
                    user.display_avatar.replace(format="png", size=128).url,  # 降級到更小尺寸
                ]
                
                for url in avatar_urls:
                    try:
                        avatar_data = await self.download_with_retry(url)
                        
                        if avatar_data:
                            # 處理頭像
                            avatar_image = self.process_avatar(avatar_data)
                            
                            # 緩存結果
                            self.cache[cache_key] = avatar_image.copy()
                            logger.info(f"成功下載並處理頭像：用戶 {user.id}")
                            return avatar_image
                    except Exception as e:
                        logger.warning(f"嘗試下載頭像格式失敗 {url}: {e}")
                        continue
                    
            except Exception as e:
                logger.warning(f"頭像下載嘗試 {attempt + 1} 失敗: {e}")
                if attempt == self.retry_config["max_retries"] - 1:
                    # 最後一次嘗試失敗，使用默認頭像
                    logger.error(f"所有頭像下載嘗試都失敗，使用默認頭像：用戶 {user.id}")
                    default_avatar = self.get_default_avatar()
                    self.cache[cache_key] = default_avatar.copy()
                    return default_avatar
                
                # 指數退避
                await asyncio.sleep(self.retry_config["backoff_factor"] ** attempt)
        
        # 如果所有嘗試都失敗，返回默認頭像
        logger.error(f"無法獲取用戶頭像，使用默認頭像：用戶 {user.id}")
        default_avatar = self.get_default_avatar()
        self.cache[cache_key] = default_avatar.copy()
        return default_avatar
    
    async def download_with_retry(self, url: str) -> bytes | None:
        """
        帶重試機制的下載
        
        Args:
            url: 下載 URL
            
        Returns:
            bytes | None: 下載的數據，失敗時返回 None
        """
        session = await self.get_session()
        
        for attempt in range(self.retry_config["max_retries"]):
            try:
                timeout = aiohttp.ClientTimeout(total=self.retry_config["timeout"])
                async with session.get(url, timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.read()
                        if len(data) > 0:  # 確保下載的數據不為空
                            return data
                        else:
                            logger.warning(f"下載的數據為空：{url}")
                    else:
                        logger.warning(f"頭像下載失敗：HTTP {response.status} - {url}")
                        
            except asyncio.TimeoutError:
                logger.warning(f"頭像下載超時（嘗試 {attempt + 1}）：{url}")
            except Exception as e:
                logger.warning(f"頭像下載錯誤（嘗試 {attempt + 1}）: {e} - {url}")
            
            # 如果不是最後一次嘗試，等待後重試
            if attempt < self.retry_config["max_retries"] - 1:
                await asyncio.sleep(self.retry_config["backoff_factor"] ** attempt)
        
        return None
    
    def process_avatar(self, avatar_data: bytes) -> Image.Image:
        """
        處理頭像 - 圓形裁剪、尺寸調整
        
        Args:
            avatar_data: 頭像二進制數據
            
        Returns:
            Image.Image: 處理後的頭像
        """
        try:
            image = Image.open(io.BytesIO(avatar_data))
            
            # 轉換為RGBA模式
            image = image.convert("RGBA")
            
            # 調整大小
            image = image.resize((256, 256), Image.Resampling.LANCZOS)
            
            # 創建圓形遮罩
            mask = Image.new("L", (256, 256), 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, 256, 256), fill=255)
            
            # 應用遮罩
            output = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
            output.paste(image, (0, 0))
            output.putalpha(mask)
            
            return output
            
        except Exception as e:
            logger.error(f"頭像處理失敗: {e}")
            return self.get_default_avatar()
    
    def get_default_avatar(self) -> Image.Image:
        """
        獲取默認頭像
        
        Returns:
            Image.Image: 默認頭像
        """
        # 創建一個簡單的默認頭像
        avatar = Image.new("RGBA", (256, 256), (128, 128, 128, 255))
        draw = ImageDraw.Draw(avatar)
        
        # 繪製一個簡單的用戶圖標
        # 頭部
        draw.ellipse((96, 64, 160, 128), fill=(200, 200, 200, 255))
        # 身體
        draw.ellipse((76, 140, 180, 220), fill=(200, 200, 200, 255))
        
        # 創建圓形遮罩
        mask = Image.new("L", (256, 256), 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.ellipse((0, 0, 256, 256), fill=255)
        
        # 應用遮罩
        output = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
        output.paste(avatar, (0, 0))
        output.putalpha(mask)
        
        return output
    
    async def close(self):
        """關閉會話"""
        if self.session and not self.session.closed:
            await self.session.close()


class LayoutCalculator:
    """佈局計算器"""
    
    def __init__(self):
        self.aspect_ratios = {
            "16:9": (16, 9),
            "4:3": (4, 3),
            "1:1": (1, 1)
        }
    
    def calculate_layout(self, template: WelcomeTemplate, username: str, 
                        guild_name: str, aspect_ratio: str = "16:9") -> LayoutConfig:
        """
        計算佈局
        
        Args:
            template: 歡迎模板
            username: 用戶名
            guild_name: 伺服器名稱
            aspect_ratio: 寬高比
            
        Returns:
            LayoutConfig: 佈局配置
        """
        base_layout = template.get_layout()
        
        # 根據寬高比調整畫布大小
        if aspect_ratio in self.aspect_ratios:
            ratio_w, ratio_h = self.aspect_ratios[aspect_ratio]
            base_width = base_layout.canvas_size[0]
            new_height = int(base_width * ratio_h / ratio_w)
            
            # 限制在合理範圍內
            new_height = max(240, min(new_height, 480))
            base_layout.canvas_size = (base_width, new_height)
        
        # 根據文字長度調整位置
        text_length_factor = len(username) + len(guild_name)
        if text_length_factor > 30:  # 文字較長時調整佈局
            base_layout.title_font_size = max(24, base_layout.title_font_size - 4)
            base_layout.description_font_size = max(16, base_layout.description_font_size - 2)
        
        return base_layout


class FontManager:
    """字體管理器"""
    
    def __init__(self):
        self.font_cache = {}
        self.font_fallback_chain = [
            "fonts/NotoSansCJKtc-Regular.otf",
            "fonts/wqy-microhei.ttc",
            DEFAULT_FONT_PATH
        ]
    
    def get_font(self, size: int):
        """
        獲取字體
        
        Args:
            size: 字體大小
            
        Returns:
            字體物件
        """
        cache_key = f"font_{size}"
        
        if cache_key not in self.font_cache:
            font = self._load_font_with_fallback(size)
            self.font_cache[cache_key] = font
        
        return self.font_cache[cache_key]
    
    def _load_font_with_fallback(self, size: int):
        """
        使用回退鏈加載字體
        
        Args:
            size: 字體大小
            
        Returns:
            字體物件
        """
        for font_path in self.font_fallback_chain:
            try:
                if os.path.exists(font_path):
                    font = ImageFont.truetype(font_path, size)
                    logger.info(f"成功加載字體: {font_path}")
                    return font
            except Exception as e:
                logger.warning(f"字體加載失敗 {font_path}: {e}")
                continue
        
        # 所有字體都失敗，使用默認字體
        logger.warning("所有字體加載失敗，使用默認字體")
        return ImageFont.load_default()


class TemplateManager:
    """模板管理器"""
    
    def __init__(self):
        self.templates = {
            TemplateStyle.DEFAULT: DefaultTemplate(),
            TemplateStyle.MINIMAL: MinimalTemplate(),
            TemplateStyle.NEON: NeonTemplate(),
        }
    
    def get_template(self, style: TemplateStyle) -> WelcomeTemplate:
        """
        獲取指定風格的模板
        
        Args:
            style: 模板風格
            
        Returns:
            WelcomeTemplate: 歡迎模板
        """
        return self.templates.get(style, self.templates[TemplateStyle.DEFAULT])


class WelcomeRenderer:
    """歡迎圖片渲染器，負責生成歡迎圖片"""
    
    def __init__(self, welcome_bg_dir: str):
        """
        初始化渲染器
        
        Args:
            welcome_bg_dir: 背景圖片目錄
        """
        self.welcome_bg_dir = welcome_bg_dir
        self.avatar_downloader = AvatarDownloader()
        self.layout_calculator = LayoutCalculator()
        self.font_manager = FontManager()
        self.template_manager = TemplateManager()
    
    async def generate_welcome_image(
        self,
        member: discord.Member,
        settings: Dict[str, Any],
        bg_path: str | None = None,
        template_style: TemplateStyle = TemplateStyle.DEFAULT
    ) -> io.BytesIO | None:
        """
        生成歡迎圖片
        
        Args:
            member: Discord 成員物件
            settings: 歡迎訊息設定
            bg_path: 背景圖片路徑，如果為 None 則使用預設背景
            template_style: 模板風格
            
        Returns:
            io.BytesIO | None: 圖片的二進位資料流，如果失敗則為 None
        """
        try:
            # 獲取模板
            template = self.template_manager.get_template(template_style)
            
            # 計算佈局
            layout = self.layout_calculator.calculate_layout(
                template, member.display_name, member.guild.name
            )
            
            # 創建畫布
            canvas = self._create_canvas(layout, template, bg_path)
            
            # 獲取頭像
            avatar = await self.avatar_downloader.get_avatar(member)
            avatar = avatar.resize((layout.avatar_size, layout.avatar_size), Image.Resampling.LANCZOS)
            
            # 貼上頭像
            canvas.paste(avatar, layout.avatar_position, avatar)
            
            # 繪製文字
            self._draw_text(canvas, layout, template, member, settings)
            
            # 繪製裝飾元素
            self._draw_decorative_elements(canvas, layout)
            
            # 儲存為 BytesIO
            buffer = io.BytesIO()
            canvas.save(buffer, format="PNG")
            buffer.seek(0)
            return buffer
            
        except Exception as exc:
            logger.error("生成歡迎圖片時發生錯誤", exc_info=True)
            return None
    
    def _create_canvas(self, layout: LayoutConfig, template: WelcomeTemplate, 
                      bg_path: str | None) -> Image.Image:
        """
        創建畫布
        
        Args:
            layout: 佈局配置
            template: 歡迎模板
            bg_path: 背景圖片路徑
            
        Returns:
            Image.Image: 畫布
        """
        if bg_path and os.path.exists(bg_path):
            try:
                bg = Image.open(bg_path).convert("RGBA")
                bg = bg.resize(layout.canvas_size, Image.Resampling.LANCZOS)
                return bg
            except Exception as e:
                logger.warning(f"背景圖片加載失敗: {e}")
        
        # 使用模板背景色
        return Image.new("RGBA", layout.canvas_size, template.background_color)
    
    def _draw_text(self, canvas: Image.Image, layout: LayoutConfig, 
                  template: WelcomeTemplate, member: discord.Member, 
                  settings: Dict[str, Any]):
        """
        繪製文字
        
        Args:
            canvas: 畫布
            layout: 佈局配置
            template: 歡迎模板
            member: Discord 成員
            settings: 設定
        """
        draw = ImageDraw.Draw(canvas)
        
        # 繪製標題
        title = settings.get("title", "歡迎！").format(member=member, guild=member.guild)
        title_font = self.font_manager.get_font(layout.title_font_size)
        
        # 添加文字陰影
        shadow_offset = 2
        draw.text(
            (layout.title_position[0] + shadow_offset, layout.title_position[1] + shadow_offset),
            title,
            font=title_font,
            fill=(0, 0, 0, 128)  # 半透明黑色陰影
        )
        draw.text(
            layout.title_position,
            title,
            font=title_font,
            fill=template.text_color
        )
        
        # 繪製描述
        description = settings.get("description", "歡迎加入！").format(member=member, guild=member.guild)
        desc_font = self.font_manager.get_font(layout.description_font_size)
        
        # 添加文字陰影
        draw.text(
            (layout.description_position[0] + shadow_offset, layout.description_position[1] + shadow_offset),
            description,
            font=desc_font,
            fill=(0, 0, 0, 128)  # 半透明黑色陰影
        )
        draw.text(
            layout.description_position,
            description,
            font=desc_font,
            fill=template.text_color
        )
    
    def _draw_decorative_elements(self, canvas: Image.Image, layout: LayoutConfig):
        """
        繪製裝飾元素
        
        Args:
            canvas: 畫布
            layout: 佈局配置
        """
        draw = ImageDraw.Draw(canvas)
        
        for element in layout.decorative_elements:
            element_type = element.get("type")
            
            if element_type == "line":
                draw.line(
                    [element["start"], element["end"]],
                    fill=element["color"],
                    width=element.get("width", 1)
                )
            elif element_type == "circle":
                center = element["center"]
                radius = element["radius"]
                bbox = (
                    center[0] - radius,
                    center[1] - radius,
                    center[0] + radius,
                    center[1] + radius
                )
                if element.get("filled", False):
                    draw.ellipse(bbox, fill=element["color"])
                else:
                    draw.ellipse(bbox, outline=element["color"], width=element.get("width", 1))
            elif element_type == "glow_line":
                # 霓虹發光線條效果
                start, end = element["start"], element["end"]
                color = element["color"]
                width = element.get("width", 3)
                glow_radius = element.get("glow_radius", 5)
                
                # 繪製發光效果
                for i in range(glow_radius, 0, -1):
                    alpha = int(255 * (glow_radius - i) / glow_radius * 0.3)
                    glow_color = (*color[:3], alpha)
                    draw.line([start, end], fill=glow_color, width=width + i * 2)
                
                # 繪製主線條
                draw.line([start, end], fill=color, width=width)
    
    def render_message(
        self, 
        member: discord.Member, 
        guild: discord.Guild, 
        channel: discord.TextChannel | None, 
        msg_template: str
    ) -> str:
        """
        渲染歡迎訊息文字
        
        Args:
            member: Discord 成員物件
            guild: Discord 伺服器物件
            channel: Discord 頻道物件
            msg_template: 訊息範本
            
        Returns:
            str: 渲染後的訊息
        """
        try:
            # 基本變數替換
            msg = msg_template.format(
                member=member,
                guild=guild,
                channel=channel
            )
            
            # 表情符號替換
            def emoji_replacer(match):
                emoji_name = match.group(1)
                emoji = discord.utils.get(guild.emojis, name=emoji_name)
                return str(emoji) if emoji else f":{emoji_name}:"
            
            import re
            msg = re.sub(r':(\w+):', emoji_replacer, msg)
            
            return msg
            
        except Exception as exc:
            logger.error("渲染歡迎訊息時發生錯誤", exc_info=True)
            return msg_template
    
    async def close(self):
        """關閉渲染器"""
        await self.avatar_downloader.close() 