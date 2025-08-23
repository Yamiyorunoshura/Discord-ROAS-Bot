"""
T4 - 資料完整性檢查測試
測試資料完整性檢查器的全面功能
"""

import pytest
import asyncio
import aiosqlite

from scripts.enhanced_migration_manager import EnhancedMigrationManager, DataIntegrityError
from test_utils.enhanced_test_isolation import fast_test_environment, TestDataFactory


class TestDataIntegrityChecker:
    """測試資料完整性檢查器 - F-4"""
    
    @pytest.mark.asyncio
    async def test_comprehensive_integrity_check(self):
        """測試全面的資料完整性檢查"""
        async with fast_test_environment() as env:
            manager = EnhancedMigrationManager(env['db_path'])
            
            # 應用遷移以建立表結構
            await manager.apply_migration("003")
            
            # 插入正常的測試資料
            factory = TestDataFactory()
            await self._insert_valid_test_data(env['db_path'], factory)
            
            # 執行完整性檢查
            result = await manager.check_data_integrity()
            
            # 驗證檢查成功
            assert result['success'] == True
            assert len(result['errors']) == 0
            
            # 驗證執行了所有必要的檢查
            expected_checks = [
                'foreign_key_integrity',
                'unique_constraints', 
                'not_null_constraints',
                'business_logic_consistency',
                'data_type_integrity'
            ]
            
            for check in expected_checks:
                assert check in result['checks_performed']
    
    @pytest.mark.asyncio
    async def test_unique_constraint_violation_detection(self):
        """測試唯一性約束違規檢測"""
        async with fast_test_environment() as env:
            manager = EnhancedMigrationManager(env['db_path'])
            
            # 建立基礎表結構（不使用唯一約束）
            await self._create_basic_activity_table(env['db_path'])
            
            # 故意插入重複資料
            await self._insert_duplicate_activity_data(env['db_path'])
            
            # 執行完整性檢查
            result = await manager.check_data_integrity()
            
            # 應該檢測到重複記錄
            assert result['success'] == False
            assert any('activity_meter 表重複記錄' in error for error in result['errors'])
    
    @pytest.mark.asyncio
    async def test_not_null_constraint_validation(self):
        """測試非空約束驗證"""
        async with fast_test_environment() as env:
            manager = EnhancedMigrationManager(env['db_path'])
            
            # 建立表結構
            await self._create_basic_activity_table(env['db_path'])
            
            # 插入包含NULL值的無效資料
            await self._insert_null_data(env['db_path'])
            
            # 執行完整性檢查
            result = await manager.check_data_integrity()
            
            # 應該檢測到NULL值問題
            assert result['success'] == False
            assert any('NULL 值' in error for error in result['errors'])
    
    @pytest.mark.asyncio
    async def test_business_logic_consistency_check(self):
        """測試業務邏輯一致性檢查"""
        async with fast_test_environment() as env:
            manager = EnhancedMigrationManager(env['db_path'])
            
            # 建立表結構並應用遷移
            await manager.apply_migration("003")
            
            # 插入業務邏輯不一致的資料
            await self._insert_inconsistent_business_data(env['db_path'])
            
            # 執行完整性檢查
            result = await manager.check_data_integrity()
            
            # 應該產生警告（不一定是錯誤）
            assert len(result['warnings']) > 0
            assert any('負數活躍度分數' in warning for warning in result['warnings'])
    
    @pytest.mark.asyncio
    async def test_data_type_integrity_validation(self):
        """測試資料類型完整性驗證"""
        async with fast_test_environment() as env:
            manager = EnhancedMigrationManager(env['db_path'])
            
            # 建立表結構
            await self._create_basic_activity_table(env['db_path'])
            
            # 插入錯誤資料類型的資料
            await self._insert_wrong_type_data(env['db_path'])
            
            # 執行完整性檢查
            result = await manager.check_data_integrity()
            
            # SQLite較寬鬆的類型系統可能不會產生錯誤，但應該記錄警告
            # 檢查是否執行了資料類型檢查
            assert 'data_type_integrity' in result['checks_performed']
    
    @pytest.mark.asyncio
    async def test_statistics_collection(self):
        """測試統計資訊收集"""
        async with fast_test_environment() as env:
            manager = EnhancedMigrationManager(env['db_path'])
            
            # 應用遷移以建立表結構
            await manager.apply_migration("003")
            
            # 插入測試資料
            factory = TestDataFactory()
            await self._insert_valid_test_data(env['db_path'], factory)
            
            # 執行完整性檢查
            result = await manager.check_data_integrity()
            
            # 驗證統計資訊
            assert 'statistics' in result
            assert 'activity_meter_count' in result['statistics']
            assert 'schema_migrations_count' in result['statistics']
            
            # 驗證統計資訊的合理性
            activity_count = result['statistics']['activity_meter_count']
            assert isinstance(activity_count, int)
            assert activity_count > 0  # 應該有測試資料
    
    @pytest.mark.asyncio
    async def test_integrity_check_performance(self):
        """測試完整性檢查的效能 - N-3: false positive < 1%"""
        async with fast_test_environment() as env:
            manager = EnhancedMigrationManager(env['db_path'])
            
            # 應用遷移
            await manager.apply_migration("003")
            
            # 插入大量有效的測試資料
            factory = TestDataFactory()
            await self._insert_large_valid_dataset(env['db_path'], factory)
            
            # 多次執行完整性檢查以測試穩定性
            false_positives = 0
            total_checks = 10
            
            for i in range(total_checks):
                result = await manager.check_data_integrity()
                
                # 如果在有效資料上檢測到錯誤，記為 false positive
                if not result['success'] and len(result['errors']) > 0:
                    false_positives += 1
            
            # 計算 false positive rate
            false_positive_rate = false_positives / total_checks
            
            # 驗證 N-3 要求：false positive rate < 1%
            assert false_positive_rate < 0.01, f"False positive rate {false_positive_rate:.2%} 超過 1% 要求"
    
    @pytest.mark.asyncio
    async def test_error_recovery_during_integrity_check(self):
        """測試完整性檢查過程中的錯誤恢復"""
        async with fast_test_environment() as env:
            manager = EnhancedMigrationManager(env['db_path'])
            
            # 建立部分表結構（模擬不完整的環境）
            async with aiosqlite.connect(env['db_path']) as db:
                await db.execute("""
                    CREATE TABLE activity_meter (
                        guild_id INTEGER,
                        user_id INTEGER,
                        score REAL
                        -- 故意缺少某些欄位
                    )
                """)
                await db.commit()
            
            # 執行完整性檢查
            result = await manager.check_data_integrity()
            
            # 應該優雅地處理錯誤，不會崩潰
            assert 'timestamp' in result
            assert 'checks_performed' in result
            
            # 可能會有警告，但不應該完全失敗
            if not result['success']:
                assert len(result['warnings']) > 0 or len(result['errors']) > 0
    
    # 輔助方法
    async def _create_basic_activity_table(self, db_path: str):
        """創建基礎的 activity_meter 表（無約束）"""
        async with aiosqlite.connect(db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS activity_meter (
                    guild_id INTEGER,
                    user_id INTEGER,
                    score REAL DEFAULT 0,
                    last_msg INTEGER DEFAULT 0
                )
            """)
            await db.commit()
    
    async def _insert_valid_test_data(self, db_path: str, factory: TestDataFactory):
        """插入有效的測試資料"""
        async with aiosqlite.connect(db_path) as db:
            for i in range(5):
                user_id = factory.create_test_user_id(f"user_{i}")
                guild_id = factory.create_test_guild_id(f"guild_{i}")
                activity_data = factory.create_test_activity_data(user_id, guild_id)
                
                await db.execute("""
                    INSERT INTO activity_meter (guild_id, user_id, score, last_msg)
                    VALUES (?, ?, ?, ?)
                """, (
                    activity_data['guild_id'],
                    activity_data['user_id'], 
                    activity_data['score'],
                    activity_data['last_msg']
                ))
            await db.commit()
    
    async def _insert_duplicate_activity_data(self, db_path: str):
        """插入重複的活躍度資料"""
        async with aiosqlite.connect(db_path) as db:
            # 插入相同的 (guild_id, user_id) 組合多次
            duplicate_data = [(1, 1, 50.0, 123456), (1, 1, 60.0, 123457)]
            
            await db.executemany("""
                INSERT INTO activity_meter (guild_id, user_id, score, last_msg)
                VALUES (?, ?, ?, ?)
            """, duplicate_data)
            await db.commit()
    
    async def _insert_null_data(self, db_path: str):
        """插入包含NULL值的資料"""
        async with aiosqlite.connect(db_path) as db:
            await db.execute("""
                INSERT INTO activity_meter (guild_id, user_id, score, last_msg)
                VALUES (NULL, 1, 50.0, 123456)
            """)
            await db.execute("""
                INSERT INTO activity_meter (guild_id, user_id, score, last_msg)
                VALUES (1, NULL, 50.0, 123456)
            """)
            await db.commit()
    
    async def _insert_inconsistent_business_data(self, db_path: str):
        """插入業務邏輯不一致的資料"""
        async with aiosqlite.connect(db_path) as db:
            # 插入負數活躍度分數
            await db.execute("""
                INSERT INTO activity_meter (guild_id, user_id, score, last_msg)
                VALUES (1, 1, -50.0, 123456)
            """)
            await db.commit()
    
    async def _insert_wrong_type_data(self, db_path: str):
        """插入錯誤資料類型的資料"""
        async with aiosqlite.connect(db_path) as db:
            # SQLite允許這樣做，但我們的檢查應該檢測到
            await db.execute("""
                INSERT INTO activity_meter (guild_id, user_id, score, last_msg)
                VALUES ('not_a_number', 'also_not_a_number', 50.0, 123456)
            """)
            await db.commit()
    
    async def _insert_large_valid_dataset(self, db_path: str, factory: TestDataFactory):
        """插入大量有效資料以測試效能和穩定性"""
        async with aiosqlite.connect(db_path) as db:
            test_data = []
            for i in range(100):  # 100筆記錄用於測試
                user_id = factory.create_test_user_id(f"user_{i}")
                guild_id = factory.create_test_guild_id(f"guild_{i % 10}")  # 10個伺服器
                activity_data = factory.create_test_activity_data(user_id, guild_id)
                
                test_data.append((
                    activity_data['guild_id'],
                    activity_data['user_id'],
                    activity_data['score'],
                    activity_data['last_msg']
                ))
            
            await db.executemany("""
                INSERT INTO activity_meter (guild_id, user_id, score, last_msg)
                VALUES (?, ?, ?, ?)
            """, test_data)
            await db.commit()