"""
訊息監聽系統嵌入訊息模組
- 提供各種嵌入訊息模板
- 統一視覺風格
"""

from .settings_embed import settings_embed
from .preview_embed import preview_embed
from .stats_embed import stats_embed

__all__ = [
    'settings_embed',
    'preview_embed',
    'stats_embed'
] 