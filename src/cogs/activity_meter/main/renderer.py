"""
活躍度進度條渲染器 - Phase 4 升級版
- 漸層效果設計
- 等級系統和成就徽章
- 動態效果和個性化主題
- GIF 動畫進度條支援
- 自訂選項與樣式配置
"""

import io
import logging
import math
import random
from enum import Enum
from pathlib import Path
from typing import Any

import discord
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from ..config import config
from ..constants import (
    GLOW_THRESHOLD,
    GRADIENT_COLOR_COUNT,
    HIGH_LEVEL_SCORE_THRESHOLD,
    MIN_PROGRESS_WIDTH,
    PULSE_THRESHOLD,
)

logger = logging.getLogger("activity_meter")

class ActivityLevel(Enum):
    """活躍度等級系統"""

    NEWCOMER = (0, 25, "新手", "🌱", "#9CA3AF")
    ACTIVE = (26, 50, "活躍", "🔥", "#3B82F6")
    VETERAN = (51, 75, "資深", "⭐", "#10B981")
    EXPERT = (76, 90, "專家", "💎", "#F59E0B")
    LEGEND = (91, 100, "傳奇", "👑", "#EF4444")

    def __init__(
        self, min_score: int, max_score: int, name: str, emoji: str, color: str
    ):
        self.min_score = min_score
        self.max_score = max_score
        self.level_name = name
        self.emoji = emoji
        self.color = color

    @classmethod
    def get_level(cls, score: float) -> "ActivityLevel":
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
    活躍度進度條渲染器 - Phase 4 升級版

    新功能:
    - 漸層效果設計
    - 等級系統和徽章
    - 動態效果
    - 個性化主題
    - GIF 動畫進度條
    - 自訂配置選項
    """

    def __init__(self):
        """初始化渲染器"""
        self._font_cache = {}

        # 漸層色彩配置
        self.gradient_colors = {
            (0, 25): [(156, 163, 175), (107, 114, 128)],  # 灰藍
            (26, 50): [(59, 130, 246), (37, 99, 235)],  # 藍色
            (51, 75): [(16, 185, 129), (5, 150, 105)],  # 綠色
            (76, 90): [(245, 158, 11), (217, 119, 6)],  # 黃金
            (91, 100): [(239, 68, 68), (220, 38, 127)],  # 紅紫
        }

        # GIF 動畫配置
        self.gif_config = {
            "frame_count": 30,  # 總幀數
            "duration": 100,  # 每幀持續時間 (毫秒)
            "loop": 0,  # 無限循環
            "animation_styles": {
                "pulse": self._create_pulse_animation,
                "slide": self._create_slide_animation,
                "sparkle": self._create_sparkle_animation,
                "wave": self._create_wave_animation,
                "glow": self._create_glow_animation,
            },
        }

        # 自訂選項配置
        self.custom_options = {
            "show_percentage": True,
            "show_level_badge": True,
            "show_animation": True,
            "animation_style": "pulse",
            "custom_colors": None,
            "custom_text": None,
            "progress_style": "gradient",  # gradient, solid, striped
            "bar_thickness": "normal",  # thin, normal, thick
            "corner_style": "rounded",  # rounded, square, pill
        }

        # 主題配置
        self.themes = {
            ThemeStyle.CLASSIC: {
                "bg_color": (54, 57, 63, 255),
                "border_color": (114, 118, 125),
                "text_color": (255, 255, 255),
                "shadow": True,
                "glow": False,
            },
            ThemeStyle.MODERN: {
                "bg_color": (32, 34, 37, 255),
                "border_color": (79, 84, 92),
                "text_color": (220, 221, 222),
                "shadow": True,
                "glow": True,
            },
            ThemeStyle.NEON: {
                "bg_color": (0, 0, 0, 255),
                "border_color": (0, 255, 255),
                "text_color": (0, 255, 255),
                "shadow": False,
                "glow": True,
            },
            ThemeStyle.MINIMAL: {
                "bg_color": (248, 249, 250, 255),
                "border_color": (209, 213, 219),
                "text_color": (55, 65, 81),
                "shadow": False,
                "glow": False,
            },
            ThemeStyle.GRADIENT: {
                "bg_color": (17, 24, 39, 255),
                "border_color": (75, 85, 99),
                "text_color": (243, 244, 246),
                "shadow": True,
                "glow": True,
            },
        }

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
            if not font_path or not Path(font_path).exists():
                # 嘗試其他字體路徑
                current_file = Path(__file__)
                assets_dir = current_file.parent.parent.parent / "assets" / "fonts"

                font_paths = [
                    assets_dir / "NotoSansCJKtc-Regular.otf",
                    assets_dir / "wqy-microhei.ttc",
                    Path("/System/Library/Fonts/PingFang.ttc"),  # macOS中文字體
                    Path("/System/Library/Fonts/STHeiti Light.ttc"),  # macOS中文字體
                ]

                for path in font_paths:
                    if path.exists():
                        font_path = str(path)
                        break
                else:
                    # 如果都找不到,使用預設字體
                    logger.warning("[活躍度]無法找到中文字體,使用預設字體")
                    return ImageFont.load_default()

            return ImageFont.truetype(font_path, size)

        except Exception as e:
            logger.warning(f"[活躍度]無法載入字體 {font_path},使用預設字體: {e}")
            return ImageFont.load_default()

    def _hex_to_rgb(self, hex_color: str) -> tuple[int, int, int]:
        """將十六進制顏色轉換為 RGB"""
        hex_color = hex_color.lstrip("#")
        return (
            int(hex_color[0:2], 16),
            int(hex_color[2:4], 16),
            int(hex_color[4:6], 16),
        )

    def _create_gradient(
        self, width: int, height: int, colors: list, direction: str = "horizontal"
    ) -> Image.Image:
        """
        創建漸層圖片

        Args:
            width: 寬度
            height: 高度
            colors: 顏色列表 [(r, g, b), ...]
            direction: 方向 ('horizontal' 或 'vertical')
        """
        img = Image.new("RGBA", (width, height))
        draw = ImageDraw.Draw(img)

        if direction == "horizontal":
            for x in range(width):
                # 計算當前位置的顏色
                ratio = x / (width - 1) if width > 1 else 0

                if len(colors) == GRADIENT_COLOR_COUNT:
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

    def _add_glow_effect(
        self, img: Image.Image, _glow_color: tuple[int, int, int] = (255, 255, 255)
    ) -> Image.Image:
        """添加發光效果"""
        # 創建發光圖層
        glow = img.copy()
        glow = glow.filter(ImageFilter.GaussianBlur(radius=3))

        # 合成發光效果
        result = Image.new("RGBA", img.size, (0, 0, 0, 0))
        result.paste(glow, (0, 0))
        result.paste(img, (0, 0), img)

        return result

    def _add_shadow_effect(
        self, img: Image.Image, offset: tuple[int, int] = (2, 2)
    ) -> Image.Image:
        """添加陰影效果"""
        # 創建陰影圖層
        shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(shadow)

        shadow = img.copy()
        shadow = shadow.filter(ImageFilter.GaussianBlur(radius=1))

        # 合成陰影
        result = Image.new("RGBA", img.size, (0, 0, 0, 0))
        result.paste(shadow, offset)
        result.paste(img, (0, 0), img)

        return result

    def _get_progress_colors(
        self, score: float
    ) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
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
        custom_height: int | None = None,
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
        # 初始化設置
        dimensions = self._initialize_dimensions(custom_width, custom_height)
        theme_config = self.themes.get(theme, self.themes[ThemeStyle.MODERN])
        level = ActivityLevel.get_level(score)

        # 創建基礎圖片
        main_img = self._create_base_image(dimensions, theme_config, score, theme, show_effects)

        # 渲染文字
        main_img = self._render_text_on_image(main_img, member_name, score, level,
                                            show_level, theme_config, show_effects, dimensions)

        # 應用特效並組合最終圖片
        final_img = self._apply_effects_and_compose(main_img, level, score, show_effects, dimensions)

        # 轉換為 Discord 檔案
        return self._convert_to_discord_file(final_img, level, theme)

    def _initialize_dimensions(self, custom_width: int | None, custom_height: int | None) -> dict:
        """初始化圖片尺寸"""
        w = custom_width if custom_width is not None else config.ACT_BAR_WIDTH
        h = custom_height if custom_height is not None else config.ACT_BAR_HEIGHT
        return {"w": w, "h": h, "canvas_w": w + 20, "canvas_h": h + 20}

    def _create_base_image(self, dimensions: dict, theme_config: dict, score: float,
                          theme: ThemeStyle, show_effects: bool) -> Image.Image:
        """創建基礎進度條圖片"""
        w, h = dimensions["w"], dimensions["h"]
        main_img = Image.new("RGBA", (w, h), theme_config["bg_color"])
        draw = ImageDraw.Draw(main_img)

        # 繪製圓角邊框
        corner_radius = 8
        draw.rounded_rectangle(
            [(0, 0), (w - 1, h - 1)],
            radius=corner_radius,
            outline=theme_config["border_color"],
            width=2,
        )

        # 繪製進度填充
        self._draw_progress_fill(main_img, score, theme, show_effects, corner_radius, dimensions)

        return main_img

    def _draw_progress_fill(self, main_img: Image.Image, score: float, theme: ThemeStyle,
                           show_effects: bool, corner_radius: int, dimensions: dict):
        """繪製進度條填充"""
        w, h = dimensions["w"], dimensions["h"]
        fill_w = int((w - 8) * score / config.ACTIVITY_MAX_SCORE)

        if fill_w <= MIN_PROGRESS_WIDTH:
            return

        start_color, end_color = self._get_progress_colors(score)

        if theme == ThemeStyle.GRADIENT or show_effects:
            self._apply_gradient_fill(main_img, fill_w, h, corner_radius, start_color, end_color)
        else:
            self._apply_simple_fill(main_img, fill_w, h, corner_radius, start_color)

    def _apply_gradient_fill(self, main_img: Image.Image, fill_w: int, h: int,
                           corner_radius: int, start_color: tuple, end_color: tuple):
        """應用漸層填充"""
        gradient = self._create_gradient(fill_w, h - 8, [start_color, end_color])

        mask = Image.new("L", (fill_w, h - 8), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle(
            [(0, 0), (fill_w - 1, h - 9)], radius=corner_radius - 2, fill=255
        )

        gradient.putalpha(mask)
        main_img.paste(gradient, (4, 4), gradient)

    def _apply_simple_fill(self, main_img: Image.Image, fill_w: int, h: int,
                          corner_radius: int, start_color: tuple):
        """應用簡單填充"""
        draw = ImageDraw.Draw(main_img)
        draw.rounded_rectangle(
            [(4, 4), (fill_w, h - 5)],
            radius=corner_radius - 2,
            fill=start_color,
        )

    def _render_text_on_image(self, main_img: Image.Image, member_name: str, score: float,
                             level, show_level: bool, theme_config: dict,
                             show_effects: bool, dimensions: dict) -> Image.Image:
        """在圖片上渲染文字"""
        w, h = dimensions["w"], dimensions["h"]
        draw = ImageDraw.Draw(main_img)

        # 準備文字
        if show_level:
            txt = f"{level.emoji} {member_name} ‧ {level.level_name} ‧ {score:.1f}/100"
        else:
            txt = f"{member_name} ‧ {score:.1f}/100"

        # 字體設定
        font_size = 16 if show_level else 18
        font = self._get_font(font_size)

        # 計算文字位置
        text_x, text_y = self._calculate_text_position(draw, txt, font, w, h)

        # 繪製陰影
        if theme_config["shadow"] and show_effects:
            draw.text((text_x + 1, text_y + 1), txt, fill=(0, 0, 0, 128), font=font)

        # 繪製主要文字
        draw.text((text_x, text_y), txt, fill=theme_config["text_color"], font=font)

        return main_img

    def _calculate_text_position(self, draw, txt: str, font, w: int, h: int) -> tuple:
        """計算文字位置"""
        try:
            bbox = draw.textbbox((0, 0), txt, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        except (OSError, AttributeError):
            tw, th = 200, 20  # 預設值

        text_x = (w - tw) // 2
        text_y = (h - th) // 2
        return text_x, text_y

    def _apply_effects_and_compose(self, main_img: Image.Image, level, score: float,
                                  show_effects: bool, dimensions: dict) -> Image.Image:
        """應用特效並組合最終圖片"""
        # 基礎特效
        if show_effects:
            main_img = self._apply_basic_effects(main_img)

        # 創建最終畫布
        canvas_w, canvas_h = dimensions["canvas_w"], dimensions["canvas_h"]
        final_img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        final_img.paste(main_img, (10, 10), main_img)

        # 高等級特效
        if score >= HIGH_LEVEL_SCORE_THRESHOLD and show_effects:
            glow_color = self._hex_to_rgb(level.color)
            final_img = self._add_glow_effect(final_img, glow_color)

        return final_img

    def _apply_basic_effects(self, main_img: Image.Image) -> Image.Image:
        """應用基礎特效"""
        theme_config = self.themes.get(ThemeStyle.MODERN, self.themes[ThemeStyle.MODERN])

        if theme_config["glow"]:
            main_img = self._add_glow_effect(main_img)

        if theme_config["shadow"]:
            main_img = self._add_shadow_effect(main_img)

        return main_img

    def _convert_to_discord_file(self, img: Image.Image, level, theme: ThemeStyle) -> discord.File:
        """轉換為 Discord 檔案"""
        buf = io.BytesIO()
        img.save(buf, "PNG")
        buf.seek(0)

        filename = f"activity_{level.level_name.lower()}_{theme.value}.png"
        return discord.File(buf, filename=filename)

    def render_achievement_badge(
        self, achievement_name: str, description: str, icon: str = "🏆"
    ) -> discord.File:
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

        gradient = self._create_gradient(w, h, [(255, 215, 0), (255, 165, 0)])

        # 創建圓角遮罩
        mask = Image.new("L", (w, h), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle([(0, 0), (w - 1, h - 1)], radius=15, fill=255)

        gradient.putalpha(mask)
        img.paste(gradient, (0, 0), gradient)

        # 繪製邊框
        draw.rounded_rectangle(
            [(2, 2), (w - 3, h - 3)], radius=13, outline=(255, 255, 255), width=3
        )

        # 繪製圖示
        icon_font = self._get_font(32)
        icon_bbox = draw.textbbox((0, 0), icon, font=icon_font)
        icon_bbox[2] - icon_bbox[0]
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

    def get_level_info(self, score: float) -> dict[str, Any]:
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
            "current_level": {
                "name": level.level_name,
                "emoji": level.emoji,
                "color": level.color,
                "min_score": level.min_score,
                "max_score": level.max_score,
            },
            "next_level": {
                "name": next_level.level_name if next_level else None,
                "emoji": next_level.emoji if next_level else None,
                "min_score": next_level.min_score if next_level else None,
            }
            if next_level
            else None,
            "progress_to_next": progress_to_next,
            "is_max_level": next_level is None,
        }

    # ========== GIF 動畫功能 ==========

    def render_animated_progress_bar(
        self,
        member_name: str,
        score: float,
        animation_style: str = "pulse",
        theme: ThemeStyle = ThemeStyle.MODERN,
        custom_options: dict[str, Any] | None = None,
    ) -> discord.File:
        """
        渲染動畫 GIF 進度條

        Args:
            member_name: 成員名稱
            score: 活躍度分數
            animation_style: 動畫風格 (pulse, slide, sparkle, wave, glow)
            theme: 主題風格
            custom_options: 自訂選項

        Returns:
            discord.File: 包含 GIF 動畫的 Discord 檔案
        """
        # 合併自訂選項
        options = {**self.custom_options}
        if custom_options:
            options.update(custom_options)

        # 獲取動畫創建函數
        animation_func = self.gif_config["animation_styles"].get(
            animation_style, self._create_pulse_animation
        )

        # 創建動畫幀
        frames = animation_func(member_name, score, theme, options)

        # 保存為 GIF
        buf = io.BytesIO()
        if frames:
            frames[0].save(
                buf,
                format="GIF",
                save_all=True,
                append_images=frames[1:],
                duration=self.gif_config["duration"],
                loop=self.gif_config["loop"],
                optimize=True,
            )
        buf.seek(0)

        level = ActivityLevel.get_level(score)
        filename = f"activity_{level.level_name.lower()}_{animation_style}_animated.gif"
        return discord.File(buf, filename=filename)

    def _create_pulse_animation(
        self, member_name: str, score: float, theme: ThemeStyle, options: dict[str, Any]
    ) -> list[Image.Image]:
        """創建脈動動畫"""
        frames = []
        frame_count = self.gif_config["frame_count"]

        for i in range(frame_count):
            pulse_intensity = (math.sin(2 * math.pi * i / frame_count) + 1) / 2

            # 創建基礎進度條
            frame = self._create_base_frame(member_name, score, theme, options)

            if pulse_intensity > PULSE_THRESHOLD:
                frame = self._apply_pulse_effect(frame, pulse_intensity)

            frames.append(frame)

        return frames

    def _create_slide_animation(
        self, member_name: str, score: float, theme: ThemeStyle, options: dict[str, Any]
    ) -> list[Image.Image]:
        """創建滑動填充動畫"""
        frames = []
        frame_count = self.gif_config["frame_count"]

        for i in range(frame_count):
            # 計算當前進度 (從 0 到實際分數)
            current_progress = (i / (frame_count - 1)) * score

            # 創建該進度的進度條
            frame = self._create_base_frame(
                member_name, current_progress, theme, options
            )
            frames.append(frame)

        return frames

    def _create_sparkle_animation(
        self, member_name: str, score: float, theme: ThemeStyle, options: dict[str, Any]
    ) -> list[Image.Image]:
        """創建閃爍星星動畫"""
        frames = []
        frame_count = self.gif_config["frame_count"]

        # 創建基礎進度條
        base_frame = self._create_base_frame(member_name, score, theme, options)

        for i in range(frame_count):
            frame = base_frame.copy()

            # 在進度條上隨機添加閃爍點
            if score > 0:
                self._add_sparkle_effects(frame, score, i)

            frames.append(frame)

        return frames

    def _create_wave_animation(
        self, member_name: str, score: float, theme: ThemeStyle, options: dict[str, Any]
    ) -> list[Image.Image]:
        """創建波浪動畫"""
        frames = []
        frame_count = self.gif_config["frame_count"]

        for i in range(frame_count):
            # 創建帶波浪效果的進度條
            frame = self._create_wave_frame(member_name, score, theme, options, i)
            frames.append(frame)

        return frames

    def _create_glow_animation(
        self, member_name: str, score: float, theme: ThemeStyle, options: dict[str, Any]
    ) -> list[Image.Image]:
        """創建發光動畫"""
        frames = []
        frame_count = self.gif_config["frame_count"]

        for i in range(frame_count):
            glow_intensity = (math.sin(2 * math.pi * i / frame_count) + 1) / 2

            # 創建基礎進度條
            frame = self._create_base_frame(member_name, score, theme, options)

            # 添加發光效果
            if glow_intensity > GLOW_THRESHOLD:
                frame = self._apply_glow_animation(frame, glow_intensity)

            frames.append(frame)

        return frames

    def _create_base_frame(
        self, member_name: str, score: float, theme: ThemeStyle, options: dict[str, Any]
    ) -> Image.Image:
        """創建基礎進度條幀"""
        # 重用現有的靜態進度條邏輯, 但返回 Image 而不是 File
        w = config.ACT_BAR_WIDTH
        h = config.ACT_BAR_HEIGHT

        theme_config = self.themes.get(theme, self.themes[ThemeStyle.MODERN])
        level = ActivityLevel.get_level(score)

        # 創建圖片
        canvas_w, canvas_h = w + 20, h + 20
        img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        main_img = Image.new("RGBA", (w, h), theme_config["bg_color"])
        draw = ImageDraw.Draw(main_img)

        # 繪製邊框
        corner_radius = 8
        draw.rounded_rectangle(
            [(0, 0), (w - 1, h - 1)],
            radius=corner_radius,
            outline=theme_config["border_color"],
            width=2,
        )

        # 計算填充寬度
        fill_w = int((w - 8) * score / config.ACTIVITY_MAX_SCORE)

        if fill_w > MIN_PROGRESS_WIDTH:
            start_color, end_color = self._get_progress_colors(score)

            # 根據進度樣式創建填充
            if options.get("progress_style") == "gradient":
                gradient = self._create_gradient(
                    fill_w, h - 8, [start_color, end_color]
                )
                mask = Image.new("L", (fill_w, h - 8), 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.rounded_rectangle(
                    [(0, 0), (fill_w - 1, h - 9)], radius=corner_radius - 2, fill=255
                )
                gradient.putalpha(mask)
                main_img.paste(gradient, (4, 4), gradient)
            else:
                draw.rounded_rectangle(
                    [(4, 4), (fill_w, h - 5)],
                    radius=corner_radius - 2,
                    fill=start_color,
                )

        # 添加文字
        if options.get("show_level_badge", True):
            txt = f"{level.emoji} {member_name}"
            if options.get("show_percentage", True):
                txt += f" ‧ {level.level_name} ‧ {score:.1f}/100"
            else:
                txt += f" ‧ {level.level_name}"
        else:
            txt = f"{member_name}"
            if options.get("show_percentage", True):
                txt += f" ‧ {score:.1f}/100"

        # 自訂文字覆蓋
        if options.get("custom_text"):
            txt = options["custom_text"].format(
                name=member_name, score=score, level=level.level_name
            )

        font = self._get_font(16)
        try:
            bbox = draw.textbbox((0, 0), txt, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        except (OSError, AttributeError):
            tw, th = 200, 20

        text_x = (w - tw) // 2
        text_y = (h - th) // 2

        # 文字陰影
        if theme_config["shadow"]:
            draw.text((text_x + 1, text_y + 1), txt, fill=(0, 0, 0, 128), font=font)

        draw.text((text_x, text_y), txt, fill=theme_config["text_color"], font=font)

        # 將主圖片放到畫布上
        img.paste(main_img, (10, 10), main_img)

        return img

    def _apply_pulse_effect(self, img: Image.Image, intensity: float) -> Image.Image:
        """應用脈動效果"""
        # 簡單的亮度調整實現脈動
        enhancer = Image.new("RGBA", img.size, (255, 255, 255, int(30 * intensity)))
        result = Image.alpha_composite(img.convert("RGBA"), enhancer)
        return result

    def _add_sparkle_effects(
        self, img: Image.Image, score: float, frame_idx: int
    ) -> None:
        """添加閃爍效果"""
        draw = ImageDraw.Draw(img)
        w, h = img.size

        # 隨機生成閃爍點
        random.seed(frame_idx)  # 使用 frame_idx 作為種子確保一致性
        sparkle_count = min(5, int(score / 20))

        for _ in range(sparkle_count):
            x = random.randint(10, w - 10)
            y = random.randint(10, h - 10)
            size = random.randint(2, 4)

            # 繪製閃爍點
            draw.ellipse(
                [(x - size, y - size), (x + size, y + size)], fill=(255, 255, 255, 200)
            )

    def _create_wave_frame(
        self,
        member_name: str,
        score: float,
        theme: ThemeStyle,
        options: dict[str, Any],
        _frame_idx: int,
    ) -> Image.Image:
        """創建波浪效果幀"""
        base_frame = self._create_base_frame(member_name, score, theme, options)

        # 簡化實現: 只返回基礎幀, 實際波浪效果需要更複雜的像素操作
        return base_frame

    def _apply_glow_animation(self, img: Image.Image, intensity: float) -> Image.Image:
        """應用發光動畫效果"""
        # 創建發光效果
        glow = img.copy()
        glow = glow.filter(ImageFilter.GaussianBlur(radius=int(2 + intensity * 3)))

        # 調整發光強度
        enhancer = Image.new("RGBA", img.size, (255, 255, 255, int(20 * intensity)))
        glow = Image.alpha_composite(glow.convert("RGBA"), enhancer)

        # 合成最終圖像
        result = Image.alpha_composite(glow, img.convert("RGBA"))
        return result

    def update_custom_options(self, options: dict[str, Any]) -> None:
        """更新自訂選項"""
        self.custom_options.update(options)

    def get_available_animations(self) -> list[str]:
        """獲取可用的動畫風格列表"""
        return list(self.gif_config["animation_styles"].keys())

    def get_custom_options(self) -> dict[str, Any]:
        """獲取當前自訂選項"""
        return self.custom_options.copy()
