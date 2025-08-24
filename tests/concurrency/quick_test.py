#!/usr/bin/env python3
"""
T2 - 快速併發測試驗證
專注於10+工作者測試，簡化其他功能
"""

import asyncio
import logging
import sys
import tempfile
import time
from pathlib import Path

# 添加專案路徑
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from services.connection_pool.connection_pool_manager import ConnectionPoolManager
from services.connection_pool.models import PoolConfiguration

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def quick_10_worker_test():
    """快速10工作者併發測試"""
    logger.info("🚀 開始10工作者併發測試...")
    
    # 創建臨時資料庫
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    db_path = temp_db.name
    temp_db.close()
    
    # 配置連線池
    config = PoolConfiguration(
        min_connections=3,
        max_connections=15,
        connection_timeout=10.0,
        acquire_timeout=5.0,
        enable_monitoring=True
    )
    
    pool_manager = ConnectionPoolManager(db_path=db_path, config=config)
    
    try:
        await pool_manager.start()
        
        # 建立簡單測試表
        async with pool_manager.connection() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS simple_test (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await conn.commit()
        
        logger.info("開始10工作者併發操作...")
        start_time = time.time()
        
        # 統計變數
        successful_ops = 0
        failed_ops = 0
        response_times = []
        
        async def worker_task(worker_id: int):
            """工作者任務"""
            nonlocal successful_ops, failed_ops, response_times
            
            worker_successes = 0
            worker_failures = 0
            
            # 每個工作者執行10次操作
            for i in range(10):
                op_start = time.time()
                try:
                    async with pool_manager.connection() as conn:
                        # 插入數據
                        await conn.execute(
                            "INSERT INTO simple_test (data) VALUES (?)",
                            (f"Worker-{worker_id}-Op-{i}",)
                        )
                        
                        # 查詢數據
                        async with conn.execute("SELECT COUNT(*) as count FROM simple_test") as cursor:
                            result = await cursor.fetchone()
                            count = result['count'] if result else 0
                        
                        await conn.commit()
                        
                        worker_successes += 1
                        op_time = (time.time() - op_start) * 1000
                        response_times.append(op_time)
                        
                except Exception as e:
                    worker_failures += 1
                    logger.debug(f"Worker {worker_id} operation {i} failed: {e}")
                
                # 短暫延遲
                await asyncio.sleep(0.01)
            
            successful_ops += worker_successes
            failed_ops += worker_failures
            
            logger.info(f"Worker {worker_id}: {worker_successes}/{worker_successes + worker_failures} 成功")
        
        # 啟動10個工作者
        tasks = [worker_task(i) for i in range(10)]
        await asyncio.gather(*tasks)
        
        duration = time.time() - start_time
        total_ops = successful_ops + failed_ops
        
        # 計算統計
        success_rate = (successful_ops / total_ops) * 100 if total_ops > 0 else 0
        error_rate = (failed_ops / total_ops) * 100 if total_ops > 0 else 0
        throughput = total_ops / duration if duration > 0 else 0
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        # 計算P95響應時間
        sorted_times = sorted(response_times)
        p95_index = int(0.95 * len(sorted_times)) if sorted_times else 0
        p95_response_time = sorted_times[p95_index] if sorted_times else 0
        
        # 獲取連線池統計
        pool_stats = pool_manager.get_pool_stats()
        
        logger.info("="*80)
        logger.info("📊 10工作者併發測試結果")
        logger.info("="*80)
        logger.info(f"總操作數：{total_ops}")
        logger.info(f"成功操作：{successful_ops}")
        logger.info(f"失敗操作：{failed_ops}")
        logger.info(f"成功率：{success_rate:.2f}%")
        logger.info(f"錯誤率：{error_rate:.2f}%")
        logger.info(f"吞吐量：{throughput:.2f} ops/s")
        logger.info(f"平均響應時間：{avg_response_time:.2f} ms")
        logger.info(f"P95響應時間：{p95_response_time:.2f} ms")
        logger.info(f"連線池統計：活躍={pool_stats['active_connections']}, 空閒={pool_stats['idle_connections']}")
        
        # 驗證T2標準
        t2_pass = (
            error_rate <= 1.0 and
            p95_response_time <= 50.0 and
            success_rate >= 99.0
        )
        
        if t2_pass:
            logger.info("✅ 10工作者測試符合T2標準！")
        else:
            logger.warning("⚠️  10工作者測試未完全符合T2標準")
            if error_rate > 1.0:
                logger.warning(f"  - 錯誤率 {error_rate:.2f}% 超過1%")
            if p95_response_time > 50.0:
                logger.warning(f"  - P95響應時間 {p95_response_time:.2f}ms 超過50ms")
            if success_rate < 99.0:
                logger.warning(f"  - 成功率 {success_rate:.2f}% 低於99%")
        
        return t2_pass
        
    finally:
        await pool_manager.stop()
        
        # 清理
        import os
        try:
            os.unlink(db_path)
        except:
            pass


async def quick_20_worker_test():
    """快速20工作者壓力測試"""
    logger.info("🔥 開始20工作者壓力測試...")
    
    # 創建臨時資料庫
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    db_path = temp_db.name
    temp_db.close()
    
    # 較大的連線池配置
    config = PoolConfiguration(
        min_connections=5,
        max_connections=25,
        connection_timeout=15.0,
        acquire_timeout=10.0,
        enable_monitoring=True
    )
    
    pool_manager = ConnectionPoolManager(db_path=db_path, config=config)
    
    try:
        await pool_manager.start()
        
        # 建立測試表
        async with pool_manager.connection() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS stress_test (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    worker_id INTEGER NOT NULL,
                    data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await conn.commit()
        
        logger.info("開始20工作者壓力操作...")
        start_time = time.time()
        
        successful_ops = 0
        failed_ops = 0
        response_times = []
        
        async def stress_worker(worker_id: int):
            """壓力測試工作者"""
            nonlocal successful_ops, failed_ops, response_times
            
            worker_ops = 0
            # 每個工作者執行15次操作
            for i in range(15):
                op_start = time.time()
                try:
                    async with pool_manager.connection() as conn:
                        # 插入操作
                        await conn.execute(
                            "INSERT INTO stress_test (worker_id, data) VALUES (?, ?)",
                            (worker_id, f"StressData-{worker_id}-{i}")
                        )
                        
                        # 複雜查詢
                        async with conn.execute("""
                            SELECT worker_id, COUNT(*) as count, MAX(id) as max_id
                            FROM stress_test 
                            WHERE worker_id <= ?
                            GROUP BY worker_id
                            ORDER BY count DESC
                            LIMIT 5
                        """, (worker_id,)) as cursor:
                            results = await cursor.fetchall()
                        
                        await conn.commit()
                        
                        successful_ops += 1
                        worker_ops += 1
                        op_time = (time.time() - op_start) * 1000
                        response_times.append(op_time)
                        
                except Exception as e:
                    failed_ops += 1
                    logger.debug(f"Stress Worker {worker_id} op {i} failed: {e}")
                
                # 減少延遲增加壓力
                await asyncio.sleep(0.005)
            
            logger.debug(f"Stress Worker {worker_id}: {worker_ops} 操作完成")
        
        # 啟動20個工作者
        tasks = [stress_worker(i) for i in range(20)]
        await asyncio.gather(*tasks)
        
        duration = time.time() - start_time
        total_ops = successful_ops + failed_ops
        
        # 統計計算
        success_rate = (successful_ops / total_ops) * 100 if total_ops > 0 else 0
        error_rate = (failed_ops / total_ops) * 100 if total_ops > 0 else 0
        throughput = total_ops / duration if duration > 0 else 0
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        sorted_times = sorted(response_times)
        p95_index = int(0.95 * len(sorted_times)) if sorted_times else 0
        p95_response_time = sorted_times[p95_index] if sorted_times else 0
        
        pool_stats = pool_manager.get_pool_stats()
        
        logger.info("="*80)
        logger.info("🔥 20工作者壓力測試結果")
        logger.info("="*80)
        logger.info(f"總操作數：{total_ops}")
        logger.info(f"成功操作：{successful_ops}")
        logger.info(f"失敗操作：{failed_ops}")
        logger.info(f"成功率：{success_rate:.2f}%")
        logger.info(f"錯誤率：{error_rate:.2f}%")
        logger.info(f"吞吐量：{throughput:.2f} ops/s")
        logger.info(f"平均響應時間：{avg_response_time:.2f} ms")
        logger.info(f"P95響應時間：{p95_response_time:.2f} ms")
        logger.info(f"測試持續時間：{duration:.2f} 秒")
        logger.info(f"最大連線使用：{pool_stats['active_connections'] + pool_stats['idle_connections']}")
        
        # T2標準驗證
        t2_pass = (
            error_rate <= 1.0 and
            p95_response_time <= 50.0 and
            success_rate >= 99.0
        )
        
        if t2_pass:
            logger.info("✅ 20工作者壓力測試符合T2標準！")
        else:
            logger.warning("⚠️  20工作者壓力測試未完全符合T2標準")
        
        return t2_pass
        
    finally:
        await pool_manager.stop()
        
        import os
        try:
            os.unlink(db_path)
        except:
            pass


async def main():
    """主函數"""
    try:
        logger.info("=" * 80)
        logger.info("⚡ T2 快速併發測試驗證")
        logger.info("=" * 80)
        
        # 10工作者測試
        test_10_pass = await quick_10_worker_test()
        
        await asyncio.sleep(1)  # 短暫間隔
        
        # 20工作者測試
        test_20_pass = await quick_20_worker_test()
        
        # 最終結果
        logger.info("=" * 80)
        logger.info("🏁 快速併發測試總結")
        logger.info("=" * 80)
        
        if test_10_pass:
            logger.info("✅ 10工作者測試：通過T2標準")
        else:
            logger.warning("❌ 10工作者測試：未達T2標準")
        
        if test_20_pass:
            logger.info("✅ 20工作者測試：通過T2標準")
        else:
            logger.warning("❌ 20工作者測試：未達T2標準")
        
        if test_10_pass and test_20_pass:
            logger.info("🎉 所有併發測試都通過T2標準！")
            return True
        else:
            logger.warning("⚠️  部分測試需要優化")
            return False
            
    except Exception as e:
        logger.error(f"❌ 測試執行錯誤：{e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)