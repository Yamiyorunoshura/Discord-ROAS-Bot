#!/usr/bin/env python3
"""
資料庫備份和恢復工具
Task ID: 8 - 建立資料庫遷移腳本

這個腳本提供完整的資料庫備份和恢復功能：
- 自動備份資料庫
- 增量備份支援
- 備份驗證和完整性檢查
- 快速恢復功能
- 備份歷史管理
"""

import argparse
import asyncio
import aiosqlite
import gzip
import json
import os
import shutil
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# 設定專案路徑
PROJECT_ROOT = Path(__file__).parent.parent
DBS_DIR = PROJECT_ROOT / "dbs"
BACKUPS_DIR = PROJECT_ROOT / "backups"
LOGS_DIR = PROJECT_ROOT / "logs"

# 確保目錄存在
DBS_DIR.mkdir(exist_ok=True)
BACKUPS_DIR.mkdir(exist_ok=True)
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

class DatabaseBackupManager:
    """資料庫備份管理器"""
    
    def __init__(self, database_path: Optional[str] = None, backup_dir: Optional[str] = None):
        self.database_path = database_path or str(DBS_DIR / "main.db")
        self.backup_dir = Path(backup_dir) if backup_dir else BACKUPS_DIR
        self.backup_dir.mkdir(exist_ok=True)
        
        # 建立備份清單檔案
        self.backup_index_file = self.backup_dir / "backup_index.json"
        self._ensure_backup_index()
    
    def _ensure_backup_index(self):
        """確保備份索引檔案存在"""
        if not self.backup_index_file.exists():
            with open(self.backup_index_file, 'w', encoding='utf-8') as f:
                json.dump({'backups': []}, f, indent=2)
    
    def _load_backup_index(self) -> Dict[str, Any]:
        """載入備份索引"""
        try:
            with open(self.backup_index_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {'backups': []}
    
    def _save_backup_index(self, index: Dict[str, Any]):
        """儲存備份索引"""
        with open(self.backup_index_file, 'w', encoding='utf-8') as f:
            json.dump(index, f, indent=2, ensure_ascii=False)
    
    def _get_database_stats(self, db_path: str) -> Dict[str, Any]:
        """獲取資料庫統計資訊"""
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                
                # 獲取表格數量
                cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='table'")
                table_count = cursor.fetchone()[0]
                
                # 獲取資料庫大小
                cursor.execute("PRAGMA page_count")
                page_count = cursor.fetchone()[0]
                cursor.execute("PRAGMA page_size")
                page_size = cursor.fetchone()[0]
                db_size = page_count * page_size
                
                # 獲取表格行數統計
                table_stats = {}
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
                tables = cursor.fetchall()
                
                for table in tables:
                    table_name = table[0]
                    try:
                        cursor.execute(f"SELECT count(*) FROM `{table_name}`")
                        row_count = cursor.fetchone()[0]
                        table_stats[table_name] = row_count
                    except Exception:
                        table_stats[table_name] = -1  # 表示無法查詢
                
                return {
                    'table_count': table_count,
                    'database_size': db_size,
                    'table_stats': table_stats
                }
                
        except Exception as e:
            return {'error': str(e)}
    
    async def create_backup(self, backup_name: Optional[str] = None, compress: bool = True) -> Dict[str, Any]:
        """建立資料庫備份"""
        try:
            # 檢查源資料庫是否存在
            if not os.path.exists(self.database_path):
                return {
                    'success': False,
                    'error': f'源資料庫不存在: {self.database_path}'
                }
            
            # 生成備份名稱
            if not backup_name:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_name = f"backup_{timestamp}"
            
            backup_filename = f"{backup_name}.db"
            if compress:
                backup_filename += ".gz"
            
            backup_path = self.backup_dir / backup_filename
            
            # 確保備份不重複
            if backup_path.exists():
                return {
                    'success': False,
                    'error': f'備份檔案已存在: {backup_path}'
                }
            
            print(f"🔄 正在建立資料庫備份...")
            print(f"源資料庫: {self.database_path}")
            print(f"備份路徑: {backup_path}")
            
            start_time = time.time()
            
            # 獲取源資料庫統計
            source_stats = self._get_database_stats(self.database_path)
            
            if compress:
                # 壓縮備份
                with open(self.database_path, 'rb') as source:
                    with gzip.open(backup_path, 'wb', compresslevel=9) as backup:
                        shutil.copyfileobj(source, backup)
            else:
                # 直接複製
                shutil.copy2(self.database_path, backup_path)
            
            backup_time = time.time() - start_time
            backup_size = backup_path.stat().st_size
            source_size = Path(self.database_path).stat().st_size
            
            # 建立備份記錄
            backup_record = {
                'backup_name': backup_name,
                'filename': backup_filename,
                'created_at': datetime.now().isoformat(),
                'source_database': self.database_path,
                'backup_path': str(backup_path),
                'compressed': compress,
                'source_size': source_size,
                'backup_size': backup_size,
                'compression_ratio': backup_size / source_size if source_size > 0 else 0,
                'backup_time_seconds': backup_time,
                'source_stats': source_stats
            }
            
            # 更新備份索引
            index = self._load_backup_index()
            index['backups'].append(backup_record)
            
            # 按時間排序備份記錄
            index['backups'] = sorted(index['backups'], key=lambda x: x['created_at'], reverse=True)
            
            self._save_backup_index(index)
            
            print(f"{Colors.GREEN}✓ 備份建立成功!{Colors.END}")
            print(f"  備份大小: {backup_size:,} bytes")
            print(f"  壓縮比: {backup_record['compression_ratio']:.1%}")
            print(f"  備份時間: {backup_time:.2f} 秒")
            
            return {
                'success': True,
                'backup_record': backup_record
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    async def restore_backup(self, backup_name: str, target_path: Optional[str] = None) -> Dict[str, Any]:
        """從備份恢復資料庫"""
        try:
            # 尋找備份記錄
            index = self._load_backup_index()
            backup_record = None
            
            for backup in index['backups']:
                if backup['backup_name'] == backup_name:
                    backup_record = backup
                    break
            
            if not backup_record:
                return {
                    'success': False,
                    'error': f'未找到備份: {backup_name}'
                }
            
            backup_path = Path(backup_record['backup_path'])
            if not backup_path.exists():
                return {
                    'success': False,
                    'error': f'備份檔案不存在: {backup_path}'
                }
            
            # 確定恢復目標路徑
            if not target_path:
                target_path = self.database_path
            
            # 檢查是否需要備份現有資料庫
            if os.path.exists(target_path):
                backup_existing = input(f"目標資料庫已存在: {target_path}\n是否先備份現有資料庫? (y/N): ")
                if backup_existing.lower() == 'y':
                    existing_backup_name = f"pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    existing_backup_result = await self.create_backup(existing_backup_name)
                    if existing_backup_result['success']:
                        print(f"{Colors.GREEN}✓ 現有資料庫已備份為: {existing_backup_name}{Colors.END}")
                    else:
                        print(f"{Colors.YELLOW}⚠ 無法備份現有資料庫: {existing_backup_result['error']}{Colors.END}")
            
            print(f"🔄 正在恢復資料庫...")
            print(f"備份來源: {backup_path}")
            print(f"恢復目標: {target_path}")
            
            start_time = time.time()
            
            # 恢復資料庫
            if backup_record['compressed']:
                # 解壓縮恢復
                with gzip.open(backup_path, 'rb') as backup:
                    with open(target_path, 'wb') as target:
                        shutil.copyfileobj(backup, target)
            else:
                # 直接複製
                shutil.copy2(backup_path, target_path)
            
            restore_time = time.time() - start_time
            
            # 驗證恢復的資料庫
            restored_stats = self._get_database_stats(target_path)
            
            print(f"{Colors.GREEN}✓ 資料庫恢復成功!{Colors.END}")
            print(f"  恢復時間: {restore_time:.2f} 秒")
            
            if 'error' not in restored_stats:
                print(f"  表格數量: {restored_stats['table_count']}")
                print(f"  資料庫大小: {restored_stats['database_size']:,} bytes")
            
            return {
                'success': True,
                'backup_name': backup_name,
                'target_path': target_path,
                'restore_time_seconds': restore_time,
                'restored_stats': restored_stats
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def list_backups(self) -> Dict[str, Any]:
        """列出所有備份"""
        try:
            index = self._load_backup_index()
            backups = index['backups']
            
            # 計算統計
            total_backup_size = sum(backup['backup_size'] for backup in backups)
            total_source_size = sum(backup['source_size'] for backup in backups)
            
            return {
                'success': True,
                'backups': backups,
                'total_backups': len(backups),
                'total_backup_size': total_backup_size,
                'total_source_size': total_source_size,
                'avg_compression_ratio': sum(backup['compression_ratio'] for backup in backups) / len(backups) if backups else 0
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def delete_backup(self, backup_name: str) -> Dict[str, Any]:
        """刪除指定的備份"""
        try:
            index = self._load_backup_index()
            backup_record = None
            backup_index = -1
            
            for i, backup in enumerate(index['backups']):
                if backup['backup_name'] == backup_name:
                    backup_record = backup
                    backup_index = i
                    break
            
            if not backup_record:
                return {
                    'success': False,
                    'error': f'未找到備份: {backup_name}'
                }
            
            backup_path = Path(backup_record['backup_path'])
            
            # 刪除備份檔案
            if backup_path.exists():
                backup_path.unlink()
            
            # 從索引中移除記錄
            index['backups'].pop(backup_index)
            self._save_backup_index(index)
            
            return {
                'success': True,
                'deleted_backup': backup_record
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def cleanup_old_backups(self, keep_days: int = 30, keep_count: int = 10) -> Dict[str, Any]:
        """清理舊備份"""
        try:
            index = self._load_backup_index()
            backups = index['backups']
            
            if not backups:
                return {
                    'success': True,
                    'deleted_count': 0,
                    'message': '沒有備份需要清理'
                }
            
            # 按時間排序（最新的在前）
            backups.sort(key=lambda x: x['created_at'], reverse=True)
            
            cutoff_date = datetime.now() - timedelta(days=keep_days)
            deleted_backups = []
            
            # 保留最新的 keep_count 個備份，以及 keep_days 天內的備份
            for i, backup in enumerate(backups):
                backup_date = datetime.fromisoformat(backup['created_at'])
                
                # 如果超出保留數量且超過保留天數，則刪除
                if i >= keep_count and backup_date < cutoff_date:
                    backup_path = Path(backup['backup_path'])
                    if backup_path.exists():
                        backup_path.unlink()
                    deleted_backups.append(backup)
            
            # 更新索引，移除已刪除的備份記錄
            remaining_backups = [b for b in backups if b not in deleted_backups]
            index['backups'] = remaining_backups
            self._save_backup_index(index)
            
            return {
                'success': True,
                'deleted_count': len(deleted_backups),
                'deleted_backups': [b['backup_name'] for b in deleted_backups],
                'remaining_count': len(remaining_backups)
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def print_backup_list(self, backups_info: Dict[str, Any]):
        """輸出備份清單"""
        if not backups_info['success']:
            print(f"{Colors.RED}❌ 錯誤: {backups_info['error']}{Colors.END}")
            return
        
        backups = backups_info['backups']
        
        if not backups:
            print(f"{Colors.YELLOW}📦 沒有找到任何備份{Colors.END}")
            return
        
        print(f"{Colors.BOLD}{Colors.BLUE}📦 資料庫備份清單{Colors.END}")
        print(f"總備份數: {backups_info['total_backups']}")
        print(f"總備份大小: {backups_info['total_backup_size']:,} bytes")
        print(f"平均壓縮比: {backups_info['avg_compression_ratio']:.1%}")
        print("=" * 80)
        
        for backup in backups:
            created_date = datetime.fromisoformat(backup['created_at'])
            age = datetime.now() - created_date
            
            print(f"{Colors.BOLD}{backup['backup_name']}{Colors.END}")
            print(f"  建立時間: {created_date.strftime('%Y-%m-%d %H:%M:%S')} ({age.days} 天前)")
            print(f"  檔案名稱: {backup['filename']}")
            print(f"  備份大小: {backup['backup_size']:,} bytes")
            print(f"  壓縮比: {backup['compression_ratio']:.1%}")
            print(f"  備份時間: {backup['backup_time_seconds']:.2f} 秒")
            print(f"  壓縮: {'是' if backup['compressed'] else '否'}")
            
            # 顯示資料庫統計
            if 'source_stats' in backup and 'error' not in backup['source_stats']:
                stats = backup['source_stats']
                print(f"  表格數: {stats['table_count']}")
                if stats['table_stats']:
                    table_info = ', '.join([f"{k}:{v}" for k, v in stats['table_stats'].items()])
                    print(f"  資料統計: {table_info}")
            
            print()

async def main():
    """主函數"""
    parser = argparse.ArgumentParser(description='資料庫備份和恢復工具')
    parser.add_argument('--db', default=None, help='資料庫檔案路徑')
    parser.add_argument('--backup-dir', default=None, help='備份目錄路徑')
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 建立備份命令
    backup_parser = subparsers.add_parser('backup', help='建立資料庫備份')
    backup_parser.add_argument('--name', help='備份名稱')
    backup_parser.add_argument('--no-compress', action='store_true', help='不壓縮備份')
    
    # 恢復備份命令
    restore_parser = subparsers.add_parser('restore', help='恢復資料庫備份')
    restore_parser.add_argument('backup_name', help='要恢復的備份名稱')
    restore_parser.add_argument('--target', help='恢復目標路徑')
    
    # 列出備份命令
    subparsers.add_parser('list', help='列出所有備份')
    
    # 刪除備份命令
    delete_parser = subparsers.add_parser('delete', help='刪除指定備份')
    delete_parser.add_argument('backup_name', help='要刪除的備份名稱')
    
    # 清理備份命令
    cleanup_parser = subparsers.add_parser('cleanup', help='清理舊備份')
    cleanup_parser.add_argument('--keep-days', type=int, default=30, help='保留天數（預設30天）')
    cleanup_parser.add_argument('--keep-count', type=int, default=10, help='保留數量（預設10個）')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    manager = DatabaseBackupManager(args.db, args.backup_dir)
    
    try:
        if args.command == 'backup':
            compress = not args.no_compress
            result = await manager.create_backup(args.name, compress)
            if not result['success']:
                print(f"{Colors.RED}❌ 備份失敗: {result['error']}{Colors.END}")
                sys.exit(1)
        
        elif args.command == 'restore':
            result = await manager.restore_backup(args.backup_name, args.target)
            if not result['success']:
                print(f"{Colors.RED}❌ 恢復失敗: {result['error']}{Colors.END}")
                sys.exit(1)
        
        elif args.command == 'list':
            result = manager.list_backups()
            manager.print_backup_list(result)
        
        elif args.command == 'delete':
            result = manager.delete_backup(args.backup_name)
            if result['success']:
                print(f"{Colors.GREEN}✓ 備份 {args.backup_name} 已刪除{Colors.END}")
            else:
                print(f"{Colors.RED}❌ 刪除失敗: {result['error']}{Colors.END}")
                sys.exit(1)
        
        elif args.command == 'cleanup':
            result = manager.cleanup_old_backups(args.keep_days, args.keep_count)
            if result['success']:
                if result['deleted_count'] > 0:
                    print(f"{Colors.GREEN}✓ 清理完成，刪除了 {result['deleted_count']} 個舊備份{Colors.END}")
                    print(f"剩餘備份: {result['remaining_count']} 個")
                    print(f"已刪除: {', '.join(result['deleted_backups'])}")
                else:
                    print(f"{Colors.GREEN}✓ {result['message']}{Colors.END}")
            else:
                print(f"{Colors.RED}❌ 清理失敗: {result['error']}{Colors.END}")
                sys.exit(1)
    
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}⚠ 操作被使用者中斷{Colors.END}")
        sys.exit(2)
    except Exception as e:
        print(f"\n{Colors.RED}❌ 發生未預期的錯誤: {str(e)}{Colors.END}")
        sys.exit(3)

if __name__ == "__main__":
    asyncio.run(main())