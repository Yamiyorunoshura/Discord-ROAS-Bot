"""
資料庫操作重試機制
T3 - 併發與資料庫鎖定穩定性實施

提供指數退避重試裝飾器，專門處理 SQLite 鎖定與忙碌錯誤
實現智能重試策略以提升併發環境下的操作成功率
"""

import time
import random
import logging
import sqlite3
import functools
from typing import Callable, Optional, Union, Tuple, Any
from datetime import datetime

logger = logging.getLogger('src.db.retry')

class DatabaseRetryError(Exception):
    """資料庫重試相關錯誤"""
    
    def __init__(self, message: str, original_error: Exception = None, attempts: int = 0):
        self.message = message
        self.original_error = original_error
        self.attempts = attempts
        super().__init__(f"{message} (嘗試 {attempts} 次)")


class RetryStrategy:
    """重試策略配置類"""
    
    def __init__(
        self,
        max_retries: int = 5,
        base_delay: float = 0.1,
        max_delay: float = 30.0,
        backoff_multiplier: float = 2.0,
        jitter: bool = True,
        jitter_range: float = 0.1
    ):
        """
        初始化重試策略
        
        參數：
            max_retries: 最大重試次數
            base_delay: 基礎延遲時間（秒）
            max_delay: 最大延遲時間（秒）
            backoff_multiplier: 退避倍數
            jitter: 是否添加隨機抖動
            jitter_range: 抖動範圍（0-1之間的比例）
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_multiplier = backoff_multiplier
        self.jitter = jitter
        self.jitter_range = jitter_range
    
    def calculate_delay(self, attempt: int) -> float:
        """
        計算指定重試次數的延遲時間
        
        參數：
            attempt: 當前重試次數（從0開始）
            
        返回：
            延遲時間（秒）
        """
        # 指數退避計算
        delay = self.base_delay * (self.backoff_multiplier ** attempt)
        
        # 限制最大延遲
        delay = min(delay, self.max_delay)
        
        # 添加隨機抖動避免雷群效應
        if self.jitter:
            jitter_amount = delay * self.jitter_range * (random.random() * 2 - 1)
            delay += jitter_amount
        
        return max(0, delay)


def is_retryable_database_error(error: Exception) -> bool:
    """
    判斷資料庫錯誤是否應該重試
    
    參數：
        error: 錯誤實例
        
    返回：
        是否應該重試
    """
    if isinstance(error, sqlite3.OperationalError):
        error_msg = str(error).lower()
        
        # SQLite 鎖定相關錯誤
        if any(keyword in error_msg for keyword in [
            'database is locked',
            'database table is locked', 
            'database schema has changed',
            'cannot commit transaction',
            'sql logic error',
            'busy',
            'locked'
        ]):
            return True
    
    # 其他暫時性錯誤
    if isinstance(error, (sqlite3.IntegrityError, sqlite3.DatabaseError)):
        error_msg = str(error).lower()
        if 'temporary' in error_msg or 'retry' in error_msg:
            return True
    
    return False


def retry_on_database_locked(
    max_retries: int = 5,
    base_delay: float = 0.1,
    max_delay: float = 30.0,
    backoff_multiplier: float = 2.0,
    jitter: bool = True,
    strategy: Optional[RetryStrategy] = None,
    log_attempts: bool = True
):
    """
    資料庫鎖定重試裝飾器
    
    專門處理 SQLite 資料庫鎖定、忙碌等暫時性錯誤的重試機制
    
    參數：
        max_retries: 最大重試次數（預設5次）
        base_delay: 基礎延遲時間（預設0.1秒）
        max_delay: 最大延遲時間（預設30秒）
        backoff_multiplier: 退避倍數（預設2.0）
        jitter: 是否添加隨機抖動（預設True）
        strategy: 自定義重試策略（可選）
        log_attempts: 是否記錄重試嘗試（預設True）
    
    使用範例：
        @retry_on_database_locked(max_retries=3, base_delay=0.2)
        def update_activity(user_id, guild_id, score):
            # 資料庫操作代碼
            pass
    """
    def decorator(func: Callable) -> Callable:
        # 使用自定義策略或建立預設策略
        retry_strategy = strategy or RetryStrategy(
            max_retries=max_retries,
            base_delay=base_delay,
            max_delay=max_delay,
            backoff_multiplier=backoff_multiplier,
            jitter=jitter
        )
        
        if hasattr(func, '__call__'):
            if hasattr(func, '__code__') and func.__code__.co_flags & 0x80:  # 檢查是否為 async 函數
                return _async_retry_wrapper(func, retry_strategy, log_attempts)
            else:
                return _sync_retry_wrapper(func, retry_strategy, log_attempts)
        
        return func
    
    return decorator


def _sync_retry_wrapper(func: Callable, strategy: RetryStrategy, log_attempts: bool) -> Callable:
    """同步函數重試包裝器"""
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        last_error = None
        
        for attempt in range(strategy.max_retries + 1):
            try:
                result = func(*args, **kwargs)
                
                # 成功時記錄（僅在重試過的情況下）
                if attempt > 0 and log_attempts:
                    logger.info(
                        f"{func.__name__} 在第 {attempt + 1} 次嘗試後成功"
                    )
                
                return result
                
            except Exception as error:
                last_error = error
                
                # 檢查是否為可重試錯誤
                if not is_retryable_database_error(error):
                    if log_attempts:
                        logger.warning(
                            f"{func.__name__} 發生不可重試錯誤：{error}"
                        )
                    raise
                
                # 達到最大重試次數
                if attempt >= strategy.max_retries:
                    if log_attempts:
                        logger.error(
                            f"{func.__name__} 達到最大重試次數 {strategy.max_retries}，"
                            f"最後錯誤：{error}"
                        )
                    raise DatabaseRetryError(
                        f"達到最大重試次數 {strategy.max_retries}",
                        original_error=error,
                        attempts=attempt + 1
                    )
                
                # 計算延遲並等待
                delay = strategy.calculate_delay(attempt)
                
                if log_attempts:
                    logger.warning(
                        f"{func.__name__} 第 {attempt + 1} 次嘗試失敗：{error}，"
                        f"等待 {delay:.2f}s 後重試"
                    )
                
                time.sleep(delay)
        
        # 理論上不會到達這裡
        raise DatabaseRetryError(
            "重試邏輯異常終止",
            original_error=last_error,
            attempts=strategy.max_retries + 1
        )
    
    return wrapper


def _async_retry_wrapper(func: Callable, strategy: RetryStrategy, log_attempts: bool) -> Callable:
    """非同步函數重試包裝器"""
    
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        last_error = None
        
        for attempt in range(strategy.max_retries + 1):
            try:
                result = await func(*args, **kwargs)
                
                # 成功時記錄（僅在重試過的情況下）
                if attempt > 0 and log_attempts:
                    logger.info(
                        f"{func.__name__} 在第 {attempt + 1} 次嘗試後成功"
                    )
                
                return result
                
            except Exception as error:
                last_error = error
                
                # 檢查是否為可重試錯誤
                if not is_retryable_database_error(error):
                    if log_attempts:
                        logger.warning(
                            f"{func.__name__} 發生不可重試錯誤：{error}"
                        )
                    raise
                
                # 達到最大重試次數
                if attempt >= strategy.max_retries:
                    if log_attempts:
                        logger.error(
                            f"{func.__name__} 達到最大重試次數 {strategy.max_retries}，"
                            f"最後錯誤：{error}"
                        )
                    raise DatabaseRetryError(
                        f"達到最大重試次數 {strategy.max_retries}",
                        original_error=error,
                        attempts=attempt + 1
                    )
                
                # 計算延遲並等待
                delay = strategy.calculate_delay(attempt)
                
                if log_attempts:
                    logger.warning(
                        f"{func.__name__} 第 {attempt + 1} 次嘗試失敗：{error}，"
                        f"等待 {delay:.2f}s 後重試"
                    )
                
                # 使用 asyncio.sleep 進行非阻塞等待
                import asyncio
                await asyncio.sleep(delay)
        
        # 理論上不會到達這裡
        raise DatabaseRetryError(
            "重試邏輯異常終止",
            original_error=last_error,
            attempts=strategy.max_retries + 1
        )
    
    return wrapper


# 便利函數與常用重試策略
class CommonRetryStrategies:
    """常用重試策略預設值"""
    
    AGGRESSIVE = RetryStrategy(
        max_retries=10,
        base_delay=0.05,
        max_delay=5.0,
        backoff_multiplier=1.5,
        jitter=True
    )
    
    BALANCED = RetryStrategy(
        max_retries=5,
        base_delay=0.1,
        max_delay=30.0,
        backoff_multiplier=2.0,
        jitter=True
    )
    
    CONSERVATIVE = RetryStrategy(
        max_retries=3,
        base_delay=0.5,
        max_delay=60.0,
        backoff_multiplier=3.0,
        jitter=True
    )


def retry_database_operation(
    operation: Callable,
    *args,
    strategy: RetryStrategy = None,
    **kwargs
) -> Any:
    """
    直接重試資料庫操作（不使用裝飾器的場合）
    
    參數：
        operation: 要執行的操作函數
        *args: 操作函數的位置參數
        strategy: 重試策略（可選）
        **kwargs: 操作函數的關鍵字參數
        
    返回：
        操作結果
    """
    retry_strategy = strategy or CommonRetryStrategies.BALANCED
    
    @retry_on_database_locked(strategy=retry_strategy)
    def wrapped_operation():
        return operation(*args, **kwargs)
    
    return wrapped_operation()