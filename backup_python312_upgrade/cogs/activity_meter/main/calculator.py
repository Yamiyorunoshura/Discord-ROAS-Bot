"""
活躍度計算邏輯
- 提供活躍度計算、衰減和更新的核心邏輯
"""

import time
import logging
from typing import Tuple

from ..config import config

logger = logging.getLogger("activity_meter")

class ActivityCalculator:
    """
    活躍度計算器類別
    
    功能：
    - 計算活躍度分數
    - 處理活躍度衰減
    - 提供活躍度更新邏輯
    """
    
    @staticmethod
    def decay(score: float, delta: int) -> float:
        """
        計算活躍度隨時間衰減
        
        Args:
            score: 當前活躍度分數
            delta: 時間差（秒）
            
        Returns:
            float: 衰減後的活躍度分數
        """
        if delta <= config.ACTIVITY_DECAY_AFTER:
            return score
        
        # 計算衰減量
        decay = (config.ACTIVITY_DECAY_PER_H / 3600) * (delta - config.ACTIVITY_DECAY_AFTER)
        
        # 返回衰減後的分數（不低於0）
        return max(0, score - decay)
    
    @staticmethod
    def calculate_new_score(current_score: float, last_msg_time: int, now: int) -> float:
        """
        計算新的活躍度分數
        
        Args:
            current_score: 當前活躍度分數
            last_msg_time: 上次訊息時間戳
            now: 當前時間戳
            
        Returns:
            float: 新的活躍度分數
        """
        # 先計算衰減
        decayed_score = ActivityCalculator.decay(current_score, now - last_msg_time)
        
        # 添加新訊息的活躍度增益
        new_score = decayed_score + config.ACTIVITY_GAIN
        
        # 確保不超過最大值
        return min(new_score, config.ACTIVITY_MAX_SCORE)
    
    @staticmethod
    def should_update(last_msg_time: int, now: int) -> bool:
        """
        判斷是否應該更新活躍度
        
        Args:
            last_msg_time: 上次訊息時間戳
            now: 當前時間戳
            
        Returns:
            bool: 是否應該更新活躍度
        """
        return now - last_msg_time >= config.ACTIVITY_COOLDOWN 