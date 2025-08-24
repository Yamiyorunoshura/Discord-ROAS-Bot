#!/usr/bin/env python3
"""
T2 - 簡化併發測試執行腳本
用於驗證併發測試框架是否正常工作
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# 添加專案路徑
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.concurrency.test_connection_pool import ConnectionPoolTestSuite

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_basic_concurrency():
    """測試基礎併發功能"""
    logger.info("🚀 開始基礎併發測試...")
    
    async with ConnectionPoolTestSuite() as suite:
        await suite.setup_test_environment()
        
        # 執行 10 工作者併發讀取測試
        logger.info("執行 10 工作者併發讀取測試...")
        result1 = await suite.run_concurrent_read_test(num_workers=10, operations_per_worker=50)
        
        logger.info(f"讀取測試結果：{result1.successful_operations}/{result1.total_operations} 成功")
        logger.info(f"錯誤率：{result1.error_rate_percentage:.2f}%")
        logger.info(f"吞吐量：{result1.operations_per_second:.2f} ops/s")
        logger.info(f"平均響應時間：{result1.average_response_time_ms:.2f} ms")
        
        # 執行併發寫入測試
        logger.info("執行併發寫入測試...")
        result2 = await suite.run_concurrent_write_test(num_workers=5, operations_per_worker=20)
        
        logger.info(f"寫入測試結果：{result2.successful_operations}/{result2.total_operations} 成功")
        logger.info(f"錯誤率：{result2.error_rate_percentage:.2f}%")
        logger.info(f"吞吐量：{result2.operations_per_second:.2f} ops/s")
        
        # 執行混合負載測試
        logger.info("執行混合負載測試...")
        result3 = await suite.run_mixed_workload_test(num_workers=8, test_duration=15.0)
        
        logger.info(f"混合測試結果：{result3.successful_operations}/{result3.total_operations} 成功")
        logger.info(f"錯誤率：{result3.error_rate_percentage:.2f}%")
        logger.info(f"吞吐量：{result3.operations_per_second:.2f} ops/s")
        
        # 生成效能報告
        report = suite.generate_performance_report()
        
        # T2 標準驗證
        t2_compliance = report["performance_assessment"]
        overall_pass = t2_compliance["overall_assessment"]["pass"]
        
        logger.info("="*80)
        logger.info("📊 T2 併發測試結果摘要")
        logger.info("="*80)
        
        if overall_pass:
            logger.info("✅ 所有測試都符合 T2 效能標準！")
        else:
            logger.info("⚠️  部分測試未達到 T2 標準")
            for test_name, assessment in t2_compliance["results"].items():
                if not assessment["pass"]:
                    logger.warning(f"❌ {test_name}: {', '.join(assessment['issues'])}")
        
        # 輸出關鍵指標
        summary = report["summary"]
        logger.info(f"總測試數：{summary['total_tests']}")
        logger.info(f"整體成功率：{summary['overall_success_rate']:.2%}")
        logger.info(f"整體錯誤率：{summary['overall_error_rate']:.2%}")
        logger.info(f"平均吞吐量：{report['performance_metrics']['average_throughput_ops_per_sec']:.2f} ops/s")
        
        return overall_pass


async def test_20_plus_workers():
    """測試 20+ 工作者極限場景"""
    logger.info("🔥 開始 20+ 工作者極限測試...")
    
    async with ConnectionPoolTestSuite() as suite:
        await suite.setup_test_environment()
        
        # 20+ 工作者壓力測試
        result = await suite.run_stress_test(max_workers=20, ramp_up_duration=5.0, test_duration=30.0)
        
        logger.info("="*80)
        logger.info("🔥 20+ 工作者極限測試結果")
        logger.info("="*80)
        logger.info(f"總操作數：{result.total_operations}")
        logger.info(f"成功操作：{result.successful_operations}")
        logger.info(f"失敗操作：{result.failed_operations}")
        logger.info(f"錯誤率：{result.error_rate_percentage:.2f}%")
        logger.info(f"吞吐量：{result.operations_per_second:.2f} ops/s")
        logger.info(f"P95響應時間：{result.p95_response_time_ms:.2f} ms")
        logger.info(f"最大連線數：{result.max_connections_used}")
        
        # 驗證 T2 標準
        t2_pass = (
            result.error_rate_percentage <= 1.0 and
            result.p95_response_time_ms <= 50.0 and
            (result.successful_operations / result.total_operations) >= 0.99
        )
        
        if t2_pass:
            logger.info("✅ 20+ 工作者測試符合 T2 標準！")
        else:
            logger.warning("⚠️  20+ 工作者測試未完全符合 T2 標準")
        
        return t2_pass


async def main():
    """主函數"""
    try:
        logger.info("=" * 80)
        logger.info("🧪 T2 併發測試框架驗證")
        logger.info("=" * 80)
        
        # 執行基礎測試
        basic_pass = await test_basic_concurrency()
        
        # 執行極限測試
        extreme_pass = await test_20_plus_workers()
        
        # 最終結果
        logger.info("=" * 80)
        logger.info("🏁 最終測試結果")
        logger.info("=" * 80)
        
        if basic_pass and extreme_pass:
            logger.info("🎉 所有併發測試都通過了 T2 標準！")
            sys.exit(0)
        else:
            logger.warning("⚠️  部分測試需要優化以符合 T2 標準")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"❌ 測試執行過程中發生錯誤：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())