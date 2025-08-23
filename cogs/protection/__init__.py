# cogs/protection/__init__.py ── 群組保護模組
# ============================================================
# Discord ADR Bot v1.5 - 群組保護模組
# 
# 模組說明：
# 此模組提供完整的 Discord 伺服器保護功能，
# 包含反垃圾訊息、反惡意連結、反惡意程式等保護機制。
# 
# 包含的保護模組：
# - base.py: 基礎類別和共用功能
# - anti_spam.py: 反垃圾訊息保護
# - anti_link.py: 反惡意連結保護  
# - anti_executable.py: 反惡意程式保護
# 
# 版本：1.5.0
# 更新日期：2024
# ============================================================

__version__ = "1.5.0"
__author__ = "Discord ADR Bot Team"
__description__ = "Discord 伺服器群組保護模組"

# 匯出主要類別
from .base import ProtectionCog, admin_only, handle_error, friendly_log
from .anti_spam import AntiSpam
from .anti_link import AntiLink
from .anti_executable import AntiExecutable

__all__ = [
    "ProtectionCog",
    "admin_only", 
    "handle_error",
    "friendly_log",
    "AntiSpam",
    "AntiLink", 
    "AntiExecutable"
]
