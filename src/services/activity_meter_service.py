"""
Activity Meter Service for the new architecture
Task ID: T2 - App architecture baseline and scaffolding

This module provides activity tracking and measurement functionality.
It will integrate with the existing activity meter system.
"""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import asyncio


class ActivityMeterService:
    """
    Activity meter service for tracking user activity
    
    Provides functionality for:
    - Recording user activity events
    - Calculating activity summaries
    - Activity-based achievements integration
    """
    
    def __init__(self):
        """Initialize the activity meter service"""
        self.service_name = "ActivityMeterService"
        self._initialized = False
        self._db_connection = None
        self._activity_cache = {}  # 簡單的活動快取
        
    async def initialize(self) -> None:
        """Initialize the service and its dependencies"""
        if self._initialized:
            return
            
        # 初始化與現有活動計量服務的整合
        try:
            # 這裡可以初始化資料庫連接、載入設定等
            # 目前先建立基本結構
            self._activity_cache = {}
            print(f"{self.service_name} 已成功初始化")
            self._initialized = True
        except Exception as e:
            print(f"{self.service_name} 初始化失敗: {e}")
            raise
        
    async def shutdown(self) -> None:
        """Cleanup service resources"""
        self._initialized = False
        
    async def record_activity(self, user_id: int, guild_id: int, activity_type: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Record a user activity event
        
        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID
            activity_type: Type of activity (message, reaction, voice, etc.)
            metadata: Additional activity metadata
            
        Returns:
            bool: True if activity was recorded successfully
        """
        if not self._initialized:
            raise RuntimeError("Service not initialized")
            
        # 實作活動記錄邏輯
        activity_key = f"{user_id}_{guild_id}"
        current_time = datetime.now()
        
        # 建立活動記錄
        activity_record = {
            "user_id": user_id,
            "guild_id": guild_id,
            "activity_type": activity_type,
            "timestamp": current_time,
            "metadata": metadata or {}
        }
        
        # 將記錄存入快取（在生產環境中應該存入資料庫）
        if activity_key not in self._activity_cache:
            self._activity_cache[activity_key] = []
        
        self._activity_cache[activity_key].append(activity_record)
        
        # 限制快取大小，保留最近100條記錄
        if len(self._activity_cache[activity_key]) > 100:
            self._activity_cache[activity_key] = self._activity_cache[activity_key][-100:]
        
        return True
        
    async def get_activity_summary(self, user_id: int, guild_id: int, days: int = 30) -> Dict[str, Any]:
        """
        Get activity summary for a user
        
        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID
            days: Number of days to include in summary
            
        Returns:
            Activity summary data
        """
        if not self._initialized:
            raise RuntimeError("Service not initialized")
            
        # 實作活動摘要邏輯
        activity_key = f"{user_id}_{guild_id}"
        cutoff_time = datetime.now() - timedelta(days=days)
        
        # 從快取中獲取活動記錄
        all_activities = self._activity_cache.get(activity_key, [])
        
        # 過濾指定天數內的活動
        recent_activities = [
            activity for activity in all_activities
            if activity["timestamp"] >= cutoff_time
        ]
        
        # 統計不同類型的活動
        message_count = len([a for a in recent_activities if a["activity_type"] == "message"])
        reaction_count = len([a for a in recent_activities if a["activity_type"] == "reaction"])
        voice_activities = [a for a in recent_activities if a["activity_type"] in ["voice_join", "voice_leave"]]
        
        # 計算語音時間（簡化版本）
        voice_minutes = len(voice_activities) * 5  # 假設每次語音活動5分鐘
        
        # 找到最後活動時間
        last_activity = max([a["timestamp"] for a in recent_activities]) if recent_activities else None
        
        return {
            "user_id": user_id,
            "guild_id": guild_id, 
            "days": days,
            "total_messages": message_count,
            "total_reactions": reaction_count,
            "voice_minutes": voice_minutes,
            "last_activity": last_activity.isoformat() if last_activity else None,
            "total_activities": len(recent_activities)
        }
        
    def is_initialized(self) -> bool:
        """Check if service is initialized"""
        return self._initialized