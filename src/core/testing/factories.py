"""
🧪 測試資料工廠
提供生成測試資料的工廠函數
"""

import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

# import dpytest  # Temporarily commented out due to installation issues


class TestDataFactory:
    """測試資料工廠類別"""

    @staticmethod
    def create_guild_data(
        guild_id: int = 12345,
        name: str = "測試伺服器",
        member_count: int = 100,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        創建伺服器測試資料

        Args:
            guild_id: 伺服器 ID
            name: 伺服器名稱
            member_count: 成員數量
            **kwargs: 其他屬性

        Returns:
            伺服器資料字典
        """
        return {
            "guild_id": guild_id,
            "guild_name": name,
            "owner_id": kwargs.get("owner_id", 11111),
            "member_count": member_count,
            "channel_count": kwargs.get("channel_count", 5),
            "role_count": kwargs.get("role_count", 3),
            "created_at": kwargs.get("created_at", time.time()),
            "last_updated": kwargs.get("last_updated", time.time()),
        }

    @staticmethod
    def create_user_data(
        user_id: int = 67890, username: str = "測試用戶", **kwargs: Any
    ) -> dict[str, Any]:
        """
        創建用戶測試資料

        Args:
            user_id: 用戶 ID
            username: 用戶名稱
            **kwargs: 其他屬性

        Returns:
            用戶資料字典
        """
        return {
            "user_id": user_id,
            "username": username,
            "discriminator": kwargs.get("discriminator", "0001"),
            "bot": kwargs.get("bot", False),
            "created_at": kwargs.get("created_at", time.time()),
        }

    @staticmethod
    def create_message_data(
        message_id: int = 123456789,
        content: str = "測試訊息",
        channel_id: int = 98765,
        author_id: int = 67890,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        創建訊息測試資料

        Args:
            message_id: 訊息 ID
            content: 訊息內容
            channel_id: 頻道 ID
            author_id: 作者 ID
            **kwargs: 其他屬性

        Returns:
            訊息資料字典
        """
        return {
            "message_id": message_id,
            "content": content,
            "channel_id": channel_id,
            "guild_id": kwargs.get("guild_id", 12345),
            "author_id": author_id,
            "timestamp": kwargs.get("timestamp", time.time()),
            "attachments": kwargs.get("attachments", "[]"),
            "stickers": kwargs.get("stickers", "[]"),
            "deleted": kwargs.get("deleted", 0),
            "edited_at": kwargs.get("edited_at"),
            "reference_id": kwargs.get("reference_id"),
        }

    @staticmethod
    def create_activity_data(
        guild_id: int = 12345, user_id: int = 67890, score: float = 100.0, **kwargs: Any
    ) -> dict[str, Any]:
        """
        創建活躍度測試資料

        Args:
            guild_id: 伺服器 ID
            user_id: 用戶 ID
            score: 活躍度分數
            **kwargs: 其他屬性

        Returns:
            活躍度資料字典
        """
        return {
            "guild_id": guild_id,
            "user_id": user_id,
            "score": score,
            "last_msg": kwargs.get("last_msg", int(time.time())),
            "msg_cnt": kwargs.get("msg_cnt", 10),
            "ymd": kwargs.get("ymd", datetime.now(UTC).strftime("%Y-%m-%d")),
        }

    @staticmethod

    def create_channel_data(
        channel_id: int = 98765,
        name: str = "測試頻道",
        guild_id: int = 12345,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        創建頻道測試資料

        Args:
            channel_id: 頻道 ID
            name: 頻道名稱
            guild_id: 伺服器 ID
            **kwargs: 其他屬性

        Returns:
            頻道資料字典
        """
        return {
            "channel_id": channel_id,
            "guild_id": guild_id,
            "channel_name": name,
            "channel_type": kwargs.get("channel_type", "text"),
            "position": kwargs.get("position", 0),
            "topic": kwargs.get("topic", "測試頻道主題"),
            "created_at": kwargs.get("created_at", time.time()),
            "last_updated": kwargs.get("last_updated", time.time()),
        }

    @staticmethod
    def create_batch_data(
        factory_method: Callable[..., dict[str, Any]], count: int, base_id: int = 1000, **kwargs: Any
    ) -> list[dict[str, Any]]:
        """
        批量創建測試資料

        Args:
            factory_method: 工廠方法
            count: 創建數量
            base_id: 基礎 ID
            **kwargs: 傳遞給工廠方法的參數

        Returns:
            測試資料列表
        """
        return [
            factory_method(
                **{k: (v + i if k.endswith("_id") else v) for k, v in kwargs.items()},
                **(
                    {"user_id": base_id + i}
                    if "user_id" in factory_method.__code__.co_varnames
                    else {"guild_id": base_id + i}
                    if "guild_id" in factory_method.__code__.co_varnames
                    else {"channel_id": base_id + i}
                    if "channel_id" in factory_method.__code__.co_varnames
                    else {"message_id": base_id + i}
                ),
            )
            for i in range(count)
        ]


# 便捷函數
def create_test_guild(guild_id: int = 12345, **kwargs: Any) -> dict[str, Any]:
    """創建測試伺服器資料（便捷函數）"""
    return TestDataFactory.create_guild_data(guild_id, **kwargs)


def create_test_user(user_id: int = 67890, **kwargs: Any) -> dict[str, Any]:
    """創建測試用戶資料（便捷函數）"""
    return TestDataFactory.create_user_data(user_id, **kwargs)


def create_test_message(message_id: int = 123456789, **kwargs: Any) -> dict[str, Any]:
    """創建測試訊息資料（便捷函數）"""
    return TestDataFactory.create_message_data(message_id, **kwargs)
