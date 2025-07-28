"""
活躍度面板權限管理器
- 建立清晰的分層權限設計
- 提供統一的權限檢查機制
- 支援不同級別的權限控制
"""

import logging

import discord

logger = logging.getLogger("activity_meter")


class PermissionManager:
    """
    權限管理器

    功能:
    - 建立清晰的分層權限設計
    - 提供統一的權限檢查機制
    - 支援不同級別的權限控制
    """

    def __init__(self):
        """初始化權限管理器"""
        self.permission_levels = {
            "view": "查看權限",
            "manage": "管理權限",
            "export": "導出權限",
            "modify_settings": "設定修改權限",
        }

    @staticmethod
    def can_view(user: discord.Member) -> bool:
        """
        檢查查看權限 - 所有人可查看

        Args:
            user: Discord 成員

        Returns:
            bool: 是否有查看權限
        """
        return True

    @staticmethod
    def can_manage(user: discord.Member) -> bool:
        """
        檢查管理權限 - 需要管理伺服器權限

        Args:
            user: Discord 成員

        Returns:
            bool: 是否有管理權限
        """
        return user.guild_permissions.manage_guild

    @staticmethod
    def can_export(user: discord.Member) -> bool:
        """
        檢查導出權限 - 需要管理員權限

        Args:
            user: Discord 成員

        Returns:
            bool: 是否有導出權限
        """
        return user.guild_permissions.administrator

    @staticmethod
    def can_modify_settings(user: discord.Member) -> bool:
        """
        檢查設定修改權限

        Args:
            user: Discord 成員

        Returns:
            bool: 是否有設定修改權限
        """
        return user.guild_permissions.manage_guild

    @staticmethod
    def can_manage_settings(user: discord.Member) -> bool:
        """
        檢查管理設定權限

        Args:
            user: Discord 成員

        Returns:
            bool: 是否有管理設定權限
        """
        try:
            # 檢查用戶是否存在
            if not user:
                return False

            # 檢查是否為伺服器擁有者
            if user.guild_permissions.administrator:
                return True

            # 檢查是否有管理伺服器權限
            return bool(user.guild_permissions.manage_guild)

        except Exception as e:
            logger.error(f"權限檢查失敗: {e!s}")
            return False

    @staticmethod
    def can_view_stats(user: discord.Member) -> bool:
        """
        檢查查看統計權限

        Args:
            user: Discord 成員

        Returns:
            bool: 是否有查看統計權限
        """
        try:
            # 所有用戶都可以查看統計
            if not user:
                return False

            # 檢查是否有讀取訊息權限
            return bool(user.guild_permissions.read_messages)

        except Exception as e:
            logger.error(f"權限檢查失敗: {e!s}")
            return False

    def check_permission(self, user: discord.Member, permission_type: str) -> bool:
        """
        檢查指定類型的權限

        Args:
            user: Discord 成員
            permission_type: 權限類型

        Returns:
            bool: 是否有權限
        """
        if permission_type == "view":
            return self.can_view(user)
        elif permission_type == "manage":
            return self.can_manage(user)
        elif permission_type == "export":
            return self.can_export(user)
        elif permission_type == "modify_settings":
            return self.can_modify_settings(user)
        elif permission_type == "manage_settings":
            return self.can_manage_settings(user)
        elif permission_type == "view_stats":
            return self.can_view_stats(user)
        else:
            logger.warning(f"未知的權限類型: {permission_type}")
            return False

    def get_user_permissions(self, user: discord.Member) -> dict[str, bool]:
        """
        獲取用戶的所有權限

        Args:
            user: Discord 成員

        Returns:
            Dict[str, bool]: 權限字典
        """
        return {
            "view": self.can_view(user),
            "manage": self.can_manage(user),
            "export": self.can_export(user),
            "modify_settings": self.can_modify_settings(user),
            "manage_settings": self.can_manage_settings(user),
            "view_stats": self.can_view_stats(user),
        }

    def get_required_permission_message(self, permission_type: str) -> str:
        """
        獲取權限不足的提示訊息

        Args:
            permission_type: 權限類型

        Returns:
            str: 提示訊息
        """
        messages = {
            "view": "您沒有查看權限",
            "manage": "您需要「管理伺服器」權限",
            "export": "您需要「管理員」權限",
            "modify_settings": "您需要「管理伺服器」權限才能修改設定",
            "manage_settings": "您需要「管理伺服器」或「管理員」權限才能管理設定",
            "view_stats": "您需要「讀取訊息」權限才能查看統計",
        }

        return messages.get(permission_type, "您沒有足夠的權限")

    def can_access_page(self, user: discord.Member, page_name: str) -> bool:
        """
        檢查用戶是否可以訪問指定頁面

        Args:
            user: Discord 成員
            page_name: 頁面名稱

        Returns:
            bool: 是否可以訪問
        """
        # 所有頁面都需要查看權限
        if not self.can_view(user):
            return False

        # 特定頁面的權限檢查
        if page_name == "settings":
            return self.can_modify_settings(user)
        elif page_name == "preview":
            return self.can_view(user)  # 所有人都可以預覽
        elif page_name == "stats":
            return self.can_view(user)  # 所有人都可以查看統計
        elif page_name == "history":
            return self.can_manage(user)  # 需要管理權限查看歷史

        return True
