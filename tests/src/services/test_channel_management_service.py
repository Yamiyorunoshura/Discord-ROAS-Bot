"""
子機器人頻道管理服務測試套件
Task ID: 3 - 子機器人聊天功能和管理系統開發

測試子機器人與頻道的關聯和權限管理：
- 頻道分配和權限設定
- 頻道衝突檢測和解決
- 權限驗證和控制
- 頻道路由和訊息轉發
- 多頻道管理和協調
"""

import pytest
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, patch, AsyncMock, MagicMock

from src.core.errors import SubBotChannelError, SubBotError, PermissionError


# 模擬實現 ChannelManagementService
class MockChannelManagementService:
    """頻道管理服務的模擬實現"""
    
    def __init__(self, database_manager=None):
        self.database_manager = database_manager
        self.channel_assignments: Dict[str, Dict[str, Any]] = {}  # bot_id -> channel config
        self.channel_conflicts: Dict[int, List[str]] = {}  # channel_id -> [bot_ids]
        self.permission_cache: Dict[str, Dict[int, Dict[str, bool]]] = {}  # bot_id -> channel_id -> permissions
        
    async def assign_channels(self, bot_id: str, channels: List[int]) -> bool:
        """分配頻道給子機器人"""
        if not bot_id or not channels:
            raise SubBotChannelError(
                bot_id=bot_id, 
                channel_id=None, 
                operation="assign", 
                reason="bot_id 和 channels 不能為空"
            )
        
        # 檢查頻道衝突
        conflicts = await self._check_channel_conflicts(channels, bot_id)
        if conflicts:
            conflict_channels = [str(ch) for ch in conflicts]
            raise SubBotChannelError(
                bot_id=bot_id,
                channel_id=",".join(conflict_channels),
                operation="assign",
                reason=f"頻道衝突: {conflict_channels}"
            )
        
        # 記錄頻道分配
        self.channel_assignments[bot_id] = {
            'channels': channels,
            'assigned_at': datetime.now(),
            'permissions': self._get_default_permissions()
        }
        
        # 更新衝突映射
        for channel_id in channels:
            if channel_id not in self.channel_conflicts:
                self.channel_conflicts[channel_id] = []
            if bot_id not in self.channel_conflicts[channel_id]:
                self.channel_conflicts[channel_id].append(bot_id)
        
        # 更新權限快取
        await self._update_permission_cache(bot_id, channels)
        
        return True
    
    async def unassign_channels(self, bot_id: str, channels: Optional[List[int]] = None) -> bool:
        """取消子機器人的頻道分配"""
        if bot_id not in self.channel_assignments:
            return False
        
        assigned_channels = self.channel_assignments[bot_id]['channels']
        
        if channels is None:
            # 取消所有頻道分配
            channels_to_remove = assigned_channels.copy()
        else:
            # 只取消指定頻道
            channels_to_remove = [ch for ch in channels if ch in assigned_channels]
        
        # 更新頻道分配
        remaining_channels = [ch for ch in assigned_channels if ch not in channels_to_remove]
        
        if remaining_channels:
            self.channel_assignments[bot_id]['channels'] = remaining_channels
        else:
            del self.channel_assignments[bot_id]
        
        # 更新衝突映射
        for channel_id in channels_to_remove:
            if channel_id in self.channel_conflicts:
                if bot_id in self.channel_conflicts[channel_id]:
                    self.channel_conflicts[channel_id].remove(bot_id)
                if not self.channel_conflicts[channel_id]:
                    del self.channel_conflicts[channel_id]
        
        # 清理權限快取
        if bot_id in self.permission_cache:
            for channel_id in channels_to_remove:
                if channel_id in self.permission_cache[bot_id]:
                    del self.permission_cache[bot_id][channel_id]
            
            if not self.permission_cache[bot_id]:
                del self.permission_cache[bot_id]
        
        return True
    
    async def check_channel_permissions(self, bot_id: str, channel_id: int) -> bool:
        """檢查子機器人對指定頻道的權限"""
        if bot_id not in self.channel_assignments:
            return False
        
        assigned_channels = self.channel_assignments[bot_id]['channels']
        if channel_id not in assigned_channels:
            return False
        
        # 從快取或計算權限
        if bot_id in self.permission_cache and channel_id in self.permission_cache[bot_id]:
            permissions = self.permission_cache[bot_id][channel_id]
            return permissions.get('send_messages', False)
        
        return True  # 預設允許
    
    async def get_bot_channels(self, bot_id: str) -> List[Dict[str, Any]]:
        """獲取子機器人分配的頻道列表"""
        if bot_id not in self.channel_assignments:
            return []
        
        assignment = self.channel_assignments[bot_id]
        channels = []
        
        for channel_id in assignment['channels']:
            permissions = await self._get_channel_permissions(bot_id, channel_id)
            channels.append({
                'channel_id': channel_id,
                'assigned_at': assignment['assigned_at'],
                'permissions': permissions
            })
        
        return channels
    
    async def get_channel_bots(self, channel_id: int) -> List[str]:
        """獲取分配到指定頻道的所有子機器人"""
        return self.channel_conflicts.get(channel_id, [])
    
    async def resolve_channel_conflicts(self) -> Dict[int, List[str]]:
        """解決頻道衝突"""
        conflicts = {}
        
        for channel_id, bot_ids in self.channel_conflicts.items():
            if len(bot_ids) > 1:
                # 有衝突，保留最早分配的bot
                earliest_bot = None
                earliest_time = None
                
                for bot_id in bot_ids:
                    if bot_id in self.channel_assignments:
                        assigned_at = self.channel_assignments[bot_id]['assigned_at']
                        if earliest_time is None or assigned_at < earliest_time:
                            earliest_time = assigned_at
                            earliest_bot = bot_id
                
                if earliest_bot:
                    # 移除其他bot的此頻道分配
                    conflicting_bots = [bid for bid in bot_ids if bid != earliest_bot]
                    for bot_id in conflicting_bots:
                        await self.unassign_channels(bot_id, [channel_id])
                    
                    conflicts[channel_id] = conflicting_bots
        
        return conflicts
    
    async def validate_channel_access(self, bot_id: str, channel_id: int, operation: str) -> bool:
        """驗證子機器人對頻道的特定操作權限"""
        # 首先檢查基本權限
        if not await self.check_channel_permissions(bot_id, channel_id):
            return False
        
        # 檢查特定操作權限
        if bot_id in self.permission_cache and channel_id in self.permission_cache[bot_id]:
            permissions = self.permission_cache[bot_id][channel_id]
            return permissions.get(operation, False)
        
        # 預設權限
        default_permissions = self._get_default_permissions()
        return default_permissions.get(operation, False)
    
    async def update_channel_permissions(
        self, 
        bot_id: str, 
        channel_id: int, 
        permissions: Dict[str, bool]
    ) -> bool:
        """更新子機器人對指定頻道的權限"""
        if bot_id not in self.channel_assignments:
            raise SubBotChannelError(
                bot_id=bot_id,
                channel_id=str(channel_id),
                operation="update_permissions",
                reason="子機器人未分配到任何頻道"
            )
        
        assigned_channels = self.channel_assignments[bot_id]['channels']
        if channel_id not in assigned_channels:
            raise SubBotChannelError(
                bot_id=bot_id,
                channel_id=str(channel_id),
                operation="update_permissions",
                reason="子機器人未分配到此頻道"
            )
        
        # 更新權限快取
        if bot_id not in self.permission_cache:
            self.permission_cache[bot_id] = {}
        
        if channel_id not in self.permission_cache[bot_id]:
            self.permission_cache[bot_id][channel_id] = self._get_default_permissions()
        
        self.permission_cache[bot_id][channel_id].update(permissions)
        
        # 保存到資料庫（模擬）
        if self.database_manager:
            await self._save_permissions_to_db(bot_id, channel_id, permissions)
        
        return True
    
    def get_service_stats(self) -> Dict[str, Any]:
        """獲取服務統計資訊"""
        total_assignments = len(self.channel_assignments)
        total_channels = len(self.channel_conflicts)
        total_conflicts = sum(1 for bots in self.channel_conflicts.values() if len(bots) > 1)
        
        return {
            'total_bot_assignments': total_assignments,
            'total_channels': total_channels,
            'total_conflicts': total_conflicts,
            'assignment_details': {
                bot_id: {
                    'channel_count': len(config['channels']),
                    'assigned_at': config['assigned_at']
                }
                for bot_id, config in self.channel_assignments.items()
            }
        }
    
    # 私有方法
    
    async def _check_channel_conflicts(self, channels: List[int], exclude_bot_id: str = None) -> List[int]:
        """檢查頻道衝突"""
        conflicts = []
        
        for channel_id in channels:
            if channel_id in self.channel_conflicts:
                existing_bots = self.channel_conflicts[channel_id]
                if exclude_bot_id:
                    existing_bots = [bid for bid in existing_bots if bid != exclude_bot_id]
                
                if existing_bots:
                    conflicts.append(channel_id)
        
        return conflicts
    
    def _get_default_permissions(self) -> Dict[str, bool]:
        """獲取預設權限設定"""
        return {
            'send_messages': True,
            'read_messages': True,
            'embed_links': True,
            'attach_files': False,
            'mention_everyone': False,
            'manage_messages': False
        }
    
    async def _update_permission_cache(self, bot_id: str, channels: List[int]):
        """更新權限快取"""
        if bot_id not in self.permission_cache:
            self.permission_cache[bot_id] = {}
        
        default_permissions = self._get_default_permissions()
        for channel_id in channels:
            if channel_id not in self.permission_cache[bot_id]:
                self.permission_cache[bot_id][channel_id] = default_permissions.copy()
    
    async def _get_channel_permissions(self, bot_id: str, channel_id: int) -> Dict[str, bool]:
        """獲取頻道權限"""
        if (bot_id in self.permission_cache and 
            channel_id in self.permission_cache[bot_id]):
            return self.permission_cache[bot_id][channel_id].copy()
        
        return self._get_default_permissions()
    
    async def _save_permissions_to_db(self, bot_id: str, channel_id: int, permissions: Dict[str, bool]):
        """保存權限到資料庫（模擬）"""
        if self.database_manager:
            # 模擬資料庫保存操作
            pass


@pytest.fixture
def mock_database_manager():
    """模擬資料庫管理器"""
    db_manager = AsyncMock()
    db_manager.fetchall.return_value = []
    db_manager.fetchone.return_value = None
    db_manager.execute.return_value = None
    return db_manager


@pytest.fixture
async def channel_service(mock_database_manager):
    """創建頻道管理服務實例"""
    service = MockChannelManagementService(database_manager=mock_database_manager)
    yield service


@pytest.fixture
def sample_channels():
    """提供測試用的頻道ID列表"""
    return [123456789, 987654321, 555666777, 111222333]


@pytest.fixture
def sample_bot_ids():
    """提供測試用的子機器人ID列表"""
    return ['bot_1', 'bot_2', 'bot_3']


class TestChannelAssignment:
    """頻道分配功能測試"""
    
    @pytest.mark.asyncio
    async def test_assign_single_channel(self, channel_service, sample_channels):
        """測試分配單個頻道"""
        bot_id = 'test_bot_1'
        channels = [sample_channels[0]]
        
        result = await channel_service.assign_channels(bot_id, channels)
        
        assert result is True
        assert bot_id in channel_service.channel_assignments
        assert channel_service.channel_assignments[bot_id]['channels'] == channels
        assert sample_channels[0] in channel_service.channel_conflicts
        assert bot_id in channel_service.channel_conflicts[sample_channels[0]]
    
    @pytest.mark.asyncio
    async def test_assign_multiple_channels(self, channel_service, sample_channels):
        """測試分配多個頻道"""
        bot_id = 'test_bot_1'
        channels = sample_channels[:3]
        
        result = await channel_service.assign_channels(bot_id, channels)
        
        assert result is True
        assert channel_service.channel_assignments[bot_id]['channels'] == channels
        
        # 檢查所有頻道都被正確記錄
        for channel_id in channels:
            assert channel_id in channel_service.channel_conflicts
            assert bot_id in channel_service.channel_conflicts[channel_id]
    
    @pytest.mark.asyncio
    async def test_assign_empty_channels_list(self, channel_service):
        """測試分配空的頻道列表"""
        bot_id = 'test_bot_1'
        
        with pytest.raises(SubBotChannelError, match="bot_id 和 channels 不能為空"):
            await channel_service.assign_channels(bot_id, [])
    
    @pytest.mark.asyncio
    async def test_assign_with_empty_bot_id(self, channel_service, sample_channels):
        """測試使用空的bot_id分配頻道"""
        with pytest.raises(SubBotChannelError, match="bot_id 和 channels 不能為空"):
            await channel_service.assign_channels("", sample_channels[:1])
    
    @pytest.mark.asyncio
    async def test_assign_conflicting_channels(self, channel_service, sample_channels):
        """測試分配衝突的頻道"""
        bot_id_1 = 'test_bot_1'
        bot_id_2 = 'test_bot_2'
        channel = sample_channels[0]
        
        # 第一個bot成功分配
        await channel_service.assign_channels(bot_id_1, [channel])
        
        # 第二個bot嘗試分配相同頻道應該失敗
        with pytest.raises(SubBotChannelError, match="頻道衝突"):
            await channel_service.assign_channels(bot_id_2, [channel])
    
    @pytest.mark.asyncio
    async def test_reassign_channels_to_same_bot(self, channel_service, sample_channels):
        """測試重新分配頻道給同一個bot"""
        bot_id = 'test_bot_1'
        
        # 首次分配
        await channel_service.assign_channels(bot_id, [sample_channels[0]])
        
        # 重新分配更多頻道
        new_channels = sample_channels[:2]
        result = await channel_service.assign_channels(bot_id, new_channels)
        
        assert result is True
        assert channel_service.channel_assignments[bot_id]['channels'] == new_channels


class TestChannelUnassignment:
    """頻道取消分配功能測試"""
    
    @pytest.mark.asyncio
    async def test_unassign_specific_channels(self, channel_service, sample_channels):
        """測試取消分配特定頻道"""
        bot_id = 'test_bot_1'
        assigned_channels = sample_channels[:3]
        channels_to_remove = [sample_channels[0], sample_channels[2]]
        
        # 首先分配頻道
        await channel_service.assign_channels(bot_id, assigned_channels)
        
        # 取消分配特定頻道
        result = await channel_service.unassign_channels(bot_id, channels_to_remove)
        
        assert result is True
        remaining_channels = channel_service.channel_assignments[bot_id]['channels']
        expected_remaining = [sample_channels[1]]
        assert remaining_channels == expected_remaining
        
        # 檢查衝突映射已更新
        for channel_id in channels_to_remove:
            assert bot_id not in channel_service.channel_conflicts.get(channel_id, [])
    
    @pytest.mark.asyncio
    async def test_unassign_all_channels(self, channel_service, sample_channels):
        """測試取消分配所有頻道"""
        bot_id = 'test_bot_1'
        assigned_channels = sample_channels[:3]
        
        # 首先分配頻道
        await channel_service.assign_channels(bot_id, assigned_channels)
        
        # 取消分配所有頻道
        result = await channel_service.unassign_channels(bot_id)
        
        assert result is True
        assert bot_id not in channel_service.channel_assignments
        
        # 檢查衝突映射已清理
        for channel_id in assigned_channels:
            assert bot_id not in channel_service.channel_conflicts.get(channel_id, [])
    
    @pytest.mark.asyncio
    async def test_unassign_nonexistent_bot(self, channel_service):
        """測試取消分配不存在的bot"""
        result = await channel_service.unassign_channels('nonexistent_bot')
        assert result is False
    
    @pytest.mark.asyncio
    async def test_unassign_non_assigned_channels(self, channel_service, sample_channels):
        """測試取消分配未分配的頻道"""
        bot_id = 'test_bot_1'
        
        # 分配部分頻道
        await channel_service.assign_channels(bot_id, [sample_channels[0]])
        
        # 嘗試取消分配未分配的頻道
        result = await channel_service.unassign_channels(bot_id, [sample_channels[1]])
        
        assert result is True  # 應該成功，但不會有實際變化
        assert channel_service.channel_assignments[bot_id]['channels'] == [sample_channels[0]]


class TestPermissionManagement:
    """權限管理功能測試"""
    
    @pytest.mark.asyncio
    async def test_check_basic_channel_permissions(self, channel_service, sample_channels):
        """測試檢查基本頻道權限"""
        bot_id = 'test_bot_1'
        channel_id = sample_channels[0]
        
        # 分配頻道
        await channel_service.assign_channels(bot_id, [channel_id])
        
        # 檢查權限
        has_permission = await channel_service.check_channel_permissions(bot_id, channel_id)
        assert has_permission is True
    
    @pytest.mark.asyncio
    async def test_check_permissions_for_unassigned_channel(self, channel_service, sample_channels):
        """測試檢查未分配頻道的權限"""
        bot_id = 'test_bot_1'
        channel_id = sample_channels[0]
        
        has_permission = await channel_service.check_channel_permissions(bot_id, channel_id)
        assert has_permission is False
    
    @pytest.mark.asyncio
    async def test_validate_specific_operation_access(self, channel_service, sample_channels):
        """測試驗證特定操作權限"""
        bot_id = 'test_bot_1'
        channel_id = sample_channels[0]
        
        # 分配頻道
        await channel_service.assign_channels(bot_id, [channel_id])
        
        # 測試不同操作的權限
        operations = ['send_messages', 'read_messages', 'embed_links', 'manage_messages']
        
        for operation in operations:
            has_access = await channel_service.validate_channel_access(bot_id, channel_id, operation)
            # 根據預設權限，前三個應該為True，manage_messages應該為False
            if operation in ['send_messages', 'read_messages', 'embed_links']:
                assert has_access is True
            elif operation == 'manage_messages':
                assert has_access is False
    
    @pytest.mark.asyncio
    async def test_update_channel_permissions(self, channel_service, sample_channels):
        """測試更新頻道權限"""
        bot_id = 'test_bot_1'
        channel_id = sample_channels[0]
        
        # 分配頻道
        await channel_service.assign_channels(bot_id, [channel_id])
        
        # 更新權限
        new_permissions = {
            'manage_messages': True,
            'mention_everyone': True,
            'attach_files': False
        }
        
        result = await channel_service.update_channel_permissions(bot_id, channel_id, new_permissions)
        assert result is True
        
        # 驗證權限已更新
        can_manage = await channel_service.validate_channel_access(bot_id, channel_id, 'manage_messages')
        can_mention = await channel_service.validate_channel_access(bot_id, channel_id, 'mention_everyone')
        can_attach = await channel_service.validate_channel_access(bot_id, channel_id, 'attach_files')
        
        assert can_manage is True
        assert can_mention is True
        assert can_attach is False
    
    @pytest.mark.asyncio
    async def test_update_permissions_for_unassigned_bot(self, channel_service, sample_channels):
        """測試為未分配的bot更新權限"""
        bot_id = 'unassigned_bot'
        channel_id = sample_channels[0]
        
        with pytest.raises(SubBotChannelError, match="子機器人未分配到任何頻道"):
            await channel_service.update_channel_permissions(bot_id, channel_id, {'send_messages': False})
    
    @pytest.mark.asyncio
    async def test_update_permissions_for_unassigned_channel(self, channel_service, sample_channels):
        """測試為未分配的頻道更新權限"""
        bot_id = 'test_bot_1'
        assigned_channel = sample_channels[0]
        unassigned_channel = sample_channels[1]
        
        # 只分配一個頻道
        await channel_service.assign_channels(bot_id, [assigned_channel])
        
        # 嘗試更新未分配頻道的權限
        with pytest.raises(SubBotChannelError, match="子機器人未分配到此頻道"):
            await channel_service.update_channel_permissions(bot_id, unassigned_channel, {'send_messages': False})


class TestChannelConflictResolution:
    """頻道衝突解決測試"""
    
    @pytest.mark.asyncio
    async def test_detect_channel_conflicts(self, channel_service, sample_channels, sample_bot_ids):
        """測試檢測頻道衝突"""
        channel_id = sample_channels[0]
        
        # 手動創建衝突情況（繞過正常的衝突檢查）
        for bot_id in sample_bot_ids[:2]:
            channel_service.channel_assignments[bot_id] = {
                'channels': [channel_id],
                'assigned_at': datetime.now(),
                'permissions': channel_service._get_default_permissions()
            }
            
            if channel_id not in channel_service.channel_conflicts:
                channel_service.channel_conflicts[channel_id] = []
            channel_service.channel_conflicts[channel_id].append(bot_id)
        
        # 檢查衝突
        bots_in_channel = await channel_service.get_channel_bots(channel_id)
        assert len(bots_in_channel) == 2
        assert sample_bot_ids[0] in bots_in_channel
        assert sample_bot_ids[1] in bots_in_channel
    
    @pytest.mark.asyncio
    async def test_resolve_channel_conflicts(self, channel_service, sample_channels, sample_bot_ids):
        """測試解決頻道衝突"""
        channel_id = sample_channels[0]
        
        # 手動創建衝突情況，設置不同的分配時間
        import time
        base_time = datetime.now()
        
        for i, bot_id in enumerate(sample_bot_ids[:2]):
            channel_service.channel_assignments[bot_id] = {
                'channels': [channel_id],
                'assigned_at': base_time + (i * 1000),  # 確保時間不同
                'permissions': channel_service._get_default_permissions()
            }
            
            if channel_id not in channel_service.channel_conflicts:
                channel_service.channel_conflicts[channel_id] = []
            channel_service.channel_conflicts[channel_id].append(bot_id)
        
        # 解決衝突
        conflicts = await channel_service.resolve_channel_conflicts()
        
        # 檢查衝突解決結果
        assert channel_id in conflicts
        assert len(conflicts[channel_id]) == 1  # 應該移除一個bot
        
        # 檢查最早的bot仍然分配到頻道
        remaining_bots = await channel_service.get_channel_bots(channel_id)
        assert len(remaining_bots) == 1
        assert remaining_bots[0] == sample_bot_ids[0]  # 最早分配的bot
    
    @pytest.mark.asyncio
    async def test_no_conflicts_to_resolve(self, channel_service, sample_channels, sample_bot_ids):
        """測試沒有衝突需要解決的情況"""
        # 分配不同頻道給不同bot
        for i, bot_id in enumerate(sample_bot_ids[:2]):
            await channel_service.assign_channels(bot_id, [sample_channels[i]])
        
        # 嘗試解決衝突
        conflicts = await channel_service.resolve_channel_conflicts()
        
        assert len(conflicts) == 0


class TestChannelQueryOperations:
    """頻道查詢操作測試"""
    
    @pytest.mark.asyncio
    async def test_get_bot_channels(self, channel_service, sample_channels):
        """測試獲取bot的頻道列表"""
        bot_id = 'test_bot_1'
        assigned_channels = sample_channels[:2]
        
        # 分配頻道
        await channel_service.assign_channels(bot_id, assigned_channels)
        
        # 獲取bot的頻道
        channels = await channel_service.get_bot_channels(bot_id)
        
        assert len(channels) == 2
        
        for i, channel_info in enumerate(channels):
            assert channel_info['channel_id'] == assigned_channels[i]
            assert 'assigned_at' in channel_info
            assert 'permissions' in channel_info
            assert isinstance(channel_info['permissions'], dict)
    
    @pytest.mark.asyncio
    async def test_get_bot_channels_for_unassigned_bot(self, channel_service):
        """測試獲取未分配bot的頻道列表"""
        channels = await channel_service.get_bot_channels('unassigned_bot')
        assert channels == []
    
    @pytest.mark.asyncio
    async def test_get_channel_bots(self, channel_service, sample_channels, sample_bot_ids):
        """測試獲取頻道分配的bot列表"""
        channel_id = sample_channels[0]
        
        # 分配多個bot到同一頻道（手動創建，繞過衝突檢查）
        for bot_id in sample_bot_ids[:2]:
            channel_service.channel_assignments[bot_id] = {
                'channels': [channel_id],
                'assigned_at': datetime.now(),
                'permissions': channel_service._get_default_permissions()
            }
            
            if channel_id not in channel_service.channel_conflicts:
                channel_service.channel_conflicts[channel_id] = []
            channel_service.channel_conflicts[channel_id].append(bot_id)
        
        # 獲取頻道的bot列表
        bots = await channel_service.get_channel_bots(channel_id)
        
        assert len(bots) == 2
        assert sample_bot_ids[0] in bots
        assert sample_bot_ids[1] in bots
    
    @pytest.mark.asyncio
    async def test_get_channel_bots_for_empty_channel(self, channel_service, sample_channels):
        """測試獲取空頻道的bot列表"""
        bots = await channel_service.get_channel_bots(sample_channels[0])
        assert bots == []


class TestServiceStatistics:
    """服務統計功能測試"""
    
    @pytest.mark.asyncio
    async def test_get_service_stats_empty(self, channel_service):
        """測試獲取空服務的統計資訊"""
        stats = channel_service.get_service_stats()
        
        assert stats['total_bot_assignments'] == 0
        assert stats['total_channels'] == 0
        assert stats['total_conflicts'] == 0
        assert stats['assignment_details'] == {}
    
    @pytest.mark.asyncio
    async def test_get_service_stats_with_assignments(self, channel_service, sample_channels, sample_bot_ids):
        """測試獲取有分配的服務統計資訊"""
        # 分配一些頻道
        await channel_service.assign_channels(sample_bot_ids[0], sample_channels[:2])
        await channel_service.assign_channels(sample_bot_ids[1], [sample_channels[2]])
        
        stats = channel_service.get_service_stats()
        
        assert stats['total_bot_assignments'] == 2
        assert stats['total_channels'] == 3
        assert stats['total_conflicts'] == 0
        
        # 檢查詳細資訊
        details = stats['assignment_details']
        assert len(details) == 2
        assert details[sample_bot_ids[0]]['channel_count'] == 2
        assert details[sample_bot_ids[1]]['channel_count'] == 1


class TestConcurrencyAndEdgeCases:
    """並發和邊界條件測試"""
    
    @pytest.mark.asyncio
    async def test_concurrent_channel_assignments(self, channel_service, sample_channels):
        """測試並發頻道分配"""
        async def assign_channels_to_bot(bot_id, channels):
            try:
                return await channel_service.assign_channels(bot_id, channels)
            except SubBotChannelError:
                return False
        
        # 並發分配不同頻道
        tasks = []
        for i in range(3):
            bot_id = f'concurrent_bot_{i}'
            channels = [sample_channels[i]]
            tasks.append(assign_channels_to_bot(bot_id, channels))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 所有分配都應該成功
        successful_assignments = [r for r in results if r is True]
        assert len(successful_assignments) == 3
    
    @pytest.mark.asyncio
    async def test_concurrent_conflicting_assignments(self, channel_service, sample_channels):
        """測試並發衝突分配"""
        channel_id = sample_channels[0]
        
        async def assign_channel_to_bot(bot_id):
            try:
                return await channel_service.assign_channels(bot_id, [channel_id])
            except SubBotChannelError:
                return False
        
        # 並發分配相同頻道到不同bot
        tasks = []
        for i in range(3):
            bot_id = f'conflict_bot_{i}'
            tasks.append(assign_channel_to_bot(bot_id))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 只有一個應該成功，其他應該失敗
        successful_assignments = [r for r in results if r is True]
        failed_assignments = [r for r in results if r is False]
        
        assert len(successful_assignments) == 1
        assert len(failed_assignments) >= 1
    
    @pytest.mark.asyncio
    async def test_permission_updates_during_assignments(self, channel_service, sample_channels):
        """測試在分配過程中更新權限"""
        bot_id = 'test_bot_1'
        channel_id = sample_channels[0]
        
        # 分配頻道
        await channel_service.assign_channels(bot_id, [channel_id])
        
        # 並發更新權限
        async def update_permissions(permissions):
            try:
                return await channel_service.update_channel_permissions(bot_id, channel_id, permissions)
            except Exception as e:
                return False
        
        permission_updates = [
            {'send_messages': False},
            {'read_messages': True},
            {'manage_messages': True},
            {'attach_files': True}
        ]
        
        tasks = [update_permissions(perms) for perms in permission_updates]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 所有權限更新都應該成功
        successful_updates = [r for r in results if r is True]
        assert len(successful_updates) == 4


if __name__ == "__main__":
    # 運行測試時的配置
    pytest.main([
        __file__,
        "-v",  # 詳細輸出
        "--tb=short",  # 簡短的錯誤追蹤
        "-x",  # 遇到第一個失敗就停止
    ])