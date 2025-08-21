"""
系統整合測試
Task ID: 1 - 建立核心架構基礎

驗證整個新架構系統的功能：
- 服務間整合
- 面板與服務層互動
- 資料庫管理器整合
- 錯誤處理流程
- 端到端工作流程
"""
import pytest
import pytest_asyncio
import asyncio
import tempfile
import os
from unittest.mock import MagicMock, AsyncMock, patch
import discord

# 導入所有核心模組
from core.base_service import BaseService, ServiceRegistry, service_registry
from core.database_manager import DatabaseManager
from panels.base_panel import BasePanel
from core.exceptions import (
    ServiceError,
    ValidationError,
    ServicePermissionError
)


class TestUserService(BaseService):
    """測試用的使用者服務"""
    
    def __init__(self, database_manager: DatabaseManager):
        super().__init__("TestUserService")
        self.add_dependency(database_manager, "database")
        self.users = {}  # 簡化實作，使用記憶體存儲
    
    async def _initialize(self) -> bool:
        db = self.get_dependency("database")
        if not db:
            return False
        
        # 建立測試表
        try:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS test_users (
                    id INTEGER PRIMARY KEY,
                    discord_id INTEGER UNIQUE NOT NULL,
                    username TEXT NOT NULL,
                    points INTEGER DEFAULT 0,
                    level INTEGER DEFAULT 1
                )
            """)
            return True
        except Exception as e:
            self.logger.error(f"初始化測試使用者服務失敗：{e}")
            return False
    
    async def _cleanup(self) -> None:
        self.users.clear()
    
    async def _validate_permissions(self, user_id: int, guild_id: int, action: str) -> bool:
        if action == "admin_only":
            # 簡化權限檢查：ID 以 1 開頭的是管理員
            return str(user_id).startswith("1")
        return True
    
    async def create_user(self, discord_id: int, username: str) -> dict:
        """建立使用者"""
        db = self.get_dependency("database")
        
        try:
            await db.execute(
                "INSERT INTO test_users (discord_id, username) VALUES (?, ?)",
                (discord_id, username)
            )
            
            user = await db.fetchone(
                "SELECT * FROM test_users WHERE discord_id = ?",
                (discord_id,)
            )
            return dict(user)
        except Exception as e:
            raise ServiceError(
                f"建立使用者失敗：{str(e)}",
                service_name=self.name,
                operation="create_user"
            )
    
    async def get_user(self, discord_id: int) -> dict:
        """獲取使用者"""
        db = self.get_dependency("database")
        
        user = await db.fetchone(
            "SELECT * FROM test_users WHERE discord_id = ?",
            (discord_id,)
        )
        
        if not user:
            raise ServiceError(
                f"使用者不存在：{discord_id}",
                service_name=self.name,
                operation="get_user"
            )
        
        return dict(user)
    
    async def add_points(self, discord_id: int, points: int) -> dict:
        """增加積分"""
        if points <= 0:
            raise ValidationError(
                "積分必須大於 0",
                field="points",
                value=points,
                expected="正整數"
            )
        
        db = self.get_dependency("database")
        
        await db.execute(
            "UPDATE test_users SET points = points + ? WHERE discord_id = ?",
            (points, discord_id)
        )
        
        return await self.get_user(discord_id)


class TestUserPanel(BasePanel):
    """測試用的使用者面板"""
    
    def __init__(self, user_service: TestUserService):
        super().__init__(
            name="TestUserPanel",
            title="測試使用者面板",
            description="用於整合測試的面板"
        )
        self.add_service(user_service, "user_service")
        self.last_interaction_result = None
        
        # 註冊處理器
        self.register_interaction_handler("create_user", self._handle_create_user)
        self.register_interaction_handler("view_user", self._handle_view_user)
        self.register_interaction_handler("add_points", self._handle_add_points)
    
    async def _handle_slash_command(self, interaction: discord.Interaction):
        """處理斜線命令"""
        embed = await self.create_embed(
            title="測試使用者系統",
            description="系統運行正常",
            fields=[
                {"name": "功能", "value": "建立使用者、查看資料、增加積分", "inline": False}
            ]
        )
        self.last_interaction_result = "slash_command_handled"
        # 在測試中不實際發送訊息
    
    async def _handle_create_user(self, interaction: discord.Interaction):
        """處理建立使用者"""
        user_service = self.get_service("user_service")
        
        try:
            user_data = await user_service.create_user(
                discord_id=interaction.user.id,
                username=interaction.user.display_name
            )
            self.last_interaction_result = {"action": "create_user", "success": True, "data": user_data}
        except Exception as e:
            self.last_interaction_result = {"action": "create_user", "success": False, "error": str(e)}
    
    async def _handle_view_user(self, interaction: discord.Interaction):
        """處理查看使用者"""
        user_service = self.get_service("user_service")
        
        try:
            user_data = await user_service.get_user(interaction.user.id)
            self.last_interaction_result = {"action": "view_user", "success": True, "data": user_data}
        except Exception as e:
            self.last_interaction_result = {"action": "view_user", "success": False, "error": str(e)}
    
    async def _handle_add_points(self, interaction: discord.Interaction):
        """處理增加積分"""
        # 檢查權限
        if not await self.validate_permissions(interaction, "admin_only", "user_service"):
            self.last_interaction_result = {"action": "add_points", "success": False, "error": "無權限"}
            return
        
        user_service = self.get_service("user_service")
        
        try:
            user_data = await user_service.add_points(interaction.user.id, 10)
            self.last_interaction_result = {"action": "add_points", "success": True, "data": user_data}
        except Exception as e:
            self.last_interaction_result = {"action": "add_points", "success": False, "error": str(e)}


@pytest_asyncio.fixture
async def integration_system():
    """建立完整的整合測試系統"""
    with tempfile.TemporaryDirectory() as temp_dir:
        # 設定臨時環境
        original_project_root = os.environ.get("PROJECT_ROOT")
        os.environ["PROJECT_ROOT"] = temp_dir
        
        # 建立清潔的服務註冊表
        registry = ServiceRegistry()
        
        try:
            # 建立資料庫管理器
            db_manager = DatabaseManager(
                db_name="integration_test.db",
                message_db_name="integration_test_msg.db"
            )
            await registry.register_service(db_manager)
            
            # 建立使用者服務
            user_service = TestUserService(db_manager)
            await registry.register_service(user_service)
            
            # 初始化所有服務
            init_success = await registry.initialize_all_services()
            assert init_success, "服務初始化失敗"
            
            # 建立面板
            user_panel = TestUserPanel(user_service)
            
            yield {
                "registry": registry,
                "db_manager": db_manager,
                "user_service": user_service,
                "user_panel": user_panel
            }
            
        finally:
            # 清理
            await registry.cleanup_all_services()
            
            # 恢復環境變數
            if original_project_root:
                os.environ["PROJECT_ROOT"] = original_project_root
            elif "PROJECT_ROOT" in os.environ:
                del os.environ["PROJECT_ROOT"]


def create_mock_interaction(user_id: int = 12345, username: str = "TestUser"):
    """建立模擬的 Discord 互動"""
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = MagicMock()
    interaction.user.id = user_id
    interaction.user.display_name = username
    interaction.guild = MagicMock()
    interaction.guild.id = 67890
    interaction.response = MagicMock()
    interaction.response.is_done.return_value = False
    interaction.response.send_message = AsyncMock()
    interaction.data = {}
    return interaction


class TestSystemIntegration:
    """系統整合測試"""
    
    @pytest.mark.asyncio
    async def test_service_registration_and_initialization(self, integration_system):
        """測試服務註冊和初始化"""
        registry = integration_system["registry"]
        
        # 檢查服務是否正確註冊
        services = registry.list_services()
        assert "DatabaseManager" in services
        assert "TestUserService" in services
        
        # 檢查服務是否已初始化
        db_manager = registry.get_service("DatabaseManager")
        user_service = registry.get_service("TestUserService")
        
        assert db_manager.is_initialized
        assert user_service.is_initialized
    
    @pytest.mark.asyncio
    async def test_service_dependency_injection(self, integration_system):
        """測試服務依賴注入"""
        user_service = integration_system["user_service"]
        
        # 檢查依賴是否正確注入
        db_dependency = user_service.get_dependency("database")
        assert db_dependency is not None
        assert db_dependency == integration_system["db_manager"]
    
    @pytest.mark.asyncio
    async def test_database_operations_integration(self, integration_system):
        """測試資料庫操作整合"""
        db_manager = integration_system["db_manager"]
        
        # 測試基本 CRUD 操作
        await db_manager.execute(
            "CREATE TABLE test_integration (id INTEGER PRIMARY KEY, value TEXT)"
        )
        
        await db_manager.execute(
            "INSERT INTO test_integration (value) VALUES (?)",
            ("test_value",)
        )
        
        result = await db_manager.fetchone(
            "SELECT value FROM test_integration WHERE id = 1"
        )
        
        assert result["value"] == "test_value"
    
    @pytest.mark.asyncio
    async def test_user_service_operations(self, integration_system):
        """測試使用者服務操作"""
        user_service = integration_system["user_service"]
        
        # 測試建立使用者
        user_data = await user_service.create_user(12345, "TestUser")
        assert user_data["discord_id"] == 12345
        assert user_data["username"] == "TestUser"
        assert user_data["points"] == 0
        
        # 測試獲取使用者
        retrieved_user = await user_service.get_user(12345)
        assert retrieved_user["discord_id"] == 12345
        
        # 測試增加積分
        updated_user = await user_service.add_points(12345, 50)
        assert updated_user["points"] == 50
    
    @pytest.mark.asyncio
    async def test_panel_service_integration(self, integration_system):
        """測試面板與服務整合"""
        user_panel = integration_system["user_panel"]
        
        # 檢查面板是否正確連接到服務
        user_service = user_panel.get_service("user_service")
        assert user_service is not None
        assert user_service == integration_system["user_service"]
    
    @pytest.mark.asyncio
    async def test_end_to_end_user_creation_flow(self, integration_system):
        """測試端到端使用者建立流程"""
        user_panel = integration_system["user_panel"]
        interaction = create_mock_interaction(54321, "EndToEndUser")
        
        # 模擬互動處理
        interaction.data = {"custom_id": "create_user"}
        interaction.type = discord.InteractionType.component
        
        await user_panel.handle_interaction(interaction)
        
        # 檢查結果
        result = user_panel.last_interaction_result
        assert result is not None
        assert result["action"] == "create_user"
        assert result["success"] is True
        assert result["data"]["discord_id"] == 54321
        assert result["data"]["username"] == "EndToEndUser"
    
    @pytest.mark.asyncio
    async def test_end_to_end_view_user_flow(self, integration_system):
        """測試端到端查看使用者流程"""
        user_panel = integration_system["user_panel"]
        user_service = integration_system["user_service"]
        
        # 先建立使用者
        await user_service.create_user(98765, "ViewTestUser")
        
        # 模擬查看互動
        interaction = create_mock_interaction(98765, "ViewTestUser")
        interaction.data = {"custom_id": "view_user"}
        interaction.type = discord.InteractionType.component
        
        await user_panel.handle_interaction(interaction)
        
        # 檢查結果
        result = user_panel.last_interaction_result
        assert result is not None
        assert result["action"] == "view_user"
        assert result["success"] is True
        assert result["data"]["discord_id"] == 98765
    
    @pytest.mark.asyncio
    async def test_permission_system_integration(self, integration_system):
        """測試權限系統整合"""
        user_panel = integration_system["user_panel"]
        user_service = integration_system["user_service"]
        
        # 建立測試使用者
        await user_service.create_user(11111, "AdminUser")  # ID 以 1 開頭，有管理員權限
        await user_service.create_user(22222, "RegularUser")  # 沒有管理員權限
        
        # 測試管理員權限
        admin_interaction = create_mock_interaction(11111, "AdminUser")
        admin_interaction.data = {"custom_id": "add_points"}
        admin_interaction.type = discord.InteractionType.component
        
        await user_panel.handle_interaction(admin_interaction)
        
        admin_result = user_panel.last_interaction_result
        assert admin_result["success"] is True
        assert admin_result["data"]["points"] == 10
        
        # 測試一般使用者權限（應該被拒絕）
        user_interaction = create_mock_interaction(22222, "RegularUser")
        user_interaction.data = {"custom_id": "add_points"}
        user_interaction.type = discord.InteractionType.component
        
        await user_panel.handle_interaction(user_interaction)
        
        user_result = user_panel.last_interaction_result
        assert user_result["success"] is False
        assert "無權限" in user_result["error"]
    
    @pytest.mark.asyncio
    async def test_error_handling_integration(self, integration_system):
        """測試錯誤處理整合"""
        user_panel = integration_system["user_panel"]
        
        # 測試查看不存在的使用者
        interaction = create_mock_interaction(99999, "NonExistentUser")
        interaction.data = {"custom_id": "view_user"}
        interaction.type = discord.InteractionType.component
        
        await user_panel.handle_interaction(interaction)
        
        result = user_panel.last_interaction_result
        assert result is not None
        assert result["action"] == "view_user"
        assert result["success"] is False
        assert "使用者不存在" in result["error"]
    
    @pytest.mark.asyncio
    async def test_validation_error_handling(self, integration_system):
        """測試輸入驗證錯誤處理"""
        user_service = integration_system["user_service"]
        
        # 使用唯一的ID避免與其他測試衝突
        test_user_id = 98765
        
        # 先檢查使用者是否存在，如果存在先刪除
        try:
            await user_service.get_user(test_user_id)
            # 如果使用者存在，刪除它
            db = user_service.get_dependency("database")
            await db.execute(
                "DELETE FROM test_users WHERE discord_id = ?",
                (test_user_id,)
            )
        except:
            # 使用者不存在，這是預期的
            pass
        
        # 建立測試使用者
        await user_service.create_user(test_user_id, "ValidationUser")
        
        # 測試無效積分（負數）
        with pytest.raises(ValidationError) as exc_info:
            await user_service.add_points(test_user_id, -10)
        
        assert "積分必須大於 0" in str(exc_info.value)
        assert exc_info.value.field == "points"
        assert exc_info.value.value == -10
    
    @pytest.mark.asyncio
    async def test_transaction_rollback_integration(self, integration_system):
        """測試事務回滾整合"""
        db_manager = integration_system["db_manager"]
        
        # 先清理表格（如果存在）
        try:
            await db_manager.execute("DROP TABLE IF EXISTS test_transaction_rollback")
        except:
            pass
        
        # 建立測試表
        await db_manager.execute(
            "CREATE TABLE test_transaction_rollback (id INTEGER PRIMARY KEY, value TEXT)"
        )
        
        # 測試事務回滾
        try:
            async with db_manager.transaction() as conn:
                await conn.execute(
                    "INSERT INTO test_transaction_rollback (value) VALUES (?)",
                    ("should_rollback",)
                )
                # 故意拋出異常
                raise Exception("Test rollback")
        except Exception:
            pass
        
        # 檢查資料是否已回滾
        result = await db_manager.fetchone(
            "SELECT COUNT(*) as count FROM test_transaction_rollback"
        )
        assert result["count"] == 0
    
    @pytest.mark.asyncio
    async def test_service_health_check_integration(self, integration_system):
        """測試服務健康檢查整合"""
        db_manager = integration_system["db_manager"]
        user_service = integration_system["user_service"]
        
        # 檢查資料庫管理器健康狀態
        db_health = await db_manager.health_check()
        assert db_health["service_name"] == "DatabaseManager"
        assert db_health["initialized"] is True
        assert db_health["uptime_seconds"] is not None
        
        # 檢查使用者服務健康狀態
        user_health = await user_service.health_check()
        assert user_health["service_name"] == "TestUserService"
        assert user_health["initialized"] is True
        assert "database" in user_health["dependencies"]
    
    @pytest.mark.asyncio
    async def test_database_statistics_integration(self, integration_system):
        """測試資料庫統計整合"""
        db_manager = integration_system["db_manager"]
        
        # 建立一些測試資料
        await db_manager.execute(
            "CREATE TABLE test_stats (id INTEGER PRIMARY KEY, data TEXT)"
        )
        await db_manager.execute(
            "INSERT INTO test_stats (data) VALUES (?)",
            ("test_data",)
        )
        
        # 獲取統計信息
        stats = await db_manager.get_database_stats()
        
        assert "main_database" in stats
        assert "message_database" in stats
        assert "connection_pool" in stats
        
        # 檢查主資料庫統計
        main_db_stats = stats["main_database"]
        assert "tables" in main_db_stats
        
        # 查找測試表
        test_table_stats = None
        for table in main_db_stats["tables"]:
            if table["name"] == "test_stats":
                test_table_stats = table
                break
        
        assert test_table_stats is not None
        assert test_table_stats["row_count"] == 1
    
    @pytest.mark.asyncio
    async def test_system_cleanup_integration(self, integration_system):
        """測試系統清理整合"""
        registry = integration_system["registry"]
        
        # 檢查服務是否正在運行
        assert len(registry.list_services()) > 0
        
        # 清理所有服務
        await registry.cleanup_all_services()
        
        # 檢查服務是否已關閉
        for service_name in registry.list_services():
            service = registry.get_service(service_name)
            assert not service.is_initialized


class TestBackwardCompatibilityIntegration:
    """向後相容性整合測試"""
    
    @pytest.mark.asyncio
    async def test_database_cog_compatibility(self):
        """測試 Database Cog 相容性整合"""
        with tempfile.TemporaryDirectory() as temp_dir:
            original_project_root = os.environ.get("PROJECT_ROOT")
            os.environ["PROJECT_ROOT"] = temp_dir
            
            try:
                # 導入相容性模組
                from core.database_manager import Database
                
                # 建立模擬 bot
                bot = MagicMock()
                
                # 建立相容性 Cog
                db_cog = Database(bot, "compat_test.db", "compat_test_msg.db")
                await db_cog.cog_load()
                
                # 檢查是否成功載入
                assert db_cog.ready is True
                assert hasattr(bot, 'database')
                
                # 測試向後相容的方法
                await db_cog.set_setting("test_key", "test_value")
                result = await db_cog.get_setting("test_key")
                assert result == "test_value"
                
                # 測試歡迎訊息功能
                await db_cog.update_welcome_message(12345, 67890, "Welcome!")
                welcome_msg = await db_cog.get_welcome_message(12345)
                assert welcome_msg == "Welcome!"
                
                # 清理
                await db_cog.cog_unload()
                
            finally:
                if original_project_root:
                    os.environ["PROJECT_ROOT"] = original_project_root
                elif "PROJECT_ROOT" in os.environ:
                    del os.environ["PROJECT_ROOT"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])