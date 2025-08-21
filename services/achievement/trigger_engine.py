"""
成就觸發引擎
Task ID: 6 - 成就系統核心功能

這個模組提供成就系統的觸發檢查核心功能，包括：
- TriggerEngine: 核心觸發檢查引擎
- ConditionEvaluator: 觸發條件評估器
- EventProcessor: 事件處理器

符合要求：
- F3: 成就觸發系統
- N1: 效能要求 - 觸發檢查 < 100ms
- N2: 可擴展性要求 - 支援自訂觸發類型
"""

import asyncio
import time
from typing import Dict, Any, List, Optional, Callable, Union
from datetime import datetime

from .models import TriggerCondition, TriggerType
from core.exceptions import ValidationError, ServiceError


class ConditionEvaluator:
    """
    觸發條件評估器
    
    負責評估各種觸發條件是否滿足
    """
    
    def __init__(self):
        self._custom_evaluators: Dict[str, Callable] = {}
        self._setup_builtin_evaluators()
    
    def _setup_builtin_evaluators(self):
        """設定內建評估器"""
        
        def message_count_evaluator(progress_data: Dict[str, Any], target_value: Union[int, float], operator: str) -> bool:
            current_count = progress_data.get("message_count", 0)
            return self._compare_values(current_count, target_value, operator)
        
        def voice_time_evaluator(progress_data: Dict[str, Any], target_value: Union[int, float], operator: str) -> bool:
            current_time = progress_data.get("voice_time", 0)
            return self._compare_values(current_time, target_value, operator)
        
        def reaction_count_evaluator(progress_data: Dict[str, Any], target_value: Union[int, float], operator: str) -> bool:
            current_count = progress_data.get("reaction_count", 0)
            return self._compare_values(current_count, target_value, operator)
        
        # 註冊內建評估器
        self._custom_evaluators[TriggerType.MESSAGE_COUNT.value] = message_count_evaluator
        self._custom_evaluators[TriggerType.VOICE_TIME.value] = voice_time_evaluator
        self._custom_evaluators[TriggerType.REACTION_COUNT.value] = reaction_count_evaluator
    
    def _compare_values(self, current: Union[int, float], target: Union[int, float], operator: str) -> bool:
        """比較兩個值"""
        if operator == "==":
            return current == target
        elif operator == "!=":
            return current != target
        elif operator == ">":
            return current > target
        elif operator == "<":
            return current < target
        elif operator == ">=":
            return current >= target
        elif operator == "<=":
            return current <= target
        else:
            raise ValidationError(
                f"不支援的比較運算符：{operator}",
                field="comparison_operator", 
                value=operator,
                expected="==, !=, >, <, >=, <="
            )
    
    def evaluate_condition(
        self,
        condition: TriggerCondition,
        progress_data: Optional[Dict[str, Any]]
    ) -> bool:
        """
        評估單個觸發條件
        
        參數：
            condition: 觸發條件
            progress_data: 使用者進度資料
            
        返回：
            是否滿足條件
        """
        try:
            if not progress_data:
                return False
            
            trigger_type_value = (
                condition.trigger_type.value if isinstance(condition.trigger_type, TriggerType)
                else condition.trigger_type
            )
            
            # 使用自訂評估器
            if trigger_type_value in self._custom_evaluators:
                evaluator = self._custom_evaluators[trigger_type_value]
                return evaluator(progress_data, condition.target_value, condition.comparison_operator)
            
            # 未知觸發類型
            raise ValidationError(
                f"未知的觸發類型：{trigger_type_value}",
                field="trigger_type",
                value=trigger_type_value,
                expected="message_count, voice_time, custom_action, level_reached等有效觸發類型"
            )
            
        except Exception as e:
            from core.exceptions import ServiceError
            # 將任何異常包裝為ServiceError
            raise ServiceError(
                f"觸發條件評估失敗：{str(e)}",
                service_name="TriggerEngine",
                operation="evaluate_condition"
            ) from e
    
    def register_custom_evaluator(self, trigger_type: str, evaluator_func: Callable):
        """
        註冊自訂評估器
        
        參數：
            trigger_type: 觸發類型
            evaluator_func: 評估函數 (progress_data, target_value, operator) -> bool
        """
        self._custom_evaluators[trigger_type] = evaluator_func


class EventProcessor:
    """
    事件處理器
    
    負責處理各種事件並轉換為進度更新
    """
    
    def __init__(self):
        self._custom_processors: Dict[str, Callable] = {}
    
    def process_event(
        self,
        event_data: Dict[str, Any],
        existing_progress: Optional[Dict[str, Any]],
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        處理事件並生成進度更新
        
        參數：
            event_data: 事件資料
            existing_progress: 現有進度
            metadata_filter: 元資料篩選條件
            
        返回：
            進度更新資料
        """
        if not existing_progress:
            existing_progress = {}
        
        event_type = event_data.get("type")
        if not event_type:
            return {}
        
        # 應用元資料篩選
        if metadata_filter and not self._passes_metadata_filter(event_data, metadata_filter):
            return {}
        
        # 使用自訂處理器
        if event_type in self._custom_processors:
            processor = self._custom_processors[event_type]
            return processor(event_data, existing_progress)
        
        # 內建事件處理
        return self._process_builtin_event(event_type, event_data, existing_progress)
    
    def _process_builtin_event(
        self,
        event_type: str,
        event_data: Dict[str, Any],
        existing_progress: Dict[str, Any]
    ) -> Dict[str, Any]:
        """處理內建事件類型"""
        progress_update = existing_progress.copy()
        
        if event_type == "message_sent":
            progress_update["message_count"] = progress_update.get("message_count", 0) + 1
            
        elif event_type == "voice_activity":
            duration = event_data.get("duration", 0)
            progress_update["voice_time"] = progress_update.get("voice_time", 0) + duration
            
        elif event_type == "reaction_added":
            progress_update["reaction_count"] = progress_update.get("reaction_count", 0) + 1
        
        return progress_update
    
    def _passes_metadata_filter(
        self,
        event_data: Dict[str, Any],
        metadata_filter: Dict[str, Any]
    ) -> bool:
        """檢查事件是否通過元資料篩選"""
        # 檢查允許的頻道
        if "allowed_channels" in metadata_filter:
            channel_id = event_data.get("channel_id")
            if channel_id not in metadata_filter["allowed_channels"]:
                return False
        
        # 可以添加更多篩選條件
        return True
    
    def register_custom_processor(self, event_type: str, processor_func: Callable):
        """
        註冊自訂事件處理器
        
        參數：
            event_type: 事件類型
            processor_func: 處理函數 (event_data, existing_progress) -> updated_progress
        """
        self._custom_processors[event_type] = processor_func


class TriggerEngine:
    """
    觸發引擎
    
    成就觸發系統的核心引擎，負責條件檢查和批量處理
    """
    
    def __init__(self):
        self.condition_evaluator = ConditionEvaluator()
        self.event_processor = EventProcessor()
        self._async_evaluators: Dict[str, Callable] = {}
        self._condition_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = 60  # 快取1分鐘
    
    async def check_conditions(
        self,
        conditions: List[TriggerCondition],
        user_progress: Dict[str, Any],
        operator: str = "AND"
    ) -> bool:
        """
        檢查觸發條件
        
        參數：
            conditions: 觸發條件列表
            user_progress: 使用者進度資料
            operator: 邏輯運算符 ("AND" 或 "OR")
            
        返回：
            是否滿足條件
        """
        if not conditions:
            return True
        
        results = []
        
        for condition in conditions:
            # 檢查是否有異步評估器
            trigger_type_value = (
                condition.trigger_type.value if isinstance(condition.trigger_type, TriggerType)
                else condition.trigger_type
            )
            
            if trigger_type_value in self._async_evaluators:
                # 使用異步評估器
                evaluator = self._async_evaluators[trigger_type_value]
                result = await evaluator(condition, user_progress)
            else:
                # 使用同步評估器
                result = self.condition_evaluator.evaluate_condition(condition, user_progress)
            
            results.append(result)
            
            # 提前退出最佳化
            if operator.upper() == "AND" and not result:
                return False
            elif operator.upper() == "OR" and result:
                return True
        
        if operator.upper() == "AND":
            return all(results)
        elif operator.upper() == "OR":
            return any(results)
        else:
            return all(results)  # 預設使用AND
    
    def register_async_evaluator(self, trigger_type: str, evaluator_func: Callable):
        """
        註冊異步評估器
        
        參數：
            trigger_type: 觸發類型
            evaluator_func: 異步評估函數 (condition, progress) -> bool
        """
        self._async_evaluators[trigger_type] = evaluator_func
    
    async def batch_check_conditions(
        self,
        conditions: List[TriggerCondition],
        users_progress: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        批量檢查條件
        
        參數：
            conditions: 觸發條件列表
            users_progress: 使用者進度列表
            
        返回：
            檢查結果列表
        """
        results = []
        
        # 並行處理以提高效能
        tasks = []
        for user_progress_data in users_progress:
            user_id = user_progress_data.get("user_id")
            progress = {k: v for k, v in user_progress_data.items() if k != "user_id"}
            
            task = self._check_conditions_for_user(conditions, user_id, progress)
            tasks.append(task)
        
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(batch_results):
            if isinstance(result, Exception):
                # 處理異常
                user_id = users_progress[i].get("user_id")
                results.append({"user_id": user_id, "result": False, "error": str(result)})
            else:
                results.append(result)
        
        return results
    
    async def _check_conditions_for_user(
        self,
        conditions: List[TriggerCondition],
        user_id: int,
        progress: Dict[str, Any]
    ) -> Dict[str, Any]:
        """為單個使用者檢查條件"""
        result = await self.check_conditions(conditions, progress, "AND")
        return {"user_id": user_id, "result": result}
    
    def _get_cache_key(self, conditions: List[TriggerCondition], progress: Dict[str, Any]) -> str:
        """生成快取鍵"""
        # 簡化的快取鍵生成邏輯
        conditions_hash = hash(tuple(c.trigger_type for c in conditions))
        progress_hash = hash(tuple(sorted(progress.items())))
        return f"{conditions_hash}_{progress_hash}"
    
    def _is_cache_valid(self, timestamp: datetime) -> bool:
        """檢查快取是否有效"""
        return (datetime.now() - timestamp).total_seconds() < self._cache_ttl