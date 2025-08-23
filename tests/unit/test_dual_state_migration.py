"""
T4 - 雙態遷移驗證測試
測試增強遷移管理器在新建和既有資料庫上的執行效果
"""

import pytest
import tempfile
import os
from pathlib import Path
import asyncio

from scripts.enhanced_migration_manager import EnhancedMigrationManager
from test_utils.enhanced_test_isolation import (
    TestConfiguration, 
    isolated_test_environment,
    fast_test_environment
)


class TestDualStateMigration:
    """測試雙態遷移驗證 - F-1"""
    
    @pytest.mark.asyncio
    async def test_new_database_migration_success(self):
        """測試在新建資料庫上應用遷移成功"""
        # 使用快速測試環境（記憶體資料庫）
        async with fast_test_environment() as env:
            # 創建臨時遷移管理器
            temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
            temp_db.close()
            
            try:
                manager = EnhancedMigrationManager(temp_db.name)
                
                # 驗證雙態遷移 - 這應該在新資料庫上成功
                result = await manager.verify_dual_state_migration("003")
                
                # 驗證結果
                assert result['validation_passed'] == True
                assert result['new_database_test']['success'] == True
                assert result['new_database_test']['execution_time_ms'] > 0
                assert len(result['errors']) == 0
                
            finally:
                # 清理臨時檔案
                if os.path.exists(temp_db.name):
                    os.unlink(temp_db.name)
    
    @pytest.mark.asyncio
    async def test_existing_database_migration_success(self):
        """測試在既有資料庫上應用遷移成功"""
        async with fast_test_environment() as env:
            manager = EnhancedMigrationManager(env['db_path'])
            
            # 首先確保有一些基礎表結構
            await manager.apply_migration("002")  # 先應用較早的遷移
            
            # 然後驗證雙態遷移
            result = await manager.verify_dual_state_migration("003")
            
            # 驗證結果
            assert result['validation_passed'] == True
            assert result['existing_database_test']['success'] == True
            assert len(result['errors']) == 0
    
    @pytest.mark.asyncio 
    async def test_migration_rollback_mechanism(self):
        """測試遷移回滾機制"""
        async with fast_test_environment() as env:
            manager = EnhancedMigrationManager(env['db_path'])
            
            # 應用遷移
            apply_result = await manager.apply_migration("003")
            assert apply_result['success'] == True
            
            # 驗證回滾腳本可用
            assert apply_result['rollback_available'] == True
            
            # 執行回滾
            rollback_result = await manager.rollback_migration("003")
            assert rollback_result['success'] == True
            
            # 驗證回滾後的完整性
            integrity_result = rollback_result['integrity_check']
            assert integrity_result['success'] == True
    
    @pytest.mark.asyncio
    async def test_migration_performance_requirement(self):
        """測試遷移效能要求 - N-1: < 5分鐘"""
        async with fast_test_environment() as env:
            manager = EnhancedMigrationManager(env['db_path'])
            
            # 模擬大量資料（較小規模以適應測試環境）
            await self._populate_test_data(env['db_path'])
            
            # 測量遷移時間
            result = await manager.apply_migration("003")
            
            # 驗證效能要求（毫秒轉換為分鐘）
            execution_time_minutes = result['execution_time_ms'] / (1000 * 60)
            assert execution_time_minutes < 5.0  # N-1 要求
            assert result['success'] == True
    
    async def _populate_test_data(self, db_path: str):
        """填充測試資料以模擬大量資料庫"""
        import aiosqlite
        
        async with aiosqlite.connect(db_path) as db:
            # 確保 activity_meter 表存在
            await db.execute("""
                CREATE TABLE IF NOT EXISTS activity_meter (
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    score REAL DEFAULT 0,
                    last_msg INTEGER DEFAULT 0
                )
            """)
            
            # 插入測試資料（模擬重複記錄以測試去重邏輯）
            test_data = []
            for guild_id in range(1, 6):  # 5個伺服器
                for user_id in range(1, 21):  # 每個伺服器20個用戶
                    # 為每個用戶插入2-3筆記錄以測試去重
                    for i in range(2 + (user_id % 2)):
                        test_data.append((guild_id, user_id, float(i * 10), i * 1000))
            
            await db.executemany(
                "INSERT INTO activity_meter (guild_id, user_id, score, last_msg) VALUES (?, ?, ?, ?)",
                test_data
            )
            await db.commit()
    
    @pytest.mark.asyncio
    async def test_validation_failure_handling(self):
        """測試驗證失敗時的處理"""
        async with fast_test_environment() as env:
            manager = EnhancedMigrationManager(env['db_path'])
            
            # 嘗試驗證不存在的遷移
            result = await manager.verify_dual_state_migration("999")
            
            # 應該優雅地處理失敗
            assert result['validation_passed'] == False
            assert len(result['errors']) > 0
            assert "未找到版本 999 的遷移檔案" in str(result['errors'])
    
    @pytest.mark.asyncio
    async def test_data_integrity_after_migration(self):
        """測試遷移後資料完整性"""
        async with fast_test_environment() as env:
            manager = EnhancedMigrationManager(env['db_path'])
            
            # 填充測試資料
            await self._populate_test_data(env['db_path'])
            
            # 應用遷移
            result = await manager.apply_migration("003")
            assert result['success'] == True
            
            # 檢查完整性結果
            integrity_check = result['integrity_check']
            assert integrity_check['success'] == True
            assert 'unique_constraints' in integrity_check['checks_performed']
            
            # 驗證沒有重複記錄
            import aiosqlite
            async with aiosqlite.connect(env['db_path']) as db:
                cursor = await db.execute("""
                    SELECT guild_id, user_id, COUNT(*) as cnt
                    FROM activity_meter
                    GROUP BY guild_id, user_id
                    HAVING COUNT(*) > 1
                """)
                duplicates = await cursor.fetchall()
                assert len(duplicates) == 0  # 應該沒有重複記錄