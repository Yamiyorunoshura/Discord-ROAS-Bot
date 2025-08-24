"""
T2 - 高併發連線競爭修復 - 高級效能基準測試與優化引擎
Task ID: T2

企業級效能測試和最佳化平台：
- 智慧負載測試場景生成
- 自動化效能回歸檢測
- 效能瓶頸分析和診斷
- 動態調校建議系統
- 連續效能監控平台

作者: Ethan - 效能優化專家
"""

import asyncio
import logging
import json
import time
import statistics
import uuid
from typing import Dict, List, Optional, Any, Tuple, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import threading
import psutil
import os
import sqlite3
import aiosqlite
import tempfile
from contextlib import asynccontextmanager

logger = logging.getLogger('advanced_performance_benchmark')


@dataclass
class LoadTestScenario:
    """負載測試場景定義"""
    name: str
    description: str
    concurrent_workers: int
    operations_per_worker: int
    test_duration_seconds: float
    workload_pattern: str  # "read", "write", "mixed", "ramp_up", "spike"
    read_percentage: float = 70.0
    complexity_level: str = "medium"  # "low", "medium", "high", "extreme"


@dataclass
class PerformanceBaseline:
    """效能基準線"""
    scenario_name: str
    baseline_throughput_ops: float
    baseline_response_time_p95_ms: float
    baseline_error_rate_percent: float
    memory_usage_mb: float
    cpu_usage_percent: float
    connection_efficiency: float
    recorded_at: datetime
    system_info: Dict[str, Any]


@dataclass 
class RegressionTestResult:
    """效能回歸測試結果"""
    scenario_name: str
    current_performance: Dict[str, float]
    baseline_performance: Dict[str, float]
    performance_delta: Dict[str, float]
    regression_detected: bool
    significance_score: float
    recommendations: List[str]


@dataclass
class OptimizationRecommendation:
    """最佳化建議"""
    category: str           # "connection_pool", "query", "system", "architecture"
    priority: str          # "critical", "high", "medium", "low"
    title: str
    description: str
    expected_improvement: str
    implementation_effort: str  # "low", "medium", "high"
    risk_level: str        # "low", "medium", "high"
    specific_actions: List[str]
    estimated_impact_percent: float


class SystemResourceMonitor:
    """系統資源監控器"""
    
    def __init__(self):
        self.monitoring_active = False
        self.metrics_history = []
        self.monitoring_task = None
        
    async def start_monitoring(self, interval_seconds: float = 1.0):
        """開始監控系統資源"""
        self.monitoring_active = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop(interval_seconds))
    
    async def stop_monitoring(self):
        """停止監控"""
        self.monitoring_active = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
    
    async def _monitoring_loop(self, interval_seconds: float):
        """監控循環"""
        while self.monitoring_active:
            try:
                # 收集系統指標
                cpu_percent = psutil.cpu_percent(interval=None)
                memory_info = psutil.virtual_memory()
                disk_io = psutil.disk_io_counters()
                
                metrics = {
                    'timestamp': time.time(),
                    'cpu_percent': cpu_percent,
                    'memory_percent': memory_info.percent,
                    'memory_available_mb': memory_info.available / (1024 * 1024),
                    'disk_read_mb_per_sec': 0,  # 會在下一次計算
                    'disk_write_mb_per_sec': 0
                }
                
                self.metrics_history.append(metrics)
                
                # 保持最近1000個數據點
                if len(self.metrics_history) > 1000:
                    self.metrics_history.pop(0)
                
                await asyncio.sleep(interval_seconds)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"資源監控錯誤: {e}")
    
    def get_current_metrics(self) -> Dict[str, float]:
        """獲取當前系統指標"""
        if not self.metrics_history:
            return {}
        
        recent_metrics = self.metrics_history[-10:]  # 最近10個數據點
        
        return {
            'avg_cpu_percent': statistics.mean([m['cpu_percent'] for m in recent_metrics]),
            'avg_memory_percent': statistics.mean([m['memory_percent'] for m in recent_metrics]),
            'avg_memory_available_mb': statistics.mean([m['memory_available_mb'] for m in recent_metrics])
        }


class AdvancedPerformanceBenchmarkEngine:
    """
    高級效能基準測試引擎
    
    核心功能：
    1. 智慧負載場景生成
    2. 自動化回歸檢測  
    3. 效能瓶頸診斷
    4. 動態調校建議
    5. 基準線管理
    """
    
    def __init__(self, results_dir: str = "benchmark_results"):
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        # 基準線存儲
        self.baselines: Dict[str, PerformanceBaseline] = {}
        self.baseline_db_path = self.results_dir / "performance_baselines.db"
        
        # 測試場景
        self.test_scenarios = self._create_default_scenarios()
        
        # 系統資源監控
        self.resource_monitor = SystemResourceMonitor()
        
        # 優化建議生成器
        self.recommendation_engine = PerformanceOptimizationEngine()
        
        self._init_baseline_storage()
        
        logger.info("高級效能基準測試引擎已初始化")
    
    def _init_baseline_storage(self):
        """初始化基準線存儲"""
        conn = sqlite3.connect(self.baseline_db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS performance_baselines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scenario_name TEXT NOT NULL,
                baseline_throughput_ops REAL,
                baseline_response_time_p95_ms REAL,
                baseline_error_rate_percent REAL,
                memory_usage_mb REAL,
                cpu_usage_percent REAL,
                connection_efficiency REAL,
                recorded_at TIMESTAMP,
                system_info TEXT,
                UNIQUE(scenario_name)
            )
        """)
        
        conn.commit()
        conn.close()
        
        # 載入現有基準線
        self._load_baselines()
    
    def _load_baselines(self):
        """載入現有基準線"""
        try:
            conn = sqlite3.connect(self.baseline_db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM performance_baselines")
            rows = cursor.fetchall()
            
            for row in rows:
                baseline = PerformanceBaseline(
                    scenario_name=row[1],
                    baseline_throughput_ops=row[2],
                    baseline_response_time_p95_ms=row[3],
                    baseline_error_rate_percent=row[4],
                    memory_usage_mb=row[5],
                    cpu_usage_percent=row[6],
                    connection_efficiency=row[7],
                    recorded_at=datetime.fromisoformat(row[8]),
                    system_info=json.loads(row[9]) if row[9] else {}
                )
                self.baselines[baseline.scenario_name] = baseline
            
            conn.close()
            logger.info(f"載入 {len(self.baselines)} 個效能基準線")
            
        except Exception as e:
            logger.error(f"載入基準線失敗: {e}")
    
    def _create_default_scenarios(self) -> List[LoadTestScenario]:
        """建立預設測試場景"""
        return [
            # T2 核心驗證場景
            LoadTestScenario(
                name="T2_10_workers_standard",
                description="T2標準：10個工作者併發連線競爭測試",
                concurrent_workers=10,
                operations_per_worker=100,
                test_duration_seconds=60.0,
                workload_pattern="mixed",
                read_percentage=70.0,
                complexity_level="medium"
            ),
            LoadTestScenario(
                name="T2_20_workers_extreme",
                description="T2極限：20個工作者高強度併發測試",
                concurrent_workers=20,
                operations_per_worker=150,
                test_duration_seconds=120.0,
                workload_pattern="mixed",
                read_percentage=60.0,
                complexity_level="high"
            ),
            LoadTestScenario(
                name="T2_spike_load",
                description="T2尖峰測試：模擬突發流量",
                concurrent_workers=25,
                operations_per_worker=50,
                test_duration_seconds=90.0,
                workload_pattern="spike",
                read_percentage=80.0,
                complexity_level="extreme"
            ),
            # 專業效能測試場景
            LoadTestScenario(
                name="sustained_high_load",
                description="持續高負載穩定性測試",
                concurrent_workers=15,
                operations_per_worker=200,
                test_duration_seconds=300.0,
                workload_pattern="mixed",
                read_percentage=75.0,
                complexity_level="high"
            ),
            LoadTestScenario(
                name="read_heavy_workload", 
                description="讀取密集工作負載測試",
                concurrent_workers=30,
                operations_per_worker=100,
                test_duration_seconds=120.0,
                workload_pattern="read",
                read_percentage=95.0,
                complexity_level="medium"
            ),
            LoadTestScenario(
                name="write_intensive_test",
                description="寫入密集併發測試",
                concurrent_workers=8,
                operations_per_worker=75,
                test_duration_seconds=90.0,
                workload_pattern="write", 
                read_percentage=10.0,
                complexity_level="high"
            )
        ]
    
    async def run_comprehensive_benchmark(
        self,
        pool_manager,
        scenarios: Optional[List[LoadTestScenario]] = None
    ) -> Dict[str, Any]:
        """
        執行綜合性效能基準測試
        
        包含：
        - 多場景負載測試
        - 系統資源監控
        - 回歸檢測
        - 優化建議生成
        """
        if scenarios is None:
            scenarios = self.test_scenarios
        
        logger.info(f"開始綜合效能基準測試，共 {len(scenarios)} 個場景")
        
        # 啟動系統資源監控
        await self.resource_monitor.start_monitoring()
        
        benchmark_results = {
            'start_time': datetime.now().isoformat(),
            'system_info': self._collect_system_info(),
            'scenario_results': [],
            'regression_analysis': {},
            'optimization_recommendations': [],
            'summary': {}
        }
        
        try:
            from .test_connection_pool import ConnectionPoolTestSuite
            
            # 為每個場景執行測試
            for scenario in scenarios:
                logger.info(f"執行場景: {scenario.name}")
                
                scenario_start_time = time.time()
                
                # 建立測試環境
                async with ConnectionPoolTestSuite() as test_suite:
                    await test_suite.setup_test_environment()
                    
                    # 根據場景類型執行適當的測試
                    test_result = await self._execute_scenario(test_suite, scenario)
                    
                    # 收集系統資源指標
                    system_metrics = self.resource_monitor.get_current_metrics()
                    
                    # 計算連線效率
                    pool_stats = pool_manager.get_pool_stats()
                    connection_efficiency = self._calculate_connection_efficiency(pool_stats, test_result)
                    
                    # 組合結果
                    scenario_result = {
                        'scenario': asdict(scenario),
                        'test_result': self._serialize_test_result(test_result),
                        'system_metrics': system_metrics,
                        'connection_efficiency': connection_efficiency,
                        'duration_seconds': time.time() - scenario_start_time
                    }
                    
                    benchmark_results['scenario_results'].append(scenario_result)
                    
                    # 執行回歸檢測
                    if scenario.name in self.baselines:
                        regression_result = self._analyze_regression(scenario.name, scenario_result)
                        benchmark_results['regression_analysis'][scenario.name] = regression_result
                    
                    # 更新或建立基準線
                    await self._update_baseline(scenario.name, scenario_result)
                    
                    logger.info(f"場景 {scenario.name} 完成")
            
            # 生成優化建議
            recommendations = await self._generate_optimization_recommendations(
                benchmark_results['scenario_results']
            )
            benchmark_results['optimization_recommendations'] = recommendations
            
            # 生成總結
            benchmark_results['summary'] = self._generate_benchmark_summary(benchmark_results)
            
        finally:
            # 停止系統監控
            await self.resource_monitor.stop_monitoring()
        
        benchmark_results['end_time'] = datetime.now().isoformat()
        
        # 保存結果
        self._save_benchmark_results(benchmark_results)
        
        logger.info("綜合效能基準測試完成")
        return benchmark_results
    
    async def _execute_scenario(self, test_suite, scenario: LoadTestScenario):
        """執行特定測試場景"""
        
        if scenario.workload_pattern == "read":
            return await test_suite.run_concurrent_read_test(
                num_workers=scenario.concurrent_workers,
                operations_per_worker=scenario.operations_per_worker
            )
        
        elif scenario.workload_pattern == "write":
            return await test_suite.run_concurrent_write_test(
                num_workers=scenario.concurrent_workers,
                operations_per_worker=scenario.operations_per_worker
            )
        
        elif scenario.workload_pattern == "mixed":
            return await test_suite.run_mixed_workload_test(
                num_workers=scenario.concurrent_workers,
                read_percentage=scenario.read_percentage,
                test_duration=scenario.test_duration_seconds
            )
        
        elif scenario.workload_pattern == "spike" or scenario.workload_pattern == "ramp_up":
            return await test_suite.run_stress_test(
                max_workers=scenario.concurrent_workers,
                test_duration=scenario.test_duration_seconds
            )
        
        else:
            # 預設為混合測試
            return await test_suite.run_mixed_workload_test(
                num_workers=scenario.concurrent_workers,
                read_percentage=scenario.read_percentage,
                test_duration=scenario.test_duration_seconds
            )
    
    def _calculate_connection_efficiency(self, pool_stats: Dict, test_result) -> float:
        """計算連線池效率"""
        try:
            total_connections = pool_stats.get('active_connections', 0) + pool_stats.get('idle_connections', 0)
            max_connections = pool_stats.get('max_connections', 1)
            
            if max_connections == 0:
                return 0.0
            
            # 連線利用率
            utilization_ratio = total_connections / max_connections
            
            # 成功率
            success_rate = 1.0 - (test_result.error_rate_percentage / 100.0)
            
            # 響應時間效率（50ms為基準）
            response_efficiency = min(50.0 / max(test_result.average_response_time_ms, 1), 1.0)
            
            # 綜合效率分數
            efficiency = (utilization_ratio * 0.3 + success_rate * 0.4 + response_efficiency * 0.3) * 100
            
            return min(max(efficiency, 0), 100)
            
        except Exception as e:
            logger.error(f"計算連線效率失敗: {e}")
            return 0.0
    
    def _analyze_regression(self, scenario_name: str, current_result: Dict) -> RegressionTestResult:
        """分析效能回歸"""
        baseline = self.baselines.get(scenario_name)
        if not baseline:
            return RegressionTestResult(
                scenario_name=scenario_name,
                current_performance={},
                baseline_performance={},
                performance_delta={},
                regression_detected=False,
                significance_score=0.0,
                recommendations=["首次執行，建立基準線"]
            )
        
        # 提取效能指標
        current_perf = self._extract_performance_metrics(current_result)
        baseline_perf = {
            'throughput_ops': baseline.baseline_throughput_ops,
            'response_time_p95_ms': baseline.baseline_response_time_p95_ms,
            'error_rate_percent': baseline.baseline_error_rate_percent,
            'connection_efficiency': baseline.connection_efficiency
        }
        
        # 計算變化量
        performance_delta = {}
        for metric in current_perf:
            if metric in baseline_perf:
                delta = ((current_perf[metric] - baseline_perf[metric]) / baseline_perf[metric]) * 100
                performance_delta[metric] = delta
        
        # 回歸檢測邏輯
        regression_detected = False
        significance_score = 0.0
        recommendations = []
        
        # 吞吐量下降 > 10%
        if performance_delta.get('throughput_ops', 0) < -10:
            regression_detected = True
            significance_score += 30
            recommendations.append("吞吐量顯著下降，檢查連線池配置和查詢效率")
        
        # 響應時間增加 > 20%
        if performance_delta.get('response_time_p95_ms', 0) > 20:
            regression_detected = True
            significance_score += 40
            recommendations.append("響應時間顯著增加，分析系統負載和連線爭用")
        
        # 錯誤率增加 > 50%
        if performance_delta.get('error_rate_percent', 0) > 50:
            regression_detected = True
            significance_score += 50
            recommendations.append("錯誤率異常增高，優先檢查連線穩定性")
        
        if not regression_detected:
            recommendations.append("效能表現穩定，無顯著回歸")
        
        return RegressionTestResult(
            scenario_name=scenario_name,
            current_performance=current_perf,
            baseline_performance=baseline_perf,
            performance_delta=performance_delta,
            regression_detected=regression_detected,
            significance_score=significance_score,
            recommendations=recommendations
        )
    
    async def _update_baseline(self, scenario_name: str, scenario_result: Dict):
        """更新或建立效能基準線"""
        try:
            perf_metrics = self._extract_performance_metrics(scenario_result)
            system_metrics = scenario_result.get('system_metrics', {})
            
            baseline = PerformanceBaseline(
                scenario_name=scenario_name,
                baseline_throughput_ops=perf_metrics.get('throughput_ops', 0),
                baseline_response_time_p95_ms=perf_metrics.get('response_time_p95_ms', 0),
                baseline_error_rate_percent=perf_metrics.get('error_rate_percent', 0),
                memory_usage_mb=system_metrics.get('avg_memory_available_mb', 0),
                cpu_usage_percent=system_metrics.get('avg_cpu_percent', 0),
                connection_efficiency=scenario_result.get('connection_efficiency', 0),
                recorded_at=datetime.now(),
                system_info=self._collect_system_info()
            )
            
            # 更新內存中的基準線
            self.baselines[scenario_name] = baseline
            
            # 保存到數據庫
            conn = sqlite3.connect(self.baseline_db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO performance_baselines 
                (scenario_name, baseline_throughput_ops, baseline_response_time_p95_ms,
                 baseline_error_rate_percent, memory_usage_mb, cpu_usage_percent,
                 connection_efficiency, recorded_at, system_info)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                baseline.scenario_name,
                baseline.baseline_throughput_ops,
                baseline.baseline_response_time_p95_ms, 
                baseline.baseline_error_rate_percent,
                baseline.memory_usage_mb,
                baseline.cpu_usage_percent,
                baseline.connection_efficiency,
                baseline.recorded_at.isoformat(),
                json.dumps(baseline.system_info)
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"已更新場景 {scenario_name} 的效能基準線")
            
        except Exception as e:
            logger.error(f"更新基準線失敗: {e}")
    
    async def _generate_optimization_recommendations(
        self, 
        scenario_results: List[Dict]
    ) -> List[OptimizationRecommendation]:
        """生成效能優化建議"""
        recommendations = []
        
        # 分析整體效能模式
        throughputs = []
        response_times = []
        error_rates = []
        connection_efficiencies = []
        
        for result in scenario_results:
            metrics = self._extract_performance_metrics(result)
            throughputs.append(metrics.get('throughput_ops', 0))
            response_times.append(metrics.get('response_time_p95_ms', 0))
            error_rates.append(metrics.get('error_rate_percent', 0))
            connection_efficiencies.append(result.get('connection_efficiency', 0))
        
        avg_throughput = statistics.mean(throughputs) if throughputs else 0
        avg_response_time = statistics.mean(response_times) if response_times else 0
        avg_error_rate = statistics.mean(error_rates) if error_rates else 0
        avg_connection_efficiency = statistics.mean(connection_efficiencies) if connection_efficiencies else 0
        
        # 基於分析結果生成建議
        
        # 連線池優化建議
        if avg_connection_efficiency < 60:
            recommendations.append(OptimizationRecommendation(
                category="connection_pool",
                priority="high",
                title="連線池效率優化",
                description="連線池整體效率偏低，建議調整連線池參數配置",
                expected_improvement="提升 15-25% 整體效能",
                implementation_effort="medium",
                risk_level="low",
                specific_actions=[
                    "增加最小連線數到 5",
                    "將最大連線數調整到 25",
                    "縮短連線獲取超時時間到 5秒",
                    "啟用連線健康檢查"
                ],
                estimated_impact_percent=20.0
            ))
        
        # 響應時間優化建議
        if avg_response_time > 50:
            recommendations.append(OptimizationRecommendation(
                category="query",
                priority="high",
                title="響應時間優化",
                description="系統響應時間超過50ms基準，需要查詢和系統層面優化",
                expected_improvement="降低響應時間 30-40%",
                implementation_effort="high",
                risk_level="medium",
                specific_actions=[
                    "分析和優化慢查詢",
                    "添加適當的資料庫索引", 
                    "實施查詢結果緩存",
                    "考慮讀寫分離架構"
                ],
                estimated_impact_percent=35.0
            ))
        
        # 錯誤率優化建議
        if avg_error_rate > 1.0:
            recommendations.append(OptimizationRecommendation(
                category="system",
                priority="critical",
                title="系統穩定性提升",
                description="錯誤率超過1%基準，需要系統穩定性改進",
                expected_improvement="錯誤率降至 0.5% 以下",
                implementation_effort="high", 
                risk_level="high",
                specific_actions=[
                    "實施重試機制",
                    "添加斷路器模式",
                    "強化錯誤處理邏輯",
                    "增加系統監控告警"
                ],
                estimated_impact_percent=40.0
            ))
        
        # 吞吐量優化建議
        if avg_throughput < 100:
            recommendations.append(OptimizationRecommendation(
                category="architecture",
                priority="medium",
                title="吞吐量提升",
                description="系統吞吐量低於100 ops/s基準，建議架構層面改進",
                expected_improvement="吞吐量提升 50-80%",
                implementation_effort="high",
                risk_level="medium",
                specific_actions=[
                    "實施異步處理模式",
                    "增加並行處理能力",
                    "優化資料庫連線管理",
                    "考慮分散式處理"
                ],
                estimated_impact_percent=60.0
            ))
        
        return recommendations
    
    def _extract_performance_metrics(self, scenario_result: Dict) -> Dict[str, float]:
        """從場景結果中提取效能指標"""
        test_result = scenario_result.get('test_result', {})
        
        return {
            'throughput_ops': test_result.get('operations_per_second', 0),
            'response_time_p95_ms': test_result.get('p95_response_time_ms', 0),
            'response_time_avg_ms': test_result.get('average_response_time_ms', 0),
            'error_rate_percent': test_result.get('error_rate_percentage', 0),
            'total_operations': test_result.get('total_operations', 0),
            'successful_operations': test_result.get('successful_operations', 0)
        }
    
    def _serialize_test_result(self, test_result) -> Dict:
        """序列化測試結果"""
        return {
            'test_name': getattr(test_result, 'test_name', ''),
            'duration_seconds': getattr(test_result, 'duration_seconds', 0),
            'total_operations': getattr(test_result, 'total_operations', 0),
            'successful_operations': getattr(test_result, 'successful_operations', 0),
            'failed_operations': getattr(test_result, 'failed_operations', 0),
            'operations_per_second': getattr(test_result, 'operations_per_second', 0),
            'average_response_time_ms': getattr(test_result, 'average_response_time_ms', 0),
            'p50_response_time_ms': getattr(test_result, 'p50_response_time_ms', 0),
            'p95_response_time_ms': getattr(test_result, 'p95_response_time_ms', 0),
            'p99_response_time_ms': getattr(test_result, 'p99_response_time_ms', 0),
            'error_rate_percentage': getattr(test_result, 'error_rate_percentage', 0),
            'concurrent_workers': getattr(test_result, 'concurrent_workers', 0),
            'max_connections_used': getattr(test_result, 'max_connections_used', 0)
        }
    
    def _collect_system_info(self) -> Dict[str, Any]:
        """收集系統資訊"""
        return {
            'cpu_count': psutil.cpu_count(),
            'total_memory_mb': psutil.virtual_memory().total / (1024 * 1024),
            'platform': os.name,
            'python_version': f"{os.sys.version_info.major}.{os.sys.version_info.minor}",
            'timestamp': datetime.now().isoformat()
        }
    
    def _generate_benchmark_summary(self, benchmark_results: Dict) -> Dict[str, Any]:
        """生成基準測試總結"""
        scenario_results = benchmark_results.get('scenario_results', [])
        
        if not scenario_results:
            return {'status': 'no_results'}
        
        # 提取關鍵指標
        throughputs = []
        response_times = []
        error_rates = []
        
        for result in scenario_results:
            metrics = self._extract_performance_metrics(result)
            throughputs.append(metrics['throughput_ops'])
            response_times.append(metrics['response_time_p95_ms'])
            error_rates.append(metrics['error_rate_percent'])
        
        # T2 合規性檢查
        t2_compliant_tests = 0
        for result in scenario_results:
            metrics = self._extract_performance_metrics(result)
            if (metrics['error_rate_percent'] <= 1.0 and 
                metrics['response_time_p95_ms'] <= 50.0):
                t2_compliant_tests += 1
        
        return {
            'total_scenarios': len(scenario_results),
            't2_compliant_scenarios': t2_compliant_tests,
            't2_compliance_rate': (t2_compliant_tests / len(scenario_results)) * 100,
            'performance_summary': {
                'avg_throughput_ops': statistics.mean(throughputs),
                'max_throughput_ops': max(throughputs),
                'avg_response_time_p95_ms': statistics.mean(response_times),
                'min_response_time_p95_ms': min(response_times),
                'avg_error_rate': statistics.mean(error_rates),
                'max_error_rate': max(error_rates)
            },
            'regression_count': len([r for r in benchmark_results.get('regression_analysis', {}).values() 
                                  if r.get('regression_detected', False)]),
            'recommendation_count': len(benchmark_results.get('optimization_recommendations', [])),
            'overall_grade': 'PASS' if t2_compliant_tests == len(scenario_results) else 'PARTIAL' if t2_compliant_tests > 0 else 'FAIL'
        }
    
    def _save_benchmark_results(self, results: Dict[str, Any]):
        """保存基準測試結果"""
        timestamp = int(time.time())
        result_file = self.results_dir / f"comprehensive_benchmark_{timestamp}.json"
        
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"基準測試結果已保存: {result_file}")


class PerformanceOptimizationEngine:
    """效能優化引擎"""
    
    def __init__(self):
        self.optimization_rules = self._load_optimization_rules()
    
    def _load_optimization_rules(self) -> Dict[str, Any]:
        """載入優化規則庫"""
        return {
            'connection_pool': {
                'low_efficiency': {
                    'threshold': 60,
                    'recommendations': [
                        "調整連線池大小",
                        "優化連線獲取邏輯",
                        "實施連線預熱"
                    ]
                },
                'high_contention': {
                    'threshold': 10,  # 等待請求數
                    'recommendations': [
                        "增加最大連線數",
                        "實施連線優先級",
                        "添加連線負載平衡"
                    ]
                }
            },
            'response_time': {
                'slow_queries': {
                    'threshold': 50,  # ms
                    'recommendations': [
                        "查詢優化",
                        "索引優化",
                        "緩存實施"
                    ]
                }
            }
        }