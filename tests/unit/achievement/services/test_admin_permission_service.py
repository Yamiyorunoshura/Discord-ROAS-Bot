"""成就系統管理員權限服務的單元測試.

測試涵蓋：
- 權限檢查邏輯
- 權限裝飾器功能
- 錯誤處理和用戶回饋
- 審計日誌記錄
- 服務清理
"""

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from src.cogs.achievement.services.admin_permission_service import (
    AdminPermissionService,
    get_admin_permission_service,
    require_achievement_admin,
)
from src.cogs.core.permission_system import (
    ActionType,
    PermissionCheck,
    PermissionSystem,
    UserRole,
)


class TestAdminPermissionService:
    """測試 AdminPermissionService 類別."""

    @pytest.fixture
    def mock_permission_system(self):
        """創建模擬的權限系統."""
        return MagicMock(spec=PermissionSystem)

    @pytest.fixture
    def admin_service(self, mock_permission_system):
        """創建 AdminPermissionService 實例."""
        return AdminPermissionService(mock_permission_system)

    @pytest.fixture
    def mock_user(self):
        """創建模擬的 Discord 用戶."""
        user = MagicMock(spec=discord.Member)
        user.id = 123456789
        user.display_name = "TestAdmin"
        user.discriminator = "1234"

        # 模擬 guild
        guild = MagicMock(spec=discord.Guild)
        guild.id = 987654321
        guild.name = "Test Guild"
        user.guild = guild

        return user

    @pytest.fixture
    def mock_interaction(self, mock_user):
        """創建模擬的 Discord 互動."""
        interaction = MagicMock(spec=discord.Interaction)
        interaction.user = mock_user
        interaction.guild = mock_user.guild
        interaction.response = MagicMock()
        interaction.followup = MagicMock()
        return interaction

    async def test_check_admin_permission_success(self, admin_service, mock_user, mock_permission_system):
        """測試成功的管理員權限檢查."""
        # 設置模擬的成功回應
        mock_permission_system.check_permission.return_value = PermissionCheck(
            allowed=True,
            reason="權限檢查通過",
            audit_log={"test": "data"}
        )

        # 執行權限檢查
        result = await admin_service.check_admin_permission(
            user=mock_user,
            action="測試操作",
            context={"test": "context"}
        )

        # 驗證結果
        assert result.allowed is True
        assert result.reason == "權限檢查通過"
        assert result.audit_log is not None

        # 驗證權限系統被正確調用
        mock_permission_system.check_permission.assert_called_once_with(
            user_role=UserRole.ADMIN,
            action_type=ActionType.ADMIN,
            resource="achievement_management",
            context={
                "user_id": mock_user.id,
                "guild_id": mock_user.guild.id,
                "action": "測試操作",
                "timestamp": pytest.approx(discord.utils.utcnow().isoformat(), abs=10),
                "test": "context"
            }
        )

    async def test_check_admin_permission_failure(self, admin_service, mock_user, mock_permission_system):
        """測試失敗的管理員權限檢查."""
        # 設置模擬的失敗回應
        mock_permission_system.check_permission.return_value = PermissionCheck(
            allowed=False,
            reason="權限不足,需要 admin 角色",
            required_role=UserRole.ADMIN,
            audit_log={"denied": True}
        )

        # 執行權限檢查
        result = await admin_service.check_admin_permission(
            user=mock_user,
            action="測試操作"
        )

        # 驗證結果
        assert result.allowed is False
        assert "權限不足,需要 admin 角色" in result.reason
        assert result.required_role == UserRole.ADMIN

    async def test_check_admin_permission_exception(self, admin_service, mock_user, mock_permission_system):
        """測試權限檢查異常處理."""
        # 設置模擬的異常
        mock_permission_system.check_permission.side_effect = Exception("測試異常")

        # 執行權限檢查
        result = await admin_service.check_admin_permission(
            user=mock_user,
            action="測試操作"
        )

        # 驗證異常處理
        assert result.allowed is False
        assert "權限檢查系統錯誤" in result.reason
        assert "測試異常" in result.reason

    def test_create_admin_required_embed(self, admin_service):
        """測試創建權限不足的錯誤 Embed."""
        embed = admin_service.create_admin_required_embed(
            required_role=UserRole.ADMIN,
            action="測試操作"
        )

        # 驗證 embed 內容
        assert embed.title == "權限不足"
        assert "Admin" in embed.description
        assert "測試操作" in embed.description
        assert embed.color.value == 0xff0000  # 錯誤 embed 應該是紅色

    async def test_handle_permission_denied_not_done(self, admin_service, mock_interaction):
        """測試處理權限被拒絕的情況（回應未完成）."""
        mock_interaction.response.is_done.return_value = False

        result = PermissionCheck(
            allowed=False,
            reason="權限不足",
            required_role=UserRole.ADMIN
        )

        await admin_service.handle_permission_denied(
            interaction=mock_interaction,
            result=result,
            action="測試操作"
        )

        # 驗證使用了 response.send_message
        mock_interaction.response.send_message.assert_called_once()
        call_args = mock_interaction.response.send_message.call_args
        assert call_args[1]["ephemeral"] is True

    async def test_handle_permission_denied_already_done(self, admin_service, mock_interaction):
        """測試處理權限被拒絕的情況（回應已完成）."""
        mock_interaction.response.is_done.return_value = True

        result = PermissionCheck(
            allowed=False,
            reason="權限不足",
            required_role=UserRole.ADMIN
        )

        await admin_service.handle_permission_denied(
            interaction=mock_interaction,
            result=result,
            action="測試操作"
        )

        # 驗證使用了 followup.send
        mock_interaction.followup.send.assert_called_once()
        call_args = mock_interaction.followup.send.call_args
        assert call_args[1]["ephemeral"] is True

    async def test_require_admin_permission_decorator_success(self, admin_service, mock_interaction):
        """測試權限裝飾器成功的情況."""
        # 設置成功的權限檢查
        admin_service.check_admin_permission = AsyncMock(return_value=PermissionCheck(
            allowed=True,
            reason="權限檢查通過"
        ))

        # 創建被裝飾的函數
        @admin_service.require_admin_permission("測試操作")
        async def test_function(interaction: discord.Interaction) -> str:
            return "success"

        # 執行被裝飾的函數
        result = await test_function(mock_interaction)

        # 驗證結果
        assert result == "success"
        admin_service.check_admin_permission.assert_called_once()

    async def test_require_admin_permission_decorator_failure(self, admin_service, mock_interaction):
        """測試權限裝飾器失敗的情況."""
        # 設置失敗的權限檢查
        permission_result = PermissionCheck(
            allowed=False,
            reason="權限不足",
            required_role=UserRole.ADMIN
        )
        admin_service.check_admin_permission = AsyncMock(return_value=permission_result)
        admin_service.handle_permission_denied = AsyncMock()

        # 創建被裝飾的函數
        @admin_service.require_admin_permission("測試操作")
        async def test_function(interaction: discord.Interaction) -> str:
            return "success"

        # 執行被裝飾的函數
        result = await test_function(mock_interaction)

        # 驗證結果
        assert result is None  # 權限檢查失敗應該返回 None
        admin_service.handle_permission_denied.assert_called_once_with(
            mock_interaction, permission_result, "測試操作"
        )

    async def test_require_admin_permission_decorator_no_guild(self):
        """測試權限裝飾器在非伺服器環境的情況."""
        admin_service = AdminPermissionService()

        # 創建沒有 guild 的互動
        mock_interaction = MagicMock(spec=discord.Interaction)
        mock_interaction.guild = None
        mock_interaction.response.is_done.return_value = False

        @admin_service.require_admin_permission("測試操作")
        async def test_function(interaction: discord.Interaction) -> str:
            return "success"

        # 執行被裝飾的函數
        result = await test_function(mock_interaction)

        # 驗證結果
        assert result is None
        mock_interaction.response.send_message.assert_called_once()

    async def test_require_admin_permission_decorator_not_member(self):
        """測試權限裝飾器在用戶不是成員的情況."""
        admin_service = AdminPermissionService()

        # 創建不是 Member 的用戶
        mock_interaction = MagicMock(spec=discord.Interaction)
        mock_interaction.guild = MagicMock(spec=discord.Guild)
        mock_interaction.user = MagicMock(spec=discord.User)  # 不是 Member
        mock_interaction.response.is_done.return_value = False

        @admin_service.require_admin_permission("測試操作")
        async def test_function(interaction: discord.Interaction) -> str:
            return "success"

        # 執行被裝飾的函數
        result = await test_function(mock_interaction)

        # 驗證結果
        assert result is None
        mock_interaction.response.send_message.assert_called_once()

    def test_get_audit_logs(self, admin_service, mock_permission_system):
        """測試獲取審計日誌."""
        mock_logs = [{"test": "log1"}, {"test": "log2"}]
        mock_permission_system.get_audit_logs.return_value = mock_logs

        result = admin_service.get_audit_logs(limit=10)

        assert result == mock_logs
        mock_permission_system.get_audit_logs.assert_called_once_with(10)

    def test_get_permission_stats(self, admin_service, mock_permission_system):
        """測試獲取權限統計數據."""
        mock_stats = {
            "total_checks": 100,
            "allowed_checks": 80,
            "denied_checks": 20
        }
        mock_permission_system.get_permission_stats.return_value = mock_stats

        result = admin_service.get_permission_stats()

        # 驗證基本統計被包含
        assert result["total_checks"] == 100
        assert result["allowed_checks"] == 80
        assert result["denied_checks"] == 20

        # 驗證添加的服務特定統計
        assert result["service"] == "AdminPermissionService"
        assert "audit_enabled" in result

    async def test_cleanup(self, admin_service, mock_permission_system):
        """測試服務清理."""
        mock_permission_system.clear_audit_logs = MagicMock()

        await admin_service.cleanup()

        # 驗證清理方法被調用
        mock_permission_system.clear_audit_logs.assert_called_once()


class TestGlobalFunctions:
    """測試全域函數."""

    def test_get_admin_permission_service(self):
        """測試獲取全域服務實例."""
        # 第一次調用應該創建新實例
        service1 = get_admin_permission_service()
        assert isinstance(service1, AdminPermissionService)

        # 第二次調用應該返回相同實例
        service2 = get_admin_permission_service()
        assert service1 is service2

    async def test_require_achievement_admin_decorator(self, mock_interaction):
        """測試便捷裝飾器函數."""
        @require_achievement_admin("測試成就操作")
        async def test_function(interaction: discord.Interaction) -> str:
            return "success"

        # 由於需要實際的權限檢查，我們只驗證裝飾器不會拋出異常
        # 並且函數可以被正確裝飾
        assert callable(test_function)
        assert hasattr(test_function, "__wrapped__")


class TestDecoratorsWithDifferentFunctionSignatures:
    """測試裝飾器與不同函數簽名的兼容性."""

    @pytest.fixture
    def admin_service(self):
        """創建帶有模擬權限檢查的服務."""
        service = AdminPermissionService()
        service.check_admin_permission = AsyncMock(return_value=PermissionCheck(
            allowed=True,
            reason="權限檢查通過"
        ))
        return service

    async def test_decorator_with_positional_interaction(self, admin_service, mock_interaction):
        """測試裝飾器處理位置參數中的 interaction."""
        @admin_service.require_admin_permission("測試操作")
        async def test_function(self, interaction: discord.Interaction, other_param: str) -> str:
            return f"success_{other_param}"

        # 模擬 self 參數
        mock_self = MagicMock()

        result = await test_function(mock_self, mock_interaction, "test")
        assert result == "success_test"

    async def test_decorator_with_keyword_interaction(self, admin_service, mock_interaction):
        """測試裝飾器處理關鍵字參數中的 interaction."""
        @admin_service.require_admin_permission("測試操作")
        async def test_function(other_param: str, *, interaction: discord.Interaction) -> str:
            return f"success_{other_param}"

        result = await test_function("test", interaction=mock_interaction)
        assert result == "success_test"

    async def test_decorator_no_interaction_found(self, admin_service):
        """測試裝飾器在找不到 interaction 參數時的處理."""
        @admin_service.require_admin_permission("測試操作")
        async def test_function(other_param: str) -> str:
            return f"success_{other_param}"

        result = await test_function("test")
        assert result is None  # 應該返回 None 當找不到 interaction 時


@pytest.mark.asyncio
class TestIntegrationWithPermissionSystem:
    """測試與實際權限系統的整合."""

    async def test_integration_with_real_permission_system(self, mock_user):
        """測試與真實權限系統的整合."""
        # 使用真實的權限系統
        real_permission_system = PermissionSystem()
        admin_service = AdminPermissionService(real_permission_system)

        # 執行權限檢查（預期會失敗，因為我們沒有設置真實的管理員權限）
        result = await admin_service.check_admin_permission(
            user=mock_user,
            action="整合測試",
            context={"test": "integration"}
        )

        # 驗證結果結構正確
        assert isinstance(result, PermissionCheck)
        assert isinstance(result.allowed, bool)
        assert isinstance(result.reason, str)
        assert result.audit_log is not None

    async def test_audit_log_enhancement(self, mock_user):
        """測試審計日誌的增強功能."""
        real_permission_system = PermissionSystem()
        admin_service = AdminPermissionService(real_permission_system)

        result = await admin_service.check_admin_permission(
            user=mock_user,
            action="審計測試",
            context={"custom": "data"}
        )

        # 驗證審計日誌包含增強的信息
        audit_log = result.audit_log
        assert audit_log is not None
        assert audit_log["service"] == "AdminPermissionService"
        assert "discord_user" in audit_log
        assert audit_log["discord_user"]["id"] == mock_user.id
        assert "guild_context" in audit_log
