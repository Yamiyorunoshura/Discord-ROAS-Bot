"""
歡迎系統配置服務實現

提供統一的配置管理,支援依賴注入和環境變數覆蓋
"""

import os
from dataclasses import dataclass

from src.cogs.core.logger import setup_module_logger
from src.core.config import get_settings

logger = setup_module_logger("welcome.config")

@dataclass
class WelcomeConfig:
    """歡迎系統配置實現"""

    def __init__(
        self,
        background_dir: str | None = None,
        cache_timeout: int | None = None,
        max_cache_size: int | None = None,
    ):
        """
        初始化配置

        Args:
            background_dir: 背景圖片目錄
            cache_timeout: 快取超時時間(秒)
            max_cache_size: 最大快取大小
        """
        self._background_dir = background_dir or self._get_background_dir()
        self._cache_timeout = cache_timeout or self._get_cache_timeout()
        self._max_cache_size = max_cache_size or self._get_max_cache_size()

        logger.info(
            f"歡迎系統配置初始化完成: background_dir={self._background_dir}, "
            f"cache_timeout={self._cache_timeout}, max_cache_size={self._max_cache_size}"
        )

    @property
    def background_dir(self) -> str:
        """背景圖片目錄"""
        return self._background_dir

    @property
    def cache_timeout(self) -> int:
        """快取超時時間(秒)"""
        return self._cache_timeout

    @property
    def max_cache_size(self) -> int:
        """最大快取大小"""
        return self._max_cache_size

    @property
    def default_backgrounds_dir(self) -> str:
        """默認背景圖片目錄(專案內靜態資源)"""
        settings = get_settings()
        return str(settings.assets_dir / "backgrounds")

    def _get_background_dir(self) -> str:
        """獲取背景圖片目錄"""
        # 使用統一配置系統獲取用戶數據目錄下的背景目錄
        if "WELCOME_BG_DIR" in os.environ:
            return os.environ["WELCOME_BG_DIR"]

        settings = get_settings()
        user_backgrounds_dir = settings.data_dir / "backgrounds"
        user_backgrounds_dir.mkdir(parents=True, exist_ok=True)
        return str(user_backgrounds_dir)

    def _get_cache_timeout(self) -> int:
        """獲取快取超時時間"""
        try:
            return int(os.environ.get("WELCOME_CACHE_TIMEOUT", "3600"))  # 預設1小時
        except ValueError:
            logger.warning("無效的 WELCOME_CACHE_TIMEOUT 值,使用預設值 3600")
            return 3600

    def _get_max_cache_size(self) -> int:
        """獲取最大快取大小"""
        try:
            return int(os.environ.get("WELCOME_MAX_CACHE_SIZE", "50"))  # 預設50個項目
        except ValueError:
            logger.warning("無效的 WELCOME_MAX_CACHE_SIZE 值,使用預設值 50")
            return 50

    def update_config(self, **kwargs) -> None:
        """
        動態更新配置

        Args:
            **kwargs: 要更新的配置項
        """
        for key, value in kwargs.items():
            if hasattr(self, f"_{key}"):
                setattr(self, f"_{key}", value)
                logger.info(f"配置項 {key} 已更新為 {value}")
            else:
                logger.warning(f"未知的配置項: {key}")

    def to_dict(self) -> dict:
        """轉換為字典格式"""
        return {
            "background_dir": self.background_dir,
            "cache_timeout": self.cache_timeout,
            "max_cache_size": self.max_cache_size,
        }
