"""
歡迎系統模組初始化檔案

此模組負責處理新成員加入時的歡迎訊息和圖片
"""

from .main import WelcomeCog

async def setup(bot):
    """
    設置 Cog
    
    Args:
        bot: Discord Bot 實例
    """
    await bot.add_cog(WelcomeCog(bot))