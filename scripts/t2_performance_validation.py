"""
T2 - 高併發連線競爭修復 - 效能驗證和優化執行腳本
Task ID: T2

專業效能驗證執行器：
- 整合所有效能優化組件
- 自動化T2需求驗證
- 生成專業效能分析報告
- 提供系統調校建議
- 驗證併發錯誤率 ≤ 1% 目標

作者: Ethan - 效能優化專家
"""

import asyncio
import logging
import json
import os
import sys
import time
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
import argparse

# 添加專案路徑
current_dir = Path(__file__).parent
project_root = current_dir.parent.parent
sys.path.append(str(project_root))

from services.connection_pool.connection_pool_manager import ConnectionPoolManager, PoolConfiguration
from services.connection_pool.adaptive_algorithm import AdaptiveScalingAlgorithm, CompetitionAwareScheduler
from services.connection_pool.performance_monitor import AdvancedPerformanceMonitor
from services.connection_pool.advanced_benchmark_engine import AdvancedPerformanceBenchmarkEngine
from tests.concurrency.test_connection_pool import ConnectionPoolTestSuite

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('performance_validation')


class T2PerformanceValidator:
    """
    T2任務效能驗證器
    
    專業功能：
    1. 自動化T2需求驗證
    2. 併發錯誤率測試
    3. 響應時間基準驗證
    4. 系統負載能力評估
    5. 專業效能分析報告
    """
    
    def __init__(self, results_dir: str = "t2_validation_results"):
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        # T2 目標要求
        self.t2_requirements = {
            'max_error_rate_percent': 1.0,       # 併發錯誤率 ≤ 1%
            'max_p95_response_time_ms': 50.0,    # P95響應時間 ≤ 50ms
            'min_concurrent_workers': 10,        # 支援10+工作者併發
            'target_concurrent_workers': 20,     # 目標20+工作者併發
            'min_throughput_ops_per_sec': 100,   # 最低吞吐量要求
            'min_success_rate_percent': 99.0     # 最低成功率要求
        }
        
        # 驗證結果
        self.validation_results = {
            'start_time': None,
            'end_time': None,
            'system_info': {},
            'test_results': [],
            'compliance_analysis': {},
            'performance_summary': {},
            'optimization_recommendations': [],
            'final_verdict': 'PENDING'
        }
        
        logger.info("T2效能驗證器已初始化")
        logger.info(f"T2目標要求: {json.dumps(self.t2_requirements, indent=2, ensure_ascii=False)}")
    
    async def run_full_validation(self) -> Dict[str, Any]:
        """
        執行完整的T2效能驗證
        
        驗證流程：
        1. 系統基礎驗證
        2. 10+工作者併發測試  
        3. 20+工作者極限測試
        4. 混合負載穩定性測試
        5. 效能回歸分析
        6. 優化建議生成
        """
        self.validation_results['start_time'] = datetime.now().isoformat()
        self.validation_results['system_info'] = self._collect_system_info()
        
        logger.info("🚀 開始T2效能驗證流程")
        
        try:
            # 階段1: 基礎效能驗證
            logger.info("📋 階段1: 基礎效能驗證")
            basic_results = await self._run_basic_performance_test()
            self.validation_results['test_results'].append(basic_results)
            
            # 階段2: T2標準併發測試 (10工作者)
            logger.info("⚡ 階段2: T2標準併發測試 (10工作者)")
            standard_results = await self._run_t2_standard_concurrency_test()
            self.validation_results['test_results'].append(standard_results)
            
            # 階段3: T2極限併發測試 (20工作者)
            logger.info("🔥 階段3: T2極限併發測試 (20工作者)")
            extreme_results = await self._run_t2_extreme_concurrency_test()
            self.validation_results['test_results'].append(extreme_results)
            
            # 階段4: 混合負載穩定性測試
            logger.info("🔄 階段4: 混合負載穩定性測試")
            stability_results = await self._run_stability_test()
            self.validation_results['test_results'].append(stability_results)
            
            # 階段5: 壓力極限測試
            logger.info("💥 階段5: 壓力極限測試")  
            stress_results = await self._run_stress_limit_test()
            self.validation_results['test_results'].append(stress_results)
            
            # 分析合規性
            logger.info("📊 分析T2合規性")
            self.validation_results['compliance_analysis'] = self._analyze_t2_compliance()
            
            # 生成效能總結
            logger.info("📈 生成效能總結")
            self.validation_results['performance_summary'] = self._generate_performance_summary()
            
            # 生成優化建議
            logger.info("💡 生成優化建議")
            self.validation_results['optimization_recommendations'] = await self._generate_optimization_recommendations()
            
            # 最終裁決
            self.validation_results['final_verdict'] = self._make_final_verdict()
            
        except Exception as e:
            logger.error(f"驗證過程發生錯誤: {e}")
            self.validation_results['error'] = str(e)
            self.validation_results['final_verdict'] = 'ERROR'
        
        finally:
            self.validation_results['end_time'] = datetime.now().isoformat()
        
        # 保存驗證報告
        self._save_validation_report()
        
        # 輸出最終結果
        self._print_final_results()
        
        logger.info("✅ T2效能驗證完成")
        return self.validation_results
    
    async def _run_basic_performance_test(self) -> Dict[str, Any]:
        """執行基礎效能測試"""
        logger.info("執行基礎效能測試: 5工作者, 50操作/工作者")
        
        pool_config = PoolConfiguration(
            min_connections=2,
            max_connections=15,
            connection_timeout=30.0,
            acquire_timeout=10.0,
            enable_monitoring=True
        )
        
        async with ConnectionPoolTestSuite() as test_suite:
            await test_suite.setup_test_environment(pool_config)
            
            # 預熱連線池
            await self._warmup_connection_pool(test_suite)
            
            # 執行讀取測試
            read_result = await test_suite.run_concurrent_read_test(
                num_workers=5,
                operations_per_worker=50
            )
            
            # 執行寫入測試
            write_result = await test_suite.run_concurrent_write_test(
                num_workers=3,
                operations_per_worker=30
            )
            
            return {
                'test_phase': 'basic_performance',
                'read_test': self._serialize_test_result(read_result),
                'write_test': self._serialize_test_result(write_result),
                'timestamp': datetime.now().isoformat()
            }
    
    async def _run_t2_standard_concurrency_test(self) -> Dict[str, Any]:
        """執行T2標準併發測試 - 10+工作者"""
        logger.info("執行T2標準併發測試: 10工作者, 100操作/工作者")
        
        # 優化的連線池配置
        pool_config = PoolConfiguration(
            min_connections=5,
            max_connections=20,
            connection_timeout=30.0,
            acquire_timeout=5.0,
            enable_monitoring=True
        )
        
        async with ConnectionPoolTestSuite() as test_suite:
            await test_suite.setup_test_environment(pool_config)
            
            # 預熱系統
            await self._warmup_connection_pool(test_suite)
            
            # 混合工作負載測試 - 這是T2的核心驗證
            mixed_result = await test_suite.run_mixed_workload_test(
                num_workers=10,
                read_percentage=70.0,
                test_duration=120.0  # 2分鐘穩定測試
            )
            
            # 併發讀取壓力測試
            read_result = await test_suite.run_concurrent_read_test(
                num_workers=12,
                operations_per_worker=80
            )
            
            return {
                'test_phase': 't2_standard_concurrency',
                'target_workers': 10,
                'mixed_workload_test': self._serialize_test_result(mixed_result),
                'concurrent_read_test': self._serialize_test_result(read_result),
                't2_compliance_check': self._check_t2_compliance(mixed_result),
                'timestamp': datetime.now().isoformat()
            }
    
    async def _run_t2_extreme_concurrency_test(self) -> Dict[str, Any]:
        """執行T2極限併發測試 - 20+工作者"""
        logger.info("執行T2極限併發測試: 20工作者, 極限負載")
        
        # 最大化連線池配置
        pool_config = PoolConfiguration(
            min_connections=8,
            max_connections=25,
            connection_timeout=30.0,
            acquire_timeout=8.0,
            enable_monitoring=True
        )
        
        async with ConnectionPoolTestSuite() as test_suite:
            await test_suite.setup_test_environment(pool_config)
            
            # 預熱系統到最佳狀態
            await self._warmup_connection_pool(test_suite)
            
            # 20工作者混合測試
            extreme_mixed_result = await test_suite.run_mixed_workload_test(
                num_workers=20,
                read_percentage=65.0,
                test_duration=180.0  # 3分鐘極限測試
            )
            
            # 壓力測試：漸進式增加到25工作者
            stress_result = await test_suite.run_stress_test(
                max_workers=25,
                ramp_up_duration=30.0,
                test_duration=150.0
            )
            
            return {
                'test_phase': 't2_extreme_concurrency',
                'target_workers': 20,
                'extreme_mixed_test': self._serialize_test_result(extreme_mixed_result),
                'stress_ramp_test': self._serialize_test_result(stress_result),
                't2_compliance_check': self._check_t2_compliance(extreme_mixed_result),
                'timestamp': datetime.now().isoformat()
            }
    
    async def _run_stability_test(self) -> Dict[str, Any]:
        """執行穩定性測試"""
        logger.info("執行穩定性測試: 持續負載, 長時間運行")
        
        pool_config = PoolConfiguration(
            min_connections=6,
            max_connections=22,
            connection_timeout=30.0,
            acquire_timeout=6.0,
            enable_monitoring=True
        )
        
        async with ConnectionPoolTestSuite() as test_suite:
            await test_suite.setup_test_environment(pool_config)
            
            # 長時間穩定性測試 - 15工作者持續5分鐘
            stability_result = await test_suite.run_mixed_workload_test(
                num_workers=15,
                read_percentage=75.0,
                test_duration=300.0  # 5分鐘持續測試
            )
            
            return {
                'test_phase': 'stability_test',
                'duration_minutes': 5,
                'stability_result': self._serialize_test_result(stability_result),
                't2_compliance_check': self._check_t2_compliance(stability_result),
                'timestamp': datetime.now().isoformat()
            }
    
    async def _run_stress_limit_test(self) -> Dict[str, Any]:
        """執行壓力極限測試"""
        logger.info("執行壓力極限測試: 尋找系統極限")
        
        pool_config = PoolConfiguration(
            min_connections=10,
            max_connections=30,
            connection_timeout=30.0,
            acquire_timeout=10.0,
            enable_monitoring=True
        )
        
        async with ConnectionPoolTestSuite() as test_suite:
            await test_suite.setup_test_environment(pool_config)
            
            # 極限測試：30工作者
            limit_result = await test_suite.run_stress_test(
                max_workers=30,
                ramp_up_duration=45.0,
                test_duration=120.0
            )
            
            return {
                'test_phase': 'stress_limit_test',
                'max_workers_tested': 30,
                'limit_stress_result': self._serialize_test_result(limit_result),
                'system_limit_analysis': self._analyze_system_limits(limit_result),
                'timestamp': datetime.now().isoformat()
            }
    
    async def _warmup_connection_pool(self, test_suite, warmup_operations: int = 20):
        """預熱連線池"""
        logger.debug("預熱連線池...")
        
        try:
            # 執行少量操作預熱
            warmup_result = await test_suite.run_concurrent_read_test(
                num_workers=3,
                operations_per_worker=warmup_operations
            )
            logger.debug(f"預熱完成: {warmup_result.successful_operations} 操作成功")
        except Exception as e:
            logger.warning(f"預熱過程發生錯誤: {e}")
    
    def _serialize_test_result(self, test_result) -> Dict[str, Any]:
        """序列化測試結果"""
        if not test_result:
            return {}
        
        return {
            'test_name': getattr(test_result, 'test_name', ''),
            'duration_seconds': getattr(test_result, 'duration_seconds', 0),
            'concurrent_workers': getattr(test_result, 'concurrent_workers', 0),
            'total_operations': getattr(test_result, 'total_operations', 0),
            'successful_operations': getattr(test_result, 'successful_operations', 0),
            'failed_operations': getattr(test_result, 'failed_operations', 0),
            'operations_per_second': getattr(test_result, 'operations_per_second', 0),
            'average_response_time_ms': getattr(test_result, 'average_response_time_ms', 0),
            'p50_response_time_ms': getattr(test_result, 'p50_response_time_ms', 0),
            'p95_response_time_ms': getattr(test_result, 'p95_response_time_ms', 0),
            'p99_response_time_ms': getattr(test_result, 'p99_response_time_ms', 0),
            'error_rate_percentage': getattr(test_result, 'error_rate_percentage', 0),
            'max_connections_used': getattr(test_result, 'max_connections_used', 0),
            'timestamp': getattr(test_result, 'timestamp', datetime.now()).isoformat()
        }
    
    def _check_t2_compliance(self, test_result) -> Dict[str, Any]:
        """檢查T2合規性"""
        if not test_result:
            return {'compliant': False, 'reason': 'No test result'}
        
        error_rate = getattr(test_result, 'error_rate_percentage', 100)
        p95_response_time = getattr(test_result, 'p95_response_time_ms', 1000)
        workers = getattr(test_result, 'concurrent_workers', 0)
        success_rate = (getattr(test_result, 'successful_operations', 0) / 
                       max(getattr(test_result, 'total_operations', 1), 1)) * 100
        
        compliance_checks = {
            'error_rate_ok': error_rate <= self.t2_requirements['max_error_rate_percent'],
            'response_time_ok': p95_response_time <= self.t2_requirements['max_p95_response_time_ms'],
            'workers_ok': workers >= self.t2_requirements['min_concurrent_workers'],
            'success_rate_ok': success_rate >= self.t2_requirements['min_success_rate_percent']
        }
        
        all_compliant = all(compliance_checks.values())
        
        return {
            'compliant': all_compliant,
            'checks': compliance_checks,
            'metrics': {
                'error_rate_percent': error_rate,
                'p95_response_time_ms': p95_response_time,
                'concurrent_workers': workers,
                'success_rate_percent': success_rate
            },
            'requirements': self.t2_requirements
        }
    
    def _analyze_t2_compliance(self) -> Dict[str, Any]:
        """分析整體T2合規性"""
        compliant_tests = 0
        total_tests = 0
        detailed_analysis = {}
        
        for test_result in self.validation_results['test_results']:
            # 分析每個測試階段的合規性
            phase = test_result.get('test_phase', 'unknown')
            
            if 't2_compliance_check' in test_result:
                compliance = test_result['t2_compliance_check']
                detailed_analysis[phase] = compliance
                
                if compliance.get('compliant', False):
                    compliant_tests += 1
                total_tests += 1
        
        overall_compliance_rate = (compliant_tests / total_tests * 100) if total_tests > 0 else 0
        
        return {
            'overall_compliant': overall_compliance_rate >= 80,  # 80%以上測試通過
            'compliance_rate_percent': overall_compliance_rate,
            'compliant_tests': compliant_tests,
            'total_tests': total_tests,
            'detailed_analysis': detailed_analysis,
            't2_requirements': self.t2_requirements
        }
    
    def _generate_performance_summary(self) -> Dict[str, Any]:
        """生成效能總結"""
        all_throughputs = []
        all_response_times = []
        all_error_rates = []
        max_workers_tested = 0
        
        for test_result in self.validation_results['test_results']:
            # 從各種測試結果中提取指標
            for test_key in test_result:
                if test_key.endswith('_test') or test_key.endswith('_result'):
                    test_data = test_result[test_key]
                    if isinstance(test_data, dict):
                        all_throughputs.append(test_data.get('operations_per_second', 0))
                        all_response_times.append(test_data.get('p95_response_time_ms', 0))
                        all_error_rates.append(test_data.get('error_rate_percentage', 0))
                        max_workers_tested = max(max_workers_tested, 
                                               test_data.get('concurrent_workers', 0))
        
        # 過濾無效數據
        all_throughputs = [t for t in all_throughputs if t > 0]
        all_response_times = [r for r in all_response_times if r > 0]
        all_error_rates = [e for e in all_error_rates if e >= 0]
        
        import statistics
        
        return {
            'performance_metrics': {
                'max_throughput_ops_per_sec': max(all_throughputs) if all_throughputs else 0,
                'avg_throughput_ops_per_sec': statistics.mean(all_throughputs) if all_throughputs else 0,
                'min_response_time_p95_ms': min(all_response_times) if all_response_times else 0,
                'avg_response_time_p95_ms': statistics.mean(all_response_times) if all_response_times else 0,
                'max_error_rate_percent': max(all_error_rates) if all_error_rates else 0,
                'avg_error_rate_percent': statistics.mean(all_error_rates) if all_error_rates else 0
            },
            'test_coverage': {
                'max_workers_tested': max_workers_tested,
                'total_test_phases': len(self.validation_results['test_results']),
                'meets_10_worker_requirement': max_workers_tested >= 10,
                'meets_20_worker_target': max_workers_tested >= 20
            }
        }
    
    async def _generate_optimization_recommendations(self) -> List[Dict[str, Any]]:
        """生成優化建議"""
        recommendations = []
        
        # 基於測試結果分析性能瓶頸
        perf_summary = self.validation_results['performance_summary']
        
        if perf_summary:
            metrics = perf_summary.get('performance_metrics', {})
            
            # 錯誤率建議
            max_error_rate = metrics.get('max_error_rate_percent', 0)
            if max_error_rate > 1.0:
                recommendations.append({
                    'category': 'reliability',
                    'priority': 'critical',
                    'title': '併發錯誤率過高',
                    'description': f'檢測到最大錯誤率為 {max_error_rate:.2f}%，超過1%的T2要求',
                    'actions': [
                        '實施連線重試機制',
                        '增強錯誤恢復邏輯',
                        '添加連線健康檢查',
                        '優化連線池配置'
                    ]
                })
            
            # 響應時間建議
            avg_response_time = metrics.get('avg_response_time_p95_ms', 0)
            if avg_response_time > 50:
                recommendations.append({
                    'category': 'performance',
                    'priority': 'high',
                    'title': '響應時間優化',
                    'description': f'平均P95響應時間為 {avg_response_time:.2f}ms，超過50ms基準',
                    'actions': [
                        '優化資料庫查詢效率',
                        '增加連線池預分配',
                        '實施查詢結果緩存',
                        '調整連線獲取超時參數'
                    ]
                })
            
            # 吞吐量建議
            max_throughput = metrics.get('max_throughput_ops_per_sec', 0)
            if max_throughput < 200:
                recommendations.append({
                    'category': 'scalability',
                    'priority': 'medium',
                    'title': '吞吐量提升',
                    'description': f'最大吞吐量為 {max_throughput:.2f} ops/s，有提升空間',
                    'actions': [
                        '增加連線池最大大小',
                        '實施異步操作模式',
                        '優化業務邏輯處理',
                        '考慮分片或分散式處理'
                    ]
                })
        
        # 如果沒有問題，提供一般性建議
        if not recommendations:
            recommendations.append({
                'category': 'maintenance',
                'priority': 'low',
                'title': '持續優化',
                'description': '系統表現良好，建議進行持續監控和維護',
                'actions': [
                    '定期執行效能基準測試',
                    '監控生產環境指標',
                    '保持依賴項目更新',
                    '定期檢查連線池配置'
                ]
            })
        
        return recommendations
    
    def _analyze_system_limits(self, stress_result) -> Dict[str, Any]:
        """分析系統極限"""
        if not stress_result:
            return {'analysis': 'No stress test result available'}
        
        error_rate = getattr(stress_result, 'error_rate_percentage', 0)
        workers = getattr(stress_result, 'concurrent_workers', 0)
        throughput = getattr(stress_result, 'operations_per_second', 0)
        
        return {
            'max_stable_workers': workers if error_rate <= 5 else max(1, workers - 5),
            'breaking_point_error_rate': error_rate,
            'max_observed_throughput': throughput,
            'system_stability': 'stable' if error_rate <= 2 else 'unstable' if error_rate <= 10 else 'critical'
        }
    
    def _make_final_verdict(self) -> str:
        """做出最終裁決"""
        compliance = self.validation_results.get('compliance_analysis', {})
        
        if compliance.get('overall_compliant', False):
            return 'PASS'
        elif compliance.get('compliance_rate_percent', 0) >= 50:
            return 'PARTIAL_PASS'
        else:
            return 'FAIL'
    
    def _collect_system_info(self) -> Dict[str, Any]:
        """收集系統資訊"""
        import psutil
        import platform
        
        return {
            'platform': platform.platform(),
            'cpu_count': psutil.cpu_count(),
            'total_memory_gb': psutil.virtual_memory().total / (1024**3),
            'python_version': sys.version,
            'timestamp': datetime.now().isoformat()
        }
    
    def _save_validation_report(self):
        """保存驗證報告"""
        timestamp = int(time.time())
        report_file = self.results_dir / f"t2_validation_report_{timestamp}.json"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(self.validation_results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"驗證報告已保存: {report_file}")
    
    def _print_final_results(self):
        """輸出最終結果"""
        verdict = self.validation_results.get('final_verdict', 'UNKNOWN')
        compliance = self.validation_results.get('compliance_analysis', {})
        summary = self.validation_results.get('performance_summary', {})
        
        print("\n" + "="*80)
        print("🎯 T2 高併發連線競爭修復 - 效能驗證結果")
        print("="*80)
        
        print(f"\n📊 最終裁決: {verdict}")
        
        if compliance:
            rate = compliance.get('compliance_rate_percent', 0)
            print(f"📈 T2合規率: {rate:.1f}% ({compliance.get('compliant_tests', 0)}/{compliance.get('total_tests', 0)} 測試通過)")
        
        if summary and 'performance_metrics' in summary:
            metrics = summary['performance_metrics']
            print("\n🚀 效能指標總結:")
            print(f"   • 最大吞吐量: {metrics.get('max_throughput_ops_per_sec', 0):.2f} ops/s")
            print(f"   • 平均P95響應時間: {metrics.get('avg_response_time_p95_ms', 0):.2f} ms")
            print(f"   • 最大錯誤率: {metrics.get('max_error_rate_percent', 0):.2f}%")
        
        recommendations = self.validation_results.get('optimization_recommendations', [])
        if recommendations:
            print(f"\n💡 優化建議 ({len(recommendations)} 項):")
            for i, rec in enumerate(recommendations[:3], 1):  # 只顯示前3個
                print(f"   {i}. [{rec.get('priority', 'unknown')}] {rec.get('title', 'Unknown')}")
        
        print("\n" + "="*80)


async def main():
    """主執行函數"""
    parser = argparse.ArgumentParser(description="T2 高併發連線競爭修復 - 效能驗證")
    parser.add_argument('--results-dir', default='t2_validation_results', 
                       help='結果輸出目錄')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='詳細輸出')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 創建驗證器並執行
    validator = T2PerformanceValidator(results_dir=args.results_dir)
    
    try:
        results = await validator.run_full_validation()
        
        # 輸出結果摘要
        verdict = results.get('final_verdict', 'UNKNOWN')
        if verdict == 'PASS':
            print("\n✅ T2效能驗證通過！系統滿足併發效能要求。")
            return 0
        elif verdict == 'PARTIAL_PASS':
            print("\n⚠️ T2效能驗證部分通過，建議查看優化建議。")
            return 1
        else:
            print("\n❌ T2效能驗證未通過，需要系統優化。")
            return 2
    
    except Exception as e:
        logger.error(f"驗證執行失敗: {e}")
        print(f"\n💥 驗證執行失敗: {e}")
        return 3


if __name__ == "__main__":
    exit(asyncio.run(main()))