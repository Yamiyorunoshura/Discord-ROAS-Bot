"""
活躍度系統資料模型
Task ID: 9 - 重構現有模組以符合新架構

定義活躍度系統使用的所有資料模型
"""

import time
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class ActivitySettings:
    """活躍度系統設定"""
    guild_id: int
    report_channel_id: Optional[int] = None
    report_hour: int = 8  # 自動播報時間（小時）
    max_score: float = 100.0  # 最大活躍度分數
    gain_per_message: float = 1.0  # 每則訊息獲得的活躍度
    decay_after_seconds: int = 300  # 多少秒後開始衰減
    decay_per_hour: float = 6.0  # 每小時衰減多少分
    cooldown_seconds: int = 60  # 計算活躍度的冷卻時間
    auto_report_enabled: bool = True  # 是否啟用自動播報


@dataclass
class ActivityRecord:
    """活躍度記錄"""
    guild_id: int
    user_id: int
    score: float
    last_message_time: int  # Unix timestamp
    calculated_at: Optional[datetime] = None
    
    def __post_init__(self):
        """初始化後處理"""
        if self.calculated_at is None:
            self.calculated_at = datetime.now()
    
    def calculate_current_score(self, settings: ActivitySettings) -> float:
        """
        根據設定計算當前活躍度分數（考慮時間衰減）
        
        參數：
            settings: 活躍度設定
            
        返回：
            當前活躍度分數
        """
        current_time = int(time.time())
        time_delta = current_time - self.last_message_time
        
        # 如果時間差小於衰減起始時間，不衰減
        if time_delta <= settings.decay_after_seconds:
            return self.score
        
        # 計算衰減
        decay_time = time_delta - settings.decay_after_seconds
        decay_amount = (settings.decay_per_hour / 3600) * decay_time
        
        return max(0, self.score - decay_amount)


@dataclass
class DailyActivityRecord:
    """每日活躍度記錄"""
    date_key: str  # YYYYMMDD 格式
    guild_id: int
    user_id: int
    message_count: int = 0


@dataclass
class ActivityStats:
    """活躍度統計資料"""
    guild_id: int
    user_id: int
    current_score: float
    daily_messages: int
    monthly_messages: int
    monthly_average: float
    rank_daily: Optional[int] = None
    rank_monthly: Optional[int] = None


@dataclass
class LeaderboardEntry:
    """排行榜項目"""
    rank: int
    user_id: int
    username: str
    display_name: str
    score: float
    daily_messages: int
    monthly_messages: int
    monthly_average: float


@dataclass
class MonthlyStats:
    """月度統計"""
    guild_id: int
    month_key: str  # YYYYMM 格式
    total_messages: int
    active_users: int
    average_messages_per_user: float
    top_users: List[LeaderboardEntry] = field(default_factory=list)


@dataclass
class ActivityReport:
    """活躍度報告"""
    guild_id: int
    date_key: str
    leaderboard: List[LeaderboardEntry]
    monthly_stats: MonthlyStats
    generated_at: datetime = field(default_factory=datetime.now)
    
    def to_embed_fields(self) -> List[Dict[str, Any]]:
        """轉換為 Discord Embed 欄位格式"""
        fields = []
        
        # 今日排行榜
        if self.leaderboard:
            leaderboard_text = []
            for entry in self.leaderboard[:10]:  # 只顯示前10名
                leaderboard_text.append(
                    f"`#{entry.rank:2}` {entry.display_name:<20} ‧ "
                    f"今日 {entry.daily_messages} 則 ‧ 月均 {entry.monthly_average:.1f}"
                )
            
            fields.append({
                'name': '📈 今日活躍排行榜',
                'value': '\n'.join(leaderboard_text) if leaderboard_text else '今天還沒有人說話！',
                'inline': False
            })
        
        # 月度統計
        if self.monthly_stats:
            stats_text = (
                f"📊 總訊息數：{self.monthly_stats.total_messages:,}\n"
                f"👥 活躍用戶：{self.monthly_stats.active_users}\n"
                f"📈 平均訊息：{self.monthly_stats.average_messages_per_user:.1f} 則/人"
            )
            
            fields.append({
                'name': '📈 本月統計',
                'value': stats_text,
                'inline': False
            })
        
        return fields


@dataclass
class ActivityImage:
    """活躍度進度條圖片"""
    guild_id: int
    user_id: int
    username: str
    display_name: str
    score: float
    max_score: float
    image_bytes: bytes
    generated_at: datetime = field(default_factory=datetime.now)
    
    def get_progress_percentage(self) -> float:
        """獲取進度百分比"""
        if self.max_score <= 0:
            return 0.0
        return min(100.0, (self.score / self.max_score) * 100.0)