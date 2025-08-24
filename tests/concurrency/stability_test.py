#!/usr/bin/env python3
"""
T2 - 長時間運行穩定性測試
測試連線池在長時間高併發負載下的穩定性和錯誤率控制
"""

import asyncio
import logging
import sys
import tempfile
import time
import random
from pathlib import Path
from typing import List, Dict, Any

# 添加專案路徑
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from services.connection_pool.connection_pool_manager import ConnectionPoolManager
from services.connection_pool.models import PoolConfiguration
from error_rate_monitor import ErrorRateMonitor, ConcurrencyTestReporter, PerformanceThresholds

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class LongRunningStabilityTest:
    """長時間運行穩定性測試套件"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
            self.db_path = self.temp_db.name
            self.temp_db.close()
        else:
            self.db_path = db_path
        
        # 配置連線池 - 針對長時間運行優化
        self.pool_config = PoolConfiguration(
            min_connections=5,
            max_connections=30,
            connection_timeout=20.0,
            acquire_timeout=15.0,
            idle_timeout=600.0,  # 10分鐘空閒超時
            enable_monitoring=True,
            stats_collection_interval=30  # 30秒收集一次統計
        )
        
        self.pool_manager = None
        self.monitor = ErrorRateMonitor(
            thresholds=PerformanceThresholds(
                max_error_rate=1.0,
                max_p95_response_time_ms=100.0,  # 長時間測試放寬至100ms
                min_success_rate=98.0,  # 放寬至98%
                max_concurrent_failures=3,
                alert_error_rate=0.8
            )
        )
        self.reporter = ConcurrencyTestReporter()
    
    async def setup(self):
        """設置測試環境"""
        logger.info(f"設置長時間穩定性測試環境 - 資料庫: {self.db_path}")
        
        self.pool_manager = ConnectionPoolManager(
            db_path=self.db_path,
            config=self.pool_config
        )
        
        await self.pool_manager.start()
        
        # 建立測試表
        async with self.pool_manager.connection() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS stability_test_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    email TEXT NOT NULL,
                    score INTEGER DEFAULT 0,
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS stability_test_activities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    activity_type TEXT NOT NULL,
                    points INTEGER DEFAULT 0,
                    metadata TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES stability_test_users(id)
                )
            """)
            
            # 建立索引
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON stability_test_users(username)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_users_score ON stability_test_users(score)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_activities_user_id ON stability_test_activities(user_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_activities_timestamp ON stability_test_activities(timestamp)")
            
            await conn.commit()
        
        # 填充基礎數據
        await self._populate_base_data(5000)  # 5000個用戶
        
        logger.info("長時間穩定性測試環境設置完成")
    
    async def _populate_base_data(self, num_users: int):
        """填充基礎測試數據"""
        logger.info(f"填充基礎測試數據：{num_users} 個用戶")
        
        async with self.pool_manager.connection() as conn:
            # 檢查是否已有數據
            async with conn.execute("SELECT COUNT(*) as count FROM stability_test_users") as cursor:
                existing = await cursor.fetchone()
                if existing and existing['count'] >= num_users:
                    logger.info("基礎數據已存在，跳過填充")
                    return
            
            # 批量插入用戶
            users_data = []
            for i in range(num_users):
                username = f"stable_user_{i:06d}"
                email = f"{username}@stability.test"
                score = random.randint(0, 10000)
                users_data.append((username, email, score))
            
            # 分批插入避免單次操作過大
            batch_size = 500
            for i in range(0, len(users_data), batch_size):
                batch = users_data[i:i + batch_size]
                await conn.executemany("""
                    INSERT OR IGNORE INTO stability_test_users (username, email, score) 
                    VALUES (?, ?, ?)
                """, batch)
                
                if i % (batch_size * 5) == 0:  # 每2500個用戶commit一次
                    await conn.commit()
                    logger.info(f"已插入 {min(i + batch_size, len(users_data))} / {len(users_data)} 用戶")
            
            await conn.commit()
        
        logger.info("基礎測試數據填充完成")
    
    async def run_stability_test(
        self,
        duration_minutes: int = 30,
        base_workers: int = 10,
        peak_workers: int = 20,
        surge_interval_minutes: int = 5
    ):
        """
        運行長時間穩定性測試
        
        Args:
            duration_minutes: 測試總時長（分鐘）
            base_workers: 基礎工作者數量
            peak_workers: 峰值工作者數量  
            surge_interval_minutes: 峰值負載間隔（分鐘）
        """
        logger.info(
            f"開始長時間穩定性測試：持續 {duration_minutes} 分鐘，"
            f"基礎負載 {base_workers} 工作者，峰值負載 {peak_workers} 工作者"
        )
        
        start_time = time.time()
        end_time = start_time + (duration_minutes * 60)
        next_surge_time = start_time + (surge_interval_minutes * 60)
        
        phase_counter = 0
        
        while time.time() < end_time:
            current_time = time.time()
            elapsed_minutes = (current_time - start_time) / 60
            
            # 決定當前工作者數量
            if current_time >= next_surge_time:
                current_workers = peak_workers
                phase_name = f"peak_load_{phase_counter}"
                next_surge_time = current_time + (surge_interval_minutes * 60)
                test_duration = 60  # 峰值持續1分鐘
                phase_counter += 1
            else:
                current_workers = base_workers
                phase_name = f"base_load_{int(elapsed_minutes)}"
                test_duration = min(60, (next_surge_time - current_time))
            
            logger.info(
                f"[{elapsed_minutes:.1f}分鐘] 執行 {phase_name}：{current_workers} 工作者，"
                f"持續 {test_duration:.1f} 秒"
            )
            
            # 執行此階段的測試
            phase_results = await self._run_test_phase(
                phase_name, current_workers, test_duration
            )
            
            # 記錄到監控系統
            self.monitor.record_operation_batch(
                successful_ops=phase_results['successful_operations'],
                failed_ops=phase_results['failed_operations'],
                response_times=phase_results['response_times'],
                concurrent_workers=current_workers,
                error_details=phase_results['error_types'],
                phase=phase_name
            )
            
            # 檢查是否需要提前終止（連續失敗過多）
            current_stats = self.monitor.get_current_stats()
            if current_stats['consecutive_failures'] >= 5:
                logger.error(
                    f"連續失敗過多 ({current_stats['consecutive_failures']})，提前終止測試"
                )
                break
            
            # 簡短的休息間隔
            await asyncio.sleep(2)
        
        total_duration = time.time() - start_time
        logger.info(f"長時間穩定性測試完成，總持續時間：{total_duration / 60:.1f} 分鐘")
        
        # 生成最終報告
        test_config = {
            "test_type": "long_running_stability",
            "planned_duration_minutes": duration_minutes,
            "actual_duration_minutes": total_duration / 60,
            "base_workers": base_workers,
            "peak_workers": peak_workers,
            "surge_interval_minutes": surge_interval_minutes
        }
        
        final_report = self.reporter.generate_comprehensive_report(
            self.monitor, test_config, total_duration
        )
        
        return final_report
    
    async def _run_test_phase(self, phase_name: str, num_workers: int, duration_seconds: float):
        """執行單個測試階段"""
        start_time = time.time()
        end_time = start_time + duration_seconds
        
        # 結果收集
        successful_operations = 0
        failed_operations = 0
        response_times = []
        error_types = {}
        
        async def stability_worker(worker_id: int):
            """穩定性測試工作者"""
            nonlocal successful_operations, failed_operations, response_times, error_types
            
            worker_ops = 0
            while time.time() < end_time:
                operation_start = time.time()
                
                try:
                    # 隨機選擇操作類型
                    operation_type = random.choices(
                        ['read_user', 'update_score', 'add_activity', 'complex_query'],
                        weights=[50, 20, 20, 10]  # 50% 讀取，20% 更新，20% 插入，10% 複雜查詢
                    )[0]
                    
                    async with self.pool_manager.connection() as conn:
                        if operation_type == 'read_user':
                            # 讀取用戶信息
                            user_id = random.randint(1, 5000)
                            async with conn.execute(
                                "SELECT * FROM stability_test_users WHERE id = ?", 
                                (user_id,)
                            ) as cursor:
                                result = await cursor.fetchone()
                        
                        elif operation_type == 'update_score':
                            # 更新用戶分數
                            user_id = random.randint(1, 5000)
                            score_change = random.randint(-100, 100)
                            await conn.execute("""
                                UPDATE stability_test_users 
                                SET score = score + ?, last_active = CURRENT_TIMESTAMP 
                                WHERE id = ?
                            """, (score_change, user_id))
                            await conn.commit()
                        
                        elif operation_type == 'add_activity':
                            # 添加活動記錄
                            user_id = random.randint(1, 5000)
                            activity_type = random.choice(['login', 'view', 'click', 'purchase'])
                            points = random.randint(1, 50)
                            await conn.execute("""
                                INSERT INTO stability_test_activities 
                                (user_id, activity_type, points, metadata)
                                VALUES (?, ?, ?, ?)
                            """, (user_id, activity_type, points, f"worker_{worker_id}"))
                            await conn.commit()
                        
                        elif operation_type == 'complex_query':
                            # 複雜查詢
                            async with conn.execute("""
                                SELECT u.id, u.username, u.score,
                                       COUNT(a.id) as activity_count,
                                       AVG(a.points) as avg_points,
                                       MAX(a.timestamp) as last_activity
                                FROM stability_test_users u
                                LEFT JOIN stability_test_activities a ON u.id = a.user_id
                                WHERE u.score > ?
                                GROUP BY u.id
                                ORDER BY u.score DESC
                                LIMIT 20
                            """, (random.randint(5000, 9000),)) as cursor:
                                results = await cursor.fetchall()
                    
                    successful_operations += 1
                    worker_ops += 1
                    operation_time = (time.time() - operation_start) * 1000
                    response_times.append(operation_time)
                
                except Exception as e:
                    failed_operations += 1
                    error_str = str(e)
                    error_type = "unknown_error"
                    
                    if "timeout" in error_str.lower():
                        error_type = "timeout"
                    elif "locked" in error_str.lower() or "busy" in error_str.lower():
                        error_type = "database_lock"
                    elif "connection" in error_str.lower():
                        error_type = "connection_error"
                    
                    if error_type not in error_types:
                        error_types[error_type] = 0
                    error_types[error_type] += 1
                    
                    logger.debug(f"Worker {worker_id} 操作失敗 ({error_type}): {e}")
                
                # 動態延遲：基礎負載時較長延遲，峰值負載時較短延遲
                if num_workers <= 10:
                    await asyncio.sleep(random.uniform(0.1, 0.3))  # 基礎負載
                else:
                    await asyncio.sleep(random.uniform(0.01, 0.1))  # 峰值負載
            
            logger.debug(f"Stability Worker {worker_id} 完成 {worker_ops} 操作")
        
        # 啟動工作者
        tasks = [stability_worker(i) for i in range(num_workers)]
        await asyncio.gather(*tasks)
        
        return {
            'successful_operations': successful_operations,
            'failed_operations': failed_operations,
            'response_times': response_times,
            'error_types': error_types,
            'duration_seconds': time.time() - start_time
        }
    
    async def cleanup(self):
        """清理測試環境"""
        if self.pool_manager:
            await self.pool_manager.stop()
        
        # 清理臨時資料庫
        if hasattr(self, 'temp_db'):
            try:
                import os
                os.unlink(self.db_path)
                logger.info("臨時測試資料庫已清理")
            except OSError:
                logger.warning(f"無法刪除臨時資料庫檔案：{self.db_path}")


async def main():
    """主函數 - 執行長時間穩定性測試"""
    logger.info("=" * 80)
    logger.info("🏃‍♂️ T2 長時間運行穩定性測試")
    logger.info("=" * 80)
    
    stability_test = LongRunningStabilityTest()
    
    try:
        await stability_test.setup()
        
        # 執行30分鐘穩定性測試
        # 對於演示，我們使用較短的時間（3分鐘）
        report = await stability_test.run_stability_test(
            duration_minutes=3,    # 演示用3分鐘，實際可設為30-60分鐘
            base_workers=8,
            peak_workers=15,
            surge_interval_minutes=1  # 演示用1分鐘間隔
        )
        
        # 顯示測試結果摘要
        logger.info("=" * 80)
        logger.info("📊 長時間穩定性測試結果")
        logger.info("=" * 80)
        
        exec_summary = report['executive_summary']
        t2_compliance = report['t2_compliance']
        
        logger.info(f"測試持續時間：{report['report_metadata']['test_duration_seconds'] / 60:.1f} 分鐘")
        logger.info(f"總操作數：{exec_summary['total_operations']}")
        logger.info(f"成功操作：{exec_summary['successful_operations']}")
        logger.info(f"失敗操作：{exec_summary['failed_operations']}")
        logger.info(f"整體成功率：{exec_summary['overall_success_rate_percent']:.2f}%")
        logger.info(f"整體錯誤率：{exec_summary['overall_error_rate_percent']:.2f}%")
        logger.info(f"平均吞吐量：{exec_summary['average_throughput_ops_per_sec']:.2f} ops/s")
        
        logger.info("\n🎯 T2 標準合規性：")
        logger.info(f"錯誤率要求：≤ 1.0%，實際：{t2_compliance['measured_performance']['actual_error_rate_percent']:.2f}%")
        logger.info(f"成功率要求：≥ 98%，實際：{t2_compliance['measured_performance']['actual_success_rate_percent']:.2f}%")
        logger.info(f"響應時間：平均 {t2_compliance['measured_performance']['average_response_time_ms']:.2f}ms")
        
        if t2_compliance['overall_t2_compliant']:
            logger.info("✅ 長時間穩定性測試通過 T2 標準！")
        else:
            logger.warning("⚠️ 長時間穩定性測試未完全符合 T2 標準")
        
        logger.info(f"合規分數：{t2_compliance['compliance_score']:.1f}/100")
        
        # 顯示建議
        if report['recommendations']:
            logger.info("\n💡 優化建議：")
            for i, rec in enumerate(report['recommendations'][:3], 1):
                logger.info(f"  {i}. {rec}")
        
        return t2_compliance['overall_t2_compliant']
        
    except Exception as e:
        logger.error(f"長時間穩定性測試失敗：{e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        await stability_test.cleanup()


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)