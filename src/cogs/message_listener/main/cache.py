"""
訊息緩存模組
- 負責管理訊息緩存
- 提供批次處理機制
- 實現超時處理邏輯
"""

import time
from collections import defaultdict

import discord

from ..config.config import MAX_CACHE_TIME, MAX_CACHED_MESSAGES


class MessageCache:
    """
    訊息緩存類別

    功能:
    - 緩存各頻道的訊息
    - 提供批次處理機制
    - 實現超時處理邏輯
    """

    def __init__(self):
        """初始化訊息緩存"""
        # 頻道ID -> 訊息列表
        self._cache: dict[int, list[discord.Message]] = defaultdict(list)
        # 頻道ID -> 最早訊息時間戳
        self._timestamps: dict[int, float] = {}

    def add_message(self, message: discord.Message) -> bool:
        """
        添加訊息到緩存

        Args:
            message: Discord 訊息

        Returns:
            bool: 是否需要立即處理
        """
        channel_id = message.channel.id

        # 添加訊息到緩存
        self._cache[channel_id].append(message)

        # 更新時間戳
        if channel_id not in self._timestamps:
            self._timestamps[channel_id] = time.time()

        # 檢查是否需要立即處理
        return self.should_process(channel_id)

    def should_process(self, channel_id: int) -> bool:
        """
        檢查是否應該處理該頻道的訊息

        Args:
            channel_id: 頻道ID

        Returns:
            bool: 是否應該處理
        """
        # 檢查緩存是否為空
        if channel_id not in self._cache or not self._cache[channel_id]:
            return False

        # 檢查是否達到最大緩存數量
        if len(self._cache[channel_id]) >= MAX_CACHED_MESSAGES:
            return True

        # 檢查是否超過最大緩存時間
        current_time = time.time()
        return bool(
            channel_id in self._timestamps
            and current_time - self._timestamps[channel_id] >= MAX_CACHE_TIME
        )

    def get_messages(self, channel_id: int) -> list[discord.Message]:
        """
        取得頻道的緩存訊息

        Args:
            channel_id: 頻道ID

        Returns:
            List[discord.Message]: 訊息列表
        """
        return self._cache.get(channel_id, [])

    def clear_channel(self, channel_id: int):
        """
        清空頻道的緩存

        Args:
            channel_id: 頻道ID
        """
        if channel_id in self._cache:
            del self._cache[channel_id]

        if channel_id in self._timestamps:
            del self._timestamps[channel_id]

    def check_all_channels(self) -> list[int]:
        """
        檢查所有頻道,返回需要處理的頻道ID列表

        Returns:
            List[int]: 需要處理的頻道ID列表
        """
        current_time = time.time()
        channels_to_process = []

        for channel_id in list(self._cache.keys()):
            # 檢查是否達到最大緩存數量
            if len(self._cache[channel_id]) >= MAX_CACHED_MESSAGES:
                channels_to_process.append(channel_id)
                continue

            # 檢查是否超過最大緩存時間
            if (
                channel_id in self._timestamps
                and current_time - self._timestamps[channel_id] >= MAX_CACHE_TIME
            ):
                channels_to_process.append(channel_id)
                continue

        return channels_to_process
