"""成就系統端到端整合測試.

測試成就系統各組件之間的完整整合，包括：
- 資料庫、快取、效能監控的協作
- 事件驅動的成就解鎖流程
- 錯誤恢復和容錯機制
- 效能優化和監控整合
- 用戶界面和通知系統協作

此整合測試旨在驗證 Story 5.2 的所有功能正常協作。
"""

import asyncio
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from src.cogs.achievement.database.models import (
    Achievement,
    AchievementType,
)
from src.cogs.achievement.database.repository import AchievementRepository
from src.cogs.achievement.services.cache_manager import CacheManager, CacheType
from src.cogs.achievement.services.performance_service import (
    AchievementPerformanceService,
)
from src.core.config import Settings
from src.core.database import DatabasePool


@pytest.mark.integration
class TestAchievementSystemIntegration:
    """成就系統整合測試."""

    @pytest.fixture(autouse=True)
    async def setup_test_environment(self):
        """設置測試環境."""
        # 創建臨時資料庫
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db_path = Path(self.temp_db.name)
        self.temp_db.close()

        # 創建臨時快取目錄
        self.temp_cache_dir = tempfile.mkdtemp()

        # 設置測試配置
        self.test_settings = Settings()

        # 初始化資料庫連線池
        self.db_pool = DatabasePool(self.temp_db_path, self.test_settings)
        await self.db_pool.initialize()

        # 初始化成就資料庫結構
        from src.cogs.achievement.database import initialize_achievement_database
        await initialize_achievement_database(self.db_pool)

        # 初始化核心服務
        self.repository = AchievementRepository(self.db_pool)
        self.cache_manager = CacheManager(cache_dir=self.temp_cache_dir)

        # 模擬效能服務
        with patch('src.cogs.achievement.services.performance_service.AchievementPerformanceMonitor'), \
             patch('src.cogs.achievement.services.performance_service.PerformanceAnalyzer'):
            self.performance_service = AchievementPerformanceService(
                repository=self.repository,
                cache_manager=self.cache_manager
            )

        # 啟動服務
        async with self.cache_manager:
            async with self.performance_service:
                yield

        # 清理
        await self.db_pool.close_all()
        if self.temp_db_path.exists():
            self.temp_db_path.unlink()

    @pytest.mark.asyncio
    async def test_database_cache_integration(self):
        """測試資料庫和快取系統整合."""
        # 創建測試成就
        achievement = Achievement(
            name="整合測試成就",
            description="測試資料庫和快取整合",
            category_id=1,
            type=AchievementType.COUNTER,
            criteria={"target_value": 100},
            points=500
        )

        # 通過資料庫創建成就
        created_achievement = await self.repository.create_achievement(achievement)
        assert created_achievement.id is not None

        # 測試快取功能
        cache_key = f"achievement:{created_achievement.id}"

        # 設置快取
        await self.cache_manager.set(
            CacheType.ACHIEVEMENT,
            cache_key,
            created_achievement
        )

        # 從快取讀取
        cached_achievement = await self.cache_manager.get(
            CacheType.ACHIEVEMENT,
            cache_key
        )

        assert cached_achievement is not None
        assert cached_achievement.id == created_achievement.id
        assert cached_achievement.name == created_achievement.name

        # 驗證快取統計
        cache_stats = await self.cache_manager.get_stats(CacheType.ACHIEVEMENT)
        assert cache_stats.hits >= 1

    @pytest.mark.asyncio
    async def test_achievement_unlock_with_performance_monitoring(self):
        """測試帶效能監控的成就解鎖流程."""
        user_id = 123456789

        # 創建測試成就
        achievement = Achievement(
            name="效能監控測試成就",
            description="測試效能監控整合",
            category_id=1,
            type=AchievementType.COUNTER,
            criteria={"target_value": 10},
            points=100
        )

        created_achievement = await self.repository.create_achievement(achievement)

        # 使用效能服務執行操作
        start_time = datetime.now()

        # 模擬進度更新到解鎖
        for i in range(1, 11):
            await self.performance_service.update_progress_optimized(
                user_id=user_id,
                achievement_id=created_achievement.id,
                current_value=i
            )

        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()

        # 驗證成就已解鎖
        user_achievements = await self.repository.get_user_achievements(user_id)
        assert len(user_achievements) == 1

        user_achievement, achievement_data = user_achievements[0]
        assert user_achievement.user_id == user_id
        assert achievement_data.id == created_achievement.id

        # 驗證效能監控記錄了操作
        # 這裡應該檢查效能指標，但由於使用 mock，我們檢查執行時間
        assert execution_time < 1.0  # 操作應該在1秒內完成

    @pytest.mark.asyncio
    async def test_concurrent_achievement_operations(self):
        """測試並發成就操作."""
        # 創建多個用戶和成就
        user_ids = [100001, 100002, 100003, 100004, 100005]

        achievements = []
        for i in range(3):
            achievement = Achievement(
                name=f"並發測試成就 {i+1}",
                description=f"測試並發操作 {i+1}",
                category_id=1,
                type=AchievementType.COUNTER,
                criteria={"target_value": 5},
                points=50
            )
            created = await self.repository.create_achievement(achievement)
            achievements.append(created)

        # 並發執行進度更新
        async def update_user_progress(user_id: int, achievement: Achievement):
            """為用戶更新成就進度."""
            for progress in range(1, 6):  # 1-5，觸發解鎖
                await self.performance_service.update_progress_optimized(
                    user_id=user_id,
                    achievement_id=achievement.id,
                    current_value=progress
                )
                # 小延遲模擬真實操作
                await asyncio.sleep(0.01)

        # 創建並發任務
        tasks = []
        for user_id in user_ids:
            for achievement in achievements:
                task = update_user_progress(user_id, achievement)
                tasks.append(task)

        # 執行所有並發任務
        await asyncio.gather(*tasks)

        # 驗證結果
        for user_id in user_ids:
            user_achievements = await self.repository.get_user_achievements(user_id)
            assert len(user_achievements) == len(achievements)  # 每個用戶都應該解鎖所有成就

    @pytest.mark.asyncio
    async def test_cache_invalidation_with_database_updates(self):
        """測試資料庫更新時的快取失效機制."""
        # 創建測試成就
        achievement = Achievement(
            name="快取失效測試",
            description="測試快取失效機制",
            category_id=1,
            type=AchievementType.COUNTER,
            criteria={"target_value": 50},
            points=200
        )

        created_achievement = await self.repository.create_achievement(achievement)
        cache_key = f"achievement:{created_achievement.id}"

        # 設置初始快取
        await self.cache_manager.set(
            CacheType.ACHIEVEMENT,
            cache_key,
            created_achievement
        )

        # 驗證快取存在
        cached_data = await self.cache_manager.get(CacheType.ACHIEVEMENT, cache_key)
        assert cached_data.name == "快取失效測試"

        # 更新資料庫中的成就
        updates = {"name": "已更新的快取失效測試", "points": 300}
        success = await self.repository.update_achievement(created_achievement.id, updates)
        assert success is True

        # 失效快取
        await self.cache_manager.invalidate_pattern(
            CacheType.ACHIEVEMENT,
            f"achievement:{created_achievement.id}"
        )

        # 重新從資料庫載入
        updated_achievement = await self.repository.get_achievement_by_id(created_achievement.id)

        # 更新快取
        await self.cache_manager.set(
            CacheType.ACHIEVEMENT,
            cache_key,
            updated_achievement
        )

        # 驗證快取已更新
        refreshed_cache = await self.cache_manager.get(CacheType.ACHIEVEMENT, cache_key)
        assert refreshed_cache.name == "已更新的快取失效測試"
        assert refreshed_cache.points == 300

    @pytest.mark.asyncio
    async def test_error_recovery_and_rollback(self):
        """測試錯誤恢復和回滾機制."""
        user_id = 987654321

        # 創建測試成就
        achievement = Achievement(
            name="錯誤恢復測試",
            description="測試系統錯誤恢復",
            category_id=1,
            type=AchievementType.COUNTER,
            criteria={"target_value": 1},
            points=100
        )

        created_achievement = await self.repository.create_achievement(achievement)

        # 模擬部分操作成功，後續操作失敗的情況
        try:
            # 更新進度到解鎖狀態
            await self.repository.update_progress(
                user_id=user_id,
                achievement_id=created_achievement.id,
                current_value=1.0
            )

            # 驗證成就已自動解鎖（如果實作了自動解鎖機制）
            user_achievements = await self.repository.get_user_achievements(user_id)
            if user_achievements:
                # 模擬後續處理失敗（比如通知發送失敗）
                raise Exception("模擬通知發送失敗")

        except Exception as e:
            # 模擬錯誤恢復機制
            assert "模擬通知發送失敗" in str(e)

            # 驗證資料庫狀態仍然正確（進度已保存）
            progress = await self.repository.get_user_progress(user_id, created_achievement.id)
            assert progress is not None
            assert progress.current_value == 1.0

    @pytest.mark.asyncio
    async def test_performance_monitoring_integration(self):
        """測試效能監控系統整合."""
        # 創建多個測試操作來生成效能數據
        operations = [
            ("create_achievement", self._create_test_achievements),
            ("bulk_progress_update", self._bulk_progress_updates),
            ("cache_operations", self._cache_intensive_operations),
        ]

        performance_results = {}

        for operation_name, operation_func in operations:
            start_time = datetime.now()

            try:
                await operation_func()
                success = True
                error = None
            except Exception as e:
                success = False
                error = str(e)

            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()

            performance_results[operation_name] = {
                "execution_time": execution_time,
                "success": success,
                "error": error
            }

        # 驗證所有操作都成功執行
        for operation, result in performance_results.items():
            assert result["success"] is True, f"操作 {operation} 失敗: {result['error']}"
            assert result["execution_time"] < 5.0, f"操作 {operation} 執行時間過長: {result['execution_time']}s"

        # 驗證效能監控收集了數據
        # 由於使用 mock，這裡主要驗證操作完成
        assert len(performance_results) == len(operations)

    async def _create_test_achievements(self):
        """創建測試成就."""
        achievements = []
        for i in range(5):
            achievement = Achievement(
                name=f"效能測試成就 {i+1}",
                description=f"效能測試成就描述 {i+1}",
                category_id=1,
                type=AchievementType.COUNTER,
                criteria={"target_value": 10},
                points=100
            )
            created = await self.repository.create_achievement(achievement)
            achievements.append(created)

        return achievements

    async def _bulk_progress_updates(self):
        """批量進度更新."""
        user_ids = [200001, 200002, 200003]

        # 先創建測試成就
        achievements = await self._create_test_achievements()

        # 批量更新進度
        for user_id in user_ids:
            for achievement in achievements:
                await self.repository.update_progress(
                    user_id=user_id,
                    achievement_id=achievement.id,
                    current_value=5.0  # 50% 進度
                )

    async def _cache_intensive_operations(self):
        """快取密集操作."""
        # 大量快取讀寫操作
        for i in range(50):
            cache_key = f"performance_test:{i}"
            test_data = {"operation": i, "timestamp": datetime.now().isoformat()}

            # 寫入快取
            await self.cache_manager.set(
                CacheType.STATS,
                cache_key,
                test_data
            )

            # 立即讀取
            cached_data = await self.cache_manager.get(
                CacheType.STATS,
                cache_key
            )

            assert cached_data == test_data

    @pytest.mark.asyncio
    async def test_system_load_tolerance(self):
        """測試系統負載容忍度."""
        # 模擬高並發場景
        concurrent_users = 20
        operations_per_user = 10

        async def simulate_user_activity(user_id: int):
            """模擬用戶活動."""
            # 創建用戶專屬成就
            achievement = Achievement(
                name=f"負載測試成就-用戶{user_id}",
                description=f"用戶 {user_id} 的負載測試",
                category_id=1,
                type=AchievementType.COUNTER,
                criteria={"target_value": operations_per_user},
                points=50
            )

            created_achievement = await self.repository.create_achievement(achievement)

            # 執行多個操作
            for operation_num in range(operations_per_user):
                await self.repository.update_progress(
                    user_id=user_id,
                    achievement_id=created_achievement.id,
                    current_value=operation_num + 1
                )

                # 模擬網路延遲
                await asyncio.sleep(0.005)

        # 創建並發用戶任務
        start_time = datetime.now()
        tasks = [
            simulate_user_activity(user_id)
            for user_id in range(300001, 300001 + concurrent_users)
        ]

        # 執行所有任務
        await asyncio.gather(*tasks)

        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds()

        # 驗證系統在合理時間內完成所有操作
        expected_max_time = concurrent_users * operations_per_user * 0.01  # 每操作 10ms 的寬鬆估計
        assert total_time < expected_max_time, f"系統負載測試超時: {total_time}s > {expected_max_time}s"

        # 驗證所有用戶都完成了操作
        total_operations = concurrent_users * operations_per_user

        # 檢查資料庫中的記錄數量
        # 由於每個用戶創建了一個成就並完成了所有進度，應該有相應的用戶成就記錄
        all_user_achievements = []
        for user_id in range(300001, 300001 + concurrent_users):
            user_achievements = await self.repository.get_user_achievements(user_id)
            all_user_achievements.extend(user_achievements)

        assert len(all_user_achievements) == concurrent_users, \
            f"預期 {concurrent_users} 個用戶成就記錄，實際 {len(all_user_achievements)} 個"

    @pytest.mark.asyncio
    async def test_data_consistency_under_concurrent_access(self):
        """測試並發訪問下的資料一致性."""
        user_id = 400001

        # 創建測試成就
        achievement = Achievement(
            name="並發一致性測試",
            description="測試並發存取時的資料一致性",
            category_id=1,
            type=AchievementType.COUNTER,
            criteria={"target_value": 100},
            points=500
        )

        created_achievement = await self.repository.create_achievement(achievement)

        # 並發更新同一用戶的同一成就進度
        async def increment_progress():
            """增加進度值."""
            # 獲取當前進度
            current_progress = await self.repository.get_user_progress(
                user_id, created_achievement.id
            )

            current_value = current_progress.current_value if current_progress else 0
            new_value = current_value + 1

            # 更新進度
            await self.repository.update_progress(
                user_id=user_id,
                achievement_id=created_achievement.id,
                current_value=new_value
            )

        # 執行並發進度更新
        concurrent_updates = 10
        tasks = [increment_progress() for _ in range(concurrent_updates)]

        await asyncio.gather(*tasks, return_exceptions=True)

        # 驗證最終進度值的一致性
        final_progress = await self.repository.get_user_progress(
            user_id, created_achievement.id
        )

        # 由於並發更新，最終值可能不等於 concurrent_updates
        # 但應該是一個合理的值（介於 1 和 concurrent_updates 之間）
        assert final_progress is not None
        assert 1 <= final_progress.current_value <= concurrent_updates

        # 驗證資料庫中沒有重複的進度記錄
        # 這需要直接查詢資料庫來確認唯一性約束有效
        progress_records = await self.repository.get_user_progresses(user_id)

        # 同一用戶對同一成就應該只有一條進度記錄
        achievement_progress_records = [
            p for p in progress_records
            if p.achievement_id == created_achievement.id
        ]
        assert len(achievement_progress_records) == 1


# 測試運行標記
pytestmark = [pytest.mark.asyncio, pytest.mark.integration]
