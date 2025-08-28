"""
子機器人資料庫系統相容性測試套件
Task ID: 3 - 子機器人聊天功能和管理系統開發

這個測試套件驗證：
- 與現有資料庫管理器的相容性
- 新資料存取層的功能完整性
- Token安全管理的正確性
- 異步操作的穩定性
- 錯誤處理機制的有效性
- 整體系統的效能和可靠性
"""

import asyncio
import pytest
import sqlite3
import tempfile
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, patch, AsyncMock

# 測試目標組件
from ..subbot_repository import (
    SubBotRepository, 
    SubBotEntity, 
    SubBotChannelEntity, 
    SubBotStatus,
    get_subbot_repository
)
from ..subbot_database_service import (
    SubBotDatabaseService,
    get_subbot_database_service
)
from ...security.subbot_token_manager import (
    SubBotTokenManager,
    TokenEncryptionLevel,
    get_token_manager
)
from ..query_optimizer import (
    QueryOptimizer,
    get_query_optimizer
)
from ..async_manager import (
    SubBotAsyncManager,
    OperationType,
    OperationPriority,
    get_async_manager
)
from ..error_handler import (
    SubBotErrorHandler,
    ErrorSeverity,
    ErrorCategory,
    get_error_handler
)

# 核心依賴
from core.database_manager import DatabaseManager
from core.security_manager import get_security_manager
from src.core.errors import (
    SubBotError,
    SubBotCreationError,
    SubBotTokenError
)

logger = logging.getLogger('tests.database.compatibility')


class TestDatabaseCompatibility:
    """資料庫相容性測試"""
    
    @pytest.fixture
    async def temp_db(self):
        """臨時資料庫"""
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_file.close()
        
        # 創建測試資料庫
        conn = sqlite3.connect(temp_file.name)
        
        # 創建測試表結構（簡化版）
        conn.execute('''
            CREATE TABLE sub_bots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_id VARCHAR(50) UNIQUE NOT NULL,
                name VARCHAR(100) NOT NULL,
                token_hash VARCHAR(255) NOT NULL,
                target_channels TEXT NOT NULL,
                ai_enabled BOOLEAN DEFAULT FALSE,
                ai_model VARCHAR(50),
                personality TEXT,
                rate_limit INTEGER DEFAULT 10,
                status VARCHAR(20) DEFAULT 'offline',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_active_at DATETIME,
                message_count INTEGER DEFAULT 0,
                owner_id INTEGER
            )
        ''')
        
        conn.execute('''
            CREATE TABLE sub_bot_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sub_bot_id INTEGER NOT NULL,
                channel_id BIGINT NOT NULL,
                channel_type VARCHAR(20) DEFAULT 'text',
                permissions TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sub_bot_id) REFERENCES sub_bots(id) ON DELETE CASCADE,
                UNIQUE(sub_bot_id, channel_id)
            )
        ''')
        
        conn.close()
        
        yield temp_file.name
        
        # 清理
        try:
            os.unlink(temp_file.name)
        except OSError:
            pass
    
    @pytest.fixture
    async def mock_db_manager(self, temp_db):
        """模擬資料庫管理器"""
        db_manager = Mock(spec=DatabaseManager)
        
        # 模擬資料庫連接
        async def mock_execute(sql, params=(), db_type="main"):
            conn = sqlite3.connect(temp_db)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
            result = cursor.lastrowid
            conn.close()
            return result
        
        async def mock_fetchone(sql, params=(), db_type="main"):
            conn = sqlite3.connect(temp_db)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sql, params)
            result = cursor.fetchone()
            conn.close()
            return dict(result) if result else None
        
        async def mock_fetchall(sql, params=(), db_type="main"):
            conn = sqlite3.connect(temp_db)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sql, params)
            results = cursor.fetchall()
            conn.close()
            return [dict(row) for row in results]
        
        db_manager.execute = AsyncMock(side_effect=mock_execute)
        db_manager.fetchone = AsyncMock(side_effect=mock_fetchone)
        db_manager.fetchall = AsyncMock(side_effect=mock_fetchall)
        
        return db_manager
    
    @pytest.mark.asyncio
    async def test_repository_basic_operations(self, mock_db_manager):
        """測試Repository基本操作"""
        # 創建Repository實例
        repository = SubBotRepository()
        repository.db_manager = mock_db_manager
        
        # 測試創建子機器人
        subbot = SubBotEntity(
            bot_id="test_bot_001",
            name="Test Bot",
            token_hash="encrypted_token_hash",
            target_channels=[123456789],
            ai_enabled=True,
            ai_model="gpt-3.5-turbo",
            owner_id=999
        )
        
        created_subbot = await repository.create_subbot(subbot)
        assert created_subbot.id is not None
        assert created_subbot.bot_id == "test_bot_001"
        assert created_subbot.name == "Test Bot"
        
        # 測試獲取子機器人
        retrieved_subbot = await repository.get_subbot_by_bot_id("test_bot_001")
        assert retrieved_subbot is not None
        assert retrieved_subbot.bot_id == "test_bot_001"
        assert retrieved_subbot.name == "Test Bot"
        
        # 測試更新子機器人
        retrieved_subbot.status = SubBotStatus.ONLINE.value
        update_success = await repository.update_subbot(retrieved_subbot)
        assert update_success is True
        
        # 驗證更新
        updated_subbot = await repository.get_subbot_by_bot_id("test_bot_001")
        assert updated_subbot.status == SubBotStatus.ONLINE.value
        
        # 測試統計功能
        stats = await repository.get_subbots_statistics()
        assert stats['total_count'] >= 1
        assert stats['status_distribution'][SubBotStatus.ONLINE.value] >= 1
        
        # 測試刪除
        delete_success = await repository.delete_subbot("test_bot_001")
        assert delete_success is True
        
        # 驗證刪除
        deleted_subbot = await repository.get_subbot_by_bot_id("test_bot_001")
        assert deleted_subbot is None
    
    @pytest.mark.asyncio
    async def test_token_security_integration(self):
        """測試Token安全管理整合"""
        # 創建Token管理器
        token_manager = SubBotTokenManager(
            encryption_level=TokenEncryptionLevel.STANDARD
        )
        await token_manager.initialize()
        
        # 測試Token加密
        original_token = ""
        bot_id = "test_bot_token"
        
        encrypted_token, metadata_json = await token_manager.encrypt_discord_token(
            original_token, bot_id
        )
        
        assert encrypted_token != original_token
        assert metadata_json is not None
        
        # 測試Token解密
        decrypted_token = await token_manager.decrypt_discord_token(
            encrypted_token, metadata_json, bot_id
        )
        
        assert decrypted_token == original_token
        
        # 測試Token完整性驗證
        integrity_status = await token_manager.verify_token_integrity(
            bot_id, encrypted_token, metadata_json
        )
        
        assert integrity_status.name == "VALID"
        
        # 測試Token資訊獲取
        token_info = token_manager.get_token_info(bot_id)
        assert token_info is not None
        assert token_info['bot_id'] == bot_id
        assert token_info['encryption_level'] == TokenEncryptionLevel.STANDARD.value
    
    @pytest.mark.asyncio
    async def test_database_service_integration(self, mock_db_manager):
        """測試資料庫服務整合"""
        # 創建資料庫服務
        db_service = SubBotDatabaseService()
        
        # 注入模擬的依賴
        with patch('src.core.database.subbot_database_service.get_database_manager') as mock_get_db:
            mock_get_db.return_value = mock_db_manager
            
            await db_service.initialize()
            
            # 測試創建子機器人
            result = await db_service.create_subbot(
                name="Integration Test Bot",
                token="test_token_123",
                owner_id=123,
                channel_ids=[111, 222, 333],
                ai_enabled=True,
                ai_model="gpt-4"
            )
            
            assert result['success'] is True
            assert 'subbot' in result
            assert result['subbot']['name'] == "Integration Test Bot"
            assert result['channels_configured'] == 3
            assert result['token_encrypted'] is True
            
            bot_id = result['subbot']['bot_id']
            
            # 測試獲取子機器人
            subbot_info = await db_service.get_subbot(bot_id)
            assert subbot_info is not None
            assert subbot_info['name'] == "Integration Test Bot"
            assert subbot_info['ai_enabled'] is True
            
            # 測試列出子機器人
            subbot_list = await db_service.list_subbots()
            assert len(subbot_list) >= 1
            assert any(bot['bot_id'] == bot_id for bot in subbot_list)
            
            # 測試狀態更新
            status_update = await db_service.update_status(bot_id, SubBotStatus.ONLINE.value)
            assert status_update is True
            
            # 測試活動更新
            activity_update = await db_service.update_activity(bot_id, 5)
            assert activity_update is True
    
    @pytest.mark.asyncio
    async def test_async_operations(self, mock_db_manager):
        """測試異步操作管理"""
        # 創建異步管理器
        async_manager = SubBotAsyncManager()
        await async_manager.initialize()
        
        # 測試簡單異步操作
        async def test_operation(value: int) -> int:
            await asyncio.sleep(0.1)  # 模擬異步操作
            return value * 2
        
        result = await async_manager.execute_async(
            test_operation,
            5,
            operation_type=OperationType.READ,
            priority=OperationPriority.HIGH
        )
        
        assert result == 10
        
        # 測試批次操作
        operations = [
            (test_operation, (i,), {}) for i in range(1, 6)
        ]
        
        batch_result = await async_manager.execute_batch(
            operations,
            strategy="parallel",
            max_concurrency=3
        )
        
        assert batch_result.success_count == 5
        assert batch_result.failure_count == 0
        assert len(batch_result.results) == 5
        
        # 測試背景任務
        counter = {'value': 0}
        
        async def background_task():
            counter['value'] += 1
        
        task_id = async_manager.create_background_task(background_task)
        await asyncio.sleep(0.2)  # 讓背景任務執行
        
        assert task_id is not None
        assert counter['value'] >= 1
        
        # 取消背景任務
        cancel_success = async_manager.cancel_background_task(task_id)
        assert cancel_success is True
    
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """測試錯誤處理系統"""
        # 創建錯誤處理器
        error_handler = SubBotErrorHandler()
        await error_handler.initialize()
        
        # 創建測試錯誤上下文
        from ..error_handler import ErrorContext
        context = ErrorContext(
            operation="test_operation",
            user_id=123,
            bot_id="test_bot",
            additional_data={'test': True}
        )
        
        # 測試錯誤處理
        test_error = ValueError("Test error message")
        
        error_event = await error_handler.handle_error(
            test_error,
            context,
            severity=ErrorSeverity.MEDIUM
        )
        
        assert error_event is not None
        assert error_event.error_type == "ValueError"
        assert error_event.message == "Test error message"
        assert error_event.severity == ErrorSeverity.MEDIUM
        assert error_event.context.operation == "test_operation"
        
        # 測試錯誤統計
        error_summary = error_handler.get_error_summary()
        assert error_summary['total_errors_24h'] >= 1
        
        # 測試手動解決錯誤
        resolve_success = await error_handler.manual_resolve_error(
            error_event.id,
            "manual_fix"
        )
        assert resolve_success is True
        
        # 驗證錯誤已解決
        resolved_event = error_handler.get_error_event(error_event.id)
        assert resolved_event is not None
        assert resolved_event.resolved is True
    
    @pytest.mark.asyncio
    async def test_query_optimization(self, mock_db_manager):
        """測試查詢優化功能"""
        # 創建查詢優化器
        optimizer = QueryOptimizer()
        optimizer.db_manager = mock_db_manager
        await optimizer.initialize()
        
        # 測試查詢分析
        test_sql = "SELECT * FROM sub_bots WHERE status = 'online' AND ai_enabled = 1"
        
        analysis_result = await optimizer.analyze_query(test_sql, None, 0.5)
        
        assert 'query_hash' in analysis_result
        assert 'pattern_analysis' in analysis_result
        assert 'optimization_suggestions' in analysis_result
        
        # 測試查詢優化
        optimization_result = await optimizer.optimize_query(test_sql)
        
        assert 'optimized' in optimization_result
        assert 'original_sql' in optimization_result
        assert 'optimized_sql' in optimization_result
        
        # 測試索引建議
        index_recommendations = optimizer.get_index_recommendations()
        
        # 應該有一些索引建議
        assert isinstance(index_recommendations, list)
        
        # 測試查詢統計
        query_stats = optimizer.get_query_statistics()
        
        assert 'total_unique_queries' in query_stats
        assert query_stats['total_unique_queries'] >= 1
    
    @pytest.mark.asyncio
    async def test_full_integration_scenario(self, mock_db_manager):
        """完整集成場景測試"""
        # 模擬完整的子機器人創建到運行的流程
        
        # 1. 初始化所有組件
        db_service = SubBotDatabaseService(
            enable_query_optimization=True,
            enable_token_encryption=True,
            encryption_level=TokenEncryptionLevel.STANDARD
        )
        
        with patch('src.core.database.subbot_database_service.get_database_manager') as mock_get_db:
            mock_get_db.return_value = mock_db_manager
            
            await db_service.initialize()
            
            # 2. 創建子機器人
            create_result = await db_service.create_subbot(
                name="Full Integration Bot",
                token="",
                owner_id=12345,
                channel_ids=[111111, 222222],
                ai_enabled=True,
                ai_model="gpt-3.5-turbo",
                personality="helpful assistant"
            )
            
            assert create_result['success'] is True
            bot_id = create_result['subbot']['bot_id']
            
            # 3. 獲取子機器人詳細資訊
            bot_info = await db_service.get_subbot(bot_id, include_token=False)
            assert bot_info is not None
            assert len(bot_info['channels']) == 2
            
            # 4. 更新子機器人狀態和活動
            await db_service.update_status(bot_id, SubBotStatus.ONLINE.value)
            await db_service.update_activity(bot_id, 10)
            
            # 5. 批次操作測試
            async_manager = await get_async_manager()
            
            # 批次更新多個狀態
            status_updates = [
                (bot_id, SubBotStatus.ONLINE.value)
            ]
            
            batch_result = await db_service.batch_update_status(status_updates)
            assert batch_result['success_count'] >= 1
            
            # 6. 獲取系統統計
            stats = await db_service.get_statistics()
            
            assert 'repository' in stats
            assert 'service' in stats
            assert stats['repository']['total_count'] >= 1
            
            # 7. 健康檢查
            health = await db_service.health_check()
            assert health['status'] in ['healthy', 'degraded']
            
            # 8. 資料庫優化
            optimization_result = await db_service.optimize_database()
            assert optimization_result['success'] is True
            
            # 9. 清理測試數據
            delete_success = await db_service.delete_subbot(bot_id)
            assert delete_success is True
    
    def test_performance_benchmark(self, mock_db_manager):
        """效能基準測試"""
        async def benchmark_operations():
            db_service = SubBotDatabaseService()
            
            with patch('src.core.database.subbot_database_service.get_database_manager') as mock_get_db:
                mock_get_db.return_value = mock_db_manager
                await db_service.initialize()
                
                # 創建多個子機器人並測量時間
                start_time = datetime.now()
                
                bot_ids = []
                for i in range(10):
                    result = await db_service.create_subbot(
                        name=f"Benchmark Bot {i}",
                        token=f"test_token_{i}",
                        owner_id=i,
                        ai_enabled=i % 2 == 0
                    )
                    if result['success']:
                        bot_ids.append(result['subbot']['bot_id'])
                
                create_time = (datetime.now() - start_time).total_seconds()
                
                # 批次查詢測試
                start_time = datetime.now()
                
                for bot_id in bot_ids:
                    await db_service.get_subbot(bot_id)
                
                query_time = (datetime.now() - start_time).total_seconds()
                
                # 批次更新測試
                start_time = datetime.now()
                
                status_updates = [(bot_id, SubBotStatus.ONLINE.value) for bot_id in bot_ids]
                await db_service.batch_update_status(status_updates)
                
                update_time = (datetime.now() - start_time).total_seconds()
                
                # 清理
                for bot_id in bot_ids:
                    await db_service.delete_subbot(bot_id)
                
                return {
                    'create_time': create_time,
                    'query_time': query_time,
                    'update_time': update_time,
                    'operations_count': len(bot_ids)
                }
        
        # 運行基準測試
        result = asyncio.run(benchmark_operations())
        
        # 驗證效能指標（這些是合理的閾值）
        assert result['create_time'] < 5.0  # 10個創建操作應在5秒內完成
        assert result['query_time'] < 2.0   # 10個查詢操作應在2秒內完成
        assert result['update_time'] < 3.0  # 批次更新應在3秒內完成
        
        logger.info(f"效能基準測試結果: {result}")


class TestCompatibilityRunner:
    """相容性測試運行器"""
    
    def __init__(self):
        self.test_results = []
        self.logger = logging.getLogger(f"{__name__}.Runner")
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """運行所有相容性測試"""
        self.logger.info("開始執行相容性測試套件...")
        
        test_cases = [
            ("基本資料庫操作", self._test_basic_database_operations),
            ("Token安全管理", self._test_token_security),
            ("異步操作管理", self._test_async_operations),
            ("錯誤處理機制", self._test_error_handling),
            ("查詢優化功能", self._test_query_optimization),
            ("系統整合測試", self._test_system_integration),
            ("效能壓力測試", self._test_performance)
        ]
        
        results = {
            'total_tests': len(test_cases),
            'passed_tests': 0,
            'failed_tests': 0,
            'test_results': [],
            'overall_status': 'unknown',
            'execution_time': None
        }
        
        start_time = datetime.now()
        
        for test_name, test_func in test_cases:
            try:
                self.logger.info(f"執行測試: {test_name}")
                
                test_start = datetime.now()
                await test_func()
                test_duration = (datetime.now() - test_start).total_seconds()
                
                results['test_results'].append({
                    'name': test_name,
                    'status': 'PASSED',
                    'duration': test_duration,
                    'error': None
                })
                results['passed_tests'] += 1
                
                self.logger.info(f"測試通過: {test_name} ({test_duration:.2f}s)")
                
            except Exception as e:
                test_duration = (datetime.now() - test_start).total_seconds()
                
                results['test_results'].append({
                    'name': test_name,
                    'status': 'FAILED',
                    'duration': test_duration,
                    'error': str(e)
                })
                results['failed_tests'] += 1
                
                self.logger.error(f"測試失敗: {test_name} - {e}")
        
        # 計算總執行時間
        results['execution_time'] = (datetime.now() - start_time).total_seconds()
        
        # 確定整體狀態
        if results['failed_tests'] == 0:
            results['overall_status'] = 'ALL_PASSED'
        elif results['passed_tests'] > results['failed_tests']:
            results['overall_status'] = 'MOSTLY_PASSED'
        else:
            results['overall_status'] = 'MOSTLY_FAILED'
        
        self.logger.info(f"相容性測試完成: {results['overall_status']}")
        self.logger.info(f"總計: {results['total_tests']} 個測試, {results['passed_tests']} 通過, {results['failed_tests']} 失敗")
        
        return results
    
    async def _test_basic_database_operations(self):
        """基本資料庫操作測試"""
        # 創建臨時測試環境
        async with self._create_test_environment() as env:
            repository = env['repository']
            
            # 測試CRUD操作
            subbot = SubBotEntity(
                bot_id="compatibility_test_001",
                name="Compatibility Test Bot",
                token_hash="test_hash",
                target_channels=[123],
                owner_id=999
            )
            
            # 創建
            created = await repository.create_subbot(subbot)
            assert created.id is not None
            
            # 讀取
            retrieved = await repository.get_subbot_by_bot_id("compatibility_test_001")
            assert retrieved is not None
            assert retrieved.name == "Compatibility Test Bot"
            
            # 更新
            retrieved.status = SubBotStatus.ONLINE.value
            updated = await repository.update_subbot(retrieved)
            assert updated is True
            
            # 刪除
            deleted = await repository.delete_subbot("compatibility_test_001")
            assert deleted is True
    
    async def _test_token_security(self):
        """Token安全管理測試"""
        token_manager = SubBotTokenManager()
        await token_manager.initialize()
        
        # 測試加密解密
        original_token = "test_token_12345"
        bot_id = "security_test_bot"
        
        encrypted_token, metadata = await token_manager.encrypt_discord_token(original_token, bot_id)
        decrypted_token = await token_manager.decrypt_discord_token(encrypted_token, metadata, bot_id)
        
        assert decrypted_token == original_token
    
    async def _test_async_operations(self):
        """異步操作管理測試"""
        async_manager = SubBotAsyncManager()
        await async_manager.initialize()
        
        # 測試基本異步操作
        async def test_func(x):
            await asyncio.sleep(0.01)
            return x * 2
        
        result = await async_manager.execute_async(test_func, 5)
        assert result == 10
        
        await async_manager.cleanup()
    
    async def _test_error_handling(self):
        """錯誤處理機制測試"""
        error_handler = SubBotErrorHandler()
        await error_handler.initialize()
        
        from ..error_handler import ErrorContext
        context = ErrorContext(operation="test_error_handling")
        
        # 測試錯誤處理
        test_error = RuntimeError("Test error for compatibility")
        error_event = await error_handler.handle_error(test_error, context)
        
        assert error_event is not None
        assert error_event.error_type == "RuntimeError"
        
        await error_handler.cleanup()
    
    async def _test_query_optimization(self):
        """查詢優化功能測試"""
        optimizer = QueryOptimizer()
        await optimizer.initialize()
        
        # 測試查詢分析
        test_sql = "SELECT * FROM sub_bots WHERE status = ?"
        analysis = await optimizer.analyze_query(test_sql, ("online",), 0.1)
        
        assert 'query_hash' in analysis
        assert 'pattern_analysis' in analysis
        
        await optimizer.cleanup()
    
    async def _test_system_integration(self):
        """系統整合測試"""
        # 測試多個組件協同工作
        async with self._create_test_environment() as env:
            db_service = env['db_service']
            
            # 執行完整的子機器人生命週期
            create_result = await db_service.create_subbot(
                name="Integration Test Bot",
                token="integration_test_token",
                owner_id=123,
                ai_enabled=True
            )
            
            assert create_result['success'] is True
            
            bot_id = create_result['subbot']['bot_id']
            
            # 測試狀態更新
            status_updated = await db_service.update_status(bot_id, SubBotStatus.ONLINE.value)
            assert status_updated is True
            
            # 清理
            deleted = await db_service.delete_subbot(bot_id)
            assert deleted is True
    
    async def _test_performance(self):
        """效能測試"""
        async with self._create_test_environment() as env:
            db_service = env['db_service']
            
            # 批次操作效能測試
            start_time = datetime.now()
            
            create_tasks = []
            for i in range(5):  # 減少數量以加快測試
                task = db_service.create_subbot(
                    name=f"Perf Test Bot {i}",
                    token=f"perf_test_token_{i}",
                    owner_id=i
                )
                create_tasks.append(task)
            
            results = await asyncio.gather(*create_tasks)
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # 驗證所有操作都成功
            success_count = sum(1 for result in results if result['success'])
            assert success_count == 5
            
            # 效能應該在合理範圍內
            assert execution_time < 10.0  # 5個操作應在10秒內完成
            
            # 清理測試數據
            cleanup_tasks = []
            for result in results:
                if result['success']:
                    cleanup_task = db_service.delete_subbot(result['subbot']['bot_id'])
                    cleanup_tasks.append(cleanup_task)
            
            await asyncio.gather(*cleanup_tasks)
    
    async def _create_test_environment(self):
        """創建測試環境上下文管理器"""
        class TestEnvironment:
            def __init__(self):
                self.repository = None
                self.db_service = None
                self.temp_db = None
                self.mock_db_manager = None
            
            async def __aenter__(self):
                # 創建臨時資料庫
                import tempfile
                self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
                self.temp_file.close()
                
                # 設置基本表結構
                conn = sqlite3.connect(self.temp_file.name)
                conn.execute('''
                    CREATE TABLE sub_bots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        bot_id VARCHAR(50) UNIQUE NOT NULL,
                        name VARCHAR(100) NOT NULL,
                        token_hash VARCHAR(255) NOT NULL,
                        target_channels TEXT NOT NULL,
                        ai_enabled BOOLEAN DEFAULT FALSE,
                        ai_model VARCHAR(50),
                        personality TEXT,
                        rate_limit INTEGER DEFAULT 10,
                        status VARCHAR(20) DEFAULT 'offline',
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        last_active_at DATETIME,
                        message_count INTEGER DEFAULT 0,
                        owner_id INTEGER
                    )
                ''')
                conn.close()
                
                # 創建模擬資料庫管理器
                self.mock_db_manager = Mock(spec=DatabaseManager)
                
                async def mock_execute(sql, params=(), db_type="main"):
                    conn = sqlite3.connect(self.temp_file.name)
                    cursor = conn.cursor()
                    cursor.execute(sql, params)
                    conn.commit()
                    result = cursor.lastrowid
                    conn.close()
                    return result
                
                async def mock_fetchone(sql, params=(), db_type="main"):
                    conn = sqlite3.connect(self.temp_file.name)
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute(sql, params)
                    result = cursor.fetchone()
                    conn.close()
                    return dict(result) if result else None
                
                async def mock_fetchall(sql, params=(), db_type="main"):
                    conn = sqlite3.connect(self.temp_file.name)
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute(sql, params)
                    results = cursor.fetchall()
                    conn.close()
                    return [dict(row) for row in results]
                
                self.mock_db_manager.execute = AsyncMock(side_effect=mock_execute)
                self.mock_db_manager.fetchone = AsyncMock(side_effect=mock_fetchone)
                self.mock_db_manager.fetchall = AsyncMock(side_effect=mock_fetchall)
                
                # 創建Repository
                self.repository = SubBotRepository()
                self.repository.db_manager = self.mock_db_manager
                
                # 創建資料庫服務
                self.db_service = SubBotDatabaseService()
                
                with patch('src.core.database.subbot_database_service.get_database_manager') as mock_get_db:
                    mock_get_db.return_value = self.mock_db_manager
                    await self.db_service.initialize()
                
                return self
            
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                # 清理資源
                if self.repository:
                    await self.repository.cleanup()
                
                if self.db_service:
                    await self.db_service.cleanup()
                
                # 刪除臨時檔案
                try:
                    os.unlink(self.temp_file.name)
                except OSError:
                    pass
        
        return TestEnvironment()


# 執行測試的便利函數

async def run_compatibility_tests() -> Dict[str, Any]:
    """
    執行完整的相容性測試套件
    
    Returns:
        測試結果摘要
    """
    runner = TestCompatibilityRunner()
    return await runner.run_all_tests()


def create_test_report(results: Dict[str, Any]) -> str:
    """
    創建測試報告
    
    Args:
        results: 測試結果
        
    Returns:
        格式化的測試報告
    """
    report = []
    report.append("=" * 80)
    report.append("子機器人資料庫系統相容性測試報告")
    report.append("=" * 80)
    report.append("")
    
    # 總結
    report.append(f"執行時間: {results['execution_time']:.2f} 秒")
    report.append(f"總測試數: {results['total_tests']}")
    report.append(f"通過測試: {results['passed_tests']}")
    report.append(f"失敗測試: {results['failed_tests']}")
    report.append(f"整體狀態: {results['overall_status']}")
    report.append("")
    
    # 詳細結果
    report.append("測試詳細結果:")
    report.append("-" * 40)
    
    for test_result in results['test_results']:
        status_icon = "✅" if test_result['status'] == 'PASSED' else "❌"
        report.append(f"{status_icon} {test_result['name']} ({test_result['duration']:.2f}s)")
        
        if test_result['error']:
            report.append(f"   錯誤: {test_result['error']}")
    
    report.append("")
    report.append("=" * 80)
    
    return "\n".join(report)


if __name__ == "__main__":
    # 直接執行測試
    async def main():
        results = await run_compatibility_tests()
        report = create_test_report(results)
        print(report)
        
        # 返回適當的退出碼
        if results['overall_status'] == 'ALL_PASSED':
            exit(0)
        elif results['overall_status'] == 'MOSTLY_PASSED':
            exit(1)
        else:
            exit(2)
    
    asyncio.run(main())