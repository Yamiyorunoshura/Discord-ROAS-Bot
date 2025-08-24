"""
T2 - 併發效能基準測試和負載測試實施
Task ID: T2

提供全面的連線池效能驗證和基準測試框架
"""

import asyncio
import json
import logging
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import uuid
import statistics

# 添加專案根目錄到路徑
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.append(project_root)

from services.connection_pool import (
    ConnectionPoolManager, 
    PoolConfiguration,
    ConnectionPoolMonitor
)
from services.monitoring.monitoring_service import MonitoringService
from tests.concurrency.test_connection_pool import ConnectionPoolTestSuite, TestResult

logger = logging.getLogger('performance_benchmark')


class PerformanceBenchmark:
    """
    效能基準測試套件
    
    專為T2任務設計的全面效能驗證：
    - 10+工作者併發測試
    - 錯誤率 ≤ 1% 驗證
    - 響應時間 P95 ≤ 50ms 驗證
    - 智慧動態調整驗證
    """
    
    def __init__(self, test_db_path: Optional[str] = None):
        """
        初始化效能基準測試
        
        參數：
            test_db_path: 測試資料庫路徑，None則使用臨時檔案
        """
        if test_db_path is None:
            self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
            self.test_db_path = self.temp_db.name
            self.temp_db.close()
        else:
            self.test_db_path = test_db_path
        
        self.test_suite = ConnectionPoolTestSuite(self.test_db_path)
        self.benchmark_results: List[Dict[str, Any]] = []
        self.monitoring_service = MonitoringService()
        
        logger.info(f"效能基準測試初始化完成 - 測試DB: {self.test_db_path}")
    
    async def run_t2_performance_validation(self) -> Dict[str, Any]:
        """
        執行T2任務要求的效能驗證
        
        驗證標準：
        - 併發錯誤率 ≤ 1%
        - 連線池響應時間 p95 ≤ 50ms
        - 支援20+工作者併發負載
        - 智慧動態調整功能
        """
        logger.info("開始T2效能驗證測試")
        
        validation_results = {
            "test_timestamp": datetime.now().isoformat(),
            "test_db_path": self.test_db_path,
            "validation_criteria": {
                "max_error_rate": 1.0,
                "max_p95_response_time": 50.0,
                "min_concurrent_workers": 10,
                "target_concurrent_workers": 20
            },
            "test_results": [],
            "overall_validation": {}
        }
        
        try:
            # 設置測試環境
            pool_config = PoolConfiguration(
                min_connections=3,
                max_connections=25,
                connection_timeout=30.0,
                acquire_timeout=15.0,
                enable_monitoring=True,
                stats_collection_interval=10
            )
            
            await self.test_suite.setup_test_environment(pool_config)
            
            # 設置監控
            pool_monitor = ConnectionPoolMonitor(
                pool_manager=self.test_suite.pool_manager,
                monitoring_service=self.monitoring_service
            )
            await pool_monitor.start_monitoring()
            
            try:
                # 測試1: 10工作者併發讀取 - 基本需求驗證
                logger.info("執行10工作者併發讀取測試...")
                read_result = await self.test_suite.run_concurrent_read_test(
                    num_workers=10,
                    operations_per_worker=200
                )
                validation_results["test_results"].append({
                    "test_name": "10_workers_concurrent_read",
                    "result": self._serialize_test_result(read_result),
                    "validation_passed": self._validate_test_result(read_result, validation_results["validation_criteria"])
                })
                
                # 測試2: 15工作者混合負載 - 實際負載模擬
                logger.info("執行15工作者混合負載測試...")
                mixed_result = await self.test_suite.run_mixed_workload_test(
                    num_workers=15,
                    read_percentage=75.0,
                    test_duration=60.0
                )
                validation_results["test_results"].append({
                    "test_name": "15_workers_mixed_workload",
                    "result": self._serialize_test_result(mixed_result),
                    "validation_passed": self._validate_test_result(mixed_result, validation_results["validation_criteria"])
                })
                
                # 測試3: 20工作者壓力測試 - 目標負載驗證
                logger.info("執行20工作者壓力測試...")
                stress_result = await self.test_suite.run_stress_test(
                    max_workers=20,
                    ramp_up_duration=15.0,
                    test_duration=90.0
                )
                validation_results["test_results"].append({
                    "test_name": "20_workers_stress_test",
                    "result": self._serialize_test_result(stress_result),
                    "validation_passed": self._validate_test_result(stress_result, validation_results["validation_criteria"])
                })
                
                # 測試4: 動態調整功能驗證
                logger.info("執行動態調整功能測試...")
                dynamic_result = await self._test_dynamic_adjustment()
                validation_results["test_results"].append({
                    "test_name": "dynamic_adjustment_test",
                    "result": dynamic_result,
                    "validation_passed": dynamic_result["passed"]
                })
                
                # 收集監控數據
                monitoring_stats = await pool_monitor.get_current_stats()
                performance_trends = await pool_monitor.analyze_performance_trends()
                alerts = await pool_monitor.check_alerts()
                
                validation_results["monitoring_data"] = {
                    "current_stats": monitoring_stats,
                    "performance_trends": performance_trends,
                    "alerts": alerts
                }
                
            finally:
                await pool_monitor.stop_monitoring()
            
            # 整體驗證評估
            validation_results["overall_validation"] = self._assess_overall_validation(validation_results)
            
            logger.info(f"T2效能驗證完成 - 整體結果: {validation_results['overall_validation']['status']}")
            
        except Exception as e:
            logger.error(f"T2效能驗證失敗: {e}")
            validation_results["error"] = str(e)
            validation_results["overall_validation"] = {
                "status": "ERROR",
                "message": f"測試執行失敗: {str(e)}"
            }
        
        finally:
            await self.test_suite.cleanup()
        
        return validation_results
    
    async def _test_dynamic_adjustment(self) -> Dict[str, Any]:
        """測試動態調整功能"""
        logger.info("開始動態調整功能測試...")
        
        pool_manager = self.test_suite.pool_manager
        result = {
            "test_name": "dynamic_adjustment",
            "timestamp": datetime.now().isoformat(),
            "passed": False,
            "details": {},
            "observations": []
        }
        
        try:
            # 記錄初始狀態
            initial_stats = pool_manager.get_pool_stats()
            result["details"]["initial_connections"] = initial_stats["active_connections"] + initial_stats["idle_connections"]
            
            # 模擬突發負載
            async def burst_load():
                tasks = []
                for i in range(12):  # 12個並行任務
                    tasks.append(self._simulate_db_work(f"burst_{i}"))
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                successful = sum(1 for r in results if not isinstance(r, Exception))
                return successful, len(results)
            
            # 執行突發負載並觀察調整
            burst_start = time.time()
            successful_ops, total_ops = await burst_load()
            burst_duration = time.time() - burst_start
            
            # 記錄負載後狀態
            post_load_stats = pool_manager.get_pool_stats()
            result["details"]["post_load_connections"] = post_load_stats["active_connections"] + post_load_stats["idle_connections"]
            
            result["observations"].append(
                f"突發負載: {successful_ops}/{total_ops} 成功，耗時 {burst_duration:.2f}s"
            )
            
            # 等待動態調整
            await asyncio.sleep(5)
            
            # 執行池優化
            await pool_manager.optimize_pool()
            
            # 記錄優化後狀態
            optimized_stats = pool_manager.get_pool_stats()
            result["details"]["optimized_connections"] = optimized_stats["active_connections"] + optimized_stats["idle_connections"]
            
            # 驗證動態調整是否有效
            initial_total = result["details"]["initial_connections"]
            post_load_total = result["details"]["post_load_connections"]
            optimized_total = result["details"]["optimized_connections"]
            
            # 檢查是否發生了調整
            has_scaling = post_load_total != initial_total or optimized_total != post_load_total
            
            # 檢查錯誤率
            error_rate = ((total_ops - successful_ops) / total_ops * 100) if total_ops > 0 else 0
            
            result["details"]["burst_load_results"] = {
                "successful_operations": successful_ops,
                "total_operations": total_ops,
                "error_rate": error_rate,
                "duration_seconds": burst_duration
            }
            
            # 評估是否通過
            result["passed"] = (
                has_scaling and  # 有動態調整
                error_rate <= 2.0 and  # 錯誤率可接受（突發負載下稍寬鬆）
                burst_duration <= 10.0  # 處理時間合理
            )
            
            result["observations"].append(
                f"動態調整檢測: 初始 {initial_total} → 負載後 {post_load_total} → 優化後 {optimized_total} 連線"
            )
            result["observations"].append(
                f"突發負載錯誤率: {error_rate:.2f}%"
            )
            
            logger.info(f"動態調整測試完成 - 通過: {result['passed']}")
            
        except Exception as e:
            logger.error(f"動態調整測試失敗: {e}")
            result["error"] = str(e)
            result["passed"] = False
        
        return result
    
    async def _simulate_db_work(self, task_id: str) -> bool:
        """模擬資料庫工作負載"""
        try:
            async with self.test_suite.pool_manager.connection() as conn:
                # 執行複雜查詢模擬真實負載
                async with conn.execute("""
                    SELECT u.username, u.score, COUNT(a.id) as activity_count
                    FROM test_users u 
                    LEFT JOIN test_activities a ON u.id = a.user_id
                    WHERE u.score > ?
                    GROUP BY u.id
                    ORDER BY activity_count DESC
                    LIMIT 5
                """, (100,)) as cursor:
                    results = await cursor.fetchall()
                
                # 短暫延遲模擬處理時間
                await asyncio.sleep(0.05)
                
                return True
        
        except Exception as e:
            logger.debug(f"模擬工作負載 {task_id} 失敗: {e}")
            return False
    
    def _validate_test_result(self, test_result: TestResult, criteria: Dict[str, Any]) -> bool:
        """驗證測試結果是否符合標準"""
        validations = []
        
        # 檢查錯誤率
        error_rate_ok = test_result.error_rate_percentage <= criteria["max_error_rate"]
        validations.append(error_rate_ok)
        
        # 檢查P95響應時間
        p95_response_ok = test_result.p95_response_time_ms <= criteria["max_p95_response_time"]
        validations.append(p95_response_ok)
        
        # 檢查併發工作者數量
        workers_ok = test_result.concurrent_workers >= criteria["min_concurrent_workers"]
        validations.append(workers_ok)
        
        return all(validations)
    
    def _serialize_test_result(self, test_result: TestResult) -> Dict[str, Any]:
        """序列化測試結果"""
        return {
            "test_name": test_result.test_name,
            "timestamp": test_result.timestamp.isoformat(),
            "duration_seconds": test_result.duration_seconds,
            "concurrent_workers": test_result.concurrent_workers,
            "total_operations": test_result.total_operations,
            "successful_operations": test_result.successful_operations,
            "failed_operations": test_result.failed_operations,
            "operations_per_second": test_result.operations_per_second,
            "error_rate_percentage": test_result.error_rate_percentage,
            "response_times": {
                "average_ms": test_result.average_response_time_ms,
                "p50_ms": test_result.p50_response_time_ms,
                "p95_ms": test_result.p95_response_time_ms,
                "p99_ms": test_result.p99_response_time_ms
            },
            "max_connections_used": test_result.max_connections_used
        }
    
    def _assess_overall_validation(self, validation_results: Dict[str, Any]) -> Dict[str, Any]:
        """評估整體驗證結果"""
        test_results = validation_results["test_results"]
        
        # 檢查所有測試是否通過
        all_passed = all(result["validation_passed"] for result in test_results)
        
        # 統計關鍵指標
        error_rates = []
        p95_response_times = []
        throughputs = []
        
        for test_result in test_results:
            result_data = test_result["result"]
            if "error_rate_percentage" in result_data:
                error_rates.append(result_data["error_rate_percentage"])
            if "response_times" in result_data:
                p95_response_times.append(result_data["response_times"]["p95_ms"])
            if "operations_per_second" in result_data:
                throughputs.append(result_data["operations_per_second"])
        
        # 計算綜合指標
        avg_error_rate = statistics.mean(error_rates) if error_rates else 0
        max_p95_response = max(p95_response_times) if p95_response_times else 0
        avg_throughput = statistics.mean(throughputs) if throughputs else 0
        
        # 評估等級
        if all_passed and avg_error_rate <= 0.5 and max_p95_response <= 30:
            grade = "EXCELLENT"
            status = "PASS"
        elif all_passed and avg_error_rate <= 1.0 and max_p95_response <= 50:
            grade = "GOOD"
            status = "PASS"
        elif avg_error_rate <= 2.0 and max_p95_response <= 100:
            grade = "FAIR"
            status = "CONDITIONAL_PASS"
        else:
            grade = "POOR"
            status = "FAIL"
        
        return {
            "status": status,
            "grade": grade,
            "summary": {
                "total_tests": len(test_results),
                "passed_tests": sum(1 for result in test_results if result["validation_passed"]),
                "average_error_rate": avg_error_rate,
                "max_p95_response_time": max_p95_response,
                "average_throughput": avg_throughput
            },
            "t2_requirements_met": {
                "concurrent_error_rate_under_1_percent": avg_error_rate <= 1.0,
                "p95_response_time_under_50ms": max_p95_response <= 50.0,
                "supports_20_plus_workers": any(
                    result["result"]["concurrent_workers"] >= 20 
                    for result in test_results
                ),
                "dynamic_adjustment_working": any(
                    result["test_name"] == "dynamic_adjustment_test" and result["validation_passed"]
                    for result in test_results
                )
            }
        }
    
    async def generate_performance_report(self, output_path: Optional[str] = None) -> str:
        """生成詳細效能報告"""
        
        # 執行完整效能驗證
        validation_results = await self.run_t2_performance_validation()
        
        # 生成報告
        report = {
            "report_metadata": {
                "generated_at": datetime.now().isoformat(),
                "report_version": "T2-1.0",
                "task_id": "T2",
                "test_database": self.test_db_path
            },
            "executive_summary": validation_results["overall_validation"],
            "detailed_results": validation_results,
            "recommendations": self._generate_recommendations(validation_results)
        }
        
        # 保存報告
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"/Users/tszkinlai/Coding/roas-bot/test_reports/t2_performance_report_{timestamp}.json"
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"效能報告已生成: {output_path}")
        return output_path
    
    def _generate_recommendations(self, validation_results: Dict[str, Any]) -> List[str]:
        """生成優化建議"""
        recommendations = []
        overall = validation_results["overall_validation"]
        
        if overall["status"] == "FAIL":
            recommendations.append("系統未達到T2任務要求，需要進行重大優化")
            
            if not overall["t2_requirements_met"]["concurrent_error_rate_under_1_percent"]:
                recommendations.append(
                    "併發錯誤率超過1%閾值，建議："
                    "\n- 增加連線池超時時間"
                    "\n- 優化SQLite WAL配置" 
                    "\n- 實施更智慧的重試機制"
                )
            
            if not overall["t2_requirements_met"]["p95_response_time_under_50ms"]:
                recommendations.append(
                    "P95響應時間超過50ms閾值，建議："
                    "\n- 增加最小連線數以減少連線建立開銷"
                    "\n- 優化查詢語句和索引"
                    "\n- 考慮連線預熱機制"
                )
        
        elif overall["status"] == "CONDITIONAL_PASS":
            recommendations.append("系統基本滿足要求，但有改進空間")
            recommendations.append(
                "建議進行以下優化："
                "\n- 微調連線池參數"
                "\n- 增強監控和告警"
                "\n- 定期執行效能回歸測試"
            )
        
        else:
            recommendations.append("系統效能表現優秀，達到T2任務要求")
            recommendations.append(
                "持續改進建議："
                "\n- 建立定期效能測試流程"
                "\n- 監控生產環境效能指標"
                "\n- 準備更高併發場景的擴展計劃"
            )
        
        return recommendations
    
    async def cleanup(self):
        """清理測試資源"""
        try:
            if hasattr(self, 'temp_db'):
                os.unlink(self.test_db_path)
                logger.info("臨時測試資料庫已清理")
        except OSError:
            logger.warning(f"無法刪除測試資料庫: {self.test_db_path}")


async def main():
    """主測試入口"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("T2 - 高併發連線競爭修復 - 效能基準測試")
    print("=" * 60)
    
    benchmark = PerformanceBenchmark()
    
    try:
        # 執行完整效能驗證並生成報告
        report_path = await benchmark.generate_performance_report()
        
        print(f"\n效能測試完成！")
        print(f"報告已生成: {report_path}")
        
        # 讀取並顯示摘要
        with open(report_path, 'r', encoding='utf-8') as f:
            report = json.load(f)
        
        summary = report["executive_summary"]
        print(f"\n測試結果: {summary['status']} - {summary['grade']}")
        print(f"平均錯誤率: {summary['summary']['average_error_rate']:.2f}%")
        print(f"最大P95響應時間: {summary['summary']['max_p95_response_time']:.2f}ms")
        print(f"平均吞吐量: {summary['summary']['average_throughput']:.2f} ops/s")
        
        # 顯示T2需求滿足情況
        t2_met = summary["t2_requirements_met"]
        print(f"\nT2任務需求滿足情況:")
        print(f"- 併發錯誤率 ≤ 1%: {'✓' if t2_met['concurrent_error_rate_under_1_percent'] else '✗'}")
        print(f"- P95響應時間 ≤ 50ms: {'✓' if t2_met['p95_response_time_under_50ms'] else '✗'}")
        print(f"- 支援20+工作者: {'✓' if t2_met['supports_20_plus_workers'] else '✗'}")
        print(f"- 動態調整功能: {'✓' if t2_met['dynamic_adjustment_working'] else '✗'}")
        
    finally:
        await benchmark.cleanup()


if __name__ == "__main__":
    asyncio.run(main())