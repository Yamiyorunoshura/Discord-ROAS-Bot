"""
統一錯誤處理模塊
- 提供標準化的錯誤處理機制
- 支援追蹤碼系統
- 統一的日誌記錄格式
- 分級錯誤處理和自動恢復
"""

import asyncio
import contextlib
import logging
import traceback
import time
from datetime import datetime, timedelta
from typing import Optional, Any, Union, Dict, Callable, List, Tuple
from enum import Enum

import discord
from discord.ext import commands

# 錯誤嚴重程度分級
class ErrorSeverity(Enum):
    """錯誤嚴重程度"""
    LOW = "LOW"           # 輕微錯誤，不影響功能
    MEDIUM = "MEDIUM"     # 中等錯誤，部分功能受影響
    HIGH = "HIGH"         # 嚴重錯誤，主要功能受影響
    CRITICAL = "CRITICAL" # 致命錯誤，系統無法正常運行

# 錯誤分類常數
class ErrorCodes:
    """錯誤代碼分類"""
    STARTUP_ERROR = (1, 99)      # 啟動錯誤
    DATABASE_ERROR = (101, 199)  # 資料庫錯誤
    NETWORK_ERROR = (201, 299)   # 網路錯誤
    PERMISSION_ERROR = (301, 399) # 權限錯誤
    CONFIG_ERROR = (401, 499)    # 配置錯誤
    MODULE_ERROR = (501, 599)    # 模組特定錯誤
    PANEL_ERROR = (601, 699)     # 面板錯誤
    API_ERROR = (701, 799)       # API 錯誤
    CACHE_ERROR = (801, 899)     # 快取錯誤

# 錯誤恢復策略
class RecoveryStrategy:
    """錯誤恢復策略"""
    
    def __init__(self, name: str, max_retries: int = 3, retry_delay: float = 1.0):
        self.name = name
        self.max_retries = max_retries
        self.retry_delay = retry_delay
    
    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """執行恢復策略"""
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    continue
                else:
                    raise last_error

class ErrorStatistics:
    """錯誤統計"""
    
    def __init__(self):
        self.error_counts: Dict[str, int] = {}
        self.error_history: List[Tuple[datetime, str, str]] = []
        self.last_reset = datetime.utcnow()
    
    def record_error(self, error_type: str, tracking_id: str):
        """記錄錯誤"""
        self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
        self.error_history.append((datetime.utcnow(), error_type, tracking_id))
        
        # 保持歷史記錄在合理範圍內
        if len(self.error_history) > 1000:
            self.error_history = self.error_history[-500:]
    
    def get_error_rate(self, minutes: int = 60) -> Dict[str, int]:
        """獲取指定時間內的錯誤率"""
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        recent_errors = [e for e in self.error_history if e[0] > cutoff]
        
        error_rate = {}
        for _, error_type, _ in recent_errors:
            error_rate[error_type] = error_rate.get(error_type, 0) + 1
        
        return error_rate
    
    def reset_statistics(self):
        """重置統計"""
        self.error_counts.clear()
        self.error_history.clear()
        self.last_reset = datetime.utcnow()

class ErrorHandler:
    """統一錯誤處理器"""
    
    def __init__(self, module_name: str, logger: logging.Logger | None = None):
        """
        初始化錯誤處理器
        
        Args:
            module_name: 模組名稱
            logger: 日誌記錄器
        """
        self.module_name = module_name
        self.logger = logger or logging.getLogger(module_name)
        self.statistics = ErrorStatistics()
        self.recovery_strategies: Dict[str, RecoveryStrategy] = {}
        self.error_callbacks: Dict[ErrorSeverity, List[Callable]] = {
            severity: [] for severity in ErrorSeverity
        }
        
        # 預設恢復策略
        self._setup_default_strategies()
    
    def _setup_default_strategies(self):
        """設置預設恢復策略"""
        self.recovery_strategies.update({
            "database_retry": RecoveryStrategy("資料庫重試", max_retries=3, retry_delay=1.0),
            "network_retry": RecoveryStrategy("網路重試", max_retries=2, retry_delay=2.0),
            "cache_retry": RecoveryStrategy("快取重試", max_retries=1, retry_delay=0.5),
            "api_retry": RecoveryStrategy("API重試", max_retries=2, retry_delay=1.5)
        })
    
    def add_recovery_strategy(self, name: str, strategy: RecoveryStrategy):
        """添加自定義恢復策略"""
        self.recovery_strategies[name] = strategy
    
    def add_error_callback(self, severity: ErrorSeverity, callback: Callable):
        """添加錯誤回調函數"""
        self.error_callbacks[severity].append(callback)
    
    def generate_tracking_id(self, error_code: int = 999) -> str:
        """
        生成追蹤碼
        
        Args:
            error_code: 錯誤代碼
            
        Returns:
            str: 追蹤碼
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
        return f"TRK-{self.module_name[:3].upper()}-{error_code:03d}-{timestamp[-8:]}"
    
    def classify_error(self, error: Exception) -> Tuple[ErrorSeverity, int]:
        """
        分類錯誤嚴重程度和代碼
        
        Args:
            error: 錯誤對象
            
        Returns:
            Tuple[ErrorSeverity, int]: 嚴重程度和錯誤代碼
        """
        error_type = type(error).__name__
        
        # 根據錯誤類型分類
        if isinstance(error, (discord.NotFound, discord.Forbidden)):
            return ErrorSeverity.LOW, 301
        elif isinstance(error, (discord.HTTPException, ConnectionError)):
            return ErrorSeverity.MEDIUM, 201
        elif isinstance(error, (asyncio.TimeoutError, TimeoutError)):
            return ErrorSeverity.MEDIUM, 202
        elif isinstance(error, (MemoryError, SystemError)):
            return ErrorSeverity.CRITICAL, 1
        elif "database" in error_type.lower():
            return ErrorSeverity.HIGH, 101
        elif "permission" in error_type.lower():
            return ErrorSeverity.LOW, 301
        else:
            return ErrorSeverity.MEDIUM, 999
    
    def format_user_friendly_message(self, error: Exception, severity: ErrorSeverity, 
                                    tracking_id: str) -> str:
        """
        格式化用戶友好的錯誤訊息
        
        Args:
            error: 錯誤對象
            severity: 錯誤嚴重程度
            tracking_id: 追蹤碼
            
        Returns:
            str: 用戶友好的錯誤訊息
        """
        # 根據錯誤類型提供具體建議
        if isinstance(error, discord.NotFound):
            return "❌ 找不到指定的資源，可能已被刪除或移動。"
        elif isinstance(error, discord.Forbidden):
            return "❌ 機器人沒有執行此操作的權限，請檢查權限設定。"
        elif isinstance(error, (discord.HTTPException, ConnectionError)):
            return "❌ 網路連線發生問題，請稍後再試。"
        elif isinstance(error, (asyncio.TimeoutError, TimeoutError)):
            return "❌ 操作超時，請稍後再試。"
        elif "database" in type(error).__name__.lower():
            return "❌ 資料庫連線發生問題，正在嘗試恢復。"
        else:
            # 根據嚴重程度提供不同訊息
            if severity == ErrorSeverity.LOW:
                return "❌ 發生輕微錯誤，功能可能受到輕微影響。"
            elif severity == ErrorSeverity.MEDIUM:
                return "❌ 發生錯誤，部分功能可能暫時無法使用。"
            elif severity == ErrorSeverity.HIGH:
                return "❌ 發生嚴重錯誤，主要功能可能受到影響。"
            else:  # CRITICAL
                return "❌ 發生致命錯誤，系統可能無法正常運行。"
    
    def format_error_message(self, user_msg: str, tracking_id: str, 
                           severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                           suggestions: List[str | None] = None) -> str:
        """
        格式化錯誤訊息
        
        Args:
            user_msg: 用戶訊息
            tracking_id: 追蹤碼
            severity: 錯誤嚴重程度
            suggestions: 建議解決方案
            
        Returns:
            str: 格式化後的錯誤訊息
        """
        # 根據嚴重程度選擇表情符號
        severity_icons = {
            ErrorSeverity.LOW: "⚠️",
            ErrorSeverity.MEDIUM: "❌",
            ErrorSeverity.HIGH: "🚨",
            ErrorSeverity.CRITICAL: "💥"
        }
        
        icon = severity_icons.get(severity, "❌")
        message = f"{icon} {user_msg}\n\n📋 追蹤碼：`{tracking_id}`"
        
        if suggestions:
            message += "\n\n💡 **建議解決方案：**"
            for i, suggestion in enumerate(suggestions, 1):
                message += f"\n{i}. {suggestion}"
        
        if severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            message += "\n\n🔧 如果問題持續發生，請聯絡管理員並提供追蹤碼。"
        
        return message
    
    def log_error(self, error: Exception, context: str, tracking_id: str, 
                  severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                  extra_info: Dict[str, Any | None] = None):
        """
        記錄錯誤到日誌
        
        Args:
            error: 錯誤對象
            context: 上下文描述
            tracking_id: 追蹤碼
            severity: 錯誤嚴重程度
            extra_info: 額外信息
        """
        # 記錄到統計
        error_type = type(error).__name__
        self.statistics.record_error(error_type, tracking_id)
        
        # 格式化日誌訊息
        error_msg = f"[{severity.value}] 【{self.module_name}】{context} ({tracking_id})"
        
        if extra_info:
            error_msg += f" | 額外信息: {extra_info}"
        
        # 根據嚴重程度選擇日誌等級
        if severity == ErrorSeverity.LOW:
            self.logger.warning(error_msg, exc_info=True)
        elif severity == ErrorSeverity.MEDIUM:
            self.logger.error(error_msg, exc_info=True)
        else:  # HIGH or CRITICAL
            self.logger.critical(error_msg, exc_info=True)
        
        # 執行錯誤回調
        for callback in self.error_callbacks.get(severity, []):
            try:
                asyncio.create_task(callback(error, tracking_id, extra_info))
            except Exception as callback_error:
                self.logger.error(f"錯誤回調失敗: {callback_error}")
    
    async def try_recovery(self, strategy_name: str, func: Callable, *args, **kwargs) -> Any:
        """
        嘗試錯誤恢復
        
        Args:
            strategy_name: 恢復策略名稱
            func: 要執行的函數
            *args, **kwargs: 函數參數
            
        Returns:
            Any: 函數執行結果
        """
        if strategy_name not in self.recovery_strategies:
            raise ValueError(f"未知的恢復策略: {strategy_name}")
        
        strategy = self.recovery_strategies[strategy_name]
        return await strategy.execute(func, *args, **kwargs)
    
    @contextlib.contextmanager
    def handle_error(self, interaction_or_ctx: commands.Context | discord.Interaction | None = None,
                     user_msg: str = "發生未知錯誤", error_code: int = 999,
                     recovery_strategy: str | None = None,
                     auto_classify: bool = True):
        """
        統一的錯誤處理上下文管理器
        
        Args:
            interaction_or_ctx: Discord 互動或上下文
            user_msg: 用戶訊息
            error_code: 錯誤代碼
            recovery_strategy: 恢復策略名稱
            auto_classify: 是否自動分類錯誤
        """
        tracking_id = self.generate_tracking_id(error_code)
        
        try:
            yield tracking_id
        except Exception as exc:
            # 自動分類錯誤
            if auto_classify:
                severity, classified_code = self.classify_error(exc)
                error_code = classified_code
            else:
                severity = ErrorSeverity.MEDIUM
            
            # 嘗試恢復（如果指定了恢復策略）
            if recovery_strategy and recovery_strategy in self.recovery_strategies:
                try:
                    self.logger.info(f"嘗試使用 {recovery_strategy} 策略恢復錯誤")
                    # 這裡需要具體的恢復邏輯，暫時只記錄
                except Exception as recovery_error:
                    self.logger.error(f"錯誤恢復失敗: {recovery_error}")
            
            # 記錄錯誤
            self.log_error(exc, user_msg, tracking_id, severity)
            
            # 生成用戶友好的錯誤訊息
            if auto_classify:
                formatted_msg = self.format_user_friendly_message(exc, severity, tracking_id)
            else:
                formatted_msg = self.format_error_message(user_msg, tracking_id, severity)
            
            # 發送錯誤訊息給用戶
            try:
                if isinstance(interaction_or_ctx, discord.Interaction):
                    if interaction_or_ctx.response.is_done():
                        asyncio.create_task(interaction_or_ctx.followup.send(formatted_msg, ephemeral=True))
                    else:
                        asyncio.create_task(interaction_or_ctx.response.send_message(formatted_msg, ephemeral=True))
                elif isinstance(interaction_or_ctx, commands.Context):
                    asyncio.create_task(interaction_or_ctx.reply(formatted_msg, mention_author=False))
            except Exception:
                # 如果連錯誤訊息都發送失敗，只記錄到日誌
                self.logger.error(f"無法發送錯誤訊息：{tracking_id}")
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """獲取錯誤統計信息"""
        return {
            "total_errors": sum(self.statistics.error_counts.values()),
            "error_counts": self.statistics.error_counts.copy(),
            "recent_error_rate": self.statistics.get_error_rate(60),
            "last_reset": self.statistics.last_reset.isoformat(),
            "total_history_entries": len(self.statistics.error_history)
        }
    
    def reset_statistics(self):
        """重置錯誤統計"""
        self.statistics.reset_statistics()

def create_error_handler(module_name: str, logger: logging.Logger | None = None) -> ErrorHandler:
    """
    創建錯誤處理器的工廠函數
    
    Args:
        module_name: 模組名稱
        logger: 日誌記錄器
        
    Returns:
        ErrorHandler: 錯誤處理器實例
    """
    return ErrorHandler(module_name, logger)

# 常用的錯誤處理裝飾器
def error_handler(module_name: str, error_code: int = 999, user_msg: str = "操作失敗",
                 recovery_strategy: str | None = None, auto_classify: bool = True):
    """
    錯誤處理裝飾器
    
    Args:
        module_name: 模組名稱
        error_code: 錯誤代碼
        user_msg: 用戶訊息
        recovery_strategy: 恢復策略名稱
        auto_classify: 是否自動分類錯誤
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            handler = create_error_handler(module_name)
            
            # 嘗試從參數中找到 interaction 或 context
            interaction_or_ctx = None
            for arg in args:
                if isinstance(arg, (discord.Interaction, commands.Context)):
                    interaction_or_ctx = arg
                    break
            
            with handler.handle_error(interaction_or_ctx, user_msg, error_code, 
                                    recovery_strategy, auto_classify):
                return await func(*args, **kwargs)
        
        return wrapper
    return decorator 