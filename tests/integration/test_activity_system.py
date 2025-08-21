"""
活躍度系統整合測試
Task ID: 9 - 重構現有模組以符合新架構

測試活躍度系統的完整運行流程，包括：
- 服務和面板的初始化
- 活躍度更新和計算
- 排行榜生成
- 成就系統整合
- 自動播報功能
"""

import pytest
import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

# 假設我們有一個測試用的 Discord 模擬器
import discord
from discord.ext import commands

from services.activity import ActivityService
from services.activity.models import ActivitySettings, ActivityRecord, LeaderboardEntry
from panels.activity import ActivityPanel
from core.database_manager import DatabaseManager
from core.exceptions import ServiceError
from test_utils.discord_mocks import MockMember, MockGuild, MockTextChannel, MockMessage, MockInteraction


@pytest.fixture
async def db_manager():
    """創建測試用資料庫管理器"""
    db_manager = DatabaseManager()
    await db_manager.initialize()
    return db_manager


@pytest.fixture
async def activity_service(db_manager):
    """創建測試用活躍度服務"""
    config = {
        'fonts_dir': 'fonts',
        'default_font': 'fonts/NotoSansCJKtc-Regular.otf'
    }
    service = ActivityService(db_manager, config)
    await service.initialize()
    return service


@pytest.fixture
async def activity_panel(activity_service):
    """創建測試用活躍度面板"""
    config = {}
    panel = ActivityPanel(activity_service, config)
    return panel


@pytest.fixture
def mock_guild():
    """創建模擬伺服器"""
    return MockGuild(
        guild_id=123456789,
        name="測試伺服器"
    )


@pytest.fixture
def mock_member(mock_guild):
    """創建模擬成員"""
    return MockMember(
        user_id=987654321,
        name="TestUser",
        display_name="測試用戶",
        guild=mock_guild
    )


@pytest.fixture
def mock_channel(mock_guild):
    """創建模擬頻道"""
    return MockTextChannel(
        channel_id=555666777,
        name="一般",
        guild=mock_guild
    )


@pytest.fixture
def mock_message(mock_member, mock_channel):
    """創建模擬訊息"""
    return MockMessage(
        message_id=111222333,
        content="測試訊息",
        author=mock_member,
        channel=mock_channel
    )


class TestActivityServiceIntegration:
    """活躍度服務整合測試"""
    
    @pytest.mark.asyncio
    async def test_service_initialization(self, activity_service):
        """測試服務初始化"""
        assert activity_service.is_initialized
        assert activity_service.name == "ActivityService"
        assert activity_service.db_manager is not None
    
    @pytest.mark.asyncio
    async def test_settings_management(self, activity_service, mock_guild):
        """測試設定管理"""
        guild_id = mock_guild.id
        
        # 測試獲取預設設定
        settings = await activity_service.get_settings(guild_id)
        assert settings.guild_id == guild_id
        assert settings.max_score == 100.0
        assert settings.gain_per_message == 1.0
        
        # 測試更新設定
        success = await activity_service.update_setting(guild_id, 'max_score', 200.0)
        assert success
        
        # 確認設定已更新
        updated_settings = await activity_service.get_settings(guild_id)
        assert updated_settings.max_score == 200.0
    
    @pytest.mark.asyncio
    async def test_activity_calculation(self, activity_service, mock_member, mock_message):
        """測試活躍度計算"""
        guild_id = mock_member.guild.id
        user_id = mock_member.id
        
        # 初始活躍度應該是 0
        initial_score = await activity_service.get_activity_score(user_id, guild_id)
        assert initial_score == 0.0
        
        # 更新活躍度
        new_score = await activity_service.update_activity(user_id, guild_id, mock_message)
        assert new_score > 0.0
        
        # 驗證分數持久化
        stored_score = await activity_service.get_activity_score(user_id, guild_id)
        assert stored_score == new_score
    
    @pytest.mark.asyncio
    async def test_activity_decay(self, activity_service, mock_member, mock_guild):
        """測試活躍度衰減"""
        guild_id = mock_guild.id
        user_id = mock_member.id
        
        # 設定較快的衰減參數以便測試
        await activity_service.update_setting(guild_id, 'decay_after_seconds', 1)
        await activity_service.update_setting(guild_id, 'decay_per_hour', 60.0)  # 1分/小時
        
        # 手動插入活躍度記錄
        past_time = int(time.time()) - 3661  # 1小時1秒前
        await activity_service.db_manager.execute("""
            INSERT INTO activity_meter (guild_id, user_id, score, last_msg)
            VALUES (?, ?, ?, ?)
        """, (guild_id, user_id, 100.0, past_time))
        
        # 獲取當前分數（應該已衰減）
        current_score = await activity_service.get_activity_score(user_id, guild_id)
        assert current_score < 100.0
        assert current_score > 38.0  # 大概衰減 ~61分
    
    @pytest.mark.asyncio
    async def test_cooldown_mechanism(self, activity_service, mock_member, mock_message):
        """測試冷卻機制"""
        guild_id = mock_member.guild.id
        user_id = mock_member.id
        
        # 設定冷卻時間
        await activity_service.update_setting(guild_id, 'cooldown_seconds', 5)
        
        # 第一次更新
        score1 = await activity_service.update_activity(user_id, guild_id, mock_message)
        assert score1 > 0.0
        
        # 立即第二次更新（應該被冷卻）
        score2 = await activity_service.update_activity(user_id, guild_id, mock_message)
        assert score2 == score1  # 分數不變
        
        # 等待冷卻時間後再試（實際測試中可能需要模擬時間）
        # 這裡簡化處理，因為真實等待會讓測試太慢
    
    @pytest.mark.asyncio
    async def test_leaderboard_generation(self, activity_service, mock_guild):
        """測試排行榜生成"""
        guild_id = mock_guild.id
        
        # 插入測試數據
        today = datetime.now().strftime("%Y%m%d")
        test_users = [
            (111, 50),  # user_id, message_count
            (222, 30),
            (333, 80),
            (444, 10)
        ]
        
        for user_id, msg_count in test_users:
            await activity_service.db_manager.execute("""
                INSERT OR REPLACE INTO activity_daily (ymd, guild_id, user_id, msg_cnt)
                VALUES (?, ?, ?, ?)
            """, (today, guild_id, user_id, msg_count))
        
        # 生成排行榜
        leaderboard = await activity_service.get_daily_leaderboard(guild_id, 10)
        
        assert len(leaderboard) == 4
        assert leaderboard[0].user_id == 333  # 最高分
        assert leaderboard[0].daily_messages == 80
        assert leaderboard[1].user_id == 111  # 第二高
        assert leaderboard[1].daily_messages == 50
    
    @pytest.mark.asyncio
    async def test_monthly_stats(self, activity_service, mock_guild):
        """測試月度統計"""
        guild_id = mock_guild.id
        
        # 插入本月的測試數據
        current_month = datetime.now().strftime("%Y%m")
        dates = [
            f"{current_month}01",
            f"{current_month}02",
            f"{current_month}03"
        ]
        
        for date in dates:
            await activity_service.db_manager.execute("""
                INSERT OR REPLACE INTO activity_daily (ymd, guild_id, user_id, msg_cnt)
                VALUES (?, ?, ?, ?)
            """, (date, guild_id, 111, 20))  # 每天20條訊息
        
        # 獲取月度統計
        monthly_stats = await activity_service.get_monthly_stats(guild_id)
        
        assert monthly_stats.guild_id == guild_id
        assert monthly_stats.total_messages == 60  # 3天 x 20條
        assert monthly_stats.active_users == 1
        assert monthly_stats.average_messages_per_user == 60.0
    
    @pytest.mark.asyncio
    async def test_report_channel_setting(self, activity_service, mock_guild, mock_channel):
        """測試報告頻道設定"""
        guild_id = mock_guild.id
        channel_id = mock_channel.id
        
        # 設定報告頻道
        success = await activity_service.set_report_channel(guild_id, channel_id)
        assert success
        
        # 確認設定已保存
        settings = await activity_service.get_settings(guild_id)
        assert settings.report_channel_id == channel_id
    
    @pytest.mark.asyncio
    async def test_activity_image_generation(self, activity_service, mock_member):
        """測試活躍度圖片生成"""
        guild_id = mock_member.guild.id
        user_id = mock_member.id
        
        # 生成圖片
        activity_image = await activity_service.generate_activity_image(
            user_id, guild_id, mock_member
        )
        
        assert activity_image.guild_id == guild_id
        assert activity_image.user_id == user_id
        assert activity_image.display_name == mock_member.display_name
        assert activity_image.max_score == 100.0
        assert len(activity_image.image_bytes) > 0  # 確保有圖片數據
    
    @pytest.mark.asyncio
    async def test_daily_report_generation(self, activity_service, mock_guild):
        """測試每日報告生成"""
        guild_id = mock_guild.id
        
        # 插入今日測試數據
        today = datetime.now().strftime("%Y%m%d")
        await activity_service.db_manager.execute("""
            INSERT OR REPLACE INTO activity_daily (ymd, guild_id, user_id, msg_cnt)
            VALUES (?, ?, ?, ?)
        """, (today, guild_id, 123, 25))
        
        # 生成報告
        report = await activity_service.generate_daily_report(guild_id)
        
        assert report is not None
        assert report.guild_id == guild_id
        assert len(report.leaderboard) > 0
        assert report.monthly_stats is not None


class TestActivityPanelIntegration:
    """活躍度面板整合測試"""
    
    @pytest.mark.asyncio
    async def test_panel_initialization(self, activity_panel, activity_service):
        """測試面板初始化"""
        assert activity_panel.name == "ActivityPanel"
        assert activity_panel.activity_service == activity_service
        assert activity_panel.get_service("activity") == activity_service
    
    @pytest.mark.asyncio
    async def test_activity_bar_display(self, activity_panel, mock_member):
        """測試活躍度進度條顯示"""
        # 創建模擬互動
        interaction = MockInteraction(mock_member.guild, mock_member)
        
        with patch.object(interaction, 'response') as mock_response, \
             patch.object(interaction, 'followup') as mock_followup:
            
            mock_response.defer = AsyncMock()
            mock_followup.send = AsyncMock()
            
            # 呼叫面板方法
            await activity_panel.show_activity_bar(interaction, mock_member)
            
            # 確認已延遲回應和發送結果
            mock_response.defer.assert_called_once()
            mock_followup.send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_leaderboard_display(self, activity_panel, mock_guild):
        """測試排行榜顯示"""
        # 創建模擬互動
        interaction = MockInteraction(mock_guild, mock_guild.get_member(123))
        
        with patch.object(interaction, 'response') as mock_response, \
             patch.object(interaction, 'followup') as mock_followup:
            
            mock_response.defer = AsyncMock()
            mock_followup.send = AsyncMock()
            
            # 呼叫面板方法
            await activity_panel.display_leaderboard(interaction, 5)
            
            # 確認已處理
            mock_response.defer.assert_called_once()
            mock_followup.send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_settings_panel_display(self, activity_panel, mock_guild):
        """測試設定面板顯示"""
        # 創建管理員成員
        admin_member = MockMember(999, "Admin", "管理員", mock_guild)
        admin_member.guild_permissions.manage_guild = True
        
        interaction = MockInteraction(mock_guild, admin_member)
        
        with patch.object(interaction, 'response') as mock_response:
            mock_response.send_message = AsyncMock()
            
            # 呼叫面板方法
            await activity_panel.show_settings_panel(interaction)
            
            # 確認已發送設定面板
            mock_response.send_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_report_channel_setting(self, activity_panel, mock_guild, mock_channel):
        """測試報告頻道設定"""
        # 創建管理員成員
        admin_member = MockMember(999, "Admin", "管理員", mock_guild)
        admin_member.guild_permissions.manage_guild = True
        
        interaction = MockInteraction(mock_guild, admin_member)
        
        with patch.object(activity_panel, 'send_success') as mock_success:
            mock_success.return_value = AsyncMock()
            
            # 設定頻道
            await activity_panel.set_report_channel(interaction, mock_channel)
            
            # 確認成功訊息
            mock_success.assert_called_once()


class TestAchievementIntegration:
    """成就系統整合測試"""
    
    @pytest.mark.asyncio
    async def test_achievement_service_integration(self, activity_service):
        """測試成就服務整合"""
        # 模擬成就服務
        mock_achievement_service = AsyncMock()
        mock_achievement_service.process_event_triggers = AsyncMock(return_value=["achievement_1"])
        
        activity_service._achievement_service = mock_achievement_service
        
        # 創建模擬訊息
        mock_message = MockMessage(111, "test", MockMember(222, "user", "用戶"), None)
        
        # 觸發成就檢查
        await activity_service._trigger_activity_achievements(222, 333, 50.0, mock_message)
        
        # 確認成就服務被呼叫
        assert mock_achievement_service.process_event_triggers.call_count >= 1
    
    @pytest.mark.asyncio
    async def test_achievement_event_data_format(self, activity_service):
        """測試成就事件資料格式"""
        # 捕獲傳給成就系統的事件資料
        captured_events = []
        
        async def capture_event(event_data):
            captured_events.append(event_data)
            return []
        
        mock_achievement_service = AsyncMock()
        mock_achievement_service.process_event_triggers = capture_event
        
        activity_service._achievement_service = mock_achievement_service
        
        # 觸發事件
        mock_message = MockMessage(111, "test", MockMember(222, "user", "用戶"), None)
        await activity_service._trigger_activity_achievements(222, 333, 75.5, mock_message)
        
        # 檢查事件格式
        assert len(captured_events) >= 1
        
        activity_event = captured_events[0]
        assert activity_event["type"] == "activity_score"
        assert activity_event["user_id"] == 222
        assert activity_event["guild_id"] == 333
        assert activity_event["value"] == 75.5
        assert "timestamp" in activity_event


class TestSystemIntegration:
    """系統整合測試"""
    
    @pytest.mark.asyncio
    async def test_complete_workflow(self, activity_service, activity_panel, mock_member, mock_message):
        """測試完整工作流程"""
        guild_id = mock_member.guild.id
        user_id = mock_member.id
        
        # 1. 初始狀態檢查
        initial_score = await activity_service.get_activity_score(user_id, guild_id)
        assert initial_score == 0.0
        
        # 2. 處理訊息並更新活躍度
        new_score = await activity_service.update_activity(user_id, guild_id, mock_message)
        assert new_score > 0.0
        
        # 3. 生成活躍度圖片
        activity_image = await activity_service.generate_activity_image(user_id, guild_id, mock_member)
        assert activity_image.score == new_score
        
        # 4. 檢查排行榜
        leaderboard = await activity_service.get_daily_leaderboard(guild_id, 10)
        user_found = any(entry.user_id == user_id for entry in leaderboard)
        assert user_found
        
        # 5. 生成每日報告
        report = await activity_service.generate_daily_report(guild_id)
        assert report is not None
        assert len(report.leaderboard) > 0
    
    @pytest.mark.asyncio
    async def test_error_resilience(self, activity_service, mock_member):
        """測試錯誤恢復能力"""
        guild_id = mock_member.guild.id
        user_id = mock_member.id
        
        # 測試無效輸入
        with pytest.raises(ServiceError):
            await activity_service.update_setting(guild_id, "invalid_key", "value")
        
        # 測試服務仍然正常運作
        score = await activity_service.get_activity_score(user_id, guild_id)
        assert isinstance(score, (int, float))
    
    @pytest.mark.asyncio  
    async def test_concurrent_updates(self, activity_service, mock_member):
        """測試並發更新處理"""
        guild_id = mock_member.guild.id
        user_id = mock_member.id
        
        # 創建多個模擬訊息
        messages = [
            MockMessage(i, f"message {i}", mock_member, None)
            for i in range(100, 110)
        ]
        
        # 同時處理多個更新
        tasks = [
            activity_service.update_activity(user_id, guild_id, msg)
            for msg in messages
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 檢查沒有異常
        exceptions = [r for r in results if isinstance(r, Exception)]
        assert len(exceptions) == 0
        
        # 檢查最終分數合理
        final_score = await activity_service.get_activity_score(user_id, guild_id)
        assert final_score > 0.0


if __name__ == "__main__":
    # 執行測試
    pytest.main([__file__, "-v", "--tb=short"])