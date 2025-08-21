"""
政府系統模組初始化
Task ID: 4 - 實作政府系統核心功能

此模組提供Discord機器人政府系統的完整功能，包括：
- 部門管理
- 身分組管理
- 與經濟系統整合
- JSON註冊表維護
"""

from .models import DepartmentRegistry, JSONRegistryManager, get_migration_scripts
from .role_service import RoleService
from .government_service import GovernmentService

__all__ = [
    "DepartmentRegistry",
    "JSONRegistryManager", 
    "get_migration_scripts",
    "RoleService",
    "GovernmentService"
]

__version__ = "1.0.0"
__author__ = "Discord Bot Development Team"
__description__ = "政府系統核心功能模組"