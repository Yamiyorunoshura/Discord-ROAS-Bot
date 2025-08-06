"""成就系統快取鍵值標準化和命名規範.

此模組定義成就系統的快取鍵值標準化規範,提供:
- 快取鍵值命名規範和標準
- 快取鍵值驗證和規範化
- 快取鍵值文檔和範例
- 快取鍵值生成和解析工具
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar

from ..constants import CACHE_KEY_MAX_LENGTH, MINIMUM_CACHE_PARTS

logger = logging.getLogger(__name__)


class CacheKeyType(Enum):
    """快取鍵值類型枚舉."""

    ACHIEVEMENT = "achievement"  # 單個成就資料
    ACHIEVEMENTS = "achievements"  # 成就列表
    CATEGORY = "category"  # 成就分類
    CATEGORIES = "categories"  # 分類列表
    USER_ACHIEVEMENTS = "user_achievements"  # 用戶成就
    USER_PROGRESS = "user_progress"  # 用戶進度
    USER_STATS = "user_stats"  # 用戶統計
    GLOBAL_STATS = "global_stats"  # 全域統計
    LEADERBOARD = "leaderboard"  # 排行榜
    POPULAR_ACHIEVEMENTS = "popular_achievements"  # 熱門成就


@dataclass
class CacheKeyPattern:
    """快取鍵值模式定義."""

    key_type: CacheKeyType
    pattern: str
    description: str
    example: str
    required_args: list[str]
    optional_args: list[str]


class CacheKeyStandard:
    """快取鍵值標準化管理器.

    定義和管理成就系統的快取鍵值命名標準.
    """

    # 快取鍵值前綴
    KEY_PREFIX = "achievement"

    # 分隔符
    SEPARATOR = ":"

    # 快取鍵值模式定義
    KEY_PATTERNS: ClassVar[dict] = {
        CacheKeyType.ACHIEVEMENT: CacheKeyPattern(
            key_type=CacheKeyType.ACHIEVEMENT,
            pattern=f"{KEY_PREFIX}:achievement:{{achievement_id}}",
            description="單個成就資料快取",
            example=f"{KEY_PREFIX}:achievement:123",
            required_args=["achievement_id"],
            optional_args=[],
        ),
        CacheKeyType.ACHIEVEMENTS: CacheKeyPattern(
            key_type=CacheKeyType.ACHIEVEMENTS,
            pattern=f"{KEY_PREFIX}:achievements:{{category_id}}:{{type}}:{{active}}:{{limit}}:{{offset}}",
            description="成就列表快取(支援篩選和分頁)",
            example=f"{KEY_PREFIX}:achievements:1:daily:True:10:0",
            required_args=[],
            optional_args=["category_id", "type", "active", "limit", "offset"],
        ),
        CacheKeyType.CATEGORY: CacheKeyPattern(
            key_type=CacheKeyType.CATEGORY,
            pattern=f"{KEY_PREFIX}:category:{{category_id}}",
            description="單個成就分類資料快取",
            example=f"{KEY_PREFIX}:category:456",
            required_args=["category_id"],
            optional_args=[],
        ),
        CacheKeyType.CATEGORIES: CacheKeyPattern(
            key_type=CacheKeyType.CATEGORIES,
            pattern=f"{KEY_PREFIX}:categories:{{active_only}}",
            description="成就分類列表快取",
            example=f"{KEY_PREFIX}:categories:True",
            required_args=["active_only"],
            optional_args=[],
        ),
        CacheKeyType.USER_ACHIEVEMENTS: CacheKeyPattern(
            key_type=CacheKeyType.USER_ACHIEVEMENTS,
            pattern=f"{KEY_PREFIX}:user_achievements:{{user_id}}:{{category_id}}:{{limit}}",
            description="用戶成就列表快取",
            example=f"{KEY_PREFIX}:user_achievements:789:1:50",
            required_args=["user_id"],
            optional_args=["category_id", "limit"],
        ),
        CacheKeyType.USER_PROGRESS: CacheKeyPattern(
            key_type=CacheKeyType.USER_PROGRESS,
            pattern=f"{KEY_PREFIX}:user_progress:{{user_id}}:{{achievement_id}}",
            description="用戶成就進度快取",
            example=f"{KEY_PREFIX}:user_progress:789:123",
            required_args=["user_id"],
            optional_args=["achievement_id"],
        ),
        CacheKeyType.USER_STATS: CacheKeyPattern(
            key_type=CacheKeyType.USER_STATS,
            pattern=f"{KEY_PREFIX}:user_stats:{{user_id}}",
            description="用戶成就統計快取",
            example=f"{KEY_PREFIX}:user_stats:789",
            required_args=["user_id"],
            optional_args=[],
        ),
        CacheKeyType.GLOBAL_STATS: CacheKeyPattern(
            key_type=CacheKeyType.GLOBAL_STATS,
            pattern=f"{KEY_PREFIX}:global_stats",
            description="全域成就統計快取",
            example=f"{KEY_PREFIX}:global_stats",
            required_args=[],
            optional_args=[],
        ),
        CacheKeyType.LEADERBOARD: CacheKeyPattern(
            key_type=CacheKeyType.LEADERBOARD,
            pattern=f"{KEY_PREFIX}:leaderboard:{{type}}:{{limit}}",
            description="排行榜快取",
            example=f"{KEY_PREFIX}:leaderboard:points:10",
            required_args=["type"],
            optional_args=["limit"],
        ),
        CacheKeyType.POPULAR_ACHIEVEMENTS: CacheKeyPattern(
            key_type=CacheKeyType.POPULAR_ACHIEVEMENTS,
            pattern=f"{KEY_PREFIX}:popular_achievements:{{limit}}",
            description="熱門成就列表快取",
            example=f"{KEY_PREFIX}:popular_achievements:10",
            required_args=["limit"],
            optional_args=[],
        ),
    }

    @classmethod
    def generate_cache_key(cls, key_type: CacheKeyType, **kwargs) -> str:
        """生成標準化的快取鍵值.

        Args:
            key_type: 快取鍵值類型
            **kwargs: 鍵值參數

        Returns:
            標準化的快取鍵值

        Raises:
            ValueError: 當必要參數缺失時
        """
        pattern = cls.KEY_PATTERNS.get(key_type)
        if not pattern:
            raise ValueError(f"不支援的快取鍵值類型: {key_type}")

        # 檢查必要參數
        for required_arg in pattern.required_args:
            if required_arg not in kwargs:
                raise ValueError(f"缺少必要參數: {required_arg}")

        # 構建鍵值組件
        key_parts = [cls.KEY_PREFIX, key_type.value]

        # Add parameters in defined order
        all_args = pattern.required_args + pattern.optional_args
        for arg in all_args:
            if arg in kwargs:
                key_parts.append(str(kwargs[arg]))
            elif arg in pattern.required_args:
                # 必要參數已在上面檢查過,這裡不應該到達
                raise ValueError(f"缺少必要參數: {arg}")
            else:
                # 可選參數缺失,使用 None 占位
                key_parts.append("None")

        return cls.SEPARATOR.join(key_parts)

    @classmethod
    def parse_cache_key(
        cls, cache_key: str
    ) -> tuple[CacheKeyType | None, dict[str, Any]]:
        """解析快取鍵值.

        Args:
            cache_key: 快取鍵值字串

        Returns:
            (鍵值類型, 參數字典) 或 (None, {}) 如果解析失敗
        """
        try:
            parts = cache_key.split(cls.SEPARATOR)

            # 檢查前綴
            if len(parts) < MINIMUM_CACHE_PARTS or parts[0] != cls.KEY_PREFIX:
                return None, {}

            # 取得鍵值類型
            try:
                key_type = CacheKeyType(parts[1])
            except ValueError:
                return None, {}

            pattern = cls.KEY_PATTERNS.get(key_type)
            if not pattern:
                return None, {}

            # 解析參數
            params = {}
            all_args = pattern.required_args + pattern.optional_args

            # 從第3個部分開始是參數
            for i, arg in enumerate(all_args):
                param_index = i + 2  # 跳過 prefix 和 key_type
                if param_index < len(parts):
                    value = parts[param_index]
                    if value != "None":
                        # 嘗試轉換數據類型
                        params[arg] = cls._convert_param_value(value)

            return key_type, params

        except Exception as e:
            logger.warning(f"快取鍵值解析失敗: {cache_key}, 錯誤: {e}")
            return None, {}

    @classmethod
    def _convert_param_value(cls, value: str) -> Any:
        """轉換參數值為適當的數據類型.

        Args:
            value: 字串值

        Returns:
            轉換後的值
        """
        # 嘗試轉換為整數
        if value.isdigit():
            return int(value)

        # 嘗試轉換為布林值
        if value.lower() in ("true", "false"):
            return value.lower() == "true"

        # 保持字串
        return value

    @classmethod
    def validate_cache_key(cls, cache_key: str) -> tuple[bool, str]:
        """驗證快取鍵值是否符合標準.

        Args:
            cache_key: 快取鍵值字串

        Returns:
            (是否有效, 錯誤訊息)
        """
        # 基本格式檢查
        if not cache_key or not isinstance(cache_key, str):
            return False, "快取鍵值不能為空"

        # 長度檢查
        if len(cache_key) > CACHE_KEY_MAX_LENGTH:
            return False, f"快取鍵值長度不能超過 {CACHE_KEY_MAX_LENGTH} 字元"

        # 字元檢查(只允許字母、數字、冒號、底線、破折號)
        if not re.match(r"^[a-zA-Z0-9:_-]+$", cache_key):
            return False, "快取鍵值包含無效字元"

        # 解析檢查
        key_type, params = cls.parse_cache_key(cache_key)
        if key_type is None:
            return False, "快取鍵值格式不正確"

        return True, ""

    @classmethod
    def get_key_pattern_documentation(cls) -> dict[str, dict[str, Any]]:
        """取得快取鍵值模式文檔.

        Returns:
            包含所有模式文檔的字典
        """
        docs = {}
        for key_type, pattern in cls.KEY_PATTERNS.items():
            docs[key_type.value] = {
                "pattern": pattern.pattern,
                "description": pattern.description,
                "example": pattern.example,
                "required_args": pattern.required_args,
                "optional_args": pattern.optional_args,
            }
        return docs

    @classmethod
    def find_matching_keys(cls, cache_keys: list[str], pattern: str) -> list[str]:
        """根據模式尋找匹配的快取鍵值.

        Args:
            cache_keys: 快取鍵值列表
            pattern: 搜尋模式(支援萬用字元 *)

        Returns:
            匹配的快取鍵值列表
        """
        # 將萬用字元轉換為正則表達式
        regex_pattern = pattern.replace("*", ".*")
        regex = re.compile(f"^{regex_pattern}$")

        matching_keys = []
        for key in cache_keys:
            if regex.match(key):
                matching_keys.append(key)

        return matching_keys

    @classmethod
    def get_invalidation_patterns_for_operation(
        cls, operation_type: str, **kwargs
    ) -> list[str]:
        """取得操作對應的快取無效化模式.

        Args:
            operation_type: 操作類型
            **kwargs: 操作相關參數

        Returns:
            快取無效化模式列表
        """
        patterns = []

        if operation_type in [
            "create_achievement",
            "update_achievement",
            "delete_achievement",
        ]:
            patterns.extend([
                f"{cls.KEY_PREFIX}:achievement:*",
                f"{cls.KEY_PREFIX}:achievements:*",
                f"{cls.KEY_PREFIX}:global_stats",
                f"{cls.KEY_PREFIX}:popular_achievements:*",
            ])

            # 如果有分類 ID,也無效化分類相關快取
            if "category_id" in kwargs:
                patterns.append(f"{cls.KEY_PREFIX}:category:{kwargs['category_id']}")

        elif operation_type in [
            "create_category",
            "update_category",
            "delete_category",
        ]:
            patterns.extend([
                f"{cls.KEY_PREFIX}:category:*",
                f"{cls.KEY_PREFIX}:categories:*",
            ])

        elif operation_type in ["award_achievement", "update_progress"]:
            user_id = kwargs.get("user_id")
            if user_id:
                patterns.extend([
                    f"{cls.KEY_PREFIX}:user_achievements:{user_id}:*",
                    f"{cls.KEY_PREFIX}:user_progress:{user_id}:*",
                    f"{cls.KEY_PREFIX}:user_stats:{user_id}",
                    f"{cls.KEY_PREFIX}:global_stats",
                    f"{cls.KEY_PREFIX}:leaderboard:*",
                ])

        return patterns


__all__ = [
    "CacheKeyPattern",
    "CacheKeyStandard",
    "CacheKeyType",
]
