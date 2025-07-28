"""
歡迎系統配置模組

此模組包含歡迎系統的所有常數、預設值和配置項目
"""

import os
from pathlib import Path

# 字體配置 - 使用專案結構的字體路徑
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
WELCOME_FONTS_DIR = str(PROJECT_ROOT / "src" / "assets" / "fonts")
WELCOME_DEFAULT_FONT = "NotoSansCJKtc-Regular.otf"

# 日誌配置
LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"
LOG_MAX_SIZE = 2 * 1024 * 1024  # 2MB
LOG_BACKUP_COUNT = 2

# 預設設定
DEFAULT_SETTINGS = {
    "channel_id": None,
    "title": "歡迎 {member.name}!",
    "description": "很高興見到你～",
    "message": "歡迎 {member.mention} 加入 {guild.name}!",
    "avatar_x": 30,
    "avatar_y": 80,
    "title_y": 60,
    "description_y": 120,
    "title_font_size": 36,
    "desc_font_size": 22,
    "avatar_size": None,
}

# 圖片生成相關設定
DEFAULT_BG_SIZE = (600, 240)
DEFAULT_BG_COLOR = (47, 49, 54)  # Discord 深灰色
DEFAULT_TEXT_COLOR = (255, 255, 255)  # 白色
DEFAULT_AVATAR_SIZE = 80

# 字型相關設定
DEFAULT_FONT_PATH = os.path.join(WELCOME_FONTS_DIR, WELCOME_DEFAULT_FONT)

# 快取設定
CACHE_TIMEOUT = 3600  # 1小時
MAX_CACHE_SIZE = 50  # 最多快取50個伺服器的圖片


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
