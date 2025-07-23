"""
資料同步系統測試模組

測試 SyncDataCog 和 SyncDataDatabase 的功能
"""

import pytest
import pytest_asyncio
import asyncio
import os
import tempfile
import discord
from discord.ext import commands
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock

# 導入要測試的模組
from cogs.sync_data.main.main import SyncDataCog
from cogs.sync_data.database.database import SyncDataDatabase


class TestSyncDataDatabase:
    """測試資料同步系統資料庫"""
    
    @pytest_asyncio.fixture
    async def db(self):
        """創建資料庫實例"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            mock_bot = Mock()
            db = SyncDataDatabase(mock_bot)
            db.db_path = temp_path
            await db.init_db()
            yield db
        finally:
            # 清理
            await db.close()
            try:
                os.unlink(temp_path)
            except FileNotFoundError:
                pass
    
    @pytest.mark.asyncio
    async def test_init_db(self, db):
        """測試資料庫初始化"""
        # 檢查表格是否創建
        pool = await db._get_pool()
        async with pool.get_connection_context(db.db_path) as conn:
            cursor = await conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = await cursor.fetchall()
            table_names = [table[0] for table in tables]
            
            assert 'roles' in table_names
            assert 'channels' in table_names
            assert 'sync_data_log' in table_names
    
    @pytest.mark.asyncio
    async def test_insert_or_replace_role(self, db):
        """測試插入或更新角色資料"""
        # 創建模擬角色
        mock_role = Mock(spec=discord.Role)
        mock_role.id = 12345
        mock_role.guild.id = 67890
        mock_role.name = "測試角色"
        mock_role.color = discord.Color.red()
        mock_role.permissions.value = 8
        mock_role.position = 1
        mock_role.mentionable = True
        mock_role.hoist = False
        mock_role.managed = False
        
        # 插入角色
        await db.insert_or_replace_role(mock_role)
        
        # 驗證插入結果
        roles = await db.get_guild_roles(67890)
        assert len(roles) == 1
        assert roles[0]['role_id'] == 12345
        assert roles[0]['name'] == "測試角色"
    
    @pytest.mark.asyncio
    async def test_get_guild_roles(self, db):
        """測試獲取伺服器角色資料"""
        guild_id = 12345
        
        # 插入測試資料
        await db.execute(
            "INSERT INTO roles (role_id, guild_id, name, color, permissions, position, mentionable, hoist, managed) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (1, guild_id, "角色1", "red", 8, 1, True, False, False)
        )
        await db.execute(
            "INSERT INTO roles (role_id, guild_id, name, color, permissions, position, mentionable, hoist, managed) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (2, guild_id, "角色2", "blue", 0, 2, False, True, True)
        )
        
        # 獲取角色資料
        roles = await db.get_guild_roles(guild_id)
        assert len(roles) == 2
        assert roles[0]['name'] == "角色1"
        assert roles[1]['name'] == "角色2"
    
    @pytest.mark.asyncio
    async def test_delete_role(self, db):
        """測試刪除角色資料"""
        guild_id = 12345
        role_id = 1
        
        # 插入測試資料
        await db.execute(
            "INSERT INTO roles (role_id, guild_id, name, color, permissions, position, mentionable, hoist, managed) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (role_id, guild_id, "測試角色", "red", 8, 1, True, False, False)
        )
        
        # 確認資料存在
        roles = await db.get_guild_roles(guild_id)
        assert len(roles) == 1
        
        # 刪除角色
        await db.delete_role(role_id)
        
        # 確認資料已刪除
        roles = await db.get_guild_roles(guild_id)
        assert len(roles) == 0
    
    @pytest.mark.asyncio
    async def test_insert_or_replace_channel(self, db):
        """測試插入或更新頻道資料"""
        # 創建模擬頻道
        mock_channel = Mock(spec=discord.TextChannel)
        mock_channel.id = 12345
        mock_channel.guild.id = 67890
        mock_channel.name = "測試頻道"
        mock_channel.type = discord.ChannelType.text
        mock_channel.topic = "測試主題"
        mock_channel.position = 1
        mock_channel.category_id = None
        
        # 插入頻道
        await db.insert_or_replace_channel(mock_channel)
        
        # 驗證插入結果
        channels = await db.get_guild_channels(67890)
        assert len(channels) == 1
        assert channels[0]['channel_id'] == 12345
        assert channels[0]['name'] == "測試頻道"
    
    @pytest.mark.asyncio
    async def test_get_guild_channels(self, db):
        """測試獲取伺服器頻道資料"""
        guild_id = 12345
        
        # 插入測試資料
        await db.execute(
            "INSERT INTO channels (channel_id, guild_id, name, type, topic, position, category_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (1, guild_id, "頻道1", "text", "主題1", 1, None)
        )
        await db.execute(
            "INSERT INTO channels (channel_id, guild_id, name, type, topic, position, category_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (2, guild_id, "頻道2", "voice", None, 2, None)
        )
        
        # 獲取頻道資料
        channels = await db.get_guild_channels(guild_id)
        assert len(channels) == 2
        assert channels[0]['name'] == "頻道1"
        assert channels[1]['name'] == "頻道2"
    
    @pytest.mark.asyncio
    async def test_delete_channel(self, db):
        """測試刪除頻道資料"""
        guild_id = 12345
        channel_id = 1
        
        # 插入測試資料
        await db.execute(
            "INSERT INTO channels (channel_id, guild_id, name, type, topic, position, category_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (channel_id, guild_id, "測試頻道", "text", "主題", 1, None)
        )
        
        # 確認資料存在
        channels = await db.get_guild_channels(guild_id)
        assert len(channels) == 1
        
        # 刪除頻道
        await db.delete_channel(channel_id)
        
        # 確認資料已刪除
        channels = await db.get_guild_channels(guild_id)
        assert len(channels) == 0
    
    @pytest.mark.asyncio
    async def test_log_sync_result(self, db):
        """測試記錄同步結果"""
        guild_id = 12345
        sync_type = "full"
        status = "success"
        start_time = datetime.utcnow()
        end_time = start_time + timedelta(seconds=10)
        
        # 記錄同步結果
        await db.log_sync_result(
            guild_id=guild_id,
            sync_type=sync_type,
            status=status,
            roles_affected=5,
            channels_affected=3,
            error_message="",
            start_time=start_time,
            end_time=end_time,
            duration=10.0
        )
        
        # 驗證記錄結果
        history = await db.get_sync_history(guild_id)
        assert len(history) == 1
        assert history[0]['sync_type'] == sync_type
        assert history[0]['status'] == status
        assert history[0]['roles_affected'] == 5
        assert history[0]['channels_affected'] == 3
    
    @pytest.mark.asyncio
    async def test_get_sync_history(self, db):
        """測試獲取同步歷史記錄"""
        guild_id = 12345
        
        # 插入多筆同步記錄
        for i in range(3):
            await db.log_sync_result(
                guild_id=guild_id,
                sync_type="full",
                status="success",
                roles_affected=i + 1,
                channels_affected=i + 2,
                start_time=datetime.utcnow(),
                end_time=datetime.utcnow(),
                duration=float(i + 1)
            )
        
        # 獲取同步歷史
        history = await db.get_sync_history(guild_id)
        assert len(history) == 3
        
        # 限制數量測試
        history_limited = await db.get_sync_history(guild_id, limit=2)
        assert len(history_limited) == 2


class TestSyncDataCog:
    """測試資料同步系統 Cog"""
    
    @pytest.fixture
    def mock_bot(self):
        """創建模擬的 Bot"""
        bot = Mock(spec=commands.Bot)
        return bot
    
    @pytest_asyncio.fixture
    async def sync_cog(self, mock_bot):
        """創建資料同步系統 Cog"""
        with patch('cogs.sync_data.main.main.SyncDataDatabase') as mock_db_class:
            mock_db = AsyncMock()
            mock_db_class.return_value = mock_db
            
            cog = SyncDataCog(mock_bot)
            cog.db = mock_db
            
            yield cog
    
    @pytest.mark.asyncio
    async def test_sync_guild_data_full(self, sync_cog):
        """測試完整同步伺服器資料"""
        # 創建模擬伺服器
        mock_guild = Mock(spec=discord.Guild)
        mock_guild.id = 12345
        mock_guild.name = "測試伺服器"
        
        # 創建模擬角色
        mock_role = Mock(spec=discord.Role)
        mock_role.id = 1
        mock_role.name = "測試角色"
        mock_guild.roles = [mock_role]
        
        # 創建模擬頻道
        mock_channel = Mock(spec=discord.TextChannel)
        mock_channel.id = 1
        mock_channel.name = "測試頻道"
        mock_guild.channels = [mock_channel]
        
        # 設定資料庫模擬
        sync_cog.db.get_guild_roles.return_value = []
        sync_cog.db.get_guild_channels.return_value = []
        
        # 執行同步
        result = await sync_cog.sync_guild_data(mock_guild, "full")
        
        # 驗證結果
        assert result["success"] is True
        assert "roles_added" in result
        assert "channels_added" in result
        assert result["sync_type"] == "full"
    
    @pytest.mark.asyncio
    async def test_sync_guild_data_roles_only(self, sync_cog):
        """測試僅同步角色"""
        # 創建模擬伺服器
        mock_guild = Mock(spec=discord.Guild)
        mock_guild.id = 12345
        mock_guild.name = "測試伺服器"
        
        # 創建模擬角色
        mock_role = Mock(spec=discord.Role)
        mock_role.id = 1
        mock_role.name = "測試角色"
        mock_guild.roles = [mock_role]
        
        # 設定資料庫模擬
        sync_cog.db.get_guild_roles.return_value = []
        
        # 執行同步
        result = await sync_cog.sync_guild_data(mock_guild, "roles")
        
        # 驗證結果
        assert result["success"] is True
        assert result["sync_type"] == "roles"
        assert "roles_added" in result
    
    @pytest.mark.asyncio
    async def test_sync_guild_data_channels_only(self, sync_cog):
        """測試僅同步頻道"""
        # 創建模擬伺服器
        mock_guild = Mock(spec=discord.Guild)
        mock_guild.id = 12345
        mock_guild.name = "測試伺服器"
        
        # 創建模擬頻道
        mock_channel = Mock(spec=discord.TextChannel)
        mock_channel.id = 1
        mock_channel.name = "測試頻道"
        mock_guild.channels = [mock_channel]
        
        # 設定資料庫模擬
        sync_cog.db.get_guild_channels.return_value = []
        
        # 執行同步
        result = await sync_cog.sync_guild_data(mock_guild, "channels")
        
        # 驗證結果
        assert result["success"] is True
        assert result["sync_type"] == "channels"
        assert "channels_added" in result
    
    def test_get_cache_key(self, sync_cog):
        """測試快取鍵生成"""
        guild_id = 12345
        cache_key = sync_cog._get_cache_key(guild_id)
        assert cache_key == "sync_12345"
    
    def test_is_syncing(self, sync_cog):
        """測試同步狀態檢查"""
        guild_id = 12345
        
        # 初始狀態應該不是同步中
        assert not sync_cog._is_syncing(guild_id)
        
        # 標記為同步中
        sync_cog._mark_syncing(guild_id)
        
        # 現在應該是同步中
        assert sync_cog._is_syncing(guild_id)
    
    @pytest.mark.asyncio
    async def test_get_sync_lock(self, sync_cog):
        """測試同步鎖獲取"""
        guild_id = 12345
        
        # 獲取同步鎖
        lock1 = await sync_cog._get_sync_lock(guild_id)
        lock2 = await sync_cog._get_sync_lock(guild_id)
        
        # 應該是同一個鎖
        assert lock1 is lock2
        assert isinstance(lock1, asyncio.Lock)
    
    @pytest.mark.asyncio
    async def test_cog_load(self, sync_cog):
        """測試 Cog 載入"""
        # 執行載入
        await sync_cog.cog_load()
        
        # 驗證資料庫初始化被調用
        sync_cog.db.init_db.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cog_unload(self, sync_cog):
        """測試 Cog 卸載"""
        # 添加一些同步鎖
        await sync_cog._get_sync_lock(12345)
        await sync_cog._get_sync_lock(67890)
        
        # 執行卸載
        await sync_cog.cog_unload()
        
        # 驗證鎖被清理
        assert len(sync_cog._sync_locks) == 0


class TestSyncDataIntegration:
    """測試資料同步系統整合"""
    
    @pytest.mark.asyncio
    async def test_full_sync_workflow(self):
        """測試完整的同步工作流程"""
        # 這是一個簡化的整合測試
        mock_bot = Mock(spec=commands.Bot)
        
        with patch('cogs.sync_data.main.main.SyncDataDatabase') as mock_db_class:
            mock_db = AsyncMock()
            mock_db_class.return_value = mock_db
            
            # 創建 Cog
            cog = SyncDataCog(mock_bot)
            assert cog.bot == mock_bot
            assert cog.db is not None
            
            # 測試初始化
            await cog.cog_load()
            mock_db.init_db.assert_called_once()


class TestSyncDataPerformance:
    """測試資料同步系統性能"""
    
    @pytest.mark.asyncio
    async def test_concurrent_sync_operations(self):
        """測試並發同步操作"""
        mock_bot = Mock(spec=commands.Bot)
        
        with patch('cogs.sync_data.main.main.SyncDataDatabase') as mock_db_class:
            mock_db = AsyncMock()
            mock_db_class.return_value = mock_db
            
            cog = SyncDataCog(mock_bot)
            cog.db = mock_db
            
            # 模擬多個並發同步操作
            async def sync_operation(guild_id):
                mock_guild = Mock(spec=discord.Guild)
                mock_guild.id = guild_id
                mock_guild.name = f"測試伺服器{guild_id}"
                mock_guild.roles = []
                mock_guild.channels = []
                
                mock_db.get_guild_roles.return_value = []
                mock_db.get_guild_channels.return_value = []
                
                return await cog.sync_guild_data(mock_guild, "full")
            
            # 並發執行多個同步操作
            tasks = []
            for i in range(3):
                task = asyncio.create_task(sync_operation(12345 + i))
                tasks.append(task)
            
            # 等待所有操作完成
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 驗證所有操作都成功
            for result in results:
                if not isinstance(result, Exception):
                    assert result["success"] is True


class TestSyncDataErrorHandling:
    """測試資料同步系統錯誤處理"""
    
    @pytest.mark.asyncio
    async def test_sync_operation_failure(self):
        """測試同步操作失敗的處理"""
        mock_bot = Mock(spec=commands.Bot)
        
        with patch('cogs.sync_data.main.main.SyncDataDatabase') as mock_db_class:
            mock_db = AsyncMock()
            mock_db.get_guild_roles.side_effect = Exception("資料庫錯誤")
            mock_db_class.return_value = mock_db
            
            cog = SyncDataCog(mock_bot)
            cog.db = mock_db
            
            # 創建模擬伺服器
            mock_guild = Mock(spec=discord.Guild)
            mock_guild.id = 12345
            mock_guild.name = "測試伺服器"
            mock_guild.roles = []
            
            # 執行同步，應該處理錯誤
            result = await cog.sync_guild_data(mock_guild, "roles")
            
            # 驗證錯誤被正確處理
            assert result["success"] is False
            if "error_message" in result:
                assert "資料庫錯誤" in result["error_message"]
    
    @pytest.mark.asyncio
    async def test_database_connection_failure(self):
        """測試資料庫連接失敗的處理"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            mock_bot = Mock()
            db = SyncDataDatabase(mock_bot)
            db.db_path = "/invalid/path/test.db"  # 無效路徑
            
            # 嘗試初始化，應該拋出異常
            with pytest.raises(Exception):
                await db.init_db()
                
        finally:
            try:
                os.unlink(temp_path)
            except FileNotFoundError:
                pass 