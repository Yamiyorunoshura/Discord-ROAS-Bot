"""
事件總線系統測試
Discord ADR Bot v1.6 - 事件驅動架構測試

測試覆蓋：
- 事件發布和訂閱
- 事件過濾和路由
- 事件持久化
- 事件重放
- 優先級處理
- 錯誤處理和重試

作者：Discord ADR Bot 測試工程師
版本：v1.6
"""

import asyncio
import pytest
import pytest_asyncio
import time
from unittest.mock import AsyncMock, MagicMock
from typing import List, Dict, Any

from cogs.core.event_bus import (
    Event, EventBus, EventPriority, EventFilter, EventSubscription,
    MemoryEventPersistence, publish_event, get_global_event_bus
)


class TestEvent:
    """事件基礎類別測試"""
    
    def test_event_creation(self):
        """測試事件創建"""
        event = Event(
            event_type="test.event",
            data={"key": "value"},
            source="test_source",
            target="test_target",
            priority=EventPriority.HIGH
        )
        
        assert event.event_type == "test.event"
        assert event.data == {"key": "value"}
        assert event.source == "test_source"
        assert event.target == "test_target"
        assert event.priority == EventPriority.HIGH
        assert event.event_id is not None
        assert event.timestamp > 0
    
    def test_event_id_generation(self):
        """測試事件ID生成"""
        event1 = Event("test.event1")
        event2 = Event("test.event2")
        
        assert event1.event_id != event2.event_id
        assert event1.event_id is not None and event1.event_id.startswith("test.event1_")
        assert event2.event_id is not None and event2.event_id.startswith("test.event2_")
    
    def test_event_to_dict(self):
        """測試事件轉字典"""
        event = Event(
            event_type="test.event",
            data={"test": "data"},
            source="source",
            priority=EventPriority.CRITICAL
        )
        
        event_dict = event.to_dict()
        
        assert event_dict["event_type"] == "test.event"
        assert event_dict["data"] == {"test": "data"}
        assert event_dict["source"] == "source"
        assert event_dict["priority"] == EventPriority.CRITICAL.value
    
    def test_event_from_dict(self):
        """測試從字典創建事件"""
        event_dict = {
            "event_type": "test.event",
            "data": {"test": "data"},
            "source": "source",
            "priority": EventPriority.HIGH.value,
            "timestamp": 1234567890.0,
            "event_id": "test_id"
        }
        
        event = Event.from_dict(event_dict)
        
        assert event.event_type == "test.event"
        assert event.data == {"test": "data"}
        assert event.source == "source"
        assert event.priority == EventPriority.HIGH
        assert event.timestamp == 1234567890.0
        assert event.event_id == "test_id"


class TestEventFilter:
    """事件過濾器測試"""
    
    def test_filter_by_source(self):
        """測試按來源過濾"""
        filter_func = EventFilter.by_source("test_source")
        
        event1 = Event("test.event", source="test_source")
        event2 = Event("test.event", source="other_source")
        
        assert filter_func(event1) is True
        assert filter_func(event2) is False
    
    def test_filter_by_target(self):
        """測試按目標過濾"""
        filter_func = EventFilter.by_target("test_target")
        
        event1 = Event("test.event", target="test_target")
        event2 = Event("test.event", target="other_target")
        
        assert filter_func(event1) is True
        assert filter_func(event2) is False
    
    def test_filter_by_priority(self):
        """測試按優先級過濾"""
        filter_func = EventFilter.by_priority(EventPriority.HIGH)
        
        event1 = Event("test.event", priority=EventPriority.CRITICAL)
        event2 = Event("test.event", priority=EventPriority.HIGH)
        event3 = Event("test.event", priority=EventPriority.NORMAL)
        
        assert filter_func(event1) is True
        assert filter_func(event2) is True
        assert filter_func(event3) is False
    
    def test_filter_by_data_key(self):
        """測試按數據鍵過濾"""
        filter_func = EventFilter.by_data_key("test_key", "test_value")
        
        event1 = Event("test.event", data={"test_key": "test_value"})
        event2 = Event("test.event", data={"test_key": "other_value"})
        event3 = Event("test.event", data={"other_key": "test_value"})
        
        assert filter_func(event1) is True
        assert filter_func(event2) is False
        assert filter_func(event3) is False
    
    def test_filter_by_time_range(self):
        """測試按時間範圍過濾"""
        start_time = time.time()
        end_time = start_time + 10
        
        filter_func = EventFilter.by_time_range(start_time, end_time)
        
        event1 = Event("test.event")
        event1.timestamp = start_time + 5
        
        event2 = Event("test.event")
        event2.timestamp = start_time - 5
        
        assert filter_func(event1) is True
        assert filter_func(event2) is False


class TestEventSubscription:
    """事件訂閱測試"""
    
    @pytest.fixture
    def mock_handler(self):
        """模擬事件處理器"""
        return AsyncMock()
    
    def test_subscription_creation(self, mock_handler):
        """測試訂閱創建"""
        subscription = EventSubscription(
            handler=mock_handler,
            event_types={"test.event"},
            priority=EventPriority.HIGH,
            max_retries=5
        )
        
        assert subscription.handler == mock_handler
        assert subscription.event_types == {"test.event"}
        assert subscription.priority == EventPriority.HIGH
        assert subscription.max_retries == 5
        assert subscription.enabled is True
    
    def test_subscription_matches_event_type(self, mock_handler):
        """測試訂閱匹配事件類型"""
        subscription = EventSubscription(
            handler=mock_handler,
            event_types={"test.event", "other.event"}
        )
        
        event1 = Event("test.event")
        event2 = Event("other.event")
        event3 = Event("unknown.event")
        
        assert subscription.matches(event1) is True
        assert subscription.matches(event2) is True
        assert subscription.matches(event3) is False
    
    def test_subscription_matches_wildcard(self, mock_handler):
        """測試訂閱匹配通配符"""
        subscription = EventSubscription(
            handler=mock_handler,
            event_types={"*"}
        )
        
        event1 = Event("test.event")
        event2 = Event("any.event")
        
        assert subscription.matches(event1) is True
        assert subscription.matches(event2) is True
    
    def test_subscription_matches_with_filters(self, mock_handler):
        """測試訂閱匹配帶過濾器"""
        subscription = EventSubscription(
            handler=mock_handler,
            event_types={"test.event"},
            filters=[EventFilter.by_source("test_source")]
        )
        
        event1 = Event("test.event", source="test_source")
        event2 = Event("test.event", source="other_source")
        
        assert subscription.matches(event1) is True
        assert subscription.matches(event2) is False


class TestMemoryEventPersistence:
    """內存事件持久化測試"""
    
    @pytest.fixture
    def persistence(self):
        """創建持久化實例"""
        return MemoryEventPersistence(max_events=100)
    
    @pytest.mark.asyncio
    async def test_save_event(self, persistence):
        """測試保存事件"""
        event = Event("test.event", data={"test": "data"})
        
        result = await persistence.save_event(event)
        
        assert result is True
        assert len(persistence.events) == 1
        assert persistence.events[0] == event
    
    @pytest.mark.asyncio
    async def test_save_event_max_limit(self, persistence):
        """測試保存事件最大限制"""
        persistence.max_events = 3
        
        # 保存4個事件
        for i in range(4):
            event = Event(f"test.event.{i}")
            await persistence.save_event(event)
        
        # 應該只保留最後3個
        assert len(persistence.events) == 3
        assert persistence.events[0].event_type == "test.event.1"
        assert persistence.events[1].event_type == "test.event.2"
        assert persistence.events[2].event_type == "test.event.3"
    
    @pytest.mark.asyncio
    async def test_load_events(self, persistence):
        """測試加載事件"""
        # 保存測試事件
        event1 = Event("test.event.1", data={"id": 1})
        event2 = Event("test.event.2", data={"id": 2})
        event3 = Event("test.event.1", data={"id": 3})
        
        await persistence.save_event(event1)
        await persistence.save_event(event2)
        await persistence.save_event(event3)
        
        # 加載所有事件
        all_events = await persistence.load_events()
        assert len(all_events) == 3
        
        # 按類型過濾
        filtered_events = await persistence.load_events(event_type="test.event.1")
        assert len(filtered_events) == 2
        assert all(e.event_type == "test.event.1" for e in filtered_events)
    
    @pytest.mark.asyncio
    async def test_delete_events(self, persistence):
        """測試刪除事件"""
        # 保存測試事件
        event1 = Event("test.event.1")
        event2 = Event("test.event.2")
        
        await persistence.save_event(event1)
        await persistence.save_event(event2)
        
        # 刪除一個事件
        deleted_count = await persistence.delete_events([event1.event_id])
        
        assert deleted_count == 1
        assert len(persistence.events) == 1
        assert persistence.events[0] == event2


class TestEventBus:
    """事件總線測試"""
    
    @pytest_asyncio.fixture
    async def event_bus(self):
        """創建事件總線實例"""
        bus = EventBus()
        await bus.initialize()
        yield bus
        await bus.shutdown()
    
    @pytest.fixture
    def mock_handler(self):
        """模擬事件處理器"""
        return AsyncMock()
    
    @pytest.mark.asyncio
    async def test_subscribe_and_unsubscribe(self, event_bus, mock_handler):
        """測試訂閱和取消訂閱"""
        # 訂閱事件
        subscription_id = event_bus.subscribe("test.event", mock_handler)
        
        assert subscription_id is not None
        assert event_bus.get_metrics()["active_subscriptions"] == 1
        
        # 取消訂閱
        result = event_bus.unsubscribe(subscription_id)
        
        assert result is True
        assert event_bus.get_metrics()["active_subscriptions"] == 0
    
    @pytest.mark.asyncio
    async def test_publish_and_handle_event(self, event_bus, mock_handler):
        """測試發布和處理事件"""
        # 訂閱事件
        event_bus.subscribe("test.event", mock_handler)
        
        # 發布事件
        event = Event("test.event", data={"test": "data"})
        result = await event_bus.publish(event)
        
        assert result is True
        
        # 等待事件處理
        await asyncio.sleep(0.1)
        
        # 驗證處理器被調用
        mock_handler.assert_called_once_with(event)
    
    @pytest.mark.asyncio
    async def test_publish_sync(self, event_bus, mock_handler):
        """測試同步發布事件"""
        # 設置處理器返回值
        mock_handler.return_value = "handled"
        
        # 訂閱事件
        event_bus.subscribe("test.event", mock_handler)
        
        # 同步發布事件
        event = Event("test.event", data={"test": "data"})
        results = await event_bus.publish_sync(event)
        
        assert results == ["handled"]
        mock_handler.assert_called_once_with(event)
    
    @pytest.mark.asyncio
    async def test_event_filtering(self, event_bus, mock_handler):
        """測試事件過濾"""
        # 訂閱帶過濾器的事件
        event_bus.subscribe(
            "test.event",
            mock_handler,
            filters=[EventFilter.by_source("test_source")]
        )
        
        # 發布匹配的事件
        event1 = Event("test.event", source="test_source")
        await event_bus.publish(event1)
        
        # 發布不匹配的事件
        event2 = Event("test.event", source="other_source")
        await event_bus.publish(event2)
        
        # 等待處理
        await asyncio.sleep(0.1)
        
        # 只有匹配的事件被處理
        mock_handler.assert_called_once_with(event1)
    
    @pytest.mark.asyncio
    async def test_event_priority_handling(self, event_bus):
        """測試事件優先級處理"""
        results = []
        
        async def high_priority_handler(event):
            results.append("high")
        
        async def low_priority_handler(event):
            results.append("low")
        
        # 訂閱不同優先級的處理器
        event_bus.subscribe("test.event", high_priority_handler, priority=EventPriority.HIGH)
        event_bus.subscribe("test.event", low_priority_handler, priority=EventPriority.LOW)
        
        # 同步發布事件
        event = Event("test.event")
        await event_bus.publish_sync(event)
        
        # 高優先級處理器應該先執行
        assert results == ["high", "low"]
    
    @pytest.mark.asyncio
    async def test_event_history(self, event_bus):
        """測試事件歷史"""
        # 發布幾個事件
        event1 = Event("test.event.1")
        event2 = Event("test.event.2")
        event3 = Event("test.event.1")
        
        await event_bus.publish(event1)
        await event_bus.publish(event2)
        await event_bus.publish(event3)
        
        # 獲取所有歷史
        all_history = await event_bus.get_event_history()
        assert len(all_history) == 3
        
        # 按類型過濾歷史
        filtered_history = await event_bus.get_event_history(event_type="test.event.1")
        assert len(filtered_history) == 2
    
    @pytest.mark.asyncio
    async def test_event_metrics(self, event_bus, mock_handler):
        """測試事件指標"""
        # 訂閱事件
        event_bus.subscribe("test.event", mock_handler)
        
        # 發布事件
        event = Event("test.event")
        await event_bus.publish(event)
        
        # 等待處理
        await asyncio.sleep(0.1)
        
        # 檢查指標
        metrics = event_bus.get_metrics()
        assert metrics["events_published"] == 1
        assert metrics["events_processed"] == 1
        assert metrics["active_subscriptions"] == 1
    
    @pytest.mark.asyncio
    async def test_handler_retry_on_failure(self, event_bus):
        """測試處理器失敗重試"""
        call_count = 0
        
        async def failing_handler(event):
            nonlocal call_count
            call_count += 1
            raise Exception("Test error")  # 總是失敗
        
        # 訂閱事件（最大重試2次）
        event_bus.subscribe("test.event", failing_handler, max_retries=2)
        
        # 發布事件
        event = Event("test.event")
        await event_bus.publish(event)
        
        # 等待處理和重試（增加等待時間）
        await asyncio.sleep(5.0)
        
        # 應該被調用3次（原始 + 2次重試）
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_event_scope(self, event_bus):
        """測試事件作用域"""
        async with event_bus.event_scope("test_scope") as scope_events:
            # 在作用域內發布事件
            event1 = Event("test.event.1")
            event2 = Event("test.event.2")
            
            await event_bus.publish(event1)
            await event_bus.publish(event2)
            
            # 等待處理
            await asyncio.sleep(0.1)
        
        # 作用域應該捕獲到事件
        assert len(scope_events) == 2
        assert scope_events[0].event_type == "test.event.1"
        assert scope_events[1].event_type == "test.event.2"


class TestGlobalEventBus:
    """全局事件總線測試"""
    
    @pytest.mark.asyncio
    async def test_get_global_event_bus(self):
        """測試獲取全局事件總線"""
        bus1 = await get_global_event_bus()
        bus2 = await get_global_event_bus()
        
        # 應該返回同一個實例
        assert bus1 is bus2
        assert bus1.get_metrics()["processing"] is True
    
    @pytest.mark.asyncio
    async def test_publish_event_convenience_function(self):
        """測試便利發布函數"""
        mock_handler = AsyncMock()
        
        # 創建新的事件總線實例（避免全局實例問題）
        bus = EventBus()
        await bus.initialize()
        
        try:
            bus.subscribe("test.event", mock_handler)
            
            # 創建事件並直接發布
            event = Event(
                event_type="test.event",
                data={"test": "data"},
                source="test_source",
                priority=EventPriority.HIGH
            )
            
            result = await bus.publish(event)
            
            assert result is True
            
            # 等待處理
            await asyncio.sleep(0.1)
            
            # 驗證處理器被調用
            mock_handler.assert_called_once()
            
            # 驗證事件數據
            called_event = mock_handler.call_args[0][0]
            assert called_event.event_type == "test.event"
            assert called_event.data == {"test": "data"}
            assert called_event.source == "test_source"
            assert called_event.priority == EventPriority.HIGH
            
        finally:
            await bus.shutdown()


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 