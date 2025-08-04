"""
NumPy 優化的活躍度計算器
- 使用向量化運算提升計算性能
- 支援批量處理和回退機制
"""

import logging
import random
import time
from typing import Union

from ..config import config

logger = logging.getLogger("activity_meter")

# NumPy 依賴檢查
try:
    import numpy as np
    NUMPY_AVAILABLE = True
    logger.info("NumPy 已載入, 版本: %s", np.__version__)
except ImportError:
    NUMPY_AVAILABLE = False
    logger.warning("NumPy 不可用, 將使用標準計算方法")

class OptimizedActivityCalculator:
    """
    NumPy 優化的活躍度計算器

    功能:
    - 向量化的活躍度衰減計算
    - 批量分數更新
    - 自動回退機制
    - 性能監控
    """

    def __init__(self, fallback_calculator=None):
        """
        初始化優化計算器

        Args:
            fallback_calculator: 回退計算器實例
        """
        self.numpy_available = NUMPY_AVAILABLE
        self.fallback_calculator = fallback_calculator
        self.performance_threshold = 1.5  # 最小性能改善倍數
        self.use_numpy = self.numpy_available

        if not self.numpy_available:
            logger.warning("NumPy 不可用, 所有計算將使用回退機制")

    def bulk_decay_calculation(
        self,
        scores: Union[list[float], 'np.ndarray'],
        deltas: Union[list[int], 'np.ndarray']
    ) -> Union[list[float], 'np.ndarray']:
        """
        批量計算活躍度衰減

        Args:
            scores: 活躍度分數陣列
            deltas: 時間差陣列 (秒)

        Returns:
            Union[List[float], np.ndarray]: 衰減後的分數陣列
        """
        if not self.use_numpy or not self.numpy_available:
            return self._fallback_bulk_decay(scores, deltas)

        try:
            # 直接轉換為 NumPy 陣列, 使用最佳資料型別
            scores_arr = np.asarray(scores, dtype=np.float32)
            deltas_arr = np.asarray(deltas, dtype=np.int32)


            decay_threshold = np.int32(config.ACTIVITY_DECAY_AFTER)
            decay_rate = np.float32(config.ACTIVITY_DECAY_PER_H / 3600.0)

            # 一步完成整個計算: 對於 delta > threshold 的項目進行衰減
            # 使用條件選擇避免分支
            decay_amount = np.where(
                deltas_arr > decay_threshold,
                (deltas_arr - decay_threshold) * decay_rate,
                0.0
            )

            # 直接返回結果, 確保不低於 0
            return np.maximum(scores_arr - decay_amount, 0.0)

        except Exception as e:
            logger.warning(f"NumPy 衰減計算失敗, 使用回退機制: {e}")
            return self._fallback_bulk_decay(scores, deltas)

    def bulk_score_update(
        self,
        current_scores: Union[list[float], 'np.ndarray'],
        last_msg_times: Union[list[int], 'np.ndarray'],
        now_times: Union[list[int], 'np.ndarray']
    ) -> Union[list[float], 'np.ndarray']:
        """
        批量更新活躍度分數

        Args:
            current_scores: 當前分數陣列
            last_msg_times: 上次訊息時間陣列
            now_times: 當前時間陣列

        Returns:
            Union[List[float], np.ndarray]: 更新後的分數陣列
        """
        if not self.use_numpy or not self.numpy_available:
            return self._fallback_bulk_score_update(
                current_scores, last_msg_times, now_times
            )

        try:
            # 轉換為 NumPy 陣列
            scores_arr = np.asarray(current_scores, dtype=np.float32)
            last_times_arr = np.asarray(last_msg_times, dtype=np.int32)
            now_times_arr = np.asarray(now_times, dtype=np.int32)

            # 計算時間差
            deltas = now_times_arr - last_times_arr

            # 配置常數
            decay_threshold = np.int32(config.ACTIVITY_DECAY_AFTER)
            decay_rate = np.float32(config.ACTIVITY_DECAY_PER_H / 3600.0)
            gain = np.float32(config.ACTIVITY_GAIN)
            max_score = np.float32(config.ACTIVITY_MAX_SCORE)


            decay_amount = np.where(
                deltas > decay_threshold,
                (deltas - decay_threshold) * decay_rate,
                0.0
            )

            # 計算最終分數: (原分數 - 衰減) + 增益, 限制在 [0, max_score]
            final_scores = np.clip(
                scores_arr - decay_amount + gain,
                0.0,
                max_score
            )

            return final_scores

        except Exception as e:
            logger.warning(f"NumPy 分數更新失敗, 使用回退機制: {e}")
            return self._fallback_bulk_score_update(
                current_scores, last_msg_times, now_times
            )

    def bulk_should_update(
        self,
        last_msg_times: Union[list[int], 'np.ndarray'],
        now_times: Union[list[int], 'np.ndarray']
    ) -> Union[list[bool], 'np.ndarray']:
        """
        批量判斷是否應該更新活躍度

        Args:
            last_msg_times: 上次訊息時間陣列
            now_times: 當前時間陣列

        Returns:
            Union[List[bool], np.ndarray]: 是否需要更新的布林陣列
        """
        if not self.use_numpy or not self.numpy_available:
            return self._fallback_bulk_should_update(last_msg_times, now_times)

        try:
            # 轉換為 NumPy 陣列
            last_times_array = np.asarray(last_msg_times, dtype=np.int32)
            now_times_array = np.asarray(now_times, dtype=np.int32)

            # 計算時間差並比較冷卻時間
            deltas = now_times_array - last_times_array
            should_update = deltas >= config.ACTIVITY_COOLDOWN

            return should_update

        except Exception as e:
            logger.warning(f"NumPy 冷卻檢查失敗, 使用回退機制: {e}")
            return self._fallback_bulk_should_update(last_msg_times, now_times)

    def _fallback_bulk_decay(
        self,
        scores: list[float],
        deltas: list[int]
    ) -> list[float]:
        """回退方式的批量衰減計算"""
        if not self.fallback_calculator:
            # 如果沒有回退計算器, 使用內建邏輯
            return [
                self._simple_decay(score, delta)
                for score, delta in zip(scores, deltas, strict=False)
            ]

        return [
            self.fallback_calculator.decay(score, delta)
            for score, delta in zip(scores, deltas, strict=False)
        ]

    def _fallback_bulk_score_update(
        self,
        current_scores: list[float],
        last_msg_times: list[int],
        now_times: list[int]
    ) -> list[float]:
        """回退方式的批量分數更新"""
        if not self.fallback_calculator:
            return [
                self._simple_score_update(score, last_time, now_time)
                for score, last_time, now_time
                in zip(current_scores, last_msg_times, now_times, strict=False)
            ]

        return [
            self.fallback_calculator.calculate_new_score(score, last_time, now_time)
            for score, last_time, now_time
            in zip(current_scores, last_msg_times, now_times, strict=False)
        ]

    def _fallback_bulk_should_update(
        self,
        last_msg_times: list[int],
        now_times: list[int]
    ) -> list[bool]:
        """回退方式的批量冷卻檢查"""
        if not self.fallback_calculator:
            return [
                (now_time - last_time) >= config.ACTIVITY_COOLDOWN
                for last_time, now_time in zip(last_msg_times, now_times, strict=False)
            ]

        return [
            self.fallback_calculator.should_update(last_time, now_time)
            for last_time, now_time in zip(last_msg_times, now_times, strict=False)
        ]

    def _simple_decay(self, score: float, delta: int) -> float:
        """簡單的衰減計算(內建回退)"""
        if delta <= config.ACTIVITY_DECAY_AFTER:
            return score

        decay = (config.ACTIVITY_DECAY_PER_H / 3600) * (
            delta - config.ACTIVITY_DECAY_AFTER
        )
        return max(0, score - decay)

    def _simple_score_update(
        self, current_score: float, last_msg_time: int, now: int
    ) -> float:
        """簡單的分數更新計算(內建回退)"""
        decayed_score = self._simple_decay(current_score, now - last_msg_time)
        new_score = decayed_score + config.ACTIVITY_GAIN
        return min(new_score, config.ACTIVITY_MAX_SCORE)

    def check_numpy_performance(self, test_size: int = 1000) -> bool:
        """
        檢查 NumPy 性能是否達到要求

        Args:
            test_size: 測試資料大小

        Returns:
            bool: NumPy 是否有效且性能良好
        """
        if not self.numpy_available:
            return False

        try:
            # 生成測試資料
            scores = [random.uniform(0, 100) for _ in range(test_size)]
            deltas = [random.randint(0, 86400) for _ in range(test_size)]

            # 測試回退方法
            start_time = time.perf_counter()
            self._fallback_bulk_decay(scores, deltas)
            fallback_time = time.perf_counter() - start_time

            # 測試 NumPy 方法
            start_time = time.perf_counter()
            self.bulk_decay_calculation(scores, deltas)
            numpy_time = time.perf_counter() - start_time

            # 檢查性能改善
            if numpy_time > 0:
                improvement = fallback_time / numpy_time
                performance_good = improvement >= self.performance_threshold

                logger.info(
                    f"NumPy 性能測試: 改善 {improvement:.2f}x "
                    f"({'通過' if performance_good else '未通過'})"
                )

                return performance_good

            return False

        except Exception as e:
            logger.warning(f"NumPy 性能檢查失敗: {e}")
            return False

    def get_status(self) -> dict:
        """
        獲取計算器狀態

        Returns:
            dict: 狀態資訊
        """
        return {
            "numpy_available": self.numpy_available,
            "use_numpy": self.use_numpy,
            "performance_threshold": self.performance_threshold,
            "fallback_available": self.fallback_calculator is not None
        }
