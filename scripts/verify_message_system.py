#!/usr/bin/env python3
"""
訊息系統驗證腳本
Task ID: 9 - 重構現有模組以符合新架構

執行訊息系統的基本驗證測試，確保重構後的系統正常運作
"""

import asyncio
import sys
import os
import tempfile
from unittest.mock import Mock, AsyncMock
from datetime import datetime, timedelta
import logging

# 設定路徑
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.message.message_service import MessageService
from services.message.models import MessageRecord, MonitorSettings, SearchQuery, SearchResult
from panels.message.message_panel import MessagePanel
from core.database_manager import DatabaseManager

# 設定日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_message_service():
    """測試訊息服務基本功能"""
    logger.info("🧪 測試訊息服務...")
    
    try:
        # 建立模擬資料庫管理器
        mock_db = Mock(spec=DatabaseManager)
        mock_db.execute = AsyncMock()
        mock_db.fetchone = AsyncMock()
        mock_db.fetchall = AsyncMock()
        
        config = {
            'render': {
                'max_cached_messages': 5,
                'max_cache_time': 300
            }
        }
        
        # 初始化服務
        service = MessageService(mock_db, config)
        result = await service.initialize()
        
        if not result:
            logger.error("❌ 訊息服務初始化失敗")
            return False
        
        logger.info("✅ 訊息服務初始化成功")
        
        # 測試獲取預設設定
        mock_db.fetchall.return_value = []
        settings = await service.get_settings()
        
        assert isinstance(settings, MonitorSettings)
        assert settings.enabled is True
        assert settings.retention_days == 7
        
        logger.info("✅ 預設設定測試通過")
        
        # 測試更新設定
        result = await service.update_setting("enabled", "false")
        assert result is True
        
        mock_db.execute.assert_called()
        logger.info("✅ 設定更新測試通過")
        
        # 測試監聽頻道管理
        result = await service.add_monitored_channel(123456789)
        assert result is True
        
        result = await service.remove_monitored_channel(123456789)
        assert result is True
        
        logger.info("✅ 監聽頻道管理測試通過")
        
        # 測試訊息搜尋
        mock_db.fetchone.return_value = {'total': 5}
        mock_db.fetchall.return_value = [
            {
                'message_id': 123,
                'channel_id': 456,
                'guild_id': 789,
                'author_id': 111,
                'content': 'test message',
                'timestamp': datetime.now().timestamp(),
                'attachments': None
            }
        ]
        
        query = SearchQuery(keyword="test", limit=10)
        result = await service.search_messages(query)
        
        assert isinstance(result, SearchResult)
        assert len(result.records) == 1
        assert result.total_count == 5
        
        logger.info("✅ 訊息搜尋測試通過")
        
        # 清理
        await service.cleanup()
        logger.info("✅ 服務清理完成")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 訊息服務測試失敗: {e}")
        return False


async def test_message_panel():
    """測試訊息面板基本功能"""
    logger.info("🧪 測試訊息面板...")
    
    try:
        # 建立模擬服務
        mock_service = Mock(spec=MessageService)
        mock_service.get_settings = AsyncMock()
        mock_service.update_setting = AsyncMock()
        mock_service.search_messages = AsyncMock()
        
        config = {}
        
        # 初始化面板
        panel = MessagePanel(mock_service, config)
        
        assert panel.name == "MessagePanel"
        assert panel.title == "📝 訊息監聽管理面板"
        assert panel.message_service == mock_service
        
        logger.info("✅ 訊息面板初始化成功")
        
        # 測試設定更新處理
        mock_interaction = Mock()
        mock_interaction.guild = Mock()
        mock_interaction.guild.id = 123456789
        
        mock_service.update_setting.return_value = True
        
        # 模擬方法
        panel.send_success = AsyncMock()
        panel._refresh_settings_panel = AsyncMock()
        
        await panel.handle_setting_update(mock_interaction, "enabled", "true")
        
        mock_service.update_setting.assert_called_once_with("enabled", "true")
        panel.send_success.assert_called_once()
        panel._refresh_settings_panel.assert_called_once()
        
        logger.info("✅ 面板設定更新測試通過")
        
        # 測試搜尋處理
        mock_query = SearchQuery(keyword="test")
        mock_result = SearchResult(
            records=[],
            total_count=0,
            has_more=False,
            query=mock_query
        )
        mock_service.search_messages.return_value = mock_result
        
        # 模擬方法
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup.send = AsyncMock()
        panel._build_search_result_embed = AsyncMock()
        panel._build_search_result_embed.return_value = Mock()
        
        await panel.handle_search(mock_interaction, mock_query)
        
        mock_service.search_messages.assert_called_once_with(mock_query)
        mock_interaction.response.defer.assert_called_once()
        mock_interaction.followup.send.assert_called_once()
        
        logger.info("✅ 面板搜尋處理測試通過")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 訊息面板測試失敗: {e}")
        return False


async def test_data_models():
    """測試資料模型"""
    logger.info("🧪 測試資料模型...")
    
    try:
        # 測試 MessageRecord
        record = MessageRecord(
            message_id=123,
            channel_id=456,
            guild_id=789,
            author_id=111,
            content="test content",
            timestamp=datetime.now().timestamp()
        )
        
        assert record.message_id == 123
        assert record.channel_id == 456
        assert record.content == "test content"
        
        logger.info("✅ MessageRecord 模型測試通過")
        
        # 測試 MonitorSettings
        settings = MonitorSettings(
            enabled=True,
            log_channel_id=123,
            monitored_channels=[456, 789],
            retention_days=30
        )
        
        assert settings.enabled is True
        assert settings.log_channel_id == 123
        assert len(settings.monitored_channels) == 2
        assert settings.retention_days == 30
        
        logger.info("✅ MonitorSettings 模型測試通過")
        
        # 測試 SearchQuery
        query = SearchQuery(
            keyword="test",
            channel_id=123,
            limit=20,
            start_time=datetime.now() - timedelta(days=1),
            end_time=datetime.now()
        )
        
        assert query.keyword == "test"
        assert query.channel_id == 123
        assert query.limit == 20
        assert isinstance(query.start_time, datetime)
        
        logger.info("✅ SearchQuery 模型測試通過")
        
        # 測試 SearchResult
        result = SearchResult(
            records=[record],
            total_count=1,
            has_more=False,
            query=query
        )
        
        assert len(result.records) == 1
        assert result.total_count == 1
        assert result.has_more is False
        assert result.query == query
        
        logger.info("✅ SearchResult 模型測試通過")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 資料模型測試失敗: {e}")
        return False


async def test_integration():
    """測試整合功能"""
    logger.info("🧪 測試整合功能...")
    
    try:
        # 建立模擬環境
        mock_db = Mock(spec=DatabaseManager)
        mock_db.execute = AsyncMock()
        mock_db.fetchone = AsyncMock()
        mock_db.fetchall = AsyncMock()
        
        config = {
            'render': {
                'max_cached_messages': 3,
                'max_cache_time': 120
            }
        }
        
        # 建立服務和面板
        service = MessageService(mock_db, config)
        await service.initialize()
        
        panel = MessagePanel(service, config)
        
        # 測試服務和面板的整合
        assert panel.message_service == service
        assert panel.get_service("message") == service
        
        logger.info("✅ 服務和面板整合測試通過")
        
        # 測試快取機制
        # 模擬 Discord 訊息
        mock_message = Mock()
        mock_message.id = 123456
        mock_message.channel.id = 789
        mock_message.guild.id = 999
        mock_message.author.id = 111
        mock_message.content = "test message"
        mock_message.created_at.timestamp.return_value = datetime.now().timestamp()
        mock_message.attachments = []
        
        # 設定監聽頻道
        await service.add_monitored_channel(789)
        
        # 儲存訊息（應該會被快取）
        result = await service.save_message(mock_message)
        assert result is True
        
        logger.info("✅ 快取機制測試通過")
        
        # 清理
        await service.cleanup()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 整合測試失敗: {e}")
        return False


async def main():
    """主測試函數"""
    logger.info("🚀 開始訊息系統驗證測試...")
    
    tests = [
        test_data_models,
        test_message_service,
        test_message_panel,
        test_integration,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            result = await test()
            if result:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            logger.error(f"❌ 測試執行錯誤: {e}")
            failed += 1
    
    logger.info(f"\n📊 測試結果:")
    logger.info(f"✅ 通過: {passed}")
    logger.info(f"❌ 失敗: {failed}")
    logger.info(f"📈 成功率: {passed/(passed+failed)*100:.1f}%")
    
    if failed == 0:
        logger.info("🎉 所有測試都通過了！訊息系統重構成功！")
        return True
    else:
        logger.error("💥 有測試失敗，需要進一步檢查")
        return False


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)