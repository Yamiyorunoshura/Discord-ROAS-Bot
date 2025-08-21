"""
經濟系統資料模型
Task ID: 2 - 實作經濟系統核心功能

這個模組定義了經濟系統的資料模型，包括：
- AccountType 枚舉：定義帳戶類型
- 資料驗證函數：驗證輸入資料的有效性
- 資料庫模型映射：處理資料庫記錄的轉換
"""

import re
import json
from enum import Enum
from typing import Optional, Dict, Any, Union
from datetime import datetime
from dataclasses import dataclass

from core.exceptions import ValidationError


class AccountType(Enum):
    """
    帳戶類型枚舉
    
    定義經濟系統支援的三種帳戶類型：
    - USER: 一般使用者帳戶
    - GOVERNMENT_COUNCIL: 政府理事會帳戶
    - GOVERNMENT_DEPARTMENT: 政府部門帳戶
    """
    USER = "user"
    GOVERNMENT_COUNCIL = "government_council"
    GOVERNMENT_DEPARTMENT = "government_department"
    
    def __str__(self) -> str:
        return self.value
    
    @classmethod
    def from_string(cls, value: str) -> 'AccountType':
        """
        從字串建立 AccountType
        
        參數：
            value: 帳戶類型字串
            
        返回：
            AccountType 枚舉值
            
        異常：
            ValidationError: 當帳戶類型無效時
        """
        try:
            return cls(value.lower())
        except ValueError:
            raise ValidationError(
                f"無效的帳戶類型：{value}",
                field="account_type",
                value=value,
                expected="user, government_council, government_department"
            )
    
    @property
    def display_name(self) -> str:
        """獲取帳戶類型的顯示名稱"""
        display_names = {
            AccountType.USER: "使用者帳戶",
            AccountType.GOVERNMENT_COUNCIL: "政府理事會",
            AccountType.GOVERNMENT_DEPARTMENT: "政府部門"
        }
        return display_names[self]
    
    @property
    def is_government(self) -> bool:
        """檢查是否為政府帳戶"""
        return self in [AccountType.GOVERNMENT_COUNCIL, AccountType.GOVERNMENT_DEPARTMENT]


class TransactionType(Enum):
    """
    交易類型枚舉
    
    定義經濟系統支援的交易類型：
    - TRANSFER: 帳戶間轉帳
    - DEPOSIT: 系統存款（增加餘額）
    - WITHDRAW: 系統提款（減少餘額）
    - REWARD: 獎勵發放
    - PENALTY: 罰金扣除
    """
    TRANSFER = "transfer"
    DEPOSIT = "deposit"
    WITHDRAW = "withdraw"
    REWARD = "reward"
    PENALTY = "penalty"
    
    def __str__(self) -> str:
        return self.value
    
    @classmethod
    def from_string(cls, value: str) -> 'TransactionType':
        """從字串建立 TransactionType"""
        try:
            return cls(value.lower())
        except ValueError:
            raise ValidationError(
                f"無效的交易類型：{value}",
                field="transaction_type",
                value=value,
                expected="transfer, deposit, withdraw, reward, penalty"
            )
    
    @property
    def display_name(self) -> str:
        """獲取交易類型的顯示名稱"""
        display_names = {
            TransactionType.TRANSFER: "轉帳",
            TransactionType.DEPOSIT: "存款",
            TransactionType.WITHDRAW: "提款",
            TransactionType.REWARD: "獎勵",
            TransactionType.PENALTY: "罰金"
        }
        return display_names[self]


@dataclass
class Account:
    """
    帳戶資料類別
    
    表示經濟系統中的一個帳戶
    """
    id: str
    account_type: AccountType
    guild_id: int
    user_id: Optional[int]
    balance: float
    created_at: datetime
    updated_at: datetime
    is_active: bool = True
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """初始化後驗證"""
        self.validate()
    
    def validate(self):
        """驗證帳戶資料的有效性"""
        # 驗證帳戶ID格式
        if not validate_account_id(self.id):
            raise ValidationError(
                f"無效的帳戶ID格式：{self.id}",
                field="id",
                value=self.id,
                expected="user_{user_id}_{guild_id} 或 gov_{type}_{guild_id}"
            )
        
        # 驗證餘額
        if self.balance < 0:
            raise ValidationError(
                f"帳戶餘額不能為負數：{self.balance}",
                field="balance",
                value=self.balance,
                expected="非負數"
            )
        
        # 驗證使用者ID與帳戶類型的對應關係
        if self.account_type == AccountType.USER and self.user_id is None:
            raise ValidationError(
                "使用者帳戶必須有 user_id",
                field="user_id",
                value=None,
                expected="有效的使用者ID"
            )
        
        if self.account_type.is_government and self.user_id is not None:
            raise ValidationError(
                "政府帳戶不應該有 user_id",
                field="user_id",
                value=self.user_id,
                expected="None"
            )
    
    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> 'Account':
        """從資料庫記錄建立 Account 物件"""
        return cls(
            id=row['id'],
            account_type=AccountType.from_string(row['account_type']),
            guild_id=row['guild_id'],
            user_id=row.get('user_id'),
            balance=float(row['balance']),
            created_at=datetime.fromisoformat(row['created_at']),
            updated_at=datetime.fromisoformat(row['updated_at']),
            is_active=bool(row['is_active']),
            metadata=json.loads(row['metadata']) if row.get('metadata') else None
        )
    
    def to_db_dict(self) -> Dict[str, Any]:
        """轉換為資料庫插入用的字典"""
        return {
            'id': self.id,
            'account_type': self.account_type.value,
            'guild_id': self.guild_id,
            'user_id': self.user_id,
            'balance': self.balance,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'is_active': int(self.is_active),
            'metadata': json.dumps(self.metadata) if self.metadata else None
        }
@dataclass
class Transaction:
    """
    交易資料類別
    
    表示經濟系統中的一筆交易
    """
    id: Optional[int]
    from_account: Optional[str]
    to_account: Optional[str]
    amount: float
    transaction_type: TransactionType
    reason: Optional[str]
    guild_id: int
    created_by: Optional[int]
    created_at: datetime
    status: str = "completed"
    reference_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """初始化後驗證"""
        self.validate()
    
    def validate(self):
        """驗證交易資料的有效性"""
        # 驗證交易金額
        if self.amount <= 0:
            raise ValidationError(
                f"交易金額必須大於零：{self.amount}",
                field="amount",
                value=self.amount,
                expected="大於零的數值"
            )
        
        # 驗證交易狀態
        valid_statuses = ["pending", "completed", "failed", "cancelled"]
        if self.status not in valid_statuses:
            raise ValidationError(
                f"無效的交易狀態：{self.status}",
                field="status",
                value=self.status,
                expected=", ".join(valid_statuses)
            )
        
        # 驗證帳戶ID與交易類型的對應關係
        if self.transaction_type == TransactionType.TRANSFER:
            if not self.from_account or not self.to_account:
                raise ValidationError(
                    "轉帳交易必須指定來源和目標帳戶",
                    field="accounts",
                    value=f"from: {self.from_account}, to: {self.to_account}",
                    expected="兩個帳戶ID都不為空"
                )
        elif self.transaction_type == TransactionType.DEPOSIT:
            if self.from_account is not None or not self.to_account:
                raise ValidationError(
                    "存款交易只能有目標帳戶",
                    field="accounts",
                    value=f"from: {self.from_account}, to: {self.to_account}",
                    expected="from_account為None，to_account不為空"
                )
        elif self.transaction_type == TransactionType.WITHDRAW:
            if not self.from_account or self.to_account is not None:
                raise ValidationError(
                    "提款交易只能有來源帳戶",
                    field="accounts",
                    value=f"from: {self.from_account}, to: {self.to_account}",
                    expected="from_account不為空，to_account為None"
                )
    
    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> 'Transaction':
        """從資料庫記錄建立 Transaction 物件"""
        return cls(
            id=row['id'],
            from_account=row.get('from_account'),
            to_account=row.get('to_account'),
            amount=float(row['amount']),
            transaction_type=TransactionType.from_string(row['transaction_type']),
            reason=row.get('reason'),
            guild_id=row['guild_id'],
            created_by=row.get('created_by'),
            created_at=datetime.fromisoformat(row['created_at']),
            status=row['status'],
            reference_id=row.get('reference_id'),
            metadata=json.loads(row['metadata']) if row.get('metadata') else None
        )
    
    def to_db_dict(self) -> Dict[str, Any]:
        """轉換為資料庫插入用的字典"""
        return {
            'from_account': self.from_account,
            'to_account': self.to_account,
            'amount': self.amount,
            'transaction_type': self.transaction_type.value,
            'reason': self.reason,
            'guild_id': self.guild_id,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat(),
            'status': self.status,
            'reference_id': self.reference_id,
            'metadata': json.dumps(self.metadata) if self.metadata else None
        }


@dataclass
class CurrencyConfig:
    """
    貨幣配置資料類別
    
    表示伺服器的貨幣設定
    """
    guild_id: int
    currency_name: str = "金幣"
    currency_symbol: str = "💰"
    decimal_places: int = 2
    min_transfer_amount: float = 1.0
    max_transfer_amount: Optional[float] = None
    daily_transfer_limit: Optional[float] = None
    enable_negative_balance: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        """初始化後驗證"""
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()
        self.validate()
    
    def validate(self):
        """驗證貨幣配置的有效性"""
        # 驗證小數位數
        if not (0 <= self.decimal_places <= 8):
            raise ValidationError(
                f"小數位數必須在0-8之間：{self.decimal_places}",
                field="decimal_places",
                value=self.decimal_places,
                expected="0-8的整數"
            )
        
        # 驗證最小轉帳金額
        if self.min_transfer_amount < 0:
            raise ValidationError(
                f"最小轉帳金額不能為負數：{self.min_transfer_amount}",
                field="min_transfer_amount",
                value=self.min_transfer_amount,
                expected="非負數"
            )
        
        # 驗證最大轉帳金額
        if (self.max_transfer_amount is not None and 
            self.max_transfer_amount < self.min_transfer_amount):
            raise ValidationError(
                f"最大轉帳金額不能小於最小轉帳金額",
                field="max_transfer_amount",
                value=self.max_transfer_amount,
                expected=f"大於等於 {self.min_transfer_amount}"
            )
        
        # 驗證每日轉帳限額
        if self.daily_transfer_limit is not None and self.daily_transfer_limit < 0:
            raise ValidationError(
                f"每日轉帳限額不能為負數：{self.daily_transfer_limit}",
                field="daily_transfer_limit",
                value=self.daily_transfer_limit,
                expected="非負數或None"
            )
    
    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> 'CurrencyConfig':
        """從資料庫記錄建立 CurrencyConfig 物件"""
        return cls(
            guild_id=row['guild_id'],
            currency_name=row['currency_name'],
            currency_symbol=row['currency_symbol'],
            decimal_places=row['decimal_places'],
            min_transfer_amount=float(row['min_transfer_amount']),
            max_transfer_amount=float(row['max_transfer_amount']) if row.get('max_transfer_amount') else None,
            daily_transfer_limit=float(row['daily_transfer_limit']) if row.get('daily_transfer_limit') else None,
            enable_negative_balance=bool(row['enable_negative_balance']),
            created_at=datetime.fromisoformat(row['created_at']),
            updated_at=datetime.fromisoformat(row['updated_at'])
        )
    
    def to_db_dict(self) -> Dict[str, Any]:
        """轉換為資料庫插入用的字典"""
        return {
            'guild_id': self.guild_id,
            'currency_name': self.currency_name,
            'currency_symbol': self.currency_symbol,
            'decimal_places': self.decimal_places,
            'min_transfer_amount': self.min_transfer_amount,
            'max_transfer_amount': self.max_transfer_amount,
            'daily_transfer_limit': self.daily_transfer_limit,
            'enable_negative_balance': int(self.enable_negative_balance),
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


# =============================================================================
# 資料驗證函數
# =============================================================================

def validate_account_id(account_id: str) -> bool:
    """
    驗證帳戶ID格式
    
    有效格式：
    - 使用者帳戶：user_{user_id}_{guild_id}
    - 政府理事會：gov_council_{guild_id}
    - 政府部門：gov_department_{guild_id}
    
    參數：
        account_id: 要驗證的帳戶ID
        
    返回：
        是否為有效格式
    """
    if not isinstance(account_id, str):
        return False
    
    # 使用者帳戶格式
    user_pattern = r'^user_\d+_\d+$'
    if re.match(user_pattern, account_id):
        return True
    
    # 政府帳戶格式
    gov_pattern = r'^gov_(council|department)_\d+$'
    if re.match(gov_pattern, account_id):
        return True
    
    return False


def generate_account_id(account_type: AccountType, guild_id: int, user_id: Optional[int] = None) -> str:
    """
    生成帳戶ID
    
    參數：
        account_type: 帳戶類型
        guild_id: 伺服器ID
        user_id: 使用者ID（僅用於使用者帳戶）
        
    返回：
        生成的帳戶ID
        
    異常：
        ValidationError: 當參數無效時
    """
    if account_type == AccountType.USER:
        if user_id is None:
            raise ValidationError(
                "使用者帳戶必須提供 user_id",
                field="user_id",
                value=None,
                expected="有效的使用者ID"
            )
        return f"user_{user_id}_{guild_id}"
    
    elif account_type == AccountType.GOVERNMENT_COUNCIL:
        return f"gov_council_{guild_id}"
    
    elif account_type == AccountType.GOVERNMENT_DEPARTMENT:
        return f"gov_department_{guild_id}"
    
    else:
        raise ValidationError(
            f"不支援的帳戶類型：{account_type}",
            field="account_type",
            value=account_type,
            expected="USER, GOVERNMENT_COUNCIL, GOVERNMENT_DEPARTMENT"
        )


def validate_amount(amount: Union[int, float], min_amount: float = 0.01, max_amount: Optional[float] = None) -> float:
    """
    驗證金額
    
    參數：
        amount: 要驗證的金額
        min_amount: 最小金額
        max_amount: 最大金額（可選）
        
    返回：
        驗證後的金額（float）
        
    異常：
        ValidationError: 當金額無效時
    """
    try:
        amount = float(amount)
    except (ValueError, TypeError):
        raise ValidationError(
            f"無效的金額格式：{amount}",
            field="amount",
            value=amount,
            expected="數值"
        )
    
    if amount < min_amount:
        raise ValidationError(
            f"金額不能小於 {min_amount}：{amount}",
            field="amount",
            value=amount,
            expected=f"大於等於 {min_amount}"
        )
    
    if max_amount is not None and amount > max_amount:
        raise ValidationError(
            f"金額不能大於 {max_amount}：{amount}",
            field="amount",
            value=amount,
            expected=f"小於等於 {max_amount}"
        )
    
    return amount


def validate_guild_id(guild_id: Union[int, str]) -> int:
    """
    驗證Discord伺服器ID
    
    參數：
        guild_id: 要驗證的伺服器ID
        
    返回：
        驗證後的伺服器ID（int）
        
    異常：
        ValidationError: 當伺服器ID無效時
    """
    try:
        guild_id = int(guild_id)
    except (ValueError, TypeError):
        raise ValidationError(
            f"無效的伺服器ID格式：{guild_id}",
            field="guild_id",
            value=guild_id,
            expected="整數"
        )
    
    if guild_id <= 0:
        raise ValidationError(
            f"伺服器ID必須為正整數：{guild_id}",
            field="guild_id",
            value=guild_id,
            expected="正整數"
        )
    
    return guild_id


def validate_user_id(user_id: Union[int, str]) -> int:
    """
    驗證Discord使用者ID
    
    參數：
        user_id: 要驗證的使用者ID
        
    返回：
        驗證後的使用者ID（int）
        
    異常：
        ValidationError: 當使用者ID無效時
    """
    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        raise ValidationError(
            f"無效的使用者ID格式：{user_id}",
            field="user_id",
            value=user_id,
            expected="整數"
        )
    
    if user_id <= 0:
        raise ValidationError(
            f"使用者ID必須為正整數：{user_id}",
            field="user_id",
            value=user_id,
            expected="正整數"
        )
    
    return user_id


def format_currency(amount: float, config: CurrencyConfig) -> str:
    """
    格式化貨幣顯示
    
    參數：
        amount: 金額
        config: 貨幣配置
        
    返回：
        格式化後的貨幣字串
    """
    formatted_amount = f"{amount:.{config.decimal_places}f}"
    return f"{config.currency_symbol}{formatted_amount}"


def parse_currency_input(input_str: str) -> float:
    """
    解析使用者輸入的貨幣字串
    
    支援的格式：
    - 純數字：100, 100.50
    - 帶符號：💰100, $100.50
    - 帶千分位：1,000, 1,000.50
    
    參數：
        input_str: 輸入字串
        
    返回：
        解析後的金額
        
    異常：
        ValidationError: 當輸入格式無效時
    """
    if not isinstance(input_str, str):
        input_str = str(input_str)
    
    # 移除常見的貨幣符號和空格
    cleaned = input_str.strip()
    # 移除貨幣符號（emoji和常見符號）
    cleaned = re.sub(r'^[💰$€£¥]+', '', cleaned)
    # 移除千分位逗號
    cleaned = cleaned.replace(',', '')
    
    try:
        return float(cleaned)
    except ValueError:
        raise ValidationError(
            f"無法解析貨幣輸入：{input_str}",
            field="currency_input",
            value=input_str,
            expected="有效的數值格式"
        )