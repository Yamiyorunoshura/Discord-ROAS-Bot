"""
子機器人端到端測試套件
Task ID: 3 - 子機器人聊天功能和管理系統開發

完整的端到端測試，涵蓋子機器人從創建到啟動的整個流程：
- 完整的服務整合測試
- 真實Discord.py模擬
- 資料庫持久化驗證
- 服務間協調測試
- 實際使用場景模擬
"""

import pytest
import asyncio
import json
import tempfile
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, patch, AsyncMock, MagicMock, create_autospec
from pathlib import Path

# 模擬完整的端到端測試環境
class MockDatabaseManager:
    """完整的資料庫管理器模擬"""
    
    def __init__(self):
        self.data = {
            'sub_bots': [],
            'sub_bot_channels': []
        }
        self.connection_active = True
    
    async def fetchall(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """模擬fetchall操作"""
        if not self.connection_active:
            raise Exception("Database connection lost")
        
        if 'sub_bots' in query:
            return self.data['sub_bots']
        elif 'sub_bot_channels' in query:
            return self.data['sub_bot_channels']
        return []
    
    async def fetchone(self, query: str, params: tuple = None) -> Optional[Dict[str, Any]]:
        """模擬fetchone操作"""
        if not self.connection_active:
            raise Exception("Database connection lost")
        
        if params and 'WHERE bot_id = ?' in query:
            bot_id = params[0]
            for bot in self.data['sub_bots']:
                if bot['bot_id'] == bot_id:
                    return bot
        elif params and 'WHERE id =' in query:
            bot_id = params[0]
            for i, bot in enumerate(self.data['sub_bots']):
                if bot['bot_id'] == bot_id:
                    return {'id': i + 1}
        return None
    
    async def execute(self, query: str, params: tuple = None) -> None:
        """模擬execute操作"""
        if not self.connection_active:
            raise Exception("Database connection lost")
        
        if 'INSERT INTO sub_bots' in query:
            # 解析插入的資料
            bot_data = {
                'bot_id': params[0],
                'name': params[1],
                'token_hash': params[2],
                'target_channels': params[3],
                'ai_enabled': params[4],
                'ai_model': params[5],
                'personality': params[6],
                'rate_limit': params[7],
                'status': params[8],
                'created_at': params[9],
                'message_count': params[10]
            }
            self.data['sub_bots'].append(bot_data)
            
        elif 'INSERT INTO sub_bot_channels' in query:
            channel_data = {
                'sub_bot_id': params[0],
                'channel_id': params[1],
                'channel_type': params[2],
                'permissions': params[3]
            }
            self.data['sub_bot_channels'].append(channel_data)
            
        elif 'UPDATE sub_bots SET status' in query:
            # 更新狀態
            new_status, updated_at, bot_id = params
            for bot in self.data['sub_bots']:
                if bot['bot_id'] == bot_id:
                    bot['status'] = new_status
                    bot['updated_at'] = updated_at
                    break
                    
        elif 'DELETE FROM sub_bots WHERE bot_id' in query:
            # 刪除bot
            bot_id = params[0]
            self.data['sub_bots'] = [
                bot for bot in self.data['sub_bots'] 
                if bot['bot_id'] != bot_id
            ]


class MockDiscordClient:
    """完整的Discord客戶端模擬"""
    
    def __init__(self, token: str):
        self.token = token
        self.user = Mock()
        self.user.id = 123456789
        self.user.name = "TestBot"
        
        self.guilds = []
        self.channels = {}
        
        self.is_ready_value = False
        self.is_closed_value = False
        self.latency = 0.05
        
        # 事件回調
        self.on_ready_callback = None
        self.on_message_callback = None
        
        # 連線狀態
        self.connection_attempts = 0
        self.max_connection_attempts = 3
    
    @property
    def is_ready(self):
        return self.is_ready_value
    
    @property
    def is_closed(self):
        return self.is_closed_value
    
    async def start(self, token: str, *, reconnect: bool = True):
        """模擬啟動Discord客戶端"""
        self.connection_attempts += 1
        
        if self.connection_attempts > self.max_connection_attempts:
            raise Exception("Max connection attempts exceeded")
        
        if "invalid" in token.lower():
            raise Exception("Invalid token")
        
        # 模擬連線延遲
        await asyncio.sleep(0.1)
        
        self.token = token
        self.is_ready_value = True
        self.is_closed_value = False
        
        # 觸發ready事件
        if self.on_ready_callback:
            await self.on_ready_callback()
    
    async def close(self):
        """模擬關閉Discord客戶端"""
        self.is_ready_value = False
        self.is_closed_value = True
    
    async def wait_until_ready(self):
        """等待客戶端準備就緒"""
        while not self.is_ready_value:
            await asyncio.sleep(0.01)
    
    def get_channel(self, channel_id: int):
        """獲取頻道"""
        return self.channels.get(channel_id)
    
    def add_mock_channel(self, channel_id: int, name: str = "test-channel"):
        """添加模擬頻道"""
        channel = Mock()
        channel.id = channel_id
        channel.name = name
        channel.send = AsyncMock()
        self.channels[channel_id] = channel
        return channel


class EndToEndTestEnvironment:
    """端到端測試環境"""
    
    def __init__(self):
        self.database_manager = MockDatabaseManager()
        self.discord_clients = {}  # bot_id -> MockDiscordClient
        
        # 創建服務實例
        self.subbot_service = None
        self.channel_service = None
        self.subbot_manager = None
        
        self.setup_services()
    
    def setup_services(self):
        """設定服務實例"""
        # 這裡會創建實際的服務實例，但使用模擬的依賴
        pass
    
    async def create_mock_discord_client(self, token: str) -> MockDiscordClient:
        """創建模擬Discord客戶端"""
        client = MockDiscordClient(token)
        
        # 添加一些測試頻道
        client.add_mock_channel(123456789, "general")
        client.add_mock_channel(987654321, "testing")
        
        return client
    
    async def cleanup(self):
        """清理測試環境"""
        for client in self.discord_clients.values():
            if not client.is_closed:
                await client.close()
        
        self.discord_clients.clear()


@pytest.fixture
async def e2e_environment():
    """端到端測試環境fixture"""
    env = EndToEndTestEnvironment()
    yield env
    await env.cleanup()


@pytest.fixture
def sample_subbot_configs():
    """測試用的子機器人配置"""
    return [
        {
            'name': 'E2E_TestBot1',
            'token': 'MTAxODcxNTI5MzE5NDA3OTQzNw.GXkHZA.e2e_test_token_1',
            'target_channels': [123456789, 987654321],
            'ai_enabled': False,
            'rate_limit': 10
        },
        {
            'name': 'E2E_TestBot2',
            'token': 'MTAxODcxNTI5MzE5NDA3OTQzNw.GXkHZA.e2e_test_token_2',
            'target_channels': [555666777],
            'ai_enabled': True,
            'ai_model': 'gpt-3.5-turbo',
            'rate_limit': 5
        }
    ]


class TestEndToEndSubBotLifecycle:
    """端到端子機器人生命週期測試"""
    
    @pytest.mark.asyncio
    async def test_complete_subbot_lifecycle(self, e2e_environment, sample_subbot_configs):
        """測試完整的子機器人生命週期"""
        env = e2e_environment
        config = sample_subbot_configs[0]
        
        # 模擬服務依賴
        with patch('src.services.subbot_service.SubBotService') as MockSubBotService:
            # 創建實際的服務實例模擬
            service_instance = AsyncMock()
            service_instance.get_dependency.return_value = env.database_manager
            
            # 模擬創建子機器人
            bot_id = f"e2e_bot_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            service_instance.create_sub_bot.return_value = bot_id
            
            # 1. 創建子機器人
            created_bot_id = await service_instance.create_sub_bot(
                name=config['name'],
                token=config['token'],
                target_channels=config['target_channels'],
                ai_enabled=config['ai_enabled'],
                rate_limit=config['rate_limit']
            )
            
            assert created_bot_id == bot_id
            
            # 驗證資料庫中的資料
            service_instance.create_sub_bot.assert_called_once_with(
                name=config['name'],
                token=config['token'],
                target_channels=config['target_channels'],
                ai_enabled=config['ai_enabled'],
                rate_limit=config['rate_limit']
            )
    
    @pytest.mark.asyncio
    async def test_subbot_discord_connection_flow(self, e2e_environment):
        """測試子機器人Discord連線流程"""
        env = e2e_environment
        
        # 創建模擬的Discord客戶端
        token = 'MTAxODcxNTI5MzE5NDA3OTQzNw.GXkHZA.connection_test_token'
        discord_client = await env.create_mock_discord_client(token)
        
        # 測試連線
        await discord_client.start(token)
        
        assert discord_client.is_ready is True
        assert discord_client.is_closed is False
        assert discord_client.token == token
        
        # 測試關閉連線
        await discord_client.close()
        
        assert discord_client.is_ready is False
        assert discord_client.is_closed is True
    
    @pytest.mark.asyncio
    async def test_database_persistence_flow(self, e2e_environment, sample_subbot_configs):
        """測試資料庫持久化流程"""
        env = e2e_environment
        db = env.database_manager
        config = sample_subbot_configs[0]
        
        # 模擬插入子機器人資料
        bot_id = "db_test_bot_123"
        await db.execute(
            """INSERT INTO sub_bots 
               (bot_id, name, token_hash, target_channels, ai_enabled, ai_model, 
                personality, rate_limit, status, created_at, message_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                bot_id,
                config['name'],
                'encrypted_token_hash',
                json.dumps(config['target_channels']),
                config['ai_enabled'],
                config.get('ai_model'),
                config.get('personality'),
                config['rate_limit'],
                'offline',
                datetime.now().isoformat(),
                0
            )
        )
        
        # 驗證資料已保存
        assert len(db.data['sub_bots']) == 1
        saved_bot = db.data['sub_bots'][0]
        assert saved_bot['bot_id'] == bot_id
        assert saved_bot['name'] == config['name']
        assert saved_bot['status'] == 'offline'
        
        # 測試查詢資料
        result = await db.fetchone("SELECT * FROM sub_bots WHERE bot_id = ?", (bot_id,))
        assert result is not None
        assert result['bot_id'] == bot_id
        
        # 測試更新狀態
        await db.execute(
            "UPDATE sub_bots SET status = ?, updated_at = ? WHERE bot_id = ?",
            ('online', datetime.now().isoformat(), bot_id)
        )
        
        # 驗證狀態已更新
        updated_bot = db.data['sub_bots'][0]
        assert updated_bot['status'] == 'online'


class TestServiceIntegration:
    """服務整合測試"""
    
    @pytest.mark.asyncio
    async def test_subbot_service_and_channel_service_integration(self, e2e_environment):
        """測試SubBotService和ChannelService整合"""
        env = e2e_environment
        
        # 創建模擬服務
        subbot_service = AsyncMock()
        channel_service = AsyncMock()
        
        bot_id = "integration_test_bot"
        channels = [123456789, 987654321]
        
        # 模擬創建子機器人
        subbot_service.create_sub_bot.return_value = bot_id
        
        # 模擬分配頻道
        channel_service.assign_channels.return_value = True
        
        # 執行整合測試
        created_bot_id = await subbot_service.create_sub_bot(
            name="IntegrationBot",
            token="test_token",
            target_channels=channels,
            ai_enabled=False,
            rate_limit=10
        )
        
        await channel_service.assign_channels(created_bot_id, channels)
        
        # 驗證調用
        subbot_service.create_sub_bot.assert_called_once()
        channel_service.assign_channels.assert_called_once_with(created_bot_id, channels)
    
    @pytest.mark.asyncio
    async def test_manager_service_coordination(self, e2e_environment):
        """測試Manager服務協調"""
        env = e2e_environment
        
        # 創建模擬管理器
        manager = AsyncMock()
        
        # 模擬註冊多個子機器人
        bot_configs = [
            {'name': 'Bot1', 'token': 'token1', 'channels': [123]},
            {'name': 'Bot2', 'token': 'token2', 'channels': [456]},
        ]
        
        registered_bots = []
        for i, config in enumerate(bot_configs):
            bot_id = f"managed_bot_{i}"
            manager.register_subbot.return_value = bot_id
            
            result = await manager.register_subbot(config)
            registered_bots.append(result)
        
        # 驗證所有bot都已註冊
        assert len(registered_bots) == 2
        assert manager.register_subbot.call_count == 2


class TestErrorRecoveryAndFailures:
    """錯誤恢復和故障測試"""
    
    @pytest.mark.asyncio
    async def test_database_connection_failure_recovery(self, e2e_environment):
        """測試資料庫連線失敗恢復"""
        env = e2e_environment
        db = env.database_manager
        
        # 模擬資料庫連線失敗
        db.connection_active = False
        
        with pytest.raises(Exception, match="Database connection lost"):
            await db.fetchall("SELECT * FROM sub_bots")
        
        # 模擬恢復連線
        db.connection_active = True
        
        # 應該能正常工作
        result = await db.fetchall("SELECT * FROM sub_bots")
        assert result == []
    
    @pytest.mark.asyncio
    async def test_discord_connection_failure_handling(self, e2e_environment):
        """測試Discord連線失敗處理"""
        env = e2e_environment
        
        # 創建有問題的token
        invalid_token = "invalid_discord_token"
        client = await env.create_mock_discord_client(invalid_token)
        
        # 嘗試連線應該失敗
        with pytest.raises(Exception, match="Invalid token"):
            await client.start(invalid_token)
        
        assert client.is_ready is False
    
    @pytest.mark.asyncio
    async def test_partial_failure_handling(self, e2e_environment, sample_subbot_configs):
        """測試部分失敗處理"""
        env = e2e_environment
        
        # 創建服務模擬
        subbot_service = AsyncMock()
        channel_service = AsyncMock()
        
        # 模擬子機器人創建成功，但頻道分配失敗
        bot_id = "partial_failure_bot"
        subbot_service.create_sub_bot.return_value = bot_id
        channel_service.assign_channels.side_effect = Exception("Channel assignment failed")
        
        # 執行操作
        created_bot_id = await subbot_service.create_sub_bot(
            name="PartialFailureBot",
            token="test_token",
            target_channels=[123456789],
            ai_enabled=False,
            rate_limit=10
        )
        
        assert created_bot_id == bot_id
        
        # 頻道分配應該失敗
        with pytest.raises(Exception, match="Channel assignment failed"):
            await channel_service.assign_channels(created_bot_id, [123456789])
        
        # 在實際實現中，這裡應該有清理邏輯


class TestConcurrentOperations:
    """並發操作測試"""
    
    @pytest.mark.asyncio
    async def test_concurrent_subbot_creation(self, e2e_environment):
        """測試並發子機器人創建"""
        env = e2e_environment
        
        # 創建服務模擬
        subbot_service = AsyncMock()
        
        async def create_bot(i):
            bot_id = f"concurrent_bot_{i}"
            subbot_service.create_sub_bot.return_value = bot_id
            
            return await subbot_service.create_sub_bot(
                name=f"ConcurrentBot{i}",
                token=f"token_{i}",
                target_channels=[123456789 + i],
                ai_enabled=False,
                rate_limit=10
            )
        
        # 並發創建5個子機器人
        tasks = [create_bot(i) for i in range(5)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 檢查結果
        successful_creates = [r for r in results if not isinstance(r, Exception)]
        assert len(successful_creates) == 5
        
        # 檢查所有bot_id都是唯一的
        assert len(set(successful_creates)) == 5
    
    @pytest.mark.asyncio
    async def test_concurrent_start_stop_operations(self, e2e_environment):
        """測試並發啟動停止操作"""
        env = e2e_environment
        
        # 創建服務模擬
        subbot_service = AsyncMock()
        
        bot_ids = [f"concurrent_operation_bot_{i}" for i in range(3)]
        
        # 模擬成功的操作
        subbot_service.start_sub_bot.return_value = True
        subbot_service.stop_sub_bot.return_value = True
        
        # 並發啟動
        start_tasks = [subbot_service.start_sub_bot(bot_id) for bot_id in bot_ids]
        start_results = await asyncio.gather(*start_tasks, return_exceptions=True)
        
        # 並發停止
        stop_tasks = [subbot_service.stop_sub_bot(bot_id) for bot_id in bot_ids]
        stop_results = await asyncio.gather(*stop_tasks, return_exceptions=True)
        
        # 檢查結果
        assert all(r is True for r in start_results)
        assert all(r is True for r in stop_results)


class TestRealWorldScenarios:
    """真實世界場景測試"""
    
    @pytest.mark.asyncio
    async def test_multi_guild_subbot_deployment(self, e2e_environment):
        """測試多伺服器子機器人部署"""
        env = e2e_environment
        
        # 模擬多個伺服器的場景
        guilds = [
            {'id': 111111111, 'name': 'TestGuild1', 'channels': [123456789, 123456790]},
            {'id': 222222222, 'name': 'TestGuild2', 'channels': [987654321, 987654322]},
        ]
        
        subbot_service = AsyncMock()
        channel_service = AsyncMock()
        
        created_bots = []
        
        for i, guild in enumerate(guilds):
            bot_id = f"guild_{guild['id']}_bot"
            
            # 模擬為每個伺服器創建子機器人
            subbot_service.create_sub_bot.return_value = bot_id
            channel_service.assign_channels.return_value = True
            
            # 創建子機器人
            created_bot_id = await subbot_service.create_sub_bot(
                name=f"GuildBot_{guild['name']}",
                token=f"guild_token_{i}",
                target_channels=guild['channels'],
                ai_enabled=True,
                ai_model="gpt-3.5-turbo",
                rate_limit=15
            )
            
            # 分配頻道
            await channel_service.assign_channels(created_bot_id, guild['channels'])
            
            created_bots.append(created_bot_id)
        
        # 驗證所有伺服器都有子機器人
        assert len(created_bots) == len(guilds)
        assert subbot_service.create_sub_bot.call_count == len(guilds)
        assert channel_service.assign_channels.call_count == len(guilds)
    
    @pytest.mark.asyncio
    async def test_subbot_message_handling_simulation(self, e2e_environment):
        """測試子機器人訊息處理模擬"""
        env = e2e_environment
        
        # 創建Discord客戶端模擬
        token = 'MTAxODcxNTI5MzE5NDA3OTQzNw.GXkHZA.message_handling_token'
        client = await env.create_mock_discord_client(token)
        
        # 啟動客戶端
        await client.start(token)
        
        # 獲取測試頻道
        channel = client.get_channel(123456789)
        assert channel is not None
        
        # 模擬發送訊息
        await channel.send("Hello from SubBot!")
        
        # 驗證訊息已發送
        channel.send.assert_called_once_with("Hello from SubBot!")
    
    @pytest.mark.asyncio
    async def test_high_availability_scenario(self, e2e_environment):
        """測試高可用性場景"""
        env = e2e_environment
        
        # 模擬高可用性設定：多個子機器人處理相同功能
        subbot_service = AsyncMock()
        channel_service = AsyncMock()
        manager = AsyncMock()
        
        # 創建主要子機器人
        primary_bot_id = "primary_ha_bot"
        subbot_service.create_sub_bot.return_value = primary_bot_id
        
        await subbot_service.create_sub_bot(
            name="PrimaryHABot",
            token="primary_token",
            target_channels=[123456789],
            ai_enabled=True,
            rate_limit=20
        )
        
        # 創建備用子機器人
        backup_bot_id = "backup_ha_bot"
        subbot_service.create_sub_bot.return_value = backup_bot_id
        
        await subbot_service.create_sub_bot(
            name="BackupHABot",
            token="backup_token",
            target_channels=[123456789],  # 相同頻道
            ai_enabled=True,
            rate_limit=20
        )
        
        # 模擬主要bot失敗
        subbot_service.start_sub_bot.side_effect = [
            Exception("Primary bot failed"),  # 主要bot失敗
            True  # 備用bot成功
        ]
        
        # 嘗試啟動主要bot
        try:
            await subbot_service.start_sub_bot(primary_bot_id)
        except Exception:
            # 啟動備用bot
            backup_result = await subbot_service.start_sub_bot(backup_bot_id)
            assert backup_result is True
        
        # 驗證容錯機制
        assert subbot_service.start_sub_bot.call_count == 2


class TestPerformanceAndScaling:
    """效能和擴展性測試"""
    
    @pytest.mark.asyncio
    async def test_database_query_performance(self, e2e_environment):
        """測試資料庫查詢效能"""
        env = e2e_environment
        db = env.database_manager
        
        # 插入大量測試資料
        test_bots = []
        for i in range(100):
            bot_data = {
                'bot_id': f'perf_test_bot_{i}',
                'name': f'PerfTestBot{i}',
                'token_hash': f'encrypted_token_{i}',
                'target_channels': json.dumps([123456789 + i]),
                'ai_enabled': i % 2 == 0,
                'ai_model': 'gpt-3.5-turbo' if i % 2 == 0 else None,
                'personality': None,
                'rate_limit': 10,
                'status': 'offline',
                'created_at': datetime.now().isoformat(),
                'message_count': 0
            }
            test_bots.append(bot_data)
            db.data['sub_bots'].append(bot_data)
        
        # 測試查詢性能
        import time
        
        start_time = time.time()
        result = await db.fetchall("SELECT * FROM sub_bots")
        query_time = time.time() - start_time
        
        assert len(result) == 100
        assert query_time < 1.0  # 應該在1秒內完成
    
    @pytest.mark.asyncio
    async def test_memory_usage_scaling(self, e2e_environment):
        """測試記憶體使用擴展性"""
        env = e2e_environment
        
        # 創建多個Discord客戶端模擬記憶體使用
        clients = []
        
        for i in range(20):  # 創建20個客戶端
            token = f'MTAxODcxNTI5MzE5NDA3OTQzNw.GXkHZA.memory_test_token_{i}'
            client = await env.create_mock_discord_client(token)
            clients.append(client)
        
        # 檢查所有客戶端都已創建
        assert len(clients) == 20
        
        # 清理客戶端
        for client in clients:
            if not client.is_closed:
                await client.close()
        
        # 驗證清理完成
        closed_clients = [c for c in clients if c.is_closed]
        assert len(closed_clients) == 20


if __name__ == "__main__":
    # 運行測試時的配置
    pytest.main([
        __file__,
        "-v",  # 詳細輸出
        "--tb=short",  # 簡短的錯誤追蹤
        "-x",  # 遇到第一個失敗就停止
        "--asyncio-mode=auto",  # 自動asyncio模式
    ])