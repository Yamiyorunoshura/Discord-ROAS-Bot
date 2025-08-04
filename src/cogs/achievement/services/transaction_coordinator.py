"""成就系統事務協調器.

此模組提供成就系統的統一事務協調功能,整合:
- 事務管理器
- 快取同步管理器
- 資料完整性驗證器
- 統計資料更新器

提供完整的 ACID 事務保證和資料一致性管理.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from .cache_sync_manager import CacheEvent, CacheEventType, CacheSyncManager
from .data_integrity_validator import (
    DataIntegrityValidator,
    ValidationLevel,
    ValidationReport,
)
from .transaction_manager import (
    OperationType,
    Transaction,
    TransactionManager,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

logger = logging.getLogger(__name__)

class CoordinatorStatus(Enum):
    """協調器狀態枚舉."""

    INITIALIZING = "initializing"
    READY = "ready"
    BUSY = "busy"
    ERROR = "error"
    SHUTDOWN = "shutdown"

@dataclass
class CoordinatedOperation:
    """協調操作記錄."""

    operation_id: str
    operation_type: OperationType
    user_ids: list[int] = field(default_factory=list)
    achievement_ids: list[int] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    transaction: Transaction | None = None
    cache_events: list[CacheEvent] = field(default_factory=list)
    validation_reports: list[ValidationReport] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    success: bool = False
    error_message: str | None = None

class TransactionCoordinator:
    """事務協調器.

    統一協調事務管理、快取同步和資料驗證.
    """

    def __init__(
        self,
        achievement_service=None,
        cache_service=None,
        enable_validation: bool = True,
        validation_level: ValidationLevel = ValidationLevel.STANDARD,
    ):
        """初始化事務協調器.

        Args:
            achievement_service: 成就服務實例
            cache_service: 快取服務實例
            enable_validation: 是否啟用驗證
            validation_level: 驗證級別
        """
        self.achievement_service = achievement_service
        self.cache_service = cache_service
        self.enable_validation = enable_validation
        self.validation_level = validation_level

        # 初始化子管理器
        self.transaction_manager = TransactionManager(
            cache_service=cache_service, achievement_service=achievement_service
        )

        self.cache_sync_manager = CacheSyncManager(cache_service=cache_service)

        self.data_validator = (
            DataIntegrityValidator(
                achievement_service=achievement_service, cache_service=cache_service
            )
            if enable_validation
            else None
        )

        # 狀態管理
        self.status = CoordinatorStatus.READY

        # 統計資料
        self._stats = {
            "operations_coordinated": 0,
            "successful_operations": 0,
            "failed_operations": 0,
            "validations_performed": 0,
            "cache_events_processed": 0,
        }

        logger.info("TransactionCoordinator 初始化完成")

    @asynccontextmanager
    async def coordinate_operation(
        self,
        operation_type: OperationType,
        user_ids: list[int] | None = None,
        achievement_ids: list[int] | None = None,
        pre_validation: bool = False,
        post_validation: bool = True,
        **metadata,
    ) -> AsyncGenerator[CoordinatedOperation, None]:
        """協調操作上下文管理器.

        Args:
            operation_type: 操作類型
            user_ids: 涉及的用戶ID列表
            achievement_ids: 涉及的成就ID列表
            pre_validation: 是否執行預驗證
            post_validation: 是否執行後驗證
            **metadata: 額外的操作元數據

        Yields:
            CoordinatedOperation: 協調操作實例
        """
        # 檢查協調器狀態
        if self.status != CoordinatorStatus.READY:
            raise RuntimeError(f"事務協調器不可用,當前狀態: {self.status.value}")

        self.status = CoordinatorStatus.BUSY

        coordinated_op = CoordinatedOperation(
            operation_id=str(uuid4()),
            operation_type=operation_type,
            user_ids=user_ids or [],
            achievement_ids=achievement_ids or [],
            metadata=metadata,
        )

        self._stats["operations_coordinated"] += 1

        logger.info(
            f"[事務協調器]開始協調操作 {coordinated_op.operation_id}",
            extra={
                "operation_type": operation_type.value,
                "user_ids": user_ids,
                "achievement_ids": achievement_ids,
                "metadata": metadata,
            },
        )

        try:
            # 預驗證
            if pre_validation and self.enable_validation:
                await self._perform_pre_validation(coordinated_op)

            # 開始事務
            async with self.transaction_manager.transaction(
                operation_type, user_ids, **metadata
            ) as transaction:
                coordinated_op.transaction = transaction

                yield coordinated_op

                # 操作完成後的處理
                await self._post_operation_processing(coordinated_op)

            # 後驗證
            if post_validation and self.enable_validation:
                await self._perform_post_validation(coordinated_op)

            coordinated_op.success = True
            coordinated_op.completed_at = datetime.utcnow()
            self._stats["successful_operations"] += 1

            logger.info(
                f"[事務協調器]操作協調完成 {coordinated_op.operation_id}",
                extra={
                    "success": True,
                    "duration_ms": (
                        coordinated_op.completed_at - coordinated_op.started_at
                    ).total_seconds()
                    * 1000,
                },
            )

        except Exception as e:
            coordinated_op.success = False
            coordinated_op.error_message = str(e)
            coordinated_op.completed_at = datetime.utcnow()
            self._stats["failed_operations"] += 1

            logger.error(
                f"[事務協調器]操作協調失敗 {coordinated_op.operation_id}: {e}",
                exc_info=True,
            )
            raise

        finally:
            self.status = CoordinatorStatus.READY

    async def grant_achievement_coordinated(
        self, user_id: int, achievement_id: int, notify: bool = True, **metadata
    ) -> dict[str, Any]:
        """協調式成就授予.

        Args:
            user_id: 用戶ID
            achievement_id: 成就ID
            notify: 是否通知用戶
            **metadata: 額外元數據

        Returns:
            Dict[str, Any]: 操作結果
        """
        async with self.coordinate_operation(
            OperationType.GRANT_ACHIEVEMENT,
            user_ids=[user_id],
            achievement_ids=[achievement_id],
            notify=notify,
            **metadata,
        ) as coord_op:
            # 檢查用戶是否已經擁有該成就
            if self.achievement_service:
                existing_achievements = (
                    await self.achievement_service.get_user_achievements(user_id)
                )
                if any(
                    ua.achievement_id == achievement_id for ua in existing_achievements
                ):
                    raise ValueError(f"用戶 {user_id} 已經擁有成就 {achievement_id}")

            # 執行授予操作
            if self.achievement_service:
                user_achievement = (
                    await self.achievement_service.grant_user_achievement(
                        user_id, achievement_id, notify=notify
                    )
                )

                # 記錄操作到事務
                await self.transaction_manager.add_operation(
                    coord_op.transaction,
                    OperationType.GRANT_ACHIEVEMENT,
                    user_id,
                    achievement_id,
                    old_value=None,
                    new_value=user_achievement,
                    notify=notify,
                    **metadata,
                )

                # 添加快取失效
                await self.transaction_manager.add_cache_invalidation(
                    coord_op.transaction,
                    "user_achievements",
                    {f"user_achievements:{user_id}", "global_stats:*"},
                )

                # 添加完整性檢查
                await self.transaction_manager.add_integrity_check(
                    coord_op.transaction,
                    "user_achievement_count",
                    user_id,
                    {"count": {"min": len(existing_achievements) + 1}},
                )

                return {
                    "success": True,
                    "user_achievement": user_achievement,
                    "operation_id": coord_op.operation_id,
                }

            return {"success": False, "error": "成就服務不可用"}

    async def revoke_achievement_coordinated(
        self, user_id: int, achievement_id: int, reason: str = "管理員撤銷", **metadata
    ) -> dict[str, Any]:
        """協調式成就撤銷.

        Args:
            user_id: 用戶ID
            achievement_id: 成就ID
            reason: 撤銷原因
            **metadata: 額外元數據

        Returns:
            Dict[str, Any]: 操作結果
        """
        async with self.coordinate_operation(
            OperationType.REVOKE_ACHIEVEMENT,
            user_ids=[user_id],
            achievement_ids=[achievement_id],
            reason=reason,
            **metadata,
        ) as coord_op:
            # 檢查用戶是否擁有該成就
            if self.achievement_service:
                existing_achievements = (
                    await self.achievement_service.get_user_achievements(user_id)
                )
                user_achievement = next(
                    (
                        ua
                        for ua in existing_achievements
                        if ua.achievement_id == achievement_id
                    ),
                    None,
                )

                if not user_achievement:
                    raise ValueError(f"用戶 {user_id} 沒有成就 {achievement_id}")

                # 執行撤銷操作
                success = await self.achievement_service.revoke_user_achievement(
                    user_id, achievement_id
                )

                if success:
                    # 記錄操作到事務
                    await self.transaction_manager.add_operation(
                        coord_op.transaction,
                        OperationType.REVOKE_ACHIEVEMENT,
                        user_id,
                        achievement_id,
                        old_value=user_achievement,
                        new_value=None,
                        reason=reason,
                        **metadata,
                    )

                    # 添加快取失效
                    await self.transaction_manager.add_cache_invalidation(
                        coord_op.transaction,
                        "user_achievements",
                        {f"user_achievements:{user_id}", "global_stats:*"},
                    )

                    # 添加完整性檢查
                    await self.transaction_manager.add_integrity_check(
                        coord_op.transaction,
                        "user_achievement_count",
                        user_id,
                        {"count": {"max": len(existing_achievements) - 1}},
                    )

                    return {
                        "success": True,
                        "revoked_achievement": user_achievement,
                        "operation_id": coord_op.operation_id,
                    }

                return {"success": False, "error": "撤銷操作失敗"}

            return {"success": False, "error": "成就服務不可用"}

    async def adjust_progress_coordinated(
        self, user_id: int, achievement_id: int, new_value: float, **metadata
    ) -> dict[str, Any]:
        """協調式進度調整.

        Args:
            user_id: 用戶ID
            achievement_id: 成就ID
            new_value: 新的進度值
            **metadata: 額外元數據

        Returns:
            Dict[str, Any]: 操作結果
        """
        async with self.coordinate_operation(
            OperationType.ADJUST_PROGRESS,
            user_ids=[user_id],
            achievement_ids=[achievement_id],
            new_value=new_value,
            **metadata,
        ) as coord_op:
            if self.achievement_service:
                # 獲取當前進度
                current_progress = (
                    await self.achievement_service.get_user_progress_for_achievement(
                        user_id, achievement_id
                    )
                )

                old_value = current_progress.current_value if current_progress else 0

                # 執行進度調整
                updated_progress = await self.achievement_service.update_user_progress(
                    user_id, achievement_id, new_value
                )

                # 記錄操作到事務
                await self.transaction_manager.add_operation(
                    coord_op.transaction,
                    OperationType.ADJUST_PROGRESS,
                    user_id,
                    achievement_id,
                    old_value=old_value,
                    new_value=new_value,
                    **metadata,
                )

                # 添加快取失效
                await self.transaction_manager.add_cache_invalidation(
                    coord_op.transaction,
                    "user_progress",
                    {
                        f"user_progress:{user_id}",
                        f"user_progress:{user_id}:{achievement_id}",
                    },
                )

                # 檢查是否完成成就
                if (
                    updated_progress
                    and updated_progress.current_value >= updated_progress.target_value
                ):
                    # 可能需要授予成就
                    existing_achievements = (
                        await self.achievement_service.get_user_achievements(user_id)
                    )
                    if not any(
                        ua.achievement_id == achievement_id
                        for ua in existing_achievements
                    ):
                        # 自動授予成就
                        await self.achievement_service.grant_user_achievement(
                            user_id, achievement_id
                        )

                        # 添加成就授予的快取失效
                        await self.transaction_manager.add_cache_invalidation(
                            coord_op.transaction,
                            "user_achievements",
                            {f"user_achievements:{user_id}"},
                        )

                return {
                    "success": True,
                    "updated_progress": updated_progress,
                    "old_value": old_value,
                    "new_value": new_value,
                    "operation_id": coord_op.operation_id,
                }

            return {"success": False, "error": "成就服務不可用"}

    async def reset_user_data_coordinated(
        self, user_id: int, backup_data: bool = True, **metadata
    ) -> dict[str, Any]:
        """協調式用戶資料重置.

        Args:
            user_id: 用戶ID
            backup_data: 是否備份資料
            **metadata: 額外元數據

        Returns:
            Dict[str, Any]: 操作結果
        """
        async with self.coordinate_operation(
            OperationType.RESET_USER_DATA,
            user_ids=[user_id],
            backup_data=backup_data,
            **metadata,
        ) as coord_op:
            if self.achievement_service:
                # 備份用戶資料
                backup = None
                if backup_data:
                    backup = await self._create_user_backup(user_id)

                # 執行重置
                reset_result = await self.achievement_service.reset_user_data(user_id)

                # 記錄操作到事務
                await self.transaction_manager.add_operation(
                    coord_op.transaction,
                    OperationType.RESET_USER_DATA,
                    user_id,
                    None,
                    old_value=backup,
                    new_value=reset_result,
                    backup_data=backup_data,
                    **metadata,
                )

                # 添加快取失效
                await self.transaction_manager.add_cache_invalidation(
                    coord_op.transaction,
                    "user_achievements",
                    {
                        f"user_achievements:{user_id}",
                        f"user_progress:{user_id}",
                        "global_stats:*",
                    },
                )

                return {
                    "success": True,
                    "reset_result": reset_result,
                    "backup": backup,
                    "operation_id": coord_op.operation_id,
                }

            return {"success": False, "error": "成就服務不可用"}

    async def bulk_operation_coordinated(
        self,
        operation_type: OperationType,
        user_ids: list[int],
        achievement_id: int | None = None,
        **metadata,
    ) -> dict[str, Any]:
        """協調式批量操作.

        Args:
            operation_type: 操作類型
            user_ids: 用戶ID列表
            achievement_id: 成就ID(用於批量授予/撤銷)
            **metadata: 額外元數據

        Returns:
            Dict[str, Any]: 操作結果
        """
        async with self.coordinate_operation(
            operation_type,
            user_ids=user_ids,
            achievement_ids=[achievement_id] if achievement_id else None,
            **metadata,
        ) as coord_op:
            results = []
            successful_operations = 0
            failed_operations = 0

            for user_id in user_ids:
                try:
                    if operation_type == OperationType.BULK_GRANT:
                        result = await self._execute_single_grant(
                            user_id, achievement_id, coord_op
                        )
                    elif operation_type == OperationType.BULK_REVOKE:
                        result = await self._execute_single_revoke(
                            user_id, achievement_id, coord_op
                        )
                    elif operation_type == OperationType.BULK_RESET:
                        result = await self._execute_single_reset(user_id, coord_op)
                    else:
                        result = {
                            "success": False,
                            "error": f"不支援的批量操作類型: {operation_type}",
                        }

                    results.append({"user_id": user_id, **result})

                    if result.get("success"):
                        successful_operations += 1
                    else:
                        failed_operations += 1

                except Exception as e:
                    logger.error(f"[事務協調器]批量操作失敗 用戶 {user_id}: {e}")
                    results.append(
                        {"user_id": user_id, "success": False, "error": str(e)}
                    )
                    failed_operations += 1

            # 添加批量快取失效
            cache_keys = set()
            for user_id in user_ids:
                cache_keys.add(f"user_achievements:{user_id}")
                cache_keys.add(f"user_progress:{user_id}")
            cache_keys.add("global_stats:*")

            await self.transaction_manager.add_cache_invalidation(
                coord_op.transaction, "bulk_operation", cache_keys
            )

            return {
                "success": failed_operations == 0,
                "results": results,
                "successful_operations": successful_operations,
                "failed_operations": failed_operations,
                "total_operations": len(user_ids),
                "operation_id": coord_op.operation_id,
            }

    async def _perform_pre_validation(
        self, coordinated_op: CoordinatedOperation
    ) -> None:
        """執行預驗證.

        Args:
            coordinated_op: 協調操作
        """
        if not self.data_validator:
            return

        try:
            # 驗證涉及的用戶
            for user_id in coordinated_op.user_ids:
                report = await self.data_validator.validate_user_data(
                    user_id,
                    ValidationLevel.BASIC,  # 預驗證使用基本級別
                )
                coordinated_op.validation_reports.append(report)

                # 檢查嚴重問題
                critical_issues = [
                    issue
                    for issue in report.issues
                    if issue.severity.value in ["failed", "error"]
                ]

                if critical_issues:
                    raise ValueError(
                        f"用戶 {user_id} 資料驗證失敗: {len(critical_issues)} 個嚴重問題"
                    )

            self._stats["validations_performed"] += len(coordinated_op.user_ids)

        except Exception as e:
            logger.error(f"[事務協調器]預驗證失敗: {e}")
            raise

    async def _perform_post_validation(
        self, coordinated_op: CoordinatedOperation
    ) -> None:
        """執行後驗證.

        Args:
            coordinated_op: 協調操作
        """
        if not self.data_validator:
            return

        try:
            # 驗證操作後的資料狀態
            for user_id in coordinated_op.user_ids:
                report = await self.data_validator.validate_user_data(
                    user_id, self.validation_level
                )
                coordinated_op.validation_reports.append(report)

            self._stats["validations_performed"] += len(coordinated_op.user_ids)

        except Exception as e:
            logger.warning(f"[事務協調器]後驗證失敗: {e}")
            # 後驗證失敗不應該中斷事務

    async def _post_operation_processing(
        self, coordinated_op: CoordinatedOperation
    ) -> None:
        """操作後處理.

        Args:
            coordinated_op: 協調操作
        """
        try:
            # 創建快取事件
            cache_event = await self._create_cache_event(coordinated_op)
            if cache_event:
                await self.cache_sync_manager.process_cache_event(cache_event)
                coordinated_op.cache_events.append(cache_event)
                self._stats["cache_events_processed"] += 1

        except Exception as e:
            logger.error(f"[事務協調器]操作後處理失敗: {e}")
            # 不中斷主要流程

    async def _create_cache_event(
        self, coordinated_op: CoordinatedOperation
    ) -> CacheEvent | None:
        """創建快取事件.

        Args:
            coordinated_op: 協調操作

        Returns:
            Optional[CacheEvent]: 快取事件
        """
        try:
            # 映射操作類型到快取事件類型
            event_type_mapping = {
                OperationType.GRANT_ACHIEVEMENT: CacheEventType.ACHIEVEMENT_GRANTED,
                OperationType.REVOKE_ACHIEVEMENT: CacheEventType.ACHIEVEMENT_REVOKED,
                OperationType.ADJUST_PROGRESS: CacheEventType.PROGRESS_UPDATED,
                OperationType.RESET_USER_DATA: CacheEventType.USER_DATA_RESET,
                OperationType.BULK_GRANT: CacheEventType.BULK_OPERATION,
                OperationType.BULK_REVOKE: CacheEventType.BULK_OPERATION,
                OperationType.BULK_RESET: CacheEventType.BULK_OPERATION,
            }

            event_type = event_type_mapping.get(coordinated_op.operation_type)
            if not event_type:
                return None

            return await self.cache_sync_manager.create_cache_event(
                event_type=event_type,
                user_ids=coordinated_op.user_ids,
                achievement_ids=coordinated_op.achievement_ids,
                operation_id=coordinated_op.operation_id,
                **coordinated_op.metadata,
            )

        except Exception as e:
            logger.error(f"[事務協調器]創建快取事件失敗: {e}")
            return None

    async def _create_user_backup(self, user_id: int) -> dict[str, Any]:
        """創建用戶資料備份.

        Args:
            user_id: 用戶ID

        Returns:
            Dict[str, Any]: 備份資料
        """
        try:
            backup = {
                "user_id": user_id,
                "backup_time": datetime.utcnow().isoformat(),
                "achievements": [],
                "progress": [],
            }

            if self.achievement_service:
                # 備份成就
                user_achievements = (
                    await self.achievement_service.get_user_achievements(user_id)
                )
                backup["achievements"] = [
                    {
                        "achievement_id": ua.achievement_id,
                        "earned_at": ua.earned_at.isoformat() if ua.earned_at else None,
                        "notified": getattr(ua, "notified", True),
                    }
                    for ua in user_achievements
                ]

                # 備份進度
                user_progress = await self.achievement_service.get_user_progress(
                    user_id
                )
                backup["progress"] = [
                    {
                        "achievement_id": up.achievement_id,
                        "current_value": up.current_value,
                        "target_value": up.target_value,
                        "progress_data": getattr(up, "progress_data", {}),
                        "last_updated": up.last_updated.isoformat()
                        if up.last_updated
                        else None,
                    }
                    for up in user_progress
                ]

            return backup

        except Exception as e:
            logger.error(f"[事務協調器]創建用戶備份失敗 {user_id}: {e}")
            return {}

    async def _execute_single_grant(
        self, user_id: int, achievement_id: int, coord_op: CoordinatedOperation
    ) -> dict[str, Any]:
        """執行單個授予操作."""
        try:
            if not self.achievement_service:
                return {"success": False, "error": "成就服務不可用"}

            user_achievement = await self.achievement_service.grant_user_achievement(
                user_id, achievement_id
            )

            # 記錄到事務
            await self.transaction_manager.add_operation(
                coord_op.transaction,
                OperationType.BULK_GRANT,
                user_id,
                achievement_id,
                new_value=user_achievement,
            )

            return {"success": True, "user_achievement": user_achievement}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _execute_single_revoke(
        self, user_id: int, achievement_id: int, coord_op: CoordinatedOperation
    ) -> dict[str, Any]:
        """執行單個撤銷操作."""
        try:
            if not self.achievement_service:
                return {"success": False, "error": "成就服務不可用"}

            success = await self.achievement_service.revoke_user_achievement(
                user_id, achievement_id
            )

            # 記錄到事務
            await self.transaction_manager.add_operation(
                coord_op.transaction,
                OperationType.BULK_REVOKE,
                user_id,
                achievement_id,
                old_value=True,
                new_value=None,
            )

            return {"success": success}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _execute_single_reset(
        self, user_id: int, coord_op: CoordinatedOperation
    ) -> dict[str, Any]:
        """執行單個重置操作."""
        try:
            if not self.achievement_service:
                return {"success": False, "error": "成就服務不可用"}

            # 創建備份
            backup = await self._create_user_backup(user_id)

            # 執行重置
            reset_result = await self.achievement_service.reset_user_data(user_id)

            # 記錄到事務
            await self.transaction_manager.add_operation(
                coord_op.transaction,
                OperationType.BULK_RESET,
                user_id,
                None,
                old_value=backup,
                new_value=reset_result,
            )

            return {"success": True, "reset_result": reset_result, "backup": backup}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_coordinator_stats(self) -> dict[str, Any]:
        """獲取協調器統計.

        Returns:
            Dict[str, Any]: 統計資料
        """
        stats = {
            "coordinator": self._stats,
            "status": self.status.value,
            "validation_enabled": self.enable_validation,
            "validation_level": self.validation_level.value
            if self.enable_validation
            else None,
        }

        # 添加子管理器統計
        if self.transaction_manager:
            stats["transaction_manager"] = (
                self.transaction_manager.get_transaction_stats()
            )

        if self.cache_sync_manager:
            stats["cache_sync_manager"] = self.cache_sync_manager.get_cache_stats()

        if self.data_validator:
            stats["data_validator"] = self.data_validator.get_validation_stats()

        return stats

    async def get_health_status(self) -> dict[str, Any]:
        """獲取健康狀態.

        Returns:
            Dict[str, Any]: 健康狀態資訊
        """
        health = {
            "coordinator_status": self.status.value,
            "services_available": {
                "achievement_service": self.achievement_service is not None,
                "cache_service": self.cache_service is not None,
                "transaction_manager": self.transaction_manager is not None,
                "cache_sync_manager": self.cache_sync_manager is not None,
                "data_validator": self.data_validator is not None,
            },
            "configuration": {
                "validation_enabled": self.enable_validation,
                "validation_level": self.validation_level.value
                if self.enable_validation
                else None,
            },
            "statistics": self.get_coordinator_stats(),
        }

        # 獲取快取健康狀態
        if self.cache_sync_manager:
            try:
                cache_health = await self.cache_sync_manager.get_cache_health()
                health["cache_health"] = cache_health
            except Exception as e:
                health["cache_health_error"] = str(e)

        return health
