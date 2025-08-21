"""
BasePanel 單元測試
Task ID: 1 - 建立核心架構基礎

測試 BasePanel 抽象類別的所有功能：
- 嵌入訊息建立和格式化
- 互動處理和狀態管理
- 錯誤和成功訊息發送
- 服務層整合
- 權限驗證和輸入驗證
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import discord

from panels.base_panel import BasePanel, PanelState
from core.base_service import BaseService
from core.exceptions import (
    ValidationError,
    DiscordError,
    ServicePermissionError
)


class MockService(BaseService):
    """測試用的模擬服務"""
    
    def __init__(self, name: str = "MockService", has_permission: bool = True):
        super().__init__(name)
        self.has_permission = has_permission
    
    async def _initialize(self) -> bool:
        return True
    
    async def _cleanup(self) -> None:
        pass
    
    async def _validate_permissions(self, user_id: int, guild_id: int, action: str) -> bool:
        return self.has_permission


class TestPanel(BasePanel):
    """測試用的面板實作"""
    
    def __init__(self, name: str = "TestPanel", **kwargs):
        super().__init__(name, **kwargs)
        self.slash_command_called = False
        self.component_called = False
        self.modal_called = False
    
    async def _handle_slash_command(self, interaction: discord.Interaction):
        self.slash_command_called = True
    
    async def _handle_component(self, interaction: discord.Interaction):
        self.component_called = True
    
    async def _handle_modal(self, interaction: discord.Interaction):
        self.modal_called = True


@pytest.fixture
def mock_interaction():
    """建立模擬的 Discord 互動"""
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = MagicMock()
    interaction.user.id = 12345
    interaction.guild = MagicMock()
    interaction.guild.id = 67890
    interaction.response = MagicMock()
    interaction.response.is_done.return_value = False
    interaction.response.send_message = AsyncMock()
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()
    interaction.data = {"custom_id": "test_button"}
    interaction.type = discord.InteractionType.component
    return interaction


class TestPanelState:
    """PanelState 測試類別"""
    
    def test_panel_state_creation(self):
        """測試面板狀態建立"""
        state = PanelState("TestPanel")
        
        assert state.panel_name == "TestPanel"
        assert state.interaction_count == 0
        assert state.current_page == 0
        assert isinstance(state.created_at, datetime)
        assert state.last_interaction is None
    
    def test_update_interaction(self):
        """測試更新互動"""
        state = PanelState("TestPanel")
        initial_count = state.interaction_count
        
        state.update_interaction()
        
        assert state.interaction_count == initial_count + 1
        assert isinstance(state.last_interaction, datetime)
    
    def test_context_management(self):
        """測試上下文管理"""
        state = PanelState("TestPanel")
        
        state.set_context("key1", "value1")
        assert state.get_context("key1") == "value1"
        assert state.get_context("nonexistent", "default") == "default"
    
    def test_user_data_management(self):
        """測試使用者資料管理"""
        state = PanelState("TestPanel")
        user_id = 12345
        
        state.set_user_data(user_id, "setting1", "value1")
        assert state.get_user_data(user_id, "setting1") == "value1"
        assert state.get_user_data(user_id, "nonexistent", "default") == "default"
        assert state.get_user_data(99999, "setting1", "default") == "default"


class TestBasePanel:
    """BasePanel 測試類別"""
    
    def test_panel_creation(self):
        """測試面板建立"""
        panel = TestPanel("TestPanel", title="Test Title", description="Test Description")
        
        assert panel.name == "TestPanel"
        assert panel.title == "Test Title"
        assert panel.description == "Test Description"
        assert isinstance(panel.color, discord.Color)
        assert isinstance(panel.state, PanelState)
    
    def test_panel_creation_defaults(self):
        """測試面板預設值"""
        panel = TestPanel()
        
        assert panel.name == "TestPanel"
        assert panel.title == "TestPanel"
        assert panel.description is None
        assert panel.color == discord.Color.blue()
    
    def test_service_management(self):
        """測試服務管理"""
        panel = TestPanel()
        service = MockService("TestService")
        
        panel.add_service(service)
        
        assert panel.get_service("TestService") == service
        assert "TestService" in panel.services
    
    def test_service_management_custom_name(self):
        """測試使用自定義名稱管理服務"""
        panel = TestPanel()
        service = MockService("TestService")
        
        panel.add_service(service, "CustomName")
        
        assert panel.get_service("CustomName") == service
        assert panel.get_service("TestService") is None
    
    def test_interaction_handler_registration(self):
        """測試互動處理器註冊"""
        panel = TestPanel()
        
        async def test_handler(interaction):
            pass
        
        panel.register_interaction_handler("test_button", test_handler)
        
        assert "test_button" in panel.interaction_handlers
        assert panel.interaction_handlers["test_button"] == test_handler
    
    @pytest.mark.asyncio
    async def test_create_embed_basic(self):
        """測試基礎嵌入訊息建立"""
        panel = TestPanel("TestPanel", title="Test Title", description="Test Description")
        
        embed = await panel.create_embed()
        
        assert embed.title == "Test Title"
        assert embed.description == "Test Description"
        assert embed.color == panel.color
        assert embed.footer.text.startswith("TestPanel")
    
    @pytest.mark.asyncio
    async def test_create_embed_custom_params(self):
        """測試自定義參數嵌入訊息"""
        panel = TestPanel()
        
        embed = await panel.create_embed(
            title="Custom Title",
            description="Custom Description",
            color=discord.Color.red(),
            thumbnail_url="https://example.com/thumb.jpg",
            image_url="https://example.com/image.jpg",
            footer_text="Custom Footer"
        )
        
        assert embed.title == "Custom Title"
        assert embed.description == "Custom Description"
        assert embed.color == discord.Color.red()
        assert embed.thumbnail.url == "https://example.com/thumb.jpg"
        assert embed.image.url == "https://example.com/image.jpg"
        assert embed.footer.text == "Custom Footer"
    
    @pytest.mark.asyncio
    async def test_create_embed_with_fields(self):
        """測試帶欄位的嵌入訊息"""
        panel = TestPanel()
        fields = [
            {"name": "Field 1", "value": "Value 1", "inline": True},
            {"name": "Field 2", "value": "Value 2", "inline": False}
        ]
        
        embed = await panel.create_embed(fields=fields)
        
        assert len(embed.fields) == 2
        assert embed.fields[0].name == "Field 1"
        assert embed.fields[0].value == "Value 1"
        assert embed.fields[0].inline is True
        assert embed.fields[1].name == "Field 2"
        assert embed.fields[1].value == "Value 2"
        assert embed.fields[1].inline is False
    
    @pytest.mark.asyncio
    async def test_create_embed_field_limits(self):
        """測試嵌入欄位限制"""
        panel = TestPanel()
        
        # 建立超過限制的欄位
        fields = []
        for i in range(30):  # 超過 max_embed_fields (25)
            fields.append({"name": f"Field {i}", "value": f"Value {i}"})
        
        embed = await panel.create_embed(fields=fields)
        
        # 應該只有 25 個欄位
        assert len(embed.fields) == panel.max_embed_fields
    
    @pytest.mark.asyncio
    async def test_create_embed_long_description(self):
        """測試過長描述截斷"""
        panel = TestPanel()
        long_description = "x" * 5000  # 超過 max_embed_description_length
        
        embed = await panel.create_embed(description=long_description)
        
        assert len(embed.description) <= panel.max_embed_description_length
        assert embed.description.endswith("...")
    
    @pytest.mark.asyncio
    async def test_send_error(self, mock_interaction):
        """測試發送錯誤訊息"""
        panel = TestPanel()
        
        await panel.send_error(mock_interaction, "Test error message")
        
        mock_interaction.response.send_message.assert_called_once()
        args, kwargs = mock_interaction.response.send_message.call_args
        
        assert kwargs.get("ephemeral") is True
        assert "embed" in kwargs
        embed = kwargs["embed"]
        assert "❌ 錯誤" in embed.title
        assert "Test error message" in embed.description
    
    @pytest.mark.asyncio
    async def test_send_success(self, mock_interaction):
        """測試發送成功訊息"""
        panel = TestPanel()
        
        await panel.send_success(mock_interaction, "Test success message")
        
        mock_interaction.response.send_message.assert_called_once()
        args, kwargs = mock_interaction.response.send_message.call_args
        
        assert kwargs.get("ephemeral") is False
        assert "embed" in kwargs
        embed = kwargs["embed"]
        assert "✅ 成功" in embed.title
        assert "Test success message" in embed.description
    
    @pytest.mark.asyncio
    async def test_send_warning(self, mock_interaction):
        """測試發送警告訊息"""
        panel = TestPanel()
        
        await panel.send_warning(mock_interaction, "Test warning message")
        
        mock_interaction.response.send_message.assert_called_once()
        args, kwargs = mock_interaction.response.send_message.call_args
        
        assert kwargs.get("ephemeral") is True
        assert "embed" in kwargs
        embed = kwargs["embed"]
        assert "⚠️ 警告" in embed.title
        assert "Test warning message" in embed.description
    
    @pytest.mark.asyncio
    async def test_send_message_response_done(self, mock_interaction):
        """測試在回應已完成時發送訊息"""
        mock_interaction.response.is_done.return_value = True
        panel = TestPanel()
        
        await panel.send_error(mock_interaction, "Test error")
        
        mock_interaction.followup.send.assert_called_once()
        mock_interaction.response.send_message.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_validate_permissions_default(self, mock_interaction):
        """測試預設權限驗證"""
        panel = TestPanel()
        
        result = await panel.validate_permissions(mock_interaction, "test_action")
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_validate_permissions_with_service(self, mock_interaction):
        """測試使用服務的權限驗證"""
        panel = TestPanel()
        service = MockService("TestService", has_permission=True)
        panel.add_service(service)
        
        result = await panel.validate_permissions(mock_interaction, "test_action", "TestService")
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_validate_permissions_service_denied(self, mock_interaction):
        """測試服務權限驗證拒絕"""
        panel = TestPanel()
        service = MockService("TestService", has_permission=False)
        panel.add_service(service)
        
        with patch.object(panel, 'send_error') as mock_send_error:
            result = await panel.validate_permissions(mock_interaction, "test_action", "TestService")
        
        assert result is False
        mock_send_error.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_validate_permissions_service_not_found(self, mock_interaction):
        """測試權限驗證服務未找到"""
        panel = TestPanel()
        
        with patch.object(panel, 'send_error') as mock_send_error:
            result = await panel.validate_permissions(mock_interaction, "test_action", "NonExistentService")
        
        # 當找不到服務時，面板會退回到自己的權限驗證邏輯，預設是 True
        assert result is True
        # 並且不會發送錯誤訊息，只是記錄警告
        mock_send_error.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_validate_input_success(self, mock_interaction):
        """測試輸入驗證成功"""
        panel = TestPanel()
        input_data = {"name": "test", "age": 25}
        validation_rules = {
            "name": {"required": True, "type": str, "min_length": 1},
            "age": {"required": True, "type": int, "min_value": 18}
        }
        
        result = await panel.validate_input(mock_interaction, input_data, validation_rules)
        
        assert result is True
    
    @pytest.mark.asyncio
    async def test_validate_input_missing_required(self, mock_interaction):
        """測試缺少必要欄位"""
        panel = TestPanel()
        input_data = {"name": "test"}
        validation_rules = {
            "name": {"required": True, "type": str},
            "age": {"required": True, "type": int}
        }
        
        with patch.object(panel, 'send_error') as mock_send_error:
            result = await panel.validate_input(mock_interaction, input_data, validation_rules)
        
        assert result is False
        mock_send_error.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_validate_input_wrong_type(self, mock_interaction):
        """測試錯誤類型"""
        panel = TestPanel()
        input_data = {"name": "test", "age": "not_a_number"}
        validation_rules = {
            "name": {"required": True, "type": str},
            "age": {"required": True, "type": int}
        }
        
        with patch.object(panel, 'send_error') as mock_send_error:
            result = await panel.validate_input(mock_interaction, input_data, validation_rules)
        
        assert result is False
        mock_send_error.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_validate_input_length_constraints(self, mock_interaction):
        """測試長度限制"""
        panel = TestPanel()
        input_data = {"name": "x", "description": "x" * 1000}
        validation_rules = {
            "name": {"required": True, "type": str, "min_length": 3},
            "description": {"required": True, "type": str, "max_length": 100}
        }
        
        with patch.object(panel, 'send_error') as mock_send_error:
            result = await panel.validate_input(mock_interaction, input_data, validation_rules)
        
        assert result is False
        mock_send_error.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_validate_input_value_constraints(self, mock_interaction):
        """測試數值限制"""
        panel = TestPanel()
        input_data = {"score": 150}
        validation_rules = {
            "score": {"required": True, "type": int, "min_value": 0, "max_value": 100}
        }
        
        with patch.object(panel, 'send_error') as mock_send_error:
            result = await panel.validate_input(mock_interaction, input_data, validation_rules)
        
        assert result is False
        mock_send_error.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_validate_input_custom_validator(self, mock_interaction):
        """測試自定義驗證器"""
        panel = TestPanel()
        input_data = {"email": "invalid_email"}
        validation_rules = {
            "email": {
                "required": True,
                "type": str,
                "validator": lambda x: "@" in x and "." in x
            }
        }
        
        with patch.object(panel, 'send_error') as mock_send_error:
            result = await panel.validate_input(mock_interaction, input_data, validation_rules)
        
        assert result is False
        mock_send_error.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_interaction_component(self, mock_interaction):
        """測試處理元件互動"""
        panel = TestPanel()
        mock_interaction.type = discord.InteractionType.component
        
        await panel.handle_interaction(mock_interaction)
        
        assert panel.state.interaction_count == 1
        assert panel.component_called is True
    
    @pytest.mark.asyncio
    async def test_handle_interaction_application_command(self, mock_interaction):
        """測試處理應用程式命令"""
        panel = TestPanel()
        mock_interaction.type = discord.InteractionType.application_command
        
        await panel.handle_interaction(mock_interaction)
        
        assert panel.state.interaction_count == 1
        assert panel.slash_command_called is True
    
    @pytest.mark.asyncio
    async def test_handle_interaction_modal_submit(self, mock_interaction):
        """測試處理模態框提交"""
        panel = TestPanel()
        mock_interaction.type = discord.InteractionType.modal_submit
        
        await panel.handle_interaction(mock_interaction)
        
        assert panel.state.interaction_count == 1
        assert panel.modal_called is True
    
    @pytest.mark.asyncio
    async def test_handle_interaction_with_handler(self, mock_interaction):
        """測試使用註冊處理器處理互動"""
        panel = TestPanel()
        handler_called = False
        
        async def test_handler(interaction):
            nonlocal handler_called
            handler_called = True
        
        panel.register_interaction_handler("test_button", test_handler)
        mock_interaction.type = discord.InteractionType.component
        
        await panel.handle_interaction(mock_interaction)
        
        assert handler_called is True
        assert panel.component_called is False  # 註冊處理器應該優先
    
    @pytest.mark.asyncio
    async def test_handle_interaction_unsupported_type(self, mock_interaction):
        """測試處理不支援的互動類型"""
        panel = TestPanel()
        mock_interaction.type = 999  # 不存在的互動類型
        
        with patch.object(panel, 'send_error') as mock_send_error:
            await panel.handle_interaction(mock_interaction)
        
        mock_send_error.assert_called_once()
    
    def test_get_panel_info(self):
        """測試獲取面板信息"""
        panel = TestPanel("TestPanel", title="Test Title", description="Test Description")
        service = MockService("TestService")
        panel.add_service(service)
        panel.register_interaction_handler("test_button", lambda x: None)
        
        info = panel.get_panel_info()
        
        assert info["name"] == "TestPanel"
        assert info["title"] == "Test Title"
        assert info["description"] == "Test Description"
        assert info["interaction_count"] == 0
        assert "TestService" in info["services"]
        assert "test_button" in info["registered_handlers"]
    
    def test_panel_repr(self):
        """測試面板字符串表示"""
        panel = TestPanel("TestPanel")
        
        repr_str = repr(panel)
        
        assert "TestPanel" in repr_str
        assert "interactions=0" in repr_str


if __name__ == "__main__":
    pytest.main([__file__])