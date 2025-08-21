"""
經濟系統服務
Task ID: 2 - 實作經濟系統核心功能

這個模組提供Discord機器人經濟系統的核心業務邏輯，包括：
- 帳戶管理：建立、查詢、更新帳戶
- 交易處理：轉帳、存款、提款
- 貨幣配置：伺服器級別的貨幣設定管理
- 權限驗證：操作權限檢查
- 審計記錄：所有操作的完整記錄
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Union
from decimal import Decimal

from core.base_service import BaseService
from core.database_manager import DatabaseManager
from core.exceptions import ServiceError, ValidationError, DatabaseError, handle_errors
from .models import (
    AccountType, TransactionType, Account, Transaction, CurrencyConfig,
    generate_account_id, validate_amount, validate_guild_id, validate_user_id,
    validate_account_id, format_currency
)


class EconomyService(BaseService):
    """
    經濟系統服務
    
    提供完整的經濟系統功能，包括帳戶管理、交易處理、貨幣配置等
    """
    
    def __init__(self):
        super().__init__("EconomyService")
        self.db_manager: Optional[DatabaseManager] = None
        self._audit_enabled = True
        self._transaction_lock = asyncio.Lock()
    
    async def _initialize(self) -> bool:
        """初始化經濟服務"""
        try:
            # 獲取資料庫管理器依賴
            self.db_manager = self.get_dependency("database_manager")
            if not self.db_manager or not self.db_manager.is_initialized:
                self.logger.error("資料庫管理器依賴不可用")
                return False
            
            # 註冊經濟系統資料庫遷移
            await self._register_migrations()
            
            # 應用遷移
            migration_result = await self.db_manager.migration_manager.apply_migrations()
            if not migration_result:
                self.logger.error("經濟系統遷移應用失敗")
                return False
            
            self.logger.info("經濟系統服務初始化完成")
            return True
            
        except Exception as e:
            self.logger.exception(f"經濟系統服務初始化失敗：{e}")
            return False
    
    async def _cleanup(self) -> None:
        """清理經濟服務資源"""
        self.db_manager = None
        self.logger.info("經濟系統服務已清理")
    
    async def _validate_permissions(
        self,
        user_id: int,
        guild_id: Optional[int],
        action: str
    ) -> bool:
        """
        驗證使用者權限
        
        參數：
            user_id: 使用者ID
            guild_id: 伺服器ID
            action: 要執行的動作
            
        返回：
            是否有權限
        """
        # 基本權限驗證邏輯
        # TODO: 後續可以整合更複雜的權限系統
        
        # 管理員操作需要特殊權限
        admin_actions = [
            "admin_transfer", "admin_deposit", "admin_withdraw",
            "config_change", "account_admin"
        ]
        
        if action in admin_actions:
            # TODO: 檢查使用者是否為管理員
            # 目前暫時允許所有操作
            pass
        
        # 一般操作允許所有使用者
        return True
    
    async def _register_migrations(self):
        """註冊經濟系統的資料庫遷移"""
        try:
            # 讀取遷移腳本
            import os
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            migration_file = os.path.join(project_root, "scripts", "migrations", "001_create_economy_tables.sql")
            
            if os.path.exists(migration_file):
                with open(migration_file, 'r', encoding='utf-8') as f:
                    migration_sql = f.read()
                
                # 將長腳本分割為可執行的部分
                # 移除註解和空行，然後按分號分割
                sql_lines = []
                for line in migration_sql.split('\n'):
                    line = line.strip()
                    if line and not line.startswith('--'):
                        sql_lines.append(line)
                
                # 重新組合，保持語句換行以利分割
                cleaned_sql = '\n'.join(sql_lines)
                
                self.db_manager.migration_manager.add_migration(
                    version="002_economy_system",
                    description="建立經濟系統核心表格和索引",
                    up_sql=cleaned_sql,
                    down_sql="DROP TABLE IF EXISTS economy_audit_log; DROP TABLE IF EXISTS economy_transactions; DROP TABLE IF EXISTS economy_accounts; DROP TABLE IF EXISTS currency_settings;"
                )
                
                self.logger.info("經濟系統遷移已註冊")
            else:
                self.logger.warning(f"遷移檔案不存在：{migration_file}")
                
        except Exception as e:
            self.logger.error(f"註冊遷移失敗：{e}")
    
    # ==========================================================================
    # 帳戶管理功能
    # ==========================================================================
    
    @handle_errors(log_errors=True)
    async def create_account(
        self,
        guild_id: int,
        account_type: AccountType,
        user_id: Optional[int] = None,
        initial_balance: float = 0.0
    ) -> Account:
        """
        建立新帳戶
        
        參數：
            guild_id: Discord伺服器ID
            account_type: 帳戶類型
            user_id: 使用者ID（僅用於使用者帳戶）
            initial_balance: 初始餘額
            
        返回：
            建立的帳戶物件
            
        異常：
            ValidationError: 當參數無效時
            ServiceError: 當帳戶已存在或建立失敗時
        """
        try:
            # 驗證參數
            guild_id = validate_guild_id(guild_id)
            if user_id is not None:
                user_id = validate_user_id(user_id)
            initial_balance = validate_amount(initial_balance, min_amount=0.0)
            
            # 生成帳戶ID
            account_id = generate_account_id(account_type, guild_id, user_id)
            
            # 檢查帳戶是否已存在
            existing_account = await self.get_account(account_id)
            if existing_account is not None:
                raise ServiceError(
                    f"帳戶已存在：{account_id}",
                    service_name=self.name,
                    operation="create_account"
                )
            
            # 建立帳戶物件
            now = datetime.now()
            account = Account(
                id=account_id,
                account_type=account_type,
                guild_id=guild_id,
                user_id=user_id,
                balance=initial_balance,
                created_at=now,
                updated_at=now
            )
            
            # 插入資料庫
            await self.db_manager.execute(
                """INSERT INTO economy_accounts 
                   (id, account_type, guild_id, user_id, balance, created_at, updated_at, is_active, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    account.id,
                    account.account_type.value,
                    account.guild_id,
                    account.user_id,
                    account.balance,
                    account.created_at.isoformat(),
                    account.updated_at.isoformat(),
                    1,  # is_active
                    None  # metadata
                )
            )
            
            # 記錄審計日誌
            await self._audit_log(
                operation="create_account",
                target_type="account",
                target_id=account_id,
                guild_id=guild_id,
                user_id=user_id,
                new_values={
                    "account_type": account_type.value,
                    "initial_balance": initial_balance
                }
            )
            
            self.logger.info(f"帳戶建立成功：{account_id}")
            return account
            
        except (ValidationError, ServiceError):
            raise
        except Exception as e:
            raise ServiceError(
                f"建立帳戶失敗：{str(e)}",
                service_name=self.name,
                operation="create_account"
            )
    
    @handle_errors(log_errors=True)
    async def get_account(self, account_id: str) -> Optional[Account]:
        """
        獲取帳戶資訊
        
        參數：
            account_id: 帳戶ID
            
        返回：
            帳戶物件，如果不存在則返回 None
        """
        try:
            if not validate_account_id(account_id):
                raise ValidationError(
                    f"無效的帳戶ID格式：{account_id}",
                    field="account_id",
                    value=account_id,
                    expected="有效的帳戶ID格式"
                )
            
            row = await self.db_manager.fetchone(
                "SELECT * FROM economy_accounts WHERE id = ? AND is_active = 1",
                (account_id,)
            )
            
            if row:
                return Account.from_db_row(dict(row))
            return None
            
        except ValidationError:
            raise
        except Exception as e:
            raise ServiceError(
                f"獲取帳戶失敗：{str(e)}",
                service_name=self.name,
                operation="get_account"
            )
    
    @handle_errors(log_errors=True)
    async def get_balance(self, account_id: str) -> float:
        """
        獲取帳戶餘額
        
        參數：
            account_id: 帳戶ID
            
        返回：
            帳戶餘額
            
        異常：
            ServiceError: 當帳戶不存在時
        """
        try:
            if not validate_account_id(account_id):
                raise ValidationError(
                    f"無效的帳戶ID格式：{account_id}",
                    field="account_id",
                    value=account_id,
                    expected="有效的帳戶ID格式"
                )
            
            row = await self.db_manager.fetchone(
                "SELECT balance FROM economy_accounts WHERE id = ? AND is_active = 1",
                (account_id,)
            )
            
            if row:
                return float(row['balance'])
            else:
                raise ServiceError(
                    f"帳戶不存在：{account_id}",
                    service_name=self.name,
                    operation="get_balance"
                )
                
        except (ValidationError, ServiceError):
            raise
        except Exception as e:
            raise ServiceError(
                f"獲取餘額失敗：{str(e)}",
                service_name=self.name,
                operation="get_balance"
            )    
    # ==========================================================================
    # 交易管理功能
    # ==========================================================================
    
    @handle_errors(log_errors=True)
    async def transfer(
        self,
        from_account_id: str,
        to_account_id: str,
        amount: float,
        reason: Optional[str] = None,
        created_by: Optional[int] = None
    ) -> Transaction:
        """
        執行帳戶間轉帳
        
        參數：
            from_account_id: 來源帳戶ID
            to_account_id: 目標帳戶ID
            amount: 轉帳金額
            reason: 轉帳原因
            created_by: 執行轉帳的使用者ID
            
        返回：
            交易記錄
            
        異常：
            ValidationError: 當參數無效時
            ServiceError: 當轉帳失敗時
        """
        async with self._transaction_lock:
            try:
                # 驗證參數
                if not validate_account_id(from_account_id):
                    raise ValidationError(
                        f"無效的來源帳戶ID：{from_account_id}",
                        field="from_account_id",
                        value=from_account_id,
                        expected="有效的帳戶ID格式"
                    )
                
                if not validate_account_id(to_account_id):
                    raise ValidationError(
                        f"無效的目標帳戶ID：{to_account_id}",
                        field="to_account_id",
                        value=to_account_id,
                        expected="有效的帳戶ID格式"
                    )
                
                if from_account_id == to_account_id:
                    raise ValidationError(
                        "不能向自己轉帳",
                        field="account_ids",
                        value=f"{from_account_id} -> {to_account_id}",
                        expected="不同的帳戶ID"
                    )
                
                amount = validate_amount(amount, min_amount=0.01)
                
                if created_by is not None:
                    created_by = validate_user_id(created_by)
                
                # 獲取帳戶資訊並檢查餘額
                from_account = await self.get_account(from_account_id)
                to_account = await self.get_account(to_account_id)
                
                if not from_account:
                    raise ServiceError(
                        f"來源帳戶不存在：{from_account_id}",
                        service_name=self.name,
                        operation="transfer"
                    )
                
                if not to_account:
                    raise ServiceError(
                        f"目標帳戶不存在：{to_account_id}",
                        service_name=self.name,
                        operation="transfer"
                    )
                
                # 檢查餘額
                if from_account.balance < amount:
                    raise ServiceError(
                        f"餘額不足：當前餘額 {from_account.balance}，需要 {amount}",
                        service_name=self.name,
                        operation="transfer"
                    )
                
                # 獲取伺服器ID（用於交易記錄）
                guild_id = from_account.guild_id
                
                # 使用資料庫事務執行轉帳
                async with self.db_manager.transaction() as conn:
                    # 扣除來源帳戶餘額
                    await self.db_manager.execute(
                        "UPDATE economy_accounts SET balance = balance - ?, updated_at = ? WHERE id = ?",
                        (amount, datetime.now().isoformat(), from_account_id)
                    )
                    
                    # 增加目標帳戶餘額
                    await self.db_manager.execute(
                        "UPDATE economy_accounts SET balance = balance + ?, updated_at = ? WHERE id = ?",
                        (amount, datetime.now().isoformat(), to_account_id)
                    )
                    
                    # 記錄交易
                    transaction = Transaction(
                        id=None,
                        from_account=from_account_id,
                        to_account=to_account_id,
                        amount=amount,
                        transaction_type=TransactionType.TRANSFER,
                        reason=reason,
                        guild_id=guild_id,
                        created_by=created_by,
                        created_at=datetime.now()
                    )
                    
                    await self.db_manager.execute(
                        """INSERT INTO economy_transactions 
                           (from_account, to_account, amount, transaction_type, reason, guild_id, created_by, created_at, status, reference_id, metadata)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            transaction.from_account,
                            transaction.to_account,
                            transaction.amount,
                            transaction.transaction_type.value,
                            transaction.reason,
                            transaction.guild_id,
                            transaction.created_by,
                            transaction.created_at.isoformat(),
                            transaction.status,
                            transaction.reference_id,
                            json.dumps(transaction.metadata) if transaction.metadata else None
                        )
                    )
                
                # 記錄審計日誌
                await self._audit_log(
                    operation="transfer",
                    target_type="transaction",
                    target_id=f"{from_account_id}->{to_account_id}",
                    guild_id=guild_id,
                    user_id=created_by,
                    new_values={
                        "from_account": from_account_id,
                        "to_account": to_account_id,
                        "amount": amount,
                        "reason": reason
                    }
                )
                
                self.logger.info(f"轉帳成功：{from_account_id} -> {to_account_id}, 金額：{amount}")
                return transaction
                
            except (ValidationError, ServiceError):
                raise
            except Exception as e:
                raise ServiceError(
                    f"轉帳失敗：{str(e)}",
                    service_name=self.name,
                    operation="transfer"
                )
    
    @handle_errors(log_errors=True)
    async def deposit(
        self,
        account_id: str,
        amount: float,
        reason: Optional[str] = None,
        created_by: Optional[int] = None
    ) -> Transaction:
        """
        向帳戶存款（系統增加餘額）
        
        參數：
            account_id: 目標帳戶ID
            amount: 存款金額
            reason: 存款原因
            created_by: 執行存款的使用者ID
            
        返回：
            交易記錄
        """
        try:
            # 驗證參數
            if not validate_account_id(account_id):
                raise ValidationError(
                    f"無效的帳戶ID：{account_id}",
                    field="account_id",
                    value=account_id,
                    expected="有效的帳戶ID格式"
                )
            
            amount = validate_amount(amount, min_amount=0.01)
            
            if created_by is not None:
                created_by = validate_user_id(created_by)
            
            # 確認帳戶存在
            account = await self.get_account(account_id)
            if not account:
                raise ServiceError(
                    f"帳戶不存在：{account_id}",
                    service_name=self.name,
                    operation="deposit"
                )
            
            # 使用資料庫事務執行存款
            async with self.db_manager.transaction() as conn:
                # 增加帳戶餘額
                await self.db_manager.execute(
                    "UPDATE economy_accounts SET balance = balance + ?, updated_at = ? WHERE id = ?",
                    (amount, datetime.now().isoformat(), account_id)
                )
                
                # 記錄交易
                transaction = Transaction(
                    id=None,
                    from_account=None,
                    to_account=account_id,
                    amount=amount,
                    transaction_type=TransactionType.DEPOSIT,
                    reason=reason,
                    guild_id=account.guild_id,
                    created_by=created_by,
                    created_at=datetime.now()
                )
                
                await self.db_manager.execute(
                    """INSERT INTO economy_transactions 
                       (from_account, to_account, amount, transaction_type, reason, guild_id, created_by, created_at, status, reference_id, metadata)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        transaction.from_account,
                        transaction.to_account,
                        transaction.amount,
                        transaction.transaction_type.value,
                        transaction.reason,
                        transaction.guild_id,
                        transaction.created_by,
                        transaction.created_at.isoformat(),
                        transaction.status,
                        transaction.reference_id,
                        json.dumps(transaction.metadata) if transaction.metadata else None
                    )
                )
            
            # 記錄審計日誌
            await self._audit_log(
                operation="deposit",
                target_type="transaction",
                target_id=account_id,
                guild_id=account.guild_id,
                user_id=created_by,
                new_values={
                    "account_id": account_id,
                    "amount": amount,
                    "reason": reason
                }
            )
            
            self.logger.info(f"存款成功：{account_id}, 金額：{amount}")
            return transaction
            
        except (ValidationError, ServiceError):
            raise
        except Exception as e:
            raise ServiceError(
                f"存款失敗：{str(e)}",
                service_name=self.name,
                operation="deposit"
            )
    
    @handle_errors(log_errors=True)
    async def withdraw(
        self,
        account_id: str,
        amount: float,
        reason: Optional[str] = None,
        created_by: Optional[int] = None
    ) -> Transaction:
        """
        從帳戶提款（系統減少餘額）
        
        參數：
            account_id: 來源帳戶ID
            amount: 提款金額
            reason: 提款原因
            created_by: 執行提款的使用者ID
            
        返回：
            交易記錄
        """
        async with self._transaction_lock:
            try:
                # 驗證參數
                if not validate_account_id(account_id):
                    raise ValidationError(
                        f"無效的帳戶ID：{account_id}",
                        field="account_id",
                        value=account_id,
                        expected="有效的帳戶ID格式"
                    )
                
                amount = validate_amount(amount, min_amount=0.01)
                
                if created_by is not None:
                    created_by = validate_user_id(created_by)
                
                # 獲取帳戶資訊並檢查餘額
                current_balance = await self.get_balance(account_id)
                
                if current_balance < amount:
                    raise ServiceError(
                        f"餘額不足：當前餘額 {current_balance}，需要 {amount}",
                        service_name=self.name,
                        operation="withdraw"
                    )
                
                account = await self.get_account(account_id)
                
                # 使用資料庫事務執行提款
                async with self.db_manager.transaction() as conn:
                    # 減少帳戶餘額
                    await self.db_manager.execute(
                        "UPDATE economy_accounts SET balance = balance - ?, updated_at = ? WHERE id = ?",
                        (amount, datetime.now().isoformat(), account_id)
                    )
                    
                    # 記錄交易
                    transaction = Transaction(
                        id=None,
                        from_account=account_id,
                        to_account=None,
                        amount=amount,
                        transaction_type=TransactionType.WITHDRAW,
                        reason=reason,
                        guild_id=account.guild_id,
                        created_by=created_by,
                        created_at=datetime.now()
                    )
                    
                    await self.db_manager.execute(
                        """INSERT INTO economy_transactions 
                           (from_account, to_account, amount, transaction_type, reason, guild_id, created_by, created_at, status, reference_id, metadata)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            transaction.from_account,
                            transaction.to_account,
                            transaction.amount,
                            transaction.transaction_type.value,
                            transaction.reason,
                            transaction.guild_id,
                            transaction.created_by,
                            transaction.created_at.isoformat(),
                            transaction.status,
                            transaction.reference_id,
                            json.dumps(transaction.metadata) if transaction.metadata else None
                        )
                    )
                
                # 記錄審計日誌
                await self._audit_log(
                    operation="withdraw",
                    target_type="transaction",
                    target_id=account_id,
                    guild_id=account.guild_id,
                    user_id=created_by,
                    new_values={
                        "account_id": account_id,
                        "amount": amount,
                        "reason": reason
                    }
                )
                
                self.logger.info(f"提款成功：{account_id}, 金額：{amount}")
                return transaction
                
            except (ValidationError, ServiceError):
                raise
            except Exception as e:
                raise ServiceError(
                    f"提款失敗：{str(e)}",
                    service_name=self.name,
                    operation="withdraw"
                )
    
    @handle_errors(log_errors=True)
    async def get_transaction_history(
        self,
        account_id: str,
        limit: int = 50,
        transaction_type: Optional[TransactionType] = None
    ) -> List[Transaction]:
        """
        獲取帳戶交易記錄
        
        參數：
            account_id: 帳戶ID
            limit: 記錄數量限制
            transaction_type: 交易類型篩選
            
        返回：
            交易記錄列表
        """
        try:
            if not validate_account_id(account_id):
                raise ValidationError(
                    f"無效的帳戶ID：{account_id}",
                    field="account_id",
                    value=account_id,
                    expected="有效的帳戶ID格式"
                )
            
            # 構建查詢
            query = """
                SELECT * FROM economy_transactions 
                WHERE (from_account = ? OR to_account = ?)
            """
            params = [account_id, account_id]
            
            if transaction_type:
                query += " AND transaction_type = ?"
                params.append(transaction_type.value)
            
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            
            rows = await self.db_manager.fetchall(query, params)
            
            transactions = []
            for row in rows:
                transaction = Transaction.from_db_row(dict(row))
                transactions.append(transaction)
            
            return transactions
            
        except ValidationError:
            raise
        except Exception as e:
            raise ServiceError(
                f"獲取交易記錄失敗：{str(e)}",
                service_name=self.name,
                operation="get_transaction_history"
            )    
    # ==========================================================================
    # 貨幣配置管理功能
    # ==========================================================================
    
    @handle_errors(log_errors=True)
    async def get_currency_config(self, guild_id: int) -> CurrencyConfig:
        """
        獲取伺服器的貨幣配置
        
        參數：
            guild_id: Discord伺服器ID
            
        返回：
            貨幣配置物件
        """
        try:
            guild_id = validate_guild_id(guild_id)
            
            row = await self.db_manager.fetchone(
                "SELECT * FROM currency_settings WHERE guild_id = ?",
                (guild_id,)
            )
            
            if row:
                return CurrencyConfig.from_db_row(dict(row))
            else:
                # 返回預設配置
                config = CurrencyConfig(guild_id=guild_id)
                
                # 儲存預設配置到資料庫
                await self.set_currency_config(
                    guild_id=guild_id,
                    currency_name=config.currency_name,
                    currency_symbol=config.currency_symbol
                )
                
                return config
                
        except ValidationError:
            raise
        except Exception as e:
            raise ServiceError(
                f"獲取貨幣配置失敗：{str(e)}",
                service_name=self.name,
                operation="get_currency_config"
            )
    
    @handle_errors(log_errors=True)
    async def set_currency_config(
        self,
        guild_id: int,
        currency_name: Optional[str] = None,
        currency_symbol: Optional[str] = None,
        decimal_places: Optional[int] = None,
        min_transfer_amount: Optional[float] = None,
        max_transfer_amount: Optional[float] = None,
        daily_transfer_limit: Optional[float] = None,
        enable_negative_balance: Optional[bool] = None,
        updated_by: Optional[int] = None
    ) -> CurrencyConfig:
        """
        設定伺服器的貨幣配置
        
        參數：
            guild_id: Discord伺服器ID
            currency_name: 貨幣名稱
            currency_symbol: 貨幣符號
            decimal_places: 小數位數
            min_transfer_amount: 最小轉帳金額
            max_transfer_amount: 最大轉帳金額
            daily_transfer_limit: 每日轉帳限額
            enable_negative_balance: 是否允許負餘額
            updated_by: 更新者使用者ID
            
        返回：
            更新後的貨幣配置
        """
        try:
            guild_id = validate_guild_id(guild_id)
            
            if updated_by is not None:
                updated_by = validate_user_id(updated_by)
            
            # 獲取現有配置
            existing_config = await self.db_manager.fetchone(
                "SELECT * FROM currency_settings WHERE guild_id = ?",
                (guild_id,)
            )
            
            if existing_config:
                # 更新現有配置
                config = CurrencyConfig.from_db_row(dict(existing_config))
                old_values = config.to_db_dict()
                
                # 更新指定的欄位
                if currency_name is not None:
                    config.currency_name = currency_name
                if currency_symbol is not None:
                    config.currency_symbol = currency_symbol
                if decimal_places is not None:
                    config.decimal_places = decimal_places
                if min_transfer_amount is not None:
                    config.min_transfer_amount = min_transfer_amount
                if max_transfer_amount is not None:
                    config.max_transfer_amount = max_transfer_amount
                if daily_transfer_limit is not None:
                    config.daily_transfer_limit = daily_transfer_limit
                if enable_negative_balance is not None:
                    config.enable_negative_balance = enable_negative_balance
                
                config.updated_at = datetime.now()
                
                # 重新驗證配置
                config.validate()
                
                # 更新資料庫
                await self.db_manager.execute(
                    """UPDATE currency_settings SET 
                       currency_name = ?, currency_symbol = ?, decimal_places = ?,
                       min_transfer_amount = ?, max_transfer_amount = ?, daily_transfer_limit = ?,
                       enable_negative_balance = ?, updated_at = ?
                       WHERE guild_id = ?""",
                    (
                        config.currency_name,
                        config.currency_symbol,
                        config.decimal_places,
                        config.min_transfer_amount,
                        config.max_transfer_amount,
                        config.daily_transfer_limit,
                        int(config.enable_negative_balance),
                        config.updated_at.isoformat(),
                        guild_id
                    )
                )
                
                # 記錄審計日誌
                await self._audit_log(
                    operation="update_currency_config",
                    target_type="config",
                    target_id=str(guild_id),
                    guild_id=guild_id,
                    user_id=updated_by,
                    old_values=old_values,
                    new_values=config.to_db_dict()
                )
                
            else:
                # 建立新配置
                config = CurrencyConfig(
                    guild_id=guild_id,
                    currency_name=currency_name or "金幣",
                    currency_symbol=currency_symbol or "💰",
                    decimal_places=decimal_places if decimal_places is not None else 2,
                    min_transfer_amount=min_transfer_amount if min_transfer_amount is not None else 1.0,
                    max_transfer_amount=max_transfer_amount,
                    daily_transfer_limit=daily_transfer_limit,
                    enable_negative_balance=enable_negative_balance if enable_negative_balance is not None else False
                )
                
                # 插入資料庫
                await self.db_manager.execute(
                    """INSERT INTO currency_settings 
                       (guild_id, currency_name, currency_symbol, decimal_places,
                        min_transfer_amount, max_transfer_amount, daily_transfer_limit,
                        enable_negative_balance, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        config.guild_id,
                        config.currency_name,
                        config.currency_symbol,
                        config.decimal_places,
                        config.min_transfer_amount,
                        config.max_transfer_amount,
                        config.daily_transfer_limit,
                        int(config.enable_negative_balance),
                        config.created_at.isoformat(),
                        config.updated_at.isoformat()
                    )
                )
                
                # 記錄審計日誌
                await self._audit_log(
                    operation="create_currency_config",
                    target_type="config",
                    target_id=str(guild_id),
                    guild_id=guild_id,
                    user_id=updated_by,
                    new_values=config.to_db_dict()
                )
            
            self.logger.info(f"貨幣配置已更新：伺服器 {guild_id}")
            return config
            
        except (ValidationError, ServiceError):
            raise
        except Exception as e:
            raise ServiceError(
                f"設定貨幣配置失敗：{str(e)}",
                service_name=self.name,
                operation="set_currency_config"
            )
    
    # ==========================================================================
    # 查詢和統計功能
    # ==========================================================================
    
    @handle_errors(log_errors=True)
    async def get_guild_accounts(
        self,
        guild_id: int,
        account_type: Optional[AccountType] = None,
        include_inactive: bool = False
    ) -> List[Account]:
        """
        獲取伺服器的所有帳戶
        
        參數：
            guild_id: Discord伺服器ID
            account_type: 帳戶類型篩選
            include_inactive: 是否包含停用的帳戶
            
        返回：
            帳戶列表
        """
        try:
            guild_id = validate_guild_id(guild_id)
            
            query = "SELECT * FROM economy_accounts WHERE guild_id = ?"
            params = [guild_id]
            
            if account_type:
                query += " AND account_type = ?"
                params.append(account_type.value)
            
            if not include_inactive:
                query += " AND is_active = 1"
            
            query += " ORDER BY created_at DESC"
            
            rows = await self.db_manager.fetchall(query, params)
            
            accounts = []
            for row in rows:
                account = Account.from_db_row(dict(row))
                accounts.append(account)
            
            return accounts
            
        except ValidationError:
            raise
        except Exception as e:
            raise ServiceError(
                f"獲取伺服器帳戶失敗：{str(e)}",
                service_name=self.name,
                operation="get_guild_accounts"
            )
    
    @handle_errors(log_errors=True)
    async def get_economy_statistics(self, guild_id: int) -> Dict[str, Any]:
        """
        獲取經濟系統統計資料
        
        參數：
            guild_id: Discord伺服器ID
            
        返回：
            統計資料字典
        """
        try:
            guild_id = validate_guild_id(guild_id)
            
            # 帳戶統計
            account_stats = await self.db_manager.fetchone(
                """SELECT 
                    COUNT(*) as total_accounts,
                    SUM(CASE WHEN account_type = 'user' THEN 1 ELSE 0 END) as user_accounts,
                    SUM(CASE WHEN account_type = 'government_council' THEN 1 ELSE 0 END) as council_accounts,
                    SUM(CASE WHEN account_type = 'government_department' THEN 1 ELSE 0 END) as department_accounts,
                    SUM(balance) as total_currency,
                    AVG(balance) as avg_balance,
                    MAX(balance) as max_balance
                   FROM economy_accounts 
                   WHERE guild_id = ? AND is_active = 1""",
                (guild_id,)
            )
            
            # 交易統計
            transaction_stats = await self.db_manager.fetchone(
                """SELECT 
                    COUNT(*) as total_transactions,
                    SUM(CASE WHEN transaction_type = 'transfer' THEN 1 ELSE 0 END) as transfers,
                    SUM(CASE WHEN transaction_type = 'deposit' THEN 1 ELSE 0 END) as deposits,
                    SUM(CASE WHEN transaction_type = 'withdraw' THEN 1 ELSE 0 END) as withdraws,
                    SUM(amount) as total_volume,
                    AVG(amount) as avg_amount
                   FROM economy_transactions 
                   WHERE guild_id = ? AND status = 'completed'""",
                (guild_id,)
            )
            
            # 近期活動（最近7天）
            recent_activity = await self.db_manager.fetchone(
                """SELECT COUNT(*) as recent_transactions
                   FROM economy_transactions 
                   WHERE guild_id = ? 
                   AND created_at >= datetime('now', '-7 days')
                   AND status = 'completed'""",
                (guild_id,)
            )
            
            return {
                "guild_id": guild_id,
                "accounts": {
                    "total": account_stats['total_accounts'] or 0,
                    "user": account_stats['user_accounts'] or 0,
                    "government_council": account_stats['council_accounts'] or 0,
                    "government_department": account_stats['department_accounts'] or 0
                },
                "currency": {
                    "total_in_circulation": float(account_stats['total_currency'] or 0),
                    "average_balance": float(account_stats['avg_balance'] or 0),
                    "highest_balance": float(account_stats['max_balance'] or 0)
                },
                "transactions": {
                    "total": transaction_stats['total_transactions'] or 0,
                    "transfers": transaction_stats['transfers'] or 0,
                    "deposits": transaction_stats['deposits'] or 0,
                    "withdraws": transaction_stats['withdraws'] or 0,
                    "total_volume": float(transaction_stats['total_volume'] or 0),
                    "average_amount": float(transaction_stats['avg_amount'] or 0)
                },
                "activity": {
                    "recent_transactions_7days": recent_activity['recent_transactions'] or 0
                }
            }
            
        except ValidationError:
            raise
        except Exception as e:
            raise ServiceError(
                f"獲取統計資料失敗：{str(e)}",
                service_name=self.name,
                operation="get_economy_statistics"
            )
    
    # ==========================================================================
    # 審計和日誌功能
    # ==========================================================================
    
    async def _audit_log(
        self,
        operation: str,
        target_type: str,
        target_id: str,
        guild_id: int,
        user_id: Optional[int] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: Optional[str] = None
    ):
        """
        記錄審計日誌
        
        參數：
            operation: 操作類型
            target_type: 目標類型
            target_id: 目標ID
            guild_id: 伺服器ID
            user_id: 執行操作的使用者ID
            old_values: 操作前的值
            new_values: 操作後的值
            success: 操作是否成功
            error_message: 錯誤訊息
        """
        if not self._audit_enabled:
            return
        
        try:
            await self.db_manager.execute(
                """INSERT INTO economy_audit_log 
                   (operation, target_type, target_id, guild_id, user_id, 
                    old_values, new_values, created_at, success, error_message)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    operation,
                    target_type,
                    target_id,
                    guild_id,
                    user_id,
                    json.dumps(old_values) if old_values else None,
                    json.dumps(new_values) if new_values else None,
                    datetime.now().isoformat(),
                    int(success),
                    error_message
                )
            )
        except Exception as e:
            # 審計日誌失敗不應影響主要操作
            self.logger.error(f"審計日誌記錄失敗：{e}")
    
    @handle_errors(log_errors=True)
    async def get_audit_log(
        self,
        guild_id: int,
        limit: int = 100,
        operation: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        獲取審計日誌
        
        參數：
            guild_id: 伺服器ID
            limit: 記錄數量限制
            operation: 操作類型篩選
            user_id: 使用者ID篩選
            
        返回：
            審計日誌列表
        """
        try:
            guild_id = validate_guild_id(guild_id)
            
            query = "SELECT * FROM economy_audit_log WHERE guild_id = ?"
            params = [guild_id]
            
            if operation:
                query += " AND operation = ?"
                params.append(operation)
            
            if user_id:
                query += " AND user_id = ?"
                params.append(user_id)
            
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            
            rows = await self.db_manager.fetchall(query, params)
            
            audit_logs = []
            for row in rows:
                log_entry = dict(row)
                # 解析JSON欄位
                if log_entry['old_values']:
                    log_entry['old_values'] = json.loads(log_entry['old_values'])
                if log_entry['new_values']:
                    log_entry['new_values'] = json.loads(log_entry['new_values'])
                audit_logs.append(log_entry)
            
            return audit_logs
            
        except ValidationError:
            raise
        except Exception as e:
            raise ServiceError(
                f"獲取審計日誌失敗：{str(e)}",
                service_name=self.name,
                operation="get_audit_log"
            )
    
    # ==========================================================================
    # 輔助功能
    # ==========================================================================
    
    def enable_audit(self, enabled: bool = True):
        """啟用或停用審計記錄"""
        self._audit_enabled = enabled
        self.logger.info(f"審計記錄已{'啟用' if enabled else '停用'}")
    
    async def health_check(self) -> Dict[str, Any]:
        """
        健康檢查
        
        返回：
            服務健康狀態
        """
        base_health = await super().health_check()
        
        try:
            # 檢查資料庫連接
            await self.db_manager.fetchone("SELECT 1")
            db_status = "healthy"
        except Exception as e:
            db_status = f"unhealthy: {str(e)}"
        
        base_health.update({
            "database_status": db_status,
            "audit_enabled": self._audit_enabled,
            "features": [
                "account_management",
                "transaction_processing",
                "currency_configuration",
                "audit_logging",
                "statistics"
            ]
        })
        
        return base_health