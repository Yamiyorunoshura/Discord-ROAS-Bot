"""Currency Panel Embeds.

Embed渲染器模組,提供貨幣面板的訊息嵌入:
- 主面板 Embed
- 排行榜 Embed
- 管理員面板 Embed
- 經濟統計 Embed
- 審計記錄 Embed
"""

from .admin_embed import AdminEmbedRenderer
from .leaderboard_embed import LeaderboardEmbedRenderer
from .main_embed import MainEmbedRenderer
from .stats_embed import StatsEmbedRenderer

__all__ = [
    "AdminEmbedRenderer",
    "LeaderboardEmbedRenderer",
    "MainEmbedRenderer",
    "StatsEmbedRenderer",
]
