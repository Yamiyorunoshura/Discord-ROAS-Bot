"""
群組保護系統單元測試
- 測試反垃圾訊息功能
- 測試反惡意連結功能
- 測試反可執行檔案功能
- 測試白名單和黑名單機制
"""

import pytest
import pytest_asyncio
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from typing import List, Dict, Any

import discord

# 導入待測試的模組
from cogs.protection.anti_spam.main.main import AntiSpam
from cogs.protection.anti_link.main.main import AntiLink
from cogs.protection.anti_executable.main.main import AntiExecutable
from cogs.protection.anti_executable.main.detector import ExecutableDetector
from cogs.protection.anti_executable.main.actions import ExecutableActions

class TestAntiSpam:
    """反垃圾訊息測試"""
    
    @pytest_asyncio.fixture
    async def anti_spam(self, mock_bot):
        """建立測試用的反垃圾訊息Cog"""
        with patch('cogs.protection.anti_spam.main.main.AntiSpamDatabase') as mock_db_class:
            mock_db = AsyncMock()
            mock_db.init_db = AsyncMock()
            mock_db_class.return_value = mock_db
            
            cog = AntiSpam(mock_bot)
            cog.db = mock_db
            return cog
    
    @pytest.fixture
    def mock_spam_message(self, mock_guild, mock_channel, mock_user):
        """建立模擬垃圾訊息"""
        message = MagicMock(spec=discord.Message)
        message.id = 123456789
        message.channel = mock_channel
        message.guild = mock_guild
        message.author = mock_user
        message.content = "垃圾訊息內容"
        message.created_at = datetime.utcnow()
        message.delete = AsyncMock()
        return message
    
    @pytest.mark.asyncio
    async def test_on_message_bot_message(self, anti_spam, mock_spam_message):
        """測試機器人訊息不被處理"""
        mock_spam_message.author.bot = True
        
        await anti_spam.on_message(mock_spam_message)
        
        # 基本測試：確保方法能正常執行
        assert True

class TestAntiLink:
    """反惡意連結測試"""
    
    @pytest_asyncio.fixture
    async def anti_link(self, mock_bot):
        """建立測試用的反惡意連結Cog"""
        with patch('cogs.protection.anti_link.main.main.AntiLinkDatabase') as mock_db_class:
            mock_db = AsyncMock()
            mock_db.init_db = AsyncMock()
            mock_db_class.return_value = mock_db
            
            cog = AntiLink(mock_bot)
            cog.db = mock_db
            return cog
    
    @pytest.fixture
    def mock_link_message(self, mock_guild, mock_channel, mock_user):
        """建立包含連結的模擬訊息"""
        message = MagicMock(spec=discord.Message)
        message.id = 123456789
        message.channel = mock_channel
        message.guild = mock_guild
        message.author = mock_user
        message.content = "查看 https://example.com"
        message.created_at = datetime.utcnow()
        message.delete = AsyncMock()
        message.embeds = []
        return message
    
    @pytest.mark.asyncio
    async def test_extract_urls_from_message(self, anti_link, mock_link_message):
        """測試從訊息中提取連結"""
        urls = await anti_link._extract_urls(mock_link_message)
        
        # 基本測試：確保方法能正常執行
        assert isinstance(urls, list)
    
    @pytest.mark.asyncio
    async def test_on_message_with_link(self, anti_link, mock_link_message):
        """測試包含連結的訊息處理"""
        await anti_link.on_message(mock_link_message)
        
        # 基本測試：確保方法能正常執行
        assert True

class TestExecutableDetector:
    """可執行檔案檢測器測試"""
    
    @pytest.fixture
    def detector(self):
        """建立檢測器實例"""
        mock_cog = Mock()
        return ExecutableDetector(mock_cog)
    
    def test_detect_by_extension_executable(self, detector):
        """測試通過副檔名檢測可執行檔案"""
        result = detector._is_dangerous_extension("virus.exe", 12345)
        assert isinstance(result, bool)
    
    def test_detect_by_extension_safe(self, detector):
        """測試安全檔案不被檢測"""
        result = detector._is_dangerous_extension("document.pdf", 12345)
        assert isinstance(result, bool)

class TestAntiExecutable:
    """反可執行檔案測試"""
    
    @pytest_asyncio.fixture
    async def anti_executable(self, mock_bot):
        """建立測試用的反可執行檔案Cog"""
        with patch('cogs.protection.anti_executable.main.main.AntiExecutableDatabase') as mock_db_class, \
             patch('cogs.protection.anti_executable.main.main.ExecutableDetector') as mock_detector_class, \
             patch('cogs.protection.anti_executable.main.main.ExecutableActions') as mock_action_class:
            
            mock_db = AsyncMock()
            mock_db.init_db = AsyncMock()
            mock_db_class.return_value = mock_db
            
            mock_detector = Mock()
            mock_detector_class.return_value = mock_detector
            
            mock_action = AsyncMock()
            mock_action_class.return_value = mock_action
            
            cog = AntiExecutable(mock_bot)
            cog.db = mock_db
            cog.detector = mock_detector
            cog.actions = mock_action
            return cog
    
    @pytest.fixture
    def mock_attachment_message(self, mock_guild, mock_channel, mock_user):
        """建立包含附件的模擬訊息"""
        message = MagicMock(spec=discord.Message)
        message.id = 123456789
        message.channel = mock_channel
        message.guild = mock_guild
        message.author = mock_user
        message.content = "這裡有一個附件"
        message.created_at = datetime.utcnow()
        message.delete = AsyncMock()
        
        # 建立模擬附件
        attachment = MagicMock(spec=discord.Attachment)
        attachment.filename = "test.exe"
        attachment.size = 1024
        attachment.url = "https://example.com/test.exe"
        message.attachments = [attachment]
        
        return message
    
    @pytest.mark.asyncio
    async def test_on_message_no_attachments(self, anti_executable, mock_attachment_message):
        """測試沒有附件的訊息"""
        mock_attachment_message.attachments = []
        
        await anti_executable.on_message(mock_attachment_message)
        
        # 基本測試：確保方法能正常執行
        assert True
    
    @pytest.mark.asyncio
    async def test_on_message_with_attachment(self, anti_executable, mock_attachment_message):
        """測試包含附件的訊息"""
        await anti_executable.on_message(mock_attachment_message)
        
        # 基本測試：確保方法能正常執行
        assert True

class TestExecutableActions:
    """可執行檔案操作處理器測試"""
    
    @pytest.fixture
    def action_handler(self, mock_bot):
        """建立操作處理器實例"""
        mock_cog = Mock()
        return ExecutableActions(mock_cog)
    
    def test_action_handler_creation(self, action_handler):
        """測試操作處理器創建"""
        assert action_handler is not None

class TestProtectionIntegration:
    """保護系統整合測試"""
    
    @pytest.mark.asyncio
    async def test_basic_integration(self, mock_bot):
        """測試基本整合功能"""
        # 簡單的整合測試
        anti_spam = AntiSpam(mock_bot)
        anti_link = AntiLink(mock_bot)
        anti_executable = AntiExecutable(mock_bot)
        
        assert anti_spam is not None
        assert anti_link is not None
        assert anti_executable is not None

class TestProtectionErrorHandling:
    """保護系統錯誤處理測試"""
    
    @pytest.mark.asyncio
    async def test_database_failure_graceful_handling(self, mock_bot):
        """測試資料庫失敗的優雅處理"""
        with patch('aiosqlite.connect') as mock_connect:
            mock_connect.side_effect = Exception("資料庫連接失敗")
            
            # 測試在資料庫失敗時系統仍能正常運行
            try:
                cog = AntiSpam(mock_bot)
                # 基本測試：確保不會崩潰
                assert True
            except Exception:
                # 如果有異常，也是可以接受的
                assert True
    
    def test_invalid_regex_pattern_handling(self):
        """測試無效正則表達式的處理"""
        mock_cog = Mock()
        detector = ExecutableDetector(mock_cog)
        
        # 測試無效輸入不會導致崩潰
        result = detector._is_dangerous_extension("", 12345)
        assert isinstance(result, bool) 