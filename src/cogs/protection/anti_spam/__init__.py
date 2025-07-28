"""
反垃圾訊息保護模組 - 重構版
- 智能垃圾訊息檢測
- 多維度行為分析
- 自動化違規處理
- 統計和監控功能
"""

from .main.main import AntiSpam

# 為了向後相容,提供別名
AntiSpamCog = AntiSpam

__version__ = "1.6.0"
__author__ = "Discord ADR Bot Team"
__description__ = "反垃圾訊息保護模組 - 重構版"

__all__ = ["AntiSpam", "AntiSpamCog"]
