"""
Performance Optimization Service.

This service provides centralized performance optimization capabilities
using numpy for vectorized operations and benchmarking utilities.
"""

import time
from collections.abc import Callable
from typing import Any

import numpy as np
from structlog import get_logger

logger = get_logger(__name__)

# Performance benchmark targets
PERFORMANCE_TARGET_THRESHOLD = 30.0


class PerformanceOptimizationService:
    """
    Service for optimizing computational performance using numpy.

    This service provides methods to optimize calculations using numpy's
    vectorized operations and benchmark performance improvements.
    """

    def __init__(self) -> None:
        """Initialize the performance optimization service."""
        self._benchmarks: dict[str, list[float]] = {}
        self._operations = {
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
        Optimize calculations using numpy vectorized operations.

        Args:
            data: Input data as list or numpy array
            operation: Type of operation to perform
            **kwargs: Additional parameters for the operation

        Returns:
            Optimized calculation result

        Raises:
            ValueError: If operation is not supported
        """
        # Convert input to numpy array for optimization
        if not isinstance(data, np.ndarray):
            data = np.array(data)

        if data.size == 0:
            logger.warning("Empty data provided for optimization")
            return 0.0

        # Handle simple operations without parameters
        if operation in self._operations:
            return self._operations[operation](data)

        # Handle operations with parameters
        return self._handle_parameterized_operations(data, operation, **kwargs)

    def _handle_parameterized_operations(
        self, data: np.ndarray[Any, Any], operation: str, **kwargs: Any
    ) -> float | np.ndarray[Any, Any] | list[float]:
        """Handle operations that require additional parameters."""
        if operation == "percentile":
            percentile = kwargs.get("percentile", 50)
            return float(np.percentile(data, percentile))
        elif operation == "weighted_average":
            weights = kwargs.get("weights")
            if weights is None:
                raise ValueError("Weights required for weighted_average operation")
            weights = (
                np.array(weights) if not isinstance(weights, np.ndarray) else weights
            )
            return float(np.average(data, weights=weights))
        elif operation == "correlation":
            other_data = kwargs.get("other_data")
            if other_data is None:
                raise ValueError("other_data required for correlation operation")
            other_data = (
                np.array(other_data)
                if not isinstance(other_data, np.ndarray)
                else other_data
            )
            return float(np.corrcoef(data, other_data)[0, 1])
        elif operation == "moving_average":
            window_size = kwargs.get("window_size", 5)
            return np.convolve(data, np.ones(window_size) / window_size, mode="valid")
        elif operation == "normalize":
            return (data - np.mean(data)) / np.std(data)
        else:
            raise ValueError(f"Unsupported operation: {operation}")

    def benchmark_performance(
        self,
        name: str,
        old_function: Callable[..., Any],
        new_function: Callable[..., Any],
        test_data: Any,
        iterations: int = 100,
    ) -> dict[str, Any]:
        """
        Benchmark performance between old and new implementations.

        Args:
            name: Name of the benchmark
            old_function: Original function implementation
            new_function: Optimized function implementation
            test_data: Test data to use for benchmarking
            iterations: Number of iterations to run

        Returns:
            Benchmark results including timing and improvement metrics
        """
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
        }

        # Store benchmark results
        if name not in self._benchmarks:
            self._benchmarks[name] = []
        self._benchmarks[name].append(improvement)

        logger.info(
            f"Benchmark {name} completed: "
            f"{improvement:.2f}% improvement, "
            f"{results['speedup_factor']:.2f}x speedup"
        )

        return results

    def get_benchmark_summary(self, name: str | None = None) -> dict[str, Any]:
        """
        Get summary of benchmark results.

        Args:
            name: Specific benchmark name, or None for all benchmarks

        Returns:
            Summary of benchmark results
        """
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
        """
        Create a detailed performance report.

        Returns:
            Formatted performance report
        """
        if not self._benchmarks:
            return "No benchmark data available"

        report_lines = ["# Performance Optimization Report\n"]

        for name, improvements in self._benchmarks.items():
            avg_improvement = np.mean(improvements)
            std_improvement = np.std(improvements)

            report_lines.extend([
                f"## {name}",
                f"- Average improvement: {avg_improvement:.2f}%",
                f"- Standard deviation: {std_improvement:.2f}%",
                f"- Benchmarks run: {len(improvements)}",
                f"- Status: {'✅ Target met' if avg_improvement >= PERFORMANCE_TARGET_THRESHOLD else '⚠️ Below target'}",
                "",
            ])

        return "\n".join(report_lines)
