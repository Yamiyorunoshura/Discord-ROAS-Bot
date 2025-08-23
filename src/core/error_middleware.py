"""
錯誤處理中介器模組
Task ID: T8 - 錯誤代碼系統統一化

這個模組提供服務層錯誤處理的標準化裝飾器和工具，確保所有服務採用一致的錯誤處理機制。

主要功能：
- 標準化錯誤處理裝飾器
- 錯誤代碼一致性驗證器  
- 錯誤處理統一格式化工具
- 錯誤記錄標準化機制
"""

import functools
import logging
import traceback
from typing import Optional, Dict, Any, Callable, Type, List
from datetime import datetime

from .errors import AppError, ServiceError, DatabaseError, ValidationError
from .error_codes import ErrorCode, map_exception_to_error_code, get_user_message, log_error, format_error_response


class ErrorCodeValidator:
    """
    錯誤代碼一致性驗證器
    
    用於檢查錯誤代碼的唯一性、完整性和一致性
    """
    
    @staticmethod
    def validate_error_code_uniqueness() -> Dict[str, List[str]]:
        """
        驗證錯誤代碼的唯一性
        
        Returns:
            包含重複錯誤代碼的字典，如果無重複則返回空字典
        """
        error_values = [code.value for code in ErrorCode]
        duplicates = {}
        seen_values = set()
        
        for value in error_values:
            if value in seen_values:
                if value not in duplicates:
                    duplicates[value] = []
                # 查找所有使用此值的錯誤代碼
                for code in ErrorCode:
                    if code.value == value:
                        duplicates[value].append(code.name)
            else:
                seen_values.add(value)
        
        return duplicates
    
    @staticmethod
    def validate_message_completeness() -> List[str]:
        """
        驗證所有錯誤代碼都有對應的使用者訊息
        
        Returns:
            缺少訊息的錯誤代碼列表
        """
        missing_messages = []
        
        for error_code in ErrorCode:
            try:
                message = get_user_message(error_code)
                if message == "發生未知錯誤" and error_code != ErrorCode.UNKNOWN_ERROR:
                    missing_messages.append(error_code.name)
            except Exception:
                missing_messages.append(error_code.name)
        
        return missing_messages
    
    @staticmethod
    def validate_error_code_format() -> List[str]:
        """
        驗證錯誤代碼格式符合規範
        
        Returns:
            格式不正確的錯誤代碼列表
        """
        invalid_formats = []
        
        for error_code in ErrorCode:
            value = error_code.value
            # 檢查格式：[MODULE]_[NUMBER]
            if '_' not in value:
                invalid_formats.append(f"{error_code.name}: 缺少分隔符 '_'")
                continue
                
            parts = value.split('_')
            if len(parts) != 2:
                invalid_formats.append(f"{error_code.name}: 格式不正確，應為 MODULE_NUMBER")
                continue
                
            module, number = parts
            if len(module) < 2 or len(module) > 4:
                invalid_formats.append(f"{error_code.name}: 模組縮寫長度應為 2-4 個字母")
                
            if not number.isdigit() or len(number) != 4:
                invalid_formats.append(f"{error_code.name}: 數字部分應為 4 位數字")
        
        return invalid_formats


class ConsistencyChecker:
    """
    錯誤處理一致性檢查器
    
    檢查服務是否採用標準化錯誤處理
    """
    
    @staticmethod
    def check_service_error_adoption(service_instance) -> Dict[str, Any]:
        """
        檢查服務是否採用標準錯誤處理
        
        Args:
            service_instance: 服務實例
            
        Returns:
            包含檢查結果的字典
        """
        results = {
            "service_name": getattr(service_instance, 'name', service_instance.__class__.__name__),
            "uses_standard_errors": True,
            "error_handling_methods": [],
            "issues": []
        }
        
        # 檢查服務方法是否使用標準化錯誤處理
        for method_name in dir(service_instance):
            if method_name.startswith('_'):
                continue
                
            method = getattr(service_instance, method_name)
            if callable(method):
                # 檢查是否有標準化錯誤處理裝飾器
                if hasattr(method, '_standardized_error_handling'):
                    results["error_handling_methods"].append(method_name)
                elif hasattr(method, '__code__'):
                    # 檢查方法內是否使用了標準錯誤類型
                    try:
                        source = method.__code__.co_names
                        if any(error_type in source for error_type in 
                               ['ServiceError', 'ValidationError', 'DatabaseError']):
                            results["error_handling_methods"].append(method_name)
                    except Exception:
                        pass
        
        if not results["error_handling_methods"]:
            results["uses_standard_errors"] = False
            results["issues"].append("未發現標準化錯誤處理的使用")
        
        return results


def standardized_error_handling(error_code: Optional[ErrorCode] = None, 
                               include_technical_details: bool = False):
    """
    標準化錯誤處理裝飾器
    
    為服務方法提供統一的錯誤處理，包括錯誤日誌記錄、錯誤代碼映射和回應格式化。
    
    Args:
        error_code: 可選的默認錯誤代碼，如果未提供將自動映射
        include_technical_details: 是否在回應中包含技術細節
    
    Usage:
        @standardized_error_handling(ErrorCode.SERVICE_ERROR)
        async def my_service_method(self):
            # 方法實作
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            service_instance = args[0] if args else None
            logger = getattr(service_instance, 'logger', logging.getLogger(func.__name__))
            
            try:
                # 執行原始方法
                return await func(*args, **kwargs)
                
            except (ServiceError, ValidationError, DatabaseError, AppError) as e:
                # 已經是標準化錯誤，直接記錄和重新拋出
                log_error(logger, e, context={
                    "method": func.__name__,
                    "service": getattr(service_instance, 'name', 'Unknown')
                })
                raise
                
            except Exception as e:
                # 非標準化錯誤，包裝為ServiceError
                wrapped_error = ServiceError(
                    service_name=getattr(service_instance, 'name', 'Unknown'),
                    operation=func.__name__,
                    message=str(e),
                    error_code=(error_code.value if error_code else 
                               map_exception_to_error_code(e).value),
                    cause=e
                )
                
                log_error(logger, wrapped_error, context={
                    "method": func.__name__,
                    "original_exception": type(e).__name__
                })
                
                raise wrapped_error
        
        # 標記方法已使用標準化錯誤處理
        wrapper._standardized_error_handling = True
        return wrapper
    
    return decorator


class ErrorMetricsCollector:
    """
    錯誤指標收集器
    
    收集和統計錯誤處理相關的指標數據
    """
    
    def __init__(self):
        self._error_counts = {}
        self._error_history = []
    
    def record_error(self, error_code: ErrorCode, service_name: str, 
                    method_name: str, timestamp: Optional[datetime] = None):
        """
        記錄錯誤發生
        
        Args:
            error_code: 錯誤代碼
            service_name: 服務名稱
            method_name: 方法名稱
            timestamp: 發生時間，默認為當前時間
        """
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        key = f"{service_name}::{method_name}::{error_code.value}"
        self._error_counts[key] = self._error_counts.get(key, 0) + 1
        
        self._error_history.append({
            "error_code": error_code.value,
            "service": service_name,
            "method": method_name,
            "timestamp": timestamp
        })
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """
        獲取錯誤統計數據
        
        Returns:
            包含錯誤統計的字典
        """
        total_errors = len(self._error_history)
        if total_errors == 0:
            return {"total_errors": 0, "error_rates": {}, "top_errors": []}
        
        # 計算錯誤率
        error_rates = {}
        for error_code in ErrorCode:
            count = sum(1 for record in self._error_history 
                       if record["error_code"] == error_code.value)
            if count > 0:
                error_rates[error_code.value] = {
                    "count": count,
                    "percentage": (count / total_errors) * 100
                }
        
        # 獲取最常見的錯誤
        top_errors = sorted(error_rates.items(), 
                           key=lambda x: x[1]["count"], reverse=True)[:10]
        
        return {
            "total_errors": total_errors,
            "error_rates": error_rates,
            "top_errors": top_errors,
            "services_affected": len(set(record["service"] for record in self._error_history))
        }


# 全局錯誤指標收集器實例
error_metrics = ErrorMetricsCollector()


def create_error_response(exception: Exception, 
                         include_technical_details: bool = False) -> Dict[str, Any]:
    """
    創建標準化錯誤回應
    
    Args:
        exception: 異常實例
        include_technical_details: 是否包含技術細節
        
    Returns:
        標準化的錯誤回應字典
    """
    return format_error_response(exception, include_technical_details)


def validate_error_handling_consistency() -> Dict[str, Any]:
    """
    驗證整個系統的錯誤處理一致性
    
    Returns:
        包含一致性檢查結果的字典
    """
    validator = ErrorCodeValidator()
    
    results = {
        "timestamp": datetime.utcnow().isoformat(),
        "overall_status": "PASS",
        "checks": {}
    }
    
    # 檢查錯誤代碼唯一性
    duplicates = validator.validate_error_code_uniqueness()
    results["checks"]["error_code_uniqueness"] = {
        "status": "PASS" if not duplicates else "FAIL",
        "duplicates": duplicates
    }
    
    # 檢查訊息完整性
    missing_messages = validator.validate_message_completeness()
    results["checks"]["message_completeness"] = {
        "status": "PASS" if not missing_messages else "FAIL",
        "missing_messages": missing_messages
    }
    
    # 檢查格式正確性
    invalid_formats = validator.validate_error_code_format()
    results["checks"]["format_validation"] = {
        "status": "PASS" if not invalid_formats else "FAIL",
        "invalid_formats": invalid_formats
    }
    
    # 更新整體狀態
    if any(check["status"] == "FAIL" for check in results["checks"].values()):
        results["overall_status"] = "FAIL"
    
    return results


# 便利函數：記錄錯誤到指標收集器
def track_error(error_code: ErrorCode, service_name: str, method_name: str):
    """
    追蹤錯誤到指標收集器
    
    Args:
        error_code: 錯誤代碼
        service_name: 服務名稱  
        method_name: 方法名稱
    """
    error_metrics.record_error(error_code, service_name, method_name)


# 便利函數：獲取錯誤統計
def get_error_stats() -> Dict[str, Any]:
    """
    獲取系統錯誤統計
    
    Returns:
        錯誤統計字典
    """
    return error_metrics.get_error_statistics()