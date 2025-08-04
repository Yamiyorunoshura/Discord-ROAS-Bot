"""成就系統事務和資料一致性管理器.

此模組提供成就系統的事務管理和資料一致性保證功能,包含:
- 資料庫事務管理
- 快取同步機制
- 資料完整性驗證
- 操作回滾機制
- 統計資料即時更新

確保所有用戶成就管理操作的原子性、一致性、隔離性和持久性(ACID).
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable

logger = logging.getLogger(__name__)

class TransactionStatus(Enum):
    """事務狀態枚舉."""

    PENDING = "pending"
    ACTIVE = "active"
    COMMITTING = "committing"
    COMMITTED = "committed"
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"

class OperationType(Enum):
    """操作類型枚舉."""

    GRANT_ACHIEVEMENT = "grant_achievement"
    REVOKE_ACHIEVEMENT = "revoke_achievement"
    ADJUST_PROGRESS = "adjust_progress"
    RESET_USER_DATA = "reset_user_data"
    BULK_GRANT = "bulk_grant"
    BULK_REVOKE = "bulk_revoke"
    BULK_RESET = "bulk_reset"

@dataclass
class TransactionOperation:
    """事務操作記錄."""

    operation_id: str = field(default_factory=lambda: str(uuid4()))
    operation_type: OperationType = OperationType.GRANT_ACHIEVEMENT
    user_id: int = 0
    achievement_id: int | None = None
    old_value: Any | None = None
    new_value: Any | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    executed_at: datetime | None = None
    rollback_executed: bool = False

@dataclass
class CacheInvalidation:
    """快取失效記錄."""

    cache_type: str
    cache_keys: set[str] = field(default_factory=set)
    invalidated: bool = False

@dataclass
class DataIntegrityCheck:
    """資料完整性檢查."""

    check_id: str = field(default_factory=lambda: str(uuid4()))
    check_type: str = ""
    target_id: int = 0
    expected_state: dict[str, Any] = field(default_factory=dict)
    actual_state: dict[str, Any] = field(default_factory=dict)
    passed: bool = False
    error_message: str | None = None

@dataclass
class Transaction:
    """事務記錄."""

    transaction_id: str = field(default_factory=lambda: str(uuid4()))
    status: TransactionStatus = TransactionStatus.PENDING
    operations: list[TransactionOperation] = field(default_factory=list)
    cache_invalidations: list[CacheInvalidation] = field(default_factory=list)
    integrity_checks: list[DataIntegrityCheck] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    rollback_reason: str | None = None

class TransactionManager:
    """事務管理器.

    提供資料庫事務管理、快取同步、資料完整性驗證等功能.
    """

    def __init__(self, cache_service=None, achievement_service=None):
        """初始化事務管理器.

        Args:
            cache_service: 快取服務實例
            achievement_service: 成就服務實例
        """
        self.cache_service = cache_service
        self.achievement_service = achievement_service

        # 活動事務追蹤
        self._active_transactions: dict[str, Transaction] = {}

        # 事務鎖,防止並發衝突
        self._transaction_locks: dict[str, asyncio.Lock] = {}

        # 統計資料
        self._stats = {
            "transactions_created": 0,
            "transactions_committed": 0,
            "transactions_rolled_back": 0,
            "operations_executed": 0,
            "cache_invalidations": 0,
            "integrity_checks_passed": 0,
            "integrity_checks_failed": 0,
        }

        logger.info("TransactionManager 初始化完成")

    @asynccontextmanager
    async def transaction(
        self,
        operation_type: OperationType,
        user_ids: list[int] | None = None,
        **metadata,
    ) -> AsyncGenerator[Transaction, None]:
        """創建事務上下文管理器.

        Args:
            operation_type: 操作類型
            user_ids: 涉及的用戶ID列表
            **metadata: 額外的事務元數據

        Yields:
            Transaction: 事務實例
        """
        transaction = Transaction()
        transaction.status = TransactionStatus.ACTIVE
        transaction.started_at = datetime.utcnow()

        # 添加到活動事務追蹤
        self._active_transactions[transaction.transaction_id] = transaction
        self._stats["transactions_created"] += 1

        # 創建用戶鎖
        if user_ids:
            for user_id in user_ids:
                lock_key = f"user_{user_id}"
                if lock_key not in self._transaction_locks:
                    self._transaction_locks[lock_key] = asyncio.Lock()

        logger.info(
            f"[事務管理器]開始事務 {transaction.transaction_id}",
            extra={
                "transaction_id": transaction.transaction_id,
                "operation_type": operation_type.value,
                "user_ids": user_ids,
                "metadata": metadata,
            },
        )

        try:
            # 獲取用戶鎖
            acquired_locks = []
            if user_ids:
                for user_id in user_ids:
                    lock_key = f"user_{user_id}"
                    lock = self._transaction_locks[lock_key]
                    await lock.acquire()
                    acquired_locks.append(lock)

            yield transaction

            # 提交事務
            await self._commit_transaction(transaction)

        except Exception as e:
            logger.error(
                f"[事務管理器]事務執行失敗 {transaction.transaction_id}: {e}",
                exc_info=True,
            )
            transaction.error_message = str(e)
            await self._rollback_transaction(transaction, f"執行錯誤: {e}")
            raise

        finally:
            # 釋放鎖
            for lock in acquired_locks:
                with suppress(RuntimeError):
                    lock.release()

            # 從活動事務中移除
            self._active_transactions.pop(transaction.transaction_id, None)

            # 清理過期的鎖
            await self._cleanup_expired_locks()

    async def add_operation(
        self,
        transaction: Transaction,
        operation_type: OperationType,
        user_id: int,
        achievement_id: int | None = None,
        old_value: Any | None = None,
        new_value: Any | None = None,
        **metadata,
    ) -> TransactionOperation:
        """添加操作到事務.

        Args:
            transaction: 事務實例
            operation_type: 操作類型
            user_id: 用戶ID
            achievement_id: 成就ID
            old_value: 操作前的值
            new_value: 操作後的值
            **metadata: 操作元數據

        Returns:
            TransactionOperation: 操作記錄
        """
        operation = TransactionOperation(
            operation_type=operation_type,
            user_id=user_id,
            achievement_id=achievement_id,
            old_value=old_value,
            new_value=new_value,
            metadata=metadata,
            executed_at=datetime.utcnow(),
        )

        transaction.operations.append(operation)
        self._stats["operations_executed"] += 1

        logger.debug(
            f"[事務管理器]添加操作到事務 {transaction.transaction_id}",
            extra={
                "operation_id": operation.operation_id,
                "operation_type": operation_type.value,
                "user_id": user_id,
                "achievement_id": achievement_id,
            },
        )

        return operation

    async def add_cache_invalidation(
        self, transaction: Transaction, cache_type: str, cache_keys: set[str]
    ) -> CacheInvalidation:
        """添加快取失效記錄.

        Args:
            transaction: 事務實例
            cache_type: 快取類型
            cache_keys: 要失效的快取鍵集合

        Returns:
            CacheInvalidation: 快取失效記錄
        """
        invalidation = CacheInvalidation(cache_type=cache_type, cache_keys=cache_keys)

        transaction.cache_invalidations.append(invalidation)

        logger.debug(
            f"[事務管理器]添加快取失效到事務 {transaction.transaction_id}",
            extra={"cache_type": cache_type, "cache_keys_count": len(cache_keys)},
        )

        return invalidation

    async def add_integrity_check(
        self,
        transaction: Transaction,
        check_type: str,
        target_id: int,
        expected_state: dict[str, Any],
        validation_func: Callable | None = None,
    ) -> DataIntegrityCheck:
        """添加資料完整性檢查.

        Args:
            transaction: 事務實例
            check_type: 檢查類型
            target_id: 目標ID
            expected_state: 期望狀態
            validation_func: 自定義驗證函數

        Returns:
            DataIntegrityCheck: 完整性檢查記錄
        """
        check = DataIntegrityCheck(
            check_type=check_type, target_id=target_id, expected_state=expected_state
        )

        # 執行檢查
        try:
            if validation_func:
                actual_state = await validation_func(target_id)
            else:
                actual_state = await self._get_actual_state(check_type, target_id)

            check.actual_state = actual_state
            check.passed = self._validate_state(expected_state, actual_state)

            if not check.passed:
                check.error_message = (
                    f"狀態不匹配: 期望 {expected_state}, 實際 {actual_state}"
                )
                self._stats["integrity_checks_failed"] += 1
            else:
                self._stats["integrity_checks_passed"] += 1

        except Exception as e:
            check.passed = False
            check.error_message = f"檢查執行失敗: {e}"
            self._stats["integrity_checks_failed"] += 1
            logger.error(f"[事務管理器]完整性檢查失敗: {e}", exc_info=True)

        transaction.integrity_checks.append(check)

        logger.debug(
            f"[事務管理器]添加完整性檢查到事務 {transaction.transaction_id}",
            extra={
                "check_id": check.check_id,
                "check_type": check_type,
                "target_id": target_id,
                "passed": check.passed,
            },
        )

        return check

    async def _commit_transaction(self, transaction: Transaction) -> None:
        """提交事務.

        Args:
            transaction: 事務實例
        """
        transaction.status = TransactionStatus.COMMITTING

        try:
            # 執行完整性檢查
            failed_checks = [
                check for check in transaction.integrity_checks if not check.passed
            ]
            if failed_checks:
                raise ValueError(f"完整性檢查失敗: {len(failed_checks)} 個檢查未通過")

            # 執行快取失效
            await self._execute_cache_invalidations(transaction)

            # 更新統計資料
            await self._update_statistics(transaction)

            transaction.status = TransactionStatus.COMMITTED
            transaction.completed_at = datetime.utcnow()
            self._stats["transactions_committed"] += 1

            logger.info(
                f"[事務管理器]事務提交成功 {transaction.transaction_id}",
                extra={
                    "operations_count": len(transaction.operations),
                    "cache_invalidations_count": len(transaction.cache_invalidations),
                    "integrity_checks_count": len(transaction.integrity_checks),
                    "duration_ms": (
                        transaction.completed_at - transaction.started_at
                    ).total_seconds()
                    * 1000,
                },
            )

        except Exception as e:
            logger.error(
                f"[事務管理器]事務提交失敗 {transaction.transaction_id}: {e}",
                exc_info=True,
            )
            transaction.status = TransactionStatus.FAILED
            transaction.error_message = str(e)
            raise

    async def _rollback_transaction(
        self, transaction: Transaction, reason: str
    ) -> None:
        """回滾事務.

        Args:
            transaction: 事務實例
            reason: 回滾原因
        """
        transaction.status = TransactionStatus.ROLLING_BACK
        transaction.rollback_reason = reason

        try:
            rollback_count = 0
            for operation in reversed(transaction.operations):
                if not operation.rollback_executed:
                    await self._rollback_operation(operation)
                    operation.rollback_executed = True
                    rollback_count += 1

            transaction.status = TransactionStatus.ROLLED_BACK
            transaction.completed_at = datetime.utcnow()
            self._stats["transactions_rolled_back"] += 1

            logger.warning(
                f"[事務管理器]事務回滾完成 {transaction.transaction_id}",
                extra={
                    "reason": reason,
                    "rollback_operations": rollback_count,
                    "total_operations": len(transaction.operations),
                },
            )

        except Exception as e:
            logger.error(
                f"[事務管理器]事務回滾失敗 {transaction.transaction_id}: {e}",
                exc_info=True,
            )
            transaction.status = TransactionStatus.FAILED
            transaction.error_message = f"回滾失敗: {e}"
            raise

    async def _rollback_operation(self, operation: TransactionOperation) -> None:
        """回滾單個操作.

        Args:
            operation: 操作記錄
        """
        try:
            if operation.operation_type == OperationType.GRANT_ACHIEVEMENT:
                if self.achievement_service and operation.achievement_id:
                    await self.achievement_service.revoke_user_achievement(
                        operation.user_id, operation.achievement_id
                    )

            elif operation.operation_type == OperationType.REVOKE_ACHIEVEMENT:
                if self.achievement_service and operation.achievement_id:
                    await self.achievement_service.grant_user_achievement(
                        operation.user_id, operation.achievement_id
                    )

            elif operation.operation_type == OperationType.ADJUST_PROGRESS:
                if (
                    self.achievement_service
                    and operation.achievement_id
                    and operation.old_value is not None
                ):
                    await self.achievement_service.update_user_progress(
                        operation.user_id, operation.achievement_id, operation.old_value
                    )

            elif operation.operation_type == OperationType.RESET_USER_DATA and operation.old_value and isinstance(operation.old_value, dict):
                await self._restore_user_data(
                    operation.user_id, operation.old_value
                )

            logger.debug(
                "[事務管理器]操作回滾成功",
                extra={
                    "operation_id": operation.operation_id,
                    "operation_type": operation.operation_type.value,
                    "user_id": operation.user_id,
                },
            )

        except Exception as e:
            logger.error(
                f"[事務管理器]操作回滾失敗 {operation.operation_id}: {e}",
                exc_info=True,
            )
            raise

    async def _execute_cache_invalidations(self, transaction: Transaction) -> None:
        """執行快取失效.

        Args:
            transaction: 事務實例
        """
        if not self.cache_service:
            return

        invalidation_count = 0
        for invalidation in transaction.cache_invalidations:
            try:
                for cache_key in invalidation.cache_keys:
                    await self.cache_service.invalidate(
                        invalidation.cache_type, cache_key
                    )
                    invalidation_count += 1

                invalidation.invalidated = True

            except Exception as e:
                logger.error(
                    f"[事務管理器]快取失效失敗 {invalidation.cache_type}: {e}"
                )
                raise

        self._stats["cache_invalidations"] += invalidation_count

        logger.debug(
            "[事務管理器]快取失效完成",
            extra={
                "transaction_id": transaction.transaction_id,
                "invalidation_count": invalidation_count,
            },
        )

    async def _update_statistics(self, transaction: Transaction) -> None:
        """更新統計資料.

        Args:
            transaction: 事務實例
        """
        try:
            # 統計需要更新的類型
            stats_to_update = set()

            for operation in transaction.operations:
                if operation.operation_type in [
                    OperationType.GRANT_ACHIEVEMENT,
                    OperationType.REVOKE_ACHIEVEMENT,
                ]:
                    stats_to_update.add("user_achievements")
                    stats_to_update.add("global_stats")

                elif operation.operation_type == OperationType.ADJUST_PROGRESS:
                    stats_to_update.add("user_progress")
                    stats_to_update.add("global_stats")

                elif operation.operation_type in [
                    OperationType.RESET_USER_DATA,
                    OperationType.BULK_RESET,
                ]:
                    stats_to_update.add("user_achievements")
                    stats_to_update.add("user_progress")
                    stats_to_update.add("global_stats")
                    stats_to_update.add("leaderboard")

            # 觸發統計更新
            for stat_type in stats_to_update:
                await self._trigger_stats_update(stat_type, transaction)

            logger.debug(
                "[事務管理器]統計更新完成",
                extra={
                    "transaction_id": transaction.transaction_id,
                    "updated_stats": list(stats_to_update),
                },
            )

        except Exception as e:
            logger.error(f"[事務管理器]統計更新失敗: {e}", exc_info=True)
            # 統計更新失敗不應該影響事務提交

    async def _get_actual_state(
        self, check_type: str, target_id: int
    ) -> dict[str, Any]:
        """獲取實際狀態.

        Args:
            check_type: 檢查類型
            target_id: 目標ID

        Returns:
            Dict[str, Any]: 實際狀態
        """
        if check_type == "user_achievement_count":
            # 獲取用戶成就數量
            if self.achievement_service:
                achievements = await self.achievement_service.get_user_achievements(
                    target_id
                )
                return {"count": len(achievements)}

        elif check_type == "user_progress":
            # 獲取用戶進度狀態
            if self.achievement_service:
                progress = await self.achievement_service.get_user_progress(target_id)
                return {"progress_count": len(progress)}

        elif check_type == "achievement_exists" and self.achievement_service:
            # 檢查成就是否存在
            achievement = await self.achievement_service.get_achievement(target_id)
            return {"exists": achievement is not None}

        return {}

    def _validate_state(self, expected: dict[str, Any], actual: dict[str, Any]) -> bool:
        """驗證狀態是否匹配.

        Args:
            expected: 期望狀態
            actual: 實際狀態

        Returns:
            bool: 是否匹配
        """
        for key, expected_value in expected.items():
            if key not in actual:
                return False

            actual_value = actual[key]

            # 支援範圍檢查
            if (
                isinstance(expected_value, dict)
                and "min" in expected_value
                and "max" in expected_value
            ):
                if not (expected_value["min"] <= actual_value <= expected_value["max"]):
                    return False
            elif actual_value != expected_value:
                return False

        return True

    async def _restore_user_data(
        self, user_id: int, backup_data: dict[str, Any]
    ) -> None:
        """恢復用戶資料.

        Args:
            user_id: 用戶ID
            backup_data: 備份資料
        """
        try:
            if not self.achievement_service:
                return

            # 恢復用戶成就
            if "achievements" in backup_data:
                for achievement_data in backup_data["achievements"]:
                    await self.achievement_service.grant_user_achievement(
                        user_id, achievement_data["achievement_id"]
                    )

            # 恢復用戶進度
            if "progress" in backup_data:
                for progress_data in backup_data["progress"]:
                    await self.achievement_service.update_user_progress(
                        user_id,
                        progress_data["achievement_id"],
                        progress_data["current_value"],
                    )

            logger.info(f"[事務管理器]用戶資料恢復完成: {user_id}")

        except Exception as e:
            logger.error(
                f"[事務管理器]用戶資料恢復失敗 {user_id}: {e}", exc_info=True
            )
            raise

    async def _trigger_stats_update(
        self, stat_type: str, transaction: Transaction  # noqa: ARG002
    ) -> None:
        """觸發統計更新.

        Args:
            stat_type: 統計類型
            transaction: 事務實例
        """
        try:
            # 這裡可以觸發異步統計更新任務
            # 實際實現中可能需要使用任務隊列或後台任務
            logger.debug(f"[事務管理器]觸發統計更新: {stat_type}")

        except Exception as e:
            logger.error(f"[事務管理器]觸發統計更新失敗 {stat_type}: {e}")

    async def _cleanup_expired_locks(self) -> None:
        """清理過期的鎖."""
        try:
            # 清理不再使用的鎖
            # 實際實現中可能需要更複雜的清理邏輯
            pass
        except Exception as e:
            logger.error(f"[事務管理器]清理鎖失敗: {e}")

    def get_transaction_stats(self) -> dict[str, Any]:
        """獲取事務統計.

        Returns:
            Dict[str, Any]: 統計資料
        """
        return {
            **self._stats,
            "active_transactions": len(self._active_transactions),
            "active_locks": len(self._transaction_locks),
        }

    async def get_active_transactions(self) -> list[dict[str, Any]]:
        """獲取活動事務列表.

        Returns:
            List[Dict[str, Any]]: 活動事務資訊
        """
        transactions = []
        for transaction in self._active_transactions.values():
            transactions.append(
                {
                    "transaction_id": transaction.transaction_id,
                    "status": transaction.status.value,
                    "operations_count": len(transaction.operations),
                    "created_at": transaction.created_at.isoformat(),
                    "started_at": transaction.started_at.isoformat()
                    if transaction.started_at
                    else None,
                    "duration_seconds": (
                        datetime.utcnow() - transaction.started_at
                    ).total_seconds()
                    if transaction.started_at
                    else 0,
                }
            )

        return transactions
