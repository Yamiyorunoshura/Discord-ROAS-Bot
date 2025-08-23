#!/usr/bin/env python3
"""
增強的遷移管理器 - T4 資料完整性與測試隔離
Task ID: T4 - 資料完整性與測試隔離

這個模組擴展現有的遷移管理器，增加：
- 雙態驗證（新/舊資料庫）
- 資料完整性檢查
- 自動回滾機制
- 強化的錯誤處理
"""

import asyncio
import aiosqlite
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
import tempfile
import shutil

# 設定專案路徑
PROJECT_ROOT = Path(__file__).parent.parent
MIGRATIONS_DIR = PROJECT_ROOT / "migrations"
DBS_DIR = PROJECT_ROOT / "dbs"
LOGS_DIR = PROJECT_ROOT / "logs"

# 確保目錄存在
MIGRATIONS_DIR.mkdir(exist_ok=True)
DBS_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)


class MigrationValidationError(Exception):
    """遷移驗證錯誤"""
    pass


class DataIntegrityError(Exception):
    """資料完整性錯誤"""
    pass


class EnhancedMigrationManager:
    """增強的資料庫遷移管理器，支援雙態驗證和完整性檢查"""
    
    def __init__(self, database_path: Optional[str] = None):
        self.database_path = database_path or str(DBS_DIR / "main.db")
        self.migrations_dir = MIGRATIONS_DIR
        self.validation_log = []
        
    def _get_file_checksum(self, file_path: Path) -> str:
        """計算檔案校驗和"""
        with open(file_path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()
    
    async def _ensure_migrations_table(self, db: aiosqlite.Connection):
        """確保遷移管理表存在，包含增強欄位"""
        # 首先檢查表是否存在
        cursor = await db.execute("""
            SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'
        """)
        table_exists = await cursor.fetchone()
        
        if not table_exists:
            # 建立新的表
            await db.execute("""
                CREATE TABLE schema_migrations (
                    version TEXT PRIMARY KEY,
                    description TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    checksum TEXT NOT NULL,
                    applied_at TIMESTAMP NOT NULL,
                    execution_time_ms INTEGER NOT NULL,
                    success INTEGER NOT NULL DEFAULT 1,
                    error_message TEXT,
                    rollback_available INTEGER DEFAULT 0,
                    validation_passed INTEGER DEFAULT 1,
                    pre_migration_checksum TEXT,
                    post_migration_checksum TEXT
                )
            """)
        else:
            # 檢查並添加缺失的欄位
            cursor = await db.execute("PRAGMA table_info(schema_migrations)")
            columns = await cursor.fetchall()
            existing_columns = {col[1] for col in columns}
            
            required_columns = {
                'rollback_available': 'INTEGER DEFAULT 0',
                'validation_passed': 'INTEGER DEFAULT 1',
                'pre_migration_checksum': 'TEXT',
                'post_migration_checksum': 'TEXT'
            }
            
            for column_name, column_def in required_columns.items():
                if column_name not in existing_columns:
                    await db.execute(f"ALTER TABLE schema_migrations ADD COLUMN {column_name} {column_def}")
        
        await db.commit()
    
    async def verify_dual_state_migration(self, migration_id: str) -> Dict[str, Any]:
        """
        雙態驗證：在新建和既有資料庫上驗證遷移
        F-1: 資料庫遷移與雙態驗證
        """
        results = {
            'migration_id': migration_id,
            'timestamp': datetime.now().isoformat(),
            'new_database_test': None,
            'existing_database_test': None,
            'validation_passed': False,
            'errors': []
        }
        
        try:
            # 測試1: 在新建資料庫上測試遷移
            results['new_database_test'] = await self._test_migration_on_new_database(migration_id)
            
            # 測試2: 在既有資料庫上測試遷移
            results['existing_database_test'] = await self._test_migration_on_existing_database(migration_id)
            
            # 評估整體驗證結果
            new_db_passed = results['new_database_test'].get('success', False)
            existing_db_passed = results['existing_database_test'].get('success', False)
            
            results['validation_passed'] = new_db_passed and existing_db_passed
            
            # 收集錯誤
            if not new_db_passed:
                results['errors'].extend(results['new_database_test'].get('errors', []))
            if not existing_db_passed:
                results['errors'].extend(results['existing_database_test'].get('errors', []))
            
            # 記錄驗證結果
            self.validation_log.append(results)
            
            return results
            
        except Exception as e:
            results['errors'].append(f"雙態驗證過程發生錯誤: {str(e)}")
            return results
    
    async def _test_migration_on_new_database(self, migration_id: str) -> Dict[str, Any]:
        """在新建資料庫上測試遷移"""
        test_result = {
            'test_type': 'new_database',
            'success': False,
            'execution_time_ms': 0,
            'errors': [],
            'database_path': None
        }
        
        temp_db = None
        try:
            # 創建臨時資料庫
            temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
            temp_db_path = temp_db.name
            temp_db.close()
            
            test_result['database_path'] = temp_db_path
            
            # 在新資料庫上應用遷移
            temp_manager = EnhancedMigrationManager(temp_db_path)
            
            start_time = time.time()
            apply_result = await temp_manager.apply_migration(migration_id)
            execution_time = int((time.time() - start_time) * 1000)
            
            test_result['execution_time_ms'] = execution_time
            test_result['success'] = apply_result.get('success', False)
            
            if not test_result['success']:
                test_result['errors'].append(apply_result.get('error', '未知錯誤'))
            
            # 驗證遷移後的資料完整性
            integrity_result = await temp_manager.check_data_integrity()
            if not integrity_result.get('success', False):
                test_result['errors'].extend(integrity_result.get('errors', []))
                test_result['success'] = False
            
        except Exception as e:
            test_result['errors'].append(f"新資料庫測試過程錯誤: {str(e)}")
        
        finally:
            # 清理臨時資料庫
            if temp_db and os.path.exists(temp_db.name):
                try:
                    os.unlink(temp_db.name)
                except OSError:
                    pass
        
        return test_result
    
    async def _test_migration_on_existing_database(self, migration_id: str) -> Dict[str, Any]:
        """在既有資料庫上測試遷移"""
        test_result = {
            'test_type': 'existing_database',
            'success': False,
            'execution_time_ms': 0,
            'errors': [],
            'backup_path': None
        }
        
        backup_path = None
        try:
            # 創建資料庫備份
            if os.path.exists(self.database_path):
                backup_path = f"{self.database_path}.backup_{int(time.time())}"
                shutil.copy2(self.database_path, backup_path)
                test_result['backup_path'] = backup_path
                
                # 應用遷移
                start_time = time.time()
                apply_result = await self.apply_migration(migration_id)
                execution_time = int((time.time() - start_time) * 1000)
                
                test_result['execution_time_ms'] = execution_time
                test_result['success'] = apply_result.get('success', False)
                
                if not test_result['success']:
                    test_result['errors'].append(apply_result.get('error', '未知錯誤'))
                    # 從備份恢復
                    if backup_path:
                        shutil.copy2(backup_path, self.database_path)
                
                # 驗證遷移後的資料完整性
                integrity_result = await self.check_data_integrity()
                if not integrity_result.get('success', False):
                    test_result['errors'].extend(integrity_result.get('errors', []))
                    test_result['success'] = False
                    # 從備份恢復
                    if backup_path:
                        shutil.copy2(backup_path, self.database_path)
            else:
                # 如果原資料庫不存在，這實際上是新資料庫測試
                test_result = await self._test_migration_on_new_database(migration_id)
                test_result['test_type'] = 'existing_database_fallback_to_new'
            
        except Exception as e:
            test_result['errors'].append(f"既有資料庫測試過程錯誤: {str(e)}")
            # 嘗試從備份恢復
            if backup_path and os.path.exists(backup_path):
                try:
                    shutil.copy2(backup_path, self.database_path)
                except Exception as restore_error:
                    test_result['errors'].append(f"備份恢復失敗: {str(restore_error)}")
        
        finally:
            # 清理備份檔案
            if backup_path and os.path.exists(backup_path):
                try:
                    os.unlink(backup_path)
                except OSError:
                    pass
        
        return test_result
    
    async def check_data_integrity(self) -> Dict[str, Any]:
        """
        檢查資料完整性
        F-4: 資料完整性回歸測試套件
        """
        integrity_result = {
            'success': True,
            'timestamp': datetime.now().isoformat(),
            'checks_performed': [],
            'errors': [],
            'warnings': [],
            'statistics': {}
        }
        
        try:
            async with aiosqlite.connect(self.database_path) as db:
                # 檢查1: 外鍵約束
                await self._check_foreign_key_integrity(db, integrity_result)
                
                # 檢查2: 唯一性約束
                await self._check_unique_constraints(db, integrity_result)
                
                # 檢查3: 非空約束
                await self._check_not_null_constraints(db, integrity_result)
                
                # 檢查4: 業務邏輯一致性
                await self._check_business_logic_consistency(db, integrity_result)
                
                # 檢查5: 資料類型完整性
                await self._check_data_type_integrity(db, integrity_result)
                
                # 統計資訊
                await self._collect_integrity_statistics(db, integrity_result)
                
        except Exception as e:
            integrity_result['success'] = False
            integrity_result['errors'].append(f"完整性檢查過程錯誤: {str(e)}")
        
        return integrity_result
    
    async def _check_foreign_key_integrity(self, db: aiosqlite.Connection, result: Dict[str, Any]):
        """檢查外鍵完整性"""
        result['checks_performed'].append('foreign_key_integrity')
        
        try:
            # 啟用外鍵檢查
            await db.execute("PRAGMA foreign_keys = ON")
            
            # 執行外鍵完整性檢查
            cursor = await db.execute("PRAGMA foreign_key_check")
            violations = await cursor.fetchall()
            
            if violations:
                result['errors'].extend([
                    f"外鍵違規: {violation}" for violation in violations
                ])
                result['success'] = False
            
        except Exception as e:
            result['errors'].append(f"外鍵檢查錯誤: {str(e)}")
            result['success'] = False
    
    async def _check_unique_constraints(self, db: aiosqlite.Connection, result: Dict[str, Any]):
        """檢查唯一性約束"""
        result['checks_performed'].append('unique_constraints')
        
        try:
            # 首先檢查表是否存在
            cursor = await db.execute("""
                SELECT name FROM sqlite_master WHERE type='table' AND name='activity_meter'
            """)
            table_exists = await cursor.fetchone()
            
            if table_exists:
                # 檢查 activity_meter 表的唯一性約束
                cursor = await db.execute("""
                    SELECT guild_id, user_id, COUNT(*) as cnt
                    FROM activity_meter
                    GROUP BY guild_id, user_id
                    HAVING COUNT(*) > 1
                """)
                duplicates = await cursor.fetchall()
                
                if duplicates:
                    result['errors'].extend([
                        f"activity_meter 表重複記錄: guild_id={dup[0]}, user_id={dup[1]}, count={dup[2]}"
                        for dup in duplicates
                    ])
                    result['success'] = False
            else:
                result['warnings'].append("activity_meter 表不存在，跳過唯一性約束檢查")
            
        except Exception as e:
            result['warnings'].append(f"唯一性約束檢查錯誤: {str(e)}")
    
    async def _check_not_null_constraints(self, db: aiosqlite.Connection, result: Dict[str, Any]):
        """檢查非空約束"""
        result['checks_performed'].append('not_null_constraints')
        
        # 定義關鍵表的非空欄位
        not_null_checks = {
            'activity_meter': ['guild_id', 'user_id'],
            'economy_accounts': ['account_id', 'guild_id'],
            'achievements': ['achievement_id', 'name']
        }
        
        for table, columns in not_null_checks.items():
            try:
                # 首先檢查表是否存在
                cursor = await db.execute("""
                    SELECT name FROM sqlite_master WHERE type='table' AND name=?
                """, (table,))
                table_exists = await cursor.fetchone()
                
                if not table_exists:
                    result['warnings'].append(f"表 {table} 不存在，跳過非空約束檢查")
                    continue
                
                for column in columns:
                    try:
                        cursor = await db.execute(f"""
                            SELECT COUNT(*) FROM {table} WHERE {column} IS NULL
                        """)
                        null_count = (await cursor.fetchone())[0]
                        
                        if null_count > 0:
                            result['errors'].append(
                                f"表 {table} 的欄位 {column} 有 {null_count} 個 NULL 值"
                            )
                            result['success'] = False
                            
                    except Exception as e:
                        result['warnings'].append(
                            f"檢查 {table}.{column} 非空約束時錯誤: {str(e)}"
                        )
                        
            except Exception as e:
                result['warnings'].append(
                    f"檢查表 {table} 存在性時錯誤: {str(e)}"
                )
    
    async def _check_business_logic_consistency(self, db: aiosqlite.Connection, result: Dict[str, Any]):
        """檢查業務邏輯一致性"""
        result['checks_performed'].append('business_logic_consistency')
        
        try:
            # 檢查表是否存在
            cursor = await db.execute("""
                SELECT name FROM sqlite_master WHERE type='table' AND name='activity_meter'
            """)
            if not await cursor.fetchone():
                result['warnings'].append("activity_meter 表不存在，跳過業務邏輯檢查")
                return
                
            # 檢查活躍度分數不能為負數
            cursor = await db.execute("""
                SELECT COUNT(*) FROM activity_meter WHERE score < 0
            """)
            negative_scores = (await cursor.fetchone())[0]
            
            if negative_scores > 0:
                result['warnings'].append(f"發現 {negative_scores} 個負數活躍度分數")
            
            # 檢查經濟帳戶餘額合理性
            try:
                cursor = await db.execute("""
                    SELECT name FROM sqlite_master WHERE type='table' AND name='economy_accounts'
                """)
                if await cursor.fetchone():
                    cursor = await db.execute("""
                        SELECT COUNT(*) FROM economy_accounts WHERE balance < -1000000
                    """)
                    extreme_negative_balance = (await cursor.fetchone())[0]
                    
                    if extreme_negative_balance > 0:
                        result['warnings'].append(f"發現 {extreme_negative_balance} 個極端負餘額帳戶")
                else:
                    result['warnings'].append("economy_accounts 表不存在，跳過餘額檢查")
            except Exception:
                result['warnings'].append("economy_accounts 表檢查失敗")
            
        except Exception as e:
            result['warnings'].append(f"業務邏輯檢查錯誤: {str(e)}")
    
    async def _check_data_type_integrity(self, db: aiosqlite.Connection, result: Dict[str, Any]):
        """檢查資料類型完整性"""
        result['checks_performed'].append('data_type_integrity')
        
        try:
            # 檢查表是否存在
            cursor = await db.execute("""
                SELECT name FROM sqlite_master WHERE type='table' AND name='activity_meter'
            """)
            if not await cursor.fetchone():
                result['warnings'].append("activity_meter 表不存在，跳過資料類型檢查")
                return
                
            # 檢查 guild_id 和 user_id 是否為有效整數
            cursor = await db.execute("""
                SELECT COUNT(*) FROM activity_meter 
                WHERE typeof(guild_id) != 'integer' OR typeof(user_id) != 'integer'
            """)
            invalid_types = (await cursor.fetchone())[0]
            
            if invalid_types > 0:
                result['errors'].append(f"發現 {invalid_types} 個無效的 ID 資料類型")
                result['success'] = False
            
        except Exception as e:
            result['warnings'].append(f"資料類型檢查錯誤: {str(e)}")
    
    async def _collect_integrity_statistics(self, db: aiosqlite.Connection, result: Dict[str, Any]):
        """收集完整性統計資訊"""
        try:
            # 收集各表的記錄數
            tables = ['activity_meter', 'economy_accounts', 'achievements', 'schema_migrations']
            
            for table in tables:
                try:
                    cursor = await db.execute(f"SELECT COUNT(*) FROM {table}")
                    count = (await cursor.fetchone())[0]
                    result['statistics'][f'{table}_count'] = count
                except Exception:
                    result['statistics'][f'{table}_count'] = 'N/A'
            
        except Exception as e:
            result['warnings'].append(f"統計資訊收集錯誤: {str(e)}")
    
    async def apply_migration(self, version: str) -> Dict[str, Any]:
        """應用特定版本的遷移，包含完整性驗證"""
        try:
            # 找到遷移檔案，支援填充零的版本號
            migration_file = None
            patterns_to_try = [
                f"{version}_",                    # 原始版本號
                f"{version.zfill(4)}_",          # 4位數填充零
                f"{version.zfill(3)}_"           # 3位數填充零
            ]
            
            for pattern in patterns_to_try:
                for file in self.migrations_dir.glob("*.sql"):
                    if file.name.startswith(pattern) and not file.name.endswith('_rollback.sql'):
                        migration_file = file
                        break
                if migration_file:
                    break
            
            if not migration_file:
                return {
                    'success': False,
                    'error': f'未找到版本 {version} 的遷移檔案'
                }
            
            # 讀取遷移內容
            with open(migration_file, 'r', encoding='utf-8') as f:
                sql_content = f.read()
            
            # 提取描述
            description = ""
            for line in sql_content.split('\n'):
                if '描述:' in line or 'Description:' in line:
                    description = line.split(':', 1)[-1].strip()
                    break
            if not description:
                description = f"Migration {version}"
            
            # 計算校驗和
            checksum = self._get_file_checksum(migration_file)
            
            async with aiosqlite.connect(self.database_path) as db:
                await self._ensure_migrations_table(db)
                
                # 檢查是否已應用
                cursor = await db.execute(
                    "SELECT version FROM schema_migrations WHERE version = ?",
                    (version,)
                )
                if await cursor.fetchone():
                    return {
                        'success': False,
                        'error': f'遷移 {version} 已經應用過了'
                    }
                
                # 記錄遷移前的資料庫狀態
                pre_migration_result = await self.check_data_integrity()
                pre_checksum = hashlib.md5(
                    json.dumps(pre_migration_result, sort_keys=True).encode()
                ).hexdigest()
                
                # 應用遷移
                start_time = time.time()
                success = True
                error_message = None
                
                try:
                    # 將SQL分割成多個語句分別執行，以便更好的錯誤報告
                    statements = sql_content.split(';')
                    for i, statement in enumerate(statements):
                        statement = statement.strip()
                        if statement and not statement.startswith('--'):
                            try:
                                await db.execute(statement)
                            except Exception as stmt_error:
                                error_message = f"執行第 {i+1} 個SQL語句時失敗: {str(stmt_error)}\n語句: {statement[:200]}..."
                                raise stmt_error
                    
                    await db.commit()
                except Exception as e:
                    success = False
                    if not error_message:
                        error_message = str(e)
                    await db.rollback()
                
                execution_time_ms = int((time.time() - start_time) * 1000)
                
                # 驗證遷移後的資料完整性
                post_migration_result = await self.check_data_integrity()
                post_checksum = hashlib.md5(
                    json.dumps(post_migration_result, sort_keys=True).encode()
                ).hexdigest()
                
                validation_passed = post_migration_result.get('success', False)
                
                # 檢查是否有回滾腳本
                rollback_file = self.migrations_dir / f"{migration_file.stem}_rollback.sql"
                rollback_available = rollback_file.exists()
                
                # 記錄遷移狀態
                await db.execute("""
                    INSERT INTO schema_migrations 
                    (version, description, filename, checksum, applied_at, 
                     execution_time_ms, success, error_message, rollback_available,
                     validation_passed, pre_migration_checksum, post_migration_checksum)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    version,
                    description,
                    migration_file.name,
                    checksum,
                    datetime.now().isoformat(),
                    execution_time_ms,
                    1 if success else 0,
                    error_message,
                    1 if rollback_available else 0,
                    1 if validation_passed else 0,
                    pre_checksum,
                    post_checksum
                ))
                await db.commit()
                
                result = {
                    'success': success and validation_passed,
                    'version': version,
                    'filename': migration_file.name,
                    'description': description,
                    'execution_time_ms': execution_time_ms,
                    'rollback_available': rollback_available,
                    'validation_passed': validation_passed,
                    'integrity_check': post_migration_result
                }
                
                if not success:
                    result['error'] = error_message
                elif not validation_passed:
                    result['error'] = '遷移後資料完整性驗證失敗'
                    result['integrity_errors'] = post_migration_result.get('errors', [])
                
                return result
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def apply_pending_migrations(self) -> Dict[str, Any]:
        """應用所有待處理的遷移"""
        try:
            # 獲取可用的遷移檔案
            migration_files = sorted([
                f for f in self.migrations_dir.glob("*.sql")
                if re.match(r'^\d{3}_.*\.sql$', f.name) and not f.name.endswith('_rollback.sql')
            ])
            
            if not migration_files:
                return {
                    'success': True,
                    'message': '沒有可用的遷移檔案',
                    'applied_count': 0,
                    'results': []
                }
            
            # 檢查已應用的遷移
            async with aiosqlite.connect(self.database_path) as db:
                await self._ensure_migrations_table(db)
                
                cursor = await db.execute("SELECT version FROM schema_migrations")
                applied_versions = {row[0] for row in await cursor.fetchall()}
            
            # 找出待處理的遷移
            pending_migrations = []
            for file in migration_files:
                version = file.name[:3]
                if version not in applied_versions:
                    pending_migrations.append(version)
            
            if not pending_migrations:
                return {
                    'success': True,
                    'message': '沒有待處理的遷移',
                    'applied_count': 0,
                    'results': []
                }
            
            # 按順序應用遷移
            results = []
            applied_count = 0
            
            for version in sorted(pending_migrations):
                result = await self.apply_migration(version)
                results.append(result)
                
                if result['success']:
                    applied_count += 1
                else:
                    # 如果遷移失敗，停止處理後續遷移
                    break
            
            return {
                'success': applied_count == len(pending_migrations),
                'applied_count': applied_count,
                'total_pending': len(pending_migrations),
                'results': results
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'applied_count': 0,
                'results': []
            }
    
    async def rollback_migration(self, version: str) -> Dict[str, Any]:
        """回滾特定版本的遷移，使用回滾腳本"""
        try:
            # 尋找回滾腳本，支援填充零的版本號
            rollback_file = None
            patterns_to_try = [
                f"{version}_",                    # 原始版本號
                f"{version.zfill(4)}_",          # 4位數填充零
                f"{version.zfill(3)}_"           # 3位數填充零
            ]
            
            for pattern in patterns_to_try:
                for file in self.migrations_dir.glob("*_rollback.sql"):
                    if file.name.startswith(pattern):
                        rollback_file = file
                        break
                if rollback_file:
                    break
            
            if not rollback_file:
                return {
                    'success': False,
                    'error': f'未找到版本 {version} 的回滾腳本'
                }
            
            async with aiosqlite.connect(self.database_path) as db:
                await self._ensure_migrations_table(db)
                
                # 檢查遷移是否存在
                cursor = await db.execute(
                    "SELECT version, filename FROM schema_migrations WHERE version = ?",
                    (version,)
                )
                migration = await cursor.fetchone()
                
                if not migration:
                    return {
                        'success': False,
                        'error': f'未找到已應用的遷移 {version}'
                    }
                
                # 讀取回滾腳本
                with open(rollback_file, 'r', encoding='utf-8') as f:
                    rollback_sql = f.read()
                
                # 執行回滾
                start_time = time.time()
                success = True
                error_message = None
                
                try:
                    await db.executescript(rollback_sql)
                    await db.commit()
                    
                    # 從遷移記錄中移除
                    await db.execute(
                        "DELETE FROM schema_migrations WHERE version = ?",
                        (version,)
                    )
                    await db.commit()
                    
                except Exception as e:
                    success = False
                    error_message = str(e)
                    await db.rollback()
                
                execution_time_ms = int((time.time() - start_time) * 1000)
                
                # 驗證回滾後的資料完整性
                integrity_result = await self.check_data_integrity()
                
                return {
                    'success': success and integrity_result.get('success', False),
                    'version': version,
                    'filename': migration[1],
                    'rollback_filename': rollback_file.name,
                    'execution_time_ms': execution_time_ms,
                    'message': f'遷移 {version} 已成功回滾' if success else f'回滾失敗: {error_message}',
                    'integrity_check': integrity_result,
                    'error': error_message if not success else None
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }


# 與原有 MigrationManager 保持相容性的包裝函數
def create_enhanced_migration_manager(database_path: Optional[str] = None) -> EnhancedMigrationManager:
    """創建增強的遷移管理器實例"""
    return EnhancedMigrationManager(database_path)


# 如果直接執行此檔案，提供命令列介面
if __name__ == "__main__":
    import argparse
    
    async def main():
        parser = argparse.ArgumentParser(description='增強的資料庫遷移管理工具')
        parser.add_argument('--db', default=None, help='資料庫檔案路徑')
        
        subparsers = parser.add_subparsers(dest='command', help='可用命令')
        
        # 雙態驗證命令
        dual_parser = subparsers.add_parser('dual-verify', help='執行雙態驗證')
        dual_parser.add_argument('version', help='要驗證的遷移版本號')
        
        # 完整性檢查命令
        subparsers.add_parser('integrity-check', help='執行資料完整性檢查')
        
        args = parser.parse_args()
        
        if not args.command:
            parser.print_help()
            return
        
        manager = EnhancedMigrationManager(args.db)
        
        if args.command == 'dual-verify':
            result = await manager.verify_dual_state_migration(args.version)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            
        elif args.command == 'integrity-check':
            result = await manager.check_data_integrity()
            print(json.dumps(result, indent=2, ensure_ascii=False))
    
    asyncio.run(main())