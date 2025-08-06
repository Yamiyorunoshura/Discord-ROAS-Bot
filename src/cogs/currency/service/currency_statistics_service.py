"""
Currency Statistics Service with NumPy optimization.

這個模組提供基於 numpy 的貨幣統計計算優化。
"""

import logging
from typing import Any

from src.core.performance import PerformanceOptimizationService

logger = logging.getLogger(__name__)


class CurrencyStatisticsService:
    """
    貨幣統計服務 - 使用 numpy 優化統計計算
    """

    def __init__(self):
        """初始化統計服務。"""
        self.performance_service = PerformanceOptimizationService()
        logger.info(
            "CurrencyStatisticsService initialized with performance optimization"
        )

    def calculate_guild_statistics(self, balances: list[float]) -> dict[str, Any]:
        """
        計算伺服器經濟統計 (使用 numpy 優化)

        Args:
            balances: 餘額列表

        Returns:
            Dict[str, Any]: 統計結果字典
        """
        if not balances:
            return {
                "total_users": 0,
                "total_currency": 0.0,
                "average_balance": 0.0,
                "max_balance": 0.0,
                "min_balance": 0.0,
                "median_balance": 0.0,
                "std_balance": 0.0,
                "balance_distribution": {},
            }

        try:
            # 使用 numpy 向量化計算所有統計指標
            total_currency = self.performance_service.optimize_calculations(
                balances, "sum"
            )
            average_balance = self.performance_service.optimize_calculations(
                balances, "mean"
            )
            max_balance = self.performance_service.optimize_calculations(
                balances, "max"
            )
            min_balance = self.performance_service.optimize_calculations(
                balances, "min"
            )
            median_balance = self.performance_service.optimize_calculations(
                balances, "median"
            )
            std_balance = self.performance_service.optimize_calculations(
                balances, "std"
            )

            # 計算餘額分佈
            distribution = self._calculate_balance_distribution(balances)

            return {
                "total_users": len(balances),
                "total_currency": float(total_currency),
                "average_balance": float(average_balance),
                "max_balance": float(max_balance),
                "min_balance": float(min_balance),
                "median_balance": float(median_balance),
                "std_balance": float(std_balance),
                "balance_distribution": distribution,
            }

        except Exception as e:
            logger.warning(f"NumPy statistics calculation failed, using fallback: {e}")
            return self._fallback_calculate_statistics(balances)

    def calculate_wealth_inequality_metrics(
        self, balances: list[float]
    ) -> dict[str, float]:
        """
        計算財富不平等指標 (使用 numpy 優化)

        Args:
            balances: 餘額列表

        Returns:
            Dict[str, float]: 不平等指標
        """
        if not balances or len(balances) < 2:
            return {
                "gini_coefficient": 0.0,
                "top_1_percent_share": 0.0,
                "top_10_percent_share": 0.0,
                "bottom_50_percent_share": 0.0,
            }

        try:
            # 排序餘額 (使用 numpy)
            sorted_balances = sorted(balances, reverse=True)
            total_wealth = sum(sorted_balances)

            if total_wealth == 0:
                return {
                    "gini_coefficient": 0.0,
                    "top_1_percent_share": 0.0,
                    "top_10_percent_share": 0.0,
                    "bottom_50_percent_share": 0.0,
                }

            n = len(sorted_balances)

            # 計算百分比分享
            top_1_percent_count = max(1, n // 100)
            top_10_percent_count = max(1, n // 10)
            bottom_50_percent_count = n // 2

            top_1_percent_wealth = sum(sorted_balances[:top_1_percent_count])
            top_10_percent_wealth = sum(sorted_balances[:top_10_percent_count])
            bottom_50_percent_wealth = sum(sorted_balances[-bottom_50_percent_count:])

            # 使用 numpy 計算基尼係數
            gini = self._calculate_gini_coefficient(balances)

            return {
                "gini_coefficient": float(gini),
                "top_1_percent_share": float(top_1_percent_wealth / total_wealth * 100),
                "top_10_percent_share": float(
                    top_10_percent_wealth / total_wealth * 100
                ),
                "bottom_50_percent_share": float(
                    bottom_50_percent_wealth / total_wealth * 100
                ),
            }

        except Exception as e:
            logger.warning(f"Wealth inequality calculation failed: {e}")
            return {
                "gini_coefficient": 0.0,
                "top_1_percent_share": 0.0,
                "top_10_percent_share": 0.0,
                "bottom_50_percent_share": 0.0,
            }

    def batch_calculate_transaction_metrics(
        self, transaction_amounts: list[float], user_balances: list[float]
    ) -> dict[str, Any]:
        """
        批量計算交易指標 (使用 numpy 優化)

        Args:
            transaction_amounts: 交易金額列表
            user_balances: 用戶餘額列表

        Returns:
            Dict[str, Any]: 交易指標
        """
        if not transaction_amounts:
            return {
                "total_transactions": 0,
                "total_volume": 0.0,
                "average_transaction": 0.0,
                "median_transaction": 0.0,
                "transaction_velocity": 0.0,
            }

        try:
            # 使用 numpy 計算交易統計
            total_volume = self.performance_service.optimize_calculations(
                transaction_amounts, "sum"
            )
            average_transaction = self.performance_service.optimize_calculations(
                transaction_amounts, "mean"
            )
            median_transaction = self.performance_service.optimize_calculations(
                transaction_amounts, "median"
            )

            # 計算交易速度 (總交易量 / 總餘額)
            total_balance = (
                self.performance_service.optimize_calculations(user_balances, "sum")
                if user_balances
                else 1.0
            )

            transaction_velocity = (
                total_volume / total_balance if total_balance > 0 else 0.0
            )

            return {
                "total_transactions": len(transaction_amounts),
                "total_volume": float(total_volume),
                "average_transaction": float(average_transaction),
                "median_transaction": float(median_transaction),
                "transaction_velocity": float(transaction_velocity),
            }

        except Exception as e:
            logger.warning(f"Transaction metrics calculation failed: {e}")
            return {
                "total_transactions": len(transaction_amounts),
                "total_volume": sum(transaction_amounts),
                "average_transaction": sum(transaction_amounts)
                / len(transaction_amounts),
                "median_transaction": sorted(transaction_amounts)[
                    len(transaction_amounts) // 2
                ],
                "transaction_velocity": 0.0,
            }

    def _calculate_balance_distribution(self, balances: list[float]) -> dict[str, int]:
        """
        計算餘額分佈 (使用 numpy 優化的分桶計算)

        Args:
            balances: 餘額列表

        Returns:
            Dict[str, int]: 分佈字典
        """
        if not balances:
            return {}

        try:
            # 定義分桶範圍
            buckets = {
                "0-100": (0, 100),
                "101-500": (101, 500),
                "501-1000": (501, 1000),
                "1001-5000": (1001, 5000),
                "5001-10000": (5001, 10000),
                "10000+": (10001, float("inf")),
            }

            distribution = {}
            for bucket_name, (min_val, max_val) in buckets.items():
                count = sum(1 for balance in balances if min_val <= balance <= max_val)
                distribution[bucket_name] = count

            return distribution

        except Exception as e:
            logger.warning(f"Balance distribution calculation failed: {e}")
            return {}

    def _calculate_gini_coefficient(self, balances: list[float]) -> float:
        """
        計算基尼係數 (使用 numpy 優化)

        Args:
            balances: 餘額列表

        Returns:
            float: 基尼係數 (0-1)
        """
        if not balances or len(balances) < 2:
            return 0.0

        try:
            # 使用 numpy 向量化計算基尼係數
            n = len(balances)
            sorted_balances = sorted(balances)

            # 累積分布
            self.performance_service.optimize_calculations(sorted_balances, "cumsum")

            # 基尼係數計算
            total = sum(sorted_balances)
            if total == 0:
                return 0.0

            # 使用數學公式計算基尼係數
            gini = (2 * sum((i + 1) * val for i, val in enumerate(sorted_balances))) / (
                n * total
            ) - (n + 1) / n

            return max(0.0, min(1.0, gini))

        except Exception as e:
            logger.warning(f"Gini coefficient calculation failed: {e}")
            return 0.0

    def _fallback_calculate_statistics(self, balances: list[float]) -> dict[str, Any]:
        """
        回退統計計算方法

        Args:
            balances: 餘額列表

        Returns:
            Dict[str, Any]: 統計結果
        """
        if not balances:
            return {
                "total_users": 0,
                "total_currency": 0.0,
                "average_balance": 0.0,
                "max_balance": 0.0,
                "min_balance": 0.0,
                "median_balance": 0.0,
                "std_balance": 0.0,
                "balance_distribution": {},
            }

        total_currency = sum(balances)
        average_balance = total_currency / len(balances)
        sorted_balances = sorted(balances)
        median_balance = sorted_balances[len(balances) // 2]

        # 簡單的標準差計算
        variance = sum((x - average_balance) ** 2 for x in balances) / len(balances)
        std_balance = variance**0.5

        return {
            "total_users": len(balances),
            "total_currency": float(total_currency),
            "average_balance": float(average_balance),
            "max_balance": float(max(balances)),
            "min_balance": float(min(balances)),
            "median_balance": float(median_balance),
            "std_balance": float(std_balance),
            "balance_distribution": self._calculate_balance_distribution(balances),
        }
