"""
活躍度進度條渲染器 - Phase 3 升級版
- 漸層效果設計
- 等級系統和成就徽章
- 動態效果和個性化主題
"""

import io
import logging
import math
from typing import Tuple, Optional, Union, Any, Dict
from functools import lru_cache
from enum import Enum
import os # Added for font loading

import discord
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from ..config import config

logger = logging.getLogger("activity_meter")

class ActivityLevel(Enum):
    """活躍度等級系統"""
    NEWCOMER = (0, 25, "新手", "🌱", "#9CA3AF")
    ACTIVE = (26, 50, "活躍", "🔥", "#3B82F6")
    VETERAN = (51, 75, "資深", "⭐", "#10B981")
    EXPERT = (76, 90, "專家", "💎", "#F59E0B")
    LEGEND = (91, 100, "傳奇", "👑", "#EF4444")
    
    def __init__(self, min_score: int, max_score: int, name: str, emoji: str, color: str):
        self.min_score = min_score
        self.max_score = max_score
        self.level_name = name
        self.emoji = emoji
        self.color = color
    
    @classmethod
    def get_level(cls, score: float) -> 'ActivityLevel':
        """根據分數獲取等級"""
        for level in cls:
            if level.min_score <= score <= level.max_score:
                return level
        return cls.NEWCOMER

class ThemeStyle(Enum):
    """主題風格"""
    CLASSIC = "classic"
    MODERN = "modern"
    NEON = "neon"
    MINIMAL = "minimal"
    GRADIENT = "gradient"

class ActivityRenderer:
    """
    活躍度進度條渲染器 - Phase 3 升級版
    
    新功能：
    - 漸層效果設計
    - 等級系統和徽章
    - 動態效果
    - 個性化主題
    """
    
    def __init__(self):
        """初始化渲染器"""
        self._font_cache = {}
        
        # 漸層色彩配置
        self.gradient_colors = {
            (0, 25): [(156, 163, 175), (107, 114, 128)],    # 灰藍
            (26, 50): [(59, 130, 246), (37, 99, 235)],     # 藍色
            (51, 75): [(16, 185, 129), (5, 150, 105)],     # 綠色
            (76, 90): [(245, 158, 11), (217, 119, 6)],     # 黃金
            (91, 100): [(239, 68, 68), (220, 38, 127)]     # 紅紫
        }
        
        # 主題配置
        self.themes = {
            ThemeStyle.CLASSIC: {
                'bg_color': (54, 57, 63, 255),
                'border_color': (114, 118, 125),
                'text_color': (255, 255, 255),
                'shadow': True,
                'glow': False
            },
            ThemeStyle.MODERN: {
                'bg_color': (32, 34, 37, 255),
                'border_color': (79, 84, 92),
                'text_color': (220, 221, 222),
                'shadow': True,
                'glow': True
            },
            ThemeStyle.NEON: {
                'bg_color': (0, 0, 0, 255),
                'border_color': (0, 255, 255),
                'text_color': (0, 255, 255),
                'shadow': False,
                'glow': True
            },
            ThemeStyle.MINIMAL: {
                'bg_color': (248, 249, 250, 255),
                'border_color': (209, 213, 219),
                'text_color': (55, 65, 81),
                'shadow': False,
                'glow': False
            },
            ThemeStyle.GRADIENT: {
                'bg_color': (17, 24, 39, 255),
                'border_color': (75, 85, 99),
                'text_color': (243, 244, 246),
                'shadow': True,
                'glow': True
            }
        }
    
    @lru_cache(maxsize=8)
    def _get_font(self, size: int = 18) -> Any:
        """
        獲取指定大小的字體
        
        Args:
            size: 字體大小
            
        Returns:
            Any: 字體物件 (PIL.ImageFont)
        """
        try:
            # 使用Activity Meter模組的字體配置
            font_path = config.WELCOME_DEFAULT_FONT
            if not font_path or not os.path.exists(font_path):
                # 嘗試其他字體路徑
                font_paths = [
                    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "fonts", "NotoSansCJKtc-Regular.otf"),
                    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "fonts", "wqy-microhei.ttc"),
                    "/System/Library/Fonts/PingFang.ttc",  # macOS中文字體
                    "/System/Library/Fonts/STHeiti Light.ttc",  # macOS中文字體
                ]
                
                for path in font_paths:
                    if os.path.exists(path):
                        font_path = path
                        break
                else:
                    # 如果都找不到，使用預設字體
                    logger.warning(f"【活躍度】無法找到中文字體，使用預設字體")
                    return ImageFont.load_default()
            
            return ImageFont.truetype(font_path, size)
            
        except Exception as e:
            logger.warning(f"【活躍度】無法載入字體 {font_path}，使用預設字體: {e}")
            return ImageFont.load_default()
    
    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """將十六進制顏色轉換為 RGB"""
        hex_color = hex_color.lstrip('#')
        return (
            int(hex_color[0:2], 16),
            int(hex_color[2:4], 16),
            int(hex_color[4:6], 16)
        )
    
    def _create_gradient(self, width: int, height: int, colors: list, direction: str = 'horizontal') -> Image.Image:
        """
        創建漸層圖片
        
        Args:
            width: 寬度
            height: 高度
            colors: 顏色列表 [(r, g, b), ...]
            direction: 方向 ('horizontal' 或 'vertical')
        """
        img = Image.new('RGBA', (width, height))
        draw = ImageDraw.Draw(img)
        
        if direction == 'horizontal':
            for x in range(width):
                # 計算當前位置的顏色
                ratio = x / (width - 1) if width > 1 else 0
                
                if len(colors) == 2:
                    # 兩色漸層
                    r = int(colors[0][0] + (colors[1][0] - colors[0][0]) * ratio)
                    g = int(colors[0][1] + (colors[1][1] - colors[0][1]) * ratio)
                    b = int(colors[0][2] + (colors[1][2] - colors[0][2]) * ratio)
                else:
                    # 多色漸層
                    segment = ratio * (len(colors) - 1)
                    idx = int(segment)
                    local_ratio = segment - idx
                    
                    if idx >= len(colors) - 1:
                        r, g, b = colors[-1]
                    else:
                        c1, c2 = colors[idx], colors[idx + 1]
                        r = int(c1[0] + (c2[0] - c1[0]) * local_ratio)
                        g = int(c1[1] + (c2[1] - c1[1]) * local_ratio)
                        b = int(c1[2] + (c2[2] - c1[2]) * local_ratio)
                
                draw.line([(x, 0), (x, height)], fill=(r, g, b, 255))
        
        return img
    
    def _add_glow_effect(self, img: Image.Image, glow_color: Tuple[int, int, int] = (255, 255, 255)) -> Image.Image:
        """添加發光效果"""
        # 創建發光圖層
        glow = img.copy()
        glow = glow.filter(ImageFilter.GaussianBlur(radius=3))
        
        # 合成發光效果
        result = Image.new('RGBA', img.size, (0, 0, 0, 0))
        result.paste(glow, (0, 0))
        result.paste(img, (0, 0), img)
        
        return result
    
    def _add_shadow_effect(self, img: Image.Image, offset: Tuple[int, int] = (2, 2)) -> Image.Image:
        """添加陰影效果"""
        # 創建陰影圖層
        shadow = Image.new('RGBA', img.size, (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow)
        
        # 繪製陰影（簡化版）
        shadow = img.copy()
        shadow = shadow.filter(ImageFilter.GaussianBlur(radius=1))
        
        # 合成陰影
        result = Image.new('RGBA', img.size, (0, 0, 0, 0))
        result.paste(shadow, offset)
        result.paste(img, (0, 0), img)
        
        return result
    
    def _get_progress_colors(self, score: float) -> Tuple[Tuple[int, int, int], Tuple[int, int, int]]:
        """根據分數獲取漸層顏色"""
        for (min_score, max_score), colors in self.gradient_colors.items():
            if min_score <= score <= max_score:
                return colors[0], colors[1]
        
        # 預設顏色
        return (156, 163, 175), (107, 114, 128)
    
    def render_progress_bar(
        self, 
        member_name: str, 
        score: float, 
        theme: ThemeStyle = ThemeStyle.MODERN,
        show_level: bool = True,
        show_effects: bool = True,
        custom_width: int | None = None,
        custom_height: int | None = None
    ) -> discord.File:
        """
        渲染升級版活躍度進度條圖片
        
        Args:
            member_name: 成員名稱
            score: 活躍度分數
            theme: 主題風格
            show_level: 是否顯示等級
            show_effects: 是否顯示特效
            custom_width: 自定義寬度
            custom_height: 自定義高度
            
        Returns:
            discord.File: 包含進度條圖片的 Discord 檔案
        """
        # 設定圖片尺寸
        w = custom_width if custom_width is not None else config.ACT_BAR_WIDTH
        h = custom_height if custom_height is not None else config.ACT_BAR_HEIGHT
        
        # 獲取主題配置
        theme_config = self.themes.get(theme, self.themes[ThemeStyle.MODERN])
        
        # 獲取等級資訊
        level = ActivityLevel.get_level(score)
        
        # 創建新圖片 (更大尺寸以容納特效)
        canvas_w, canvas_h = w + 20, h + 20
        img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        
        # 創建主要進度條圖片
        main_img = Image.new("RGBA", (w, h), theme_config['bg_color'])
        draw = ImageDraw.Draw(main_img)
        
        # 繪製圓角邊框
        corner_radius = 8
        draw.rounded_rectangle(
            [(0, 0), (w - 1, h - 1)], 
            radius=corner_radius,
            outline=theme_config['border_color'],
            width=2
        )
        
        # 計算填充寬度
        fill_w = int((w - 8) * score / config.ACTIVITY_MAX_SCORE)
        
        if fill_w > 4:  # 確保有足夠空間繪製
            # 獲取漸層顏色
            start_color, end_color = self._get_progress_colors(score)
            
            # 創建漸層填充
            if theme == ThemeStyle.GRADIENT or show_effects:
                gradient = self._create_gradient(fill_w, h - 8, [start_color, end_color])
                
                # 創建圓角遮罩
                mask = Image.new('L', (fill_w, h - 8), 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.rounded_rectangle(
                    [(0, 0), (fill_w - 1, h - 9)], 
                    radius=corner_radius - 2, 
                    fill=255
                )
                
                # 應用遮罩
                gradient.putalpha(mask)
                main_img.paste(gradient, (4, 4), gradient)
            else:
                # 簡單填充
                draw.rounded_rectangle(
                    [(4, 4), (fill_w, h - 5)], 
                    radius=corner_radius - 2,
                    fill=start_color
                )
        
        # 準備文字
        if show_level:
            txt = f"{level.emoji} {member_name} ‧ {level.level_name} ‧ {score:.1f}/100"
        else:
            txt = f"{member_name} ‧ {score:.1f}/100"
        
        # 字體設定
        font_size = 16 if show_level else 18
        font = self._get_font(font_size)
        
        # 計算文字尺寸和位置
        try:
            bbox = draw.textbbox((0, 0), txt, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        except:
            tw, th = 200, 20  # 預設值
        
        text_x = (w - tw) // 2
        text_y = (h - th) // 2
        
        # 繪製文字陰影（如果啟用）
        if theme_config['shadow'] and show_effects:
            draw.text(
                (text_x + 1, text_y + 1), 
                txt, 
                fill=(0, 0, 0, 128), 
                font=font
            )
        
        # 繪製主要文字
        draw.text(
            (text_x, text_y), 
            txt, 
            fill=theme_config['text_color'], 
            font=font
        )
        
        # 添加特效
        if show_effects:
            if theme_config['glow']:
                main_img = self._add_glow_effect(main_img)
            
            if theme_config['shadow']:
                main_img = self._add_shadow_effect(main_img)
        
        # 將主圖片放置到畫布中央
        img.paste(main_img, (10, 10), main_img)
        
        # 如果是高等級，添加額外效果
        if score >= 76 and show_effects:
            # 添加光暈效果
            glow_color = self._hex_to_rgb(level.color)
            img = self._add_glow_effect(img, glow_color)
        
        # 轉換為 Discord 檔案
        buf = io.BytesIO()
        img.save(buf, "PNG")
        buf.seek(0)
        
        filename = f"activity_{level.level_name.lower()}_{theme.value}.png"
        return discord.File(buf, filename=filename)
    
    def render_achievement_badge(self, achievement_name: str, description: str, icon: str = "🏆") -> discord.File:
        """
        渲染成就徽章
        
        Args:
            achievement_name: 成就名稱
            description: 成就描述
            icon: 成就圖示
            
        Returns:
            discord.File: 包含徽章圖片的 Discord 檔案
        """
        # 徽章尺寸
        w, h = 300, 120
        
        # 創建徽章圖片
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # 繪製徽章背景（金色漸層）
        gradient = self._create_gradient(w, h, [(255, 215, 0), (255, 165, 0)])
        
        # 創建圓角遮罩
        mask = Image.new('L', (w, h), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle([(0, 0), (w-1, h-1)], radius=15, fill=255)
        
        gradient.putalpha(mask)
        img.paste(gradient, (0, 0), gradient)
        
        # 繪製邊框
        draw.rounded_rectangle([(2, 2), (w-3, h-3)], radius=13, outline=(255, 255, 255), width=3)
        
        # 繪製圖示
        icon_font = self._get_font(32)
        icon_bbox = draw.textbbox((0, 0), icon, font=icon_font)
        icon_w = icon_bbox[2] - icon_bbox[0]
        draw.text((20, 20), icon, fill=(255, 255, 255), font=icon_font)
        
        # 繪製成就名稱
        name_font = self._get_font(18)
        draw.text((70, 25), achievement_name, fill=(255, 255, 255), font=name_font)
        
        # 繪製描述
        desc_font = self._get_font(14)
        draw.text((70, 55), description, fill=(255, 255, 255, 200), font=desc_font)
        
        # 添加發光效果
        img = self._add_glow_effect(img)
        
        # 轉換為 Discord 檔案
        buf = io.BytesIO()
        img.save(buf, "PNG")
        buf.seek(0)
        
        return discord.File(buf, filename="achievement.png")
    
    def get_level_info(self, score: float) -> Dict[str, Any]:
        """
        獲取等級資訊
        
        Args:
            score: 活躍度分數
            
        Returns:
            Dict: 等級資訊
        """
        level = ActivityLevel.get_level(score)
        
        # 計算到下一等級的進度
        next_level = None
        progress_to_next = 0.0
        
        for lvl in ActivityLevel:
            if lvl.min_score > score:
                next_level = lvl
                break
        
        if next_level:
            current_range = level.max_score - level.min_score + 1
            current_progress = score - level.min_score
            progress_to_next = (current_progress / current_range) * 100
        
        return {
            'current_level': {
                'name': level.level_name,
                'emoji': level.emoji,
                'color': level.color,
                'min_score': level.min_score,
                'max_score': level.max_score
            },
            'next_level': {
                'name': next_level.level_name if next_level else None,
                'emoji': next_level.emoji if next_level else None,
                'min_score': next_level.min_score if next_level else None
            } if next_level else None,
            'progress_to_next': progress_to_next,
            'is_max_level': next_level is None
        } 