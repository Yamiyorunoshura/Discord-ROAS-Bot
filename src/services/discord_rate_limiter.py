"""
Discord API 速率限制和重試機制
Task ID: 3 - 子機器人聊天功能和管理系統開發

提供Discord API調用的速率限制管理和錯誤重試機制：
- 全局速率限制管理
- 每個端點的獨立速率限制
- 智能重試機制
- 429錯誤處理
- 連線錯誤恢復
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional, Callable, Awaitable
from datetime import datetime, timedelta
from enum import Enum
import random

try:
    import discord
    from discord.errors import HTTPException, RateLimited, DiscordServerError
    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False
    discord = None
    HTTPException = Exception
    RateLimited = Exception
    DiscordServerError = Exception

from src.core.errors import ExternalServiceError, SubBotError

logger = logging.getLogger('discord.rate_limiter')


class RetryStrategy(Enum):
    """重試策略枚舉"""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_DELAY = "fixed_delay"
    NO_RETRY = "no_retry"


class RateLimitBucket:
    """Discord API速率限制桶"""
    
    def __init__(self, endpoint: str, limit: int = 5, reset_interval: int = 1):
        self.endpoint = endpoint
        self.limit = limit
        self.reset_interval = reset_interval  # 重置間隔（秒）
        
        self.remaining = limit
        self.reset_at = None
        self.requests = []
        
    def can_make_request(self) -> bool:
        """檢查是否可以發出請求"""
        now = time.time()
        
        # 清理過期的請求記錄
        self.requests = [req_time for req_time in self.requests if now - req_time < self.reset_interval]
        
        # 檢查是否超過限制
        if len(self.requests) >= self.limit:
            return False
            
        return True
    
    def consume_request(self):
        """消耗一個請求配額"""
        now = time.time()
        self.requests.append(now)
        
    def time_until_reset(self) -> float:
        """計算到重置的時間（秒）"""
        if not self.requests:
            return 0
            
        oldest_request = min(self.requests)
        reset_time = oldest_request + self.reset_interval
        return max(0, reset_time - time.time())


class DiscordRateLimiter:
    """Discord API速率限制管理器"""
    
    def __init__(self, global_rate_limit: int = 50, global_reset_interval: int = 1):
        self.global_rate_limit = global_rate_limit
        self.global_reset_interval = global_reset_interval
        
        # 全局速率限制桶
        self.global_bucket = RateLimitBucket("global", global_rate_limit, global_reset_interval)
        
        # 端點特定的速率限制桶
        self.endpoint_buckets: Dict[str, RateLimitBucket] = {}
        
        # 預設的端點限制
        self.default_endpoint_limits = {
            "send_message": RateLimitBucket("send_message", 5, 5),  # 每5秒5條訊息
            "edit_message": RateLimitBucket("edit_message", 5, 1),
            "delete_message": RateLimitBucket("delete_message", 5, 1),
            "get_channel": RateLimitBucket("get_channel", 50, 1),
            "create_guild_channel": RateLimitBucket("create_guild_channel", 10, 600),  # 每10分鐘10個頻道
        }
        
        # 初始化端點桶
        for endpoint, bucket in self.default_endpoint_limits.items():
            self.endpoint_buckets[endpoint] = bucket
        
        self.logger = logging.getLogger(f'{__name__}.RateLimiter')
    
    def get_endpoint_bucket(self, endpoint: str) -> RateLimitBucket:
        """獲取或創建端點速率限制桶"""
        if endpoint not in self.endpoint_buckets:
            # 創建預設桶
            self.endpoint_buckets[endpoint] = RateLimitBucket(endpoint)
            
        return self.endpoint_buckets[endpoint]
    
    async def acquire(self, endpoint: str = "default") -> None:
        """獲取請求許可（可能需要等待）"""
        global_bucket = self.global_bucket
        endpoint_bucket = self.get_endpoint_bucket(endpoint)
        
        # 檢查全局限制
        while not global_bucket.can_make_request():
            wait_time = global_bucket.time_until_reset()
            if wait_time > 0:
                self.logger.debug(f"全局速率限制，等待 {wait_time:.2f} 秒")
                await asyncio.sleep(wait_time)
        
        # 檢查端點特定限制
        while not endpoint_bucket.can_make_request():
            wait_time = endpoint_bucket.time_until_reset()
            if wait_time > 0:
                self.logger.debug(f"端點 {endpoint} 速率限制，等待 {wait_time:.2f} 秒")
                await asyncio.sleep(wait_time)
        
        # 消耗配額
        global_bucket.consume_request()
        endpoint_bucket.consume_request()
        
        self.logger.debug(f"獲得 {endpoint} 請求許可")
    
    def update_from_response_headers(self, endpoint: str, headers: Dict[str, str]):
        """從Discord API回應標頭更新速率限制資訊"""
        bucket = self.get_endpoint_bucket(endpoint)
        
        if 'X-RateLimit-Remaining' in headers:
            bucket.remaining = int(headers['X-RateLimit-Remaining'])
        
        if 'X-RateLimit-Reset' in headers:
            bucket.reset_at = float(headers['X-RateLimit-Reset'])
        
        if 'X-RateLimit-Limit' in headers:
            bucket.limit = int(headers['X-RateLimit-Limit'])
        
        self.logger.debug(f"更新 {endpoint} 速率限制: {bucket.remaining}/{bucket.limit}")


class DiscordRetryManager:
    """Discord API重試管理器"""
    
    def __init__(self, 
                 max_retries: int = 3,
                 base_delay: float = 1.0,
                 max_delay: float = 60.0,
                 strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF,
                 jitter: bool = True):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.strategy = strategy
        self.jitter = jitter
        
        # 可重試的異常類型
        self.retryable_exceptions = {
            RateLimited,
            DiscordServerError,
            ConnectionError,
            asyncio.TimeoutError,
            OSError  # 網路相關錯誤
        }
        
        self.logger = logging.getLogger(f'{__name__}.RetryManager')
    
    def calculate_delay(self, attempt: int, exception: Exception = None) -> float:
        """計算重試延遲時間"""
        if isinstance(exception, RateLimited) and hasattr(exception, 'retry_after'):
            # 對於429錯誤，使用Discord提供的重試時間
            delay = exception.retry_after
            self.logger.info(f"Discord速率限制，等待 {delay} 秒")
            return delay
        
        if self.strategy == RetryStrategy.NO_RETRY:
            return 0
        elif self.strategy == RetryStrategy.FIXED_DELAY:
            delay = self.base_delay
        elif self.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = self.base_delay * attempt
        elif self.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = self.base_delay * (2 ** (attempt - 1))
        else:
            delay = self.base_delay
        
        # 添加抖動以避免雷群效應
        if self.jitter:
            delay = delay * (0.5 + random.random() * 0.5)
        
        # 限制最大延遲
        delay = min(delay, self.max_delay)
        
        return delay
    
    def is_retryable(self, exception: Exception) -> bool:
        """檢查異常是否可以重試"""
        if not DISCORD_AVAILABLE:
            return False
            
        for retryable_type in self.retryable_exceptions:
            if isinstance(exception, retryable_type):
                return True
        
        # 檢查HTTPException的特定狀態碼
        if isinstance(exception, HTTPException):
            # 429 (Too Many Requests), 500-599 (Server Errors) 可以重試
            if exception.status in [429] or 500 <= exception.status <= 599:
                return True
        
        return False
    
    async def execute_with_retry(self, 
                                coro_func: Callable[[], Awaitable[Any]], 
                                context: str = "Discord API call") -> Any:
        """執行帶重試的協程函數"""
        last_exception = None
        
        for attempt in range(1, self.max_retries + 1):
            try:
                self.logger.debug(f"{context} - 嘗試 {attempt}/{self.max_retries}")
                result = await coro_func()
                
                if attempt > 1:
                    self.logger.info(f"{context} - 重試成功，嘗試次數: {attempt}")
                
                return result
                
            except Exception as e:
                last_exception = e
                
                if not self.is_retryable(e):
                    self.logger.error(f"{context} - 不可重試的錯誤: {e}")
                    break
                
                if attempt >= self.max_retries:
                    self.logger.error(f"{context} - 達到最大重試次數 {self.max_retries}")
                    break
                
                delay = self.calculate_delay(attempt, e)
                self.logger.warning(f"{context} - 嘗試 {attempt} 失敗: {e}, {delay:.2f}秒後重試")
                
                if delay > 0:
                    await asyncio.sleep(delay)
        
        # 重試失敗，拋出最後的異常
        if isinstance(last_exception, (RateLimited, HTTPException)):
            raise ExternalServiceError(
                service_name="Discord",
                operation=context,
                status_code=getattr(last_exception, 'status', None),
                message=str(last_exception),
                cause=last_exception
            )
        else:
            raise SubBotError(f"{context} 失敗，已達最大重試次數: {str(last_exception)}")


class DiscordAPIManager:
    """Discord API管理器，整合速率限制和重試機制"""
    
    def __init__(self, 
                 rate_limiter: Optional[DiscordRateLimiter] = None,
                 retry_manager: Optional[DiscordRetryManager] = None):
        self.rate_limiter = rate_limiter or DiscordRateLimiter()
        self.retry_manager = retry_manager or DiscordRetryManager()
        
        self.logger = logging.getLogger(f'{__name__}.APIManager')
    
    async def safe_api_call(self, 
                           coro_func: Callable[[], Awaitable[Any]], 
                           endpoint: str = "default",
                           context: str = "Discord API call") -> Any:
        """安全的Discord API調用，包含速率限制和重試機制"""
        
        async def wrapped_call():
            # 獲取速率限制許可
            await self.rate_limiter.acquire(endpoint)
            
            try:
                # 執行實際的API調用
                result = await coro_func()
                
                # 如果有Discord響應對象，更新速率限制資訊
                if hasattr(result, 'response') and hasattr(result.response, 'headers'):
                    self.rate_limiter.update_from_response_headers(endpoint, result.response.headers)
                
                return result
                
            except Exception as e:
                self.logger.debug(f"{context} API調用失敗: {e}")
                raise
        
        # 使用重試機制執行
        return await self.retry_manager.execute_with_retry(wrapped_call, context)
    
    async def send_message_safe(self, channel, content: str, **kwargs) -> Any:
        """安全發送訊息"""
        return await self.safe_api_call(
            lambda: channel.send(content, **kwargs),
            endpoint="send_message",
            context=f"發送訊息到頻道 {getattr(channel, 'id', 'unknown')}"
        )
    
    async def edit_message_safe(self, message, **kwargs) -> Any:
        """安全編輯訊息"""
        return await self.safe_api_call(
            lambda: message.edit(**kwargs),
            endpoint="edit_message",
            context=f"編輯訊息 {getattr(message, 'id', 'unknown')}"
        )
    
    async def delete_message_safe(self, message) -> Any:
        """安全刪除訊息"""
        return await self.safe_api_call(
            lambda: message.delete(),
            endpoint="delete_message",
            context=f"刪除訊息 {getattr(message, 'id', 'unknown')}"
        )


# 全局實例
default_api_manager = DiscordAPIManager()