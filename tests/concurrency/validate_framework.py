#!/usr/bin/env python3
"""
T2 併發測試框架驗證腳本
驗證併發測試框架的基本功能和可靠性
"""

import sys
import asyncio
import tempfile
import traceback
from pathlib import Path

# 添加專案路徑
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tests.concurrency.test_connection_pool import (
    ConnectionPoolTestSuite, 
    ConcurrencyTestMonitor,
    PerformanceBenchmark
)


async def test_basic_functionality():
    """測試基本功能"""
    print("🔍 測試併發測試框架基本功能...")
    
    # 建立臨時測試資料庫
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
        test_db_path = tmp_file.name
    
    suite = ConnectionPoolTestSuite(test_db_path)
    monitor = ConcurrencyTestMonitor()
    
    try:
        # 測試1: 框架初始化
        print("  📋 測試套件初始化...")
        await suite.setup()
        print("    ✅ 初始化成功")
        
        # 測試2: 監控器功能
        print("  📊 測試監控器功能...")
        monitor.start_monitoring()
        monitor.record_operation(10.5, True)
        monitor.record_operation(25.0, False, "測試錯誤")
        
        metrics = monitor.get_metrics()
        assert len(metrics.response_times) == 2
        assert metrics.error_count == 1
        assert metrics.operation_count == 2
        print("    ✅ 監控器功能正常")
        
        # 測試3: 簡單併發測試 (2工作者)
        print("  🔄 執行簡單併發測試...")
        result = suite.run_concurrent_workers(
            worker_count=2,
            operations_per_worker=5,
            worker_function=suite._standard_database_worker,
            test_name="validation_test"
        )
        
        assert result.total_operations == 10  # 2工作者 × 5操作
        assert result.worker_count == 2
        print(f"    ✅ 併發測試完成: 成功率 {result.success_rate:.2%}, 錯誤率 {result.error_rate:.2%}")
        
        # 測試4: 效能基準系統
        print("  📈 測試效能基準系統...")
        benchmark = PerformanceBenchmark()
        benchmark.save_result(result)
        
        # 生成測試報告
        report = benchmark.generate_report([result])
        assert "test_summary" in report
        assert report["test_summary"]["total_tests"] == 1
        print("    ✅ 效能基準系統正常")
        
        # 測試5: 資料庫操作驗證
        print("  🗄️ 驗證資料庫操作...")
        test_data = await suite.database_manager.fetchall(
            "SELECT COUNT(*) as count FROM concurrency_test"
        )
        assert len(test_data) > 0
        print(f"    ✅ 資料庫操作正常，寫入 {test_data[0]['count'] if test_data else 0} 筆記錄")
        
        print("✅ 所有基本功能測試通過！")
        return True
        
    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        traceback.print_exc()
        return False
    finally:
        await suite.cleanup()
        
        # 清理臨時檔案
        try:
            Path(test_db_path).unlink()
        except:
            pass


async def test_error_handling():
    """測試錯誤處理能力"""
    print("🛡️ 測試錯誤處理能力...")
    
    # 測試無效資料庫路徑
    try:
        invalid_suite = ConnectionPoolTestSuite("/invalid/path/test.db")
        await invalid_suite.setup()
        
        # 如果到這裡沒有拋出異常，說明錯誤處理有問題
        print("❌ 未能正確處理無效資料庫路徑")
        return False
        
    except Exception as e:
        print(f"  ✅ 正確捕獲無效路徑錯誤: {type(e).__name__}")
    
    # 測試監控器異常情況
    monitor = ConcurrencyTestMonitor()
    monitor.record_operation(-1, False, "負數時間測試")  # 負數回應時間
    
    metrics = monitor.get_metrics()
    assert metrics.error_count == 1
    print("  ✅ 監控器能處理異常數據")
    
    print("✅ 錯誤處理測試通過！")
    return True


async def test_performance_thresholds():
    """測試效能閾值驗證"""
    print("⚡ 測試效能閾值驗證...")
    
    # 建立模擬測試結果
    from tests.concurrency.test_connection_pool import ConcurrencyTestResult
    
    # 良好效能結果
    good_result = ConcurrencyTestResult(
        test_name="threshold_test_good",
        worker_count=5,
        operations_per_worker=10,
        total_operations=50,
        successful_operations=50,
        failed_operations=0,
        success_rate=1.0,
        error_rate=0.0,
        avg_response_time_ms=15.0,
        p95_response_time_ms=25.0,
        p99_response_time_ms=35.0,
        total_duration_s=2.0,
        operations_per_second=25.0,
        memory_usage_mb=50.0,
        peak_memory_mb=52.0,
        errors=[],
        timestamp="2024-01-01T00:00:00"
    )
    
    # 不良效能結果
    bad_result = ConcurrencyTestResult(
        test_name="threshold_test_bad",
        worker_count=5,
        operations_per_worker=10,
        total_operations=50,
        successful_operations=45,
        failed_operations=5,
        success_rate=0.9,
        error_rate=0.1,  # 10% 錯誤率，超過1%標準
        avg_response_time_ms=75.0,
        p95_response_time_ms=120.0,  # 超過50ms標準
        p99_response_time_ms=150.0,
        total_duration_s=5.0,
        operations_per_second=10.0,
        memory_usage_mb=50.0,
        peak_memory_mb=80.0,  # 記憶體增長60%
        errors=["連線超時", "資料庫鎖定"],
        timestamp="2024-01-01T00:00:00"
    )
    
    # 測試閾值檢查邏輯
    def check_t2_standards(result):
        """檢查是否符合T2標準"""
        error_rate_ok = result.error_rate <= 0.01
        response_time_ok = result.p95_response_time_ms <= 50
        success_rate_ok = result.success_rate >= 0.99
        
        return error_rate_ok and response_time_ok and success_rate_ok
    
    # 驗證閾值檢查
    assert check_t2_standards(good_result) == True, "良好效能應該通過T2標準"
    assert check_t2_standards(bad_result) == False, "不良效能應該不通過T2標準"
    
    print("  ✅ 效能閾值驗證邏輯正確")
    print(f"    良好結果: 錯誤率 {good_result.error_rate:.1%}, P95 {good_result.p95_response_time_ms}ms")
    print(f"    不良結果: 錯誤率 {bad_result.error_rate:.1%}, P95 {bad_result.p95_response_time_ms}ms")
    
    print("✅ 效能閾值測試通過！")
    return True


async def main():
    """主驗證函數"""
    print("🚀 開始驗證 T2 併發測試框架...")
    print("="*60)
    
    test_results = []
    
    # 執行各項驗證測試
    tests = [
        ("基本功能", test_basic_functionality),
        ("錯誤處理", test_error_handling), 
        ("效能閾值", test_performance_thresholds)
    ]
    
    for test_name, test_func in tests:
        print(f"\n📋 執行 {test_name} 驗證...")
        try:
            result = await test_func()
            test_results.append((test_name, result))
            if result:
                print(f"✅ {test_name} 驗證通過")
            else:
                print(f"❌ {test_name} 驗證失敗")
        except Exception as e:
            print(f"❌ {test_name} 驗證異常: {e}")
            test_results.append((test_name, False))
    
    # 總結驗證結果
    print("\n" + "="*60)
    print("📋 T2 併發測試框架驗證總結")
    print("="*60)
    
    passed_count = sum(1 for _, result in test_results if result)
    total_count = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\n📊 總體結果: {passed_count}/{total_count} 項驗證通過")
    
    if passed_count == total_count:
        print("🎉 T2 併發測試框架驗證完全通過！框架可以正常使用。")
        return True
    else:
        print("⚠️ 部分驗證未通過，請檢查框架實現。")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)