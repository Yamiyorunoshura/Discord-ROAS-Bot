"""
活躍度系統面板模組
Task ID: 9 - 重構現有模組以符合新架構

這個模組包含活躍度系統的面板層實作，提供：
- 活躍度查詢面板
- 排行榜顯示面板
- 設定管理面板
- 進度條圖片顯示
"""

from .activity_panel import ActivityPanel

__all__ = ['ActivityPanel']