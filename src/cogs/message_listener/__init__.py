"""
訊息監聽模組入口點
- 提供訊息記錄與搜尋功能
- 支援訊息圖片渲染
- 追蹤訊息編輯與刪除
- 處理外部表情符號
"""

from discord.ext import commands

from .main import MessageListenerCog


async def setup(bot: commands.Bot):
    """
    模組載入函數,由 Discord.py 調用
    """
    await bot.add_cog(MessageListenerCog(bot))
