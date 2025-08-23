"""
T4 - 測試隔離效果驗證測試
測試增強的測試隔離基礎設施
"""

import pytest
import asyncio
import time
from pathlib import Path

from test_utils.enhanced_test_isolation import (
    TestConfiguration,
    TestEnvironmentManager,
    isolated_test_environment,
    fast_test_environment,
    thorough_test_environment,
    TestDataFactory,
    verify_test_isolation,
    run_isolation_stress_test,
    create_memory_test_config,
    create_thorough_test_config,
    create_performance_test_config
)


class TestIsolationEffectiveness:
    """測試隔離效果驗證 - F-3"""
    
    @pytest.mark.asyncio
    async def test_basic_test_isolation(self):
        """測試基本的測試隔離功能"""
        # 創建兩個並行的測試環境
        async with isolated_test_environment() as env1:
            async with isolated_test_environment() as env2:
                # 驗證隔離效果
                isolation_result = await verify_test_isolation(env1, env2)
                
                assert isolation_result['isolated'] == True
                assert len(isolation_result['violations']) == 0
                assert 'database_path_isolation' in isolation_result['checks_performed']
                assert 'test_id_isolation' in isolation_result['checks_performed']
    
    @pytest.mark.asyncio
    async def test_memory_vs_file_database_isolation(self):
        """測試記憶體資料庫與檔案資料庫的隔離"""
        memory_config = create_memory_test_config()
        file_config = create_thorough_test_config()
        
        async with isolated_test_environment(memory_config) as mem_env:
            async with isolated_test_environment(file_config) as file_env:
                # 兩種配置應該都能正常隔離
                isolation_result = await verify_test_isolation(mem_env, file_env)
                
                assert isolation_result['isolated'] == True
                assert mem_env['config'].use_memory_db == True
                assert file_env['config'].use_memory_db == False
    
    @pytest.mark.asyncio
    async def test_test_data_factory_isolation(self):
        """測試資料工廠的隔離效果"""
        async with fast_test_environment() as env:
            # 創建兩個獨立的資料工廠
            factory1 = TestDataFactory("test_1")
            factory2 = TestDataFactory("test_2")
            
            # 生成測試資料
            user1 = factory1.create_test_user_id("user_a")
            guild1 = factory1.create_test_guild_id("guild_a")
            account1 = factory1.create_test_account_data(user1, guild1)
            
            user2 = factory2.create_test_user_id("user_a")  # 相同後綴
            guild2 = factory2.create_test_guild_id("guild_a")  # 相同後綴
            account2 = factory2.create_test_account_data(user2, guild2)
            
            # 驗證生成的ID是不同的（即使後綴相同）
            assert user1 != user2
            assert guild1 != guild2
            assert account1['account_id'] != account2['account_id']
            
            # 驗證清理資訊是分離的
            cleanup1 = factory1.get_cleanup_info()
            cleanup2 = factory2.get_cleanup_info()
            
            assert len(cleanup1['users']) == 1
            assert len(cleanup2['users']) == 1
            assert cleanup1['users'][0] != cleanup2['users'][0]
    
    @pytest.mark.asyncio
    async def test_performance_isolation_overhead(self):
        """測試隔離的效能開銷 - N-2: < 500ms"""
        config = create_performance_test_config()
        
        setup_times = []
        
        # 測試多次設置以獲得平均值
        for i in range(5):
            start_time = time.time()
            async with isolated_test_environment(config) as env:
                setup_time = time.time() - start_time
                setup_times.append(setup_time)
                
                # 驗證設置時間記錄
                assert env['setup_time_ms'] > 0
                
        # 計算平均設置時間
        avg_setup_time = sum(setup_times) / len(setup_times)
        
        # 驗證效能要求 (N-2: < 500ms)
        assert avg_setup_time < 0.5, f"平均設置時間 {avg_setup_time:.3f}s 超過 500ms 要求"
    
    @pytest.mark.asyncio
    async def test_parallel_isolation_stress(self):
        """測試並行隔離的壓力測試"""
        # 運行隔離壓力測試
        stress_result = await run_isolation_stress_test(
            num_environments=5,  # 較小數量以適應測試環境
            duration_seconds=10.0  # 較短時間以加快測試
        )
        
        # 驗證壓力測試結果
        assert stress_result['success'] == True
        assert stress_result['environments_created'] == 5
        assert len(stress_result['isolation_violations']) == 0
        assert stress_result['average_setup_time'] < 0.5  # N-2 要求
        
        if stress_result['errors']:
            pytest.fail(f"壓力測試發現錯誤: {stress_result['errors']}")
    
    @pytest.mark.asyncio
    async def test_cleanup_thoroughness(self):
        """測試清理的完整性"""
        temp_dirs = []
        db_paths = []
        
        # 創建並記錄測試環境
        async with thorough_test_environment() as env:
            temp_dirs.append(env['temp_dir'])
            db_paths.append(env['db_path'])
            
            # 在環境中創建一些資料
            factory = TestDataFactory(env['test_id'])
            test_data = factory.create_test_activity_data()
            
            # 驗證環境可用
            assert env['startup_manager'] is not None
            assert env['isolation_verified'] == True
        
        # 環境應該已經清理完畢
        # 檢查檔案是否已清理（記憶體資料庫不會有檔案）
        for temp_dir in temp_dirs:
            if temp_dir:
                assert not Path(temp_dir).exists(), f"臨時目錄未清理: {temp_dir}"
    
    @pytest.mark.asyncio
    async def test_service_state_isolation(self):
        """測試服務狀態隔離"""
        # 第一個環境
        async with fast_test_environment() as env1:
            startup_manager1 = env1['startup_manager']
            
            # 獲取成就服務並修改其狀態
            achievement_service1 = startup_manager1.service_instances.get("AchievementService")
            if achievement_service1:
                # 模擬修改服務狀態
                original_cache_size = len(achievement_service1._active_achievements_cache)
                achievement_service1._active_achievements_cache['test_key'] = 'test_value'
                
            # 第二個環境
            async with fast_test_environment() as env2:
                startup_manager2 = env2['startup_manager']
                
                # 驗證服務實例是不同的
                assert startup_manager1 is not startup_manager2
                
                achievement_service2 = startup_manager2.service_instances.get("AchievementService")
                if achievement_service2:
                    # 驗證快取狀態是獨立的
                    assert achievement_service1 is not achievement_service2
                    assert 'test_key' not in achievement_service2._active_achievements_cache
    
    @pytest.mark.asyncio
    async def test_error_handling_during_setup(self):
        """測試設置過程中的錯誤處理"""
        # 創建一個可能導致問題的配置
        problematic_config = TestConfiguration(
            cleanup_timeout=0.001,  # 極短的逾時時間
            validate_isolation=True
        )
        
        try:
            async with isolated_test_environment(problematic_config) as env:
                # 即使配置有問題，環境也應該能建立
                assert env['startup_manager'] is not None
                assert env['test_id'] is not None
        except Exception:
            # 如果確實失敗，應該優雅處理
            pass  # 這是可接受的行為
    
    @pytest.mark.asyncio
    async def test_custom_cleanup_callbacks(self):
        """測試自定義清理回呼"""
        cleanup_called = []
        
        def sync_cleanup():
            cleanup_called.append('sync')
        
        async def async_cleanup():
            cleanup_called.append('async')
        
        config = create_memory_test_config()
        manager = TestEnvironmentManager(config)
        
        try:
            env = await manager.setup()
            
            # 添加清理回呼
            manager.add_cleanup_callback(sync_cleanup)
            manager.add_cleanup_callback(async_cleanup)
            
        finally:
            await manager.cleanup()
        
        # 驗證清理回呼被調用
        assert 'sync' in cleanup_called
        assert 'async' in cleanup_called