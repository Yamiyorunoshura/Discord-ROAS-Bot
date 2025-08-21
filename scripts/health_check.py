#!/usr/bin/env python3
# 系統健康檢查工具
# Task ID: 11 - 建立文件和部署準備 - F11-4: 監控維護工具

import asyncio
import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 添加項目根目錄到路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database_manager import DatabaseManager
from services.monitoring import MonitoringService, HealthStatus

class HealthCheckTool:
    """健康檢查工具"""
    
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
    
    async def run_full_check(self, output_format='text'):
        """執行完整的系統健康檢查"""
        print("🔍 執行完整系統健康檢查...")
        start_time = datetime.now()
        
        try:
            health = await self.monitoring_service.perform_full_health_check()
            duration = datetime.now() - start_time
            
            if output_format == 'json':
                self._output_json(health)
            else:
                self._output_text(health, duration)
            
            # 返回適當的退出碼
            if health.overall_status == HealthStatus.CRITICAL:
                return 2
            elif health.overall_status == HealthStatus.WARNING:
                return 1
            else:
                return 0
                
        except Exception as e:
            print(f"❌ 健康檢查失敗: {e}")
            return 3
    
    async def run_component_check(self, component, output_format='text'):
        """檢查特定組件"""
        print(f"🔍 檢查組件: {component}")
        
        try:
            # 執行完整檢查然後過濾
            health = await self.monitoring_service.perform_full_health_check()
            
            # 找到指定組件的結果
            component_result = None
            for result in health.components:
                if result.component == component:
                    component_result = result
                    break
            
            if not component_result:
                print(f"❌ 找不到組件: {component}")
                return 3
            
            if output_format == 'json':
                print(json.dumps(component_result.to_dict(), indent=2, ensure_ascii=False))
            else:
                self._output_component_text(component_result)
            
            # 返回退出碼
            if component_result.status == HealthStatus.CRITICAL:
                return 2
            elif component_result.status == HealthStatus.WARNING:
                return 1
            else:
                return 0
                
        except Exception as e:
            print(f"❌ 組件檢查失敗: {e}")
            return 3
    
    async def show_health_history(self, component=None, hours=24):
        """顯示健康檢查歷史"""
        try:
            history = await self.monitoring_service.get_health_history(component, hours)
            
            if not history:
                print("📊 沒有找到健康檢查歷史記錄")
                return
            
            print(f"📊 健康檢查歷史 (最近 {hours} 小時)")
            if component:
                print(f"組件: {component}")
            print("-" * 80)
            
            for result in history:
                status_icon = self._get_status_icon(result.status)
                timestamp = result.checked_at.strftime("%Y-%m-%d %H:%M:%S")
                print(f"{status_icon} {timestamp} | {result.component:15} | "
                      f"{result.response_time_ms:6.1f}ms | {result.message}")
                
        except Exception as e:
            print(f"❌ 獲取歷史記錄失敗: {e}")
    
    async def show_performance_metrics(self, hours=1):
        """顯示效能指標"""
        try:
            start_time = datetime.now() - timedelta(hours=hours)
            end_time = datetime.now()
            
            report = await self.monitoring_service.get_performance_report(start_time, end_time)
            
            print(f"📈 效能指標報告 (最近 {hours} 小時)")
            print(f"時間範圍: {start_time.strftime('%Y-%m-%d %H:%M')} ~ {end_time.strftime('%Y-%m-%d %H:%M')}")
            print("-" * 80)
            
            # 按組件分組顯示
            components = {}
            for metric in report.metrics:
                if metric.component not in components:
                    components[metric.component] = []
                components[metric.component].append(metric)
            
            for component, metrics in components.items():
                print(f"\n🔧 {component.upper()}")
                for metric in metrics[-5:]:  # 顯示最近5個指標
                    status_icon = self._get_status_icon(metric.status)
                    timestamp = metric.timestamp.strftime("%H:%M:%S")
                    print(f"  {status_icon} {timestamp} | {metric.metric_name:20} | "
                          f"{metric.value:8.2f} {metric.unit}")
                
        except Exception as e:
            print(f"❌ 獲取效能指標失敗: {e}")
    
    async def cleanup_old_data(self):
        """清理過期數據"""
        print("🧹 清理過期監控數據...")
        
        try:
            result = await self.monitoring_service.cleanup_old_data()
            
            print("✅ 數據清理完成:")
            print(f"  - 健康檢查記錄: {result.get('health_checks_deleted', 0)} 條")
            print(f"  - 效能指標: {result.get('metrics_deleted', 0)} 條")
            print(f"  - 警報記錄: {result.get('alerts_deleted', 0)} 條")
            print(f"  - 維護任務: {result.get('maintenance_tasks_deleted', 0)} 條")
            
        except Exception as e:
            print(f"❌ 數據清理失敗: {e}")
    
    def _output_text(self, health, duration):
        """文本格式輸出完整健康檢查結果"""
        print("\n" + "="*80)
        print("🏥 系統健康檢查報告")
        print("="*80)
        
        # 整體狀態
        overall_icon = self._get_status_icon(health.overall_status)
        print(f"整體狀態: {overall_icon} {health.overall_status.value.upper()}")
        print(f"檢查時間: {health.checked_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"掃描耗時: {health.scan_duration_ms:.2f} ms")
        print(f"檢查耗時: {duration.total_seconds():.2f} 秒")
        
        # 統計摘要
        print(f"\n📊 檢查統計:")
        print(f"  總檢查項目: {health.total_checks}")
        print(f"  正常: {health.healthy_count} ✅")
        print(f"  警告: {health.warning_count} ⚠️")
        print(f"  嚴重: {health.critical_count} ❌")
        
        # 組件詳情
        print(f"\n🔍 組件檢查詳情:")
        print("-" * 80)
        
        for result in sorted(health.components, key=lambda x: (x.status.value, x.component)):
            status_icon = self._get_status_icon(result.status)
            print(f"{status_icon} {result.component:15} | "
                  f"{result.response_time_ms:6.1f}ms | {result.message}")
            
            # 顯示詳細信息（如果有）
            if result.details:
                for key, value in result.details.items():
                    if isinstance(value, (int, float)):
                        print(f"    {key}: {value}")
                    elif isinstance(value, list):
                        print(f"    {key}: {', '.join(map(str, value))}")
        
        print("="*80)
    
    def _output_component_text(self, result):
        """文本格式輸出單個組件檢查結果"""
        status_icon = self._get_status_icon(result.status)
        print(f"\n{status_icon} 組件: {result.component}")
        print(f"狀態: {result.status.value.upper()}")
        print(f"訊息: {result.message}")
        print(f"響應時間: {result.response_time_ms:.2f} ms")
        print(f"檢查時間: {result.checked_at.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if result.details:
            print("詳細信息:")
            for key, value in result.details.items():
                print(f"  {key}: {value}")
    
    def _output_json(self, health):
        """JSON格式輸出"""
        print(json.dumps(health.to_dict(), indent=2, ensure_ascii=False))
    
    def _get_status_icon(self, status):
        """獲取狀態圖標"""
        icons = {
            HealthStatus.HEALTHY: "✅",
            HealthStatus.WARNING: "⚠️",
            HealthStatus.CRITICAL: "❌",
            HealthStatus.UNKNOWN: "❓"
        }
        return icons.get(status, "❓")

async def main():
    """主函數"""
    parser = argparse.ArgumentParser(description="Discord機器人系統健康檢查工具")
    
    # 子命令
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 完整檢查
    check_parser = subparsers.add_parser('check', help='執行完整系統健康檢查')
    check_parser.add_argument('--format', choices=['text', 'json'], default='text',
                             help='輸出格式')
    
    # 組件檢查
    component_parser = subparsers.add_parser('component', help='檢查特定組件')
    component_parser.add_argument('name', help='組件名稱')
    component_parser.add_argument('--format', choices=['text', 'json'], default='text',
                                 help='輸出格式')
    
    # 歷史記錄
    history_parser = subparsers.add_parser('history', help='顯示健康檢查歷史')
    history_parser.add_argument('--component', help='特定組件名稱')
    history_parser.add_argument('--hours', type=int, default=24, help='歷史小時數')
    
    # 效能指標
    metrics_parser = subparsers.add_parser('metrics', help='顯示效能指標')
    metrics_parser.add_argument('--hours', type=int, default=1, help='時間範圍（小時）')
    
    # 數據清理
    cleanup_parser = subparsers.add_parser('cleanup', help='清理過期監控數據')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    tool = HealthCheckTool()
    exit_code = 0
    
    try:
        await tool.initialize()
        
        if args.command == 'check':
            exit_code = await tool.run_full_check(args.format)
        elif args.command == 'component':
            exit_code = await tool.run_component_check(args.name, args.format)
        elif args.command == 'history':
            await tool.show_health_history(args.component, args.hours)
        elif args.command == 'metrics':
            await tool.show_performance_metrics(args.hours)
        elif args.command == 'cleanup':
            await tool.cleanup_old_data()
        
    except KeyboardInterrupt:
        print("\n⏹️  操作已取消")
        exit_code = 130
    except Exception as e:
        print(f"❌ 執行錯誤: {e}")
        exit_code = 1
    finally:
        await tool.cleanup()
    
    return exit_code

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        sys.exit(130)