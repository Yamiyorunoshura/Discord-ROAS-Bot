"""
經濟系統模型測試
Task ID: 2 - 實作經濟系統核心功能

測試 services/economy/models.py 中的所有資料模型和驗證函數
"""

import pytest
import json
import sys
import os
from datetime import datetime
from unittest.mock import Mock

# 添加專案根目錄到 Python 路徑
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from services.economy.models import (
    AccountType, TransactionType, Account, Transaction, CurrencyConfig,
    validate_account_id, generate_account_id, validate_amount,
    validate_guild_id, validate_user_id, format_currency, parse_currency_input
)
from core.exceptions import ValidationError


class TestAccountType:
    """測試 AccountType 枚舉"""
    
    def test_enum_values(self):
        """測試枚舉值"""
        assert AccountType.USER.value == "user"
        assert AccountType.GOVERNMENT_COUNCIL.value == "government_council"
        assert AccountType.GOVERNMENT_DEPARTMENT.value == "government_department"
    
    def test_from_string_valid(self):
        """測試從有效字串建立枚舉"""
        assert AccountType.from_string("user") == AccountType.USER
        assert AccountType.from_string("USER") == AccountType.USER
        assert AccountType.from_string("government_council") == AccountType.GOVERNMENT_COUNCIL
    
    def test_from_string_invalid(self):
        """測試從無效字串建立枚舉"""
        with pytest.raises(ValidationError):
            AccountType.from_string("invalid")
    
    def test_display_name(self):
        """測試顯示名稱"""
        assert AccountType.USER.display_name == "使用者帳戶"
        assert AccountType.GOVERNMENT_COUNCIL.display_name == "政府理事會"
        assert AccountType.GOVERNMENT_DEPARTMENT.display_name == "政府部門"
    
    def test_is_government(self):
        """測試是否為政府帳戶"""
        assert not AccountType.USER.is_government
        assert AccountType.GOVERNMENT_COUNCIL.is_government
        assert AccountType.GOVERNMENT_DEPARTMENT.is_government


class TestTransactionType:
    """測試 TransactionType 枚舉"""
    
    def test_enum_values(self):
        """測試枚舉值"""
        assert TransactionType.TRANSFER.value == "transfer"
        assert TransactionType.DEPOSIT.value == "deposit"
        assert TransactionType.WITHDRAW.value == "withdraw"
    
    def test_from_string_valid(self):
        """測試從有效字串建立枚舉"""
        assert TransactionType.from_string("transfer") == TransactionType.TRANSFER
        assert TransactionType.from_string("DEPOSIT") == TransactionType.DEPOSIT
    
    def test_display_name(self):
        """測試顯示名稱"""
        assert TransactionType.TRANSFER.display_name == "轉帳"
        assert TransactionType.DEPOSIT.display_name == "存款"


class TestAccount:
    """測試 Account 資料類別"""
    
    def test_valid_user_account(self):
        """測試有效的使用者帳戶"""
        account = Account(
            id="user_123_456",
            account_type=AccountType.USER,
            guild_id=456,
            user_id=123,
            balance=100.0,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        assert account.id == "user_123_456"
        assert account.balance == 100.0
    
    def test_valid_government_account(self):
        """測試有效的政府帳戶"""
        account = Account(
            id="gov_council_456",
            account_type=AccountType.GOVERNMENT_COUNCIL,
            guild_id=456,
            user_id=None,
            balance=1000.0,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        assert account.account_type == AccountType.GOVERNMENT_COUNCIL
        assert account.user_id is None
    
    def test_invalid_negative_balance(self):
        """測試無效的負餘額"""
        with pytest.raises(ValidationError):
            Account(
                id="user_123_456",
                account_type=AccountType.USER,
                guild_id=456,
                user_id=123,
                balance=-10.0,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
    
    def test_user_account_without_user_id(self):
        """測試使用者帳戶沒有 user_id"""
        with pytest.raises(ValidationError):
            Account(
                id="user_123_456",
                account_type=AccountType.USER,
                guild_id=456,
                user_id=None,
                balance=100.0,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
    
    def test_government_account_with_user_id(self):
        """測試政府帳戶有 user_id"""
        with pytest.raises(ValidationError):
            Account(
                id="gov_council_456",
                account_type=AccountType.GOVERNMENT_COUNCIL,
                guild_id=456,
                user_id=123,
                balance=100.0,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
    
    def test_from_db_row(self):
        """測試從資料庫記錄建立物件"""
        row = {
            'id': 'user_123_456',
            'account_type': 'user',
            'guild_id': 456,
            'user_id': 123,
            'balance': 100.0,
            'created_at': '2025-08-17T10:00:00',
            'updated_at': '2025-08-17T10:00:00',
            'is_active': 1,
            'metadata': '{"test": "value"}'
        }
        account = Account.from_db_row(row)
        assert account.id == 'user_123_456'
        assert account.account_type == AccountType.USER
        assert account.metadata['test'] == 'value'
    
    def test_to_db_dict(self):
        """測試轉換為資料庫字典"""
        now = datetime.now()
        account = Account(
            id="user_123_456",
            account_type=AccountType.USER,
            guild_id=456,
            user_id=123,
            balance=100.0,
            created_at=now,
            updated_at=now,
            metadata={"test": "value"}
        )
        db_dict = account.to_db_dict()
        assert db_dict['id'] == 'user_123_456'
        assert db_dict['account_type'] == 'user'
        assert db_dict['is_active'] == 1
        assert json.loads(db_dict['metadata'])['test'] == 'value'


class TestTransaction:
    """測試 Transaction 資料類別"""
    
    def test_valid_transfer_transaction(self):
        """測試有效的轉帳交易"""
        transaction = Transaction(
            id=1,
            from_account="user_123_456",
            to_account="user_789_456",
            amount=50.0,
            transaction_type=TransactionType.TRANSFER,
            reason="測試轉帳",
            guild_id=456,
            created_by=123,
            created_at=datetime.now()
        )
        assert transaction.amount == 50.0
        assert transaction.transaction_type == TransactionType.TRANSFER
    
    def test_valid_deposit_transaction(self):
        """測試有效的存款交易"""
        transaction = Transaction(
            id=2,
            from_account=None,
            to_account="user_123_456",
            amount=100.0,
            transaction_type=TransactionType.DEPOSIT,
            reason="系統獎勵",
            guild_id=456,
            created_by=None,
            created_at=datetime.now()
        )
        assert transaction.from_account is None
        assert transaction.to_account == "user_123_456"
    
    def test_invalid_zero_amount(self):
        """測試無效的零金額"""
        with pytest.raises(ValidationError):
            Transaction(
                id=1,
                from_account="user_123_456",
                to_account="user_789_456",
                amount=0.0,
                transaction_type=TransactionType.TRANSFER,
                reason="測試",
                guild_id=456,
                created_by=123,
                created_at=datetime.now()
            )
    
    def test_invalid_transfer_missing_accounts(self):
        """測試轉帳交易缺少帳戶"""
        with pytest.raises(ValidationError):
            Transaction(
                id=1,
                from_account=None,
                to_account="user_789_456",
                amount=50.0,
                transaction_type=TransactionType.TRANSFER,
                reason="測試",
                guild_id=456,
                created_by=123,
                created_at=datetime.now()
            )


class TestValidationFunctions:
    """測試驗證函數"""
    
    def test_validate_account_id_valid(self):
        """測試有效的帳戶ID"""
        assert validate_account_id("user_123_456")
        assert validate_account_id("gov_council_456")
        assert validate_account_id("gov_department_789")
    
    def test_validate_account_id_invalid(self):
        """測試無效的帳戶ID"""
        assert not validate_account_id("invalid")
        assert not validate_account_id("user_123")
        assert not validate_account_id("gov_invalid_456")
    
    def test_generate_account_id_user(self):
        """測試生成使用者帳戶ID"""
        account_id = generate_account_id(AccountType.USER, 456, 123)
        assert account_id == "user_123_456"
    
    def test_generate_account_id_government(self):
        """測試生成政府帳戶ID"""
        council_id = generate_account_id(AccountType.GOVERNMENT_COUNCIL, 456)
        assert council_id == "gov_council_456"
        
        dept_id = generate_account_id(AccountType.GOVERNMENT_DEPARTMENT, 456)
        assert dept_id == "gov_department_456"
    
    def test_generate_account_id_user_without_user_id(self):
        """測試生成使用者帳戶ID時沒有 user_id"""
        with pytest.raises(ValidationError):
            generate_account_id(AccountType.USER, 456)
    
    def test_validate_amount_valid(self):
        """測試有效金額驗證"""
        assert validate_amount(100.0) == 100.0
        assert validate_amount("50.5") == 50.5
        assert validate_amount(1, min_amount=1) == 1.0
    
    def test_validate_amount_invalid(self):
        """測試無效金額驗證"""
        with pytest.raises(ValidationError):
            validate_amount(-10.0)
        
        with pytest.raises(ValidationError):
            validate_amount("invalid")
        
        with pytest.raises(ValidationError):
            validate_amount(100, max_amount=50)
    
    def test_validate_guild_id_valid(self):
        """測試有效伺服器ID驗證"""
        assert validate_guild_id(123456) == 123456
        assert validate_guild_id("789012") == 789012
    
    def test_validate_guild_id_invalid(self):
        """測試無效伺服器ID驗證"""
        with pytest.raises(ValidationError):
            validate_guild_id(-123)
        
        with pytest.raises(ValidationError):
            validate_guild_id("invalid")
    
    def test_format_currency(self):
        """測試貨幣格式化"""
        config = CurrencyConfig(guild_id=123, currency_symbol="💰", decimal_places=2)
        assert format_currency(100.0, config) == "💰100.00"
        assert format_currency(99.5, config) == "💰99.50"
    
    def test_parse_currency_input(self):
        """測試解析貨幣輸入"""
        assert parse_currency_input("100") == 100.0
        assert parse_currency_input("💰100.50") == 100.5
        assert parse_currency_input("$1,000.25") == 1000.25
        assert parse_currency_input("  99.99  ") == 99.99
    
    def test_parse_currency_input_invalid(self):
        """測試解析無效貨幣輸入"""
        with pytest.raises(ValidationError):
            parse_currency_input("invalid")
        
        with pytest.raises(ValidationError):
            parse_currency_input("10.5.5")