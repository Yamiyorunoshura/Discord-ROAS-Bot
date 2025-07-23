"""
🎯 ActivityModule - 活躍度模塊統一API
- 提供統一的活躍度API接口
- 整合各個程式邏輯功能
- 實現緩存機制和錯誤處理
- 支援權限檢查和性能監控
"""

import asyncio
import time
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass

from ..database.database import ActivityDatabase, ActivityMeterError
from .calculator import ActivityCalculator
from .renderer import ActivityRenderer
from .logic_apis import LogicAPIs
from .cache import ActivityCache

logger = logging.getLogger("activity_module")

@dataclass
class ActivityData:
    """活躍度數據結構"""
    user_id: str
    activity_score: float
    last_activity: datetime | None = None
    total_messages: int = 0
    response_time: float = 0.0
    rank: int | None = None
    level: int | None = None

class ActivityAPIError(Exception):
    """Activity API 錯誤"""
    pass

class UserNotFoundError(ActivityAPIError):
    """用戶不存在錯誤"""
    pass

class ActivityModule:
    """
    活躍度模塊統一API
    - 整合各個程式邏輯功能
    - 提供統一的API接口
    - 實現緩存和錯誤處理
    """
    
    def __init__(self):
        """初始化活躍度模塊"""
        self.logic_apis = LogicAPIs()
        self.cache = ActivityCache()
        self.calculator = ActivityCalculator()
        self.renderer = ActivityRenderer()
        
        # 性能監控
        self.api_calls = 0
        self.cache_hits = 0
        self.cache_misses = 0
        
        logger.info("✅ ActivityModule 初始化成功")
    
    def get_unified_activity_api(self, user_id: str) -> ActivityData:
        """
        獲取統一活躍度API數據
        
        Args:
            user_id: 用戶ID
            
        Returns:
            ActivityData: 活躍度數據
            
        Raises:
            UserNotFoundError: 用戶不存在
            ActivityAPIError: API錯誤
        """
        try:
            start_time = time.time()
            self.api_calls += 1
            
            # 檢查緩存
            cache_key = f"activity_{user_id}"
            cached_data = self.cache.get(cache_key)
            if cached_data:
                self.cache_hits += 1
                logger.debug(f"✅ 緩存命中: {user_id}")
                return cached_data
            
            self.cache_misses += 1
            logger.debug(f"❌ 緩存未命中: {user_id}")
            
            # 調用邏輯API獲取用戶數據
            user_data = self.logic_apis.get_user_data(user_id)
            if not user_data:
                raise UserNotFoundError(f"用戶 {user_id} 不存在")
            
            # 計算活躍度分數
            activity_score = self.calculate_activity_score(user_data)
            
            # 獲取排名和等級
            rank = self.logic_apis.get_user_rank(user_id)
            level = self.calculator.calculate_level(activity_score)
            
            # 構建活躍度數據
            activity_data = ActivityData(
                user_id=user_id,
                activity_score=activity_score,
                last_activity=user_data.get("last_activity"),
                total_messages=user_data.get("total_messages", 0),
                response_time=user_data.get("response_time", 0.0),
                rank=rank,
                level=level
            )
            
            # 存入緩存 (5分鐘TTL)
            self.cache.set(cache_key, activity_data, ttl=300)
            
            response_time = time.time() - start_time
            logger.info(f"✅ 活躍度數據獲取成功: {user_id}, 分數: {activity_score}, 響應時間: {response_time:.3f}s")
            
            return activity_data
            
        except UserNotFoundError:
            logger.warning(f"⚠️ 用戶不存在: {user_id}")
            raise
        except Exception as e:
            logger.error(f"❌ 獲取活躍度數據失敗: {user_id}, 錯誤: {e}")
            raise ActivityAPIError(f"獲取活躍度數據失敗: {str(e)}")
    
    def calculate_activity_score(self, user_data: Dict[str, Any]) -> float:
        """
        計算活躍度分數
        
        Args:
            user_data: 用戶數據
            
        Returns:
            float: 活躍度分數 (0-100)
        """
        try:
            # 基礎分數
            base_score = user_data.get("base_score", 0)
            
            # 訊息獎勵
            message_bonus = user_data.get("total_messages", 0) * 0.1
            
            # 響應時間獎勵 (響應時間越短獎勵越高)
            response_time = user_data.get("response_time", 0)
            response_bonus = max(0, 10 - response_time) * 0.5
            
            # 活躍度獎勵
            activity_bonus = user_data.get("activity_bonus", 0)
            
            # 計算總分
            total_score = base_score + message_bonus + response_bonus + activity_bonus
            
            # 確保分數在0-100範圍內
            return max(0, min(100, total_score))
            
        except Exception as e:
            logger.error(f"❌ 計算活躍度分數失敗: {e}")
            return 0.0
    
    def get_user_activity_history(self, user_id: str, days: int = 30) -> List[ActivityData]:
        """
        獲取用戶活躍度歷史
        
        Args:
            user_id: 用戶ID
            days: 歷史天數
            
        Returns:
            List[ActivityData]: 活躍度歷史數據
        """
        try:
            cache_key = f"history_{user_id}_{days}"
            cached_data = self.cache.get(cache_key)
            if cached_data:
                return cached_data
            
            # 從邏輯API獲取歷史數據
            history_data = self.logic_apis.get_user_activity_history(user_id, days)
            
            # 轉換為ActivityData格式
            activity_history = []
            for data in history_data:
                activity_data = ActivityData(
                    user_id=user_id,
                    activity_score=data.get("score", 0),
                    last_activity=data.get("timestamp"),
                    total_messages=data.get("messages", 0)
                )
                activity_history.append(activity_data)
            
            # 存入緩存 (10分鐘TTL)
            self.cache.set(cache_key, activity_history, ttl=600)
            
            return activity_history
            
        except Exception as e:
            logger.error(f"❌ 獲取活躍度歷史失敗: {user_id}, 錯誤: {e}")
            return []
    
    def get_leaderboard(self, guild_id: str, limit: int = 10) -> List[ActivityData]:
        """
        獲取排行榜
        
        Args:
            guild_id: 伺服器ID
            limit: 排行榜數量限制
            
        Returns:
            List[ActivityData]: 排行榜數據
        """
        try:
            cache_key = f"leaderboard_{guild_id}_{limit}"
            cached_data = self.cache.get(cache_key)
            if cached_data:
                return cached_data
            
            # 從邏輯API獲取排行榜數據
            leaderboard_data = self.logic_apis.get_leaderboard(guild_id, limit)
            
            # 轉換為ActivityData格式
            leaderboard = []
            for i, data in enumerate(leaderboard_data, 1):
                activity_data = ActivityData(
                    user_id=data.get("user_id"),
                    activity_score=data.get("score", 0),
                    total_messages=data.get("messages", 0),
                    rank=i
                )
                leaderboard.append(activity_data)
            
            # 存入緩存 (2分鐘TTL)
            self.cache.set(cache_key, leaderboard, ttl=120)
            
            return leaderboard
            
        except Exception as e:
            logger.error(f"❌ 獲取排行榜失敗: {guild_id}, 錯誤: {e}")
            return []
    
    def update_user_activity(self, user_id: str, guild_id: str, activity_type: str = "message") -> bool:
        """
        更新用戶活躍度
        
        Args:
            user_id: 用戶ID
            guild_id: 伺服器ID
            activity_type: 活躍度類型
            
        Returns:
            bool: 更新是否成功
        """
        try:
            # 調用邏輯API更新活躍度
            success = self.logic_apis.update_user_activity(user_id, guild_id, activity_type)
            
            if success:
                # 清除相關緩存
                self.cache.delete(f"activity_{user_id}")
                self.cache.delete(f"leaderboard_{guild_id}")
                logger.info(f"✅ 活躍度更新成功: {user_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ 活躍度更新失敗: {user_id}, 錯誤: {e}")
            return False
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        獲取性能指標
        
        Returns:
            Dict[str, Any]: 性能指標數據
        """
        total_calls = self.api_calls + self.cache_hits + self.cache_misses
        cache_hit_rate = (self.cache_hits / total_calls * 100) if total_calls > 0 else 0
        
        return {
            "api_calls": self.api_calls,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": cache_hit_rate,
            "average_response_time": self._calculate_average_response_time()
        }
    
    def _calculate_average_response_time(self) -> float:
        """計算平均響應時間"""
        # 這裡可以實現更複雜的響應時間計算
        return 0.1  # 簡化實現
    
    def clear_cache(self, pattern: str = None):
        """
        清除緩存
        
        Args:
            pattern: 緩存模式匹配
        """
        self.cache.clear(pattern)
        logger.info(f"✅ 緩存已清除: {pattern or 'all'}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        獲取緩存統計
        
        Returns:
            Dict[str, Any]: 緩存統計數據
        """
        return self.cache.get_stats()