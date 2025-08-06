"""
活躍度計算邏輯
- 提供活躍度計算、衰減和更新的核心邏輯
- 整合 numpy 向量化計算提升效能
"""

import logging

from src.core.performance import PerformanceOptimizationService

from ..config import config

logger = logging.getLogger("activity_meter")


class ActivityCalculator:
    """
    活躍度計算器類別

    功能:
    - 計算活躍度分數
    - 處理活躍度衰減
    - 提供活躍度更新邏輯
    - 整合 numpy 向量化計算
    """

    def __init__(self):
        """初始化計算器並設定效能優化服務。"""
        self.performance_service = PerformanceOptimizationService()
        logger.info("ActivityCalculator initialized with performance optimization")

    @staticmethod
    def decay(score: float, delta: int) -> float:
        """
        計算活躍度隨時間衰減

        Args:
            score: 當前活躍度分數
            delta: 時間差(秒)

        Returns:
            float: 衰減後的活躍度分數
        """
        if delta <= config.ACTIVITY_DECAY_AFTER:
            return score

        # 計算衰減量
        decay = (config.ACTIVITY_DECAY_PER_H / 3600) * (
            delta - config.ACTIVITY_DECAY_AFTER
        )

        return max(0, score - decay)

    @staticmethod
    def calculate_new_score(
        current_score: float, last_msg_time: int, now: int
    ) -> float:
        """
        計算新的活躍度分數

        Args:
            current_score: 當前活躍度分數
            last_msg_time: 上次訊息時間戳
            now: 當前時間戳

        Returns:
            float: 新的活躍度分數
        """
        # 先計算衰減
        decayed_score = ActivityCalculator.decay(current_score, now - last_msg_time)

        # 添加新訊息的活躍度增益
        new_score = decayed_score + config.ACTIVITY_GAIN

        # 確保不超過最大值
        return min(new_score, config.ACTIVITY_MAX_SCORE)

    @staticmethod
    def should_update(last_msg_time: int, now: int) -> bool:
        """
        判斷是否應該更新活躍度

        Args:
            last_msg_time: 上次訊息時間戳
            now: 當前時間戳

        Returns:
            bool: 是否應該更新活躍度
        """
        return now - last_msg_time >= config.ACTIVITY_COOLDOWN

    def calculate_level(self, activity_score: float) -> int:
        """
        根據活躍度分數計算等級

        Args:
            activity_score: 活躍度分數

        Returns:
            int: 用戶等級
        """
        # 簡單的等級計算邏輯
        return max(1, int(activity_score // 10) + 1)

    def bulk_decay(self, scores: list[float], time_deltas: list[int]) -> list[float]:
        """
        批量計算活躍度衰減 (使用 numpy 優化)

        Args:
            scores: 活躍度分數列表
            time_deltas: 時間差列表

        Returns:
            List[float]: 衰減後的分數列表
        """
        if not scores:
            return []

        try:
            # 使用 PerformanceOptimizationService 進行批量衰減計算
            decay_rates = []
            for delta in time_deltas:
                if delta <= config.ACTIVITY_DECAY_AFTER:
                    decay_rates.append(0.0)
                else:
                    decay_rate = (config.ACTIVITY_DECAY_PER_H / 3600) * (
                        delta - config.ACTIVITY_DECAY_AFTER
                    )
                    decay_rates.append(decay_rate)

            # 計算衰減後的分數
            result_scores = []
            for s, d in zip(scores, decay_rates, strict=False):
                result_scores.append(max(0.0, s - d))

            return result_scores

        except Exception as e:
            logger.warning(f"Bulk decay calculation failed, using fallback: {e}")
            return [
                self.decay(score, delta)
                for score, delta in zip(scores, time_deltas, strict=False)
            ]

    def bulk_calculate_new_scores(
        self,
        current_scores: list[float],
        last_msg_times: list[int],
        now_times: list[int],
    ) -> list[float]:
        """
        批量計算新的活躍度分數 (使用 numpy 優化)

        Args:
            current_scores: 當前分數列表
            last_msg_times: 上次訊息時間列表
            now_times: 當前時間列表

        Returns:
            List[float]: 新的分數列表
        """
        if not current_scores:
            return []

        try:
            # 計算時間差
            time_deltas = [
                now - last for now, last in zip(now_times, last_msg_times, strict=False)
            ]

            # 批量衰減計算
            decayed_scores = self.bulk_decay(current_scores, time_deltas)

            # 添加增益到每個分數（每個用戶單獨獲得增益）
            gained_scores = [score + config.ACTIVITY_GAIN for score in decayed_scores]

            # 批量限制最大值
            max_values = [config.ACTIVITY_MAX_SCORE] * len(gained_scores)
            return [
                min(score, max_val)
                for score, max_val in zip(gained_scores, max_values, strict=False)
            ]

        except Exception as e:
            logger.warning(f"Bulk score calculation failed, using fallback: {e}")
            return [
                self.calculate_new_score(score, last_time, now_time)
                for score, last_time, now_time in zip(
                    current_scores, last_msg_times, now_times, strict=False
                )
            ]

    def bulk_should_update(
        self, last_msg_times: list[int], now_times: list[int]
    ) -> list[bool]:
        """
        批量判斷是否應該更新活躍度 (使用 numpy 優化)

        Args:
            last_msg_times: 上次訊息時間列表
            now_times: 當前時間列表

        Returns:
            List[bool]: 是否需要更新的列表
        """
        if not last_msg_times:
            return []

        try:
            # 計算時間差
            time_deltas = [
                now - last for now, last in zip(now_times, last_msg_times, strict=False)
            ]

            # 批量比較是否達到冷卻時間
            return [delta >= config.ACTIVITY_COOLDOWN for delta in time_deltas]

        except Exception as e:
            logger.warning(
                f"Bulk should_update calculation failed, using fallback: {e}"
            )
            return [
                self.should_update(last_time, now_time)
                for last_time, now_time in zip(last_msg_times, now_times, strict=False)
            ]
