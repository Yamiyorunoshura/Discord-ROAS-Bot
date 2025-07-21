"""
活躍度系統測試模塊
測試活躍度計算器、資料庫操作、渲染器和整合功能
"""

import pytest
import pytest_asyncio
import asyncio
import time
import logging
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Any, Dict, List, Tuple

import discord
import aiosqlite
from contextlib import asynccontextmanager

# 測試配置
logging.basicConfig(level=logging.DEBUG)

class TestActivityCalculator:
    """🧮 活躍度計算器測試類"""
    
    @pytest.fixture
    def calculator(self):
        """建立測試用計算器"""
        from cogs.activity_meter.main.calculator import ActivityCalculator
        return ActivityCalculator()
    
    def test_decay_no_time(self, calculator):
        """測試無時間差的衰減計算"""
        current_score = 50.0
        time_diff = 0
        
        result = calculator.decay(current_score, time_diff)
        
        assert result == current_score, f"無時間差應無衰減: {result} != {current_score}"
    
    def test_decay_within_grace_period(self, calculator):
        """測試寬限期內的衰減計算"""
        current_score = 50.0
        time_diff = 1800  # 30分鐘，小於1小時寬限期
        
        result = calculator.decay(current_score, time_diff)
        
        assert result == current_score, f"寬限期內應無衰減: {result} != {current_score}"
    
    def test_decay_after_grace_period(self, calculator):
        """測試寬限期後的衰減計算"""
        current_score = 50.0
        time_diff = 7200  # 2小時，大於寬限期
        
        result = calculator.decay(current_score, time_diff)
        
        assert result < current_score, f"寬限期後應有衰減: {result} >= {current_score}"
        assert result >= 0, f"衰減後分數不應為負: {result}"
    
    def test_calculate_new_score_normal_case(self, calculator):
        """測試正常情況下的新分數計算"""
        current_score = 50.0
        last_message_time = int(time.time()) - 100
        now = int(time.time())
        
        result = calculator.calculate_new_score(current_score, last_message_time, now)
        
        assert isinstance(result, float), f"結果應為浮點數: {type(result)}"
        assert result >= 0, f"新分數不應為負: {result}"
        assert result <= 100, f"新分數不應超過上限: {result}"
    
    def test_should_update_cooldown_logic(self, calculator):
        """測試更新冷卻邏輯"""
        now = int(time.time())
        recent_time = now - 10  # 10秒前
        old_time = now - 100    # 100秒前
        
        should_update_recent = calculator.should_update(recent_time, now)
        should_update_old = calculator.should_update(old_time, now)
        
        assert not should_update_recent, "最近更新應在冷卻期內"
        assert should_update_old, "較舊更新應允許更新"

class TestActivityDatabase:
    """🗄️ 活躍度資料庫測試類"""
    
    @pytest_asyncio.fixture
    async def activity_db(self, activity_test_db):
        """建立測試用活躍度資料庫"""
        from cogs.activity_meter.database.database import ActivityDatabase
        db = ActivityDatabase()
        # 使用mock pool模式
        mock_pool = MagicMock()
        
        @asynccontextmanager
        async def mock_get_connection_context(db_path):
            yield activity_test_db
        
        mock_pool.get_connection_context = mock_get_connection_context
        db._pool = mock_pool
        await db.init_db()
        return db
    
    @pytest.mark.asyncio
    async def test_database_initialization(self, activity_test_db):
        """測試資料庫初始化"""
        from cogs.activity_meter.database.database import ActivityDatabase
        
        db = ActivityDatabase()
        # 使用mock pool模式
        mock_pool = MagicMock()
        
        @asynccontextmanager
        async def mock_get_connection_context(db_path):
            yield activity_test_db
        
        mock_pool.get_connection_context = mock_get_connection_context
        db._pool = mock_pool
        
        await db.init_db()
        
        # 驗證表格創建
        tables = ["meter", "daily"]
        for table in tables:
            cursor = await activity_test_db.execute(
                f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'"
            )
            result = await cursor.fetchone()
            assert result is not None, f"表格 {table} 應該被創建"

class TestActivityRenderer:
    """📊 活躍度渲染器測試類"""
    
    @pytest.fixture
    def renderer(self):
        """建立測試用渲染器"""
        from cogs.activity_meter.main.renderer import ActivityRenderer
        return ActivityRenderer()
    
    def test_render_progress_bar_normal(self, renderer):
        """測試正常進度條渲染"""
        with patch('PIL.Image.new') as mock_image,              patch('PIL.ImageDraw.Draw') as mock_draw,              patch('PIL.ImageFont.truetype') as mock_font:
            
            mock_img = Mock()
            mock_drawer = Mock()
            mock_font_obj = Mock()
            
            mock_image.return_value = mock_img
            mock_draw.return_value = mock_drawer
            mock_font.return_value = mock_font_obj
            
            # 模擬字體方法
            mock_font_obj.getlength.return_value = 100
            mock_drawer.textbbox.return_value = (0, 0, 100, 20)
            
            # 模擬圖片保存
            mock_img.save = Mock()
            
            result = renderer.render_progress_bar("測試用戶", 75.5)
            
            assert result is not None, "應返回渲染結果"
            assert isinstance(result, discord.File), "應返回Discord文件"

# 測試工具函數
def test_config_validation():
    """測試配置驗證"""
    from cogs.activity_meter.config import config
    
    # 驗證關鍵配置存在
    assert hasattr(config, 'ACTIVITY_MAX_SCORE'), "應有最大分數配置"
    assert hasattr(config, 'ACTIVITY_DECAY_PER_H'), "應有衰減率配置"
    assert hasattr(config, 'ACTIVITY_DECAY_AFTER'), "應有寬限期配置"
    assert hasattr(config, 'ACTIVITY_GAIN'), "應有增益配置"
    assert hasattr(config, 'ACTIVITY_COOLDOWN'), "應有冷卻時間配置"

def test_time_utilities():
    """測試時間工具函數"""
    import time
    
    current_time = int(time.time())
    
    assert current_time > 0, "當前時間應大於0"
    assert isinstance(current_time, int), "時間戳應為整數"
