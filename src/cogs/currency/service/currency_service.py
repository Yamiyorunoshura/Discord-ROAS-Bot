"""Currency Service for Discord ROAS Bot v2.0.

此模組提供貨幣系統的服務層實作,支援:
- 錢包管理與餘額查詢
- 原子性轉帳交易
- 排行榜查詢與統計
- 事件發布與通知
- 安全性檢查與驗證
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from src.cogs.core.event_bus import Event, EventPriority, get_global_event_bus
from src.cogs.currency.database import (
    ConcurrencyError,
    CurrencyRepository,
    InsufficientFundsError,
)
from src.core.database.postgresql import get_db_session

from .currency_statistics_service import CurrencyStatisticsService

logger = logging.getLogger(__name__)


class CurrencyService:
    """貨幣服務層.

    提供高層次的貨幣系統業務邏輯,整合資料存取和事件發布.
    """

    def __init__(self):
        """初始化貨幣服務."""
        self.logger = logger
        self.statistics_service = CurrencyStatisticsService()

    async def get_or_create_wallet(
        self, guild_id: int, user_id: int, initial_balance: int = 0
    ) -> dict[str, Any]:
        """取得或建立用戶錢包.

        Args:
            guild_id: Discord 伺服器 ID
            user_id: Discord 用戶 ID
            initial_balance: 初始餘額,預設為 0

        Returns:
            錢包資訊字典

        Raises:
            Exception: 當資料庫操作失敗時
        """
        async with get_db_session() as session:
            repository = CurrencyRepository(session)

            try:
                wallet = await repository.get_or_create_wallet(
                    guild_id, user_id, initial_balance
                )
                await repository.commit()

                # 如果是新建錢包且有初始餘額,發布事件
                if initial_balance > 0:
                    await self._publish_balance_update_event(
                        guild_id, user_id, initial_balance, wallet.balance
                    )

                return {
                    "guild_id": wallet.guild_id,
                    "user_id": wallet.user_id,
                    "balance": wallet.balance,
                    "transaction_count": wallet.transaction_count,
                    "last_transaction_at": wallet.last_transaction_at.isoformat()
                    if wallet.last_transaction_at
                    else None,
                    "created_at": wallet.created_at.isoformat(),
                    "updated_at": wallet.updated_at.isoformat(),
                }

            except Exception as e:
                await repository.rollback()
                self.logger.error(
                    f"建立或取得錢包失敗: guild_id={guild_id}, user_id={user_id}, error={e}"
                )
                raise

    async def get_balance(self, guild_id: int, user_id: int) -> int:
        """取得用戶餘額.

        Args:
            guild_id: Discord 伺服器 ID
            user_id: Discord 用戶 ID

        Returns:
            用戶目前餘額
        """
        async with get_db_session() as session:
            repository = CurrencyRepository(session)
            return await repository.get_balance(guild_id, user_id)

    async def transfer(
        self,
        guild_id: int,
        from_user_id: int,
        to_user_id: int,
        amount: int,
        reason: str | None = None,
        admin_initiated: bool = False,
    ) -> dict[str, Any]:
        """執行用戶之間的轉帳.

        Args:
            guild_id: Discord 伺服器 ID
            from_user_id: 轉出用戶 ID
            to_user_id: 轉入用戶 ID
            amount: 轉帳金額
            reason: 轉帳原因
            admin_initiated: 是否為管理員發起的轉帳

        Returns:
            轉帳結果字典

        Raises:
            ValueError: 當參數無效時
            InsufficientFundsError: 當餘額不足時
            ConcurrencyError: 當並發衝突時
        """
        if amount <= 0:
            raise ValueError(f"轉帳金額必須為正數: {amount}")

        if amount > 2**60:  # 防止溢出
            raise ValueError(f"轉帳金額過大: {amount}")

        async with get_db_session() as session:
            repository = CurrencyRepository(session)

            try:
                # 生成唯一交易 ID
                transaction_id = str(uuid.uuid4())

                # 檢查交易 ID 是否已存在(防重放攻擊)
                if await repository.check_transaction_exists(transaction_id):
                    raise ValueError("交易 ID 已存在,請重試")

                # 準備交易元資料
                metadata = {
                    "reason": reason,
                    "admin_initiated": admin_initiated,
                    "timestamp": datetime.now(UTC).isoformat(),
                }

                # 執行轉帳
                from_wallet, to_wallet = await repository.transfer(
                    guild_id,
                    from_user_id,
                    to_user_id,
                    amount,
                    transaction_id=transaction_id,
                    metadata=metadata,
                )
                await repository.commit()

                # 發布轉帳事件
                await self._publish_transfer_event(
                    transaction_id,
                    guild_id,
                    from_user_id,
                    to_user_id,
                    amount,
                    from_wallet.balance,
                    to_wallet.balance,
                    reason,
                )

                # 發布餘額更新事件
                await self._publish_balance_update_event(
                    guild_id, from_user_id, -amount, from_wallet.balance
                )
                await self._publish_balance_update_event(
                    guild_id, to_user_id, amount, to_wallet.balance
                )

                self.logger.info(
                    f"轉帳成功: {from_user_id} -> {to_user_id}, "
                    f"amount={amount}, tx_id={transaction_id}"
                )

                return {
                    "transaction_id": transaction_id,
                    "from_user_id": from_user_id,
                    "to_user_id": to_user_id,
                    "amount": amount,
                    "from_balance_after": from_wallet.balance,
                    "to_balance_after": to_wallet.balance,
                    "timestamp": datetime.now(UTC).isoformat(),
                    "reason": reason,
                    "admin_initiated": admin_initiated,
                }

            except (InsufficientFundsError, ValueError, ConcurrencyError):
                await repository.rollback()
                raise
            except Exception as e:
                await repository.rollback()
                self.logger.error(f"轉帳失敗: {e}")
                raise

    async def get_leaderboard(
        self, guild_id: int, limit: int = 10, offset: int = 0
    ) -> dict[str, Any]:
        """取得伺服器餘額排行榜.

        Args:
            guild_id: Discord 伺服器 ID
            limit: 限制數量(最大 100)
            offset: 偏移量

        Returns:
            排行榜資料字典
        """
        # 限制查詢數量
        limit = min(limit, 100)

        async with get_db_session() as session:
            repository = CurrencyRepository(session)

            leaderboard, total_count = await repository.get_leaderboard(
                guild_id, limit, offset
            )

            return {
                "guild_id": guild_id,
                "entries": [
                    {
                        "rank": offset + i + 1,
                        "user_id": wallet.user_id,
                        "balance": wallet.balance,
                        "transaction_count": wallet.transaction_count,
                        "last_transaction_at": wallet.last_transaction_at.isoformat()
                        if wallet.last_transaction_at
                        else None,
                    }
                    for i, wallet in enumerate(leaderboard)
                ],
                "total_count": total_count,
                "page_size": limit,
                "offset": offset,
                "has_next": offset + limit < total_count,
                "has_previous": offset > 0,
            }

    async def get_user_rank(self, guild_id: int, user_id: int) -> dict[str, Any]:
        """取得用戶排名資訊.

        Args:
            guild_id: Discord 伺服器 ID
            user_id: Discord 用戶 ID

        Returns:
            排名資訊字典
        """
        async with get_db_session() as session:
            repository = CurrencyRepository(session)

            rank, total = await repository.get_user_rank(guild_id, user_id)
            balance = await repository.get_balance(guild_id, user_id)

            return {
                "guild_id": guild_id,
                "user_id": user_id,
                "rank": rank,
                "total_users": total,
                "balance": balance,
                "percentile": ((total - rank + 1) / total * 100) if total > 0 else 0,
            }

    async def get_guild_statistics(self, guild_id: int) -> dict[str, Any]:
        """取得伺服器經濟統計 (使用 numpy 優化).

        Args:
            guild_id: Discord 伺服器 ID

        Returns:
            統計資料字典
        """
        async with get_db_session() as session:
            repository = CurrencyRepository(session)

            # 獲取原始統計資料
            basic_stats = await repository.get_guild_statistics(guild_id)

            # 獲取所有餘額用於進階統計計算
            leaderboard, _ = await repository.get_leaderboard(guild_id, limit=10000)
            balances = [float(wallet.balance) for wallet in leaderboard]

            if balances:
                # 使用 numpy 優化的統計計算
                enhanced_stats = self.statistics_service.calculate_guild_statistics(
                    balances
                )
                wealth_inequality = (
                    self.statistics_service.calculate_wealth_inequality_metrics(
                        balances
                    )
                )

                # 合併統計資料
                basic_stats.update(enhanced_stats)
                basic_stats["wealth_inequality"] = wealth_inequality

            return basic_stats

    async def add_balance(
        self,
        guild_id: int,
        user_id: int,
        amount: int,
        reason: str | None = None,
        admin_user_id: int | None = None,
    ) -> dict[str, Any]:
        """管理員增加或減少用戶餘額.

        Args:
            guild_id: Discord 伺服器 ID
            user_id: Discord 用戶 ID
            amount: 調整金額(可為正數或負數)
            reason: 調整原因
            admin_user_id: 管理員用戶 ID

        Returns:
            調整結果字典
        """
        async with get_db_session() as session:
            repository = CurrencyRepository(session)

            try:
                old_balance = await repository.get_balance(guild_id, user_id)

                metadata = {
                    "admin_user_id": admin_user_id,
                    "old_balance": old_balance,
                    "reason": reason,
                }

                wallet = await repository.add_balance(
                    guild_id, user_id, amount, reason, metadata
                )
                await repository.commit()

                # 發布餘額更新事件
                await self._publish_balance_update_event(
                    guild_id, user_id, amount, wallet.balance
                )

                self.logger.info(
                    f"餘額調整: user_id={user_id}, amount={amount}, "
                    f"old_balance={old_balance}, new_balance={wallet.balance}, "
                    f"admin={admin_user_id}, reason={reason}"
                )

                return {
                    "user_id": user_id,
                    "old_balance": old_balance,
                    "new_balance": wallet.balance,
                    "amount_changed": amount,
                    "reason": reason,
                    "admin_user_id": admin_user_id,
                    "timestamp": datetime.now(UTC).isoformat(),
                }

            except Exception as e:
                await repository.rollback()
                self.logger.error(f"餘額調整失敗: {e}")
                raise

    async def set_balance(
        self,
        guild_id: int,
        user_id: int,
        new_balance: int,
        reason: str | None = None,
        admin_user_id: int | None = None,
    ) -> dict[str, Any]:
        """管理員設定用戶餘額.

        Args:
            guild_id: Discord 伺服器 ID
            user_id: Discord 用戶 ID
            new_balance: 新的餘額金額
            reason: 調整原因
            admin_user_id: 管理員用戶 ID

        Returns:
            調整結果字典
        """
        if new_balance < 0:
            raise ValueError(f"餘額不能為負數: {new_balance}")

        if new_balance > 2**60:  # 防止溢出
            raise ValueError(f"餘額過大: {new_balance}")

        async with get_db_session() as session:
            repository = CurrencyRepository(session)

            try:
                old_balance = await repository.get_balance(guild_id, user_id)
                amount_changed = new_balance - old_balance

                metadata = {
                    "admin_user_id": admin_user_id,
                    "old_balance": old_balance,
                    "new_balance": new_balance,
                    "reason": reason,
                    "operation": "set_balance",
                }

                wallet = await repository.add_balance(
                    guild_id, user_id, amount_changed, reason, metadata
                )
                await repository.commit()

                # 發布餘額更新事件
                await self._publish_balance_update_event(
                    guild_id, user_id, amount_changed, wallet.balance
                )

                self.logger.info(
                    f"餘額設定: user_id={user_id}, old_balance={old_balance}, "
                    f"new_balance={wallet.balance}, admin={admin_user_id}, reason={reason}"
                )

                return {
                    "user_id": user_id,
                    "old_balance": old_balance,
                    "new_balance": wallet.balance,
                    "amount_changed": amount_changed,
                    "reason": reason,
                    "admin_user_id": admin_user_id,
                    "timestamp": datetime.now(UTC).isoformat(),
                }

            except Exception as e:
                await repository.rollback()
                self.logger.error(f"餘額設定失敗: {e}")
                raise

    async def _publish_transfer_event(
        self,
        transaction_id: str,
        guild_id: int,
        from_user_id: int,
        to_user_id: int,
        amount: int,
        from_balance_after: int,
        to_balance_after: int,
        reason: str | None = None,
    ) -> None:
        """發布轉帳事件.

        Args:
            transaction_id: 交易 ID
            guild_id: Discord 伺服器 ID
            from_user_id: 轉出用戶 ID
            to_user_id: 轉入用戶 ID
            amount: 轉帳金額
            from_balance_after: 轉出用戶轉帳後餘額
            to_balance_after: 轉入用戶轉帳後餘額
            reason: 轉帳原因
        """
        try:
            event = Event(
                event_type="currency.transfer",
                data={
                    "transaction_id": transaction_id,
                    "guild_id": guild_id,
                    "from_user_id": from_user_id,
                    "to_user_id": to_user_id,
                    "amount": amount,
                    "from_balance_after": from_balance_after,
                    "to_balance_after": to_balance_after,
                    "reason": reason,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
                source="currency_service",
                priority=EventPriority.HIGH,
            )

            event_bus = await get_global_event_bus()
            await event_bus.publish(event)

        except Exception as e:
            self.logger.warning(f"發布轉帳事件失敗: {e}")

    async def _publish_balance_update_event(
        self, guild_id: int, user_id: int, delta: int, balance_after: int
    ) -> None:
        """發布餘額更新事件.

        Args:
            guild_id: Discord 伺服器 ID
            user_id: Discord 用戶 ID
            delta: 餘額變化量
            balance_after: 更新後餘額
        """
        try:
            event = Event(
                event_type="currency.balance_update",
                data={
                    "guild_id": guild_id,
                    "user_id": user_id,
                    "delta": delta,
                    "balance_after": balance_after,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
                source="currency_service",
                priority=EventPriority.NORMAL,
            )

            event_bus = await get_global_event_bus()
            await event_bus.publish(event)

        except Exception as e:
            self.logger.warning(f"發布餘額更新事件失敗: {e}")


class _CurrencyServiceSingleton:
    _instance: CurrencyService | None = None

    @classmethod
    def get_instance(cls) -> CurrencyService:
        if cls._instance is None:
            cls._instance = CurrencyService()
        return cls._instance


def get_currency_service() -> CurrencyService:
    """取得貨幣服務實例(單例模式).

    Returns:
        貨幣服務實例
    """
    return _CurrencyServiceSingleton.get_instance()


__all__ = [
    "CurrencyService",
    "get_currency_service",
]
