"""
🎯 LogicAPIs - 程式邏輯個別API
- 為每個程式邏輯功能提供獨立的API接口
- 實現數據驗證和錯誤處理
- 支援權限檢查和性能監控
- 提供標準化的API響應格式
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

logger = logging.getLogger("logic_apis")

@dataclass
class APIResponse:
    """API響應數據結構"""
    status: str
    data: Optional[Dict[str, Any]] = None
    message: str = ""
    timestamp: str = ""
    execution_time: float = 0.0
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

class LogicAPIs:
    """
    程式邏輯個別API
    - 為每個程式邏輯功能提供獨立的API接口
    - 實現標準化的API響應格式
    - 支援數據驗證和錯誤處理
    """
    
    def __init__(self):
        """初始化邏輯API"""
        self.database = ActivityDatabase()
        self.renderer = ActivityRenderer()
        self.calculator = ActivityCalculator()
        
        # API調用統計
        self.api_calls = {}
        self.error_counts = {}
        
        logger.info("✅ LogicAPIs 初始化成功")
    
    def renderer_logic_api(self, data: Dict[str, Any]) -> APIResponse:
        """
        渲染邏輯API
        
        Args:
            data: 渲染數據
            
        Returns:
            APIResponse: API響應
        """
        start_time = time.time()
        
        try:
            # 記錄API調用
            self._record_api_call("renderer_logic")
            
            # 驗證輸入數據
            if not self._validate_render_data(data):
                return APIResponse(
                    status="error",
                    message="渲染數據格式錯誤",
                    execution_time=time.time() - start_time
                )
            
            # 執行渲染邏輯
            rendered_data = self.renderer.render_progress_bar(
                data.get("username", "未知用戶"),
                data.get("score", 0)
            )
            
            return APIResponse(
                status="success",
                data={"rendered_file": rendered_data},
                message="渲染成功",
                execution_time=time.time() - start_time
            )
            
        except Exception as e:
            self._record_error("renderer_logic", str(e))
            logger.error(f"❌ 渲染邏輯API失敗: {e}")
            return APIResponse(
                status="error",
                message=f"渲染失敗: {str(e)}",
                execution_time=time.time() - start_time
            )
    
    def settings_logic_api(self, settings: Dict[str, Any]) -> APIResponse:
        """
        設定邏輯API
        
        Args:
            settings: 設定數據
            
        Returns:
            APIResponse: API響應
        """
        start_time = time.time()
        
        try:
            # 記錄API調用
            self._record_api_call("settings_logic")
            
            # 驗證設定數據
            if not self._validate_settings(settings):
                return APIResponse(
                    status="error",
                    message="設定數據格式錯誤",
                    execution_time=time.time() - start_time
                )
            
            # 保存設定
            success = self.database.save_settings(settings)
            
            if success:
                return APIResponse(
                    status="success",
                    message="設定保存成功",
                    execution_time=time.time() - start_time
                )
            else:
                return APIResponse(
                    status="error",
                    message="設定保存失敗",
                    execution_time=time.time() - start_time
                )
            
        except Exception as e:
            self._record_error("settings_logic", str(e))
            logger.error(f"❌ 設定邏輯API失敗: {e}")
            return APIResponse(
                status="error",
                message=f"設定保存失敗: {str(e)}",
                execution_time=time.time() - start_time
            )
    
    def get_user_data(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        獲取用戶數據
        
        Args:
            user_id: 用戶ID
            
        Returns:
            Optional[Dict[str, Any]]: 用戶數據
        """
        try:
            # 記錄API調用
            self._record_api_call("get_user_data")
            
            # 從數據庫獲取用戶數據
            user_data = self.database.get_user_activity(user_id)
            
            if not user_data:
                return None
            
            # 添加額外的計算數據
            user_data["level"] = self.calculator.calculate_level(user_data.get("score", 0))
            user_data["next_level_score"] = self.calculator.get_next_level_score(user_data.get("score", 0))
            
            return user_data
            
        except Exception as e:
            self._record_error("get_user_data", str(e))
            logger.error(f"❌ 獲取用戶數據失敗: {user_id}, 錯誤: {e}")
            return None
    
    def get_user_rank(self, user_id: str) -> Optional[int]:
        """
        獲取用戶排名
        
        Args:
            user_id: 用戶ID
            
        Returns:
            Optional[int]: 用戶排名
        """
        try:
            # 記錄API調用
            self._record_api_call("get_user_rank")
            
            # 從數據庫獲取用戶排名
            rank = self.database.get_user_rank(user_id)
            
            return rank
            
        except Exception as e:
            self._record_error("get_user_rank", str(e))
            logger.error(f"❌ 獲取用戶排名失敗: {user_id}, 錯誤: {e}")
            return None
    
    def get_user_activity_history(self, user_id: str, days: int = 30) -> List[Dict[str, Any]]:
        """
        獲取用戶活躍度歷史
        
        Args:
            user_id: 用戶ID
            days: 歷史天數
            
        Returns:
            List[Dict[str, Any]]: 活躍度歷史數據
        """
        try:
            # 記錄API調用
            self._record_api_call("get_user_activity_history")
            
            # 從數據庫獲取歷史數據
            history_data = self.database.get_user_activity_history(user_id, days)
            
            return history_data
            
        except Exception as e:
            self._record_error("get_user_activity_history", str(e))
            logger.error(f"❌ 獲取活躍度歷史失敗: {user_id}, 錯誤: {e}")
            return []
    
    def get_leaderboard(self, guild_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        獲取排行榜
        
        Args:
            guild_id: 伺服器ID
            limit: 排行榜數量限制
            
        Returns:
            List[Dict[str, Any]]: 排行榜數據
        """
        try:
            # 記錄API調用
            self._record_api_call("get_leaderboard")
            
            # 從數據庫獲取排行榜數據
            leaderboard_data = self.database.get_leaderboard(guild_id, limit)
            
            return leaderboard_data
            
        except Exception as e:
            self._record_error("get_leaderboard", str(e))
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
            # 記錄API調用
            self._record_api_call("update_user_activity")
            
            # 計算新的活躍度分數
            current_score = self.database.get_user_score(user_id, guild_id) or 0
            new_score = self.calculator.calculate_new_score(current_score, activity_type)
            
            # 更新數據庫
            success = self.database.update_user_activity(
                guild_id=guild_id,
                user_id=user_id,
                score=new_score,
                timestamp=int(time.time())
            )
            
            return success
            
        except Exception as e:
            self._record_error("update_user_activity", str(e))
            logger.error(f"❌ 更新用戶活躍度失敗: {user_id}, 錯誤: {e}")
            return False
    
    def calculate_activity_score_api(self, user_data: Dict[str, Any]) -> APIResponse:
        """
        計算活躍度分數API
        
        Args:
            user_data: 用戶數據
            
        Returns:
            APIResponse: API響應
        """
        start_time = time.time()
        
        try:
            # 記錄API調用
            self._record_api_call("calculate_activity_score")
            
            # 驗證用戶數據
            if not self._validate_user_data(user_data):
                return APIResponse(
                    status="error",
                    message="用戶數據格式錯誤",
                    execution_time=time.time() - start_time
                )
            
            # 計算活躍度分數
            score = self.calculator.calculate_score(
                user_data.get("messages", 0),
                user_data.get("total_messages", 0)
            )
            
            # 計算等級
            level = self.calculator.calculate_level(score)
            
            return APIResponse(
                status="success",
                data={
                    "score": score,
                    "level": level,
                    "next_level_score": self.calculator.get_next_level_score(score)
                },
                message="活躍度分數計算成功",
                execution_time=time.time() - start_time
            )
            
        except Exception as e:
            self._record_error("calculate_activity_score", str(e))
            logger.error(f"❌ 計算活躍度分數失敗: {e}")
            return APIResponse(
                status="error",
                message=f"計算活躍度分數失敗: {str(e)}",
                execution_time=time.time() - start_time
            )
    
    def _validate_render_data(self, data: Dict[str, Any]) -> bool:
        """
        驗證渲染數據
        
        Args:
            data: 渲染數據
            
        Returns:
            bool: 驗證是否通過
        """
        required_fields = ["username", "score"]
        return all(field in data for field in required_fields)
    
    def _validate_settings(self, settings: Dict[str, Any]) -> bool:
        """
        驗證設定數據
        
        Args:
            settings: 設定數據
            
        Returns:
            bool: 驗證是否通過
        """
        required_fields = ["guild_id", "key", "value"]
        return all(field in settings for field in required_fields)
    
    def _validate_user_data(self, user_data: Dict[str, Any]) -> bool:
        """
        驗證用戶數據
        
        Args:
            user_data: 用戶數據
            
        Returns:
            bool: 驗證是否通過
        """
        required_fields = ["user_id"]
        return all(field in user_data for field in required_fields)
    
    def _record_api_call(self, api_name: str):
        """記錄API調用"""
        if api_name not in self.api_calls:
            self.api_calls[api_name] = 0
        self.api_calls[api_name] += 1
    
    def _record_error(self, api_name: str, error_message: str):
        """記錄錯誤"""
        if api_name not in self.error_counts:
            self.error_counts[api_name] = 0
        self.error_counts[api_name] += 1
        logger.error(f"API錯誤: {api_name} - {error_message}")
    
    def get_api_metrics(self) -> Dict[str, Any]:
        """
        獲取API指標
        
        Returns:
            Dict[str, Any]: API指標數據
        """
        return {
            "api_calls": self.api_calls,
            "error_counts": self.error_counts,
            "success_rates": self._calculate_success_rates()
        }
    
    def _calculate_success_rates(self) -> Dict[str, float]:
        """計算成功率"""
        success_rates = {}
        for api_name in self.api_calls:
            total_calls = self.api_calls[api_name]
            errors = self.error_counts.get(api_name, 0)
            success_rates[api_name] = ((total_calls - errors) / total_calls * 100) if total_calls > 0 else 0
        return success_rates