"""Currency Repository for Discord ROAS Bot v2.0.

此模組提供貨幣系統的 Repository 實作, 支援:
- 錢包建立和管理
- 原子性轉帳交易
- 排行榜查詢與分頁
- 交易記錄追蹤
- 樂觀鎖並發控制
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence
from sqlalchemy import desc, func, select, text

from src.core.database.models import CurrencyBalance
from src.core.database.postgresql import BaseRepository

logger = logging.getLogger(__name__)

class CurrencyTransferError(Exception):
    """轉帳錯誤基礎類別."""

    pass

class InsufficientFundsError(CurrencyTransferError):
    """餘額不足錯誤."""

    pass

class ConcurrencyError(CurrencyTransferError):
    """並發衝突錯誤."""

    pass

class CurrencyRepository(BaseRepository):
    """貨幣 Repository 擴展實作.

    提供完整的貨幣系統操作, 包括原子性轉帳、餘額管理和排行榜查詢.
    """

    async def get_or_create_wallet(
        self, guild_id: int, user_id: int, initial_balance: int = 0
    ) -> CurrencyBalance:
        """取得或建立用戶錢包.

        如果錢包不存在則自動建立初始餘額為 0 的錢包.

        Args:
            guild_id: Discord 伺服器 ID
            user_id: Discord 用戶 ID
            initial_balance: 初始餘額, 預設為 0

        Returns:
            用戶錢包記錄

        Raises:
            Exception: 當資料庫操作失敗時
        """
        try:
            # 嘗試取得現有錢包
            result = await self.session.execute(
                select(CurrencyBalance).where(
                    CurrencyBalance.guild_id == guild_id,
                    CurrencyBalance.user_id == user_id,
                )
            )
            wallet = result.scalar_one_or_none()

            if wallet:
                return wallet

            # 建立新錢包
            wallet = CurrencyBalance(
                guild_id=guild_id,
                user_id=user_id,
                balance=initial_balance,
                transaction_count=0,
                extra_data={},
            )

            self.session.add(wallet)
            await self.flush()
            await self.refresh(wallet)

            logger.info(
                f"建立新錢包: guild_id={guild_id}, user_id={user_id}, balance={initial_balance}"
            )
            return wallet

        except Exception as e:
            await self.rollback()
            logger.error(
                f"建立或取得錢包失敗: guild_id={guild_id}, user_id={user_id}, error={e}"
            )
            raise

    async def get_balance(self, guild_id: int, user_id: int) -> int:
        """取得用戶餘額.

        如果錢包不存在則自動建立並返回 0.

        Args:
            guild_id: Discord 伺服器 ID
            user_id: Discord 用戶 ID

        Returns:
            用戶目前餘額
        """
        wallet = await self.get_or_create_wallet(guild_id, user_id)
        return wallet.balance

    async def transfer(
        self,
        guild_id: int,
        from_user_id: int,
        to_user_id: int,
        amount: int,
        transaction_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[CurrencyBalance, CurrencyBalance]:
        """執行原子性轉帳交易.

        使用資料庫鎖定確保轉帳的原子性和一致性.

        Args:
            guild_id: Discord 伺服器 ID
            from_user_id: 轉出用戶 ID
            to_user_id: 轉入用戶 ID
            amount: 轉帳金額(必須為正數)
            transaction_id: 交易 ID, 用於防重放攻擊
            metadata: 額外的交易資料

        Returns:
            (轉出錢包, 轉入錢包) 元組

        Raises:
            ValueError: 當金額無效時
            InsufficientFundsError: 當餘額不足時
            ConcurrencyError: 當並發衝突時
            Exception: 當其他資料庫錯誤時
        """
        if amount <= 0:
            raise ValueError(f"轉帳金額必須為正數: {amount}")

        if from_user_id == to_user_id:
            raise ValueError("不能轉帳給自己")

        # 生成交易 ID
        if transaction_id is None:
            transaction_id = str(uuid.uuid4())

        try:
            # 使用 SELECT FOR UPDATE 鎖定錢包記錄以防並發
            # 按照用戶 ID 順序鎖定以避免死鎖
            user_ids = sorted([from_user_id, to_user_id])

            # 鎖定錢包記錄
            result = await self.session.execute(
                select(CurrencyBalance)
                .where(
                    CurrencyBalance.guild_id == guild_id,
                    CurrencyBalance.user_id.in_(user_ids),
                )
                .order_by(CurrencyBalance.user_id)
                .with_for_update()
            )
            existing_wallets = {
                wallet.user_id: wallet for wallet in result.scalars().all()
            }

            # 確保兩個錢包都存在
            from_wallet = existing_wallets.get(from_user_id)
            to_wallet = existing_wallets.get(to_user_id)

            if not from_wallet:
                from_wallet = await self.get_or_create_wallet(guild_id, from_user_id)
                # 重新鎖定
                await self.session.execute(
                    select(CurrencyBalance)
                    .where(
                        CurrencyBalance.guild_id == guild_id,
                        CurrencyBalance.user_id == from_user_id,
                    )
                    .with_for_update()
                )

            if not to_wallet:
                to_wallet = await self.get_or_create_wallet(guild_id, to_user_id)
                # 重新鎖定
                await self.session.execute(
                    select(CurrencyBalance)
                    .where(
                        CurrencyBalance.guild_id == guild_id,
                        CurrencyBalance.user_id == to_user_id,
                    )
                    .with_for_update()
                )

            # 檢查餘額是否充足
            if from_wallet.balance < amount:
                raise InsufficientFundsError(
                    f"餘額不足: 需要 {amount}, 目前餘額 {from_wallet.balance}"
                )

            # 執行轉帳
            from_wallet.balance -= amount
            from_wallet.transaction_count += 1
            from_wallet.last_transaction_at = datetime.utcnow()

            to_wallet.balance += amount
            to_wallet.transaction_count += 1
            to_wallet.last_transaction_at = datetime.utcnow()

            # 更新交易元資料
            if metadata:
                transaction_data = {
                    "transaction_id": transaction_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    **metadata,
                }

                from_wallet.extra_data.setdefault("recent_transactions", [])
                from_wallet.extra_data["recent_transactions"].append(
                    {
                        **transaction_data,
                        "type": "transfer_out",
                        "amount": -amount,
                        "to_user_id": to_user_id,
                    }
                )
                # 保留最近 10 筆交易
                from_wallet.extra_data["recent_transactions"] = from_wallet.extra_data[
                    "recent_transactions"
                ][-10:]

                to_wallet.extra_data.setdefault("recent_transactions", [])
                to_wallet.extra_data["recent_transactions"].append(
                    {
                        **transaction_data,
                        "type": "transfer_in",
                        "amount": amount,
                        "from_user_id": from_user_id,
                    }
                )
                to_wallet.extra_data["recent_transactions"] = to_wallet.extra_data[
                    "recent_transactions"
                ][-10:]

            await self.flush()
            await self.refresh(from_wallet)
            await self.refresh(to_wallet)

            logger.info(
                f"轉帳成功: {from_user_id} -> {to_user_id}, "
                f"amount={amount}, tx_id={transaction_id}"
            )

            return from_wallet, to_wallet

        except (InsufficientFundsError, ValueError):
            await self.rollback()
            raise
        except Exception as e:
            await self.rollback()
            logger.error(f"轉帳失敗: {e}")
            if "deadlock" in str(e).lower() or "lock" in str(e).lower():
                raise ConcurrencyError(f"並發衝突, 請重試: {e}") from e
            raise

    async def get_leaderboard(
        self, guild_id: int, limit: int = 10, offset: int = 0
    ) -> tuple[Sequence[CurrencyBalance], int]:
        """取得伺服器餘額排行榜.

        Args:
            guild_id: Discord 伺服器 ID
            limit: 限制數量
            offset: 偏移量

        Returns:
            (排行榜記錄列表, 總記錄數) 元組
        """
        try:
            # 取得排行榜記錄
            leaderboard_result = await self.session.execute(
                select(CurrencyBalance)
                .where(CurrencyBalance.guild_id == guild_id)
                .order_by(desc(CurrencyBalance.balance), CurrencyBalance.user_id)
                .limit(limit)
                .offset(offset)
            )
            leaderboard = leaderboard_result.scalars().all()

            # 取得總記錄數
            count_result = await self.session.execute(
                select(func.count(CurrencyBalance.id)).where(
                    CurrencyBalance.guild_id == guild_id
                )
            )
            total_count = count_result.scalar() or 0

            return leaderboard, total_count

        except Exception as e:
            logger.error(f"取得排行榜失敗: guild_id={guild_id}, error={e}")
            raise

    async def get_user_rank(self, guild_id: int, user_id: int) -> tuple[int, int]:
        """取得用戶在排行榜中的排名.

        Args:
            guild_id: Discord 伺服器 ID
            user_id: Discord 用戶 ID

        Returns:
            (排名, 總人數) 元組, 排名從 1 開始
        """
        try:
            # 取得用戶餘額
            user_wallet = await self.get_or_create_wallet(guild_id, user_id)
            user_balance = user_wallet.balance

            rank_result = await self.session.execute(
                select(func.count(CurrencyBalance.id)).where(
                    CurrencyBalance.guild_id == guild_id,
                    CurrencyBalance.balance > user_balance,
                )
            )
            rank = (rank_result.scalar() or 0) + 1

            # 取得總人數
            total_result = await self.session.execute(
                select(func.count(CurrencyBalance.id)).where(
                    CurrencyBalance.guild_id == guild_id
                )
            )
            total = total_result.scalar() or 0

            return rank, total

        except Exception as e:
            logger.error(
                f"取得用戶排名失敗: guild_id={guild_id}, user_id={user_id}, error={e}"
            )
            raise

    async def add_balance(
        self,
        guild_id: int,
        user_id: int,
        amount: int,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CurrencyBalance:
        """增加用戶餘額.

        用於系統獎勵、管理員操作等場景.

        Args:
            guild_id: Discord 伺服器 ID
            user_id: Discord 用戶 ID
            amount: 增加金額(可為負數)
            reason: 操作原因
            metadata: 額外資料

        Returns:
            更新後的錢包記錄
        """
        try:
            wallet = await self.get_or_create_wallet(guild_id, user_id)

            old_balance = wallet.balance
            wallet.balance += amount
            wallet.transaction_count += 1
            wallet.last_transaction_at = datetime.utcnow()

            # 記錄操作歷史
            operation_data = {
                "type": "admin_adjustment" if amount != 0 else "system_reward",
                "amount": amount,
                "old_balance": old_balance,
                "new_balance": wallet.balance,
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat(),
                **(metadata or {}),
            }

            wallet.extra_data.setdefault("operations", [])
            wallet.extra_data["operations"].append(operation_data)
            wallet.extra_data["operations"] = wallet.extra_data["operations"][
                -20:
            ]  # 保留最近 20 筆

            await self.flush()
            await self.refresh(wallet)

            logger.info(
                f"餘額調整: user_id={user_id}, amount={amount}, "
                f"old_balance={old_balance}, new_balance={wallet.balance}, reason={reason}"
            )

            return wallet

        except Exception as e:
            await self.rollback()
            logger.error(f"餘額調整失敗: {e}")
            raise

    async def get_guild_statistics(self, guild_id: int) -> dict[str, Any]:
        """取得伺服器經濟統計.

        Args:
            guild_id: Discord 伺服器 ID

        Returns:
            統計資料字典
        """
        try:
            # 基本統計
            stats_result = await self.session.execute(
                select(
                    func.count(CurrencyBalance.id).label("total_users"),
                    func.sum(CurrencyBalance.balance).label("total_currency"),
                    func.avg(CurrencyBalance.balance).label("average_balance"),
                    func.max(CurrencyBalance.balance).label("max_balance"),
                    func.min(CurrencyBalance.balance).label("min_balance"),
                ).where(CurrencyBalance.guild_id == guild_id)
            )
            stats = stats_result.first()

            # 交易統計
            transaction_result = await self.session.execute(
                select(func.sum(CurrencyBalance.transaction_count)).where(
                    CurrencyBalance.guild_id == guild_id
                )
            )
            total_transactions = transaction_result.scalar() or 0

            return {
                "total_users": stats.total_users or 0,
                "total_currency": stats.total_currency or 0,
                "average_balance": float(stats.average_balance or 0),
                "max_balance": stats.max_balance or 0,
                "min_balance": stats.min_balance or 0,
                "total_transactions": total_transactions,
                "guild_id": guild_id,
                "last_updated": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"取得統計資料失敗: guild_id={guild_id}, error={e}")
            raise

    async def check_transaction_exists(self, transaction_id: str) -> bool:
        """檢查交易 ID 是否已存在(防重放攻擊).

        Args:
            transaction_id: 交易 ID

        Returns:
            是否已存在
        """
        try:
            # 在 extra_data 中搜尋交易 ID
            result = await self.session.execute(
                text("""
                    SELECT EXISTS(
                        SELECT 1 FROM currency_balance
                        WHERE extra_data::text LIKE :transaction_pattern
                    )
                """),
                {"transaction_pattern": f"%{transaction_id}%"},
            )
            return result.scalar() or False

        except Exception as e:
            logger.error(
                f"檢查交易 ID 失敗: transaction_id={transaction_id}, error={e}"
            )
            return False

__all__ = [
    "ConcurrencyError",
    "CurrencyRepository",
    "CurrencyTransferError",
    "InsufficientFundsError",
]
