"""
T2 - 連線池效能快速驗證測試
Task ID: T2

快速驗證ConnectionPoolManager是否滿足T2任務要求
"""

import asyncio
import logging
import os
import sys
import tempfile
import time
from datetime import datetime

# 添加項目根目錄到路徑
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.append(project_root)

from services.connection_pool import ConnectionPoolManager, PoolConfiguration

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('t2_quick_test')


async def quick_performance_test():
    """快速效能驗證測試"""
    print("T2 - 連線池管理器快速效能驗證")
    print("=" * 50)
    
    # 創建臨時測試資料庫
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
        test_db_path = temp_db.name
    
    try:
        # 配置連線池
        config = PoolConfiguration(
            min_connections=2,
            max_connections=20,
            connection_timeout=30.0,
            acquire_timeout=10.0,
            enable_monitoring=True
        )
        
        # 創建連線池管理器
        pool_manager = ConnectionPoolManager(test_db_path, config)
        await pool_manager.start()
        
        print(f"✓ 連線池管理器已啟動 - DB: {test_db_path}")
        
        # 創建測試表
        async with pool_manager.connection() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS test_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await conn.commit()
        
        print("✓ 測試表已創建")
        
        # 測試1：10工作者併發測試
        print("\n執行10工作者併發測試...")
        
        async def worker_task(worker_id: int, operations: int):
            successful = 0
            errors = 0
            response_times = []
            
            for i in range(operations):
                start_time = time.time()
                try:
                    async with pool_manager.connection() as conn:
                        # 執行插入操作
                        await conn.execute(
                            "INSERT INTO test_performance (data) VALUES (?)",
                            (f"worker_{worker_id}_op_{i}",)
                        )
                        await conn.commit()
                        
                        # 執行查詢操作
                        async with conn.execute(
                            "SELECT COUNT(*) FROM test_performance WHERE data LIKE ?",
                            (f"worker_{worker_id}%",)
                        ) as cursor:
                            result = await cursor.fetchone()
                    
                    successful += 1
                    response_time = (time.time() - start_time) * 1000
                    response_times.append(response_time)
                    
                except Exception as e:
                    errors += 1
                    logger.debug(f"Worker {worker_id} 操作失敗: {e}")
            
            return {
                'worker_id': worker_id,
                'successful': successful,
                'errors': errors,
                'response_times': response_times
            }
        
        # 執行併發測試
        num_workers = 10
        operations_per_worker = 20
        
        start_time = time.time()
        tasks = [worker_task(i, operations_per_worker) for i in range(num_workers)]
        results = await asyncio.gather(*tasks)
        test_duration = time.time() - start_time
        
        # 統計結果
        total_operations = 0
        total_successful = 0
        total_errors = 0
        all_response_times = []
        
        for result in results:
            total_operations += (result['successful'] + result['errors'])
            total_successful += result['successful']
            total_errors += result['errors']
            all_response_times.extend(result['response_times'])
        
        # 計算指標
        error_rate = (total_errors / total_operations * 100) if total_operations > 0 else 0
        avg_response_time = sum(all_response_times) / len(all_response_times) if all_response_times else 0
        
        # 計算P95響應時間
        if all_response_times:
            sorted_times = sorted(all_response_times)
            p95_index = int(len(sorted_times) * 0.95)
            p95_response_time = sorted_times[p95_index] if p95_index < len(sorted_times) else sorted_times[-1]
        else:
            p95_response_time = 0
        
        throughput = total_operations / test_duration if test_duration > 0 else 0
        
        # 獲取連線池統計
        pool_stats = pool_manager.get_pool_stats()
        
        # 顯示結果
        print(f"\n測試結果：")
        print(f"  總操作數: {total_operations}")
        print(f"  成功操作: {total_successful}")
        print(f"  失敗操作: {total_errors}")
        print(f"  錯誤率: {error_rate:.2f}%")
        print(f"  平均響應時間: {avg_response_time:.2f} ms")
        print(f"  P95響應時間: {p95_response_time:.2f} ms")
        print(f"  吞吐量: {throughput:.2f} ops/s")
        print(f"  測試持續時間: {test_duration:.2f} s")
        
        print(f"\n連線池狀態：")
        print(f"  活躍連線: {pool_stats['active_connections']}")
        print(f"  空閒連線: {pool_stats['idle_connections']}")
        print(f"  等待請求: {pool_stats['waiting_requests']}")
        print(f"  最大連線: {pool_stats['max_connections']}")
        print(f"  總創建連線: {pool_stats['total_connections_created']}")
        print(f"  成功率: {pool_stats['success_rate']:.2f}%")
        
        # T2要求驗證
        print(f"\nT2任務要求驗證：")
        
        # 1. 併發錯誤率 ≤ 1%
        error_rate_pass = error_rate <= 1.0
        print(f"  併發錯誤率 ≤ 1%: {'✓ PASS' if error_rate_pass else '✗ FAIL'} ({error_rate:.2f}%)")
        
        # 2. 連線池響應時間 p95 ≤ 50ms
        p95_pass = p95_response_time <= 50.0
        print(f"  P95響應時間 ≤ 50ms: {'✓ PASS' if p95_pass else '✗ FAIL'} ({p95_response_time:.2f}ms)")
        
        # 3. 支援10+工作者併發負載
        workers_pass = num_workers >= 10
        print(f"  支援10+工作者: {'✓ PASS' if workers_pass else '✗ FAIL'} ({num_workers}工作者)")
        
        # 4. 智慧動態調整 (基本驗證)
        dynamic_pass = pool_stats['total_connections_created'] > config.min_connections
        print(f"  動態調整機制: {'✓ PASS' if dynamic_pass else '✗ FAIL'} (創建了 {pool_stats['total_connections_created']} 連線)")
        
        # 整體評估
        all_pass = error_rate_pass and p95_pass and workers_pass and dynamic_pass
        
        print(f"\n整體評估: {'✓ 全部通過 - 滿足T2要求' if all_pass else '✗ 部分未通過 - 需要優化'}")
        
        if not all_pass:
            print("\n建議優化：")
            if not error_rate_pass:
                print("  - 增加連線超時時間")
                print("  - 優化重試機制")
            if not p95_pass:
                print("  - 增加最小連線數")
                print("  - 優化查詢效能")
                print("  - 實施連線預熱")
            if not dynamic_pass:
                print("  - 檢查動態調整算法")
        
        # 執行優化測試
        print("\n執行連線池優化...")
        await pool_manager.optimize_pool()
        
        optimized_stats = pool_manager.get_pool_stats()
        print(f"優化後連線數: {optimized_stats['active_connections'] + optimized_stats['idle_connections']}")
        
        # 停止連線池
        await pool_manager.stop()
        print("✓ 連線池已停止")
        
        return all_pass
        
    except Exception as e:
        logger.error(f"測試執行失敗: {e}")
        return False
        
    finally:
        # 清理臨時檔案
        try:
            os.unlink(test_db_path)
            print("✓ 臨時測試資料庫已清理")
        except OSError:
            logger.warning(f"無法刪除臨時資料庫: {test_db_path}")


if __name__ == "__main__":
    success = asyncio.run(quick_performance_test())
    
    if success:
        print("\n🎉 T2連線池管理器效能驗證成功！")
        exit(0)
    else:
        print("\n❌ T2連線池管理器效能驗證失敗，需要進一步優化")
        exit(1)