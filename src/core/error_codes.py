"""
Error Code Mapping System
Task ID: T2 - App architecture baseline and scaffolding

This module provides error code mapping and user message formatting functionality.
It maps internal exceptions to standardized error codes and provides user-friendly messages.
"""

from enum import Enum
from typing import Dict, Any, Optional, Union
import logging

from .errors import (
    AppError, ServiceError, DatabaseError, PermissionError, 
    ValidationError, NotFoundError, ConfigurationError, ExternalServiceError
)


class ErrorCode(Enum):
    """
    Standardized error codes for the application
    
    These codes provide machine-readable error identification and can be used
    for API responses, logging, monitoring, and internationalization.
    
    Format: [MODULE]_[NUMBER]
    - MODULE: 3-4 letter module abbreviation
    - NUMBER: 4-digit number indicating specific error type
    """
    
    # Generic application errors (1000-1099)
    UNKNOWN_ERROR = "APP_1000"
    INTERNAL_ERROR = "APP_1001"
    INITIALIZATION_ERROR = "APP_1002"
    SHUTDOWN_ERROR = "APP_1003"
    TIMEOUT_ERROR = "APP_1004"
    
    # Service layer errors (1100-1199)
    SERVICE_ERROR = "SVC_1100"
    SERVICE_UNAVAILABLE = "SVC_1101"
    SERVICE_INITIALIZATION_FAILED = "SVC_1102"
    SERVICE_SHUTDOWN_FAILED = "SVC_1103"
    SERVICE_DEPENDENCY_ERROR = "SVC_1104"
    
    # Achievement system errors (1200-1299)
    ACHIEVEMENT_NOT_FOUND = "ACH_1200"
    ACHIEVEMENT_ALREADY_GRANTED = "ACH_1201"
    ACHIEVEMENT_REQUIREMENTS_NOT_MET = "ACH_1202"
    ACHIEVEMENT_PROGRESS_ERROR = "ACH_1203"
    ACHIEVEMENT_TRIGGER_ERROR = "ACH_1204"
    ACHIEVEMENT_REWARD_ERROR = "ACH_1205"
    ACHIEVEMENT_CREATE_FAILED = "ACH_1206"
    ACHIEVEMENT_UPDATE_FAILED = "ACH_1207"
    ACHIEVEMENT_DELETE_FAILED = "ACH_1208"
    
    # Economy system errors (1300-1399)
    INSUFFICIENT_BALANCE = "ECO_1300"
    INVALID_AMOUNT = "ECO_1301"
    ECONOMY_TRANSACTION_FAILED = "ECO_1302"
    ECONOMY_BALANCE_ERROR = "ECO_1303"
    ECONOMY_TRANSFER_ERROR = "ECO_1304"
    ACCOUNT_NOT_FOUND = "ECO_1305"
    ACCOUNT_CREATE_FAILED = "ECO_1306"
    ACCOUNT_FROZEN = "ECO_1307"
    TRANSACTION_HISTORY_ERROR = "ECO_1308"
    
    # Government/Role system errors (1400-1499)
    ROLE_NOT_FOUND = "GOV_1400"
    ROLE_ASSIGNMENT_FAILED = "GOV_1401"
    ROLE_REMOVAL_FAILED = "GOV_1402"
    INSUFFICIENT_PERMISSIONS = "GOV_1403"
    GOVERNMENT_STRUCTURE_ERROR = "GOV_1404"
    ROLE_CREATE_FAILED = "GOV_1405"
    ROLE_DELETE_FAILED = "GOV_1406"
    PERMISSION_CHECK_FAILED = "GOV_1407"
    
    # Database errors (1500-1599)
    DATABASE_CONNECTION_ERROR = "DB_1500"
    DATABASE_QUERY_ERROR = "DB_1501"
    DATABASE_CONSTRAINT_ERROR = "DB_1502"
    DATABASE_TIMEOUT = "DB_1503"
    DATABASE_MIGRATION_ERROR = "DB_1504"
    DATA_INTEGRITY_ERROR = "DB_1505"
    DATABASE_LOCK_ERROR = "DB_1506"
    TRANSACTION_FAILED = "DB_1507"
    
    # Validation errors (1600-1699)
    VALIDATION_ERROR = "VAL_1600"
    INVALID_INPUT = "VAL_1601"
    MISSING_REQUIRED_FIELD = "VAL_1602"
    INVALID_FORMAT = "VAL_1603"
    VALUE_OUT_OF_RANGE = "VAL_1604"
    INVALID_USER_ID = "VAL_1605"
    INVALID_GUILD_ID = "VAL_1606"
    INVALID_ACCOUNT_ID = "VAL_1607"
    INVALID_ACHIEVEMENT_ID = "VAL_1608"
    
    # Permission errors (1700-1799)
    PERMISSION_DENIED = "PERM_1700"
    AUTHENTICATION_REQUIRED = "PERM_1701"
    AUTHORIZATION_FAILED = "PERM_1702"
    ACCESS_FORBIDDEN = "PERM_1703"
    ROLE_REQUIRED = "PERM_1704"
    
    # Resource not found errors (1800-1899)
    NOT_FOUND = "NF_1800"
    USER_NOT_FOUND = "NF_1801"
    GUILD_NOT_FOUND = "NF_1802"
    CHANNEL_NOT_FOUND = "NF_1803"
    MESSAGE_NOT_FOUND = "NF_1804"
    
    # Configuration errors (1900-1999)
    CONFIG_ERROR = "CFG_1900"
    CONFIG_MISSING = "CFG_1901"
    CONFIG_INVALID = "CFG_1902"
    ENVIRONMENT_ERROR = "CFG_1903"
    
    # External service errors (2000-2099)
    EXTERNAL_SERVICE_ERROR = "EXT_2000"
    API_REQUEST_FAILED = "EXT_2001"
    API_RATE_LIMIT = "EXT_2002"
    API_AUTHENTICATION_FAILED = "EXT_2003"
    DISCORD_API_ERROR = "EXT_2004"
    
    # Test orchestration errors (2100-2199)
    TEST_SETUP_ERROR = "TEST_2100"
    TEST_EXECUTION_ERROR = "TEST_2101"
    TEST_CLEANUP_ERROR = "TEST_2102"
    DPYTEST_ERROR = "TEST_2103"
    TEST_ISOLATION_ERROR = "TEST_2104"
    
    # Activity system errors (2200-2299)
    ACTIVITY_MONITORING_ERROR = "ACT_2200"
    ACTIVITY_TRACK_FAILED = "ACT_2201"
    ACTIVITY_THRESHOLD_ERROR = "ACT_2202"
    ACTIVITY_DATA_INVALID = "ACT_2203"
    
    # Monitoring system errors (2300-2399)
    MONITORING_ERROR = "MON_2300"
    HEALTH_CHECK_FAILED = "MON_2301"
    METRICS_COLLECTION_ERROR = "MON_2302"
    ALERT_TRIGGER_ERROR = "MON_2303"
    PERFORMANCE_THRESHOLD_ERROR = "MON_2304"
    
    # Deployment system errors (2400-2499)
    DEPLOYMENT_ERROR = "DEP_2400"
    DEPLOYMENT_CONFIG_ERROR = "DEP_2401"
    DEPLOYMENT_VALIDATION_ERROR = "DEP_2402"
    ENVIRONMENT_SETUP_ERROR = "DEP_2403"
    
    # Documentation system errors (2500-2599)
    DOCUMENTATION_ERROR = "DOC_2500"
    DOCUMENT_VALIDATION_ERROR = "DOC_2501"
    DOCUMENT_GENERATION_ERROR = "DOC_2502"
    DOCUMENT_PARSING_ERROR = "DOC_2503"


def map_exception_to_error_code(exception: Exception) -> ErrorCode:
    """
    Map an exception to a standardized error code
    
    Args:
        exception: The exception to map
        
    Returns:
        Corresponding ErrorCode enum value
    """
    
    # Handle custom application errors first
    if isinstance(exception, AppError):
        if hasattr(exception, 'error_code') and exception.error_code:
            # Try to find matching ErrorCode by value
            for error_code in ErrorCode:
                if error_code.value == exception.error_code:
                    return error_code
    
    # Map by exception type
    error_mapping = {
        # Service errors
        ServiceError: ErrorCode.SERVICE_ERROR,
        
        # Database errors
        DatabaseError: ErrorCode.DATABASE_QUERY_ERROR,
        
        # Permission errors
        PermissionError: ErrorCode.PERMISSION_DENIED,
        
        # Validation errors
        ValidationError: ErrorCode.VALIDATION_ERROR,
        
        # Not found errors
        NotFoundError: ErrorCode.NOT_FOUND,
        
        # Configuration errors
        ConfigurationError: ErrorCode.CONFIG_ERROR,
        
        # External service errors
        ExternalServiceError: ErrorCode.EXTERNAL_SERVICE_ERROR,
        
        # Built-in Python exceptions
        ValueError: ErrorCode.INVALID_INPUT,
        TypeError: ErrorCode.VALIDATION_ERROR,
        KeyError: ErrorCode.NOT_FOUND,
        AttributeError: ErrorCode.INTERNAL_ERROR,
        ConnectionError: ErrorCode.DATABASE_CONNECTION_ERROR,
        TimeoutError: ErrorCode.TIMEOUT_ERROR,
        PermissionError: ErrorCode.PERMISSION_DENIED,
        FileNotFoundError: ErrorCode.NOT_FOUND,
        
        # Default for unknown exceptions
        Exception: ErrorCode.UNKNOWN_ERROR,
    }
    
    # Find the most specific mapping
    for exception_type in type(exception).__mro__:
        if exception_type in error_mapping:
            return error_mapping[exception_type]
    
    # Fallback to unknown error
    return ErrorCode.UNKNOWN_ERROR


def get_user_message(error_code: ErrorCode, context: Optional[Dict[str, Any]] = None) -> str:
    """
    Get user-friendly message for an error code
    
    Args:
        error_code: The error code to get message for
        context: Optional context for message formatting
        
    Returns:
        User-friendly error message
    """
    context = context or {}
    
    message_templates = {
        # Generic application errors
        ErrorCode.UNKNOWN_ERROR: "發生未知錯誤，請稍後再試",
        ErrorCode.INTERNAL_ERROR: "系統內部錯誤，請聯繫管理員",
        ErrorCode.INITIALIZATION_ERROR: "系統初始化失敗，請稍後再試",
        ErrorCode.SHUTDOWN_ERROR: "系統關閉時發生錯誤",
        ErrorCode.TIMEOUT_ERROR: "操作逾時，請稍後再試",
        
        # Service layer errors
        ErrorCode.SERVICE_ERROR: "服務發生錯誤，請稍後再試",
        ErrorCode.SERVICE_UNAVAILABLE: "服務目前無法使用，請稍後再試",
        ErrorCode.SERVICE_INITIALIZATION_FAILED: "服務初始化失敗，請聯繫管理員",
        ErrorCode.SERVICE_SHUTDOWN_FAILED: "服務關閉失敗",
        ErrorCode.SERVICE_DEPENDENCY_ERROR: "服務依賴項錯誤",
        
        # Achievement system errors
        ErrorCode.ACHIEVEMENT_NOT_FOUND: "找不到指定的成就",
        ErrorCode.ACHIEVEMENT_ALREADY_GRANTED: "您已經獲得此成就了",
        ErrorCode.ACHIEVEMENT_REQUIREMENTS_NOT_MET: "尚未滿足成就的要求條件",
        ErrorCode.ACHIEVEMENT_PROGRESS_ERROR: "成就進度更新發生錯誤",
        ErrorCode.ACHIEVEMENT_TRIGGER_ERROR: "成就觸發檢查發生錯誤",
        ErrorCode.ACHIEVEMENT_REWARD_ERROR: "成就獎勵發放失敗",
        ErrorCode.ACHIEVEMENT_CREATE_FAILED: "成就創建失敗",
        ErrorCode.ACHIEVEMENT_UPDATE_FAILED: "成就更新失敗", 
        ErrorCode.ACHIEVEMENT_DELETE_FAILED: "成就刪除失敗",
        
        # Economy system errors
        ErrorCode.INSUFFICIENT_BALANCE: "餘額不足以完成此操作",
        ErrorCode.INVALID_AMOUNT: "金額無效，請檢查輸入",
        ErrorCode.ECONOMY_TRANSACTION_FAILED: "交易失敗，請稍後再試",
        ErrorCode.ECONOMY_BALANCE_ERROR: "餘額查詢發生錯誤",
        ErrorCode.ECONOMY_TRANSFER_ERROR: "轉帳失敗，請檢查收款人資訊",
        ErrorCode.ACCOUNT_NOT_FOUND: "找不到指定的帳戶",
        ErrorCode.ACCOUNT_CREATE_FAILED: "帳戶創建失敗",
        ErrorCode.ACCOUNT_FROZEN: "帳戶已被凍結",
        ErrorCode.TRANSACTION_HISTORY_ERROR: "交易記錄查詢失敗",
        
        # Government/Role system errors
        ErrorCode.ROLE_NOT_FOUND: "找不到指定的身分組",
        ErrorCode.ROLE_ASSIGNMENT_FAILED: "身分組指派失敗",
        ErrorCode.ROLE_REMOVAL_FAILED: "身分組移除失敗",
        ErrorCode.INSUFFICIENT_PERMISSIONS: "您沒有足夠的權限執行此操作",
        ErrorCode.GOVERNMENT_STRUCTURE_ERROR: "政府結構發生錯誤",
        ErrorCode.ROLE_CREATE_FAILED: "身分組創建失敗",
        ErrorCode.ROLE_DELETE_FAILED: "身分組刪除失敗",
        ErrorCode.PERMISSION_CHECK_FAILED: "權限檢查失敗",
        
        # Database errors
        ErrorCode.DATABASE_CONNECTION_ERROR: "資料庫連線錯誤，請稍後再試",
        ErrorCode.DATABASE_QUERY_ERROR: "資料查詢失敗，請稍後再試",
        ErrorCode.DATABASE_CONSTRAINT_ERROR: "資料約束錯誤，請檢查輸入",
        ErrorCode.DATABASE_TIMEOUT: "資料庫操作逾時，請稍後再試",
        ErrorCode.DATABASE_MIGRATION_ERROR: "資料庫遷移錯誤",
        ErrorCode.DATA_INTEGRITY_ERROR: "資料完整性錯誤",
        ErrorCode.DATABASE_LOCK_ERROR: "資料庫鎖定錯誤",
        ErrorCode.TRANSACTION_FAILED: "資料庫交易失敗",
        
        # Validation errors
        ErrorCode.VALIDATION_ERROR: "輸入驗證失敗，請檢查資料格式",
        ErrorCode.INVALID_INPUT: "輸入無效，請檢查您的資料",
        ErrorCode.MISSING_REQUIRED_FIELD: "缺少必要欄位",
        ErrorCode.INVALID_FORMAT: "資料格式不正確",
        ErrorCode.VALUE_OUT_OF_RANGE: "數值超出允許範圍",
        ErrorCode.INVALID_USER_ID: "使用者ID無效",
        ErrorCode.INVALID_GUILD_ID: "伺服器ID無效",
        ErrorCode.INVALID_ACCOUNT_ID: "帳戶ID無效",
        ErrorCode.INVALID_ACHIEVEMENT_ID: "成就ID無效",
        
        # Permission errors
        ErrorCode.PERMISSION_DENIED: "存取被拒絕，您沒有足夠的權限",
        ErrorCode.AUTHENTICATION_REQUIRED: "需要身份驗證",
        ErrorCode.AUTHORIZATION_FAILED: "授權失敗",
        ErrorCode.ACCESS_FORBIDDEN: "禁止存取",
        ErrorCode.ROLE_REQUIRED: "需要特定身分組才能執行此操作",
        
        # Resource not found errors
        ErrorCode.NOT_FOUND: "找不到請求的資源",
        ErrorCode.USER_NOT_FOUND: "找不到指定的使用者",
        ErrorCode.GUILD_NOT_FOUND: "找不到指定的伺服器",
        ErrorCode.CHANNEL_NOT_FOUND: "找不到指定的頻道",
        ErrorCode.MESSAGE_NOT_FOUND: "找不到指定的訊息",
        
        # Configuration errors
        ErrorCode.CONFIG_ERROR: "設定錯誤，請聯繫管理員",
        ErrorCode.CONFIG_MISSING: "缺少必要設定",
        ErrorCode.CONFIG_INVALID: "設定無效",
        ErrorCode.ENVIRONMENT_ERROR: "環境設定錯誤",
        
        # External service errors
        ErrorCode.EXTERNAL_SERVICE_ERROR: "外部服務錯誤，請稍後再試",
        ErrorCode.API_REQUEST_FAILED: "API 請求失敗",
        ErrorCode.API_RATE_LIMIT: "API 請求頻率限制，請稍後再試",
        ErrorCode.API_AUTHENTICATION_FAILED: "API 身份驗證失敗",
        ErrorCode.DISCORD_API_ERROR: "Discord API 錯誤",
        
        # Test orchestration errors
        ErrorCode.TEST_SETUP_ERROR: "測試環境設定失敗",
        ErrorCode.TEST_EXECUTION_ERROR: "測試執行失敗",
        ErrorCode.TEST_CLEANUP_ERROR: "測試清理失敗",
        ErrorCode.DPYTEST_ERROR: "dpytest 測試錯誤",
        ErrorCode.TEST_ISOLATION_ERROR: "測試隔離錯誤",
        
        # Activity system errors
        ErrorCode.ACTIVITY_MONITORING_ERROR: "活動監控發生錯誤",
        ErrorCode.ACTIVITY_TRACK_FAILED: "活動追蹤失敗",
        ErrorCode.ACTIVITY_THRESHOLD_ERROR: "活動閾值設定錯誤",
        ErrorCode.ACTIVITY_DATA_INVALID: "活動數據無效",
        
        # Monitoring system errors
        ErrorCode.MONITORING_ERROR: "監控系統發生錯誤",
        ErrorCode.HEALTH_CHECK_FAILED: "健康檢查失敗",
        ErrorCode.METRICS_COLLECTION_ERROR: "指標收集失敗",
        ErrorCode.ALERT_TRIGGER_ERROR: "告警觸發失敗",
        ErrorCode.PERFORMANCE_THRESHOLD_ERROR: "效能閾值錯誤",
        
        # Deployment system errors
        ErrorCode.DEPLOYMENT_ERROR: "部署發生錯誤",
        ErrorCode.DEPLOYMENT_CONFIG_ERROR: "部署配置錯誤",
        ErrorCode.DEPLOYMENT_VALIDATION_ERROR: "部署驗證失敗",
        ErrorCode.ENVIRONMENT_SETUP_ERROR: "環境設定錯誤",
        
        # Documentation system errors
        ErrorCode.DOCUMENTATION_ERROR: "文檔系統發生錯誤",
        ErrorCode.DOCUMENT_VALIDATION_ERROR: "文檔驗證失敗",
        ErrorCode.DOCUMENT_GENERATION_ERROR: "文檔生成失敗",
        ErrorCode.DOCUMENT_PARSING_ERROR: "文檔解析失敗",
    }
    
    template = message_templates.get(error_code, "發生未知錯誤")
    
    # Format template with context if available
    try:
        return template.format(**context)
    except (KeyError, ValueError):
        # If formatting fails, return the template as-is
        return template


def format_error_response(exception: Exception, 
                         include_technical_details: bool = False) -> Dict[str, Any]:
    """
    Format an exception into a standardized error response
    
    Args:
        exception: The exception to format
        include_technical_details: Whether to include technical details
        
    Returns:
        Formatted error response dictionary
    """
    error_code = map_exception_to_error_code(exception)
    
    # Extract context from AppError instances
    context = {}
    if isinstance(exception, AppError):
        context = exception.details or {}
    
    response = {
        "success": False,
        "error": {
            "code": error_code.value,
            "message": get_user_message(error_code, context),
            "type": type(exception).__name__
        }
    }
    
    # Add technical details if requested
    if include_technical_details:
        technical_details = {
            "exception_message": str(exception),
        }
        
        if isinstance(exception, AppError):
            technical_details.update({
                "details": exception.details,
                "timestamp": exception.timestamp.isoformat() if exception.timestamp else None,
                "cause": str(exception.cause) if exception.cause else None
            })
        
        response["error"]["technical_details"] = technical_details
    
    return response


def log_error(logger: logging.Logger, 
              exception: Exception, 
              context: Optional[Dict[str, Any]] = None) -> None:
    """
    Log an error with standardized formatting
    
    Args:
        logger: Logger instance to use
        exception: Exception to log
        context: Additional context for logging
    """
    error_code = map_exception_to_error_code(exception)
    context = context or {}
    
    log_data = {
        "error_code": error_code.value,
        "exception_type": type(exception).__name__,
        "message": str(exception),
        **context
    }
    
    if isinstance(exception, AppError):
        log_data.update({
            "details": exception.details,
            "cause": str(exception.cause) if exception.cause else None
        })
    
    # Log at appropriate level based on error type
    if error_code in [ErrorCode.INTERNAL_ERROR, ErrorCode.DATABASE_CONNECTION_ERROR]:
        logger.error("Error occurred: %s", log_data, exc_info=True)
    elif error_code in [ErrorCode.PERMISSION_DENIED, ErrorCode.VALIDATION_ERROR]:
        logger.warning("Warning: %s", log_data)
    else:
        logger.info("Info: %s", log_data)