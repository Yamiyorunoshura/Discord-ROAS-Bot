"""自動成就頒發系統.

此模組實作自動成就頒發和管理系統,提供:
- 原子性成就頒發機制
- 進度同步和一致性保證
- 成就通知和事件發布
- 頒發歷史記錄和審計
- 併發安全的頒發處理

頒發系統遵循以下設計原則:
- 確保成就頒發的原子性和一致性
- 支援事務處理避免重複頒發
- 整合通知系統提供即時反饋
- 詳細記錄頒發歷史和統計
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..database.models import UserAchievement
    from ..database.repository import AchievementRepository
    from .event_processor import TriggerResult
    from .progress_tracker import ProgressTracker

logger = logging.getLogger(__name__)

class AwardStatus(str, Enum):
    """頒發狀態列舉."""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    DUPLICATE = "duplicate"
    INVALID = "invalid"

@dataclass
class AwardRequest:
    """成就頒發請求.

    封裝成就頒發的完整資訊和上下文.
    """

    user_id: int
    """用戶 ID"""

    guild_id: int
    """伺服器 ID"""

    achievement_id: int
    """成就 ID"""

    trigger_reason: str
    """觸發原因"""

    trigger_context: dict[str, Any] = field(default_factory=dict)
    """觸發上下文資料"""

    awarded_at: datetime = field(default_factory=datetime.now)
    """頒發時間"""

    source_event: str | None = None
    """來源事件類型"""

    processing_priority: int = 0
    """處理優先級"""

@dataclass
class AwardResult:
    """成就頒發結果.

    封裝成就頒發的完整結果資訊.
    """

    request: AwardRequest
    """原始請求"""

    status: AwardStatus
    """頒發狀態"""

    user_achievement: UserAchievement | None = None
    """頒發的用戶成就記錄"""

    error_message: str | None = None
    """錯誤訊息"""

    processing_time: float = 0.0
    """處理時間(毫秒)"""

    notification_sent: bool = False
    """是否已發送通知"""

class AchievementAwarder:
    """自動成就頒發器.

    負責處理成就的自動頒發、進度同步和通知發送,提供:
    - 原子性成就頒發機制
    - 重複頒發檢查和防護
    - 進度更新和同步
    - 成就通知和事件發布
    - 詳細的頒發統計和審計
    """

    def __init__(
        self,
        repository: AchievementRepository,
        progress_tracker: ProgressTracker,
        notification_enabled: bool = True,
        max_concurrent_awards: int = 20,
        award_timeout: float = 10.0,
    ):
        """初始化成就頒發器.

        Args:
            repository: 成就資料存取庫
            progress_tracker: 進度追蹤器
            notification_enabled: 是否啟用通知
            max_concurrent_awards: 最大並發頒發數
            award_timeout: 頒發超時時間(秒)
        """
        self._repository = repository
        self._progress_tracker = progress_tracker
        self._notification_enabled = notification_enabled
        self._max_concurrent_awards = max_concurrent_awards
        self._award_timeout = award_timeout

        # 併發控制
        self._award_semaphore = asyncio.Semaphore(max_concurrent_awards)
        self._active_awards: set[str] = (
            set()
        )  # 正在處理的頒發(user_id:achievement_id)
        self._award_locks: dict[str, asyncio.Lock] = {}

        # 統計資訊
        self._stats = {
            "total_awards": 0,
            "successful_awards": 0,
            "failed_awards": 0,
            "duplicate_awards": 0,
            "average_processing_time": 0.0,
            "last_reset": datetime.now(),
        }

        self._notification_handlers: list[callable] = []

        logger.info(
            "AchievementAwarder 初始化完成",
            extra={
                "notification_enabled": notification_enabled,
                "max_concurrent": max_concurrent_awards,
                "timeout": award_timeout,
            },
        )

    async def __aenter__(self) -> AchievementAwarder:
        """異步上下文管理器進入."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """異步上下文管理器退出."""
        # 等待所有進行中的頒發完成
        while self._active_awards:
            await asyncio.sleep(0.1)

    # =============================================================================
    # 成就頒發主要介面
    # =============================================================================

    async def award_achievement(
        self,
        user_id: int,
        guild_id: int,
        achievement_id: int,
        trigger_reason: str,
        trigger_context: dict[str, Any] | None = None,
        source_event: str | None = None,
    ) -> AwardResult:
        """頒發單一成就.

        Args:
            user_id: 用戶 ID
            guild_id: 伺服器 ID
            achievement_id: 成就 ID
            trigger_reason: 觸發原因
            trigger_context: 觸發上下文
            source_event: 來源事件類型

        Returns:
            頒發結果
        """
        request = AwardRequest(
            user_id=user_id,
            guild_id=guild_id,
            achievement_id=achievement_id,
            trigger_reason=trigger_reason,
            trigger_context=trigger_context or {},
            source_event=source_event,
        )

        return await self._process_award_request(request)

    async def award_multiple_achievements(
        self, requests: list[AwardRequest]
    ) -> list[AwardResult]:
        """批量頒發多個成就.

        Args:
            requests: 頒發請求列表

        Returns:
            頒發結果列表
        """
        if not requests:
            return []

        # 按優先級排序
        sorted_requests = sorted(
            requests, key=lambda r: (r.processing_priority, r.awarded_at), reverse=True
        )

        # 並發處理頒發請求
        tasks = []
        for request in sorted_requests:
            task = asyncio.create_task(self._process_award_request(request))
            tasks.append(task)

        # 等待所有頒發完成
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 處理異常結果
        award_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                error_result = AwardResult(
                    request=sorted_requests[i],
                    status=AwardStatus.FAILED,
                    error_message=str(result),
                )
                award_results.append(error_result)
                logger.error(
                    "批量頒發異常",
                    extra={
                        "user_id": sorted_requests[i].user_id,
                        "achievement_id": sorted_requests[i].achievement_id,
                        "error": str(result),
                    },
                    exc_info=True,
                )
            else:
                award_results.append(result)

        logger.info(
            "批量成就頒發完成",
            extra={
                "total_requests": len(requests),
                "successful": len(
                    [r for r in award_results if r.status == AwardStatus.SUCCESS]
                ),
                "failed": len(
                    [r for r in award_results if r.status == AwardStatus.FAILED]
                ),
                "duplicates": len(
                    [r for r in award_results if r.status == AwardStatus.DUPLICATE]
                ),
            },
        )

        return award_results

    async def process_trigger_results(
        self, trigger_results: list[TriggerResult]
    ) -> list[AwardResult]:
        """處理觸發結果並頒發成就.

        Args:
            trigger_results: 觸發檢查結果列表

        Returns:
            頒發結果列表
        """
        # 過濾需要頒發的觸發結果
        award_requests = []

        for result in trigger_results:
            if result.triggered and not result.error:
                request = AwardRequest(
                    user_id=result.user_id,
                    achievement_id=result.achievement_id,
                    trigger_reason=result.reason or "成就條件滿足",
                    trigger_context={"processing_time": result.processing_time},
                )
                award_requests.append(request)

        if not award_requests:
            return []

        # 批量處理頒發
        return await self.award_multiple_achievements(award_requests)

    # =============================================================================
    # 內部頒發處理邏輯
    # =============================================================================

    async def _process_award_request(self, request: AwardRequest) -> AwardResult:
        """處理單一頒發請求.

        Args:
            request: 頒發請求

        Returns:
            頒發結果
        """
        start_time = datetime.now()
        award_key = f"{request.user_id}:{request.achievement_id}"

        try:
            # 獲取併發控制鎖
            async with self._get_award_lock(award_key):
                # 檢查是否正在處理中
                if award_key in self._active_awards:
                    return AwardResult(
                        request=request,
                        status=AwardStatus.DUPLICATE,
                        error_message="成就正在處理中",
                    )

                # 標記為處理中
                self._active_awards.add(award_key)

                try:
                    # 使用信號量控制並發數
                    async with self._award_semaphore:
                        # 執行頒發邏輯
                        result = await asyncio.wait_for(
                            self._execute_award_logic(request),
                            timeout=self._award_timeout,
                        )

                        # 計算處理時間
                        processing_time = (
                            datetime.now() - start_time
                        ).total_seconds() * 1000
                        result.processing_time = processing_time

                        # 更新統計
                        self._update_award_stats(result.status, processing_time)

                        return result

                finally:
                    # 清理處理中標記
                    self._active_awards.discard(award_key)

        except TimeoutError:
            return AwardResult(
                request=request,
                status=AwardStatus.FAILED,
                error_message=f"頒發超時({self._award_timeout}s)",
            )
        except Exception as e:
            logger.error(
                "頒發請求處理失敗",
                extra={
                    "user_id": request.user_id,
                    "achievement_id": request.achievement_id,
                    "error": str(e),
                },
                exc_info=True,
            )
            return AwardResult(
                request=request, status=AwardStatus.FAILED, error_message=str(e)
            )

    async def _execute_award_logic(self, request: AwardRequest) -> AwardResult:
        """執行成就頒發邏輯.

        Args:
            request: 頒發請求

        Returns:
            頒發結果
        """
        # 1. 驗證頒發請求
        validation_result = await self._validate_award_request(request)
        if validation_result.status != AwardStatus.PENDING:
            return validation_result

        # 2. 檢查用戶是否已獲得成就
        has_achievement = await self._repository.has_user_achievement(
            request.user_id, request.achievement_id
        )

        if has_achievement:
            return AwardResult(
                request=request,
                status=AwardStatus.DUPLICATE,
                error_message="用戶已獲得此成就",
            )

        # 3. 在事務中執行頒發
        async with self._repository.transaction() as tx:
            try:
                # 創建用戶成就記錄
                user_achievement = await self._repository.award_achievement(
                    user_id=request.user_id,
                    achievement_id=request.achievement_id,
                    earned_at=request.awarded_at,
                    trigger_context=request.trigger_context,
                    tx=tx,
                )

                # 更新相關進度
                await self._update_related_progress(request, tx)

                # 提交事務
                await tx.commit()

                # 4. 發送通知(事務外進行)
                notification_sent = False
                if self._notification_enabled:
                    try:
                        await self._send_achievement_notification(
                            request, user_achievement
                        )
                        notification_sent = True
                    except Exception as e:
                        logger.warning(
                            "成就通知發送失敗",
                            extra={
                                "user_id": request.user_id,
                                "achievement_id": request.achievement_id,
                                "error": str(e),
                            },
                        )

                # 5. 記錄頒發事件
                await self._record_award_event(request, user_achievement)

                logger.info(
                    "成就頒發成功",
                    extra={
                        "user_id": request.user_id,
                        "achievement_id": request.achievement_id,
                        "trigger_reason": request.trigger_reason,
                        "notification_sent": notification_sent,
                    },
                )

                return AwardResult(
                    request=request,
                    status=AwardStatus.SUCCESS,
                    user_achievement=user_achievement,
                    notification_sent=notification_sent,
                )

            except Exception:
                # 回滾事務
                await tx.rollback()
                raise

    async def _validate_award_request(self, request: AwardRequest) -> AwardResult:
        """驗證頒發請求.

        Args:
            request: 頒發請求

        Returns:
            驗證結果
        """
        # 檢查用戶 ID
        if request.user_id <= 0:
            return AwardResult(
                request=request,
                status=AwardStatus.INVALID,
                error_message="無效的用戶 ID",
            )

        # 檢查成就是否存在且啟用
        achievement = await self._repository.get_achievement_by_id(
            request.achievement_id
        )
        if not achievement:
            return AwardResult(
                request=request, status=AwardStatus.INVALID, error_message="成就不存在"
            )

        if not achievement.is_active:
            return AwardResult(
                request=request, status=AwardStatus.INVALID, error_message="成就未啟用"
            )

        # 檢查觸發原因
        if not request.trigger_reason or not request.trigger_reason.strip():
            return AwardResult(
                request=request,
                status=AwardStatus.INVALID,
                error_message="缺少觸發原因",
            )

        return AwardResult(request=request, status=AwardStatus.PENDING)

    async def _update_related_progress(self, request: AwardRequest, tx: Any) -> None:
        """更新相關的成就進度.

        Args:
            request: 頒發請求
            tx: 資料庫事務
        """
        # 標記成就進度為完成
        await self._progress_tracker.mark_achievement_completed(
            user_id=request.user_id,
            achievement_id=request.achievement_id,
            completion_data=request.trigger_context,
            tx=tx,
        )

        # 檢查是否有依賴此成就的其他成就需要更新
        dependent_achievements = await self._repository.get_dependent_achievements(
            request.achievement_id, tx=tx
        )

        for dependent in dependent_achievements:
            # 更新依賴成就的進度
            await self._progress_tracker.update_dependency_progress(
                user_id=request.user_id,
                achievement_id=dependent.id,
                completed_dependency_id=request.achievement_id,
                tx=tx,
            )

    async def _send_achievement_notification(
        self, request: AwardRequest, user_achievement: UserAchievement
    ) -> None:
        """發送成就通知.

        Args:
            request: 頒發請求
            user_achievement: 用戶成就記錄
        """
        # 取得成就詳細資訊
        achievement = await self._repository.get_achievement_by_id(
            request.achievement_id
        )
        if not achievement:
            return

        for handler in self._notification_handlers:
            try:
                # 新格式的通知資料,包含完整物件
                notification_data = {
                    "user_id": request.user_id,
                    "guild_id": request.guild_id,
                    "achievement": achievement,
                    "user_achievement": user_achievement,
                    "trigger_reason": request.trigger_reason,
                    "source_event": request.source_event,
                }
                await handler(notification_data)
            except Exception as e:
                logger.error(
                    "通知處理器執行失敗",
                    extra={
                        "handler": handler.__name__
                        if hasattr(handler, "__name__")
                        else str(handler),
                        "user_id": request.user_id,
                        "achievement_id": request.achievement_id,
                        "error": str(e),
                    },
                )

    async def _record_award_event(
        self, request: AwardRequest, user_achievement: UserAchievement
    ) -> None:
        """記錄頒發事件.

        Args:
            request: 頒發請求
            user_achievement: 用戶成就記錄
        """
        event_data = {
            "event_type": "achievement_awarded",
            "user_id": request.user_id,
            "achievement_id": request.achievement_id,
            "trigger_reason": request.trigger_reason,
            "source_event": request.source_event,
            "trigger_context": request.trigger_context,
            "awarded_at": user_achievement.earned_at.isoformat(),
        }

        logger.info(
            "成就頒發事件",
            extra={
                "event_data": event_data,
                "user_achievement_id": user_achievement.id,
            },
        )

    # =============================================================================
    # 輔助方法和管理功能
    # =============================================================================

    @asynccontextmanager
    async def _get_award_lock(self, award_key: str):
        """取得頒發鎖.

        Args:
            award_key: 頒發鍵(user_id:achievement_id)
        """
        if award_key not in self._award_locks:
            self._award_locks[award_key] = asyncio.Lock()

        async with self._award_locks[award_key]:
            yield

    def _update_award_stats(self, status: AwardStatus, processing_time: float) -> None:
        """更新頒發統計.

        Args:
            status: 頒發狀態
            processing_time: 處理時間(毫秒)
        """
        self._stats["total_awards"] += 1

        if status == AwardStatus.SUCCESS:
            self._stats["successful_awards"] += 1
        elif status == AwardStatus.FAILED:
            self._stats["failed_awards"] += 1
        elif status == AwardStatus.DUPLICATE:
            self._stats["duplicate_awards"] += 1

        # 更新平均處理時間
        total = self._stats["total_awards"]
        current_avg = self._stats["average_processing_time"]
        self._stats["average_processing_time"] = (
            current_avg * (total - 1) + processing_time
        ) / total

    def add_notification_handler(self, handler: callable) -> None:
        """添加通知處理器.

        Args:
            handler: 通知處理函數
        """
        if handler not in self._notification_handlers:
            self._notification_handlers.append(handler)
            logger.info(f"已添加通知處理器: {handler.__name__}")

    def remove_notification_handler(self, handler: callable) -> None:
        """移除通知處理器.

        Args:
            handler: 通知處理函數
        """
        if handler in self._notification_handlers:
            self._notification_handlers.remove(handler)
            logger.info(f"已移除通知處理器: {handler.__name__}")

    def get_award_stats(self) -> dict[str, Any]:
        """取得頒發統計資訊.

        Returns:
            統計資訊字典
        """
        current_time = datetime.now()
        uptime = (current_time - self._stats["last_reset"]).total_seconds()

        return {
            **self._stats,
            "active_awards": len(self._active_awards),
            "notification_handlers": len(self._notification_handlers),
            "uptime_seconds": uptime,
            "awards_per_second": self._stats["total_awards"] / uptime
            if uptime > 0
            else 0,
            "success_rate": (
                self._stats["successful_awards"] / self._stats["total_awards"]
                if self._stats["total_awards"] > 0
                else 0
            ),
        }

    def reset_stats(self) -> None:
        """重置頒發統計."""
        self._stats = {
            "total_awards": 0,
            "successful_awards": 0,
            "failed_awards": 0,
            "duplicate_awards": 0,
            "average_processing_time": 0.0,
            "last_reset": datetime.now(),
        }
        logger.info("頒發統計已重置")

__all__ = [
    "AchievementAwarder",
    "AwardRequest",
    "AwardResult",
    "AwardStatus",
]
