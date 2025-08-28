#!/usr/bin/env python3
"""
ROAS Discord Bot v2.4.4 資料庫遷移管理器
==========================================

這個腳本提供完整的資料庫遷移管理功能：
- 執行v2.4.4核心架構遷移
- 驗證遷移結果
- 備份和恢復功能
- 回滾支援

使用方式:
    python migrate_v2_4_4.py [command] [options]

Commands:
    migrate     - 執行v2.4.4遷移
    rollback    - 回滾v2.4.4遷移
    validate    - 驗證遷移結果
    backup      - 備份資料庫
    status      - 檢查遷移狀態
"""

import os
import sys
import sqlite3
import argparse
import shutil
import gzip
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, List

# 專案路徑設定
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
MIGRATIONS_DIR = PROJECT_ROOT / "migrations"
DBS_DIR = PROJECT_ROOT / "dbs"
BACKUPS_DIR = PROJECT_ROOT / "backups"

# 確保目錄存在
BACKUPS_DIR.mkdir(exist_ok=True)


class MigrationManager:
    """資料庫遷移管理器"""
    
    def __init__(self, db_path: Optional[str] = None):
        """
        初始化遷移管理器
        
        Args:
            db_path: 資料庫檔案路徑，預設使用主資料庫
        """
        if db_path is None:
            self.db_path = DBS_DIR / "welcome.db"
        else:
            self.db_path = Path(db_path)
            
        self.migration_file = MIGRATIONS_DIR / "0009_v2_4_4_core_tables.sql"
        self.rollback_file = MIGRATIONS_DIR / "0009_v2_4_4_core_tables_rollback.sql"
        
        # 確保資料庫目錄存在
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
    
    def create_backup(self, backup_name: Optional[str] = None) -> Path:
        """
        建立資料庫備份
        
        Args:
            backup_name: 備份檔案名稱，如果不提供則自動生成
            
        Returns:
            Path: 備份檔案路徑
        """
        if not self.db_path.exists():
            raise FileNotFoundError(f"資料庫檔案不存在: {self.db_path}")
        
        if backup_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"v2_4_4_backup_{timestamp}.db.gz"
        
        backup_path = BACKUPS_DIR / backup_name
        
        print(f"🔄 建立資料庫備份...")
        print(f"   來源: {self.db_path}")
        print(f"   目標: {backup_path}")
        
        # 使用gzip壓縮備份
        with open(self.db_path, 'rb') as f_in:
            with gzip.open(backup_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        print(f"✅ 備份完成: {backup_path}")
        return backup_path
    
    def restore_backup(self, backup_path: Path) -> bool:
        """
        從備份恢復資料庫
        
        Args:
            backup_path: 備份檔案路徑
            
        Returns:
            bool: 恢復是否成功
        """
        if not backup_path.exists():
            print(f"❌ 備份檔案不存在: {backup_path}")
            return False
        
        print(f"🔄 從備份恢復資料庫...")
        print(f"   備份: {backup_path}")
        print(f"   目標: {self.db_path}")
        
        try:
            # 解壓縮並恢復
            with gzip.open(backup_path, 'rb') as f_in:
                with open(self.db_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            print("✅ 資料庫恢復成功")
            return True
            
        except Exception as e:
            print(f"❌ 恢復失敗: {e}")
            return False
    
    def check_migration_status(self) -> Tuple[bool, List[str]]:
        """
        檢查遷移狀態
        
        Returns:
            Tuple[bool, List[str]]: (是否已遷移, 已應用的遷移列表)
        """
        if not self.db_path.exists():
            return False, []
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 檢查遷移記錄表是否存在
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='schema_migrations'
                """)
                
                if not cursor.fetchone():
                    return False, []
                
                # 獲取已應用的遷移
                cursor.execute("SELECT version FROM schema_migrations ORDER BY version")
                applied_migrations = [row[0] for row in cursor.fetchall()]
                
                # 檢查v2.4.4遷移是否已應用
                is_migrated = '0009_v2_4_4_core_tables' in applied_migrations
                
                return is_migrated, applied_migrations
                
        except Exception as e:
            print(f"⚠️  檢查遷移狀態時發生錯誤: {e}")
            return False, []
    
    def execute_sql_file(self, sql_file: Path) -> bool:
        """
        執行SQL檔案
        
        Args:
            sql_file: SQL檔案路徑
            
        Returns:
            bool: 執行是否成功
        """
        if not sql_file.exists():
            print(f"❌ SQL檔案不存在: {sql_file}")
            return False
        
        try:
            with open(sql_file, 'r', encoding='utf-8') as f:
                sql_content = f.read()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 啟用外鍵約束
                cursor.execute("PRAGMA foreign_keys = ON")
                
                # 分割並執行SQL語句
                statements = self._split_sql_statements(sql_content)
                
                for statement in statements:
                    statement = statement.strip()
                    if statement and not statement.startswith('--'):
                        try:
                            cursor.execute(statement)
                        except sqlite3.Error as e:
                            print(f"⚠️  執行SQL語句時發生錯誤: {e}")
                            print(f"    語句: {statement[:100]}...")
                            # 對於某些錯誤，我們繼續執行（如索引已存在等）
                            if "already exists" not in str(e).lower():
                                raise
                
                conn.commit()
                
            return True
            
        except Exception as e:
            print(f"❌ 執行SQL檔案失敗: {e}")
            return False
    
    def _split_sql_statements(self, sql_content: str) -> List[str]:
        """
        分割SQL語句，處理複雜的TRIGGER語法
        
        Args:
            sql_content: SQL內容
            
        Returns:
            List[str]: 分割後的SQL語句列表
        """
        statements = []
        current_statement = ""
        lines = sql_content.split('\n')
        
        in_trigger = False
        trigger_depth = 0
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('--'):
                continue
            
            # 檢測TRIGGER開始
            if line.upper().startswith('CREATE TRIGGER'):
                in_trigger = True
                trigger_depth = 0
            
            current_statement += line + '\n'
            
            # 在TRIGGER內部跟蹤BEGIN/END
            if in_trigger:
                if 'BEGIN' in line.upper():
                    trigger_depth += 1
                elif 'END;' in line.upper():
                    trigger_depth -= 1
                    if trigger_depth <= 0:
                        # TRIGGER結束
                        statements.append(current_statement.strip())
                        current_statement = ""
                        in_trigger = False
                        continue
            
            # 正常語句以分號結尾
            if line.endswith(';') and not in_trigger:
                statements.append(current_statement.strip())
                current_statement = ""
        
        # 添加剩餘的語句
        if current_statement.strip():
            statements.append(current_statement.strip())
        
        return statements
    
    def migrate(self) -> bool:
        """
        執行v2.4.4遷移
        
        Returns:
            bool: 遷移是否成功
        """
        print("🚀 開始執行v2.4.4資料庫遷移")
        print("=" * 50)
        
        # 檢查當前狀態
        is_migrated, applied_migrations = self.check_migration_status()
        
        if is_migrated:
            print("ℹ️  v2.4.4遷移已經執行過，無需重複執行")
            return True
        
        # 建立備份
        try:
            backup_path = self.create_backup()
            print(f"✅ 備份已建立: {backup_path}")
        except Exception as e:
            print(f"❌ 備份失敗: {e}")
            print("建議手動備份資料庫後再繼續")
            return False
        
        # 執行遷移
        print(f"🔄 執行遷移腳本: {self.migration_file}")
        
        if self.execute_sql_file(self.migration_file):
            print("✅ 遷移腳本執行成功")
            
            # 記錄遷移
            self._record_migration()
            
            print("🎉 v2.4.4資料庫遷移完成！")
            return True
        else:
            print("❌ 遷移失敗")
            
            # 詢問是否要恢復備份
            try:
                user_input = input("是否要從備份恢復資料庫？ (y/N): ").strip().lower()
                if user_input == 'y':
                    self.restore_backup(backup_path)
            except (KeyboardInterrupt, EOFError):
                pass
            
            return False
    
    def rollback(self) -> bool:
        """
        回滾v2.4.4遷移
        
        Returns:
            bool: 回滾是否成功
        """
        print("🔄 開始回滾v2.4.4資料庫遷移")
        print("=" * 50)
        
        # 檢查當前狀態
        is_migrated, applied_migrations = self.check_migration_status()
        
        if not is_migrated:
            print("ℹ️  v2.4.4遷移尚未執行，無需回滾")
            return True
        
        # 建立回滾前備份
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self.create_backup(f"pre_rollback_backup_{timestamp}.db.gz")
            print(f"✅ 回滾前備份已建立: {backup_path}")
        except Exception as e:
            print(f"❌ 備份失敗: {e}")
            print("建議手動備份資料庫後再繼續")
            return False
        
        # 執行回滾
        print(f"🔄 執行回滾腳本: {self.rollback_file}")
        
        if self.execute_sql_file(self.rollback_file):
            print("✅ 回滾腳本執行成功")
            print("🎉 v2.4.4資料庫回滾完成！")
            return True
        else:
            print("❌ 回滾失敗")
            return False
    
    def _record_migration(self):
        """記錄遷移到schema_migrations表"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 確保遷移記錄表存在
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version TEXT PRIMARY KEY,
                        description TEXT,
                        applied_at TEXT,
                        checksum TEXT
                    )
                """)
                
                # 記錄遷移
                cursor.execute("""
                    INSERT OR REPLACE INTO schema_migrations 
                    (version, description, applied_at) 
                    VALUES (?, ?, ?)
                """, (
                    "0009_v2_4_4_core_tables",
                    "建立支援子機器人、AI系統和部署管理的核心資料表",
                    datetime.now().isoformat()
                ))
                
                conn.commit()
                
        except Exception as e:
            print(f"⚠️  記錄遷移時發生錯誤: {e}")
    
    def validate(self) -> bool:
        """
        驗證遷移結果
        
        Returns:
            bool: 驗證是否通過
        """
        print("🔍 開始驗證v2.4.4資料庫遷移")
        print("=" * 50)
        
        # 執行驗證腳本
        validation_script = SCRIPT_DIR / "validate_v2_4_4_migration.py"
        
        if not validation_script.exists():
            print(f"❌ 驗證腳本不存在: {validation_script}")
            return False
        
        import subprocess
        
        try:
            result = subprocess.run([
                sys.executable, str(validation_script), str(self.db_path)
            ], capture_output=True, text=True)
            
            print(result.stdout)
            if result.stderr:
                print("錯誤輸出:")
                print(result.stderr)
            
            return result.returncode == 0
            
        except Exception as e:
            print(f"❌ 執行驗證腳本失敗: {e}")
            return False
    
    def status(self) -> None:
        """顯示遷移狀態"""
        print("📊 資料庫遷移狀態")
        print("=" * 30)
        
        print(f"資料庫路徑: {self.db_path}")
        print(f"資料庫存在: {'是' if self.db_path.exists() else '否'}")
        
        if self.db_path.exists():
            file_size = self.db_path.stat().st_size
            print(f"檔案大小: {file_size:,} bytes ({file_size/1024/1024:.2f} MB)")
        
        is_migrated, applied_migrations = self.check_migration_status()
        
        print(f"v2.4.4已遷移: {'是' if is_migrated else '否'}")
        print(f"已應用遷移數: {len(applied_migrations)}")
        
        if applied_migrations:
            print("已應用的遷移:")
            for migration in applied_migrations[-5:]:  # 顯示最近5個遷移
                print(f"  - {migration}")
            if len(applied_migrations) > 5:
                print(f"  ... 和其他 {len(applied_migrations) - 5} 個遷移")


def main():
    """主函數"""
    parser = argparse.ArgumentParser(
        description="ROAS Discord Bot v2.4.4 資料庫遷移管理器"
    )
    
    parser.add_argument(
        'command',
        choices=['migrate', 'rollback', 'validate', 'backup', 'status'],
        help='要執行的命令'
    )
    
    parser.add_argument(
        '--database', '-d',
        type=str,
        help='資料庫檔案路徑（預設使用主資料庫）'
    )
    
    parser.add_argument(
        '--backup-name', '-b',
        type=str,
        help='備份檔案名稱（僅用於backup命令）'
    )
    
    args = parser.parse_args()
    
    # 建立遷移管理器
    manager = MigrationManager(args.database)
    
    # 執行命令
    success = True
    
    if args.command == 'migrate':
        success = manager.migrate()
    elif args.command == 'rollback':
        success = manager.rollback()
    elif args.command == 'validate':
        success = manager.validate()
    elif args.command == 'backup':
        try:
            backup_path = manager.create_backup(args.backup_name)
            print(f"✅ 備份完成: {backup_path}")
        except Exception as e:
            print(f"❌ 備份失敗: {e}")
            success = False
    elif args.command == 'status':
        manager.status()
    
    # 設定退出代碼
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()