"""
活躍度計算性能基準測試套件
- 比較標準計算與 NumPy 優化計算的性能
- 提供詳細的性能報告和分析
"""

import logging
import random
import time
from typing import Any

# 標準庫計算
from ..main.calculator import ActivityCalculator

logger = logging.getLogger("activity_meter")

class PerformanceBenchmark:
    """
    性能基準測試類別

    提供標準計算與 NumPy 優化計算的性能比較框架
    """

    def __init__(self):
        """初始化基準測試"""
        self.standard_calculator = ActivityCalculator()
        self.numpy_calculator = None  # 將在實作後初始化

    def set_numpy_calculator(self, numpy_calc: Any) -> None:
        """設定 NumPy 計算器"""
        self.numpy_calculator = numpy_calc

    def benchmark_decay_calculation(self, sample_sizes: list[int]) -> dict[str, Any]:
        """
        基準測試衰減計算性能

        Args:
            sample_sizes: 測試資料大小列表

        Returns:
            Dict[str, Any]: 性能測試結果
        """
        results = {
            "test_name": "decay_calculation",
            "sample_sizes": sample_sizes,
            "standard_times": [],
            "numpy_times": [],
            "improvement_ratios": []
        }

        for size in sample_sizes:
            # 生成測試資料
            test_data = self._generate_decay_test_data(size)

            # 測試標準計算
            standard_time = self._benchmark_standard_decay(test_data)
            results["standard_times"].append(standard_time)

            # 測試 NumPy 計算 (如果可用)
            if self.numpy_calculator:
                numpy_time = self._benchmark_numpy_decay(test_data)
                results["numpy_times"].append(numpy_time)

                # 計算改善比例
                improvement = standard_time / numpy_time if numpy_time > 0 else float('inf')
                results["improvement_ratios"].append(improvement)
            else:
                results["numpy_times"].append(0)
                results["improvement_ratios"].append(0)

        return results

    def benchmark_score_calculation(self, sample_sizes: list[int]) -> dict[str, Any]:
        """
        基準測試分數計算性能

        Args:
            sample_sizes: 測試資料大小列表

        Returns:
            Dict[str, Any]: 性能測試結果
        """
        results = {
            "test_name": "score_calculation",
            "sample_sizes": sample_sizes,
            "standard_times": [],
            "numpy_times": [],
            "improvement_ratios": []
        }

        for size in sample_sizes:
            # 生成測試資料
            test_data = self._generate_score_test_data(size)

            # 測試標準計算
            standard_time = self._benchmark_standard_score(test_data)
            results["standard_times"].append(standard_time)

            # 測試 NumPy 計算 (如果可用)
            if self.numpy_calculator:
                numpy_time = self._benchmark_numpy_score(test_data)
                results["numpy_times"].append(numpy_time)

                # 計算改善比例
                improvement = standard_time / numpy_time if numpy_time > 0 else float('inf')
                results["improvement_ratios"].append(improvement)
            else:
                results["numpy_times"].append(0)
                results["improvement_ratios"].append(0)

        return results

    def _generate_decay_test_data(self, size: int) -> list[tuple[float, int]]:
        """
        生成衰減計算測試資料

        Args:
            size: 資料大小

        Returns:
            List[Tuple[float, int]]: (score, delta) 資料對
        """
        return [
            (random.uniform(0, 100), random.randint(0, 86400))
            for _ in range(size)
        ]

    def _generate_score_test_data(self, size: int) -> list[tuple[float, int, int]]:
        """
        生成分數計算測試資料

        Args:
            size: 資料大小

        Returns:
            List[Tuple[float, int, int]]: (current_score, last_msg_time, now) 資料
        """
        now = int(time.time())
        return [
            (
                random.uniform(0, 100),
                now - random.randint(0, 86400),
                now
            )
            for _ in range(size)
        ]

    def _benchmark_standard_decay(self, test_data: list[tuple[float, int]]) -> float:
        """基準測試標準衰減計算"""
        start_time = time.perf_counter()

        for score, delta in test_data:
            self.standard_calculator.decay(score, delta)

        end_time = time.perf_counter()
        return end_time - start_time

    def _benchmark_numpy_decay(self, test_data: list[tuple[float, int]]) -> float:
        """基準測試 NumPy 衰減計算"""
        if not self.numpy_calculator:
            return 0

        start_time = time.perf_counter()

        # 提取分數和時間差陣列
        scores = [item[0] for item in test_data]
        deltas = [item[1] for item in test_data]

        # 批量計算
        self.numpy_calculator.bulk_decay_calculation(scores, deltas)

        end_time = time.perf_counter()
        return end_time - start_time

    def _benchmark_standard_score(self, test_data: list[tuple[float, int, int]]) -> float:
        """基準測試標準分數計算"""
        start_time = time.perf_counter()

        for current_score, last_msg_time, now in test_data:
            self.standard_calculator.calculate_new_score(current_score, last_msg_time, now)

        end_time = time.perf_counter()
        return end_time - start_time

    def _benchmark_numpy_score(self, test_data: list[tuple[float, int, int]]) -> float:
        """基準測試 NumPy 分數計算"""
        if not self.numpy_calculator:
            return 0

        start_time = time.perf_counter()

        # 提取資料陣列
        current_scores = [item[0] for item in test_data]
        last_msg_times = [item[1] for item in test_data]
        nows = [item[2] for item in test_data]

        # 批量計算
        self.numpy_calculator.bulk_score_update(current_scores, last_msg_times, nows)

        end_time = time.perf_counter()
        return end_time - start_time

    def generate_report(self, results: list[dict[str, Any]]) -> str:
        """
        生成性能測試報告

        Args:
            results: 測試結果列表

        Returns:
            str: 格式化的報告文字
        """
        report_lines = [
            "=" * 60,
            "活躍度計算性能基準測試報告",
            "=" * 60,
            ""
        ]

        for result in results:
            test_name = result["test_name"]
            sample_sizes = result["sample_sizes"]
            standard_times = result["standard_times"]
            numpy_times = result["numpy_times"]
            improvements = result["improvement_ratios"]

            report_lines.extend([
                f"測試項目: {test_name}",
                "-" * 40,
                ""
            ])

            # 表頭
            report_lines.append(f"{'樣本大小':<10} {'標準(秒)':<12} {'NumPy(秒)':<12} {'改善倍數':<10}")
            report_lines.append("-" * 50)

            # 資料行
            for i, size in enumerate(sample_sizes):
                std_time = standard_times[i]
                np_time = numpy_times[i] if i < len(numpy_times) else 0
                improvement = improvements[i] if i < len(improvements) else 0

                report_lines.append(
                    f"{size:<10} {std_time:<12.4f} {np_time:<12.4f} {improvement:<10.2f}x"
                )

            # 平均改善
            if improvements and any(imp > 0 for imp in improvements):
                valid_improvements = [imp for imp in improvements if imp > 0]
                avg_improvement = sum(valid_improvements) / len(valid_improvements)
                report_lines.extend([
                    "",
                    f"平均性能改善: {avg_improvement:.2f}x",
                    ""
                ])

            report_lines.append("")

        return "\n".join(report_lines)

def run_comprehensive_benchmark() -> str:
    """
    執行完整的性能基準測試

    Returns:
        str: 完整的測試報告
    """
    benchmark = PerformanceBenchmark()

    # 測試樣本大小
    sample_sizes = [100, 500, 1000, 5000, 10000]

    results = []

    # 衰減計算基準測試
    logger.info("執行衰減計算基準測試...")
    decay_results = benchmark.benchmark_decay_calculation(sample_sizes)
    results.append(decay_results)

    # 分數計算基準測試
    logger.info("執行分數計算基準測試...")
    score_results = benchmark.benchmark_score_calculation(sample_sizes)
    results.append(score_results)

    # 生成報告
    report = benchmark.generate_report(results)

    # 記錄到日誌
    logger.info("性能基準測試完成")
    logger.info(f"\n{report}")

    return report

if __name__ == "__main__":
    # 直接執行基準測試
    report = run_comprehensive_benchmark()
    print(report)
