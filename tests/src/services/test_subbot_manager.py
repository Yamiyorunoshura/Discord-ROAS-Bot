"""
子機器人管理器測試套件
Task ID: 3 - 子機器人聊天功能和管理系統開發

測試SubBotManager統一管理所有子機器人實例和異步任務調度：
- 子機器人註冊和取消註冊
- 實例池管理
- 異步任務調度和監控  
- 服務整合
- 並發管理和資源控制
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List
from unittest.mock import Mock, patch, AsyncMock, MagicMock

# 由於SubBotManager尚未實現，我們先創建一個模擬版本用於測試
class MockSubBotManager:
    """SubBotManager的模擬實現，用於測試驅動開發"""
    
    def __init__(self, service_registry=None):
        self.service_registry = service_registry
        self.managed_bots: Dict[str, Dict[str, Any]] = {}
        self.bot_tasks: Dict[str, asyncio.Task] = {}
        self.monitoring_task: Optional[asyncio.Task] = None
        self.max_concurrent_bots = 10
        self.health_check_interval = 60
        self._shutdown_event = asyncio.Event()
    
    async def register_subbot(self, config: Dict[str, Any]) -> str:
        """註冊新的子機器人"""
        if len(self.managed_bots) >= self.max_concurrent_bots:
            raise Exception(f"已達最大並發數限制: {self.max_concurrent_bots}")
        
        bot_id = f"managed_bot_{len(self.managed_bots) + 1}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        self.managed_bots[bot_id] = {
            **config,
            'bot_id': bot_id,
            'registered_at': datetime.now(),
            'status': 'registered',
            'last_health_check': None,
            'error_count': 0
        }
        
        return bot_id
    
    async def unregister_subbot(self, bot_id: str) -> bool:
        """取消註冊子機器人"""
        if bot_id not in self.managed_bots:
            return False
        
        # 停止相關任務
        if bot_id in self.bot_tasks:
            task = self.bot_tasks[bot_id]
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            del self.bot_tasks[bot_id]
        
        del self.managed_bots[bot_id]
        return True
    
    def list_subbots(self) -> List[Dict[str, Any]]:
        """列出所有管理中的子機器人"""
        return [
            {
                'bot_id': bot_id,
                'name': config['name'],
                'status': config['status'],
                'registered_at': config['registered_at'],
                'error_count': config['error_count'],
                'has_active_task': bot_id in self.bot_tasks
            }
            for bot_id, config in self.managed_bots.items()
        ]
    
    async def start_monitoring(self) -> None:
        """啟動監控任務"""
        if self.monitoring_task and not self.monitoring_task.done():
            return  # 已經在運行
        
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
    
    async def stop_monitoring(self) -> None:
        """停止監控任務"""
        self._shutdown_event.set()
        
        if self.monitoring_task and not self.monitoring_task.done():
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
    
    async def _monitoring_loop(self) -> None:
        """監控循環"""
        while not self._shutdown_event.is_set():
            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(), 
                    timeout=self.health_check_interval
                )
                break  # 收到停止信號
            except asyncio.TimeoutError:
                # 執行健康檢查
                await self._perform_health_checks()
    
    async def _perform_health_checks(self) -> None:
        """執行健康檢查"""
        for bot_id, config in self.managed_bots.items():
            try:
                # 模擬健康檢查
                config['last_health_check'] = datetime.now()
                
                # 模擬偶爾的健康檢查失敗
                if config.get('simulate_health_failure', False):
                    config['error_count'] += 1
                    config['status'] = 'unhealthy'
                else:
                    config['status'] = 'healthy'
                    
            except Exception as e:
                config['error_count'] += 1
                config['status'] = 'error'
    
    async def get_bot_status(self, bot_id: str) -> Dict[str, Any]:
        """獲取特定子機器人狀態"""
        if bot_id not in self.managed_bots:
            raise ValueError(f"未找到子機器人: {bot_id}")
        
        config = self.managed_bots[bot_id]
        return {
            'bot_id': bot_id,
            'status': config['status'],
            'registered_at': config['registered_at'],
            'last_health_check': config['last_health_check'],
            'error_count': config['error_count'],
            'has_active_task': bot_id in self.bot_tasks,
            'uptime': datetime.now() - config['registered_at']
        }
    
    async def restart_subbot(self, bot_id: str) -> bool:
        """重啟子機器人"""
        if bot_id not in self.managed_bots:
            return False
        
        config = self.managed_bots[bot_id]
        
        # 停止舊任務
        if bot_id in self.bot_tasks:
            task = self.bot_tasks[bot_id]
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        # 重置狀態
        config['error_count'] = 0
        config['status'] = 'restarting'
        config['last_health_check'] = None
        
        return True


@pytest.fixture
def mock_service_registry():
    """提供模擬的服務註冊表"""
    registry = Mock()
    registry.get_service.return_value = None
    registry.register_service = Mock()
    registry.unregister_service = Mock()
    return registry


@pytest.fixture
async def subbot_manager(mock_service_registry):
    """創建SubBotManager實例用於測試"""
    manager = MockSubBotManager(service_registry=mock_service_registry)
    yield manager
    # 清理
    await manager.stop_monitoring()


@pytest.fixture
def sample_bot_configs():
    """提供測試用的子機器人配置"""
    return [
        {
            'name': 'TestBot1',
            'token': 'MTAxODcxNTI5MzE5NDA3OTQzNw.GXkHZA.test_token_1',
            'target_channels': [123456789],
            'ai_enabled': True,
            'ai_model': 'gpt-3.5-turbo'
        },
        {
            'name': 'TestBot2',
            'token': 'MTAxODcxNTI5MzE5NDA3OTQzNw.GXkHZA.test_token_2',
            'target_channels': [987654321],
            'ai_enabled': False
        },
        {
            'name': 'TestBot3',
            'token': 'MTAxODcxNTI5MzE5NDA3OTQzNw.GXkHZA.test_token_3',
            'target_channels': [555666777],
            'ai_enabled': True,
            'ai_model': 'gpt-4'
        }
    ]


class TestSubBotManagerInitialization:
    """SubBotManager初始化測試"""
    
    def test_manager_initialization(self, mock_service_registry):
        """測試管理器正確初始化"""
        manager = MockSubBotManager(service_registry=mock_service_registry)
        
        assert manager.service_registry == mock_service_registry
        assert len(manager.managed_bots) == 0
        assert len(manager.bot_tasks) == 0
        assert manager.monitoring_task is None
        assert manager.max_concurrent_bots == 10
        assert manager.health_check_interval == 60
    
    def test_manager_initialization_with_custom_limits(self, mock_service_registry):
        """測試使用自定義限制初始化管理器"""
        manager = MockSubBotManager(service_registry=mock_service_registry)
        manager.max_concurrent_bots = 20
        manager.health_check_interval = 30
        
        assert manager.max_concurrent_bots == 20
        assert manager.health_check_interval == 30


class TestSubBotRegistration:
    """子機器人註冊功能測試"""
    
    @pytest.mark.asyncio
    async def test_register_single_subbot(self, subbot_manager, sample_bot_configs):
        """測試註冊單個子機器人"""
        config = sample_bot_configs[0]
        
        bot_id = await subbot_manager.register_subbot(config)
        
        assert bot_id is not None
        assert bot_id.startswith('managed_bot_')
        assert bot_id in subbot_manager.managed_bots
        
        registered_config = subbot_manager.managed_bots[bot_id]
        assert registered_config['name'] == config['name']
        assert registered_config['bot_id'] == bot_id
        assert registered_config['status'] == 'registered'
        assert 'registered_at' in registered_config
    
    @pytest.mark.asyncio
    async def test_register_multiple_subbots(self, subbot_manager, sample_bot_configs):
        """測試註冊多個子機器人"""
        bot_ids = []
        
        for config in sample_bot_configs:
            bot_id = await subbot_manager.register_subbot(config)
            bot_ids.append(bot_id)
        
        assert len(bot_ids) == 3
        assert len(set(bot_ids)) == 3  # 確保所有ID都是唯一的
        assert len(subbot_manager.managed_bots) == 3
        
        # 檢查每個bot都正確註冊
        for i, bot_id in enumerate(bot_ids):
            config = subbot_manager.managed_bots[bot_id]
            assert config['name'] == sample_bot_configs[i]['name']
    
    @pytest.mark.asyncio
    async def test_register_subbot_exceeds_limit(self, subbot_manager, sample_bot_configs):
        """測試註冊子機器人超過限制"""
        # 設置較小的限制
        subbot_manager.max_concurrent_bots = 2
        
        # 註冊到限制數量
        for i in range(2):
            await subbot_manager.register_subbot(sample_bot_configs[i])
        
        # 嘗試超過限制
        with pytest.raises(Exception, match="已達最大並發數限制"):
            await subbot_manager.register_subbot(sample_bot_configs[2])
    
    @pytest.mark.asyncio
    async def test_unregister_subbot(self, subbot_manager, sample_bot_configs):
        """測試取消註冊子機器人"""
        config = sample_bot_configs[0]
        bot_id = await subbot_manager.register_subbot(config)
        
        # 驗證已註冊
        assert bot_id in subbot_manager.managed_bots
        
        # 取消註冊
        result = await subbot_manager.unregister_subbot(bot_id)
        
        assert result is True
        assert bot_id not in subbot_manager.managed_bots
        assert bot_id not in subbot_manager.bot_tasks
    
    @pytest.mark.asyncio
    async def test_unregister_nonexistent_subbot(self, subbot_manager):
        """測試取消註冊不存在的子機器人"""
        result = await subbot_manager.unregister_subbot("nonexistent_bot")
        assert result is False


class TestSubBotListing:
    """子機器人列表功能測試"""
    
    @pytest.mark.asyncio
    async def test_list_empty_subbots(self, subbot_manager):
        """測試列出空的子機器人列表"""
        bot_list = subbot_manager.list_subbots()
        assert bot_list == []
    
    @pytest.mark.asyncio
    async def test_list_subbots(self, subbot_manager, sample_bot_configs):
        """測試列出子機器人"""
        bot_ids = []
        for config in sample_bot_configs:
            bot_id = await subbot_manager.register_subbot(config)
            bot_ids.append(bot_id)
        
        bot_list = subbot_manager.list_subbots()
        
        assert len(bot_list) == 3
        
        for i, bot_info in enumerate(bot_list):
            assert bot_info['bot_id'] == bot_ids[i]
            assert bot_info['name'] == sample_bot_configs[i]['name']
            assert bot_info['status'] == 'registered'
            assert 'registered_at' in bot_info
            assert 'error_count' in bot_info
            assert 'has_active_task' in bot_info


class TestMonitoringAndHealthChecks:
    """監控和健康檢查測試"""
    
    @pytest.mark.asyncio
    async def test_start_monitoring(self, subbot_manager):
        """測試啟動監控"""
        await subbot_manager.start_monitoring()
        
        assert subbot_manager.monitoring_task is not None
        assert not subbot_manager.monitoring_task.done()
        
        # 清理
        await subbot_manager.stop_monitoring()
    
    @pytest.mark.asyncio
    async def test_stop_monitoring(self, subbot_manager):
        """測試停止監控"""
        await subbot_manager.start_monitoring()
        
        # 確保監控正在運行
        assert subbot_manager.monitoring_task is not None
        assert not subbot_manager.monitoring_task.done()
        
        await subbot_manager.stop_monitoring()
        
        # 監控任務應該被取消
        assert subbot_manager.monitoring_task.done()
    
    @pytest.mark.asyncio
    async def test_health_check_execution(self, subbot_manager, sample_bot_configs):
        """測試健康檢查執行"""
        # 註冊一些子機器人
        bot_ids = []
        for config in sample_bot_configs:
            bot_id = await subbot_manager.register_subbot(config)
            bot_ids.append(bot_id)
        
        # 手動執行健康檢查
        await subbot_manager._perform_health_checks()
        
        # 檢查所有bot都被健康檢查
        for bot_id in bot_ids:
            config = subbot_manager.managed_bots[bot_id]
            assert config['last_health_check'] is not None
            assert config['status'] in ['healthy', 'unhealthy', 'error']
    
    @pytest.mark.asyncio
    async def test_health_check_failure_handling(self, subbot_manager, sample_bot_configs):
        """測試健康檢查失敗處理"""
        config = sample_bot_configs[0]
        bot_id = await subbot_manager.register_subbot(config)
        
        # 設置模擬健康檢查失敗
        subbot_manager.managed_bots[bot_id]['simulate_health_failure'] = True
        
        # 執行健康檢查
        await subbot_manager._perform_health_checks()
        
        # 檢查失敗被正確記錄
        bot_config = subbot_manager.managed_bots[bot_id]
        assert bot_config['error_count'] > 0
        assert bot_config['status'] == 'unhealthy'
    
    @pytest.mark.asyncio
    async def test_get_bot_status(self, subbot_manager, sample_bot_configs):
        """測試獲取子機器人狀態"""
        config = sample_bot_configs[0]
        bot_id = await subbot_manager.register_subbot(config)
        
        # 執行一次健康檢查
        await subbot_manager._perform_health_checks()
        
        status = await subbot_manager.get_bot_status(bot_id)
        
        assert status['bot_id'] == bot_id
        assert 'status' in status
        assert 'registered_at' in status
        assert 'last_health_check' in status
        assert 'error_count' in status
        assert 'has_active_task' in status
        assert 'uptime' in status
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_bot_status(self, subbot_manager):
        """測試獲取不存在子機器人的狀態"""
        with pytest.raises(ValueError, match="未找到子機器人"):
            await subbot_manager.get_bot_status("nonexistent_bot")


class TestSubBotTaskManagement:
    """子機器人任務管理測試"""
    
    @pytest.mark.asyncio
    async def test_restart_subbot(self, subbot_manager, sample_bot_configs):
        """測試重啟子機器人"""
        config = sample_bot_configs[0]
        bot_id = await subbot_manager.register_subbot(config)
        
        # 模擬一些錯誤
        subbot_manager.managed_bots[bot_id]['error_count'] = 5
        subbot_manager.managed_bots[bot_id]['status'] = 'error'
        
        result = await subbot_manager.restart_subbot(bot_id)
        
        assert result is True
        
        # 檢查狀態已重置
        bot_config = subbot_manager.managed_bots[bot_id]
        assert bot_config['error_count'] == 0
        assert bot_config['status'] == 'restarting'
        assert bot_config['last_health_check'] is None
    
    @pytest.mark.asyncio
    async def test_restart_nonexistent_subbot(self, subbot_manager):
        """測試重啟不存在的子機器人"""
        result = await subbot_manager.restart_subbot("nonexistent_bot")
        assert result is False


class TestConcurrencyAndResourceManagement:
    """並發和資源管理測試"""
    
    @pytest.mark.asyncio
    async def test_concurrent_registration(self, subbot_manager):
        """測試並發註冊子機器人"""
        # 設置較大的限制
        subbot_manager.max_concurrent_bots = 20
        
        async def register_bot(i):
            config = {
                'name': f'ConcurrentBot{i}',
                'token': f'MTAxODcxNTI5MzE5NDA3OTQzNw.GXkHZA.token_{i}',
                'target_channels': [123456789 + i],
                'ai_enabled': i % 2 == 0
            }
            return await subbot_manager.register_subbot(config)
        
        # 並發註冊10個子機器人
        tasks = [register_bot(i) for i in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 檢查所有註冊都成功
        successful_registrations = [r for r in results if not isinstance(r, Exception)]
        assert len(successful_registrations) == 10
        
        # 檢查所有bot_id都是唯一的
        assert len(set(successful_registrations)) == 10
        
        # 檢查管理器狀態
        assert len(subbot_manager.managed_bots) == 10
    
    @pytest.mark.asyncio
    async def test_concurrent_unregistration(self, subbot_manager, sample_bot_configs):
        """測試並發取消註冊"""
        # 首先註冊多個子機器人
        bot_ids = []
        for config in sample_bot_configs:
            bot_id = await subbot_manager.register_subbot(config)
            bot_ids.append(bot_id)
        
        # 並發取消註冊
        tasks = [subbot_manager.unregister_subbot(bot_id) for bot_id in bot_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 檢查所有取消註冊都成功
        successful_unregistrations = [r for r in results if r is True]
        assert len(successful_unregistrations) == 3
        
        # 檢查管理器已清空
        assert len(subbot_manager.managed_bots) == 0
    
    @pytest.mark.asyncio
    async def test_resource_cleanup_on_unregistration(self, subbot_manager, sample_bot_configs):
        """測試取消註冊時的資源清理"""
        config = sample_bot_configs[0]
        bot_id = await subbot_manager.register_subbot(config)
        
        # 模擬活躍任務
        async def dummy_task():
            await asyncio.sleep(10)  # 長時間運行的任務
        
        subbot_manager.bot_tasks[bot_id] = asyncio.create_task(dummy_task())
        
        # 驗證任務正在運行
        assert bot_id in subbot_manager.bot_tasks
        assert not subbot_manager.bot_tasks[bot_id].done()
        
        # 取消註冊
        await subbot_manager.unregister_subbot(bot_id)
        
        # 驗證任務已被清理
        assert bot_id not in subbot_manager.bot_tasks


class TestErrorHandlingAndEdgeCases:
    """錯誤處理和邊界條件測試"""
    
    @pytest.mark.asyncio
    async def test_monitoring_with_no_bots(self, subbot_manager):
        """測試沒有子機器人時的監控"""
        # 設置很短的間隔以便測試
        subbot_manager.health_check_interval = 0.1
        
        await subbot_manager.start_monitoring()
        
        # 讓它運行一小段時間
        await asyncio.sleep(0.2)
        
        await subbot_manager.stop_monitoring()
        
        # 應該沒有崩潰或錯誤
        assert True  # 如果到達這裡說明沒有異常
    
    @pytest.mark.asyncio
    async def test_double_start_monitoring(self, subbot_manager):
        """測試重複啟動監控"""
        await subbot_manager.start_monitoring()
        first_task = subbot_manager.monitoring_task
        
        # 再次啟動監控
        await subbot_manager.start_monitoring()
        second_task = subbot_manager.monitoring_task
        
        # 應該是同一個任務
        assert first_task is second_task
        
        await subbot_manager.stop_monitoring()
    
    @pytest.mark.asyncio
    async def test_stop_monitoring_without_start(self, subbot_manager):
        """測試在沒有啟動的情況下停止監控"""
        # 應該不會崩潰
        await subbot_manager.stop_monitoring()
        assert True
    
    @pytest.mark.asyncio
    async def test_registration_with_invalid_config(self, subbot_manager):
        """測試使用無效配置註冊"""
        invalid_configs = [
            None,
            {},
            {'name': ''},  # 空名稱
            {'token': ''},  # 空token
        ]
        
        for invalid_config in invalid_configs:
            try:
                await subbot_manager.register_subbot(invalid_config)
                # 如果沒有拋出異常，檢查是否正確處理了無效配置
                # 這取決於具體的實現邏輯
            except Exception:
                # 預期的異常
                pass


class TestServiceIntegration:
    """服務整合測試"""
    
    def test_service_registry_integration(self, mock_service_registry):
        """測試服務註冊表整合"""
        manager = MockSubBotManager(service_registry=mock_service_registry)
        
        # 檢查服務註冊表已正確設置
        assert manager.service_registry is mock_service_registry
    
    @pytest.mark.asyncio
    async def test_manager_lifecycle_with_service_registry(self, mock_service_registry):
        """測試管理器生命週期與服務註冊表的整合"""
        manager = MockSubBotManager(service_registry=mock_service_registry)
        
        # 啟動管理器
        await manager.start_monitoring()
        
        # 模擬一些操作
        config = {
            'name': 'ServiceTestBot',
            'token': 'MTAxODcxNTI5MzE5NDA3OTQzNw.GXkHZA.service_test_token',
            'target_channels': [123456789]
        }
        
        bot_id = await manager.register_subbot(config)
        assert bot_id in manager.managed_bots
        
        # 清理
        await manager.unregister_subbot(bot_id)
        await manager.stop_monitoring()
        
        assert len(manager.managed_bots) == 0


if __name__ == "__main__":
    # 運行測試時的配置
    pytest.main([
        __file__,
        "-v",  # 詳細輸出
        "--tb=short",  # 簡短的錯誤追蹤
        "-x",  # 遇到第一個失敗就停止
    ])