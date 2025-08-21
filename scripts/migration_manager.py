#!/usr/bin/env python3
"""
遷移執行狀態監控和管理工具
Task ID: 8 - 建立資料庫遷移腳本

這個腳本提供完整的遷移管理功能：
- 遷移狀態查詢
- 遷移執行管理
- 遷移回滾功能
- 遷移歷史追蹤
- 效能監控和報告
"""

import asyncio
import aiosqlite
import argparse
import hashlib
import json
import os
import re
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

class MigrationManager:
    """資料庫遷移管理器"""
    
    def __init__(self, database_path: Optional[str] = None):
        self.database_path = database_path or str(DBS_DIR / "main.db")
        self.migrations_dir = MIGRATIONS_DIR
        
    def _get_file_checksum(self, file_path: Path) -> str:
        """計算檔案校驗和"""
        with open(file_path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()
    
    async def _ensure_migrations_table(self, db: aiosqlite.Connection):
        """確保遷移管理表存在"""
        await db.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                filename TEXT NOT NULL,
                checksum TEXT NOT NULL,
                applied_at TIMESTAMP NOT NULL,
                execution_time_ms INTEGER NOT NULL,
                success INTEGER NOT NULL DEFAULT 1,
                error_message TEXT
            )
        """)
        await db.commit()
    
    async def get_migration_status(self) -> Dict[str, Any]:
        """獲取遷移狀態"""
        try:
            async with aiosqlite.connect(self.database_path) as db:
                await self._ensure_migrations_table(db)
                
                # 獲取已應用的遷移
                cursor = await db.execute("""
                    SELECT version, description, filename, applied_at, 
                           execution_time_ms, success, error_message
                    FROM schema_migrations 
                    ORDER BY version
                """)
                applied_migrations = await cursor.fetchall()
                
                # 掃描可用的遷移檔案
                migration_files = sorted([
                    f for f in self.migrations_dir.glob("*.sql")
                    if re.match(r'^\d{3}_.*\.sql$', f.name)
                ])
                
                available_migrations = []
                for file in migration_files:
                    version = file.name[:3]  # 取前3位數字作為版本號
                    checksum = self._get_file_checksum(file)
                    
                    available_migrations.append({
                        'version': version,
                        'filename': file.name,
                        'file_path': str(file),
                        'checksum': checksum
                    })
                
                # 分析狀態
                applied_versions = {row[0] for row in applied_migrations}
                available_versions = {m['version'] for m in available_migrations}
                
                pending_migrations = available_versions - applied_versions
                unknown_migrations = applied_versions - available_versions
                
                status = {
                    'database_path': self.database_path,
                    'timestamp': datetime.now().isoformat(),
                    'applied_migrations': [
                        {
                            'version': row[0],
                            'description': row[1],
                            'filename': row[2],
                            'applied_at': row[3],
                            'execution_time_ms': row[4],
                            'success': bool(row[5]),
                            'error_message': row[6]
                        }
                        for row in applied_migrations
                    ],
                    'available_migrations': available_migrations,
                    'pending_migrations': sorted(pending_migrations),
                    'unknown_migrations': sorted(unknown_migrations),
                    'total_applied': len(applied_migrations),
                    'total_available': len(available_migrations),
                    'total_pending': len(pending_migrations)
                }
                
                return status
                
        except Exception as e:
            return {
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def apply_migration(self, version: str) -> Dict[str, Any]:
        """應用特定版本的遷移"""
        try:
            # 找到遷移檔案
            migration_file = None
            for file in self.migrations_dir.glob("*.sql"):
                if file.name.startswith(f"{version}_"):
                    migration_file = file
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
                
                # 應用遷移
                start_time = time.time()
                success = True
                error_message = None
                
                try:
                    await db.executescript(sql_content)
                    await db.commit()
                except Exception as e:
                    success = False
                    error_message = str(e)
                    await db.rollback()
                
                execution_time_ms = int((time.time() - start_time) * 1000)
                
                # 記錄遷移狀態
                await db.execute("""
                    INSERT INTO schema_migrations 
                    (version, description, filename, checksum, applied_at, 
                     execution_time_ms, success, error_message)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    version,
                    description,
                    migration_file.name,
                    checksum,
                    datetime.now().isoformat(),
                    execution_time_ms,
                    1 if success else 0,
                    error_message
                ))
                await db.commit()
                
                result = {
                    'success': success,
                    'version': version,
                    'filename': migration_file.name,
                    'description': description,
                    'execution_time_ms': execution_time_ms
                }
                
                if not success:
                    result['error'] = error_message
                
                return result
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def apply_pending_migrations(self) -> Dict[str, Any]:
        """應用所有待處理的遷移"""
        status = await self.get_migration_status()
        
        if 'error' in status:
            return status
        
        pending_migrations = status['pending_migrations']
        
        if not pending_migrations:
            return {
                'success': True,
                'message': '沒有待處理的遷移',
                'applied_count': 0
            }
        
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
    
    async def rollback_migration(self, version: str) -> Dict[str, Any]:
        """回滾特定版本的遷移"""
        # 注意：這個功能需要遷移腳本包含DOWN部分才能完全實現
        # 目前只能標記為已回滾，但不能自動反轉SQL操作
        try:
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
                
                # 標記為已回滾（在實際項目中，這裡應該執行DOWN遷移）
                await db.execute(
                    "DELETE FROM schema_migrations WHERE version = ?",
                    (version,)
                )
                await db.commit()
                
                return {
                    'success': True,
                    'version': version,
                    'filename': migration[1],
                    'message': f'遷移 {version} 已標記為回滾（注意：需要手動清理相關資料庫變更）'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def verify_migrations(self) -> Dict[str, Any]:
        """驗證已應用遷移的完整性"""
        try:
            status = await self.get_migration_status()
            
            if 'error' in status:
                return status
            
            verification_results = []
            
            for applied in status['applied_migrations']:
                version = applied['version']
                recorded_checksum = None
                
                # 找到對應的檔案
                migration_file = None
                for file in self.migrations_dir.glob("*.sql"):
                    if file.name.startswith(f"{version}_"):
                        migration_file = file
                        break
                
                if migration_file:
                    current_checksum = self._get_file_checksum(migration_file)
                    
                    # 從資料庫獲取記錄的校驗和
                    async with aiosqlite.connect(self.database_path) as db:
                        cursor = await db.execute(
                            "SELECT checksum FROM schema_migrations WHERE version = ?",
                            (version,)
                        )
                        result = await cursor.fetchone()
                        if result:
                            recorded_checksum = result[0]
                    
                    verification_results.append({
                        'version': version,
                        'filename': migration_file.name,
                        'checksum_match': current_checksum == recorded_checksum,
                        'current_checksum': current_checksum,
                        'recorded_checksum': recorded_checksum,
                        'file_exists': True
                    })
                else:
                    verification_results.append({
                        'version': version,
                        'filename': applied['filename'],
                        'file_exists': False,
                        'checksum_match': False
                    })
            
            # 統計
            total_verified = len(verification_results)
            checksum_matches = sum(1 for r in verification_results if r.get('checksum_match', False))
            files_missing = sum(1 for r in verification_results if not r['file_exists'])
            
            return {
                'success': True,
                'verification_results': verification_results,
                'total_verified': total_verified,
                'checksum_matches': checksum_matches,
                'files_missing': files_missing,
                'integrity_score': checksum_matches / total_verified if total_verified > 0 else 0
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def print_status(self, status: Dict[str, Any]):
        """輸出遷移狀態"""
        if 'error' in status:
            print(f"{Colors.RED}❌ 錯誤: {status['error']}{Colors.END}")
            return
        
        print(f"{Colors.BOLD}{Colors.BLUE}📊 資料庫遷移狀態{Colors.END}")
        print(f"資料庫路徑: {status['database_path']}")
        print(f"檢查時間: {status['timestamp']}")
        print("=" * 60)
        
        print(f"{Colors.BOLD}統計摘要:{Colors.END}")
        print(f"  已應用遷移: {Colors.GREEN}{status['total_applied']}{Colors.END}")
        print(f"  可用遷移: {Colors.CYAN}{status['total_available']}{Colors.END}")
        print(f"  待處理遷移: {Colors.YELLOW}{status['total_pending']}{Colors.END}")
        
        if status['unknown_migrations']:
            print(f"  未知遷移: {Colors.RED}{len(status['unknown_migrations'])}{Colors.END}")
        
        print()
        
        if status['applied_migrations']:
            print(f"{Colors.BOLD}已應用的遷移:{Colors.END}")
            for migration in status['applied_migrations']:
                success_icon = "✓" if migration['success'] else "✗"
                color = Colors.GREEN if migration['success'] else Colors.RED
                print(f"  {color}{success_icon} {migration['version']} - {migration['description']}{Colors.END}")
                print(f"    檔案: {migration['filename']}")
                print(f"    應用時間: {migration['applied_at']}")
                print(f"    執行時間: {migration['execution_time_ms']}ms")
                if not migration['success'] and migration['error_message']:
                    print(f"    錯誤: {Colors.RED}{migration['error_message']}{Colors.END}")
                print()
        
        if status['pending_migrations']:
            print(f"{Colors.BOLD}待處理的遷移:{Colors.END}")
            for version in status['pending_migrations']:
                print(f"  {Colors.YELLOW}⏳ {version}{Colors.END}")
            print()
        
        if status['unknown_migrations']:
            print(f"{Colors.BOLD}{Colors.RED}未知的遷移 (檔案已刪除):{Colors.END}")
            for version in status['unknown_migrations']:
                print(f"  {Colors.RED}❓ {version}{Colors.END}")

async def main():
    """主函數"""
    parser = argparse.ArgumentParser(description='資料庫遷移管理工具')
    parser.add_argument('--db', default=None, help='資料庫檔案路徑')
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 狀態命令
    subparsers.add_parser('status', help='顯示遷移狀態')
    
    # 應用遷移命令
    apply_parser = subparsers.add_parser('apply', help='應用遷移')
    apply_parser.add_argument('version', nargs='?', help='指定版本號，留空則應用所有待處理遷移')
    
    # 回滾命令
    rollback_parser = subparsers.add_parser('rollback', help='回滾遷移')
    rollback_parser.add_argument('version', help='要回滾的版本號')
    
    # 驗證命令
    subparsers.add_parser('verify', help='驗證遷移完整性')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    manager = MigrationManager(args.db)
    
    try:
        if args.command == 'status':
            status = await manager.get_migration_status()
            manager.print_status(status)
            
        elif args.command == 'apply':
            if args.version:
                result = await manager.apply_migration(args.version)
                if result['success']:
                    print(f"{Colors.GREEN}✓ 遷移 {result['version']} 應用成功{Colors.END}")
                    print(f"  執行時間: {result['execution_time_ms']}ms")
                else:
                    print(f"{Colors.RED}✗ 遷移 {args.version} 應用失敗: {result['error']}{Colors.END}")
            else:
                result = await manager.apply_pending_migrations()
                if result['success']:
                    print(f"{Colors.GREEN}✓ 成功應用 {result['applied_count']} 個遷移{Colors.END}")
                else:
                    print(f"{Colors.YELLOW}⚠ 應用了 {result['applied_count']}/{result['total_pending']} 個遷移{Colors.END}")
                    for res in result['results']:
                        if not res['success']:
                            print(f"{Colors.RED}  ✗ {res.get('version', 'unknown')}: {res.get('error', 'unknown error')}{Colors.END}")
            
        elif args.command == 'rollback':
            result = await manager.rollback_migration(args.version)
            if result['success']:
                print(f"{Colors.GREEN}✓ {result['message']}{Colors.END}")
            else:
                print(f"{Colors.RED}✗ 回滾失敗: {result['error']}{Colors.END}")
                
        elif args.command == 'verify':
            result = await manager.verify_migrations()
            if result['success']:
                print(f"{Colors.BOLD}{Colors.BLUE}🔍 遷移完整性驗證結果{Colors.END}")
                print("=" * 60)
                print(f"總計驗證: {result['total_verified']} 個遷移")
                print(f"校驗和匹配: {Colors.GREEN}{result['checksum_matches']}{Colors.END}")
                print(f"檔案缺失: {Colors.RED}{result['files_missing']}{Colors.END}")
                print(f"完整性評分: {result['integrity_score']:.1%}")
                print()
                
                for verification in result['verification_results']:
                    if verification['file_exists']:
                        if verification['checksum_match']:
                            print(f"  {Colors.GREEN}✓ {verification['version']} - {verification['filename']}{Colors.END}")
                        else:
                            print(f"  {Colors.YELLOW}⚠ {verification['version']} - {verification['filename']} (校驗和不匹配){Colors.END}")
                    else:
                        print(f"  {Colors.RED}✗ {verification['version']} - {verification['filename']} (檔案不存在){Colors.END}")
            else:
                print(f"{Colors.RED}✗ 驗證失敗: {result['error']}{Colors.END}")
        
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}⚠ 操作被使用者中斷{Colors.END}")
        sys.exit(2)
    except Exception as e:
        print(f"\n{Colors.RED}❌ 發生未預期的錯誤: {str(e)}{Colors.END}")
        sys.exit(3)

if __name__ == "__main__":
    asyncio.run(main())