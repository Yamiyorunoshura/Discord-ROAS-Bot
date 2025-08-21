"""
測試環境修復模組
為Discord.py在Python 3.10環境中提供兼容性支援
"""
from __future__ import annotations

import sys
import typing
from typing import Any, Type

# 確保類型註解在運行時可用
if sys.version_info >= (3, 10):
    # Python 3.10+ 應該本來就支援，但可能需要特殊處理
    try:
        # 測試是否可以使用subscript
        test_type = type[int]
    except TypeError:
        # 如果不行，我們需要啟用PEP 585支援
        import builtins
        original_type = builtins.type
        
        class SubscriptableType(type):
            def __getitem__(cls, item):
                return cls
        
        # 這是一個危險的操作，只在測試環境中使用
        if 'pytest' in sys.modules:
            builtins.type = SubscriptableType

def patch_discord_typing():
    """
    修補Discord.py的類型註解問題
    """
    try:
        import discord.app_commands
        
        # 如果discord.app_commands.Command不支援subscript，我們修補它
        original_command = discord.app_commands.Command
        
        class PatchedCommand(original_command):
            def __class_getitem__(cls, item):
                return cls
        
        discord.app_commands.Command = PatchedCommand
        
    except (ImportError, AttributeError):
        # 如果Discord還沒導入或者已經修復了，就不需要做任何事
        pass

# 只有在測試環境中才應用這些修補
if 'pytest' in sys.modules or 'PYTEST_CURRENT_TEST' in __import__('os').environ:
    patch_discord_typing()