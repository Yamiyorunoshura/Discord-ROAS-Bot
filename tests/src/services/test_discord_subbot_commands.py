"""
Discord 子機器人管理指令模組整合測試套件
Task ID: 3 - 子機器人聊天功能和管理系統開發

測試Discord指令模組與子機器人服務的整合：
- Slash commands 測試
- 權限驗證和用戶認證
- 互動式設定流程
- 指令回應和錯誤處理
- 管理介面操作
"""

import pytest
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, patch, AsyncMock, MagicMock

# 模擬Discord.py相關組件
class MockInteraction:
    """模擬Discord Interaction"""
    
    def __init__(self, user_id: int = 123456789, guild_id: int = 987654321, is_admin: bool = True):
        self.user = Mock()
        self.user.id = user_id
        self.guild_id = guild_id
        self.guild = Mock()
        self.guild.id = guild_id
        
        # 模擬權限
        self.user.guild_permissions = Mock()
        self.user.guild_permissions.administrator = is_admin
        self.user.guild_permissions.manage_guild = is_admin
        
        # 模擬回應方法
        self.response = Mock()
        self.response.send_message = AsyncMock()
        self.followup = Mock()
        self.followup.send = AsyncMock()
        
        self.responded = False
        self.is_expired = Mock(return_value=False)
    
    async def response_send_message(self, content=None, embed=None, view=None, ephemeral=False):
        """模擬發送回應訊息"""
        self.responded = True
        return Mock(id=999888777)


class MockSubBotManagementCog:
    """子機器人管理Cog的模擬實現"""
    
    def __init__(self, bot, subbot_service=None, channel_service=None):
        self.bot = bot
        self.subbot_service = subbot_service
        self.channel_service = channel_service
        self.setup_commands()
    
    def setup_commands(self):
        """設定指令"""
        # 這裡會設定Discord slash commands
        pass
    
    async def create_subbot_command(self, interaction: MockInteraction, name: str, token: str, channels: str):
        """創建子機器人指令"""
        try:
            # 權限檢查
            if not await self._check_admin_permission(interaction):
                await interaction.response.send_message(
                    "❌ 您需要管理員權限才能創建子機器人",
                    ephemeral=True
                )
                return
            
            # 驗證輸入
            if not name or not token:
                await interaction.response.send_message(
                    "❌ 名稱和Token都是必需的",
                    ephemeral=True
                )
                return
            
            # 解析頻道列表
            try:
                channel_ids = [int(ch.strip()) for ch in channels.split(',') if ch.strip()]
            except ValueError:
                await interaction.response.send_message(
                    "❌ 頻道ID格式無效，請使用逗號分隔的數字",
                    ephemeral=True
                )
                return
            
            if not channel_ids:
                await interaction.response.send_message(
                    "❌ 至少需要指定一個頻道",
                    ephemeral=True
                )
                return
            
            # 創建子機器人
            bot_id = await self.subbot_service.create_sub_bot(
                name=name,
                token=token,
                target_channels=channel_ids,
                ai_enabled=False,
                rate_limit=10
            )
            
            await interaction.response.send_message(
                f"✅ 子機器人 `{name}` 創建成功！\\nBot ID: `{bot_id}`",
                ephemeral=True
            )
            
            return bot_id
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ 創建子機器人時發生錯誤: {str(e)}",
                ephemeral=True
            )
            raise
    
    async def list_subbots_command(self, interaction: MockInteraction):
        """列出子機器人指令"""
        try:
            if not await self._check_admin_permission(interaction):
                await interaction.response.send_message(
                    "❌ 您需要管理員權限才能查看子機器人列表",
                    ephemeral=True
                )
                return
            
            bot_list = await self.subbot_service.list_sub_bots()
            
            if not bot_list:
                await interaction.response.send_message(
                    "📋 目前沒有註冊的子機器人",
                    ephemeral=True
                )
                return
            
            # 格式化列表
            message_lines = ["📋 **子機器人列表**\\n"]
            for i, bot in enumerate(bot_list, 1):
                status_emoji = "🟢" if bot.get('is_connected') else "🔴"
                message_lines.append(
                    f"{i}. {status_emoji} **{bot['name']}** "
                    f"(ID: `{bot['bot_id'][:16]}...`) - {bot['status']}"
                )
            
            message = "\\n".join(message_lines)
            
            await interaction.response.send_message(message, ephemeral=True)
            return bot_list
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ 獲取子機器人列表時發生錯誤: {str(e)}",
                ephemeral=True
            )
            raise
    
    async def start_subbot_command(self, interaction: MockInteraction, bot_id: str):
        """啟動子機器人指令"""
        try:
            if not await self._check_admin_permission(interaction):
                await interaction.response.send_message(
                    "❌ 您需要管理員權限才能啟動子機器人",
                    ephemeral=True
                )
                return
            
            # 先回應，因為啟動可能需要時間
            await interaction.response.send_message(
                f"⏳ 正在啟動子機器人 `{bot_id[:16]}...`",
                ephemeral=True
            )
            
            success = await self.subbot_service.start_sub_bot(bot_id)
            
            if success:
                await interaction.followup.send(
                    f"✅ 子機器人 `{bot_id[:16]}...` 啟動成功！",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"❌ 子機器人 `{bot_id[:16]}...` 啟動失敗",
                    ephemeral=True
                )
            
            return success
            
        except Exception as e:
            await interaction.followup.send(
                f"❌ 啟動子機器人時發生錯誤: {str(e)}",
                ephemeral=True
            )
            raise
    
    async def stop_subbot_command(self, interaction: MockInteraction, bot_id: str):
        """停止子機器人指令"""
        try:
            if not await self._check_admin_permission(interaction):
                await interaction.response.send_message(
                    "❌ 您需要管理員權限才能停止子機器人",
                    ephemeral=True
                )
                return
            
            success = await self.subbot_service.stop_sub_bot(bot_id)
            
            if success:
                await interaction.response.send_message(
                    f"✅ 子機器人 `{bot_id[:16]}...` 已停止",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"❌ 停止子機器人 `{bot_id[:16]}...` 失敗",
                    ephemeral=True
                )
            
            return success
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ 停止子機器人時發生錯誤: {str(e)}",
                ephemeral=True
            )
            raise
    
    async def delete_subbot_command(self, interaction: MockInteraction, bot_id: str, confirm: bool = False):
        """刪除子機器人指令"""
        try:
            if not await self._check_admin_permission(interaction):
                await interaction.response.send_message(
                    "❌ 您需要管理員權限才能刪除子機器人",
                    ephemeral=True
                )
                return
            
            if not confirm:
                await interaction.response.send_message(
                    f"⚠️ 確認要刪除子機器人 `{bot_id[:16]}...` 嗎？\\n"
                    "這個操作無法撤銷。請使用 `confirm=True` 參數確認刪除。",
                    ephemeral=True
                )
                return False
            
            success = await self.subbot_service.delete_sub_bot(bot_id)
            
            if success:
                await interaction.response.send_message(
                    f"✅ 子機器人 `{bot_id[:16]}...` 已刪除",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"❌ 刪除子機器人 `{bot_id[:16]}...` 失敗",
                    ephemeral=True
                )
            
            return success
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ 刪除子機器人時發生錯誤: {str(e)}",
                ephemeral=True
            )
            raise
    
    async def subbot_status_command(self, interaction: MockInteraction, bot_id: str):
        """查看子機器人狀態指令"""
        try:
            if not await self._check_admin_permission(interaction):
                await interaction.response.send_message(
                    "❌ 您需要管理員權限才能查看子機器人狀態",
                    ephemeral=True
                )
                return
            
            status = await self.subbot_service.get_bot_status(bot_id)
            
            # 格式化狀態資訊
            status_emoji = "🟢" if status.get('is_connected') else "🔴"
            message_lines = [
                f"📊 **子機器人狀態**\\n",
                f"**名稱:** {status.get('name', 'Unknown')}",
                f"**ID:** `{bot_id}`",
                f"**狀態:** {status_emoji} {status.get('status', 'Unknown')}",
                f"**連線:** {'是' if status.get('is_connected') else '否'}",
                f"**創建時間:** {status.get('created_at', 'Unknown')}",
                f"**訊息數量:** {status.get('message_count', 0)}"
            ]
            
            if status.get('ai_enabled'):
                message_lines.append(f"**AI模型:** {status.get('ai_model', 'Unknown')}")
            
            message = "\\n".join(message_lines)
            
            await interaction.response.send_message(message, ephemeral=True)
            return status
            
        except Exception as e:
            await interaction.response.send_message(
                f"❌ 獲取子機器人狀態時發生錯誤: {str(e)}",
                ephemeral=True
            )
            raise
    
    async def manage_channels_command(self, interaction: MockInteraction, bot_id: str, action: str, channels: str = None):
        """管理子機器人頻道指令"""
        try:
            if not await self._check_admin_permission(interaction):
                await interaction.response.send_message(
                    "❌ 您需要管理員權限才能管理子機器人頻道",
                    ephemeral=True
                )
                return
            
            if action == "list":
                # 列出當前頻道
                bot_channels = await self.channel_service.get_bot_channels(bot_id)
                
                if not bot_channels:
                    await interaction.response.send_message(
                        f"📋 子機器人 `{bot_id[:16]}...` 目前沒有分配任何頻道",
                        ephemeral=True
                    )
                    return bot_channels
                
                message_lines = [f"📋 **子機器人頻道列表**\\n"]
                for channel_info in bot_channels:
                    message_lines.append(f"• <#{channel_info['channel_id']}>")
                
                message = "\\n".join(message_lines)
                await interaction.response.send_message(message, ephemeral=True)
                return bot_channels
                
            elif action == "add":
                if not channels:
                    await interaction.response.send_message(
                        "❌ 請提供要添加的頻道ID列表",
                        ephemeral=True
                    )
                    return False
                
                try:
                    channel_ids = [int(ch.strip()) for ch in channels.split(',') if ch.strip()]
                except ValueError:
                    await interaction.response.send_message(
                        "❌ 頻道ID格式無效",
                        ephemeral=True
                    )
                    return False
                
                success = await self.channel_service.assign_channels(bot_id, channel_ids)
                
                if success:
                    await interaction.response.send_message(
                        f"✅ 已為子機器人 `{bot_id[:16]}...` 添加 {len(channel_ids)} 個頻道",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        f"❌ 添加頻道失敗",
                        ephemeral=True
                    )
                
                return success
                
            elif action == "remove":
                if not channels:
                    # 移除所有頻道
                    success = await self.channel_service.unassign_channels(bot_id)
                    message = "✅ 已移除子機器人的所有頻道分配" if success else "❌ 移除頻道分配失敗"
                else:
                    # 移除指定頻道
                    try:
                        channel_ids = [int(ch.strip()) for ch in channels.split(',') if ch.strip()]
                    except ValueError:
                        await interaction.response.send_message(
                            "❌ 頻道ID格式無效",
                            ephemeral=True
                        )
                        return False
                    
                    success = await self.channel_service.unassign_channels(bot_id, channel_ids)
                    message = f"✅ 已移除 {len(channel_ids)} 個頻道分配" if success else "❌ 移除頻道分配失敗"
                
                await interaction.response.send_message(message, ephemeral=True)
                return success
            
            else:
                await interaction.response.send_message(
                    "❌ 無效的操作。支援的操作：list, add, remove",
                    ephemeral=True
                )
                return False
                
        except Exception as e:
            await interaction.response.send_message(
                f"❌ 管理頻道時發生錯誤: {str(e)}",
                ephemeral=True
            )
            raise
    
    async def _check_admin_permission(self, interaction: MockInteraction) -> bool:
        """檢查管理員權限"""
        return interaction.user.guild_permissions.administrator or interaction.user.guild_permissions.manage_guild


@pytest.fixture
def mock_bot():
    """模擬Discord Bot"""
    bot = Mock()
    bot.user = Mock()
    bot.user.id = 111222333
    return bot


@pytest.fixture
def mock_subbot_service():
    """模擬子機器人服務"""
    service = AsyncMock()
    
    # 預設行為
    service.create_sub_bot.return_value = "subbot_20231201120000_abc123"
    service.list_sub_bots.return_value = [
        {
            'bot_id': 'subbot_20231201120000_abc123',
            'name': 'TestBot1',
            'status': 'offline',
            'is_connected': False,
            'created_at': '2023-12-01T12:00:00',
            'message_count': 0,
            'ai_enabled': False
        }
    ]
    service.start_sub_bot.return_value = True
    service.stop_sub_bot.return_value = True
    service.delete_sub_bot.return_value = True
    service.get_bot_status.return_value = {
        'bot_id': 'subbot_20231201120000_abc123',
        'name': 'TestBot1',
        'status': 'online',
        'is_connected': True,
        'created_at': '2023-12-01T12:00:00',
        'message_count': 42,
        'ai_enabled': False
    }
    
    return service


@pytest.fixture
def mock_channel_service():
    """模擬頻道管理服務"""
    service = AsyncMock()
    
    service.assign_channels.return_value = True
    service.unassign_channels.return_value = True
    service.get_bot_channels.return_value = [
        {
            'channel_id': 123456789,
            'assigned_at': datetime.now(),
            'permissions': {'send_messages': True, 'read_messages': True}
        }
    ]
    
    return service


@pytest.fixture
def subbot_cog(mock_bot, mock_subbot_service, mock_channel_service):
    """創建子機器人管理Cog實例"""
    return MockSubBotManagementCog(
        bot=mock_bot,
        subbot_service=mock_subbot_service,
        channel_service=mock_channel_service
    )


@pytest.fixture
def admin_interaction():
    """創建管理員互動"""
    return MockInteraction(user_id=123456789, guild_id=987654321, is_admin=True)


@pytest.fixture
def normal_user_interaction():
    """創建普通用戶互動"""
    return MockInteraction(user_id=555666777, guild_id=987654321, is_admin=False)


class TestCreateSubBotCommand:
    """創建子機器人指令測試"""
    
    @pytest.mark.asyncio
    async def test_create_subbot_success(self, subbot_cog, admin_interaction, mock_subbot_service):
        """測試成功創建子機器人"""
        bot_id = await subbot_cog.create_subbot_command(
            admin_interaction,
            name="TestBot",
            token="MTAxODcxNTI5MzE5NDA3OTQzNw.GXkHZA.test_token",
            channels="123456789,987654321"
        )
        
        assert bot_id == "subbot_20231201120000_abc123"
        admin_interaction.response.send_message.assert_called_once()
        
        # 檢查調用參數
        call_args = admin_interaction.response.send_message.call_args
        assert "✅" in call_args[0][0]
        assert "TestBot" in call_args[0][0]
        assert call_args[1]['ephemeral'] is True
        
        # 檢查服務調用
        mock_subbot_service.create_sub_bot.assert_called_once_with(
            name="TestBot",
            token="MTAxODcxNTI5MzE5NDA3OTQzNw.GXkHZA.test_token",
            target_channels=[123456789, 987654321],
            ai_enabled=False,
            rate_limit=10
        )
    
    @pytest.mark.asyncio
    async def test_create_subbot_no_permission(self, subbot_cog, normal_user_interaction):
        """測試無權限創建子機器人"""
        bot_id = await subbot_cog.create_subbot_command(
            normal_user_interaction,
            name="TestBot",
            token="test_token",
            channels="123456789"
        )
        
        assert bot_id is None
        normal_user_interaction.response.send_message.assert_called_once()
        
        call_args = normal_user_interaction.response.send_message.call_args
        assert "❌" in call_args[0][0]
        assert "管理員權限" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_create_subbot_empty_name(self, subbot_cog, admin_interaction):
        """測試空名稱創建子機器人"""
        bot_id = await subbot_cog.create_subbot_command(
            admin_interaction,
            name="",
            token="test_token",
            channels="123456789"
        )
        
        assert bot_id is None
        admin_interaction.response.send_message.assert_called_once()
        
        call_args = admin_interaction.response.send_message.call_args
        assert "❌" in call_args[0][0]
        assert "必需" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_create_subbot_invalid_channels(self, subbot_cog, admin_interaction):
        """測試無效頻道ID"""
        bot_id = await subbot_cog.create_subbot_command(
            admin_interaction,
            name="TestBot",
            token="test_token",
            channels="invalid,not_a_number"
        )
        
        assert bot_id is None
        admin_interaction.response.send_message.assert_called_once()
        
        call_args = admin_interaction.response.send_message.call_args
        assert "❌" in call_args[0][0]
        assert "格式無效" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_create_subbot_service_error(self, subbot_cog, admin_interaction, mock_subbot_service):
        """測試服務錯誤"""
        mock_subbot_service.create_sub_bot.side_effect = Exception("Service error")
        
        with pytest.raises(Exception, match="Service error"):
            await subbot_cog.create_subbot_command(
                admin_interaction,
                name="TestBot",
                token="test_token",
                channels="123456789"
            )
        
        admin_interaction.response.send_message.assert_called_once()
        call_args = admin_interaction.response.send_message.call_args
        assert "❌" in call_args[0][0]
        assert "Service error" in call_args[0][0]


class TestListSubBotsCommand:
    """列出子機器人指令測試"""
    
    @pytest.mark.asyncio
    async def test_list_subbots_success(self, subbot_cog, admin_interaction, mock_subbot_service):
        """測試成功列出子機器人"""
        bot_list = await subbot_cog.list_subbots_command(admin_interaction)
        
        assert len(bot_list) == 1
        assert bot_list[0]['name'] == 'TestBot1'
        
        admin_interaction.response.send_message.assert_called_once()
        call_args = admin_interaction.response.send_message.call_args
        assert "📋" in call_args[0][0]
        assert "TestBot1" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_list_subbots_empty(self, subbot_cog, admin_interaction, mock_subbot_service):
        """測試列出空的子機器人列表"""
        mock_subbot_service.list_sub_bots.return_value = []
        
        bot_list = await subbot_cog.list_subbots_command(admin_interaction)
        
        assert bot_list is None
        admin_interaction.response.send_message.assert_called_once()
        call_args = admin_interaction.response.send_message.call_args
        assert "沒有註冊" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_list_subbots_no_permission(self, subbot_cog, normal_user_interaction):
        """測試無權限列出子機器人"""
        bot_list = await subbot_cog.list_subbots_command(normal_user_interaction)
        
        assert bot_list is None
        normal_user_interaction.response.send_message.assert_called_once()
        call_args = normal_user_interaction.response.send_message.call_args
        assert "❌" in call_args[0][0]
        assert "管理員權限" in call_args[0][0]


class TestSubBotControlCommands:
    """子機器人控制指令測試"""
    
    @pytest.mark.asyncio
    async def test_start_subbot_success(self, subbot_cog, admin_interaction, mock_subbot_service):
        """測試成功啟動子機器人"""
        bot_id = "test_bot_id"
        
        success = await subbot_cog.start_subbot_command(admin_interaction, bot_id)
        
        assert success is True
        admin_interaction.response.send_message.assert_called_once()
        admin_interaction.followup.send.assert_called_once()
        
        # 檢查初始回應
        initial_call = admin_interaction.response.send_message.call_args
        assert "⏳" in initial_call[0][0]
        assert "正在啟動" in initial_call[0][0]
        
        # 檢查後續回應
        followup_call = admin_interaction.followup.send.call_args
        assert "✅" in followup_call[0][0]
        assert "啟動成功" in followup_call[0][0]
    
    @pytest.mark.asyncio
    async def test_start_subbot_failure(self, subbot_cog, admin_interaction, mock_subbot_service):
        """測試啟動子機器人失敗"""
        mock_subbot_service.start_sub_bot.return_value = False
        bot_id = "test_bot_id"
        
        success = await subbot_cog.start_subbot_command(admin_interaction, bot_id)
        
        assert success is False
        followup_call = admin_interaction.followup.send.call_args
        assert "❌" in followup_call[0][0]
        assert "啟動失敗" in followup_call[0][0]
    
    @pytest.mark.asyncio
    async def test_stop_subbot_success(self, subbot_cog, admin_interaction, mock_subbot_service):
        """測試成功停止子機器人"""
        bot_id = "test_bot_id"
        
        success = await subbot_cog.stop_subbot_command(admin_interaction, bot_id)
        
        assert success is True
        admin_interaction.response.send_message.assert_called_once()
        call_args = admin_interaction.response.send_message.call_args
        assert "✅" in call_args[0][0]
        assert "已停止" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_delete_subbot_without_confirm(self, subbot_cog, admin_interaction):
        """測試刪除子機器人但未確認"""
        bot_id = "test_bot_id"
        
        success = await subbot_cog.delete_subbot_command(admin_interaction, bot_id, confirm=False)
        
        assert success is False
        call_args = admin_interaction.response.send_message.call_args
        assert "⚠️" in call_args[0][0]
        assert "確認" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_delete_subbot_with_confirm(self, subbot_cog, admin_interaction, mock_subbot_service):
        """測試確認刪除子機器人"""
        bot_id = "test_bot_id"
        
        success = await subbot_cog.delete_subbot_command(admin_interaction, bot_id, confirm=True)
        
        assert success is True
        call_args = admin_interaction.response.send_message.call_args
        assert "✅" in call_args[0][0]
        assert "已刪除" in call_args[0][0]


class TestSubBotStatusCommand:
    """子機器人狀態指令測試"""
    
    @pytest.mark.asyncio
    async def test_get_subbot_status_success(self, subbot_cog, admin_interaction, mock_subbot_service):
        """測試成功獲取子機器人狀態"""
        bot_id = "test_bot_id"
        
        status = await subbot_cog.subbot_status_command(admin_interaction, bot_id)
        
        assert status is not None
        assert status['name'] == 'TestBot1'
        assert status['is_connected'] is True
        
        admin_interaction.response.send_message.assert_called_once()
        call_args = admin_interaction.response.send_message.call_args
        assert "📊" in call_args[0][0]
        assert "TestBot1" in call_args[0][0]
        assert "🟢" in call_args[0][0]  # 在線狀態
    
    @pytest.mark.asyncio
    async def test_get_subbot_status_not_found(self, subbot_cog, admin_interaction, mock_subbot_service):
        """測試獲取不存在子機器人的狀態"""
        mock_subbot_service.get_bot_status.side_effect = Exception("Bot not found")
        
        with pytest.raises(Exception, match="Bot not found"):
            await subbot_cog.subbot_status_command(admin_interaction, "nonexistent_bot")
        
        call_args = admin_interaction.response.send_message.call_args
        assert "❌" in call_args[0][0]
        assert "Bot not found" in call_args[0][0]


class TestChannelManagementCommands:
    """頻道管理指令測試"""
    
    @pytest.mark.asyncio
    async def test_list_channels(self, subbot_cog, admin_interaction, mock_channel_service):
        """測試列出子機器人頻道"""
        bot_id = "test_bot_id"
        
        channels = await subbot_cog.manage_channels_command(admin_interaction, bot_id, "list")
        
        assert len(channels) == 1
        assert channels[0]['channel_id'] == 123456789
        
        call_args = admin_interaction.response.send_message.call_args
        assert "📋" in call_args[0][0]
        assert "<#123456789>" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_add_channels(self, subbot_cog, admin_interaction, mock_channel_service):
        """測試添加頻道"""
        bot_id = "test_bot_id"
        
        success = await subbot_cog.manage_channels_command(
            admin_interaction, bot_id, "add", "123456789,987654321"
        )
        
        assert success is True
        call_args = admin_interaction.response.send_message.call_args
        assert "✅" in call_args[0][0]
        assert "添加" in call_args[0][0]
        
        # 檢查服務調用
        mock_channel_service.assign_channels.assert_called_once_with(
            bot_id, [123456789, 987654321]
        )
    
    @pytest.mark.asyncio
    async def test_remove_all_channels(self, subbot_cog, admin_interaction, mock_channel_service):
        """測試移除所有頻道"""
        bot_id = "test_bot_id"
        
        success = await subbot_cog.manage_channels_command(admin_interaction, bot_id, "remove")
        
        assert success is True
        call_args = admin_interaction.response.send_message.call_args
        assert "✅" in call_args[0][0]
        assert "所有頻道" in call_args[0][0]
        
        mock_channel_service.unassign_channels.assert_called_once_with(bot_id)
    
    @pytest.mark.asyncio
    async def test_remove_specific_channels(self, subbot_cog, admin_interaction, mock_channel_service):
        """測試移除特定頻道"""
        bot_id = "test_bot_id"
        
        success = await subbot_cog.manage_channels_command(
            admin_interaction, bot_id, "remove", "123456789"
        )
        
        assert success is True
        mock_channel_service.unassign_channels.assert_called_once_with(bot_id, [123456789])
    
    @pytest.mark.asyncio
    async def test_invalid_action(self, subbot_cog, admin_interaction):
        """測試無效操作"""
        bot_id = "test_bot_id"
        
        result = await subbot_cog.manage_channels_command(admin_interaction, bot_id, "invalid_action")
        
        assert result is False
        call_args = admin_interaction.response.send_message.call_args
        assert "❌" in call_args[0][0]
        assert "無效的操作" in call_args[0][0]


class TestPermissionValidation:
    """權限驗證測試"""
    
    @pytest.mark.asyncio
    async def test_admin_permission_check(self, subbot_cog):
        """測試管理員權限檢查"""
        admin_interaction = MockInteraction(is_admin=True)
        normal_interaction = MockInteraction(is_admin=False)
        
        # 管理員應該有權限
        assert await subbot_cog._check_admin_permission(admin_interaction) is True
        
        # 普通用戶應該沒有權限
        assert await subbot_cog._check_admin_permission(normal_interaction) is False
    
    @pytest.mark.asyncio
    async def test_permission_check_with_manage_guild(self, subbot_cog):
        """測試具有manage_guild權限的用戶"""
        interaction = MockInteraction(is_admin=False)
        interaction.user.guild_permissions.manage_guild = True
        
        assert await subbot_cog._check_admin_permission(interaction) is True


class TestErrorHandling:
    """錯誤處理測試"""
    
    @pytest.mark.asyncio
    async def test_service_exception_handling(self, subbot_cog, admin_interaction, mock_subbot_service):
        """測試服務異常處理"""
        mock_subbot_service.list_sub_bots.side_effect = Exception("Database connection failed")
        
        with pytest.raises(Exception, match="Database connection failed"):
            await subbot_cog.list_subbots_command(admin_interaction)
        
        # 檢查錯誤訊息已發送
        call_args = admin_interaction.response.send_message.call_args
        assert "❌" in call_args[0][0]
        assert "Database connection failed" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_invalid_input_handling(self, subbot_cog, admin_interaction):
        """測試無效輸入處理"""
        # 測試無效頻道ID格式
        bot_id = await subbot_cog.create_subbot_command(
            admin_interaction,
            name="TestBot",
            token="test_token",
            channels="not_a_number,another_invalid"
        )
        
        assert bot_id is None
        call_args = admin_interaction.response.send_message.call_args
        assert "❌" in call_args[0][0]
        assert "格式無效" in call_args[0][0]


class TestInteractionFlow:
    """互動流程測試"""
    
    @pytest.mark.asyncio
    async def test_complete_subbot_lifecycle(self, subbot_cog, admin_interaction, mock_subbot_service, mock_channel_service):
        """測試完整的子機器人生命週期"""
        # 1. 創建子機器人
        bot_id = await subbot_cog.create_subbot_command(
            admin_interaction,
            name="LifecycleBot",
            token="test_token",
            channels="123456789"
        )
        
        assert bot_id is not None
        
        # 2. 列出子機器人
        admin_interaction.response.send_message.reset_mock()
        bot_list = await subbot_cog.list_subbots_command(admin_interaction)
        assert len(bot_list) == 1
        
        # 3. 啟動子機器人
        admin_interaction.response.send_message.reset_mock()
        admin_interaction.followup.send.reset_mock()
        success = await subbot_cog.start_subbot_command(admin_interaction, bot_id)
        assert success is True
        
        # 4. 檢查狀態
        admin_interaction.response.send_message.reset_mock()
        status = await subbot_cog.subbot_status_command(admin_interaction, bot_id)
        assert status is not None
        
        # 5. 停止子機器人
        admin_interaction.response.send_message.reset_mock()
        success = await subbot_cog.stop_subbot_command(admin_interaction, bot_id)
        assert success is True
        
        # 6. 刪除子機器人
        admin_interaction.response.send_message.reset_mock()
        success = await subbot_cog.delete_subbot_command(admin_interaction, bot_id, confirm=True)
        assert success is True


if __name__ == "__main__":
    # 運行測試時的配置
    pytest.main([
        __file__,
        "-v",  # 詳細輸出
        "--tb=short",  # 簡短的錯誤追蹤
        "-x",  # 遇到第一個失敗就停止
    ])