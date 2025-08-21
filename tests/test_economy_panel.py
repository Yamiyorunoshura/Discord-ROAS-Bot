"""
經濟面板單元測試
Task ID: 3 - 實作經濟系統使用者介面

測試經濟面板的核心功能，包括：
- 面板初始化和服務整合
- 使用者功能：餘額查詢、交易記錄
- 管理員功能：餘額管理、貨幣設定
- 權限驗證和錯誤處理
- UI組件互動
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from datetime import datetime
import discord

# 測試目標
from panels.economy_panel import EconomyPanel, UserEconomyView, AdminEconomyView
from services.economy.economy_service import EconomyService
from services.economy.models import Account, Transaction, CurrencyConfig, AccountType, TransactionType
from core.exceptions import ServiceError, ValidationError, ServicePermissionError


class TestEconomyPanel:
    """EconomyPanel 單元測試類別"""
    
    @pytest.fixture
    async def mock_economy_service(self):
        """建立模擬經濟服務"""
        service = Mock(spec=EconomyService)
        service.name = "EconomyService"
        service.is_initialized = True
        
        # 模擬帳戶
        service.get_account = AsyncMock(return_value=Account(
            id="user_123_456",
            account_type=AccountType.USER,
            guild_id=456,
            user_id=123,
            balance=1000.0,
            created_at=datetime.now(),
            updated_at=datetime.now()
        ))
        
        service.create_account = AsyncMock(return_value=Account(
            id="user_123_456",
            account_type=AccountType.USER,
            guild_id=456,
            user_id=123,
            balance=0.0,
            created_at=datetime.now(),
            updated_at=datetime.now()
        ))
        
        # 模擬貨幣配置
        service.get_currency_config = AsyncMock(return_value=CurrencyConfig(
            guild_id=456,
            currency_name="金幣",
            currency_symbol="💰",
            decimal_places=2
        ))
        
        # 模擬交易記錄
        service.get_transaction_history = AsyncMock(return_value=[
            Transaction(
                id=1,
                from_account="user_123_456",
                to_account="user_789_456",
                amount=100.0,
                transaction_type=TransactionType.TRANSFER,
                reason="測試轉帳",
                guild_id=456,
                created_by=123,
                created_at=datetime.now()
            )
        ])
        
        # 模擬餘額管理操作
        service.deposit = AsyncMock(return_value=Transaction(
            id=2,
            from_account=None,
            to_account="user_123_456",
            amount=500.0,
            transaction_type=TransactionType.DEPOSIT,
            reason="管理員存款",
            guild_id=456,
            created_by=999,
            created_at=datetime.now()
        ))
        
        service.withdraw = AsyncMock(return_value=Transaction(
            id=3,
            from_account="user_123_456",
            to_account=None,
            amount=200.0,
            transaction_type=TransactionType.WITHDRAW,
            reason="管理員提款",
            guild_id=456,
            created_by=999,
            created_at=datetime.now()
        ))
        
        service.get_balance = AsyncMock(return_value=1500.0)
        
        # 模擬伺服器帳戶列表
        service.get_guild_accounts = AsyncMock(return_value=[
            Account(
                id="user_123_456",
                account_type=AccountType.USER,
                guild_id=456,
                user_id=123,
                balance=1000.0,
                created_at=datetime.now(),
                updated_at=datetime.now()
            ),
            Account(
                id="user_789_456",
                account_type=AccountType.USER,
                guild_id=456,
                user_id=789,
                balance=500.0,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
        ])
        
        service.set_currency_config = AsyncMock(return_value=CurrencyConfig(
            guild_id=456,
            currency_name="新金幣",
            currency_symbol="💎",
            decimal_places=1
        ))
        
        return service
    
    @pytest.fixture
    async def economy_panel(self, mock_economy_service):
        """建立並初始化經濟面板"""
        panel = EconomyPanel()
        await panel.initialize(mock_economy_service)
        return panel
    
    @pytest.fixture
    def mock_interaction(self):
        """建立模擬 Discord 互動"""
        interaction = Mock(spec=discord.Interaction)
        interaction.user = Mock()
        interaction.user.id = 123
        interaction.user.mention = "<@123>"
        
        interaction.guild = Mock()
        interaction.guild.id = 456
        
        interaction.response = Mock()
        interaction.response.is_done.return_value = False
        interaction.response.send_message = AsyncMock()
        interaction.response.edit_message = AsyncMock()
        interaction.response.send_modal = AsyncMock()
        
        interaction.followup = Mock()
        interaction.followup.send = AsyncMock()
        
        interaction.data = {}
        
        return interaction
    
    @pytest.fixture
    def mock_admin_interaction(self, mock_interaction):
        """建立模擬管理員互動"""
        # 模擬管理員成員
        admin_member = Mock(spec=discord.Member)
        admin_member.id = 999
        admin_member.guild_permissions = Mock()
        admin_member.guild_permissions.administrator = True
        admin_member.guild_permissions.manage_guild = True
        
        mock_interaction.user = admin_member
        return mock_interaction
    
    # ==========================================================================
    # 初始化測試
    # ==========================================================================
    
    @pytest.mark.asyncio
    async def test_panel_initialization(self, mock_economy_service):
        """測試面板初始化"""
        panel = EconomyPanel()
        
        # 測試初始化前狀態
        assert panel.economy_service is None
        assert not panel._initialized if hasattr(panel, '_initialized') else True
        
        # 執行初始化
        await panel.initialize(mock_economy_service)
        
        # 驗證初始化結果
        assert panel.economy_service == mock_economy_service
        assert "economy" in panel.services
        assert len(panel.interaction_handlers) > 0
    
    @pytest.mark.asyncio
    async def test_panel_initialization_failure(self):
        """測試面板初始化失敗"""
        panel = EconomyPanel()
        
        with pytest.raises(ServiceError):
            await panel.initialize(None)
    
    # ==========================================================================
    # 嵌入訊息建立測試
    # ==========================================================================
    
    @pytest.mark.asyncio
    async def test_create_balance_embed(self, economy_panel):
        """測試餘額嵌入訊息建立"""
        account = Account(
            id="user_123_456",
            account_type=AccountType.USER,
            guild_id=456,
            user_id=123,
            balance=1234.56,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        currency_config = CurrencyConfig(guild_id=456)
        
        embed = await economy_panel.create_balance_embed(account, currency_config)
        
        assert embed.title == "💰 個人錢包"
        assert embed.color == discord.Color.gold()
        assert len(embed.fields) >= 3
        
        # 檢查餘額欄位
        balance_field = next((f for f in embed.fields if "餘額" in f.name), None)
        assert balance_field is not None
        assert "1234.56" in balance_field.value
    
    @pytest.mark.asyncio
    async def test_create_transaction_embed(self, economy_panel):
        """測試交易記錄嵌入訊息建立"""
        transactions = [
            Transaction(
                id=1,
                from_account="user_123_456",
                to_account="user_789_456",
                amount=100.0,
                transaction_type=TransactionType.TRANSFER,
                reason="測試轉帳",
                guild_id=456,
                created_by=123,
                created_at=datetime.now()
            ),
            Transaction(
                id=2,
                from_account=None,
                to_account="user_123_456",
                amount=50.0,
                transaction_type=TransactionType.DEPOSIT,
                reason="系統存款",
                guild_id=456,
                created_by=None,
                created_at=datetime.now()
            )
        ]
        
        currency_config = CurrencyConfig(guild_id=456)
        
        embed = await economy_panel.create_transaction_embed(
            transactions, currency_config, page=0, total_pages=1
        )
        
        assert embed.title == "📊 交易記錄"
        assert "頁面 1/1" in embed.description
        assert len(embed.fields) == len(transactions)
    
    @pytest.mark.asyncio
    async def test_create_transaction_embed_empty(self, economy_panel):
        """測試空交易記錄嵌入訊息建立"""
        currency_config = CurrencyConfig(guild_id=456)
        
        embed = await economy_panel.create_transaction_embed(
            [], currency_config, page=0, total_pages=1
        )
        
        assert embed.title == "📊 交易記錄"
        record_field = next((f for f in embed.fields if "記錄" in f.name), None)
        assert record_field is not None
        assert "尚無交易記錄" in record_field.value
    
    # ==========================================================================
    # 權限驗證測試
    # ==========================================================================
    
    @pytest.mark.asyncio
    async def test_check_admin_permissions_with_admin(self, economy_panel, mock_admin_interaction):
        """測試管理員權限檢查（有權限）"""
        result = await economy_panel._check_admin_permissions(mock_admin_interaction)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_check_admin_permissions_without_admin(self, economy_panel, mock_interaction):
        """測試管理員權限檢查（無權限）"""
        # 模擬一般使用者
        regular_member = Mock(spec=discord.Member)
        regular_member.guild_permissions = Mock()
        regular_member.guild_permissions.administrator = False
        regular_member.guild_permissions.manage_guild = False
        
        mock_interaction.user = regular_member
        
        result = await economy_panel._check_admin_permissions(mock_interaction)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_validate_permissions_admin_action(self, economy_panel, mock_admin_interaction):
        """測試管理員動作權限驗證"""
        result = await economy_panel._validate_permissions(mock_admin_interaction, "admin_panel")
        assert result is True
        
        result = await economy_panel._validate_permissions(mock_admin_interaction, "manage_balance")
        assert result is True
    
    @pytest.mark.asyncio
    async def test_validate_permissions_regular_action(self, economy_panel, mock_interaction):
        """測試一般動作權限驗證"""
        result = await economy_panel._validate_permissions(mock_interaction, "show_balance")
        assert result is True
        
        result = await economy_panel._validate_permissions(mock_interaction, "show_transactions")
        assert result is True
    
    # ==========================================================================
    # 斜線指令處理測試
    # ==========================================================================
    
    @pytest.mark.asyncio
    async def test_handle_slash_command_economy(self, economy_panel, mock_interaction):
        """測試 /economy 指令處理"""
        mock_interaction.data['name'] = 'economy'
        
        with patch.object(economy_panel, '_show_main_panel') as mock_show:
            await economy_panel._handle_slash_command(mock_interaction)
            mock_show.assert_called_once_with(mock_interaction)
    
    @pytest.mark.asyncio
    async def test_handle_slash_command_balance(self, economy_panel, mock_interaction):
        """測試 /balance 指令處理"""
        mock_interaction.data['name'] = 'balance'
        
        with patch.object(economy_panel, '_handle_balance_command') as mock_handle:
            await economy_panel._handle_slash_command(mock_interaction)
            mock_handle.assert_called_once_with(mock_interaction)
    
    @pytest.mark.asyncio
    async def test_handle_slash_command_admin_with_permission(self, economy_panel, mock_admin_interaction):
        """測試 /economy_admin 指令處理（有權限）"""
        mock_admin_interaction.data['name'] = 'economy_admin'
        
        with patch.object(economy_panel, '_show_admin_panel') as mock_show:
            await economy_panel._handle_slash_command(mock_admin_interaction)
            mock_show.assert_called_once_with(mock_admin_interaction)
    
    @pytest.mark.asyncio
    async def test_handle_slash_command_admin_without_permission(self, economy_panel, mock_interaction):
        """測試 /economy_admin 指令處理（無權限）"""
        mock_interaction.data['name'] = 'economy_admin'
        
        # 模擬一般使用者
        regular_member = Mock(spec=discord.Member)
        regular_member.guild_permissions = Mock()
        regular_member.guild_permissions.administrator = False
        regular_member.guild_permissions.manage_guild = False
        mock_interaction.user = regular_member
        
        with patch.object(economy_panel, 'send_error') as mock_send_error:
            await economy_panel._handle_slash_command(mock_interaction)
            mock_send_error.assert_called_once()
    
    # ==========================================================================
    # 主面板功能測試
    # ==========================================================================
    
    @pytest.mark.asyncio
    async def test_show_main_panel_existing_account(self, economy_panel, mock_interaction):
        """測試顯示主面板（現有帳戶）"""
        await economy_panel._show_main_panel(mock_interaction)
        
        # 驗證服務調用
        economy_panel.economy_service.get_account.assert_called_once_with("user_123_456")
        economy_panel.economy_service.get_currency_config.assert_called_once_with(456)
        
        # 驗證回應
        mock_interaction.response.send_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_show_main_panel_new_account(self, economy_panel, mock_interaction):
        """測試顯示主面板（新帳戶）"""
        # 模擬帳戶不存在的情況
        economy_panel.economy_service.get_account.return_value = None
        
        await economy_panel._show_main_panel(mock_interaction)
        
        # 驗證創建新帳戶
        economy_panel.economy_service.create_account.assert_called_once_with(
            guild_id=456,
            account_type=AccountType.USER,
            user_id=123,
            initial_balance=0.0
        )
    
    @pytest.mark.asyncio
    async def test_handle_balance_command_self(self, economy_panel, mock_interaction):
        """測試餘額查詢指令（查詢自己）"""
        mock_interaction.data = {}  # 沒有指定目標使用者
        
        await economy_panel._handle_balance_command(mock_interaction)
        
        # 驗證服務調用
        economy_panel.economy_service.get_account.assert_called_with("user_123_456")
        mock_interaction.response.send_message.assert_called_once()
    
    # ==========================================================================
    # 使用者功能處理測試
    # ==========================================================================
    
    @pytest.mark.asyncio
    async def test_handle_show_balance(self, economy_panel, mock_interaction):
        """測試顯示餘額處理"""
        with patch.object(economy_panel, '_show_main_panel') as mock_show:
            await economy_panel._handle_show_balance(mock_interaction)
            mock_show.assert_called_once_with(mock_interaction)
    
    @pytest.mark.asyncio
    async def test_handle_show_transactions(self, economy_panel, mock_interaction):
        """測試顯示交易記錄處理"""
        await economy_panel._handle_show_transactions(mock_interaction)
        
        # 驗證服務調用
        economy_panel.economy_service.get_transaction_history.assert_called_once_with(
            account_id="user_123_456",
            limit=economy_panel.transactions_per_page
        )
        
        # 驗證回應
        mock_interaction.response.edit_message.assert_called_once()
    
    # ==========================================================================
    # 管理員功能測試
    # ==========================================================================
    
    @pytest.mark.asyncio
    async def test_show_admin_panel(self, economy_panel, mock_admin_interaction):
        """測試顯示管理員面板"""
        await economy_panel._show_admin_panel(mock_admin_interaction)
        
        # 驗證服務調用
        economy_panel.economy_service.get_guild_accounts.assert_called_once_with(456)
        economy_panel.economy_service.get_currency_config.assert_called_once_with(456)
        
        # 驗證回應
        mock_admin_interaction.response.send_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_manage_balance(self, economy_panel, mock_admin_interaction):
        """測試處理餘額管理"""
        await economy_panel._handle_manage_balance(mock_admin_interaction)
        
        # 驗證顯示模態框
        mock_admin_interaction.response.send_modal.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_currency_settings(self, economy_panel, mock_admin_interaction):
        """測試處理貨幣設定"""
        await economy_panel._handle_currency_settings(mock_admin_interaction)
        
        # 驗證服務調用和模態框顯示
        economy_panel.economy_service.get_currency_config.assert_called_with(456)
        mock_admin_interaction.response.send_modal.assert_called_once()


class TestUIComponents:
    """UI 組件測試類別"""
    
    @pytest.fixture
    def mock_panel(self):
        """建立模擬面板"""
        panel = Mock(spec=EconomyPanel)
        panel._handle_show_balance = AsyncMock()
        panel._handle_show_transactions = AsyncMock()
        panel._handle_transaction_prev = AsyncMock()
        panel._handle_transaction_next = AsyncMock()
        panel._handle_manage_balance = AsyncMock()
        panel._handle_currency_settings = AsyncMock()
        panel._handle_audit_log = AsyncMock()
        return panel
    
    @pytest.fixture
    def mock_account(self):
        """建立模擬帳戶"""
        return Account(
            id="user_123_456",
            account_type=AccountType.USER,
            guild_id=456,
            user_id=123,
            balance=1000.0,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
    
    @pytest.fixture
    def mock_currency_config(self):
        """建立模擬貨幣配置"""
        return CurrencyConfig(guild_id=456)
    
    @pytest.mark.asyncio
    async def test_user_economy_view_initialization(self, mock_panel, mock_account, mock_currency_config):
        """測試使用者經濟視圖初始化"""
        view = UserEconomyView(mock_panel, mock_account, mock_currency_config)
        
        assert view.panel == mock_panel
        assert view.account == mock_account
        assert view.currency_config == mock_currency_config
        assert len(view.children) == 2  # 兩個按鈕
    
    @pytest.mark.asyncio
    async def test_transaction_history_view_initialization(self, mock_panel, mock_currency_config):
        """測試交易記錄視圖初始化"""
        from panels.economy_panel import TransactionHistoryView
        
        view = TransactionHistoryView(mock_panel, "user_123_456", mock_currency_config, 0, 5)
        
        assert view.panel == mock_panel
        assert view.account_id == "user_123_456"
        assert view.current_page == 0
        assert view.total_pages == 5
        assert len(view.children) == 3  # 三個按鈕
    
    @pytest.mark.asyncio
    async def test_admin_economy_view_initialization(self, mock_panel, mock_currency_config):
        """測試管理員經濟視圖初始化"""
        view = AdminEconomyView(mock_panel, mock_currency_config)
        
        assert view.panel == mock_panel
        assert view.currency_config == mock_currency_config
        assert len(view.children) == 3  # 三個按鈕


# =============================================================================
# 測試執行輔助函數
# =============================================================================

if __name__ == "__main__":
    """直接執行測試"""
    pytest.main([__file__, "-v", "--tb=short"])