"""
經濟系統模組
Task ID: 2 - 實作經濟系統核心功能

這個模組提供Discord機器人的經濟系統功能，包括：
- 帳戶管理（使用者、政府理事會、政府部門）
- 交易處理和審計
- 貨幣配置管理
"""

from .models import AccountType
from .economy_service import EconomyService

# 版本信息
__version__ = "1.0.0"
__author__ = "開發團隊"

# 模組匯出
__all__ = [
    "AccountType",
    "EconomyService"
]