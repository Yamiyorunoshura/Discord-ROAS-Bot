"""成就系統錯誤處理和日誌記錄整合.

此模組提供成就系統的統一錯誤處理和日誌記錄,包含:
- 自定義例外類型
- 結構化錯誤處理
- 統一的日誌記錄格式
- 錯誤分類和分析

遵循錯誤處理最佳實踐,提供清晰的錯誤訊息和追蹤能力.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class AchievementErrorType(str, Enum):
    """成就系統錯誤類型列舉."""

    VALIDATION_ERROR = "validation_error"
    BUSINESS_RULE_ERROR = "business_rule_error"
    DATA_ACCESS_ERROR = "data_access_error"
    CACHE_ERROR = "cache_error"
    SERVICE_ERROR = "service_error"
    INTEGRATION_ERROR = "integration_error"
    CONFIGURATION_ERROR = "configuration_error"


@dataclass
class ErrorContext:
    """錯誤上下文資料."""

    user_id: int | None = None
    achievement_id: int | None = None
    category_id: int | None = None
    operation: str | None = None
    additional_data: dict[str, Any] | None = None


class AchievementError(Exception):
    """成就系統基礎例外類型."""

    def __init__(
        self,
        message: str,
        error_type: AchievementErrorType,
        context: ErrorContext | None = None,
        original_exception: Exception | None = None,
    ):
        """初始化成就系統例外.

        Args:
            message: 錯誤訊息
            error_type: 錯誤類型
            context: 錯誤上下文
            original_exception: 原始例外
        """
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.context = context or ErrorContext()
        self.original_exception = original_exception
        self.timestamp = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        """將例外轉換為字典格式.

        Returns:
            例外資料字典
        """
        return {
            "message": self.message,
            "error_type": self.error_type.value,
            "timestamp": self.timestamp.isoformat(),
            "context": {
                "user_id": self.context.user_id,
                "achievement_id": self.context.achievement_id,
                "category_id": self.context.category_id,
                "operation": self.context.operation,
                "additional_data": self.context.additional_data,
            },
            "original_exception": str(self.original_exception)
            if self.original_exception
            else None,
        }


class AchievementValidationError(AchievementError):
    """成就驗證錯誤."""

    def __init__(self, message: str, context: ErrorContext | None = None):
        super().__init__(message, AchievementErrorType.VALIDATION_ERROR, context)


class AchievementBusinessRuleError(AchievementError):
    """成就業務規則錯誤."""

    def __init__(self, message: str, context: ErrorContext | None = None):
        super().__init__(message, AchievementErrorType.BUSINESS_RULE_ERROR, context)


class AchievementDataAccessError(AchievementError):
    """成就資料存取錯誤."""

    def __init__(
        self,
        message: str,
        context: ErrorContext | None = None,
        original_exception: Exception | None = None,
    ):
        super().__init__(
            message, AchievementErrorType.DATA_ACCESS_ERROR, context, original_exception
        )


class AchievementCacheError(AchievementError):
    """成就快取錯誤."""

    def __init__(
        self,
        message: str,
        context: ErrorContext | None = None,
        original_exception: Exception | None = None,
    ):
        super().__init__(
            message, AchievementErrorType.CACHE_ERROR, context, original_exception
        )


class AchievementServiceError(AchievementError):
    """成就服務錯誤."""

    def __init__(
        self,
        message: str,
        context: ErrorContext | None = None,
        original_exception: Exception | None = None,
    ):
        super().__init__(
            message, AchievementErrorType.SERVICE_ERROR, context, original_exception
        )


class AchievementIntegrationError(AchievementError):
    """成就整合錯誤."""

    def __init__(
        self,
        message: str,
        context: ErrorContext | None = None,
        original_exception: Exception | None = None,
    ):
        super().__init__(
            message, AchievementErrorType.INTEGRATION_ERROR, context, original_exception
        )


class AchievementConfigurationError(AchievementError):
    """成就配置錯誤."""

    def __init__(self, message: str, context: ErrorContext | None = None):
        super().__init__(message, AchievementErrorType.CONFIGURATION_ERROR, context)


class AchievementErrorHandler:
    """成就系統錯誤處理器.

    提供統一的錯誤處理和日誌記錄功能.
    """

    def __init__(self, logger: logging.Logger | None = None):
        """初始化錯誤處理器.

        Args:
            logger: 日誌記錄器(可選)
        """
        self.logger = logger or logging.getLogger(__name__)
        self._error_counts: dict[str, int] = {}

    def handle_error(
        self,
        error: Exception,
        context: ErrorContext | None = None,
        log_level: int = logging.ERROR,
    ) -> AchievementError:
        """處理錯誤並記錄日誌.

        Args:
            error: 原始錯誤
            context: 錯誤上下文
            log_level: 日誌級別

        Returns:
            處理後的成就系統錯誤
        """
        # 如果已經是成就系統錯誤,直接記錄
        if isinstance(error, AchievementError):
            achievement_error = error
        else:
            # 包裝為成就系統錯誤
            achievement_error = self._wrap_error(error, context)

        # 記錄錯誤統計
        self._record_error_count(achievement_error.error_type.value)

        # 記錄日誌
        self._log_error(achievement_error, log_level)

        return achievement_error

    def _wrap_error(
        self, error: Exception, context: ErrorContext | None
    ) -> AchievementError:
        """包裝原始錯誤為成就系統錯誤.

        Args:
            error: 原始錯誤
            context: 錯誤上下文

        Returns:
            包裝後的成就系統錯誤
        """
        error_message = str(error)

        # 根據錯誤類型進行分類
        if isinstance(error, ValueError):
            return AchievementValidationError(error_message, context)
        elif isinstance(error, ConnectionError | TimeoutError):
            return AchievementDataAccessError(error_message, context, error)
        elif "cache" in error_message.lower():
            return AchievementCacheError(error_message, context, error)
        else:
            return AchievementServiceError(error_message, context, error)

    def _record_error_count(self, error_type: str) -> None:
        """記錄錯誤統計.

        Args:
            error_type: 錯誤類型
        """
        self._error_counts[error_type] = self._error_counts.get(error_type, 0) + 1

    def _log_error(self, error: AchievementError, log_level: int) -> None:
        """記錄錯誤日誌.

        Args:
            error: 成就系統錯誤
            log_level: 日誌級別
        """
        # 構建結構化日誌資料
        log_extra: dict[str, Any] = {
            "error_type": error.error_type.value,
            "error_message": error.message,
            "timestamp": error.timestamp.isoformat(),
        }

        # 添加上下文資料
        if error.context:
            if error.context.user_id:
                log_extra["user_id"] = error.context.user_id
            if error.context.achievement_id:
                log_extra["achievement_id"] = error.context.achievement_id
            if error.context.category_id:
                log_extra["category_id"] = error.context.category_id
            if error.context.operation:
                log_extra["operation"] = error.context.operation
            if error.context.additional_data:
                log_extra["additional_data"] = error.context.additional_data

        # 記錄日誌
        self.logger.log(
            log_level,
            f"成就系統錯誤: {error.message}",
            extra=log_extra,
            exc_info=error.original_exception,
        )

    def get_error_statistics(self) -> dict[str, Any]:
        """取得錯誤統計資料.

        Returns:
            錯誤統計字典
        """
        total_errors = sum(self._error_counts.values())

        return {
            "total_errors": total_errors,
            "error_counts": self._error_counts.copy(),
            "error_rates": {
                error_type: count / total_errors * 100 if total_errors > 0 else 0
                for error_type, count in self._error_counts.items()
            },
        }

    def reset_error_statistics(self) -> None:
        """重置錯誤統計資料."""
        self._error_counts.clear()


class AchievementLogger:
    """成就系統專用日誌記錄器.

    提供成就系統特定的日誌記錄功能和格式.
    """

    def __init__(self, logger_name: str = "achievement_system"):
        """初始化成就系統日誌記錄器.

        Args:
            logger_name: 日誌記錄器名稱
        """
        self.logger = logging.getLogger(logger_name)

    def log_achievement_earned(
        self, user_id: int, achievement_id: int, achievement_name: str, points: int
    ) -> None:
        """記錄成就獲得日誌.

        Args:
            user_id: 用戶 ID
            achievement_id: 成就 ID
            achievement_name: 成就名稱
            points: 獲得點數
        """
        self.logger.info(
            "用戶獲得新成就",
            extra={
                "event_type": "achievement_earned",
                "user_id": user_id,
                "achievement_id": achievement_id,
                "achievement_name": achievement_name,
                "points": points,
                "timestamp": datetime.now().isoformat(),
            },
        )

    def log_progress_update(
        self,
        user_id: int,
        achievement_id: int,
        old_value: float,
        new_value: float,
        is_completed: bool,
    ) -> None:
        """記錄進度更新日誌.

        Args:
            user_id: 用戶 ID
            achievement_id: 成就 ID
            old_value: 舊進度值
            new_value: 新進度值
            is_completed: 是否完成
        """
        self.logger.info(
            "成就進度更新",
            extra={
                "event_type": "progress_update",
                "user_id": user_id,
                "achievement_id": achievement_id,
                "old_value": old_value,
                "new_value": new_value,
                "progress_increase": new_value - old_value,
                "is_completed": is_completed,
                "timestamp": datetime.now().isoformat(),
            },
        )

    def log_service_operation(
        self,
        operation: str,
        success: bool,
        duration_ms: float | None = None,
        additional_data: dict[str, Any] | None = None,
    ) -> None:
        """記錄服務操作日誌.

        Args:
            operation: 操作名稱
            success: 是否成功
            duration_ms: 執行時間(毫秒)
            additional_data: 額外資料
        """
        log_data = {
            "event_type": "service_operation",
            "operation": operation,
            "success": success,
            "timestamp": datetime.now().isoformat(),
        }

        if duration_ms is not None:
            log_data["duration_ms"] = duration_ms

        if additional_data:
            log_data["additional_data"] = additional_data

        log_level = logging.INFO if success else logging.WARNING
        self.logger.log(
            log_level,
            f"服務操作 {operation} {'成功' if success else '失敗'}",
            extra=log_data,
        )


def create_error_context(
    user_id: int | None = None,
    achievement_id: int | None = None,
    category_id: int | None = None,
    operation: str | None = None,
    **kwargs: Any,
) -> ErrorContext:
    """建立錯誤上下文的便利函數.

    Args:
        user_id: 用戶 ID
        achievement_id: 成就 ID
        category_id: 分類 ID
        operation: 操作名稱
        **kwargs: 額外資料

    Returns:
        錯誤上下文物件
    """
    return ErrorContext(
        user_id=user_id,
        achievement_id=achievement_id,
        category_id=category_id,
        operation=operation,
        additional_data=kwargs if kwargs else None,
    )


__all__ = [
    "AchievementBusinessRuleError",
    "AchievementCacheError",
    "AchievementConfigurationError",
    "AchievementDataAccessError",
    "AchievementError",
    "AchievementErrorHandler",
    "AchievementErrorType",
    "AchievementIntegrationError",
    "AchievementLogger",
    "AchievementServiceError",
    "AchievementValidationError",
    "ErrorContext",
    "create_error_context",
]
