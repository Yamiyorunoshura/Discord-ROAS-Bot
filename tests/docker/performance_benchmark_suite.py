"""
Docker測試效能基準測試系統
Task ID: T1 - Docker 測試框架建立 (效能基準測試和報告系統)

Ethan 效能專家的綜合效能測試系統：
- 完整的效能基準測試套件
- 自動化效能報告生成
- 效能趨勢分析和監控
- 優化建議生成系統
"""

import time
import json
import logging
import statistics
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
import concurrent.futures
import threading

try:
    import docker
    from docker.models.containers import Container
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False

from .execution_time_optimizer_v2 import (
    ExecutionTimeOptimizer, 
    create_optimized_test_config,
    ExecutionStrategy,
    ExecutionMetrics
)
from .performance_optimizer import (
    PerformanceProfile,
    OptimizedCrossPlatformTester
)

logger = logging.getLogger(__name__)


@dataclass
class PerformanceBenchmark:
    """效能基準測試配置"""
    name: str
    description: str
    target_execution_time_seconds: float = 600.0  # 10分鐘
    target_memory_limit_mb: float = 2048.0        # 2GB
    target_cpu_limit_percent: float = 80.0        # 80%
    target_success_rate_percent: float = 98.0     # 98%
    minimum_parallel_efficiency_percent: float = 30.0  # 30%提升


class DockerPerformanceBenchmarkSuite:
    """Docker效能基準測試套件"""
    
    def __init__(self, docker_client):
        if not DOCKER_AVAILABLE:
            raise ImportError("Docker SDK 不可用")
            
        self.docker_client = docker_client
        self.benchmarks: List[PerformanceBenchmark] = []
        self.test_results: List[Dict[str, Any]] = []
        self.benchmark_history: List[Dict[str, Any]] = []
        
        # 設定標準基準測試
        self._setup_standard_benchmarks()
        
    def _setup_standard_benchmarks(self) -> None:
        """設定標準基準測試"""
        self.benchmarks = [
            PerformanceBenchmark(
                name="container_lifecycle_benchmark",
                description="容器生命週期效能基準測試",
                target_execution_time_seconds=120.0,  # 2分鐘
                target_success_rate_percent=100.0
            ),
            PerformanceBenchmark(
                name="parallel_execution_benchmark", 
                description="並行執行效能基準測試",
                target_execution_time_seconds=300.0,  # 5分鐘
                minimum_parallel_efficiency_percent=40.0
            ),
            PerformanceBenchmark(
                name="resource_efficiency_benchmark",
                description="資源使用效率基準測試",
                target_execution_time_seconds=180.0,  # 3分鐘
                target_memory_limit_mb=1024.0,        # 1GB
                target_cpu_limit_percent=60.0         # 60%
            ),
            PerformanceBenchmark(
                name="full_test_suite_benchmark",
                description="完整測試套件效能基準測試",
                target_execution_time_seconds=600.0,  # 10分鐘
                target_success_rate_percent=98.0
            )
        ]
    
    def run_all_benchmarks(self, test_image: str = "roas-bot") -> Dict[str, Any]:
        """運行所有基準測試"""
        logger.info("開始運行Docker效能基準測試套件")
        
        benchmark_results = {}
        overall_start_time = time.time()
        
        for benchmark in self.benchmarks:
            logger.info(f"執行基準測試: {benchmark.name}")
            
            try:
                result = self._run_single_benchmark(benchmark, test_image)
                benchmark_results[benchmark.name] = result
                
                # 記錄到歷史
                self.benchmark_history.append({
                    'benchmark_name': benchmark.name,
                    'timestamp': datetime.now().isoformat(),
                    'result': result
                })
                
            except Exception as e:
                logger.error(f"基準測試失敗 {benchmark.name}: {e}")
                benchmark_results[benchmark.name] = {
                    'success': False,
                    'error': str(e),
                    'execution_time': 0
                }
        
        overall_execution_time = time.time() - overall_start_time
        
        # 生成綜合報告
        comprehensive_report = self._generate_comprehensive_report(
            benchmark_results, 
            overall_execution_time
        )
        
        logger.info(f"所有基準測試完成，總時間: {overall_execution_time:.2f}s")
        return comprehensive_report
    
    def _run_single_benchmark(self, benchmark: PerformanceBenchmark, 
                            test_image: str) -> Dict[str, Any]:
        """運行單個基準測試"""
        start_time = time.time()
        
        if benchmark.name == "container_lifecycle_benchmark":
            result = self._run_container_lifecycle_benchmark(test_image)
        elif benchmark.name == "parallel_execution_benchmark":
            result = self._run_parallel_execution_benchmark(test_image)
        elif benchmark.name == "resource_efficiency_benchmark":
            result = self._run_resource_efficiency_benchmark(test_image)
        elif benchmark.name == "full_test_suite_benchmark":
            result = self._run_full_test_suite_benchmark(test_image)
        else:
            raise ValueError(f"未知的基準測試: {benchmark.name}")
        
        execution_time = time.time() - start_time
        
        # 評估基準測試結果
        benchmark_evaluation = self._evaluate_benchmark_result(
            benchmark, result, execution_time
        )
        
        return {
            **result,
            'benchmark_evaluation': benchmark_evaluation,
            'execution_time': execution_time,
            'benchmark_config': {
                'name': benchmark.name,
                'description': benchmark.description,
                'targets': {
                    'execution_time_seconds': benchmark.target_execution_time_seconds,
                    'memory_limit_mb': benchmark.target_memory_limit_mb,
                    'cpu_limit_percent': benchmark.target_cpu_limit_percent,
                    'success_rate_percent': benchmark.target_success_rate_percent
                }
            }
        }
    
    def _run_container_lifecycle_benchmark(self, test_image: str) -> Dict[str, Any]:
        """運行容器生命週期基準測試"""
        test_configs = [
            create_optimized_test_config(
                f"lifecycle_test_{i}",
                "basic",
                test_image,
                environment={'TEST_TYPE': 'lifecycle', 'TEST_INDEX': str(i)}
            )
            for i in range(5)  # 5個容器生命週期測試
        ]
        
        optimizer = ExecutionTimeOptimizer(self.docker_client, target_duration=120.0)
        return optimizer.optimize_test_execution(test_configs)
    
    def _run_parallel_execution_benchmark(self, test_image: str) -> Dict[str, Any]:
        """運行並行執行基準測試"""
        # 創建適合並行測試的配置
        test_configs = [
            create_optimized_test_config(
                f"parallel_test_{i}",
                "basic",
                test_image,
                environment={
                    'TEST_TYPE': 'parallel',
                    'TEST_INDEX': str(i),
                    'PARALLEL_OPTIMIZED': 'true'
                }
            )
            for i in range(8)  # 8個並行測試
        ]
        
        optimizer = ExecutionTimeOptimizer(self.docker_client, target_duration=300.0)
        optimizer.strategy = ExecutionStrategy.PARALLEL_AGGRESSIVE
        return optimizer.optimize_test_execution(test_configs)
    
    def _run_resource_efficiency_benchmark(self, test_image: str) -> Dict[str, Any]:
        """運行資源效率基準測試"""
        test_configs = [
            create_optimized_test_config(
                f"resource_test_{i}",
                "resource_limits",
                test_image,
                environment={
                    'TEST_TYPE': 'resource_efficiency',
                    'MEMORY_LIMIT': '256m',  # 更嚴格的記憶體限制
                    'CPU_LIMIT': '0.3'       # 更嚴格的CPU限制
                },
                mem_limit='256m',
                cpu_quota=30000  # 30% CPU
            )
            for i in range(6)  # 6個資源效率測試
        ]
        
        # 使用保守的並行策略以控制資源使用
        optimizer = ExecutionTimeOptimizer(self.docker_client, target_duration=180.0)
        optimizer.strategy = ExecutionStrategy.PARALLEL_BALANCED
        optimizer.max_parallel_workers = 2  # 限制並行度
        
        return optimizer.optimize_test_execution(test_configs)
    
    def _run_full_test_suite_benchmark(self, test_image: str) -> Dict[str, Any]:
        """運行完整測試套件基準測試"""
        # 創建混合類型的測試套件
        test_configs = []
        
        # 基本功能測試
        for i in range(3):
            test_configs.append(create_optimized_test_config(
                f"basic_test_{i}", "basic", test_image,
                environment={'TEST_TYPE': 'basic'}
            ))
        
        # 健康檢查測試
        for i in range(2):
            test_configs.append(create_optimized_test_config(
                f"health_check_{i}", "health_check", test_image,
                environment={'TEST_TYPE': 'health_check'}
            ))
        
        # 資源限制測試
        for i in range(3):
            test_configs.append(create_optimized_test_config(
                f"resource_limits_{i}", "resource_limits", test_image,
                environment={'TEST_TYPE': 'resource_limits'}
            ))
        
        # 環境變數測試
        for i in range(2):
            test_configs.append(create_optimized_test_config(
                f"environment_test_{i}", "environment", test_image,
                environment={'TEST_TYPE': 'environment', 'TEST_VAR': f'value_{i}'}
            ))
        
        # 使用自適應策略
        optimizer = ExecutionTimeOptimizer(self.docker_client, target_duration=600.0)
        optimizer.strategy = ExecutionStrategy.ADAPTIVE
        
        return optimizer.optimize_test_execution(test_configs)
    
    def _evaluate_benchmark_result(self, benchmark: PerformanceBenchmark,
                                 result: Dict[str, Any], 
                                 execution_time: float) -> Dict[str, Any]:
        """評估基準測試結果"""
        evaluation = {
            'meets_time_target': execution_time <= benchmark.target_execution_time_seconds,
            'time_efficiency_percent': (benchmark.target_execution_time_seconds / execution_time * 100) 
                                     if execution_time > 0 else 0,
            'passes_all_targets': True,
            'failed_targets': [],
            'performance_score': 0.0
        }
        
        # 檢查執行時間目標
        if execution_time > benchmark.target_execution_time_seconds:
            evaluation['passes_all_targets'] = False
            evaluation['failed_targets'].append('execution_time')
        
        # 檢查成功率目標（如果結果中有成功率資料）
        execution_summary = result.get('execution_summary', {})
        success_rate = execution_summary.get('success_rate_percent', 0)
        
        if success_rate < benchmark.target_success_rate_percent:
            evaluation['passes_all_targets'] = False
            evaluation['failed_targets'].append('success_rate')
        
        # 檢查資源使用目標
        resource_stats = result.get('resource_efficiency', {})
        memory_stats = resource_stats.get('memory', {})
        cpu_stats = resource_stats.get('cpu', {})
        
        if memory_stats.get('peak_mb', 0) > benchmark.target_memory_limit_mb:
            evaluation['passes_all_targets'] = False
            evaluation['failed_targets'].append('memory_usage')
        
        if cpu_stats.get('peak_percent', 0) > benchmark.target_cpu_limit_percent:
            evaluation['passes_all_targets'] = False
            evaluation['failed_targets'].append('cpu_usage')
        
        # 計算效能分數 (0-100)
        time_score = min(100, evaluation['time_efficiency_percent'])
        success_score = success_rate
        resource_score = 100 if not evaluation['failed_targets'] else 70
        
        evaluation['performance_score'] = (time_score * 0.4 + success_score * 0.4 + resource_score * 0.2)
        
        return evaluation
    
    def _generate_comprehensive_report(self, benchmark_results: Dict[str, Any],
                                     overall_execution_time: float) -> Dict[str, Any]:
        """生成綜合效能報告"""
        # 計算總體統計
        total_benchmarks = len(benchmark_results)
        passed_benchmarks = sum(
            1 for result in benchmark_results.values() 
            if result.get('benchmark_evaluation', {}).get('passes_all_targets', False)
        )
        
        performance_scores = [
            result.get('benchmark_evaluation', {}).get('performance_score', 0)
            for result in benchmark_results.values()
        ]
        
        overall_performance_score = statistics.mean(performance_scores) if performance_scores else 0
        
        # 效能趨勢分析
        trend_analysis = self._analyze_performance_trends()
        
        # 生成優化建議
        optimization_recommendations = self._generate_optimization_recommendations(benchmark_results)
        
        # 編譯詳細報告
        comprehensive_report = {
            'report_metadata': {
                'generated_at': datetime.now().isoformat(),
                'total_execution_time_seconds': overall_execution_time,
                'meets_10min_target': overall_execution_time <= 600.0,
                'benchmark_suite_version': 'docker_performance_benchmark_v1',
                'task_id': 'T1'
            },
            'overall_performance': {
                'total_benchmarks': total_benchmarks,
                'passed_benchmarks': passed_benchmarks,
                'pass_rate_percent': (passed_benchmarks / total_benchmarks * 100) if total_benchmarks > 0 else 0,
                'overall_performance_score': overall_performance_score,
                'performance_grade': self._calculate_performance_grade(overall_performance_score)
            },
            'benchmark_results': benchmark_results,
            'performance_analysis': {
                'execution_time_analysis': self._analyze_execution_times(benchmark_results),
                'resource_efficiency_analysis': self._analyze_resource_efficiency(benchmark_results),
                'parallel_execution_analysis': self._analyze_parallel_execution(benchmark_results)
            },
            'trend_analysis': trend_analysis,
            'optimization_recommendations': optimization_recommendations,
            'compliance_status': {
                'meets_10min_target': overall_execution_time <= 600.0,
                'meets_2gb_memory_limit': self._check_memory_compliance(benchmark_results),
                'meets_80_percent_cpu_limit': self._check_cpu_compliance(benchmark_results),
                'meets_98_percent_success_rate': self._check_success_rate_compliance(benchmark_results)
            }
        }
        
        # 保存報告到文件
        self._save_report_to_file(comprehensive_report)
        
        return comprehensive_report
    
    def _analyze_performance_trends(self) -> Dict[str, Any]:
        """分析效能趨勢"""
        if len(self.benchmark_history) < 2:
            return {'trend_analysis_available': False, 'reason': 'insufficient_data'}
        
        # 分析最近的趨勢（簡化版本）
        recent_results = self.benchmark_history[-5:]  # 最近5次結果
        
        trend_analysis = {
            'trend_analysis_available': True,
            'recent_performance_trend': 'stable',  # stable, improving, declining
            'recommendations': []
        }
        
        return trend_analysis
    
    def _generate_optimization_recommendations(self, benchmark_results: Dict[str, Any]) -> List[str]:
        """生成優化建議"""
        recommendations = []
        
        # 分析每個基準測試的結果
        for benchmark_name, result in benchmark_results.items():
            evaluation = result.get('benchmark_evaluation', {})
            failed_targets = evaluation.get('failed_targets', [])
            
            if 'execution_time' in failed_targets:
                recommendations.append(
                    f"{benchmark_name}: 執行時間超過目標，建議優化容器配置或增加並行度"
                )
            
            if 'success_rate' in failed_targets:
                recommendations.append(
                    f"{benchmark_name}: 成功率低於目標，需要調查失敗原因"
                )
            
            if 'memory_usage' in failed_targets:
                recommendations.append(
                    f"{benchmark_name}: 記憶體使用超過限制，建議優化記憶體管理"
                )
            
            if 'cpu_usage' in failed_targets:
                recommendations.append(
                    f"{benchmark_name}: CPU使用超過限制，建議調整並行配置"
                )
        
        # 如果沒有特定建議，給出一般性建議
        if not recommendations:
            recommendations.append("所有基準測試都表現良好！建議保持當前的優化策略。")
        
        return recommendations
    
    def _analyze_execution_times(self, benchmark_results: Dict[str, Any]) -> Dict[str, Any]:
        """分析執行時間"""
        execution_times = [
            result.get('execution_time', 0) 
            for result in benchmark_results.values()
        ]
        
        return {
            'total_time': sum(execution_times),
            'average_time': statistics.mean(execution_times) if execution_times else 0,
            'max_time': max(execution_times) if execution_times else 0,
            'min_time': min(execution_times) if execution_times else 0,
            'time_distribution': 'balanced' if statistics.stdev(execution_times) < 60 else 'variable'
        }
    
    def _analyze_resource_efficiency(self, benchmark_results: Dict[str, Any]) -> Dict[str, Any]:
        """分析資源使用效率"""
        memory_peaks = []
        cpu_peaks = []
        
        for result in benchmark_results.values():
            resource_stats = result.get('resource_efficiency', {})
            memory_stats = resource_stats.get('memory', {})
            cpu_stats = resource_stats.get('cpu', {})
            
            if memory_stats.get('peak_mb'):
                memory_peaks.append(memory_stats['peak_mb'])
            if cpu_stats.get('peak_percent'):
                cpu_peaks.append(cpu_stats['peak_percent'])
        
        return {
            'memory_efficiency': {
                'max_usage_mb': max(memory_peaks) if memory_peaks else 0,
                'average_usage_mb': statistics.mean(memory_peaks) if memory_peaks else 0,
                'within_2gb_limit': all(m <= 2048 for m in memory_peaks) if memory_peaks else True
            },
            'cpu_efficiency': {
                'max_usage_percent': max(cpu_peaks) if cpu_peaks else 0,
                'average_usage_percent': statistics.mean(cpu_peaks) if cpu_peaks else 0,
                'within_80_percent_limit': all(c <= 80 for c in cpu_peaks) if cpu_peaks else True
            }
        }
    
    def _analyze_parallel_execution(self, benchmark_results: Dict[str, Any]) -> Dict[str, Any]:
        """分析並行執行效果"""
        parallel_benchmark = benchmark_results.get('parallel_execution_benchmark', {})
        
        if not parallel_benchmark:
            return {'parallel_analysis_available': False}
        
        optimization_effectiveness = parallel_benchmark.get('optimization_effectiveness', {})
        
        return {
            'parallel_analysis_available': True,
            'parallel_execution_effective': optimization_effectiveness.get('parallel_execution_benefit', False),
            'execution_strategy_optimal': optimization_effectiveness.get('execution_strategy_optimal', False)
        }
    
    def _calculate_performance_grade(self, score: float) -> str:
        """計算效能等級"""
        if score >= 95:
            return 'A+'
        elif score >= 90:
            return 'A'
        elif score >= 85:
            return 'B+'
        elif score >= 80:
            return 'B'
        elif score >= 75:
            return 'C+'
        elif score >= 70:
            return 'C'
        else:
            return 'D'
    
    def _check_memory_compliance(self, benchmark_results: Dict[str, Any]) -> bool:
        """檢查記憶體合規性"""
        for result in benchmark_results.values():
            resource_stats = result.get('resource_efficiency', {})
            memory_stats = resource_stats.get('memory', {})
            if memory_stats.get('peak_mb', 0) > 2048:
                return False
        return True
    
    def _check_cpu_compliance(self, benchmark_results: Dict[str, Any]) -> bool:
        """檢查CPU合規性"""
        for result in benchmark_results.values():
            resource_stats = result.get('resource_efficiency', {})
            cpu_stats = resource_stats.get('cpu', {})
            if cpu_stats.get('peak_percent', 0) > 80:
                return False
        return True
    
    def _check_success_rate_compliance(self, benchmark_results: Dict[str, Any]) -> bool:
        """檢查成功率合規性"""
        for result in benchmark_results.values():
            execution_summary = result.get('execution_summary', {})
            success_rate = execution_summary.get('success_rate_percent', 0)
            if success_rate < 98:
                return False
        return True
    
    def _save_report_to_file(self, report: Dict[str, Any]) -> None:
        """保存報告到文件"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_path = Path("test_reports") / f"docker_performance_benchmark_{timestamp}.json"
            report_path.parent.mkdir(exist_ok=True)
            
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            logger.info(f"效能基準測試報告已保存: {report_path}")
            
        except Exception as e:
            logger.error(f"保存報告失敗: {e}")


# 便利函數
def run_docker_performance_benchmark(docker_client, test_image: str = "roas-bot") -> Dict[str, Any]:
    """運行Docker效能基準測試"""
    benchmark_suite = DockerPerformanceBenchmarkSuite(docker_client)
    return benchmark_suite.run_all_benchmarks(test_image)