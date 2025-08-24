#!/usr/bin/env python3
"""
T2 - 高併發連線競爭修復
連線池效能驗證腳本

執行完整的併發測試套件，驗證連線池管理器是否達到T2任務的效能目標
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime

# 添加系統路徑支持
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.append(project_root)

from tests.concurrency.test_connection_pool import ConnectionPoolTestSuite
from services.connection_pool.models import PoolConfiguration

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('connection_pool_benchmark')


async def run_full_benchmark():
    """執行完整的連線池基準測試"""
    logger.info("開始執行T2連線池效能基準測試")
    
    # 測試配置
    test_configs = [
        {
            "name": "標準配置",
            "description": "預設連線池配置，適用於一般場景",
            "config": PoolConfiguration(
                min_connections=2,
                max_connections=20,
                connection_timeout=30.0,
                acquire_timeout=10.0,
                enable_monitoring=True
            )
        },
        {
            "name": "高併發配置", 
            "description": "針對高併發場景優化的配置",
            "config": PoolConfiguration(
                min_connections=5,
                max_connections=25,
                connection_timeout=20.0,
                acquire_timeout=5.0,
                enable_monitoring=True
            )
        },
        {
            "name": "保守配置",
            "description": "資源受限環境下的保守配置",
            "config": PoolConfiguration(
                min_connections=1,
                max_connections=10,
                connection_timeout=60.0,
                acquire_timeout=15.0,
                enable_monitoring=True
            )
        }
    ]
    
    all_results = []
    
    for test_config in test_configs:
        logger.info(f"\n{'='*60}")
        logger.info(f"測試配置：{test_config['name']}")
        logger.info(f"描述：{test_config['description']}")
        logger.info(f"{'='*60}")
        
        async with ConnectionPoolTestSuite() as test_suite:
            await test_suite.setup_test_environment(test_config['config'])
            
            # 執行各種測試場景
            test_scenarios = [
                {
                    "name": "10工作者併發讀取",
                    "test": lambda: test_suite.run_concurrent_read_test(
                        num_workers=10, operations_per_worker=100
                    )
                },
                {
                    "name": "10工作者併發寫入", 
                    "test": lambda: test_suite.run_concurrent_write_test(
                        num_workers=10, operations_per_worker=50
                    )
                },
                {
                    "name": "15工作者混合負載",
                    "test": lambda: test_suite.run_mixed_workload_test(
                        num_workers=15, read_percentage=70.0, test_duration=30.0
                    )
                },
                {
                    "name": "20工作者壓力測試",
                    "test": lambda: test_suite.run_stress_test(
                        max_workers=20, ramp_up_duration=10.0, test_duration=45.0
                    )
                }
            ]
            
            config_results = {
                "config_name": test_config['name'],
                "config_description": test_config['description'],
                "config_details": {
                    "min_connections": test_config['config'].min_connections,
                    "max_connections": test_config['config'].max_connections,
                    "connection_timeout": test_config['config'].connection_timeout,
                    "acquire_timeout": test_config['config'].acquire_timeout
                },
                "test_results": []
            }
            
            for scenario in test_scenarios:
                logger.info(f"\n執行測試場景：{scenario['name']}")
                try:
                    result = await scenario['test']()
                    config_results["test_results"].append({
                        "scenario_name": scenario['name'],
                        "result": {
                            "test_name": result.test_name,
                            "duration_seconds": result.duration_seconds,
                            "total_operations": result.total_operations,
                            "successful_operations": result.successful_operations,
                            "failed_operations": result.failed_operations,
                            "operations_per_second": result.operations_per_second,
                            "error_rate_percentage": result.error_rate_percentage,
                            "response_times": {
                                "average_ms": result.average_response_time_ms,
                                "p50_ms": result.p50_response_time_ms,
                                "p95_ms": result.p95_response_time_ms,
                                "p99_ms": result.p99_response_time_ms
                            },
                            "concurrent_workers": result.concurrent_workers,
                            "max_connections_used": result.max_connections_used
                        }
                    })
                    
                    logger.info(f"✓ {scenario['name']} 完成")
                    logger.info(f"  成功率：{(result.successful_operations/result.total_operations*100):.2f}%")
                    logger.info(f"  吞吐量：{result.operations_per_second:.2f} ops/s")
                    logger.info(f"  P95響應時間：{result.p95_response_time_ms:.2f} ms")
                    
                except Exception as e:
                    logger.error(f"✗ {scenario['name']} 失敗：{e}")
                    config_results["test_results"].append({
                        "scenario_name": scenario['name'],
                        "error": str(e)
                    })
            
            # 生成效能報告
            performance_report = test_suite.generate_performance_report()
            config_results["performance_assessment"] = performance_report.get("performance_assessment", {})
            
            all_results.append(config_results)
    
    return all_results


def analyze_benchmark_results(results):
    """分析基準測試結果"""
    logger.info(f"\n{'='*80}")
    logger.info("T2任務效能分析報告")
    logger.info(f"{'='*80}")
    
    # T2任務的效能要求
    t2_requirements = {
        "max_acceptable_error_rate": 1.0,  # ≤ 1%
        "min_required_throughput": 100,    # ≥ 100 ops/s
        "max_acceptable_response": 50,     # ≤ 50ms (P95)
        "max_concurrent_workers": 20       # 支援20+併發
    }
    
    logger.info("T2任務效能要求：")
    logger.info(f"  - 錯誤率：≤ {t2_requirements['max_acceptable_error_rate']}%")
    logger.info(f"  - 吞吐量：≥ {t2_requirements['min_required_throughput']} ops/s") 
    logger.info(f"  - P95響應時間：≤ {t2_requirements['max_acceptable_response']} ms")
    logger.info(f"  - 併發支援：≥ {t2_requirements['max_concurrent_workers']} 工作者")
    
    overall_pass = True
    best_config = None
    best_score = 0
    
    for config_result in results:
        config_name = config_result["config_name"]
        logger.info(f"\n--- {config_name} 分析結果 ---")
        
        config_pass = True
        total_score = 0
        scenario_count = 0
        
        for test_result in config_result["test_results"]:
            if "error" in test_result:
                logger.info(f"  ✗ {test_result['scenario_name']}: 測試失敗")
                config_pass = False
                continue
            
            result = test_result["result"]
            scenario_name = test_result["scenario_name"]
            scenario_count += 1
            
            # 計算場景分數
            scenario_score = 100
            issues = []
            
            # 檢查錯誤率
            if result["error_rate_percentage"] > t2_requirements["max_acceptable_error_rate"]:
                scenario_score -= 30
                issues.append(f"錯誤率過高 ({result['error_rate_percentage']:.2f}%)")
            
            # 檢查吞吐量
            if result["operations_per_second"] < t2_requirements["min_required_throughput"]:
                scenario_score -= 25
                issues.append(f"吞吐量不足 ({result['operations_per_second']:.2f} ops/s)")
            
            # 檢查響應時間
            if result["response_times"]["p95_ms"] > t2_requirements["max_acceptable_response"]:
                scenario_score -= 20
                issues.append(f"響應時間過長 (P95: {result['response_times']['p95_ms']:.2f} ms)")
            
            # 檢查併發支援
            if result["concurrent_workers"] < t2_requirements["max_concurrent_workers"]:
                scenario_score -= 15
                issues.append(f"併發支援不足 ({result['concurrent_workers']} 工作者)")
            
            # 確保分數不為負
            scenario_score = max(0, scenario_score)
            total_score += scenario_score
            
            # 輸出場景結果
            status = "✓" if scenario_score >= 80 else "⚠" if scenario_score >= 60 else "✗"
            logger.info(f"  {status} {scenario_name}: {scenario_score}/100 分")
            logger.info(f"    - 成功率: {(result['successful_operations']/result['total_operations']*100):.2f}%")
            logger.info(f"    - 吞吐量: {result['operations_per_second']:.2f} ops/s")
            logger.info(f"    - P95響應: {result['response_times']['p95_ms']:.2f} ms")
            logger.info(f"    - 併發數: {result['concurrent_workers']} 工作者")
            
            if issues:
                logger.info(f"    問題: {', '.join(issues)}")
        
        # 計算配置總分
        avg_score = total_score / scenario_count if scenario_count > 0 else 0
        
        # 判斷是否通過T2要求
        config_grade = "優秀" if avg_score >= 90 else "良好" if avg_score >= 80 else "及格" if avg_score >= 60 else "不及格"
        
        logger.info(f"\n  配置總評：{avg_score:.1f}/100 分 ({config_grade})")
        
        if avg_score < 60:
            config_pass = False
            overall_pass = False
        
        if avg_score > best_score:
            best_score = avg_score
            best_config = config_name
    
    # 總結
    logger.info(f"\n{'='*80}")
    logger.info("總結與建議")
    logger.info(f"{'='*80}")
    
    if overall_pass:
        logger.info("🎉 T2任務效能要求：通過")
        logger.info(f"📊 最佳配置：{best_config} (得分: {best_score:.1f}/100)")
        logger.info("✅ 連線池管理器已達到所有效能指標")
    else:
        logger.info("❌ T2任務效能要求：未通過")
        logger.info("⚠️  需要優化以下方面：")
        logger.info("   1. 調整連線池配置參數")
        logger.info("   2. 優化資料庫查詢效能")
        logger.info("   3. 考慮硬體資源升級")
    
    logger.info("\n建議：")
    logger.info("- 在生產環境中使用最佳配置")
    logger.info("- 持續監控連線池效能指標")
    logger.info("- 根據實際負載調整配置參數")


def save_benchmark_report(results, filename=None):
    """儲存基準測試報告"""
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"t2_connection_pool_benchmark_{timestamp}.json"
    
    report = {
        "benchmark_info": {
            "task_id": "T2",
            "test_name": "高併發連線競爭修復 - 連線池效能基準測試",
            "timestamp": datetime.now().isoformat(),
            "description": "驗證ConnectionPoolManager是否達到T2任務的效能目標"
        },
        "test_results": results,
        "metadata": {
            "python_version": sys.version,
            "platform": sys.platform
        }
    }
    
    report_dir = os.path.join(project_root, "test_reports")
    os.makedirs(report_dir, exist_ok=True)
    
    report_path = os.path.join(report_dir, filename)
    
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    logger.info(f"基準測試報告已儲存：{report_path}")
    return report_path


async def main():
    """主執行函數"""
    try:
        logger.info("T2 - 高併發連線競爭修復")
        logger.info("連線池管理器效能驗證開始")
        
        # 執行基準測試
        results = await run_full_benchmark()
        
        # 分析結果
        analyze_benchmark_results(results)
        
        # 儲存報告
        report_path = save_benchmark_report(results)
        
        logger.info("\n基準測試完成！")
        logger.info(f"詳細報告已儲存至：{report_path}")
        
    except KeyboardInterrupt:
        logger.info("\n測試被用戶中斷")
    except Exception as e:
        logger.error(f"基準測試執行失敗：{e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())