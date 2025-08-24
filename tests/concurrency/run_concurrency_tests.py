#!/usr/bin/env python3
"""
T2 併發測試自動化執行腳本
提供命令行介面執行併發測試套件

功能：
- 執行基礎和進階併發測試
- 生成詳細報告
- CI/CD 整合支援
- 測試結果驗證
"""

import sys
import asyncio
import argparse
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

# 設定專案路徑
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from test_connection_pool import (
    ConnectionPoolTestSuite,
    PerformanceBenchmark,
    ConcurrencyTestResult,
    run_full_concurrency_test_suite
)
from test_advanced_scenarios import (
    AdvancedConcurrencyTestSuite,
    AdvancedPerformanceAnalyzer,
    run_advanced_concurrency_tests
)


class ConcurrencyTestRunner:
    """併發測試執行器"""
    
    def __init__(self, results_dir: Optional[str] = None):
        """初始化測試執行器"""
        self.results_dir = Path(results_dir) if results_dir else Path("test_reports/concurrency")
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        # 設定日誌
        self.setup_logging()
        
    def setup_logging(self):
        """設定日誌"""
        log_file = self.results_dir / "concurrency_test_runner.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    async def run_basic_tests(self) -> List[ConcurrencyTestResult]:
        """執行基礎併發測試"""
        self.logger.info("開始執行基礎併發測試...")
        
        suite = ConnectionPoolTestSuite()
        benchmark = PerformanceBenchmark(str(self.results_dir))
        
        try:
            await suite.setup()
            
            results = []
            
            # 10工作者測試
            result_10 = await suite.test_10_workers_concurrent()
            results.append(result_10)
            benchmark.save_result(result_10)
            
            # 20工作者極限測試
            result_20 = await suite.test_20_workers_extreme_load()
            results.append(result_20)
            benchmark.save_result(result_20)
            
            # 連線壓力測試
            result_stress = await suite.test_connection_stress()
            results.append(result_stress)
            benchmark.save_result(result_stress)
            
            # 穩定性測試 (短版本用於CI)
            result_stability = await suite.test_long_running_stability(duration_minutes=1)
            results.append(result_stability)
            benchmark.save_result(result_stability)
            
            self.logger.info(f"基礎測試完成，共執行 {len(results)} 個測試")
            return results
            
        finally:
            await suite.cleanup()
    
    async def run_advanced_tests(self) -> List[ConcurrencyTestResult]:
        """執行進階併發測試"""
        self.logger.info("開始執行進階併發測試...")
        
        suite = AdvancedConcurrencyTestSuite()
        
        try:
            await suite.setup()
            
            results = []
            
            # 混合讀寫測試
            result_mixed = await suite.test_mixed_read_write_operations()
            results.append(result_mixed)
            
            # 事務壓力測試
            result_tx = await suite.test_transaction_stress()
            results.append(result_tx)
            
            # 連線池耗盡測試
            result_pool = await suite.test_connection_pool_exhaustion()
            results.append(result_pool)
            
            # 突發負載測試
            result_burst = await suite.test_load_burst_patterns()
            results.append(result_burst)
            
            self.logger.info(f"進階測試完成，共執行 {len(results)} 個測試")
            return results
            
        finally:
            await suite.cleanup()
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """執行所有併發測試"""
        start_time = time.time()
        
        self.logger.info("🚀 開始執行完整併發測試套件...")
        
        # 執行基礎測試
        basic_results = await self.run_basic_tests()
        
        # 執行進階測試
        advanced_results = await self.run_advanced_tests()
        
        all_results = basic_results + advanced_results
        
        # 綜合分析
        analyzer = AdvancedPerformanceAnalyzer()
        analysis = analyzer.analyze_advanced_results(all_results)
        
        # 生成綜合報告
        benchmark = PerformanceBenchmark(str(self.results_dir))
        comprehensive_report = benchmark.generate_report(all_results)
        
        # 合併分析結果
        final_report = {
            "test_execution": {
                "start_time": start_time,
                "end_time": time.time(),
                "duration_seconds": time.time() - start_time,
                "total_tests": len(all_results),
                "basic_tests": len(basic_results),
                "advanced_tests": len(advanced_results)
            },
            "basic_report": comprehensive_report,
            "advanced_analysis": analysis,
            "test_results": [self._result_to_dict(r) for r in all_results]
        }
        
        # 儲存最終報告
        report_file = self.results_dir / f"comprehensive_concurrency_report_{int(time.time())}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(final_report, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"完整測試套件執行完成，報告儲存至: {report_file}")
        
        return final_report
    
    def _result_to_dict(self, result: ConcurrencyTestResult) -> Dict[str, Any]:
        """轉換測試結果為字典格式"""
        return {
            "test_name": result.test_name,
            "worker_count": result.worker_count,
            "operations_per_worker": result.operations_per_worker,
            "total_operations": result.total_operations,
            "successful_operations": result.successful_operations,
            "failed_operations": result.failed_operations,
            "success_rate": result.success_rate,
            "error_rate": result.error_rate,
            "avg_response_time_ms": result.avg_response_time_ms,
            "p95_response_time_ms": result.p95_response_time_ms,
            "p99_response_time_ms": result.p99_response_time_ms,
            "total_duration_s": result.total_duration_s,
            "operations_per_second": result.operations_per_second,
            "memory_usage_mb": result.memory_usage_mb,
            "peak_memory_mb": result.peak_memory_mb,
            "errors": result.errors,
            "timestamp": result.timestamp
        }
    
    def validate_test_results(self, results: List[ConcurrencyTestResult]) -> Dict[str, Any]:
        """驗證測試結果是否符合 T2 標準"""
        validation = {
            "total_tests": len(results),
            "passed_tests": 0,
            "failed_tests": 0,
            "validation_details": [],
            "overall_pass": True,
            "error_summary": []
        }
        
        for result in results:
            test_validation = {
                "test_name": result.test_name,
                "checks": {
                    "error_rate_ok": result.error_rate <= 0.01,
                    "response_time_ok": result.p95_response_time_ms <= 50,
                    "success_rate_ok": result.success_rate >= 0.99
                }
            }
            
            test_validation["overall_pass"] = all(test_validation["checks"].values())
            
            if test_validation["overall_pass"]:
                validation["passed_tests"] += 1
            else:
                validation["failed_tests"] += 1
                validation["overall_pass"] = False
                
                # 記錄失敗原因
                failures = []
                if not test_validation["checks"]["error_rate_ok"]:
                    failures.append(f"錯誤率 {result.error_rate:.2%} > 1%")
                if not test_validation["checks"]["response_time_ok"]:
                    failures.append(f"P95回應時間 {result.p95_response_time_ms:.2f}ms > 50ms")
                if not test_validation["checks"]["success_rate_ok"]:
                    failures.append(f"成功率 {result.success_rate:.2%} < 99%")
                
                validation["error_summary"].append({
                    "test": result.test_name,
                    "failures": failures
                })
            
            validation["validation_details"].append(test_validation)
        
        return validation
    
    def print_summary(self, report: Dict[str, Any]):
        """列印測試摘要"""
        print("\n" + "="*80)
        print("📋 T2 併發測試套件執行摘要")
        print("="*80)
        
        execution = report["test_execution"]
        print(f"⏱️  執行時間: {execution['duration_seconds']:.2f} 秒")
        print(f"📊 總測試數: {execution['total_tests']} ({execution['basic_tests']} 基礎 + {execution['advanced_tests']} 進階)")
        
        # 基礎報告摘要
        basic_report = report["basic_report"]["test_summary"]
        print(f"✅ 基礎測試通過率: {basic_report['tests_meeting_criteria']}/{basic_report['total_tests']}")
        print(f"📈 整體成功率: {basic_report['overall_success_rate']:.2%}")
        print(f"📉 整體錯誤率: {basic_report['overall_error_rate']:.2%}")
        
        # 進階分析摘要
        advanced_analysis = report["advanced_analysis"]["overall_performance"]
        print(f"🔬 進階測試通過: {advanced_analysis['scenarios_passing']}/{advanced_analysis['scenarios_total']}")
        print(f"📊 平均成功率: {advanced_analysis['average_success_rate']:.2%}")
        print(f"⚡ 平均P95回應時間: {advanced_analysis['average_p95_response_time_ms']:.2f}ms")
        
        # 建議
        recommendations = report["advanced_analysis"]["recommendations"]
        if recommendations:
            print("\n💡 優化建議:")
            for rec in recommendations[:3]:  # 顯示前3個建議
                print(f"  • {rec}")
        
        print("="*80)


def create_ci_script():
    """建立 CI 腳本"""
    ci_script_content = """#!/bin/bash
# T2 併發測試 CI 腳本

set -e  # 遇到錯誤立即退出

echo "🚀 開始執行 T2 併發測試..."

# 確保測試報告目錄存在
mkdir -p test_reports/concurrency

# 執行併發測試
python tests/concurrency/run_concurrency_tests.py --mode=ci --timeout=600

# 檢查測試結果
if [ -f "test_reports/concurrency/ci_test_result.json" ]; then
    # 解析測試結果
    python -c "
import json
with open('test_reports/concurrency/ci_test_result.json', 'r') as f:
    result = json.load(f)
    
if result.get('overall_pass', False):
    print('✅ 所有併發測試通過')
    exit(0)
else:
    print('❌ 併發測試失敗')
    failed_tests = result.get('failed_tests', 0)
    print(f'失敗測試數: {failed_tests}')
    exit(1)
"
else
    echo "❌ 測試結果檔案不存在"
    exit(1
fi

echo "🎉 T2 併發測試完成"
"""
    
    ci_script_path = Path("tests/concurrency/ci_test.sh")
    with open(ci_script_path, 'w') as f:
        f.write(ci_script_content)
    
    # 設定執行權限
    import stat
    ci_script_path.chmod(ci_script_path.stat().st_mode | stat.S_IEXEC)
    
    return ci_script_path


async def main():
    """主函數"""
    parser = argparse.ArgumentParser(description="T2 併發測試執行器")
    parser.add_argument(
        "--mode",
        choices=["basic", "advanced", "all", "ci"],
        default="all",
        help="測試模式"
    )
    parser.add_argument(
        "--results-dir",
        type=str,
        default="test_reports/concurrency",
        help="測試結果目錄"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=1800,  # 30分鐘
        help="測試超時時間（秒）"
    )
    parser.add_argument(
        "--create-ci-script",
        action="store_true",
        help="建立 CI 腳本"
    )
    
    args = parser.parse_args()
    
    # 建立 CI 腳本
    if args.create_ci_script:
        script_path = create_ci_script()
        print(f"✅ CI 腳本已建立: {script_path}")
        return
    
    runner = ConcurrencyTestRunner(args.results_dir)
    
    try:
        # 設定超時
        if args.mode == "basic":
            results = await asyncio.wait_for(runner.run_basic_tests(), timeout=args.timeout)
            # 生成基礎報告
            benchmark = PerformanceBenchmark(args.results_dir)
            report = benchmark.generate_report(results)
            
        elif args.mode == "advanced":
            results = await asyncio.wait_for(runner.run_advanced_tests(), timeout=args.timeout)
            # 生成進階分析
            analyzer = AdvancedPerformanceAnalyzer()
            analysis = analyzer.analyze_advanced_results(results)
            report = {"advanced_analysis": analysis, "test_results": results}
            
        else:  # all 或 ci 模式
            report = await asyncio.wait_for(runner.run_all_tests(), timeout=args.timeout)
            results = [ConcurrencyTestResult(**r) for r in report["test_results"]]
        
        # 驗證結果
        validation = runner.validate_test_results(results)
        
        if args.mode == "ci":
            # CI 模式：儲存簡化結果
            ci_result = {
                "overall_pass": validation["overall_pass"],
                "passed_tests": validation["passed_tests"],
                "failed_tests": validation["failed_tests"],
                "error_summary": validation["error_summary"],
                "timestamp": time.time()
            }
            
            ci_result_file = Path(args.results_dir) / "ci_test_result.json"
            with open(ci_result_file, 'w') as f:
                json.dump(ci_result, f, indent=2)
            
            # 輸出 CI 結果
            if validation["overall_pass"]:
                print("✅ 所有併發測試通過 T2 標準")
                sys.exit(0)
            else:
                print(f"❌ {validation['failed_tests']} 個測試未通過 T2 標準")
                for error in validation["error_summary"]:
                    print(f"  {error['test']}: {', '.join(error['failures'])}")
                sys.exit(1)
        else:
            # 互動模式：顯示詳細報告
            runner.print_summary(report)
            
            if validation["overall_pass"]:
                print("🎉 所有測試都符合 T2 效能標準！")
            else:
                print(f"⚠️  {validation['failed_tests']} 個測試需要優化")
    
    except asyncio.TimeoutError:
        print(f"❌ 測試執行超時 ({args.timeout} 秒)")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 測試執行失敗: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())