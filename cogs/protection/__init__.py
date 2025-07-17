# cogs/protection/__init__.py ── 群組保護模組
# ============================================================
# Discord ADR Bot v1.6 - 群組保護模組
# 
# 模組說明：
# 此模組提供完整的 Discord 伺服器保護功能，
# 包含反垃圾訊息、反惡意連結、反惡意程式等保護機制。
# 
# 重構版本：v1.6
# 架構：模組化設計，每個子模組都有完整的目錄結構
# 
# 子模組：
# - anti_spam: 反垃圾訊息保護
# - anti_link: 反惡意連結保護  
# - anti_executable: 反惡意程式保護
# - base: 基礎類別和共用功能
# ============================================================

__version__ = "1.6.0"
__author__ = "Discord ADR Bot Team"
__description__ = "Discord 伺服器群組保護模組 - 重構版"

# 匯出主要類別
from .base import ProtectionCog

# 載入重構完成的模組
try:
    from .anti_spam.main.main import AntiSpam
    ANTI_SPAM_AVAILABLE = True
except ImportError:
    from .anti_spam import AntiSpam
    ANTI_SPAM_AVAILABLE = False

# 其他模組暫時使用舊架構
from .anti_link import AntiLink

# 暫時使用舊的 anti_executable.py 檔案，直到新架構完全修正
try:
    from .anti_executable.main.main import AntiExecutable
    print("✅ 使用新架構的 AntiExecutable")
except ImportError as e:
    print(f"⚠️ 新架構載入失敗，使用舊架構: {e}")
    from .anti_executable import AntiExecutable

__all__ = [
    "ProtectionCog",
    "AntiSpam",
    "AntiLink", 
    "AntiExecutable"
]

# Discord.py 擴充功能載入入口點
async def setup(bot):
    """
    模組載入函數，由 Discord.py 調用
    載入所有保護模組子類別
    """
    # 載入各個保護子模組
    await bot.add_cog(AntiSpam(bot))
    await bot.add_cog(AntiLink(bot))
    await bot.add_cog(AntiExecutable(bot))
    
    # 記錄重構狀態
    import logging
    logger = logging.getLogger("protection")
    if ANTI_SPAM_AVAILABLE:
        logger.info("【群組保護】AntiSpam 模組已使用重構架構")
    else:
        logger.info("【群組保護】AntiSpam 模組使用舊架構")
    
    logger.info("【群組保護】所有子模組載入完成")
