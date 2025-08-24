"""
連結檢查API響應快取和錯誤處理系統
Task ID: T3 - 文檔連結有效性修復

提供高效的API響應快取機制和統一的錯誤處理
"""

import asyncio
import hashlib
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable, Union, List
from dataclasses import dataclass, asdict
from enum import Enum
import weakref

logger = logging.getLogger('services.documentation.api_cache')


class CachePolicy(Enum):
    """快取策略枚舉"""
    NO_CACHE = "no_cache"           # 不快取
    SHORT_TERM = "short_term"       # 短期快取（5分鐘）
    MEDIUM_TERM = "medium_term"     # 中期快取（30分鐘）
    LONG_TERM = "long_term"         # 長期快取（6小時）
    PERSISTENT = "persistent"       # 持久快取（直到手動清除）


class ErrorSeverity(Enum):
    """錯誤嚴重程度"""
    LOW = "low"
    MEDIUM = "medium" 
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class CacheEntry:
    """快取條目"""
    key: str
    value: Any
    created_at: datetime
    expires_at: Optional[datetime]
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    policy: CachePolicy = CachePolicy.MEDIUM_TERM
    
    @property
    def is_expired(self) -> bool:
        """檢查是否已過期"""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at
    
    @property
    def age_seconds(self) -> float:
        """獲取快取年齡（秒）"""
        return (datetime.now() - self.created_at).total_seconds()


@dataclass
class APIError:
    """API錯誤資訊"""
    error_code: str
    message: str
    severity: ErrorSeverity
    timestamp: datetime
    context: Dict[str, Any]
    traceback: Optional[str] = None
    user_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "severity": self.severity.value,
            "timestamp": self.timestamp.isoformat(),
            "context": self.context,
            "user_message": self.user_message or self.message
        }


class ResponseCache:
    """
    API響應快取管理器
    
    提供高效的響應快取機制，支援：
    - 多種快取策略
    - 自動過期處理
    - 記憶體使用控制
    - 統計資訊收集
    """
    
    def __init__(self, 
                 max_size: int = 1000,
                 default_ttl_seconds: int = 1800,  # 30分鐘
                 cleanup_interval_seconds: int = 300):  # 5分鐘清理一次
        """
        初始化響應快取
        
        參數:
            max_size: 最大快取條目數
            default_ttl_seconds: 預設TTL（秒）
            cleanup_interval_seconds: 清理間隔（秒）
        """
        self.max_size = max_size
        self.default_ttl_seconds = default_ttl_seconds
        self.cleanup_interval_seconds = cleanup_interval_seconds
        
        # 快取儲存
        self._cache: Dict[str, CacheEntry] = {}
        self._access_order: List[str] = []  # LRU追蹤
        
        # 統計資訊
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "cleanups": 0,
            "total_entries_created": 0
        }
        
        # 清理任務
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
        
        logger.info(f"ResponseCache初始化 - 最大大小: {max_size}, 預設TTL: {default_ttl_seconds}s")
    
    async def start(self):
        """啟動快取管理器"""
        if self._running:
            return
        
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("ResponseCache已啟動")
    
    async def stop(self):
        """停止快取管理器"""
        self._running = False
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("ResponseCache已停止")
    
    def get(self, key: str) -> Optional[Any]:
        """
        獲取快取值
        
        參數:
            key: 快取鍵
            
        返回:
            快取值，如果不存在或已過期則返回None
        """
        if key not in self._cache:
            self._stats["misses"] += 1
            return None
        
        entry = self._cache[key]
        
        # 檢查是否過期
        if entry.is_expired:
            self._remove_entry(key)
            self._stats["misses"] += 1
            return None
        
        # 更新訪問資訊
        entry.access_count += 1
        entry.last_accessed = datetime.now()
        
        # 更新LRU順序
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)
        
        self._stats["hits"] += 1
        logger.debug(f"快取命中: {key}")
        
        return entry.value
    
    def set(self, 
            key: str, 
            value: Any, 
            policy: CachePolicy = CachePolicy.MEDIUM_TERM,
            custom_ttl_seconds: Optional[int] = None):
        """
        設定快取值
        
        參數:
            key: 快取鍵
            value: 快取值
            policy: 快取策略
            custom_ttl_seconds: 自訂TTL（秒）
        """
        # 計算過期時間
        expires_at = None
        if policy != CachePolicy.PERSISTENT:
            ttl_seconds = custom_ttl_seconds or self._get_ttl_for_policy(policy)
            expires_at = datetime.now() + timedelta(seconds=ttl_seconds)
        
        # 創建快取條目
        entry = CacheEntry(
            key=key,
            value=value,
            created_at=datetime.now(),
            expires_at=expires_at,
            policy=policy
        )
        
        # 檢查是否需要清理空間
        if len(self._cache) >= self.max_size:
            self._evict_lru()
        
        # 設定快取
        self._cache[key] = entry
        
        # 更新LRU順序
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)
        
        self._stats["total_entries_created"] += 1
        logger.debug(f"快取設定: {key}, 策略: {policy.value}")
    
    def delete(self, key: str) -> bool:
        """
        刪除快取條目
        
        參數:
            key: 快取鍵
            
        返回:
            是否成功刪除
        """
        if key in self._cache:
            self._remove_entry(key)
            logger.debug(f"快取刪除: {key}")
            return True
        return False
    
    def clear(self):
        """清空所有快取"""
        count = len(self._cache)
        self._cache.clear()
        self._access_order.clear()
        logger.info(f"快取已清空，清理了 {count} 個條目")
    
    def exists(self, key: str) -> bool:
        """檢查快取鍵是否存在且未過期"""
        if key not in self._cache:
            return False
        
        entry = self._cache[key]
        if entry.is_expired:
            self._remove_entry(key)
            return False
        
        return True
    
    def generate_cache_key(self, 
                          method: str, 
                          *args, 
                          **kwargs) -> str:
        """
        生成快取鍵
        
        參數:
            method: 方法名稱
            args: 位置參數
            kwargs: 關鍵字參數
            
        返回:
            快取鍵
        """
        # 創建唯一標識符
        key_parts = [method]
        
        # 添加位置參數
        for arg in args:
            key_parts.append(str(arg))
        
        # 添加關鍵字參數（排序確保一致性）
        for k, v in sorted(kwargs.items()):
            key_parts.append(f"{k}={v}")
        
        key_string = "|".join(key_parts)
        
        # 生成哈希
        return hashlib.md5(key_string.encode('utf-8')).hexdigest()
    
    def get_stats(self) -> Dict[str, Any]:
        """獲取快取統計資訊"""
        total_requests = self._stats["hits"] + self._stats["misses"]
        hit_rate = (self._stats["hits"] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            **self._stats,
            "current_size": len(self._cache),
            "max_size": self.max_size,
            "hit_rate_percent": round(hit_rate, 2),
            "memory_usage": self._estimate_memory_usage(),
            "policies_distribution": self._get_policies_distribution()
        }
    
    async def _cleanup_loop(self):
        """清理循環任務"""
        while self._running:
            try:
                await asyncio.sleep(self.cleanup_interval_seconds)
                
                cleanup_count = self._cleanup_expired()
                if cleanup_count > 0:
                    self._stats["cleanups"] += 1
                    logger.debug(f"清理了 {cleanup_count} 個過期快取條目")
                
            except Exception as e:
                logger.error(f"快取清理錯誤: {e}")
    
    def _cleanup_expired(self) -> int:
        """清理過期條目"""
        expired_keys = []
        
        for key, entry in self._cache.items():
            if entry.is_expired:
                expired_keys.append(key)
        
        for key in expired_keys:
            self._remove_entry(key)
        
        return len(expired_keys)
    
    def _evict_lru(self):
        """驅逐最少使用的條目"""
        if not self._access_order:
            return
        
        lru_key = self._access_order[0]
        self._remove_entry(lru_key)
        self._stats["evictions"] += 1
        logger.debug(f"LRU驅逐: {lru_key}")
    
    def _remove_entry(self, key: str):
        """移除快取條目"""
        if key in self._cache:
            del self._cache[key]
        
        if key in self._access_order:
            self._access_order.remove(key)
    
    def _get_ttl_for_policy(self, policy: CachePolicy) -> int:
        """根據策略獲取TTL"""
        ttl_map = {
            CachePolicy.SHORT_TERM: 300,      # 5分鐘
            CachePolicy.MEDIUM_TERM: 1800,    # 30分鐘
            CachePolicy.LONG_TERM: 21600,     # 6小時
        }
        return ttl_map.get(policy, self.default_ttl_seconds)
    
    def _estimate_memory_usage(self) -> Dict[str, int]:
        """估算記憶體使用量"""
        # 這是一個簡單的估算
        total_entries = len(self._cache)
        avg_key_size = sum(len(k.encode('utf-8')) for k in self._cache.keys()) // max(total_entries, 1)
        
        return {
            "total_entries": total_entries,
            "estimated_avg_key_size_bytes": avg_key_size,
            "estimated_total_size_kb": (total_entries * (avg_key_size + 1000)) // 1024  # 粗略估算
        }
    
    def _get_policies_distribution(self) -> Dict[str, int]:
        """獲取策略分布"""
        distribution = {}
        for entry in self._cache.values():
            policy_name = entry.policy.value
            distribution[policy_name] = distribution.get(policy_name, 0) + 1
        return distribution


class ErrorHandler:
    """
    統一錯誤處理器
    
    提供統一的錯誤處理、記錄和響應機制
    """
    
    def __init__(self):
        self.error_counts: Dict[str, int] = {}
        self.error_history: List[APIError] = []
        self.max_history_size = 1000
        
        # 預定義錯誤碼映射
        self.error_definitions = {
            "LINK_CHECK_001": {
                "message": "文檔路徑不存在",
                "severity": ErrorSeverity.MEDIUM,
                "user_message": "指定的文檔路徑無法找到，請確認路徑是否正確"
            },
            "LINK_CHECK_002": {
                "message": "連結檢查超時",
                "severity": ErrorSeverity.MEDIUM,
                "user_message": "連結檢查處理時間過長，請稍後再試"
            },
            "LINK_CHECK_003": {
                "message": "檔案讀取權限不足",
                "severity": ErrorSeverity.HIGH,
                "user_message": "無法讀取指定檔案，請檢查檔案權限"
            },
            "LINK_CHECK_004": {
                "message": "配置格式錯誤",
                "severity": ErrorSeverity.HIGH,
                "user_message": "檢查配置格式有誤，請參考文檔修正"
            },
            "LINK_CHECK_005": {
                "message": "服務未初始化",
                "severity": ErrorSeverity.CRITICAL,
                "user_message": "服務尚未準備就緒，請稍後再試"
            },
            "SYSTEM_001": {
                "message": "記憶體不足",
                "severity": ErrorSeverity.CRITICAL,
                "user_message": "系統資源不足，請稍後再試"
            },
            "SYSTEM_002": {
                "message": "磁碟空間不足",
                "severity": ErrorSeverity.HIGH,
                "user_message": "系統儲存空間不足"
            }
        }
    
    def create_error(self,
                    error_code: str,
                    context: Optional[Dict[str, Any]] = None,
                    custom_message: Optional[str] = None,
                    traceback: Optional[str] = None) -> APIError:
        """
        創建API錯誤
        
        參數:
            error_code: 錯誤碼
            context: 上下文資訊
            custom_message: 自訂錯誤訊息
            traceback: 錯誤堆疊追蹤
            
        返回:
            API錯誤物件
        """
        # 獲取錯誤定義
        error_def = self.error_definitions.get(error_code, {
            "message": "未知錯誤",
            "severity": ErrorSeverity.MEDIUM,
            "user_message": "發生未知錯誤，請聯繫技術支援"
        })
        
        # 創建錯誤物件
        api_error = APIError(
            error_code=error_code,
            message=custom_message or error_def["message"],
            severity=error_def["severity"],
            timestamp=datetime.now(),
            context=context or {},
            traceback=traceback,
            user_message=error_def["user_message"]
        )
        
        # 記錄錯誤
        self._record_error(api_error)
        
        return api_error
    
    def handle_exception(self,
                        exception: Exception,
                        context: Optional[Dict[str, Any]] = None) -> APIError:
        """
        處理異常並轉換為API錯誤
        
        參數:
            exception: 異常物件
            context: 上下文資訊
            
        返回:
            API錯誤物件
        """
        import traceback as tb
        
        # 根據異常類型決定錯誤碼
        error_code = self._map_exception_to_code(exception)
        
        # 獲取錯誤堆疊追蹤
        traceback_str = ''.join(tb.format_exception(
            type(exception), exception, exception.__traceback__
        ))
        
        return self.create_error(
            error_code=error_code,
            context=context,
            custom_message=str(exception),
            traceback=traceback_str
        )
    
    def format_error_response(self, api_error: APIError) -> Dict[str, Any]:
        """
        格式化錯誤響應
        
        參數:
            api_error: API錯誤物件
            
        返回:
            格式化的錯誤響應
        """
        response = {
            "success": False,
            "error": api_error.to_dict(),
            "timestamp": datetime.now().isoformat()
        }
        
        # 根據嚴重程度添加額外資訊
        if api_error.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            response["support_info"] = {
                "contact": "請聯繫技術支援",
                "error_id": f"{api_error.error_code}_{int(api_error.timestamp.timestamp())}"
            }
        
        return response
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """獲取錯誤統計資訊"""
        total_errors = len(self.error_history)
        
        # 按嚴重程度分類
        severity_counts = {}
        for error in self.error_history:
            severity = error.severity.value
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        # 最近1小時的錯誤
        recent_cutoff = datetime.now() - timedelta(hours=1)
        recent_errors = len([
            e for e in self.error_history 
            if e.timestamp > recent_cutoff
        ])
        
        # 最常見錯誤
        top_errors = sorted(
            self.error_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        return {
            "total_errors": total_errors,
            "recent_errors_1h": recent_errors,
            "errors_by_severity": severity_counts,
            "error_counts_by_code": dict(self.error_counts),
            "top_error_codes": [{"code": code, "count": count} for code, count in top_errors],
            "history_size": len(self.error_history)
        }
    
    def _record_error(self, api_error: APIError):
        """記錄錯誤到歷史"""
        # 更新錯誤計數
        self.error_counts[api_error.error_code] = self.error_counts.get(api_error.error_code, 0) + 1
        
        # 加入歷史記錄
        self.error_history.append(api_error)
        
        # 限制歷史記錄大小
        if len(self.error_history) > self.max_history_size:
            self.error_history = self.error_history[-self.max_history_size:]
        
        # 記錄到日誌
        log_level = self._get_log_level(api_error.severity)
        logger.log(
            log_level,
            f"API錯誤 [{api_error.error_code}]: {api_error.message}",
            extra={"context": api_error.context}
        )
    
    def _map_exception_to_code(self, exception: Exception) -> str:
        """將異常映射到錯誤碼"""
        exception_map = {
            FileNotFoundError: "LINK_CHECK_001",
            PermissionError: "LINK_CHECK_003",
            TimeoutError: "LINK_CHECK_002",
            MemoryError: "SYSTEM_001",
            OSError: "SYSTEM_002"
        }
        
        for exc_type, error_code in exception_map.items():
            if isinstance(exception, exc_type):
                return error_code
        
        return "SYSTEM_001"  # 預設錯誤碼
    
    def _get_log_level(self, severity: ErrorSeverity) -> int:
        """根據嚴重程度獲取日誌級別"""
        level_map = {
            ErrorSeverity.LOW: logging.INFO,
            ErrorSeverity.MEDIUM: logging.WARNING,
            ErrorSeverity.HIGH: logging.ERROR,
            ErrorSeverity.CRITICAL: logging.CRITICAL
        }
        return level_map.get(severity, logging.ERROR)


def cached_api_call(cache: ResponseCache, 
                   policy: CachePolicy = CachePolicy.MEDIUM_TERM,
                   ttl_seconds: Optional[int] = None):
    """
    API呼叫快取裝飾器
    
    參數:
        cache: 快取管理器
        policy: 快取策略
        ttl_seconds: 自訂TTL
    """
    def decorator(func: Callable):
        async def wrapper(*args, **kwargs):
            # 生成快取鍵
            cache_key = cache.generate_cache_key(func.__name__, *args, **kwargs)
            
            # 嘗試從快取獲取
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # 執行函數
            result = await func(*args, **kwargs)
            
            # 儲存到快取
            cache.set(cache_key, result, policy, ttl_seconds)
            
            return result
        
        return wrapper
    return decorator