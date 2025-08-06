"""成就系統記憶體管理器.

此模組提供記憶體使用優化功能,包含:
- 記憶體使用監控和追蹤
- 垃圾回收優化
- 記憶體洩漏檢測
- 大資料集分頁處理
- 記憶體使用警報

根據 Story 5.1 Task 4 的要求實作.
"""

from __future__ import annotations

import asyncio
import contextlib
import gc
import logging
import os
import time
import tracemalloc
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

import psutil

# 常數定義
MAX_SNAPSHOTS = 100  # 最大快照保留數量
SNAPSHOT_KEEP_COUNT = 50  # 清理後保留的快照數量
MAX_LEAK_RECORDS = 50  # 最大洩漏記錄數量
LEAK_KEEP_COUNT = 25  # 清理後保留的洩漏記錄數量
RECENT_SNAPSHOTS_COUNT = 10  # 最近快照分析數量
MIN_SNAPSHOTS_FOR_TREND = 2  # 趨勢分析所需的最小快照數量

if TYPE_CHECKING:
    from collections.abc import Generator

logger = logging.getLogger(__name__)


class MemoryThreshold(str, Enum):
    """記憶體閾值級別."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class MemorySnapshot:
    """記憶體快照."""

    timestamp: datetime = field(default_factory=datetime.now)
    """快照時間"""

    rss_mb: float = 0.0
    """常駐記憶體大小(MB)"""

    vms_mb: float = 0.0
    """虛擬記憶體大小(MB)"""

    percent: float = 0.0
    """記憶體使用百分比"""

    gc_objects: int = 0
    """垃圾回收器追蹤的物件數量"""

    gc_collections: dict[int, int] = field(default_factory=dict)
    """各代垃圾回收次數"""

    active_coroutines: int = 0
    """活躍協程數量"""


@dataclass
class MemoryLeak:
    """記憶體洩漏資訊."""

    file_name: str
    """檔案名稱"""

    line_number: int
    """行號"""

    size_mb: float
    """洩漏大小(MB)"""

    count: int
    """洩漏數量"""

    traceback: list[str]
    """堆疊追蹤"""


class MemoryManager:
    """記憶體管理器.

    提供記憶體使用優化和監控功能.
    """

    def __init__(
        self,
        enable_tracing: bool = True,
        gc_threshold_0: int = 700,
        gc_threshold_1: int = 10,
        gc_threshold_2: int = 10,
        memory_warning_mb: float = 80.0,
        memory_critical_mb: float = 100.0,
    ):
        """初始化記憶體管理器.

        Args:
            enable_tracing: 是否啟用記憶體追蹤
            gc_threshold_0: 第0代垃圾回收閾值
            gc_threshold_1: 第1代垃圾回收閾值
            gc_threshold_2: 第2代垃圾回收閾值
            memory_warning_mb: 記憶體警告閾值(MB)
            memory_critical_mb: 記憶體嚴重閾值(MB)
        """
        self._enable_tracing = enable_tracing
        self._memory_warning_mb = memory_warning_mb
        self._memory_critical_mb = memory_critical_mb

        # 記憶體快照歷史
        self._snapshots: list[MemorySnapshot] = []
        self._max_snapshots = 1000

        # 記憶體洩漏檢測
        self._leak_detection_enabled = False
        self._baseline_snapshot: MemorySnapshot | None = None
        self._detected_leaks: list[MemoryLeak] = []

        # 監控任務
        self._monitoring_task: asyncio.Task | None = None
        self._is_monitoring = False

        # 垃圾回收優化
        self._original_gc_thresholds = gc.get_threshold()
        self._optimized_gc_thresholds = (gc_threshold_0, gc_threshold_1, gc_threshold_2)

        # 記憶體統計
        self._stats = {
            "total_snapshots": 0,
            "gc_optimizations": 0,
            "memory_warnings": 0,
            "memory_criticals": 0,
            "leaks_detected": 0,
            "last_reset": datetime.now(),
        }

        logger.info(
            "MemoryManager 初始化完成",
            extra={
                "tracing_enabled": enable_tracing,
                "warning_threshold": memory_warning_mb,
                "critical_threshold": memory_critical_mb,
            },
        )

    async def __aenter__(self) -> MemoryManager:
        """異步上下文管理器進入."""
        await self.start_monitoring()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """異步上下文管理器退出."""
        await self.stop_monitoring()

    # =============================================================================
    # 記憶體監控功能
    # =============================================================================

    async def start_monitoring(self) -> None:
        """啟動記憶體監控."""
        if self._is_monitoring:
            logger.warning("記憶體監控已經在運行")
            return

        # 啟用記憶體追蹤
        if self._enable_tracing and not tracemalloc.is_tracing():
            tracemalloc.start()
            logger.info("記憶體追蹤已啟用")

        # 優化垃圾回收
        self._optimize_gc()

        # 拍攝基線快照
        self._baseline_snapshot = await self.take_snapshot()

        # 啟動監控任務
        self._is_monitoring = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())

        logger.info("記憶體監控已啟動")

    async def stop_monitoring(self) -> None:
        """停止記憶體監控."""
        if not self._is_monitoring:
            return

        self._is_monitoring = False

        if self._monitoring_task and not self._monitoring_task.done():
            self._monitoring_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._monitoring_task

        # 還原垃圾回收設定
        gc.set_threshold(*self._original_gc_thresholds)

        # 停用記憶體追蹤
        if tracemalloc.is_tracing():
            tracemalloc.stop()
            logger.info("記憶體追蹤已停用")

        logger.info("記憶體監控已停止")

    async def take_snapshot(self) -> MemorySnapshot:
        """拍攝記憶體快照.

        Returns:
            記憶體快照
        """
        try:
            # 取得進程記憶體資訊
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            memory_percent = process.memory_percent()

            # 取得垃圾回收器資訊
            gc_objects = len(gc.get_objects())
            gc_stats = gc.get_stats()
            gc_collections = {
                i: stat.get("collections", 0) for i, stat in enumerate(gc_stats)
            }

            # 取得協程資訊
            try:
                active_coroutines = len([
                    task for task in asyncio.all_tasks() if not task.done()
                ])
            except RuntimeError:
                active_coroutines = 0

            snapshot = MemorySnapshot(
                rss_mb=memory_info.rss / 1024 / 1024,
                vms_mb=memory_info.vms / 1024 / 1024,
                percent=memory_percent,
                gc_objects=gc_objects,
                gc_collections=gc_collections,
                active_coroutines=active_coroutines,
            )

            # 儲存快照
            self._snapshots.append(snapshot)
            if len(self._snapshots) > self._max_snapshots:
                self._snapshots = self._snapshots[-self._max_snapshots // 2 :]

            self._stats["total_snapshots"] += 1

            # 檢查記憶體警報
            await self._check_memory_alerts(snapshot)

            return snapshot

        except Exception as e:
            logger.error(f"拍攝記憶體快照失敗: {e}")
            return MemorySnapshot()

    async def _check_memory_alerts(self, snapshot: MemorySnapshot) -> None:
        """檢查記憶體警報."""
        rss_mb = snapshot.rss_mb

        if rss_mb >= self._memory_critical_mb:
            self._stats["memory_criticals"] += 1
            logger.critical(
                f"記憶體使用嚴重警告: {rss_mb:.1f}MB (閾值: {self._memory_critical_mb}MB)",
                extra={
                    "memory_mb": rss_mb,
                    "threshold_mb": self._memory_critical_mb,
                    "gc_objects": snapshot.gc_objects,
                    "active_coroutines": snapshot.active_coroutines,
                },
            )

            # 執行緊急垃圾回收
            await self.force_gc()

        elif rss_mb >= self._memory_warning_mb:
            self._stats["memory_warnings"] += 1
            logger.warning(
                f"記憶體使用警告: {rss_mb:.1f}MB (閾值: {self._memory_warning_mb}MB)",
                extra={
                    "memory_mb": rss_mb,
                    "threshold_mb": self._memory_warning_mb,
                    "gc_objects": snapshot.gc_objects,
                },
            )

    async def _monitoring_loop(self) -> None:
        """記憶體監控循環."""
        while self._is_monitoring:
            try:
                # 拍攝快照
                await self.take_snapshot()

                # 檢測記憶體洩漏
                if self._leak_detection_enabled:
                    await self._detect_memory_leaks()

                # 定期優化垃圾回收
                if self._stats["total_snapshots"] % 10 == 0:
                    await self.optimize_memory()

                await asyncio.sleep(30)  # 每30秒監控一次

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"記憶體監控循環錯誤: {e}", exc_info=True)
                await asyncio.sleep(10)

    # =============================================================================
    # 垃圾回收優化
    # =============================================================================

    def _optimize_gc(self) -> None:
        """優化垃圾回收器設定."""
        # 設定更積極的垃圾回收閾值
        gc.set_threshold(*self._optimized_gc_thresholds)

        # Enable GC debugging in development
        if logger.level <= logging.DEBUG:
            gc.set_debug(gc.DEBUG_STATS)

        self._stats["gc_optimizations"] += 1

        logger.info(
            f"垃圾回收器已優化: {self._optimized_gc_thresholds}",
            extra={"original_thresholds": self._original_gc_thresholds},
        )

    async def force_gc(self, generation: int | None = None) -> dict[str, int]:
        """強制執行垃圾回收.

        Args:
            generation: 要回收的代數,None 表示所有代

        Returns:
            垃圾回收統計
        """
        start_time = time.time()

        collected = gc.collect(generation) if generation is not None else gc.collect()

        duration_ms = (time.time() - start_time) * 1000

        stats = {
            "collected_objects": collected,
            "duration_ms": duration_ms,
            "generation": generation or "all",
        }

        logger.debug(
            f"強制垃圾回收完成: 回收 {collected} 個物件,耗時 {duration_ms:.2f}ms",
            extra=stats,
        )

        return stats

    async def optimize_memory(self) -> dict[str, Any]:
        """執行記憶體優化.

        Returns:
            優化結果統計
        """
        logger.info("開始記憶體優化")

        optimization_start = time.time()
        results = {}

        try:
            # 1. 強制垃圾回收
            gc_stats = await self.force_gc()
            results["garbage_collection"] = gc_stats

            # 2. 清理快照歷史(保留最近的)
            if len(self._snapshots) > MAX_SNAPSHOTS:
                old_count = len(self._snapshots)
                self._snapshots = self._snapshots[-SNAPSHOT_KEEP_COUNT:]
                results["snapshots_cleaned"] = old_count - len(self._snapshots)

            # 3. 清理檢測到的洩漏記錄
            if len(self._detected_leaks) > MAX_LEAK_RECORDS:
                old_count = len(self._detected_leaks)
                self._detected_leaks = self._detected_leaks[-LEAK_KEEP_COUNT:]
                results["leaks_cleaned"] = old_count - len(self._detected_leaks)

            # 4. 檢查並清理未完成的任務
            try:
                all_tasks = asyncio.all_tasks()
                done_tasks = [task for task in all_tasks if task.done()]
                if done_tasks:
                    results["completed_tasks_found"] = len(done_tasks)
            except RuntimeError:
                pass

            duration_ms = (time.time() - optimization_start) * 1000
            results["total_duration_ms"] = duration_ms

            logger.info(f"記憶體優化完成,耗時 {duration_ms:.2f}ms", extra=results)

            return results

        except Exception as e:
            logger.error(f"記憶體優化失敗: {e}", exc_info=True)
            return {"error": str(e)}

    # =============================================================================
    # 記憶體洩漏檢測
    # =============================================================================

    def enable_leak_detection(self) -> None:
        """啟用記憶體洩漏檢測."""
        if not tracemalloc.is_tracing():
            tracemalloc.start()

        self._leak_detection_enabled = True
        logger.info("記憶體洩漏檢測已啟用")

    def disable_leak_detection(self) -> None:
        """停用記憶體洩漏檢測."""
        self._leak_detection_enabled = False
        logger.info("記憶體洩漏檢測已停用")

    async def _detect_memory_leaks(self) -> list[MemoryLeak]:
        """檢測記憶體洩漏.

        Returns:
            檢測到的記憶體洩漏列表
        """
        if not tracemalloc.is_tracing() or not self._baseline_snapshot:
            return []

        try:
            # 取得當前記憶體追蹤快照
            current_snapshot = tracemalloc.take_snapshot()

            # 過濾掉不重要的檔案
            filters = [
                tracemalloc.Filter(False, "<frozen importlib._bootstrap>"),
                tracemalloc.Filter(False, "<unknown>"),
                tracemalloc.Filter(False, tracemalloc.__file__),
            ]
            current_snapshot = current_snapshot.filter_traces(filters)

            # 取得前10個記憶體使用最多的程式碼行
            top_stats = current_snapshot.statistics("lineno")[:10]

            detected_leaks = []

            for stat in top_stats:
                # Check for potential memory leaks (> 1MB allocations)
                size_mb = stat.size / 1024 / 1024
                if size_mb > 1.0:
                    traceback_lines = []
                    for frame in stat.traceback:
                        traceback_lines.append(f"{frame.filename}:{frame.lineno}")

                    leak = MemoryLeak(
                        file_name=stat.traceback[0].filename
                        if stat.traceback
                        else "unknown",
                        line_number=stat.traceback[0].lineno if stat.traceback else 0,
                        size_mb=size_mb,
                        count=stat.count,
                        traceback=traceback_lines,
                    )

                    detected_leaks.append(leak)

            # 儲存檢測結果
            if detected_leaks:
                self._detected_leaks.extend(detected_leaks)
                self._stats["leaks_detected"] += len(detected_leaks)

                logger.warning(
                    f"檢測到 {len(detected_leaks)} 個潛在記憶體洩漏",
                    extra={
                        "leaks": [
                            {
                                "file": leak.file_name,
                                "line": leak.line_number,
                                "size_mb": round(leak.size_mb, 2),
                                "count": leak.count,
                            }
                            for leak in detected_leaks
                        ]
                    },
                )

            return detected_leaks

        except Exception as e:
            logger.error(f"記憶體洩漏檢測失敗: {e}", exc_info=True)
            return []

    # =============================================================================
    # 大資料集分頁處理
    # =============================================================================

    async def paginate_large_dataset(
        self,
        dataset: list[Any],
        page_size: int = 100,
        process_func: callable | None = None,
    ) -> Generator[list[Any], None, None]:
        """分頁處理大資料集.

        Args:
            dataset: 要處理的資料集
            page_size: 每頁大小
            process_func: 處理函數(可選)

        Yields:
            分頁後的資料
        """
        total_items = len(dataset)

        if total_items == 0:
            return

        logger.info(f"開始分頁處理大資料集: {total_items} 項,頁大小: {page_size}")

        for i in range(0, total_items, page_size):
            page_data = dataset[i : i + page_size]

            if process_func:
                try:
                    processed_data = await process_func(page_data)
                    yield processed_data
                except Exception as e:
                    logger.error(f"處理第 {i // page_size + 1} 頁失敗: {e}")
                    yield page_data
            else:
                yield page_data

            # 在處理頁面間進行小幅延遲,讓其他協程有機會執行
            await asyncio.sleep(0.001)

            # 定期進行垃圾回收
            if (i // page_size + 1) % 10 == 0:
                await self.force_gc(0)  # 只回收第0代

    async def memory_safe_bulk_operation(
        self,
        items: list[Any],
        operation_func: callable,
        batch_size: int = 50,
        memory_limit_mb: float = 50.0,
    ) -> list[Any]:
        """記憶體安全的批量操作.

        Args:
            items: 要處理的項目列表
            operation_func: 操作函數
            batch_size: 批次大小
            memory_limit_mb: 記憶體限制(MB)

        Returns:
            處理結果列表
        """
        results = []

        async for batch in self.paginate_large_dataset(items, batch_size):
            # 檢查記憶體使用量
            snapshot = await self.take_snapshot()
            if snapshot.rss_mb > memory_limit_mb:
                logger.warning(f"記憶體使用過高 ({snapshot.rss_mb:.1f}MB),執行優化")
                await self.optimize_memory()

            try:
                batch_results = await operation_func(batch)
                results.extend(batch_results)
            except Exception as e:
                logger.error(f"批量操作失敗: {e}")
                continue

        return results

    # =============================================================================
    # 統計和報告
    # =============================================================================

    def get_memory_stats(self) -> dict[str, Any]:
        """取得記憶體統計資訊.

        Returns:
            記憶體統計字典
        """
        if not self._snapshots:
            return {"error": "沒有可用的記憶體快照"}

        recent_snapshots = (
            self._snapshots[-RECENT_SNAPSHOTS_COUNT:]
            if len(self._snapshots) >= RECENT_SNAPSHOTS_COUNT
            else self._snapshots
        )
        current_snapshot = self._snapshots[-1]

        # 計算趨勢
        if len(self._snapshots) >= MIN_SNAPSHOTS_FOR_TREND:
            memory_trend = self._snapshots[-1].rss_mb - self._snapshots[-2].rss_mb
        else:
            memory_trend = 0.0

        return {
            "current": {
                "rss_mb": round(current_snapshot.rss_mb, 2),
                "vms_mb": round(current_snapshot.vms_mb, 2),
                "percent": round(current_snapshot.percent, 2),
                "gc_objects": current_snapshot.gc_objects,
                "active_coroutines": current_snapshot.active_coroutines,
            },
            "trend": {
                "memory_change_mb": round(memory_trend, 2),
                "direction": "increasing"
                if memory_trend > 0
                else "decreasing"
                if memory_trend < 0
                else "stable",
            },
            "statistics": {
                "total_snapshots": len(self._snapshots),
                "monitoring_duration_hours": (
                    (datetime.now() - self._stats["last_reset"]).total_seconds() / 3600
                ),
                "average_memory_mb": round(
                    sum(s.rss_mb for s in recent_snapshots) / len(recent_snapshots), 2
                ),
                "peak_memory_mb": round(max(s.rss_mb for s in self._snapshots), 2),
                "memory_warnings": self._stats["memory_warnings"],
                "memory_criticals": self._stats["memory_criticals"],
            },
            "leaks": {
                "detection_enabled": self._leak_detection_enabled,
                "detected_count": len(self._detected_leaks),
                "recent_leaks": [
                    {
                        "file": leak.file_name.split("/")[-1],  # 只顯示檔案名
                        "line": leak.line_number,
                        "size_mb": round(leak.size_mb, 2),
                        "count": leak.count,
                    }
                    for leak in self._detected_leaks[-5:]  # 最近5個
                ],
            },
            "thresholds": {
                "warning_mb": self._memory_warning_mb,
                "critical_mb": self._memory_critical_mb,
            },
        }

    def reset_stats(self) -> None:
        """重置統計資料."""
        self._stats = {
            "total_snapshots": 0,
            "gc_optimizations": 0,
            "memory_warnings": 0,
            "memory_criticals": 0,
            "leaks_detected": 0,
            "last_reset": datetime.now(),
        }
        self._snapshots.clear()
        self._detected_leaks.clear()

        logger.info("記憶體統計已重置")


__all__ = [
    "MemoryLeak",
    "MemoryManager",
    "MemorySnapshot",
    "MemoryThreshold",
]
