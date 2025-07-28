"""企業級結構化日誌系統

基於structlog的現代化日誌系統,提供:
- JSON格式結構化日誌
- 告警機制整合
- 分散式追蹤支援
- 多輸出目標
- 效能優化
- Discord Bot特定欄位支援
"""

from __future__ import annotations

import asyncio
import contextlib
import functools
import json
import logging
import logging.handlers
import time
import uuid
from abc import ABC, abstractmethod
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import aiohttp
import structlog
from rich.console import Console
from rich.logging import RichHandler

from src.core.config import Settings, get_settings

# =====================================================
# 分散式追蹤系統 (Distributed Tracing System)
# =====================================================

# 追蹤上下文
request_trace_id: ContextVar[str] = ContextVar("request_trace_id", default=None)
operation_span_id: ContextVar[str] = ContextVar("operation_span_id", default=None)
user_context: ContextVar[dict[str, Any]] = ContextVar("user_context", default={})
guild_context: ContextVar[dict[str, Any]] = ContextVar("guild_context", default={})


@dataclass
class TraceContext:
    """追蹤上下文資料類

    用於追蹤分散式操作的上下文信息.
    """

    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    operation_name: str = ""
    start_time: float = 0.0
    user_id: int | None = None
    username: str | None = None
    guild_id: int | None = None
    guild_name: str | None = None
    channel_id: int | None = None
    channel_name: str | None = None
    command: str | None = None
    tags: dict[str, Any] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = {}
        if self.start_time == 0.0:
            self.start_time = time.time()


class TraceManager:
    """追蹤管理器

    負責管理分散式追蹤的生命週期.
    """

    @staticmethod
    def start_trace(operation_name: str = "") -> TraceContext:
        """開始新的追蹤

        Args:
            operation_name: 操作名稱

        Returns:
            TraceContext: 追蹤上下文
        """
        trace_id = str(uuid.uuid4())
        span_id = str(uuid.uuid4())

        # 設定上下文變數
        request_trace_id.set(trace_id)
        operation_span_id.set(span_id)

        return TraceContext(
            trace_id=trace_id, span_id=span_id, operation_name=operation_name
        )

    @staticmethod
    def start_span(
        operation_name: str, parent_trace: TraceContext | None = None
    ) -> TraceContext:
        """開始新的Span

        Args:
            operation_name: 操作名稱
            parent_trace: 父追蹤上下文

        Returns:
            TraceContext: 新的Span上下文
        """
        current_trace_id = request_trace_id.get()

        if current_trace_id is None and parent_trace:
            current_trace_id = parent_trace.trace_id
            request_trace_id.set(current_trace_id)
        elif current_trace_id is None:
            # 沒有當前追蹤,開始新的
            return TraceManager.start_trace(operation_name)

        span_id = str(uuid.uuid4())
        parent_span_id = (
            operation_span_id.get() if parent_trace is None else parent_trace.span_id
        )

        # 更新當前Span
        operation_span_id.set(span_id)

        return TraceContext(
            trace_id=current_trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            operation_name=operation_name,
        )

    @staticmethod
    def get_current_trace() -> TraceContext | None:
        """獲取當前追蹤上下文

        Returns:
            Optional[TraceContext]: 當前追蹤上下文,如果不存在則返回None
        """
        trace_id = request_trace_id.get()
        span_id = operation_span_id.get()

        if trace_id is None:
            return None

        # 獲取用戶和伺服器上下文
        user = user_context.get({})
        guild = guild_context.get({})

        return TraceContext(
            trace_id=trace_id,
            span_id=span_id or str(uuid.uuid4()),
            user_id=user.get("user_id"),
            username=user.get("username"),
            guild_id=guild.get("guild_id"),
            guild_name=guild.get("guild_name"),
            channel_id=guild.get("channel_id"),
            channel_name=guild.get("channel_name"),
        )

    @staticmethod
    def set_user_context(user_id: int, username: str):
        """設定用戶上下文

        Args:
            user_id: 用戶ID
            username: 用戶名
        """
        user_context.set({"user_id": user_id, "username": username})

    @staticmethod
    def set_guild_context(
        guild_id: int,
        guild_name: str,
        channel_id: int | None = None,
        channel_name: str | None = None,
    ):
        """設定伺服器上下文

        Args:
            guild_id: 伺服器ID
            guild_name: 伺服器名稱
            channel_id: 頻道ID
            channel_name: 頻道名稱
        """
        guild_context.set(
            {
                "guild_id": guild_id,
                "guild_name": guild_name,
                "channel_id": channel_id,
                "channel_name": channel_name,
            }
        )

    @staticmethod
    def clear_context():
        """清除所有上下文"""
        request_trace_id.set(None)
        operation_span_id.set(None)
        user_context.set({})
        guild_context.set({})


# =====================================================
# 告警系統 (Alert System)
# =====================================================


@dataclass
class LogAlert:
    """日誌告警配置"""

    id: str
    name: str
    level: str  # ERROR, CRITICAL, WARNING
    pattern: str  # 正則表達式或關鍵字
    threshold: int  # 闾值
    window_seconds: int  # 時間窗口
    cooldown_seconds: int = 300  # 冷卻時間(預設5分鐘)
    enabled: bool = True
    count: int = 0
    last_reset: float = 0.0
    last_triggered: float = 0.0

    def __post_init__(self):
        if self.last_reset == 0.0:
            self.last_reset = time.time()

    def should_reset(self) -> bool:
        """檢查是否應該重設計數器"""
        return time.time() - self.last_reset > self.window_seconds

    def is_in_cooldown(self) -> bool:
        """檢查是否在冷卻時間內"""
        return time.time() - self.last_triggered < self.cooldown_seconds


class AlertHandler(ABC):
    """告警處理器抽象基類"""

    @abstractmethod
    async def handle_alert(
        self, alert: LogAlert, record: dict[str, Any], context: dict[str, Any]
    ):
        """處理告警

        Args:
            alert: 告警配置
            record: 觸發的日誌記錄
            context: 相關上下文
        """
        pass


class DiscordWebhookAlertHandler(AlertHandler):
    """使用Discord Webhook的告警處理器"""

    def __init__(self, webhook_url: str, mention_role_id: str | None = None):
        """初始化Discord Webhook告警處理器

        Args:
            webhook_url: Discord Webhook URL
            mention_role_id: 要@的角色ID
        """
        self.webhook_url = webhook_url
        self.mention_role_id = mention_role_id

    async def handle_alert(
        self, alert: LogAlert, record: dict[str, Any], context: dict[str, Any]
    ):
        """發送告警到Discord"""
        try:
            embed = self._create_alert_embed(alert, record, context)
            payload = {"embeds": [embed]}

            # 如果有角色ID,添加@提及
            if self.mention_role_id:
                payload["content"] = f"<@&{self.mention_role_id}>"

            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json=payload) as response:
                    if response.status != 204:
                        print(f"Discord webhook 送信失敗: {response.status}")

        except Exception as e:
            print(f"Discord 告警處理失敗: {e}")

    def _create_alert_embed(
        self, alert: LogAlert, record: dict[str, Any], context: dict[str, Any]
    ) -> dict[str, Any]:
        """創建告警的Discord Embed"""
        # 根據級別設定顏色
        colors = {
            "CRITICAL": 0x8B0000,  # 暗紅色
            "ERROR": 0xFF0000,  # 紅色
            "WARNING": 0xFFA500,  # 橙色
            "INFO": 0x0000FF,  # 藍色
        }

        embed = {
            "title": f"🚨 {alert.level} 告警: {alert.name}",
            "description": f"模式: `{alert.pattern}`",
            "color": colors.get(alert.level, 0xFF0000),
            "timestamp": datetime.utcnow().isoformat(),
            "fields": [
                {
                    "name": "日誌消息",
                    "value": str(record.get("message", "N/A"))[:1000],
                    "inline": False,
                },
                {
                    "name": "模組",
                    "value": record.get("name", "Unknown"),
                    "inline": True,
                },
                {
                    "name": "闾值",
                    "value": f"{alert.count}/{alert.threshold}",
                    "inline": True,
                },
            ],
        }

        # 添加追蹤信息
        if "trace_id" in record:
            embed["fields"].append(
                {"name": "追蹤ID", "value": record["trace_id"], "inline": True}
            )

        # 添加用戶信息
        if "user_id" in record:
            embed["fields"].append(
                {
                    "name": "用戶",
                    "value": f"{record.get('username', 'Unknown')} ({record['user_id']})",
                    "inline": True,
                }
            )

        # 添加伺服器信息
        if "guild_id" in record:
            embed["fields"].append(
                {
                    "name": "伺服器",
                    "value": f"{record.get('guild_name', 'Unknown')} ({record['guild_id']})",
                    "inline": True,
                }
            )

        return embed


class ConsoleAlertHandler(AlertHandler):
    """控制台告警處理器"""

    async def handle_alert(
        self, alert: LogAlert, record: dict[str, Any], context: dict[str, Any]
    ):
        """在控制台顯示告警"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n⚠️  [{timestamp}] {alert.level} 告警: {alert.name}")
        print(f"模式: {alert.pattern}")
        print(f"消息: {record.get('message', 'N/A')}")
        print(f"模組: {record.get('name', 'Unknown')}")
        print(f"闾值: {alert.count}/{alert.threshold}")
        if "trace_id" in record:
            print(f"追蹤ID: {record['trace_id']}")
        print("-" * 50)


class AlertManager:
    """告警管理器

    負責管理日誌告警的生命週期.
    """

    def __init__(self):
        """ "初始化告警管理器"""
        self.alerts: dict[str, LogAlert] = {}
        self.handlers: list[AlertHandler] = []
        self._processing_queue: asyncio.Queue = asyncio.Queue()
        self._processor_task: asyncio.Task | None = None
        self._running = False

    def add_alert(self, alert: LogAlert):
        """新增告警配置

        Args:
            alert: 告警配置
        """
        self.alerts[alert.id] = alert

    def remove_alert(self, alert_id: str):
        """移除告警配置"""
        self.alerts.pop(alert_id, None)

    def add_handler(self, handler: AlertHandler):
        """新增告警處理器"""
        self.handlers.append(handler)

    def remove_handler(self, handler: AlertHandler):
        """移除告警處理器"""
        if handler in self.handlers:
            self.handlers.remove(handler)

    async def start(self):
        """啟動告警處理器"""
        if self._running:
            return

        self._running = True
        self._processor_task = asyncio.create_task(self._process_alerts())

    async def stop(self):
        """停止告警處理器"""
        self._running = False
        if self._processor_task:
            self._processor_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._processor_task

    async def process_log_record(self, record: dict[str, Any]):
        """處理日誌記錄,檢查是否觸發告警

        Args:
            record: 日誌記錄
        """
        if not self._running:
            return

        # 將記錄放入處理佇列
        try:
            await self._processing_queue.put(record)
        except asyncio.QueueFull:
            # 佇列滿了,直接處理
            await self._check_alerts(record)

    async def _process_alerts(self):
        """處理告警佇列"""
        while self._running:
            try:
                # 等待日誌記錄
                record = await asyncio.wait_for(
                    self._processing_queue.get(), timeout=1.0
                )
                await self._check_alerts(record)
            except TimeoutError:
                continue
            except Exception as e:
                print(f"告警處理錯誤: {e}")

    async def _check_alerts(self, record: dict[str, Any]):
        """檢查記錄是否觸發告警"""
        for alert in self.alerts.values():
            if not alert.enabled:
                continue

            if self._matches_alert(record, alert):
                await self._handle_alert_match(alert, record)

    def _matches_alert(self, record: dict[str, Any], alert: LogAlert) -> bool:
        """檢查記錄是否符合告警條件"""
        # 檢查等級
        if record.get("level", "").upper() != alert.level.upper():
            return False

        # 檢查模式
        message = str(record.get("message", ""))

        # 簡單的正則檢查(可以擴展為完整的正則表達式)
        import re

        try:
            return bool(re.search(alert.pattern, message, re.IGNORECASE))
        except re.error:
            # 如果不是有效的正則,使用簡單字串匹配
            return alert.pattern.lower() in message.lower()

    async def _handle_alert_match(self, alert: LogAlert, record: dict[str, Any]):
        """處理告警匹配"""
        current_time = time.time()

        # 檢查是否在冷卻時間內
        if alert.is_in_cooldown():
            return

        # 檢查是否需要重設計數器
        if alert.should_reset():
            alert.count = 0
            alert.last_reset = current_time

        # 增加計數
        alert.count += 1

        # 檢查是否達到闾值
        if alert.count >= alert.threshold:
            await self._trigger_alert(alert, record)
            # 重設計數器和冷卻時間
            alert.count = 0
            alert.last_triggered = current_time
            alert.last_reset = current_time

    async def _trigger_alert(self, alert: LogAlert, record: dict[str, Any]):
        """觸發告警"""
        context = {
            "timestamp": datetime.utcnow().isoformat(),
            "trigger_count": alert.count,
            "alert_id": alert.id,
        }

        # 通知所有處理器
        for handler in self.handlers:
            try:
                await handler.handle_alert(alert, record, context)
            except Exception as e:
                # 避免告警處理失敗影響正常日誌
                print(f"告警處理器錯誤: {e}")


# =====================================================
# 日誌格式化器 (Log Formatters)
# =====================================================


class StructuredLogFormatter:
    """結構化日誌格式化器

    支援多種輸出格式:JSON、文字、彩色等.
    """

    def __init__(self, output_format: str = "json", include_trace: bool = True):
        """初始化格式化器

        Args:
            output_format: 輸出格式 (json/text/colored)
            include_trace: 是否包含追蹤信息
        """
        self.output_format = output_format
        self.include_trace = include_trace

    def format(self, record: dict[str, Any]) -> str:
        """格式化日誌記錄

        Args:
            record: 日誌記錄

        Returns:
            格式化後的字串
        """
        if self.output_format == "json":
            return self._format_json(record)
        elif self.output_format == "colored":
            return self._format_colored(record)
        else:
            return self._format_text(record)

    def _format_json(self, record: dict[str, Any]) -> str:
        """格式化為JSON"""
        # 添加追蹤信息
        if self.include_trace:
            trace = TraceManager.get_current_trace()
            if trace:
                record.update(
                    {
                        "trace_id": trace.trace_id,
                        "span_id": trace.span_id,
                        "user_id": trace.user_id,
                        "username": trace.username,
                        "guild_id": trace.guild_id,
                        "guild_name": trace.guild_name,
                        "channel_id": trace.channel_id,
                        "channel_name": trace.channel_name,
                        "command": trace.command,
                    }
                )

        # 添加時間戳
        if "timestamp" not in record:
            record["timestamp"] = datetime.utcnow().isoformat()

        try:
            return json.dumps(record, ensure_ascii=False, default=str)
        except (TypeError, ValueError) as e:
            # JSON序列化失敗,使用簡單格式
            return f'{{"error": "JSON serialization failed: {e}", "original_message": "{record.get("message", "N/A")}"}}'

    def _format_text(self, record: dict[str, Any]) -> str:
        """格式化為純文字"""
        timestamp = record.get("timestamp", datetime.utcnow().isoformat())
        level = record.get("level", "INFO")
        name = record.get("name", "unknown")
        message = record.get("message", "")

        base_format = f"[{timestamp}] {level:8} | {name:20} | {message}"

        # 添加追蹤信息
        if self.include_trace:
            trace = TraceManager.get_current_trace()
            if trace and trace.trace_id:
                base_format += f" | trace_id={trace.trace_id[:8]}"
                if trace.user_id:
                    base_format += f" | user={trace.username}({trace.user_id})"
                if trace.guild_id:
                    base_format += f" | guild={trace.guild_name}({trace.guild_id})"

        return base_format

    def _format_colored(self, record: dict[str, Any]) -> str:
        """格式化為彩色文字(用於rich或終端)"""
        level = record.get("level", "INFO")

        # 定義顏色
        level_colors = {
            "DEBUG": "dim",
            "INFO": "blue",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "bold red",
        }

        color = level_colors.get(level, "white")

        # 使用rich標記格式
        timestamp = record.get("timestamp", datetime.utcnow().isoformat())
        name = record.get("name", "unknown")
        message = record.get("message", "")

        base_format = f"[dim]{timestamp}[/dim] [{color}]{level:8}[/{color}] | {name:20} | {message}"

        # 添加追蹤信息
        if self.include_trace:
            trace = TraceManager.get_current_trace()
            if trace and trace.trace_id:
                base_format += f" | [cyan]trace={trace.trace_id[:8]}[/cyan]"
                if trace.user_id:
                    base_format += f" | [green]user={trace.username}[/green]"

        return base_format


def setup_logging(settings: Settings | None = None) -> None:
    """設定結構化日誌系統

    Args:
        settings: 可選的設定實例.如果為None,將獲取全局設定.
    """
    if settings is None:
        settings = get_settings()

    # 初始化追蹤上下文處理器
    def add_trace_context(logger, name, event_dict):
        """添加追蹤上下文到日誌記錄"""
        trace = TraceManager.get_current_trace()
        if trace:
            event_dict.update(
                {
                    "trace_id": trace.trace_id,
                    "span_id": trace.span_id,
                    "user_id": trace.user_id,
                    "username": trace.username,
                    "guild_id": trace.guild_id,
                    "guild_name": trace.guild_name,
                    "channel_id": trace.channel_id,
                    "channel_name": trace.channel_name,
                    "command": trace.command,
                }
            )
        return event_dict

    # 初始化告警管理器
    def add_alert_processing(logger, name, event_dict):
        """處理告警相關的日誌記錄"""
        # 這裡可以添加告警處理邏輯
        # 由於需要在異步環境中工作,我們在BotLogger中處理
        return event_dict

    # 配置structlog處理器
    processors = [
        structlog.contextvars.merge_contextvars,
        add_trace_context,  # 添加追蹤上下文
        add_alert_processing,  # 添加告警處理
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="ISO"),
        structlog.processors.CallsiteParameterAdder(
            parameters=[
                structlog.processors.CallsiteParameter.FUNC_NAME,
                structlog.processors.CallsiteParameter.LINENO,
            ]
        ),
    ]

    # Add different processors based on output format
    if settings.logging.format == "json":
        processors.extend(
            [
                structlog.processors.dict_tracebacks,
                structlog.processors.JSONRenderer(),
            ]
        )
    elif settings.logging.format == "colored":
        processors.extend(
            [
                structlog.dev.ConsoleRenderer(colors=True),
            ]
        )
    else:  # text format
        processors.extend(
            [
                structlog.dev.ConsoleRenderer(colors=False),
            ]
        )

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(settings.log_level_int),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure Python's built-in logging
    _setup_python_logging(settings)


def _setup_python_logging(settings: Settings) -> None:
    """Set up Python's built-in logging system."""
    # Create logs directory
    settings.logging.file_path.mkdir(parents=True, exist_ok=True)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.log_level_int)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler with rich formatting
    if settings.logging.console_enabled:
        console = Console(stderr=True)
        console_handler = RichHandler(
            console=console,
            show_time=True,
            show_path=True,
            markup=True,
            rich_tracebacks=True,
        )
        console_handler.setLevel(settings.log_level_int)

        # Format for console
        console_formatter = logging.Formatter(
            "%(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

    # File handler with rotation
    if settings.logging.file_enabled:
        file_handler = logging.handlers.RotatingFileHandler(
            settings.get_log_file_path("main"),
            maxBytes=settings.logging.file_max_size
            * 1024
            * 1024,  # Convert MB to bytes
            backupCount=settings.logging.file_backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(settings.log_level_int)

        # Format for file
        if settings.logging.format == "json":
            from pythonjsonlogger import jsonlogger

            file_formatter = jsonlogger.JsonFormatter(
                "%(asctime)s %(name)s %(levelname)s %(message)s %(funcName)s %(lineno)d"
            )
        else:
            file_formatter = logging.Formatter(
                "%(asctime)s | %(name)-20s | %(levelname)-8s | %(funcName)s:%(lineno)d | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )

        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)


class BotLogger:
    """Enhanced logger class for the bot with structured logging."""

    def __init__(self, name: str, settings: Settings | None = None):
        """Initialize bot logger.

        Args:
            name: Logger name
            settings: Optional settings instance
        """
        self.name = name
        self.settings = settings or get_settings()
        self._logger = structlog.get_logger(name)

        # Create module-specific file handler if needed
        if self.settings.logging.file_enabled:
            self._setup_module_file_handler()

    def _setup_module_file_handler(self) -> None:
        """Set up module-specific file logging."""
        module_log_path = self.settings.get_log_file_path(self.name)

        # Create rotating file handler for this module
        handler = logging.handlers.RotatingFileHandler(
            module_log_path,
            maxBytes=self.settings.logging.file_max_size * 1024 * 1024,
            backupCount=self.settings.logging.file_backup_count,
            encoding="utf-8",
        )

        # Set up formatter
        if self.settings.logging.format == "json":
            from pythonjsonlogger import jsonlogger

            formatter = jsonlogger.JsonFormatter(
                "%(asctime)s %(name)s %(levelname)s %(message)s %(funcName)s %(lineno)d"
            )
        else:
            formatter = logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(funcName)s:%(lineno)d | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )

        handler.setFormatter(formatter)
        handler.setLevel(self.settings.log_level_int)

        # Add handler to Python logger
        python_logger = logging.getLogger(self.name)
        python_logger.addHandler(handler)
        python_logger.setLevel(self.settings.log_level_int)

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message."""
        self._logger.debug(message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message."""
        self._logger.info(message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message."""
        self._logger.warning(message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        """Log error message."""
        self._logger.error(message, **kwargs)

    def critical(self, message: str, **kwargs: Any) -> None:
        """Log critical message."""
        self._logger.critical(message, **kwargs)

    def exception(self, message: str, **kwargs: Any) -> None:
        """Log exception with traceback."""
        self._logger.exception(message, **kwargs)

    def bind(self, **kwargs: Any) -> BotLogger:
        """Bind additional context to logger."""
        new_logger = BotLogger(self.name, self.settings)
        new_logger._logger = self._logger.bind(**kwargs)
        return new_logger

    def with_user(self, user_id: int, username: str) -> BotLogger:
        """Bind user context to logger."""
        return self.bind(user_id=user_id, username=username)

    def with_guild(self, guild_id: int, guild_name: str) -> BotLogger:
        """Bind guild context to logger."""
        return self.bind(guild_id=guild_id, guild_name=guild_name)

    def with_channel(self, channel_id: int, channel_name: str) -> BotLogger:
        """Bind channel context to logger."""
        return self.bind(channel_id=channel_id, channel_name=channel_name)

    def with_command(self, command_name: str) -> BotLogger:
        """Bind command context to logger."""
        return self.bind(command=command_name)


def get_logger(name: str, settings: Settings | None = None) -> BotLogger:
    """Get a bot logger instance.

    Args:
        name: Logger name
        settings: Optional settings instance

    Returns:
        BotLogger instance
    """
    return BotLogger(name, settings)


# Convenience function for Discord.py integration
def setup_discord_logging(level: int = logging.INFO) -> None:
    """Set up Discord.py logging with reduced verbosity."""
    # Reduce discord.py logging verbosity
    discord_logger = logging.getLogger("discord")
    discord_logger.setLevel(level)

    # Reduce HTTP request logging
    discord_http_logger = logging.getLogger("discord.http")
    discord_http_logger.setLevel(logging.WARNING)

    # Reduce gateway logging
    discord_gateway_logger = logging.getLogger("discord.gateway")
    discord_gateway_logger.setLevel(logging.WARNING)


# Logging decorators for performance monitoring
def log_performance(logger: BotLogger):
    """Decorator to log function performance."""
    import time

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                duration = time.perf_counter() - start_time
                logger.info(
                    f"Function {func.__name__} completed",
                    duration=duration,
                    function=func.__name__,
                )
                return result
            except Exception as e:
                duration = time.perf_counter() - start_time
                logger.error(
                    f"Function {func.__name__} failed",
                    duration=duration,
                    function=func.__name__,
                    error=str(e),
                )
                raise

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                duration = time.perf_counter() - start_time
                logger.info(
                    f"Async function {func.__name__} completed",
                    duration=duration,
                    function=func.__name__,
                )
                return result
            except Exception as e:
                duration = time.perf_counter() - start_time
                logger.error(
                    f"Async function {func.__name__} failed",
                    duration=duration,
                    function=func.__name__,
                    error=str(e),
                )
                raise

        return (
            async_wrapper
            if hasattr(func, "__code__") and func.__code__.co_flags & 0x80
            else wrapper
        )

    return decorator


def log_errors(logger: BotLogger):
    """Decorator to automatically log errors."""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception:
                logger.exception(f"Error in {func.__name__}", function=func.__name__)
                raise

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception:
                logger.exception(f"Error in {func.__name__}", function=func.__name__)
                raise

        return (
            async_wrapper
            if hasattr(func, "__code__") and func.__code__.co_flags & 0x80
            else wrapper
        )

    return decorator


__all__ = [
    "BotLogger",
    "get_logger",
    "log_errors",
    "log_performance",
    "setup_discord_logging",
    "setup_logging",
]
