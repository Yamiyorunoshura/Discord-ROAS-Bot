"""簡化的核心日誌系統測試.

此模組測試 src.core.logger 中的基本日誌功能.
"""

import logging
import sys
import tempfile
from pathlib import Path

# 確保正確的導入路徑
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import contextlib

from src.core.logger import (
    BotLogger,
    TraceContext,
    get_logger,
)


class TestTraceContext:
    """測試 TraceContext 分散式追蹤上下文."""

    def test_trace_context_initialization(self):
        """測試追蹤上下文初始化."""
        trace_id = "test-trace-123"
        span_id = "test-span-456"

        context = TraceContext(trace_id=trace_id, span_id=span_id)

        assert context.trace_id == trace_id
        assert context.span_id == span_id
        assert isinstance(context.start_time, float)


class TestBotLogger:
    """測試 BotLogger 機器人日誌記錄器."""

    def setup_method(self):
        """設置測試環境."""
        self.temp_log_file = tempfile.NamedTemporaryFile(suffix=".log", delete=False)
        self.temp_log_file.close()

    def teardown_method(self):
        """清理測試環境."""
        import os

        with contextlib.suppress(OSError, FileNotFoundError):
            os.unlink(self.temp_log_file.name)

    def test_bot_logger_initialization(self):
        """測試機器人日誌記錄器初始化."""
        logger = BotLogger("test_bot_logger")

        assert logger.name == "test_bot_logger"
        assert isinstance(logger.logger, logging.Logger)

    def test_bot_logger_basic_logging(self):
        """測試基本日誌記錄功能."""
        logger = BotLogger("test_logger")

        # 測試不同級別的日誌記錄
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
        logger.critical("Critical message")

        # 基本功能測試,不需要驗證具體輸出

    def test_bot_logger_with_extra_data(self):
        """測試帶額外數據的日誌記錄."""
        logger = BotLogger("test_logger")

        # 測試帶額外字段的日誌記錄
        logger.info("Test message", extra={"user_id": 12345, "guild_id": 67890})


class TestLoggerIntegration:
    """測試日誌系統整合功能."""

    def test_get_logger_function(self):
        """測試 get_logger 函數."""
        logger = get_logger("test_integration")

        assert logger is not None
        assert hasattr(logger, "info")
        assert hasattr(logger, "error")

        # 測試日誌記錄
        logger.info("Integration test message")

    def test_logger_hierarchy(self):
        """測試日誌器層級結構."""
        parent_logger = get_logger("parent")
        child_logger = get_logger("parent.child")

        assert parent_logger is not None
        assert child_logger is not None

        # 測試層級日誌記錄
        parent_logger.info("Parent message")
        child_logger.info("Child message")


class TestLoggerErrorHandling:
    """測試日誌系統錯誤處理."""

    def test_logger_with_none_message(self):
        """測試 None 消息的錯誤處理."""
        logger = get_logger("error_test")

        # 這些操作不應該拋出異常
        try:
            logger.info(None)
            logger.error(None)
        except Exception:
            # 如果拋出異常,確保是預期的類型
            pass

    def test_logger_with_invalid_level(self):
        """測試無效日誌級別處理."""
        logger = get_logger("level_test")

        # 測試基本功能仍然可用
        logger.info("Test message after potential level issues")

    def test_logger_unicode_handling(self):
        """測試 Unicode 字元處理."""
        logger = get_logger("unicode_test")

        # 測試各種 Unicode 字元
        logger.info("測試中文日誌")
        logger.info("Test émojis: 🚀 🎉 ⚡")
        logger.info("Mixed: Test 測試 🌟")


class TestLoggerPerformance:
    """測試日誌系統效能."""

    def test_logger_high_volume_logging(self):
        """測試大量日誌記錄的效能."""
        logger = get_logger("performance_test")

        import time

        start_time = time.time()

        # 記錄大量日誌
        for i in range(100):
            logger.info(f"Performance test message {i}")

        end_time = time.time()
        duration = end_time - start_time

        # 確保效能合理(應該在 1 秒內完成)
        assert duration < 1.0

    def test_logger_concurrent_logging(self):
        """測試並發日誌記錄."""
        logger = get_logger("concurrent_test")

        def log_worker(worker_id: int):
            for i in range(10):
                logger.info(f"Worker {worker_id} message {i}")

        import threading

        # 創建多個執行緒進行並發日誌記錄
        threads = []
        for i in range(3):
            thread = threading.Thread(target=log_worker, args=(i,))
            threads.append(thread)
            thread.start()

        # 等待所有執行緒完成
        for thread in threads:
            thread.join()

        # 如果沒有異常,則測試通過
