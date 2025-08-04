"""
活躍度批量計算服務
- 處理大規模背景計算任務
- 整合 NumPy 優化計算器
"""

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from ..config import config
from ..constants import PERFORMANCE_CHECK_INTERVAL
from ..database.database import ActivityDatabase
from ..main.calculator import ActivityCalculator
from ..main.numpy_calculator import OptimizedActivityCalculator

logger = logging.getLogger("activity_meter")

class BatchCalculationService:
    """
    批量計算服務

    功能:
    - 批量活躍度衰減計算
    - 批量分數更新
    - 非同步背景處理
    - 自動性能優化
    """

    def __init__(self, db: ActivityDatabase, max_workers: int = 4):
        """
        初始化批量計算服務

        Args:
            db: 資料庫實例
            max_workers: 最大工作執行緒數
        """
        self.db = db
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

        # 初始化計算器
        self.standard_calculator = ActivityCalculator()
        self.optimized_calculator = OptimizedActivityCalculator(
            fallback_calculator=self.standard_calculator
        )

        # 性能統計
        self.stats = {
            "total_calculations": 0,
            "numpy_calculations": 0,
            "fallback_calculations": 0,
            "average_improvement": 0.0,
            "last_performance_check": 0
        }

        logger.info("批量計算服務已初始化")

    async def bulk_decay_all_users(self, guild_id: int) -> dict[str, Any]:
        """
        批量計算所有用戶的活躍度衰減

        Args:
            guild_id: 伺服器 ID

        Returns:
            Dict[str, Any]: 計算結果統計
        """
        try:
            # 獲取所有用戶活躍度資料
            users_data = await self.db.get_all_user_activities(guild_id)

            if not users_data:
                return {"updated_count": 0, "calculation_time": 0}

            # 準備批量計算資料
            user_ids = []
            scores = []
            last_msg_times = []
            now = int(time.time())

            for user_data in users_data:
                user_ids.append(user_data["user_id"])
                scores.append(user_data["score"])
                last_msg_times.append(user_data["last_msg_time"])

            # 計算時間差
            deltas = [now - last_time for last_time in last_msg_times]

            start_time = time.perf_counter()

            loop = asyncio.get_event_loop()
            new_scores = await loop.run_in_executor(
                self.executor,
                self._calculate_bulk_decay,
                scores,
                deltas
            )

            calculation_time = time.perf_counter() - start_time

            # 批量更新資料庫
            updates = [
                (guild_id, user_id, new_score, now)
                for i, (user_id, new_score) in enumerate(zip(user_ids, new_scores, strict=False))
                if new_score != scores[i]  # 只更新有變化的記錄
            ]

            if updates:
                await self.db.bulk_update_user_activities(updates)

            # 更新統計
            self.stats["total_calculations"] += len(scores)

            logger.info(
                f"批量衰減計算完成: {len(updates)} 筆更新, "
                f"計算時間: {calculation_time:.4f}秒"
            )

            return {
                "updated_count": len(updates),
                "total_processed": len(scores),
                "calculation_time": calculation_time,
                "using_numpy": self.optimized_calculator.use_numpy
            }

        except Exception as e:
            logger.error(f"批量衰減計算失敗: {e}")
            raise

    async def bulk_update_rankings(self, guild_id: int, date_str: str) -> dict[str, Any]:
        """
        批量更新排行榜計算

        Args:
            guild_id: 伺服器 ID
            date_str: 日期字串

        Returns:
            Dict[str, Any]: 更新結果
        """
        try:
            # 獲取當日活躍用戶資料
            daily_data = await self.db.get_daily_message_counts(guild_id, date_str)

            if not daily_data:
                return {"processed_count": 0}

            # 準備計算資料
            user_ids = []
            current_scores = []
            msg_counts = []

            now = int(time.time())

            for data in daily_data:
                user_id = data["user_id"]
                msg_count = data["msg_count"]

                # 獲取當前活躍度
                score, last_msg_time = await self.db.get_user_activity(guild_id, user_id)

                user_ids.append(user_id)
                current_scores.append(score)
                msg_counts.append(msg_count)

            # 執行批量計算
            start_time = time.perf_counter()

            loop = asyncio.get_event_loop()
            updated_scores = await loop.run_in_executor(
                self.executor,
                self._calculate_bulk_ranking_scores,
                current_scores,
                msg_counts,
                now
            )

            calculation_time = time.perf_counter() - start_time

            # 批量更新活躍度
            updates = [
                (guild_id, user_id, new_score, now)
                for user_id, new_score in zip(user_ids, updated_scores, strict=False)
            ]

            if updates:
                await self.db.bulk_update_user_activities(updates)

            logger.info(
                f"批量排行榜更新完成: {len(updates)} 筆記錄, "
                f"計算時間: {calculation_time:.4f}秒"
            )

            return {
                "processed_count": len(updates),
                "calculation_time": calculation_time,
                "using_numpy": self.optimized_calculator.use_numpy
            }

        except Exception as e:
            logger.error(f"批量排行榜更新失敗: {e}")
            raise

    async def optimize_background_calculations(self) -> None:
        """
        優化背景計算任務
        定期執行性能檢查和調整
        """
        try:
            current_time = time.time()

            # 每小時檢查一次性能
            if current_time - self.stats["last_performance_check"] > PERFORMANCE_CHECK_INTERVAL:
                logger.info("執行 NumPy 性能檢查...")

                loop = asyncio.get_event_loop()
                performance_good = await loop.run_in_executor(
                    self.executor,
                    self.optimized_calculator.check_numpy_performance,
                    5000  # 測試 5000 筆資料
                )

                if not performance_good and self.optimized_calculator.use_numpy:
                    logger.warning("NumPy 性能不佳, 切換至回退機制")
                    self.optimized_calculator.use_numpy = False
                elif performance_good and not self.optimized_calculator.use_numpy:
                    logger.info("NumPy 性能良好, 啟用優化計算")
                    self.optimized_calculator.use_numpy = True

                self.stats["last_performance_check"] = current_time

        except Exception as e:
            logger.error(f"背景計算優化失敗: {e}")

    def _calculate_bulk_decay(
        self,
        scores: list[float],
        deltas: list[int]
    ) -> list[float]:
        """
        執行批量衰減計算(在執行緒池中執行)

        Args:
            scores: 分數列表
            deltas: 時間差列表

        Returns:
            List[float]: 衰減後的分數
        """
        try:
            if self.optimized_calculator.use_numpy:
                result = self.optimized_calculator.bulk_decay_calculation(scores, deltas)
                self.stats["numpy_calculations"] += len(scores)

                # 轉換 NumPy 陣列為列表
                if hasattr(result, 'tolist'):
                    return result.tolist()
                return list(result)
            else:
                result = self.optimized_calculator._fallback_bulk_decay(scores, deltas)
                self.stats["fallback_calculations"] += len(scores)
                return result

        except Exception as e:
            logger.warning(f"批量衰減計算異常, 使用回退方法: {e}")
            result = self.optimized_calculator._fallback_bulk_decay(scores, deltas)
            self.stats["fallback_calculations"] += len(scores)
            return result

    def _calculate_bulk_ranking_scores(
        self,
        current_scores: list[float],
        msg_counts: list[int],
        _now: int
    ) -> list[float]:
        """
        計算排行榜分數(考慮訊息數量加成)

        Args:
            current_scores: 當前分數
            msg_counts: 訊息數量
            now: 當前時間

        Returns:
            List[float]: 更新後的分數
        """
        # 簡化的排行榜分數計算
        # 基於訊息數量給予額外加分
        updated_scores = []

        for score, msg_count in zip(current_scores, msg_counts, strict=False):
            # 每條訊息給予基本分數增益
            bonus = min(msg_count * config.ACTIVITY_GAIN, config.ACTIVITY_MAX_SCORE)
            new_score = min(score + bonus, config.ACTIVITY_MAX_SCORE)
            updated_scores.append(new_score)

        return updated_scores

    def get_performance_stats(self) -> dict[str, Any]:
        """
        獲取性能統計資訊

        Returns:
            Dict[str, Any]: 性能統計
        """
        total = self.stats["total_calculations"]
        numpy_ratio = (
            self.stats["numpy_calculations"] / total
            if total > 0 else 0
        )

        return {
            **self.stats,
            "numpy_usage_ratio": numpy_ratio,
            "calculator_status": self.optimized_calculator.get_status()
        }

    async def shutdown(self) -> None:
        """關閉批量計算服務"""
        try:
            self.executor.shutdown(wait=True)
            logger.info("批量計算服務已關閉")
        except Exception as e:
            logger.error(f"關閉批量計算服務時發生錯誤: {e}")
