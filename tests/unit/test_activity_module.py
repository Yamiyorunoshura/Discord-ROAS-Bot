"""
🧪 ActivityModule 測試
- 測試活躍度模塊統一API功能
- 驗證緩存機制和錯誤處理
- 測試性能監控和指標收集
- 驗證API響應格式
"""

import pytest
import pytest_asyncio
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Any, Dict, List

from cogs.activity_meter.main.activity_module import (
    ActivityModule, ActivityData, ActivityAPIError, UserNotFoundError
)

class TestActivityModule:
    """ActivityModule 測試類"""
    
    @pytest.fixture
    def activity_module(self):
        """建立測試用 ActivityModule"""
        with patch('cogs.activity_meter.main.activity_module.LogicAPIs') as mock_logic_apis, \
             patch('cogs.activity_meter.main.activity_module.ActivityCache') as mock_cache, \
             patch('cogs.activity_meter.main.activity_module.ActivityCalculator') as mock_calculator, \
             patch('cogs.activity_meter.main.activity_module.ActivityRenderer') as mock_renderer:
            
            mock_logic_apis.return_value = Mock()
            mock_cache.return_value = Mock()
            mock_calculator.return_value = Mock()
            mock_renderer.return_value = Mock()
            
            return ActivityModule()
    
    def test_initialization(self, activity_module):
        """測試初始化"""
        assert activity_module.logic_apis is not None
        assert activity_module.cache is not None
        assert activity_module.calculator is not None
        assert activity_module.renderer is not None
        assert activity_module.api_calls == 0
        assert activity_module.cache_hits == 0
        assert activity_module.cache_misses == 0
    
    def test_get_unified_activity_api_success(self, activity_module):
        """測試成功獲取統一活躍度API"""
        # 模擬緩存未命中
        activity_module.cache.get.return_value = None
        
        # 模擬邏輯API返回用戶數據
        mock_user_data = {
            "user_id": "123456789",
            "base_score": 50.0,
            "total_messages": 100,
            "response_time": 2.0,
            "last_activity": "2024-01-01T12:00:00"
        }
        activity_module.logic_apis.get_user_data.return_value = mock_user_data
        activity_module.logic_apis.get_user_rank.return_value = 5
        
        # 模擬計算器
        activity_module.calculator.calculate_level.return_value = 3
        
        # 模擬計算活躍度分數
        activity_module.calculate_activity_score = Mock(return_value=75.5)
        
        result = activity_module.get_unified_activity_api("123456789")
        
        assert isinstance(result, ActivityData)
        assert result.user_id == "123456789"
        assert result.activity_score == 75.5
        assert result.rank == 5
        assert result.level == 3
        assert activity_module.api_calls == 1
        assert activity_module.cache_misses == 1
    
    def test_get_unified_activity_api_cache_hit(self, activity_module):
        """測試緩存命中的情況"""
        # 模擬緩存命中
        cached_data = ActivityData(
            user_id="123456789",
            activity_score=75.5,
            rank=5,
            level=3
        )
        activity_module.cache.get.return_value = cached_data
        
        result = activity_module.get_unified_activity_api("123456789")
        
        assert result == cached_data
        assert activity_module.cache_hits == 1
        assert activity_module.cache_misses == 0
    
    def test_get_unified_activity_api_user_not_found(self, activity_module):
        """測試用戶不存在的情況"""
        # 模擬緩存未命中
        activity_module.cache.get.return_value = None
        
        # 模擬邏輯API返回None（用戶不存在）
        activity_module.logic_apis.get_user_data.return_value = None
        
        with pytest.raises(UserNotFoundError):
            activity_module.get_unified_activity_api("invalid_user")
    
    def test_get_unified_activity_api_error(self, activity_module):
        """測試API錯誤的情況"""
        # 模擬緩存未命中
        activity_module.cache.get.return_value = None
        
        # 模擬邏輯API拋出異常
        activity_module.logic_apis.get_user_data.side_effect = Exception("Database error")
        
        with pytest.raises(ActivityAPIError):
            activity_module.get_unified_activity_api("123456789")
    
    def test_calculate_activity_score(self, activity_module):
        """測試活躍度分數計算"""
        user_data = {
            "base_score": 50.0,
            "total_messages": 100,
            "response_time": 2.0,
            "activity_bonus": 5.0
        }
        
        score = activity_module.calculate_activity_score(user_data)
        
        assert isinstance(score, float)
        assert 0 <= score <= 100
    
    def test_calculate_activity_score_with_zero_data(self, activity_module):
        """測試零數據的活躍度分數計算"""
        user_data = {
            "base_score": 0,
            "total_messages": 0,
            "response_time": 0,
            "activity_bonus": 0
        }
        
        score = activity_module.calculate_activity_score(user_data)
        
        assert score == 0.0
    
    def test_calculate_activity_score_with_max_data(self, activity_module):
        """測試最大數據的活躍度分數計算"""
        user_data = {
            "base_score": 100.0,
            "total_messages": 1000,
            "response_time": 0,
            "activity_bonus": 20.0
        }
        
        score = activity_module.calculate_activity_score(user_data)
        
        assert score == 100.0  # 應該被限制在100
    
    def test_get_user_activity_history(self, activity_module):
        """測試獲取用戶活躍度歷史"""
        # 模擬緩存未命中
        activity_module.cache.get.return_value = None
        
        # 模擬邏輯API返回歷史數據
        mock_history_data = [
            {"score": 75.5, "timestamp": "2024-01-01", "messages": 100},
            {"score": 80.0, "timestamp": "2024-01-02", "messages": 120}
        ]
        activity_module.logic_apis.get_user_activity_history.return_value = mock_history_data
        
        result = activity_module.get_user_activity_history("123456789", 30)
        
        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(item, ActivityData) for item in result)
    
    def test_get_leaderboard(self, activity_module):
        """測試獲取排行榜"""
        # 模擬緩存未命中
        activity_module.cache.get.return_value = None
        
        # 模擬邏輯API返回排行榜數據
        mock_leaderboard_data = [
            {"user_id": "123", "score": 95.0, "messages": 500},
            {"user_id": "456", "score": 85.0, "messages": 400}
        ]
        activity_module.logic_apis.get_leaderboard.return_value = mock_leaderboard_data
        
        result = activity_module.get_leaderboard("guild_123", 10)
        
        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(item, ActivityData) for item in result)
        assert result[0].rank == 1
        assert result[1].rank == 2
    
    def test_update_user_activity_success(self, activity_module):
        """測試成功更新用戶活躍度"""
        # 模擬邏輯API返回成功
        activity_module.logic_apis.update_user_activity.return_value = True
        
        result = activity_module.update_user_activity("123456789", "guild_123", "message")
        
        assert result is True
        # 驗證緩存被清除
        activity_module.cache.delete.assert_called()
    
    def test_update_user_activity_failure(self, activity_module):
        """測試更新用戶活躍度失敗"""
        # 模擬邏輯API返回失敗
        activity_module.logic_apis.update_user_activity.return_value = False
        
        result = activity_module.update_user_activity("123456789", "guild_123", "message")
        
        assert result is False
    
    def test_get_performance_metrics(self, activity_module):
        """測試獲取性能指標"""
        # 設置一些測試數據
        activity_module.api_calls = 100
        activity_module.cache_hits = 80
        activity_module.cache_misses = 20
        
        metrics = activity_module.get_performance_metrics()
        
        assert "api_calls" in metrics
        assert "cache_hits" in metrics
        assert "cache_misses" in metrics
        assert "cache_hit_rate" in metrics
        assert "average_response_time" in metrics
        assert metrics["api_calls"] == 100
        assert metrics["cache_hits"] == 80
        assert metrics["cache_misses"] == 20
        assert metrics["cache_hit_rate"] == 80.0  # 80/100 * 100
    
    def test_clear_cache(self, activity_module):
        """測試清除緩存"""
        activity_module.clear_cache("test_pattern")
        
        activity_module.cache.clear.assert_called_with("test_pattern")
    
    def test_get_cache_stats(self, activity_module):
        """測試獲取緩存統計"""
        mock_stats = {"size": 50, "hits": 100, "misses": 20}
        activity_module.cache.get_stats.return_value = mock_stats
        
        stats = activity_module.get_cache_stats()
        
        assert stats == mock_stats

class TestActivityData:
    """ActivityData 測試類"""
    
    def test_activity_data_creation(self):
        """測試 ActivityData 創建"""
        data = ActivityData(
            user_id="123456789",
            activity_score=75.5,
            rank=5,
            level=3
        )
        
        assert data.user_id == "123456789"
        assert data.activity_score == 75.5
        assert data.rank == 5
        assert data.level == 3
        assert data.total_messages == 0
        assert data.response_time == 0.0
    
    def test_activity_data_with_optional_fields(self):
        """測試帶可選字段的 ActivityData 創建"""
        from datetime import datetime
        
        last_activity = datetime.now()
        data = ActivityData(
            user_id="123456789",
            activity_score=85.0,
            last_activity=last_activity,
            total_messages=150,
            response_time=1.5,
            rank=3,
            level=4
        )
        
        assert data.last_activity == last_activity
        assert data.total_messages == 150
        assert data.response_time == 1.5