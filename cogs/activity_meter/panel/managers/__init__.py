"""
活躍度面板管理器包
- 提供完整的面板管理功能
- 實現提示詞 v1.7-1 的架構設計
"""

from .page_manager import PageManager
from .permission_manager import PermissionManager
from .data_manager import DataManager
from .ui_manager import UIManager

__all__ = [
    "PageManager",
    "PermissionManager", 
    "DataManager",
    "UIManager"
] 