"""
資料同步模組配置 - 重構版本

採用依賴注入模式的配置服務實現
支援協議接口定義和服務註冊
"""

from typing import Any, Protocol


# ────────────────────────────
# 服務接口定義
# ────────────────────────────
class ISyncDataConfig(Protocol):
    """資料同步配置服務接口"""

    @property
    def sync_batch_size(self) -> int:
        """同步批次大小"""
        ...

    @property
    def sync_timeout(self) -> int:
        """同步超時時間(秒)"""
        ...

    @property
    def max_retry_count(self) -> int:
        """最大重試次數"""
        ...

    @property
    def min_sync_interval(self) -> int:
        """最小同步間隔(秒)"""
        ...

    @property
    def log_retention_days(self) -> int:
        """日誌保留天數"""
        ...

    @property
    def sync_types(self) -> dict[str, str]:
        """同步類型定義"""
        ...

    @property
    def error_codes(self) -> dict[str, str]:
        """錯誤代碼定義"""
        ...

    @property
    def default_config(self) -> dict[str, Any]:
        """預設配置"""
        ...

    def get_error_message(self, code: str) -> str:
        """取得錯誤訊息"""
        ...

    def get_sync_type_name(self, sync_type: str) -> str:
        """取得同步類型名稱"""
        ...


class SyncDataConfigService:
    """資料同步配置服務實現"""

    def __init__(self):
        """初始化配置服務"""
        self._sync_batch_size = 100
        self._sync_timeout = 300
        self._max_retry_count = 3
        self._min_sync_interval = 300
        self._log_retention_days = 30

        self._sync_types = {
            "roles": "角色同步",
            "channels": "頻道同步",
            "full": "完整同步",
        }

        self._error_codes = {
            "SYNC_001": "資料庫連接失敗",
            "SYNC_002": "權限不足",
            "SYNC_003": "同步超時",
            "SYNC_004": "數據驗證失敗",
            "SYNC_005": "網路連接錯誤",
            "SYNC_006": "同步已在進行中",
            "SYNC_007": "無效的同步類型",
            "SYNC_008": "伺服器權限不足",
        }

        self._default_config = {
            "auto_sync_enabled": False,
            "auto_sync_interval": 3600,  # 1小時
            "sync_on_startup": True,
            "log_level": "INFO",
        }

    @property
    def sync_batch_size(self) -> int:
        return self._sync_batch_size

    @property
    def sync_timeout(self) -> int:
        return self._sync_timeout

    @property
    def max_retry_count(self) -> int:
        return self._max_retry_count

    @property
    def min_sync_interval(self) -> int:
        return self._min_sync_interval

    @property
    def log_retention_days(self) -> int:
        return self._log_retention_days

    @property
    def sync_types(self) -> dict[str, str]:
        return self._sync_types.copy()

    @property
    def error_codes(self) -> dict[str, str]:
        return self._error_codes.copy()

    @property
    def default_config(self) -> dict[str, Any]:
        return self._default_config.copy()

    def get_error_message(self, code: str) -> str:
        """
        取得錯誤訊息

        Args:
            code: 錯誤代碼

        Returns:
            str: 錯誤訊息
        """
        return self._error_codes.get(code, "未知錯誤")

    def get_sync_type_name(self, sync_type: str) -> str:
        """
        取得同步類型名稱

        Args:
            sync_type: 同步類型

        Returns:
            str: 同步類型名稱
        """
        return self._sync_types.get(sync_type, sync_type)


# ────────────────────────────
# 向後相容的常數和函數
# ────────────────────────────
# 保持向後相容性
_config_service = SyncDataConfigService()

SYNC_BATCH_SIZE = _config_service.sync_batch_size
SYNC_TIMEOUT = _config_service.sync_timeout
MAX_RETRY_COUNT = _config_service.max_retry_count
MIN_SYNC_INTERVAL = _config_service.min_sync_interval
LOG_RETENTION_DAYS = _config_service.log_retention_days
SYNC_TYPES = _config_service.sync_types
ERROR_CODES = _config_service.error_codes
DEFAULT_CONFIG = _config_service.default_config


def get_error_message(code: str) -> str:
    """向後相容的錯誤訊息取得函數"""
    return _config_service.get_error_message(code)


def get_sync_type_name(sync_type: str) -> str:
    """向後相容的同步類型名稱取得函數"""
    return _config_service.get_sync_type_name(sync_type)
