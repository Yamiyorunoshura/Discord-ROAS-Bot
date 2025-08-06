"""
歡迎系統快取模組

此模組負責管理歡迎圖片的快取,避免重複生成相同的圖片
"""

import io
import logging
import time

logger = logging.getLogger("welcome")


class WelcomeCache:
    """歡迎圖片快取管理類別"""

    def __init__(self, timeout: int = 3600, max_size: int = 50):
        """
        初始化快取管理器

        Args:
            timeout: 快取過期時間(秒)
            max_size: 最大快取數量
        """
        self.timeout = timeout
        self.max_size = max_size
        self._cache: dict[
            int, tuple[float, io.BytesIO]
        ] = {}  # guild_id -> (timestamp, image)

    def get(self, guild_id: int) -> io.BytesIO | None:
        """
        從快取中取得圖片

        Args:
            guild_id: Discord 伺服器 ID

        Returns:
            io.BytesIO | None: 快取的圖片,如果不存在或已過期則為 None
        """
        if guild_id not in self._cache:
            return None

        timestamp, image = self._cache[guild_id]
        current_time = time.time()

        # 檢查是否過期
        if current_time - timestamp > self.timeout:
            del self._cache[guild_id]
            return None

        image.seek(0)
        image_copy = io.BytesIO(image.getvalue())
        return image_copy

    def set(self, guild_id: int, image: io.BytesIO) -> None:
        """
        將圖片加入快取

        Args:
            guild_id: Discord 伺服器 ID
            image: 圖片資料
        """
        # 檢查快取大小,如果超過最大值則清除最舊的項目
        if len(self._cache) >= self.max_size:
            oldest_guild_id = None
            oldest_time = float("inf")

            for gid, (timestamp, _) in self._cache.items():
                if timestamp < oldest_time:
                    oldest_time = timestamp
                    oldest_guild_id = gid

            if oldest_guild_id is not None:
                del self._cache[oldest_guild_id]

        # 複製一份圖片資料,避免外部修改
        image.seek(0)
        image_copy = io.BytesIO(image.getvalue())

        # 加入快取
        self._cache[guild_id] = (time.time(), image_copy)

    def clear(self, guild_id: int | None = None) -> None:
        """
        清除快取

        Args:
            guild_id: 要清除的伺服器 ID,如果為 None 則清除所有快取
        """
        if guild_id is None:
            self._cache.clear()
            logger.debug("已清除所有歡迎圖片快取")
        elif guild_id in self._cache:
            del self._cache[guild_id]
            logger.debug(f"已清除伺服器 {guild_id} 的歡迎圖片快取")

    def cleanup(self) -> None:
        """清除所有過期的快取項目"""
        current_time = time.time()
        expired_guilds = [
            guild_id
            for guild_id, (timestamp, _) in self._cache.items()
            if current_time - timestamp > self.timeout
        ]

        for guild_id in expired_guilds:
            del self._cache[guild_id]

        if expired_guilds:
            logger.debug(f"已清除 {len(expired_guilds)} 個過期的歡迎圖片快取")
