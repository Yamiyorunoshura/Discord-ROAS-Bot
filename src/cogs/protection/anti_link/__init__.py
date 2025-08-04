"""
反惡意連結保護模組初始化文件
"""

from .main.main import AntiLink


async def setup(bot):
    """設置 Cog"""
    await bot.add_cog(AntiLink(bot))

__all__ = ["AntiLink", "setup"]
