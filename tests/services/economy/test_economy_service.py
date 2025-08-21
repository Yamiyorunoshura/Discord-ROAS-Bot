"""
經濟服務測試
Task ID: 2 - 實作經濟系統核心功能

測試 services/economy/economy_service.py 中的 EconomyService 類別
包含所有核心功能的單元測試、整合測試和邊界條件測試
"""

import pytest
import asyncio
import sys
import os
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
from typing import Optional

# 添加專案根目錄到 Python 路徑
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from services.economy.economy_service import EconomyService
from services.economy.models import AccountType, TransactionType, Account, Transaction, CurrencyConfig
from core.database_manager import DatabaseManager
from core.exceptions import ValidationError, ServiceError, DatabaseError


@pytest.fixture
async def mock_db_manager():
    """模擬資料庫管理器"""
    db_manager = Mock(spec=DatabaseManager)
    db_manager.is_initialized = True
    
    # 模擬所有異步方法
    db_manager.execute = AsyncMock()
    db_manager.fetchone = AsyncMock()
    db_manager.fetchall = AsyncMock()
    db_manager.transaction = AsyncMock()
    
    return db_manager


@pytest.fixture
async def economy_service(mock_db_manager):
    """經濟服務實例"""
    service = EconomyService()
    service.add_dependency(mock_db_manager, "database_manager")
    await service.initialize()
    return service


@pytest.fixture
def sample_account():
    """範例帳戶"""
    return Account(
        id="user_123_456",
        account_type=AccountType.USER,
        guild_id=456,
        user_id=123,
        balance=100.0,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )


@pytest.fixture
def sample_currency_config():
    """範例貨幣配置"""
    return CurrencyConfig(
        guild_id=456,
        currency_name="測試幣",
        currency_symbol="🪙",
        min_transfer_amount=1.0,
        max_transfer_amount=1000.0
    )


class TestEconomyServiceInitialization:
    """測試 EconomyService 初始化"""
    
    async def test_service_initialization(self, mock_db_manager):
        """測試服務初始化"""
        service = EconomyService()
        service.add_dependency(mock_db_manager, "database_manager")
        
        # 模擬資料庫遷移應用
        mock_db_manager.migration_manager = Mock()
        mock_db_manager.migration_manager.add_migration = Mock()
        mock_db_manager.migration_manager.apply_migrations = AsyncMock(return_value=True)
        
        result = await service.initialize()
        assert result is True
        assert service.is_initialized
    
    async def test_service_initialization_without_db(self):
        """測試沒有資料庫依賴的初始化失敗"""
        service = EconomyService()
        result = await service.initialize()
        assert result is False


class TestAccountManagement:
    """測試帳戶管理功能"""
    
    async def test_create_user_account_success(self, economy_service, mock_db_manager):
        """測試成功建立使用者帳戶"""
        # 模擬帳戶不存在
        mock_db_manager.fetchone.return_value = None
        
        account = await economy_service.create_account(
            user_id=123,
            guild_id=456,
            account_type=AccountType.USER,
            initial_balance=50.0
        )
        
        assert account.id == "user_123_456"
        assert account.account_type == AccountType.USER
        assert account.balance == 50.0
        mock_db_manager.execute.assert_called()
    
    async def test_create_government_account_success(self, economy_service, mock_db_manager):
        """測試成功建立政府帳戶"""
        mock_db_manager.fetchone.return_value = None
        
        account = await economy_service.create_account(
            guild_id=456,
            account_type=AccountType.GOVERNMENT_COUNCIL,
            initial_balance=1000.0
        )
        
        assert account.id == "gov_council_456"
        assert account.account_type == AccountType.GOVERNMENT_COUNCIL
        assert account.user_id is None
    
    async def test_create_account_already_exists(self, economy_service, mock_db_manager):
        """測試建立已存在的帳戶"""
        # 模擬帳戶已存在
        mock_db_manager.fetchone.return_value = {
            'id': 'user_123_456',
            'account_type': 'user',
            'guild_id': 456,
            'user_id': 123,
            'balance': 100.0,
            'created_at': '2025-08-17T10:00:00',
            'updated_at': '2025-08-17T10:00:00',
            'is_active': 1,
            'metadata': None
        }
        
        with pytest.raises(ServiceError):
            await economy_service.create_account(
                user_id=123,
                guild_id=456,
                account_type=AccountType.USER
            )
    
    async def test_get_account_success(self, economy_service, mock_db_manager):
        """測試成功獲取帳戶"""
        mock_db_manager.fetchone.return_value = {
            'id': 'user_123_456',
            'account_type': 'user',
            'guild_id': 456,
            'user_id': 123,
            'balance': 100.0,
            'created_at': '2025-08-17T10:00:00',
            'updated_at': '2025-08-17T10:00:00',
            'is_active': 1,
            'metadata': None
        }
        
        account = await economy_service.get_account("user_123_456")
        assert account is not None
        assert account.id == "user_123_456"
        assert account.balance == 100.0
    
    async def test_get_account_not_found(self, economy_service, mock_db_manager):
        """測試獲取不存在的帳戶"""
        mock_db_manager.fetchone.return_value = None
        
        account = await economy_service.get_account("nonexistent")
        assert account is None
    
    async def test_get_balance_success(self, economy_service, mock_db_manager):
        """測試成功獲取帳戶餘額"""
        mock_db_manager.fetchone.return_value = {
            'balance': 150.0
        }
        
        balance = await economy_service.get_balance("user_123_456")
        assert balance == 150.0
    
    async def test_get_balance_account_not_found(self, economy_service, mock_db_manager):
        """測試獲取不存在帳戶的餘額"""
        mock_db_manager.fetchone.return_value = None
        
        with pytest.raises(ServiceError):
            await economy_service.get_balance("nonexistent")


class TestTransactionManagement:
    """測試交易管理功能"""
    
    async def test_transfer_success(self, economy_service, mock_db_manager):
        """測試成功轉帳"""
        # 模擬帳戶存在且餘額足夠
        def mock_fetchone_side_effect(query, params=()):
            if "balance" in query and params[0] == "user_123_456":
                return {'balance': 100.0}
            elif "balance" in query and params[0] == "user_789_456":
                return {'balance': 50.0}
            return None
        
        mock_db_manager.fetchone.side_effect = mock_fetchone_side_effect
        
        # 模擬事務上下文
        transaction_context = AsyncMock()
        mock_db_manager.transaction.return_value.__aenter__ = AsyncMock(return_value=transaction_context)
        mock_db_manager.transaction.return_value.__aexit__ = AsyncMock(return_value=None)
        
        transaction = await economy_service.transfer(
            from_account_id="user_123_456",
            to_account_id="user_789_456",
            amount=30.0,
            reason="測試轉帳",
            created_by=123
        )
        
        assert transaction is not None
        assert transaction.amount == 30.0
        assert transaction.transaction_type == TransactionType.TRANSFER
        mock_db_manager.execute.assert_called()
    
    async def test_transfer_insufficient_balance(self, economy_service, mock_db_manager):
        """測試餘額不足的轉帳"""
        def mock_fetchone_side_effect(query, params=()):
            if "balance" in query and params[0] == "user_123_456":
                return {'balance': 10.0}  # 餘額不足
            elif "balance" in query and params[0] == "user_789_456":
                return {'balance': 50.0}
            return None
        
        mock_db_manager.fetchone.side_effect = mock_fetchone_side_effect
        
        with pytest.raises(ServiceError):
            await economy_service.transfer(
                from_account_id="user_123_456",
                to_account_id="user_789_456",
                amount=30.0,
                reason="測試轉帳",
                created_by=123
            )
    
    async def test_transfer_same_account(self, economy_service, mock_db_manager):
        """測試向自己轉帳"""
        with pytest.raises(ValidationError):
            await economy_service.transfer(
                from_account_id="user_123_456",
                to_account_id="user_123_456",
                amount=30.0,
                reason="測試轉帳",
                created_by=123
            )
    
    async def test_deposit_success(self, economy_service, mock_db_manager):
        """測試成功存款"""
        # 模擬帳戶存在
        mock_db_manager.fetchone.return_value = {'balance': 100.0}
        
        transaction_context = AsyncMock()
        mock_db_manager.transaction.return_value.__aenter__ = AsyncMock(return_value=transaction_context)
        mock_db_manager.transaction.return_value.__aexit__ = AsyncMock(return_value=None)
        
        transaction = await economy_service.deposit(
            account_id="user_123_456",
            amount=50.0,
            reason="系統獎勵",
            created_by=123
        )
        
        assert transaction is not None
        assert transaction.amount == 50.0
        assert transaction.transaction_type == TransactionType.DEPOSIT
        assert transaction.from_account is None
    
    async def test_withdraw_success(self, economy_service, mock_db_manager):
        """測試成功提款"""
        # 模擬帳戶存在且餘額足夠
        mock_db_manager.fetchone.return_value = {'balance': 100.0}
        
        transaction_context = AsyncMock()
        mock_db_manager.transaction.return_value.__aenter__ = AsyncMock(return_value=transaction_context)
        mock_db_manager.transaction.return_value.__aexit__ = AsyncMock(return_value=None)
        
        transaction = await economy_service.withdraw(
            account_id="user_123_456",
            amount=30.0,
            reason="提取資金",
            created_by=123
        )
        
        assert transaction is not None
        assert transaction.amount == 30.0
        assert transaction.transaction_type == TransactionType.WITHDRAW
        assert transaction.to_account is None
    
    async def test_get_transaction_history(self, economy_service, mock_db_manager):
        """測試獲取交易記錄"""
        mock_transactions = [
            {
                'id': 1,
                'from_account': 'user_123_456',
                'to_account': 'user_789_456',
                'amount': 30.0,
                'transaction_type': 'transfer',
                'reason': '測試轉帳',
                'guild_id': 456,
                'created_by': 123,
                'created_at': '2025-08-17T10:00:00',
                'status': 'completed',
                'reference_id': None,
                'metadata': None
            }
        ]
        mock_db_manager.fetchall.return_value = mock_transactions
        
        transactions = await economy_service.get_transaction_history(
            account_id="user_123_456",
            limit=10
        )
        
        assert len(transactions) == 1
        assert transactions[0].amount == 30.0
        assert transactions[0].transaction_type == TransactionType.TRANSFER


class TestCurrencyConfiguration:
    """測試貨幣配置功能"""
    
    async def test_get_currency_config_exists(self, economy_service, mock_db_manager):
        """測試獲取存在的貨幣配置"""
        mock_config = {
            'guild_id': 456,
            'currency_name': '測試幣',
            'currency_symbol': '🪙',
            'decimal_places': 2,
            'min_transfer_amount': 1.0,
            'max_transfer_amount': 1000.0,
            'daily_transfer_limit': None,
            'enable_negative_balance': 0,
            'created_at': '2025-08-17T10:00:00',
            'updated_at': '2025-08-17T10:00:00'
        }
        mock_db_manager.fetchone.return_value = mock_config
        
        config = await economy_service.get_currency_config(456)
        assert config is not None
        assert config.currency_name == "測試幣"
        assert config.currency_symbol == "🪙"
    
    async def test_get_currency_config_default(self, economy_service, mock_db_manager):
        """測試獲取預設貨幣配置"""
        mock_db_manager.fetchone.return_value = None
        
        config = await economy_service.get_currency_config(456)
        assert config is not None
        assert config.currency_name == "金幣"
        assert config.currency_symbol == "💰"
    
    async def test_set_currency_config_new(self, economy_service, mock_db_manager):
        """測試設定新的貨幣配置"""
        mock_db_manager.fetchone.return_value = None  # 配置不存在
        
        config = await economy_service.set_currency_config(
            guild_id=456,
            currency_name="新貨幣",
            currency_symbol="🚀",
            decimal_places=3
        )
        
        assert config.currency_name == "新貨幣"
        assert config.currency_symbol == "🚀"
        assert config.decimal_places == 3
        mock_db_manager.execute.assert_called()
    
    async def test_set_currency_config_update(self, economy_service, mock_db_manager):
        """測試更新現有貨幣配置"""
        existing_config = {
            'guild_id': 456,
            'currency_name': '舊貨幣',
            'currency_symbol': '💰',
            'decimal_places': 2,
            'min_transfer_amount': 1.0,
            'max_transfer_amount': None,
            'daily_transfer_limit': None,
            'enable_negative_balance': 0,
            'created_at': '2025-08-17T09:00:00',
            'updated_at': '2025-08-17T09:00:00'
        }
        mock_db_manager.fetchone.return_value = existing_config
        
        config = await economy_service.set_currency_config(
            guild_id=456,
            currency_name="更新貨幣"
        )
        
        assert config.currency_name == "更新貨幣"
        mock_db_manager.execute.assert_called()


class TestPermissionValidation:
    """測試權限驗證功能"""
    
    async def test_validate_permissions_user_operation(self, economy_service):
        """測試使用者操作權限驗證"""
        result = await economy_service.validate_permissions(123, 456, "transfer")
        assert result is True
    
    async def test_validate_permissions_admin_operation(self, economy_service):
        """測試管理員操作權限驗證"""
        # TODO: 當實作權限系統時，這裡需要更詳細的測試
        result = await economy_service.validate_permissions(123, 456, "admin_transfer")
        assert result is True


class TestErrorHandling:
    """測試錯誤處理"""
    
    async def test_database_error_handling(self, economy_service, mock_db_manager):
        """測試資料庫錯誤處理"""
        mock_db_manager.fetchone.side_effect = DatabaseError("資料庫連接失敗", "query")
        
        with pytest.raises(ServiceError):
            await economy_service.get_balance("user_123_456")
    
    async def test_validation_error_propagation(self, economy_service):
        """測試驗證錯誤傳播"""
        with pytest.raises(ValidationError):
            await economy_service.transfer(
                from_account_id="invalid_id",
                to_account_id="user_789_456",
                amount=30.0,
                reason="測試",
                created_by=123
            )


class TestConcurrencyAndPerformance:
    """測試並發性和效能"""
    
    async def test_concurrent_transfers(self, economy_service, mock_db_manager):
        """測試並發轉帳操作"""
        # 模擬多個帳戶
        def mock_fetchone_side_effect(query, params=()):
            if "balance" in query:
                return {'balance': 1000.0}  # 足夠的餘額
            return None
        
        mock_db_manager.fetchone.side_effect = mock_fetchone_side_effect
        
        transaction_context = AsyncMock()
        mock_db_manager.transaction.return_value.__aenter__ = AsyncMock(return_value=transaction_context)
        mock_db_manager.transaction.return_value.__aexit__ = AsyncMock(return_value=None)
        
        # 建立多個並發轉帳任務
        tasks = []
        for i in range(5):
            task = economy_service.transfer(
                from_account_id="user_123_456",
                to_account_id=f"user_{789+i}_456",
                amount=10.0,
                reason=f"並發測試 {i}",
                created_by=123
            )
            tasks.append(task)
        
        # 執行並發操作
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 檢查結果
        for result in results:
            if isinstance(result, Exception):
                pytest.fail(f"並發操作失敗：{result}")
            assert result.amount == 10.0
    
    @pytest.mark.performance
    async def test_balance_query_performance(self, economy_service, mock_db_manager):
        """測試餘額查詢效能（目標：< 100ms）"""
        import time
        
        mock_db_manager.fetchone.return_value = {'balance': 100.0}
        
        start_time = time.time()
        await economy_service.get_balance("user_123_456")
        end_time = time.time()
        
        execution_time = (end_time - start_time) * 1000  # 轉換為毫秒
        assert execution_time < 100, f"餘額查詢耗時 {execution_time:.2f}ms，超過 100ms 目標"
    
    @pytest.mark.performance
    async def test_transfer_performance(self, economy_service, mock_db_manager):
        """測試轉帳操作效能（目標：< 200ms）"""
        import time
        
        def mock_fetchone_side_effect(query, params=()):
            if "balance" in query:
                return {'balance': 1000.0}
            return None
        
        mock_db_manager.fetchone.side_effect = mock_fetchone_side_effect
        
        transaction_context = AsyncMock()
        mock_db_manager.transaction.return_value.__aenter__ = AsyncMock(return_value=transaction_context)
        mock_db_manager.transaction.return_value.__aexit__ = AsyncMock(return_value=None)
        
        start_time = time.time()
        await economy_service.transfer(
            from_account_id="user_123_456",
            to_account_id="user_789_456",
            amount=50.0,
            reason="效能測試",
            created_by=123
        )
        end_time = time.time()
        
        execution_time = (end_time - start_time) * 1000  # 轉換為毫秒
        assert execution_time < 200, f"轉帳操作耗時 {execution_time:.2f}ms，超過 200ms 目標"