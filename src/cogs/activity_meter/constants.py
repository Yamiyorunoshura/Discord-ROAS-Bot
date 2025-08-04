"""
Activity Meter 模組常數定義

這個檔案包含了活躍度計量器模組中使用的所有常數,
用於替換程式碼中的魔術數字,提高程式碼可讀性和可維護性.
"""

# 時間相關常數
CACHE_EXPIRY_SECONDS = 30  # 快取過期時間(秒)
SECONDS_PER_HOUR = 3600  # 每小時的秒數
PERFORMANCE_CHECK_INTERVAL = 3600  # 性能檢查間隔(秒)

# 時間驗證常數
MAX_HOUR = 23  # 24小時制的最大小時數
MAX_MINUTE = 59  # 最大分鐘數

# 分數相關常數
DEFAULT_MAX_SCORE = 100  # 預設最大分數
MIN_SCORE = 0  # 最小分數

# 測試相關常數
DEFAULT_TEST_RESPONSE_TIMEOUT = 5.0  # 預設測試響應超時時間(秒)
DEFAULT_UI_RESPONSE_TIMEOUT = 2.0  # 預設UI響應超時時間(秒)
TEST_DATA_SIZE = 1000  # 測試資料大小
MIN_ACCURACY_THRESHOLD = 95  # 最小準確率閾值(%)
MIN_SMOOTHNESS_THRESHOLD = 90  # 最小順暢度閾值(%)
MIN_SUCCESS_RATE_THRESHOLD = 80  # 最小成功率閾值(%)

# 動畫和效果相關常數
PULSE_THRESHOLD = 0.5  # 脈動效果閾值
GLOW_THRESHOLD = 0.3  # 發光效果閾值
GRADIENT_COLOR_COUNT = 2  # 漸層顏色數量
MIN_PROGRESS_WIDTH = 4  # 進度條最小寬度
ELLIPSIS_MIN_LENGTH = 3  # 省略號最小長度

# UI限制常數
DISCORD_UI_MAX_COMPONENTS = 25  # Discord UI 最大組件數限制
DISCORD_UI_MAX_ROWS = 5  # Discord UI 最大行數限制
UI_OPTIMIZATION_THRESHOLD = 20  # UI優化觸發閾值

# 圖像相關常數
HIGH_LEVEL_SCORE_THRESHOLD = 76  # 高等級分數閾值

# 顏色相關常數
DEFAULT_TEXT_COLOR = (255, 255, 255)  # 預設文字顏色(白色)
DEFAULT_SHADOW_COLOR = (0, 0, 0, 128)  # 預設陰影顏色(半透明黑色)
