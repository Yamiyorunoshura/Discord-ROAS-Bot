"""
政府面板模組
Task ID: 5 - 實作政府系統使用者介面

這個模組提供政府系統的Discord使用者介面，包括：
- 常任理事會政府面板
- 部門管理的完整互動介面
- 部門註冊表查看和編輯功能
- 與GovernmentService、RoleService的前端整合
"""

from .government_panel import GovernmentPanel

__all__ = ["GovernmentPanel"]