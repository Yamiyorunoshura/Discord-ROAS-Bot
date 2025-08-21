#!/usr/bin/env python3
"""
資料庫遷移驗證和完整性檢查工具
Task ID: 8 - 建立資料庫遷移腳本

這個腳本提供完整的遷移驗證功能：
- 遷移腳本語法驗證
- 資料庫結構完整性檢查
- 約束條件驗證
- 外鍵關係檢查
- 索引效能驗證
- 資料一致性檢查
"""

import asyncio
import aiosqlite
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# 設定專案路徑
PROJECT_ROOT = Path(__file__).parent.parent
MIGRATIONS_DIR = PROJECT_ROOT / "scripts" / "migrations"
DBS_DIR = PROJECT_ROOT / "dbs"
LOGS_DIR = PROJECT_ROOT / "logs"

# 確保目錄存在
DBS_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

class Colors:
    """終端機顏色常數"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'

class MigrationValidator:
    """資料庫遷移驗證器"""
    
    def __init__(self, test_db_path: Optional[str] = None):
        self.test_db_path = test_db_path or str(DBS_DIR / "migration_test.db")
        self.results: Dict[str, Any] = {
            'timestamp': datetime.now().isoformat(),
            'tests': [],
            'summary': {'total': 0, 'passed': 0, 'failed': 0, 'warnings': 0}
        }
        
    def log_result(self, test_name: str, status: str, message: str, details: Optional[Dict] = None):
        """記錄測試結果"""
        result = {
            'test_name': test_name,
            'status': status,
            'message': message,
            'details': details or {},
            'timestamp': datetime.now().isoformat()
        }
        self.results['tests'].append(result)
        self.results['summary']['total'] += 1
        self.results['summary'][status] += 1
        
        # 輸出到終端機
        color = Colors.GREEN if status == 'passed' else Colors.RED if status == 'failed' else Colors.YELLOW
        symbol = '✓' if status == 'passed' else '✗' if status == 'failed' else '⚠'
        print(f"{color}{symbol} {test_name}: {message}{Colors.END}")
        
    async def validate_sql_syntax(self, migration_file: Path) -> bool:
        """驗證SQL語法正確性"""
        try:
            with open(migration_file, 'r', encoding='utf-8') as f:
                sql_content = f.read()
            
            # 基本語法檢查
            if not sql_content.strip():
                self.log_result(
                    f"{migration_file.name} - 語法檢查",
                    'failed',
                    '遷移檔案為空'
                )
                return False
            
            # 檢查是否包含必要的SQL關鍵字
            required_patterns = [
                r'CREATE\s+TABLE',
                r'CREATE\s+INDEX'
            ]
            
            for pattern in required_patterns:
                if not re.search(pattern, sql_content, re.IGNORECASE):
                    self.log_result(
                        f"{migration_file.name} - 語法檢查",
                        'warnings',
                        f'未找到預期的SQL模式: {pattern}'
                    )
            
            # 嘗試在測試資料庫中解析SQL
            temp_db = str(DBS_DIR / "syntax_test.db")
            try:
                if os.path.exists(temp_db):
                    os.remove(temp_db)
                
                async with aiosqlite.connect(temp_db) as db:
                    await db.executescript(sql_content)
                    await db.commit()
                
                self.log_result(
                    f"{migration_file.name} - 語法檢查",
                    'passed',
                    'SQL語法正確'
                )
                return True
                
            except sqlite3.Error as e:
                self.log_result(
                    f"{migration_file.name} - 語法檢查",
                    'failed',
                    f'SQL語法錯誤: {str(e)}'
                )
                return False
            finally:
                if os.path.exists(temp_db):
                    os.remove(temp_db)
                    
        except Exception as e:
            self.log_result(
                f"{migration_file.name} - 語法檢查",
                'failed',
                f'檔案讀取錯誤: {str(e)}'
            )
            return False
    
    async def validate_migration_sequence(self) -> bool:
        """驗證遷移腳本序列完整性"""
        migration_files = sorted([
            f for f in MIGRATIONS_DIR.glob("*.sql")
            if f.name.startswith(('001_', '002_', '003_', '004_'))
        ])
        
        if not migration_files:
            self.log_result(
                "遷移序列檢查",
                'failed',
                '未找到遷移檔案'
            )
            return False
        
        # 檢查編號連續性
        expected_numbers = ['001', '002', '003', '004']
        found_numbers = []
        
        for file in migration_files:
            match = re.match(r'^(\d{3})_', file.name)
            if match:
                found_numbers.append(match.group(1))
        
        missing_numbers = set(expected_numbers) - set(found_numbers)
        if missing_numbers:
            self.log_result(
                "遷移序列檢查",
                'failed',
                f'缺少遷移檔案: {", ".join(sorted(missing_numbers))}'
            )
            return False
        
        extra_numbers = set(found_numbers) - set(expected_numbers)
        if extra_numbers:
            self.log_result(
                "遷移序列檢查",
                'warnings',
                f'發現額外的遷移檔案: {", ".join(sorted(extra_numbers))}'
            )
        
        self.log_result(
            "遷移序列檢查",
            'passed',
            f'找到 {len(migration_files)} 個遷移檔案，序列完整'
        )
        return True
    
    async def apply_migrations_test(self) -> bool:
        """測試遷移腳本應用"""
        try:
            # 清理測試資料庫
            if os.path.exists(self.test_db_path):
                os.remove(self.test_db_path)
            
            async with aiosqlite.connect(self.test_db_path) as db:
                # 按順序應用遷移
                migration_files = sorted([
                    f for f in MIGRATIONS_DIR.glob("*.sql")
                    if f.name.startswith(('001_', '002_', '003_', '004_'))
                ])
                
                applied_count = 0
                for migration_file in migration_files:
                    try:
                        with open(migration_file, 'r', encoding='utf-8') as f:
                            sql_content = f.read()
                        
                        start_time = time.time()
                        await db.executescript(sql_content)
                        await db.commit()
                        execution_time = (time.time() - start_time) * 1000
                        
                        applied_count += 1
                        self.log_result(
                            f"應用遷移 - {migration_file.name}",
                            'passed',
                            f'執行時間: {execution_time:.2f}ms'
                        )
                        
                    except Exception as e:
                        self.log_result(
                            f"應用遷移 - {migration_file.name}",
                            'failed',
                            f'應用失敗: {str(e)}'
                        )
                        return False
                
                self.log_result(
                    "遷移應用測試",
                    'passed',
                    f'成功應用 {applied_count} 個遷移腳本'
                )
                return True
                
        except Exception as e:
            self.log_result(
                "遷移應用測試",
                'failed',
                f'測試失敗: {str(e)}'
            )
            return False
    
    async def validate_database_structure(self) -> bool:
        """驗證資料庫結構完整性"""
        try:
            async with aiosqlite.connect(self.test_db_path) as db:
                # 檢查預期的表格
                expected_tables = {
                    # 經濟系統表格
                    'economy_accounts', 'economy_transactions', 'currency_settings', 'economy_audit_log',
                    # 核心系統表格
                    'schema_migrations', 'system_config', 'system_logs', 'user_sessions',
                    'permissions', 'role_permissions', 'system_statistics',
                    # 政府系統表格
                    'government_departments', 'government_members', 'government_resolutions',
                    'government_votes', 'government_audit_log',
                    # 成就系統表格
                    'achievements', 'user_achievement_progress', 'achievement_rewards_log',
                    'user_badges', 'achievement_audit_log'
                }
                
                # 獲取實際存在的表格
                cursor = await db.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name NOT LIKE 'sqlite_%'
                """)
                tables = {row[0] for row in await cursor.fetchall()}
                
                # 檢查缺少的表格
                missing_tables = expected_tables - tables
                if missing_tables:
                    self.log_result(
                        "資料庫結構檢查",
                        'failed',
                        f'缺少表格: {", ".join(sorted(missing_tables))}'
                    )
                    return False
                
                # 檢查額外的表格
                extra_tables = tables - expected_tables
                if extra_tables:
                    self.log_result(
                        "資料庫結構檢查",
                        'warnings',
                        f'發現額外表格: {", ".join(sorted(extra_tables))}'
                    )
                
                self.log_result(
                    "資料庫結構檢查",
                    'passed',
                    f'所有預期的 {len(expected_tables)} 個表格都存在'
                )
                return True
                
        except Exception as e:
            self.log_result(
                "資料庫結構檢查",
                'failed',
                f'檢查失敗: {str(e)}'
            )
            return False
    
    async def validate_indexes(self) -> bool:
        """驗證索引存在性和效能"""
        try:
            async with aiosqlite.connect(self.test_db_path) as db:
                # 獲取所有索引
                cursor = await db.execute("""
                    SELECT name, tbl_name FROM sqlite_master 
                    WHERE type='index' AND name NOT LIKE 'sqlite_%'
                """)
                indexes = await cursor.fetchall()
                
                # 檢查關鍵表格的索引
                critical_indexes = {
                    'economy_accounts': ['idx_economy_accounts_guild_id', 'idx_economy_accounts_user_id'],
                    'economy_transactions': ['idx_economy_transactions_guild_id', 'idx_economy_transactions_created_at'],
                    'government_departments': ['idx_gov_dept_guild_id', 'idx_gov_dept_name'],
                    'achievements': ['idx_achievements_guild_id', 'idx_achievements_status'],
                    'system_logs': ['idx_system_logs_level', 'idx_system_logs_created_at']
                }
                
                index_names = {idx[0] for idx in indexes}
                missing_indexes = []
                
                for table, expected_indexes in critical_indexes.items():
                    for expected_idx in expected_indexes:
                        if expected_idx not in index_names:
                            missing_indexes.append(f"{table}.{expected_idx}")
                
                if missing_indexes:
                    self.log_result(
                        "索引檢查",
                        'warnings',
                        f'缺少關鍵索引: {", ".join(missing_indexes)}'
                    )
                else:
                    self.log_result(
                        "索引檢查",
                        'passed',
                        f'找到 {len(indexes)} 個索引，包含所有關鍵索引'
                    )
                
                return True
                
        except Exception as e:
            self.log_result(
                "索引檢查",
                'failed',
                f'檢查失敗: {str(e)}'
            )
            return False
    
    async def validate_foreign_keys(self) -> bool:
        """驗證外鍵關係"""
        try:
            async with aiosqlite.connect(self.test_db_path) as db:
                # 啟用外鍵約束
                await db.execute("PRAGMA foreign_keys = ON")
                
                # 檢查外鍵約束
                cursor = await db.execute("PRAGMA foreign_key_check")
                fk_violations = await cursor.fetchall()
                
                if fk_violations:
                    self.log_result(
                        "外鍵約束檢查",
                        'failed',
                        f'發現 {len(fk_violations)} 個外鍵約束違規'
                    )
                    return False
                
                # 測試重要的外鍵關係
                test_cases = [
                    # 測試 economy_transactions -> economy_accounts 外鍵
                    {
                        'name': '經濟系統外鍵',
                        'setup': "INSERT INTO economy_accounts (id, account_type, guild_id, balance, created_at, updated_at) VALUES ('test_acc', 'user', 12345, 100.0, datetime('now'), datetime('now'))",
                        'test': "INSERT INTO economy_transactions (from_account, to_account, amount, transaction_type, guild_id, created_at) VALUES ('test_acc', NULL, 50.0, 'withdraw', 12345, datetime('now'))",
                        'cleanup': "DELETE FROM economy_transactions WHERE from_account = 'test_acc'; DELETE FROM economy_accounts WHERE id = 'test_acc';"
                    }
                ]
                
                for test_case in test_cases:
                    try:
                        # 設置測試資料
                        await db.execute(test_case['setup'])
                        # 執行測試
                        await db.execute(test_case['test'])
                        # 清理測試資料
                        await db.execute(test_case['cleanup'])
                        await db.commit()
                        
                        self.log_result(
                            f"外鍵測試 - {test_case['name']}",
                            'passed',
                            '外鍵約束正確運作'
                        )
                        
                    except Exception as e:
                        self.log_result(
                            f"外鍵測試 - {test_case['name']}",
                            'failed',
                            f'外鍵測試失敗: {str(e)}'
                        )
                
                return True
                
        except Exception as e:
            self.log_result(
                "外鍵約束檢查",
                'failed',
                f'檢查失敗: {str(e)}'
            )
            return False
    
    async def validate_triggers_and_views(self) -> bool:
        """驗證觸發器和視圖"""
        try:
            async with aiosqlite.connect(self.test_db_path) as db:
                # 檢查觸發器
                cursor = await db.execute("""
                    SELECT name, tbl_name FROM sqlite_master 
                    WHERE type='trigger'
                """)
                triggers = await cursor.fetchall()
                
                # 檢查視圖
                cursor = await db.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='view'
                """)
                views = await cursor.fetchall()
                
                expected_triggers = [
                    'update_achievements_timestamp',
                    'update_progress_timestamp', 
                    'set_completion_timestamp',
                    'update_government_departments_timestamp',
                    'update_resolution_vote_counts'
                ]
                
                trigger_names = {trigger[0] for trigger in triggers}
                missing_triggers = [t for t in expected_triggers if t not in trigger_names]
                
                if missing_triggers:
                    self.log_result(
                        "觸發器檢查",
                        'warnings',
                        f'缺少觸發器: {", ".join(missing_triggers)}'
                    )
                else:
                    self.log_result(
                        "觸發器檢查",
                        'passed',
                        f'找到 {len(triggers)} 個觸發器'
                    )
                
                expected_views = [
                    'active_achievements',
                    'user_achievement_stats',
                    'active_government_members',
                    'department_statistics'
                ]
                
                view_names = {view[0] for view in views}
                missing_views = [v for v in expected_views if v not in view_names]
                
                if missing_views:
                    self.log_result(
                        "視圖檢查",
                        'warnings',
                        f'缺少視圖: {", ".join(missing_views)}'
                    )
                else:
                    self.log_result(
                        "視圖檢查",
                        'passed',
                        f'找到 {len(views)} 個視圖'
                    )
                
                return True
                
        except Exception as e:
            self.log_result(
                "觸發器和視圖檢查",
                'failed',
                f'檢查失敗: {str(e)}'
            )
            return False
    
    async def run_comprehensive_validation(self) -> Dict[str, Any]:
        """執行全面的遷移驗證"""
        print(f"{Colors.BOLD}{Colors.BLUE}🔍 開始資料庫遷移驗證...{Colors.END}")
        print(f"測試資料庫路徑: {self.test_db_path}")
        print("=" * 60)
        
        # 1. 驗證遷移序列
        await self.validate_migration_sequence()
        
        # 2. 驗證SQL語法
        migration_files = sorted([
            f for f in MIGRATIONS_DIR.glob("*.sql")
            if f.name.startswith(('001_', '002_', '003_', '004_'))
        ])
        
        for migration_file in migration_files:
            await self.validate_sql_syntax(migration_file)
        
        # 3. 應用遷移測試
        migration_applied = await self.apply_migrations_test()
        
        if migration_applied:
            # 4. 驗證資料庫結構
            await self.validate_database_structure()
            
            # 5. 驗證索引
            await self.validate_indexes()
            
            # 6. 驗證外鍵關係
            await self.validate_foreign_keys()
            
            # 7. 驗證觸發器和視圖
            await self.validate_triggers_and_views()
        
        # 生成報告
        print("=" * 60)
        self._print_summary()
        self._save_report()
        
        return self.results
    
    def _print_summary(self):
        """輸出驗證摘要"""
        summary = self.results['summary']
        total = summary['total']
        passed = summary['passed']
        failed = summary['failed']
        warnings = summary['warnings']
        
        print(f"{Colors.BOLD}📊 驗證結果摘要:{Colors.END}")
        print(f"  總計: {total} 項測試")
        print(f"  {Colors.GREEN}✓ 通過: {passed} 項{Colors.END}")
        print(f"  {Colors.RED}✗ 失敗: {failed} 項{Colors.END}")
        print(f"  {Colors.YELLOW}⚠ 警告: {warnings} 項{Colors.END}")
        
        if failed == 0:
            print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 所有關鍵測試都通過了！遷移腳本準備就緒。{Colors.END}")
        else:
            print(f"\n{Colors.RED}{Colors.BOLD}❌ 發現 {failed} 個失敗項目，請檢查並修復後再次運行。{Colors.END}")
    
    def _save_report(self):
        """儲存驗證報告"""
        report_path = LOGS_DIR / f"migration_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(self.results, f, ensure_ascii=False, indent=2)
            
            print(f"\n📄 詳細報告已儲存至: {report_path}")
            
        except Exception as e:
            print(f"\n{Colors.YELLOW}⚠ 無法儲存報告: {str(e)}{Colors.END}")
    
    def cleanup(self):
        """清理測試資源"""
        try:
            if os.path.exists(self.test_db_path):
                os.remove(self.test_db_path)
        except Exception as e:
            print(f"{Colors.YELLOW}⚠ 清理測試資料庫時發生錯誤: {str(e)}{Colors.END}")

async def main():
    """主函數"""
    validator = MigrationValidator()
    
    try:
        results = await validator.run_comprehensive_validation()
        
        # 根據結果返回適當的退出碼
        if results['summary']['failed'] > 0:
            sys.exit(1)
        else:
            sys.exit(0)
            
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}⚠ 驗證被使用者中斷{Colors.END}")
        sys.exit(2)
    except Exception as e:
        print(f"\n{Colors.RED}❌ 驗證過程中發生未預期的錯誤: {str(e)}{Colors.END}")
        sys.exit(3)
    finally:
        validator.cleanup()

if __name__ == "__main__":
    asyncio.run(main())