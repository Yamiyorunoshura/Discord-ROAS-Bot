"""
🚀 API標準化系統
Discord ADR Bot v1.6 - 統一API接口標準

提供企業級的API標準化功能:
- 統一響應格式
- 標準錯誤處理
- 參數驗證機制
- API版本控制

作者:Discord ADR Bot 架構師
版本:v1.6
"""

import functools
import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import discord
from discord.ext import commands

# 設置日誌
logger = logging.getLogger(__name__)


class APIVersion(Enum):
    """API版本枚舉"""

    V1_0 = "1.0"
    V1_1 = "1.1"
    V1_2 = "1.2"
    LATEST = "1.2"


class ResponseStatus(Enum):
    """響應狀態枚舉"""

    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    PARTIAL = "partial"


class ErrorCode(Enum):
    """標準錯誤代碼"""

    # === 通用錯誤 (1000-1999) ===
    UNKNOWN_ERROR = 1000
    INVALID_PARAMETERS = 1001
    MISSING_PARAMETERS = 1002
    INVALID_FORMAT = 1003
    RATE_LIMITED = 1004

    # === 權限錯誤 (2000-2999) ===
    PERMISSION_DENIED = 2000
    INSUFFICIENT_PERMISSIONS = 2001
    UNAUTHORIZED = 2002

    # === 資源錯誤 (3000-3999) ===
    RESOURCE_NOT_FOUND = 3000
    RESOURCE_ALREADY_EXISTS = 3001
    RESOURCE_LIMIT_EXCEEDED = 3002

    # === 服務錯誤 (4000-4999) ===
    SERVICE_UNAVAILABLE = 4000
    DATABASE_ERROR = 4001
    NETWORK_ERROR = 4002
    CACHE_ERROR = 4003

    # === 業務邏輯錯誤 (5000-5999) ===
    BUSINESS_LOGIC_ERROR = 5000
    VALIDATION_FAILED = 5001
    OPERATION_FAILED = 5002


@dataclass
class APIResponse:
    """標準API響應格式"""

    status: ResponseStatus
    data: Any | None = None
    error: dict[str, Any | None] = None
    message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    version: APIVersion = APIVersion.LATEST
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        """後初始化處理"""
        if self.status == ResponseStatus.SUCCESS and self.data is None:
            self.data = {}

        # 添加默認元數據
        if "request_id" not in self.metadata:
            self.metadata["request_id"] = f"req_{int(time.time() * 1000)}"

    def to_dict(self) -> dict[str, Any]:
        """轉換為字典格式"""
        result = {
            "status": self.status.value,
            "version": self.version.value,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

        if self.data is not None:
            result["data"] = self.data

        if self.error is not None:
            result["error"] = self.error

        if self.message is not None:
            result["message"] = self.message

        return result

    def to_json(self) -> str:
        """轉換為JSON格式"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def success(cls, data=None, message=None, **metadata):
        """創建成功響應"""
        return cls(
            status=ResponseStatus.SUCCESS, data=data, message=message, metadata=metadata
        )

    @classmethod
    def create_error(
        cls, error_code: ErrorCode, message=None, details=None, **metadata
    ):
        """創建錯誤響應"""
        error_data = {
            "code": error_code.value,
            "name": error_code.name,
            "message": message or f"Error {error_code.value}: {error_code.name}",
        }

        if details:
            error_data["details"] = details

        return cls(
            status=ResponseStatus.ERROR,
            error=error_data,
            message=message,
            metadata=metadata,
        )

    @classmethod
    def warning(cls, data=None, message=None, **metadata):
        """創建警告響應"""
        return cls(
            status=ResponseStatus.WARNING, data=data, message=message, metadata=metadata
        )

    @classmethod
    def partial(cls, data=None, message=None, **metadata):
        """創建部分成功響應"""
        return cls(
            status=ResponseStatus.PARTIAL, data=data, message=message, metadata=metadata
        )


class APIValidator:
    """API參數驗證器"""

    @staticmethod
    def validate_string(value, min_length=0, max_length=None, allowed_values=None):
        """驗證字符串"""
        if not isinstance(value, str):
            return False, "必須是字符串類型"

        if len(value) < min_length:
            return False, f"字符串長度不能少於 {min_length}"

        if max_length and len(value) > max_length:
            return False, f"字符串長度不能超過 {max_length}"

        if allowed_values and value not in allowed_values:
            return False, f"值必須是以下之一: {', '.join(allowed_values)}"

        return True, None

    @staticmethod
    def validate_integer(value, min_value=None, max_value=None):
        """驗證整數"""
        if not isinstance(value, int):
            return False, "必須是整數類型"

        if min_value is not None and value < min_value:
            return False, f"值不能小於 {min_value}"

        if max_value is not None and value > max_value:
            return False, f"值不能大於 {max_value}"

        return True, None

    @staticmethod
    def validate_boolean(value):
        """驗證布爾值"""
        if not isinstance(value, bool):
            return False, "必須是布爾類型"
        return True, None

    @staticmethod
    def validate_list(value, min_items=0, max_items=None):
        """驗證列表"""
        if not isinstance(value, list):
            return False, "必須是列表類型"

        if len(value) < min_items:
            return False, f"列表項目數量不能少於 {min_items}"

        if max_items and len(value) > max_items:
            return False, f"列表項目數量不能超過 {max_items}"

        return True, None


class RateLimiter:
    """速率限制器"""

    def __init__(self, max_requests: int, time_window: int):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = {}

    def is_allowed(self, key: str) -> bool:
        """檢查是否允許請求"""
        now = time.time()

        # 清理過期記錄
        if key in self.requests:
            self.requests[key] = [
                timestamp
                for timestamp in self.requests[key]
                if now - timestamp < self.time_window
            ]
        else:
            self.requests[key] = []

        # 檢查是否超過限制
        if len(self.requests[key]) >= self.max_requests:
            return False

        # 記錄請求
        self.requests[key].append(now)
        return True


def api_endpoint(
    name: str,
    description: str = "",
    version: APIVersion = APIVersion.LATEST,
    rate_limit=None,
):
    """API端點裝飾器"""

    def decorator(func: Callable) -> Callable:
        # 創建速率限制器
        limiter = RateLimiter(*rate_limit) if rate_limit else None

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # 提取interaction或context
            interaction_or_ctx = None
            for arg in args:
                if isinstance(arg, discord.Interaction | commands.Context):
                    interaction_or_ctx = arg
                    break

            # 速率限制檢查
            if limiter and interaction_or_ctx:
                if isinstance(interaction_or_ctx, discord.Interaction):
                    user_id = interaction_or_ctx.user.id
                else:  # commands.Context
                    user_id = interaction_or_ctx.author.id

                if not limiter.is_allowed(str(user_id)):
                    return APIResponse.create_error(
                        ErrorCode.RATE_LIMITED, "請求過於頻繁,請稍後再試"
                    )

            try:
                # 調用原函數
                result = await func(*args, **kwargs)

                # 如果結果已經是APIResponse,直接返回
                if isinstance(result, APIResponse):
                    return result

                # 否則包裝為成功響應
                return APIResponse.success(result)

            except Exception as exc:
                logger.error(f"API端點 {name} 執行失敗: {exc}", exc_info=True)
                return APIResponse.create_error(
                    ErrorCode.UNKNOWN_ERROR, f"API執行失敗: {exc!s}"
                )

        # 添加API元數據
        wrapper._api_metadata = {
            "name": name,
            "description": description,
            "version": version,
            "rate_limit": rate_limit,
        }

        return wrapper

    return decorator


# 便利函數
def success_response(data=None, message=None, **metadata):
    """創建成功響應"""
    return APIResponse.success(data, message, **metadata)


def error_response(error_code: ErrorCode, message=None, details=None, **metadata):
    """創建錯誤響應"""
    return APIResponse.create_error(error_code, message, details, **metadata)


def warning_response(data=None, message=None, **metadata):
    """創建警告響應"""
    return APIResponse.warning(data, message, **metadata)


def partial_response(data=None, message=None, **metadata):
    """創建部分成功響應"""
    return APIResponse.partial(data, message, **metadata)


def validate_parameters(
    data: dict[str, Any], rules: dict[str, dict[str, Any]]
) -> APIResponse:
    """驗證參數"""
    errors = {}
    validated_data = {}

    # 檢查必需參數
    for param_name, rule in rules.items():
        required = rule.get("required", True)

        if required and param_name not in data:
            errors[param_name] = "此參數為必需項"
            continue

        # 使用默認值
        if param_name not in data:
            validated_data[param_name] = rule.get("default")
            continue

        # 驗證參數值
        param_type = rule.get("type", "string")
        value = data[param_name]

        if param_type == "string":
            valid, error = APIValidator.validate_string(
                value,
                rule.get("min_length", 0),
                rule.get("max_length"),
                rule.get("allowed_values"),
            )
        elif param_type == "integer":
            valid, error = APIValidator.validate_integer(
                value, rule.get("min_value"), rule.get("max_value")
            )
        elif param_type == "boolean":
            valid, error = APIValidator.validate_boolean(value)
        elif param_type == "list":
            valid, error = APIValidator.validate_list(
                value, rule.get("min_items", 0), rule.get("max_items")
            )
        else:
            valid, error = True, None

        if not valid:
            errors[param_name] = error
        else:
            validated_data[param_name] = value

    # 檢查多餘參數
    allowed_params = set(rules.keys())
    extra_params = set(data.keys()) - allowed_params
    if extra_params:
        for param in extra_params:
            errors[param] = "未知參數"

    if errors:
        return APIResponse.create_error(
            ErrorCode.VALIDATION_FAILED, "參數驗證失敗", {"validation_errors": errors}
        )

    return APIResponse.success(validated_data)
