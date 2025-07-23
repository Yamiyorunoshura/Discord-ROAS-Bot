"""
活躍度系統模組入口點
- 提供 0~100 分活躍度計算、每日/月排行榜、進度條圖片
- 支援自動播報、排行榜頻道設定、資料庫持久化
- 具備詳細錯誤處理與日誌記錄
"""

from discord.ext import commands
from .main.main import ActivityMeter

# 為了向後相容，提供別名
ActivityMeterCog = ActivityMeter

async def setup(bot: commands.Bot):
    """
    模組載入函數，由 Discord.py 調用
    """
    await bot.add_cog(ActivityMeter(bot))
