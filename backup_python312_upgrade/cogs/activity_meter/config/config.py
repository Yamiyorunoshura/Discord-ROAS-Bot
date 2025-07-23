"""
活躍度系統模組配置文件
- 定義所有常數、預設值和配置項
"""

import os
from datetime import timezone, timedelta

# 專案根目錄
PROJECT_ROOT = os.environ.get("PROJECT_ROOT", os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

# 資料庫路徑
DBS_DIR = os.path.join(PROJECT_ROOT, "dbs")
ACTIVITY_DB_PATH = os.path.join(DBS_DIR, "activity.db")

# 日誌路徑
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")
ACTIVITY_LOG_PATH = os.path.join(LOGS_DIR, "activity_meter.log")

# 時區設定
TW_TZ = timezone(timedelta(hours=8))

# 活躍度計算常數
ACTIVITY_MAX_SCORE = 100.0       # 最高分數
ACTIVITY_GAIN = 5.0              # 每則訊息增加的分數
ACTIVITY_COOLDOWN = 60           # 訊息冷卻時間（秒）
ACTIVITY_DECAY_AFTER = 3600      # 多久後開始衰減（秒）
ACTIVITY_DECAY_PER_H = 2.0       # 每小時衰減的分數

# 活躍度進度條設定
ACT_BAR_WIDTH = 400              # 進度條寬度
ACT_BAR_HEIGHT = 40              # 進度條高度
ACT_BAR_BG = (30, 30, 30, 255)   # 進度條背景色
ACT_BAR_FILL = (0, 170, 255, 255)# 進度條填充色
ACT_BAR_BORDER = (50, 50, 50, 255)# 進度條邊框色

# 自動播報設定
ACT_REPORT_HOUR = 21             # 自動播報時間（24小時制）

# 字體設定
WELCOME_DEFAULT_FONT = os.path.join(PROJECT_ROOT, "fonts", "NotoSansCJKtc-Regular.otf")

# 日期格式
DAY_FMT = "%Y%m%d"               # 日期格式（用於資料庫）
MONTH_FMT = "%Y%m"               # 月份格式（用於資料庫）

# 權限檢查函數
def is_allowed(inter, command_name):
    """檢查用戶是否有權限執行指定指令"""
    if not inter.guild:
        return False
    member = inter.guild.get_member(inter.user.id)
    if not member:
        return False
    return member.guild_permissions.administrator or member.guild_permissions.manage_guild 