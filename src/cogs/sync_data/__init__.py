"""
資料同步模組 v1.6 - 重構版
- 模組化架構設計
- 完整的錯誤處理和日誌記錄
- 智能差異檢測和進度回饋
"""

from .main.main import SyncDataCog

__version__ = "1.6.0"
__author__ = "Discord ADR Bot Team"
__description__ = "Discord 伺服器資料同步模組 - 重構版"

__all__ = ["SyncDataCog"]


async def setup(bot):
    """載入 SyncDataCog 到機器人"""
    await bot.add_cog(SyncDataCog(bot))
