"""
訊息監聽系統模組配置文件
- 定義所有常數、預設值和配置項
"""

import logging
import os
from datetime import timedelta, timezone
from pathlib import Path

# 使用統一配置系統獲取路徑
from src.core.config import get_settings

# 獲取配置實例
_settings = get_settings()

# 資料庫路徑 - 使用配置系統
MESSAGE_DB_PATH = str(_settings.get_database_path("message"))

# 日誌路徑 - 使用配置系統
MESSAGE_LOG_PATH = str(_settings.get_log_file_path("message_listener"))

# 時區設定
TW_TZ = timezone(timedelta(hours=8))

# 訊息保留設定
MESSAGE_RETENTION_DAYS = 30  # 訊息保留天數

# 訊息搜尋設定
MAX_SEARCH_RESULTS = 50  # 最大搜尋結果數

# 訊息緩存設定
MAX_CACHED_MESSAGES = 10  # 每頻道最大緩存訊息數
MAX_CACHE_TIME = 600  # 緩存最大時間 (10分鐘)

# 圖片渲染設定
CHAT_WIDTH = 800  # 聊天框寬度
MAX_HEIGHT = 2000  # 最大高度
AVATAR_SIZE = 40  # 頭像大小
MESSAGE_PADDING = 8  # 訊息間距 (優化為 8px)
CONTENT_PADDING = 62  # 內容左側留白 (優化為 62px)

# Discord 官方顏色系統 (更新為 2024 年最新的 Discord 風格)
DISCORD_COLORS = {
    # 主要背景顏色 (Discord 2024 新版本)
    "main_bg": (49, 51, 56),  # #313338 - Discord 新版主背景
    "message_area": (56, 58, 64),  # #383a40 - 訊息區域背景
    "message_hover": (67, 70, 77),  # #43464d - 訊息懸停背景
    "chat_input": (64, 68, 75),  # #40444b - 聊天輸入框背景
    # 文字顏色 (更新為新版本)
    "text_primary": (242, 243, 245),  # #f2f3f5 - 主要文字 (更亮)
    "text_secondary": (181, 186, 193),  # #b5bac1 - 次要文字
    "text_muted": (148, 155, 164),  # #949ba4 - 靜音文字
    "text_link": (0, 168, 252),  # #00a8fc - 連結文字
    # 用戶名稱顏色 (更新色彩)
    "username": (255, 255, 255),  # #ffffff - 用戶名稱
    "username_hover": (219, 222, 225),  # #dbdee1 - 用戶名稱懸停
    "timestamp": (163, 166, 170),  # #a3a6aa - 時間戳
    # 特殊元素顏色 (新版本風格)
    "embed_bg": (43, 45, 49),  # #2b2d31 - 嵌入背景
    "embed_border": (35, 39, 42),  # #23272a - 嵌入邊框
    "embed_accent": (88, 101, 242),  # #5865f2 - 嵌入重點色
    "mention": (88, 101, 242),  # #5865f2 - 提及顏色
    "mention_bg": (88, 101, 242, 51),  # #5865f2 20% opacity - 提及背景
    # 狀態顏色 (Discord 官方狀態色)
    "online": (35, 165, 90),  # #23a55a - 在線狀態
    "idle": (247, 168, 4),  # #f7a804 - 閒置狀態
    "dnd": (237, 66, 69),  # #ed4245 - 勿擾狀態
    "offline": (128, 132, 142),  # #80848e - 離線狀態
    "streaming": (89, 54, 149),  # #593695 - 直播狀態
    # 訊息類型顏色
    "system_message": (142, 146, 151),  # #8e9297 - 系統訊息
    "bot_tag": (88, 101, 242),  # #5865f2 - 機器人標籤
    "nitro_pink": (255, 115, 250),  # #ff73fa - Nitro 粉色
    # 互動元素顏色
    "button_primary": (88, 101, 242),  # #5865f2 - 主要按鈕
    "button_secondary": (75, 81, 89),  # #4b5159 - 次要按鈕
    "button_success": (35, 165, 90),  # #23a55a - 成功按鈕
    "button_danger": (237, 66, 69),  # #ed4245 - 危險按鈕
    # 新增的現代化元素
    "divider": (79, 84, 92),  # #4f545c - 分隔線
    "tooltip_bg": (24, 25, 28),  # #18191c - 工具提示背景
    "modal_bg": (43, 45, 49),  # #2b2d31 - 模態框背景
    "scrollbar": (30, 31, 34),  # #1e1f22 - 滾動條
    "selection": (88, 101, 242, 76),  # #5865f2 30% opacity - 選擇背景
}

# 向後兼容的顏色常數
BG_COLOR = DISCORD_COLORS["main_bg"]
TEXT_COLOR = DISCORD_COLORS["text_primary"]
EMBED_COLOR = DISCORD_COLORS["embed_bg"]

# 新增的渲染配置 (更新為現代化風格)
RENDER_CONFIG = {
    # 訊息氣泡設定 (更現代化的設計)
    "bubble_radius": 6,  # 訊息氣泡圓角半徑 (更小的圓角)
    "bubble_padding": 16,  # 氣泡內邊距 (更寬敞)
    "bubble_margin": 2,  # 氣泡外邊距 (更緊湊)
    # 頭像設定 (更精緻的頭像)
    "avatar_border_width": 0,  # 頭像邊框寬度 (無邊框,更簡潔)
    "avatar_border_color": (79, 84, 92),  # 頭像邊框顏色
    "status_indicator_size": 14,  # 狀態指示器大小 (稍大)
    "status_indicator_border": 3,  # 狀態指示器邊框寬度
    # 排版設定 (更好的可讀性)
    "line_height": 1.4,  # 行高倍數 (更好的行距)
    "paragraph_spacing": 12,  # 段落間距 (更大的間距)
    "max_content_width": 600,  # 最大內容寬度 (更寬)
    "username_spacing": 4,  # 用戶名與訊息間距
    # 陰影效果 (更現代的陰影)
    "text_shadow_offset": (0, 1),  # 文字陰影偏移 (更自然)
    "text_shadow_color": (0, 0, 0, 64),  # 文字陰影顏色 (更淡)
    "enable_text_shadow": False,  # 是否啟用文字陰影 (關閉,更簡潔)
    "message_shadow": True,  # 訊息區域陰影
    # 動畫和效果 (更流暢的交互)
    "hover_transition": 0.2,  # 懸停過渡時間 (更慢更自然)
    "enable_hover_effects": True,  # 是否啟用懸停效果
    "hover_lift": 2,  # 懸停提升像素
    # 時間戳格式 (更現代的格式)
    "timestamp_format": "HH:mm",  # 時間戳格式
    "show_date_separator": True,  # 是否顯示日期分隔符
    "date_format": "MM月dd日",  # 日期格式 (更簡潔)
    "relative_time": True,  # 使用相對時間 (今天、昨天等)
    # 現代化的訊息佈局
    "compact_mode": False,  # 緊湊模式
    "show_avatars": True,  # 顯示頭像
    "group_messages": True,  # 群組相同用戶的訊息
    "message_grouping_time": 300,  # 訊息群組時間間隔 (5分鐘)
    # 新增的視覺效果
    "gradient_usernames": True,  # 用戶名漸變效果
    "animated_typing": True,  # 動態打字效果
    "emoji_size_multiplier": 1.2,  # 表情符號大小倍數
    "code_block_theme": "discord",  # 代碼塊主題
}

# 字型設定 - 使用統一配置系統
from src.core.config import get_settings
_settings = get_settings()
FONT_PATH = str(_settings.assets_dir / "fonts")
DEFAULT_FONT = "arial.ttf"
DEFAULT_FONT_SIZE = 14
USERNAME_FONT_SIZE = 16
TIMESTAMP_FONT_SIZE = 12

# 字型下載 URL
FONT_DOWNLOAD_URLS = {
    "NotoSansTC-Regular.otf": "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/TraditionalChinese/NotoSansTC-Regular.otf",
    "NotoSansSC-Regular.otf": "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansSC-Regular.otf",
    "wqy-microhei.ttc": "https://github.com/anthonyfok/fonts-wqy-microhei/raw/master/wqy-microhei.ttc",
}

# 中文字型列表 (按優先順序排序)
CHINESE_FONTS = [
    "NotoSansTC-Regular.otf",  # Google Noto Sans TC (繁體中文)
    "NotoSansSC-Regular.otf",  # Google Noto Sans SC (簡體中文)
    "wqy-microhei.ttc",  # 文泉驛微米黑 (Linux)
    "wqy-zenhei.ttc",  # 文泉驛正黑 (Linux)
    "msyh.ttc",  # 微軟雅黑 (Windows)
    "msjh.ttc",  # 微軟正黑體 (Windows)
    "simhei.ttf",  # 黑體 (Windows)
    "simsun.ttc",  # 宋體 (Windows)
    "mingliu.ttc",  # 細明體 (Windows)
    "AppleGothic.ttf",  # Apple Gothic (macOS)
    "DroidSansFallback.ttf",  # Droid Sans Fallback (Android)
]


# 日誌設定
def setup_logger():
    """設定日誌記錄器"""
    logger = logging.getLogger("message_listener")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    # 檔案處理器
    file_handler = logging.FileHandler(MESSAGE_LOG_PATH, mode="a", encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    )

    # 控制台處理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    )

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# 權限檢查函數
def is_allowed(inter, command_name):
    """檢查用戶是否有權限執行指定指令"""
    if not inter.guild:
        return False
    member = inter.guild.get_member(inter.user.id)
    if not member:
        return False
    return (
        member.guild_permissions.administrator or member.guild_permissions.manage_guild
    )
