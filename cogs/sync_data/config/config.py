"""
資料同步模組配置
- 定義同步相關的常數和配置
"""

from typing import Dict, Any

# ────────────────────────────
# 同步配置常數
# ────────────────────────────
# 同步批次大小
SYNC_BATCH_SIZE = 100

# 同步超時時間（秒）
SYNC_TIMEOUT = 300

# 同步重試次數
MAX_RETRY_COUNT = 3

# 同步間隔（防止重複同步的最小間隔，秒）
MIN_SYNC_INTERVAL = 300

# 日誌保留天數
LOG_RETENTION_DAYS = 30

# ────────────────────────────
# 同步類型定義
# ────────────────────────────
SYNC_TYPES = {
    "roles": "角色同步",
    "channels": "頻道同步",
    "full": "完整同步"
}

# ────────────────────────────
# 錯誤代碼定義
# ────────────────────────────
ERROR_CODES = {
    "SYNC_001": "資料庫連接失敗",
    "SYNC_002": "權限不足",
    "SYNC_003": "同步超時",
    "SYNC_004": "數據驗證失敗",
    "SYNC_005": "網路連接錯誤"
}

# ────────────────────────────
# 預設配置
# ────────────────────────────
DEFAULT_CONFIG = {
    "auto_sync_enabled": False,
    "auto_sync_interval": 3600,  # 1小時
    "sync_on_startup": True,
    "log_level": "INFO"
}

def get_error_message(code: str) -> str:
    """
    取得錯誤訊息
    
    Args:
        code: 錯誤代碼
        
    Returns:
        str: 錯誤訊息
    """
    return ERROR_CODES.get(code, "未知錯誤")

def get_sync_type_name(sync_type: str) -> str:
    """
    取得同步類型名稱
    
    Args:
        sync_type: 同步類型
        
    Returns:
        str: 同步類型名稱
    """
    return SYNC_TYPES.get(sync_type, sync_type) 