"""
UI 組件互動測試
Task ID: 3 - 實作經濟系統使用者介面

測試 Discord UI 組件的互動功能，包括：
- 按鈕點擊處理
- 模態框提交處理
- 分頁導航功能
- 超時處理
- 組件狀態管理
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from datetime import datetime
import discord

# 測試目標
from panels.economy_panel import (
    UserEconomyView, TransactionHistoryView, AdminEconomyView,
    BalanceManagementModal, CurrencySettingsModal, EconomyPanel
)
from services.economy.models import Account, CurrencyConfig, AccountType


class TestUserEconomyView:
    """使用者經濟視圖測試"""
    
    @pytest.fixture
    def mock_panel(self):
        """建立模擬面板"""
        panel = Mock(spec=EconomyPanel)
        panel._handle_show_balance = AsyncMock()
        panel._handle_show_transactions = AsyncMock()
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
    
    @pytest.fixture
    def user_view(self, mock_panel, mock_account, mock_currency_config):
        """建立使用者經濟視圖"""
        return UserEconomyView(mock_panel, mock_account, mock_currency_config)
    
    @pytest.fixture
    def mock_interaction(self):
        """建立模擬互動"""
        interaction = Mock(spec=discord.Interaction)
        interaction.user = Mock()
        interaction.user.id = 123
        interaction.response = Mock()
        interaction.response.send_message = AsyncMock()
        return interaction
    
    def test_view_initialization(self, user_view, mock_panel, mock_account, mock_currency_config):
        """測試視圖初始化"""
        assert user_view.panel == mock_panel
        assert user_view.account == mock_account
        assert user_view.currency_config == mock_currency_config
        assert user_view.timeout == 300
        assert len(user_view.children) == 2
    
    def test_view_buttons_configuration(self, user_view):
        """測試按鈕配置"""
        buttons = [child for child in user_view.children if isinstance(child, discord.ui.Button)]
        
        assert len(buttons) == 2
        
        # 查看餘額按鈕
        balance_button = next((b for b in buttons if "餘額" in b.label), None)
        assert balance_button is not None
        assert balance_button.style == discord.ButtonStyle.primary
        assert balance_button.custom_id == "economy_show_balance"
        
        # 交易記錄按鈕
        transaction_button = next((b for b in buttons if "交易記錄" in b.label), None)
        assert transaction_button is not None
        assert transaction_button.style == discord.ButtonStyle.secondary
        assert transaction_button.custom_id == "economy_show_transactions"
    
    @pytest.mark.asyncio
    async def test_show_balance_button_click(self, user_view, mock_interaction):
        """測試查看餘額按鈕點擊"""
        # 找到餘額按鈕
        balance_button = next(
            (child for child in user_view.children if "餘額" in child.label), 
            None
        )
        assert balance_button is not None
        
        # 模擬按鈕點擊
        await balance_button.callback(mock_interaction)
        
        # 驗證面板方法被調用
        user_view.panel._handle_show_balance.assert_called_once_with(mock_interaction)
    
    @pytest.mark.asyncio
    async def test_show_transactions_button_click(self, user_view, mock_interaction):
        """測試交易記錄按鈕點擊"""
        # 找到交易記錄按鈕
        transaction_button = next(
            (child for child in user_view.children if "交易記錄" in child.label), 
            None
        )
        assert transaction_button is not None
        
        # 模擬按鈕點擊
        await transaction_button.callback(mock_interaction)
        
        # 驗證面板方法被調用
        user_view.panel._handle_show_transactions.assert_called_once_with(mock_interaction)
    
    @pytest.mark.asyncio
    async def test_view_timeout(self, user_view):
        """測試視圖超時處理"""
        # 模擬超時
        await user_view.on_timeout()
        
        # 驗證所有按鈕都被禁用
        for child in user_view.children:
            assert child.disabled is True


class TestTransactionHistoryView:
    """交易記錄視圖測試"""
    
    @pytest.fixture
    def mock_panel(self):
        """建立模擬面板"""
        panel = Mock(spec=EconomyPanel)
        panel._handle_transaction_prev = AsyncMock()
        panel._handle_transaction_next = AsyncMock()
        panel._handle_show_transactions = AsyncMock()
        return panel
    
    @pytest.fixture
    def mock_currency_config(self):
        """建立模擬貨幣配置"""
        return CurrencyConfig(guild_id=456)
    
    @pytest.fixture
    def transaction_view_first_page(self, mock_panel, mock_currency_config):
        """建立第一頁交易記錄視圖"""
        return TransactionHistoryView(
            mock_panel, "user_123_456", mock_currency_config, 0, 5
        )
    
    @pytest.fixture
    def transaction_view_middle_page(self, mock_panel, mock_currency_config):
        """建立中間頁交易記錄視圖"""
        return TransactionHistoryView(
            mock_panel, "user_123_456", mock_currency_config, 2, 5
        )
    
    @pytest.fixture
    def transaction_view_last_page(self, mock_panel, mock_currency_config):
        """建立最後一頁交易記錄視圖"""
        return TransactionHistoryView(
            mock_panel, "user_123_456", mock_currency_config, 4, 5
        )
    
    @pytest.fixture
    def mock_interaction(self):
        """建立模擬互動"""
        interaction = Mock(spec=discord.Interaction)
        interaction.user = Mock()
        interaction.user.id = 123
        return interaction
    
    def test_view_initialization(self, transaction_view_middle_page, mock_panel, mock_currency_config):
        """測試視圖初始化"""
        view = transaction_view_middle_page
        
        assert view.panel == mock_panel
        assert view.account_id == "user_123_456"
        assert view.currency_config == mock_currency_config
        assert view.current_page == 2
        assert view.total_pages == 5
        assert view.timeout == 300
        assert len(view.children) == 3
    
    def test_view_buttons_configuration(self, transaction_view_middle_page):
        """測試按鈕配置"""
        view = transaction_view_middle_page
        buttons = [child for child in view.children if isinstance(child, discord.ui.Button)]
        
        assert len(buttons) == 3
        
        # 上一頁按鈕
        prev_button = next((b for b in buttons if "上一頁" in b.label), None)
        assert prev_button is not None
        assert prev_button.custom_id == "economy_transaction_prev"
        assert not prev_button.disabled  # 中間頁不應該禁用
        
        # 下一頁按鈕
        next_button = next((b for b in buttons if "下一頁" in b.label), None)
        assert next_button is not None
        assert next_button.custom_id == "economy_transaction_next"
        assert not next_button.disabled  # 中間頁不應該禁用
        
        # 重新整理按鈕
        refresh_button = next((b for b in buttons if "重新整理" in b.label), None)
        assert refresh_button is not None
        assert refresh_button.custom_id == "economy_show_transactions"
    
    def test_first_page_button_states(self, transaction_view_first_page):
        """測試第一頁按鈕狀態"""
        view = transaction_view_first_page
        buttons = [child for child in view.children if isinstance(child, discord.ui.Button)]
        
        # 上一頁按鈕應該被禁用
        prev_button = next((b for b in buttons if "上一頁" in b.label), None)
        assert prev_button.disabled is True
        
        # 下一頁按鈕應該啟用
        next_button = next((b for b in buttons if "下一頁" in b.label), None)
        assert next_button.disabled is False
    
    def test_last_page_button_states(self, transaction_view_last_page):
        """測試最後一頁按鈕狀態"""
        view = transaction_view_last_page
        buttons = [child for child in view.children if isinstance(child, discord.ui.Button)]
        
        # 上一頁按鈕應該啟用
        prev_button = next((b for b in buttons if "上一頁" in b.label), None)
        assert prev_button.disabled is False
        
        # 下一頁按鈕應該被禁用
        next_button = next((b for b in buttons if "下一頁" in b.label), None)
        assert next_button.disabled is True
    
    @pytest.mark.asyncio
    async def test_prev_page_button_click(self, transaction_view_middle_page, mock_interaction):
        """測試上一頁按鈕點擊"""
        view = transaction_view_middle_page
        prev_button = next((b for b in view.children if "上一頁" in b.label), None)
        
        await prev_button.callback(mock_interaction)
        
        view.panel._handle_transaction_prev.assert_called_once_with(mock_interaction)
    
    @pytest.mark.asyncio
    async def test_next_page_button_click(self, transaction_view_middle_page, mock_interaction):
        """測試下一頁按鈕點擊"""
        view = transaction_view_middle_page
        next_button = next((b for b in view.children if "下一頁" in b.label), None)
        
        await next_button.callback(mock_interaction)
        
        view.panel._handle_transaction_next.assert_called_once_with(mock_interaction)
    
    @pytest.mark.asyncio
    async def test_refresh_button_click(self, transaction_view_middle_page, mock_interaction):
        """測試重新整理按鈕點擊"""
        view = transaction_view_middle_page
        refresh_button = next((b for b in view.children if "重新整理" in b.label), None)
        
        await refresh_button.callback(mock_interaction)
        
        view.panel._handle_show_transactions.assert_called_once_with(mock_interaction)


class TestAdminEconomyView:
    """管理員經濟視圖測試"""
    
    @pytest.fixture
    def mock_panel(self):
        """建立模擬面板"""
        panel = Mock(spec=EconomyPanel)
        panel._handle_manage_balance = AsyncMock()
        panel._handle_currency_settings = AsyncMock()
        panel._handle_audit_log = AsyncMock()
        return panel
    
    @pytest.fixture
    def mock_currency_config(self):
        """建立模擬貨幣配置"""
        return CurrencyConfig(guild_id=456)
    
    @pytest.fixture
    def admin_view(self, mock_panel, mock_currency_config):
        """建立管理員經濟視圖"""
        return AdminEconomyView(mock_panel, mock_currency_config)
    
    @pytest.fixture
    def mock_interaction(self):
        """建立模擬互動"""
        interaction = Mock(spec=discord.Interaction)
        interaction.user = Mock()
        interaction.user.id = 999
        return interaction
    
    def test_view_initialization(self, admin_view, mock_panel, mock_currency_config):
        """測試視圖初始化"""
        assert admin_view.panel == mock_panel
        assert admin_view.currency_config == mock_currency_config
        assert admin_view.timeout == 600  # 管理員面板超時時間較長
        assert len(admin_view.children) == 3
    
    def test_view_buttons_configuration(self, admin_view):
        """測試按鈕配置"""
        buttons = [child for child in admin_view.children if isinstance(child, discord.ui.Button)]
        
        assert len(buttons) == 3
        
        # 餘額管理按鈕
        balance_button = next((b for b in buttons if "餘額管理" in b.label), None)
        assert balance_button is not None
        assert balance_button.style == discord.ButtonStyle.primary
        assert balance_button.custom_id == "economy_manage_balance"
        
        # 貨幣設定按鈕
        currency_button = next((b for b in buttons if "貨幣設定" in b.label), None)
        assert currency_button is not None
        assert currency_button.style == discord.ButtonStyle.secondary
        assert currency_button.custom_id == "economy_currency_settings"
        
        # 審計日誌按鈕
        audit_button = next((b for b in buttons if "審計日誌" in b.label), None)
        assert audit_button is not None
        assert audit_button.style == discord.ButtonStyle.secondary
        assert audit_button.custom_id == "economy_audit_log"
    
    @pytest.mark.asyncio
    async def test_manage_balance_button_click(self, admin_view, mock_interaction):
        """測試餘額管理按鈕點擊"""
        balance_button = next((b for b in admin_view.children if "餘額管理" in b.label), None)
        
        await balance_button.callback(mock_interaction)
        
        admin_view.panel._handle_manage_balance.assert_called_once_with(mock_interaction)
    
    @pytest.mark.asyncio
    async def test_currency_settings_button_click(self, admin_view, mock_interaction):
        """測試貨幣設定按鈕點擊"""
        currency_button = next((b for b in admin_view.children if "貨幣設定" in b.label), None)
        
        await currency_button.callback(mock_interaction)
        
        admin_view.panel._handle_currency_settings.assert_called_once_with(mock_interaction)
    
    @pytest.mark.asyncio
    async def test_audit_log_button_click(self, admin_view, mock_interaction):
        """測試審計日誌按鈕點擊"""
        audit_button = next((b for b in admin_view.children if "審計日誌" in b.label), None)
        
        await audit_button.callback(mock_interaction)
        
        admin_view.panel._handle_audit_log.assert_called_once_with(mock_interaction)


class TestBalanceManagementModal:
    """餘額管理模態框測試"""
    
    @pytest.fixture
    def mock_panel(self):
        """建立模擬面板"""
        panel = Mock(spec=EconomyPanel)
        panel._handle_balance_management_modal = AsyncMock()
        return panel
    
    @pytest.fixture
    def balance_modal(self, mock_panel):
        """建立餘額管理模態框"""
        return BalanceManagementModal(mock_panel)
    
    @pytest.fixture
    def mock_interaction(self):
        """建立模擬互動"""
        interaction = Mock(spec=discord.Interaction)
        interaction.user = Mock()
        interaction.user.id = 999
        return interaction
    
    def test_modal_initialization(self, balance_modal, mock_panel):
        """測試模態框初始化"""
        assert balance_modal.panel == mock_panel
        assert balance_modal.title == "💼 餘額管理"
        assert balance_modal.custom_id == "balance_management_modal"
        assert len(balance_modal.children) == 4  # 四個輸入框
    
    def test_modal_text_inputs_configuration(self, balance_modal):
        """測試模態框文字輸入框配置"""
        text_inputs = [child for child in balance_modal.children if isinstance(child, discord.ui.TextInput)]
        
        assert len(text_inputs) == 4
        
        # 檢查各個輸入框
        input_labels = [input_field.label for input_field in text_inputs]
        assert "目標使用者ID" in input_labels
        assert "操作類型" in input_labels
        assert "金額" in input_labels
        assert "操作原因" in input_labels
        
        # 檢查必要欄位
        required_inputs = [input_field for input_field in text_inputs if input_field.required]
        assert len(required_inputs) == 3  # 前三個是必要欄位
        
        # 檢查可選欄位
        optional_inputs = [input_field for input_field in text_inputs if not input_field.required]
        assert len(optional_inputs) == 1  # 原因是可選欄位
    
    @pytest.mark.asyncio
    async def test_modal_on_submit(self, balance_modal, mock_interaction):
        """測試模態框提交"""
        await balance_modal.on_submit(mock_interaction)
        
        balance_modal.panel._handle_balance_management_modal.assert_called_once_with(mock_interaction)


class TestCurrencySettingsModal:
    """貨幣設定模態框測試"""
    
    @pytest.fixture
    def mock_panel(self):
        """建立模擬面板"""
        panel = Mock(spec=EconomyPanel)
        panel._handle_currency_settings_modal = AsyncMock()
        return panel
    
    @pytest.fixture
    def mock_currency_config(self):
        """建立模擬貨幣配置"""
        return CurrencyConfig(
            guild_id=456,
            currency_name="測試幣",
            currency_symbol="🔥",
            decimal_places=3,
            min_transfer_amount=0.5
        )
    
    @pytest.fixture
    def currency_modal(self, mock_panel, mock_currency_config):
        """建立貨幣設定模態框"""
        return CurrencySettingsModal(mock_panel, mock_currency_config)
    
    @pytest.fixture
    def mock_interaction(self):
        """建立模擬互動"""
        interaction = Mock(spec=discord.Interaction)
        interaction.user = Mock()
        interaction.user.id = 999
        return interaction
    
    def test_modal_initialization(self, currency_modal, mock_panel, mock_currency_config):
        """測試模態框初始化"""
        assert currency_modal.panel == mock_panel
        assert currency_modal.current_config == mock_currency_config
        assert currency_modal.title == "⚙️ 貨幣設定"
        assert currency_modal.custom_id == "currency_settings_modal"
        assert len(currency_modal.children) == 4  # 四個輸入框
    
    def test_modal_text_inputs_configuration(self, currency_modal, mock_currency_config):
        """測試模態框文字輸入框配置"""
        text_inputs = [child for child in currency_modal.children if isinstance(child, discord.ui.TextInput)]
        
        assert len(text_inputs) == 4
        
        # 檢查各個輸入框的預設值
        currency_name_input = next((i for i in text_inputs if i.label == "貨幣名稱"), None)
        assert currency_name_input is not None
        assert currency_name_input.default == mock_currency_config.currency_name
        assert not currency_name_input.required
        
        currency_symbol_input = next((i for i in text_inputs if i.label == "貨幣符號"), None)
        assert currency_symbol_input is not None
        assert currency_symbol_input.default == mock_currency_config.currency_symbol
        
        decimal_places_input = next((i for i in text_inputs if i.label == "小數位數"), None)
        assert decimal_places_input is not None
        assert decimal_places_input.default == str(mock_currency_config.decimal_places)
        
        min_transfer_input = next((i for i in text_inputs if i.label == "最小轉帳金額"), None)
        assert min_transfer_input is not None
        assert min_transfer_input.default == str(mock_currency_config.min_transfer_amount)
    
    def test_modal_all_inputs_optional(self, currency_modal):
        """測試模態框所有輸入框都是可選的"""
        text_inputs = [child for child in currency_modal.children if isinstance(child, discord.ui.TextInput)]
        
        for input_field in text_inputs:
            assert not input_field.required
    
    @pytest.mark.asyncio
    async def test_modal_on_submit(self, currency_modal, mock_interaction):
        """測試模態框提交"""
        await currency_modal.on_submit(mock_interaction)
        
        currency_modal.panel._handle_currency_settings_modal.assert_called_once_with(mock_interaction)


class TestUIInteractionFlows:
    """UI 互動流程測試"""
    
    @pytest.mark.asyncio
    async def test_user_balance_query_flow(self):
        """測試使用者餘額查詢流程"""
        # 建立模擬環境
        mock_panel = Mock(spec=EconomyPanel)
        mock_panel._handle_show_balance = AsyncMock()
        
        mock_account = Account(
            id="user_123_456",
            account_type=AccountType.USER,
            guild_id=456,
            user_id=123,
            balance=1000.0,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        mock_currency_config = CurrencyConfig(guild_id=456)
        
        # 建立視圖和互動
        view = UserEconomyView(mock_panel, mock_account, mock_currency_config)
        
        mock_interaction = Mock(spec=discord.Interaction)
        mock_interaction.user = Mock()
        mock_interaction.user.id = 123
        
        # 執行流程：點擊餘額按鈕
        balance_button = next((b for b in view.children if "餘額" in b.label), None)
        await balance_button.callback(mock_interaction)
        
        # 驗證流程
        mock_panel._handle_show_balance.assert_called_once_with(mock_interaction)
    
    @pytest.mark.asyncio
    async def test_admin_balance_management_flow(self):
        """測試管理員餘額管理流程"""
        # 建立模擬環境
        mock_panel = Mock(spec=EconomyPanel)
        mock_panel._handle_manage_balance = AsyncMock()
        mock_panel._handle_balance_management_modal = AsyncMock()
        
        mock_currency_config = CurrencyConfig(guild_id=456)
        
        # 建立視圖和互動
        admin_view = AdminEconomyView(mock_panel, mock_currency_config)
        balance_modal = BalanceManagementModal(mock_panel)
        
        mock_interaction = Mock(spec=discord.Interaction)
        mock_interaction.user = Mock()
        mock_interaction.user.id = 999
        
        # 執行流程：點擊餘額管理按鈕
        balance_button = next((b for b in admin_view.children if "餘額管理" in b.label), None)
        await balance_button.callback(mock_interaction)
        
        # 然後提交模態框
        await balance_modal.on_submit(mock_interaction)
        
        # 驗證流程
        mock_panel._handle_manage_balance.assert_called_once_with(mock_interaction)
        mock_panel._handle_balance_management_modal.assert_called_once_with(mock_interaction)
    
    @pytest.mark.asyncio
    async def test_transaction_pagination_flow(self):
        """測試交易記錄分頁流程"""
        # 建立模擬環境
        mock_panel = Mock(spec=EconomyPanel)
        mock_panel._handle_transaction_prev = AsyncMock()
        mock_panel._handle_transaction_next = AsyncMock()
        
        mock_currency_config = CurrencyConfig(guild_id=456)
        
        # 建立中間頁視圖
        view = TransactionHistoryView(
            mock_panel, "user_123_456", mock_currency_config, 2, 5
        )
        
        mock_interaction = Mock(spec=discord.Interaction)
        mock_interaction.user = Mock()
        mock_interaction.user.id = 123
        
        # 執行流程：上一頁 -> 下一頁
        prev_button = next((b for b in view.children if "上一頁" in b.label), None)
        next_button = next((b for b in view.children if "下一頁" in b.label), None)
        
        await prev_button.callback(mock_interaction)
        await next_button.callback(mock_interaction)
        
        # 驗證流程
        mock_panel._handle_transaction_prev.assert_called_once_with(mock_interaction)
        mock_panel._handle_transaction_next.assert_called_once_with(mock_interaction)


# =============================================================================
# 測試執行輔助函數
# =============================================================================

if __name__ == "__main__":
    """直接執行測試"""
    pytest.main([__file__, "-v", "--tb=short"])