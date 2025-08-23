"""
T4 - 整合測試：完整的遷移與隔離流程
測試所有T4組件的端到端整合
"""

import pytest
import asyncio
import tempfile
import os
from pathlib import Path

from scripts.enhanced_migration_manager import EnhancedMigrationManager
from test_utils.enhanced_test_isolation import (
    TestConfiguration,
    isolated_test_environment,
    fast_test_environment,
    thorough_test_environment,
    TestDataFactory,
    verify_test_isolation,
    run_isolation_stress_test
)


class TestMigrationAndIsolationIntegration:
    """T4 整合測試 - 遷移與隔離的端到端流程"""
    
    @pytest.mark.asyncio
    async def test_complete_migration_lifecycle_with_isolation(self):
        """測試完整的遷移生命週期與隔離"""
        # 使用完整的測試環境
        async with thorough_test_environment() as env:
            manager = EnhancedMigrationManager(env['db_path'])
            factory = TestDataFactory(env['test_id'])
            
            # 階段1: 準備測試資料
            await self._prepare_legacy_data(env['db_path'], factory)
            
            # 階段2: 執行雙態驗證
            dual_state_result = await manager.verify_dual_state_migration("003")
            assert dual_state_result['validation_passed'] == True
            
            # 階段3: 應用遷移
            migration_result = await manager.apply_migration("003")
            assert migration_result['success'] == True
            assert migration_result['validation_passed'] == True
            
            # 階段4: 驗證遷移後的資料完整性
            integrity_result = await manager.check_data_integrity()
            assert integrity_result['success'] == True
            
            # 階段5: 驗證UPSERT語義
            await self._test_upsert_semantics(env['db_path'])
            
            # 階段6: 測試回滾機制
            if migration_result['rollback_available']:
                rollback_result = await manager.rollback_migration("003")
                assert rollback_result['success'] == True
                
                # 重新應用遷移
                reapply_result = await manager.apply_migration("003")
                assert reapply_result['success'] == True
    
    @pytest.mark.asyncio
    async def test_parallel_migration_isolation(self):
        """測試並行遷移的隔離效果"""
        # 創建多個並行測試環境
        results = []
        
        async def run_migration_in_isolation(env_id: int):
            config = TestConfiguration(use_memory_db=True, validate_isolation=True)
            async with isolated_test_environment(config) as env:
                manager = EnhancedMigrationManager(env['db_path'])
                factory = TestDataFactory(f"parallel_{env_id}")
                
                # 準備不同的測試資料
                await self._prepare_legacy_data(env['db_path'], factory)
                
                # 執行遷移
                result = await manager.apply_migration("003")
                
                # 驗證完整性
                integrity = await manager.check_data_integrity()
                
                return {
                    'env_id': env_id,
                    'migration_success': result['success'],
                    'integrity_success': integrity['success'],
                    'test_id': env['test_id'],
                    'db_path': env['db_path']
                }
        
        # 並行執行
        tasks = [run_migration_in_isolation(i) for i in range(3)]
        results = await asyncio.gather(*tasks)
        
        # 驗證所有遷移都成功且互不干擾
        for result in results:
            assert result['migration_success'] == True
            assert result['integrity_success'] == True
        
        # 驗證測試環境的隔離
        assert len(set(r['test_id'] for r in results)) == 3  # 所有測試ID都不同
        assert len(set(r['db_path'] for r in results)) == 3  # 所有資料庫路徑都不同
    
    @pytest.mark.asyncio
    async def test_performance_requirements_integration(self):
        """測試整合場景下的效能要求"""
        performance_config = TestConfiguration(
            use_memory_db=True,
            enable_parallel=True,
            cleanup_timeout=3.0,
            validate_isolation=False
        )
        
        # 記錄效能指標
        setup_times = []
        migration_times = []
        integrity_check_times = []
        
        for i in range(5):  # 多次測試以獲得穩定的指標
            async with isolated_test_environment(performance_config) as env:
                # 記錄設置時間
                setup_times.append(env['setup_time_ms'])
                
                manager = EnhancedMigrationManager(env['db_path'])
                factory = TestDataFactory(f"perf_test_{i}")
                
                # 準備較大的資料集
                await self._prepare_large_dataset(env['db_path'], factory)
                
                # 測量遷移時間
                import time
                start_time = time.time()
                migration_result = await manager.apply_migration("003")
                migration_time = (time.time() - start_time) * 1000  # 轉換為毫秒
                migration_times.append(migration_time)
                
                assert migration_result['success'] == True
                
                # 測量完整性檢查時間
                start_time = time.time()
                integrity_result = await manager.check_data_integrity()
                integrity_time = (time.time() - start_time) * 1000
                integrity_check_times.append(integrity_time)
                
                assert integrity_result['success'] == True
        
        # 驗證效能要求
        avg_setup_time = sum(setup_times) / len(setup_times)
        avg_migration_time = sum(migration_times) / len(migration_times)
        avg_integrity_time = sum(integrity_check_times) / len(integrity_check_times)
        
        # N-2: 測試隔離overhead < 500ms
        assert avg_setup_time < 500, f"平均設置時間 {avg_setup_time:.1f}ms 超過 500ms"
        
        # N-1: 遷移時間應該合理（對於測試資料集）
        assert avg_migration_time < 5000, f"平均遷移時間 {avg_migration_time:.1f}ms 過長"
        
        print(f"效能指標 - 設置: {avg_setup_time:.1f}ms, 遷移: {avg_migration_time:.1f}ms, 完整性: {avg_integrity_time:.1f}ms")
    
    @pytest.mark.asyncio
    async def test_error_recovery_integration(self):
        """測試錯誤恢復的整合場景"""
        async with fast_test_environment() as env:
            manager = EnhancedMigrationManager(env['db_path'])
            
            # 場景1: 故意導致遷移失敗
            # 創建一個會導致衝突的表結構
            import aiosqlite
            async with aiosqlite.connect(env['db_path']) as db:
                await db.execute("""
                    CREATE TABLE activity_meter (
                        id INTEGER PRIMARY KEY,
                        data TEXT
                    )
                """)
                await db.commit()
            
            # 嘗試應用遷移（應該失敗）
            migration_result = await manager.apply_migration("003")
            assert migration_result['success'] == False
            
            # 場景2: 清理並重試
            async with aiosqlite.connect(env['db_path']) as db:
                await db.execute("DROP TABLE activity_meter")
                await db.commit()
            
            # 重新嘗試遷移（應該成功）
            retry_result = await manager.apply_migration("003")
            assert retry_result['success'] == True
            
            # 場景3: 驗證恢復後的系統狀態
            integrity_result = await manager.check_data_integrity()
            assert integrity_result['success'] == True
    
    @pytest.mark.asyncio
    async def test_data_consistency_across_migrations(self):
        """測試跨遷移的資料一致性"""
        async with thorough_test_environment() as env:
            manager = EnhancedMigrationManager(env['db_path'])
            factory = TestDataFactory(env['test_id'])
            
            # 準備初始資料
            original_data = await self._prepare_legacy_data(env['db_path'], factory)
            
            # 記錄遷移前的資料校驗和
            pre_migration_checksum = await self._calculate_data_checksum(env['db_path'])
            
            # 執行遷移
            migration_result = await manager.apply_migration("003")
            assert migration_result['success'] == True
            
            # 驗證遷移後資料的邏輯一致性
            post_migration_data = await self._extract_migrated_data(env['db_path'])
            
            # 檢查資料完整性
            assert len(post_migration_data) <= len(original_data)  # 可能因去重而減少
            
            # 驗證關鍵資料保持一致
            for guild_id, user_id in original_data.keys():
                # 應該能找到對應的記錄（可能已合併）
                found = any(
                    row['guild_id'] == guild_id and row['user_id'] == user_id
                    for row in post_migration_data
                )
                assert found, f"遷移後丟失資料: guild_id={guild_id}, user_id={user_id}"
    
    @pytest.mark.asyncio
    async def test_comprehensive_regression_suite(self):
        """完整的回歸測試套件 - F-4"""
        async with thorough_test_environment() as env:
            manager = EnhancedMigrationManager(env['db_path'])
            factory = TestDataFactory(env['test_id'])
            
            # 建立基準資料集
            baseline_data = await self._create_regression_baseline(env['db_path'], factory)
            
            # 執行完整的遷移流程
            await manager.apply_migration("003")
            
            # 執行回歸測試檢查
            regression_results = []
            
            # 檢查1: 資料完整性
            integrity_result = await manager.check_data_integrity()
            regression_results.append({
                'test': 'data_integrity',
                'passed': integrity_result['success'],
                'details': integrity_result
            })
            
            # 檢查2: 唯一性約束
            unique_check = await self._verify_uniqueness_constraints(env['db_path'])
            regression_results.append({
                'test': 'uniqueness_constraints',
                'passed': unique_check['success'],
                'details': unique_check
            })
            
            # 檢查3: UPSERT語義
            upsert_check = await self._test_upsert_semantics(env['db_path'])
            regression_results.append({
                'test': 'upsert_semantics',
                'passed': upsert_check['success'],
                'details': upsert_check
            })
            
            # 檢查4: 效能基準
            performance_check = await self._verify_performance_baseline(env['db_path'])
            regression_results.append({
                'test': 'performance_baseline',
                'passed': performance_check['success'],
                'details': performance_check
            })
            
            # 彙總回歸測試結果
            total_tests = len(regression_results)
            passed_tests = sum(1 for r in regression_results if r['passed'])
            success_rate = passed_tests / total_tests
            
            # 驗證回歸測試成功率
            assert success_rate >= 0.95, f"回歸測試成功率 {success_rate:.1%} 低於 95%"
            
            # 記錄詳細結果
            for result in regression_results:
                if not result['passed']:
                    print(f"回歸測試失敗: {result['test']} - {result['details']}")
    
    # 輔助方法
    async def _prepare_legacy_data(self, db_path: str, factory: TestDataFactory):
        """準備遺留測試資料"""
        import aiosqlite
        
        # 創建舊版表結構 (沒有主鍵約束，這是要測試的問題)
        async with aiosqlite.connect(db_path) as db:
            # 先檢查表是否已存在 (由於遷移)
            cursor = await db.execute("""
                SELECT sql FROM sqlite_master WHERE type='table' AND name='activity_meter'
            """)
            existing_table = await cursor.fetchone()
            
            if existing_table and 'PRIMARY KEY' in existing_table[0]:
                # 表已經有主鍵約束，表示遷移已經運行
                print("發現已遷移的activity_meter表結構")
            else:
                # 創建舊版本的表結構
                await db.execute("DROP TABLE IF EXISTS activity_meter")
                await db.execute("""
                    CREATE TABLE activity_meter (
                        guild_id INTEGER,
                        user_id INTEGER,
                        score REAL DEFAULT 0,
                        last_msg INTEGER DEFAULT 0
                    )
                """)
            
            # 插入包含重複記錄的測試資料
            test_data = {}
            raw_data = []
            
            for i in range(10):
                guild_id = factory.create_test_guild_id(f"guild_{i % 3}")  # 重複伺服器
                user_id = factory.create_test_user_id(f"user_{i % 5}")    # 重複用戶
                
                # 記錄原始資料
                key = (guild_id, user_id)
                if key not in test_data:
                    test_data[key] = []
                
                record = {
                    'guild_id': guild_id,
                    'user_id': user_id,
                    'score': float(i * 10),
                    'last_msg': i * 1000
                }
                test_data[key].append(record)
                raw_data.append((guild_id, user_id, record['score'], record['last_msg']))
            
            await db.executemany("""
                INSERT INTO activity_meter (guild_id, user_id, score, last_msg)
                VALUES (?, ?, ?, ?)
            """, raw_data)
            await db.commit()
            
            return test_data
    
    async def _prepare_large_dataset(self, db_path: str, factory: TestDataFactory):
        """準備大型資料集以測試效能"""
        import aiosqlite
        
        async with aiosqlite.connect(db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS activity_meter (
                    guild_id INTEGER,
                    user_id INTEGER,
                    score REAL DEFAULT 0,
                    last_msg INTEGER DEFAULT 0
                )
            """)
            
            # 生成較大的資料集
            batch_size = 100
            for batch in range(5):  # 500筆記錄
                test_data = []
                for i in range(batch_size):
                    record_id = batch * batch_size + i
                    guild_id = factory.create_test_guild_id(f"guild_{record_id % 10}")
                    user_id = factory.create_test_user_id(f"user_{record_id}")
                    
                    test_data.append((guild_id, user_id, float(record_id), record_id * 1000))
                
                await db.executemany("""
                    INSERT INTO activity_meter (guild_id, user_id, score, last_msg)
                    VALUES (?, ?, ?, ?)
                """, test_data)
            
            await db.commit()
    
    async def _test_upsert_semantics(self, db_path: str):
        """測試UPSERT語義"""
        import aiosqlite
        
        async with aiosqlite.connect(db_path) as db:
            # 檢查表結構，確保updated_at欄位存在
            cursor = await db.execute("PRAGMA table_info(activity_meter)")
            columns = await cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            has_updated_at = 'updated_at' in column_names
            
            # 插入初始記錄
            if has_updated_at:
                await db.execute("""
                    INSERT INTO activity_meter (guild_id, user_id, score, last_msg, updated_at)
                    VALUES (1, 1, 100.0, 123456, CURRENT_TIMESTAMP)
                    ON CONFLICT(guild_id, user_id) DO UPDATE SET
                        score = excluded.score,
                        last_msg = excluded.last_msg,
                        updated_at = CURRENT_TIMESTAMP
                """)
                
                # 更新相同記錄
                await db.execute("""
                    INSERT INTO activity_meter (guild_id, user_id, score, last_msg, updated_at)
                    VALUES (1, 1, 200.0, 654321, CURRENT_TIMESTAMP)
                    ON CONFLICT(guild_id, user_id) DO UPDATE SET
                        score = excluded.score,
                        last_msg = excluded.last_msg,
                        updated_at = CURRENT_TIMESTAMP
                """)
            else:
                # 如果沒有updated_at欄位，使用基本的UPSERT
                await db.execute("""
                    INSERT INTO activity_meter (guild_id, user_id, score, last_msg)
                    VALUES (1, 1, 100.0, 123456)
                    ON CONFLICT(guild_id, user_id) DO UPDATE SET
                        score = excluded.score,
                        last_msg = excluded.last_msg
                """)
                
                # 更新相同記錄
                await db.execute("""
                    INSERT INTO activity_meter (guild_id, user_id, score, last_msg)
                    VALUES (1, 1, 200.0, 654321)
                    ON CONFLICT(guild_id, user_id) DO UPDATE SET
                        score = excluded.score,
                        last_msg = excluded.last_msg
                """)
            
            # 驗證只有一筆記錄且值已更新
            cursor = await db.execute("""
                SELECT COUNT(*), score, last_msg FROM activity_meter 
                WHERE guild_id = 1 AND user_id = 1
            """)
            result = await cursor.fetchone()
            
            return {
                'success': result[0] == 1 and result[1] == 200.0 and result[2] == 654321,
                'count': result[0],
                'score': result[1],
                'last_msg': result[2],
                'has_updated_at': has_updated_at
            }
    
    async def _calculate_data_checksum(self, db_path: str):
        """計算資料校驗和"""
        import aiosqlite
        import hashlib
        
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute("""
                SELECT guild_id, user_id, score, last_msg FROM activity_meter
                ORDER BY guild_id, user_id
            """)
            rows = await cursor.fetchall()
            
            data_str = str(rows)
            return hashlib.md5(data_str.encode()).hexdigest()
    
    async def _extract_migrated_data(self, db_path: str):
        """提取遷移後的資料"""
        import aiosqlite
        
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute("""
                SELECT guild_id, user_id, score, last_msg FROM activity_meter
                ORDER BY guild_id, user_id
            """)
            rows = await cursor.fetchall()
            
            return [
                {
                    'guild_id': row[0],
                    'user_id': row[1],
                    'score': row[2],
                    'last_msg': row[3]
                }
                for row in rows
            ]
    
    async def _create_regression_baseline(self, db_path: str, factory: TestDataFactory):
        """創建回歸測試基準"""
        return await self._prepare_legacy_data(db_path, factory)
    
    async def _verify_uniqueness_constraints(self, db_path: str):
        """驗證唯一性約束"""
        import aiosqlite
        
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute("""
                SELECT guild_id, user_id, COUNT(*) as cnt
                FROM activity_meter
                GROUP BY guild_id, user_id
                HAVING COUNT(*) > 1
            """)
            duplicates = await cursor.fetchall()
            
            return {
                'success': len(duplicates) == 0,
                'duplicate_count': len(duplicates),
                'duplicates': duplicates
            }
    
    async def _verify_performance_baseline(self, db_path: str):
        """驗證效能基準"""
        import aiosqlite
        import time
        
        # 測試查詢效能
        start_time = time.time()
        
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute("""
                SELECT COUNT(*) FROM activity_meter
            """)
            await cursor.fetchone()
            
            cursor = await db.execute("""
                SELECT guild_id, user_id, MAX(score) FROM activity_meter
                GROUP BY guild_id, user_id
                LIMIT 10
            """)
            await cursor.fetchall()
        
        query_time = time.time() - start_time
        
        return {
            'success': query_time < 1.0,  # 查詢應在1秒內完成
            'query_time': query_time
        }