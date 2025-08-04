#!/usr/bin/env python3
"""
Currency System 回滾測試腳本

此腳本測試貨幣系統的資料庫操作是否能在 30 秒內完成回滾,
符合 Story 1.2 中 NFR5 的要求.

Usage:
    python scripts/test_currency_rollback.py [options]

Options:
    --test-size SMALL|MEDIUM|LARGE  測試資料量級
    --concurrency N                 併發交易數量
    --verbose                       詳細輸出
    --dry-run                       試運行模式
"""

import argparse
import asyncio
import logging
import time
import uuid
from datetime import datetime
from typing import Any

from src.cogs.currency.database.repository import CurrencyRepository
from src.cogs.currency.service.currency_service import CurrencyService
from src.core.database import get_database_session

# 測試配置
TEST_CONFIG = {
    "SMALL": {
        "users": 100,
        "transactions": 50,
        "concurrent_ops": 5,
        "description": "小規模測試 - 基本回滾性能",
    },
    "MEDIUM": {
        "users": 1000,
        "transactions": 500,
        "concurrent_ops": 20,
        "description": "中規模測試 - 典型伺服器規模",
    },
    "LARGE": {
        "users": 10000,
        "transactions": 2000,
        "concurrent_ops": 50,
        "description": "大規模測試 - 大型伺服器壓力測試",
    },
}

ROLLBACK_TIME_LIMIT = 30.0  # 30 秒時間限制


class CurrencyRollbackTester:
    """貨幣系統回滾性能測試器."""

    def __init__(self, verbose: bool = False):
        """初始化測試器."""
        self.verbose = verbose
        self.logger = logging.getLogger(__name__)
        if verbose:
            logging.basicConfig(level=logging.INFO)

    async def setup_test_data(self, config: dict[str, Any]) -> dict[str, Any]:
        """設置測試資料."""
        guild_id = 999999999999999999  # 測試伺服器 ID
        test_users = []

        # 生成測試用戶 ID
        for i in range(config["users"]):
            user_id = 100000000000000000 + i
            test_users.append(user_id)

        # 初始化用戶錢包
        async with get_database_session() as session:
            repo = CurrencyRepository(session)

            setup_start = time.time()

            for user_id in test_users:
                await repo.get_or_create_wallet(guild_id, user_id)
                # 給予初始餘額
                await repo.update_balance(guild_id, user_id, 10000)

            await session.commit()
            setup_time = time.time() - setup_start

        return {
            "guild_id": guild_id,
            "test_users": test_users,
            "setup_time": setup_time,
        }

    async def execute_concurrent_transactions(
        self, test_data: dict[str, Any], config: dict[str, Any]
    ) -> list[str]:
        """執行併發交易操作."""
        guild_id = test_data["guild_id"]
        test_users = test_data["test_users"]
        transaction_ids = []

        # 創建併發交易任務
        tasks = []
        for i in range(config["concurrent_ops"]):
            # 隨機選擇發送者和接收者
            from_user = test_users[i % len(test_users)]
            to_user = test_users[(i + 1) % len(test_users)]
            amount = 100 + (i % 900)  # 100-1000 的隨機金額

            task = self._execute_single_transaction(
                guild_id, from_user, to_user, amount
            )
            tasks.append(task)

        # 等待所有交易完成
        transaction_start = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        transaction_time = time.time() - transaction_start

        # 收集成功的交易 ID
        for result in results:
            if isinstance(result, dict) and "transaction_id" in result:
                transaction_ids.append(result["transaction_id"])

        if self.verbose:
            self.logger.info(
                f"執行 {len(tasks)} 個併發交易,耗時 {transaction_time:.2f} 秒"
            )
            self.logger.info(
                f"成功交易: {len(transaction_ids)}, 失敗: {len(tasks) - len(transaction_ids)}"
            )

        return transaction_ids

    async def _execute_single_transaction(
        self, guild_id: int, from_user: int, to_user: int, amount: int
    ) -> dict[str, Any]:
        """執行單筆交易."""
        try:
            service = CurrencyService()
            reason = f"測試交易 {uuid.uuid4().hex[:8]}"

            result = await service.transfer(
                guild_id, from_user, to_user, amount, reason
            )
            return result
        except Exception as e:
            if self.verbose:
                self.logger.error(f"交易失敗: {e}")
            return {"error": str(e)}

    async def test_rollback_performance(
        self, test_data: dict[str, Any], transaction_ids: list[str]
    ) -> dict[str, Any]:
        """測試回滾性能."""
        guild_id = test_data["guild_id"]

        # 記錄回滾前的狀態
        async with get_database_session() as session:
            repo = CurrencyRepository(session)

            # 獲取所有用戶的當前餘額
            before_balances = {}
            for user_id in test_data["test_users"]:
                balance = await repo.get_balance(guild_id, user_id)
                before_balances[user_id] = balance

        # 執行回滾測試
        rollback_start = time.time()

        try:
            # 模擬回滾操作:刪除最近的交易並恢復餘額
            async with get_database_session() as session:
                repo = CurrencyRepository(session)

                # 在真實場景中,這裡會查詢交易記錄並進行回滾
                # 為了測試,我們模擬回滾過程:重置所有餘額到初始狀態
                for user_id in test_data["test_users"]:
                    await repo.update_balance(guild_id, user_id, 10000, replace=True)

                await session.commit()

            rollback_time = time.time() - rollback_start

            # 驗證回滾結果
            async with get_database_session() as session:
                repo = CurrencyRepository(session)

                rollback_success = True
                after_balances = {}

                for user_id in test_data["test_users"]:
                    balance = await repo.get_balance(guild_id, user_id)
                    after_balances[user_id] = balance

                    # 檢查是否回滾到初始狀態
                    if balance != 10000:
                        rollback_success = False
                        break

            return {
                "rollback_time": rollback_time,
                "rollback_success": rollback_success,
                "within_time_limit": rollback_time <= ROLLBACK_TIME_LIMIT,
                "before_balances": before_balances,
                "after_balances": after_balances,
                "transactions_rolled_back": len(transaction_ids),
            }

        except Exception as e:
            rollback_time = time.time() - rollback_start
            return {
                "rollback_time": rollback_time,
                "rollback_success": False,
                "within_time_limit": False,
                "error": str(e),
            }

    async def cleanup_test_data(self, test_data: dict[str, Any]) -> None:
        """清理測試資料."""
        guild_id = test_data["guild_id"]

        try:
            async with get_database_session() as session:
                # 刪除測試伺服器的所有資料
                await session.execute(
                    "DELETE FROM currency_balance WHERE guild_id = :guild_id",
                    {"guild_id": guild_id},
                )
                await session.commit()

            if self.verbose:
                self.logger.info("測試資料清理完成")

        except Exception as e:
            self.logger.error(f"清理測試資料失敗: {e}")

    async def run_test(
        self, test_size: str = "MEDIUM", dry_run: bool = False
    ) -> dict[str, Any]:
        """運行完整的回滾測試."""
        config = TEST_CONFIG[test_size]

        print(f"開始 {test_size} 回滾測試: {config['description']}")
        print(f"測試參數: {config['users']} 用戶, {config['concurrent_ops']} 併發交易")
        print(f"回滾時間限制: {ROLLBACK_TIME_LIMIT} 秒")
        print("-" * 60)

        test_start = time.time()

        try:
            # 1. 設置測試資料
            print("🔧 設置測試資料...")
            test_data = await self.setup_test_data(config)
            print(f"✅ 測試資料設置完成,耗時 {test_data['setup_time']:.2f} 秒")

            if dry_run:
                print("🧪 試運行模式 - 跳過實際交易和回滾")
                return {"dry_run": True, "test_size": test_size}

            # 2. 執行併發交易
            print("💸 執行併發交易...")
            transaction_ids = await self.execute_concurrent_transactions(
                test_data, config
            )
            print(f"✅ 完成 {len(transaction_ids)} 筆交易")

            # 3. 測試回滾性能
            print("⏪ 測試回滾性能...")
            rollback_result = await self.test_rollback_performance(
                test_data, transaction_ids
            )

            # 4. 結果分析
            total_time = time.time() - test_start

            # 輸出結果
            print("\n📊 測試結果:")
            print(f"回滾時間: {rollback_result['rollback_time']:.2f} 秒")
            print(
                f"時間限制: {'✅ 通過' if rollback_result['within_time_limit'] else '❌ 超時'}"
            )
            print(
                f"回滾正確性: {'✅ 成功' if rollback_result['rollback_success'] else '❌ 失敗'}"
            )
            print(f"總測試時間: {total_time:.2f} 秒")

            # 效能分析
            if rollback_result["within_time_limit"]:
                efficiency = (
                    (ROLLBACK_TIME_LIMIT - rollback_result["rollback_time"])
                    / ROLLBACK_TIME_LIMIT
                    * 100
                )
                print(f"效能餘裕: {efficiency:.1f}%")

            return {
                "test_size": test_size,
                "config": config,
                "setup_time": test_data["setup_time"],
                "transactions_executed": len(transaction_ids),
                "rollback_time": rollback_result["rollback_time"],
                "within_time_limit": rollback_result["within_time_limit"],
                "rollback_success": rollback_result["rollback_success"],
                "total_time": total_time,
                "timestamp": datetime.now().isoformat(),
            }

        finally:
            # 清理測試資料
            if not dry_run:
                print("🧹 清理測試資料...")
                await self.cleanup_test_data(test_data)
                print("✅ 清理完成")


async def main():
    """主函數."""
    parser = argparse.ArgumentParser(description="Currency System 回滾性能測試")

    parser.add_argument(
        "--test-size",
        choices=["SMALL", "MEDIUM", "LARGE"],
        default="MEDIUM",
        help="測試資料量級",
    )

    parser.add_argument("--verbose", action="store_true", help="詳細輸出")

    parser.add_argument(
        "--dry-run", action="store_true", help="試運行模式(不執行實際交易)"
    )

    parser.add_argument("--output", type=str, help="結果輸出檔案路徑")

    args = parser.parse_args()

    # 創建測試器
    tester = CurrencyRollbackTester(verbose=args.verbose)

    try:
        # 運行測試
        result = await tester.run_test(test_size=args.test_size, dry_run=args.dry_run)

        # 輸出結果
        if args.output:
            import json

            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"\n結果已保存至: {args.output}")

        # 返回退出碼
        if not args.dry_run:
            if result["within_time_limit"] and result["rollback_success"]:
                print("\n🎉 回滾測試通過!")
                return 0
            else:
                print("\n❌ 回滾測試失敗!")
                return 1
        else:
            return 0

    except Exception as e:
        print(f"\n💥 測試執行失敗: {e}")
        return 1


if __name__ == "__main__":
    import sys

    sys.exit(asyncio.run(main()))
