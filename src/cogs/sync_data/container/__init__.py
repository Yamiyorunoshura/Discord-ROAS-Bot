"""
資料同步模組依賴注入容器子模組
"""

from .container import (
    configure_sync_data_container,
    create_sync_data_container,
    get_test_container,
)

__all__ = [
    "configure_sync_data_container",
    "create_sync_data_container",
    "get_test_container",
]
