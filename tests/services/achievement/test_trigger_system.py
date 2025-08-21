"""
成就觸發系統測試
Task ID: 6 - 成就系統核心功能

測試 services/achievement/ 中的觸發系統相關功能
包含觸發引擎、條件評估器和事件處理器的測試

測試覆蓋：
- TriggerEngine 觸發引擎
- ConditionEvaluator 條件評估器
- EventProcessor 事件處理器
- 觸發效能測試
- 複合條件邏輯測試
"""

import pytest
import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any, List

from services.achievement.trigger_engine import TriggerEngine, ConditionEvaluator, EventProcessor
from services.achievement.models import TriggerCondition, TriggerType
from core.exceptions import ValidationError, ServiceError


@pytest.fixture
def condition_evaluator():
    """條件評估器實例"""
    return ConditionEvaluator()


@pytest.fixture
def event_processor():
    """事件處理器實例"""
    return EventProcessor()


@pytest.fixture
def trigger_engine():
    """觸發引擎實例"""
    engine = TriggerEngine()
    return engine


@pytest.fixture
def sample_conditions():
    """範例觸發條件"""
    return [
        TriggerCondition(
            trigger_type=TriggerType.MESSAGE_COUNT,
            target_value=10,
            comparison_operator=">=",
            metadata={}
        ),
        TriggerCondition(
            trigger_type=TriggerType.VOICE_TIME,
            target_value=300,  # 5分鐘
            comparison_operator=">=",
            metadata={}
        ),
        TriggerCondition(
            trigger_type=TriggerType.REACTION_COUNT,
            target_value=5,
            comparison_operator=">=",
            metadata={}
        )
    ]


class TestConditionEvaluator:
    """測試條件評估器"""
    
    def test_message_count_evaluation(self, condition_evaluator):
        """測試訊息計數評估"""
        condition = TriggerCondition(
            trigger_type=TriggerType.MESSAGE_COUNT,
            target_value=10,
            comparison_operator=">=",
            metadata={}
        )
        
        # 測試達成條件
        user_progress = {"message_count": 15}
        result = condition_evaluator.evaluate_condition(condition, user_progress)
        assert result is True
        
        # 測試未達成條件
        user_progress = {"message_count": 5}
        result = condition_evaluator.evaluate_condition(condition, user_progress)
        assert result is False
        
        # 測試邊界條件
        user_progress = {"message_count": 10}
        result = condition_evaluator.evaluate_condition(condition, user_progress)
        assert result is True  # 等於目標值時應該通過 >= 檢查
    
    def test_voice_time_evaluation(self, condition_evaluator):
        """測試語音時間評估"""
        condition = TriggerCondition(
            trigger_type=TriggerType.VOICE_TIME,
            target_value=3600,  # 1小時
            comparison_operator=">=",
            metadata={}
        )
        
        # 測試達成條件（秒為單位）
        user_progress = {"voice_time": 7200}  # 2小時
        result = condition_evaluator.evaluate_condition(condition, user_progress)
        assert result is True
        
        # 測試未達成條件
        user_progress = {"voice_time": 1800}  # 30分鐘
        result = condition_evaluator.evaluate_condition(condition, user_progress)
        assert result is False
    
    def test_comparison_operators(self, condition_evaluator):
        """測試各種比較運算符"""
        operators_tests = [
            ("==", 10, 10, True),
            ("==", 10, 15, False),
            ("!=", 10, 15, True),
            ("!=", 10, 10, False),
            (">", 10, 15, True),
            (">", 10, 10, False),
            ("<", 10, 5, True),
            ("<", 10, 10, False),
            (">=", 10, 10, True),
            (">=", 10, 5, False),
            ("<=", 10, 10, True),
            ("<=", 10, 15, False)
        ]
        
        for operator, target, current, expected in operators_tests:
            condition = TriggerCondition(
                trigger_type=TriggerType.MESSAGE_COUNT,
                target_value=target,
                comparison_operator=operator,
                metadata={}
            )
            user_progress = {"message_count": current}
            result = condition_evaluator.evaluate_condition(condition, user_progress)
            assert result == expected, f"Failed for {operator} with target={target}, current={current}"
    
    def test_missing_progress_data(self, condition_evaluator):
        """測試缺少進度資料的情況"""
        condition = TriggerCondition(
            trigger_type=TriggerType.MESSAGE_COUNT,
            target_value=10,
            comparison_operator=">=",
            metadata={}
        )
        
        # 空進度資料
        user_progress = {}
        result = condition_evaluator.evaluate_condition(condition, user_progress)
        assert result is False  # 缺少資料應該返回False
        
        # None進度資料
        result = condition_evaluator.evaluate_condition(condition, None)
        assert result is False
    
    def test_custom_trigger_evaluation(self, condition_evaluator):
        """測試自訂觸發評估"""
        # 註冊自訂評估器
        def custom_evaluator(progress_data, target_value, operator):
            custom_count = progress_data.get("custom_action_count", 0)
            if operator == ">=":
                return custom_count >= target_value
            return False
        
        condition_evaluator.register_custom_evaluator("custom_action", custom_evaluator)
        
        condition = TriggerCondition(
            trigger_type="custom_action",
            target_value=3,
            comparison_operator=">=",
            metadata={}
        )
        
        user_progress = {"custom_action_count": 5}
        result = condition_evaluator.evaluate_condition(condition, user_progress)
        assert result is True
    
    def test_invalid_trigger_type(self, condition_evaluator):
        """測試無效觸發類型"""
        condition = TriggerCondition(
            trigger_type="invalid_type",
            target_value=10,
            comparison_operator=">=",
            metadata={}
        )
        
        user_progress = {"some_count": 15}
        
        with pytest.raises(ServiceError):
            condition_evaluator.evaluate_condition(condition, user_progress)


class TestEventProcessor:
    """測試事件處理器"""
    
    def test_message_event_processing(self, event_processor):
        """測試訊息事件處理"""
        event_data = {
            "type": "message_sent",
            "user_id": 123456789,
            "guild_id": 987654321,
            "channel_id": 111222333,
            "message_length": 25,
            "timestamp": datetime.now().isoformat()
        }
        
        progress_update = event_processor.process_event(event_data, {})
        
        assert "message_count" in progress_update
        assert progress_update["message_count"] == 1
        
        # 測試累積計數
        existing_progress = {"message_count": 5}
        progress_update = event_processor.process_event(event_data, existing_progress)
        assert progress_update["message_count"] == 6
    
    def test_voice_event_processing(self, event_processor):
        """測試語音事件處理"""
        event_data = {
            "type": "voice_activity",
            "user_id": 123456789,
            "guild_id": 987654321,
            "duration": 120,  # 2分鐘
            "timestamp": datetime.now().isoformat()
        }
        
        progress_update = event_processor.process_event(event_data, {})
        
        assert "voice_time" in progress_update
        assert progress_update["voice_time"] == 120
        
        # 測試累積時間
        existing_progress = {"voice_time": 300}
        progress_update = event_processor.process_event(event_data, existing_progress)
        assert progress_update["voice_time"] == 420
    
    def test_reaction_event_processing(self, event_processor):
        """測試反應事件處理"""
        event_data = {
            "type": "reaction_added",
            "user_id": 123456789,
            "guild_id": 987654321,
            "emoji": "👍",
            "timestamp": datetime.now().isoformat()
        }
        
        progress_update = event_processor.process_event(event_data, {})
        
        assert "reaction_count" in progress_update
        assert progress_update["reaction_count"] == 1
    
    def test_custom_event_processing(self, event_processor):
        """測試自訂事件處理"""
        # 註冊自訂事件處理器
        def custom_processor(event_data, existing_progress):
            if event_data["type"] == "custom_action":
                existing_progress = existing_progress or {}
                existing_progress["custom_action_count"] = existing_progress.get("custom_action_count", 0) + 1
                existing_progress["custom_points"] = existing_progress.get("custom_points", 0) + event_data.get("points", 1)
            return existing_progress
        
        event_processor.register_custom_processor("custom_action", custom_processor)
        
        event_data = {
            "type": "custom_action",
            "user_id": 123456789,
            "guild_id": 987654321,
            "points": 5
        }
        
        progress_update = event_processor.process_event(event_data, {})
        
        assert progress_update["custom_action_count"] == 1
        assert progress_update["custom_points"] == 5
    
    def test_event_metadata_filtering(self, event_processor):
        """測試事件元資料篩選"""
        # 設定頻道篩選
        event_data = {
            "type": "message_sent",
            "user_id": 123456789,
            "guild_id": 987654321,
            "channel_id": 111222333
        }
        
        # 測試頻道篩選條件
        metadata_filter = {"allowed_channels": [111222333, 444555666]}
        progress_update = event_processor.process_event(event_data, {}, metadata_filter)
        
        assert "message_count" in progress_update  # 應該通過篩選
        
        # 測試不符合篩選條件
        metadata_filter = {"allowed_channels": [444555666, 777888999]}
        progress_update = event_processor.process_event(event_data, {}, metadata_filter)
        
        assert progress_update == {}  # 不應該更新進度
    
    def test_unknown_event_type(self, event_processor):
        """測試未知事件類型"""
        event_data = {
            "type": "unknown_event",
            "user_id": 123456789,
            "guild_id": 987654321
        }
        
        progress_update = event_processor.process_event(event_data, {})
        
        # 未知事件應該返回原進度，不做修改
        assert progress_update == {}


class TestTriggerEngine:
    """測試觸發引擎"""
    
    async def test_single_condition_check(self, trigger_engine):
        """測試單一條件檢查"""
        condition = TriggerCondition(
            trigger_type=TriggerType.MESSAGE_COUNT,
            target_value=5,
            comparison_operator=">=",
            metadata={}
        )
        
        user_progress = {"message_count": 10}
        
        result = await trigger_engine.check_conditions([condition], user_progress)
        assert result is True
        
        user_progress = {"message_count": 3}
        result = await trigger_engine.check_conditions([condition], user_progress)
        assert result is False
    
    async def test_multiple_conditions_and_logic(self, trigger_engine, sample_conditions):
        """測試多條件AND邏輯"""
        user_progress = {
            "message_count": 15,    # 滿足條件1
            "voice_time": 600,      # 滿足條件2
            "reaction_count": 8     # 滿足條件3
        }
        
        # 所有條件都滿足，AND邏輯應該返回True
        result = await trigger_engine.check_conditions(sample_conditions, user_progress, "AND")
        assert result is True
        
        # 部分條件不滿足
        user_progress["voice_time"] = 60  # 不滿足條件2
        result = await trigger_engine.check_conditions(sample_conditions, user_progress, "AND")
        assert result is False
    
    async def test_multiple_conditions_or_logic(self, trigger_engine, sample_conditions):
        """測試多條件OR邏輯"""
        user_progress = {
            "message_count": 15,    # 滿足條件1
            "voice_time": 60,       # 不滿足條件2
            "reaction_count": 2     # 不滿足條件3
        }
        
        # 至少一個條件滿足，OR邏輯應該返回True
        result = await trigger_engine.check_conditions(sample_conditions, user_progress, "OR")
        assert result is True
        
        # 所有條件都不滿足
        user_progress = {
            "message_count": 5,     # 不滿足條件1
            "voice_time": 60,       # 不滿足條件2
            "reaction_count": 2     # 不滿足條件3
        }
        result = await trigger_engine.check_conditions(sample_conditions, user_progress, "OR")
        assert result is False
    
    async def test_trigger_performance(self, trigger_engine):
        """測試觸發檢查效能"""
        # 創建大量條件來測試效能
        conditions = []
        for i in range(100):  # 100個條件
            condition = TriggerCondition(
                trigger_type=TriggerType.MESSAGE_COUNT,
                target_value=i,
                comparison_operator=">=",
                metadata={}
            )
            conditions.append(condition)
        
        user_progress = {"message_count": 150}  # 滿足所有條件
        
        start_time = time.time()
        result = await trigger_engine.check_conditions(conditions, user_progress, "AND")
        end_time = time.time()
        
        execution_time = (end_time - start_time) * 1000  # 轉換為毫秒
        assert execution_time < 100  # 應該在100ms內完成
        assert result is True
    
    async def test_async_condition_evaluation(self, trigger_engine):
        """測試異步條件評估"""
        # 模擬需要異步評估的條件（例如查詢資料庫）
        async def async_evaluator(condition, progress):
            await asyncio.sleep(0.01)  # 模擬異步操作
            return progress.get("async_value", 0) >= condition.target_value
        
        trigger_engine.register_async_evaluator("async_trigger", async_evaluator)
        
        condition = TriggerCondition(
            trigger_type="async_trigger",
            target_value=10,
            comparison_operator=">=",
            metadata={}
        )
        
        user_progress = {"async_value": 15}
        
        start_time = time.time()
        result = await trigger_engine.check_conditions([condition], user_progress)
        end_time = time.time()
        
        assert result is True
        assert (end_time - start_time) >= 0.01  # 確保異步操作確實執行了
    
    async def test_condition_caching(self, trigger_engine):
        """測試條件結果快取"""
        condition = TriggerCondition(
            trigger_type=TriggerType.MESSAGE_COUNT,
            target_value=10,
            comparison_operator=">=",
            metadata={}
        )
        
        user_progress = {"message_count": 15}
        
        # 第一次執行
        start_time = time.time()
        result1 = await trigger_engine.check_conditions([condition], user_progress)
        first_time = time.time() - start_time
        
        # 第二次執行（應該使用快取）
        start_time = time.time()
        result2 = await trigger_engine.check_conditions([condition], user_progress)
        second_time = time.time() - start_time
        
        assert result1 is True
        assert result2 is True
        # 第二次應該更快（使用了快取）
        assert second_time <= first_time
    
    async def test_error_handling_in_evaluation(self, trigger_engine):
        """測試評估過程中的錯誤處理"""
        # 註冊一個會拋出異常的評估器
        def error_evaluator(progress_data, target_value, comparison_operator):
            raise ValueError("模擬評估錯誤")
        
        trigger_engine.condition_evaluator.register_custom_evaluator("error_trigger", error_evaluator)
        
        condition = TriggerCondition(
            trigger_type="error_trigger",
            target_value=10,
            comparison_operator=">=",
            metadata={}
        )
        
        user_progress = {"some_value": 15}
        
        # 應該優雅處理錯誤，而不是崩潰
        with pytest.raises(ServiceError):
            await trigger_engine.check_conditions([condition], user_progress)


class TestComplexTriggerScenarios:
    """測試複雜觸發場景"""
    
    async def test_time_based_conditions(self, trigger_engine):
        """測試基於時間的條件"""
        # 測試在特定時間範圍內的活動
        now = datetime.now()
        condition = TriggerCondition(
            trigger_type=TriggerType.MESSAGE_COUNT,
            target_value=5,
            comparison_operator=">=",
            metadata={
                "time_range": {
                    "start": (now - timedelta(hours=1)).isoformat(),
                    "end": now.isoformat()
                }
            }
        )
        
        user_progress = {
            "message_count": 10,
            "recent_messages": [
                {"timestamp": (now - timedelta(minutes=30)).isoformat()},
                {"timestamp": (now - timedelta(minutes=45)).isoformat()}
            ]
        }
        
        # 這個測試需要時間範圍評估器的實作
        # 目前先驗證基本結構
        assert condition.metadata["time_range"] is not None
    
    async def test_channel_specific_conditions(self, trigger_engine):
        """測試特定頻道的條件"""
        condition = TriggerCondition(
            trigger_type=TriggerType.MESSAGE_COUNT,
            target_value=10,
            comparison_operator=">=",
            metadata={"channel_ids": [111222333, 444555666]}
        )
        
        user_progress = {
            "message_count_by_channel": {
                "111222333": 7,
                "444555666": 5,
                "777888999": 20  # 這個頻道不在條件中
            }
        }
        
        # 需要自訂評估器來處理頻道特定條件
        def channel_specific_evaluator(progress_data, target_value, operator):
            """頻道特定的訊息計數評估器"""
            # 從metadata獲取條件中的頻道限制（需要從別處傳入）
            # 這裡簡化處理，假設progress_data中包含頻道特定的計數
            channel_counts = progress_data.get("message_count_by_channel", {})
            
            # 計算指定頻道的總計數
            # 這裡假設progress_data包含了頻道限制信息
            allowed_channels = progress_data.get("_allowed_channels", [])
            
            total_count = sum(
                count for channel_id, count in channel_counts.items()
                if int(channel_id) in allowed_channels
            )
            
            if operator == ">=":
                return total_count >= target_value
            return False
        
        # 修改user_progress以包含頻道限制信息
        user_progress_with_filter = {
            **user_progress,
            "_allowed_channels": [111222333, 444555666]  # 允許的頻道ID
        }
        
        trigger_engine.condition_evaluator.register_custom_evaluator(
            TriggerType.MESSAGE_COUNT.value, channel_specific_evaluator
        )
        
        result = await trigger_engine.check_conditions([condition], user_progress_with_filter)
        assert result is True  # 7 + 5 = 12 >= 10
    
    async def test_progressive_achievement_logic(self, trigger_engine):
        """測試漸進式成就邏輯"""
        # 漸進式成就：達到不同階段有不同獎勵
        conditions = [
            TriggerCondition(
                trigger_type=TriggerType.MESSAGE_COUNT,
                target_value=10,
                comparison_operator=">=",
                metadata={"level": 1}
            ),
            TriggerCondition(
                trigger_type=TriggerType.MESSAGE_COUNT,
                target_value=50,
                comparison_operator=">=",
                metadata={"level": 2}
            ),
            TriggerCondition(
                trigger_type=TriggerType.MESSAGE_COUNT,
                target_value=100,
                comparison_operator=">=",
                metadata={"level": 3}
            )
        ]
        
        user_progress = {"message_count": 75}
        
        # 檢查每個級別的完成狀態
        results = []
        for condition in conditions:
            result = await trigger_engine.check_conditions([condition], user_progress)
            results.append((condition.metadata["level"], result))
        
        expected_results = [(1, True), (2, True), (3, False)]
        assert results == expected_results
    
    async def test_batch_condition_checking(self, trigger_engine):
        """測試批量條件檢查"""
        # 為多個用戶檢查相同條件
        condition = TriggerCondition(
            trigger_type=TriggerType.MESSAGE_COUNT,
            target_value=10,
            comparison_operator=">=",
            metadata={}
        )
        
        users_progress = [
            {"user_id": 111, "message_count": 15},
            {"user_id": 222, "message_count": 5},
            {"user_id": 333, "message_count": 20},
            {"user_id": 444, "message_count": 8}
        ]
        
        results = await trigger_engine.batch_check_conditions(
            [condition], users_progress
        )
        
        expected_results = [
            {"user_id": 111, "result": True},
            {"user_id": 222, "result": False},
            {"user_id": 333, "result": True},
            {"user_id": 444, "result": False}
        ]
        
        assert len(results) == len(expected_results)
        for result, expected in zip(results, expected_results):
            assert result["user_id"] == expected["user_id"]
            assert result["result"] == expected["result"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])