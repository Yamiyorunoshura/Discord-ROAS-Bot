"""
數據遷移工具包 - 初始化模組

此模組提供數據遷移工具的統一入口,包括:
- 遷移工具導入
- 工具配置和初始化
- 常用功能封裝

符合 TASK-004: 數據遷移工具實現的要求
"""

from .migration_manager import MigrationManager
from .migration_validator import MigrationValidator, ValidationError
from .welcome_migration import (
    MigrationError,
    MigrationValidationError,
    WelcomeMigrationTool,
)

__all__ = [
    "MigrationError",
    "MigrationManager",
    "MigrationValidationError",
    "MigrationValidator",
    "ValidationError",
    "WelcomeMigrationTool",
]

__version__ = "1.0.0"
