#!/usr/bin/env python3
# 自動維護工具
# Task ID: 11 - 建立文件和部署準備 - F11-4: 監控維護工具

import asyncio
import argparse
import json
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

# 添加項目根目錄到路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database_manager import DatabaseManager
from services.monitoring import MonitoringService, MaintenanceType, MaintenanceTask

class MaintenanceTool:
    """自動維護工具"""
    
    def __init__(self):
        self.db_manager = None
        self.monitoring_service = None
    
    async def initialize(self):
        """初始化服務"""
        try:
            self.db_manager = DatabaseManager("data/discord_data.db")
            await self.db_manager.connect()
            
            self.monitoring_service = MonitoringService(self.db_manager)
            await self.monitoring_service.initialize()
            
        except Exception as e:
            print(f"❌ 初始化失敗: {e}")
            sys.exit(1)
    
    async def cleanup(self):
        """清理資源"""
        if self.db_manager:
            await self.db_manager.close()
    
    async def run_log_cleanup(self, dry_run=False):
        """執行日誌清理"""
        print("🧹 執行日誌清理")
        
        if dry_run:
            print("⚠️  預覽模式 - 不會實際刪除文件")
        
        try:
            if dry_run:
                # 模擬清理結果
                result = {
                    'cleaned_files': ['old_log_1.log', 'old_log_2.log'],
                    'total_files': 2,
                    'size_freed_mb': 15.5
                }
                print("✅ 預覽完成 (模擬結果):")
            else:
                # 實際執行清理
                result = await self.monitoring_service._cleanup_logs()
                print("✅ 日誌清理完成:")
            
            print(f"  清理文件數: {result['total_files']}")
            print(f"  釋放空間: {result['size_freed_mb']:.2f} MB")
            
            if result['cleaned_files']:
                print("  清理的文件:")
                for filename in result['cleaned_files']:
                    print(f"    - {filename}")
            
        except Exception as e:
            print(f"❌ 日誌清理失敗: {e}")
    
    async def run_database_optimization(self, dry_run=False):
        """執行資料庫優化"""
        print("🔧 執行資料庫優化")
        
        if dry_run:
            print("⚠️  預覽模式 - 不會實際執行優化")
            print("將執行的操作:")
            print("  - VACUUM (重整資料庫)")
            print("  - ANALYZE (更新統計信息)")
            return
        
        try:
            result = await self.monitoring_service._optimize_database()
            print("✅ 資料庫優化完成:")
            print(f"  VACUUM: {'完成' if result.get('vacuum_completed') else '失敗'}")
            print(f"  ANALYZE: {'完成' if result.get('analyze_completed') else '失敗'}")
            
        except Exception as e:
            print(f"❌ 資料庫優化失敗: {e}")
    
    async def run_backup_management(self, dry_run=False):
        """執行備份管理"""
        print("💾 執行備份管理")
        
        if dry_run:
            print("⚠️  預覽模式 - 不會實際執行備份操作")
            print("將執行的操作:")
            print("  - 創建新備份")
            print("  - 清理過期備份")
            return
        
        try:
            result = await self.monitoring_service._manage_backups()
            print("✅ 備份管理完成:")
            print(f"  備份創建: {'完成' if result.get('backup_created') else '失敗'}")
            print(f"  舊備份清理: {'完成' if result.get('old_backups_cleaned') else '失敗'}")
            
        except Exception as e:
            print(f"❌ 備份管理失敗: {e}")
    
    async def run_cache_cleanup(self, dry_run=False):
        """執行快取清理"""
        print("🗑️  執行快取清理")
        
        if dry_run:
            print("⚠️  預覽模式 - 不會實際清理快取")
            print("將執行的操作:")
            print("  - 清理Redis快取")
            print("  - 清理應用程式快取")
            return
        
        try:
            result = await self.monitoring_service._cleanup_cache()
            print("✅ 快取清理完成:")
            print(f"  快取清理: {'完成' if result.get('cache_cleared') else '失敗'}")
            
        except Exception as e:
            print(f"❌ 快取清理失敗: {e}")
    
    async def run_all_maintenance(self, dry_run=False):
        """執行所有維護任務"""
        print("🔄 執行完整維護流程")
        print("="*60)
        
        maintenance_tasks = [
            ("日誌清理", self.run_log_cleanup),
            ("資料庫優化", self.run_database_optimization),
            ("備份管理", self.run_backup_management),
            ("快取清理", self.run_cache_cleanup)
        ]
        
        results = []
        
        for task_name, task_func in maintenance_tasks:
            print(f"\n📋 {task_name}")
            print("-" * 40)
            
            try:
                start_time = datetime.now()
                await task_func(dry_run)
                duration = datetime.now() - start_time
                
                results.append({
                    'task': task_name,
                    'status': 'success',
                    'duration': duration.total_seconds()
                })
                
            except Exception as e:
                duration = datetime.now() - start_time
                print(f"❌ {task_name}失敗: {e}")
                
                results.append({
                    'task': task_name,
                    'status': 'failed',
                    'error': str(e),
                    'duration': duration.total_seconds()
                })
        
        # 顯示總結
        print("\n" + "="*60)
        print("📊 維護任務總結")
        print("="*60)
        
        total_duration = sum(r['duration'] for r in results)
        success_count = len([r for r in results if r['status'] == 'success'])
        failed_count = len([r for r in results if r['status'] == 'failed'])
        
        print(f"總任務數: {len(results)}")
        print(f"成功: {success_count} ✅")
        print(f"失敗: {failed_count} ❌")
        print(f"總耗時: {total_duration:.2f} 秒")
        
        if failed_count > 0:
            print("\n❌ 失敗的任務:")
            for result in results:
                if result['status'] == 'failed':
                    print(f"  - {result['task']}: {result['error']}")
    
    async def schedule_maintenance_task(self, task_type, title, description, schedule_time):
        """調度維護任務"""
        try:
            # 解析任務類型
            try:
                maintenance_type = MaintenanceType(task_type)
            except ValueError:
                print(f"❌ 不支持的任務類型: {task_type}")
                print(f"支持的類型: {[t.value for t in MaintenanceType]}")
                return
            
            # 解析調度時間
            if schedule_time == 'now':
                scheduled_at = datetime.now()
            else:
                try:
                    scheduled_at = datetime.fromisoformat(schedule_time)
                except ValueError:
                    print(f"❌ 無效的時間格式: {schedule_time}")
                    print("請使用 'now' 或 ISO格式時間 (例如: 2024-01-01T10:00:00)")
                    return
            
            # 創建維護任務
            task = MaintenanceTask(
                task_id=str(uuid.uuid4()),
                task_type=maintenance_type,
                title=title,
                description=description,
                scheduled_at=scheduled_at
            )
            
            # 如果是立即執行
            if schedule_time == 'now':
                print(f"🚀 立即執行維護任務: {title}")
                await self.monitoring_service._execute_maintenance_task(task)
                print("✅ 任務執行完成")
            else:
                # 儲存任務到資料庫（實際系統中會有調度器處理）
                await self.db_manager.execute("""
                    INSERT INTO monitoring_maintenance_tasks 
                    (task_id, task_type, title, description, scheduled_at, status)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    task.task_id,
                    task.task_type.value,
                    task.title,
                    task.description,
                    task.scheduled_at,
                    'scheduled'
                ))
                
                print(f"📅 維護任務已調度:")
                print(f"  任務ID: {task.task_id}")
                print(f"  類型: {task.task_type.value}")
                print(f"  標題: {task.title}")
                print(f"  調度時間: {task.scheduled_at.strftime('%Y-%m-%d %H:%M:%S')}")
                
        except Exception as e:
            print(f"❌ 任務調度失敗: {e}")
    
    async def list_scheduled_tasks(self):
        """列出已調度的維護任務"""
        try:
            tasks = await self.db_manager.fetchall("""
                SELECT task_id, task_type, title, description, scheduled_at, 
                       executed_at, completed_at, status, error_message
                FROM monitoring_maintenance_tasks
                WHERE status IN ('scheduled', 'running')
                ORDER BY scheduled_at
            """)
            
            if not tasks:
                print("📋 沒有已調度的維護任務")
                return
            
            print("📋 已調度的維護任務")
            print("-" * 80)
            
            for task in tasks:
                task_id, task_type, title, description, scheduled_at, executed_at, completed_at, status, error = task
                
                status_icon = {
                    'scheduled': '⏰',
                    'running': '🔄',
                    'completed': '✅',
                    'failed': '❌'
                }.get(status, '❓')
                
                print(f"{status_icon} {title}")
                print(f"   ID: {task_id}")
                print(f"   類型: {task_type}")
                print(f"   狀態: {status}")
                print(f"   調度時間: {scheduled_at}")
                
                if executed_at:
                    print(f"   執行時間: {executed_at}")
                if completed_at:
                    print(f"   完成時間: {completed_at}")
                if error:
                    print(f"   錯誤: {error}")
                
                print(f"   描述: {description}")
                print()
                
        except Exception as e:
            print(f"❌ 獲取任務列表失敗: {e}")
    
    async def show_maintenance_history(self, days=7):
        """顯示維護歷史"""
        try:
            start_date = datetime.now() - timedelta(days=days)
            
            tasks = await self.db_manager.fetchall("""
                SELECT task_id, task_type, title, scheduled_at, executed_at, 
                       completed_at, status, result, error_message
                FROM monitoring_maintenance_tasks
                WHERE scheduled_at >= ?
                ORDER BY scheduled_at DESC
            """, (start_date,))
            
            if not tasks:
                print(f"📊 最近 {days} 天沒有維護任務記錄")
                return
            
            print(f"📊 維護任務歷史 (最近 {days} 天)")
            print("-" * 80)
            
            for task in tasks:
                task_id, task_type, title, scheduled_at, executed_at, completed_at, status, result, error = task
                
                status_icon = {
                    'scheduled': '⏰',
                    'running': '🔄',
                    'completed': '✅',
                    'failed': '❌'
                }.get(status, '❓')
                
                scheduled_time = datetime.fromisoformat(scheduled_at).strftime('%m-%d %H:%M')
                
                print(f"{status_icon} {scheduled_time} | {task_type:15} | {title}")
                
                if status == 'completed' and executed_at and completed_at:
                    start = datetime.fromisoformat(executed_at)
                    end = datetime.fromisoformat(completed_at)
                    duration = (end - start).total_seconds()
                    print(f"    耗時: {duration:.2f}秒")
                
                if error:
                    print(f"    錯誤: {error}")
                
                if result:
                    try:
                        result_data = json.loads(result)
                        if isinstance(result_data, dict):
                            for key, value in result_data.items():
                                print(f"    {key}: {value}")
                    except:
                        pass
                
                print()
                
        except Exception as e:
            print(f"❌ 獲取維護歷史失敗: {e}")

async def main():
    """主函數"""
    parser = argparse.ArgumentParser(description="Discord機器人自動維護工具")
    
    # 子命令
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 日誌清理
    logs_parser = subparsers.add_parser('logs', help='執行日誌清理')
    logs_parser.add_argument('--dry-run', action='store_true', help='預覽模式')
    
    # 資料庫優化
    db_parser = subparsers.add_parser('database', help='執行資料庫優化')
    db_parser.add_argument('--dry-run', action='store_true', help='預覽模式')
    
    # 備份管理
    backup_parser = subparsers.add_parser('backup', help='執行備份管理')
    backup_parser.add_argument('--dry-run', action='store_true', help='預覽模式')
    
    # 快取清理
    cache_parser = subparsers.add_parser('cache', help='執行快取清理')
    cache_parser.add_argument('--dry-run', action='store_true', help='預覽模式')
    
    # 全部維護
    all_parser = subparsers.add_parser('all', help='執行所有維護任務')
    all_parser.add_argument('--dry-run', action='store_true', help='預覽模式')
    
    # 調度任務
    schedule_parser = subparsers.add_parser('schedule', help='調度維護任務')
    schedule_parser.add_argument('type', choices=[t.value for t in MaintenanceType],
                                help='任務類型')
    schedule_parser.add_argument('title', help='任務標題')
    schedule_parser.add_argument('description', help='任務描述')
    schedule_parser.add_argument('time', help='調度時間 (now 或 ISO格式)')
    
    # 任務列表
    list_parser = subparsers.add_parser('list', help='列出已調度的任務')
    
    # 維護歷史
    history_parser = subparsers.add_parser('history', help='顯示維護歷史')
    history_parser.add_argument('--days', type=int, default=7, help='歷史天數')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    tool = MaintenanceTool()
    
    try:
        await tool.initialize()
        
        if args.command == 'logs':
            await tool.run_log_cleanup(args.dry_run)
        elif args.command == 'database':
            await tool.run_database_optimization(args.dry_run)
        elif args.command == 'backup':
            await tool.run_backup_management(args.dry_run)
        elif args.command == 'cache':
            await tool.run_cache_cleanup(args.dry_run)
        elif args.command == 'all':
            await tool.run_all_maintenance(args.dry_run)
        elif args.command == 'schedule':
            await tool.schedule_maintenance_task(args.type, args.title, 
                                                args.description, args.time)
        elif args.command == 'list':
            await tool.list_scheduled_tasks()
        elif args.command == 'history':
            await tool.show_maintenance_history(args.days)
        
    except KeyboardInterrupt:
        print("\n⏹️  操作已取消")
        return 130
    except Exception as e:
        print(f"❌ 執行錯誤: {e}")
        return 1
    finally:
        await tool.cleanup()
    
    return 0

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        sys.exit(130)