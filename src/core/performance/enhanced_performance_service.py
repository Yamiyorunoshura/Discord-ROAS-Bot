"""
Enhanced Performance Optimization Service with adaptive thresholds.

This service intelligently chooses between numpy and native Python
based on data size to maximize performance.
"""

import time
from collections.abc import Callable
from typing import Any

import numpy as np
from structlog import get_logger

logger = get_logger(__name__)

# Performance benchmark targets
PERFORMANCE_TARGET_THRESHOLD = 30.0


class EnhancedPerformanceOptimizationService:
    """
    Enhanced performance optimization service with adaptive algorithm selection.

    This service automatically chooses the best implementation (numpy vs native Python)
    based on data size and operation complexity to maximize performance.
    """

    def __init__(self) -> None:
        """Initialize the enhanced performance optimization service."""
        self._benchmarks: dict[str, list[float]] = {}
        # Thresholds for when to use numpy (determined through benchmarking)
        self._numpy_thresholds = {
            "sum": 10000,
            "mean": 10000,
            "std": 5000,
            "var": 5000,
            "min": 50000,  # min/max are very fast in native Python
            "max": 50000,
            "median": 2000,
            "percentile": 2000,
            "weighted_average": 1000,
            "correlation": 100,
            "moving_average": 500,
            "normalize": 1000,
            "cumsum": 5000,
            "diff": 5000,
        }
        # Operation mappings for numpy
        self._numpy_operations = {
            "sum": lambda data: float(np.sum(data)),
            "mean": lambda data: float(np.mean(data)),
            "std": lambda data: float(np.std(data)),
            "var": lambda data: float(np.var(data)),
            "min": lambda data: float(np.min(data)),
            "max": lambda data: float(np.max(data)),
            "median": lambda data: float(np.median(data)),
            "cumsum": lambda data: np.cumsum(data),
            "diff": lambda data: np.diff(data),
        }

    def optimize_calculations(
        self, data: list[int | float] | np.ndarray[Any, Any], operation: str, **kwargs: Any
    ) -> float | np.ndarray[Any, Any] | list[float]:
        """
        Optimize calculations with adaptive algorithm selection.

        Args:
            data: Input data as list or numpy array
            operation: Type of operation to perform
            **kwargs: Additional parameters for the operation

        Returns:
            Optimized calculation result

        Raises:
            ValueError: If operation is not supported
        """
        # Handle input data
        if isinstance(data, np.ndarray):
            data_list = data.tolist()
            data_length = len(data_list)
        else:
            data_list = list(data)
            data_length = len(data_list)

        if data_length == 0:
            logger.warning("Empty data provided for optimization")
            return 0.0

        # Determine whether to use numpy based on data size and operation
        threshold = self._numpy_thresholds.get(operation, 1000)
        use_numpy = data_length >= threshold

        if use_numpy:
            # Use numpy for large datasets
            try:
                return self._numpy_calculation(data_list, operation, **kwargs)
            except Exception as e:
                logger.warning(f"Numpy calculation failed, falling back to native: {e}")
                return self._native_calculation(data_list, operation, **kwargs)
        else:
            # Use native Python for small datasets
            return self._native_calculation(data_list, operation, **kwargs)

    def _numpy_calculation(
        self, data: list[int | float], operation: str, **kwargs: Any
    ) -> float | np.ndarray | list[float]:
        """Numpy-based calculations for large datasets."""
        data_array = np.array(data)

        # Handle simple operations without parameters
        if operation in self._numpy_operations:
            return self._numpy_operations[operation](data_array)

        # Handle operations with parameters
        return self._handle_numpy_parameterized_operations(
            data_array, operation, **kwargs
        )

    def _handle_numpy_parameterized_operations(
        self, data_array: np.ndarray, operation: str, **kwargs: Any
    ) -> float | np.ndarray | list[float]:
        """Handle numpy operations that require additional parameters."""
        if operation == "percentile":
            percentile = kwargs.get("percentile", 50)
            return float(np.percentile(data_array, percentile))
        elif operation == "weighted_average":
            weights = kwargs.get("weights")
            if weights is None:
                raise ValueError("Weights required for weighted_average operation")
            weights = np.array(weights)
            return float(np.average(data_array, weights=weights))
        elif operation == "correlation":
            other_data = kwargs.get("other_data")
            if other_data is None:
                raise ValueError("other_data required for correlation operation")
            other_data = np.array(other_data)
            return float(np.corrcoef(data_array, other_data)[0, 1])
        elif operation == "moving_average":
            window_size = kwargs.get("window_size", 5)
            return np.convolve(
                data_array, np.ones(window_size) / window_size, mode="valid"
            )
        elif operation == "normalize":
            return (data_array - np.mean(data_array)) / np.std(data_array)
        else:
            raise ValueError(f"Unsupported numpy operation: {operation}")

    def _native_calculation(
        self, data: list[int | float], operation: str, **kwargs: Any
    ) -> float | list[float]:
        """Native Python calculations for small datasets."""
        if not data:
            return 0.0

        # Simple operations map
        operations_map = {
            "sum": lambda d: float(sum(d)),
            "mean": lambda d: float(sum(d) / len(d)),
            "min": lambda d: float(min(d)),
            "max": lambda d: float(max(d)),
        }

        if operation in operations_map:
            return operations_map[operation](data)

        # Complex operations requiring additional logic
        return self._handle_native_complex_operations(data, operation, **kwargs)

    def _handle_native_complex_operations(
        self, data: list[int | float], operation: str, **kwargs: Any
    ) -> float | list[float]:
        """Handle complex native Python operations."""
        # Statistical operations
        if operation in ("std", "var"):
            mean = sum(data) / len(data)
            variance = sum((x - mean) ** 2 for x in data) / len(data)
            return float(variance**0.5) if operation == "std" else float(variance)

        elif operation == "median":
            sorted_data = sorted(data)
            n = len(sorted_data)
            if n % 2 == 0:
                return float((sorted_data[n // 2 - 1] + sorted_data[n // 2]) / 2)
            else:
                return float(sorted_data[n // 2])

        elif operation == "percentile":
            return self._calculate_percentile(data, kwargs.get("percentile", 50))

        elif operation == "weighted_average":
            weights = kwargs.get("weights")
            if weights is None:
                raise ValueError("Weights required for weighted_average operation")
            return float(
                sum(d * w for d, w in zip(data, weights, strict=False)) / sum(weights)
            )

        elif operation == "cumsum":
            result = []
            cumulative = 0.0
            for x in data:
                cumulative += x
                result.append(cumulative)
            return result

        else:
            raise ValueError(f"Unsupported native operation: {operation}")

    def _calculate_percentile(
        self, data: list[int | float], percentile: float
    ) -> float:
        """Calculate percentile using native Python."""
        sorted_data = sorted(data)
        k = (len(sorted_data) - 1) * percentile / 100
        f = int(k)
        c = k - f
        if f == len(sorted_data) - 1:
            return float(sorted_data[f])
        return float(sorted_data[f] + c * (sorted_data[f + 1] - sorted_data[f]))

    def benchmark_performance(
        self,
        name: str,
        old_function: Callable[..., Any],
        new_function: Callable[..., Any],
        test_data: Any,
        iterations: int = 100,
    ) -> dict[str, Any]:
        """Benchmark performance between implementations (same as original)."""
        logger.info(f"Starting benchmark: {name}")

        # Warm up runs
        for _ in range(5):
            try:
                old_function(test_data)
                new_function(test_data)
            except Exception as e:
                logger.error(f"Warmup failed for {name}: {e}")

        # Benchmark old function
        old_times = []
        for i in range(iterations):
            start_time = time.perf_counter()
            try:
                old_function(test_data)
                end_time = time.perf_counter()
                old_times.append(end_time - start_time)
            except Exception as e:
                logger.error(f"Old function failed on iteration {i}: {e}")
                break

        # Benchmark new function
        new_times = []
        for i in range(iterations):
            start_time = time.perf_counter()
            try:
                new_function(test_data)
                end_time = time.perf_counter()
                new_times.append(end_time - start_time)
            except Exception as e:
                logger.error(f"New function failed on iteration {i}: {e}")
                break

        if not old_times or not new_times:
            logger.error(f"Benchmark {name} failed - insufficient data")
            return {"error": "Benchmark failed"}

        # Calculate statistics
        old_avg = np.mean(old_times)
        new_avg = np.mean(new_times)
        improvement = ((old_avg - new_avg) / old_avg) * 100

        results = {
            "name": name,
            "old_avg_time": old_avg,
            "new_avg_time": new_avg,
            "old_std_time": np.std(old_times),
            "new_std_time": np.std(new_times),
            "improvement_percent": improvement,
            "iterations": min(len(old_times), len(new_times)),
            "speedup_factor": old_avg / new_avg if new_avg > 0 else float("inf"),
            "data_size": len(test_data) if hasattr(test_data, "__len__") else "unknown",
        }

        # Store benchmark results
        if name not in self._benchmarks:
            self._benchmarks[name] = []
        self._benchmarks[name].append(improvement)

        logger.info(
            f"Benchmark {name} completed: "
            f"{improvement:.2f}% improvement, "
            f"{results['speedup_factor']:.2f}x speedup, "
            f"data_size={results['data_size']}"
        )

        return results

    def get_numpy_threshold(self, operation: str) -> int:
        """Get the data size threshold for using numpy for a given operation."""
        return self._numpy_thresholds.get(operation, 1000)

    def set_numpy_threshold(self, operation: str, threshold: int) -> None:
        """Set the data size threshold for using numpy for a given operation."""
        self._numpy_thresholds[operation] = threshold
        logger.info(f"Set numpy threshold for {operation} to {threshold}")

    def get_benchmark_summary(self, name: str | None = None) -> dict[str, Any]:
        """Get summary of benchmark results (same as original)."""
        if name:
            if name not in self._benchmarks:
                return {"error": f"No benchmark data for {name}"}
            improvements = self._benchmarks[name]
            return {
                "name": name,
                "avg_improvement": np.mean(improvements),
                "std_improvement": np.std(improvements),
                "min_improvement": np.min(improvements),
                "max_improvement": np.max(improvements),
                "num_benchmarks": len(improvements),
            }
        else:
            summary = {}
            for bench_name, improvements in self._benchmarks.items():
                summary[bench_name] = {
                    "avg_improvement": np.mean(improvements),
                    "std_improvement": np.std(improvements),
                    "num_benchmarks": len(improvements),
                }
            return summary

    def create_performance_report(self) -> str:
        """Create a detailed performance report (same as original)."""
        if not self._benchmarks:
            return "No benchmark data available"

        report_lines = ["# Enhanced Performance Optimization Report\n"]

        for name, improvements in self._benchmarks.items():
            avg_improvement = np.mean(improvements)
            std_improvement = np.std(improvements)

            report_lines.extend([
                f"## {name}",
                f"- Average improvement: {avg_improvement:.2f}%",
                f"- Standard deviation: {std_improvement:.2f}%",
                f"- Benchmarks run: {len(improvements)}",
                f"- Status: {'PASS - Target met' if avg_improvement >= PERFORMANCE_TARGET_THRESHOLD else 'FAIL - Below target'}",
                "",
            ])

        return "\n".join(report_lines)
