#!/usr/bin/env python3
# 效能監控工具
# Task ID: 11 - 建立文件和部署準備 - F11-4: 監控維護工具

import asyncio
import argparse
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# 添加項目根目錄到路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database_manager import DatabaseManager
from services.monitoring import MonitoringService, HealthStatus

class PerformanceMonitorTool:
    """效能監控工具"""
    
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
    
    async def monitor_realtime(self, interval=5, duration=60):
        """即時效能監控"""
        print(f"📊 開始即時效能監控")
        print(f"監控間隔: {interval} 秒")
        print(f"監控時長: {duration} 秒")
        print("-" * 80)
        
        start_time = time.time()
        iteration = 0
        
        try:
            while time.time() - start_time < duration:
                iteration += 1
                timestamp = datetime.now().strftime("%H:%M:%S")
                
                # 收集效能指標
                metrics = await self.monitoring_service.collect_all_performance_metrics()
                
                # 顯示關鍵指標
                print(f"[{timestamp}] #{iteration:3d}", end="")
                
                for metric in metrics:
                    status_icon = self._get_status_icon(metric.status)
                    
                    # 格式化數值顯示
                    if metric.unit == "percent":
                        value_str = f"{metric.value:5.1f}%"
                    elif metric.unit == "milliseconds":
                        value_str = f"{metric.value:6.1f}ms"
                    elif metric.unit == "megabytes":
                        value_str = f"{metric.value:6.1f}MB"
                    else:
                        value_str = f"{metric.value:8.2f}{metric.unit}"
                    
                    print(f" | {status_icon}{metric.metric_name[:10]:12} {value_str}", end="")
                
                print()  # 換行
                
                # 等待下一次監控
                await asyncio.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n⏹️  監控已停止")
    
    async def generate_report(self, hours=24, output_format='text'):
        """生成效能報告"""
        print(f"📈 生成效能報告 (最近 {hours} 小時)")
        
        try:
            start_time = datetime.now() - timedelta(hours=hours)
            end_time = datetime.now()
            
            report = await self.monitoring_service.get_performance_report(start_time, end_time)
            
            if output_format == 'json':
                print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
            else:
                self._output_report_text(report)
                
        except Exception as e:
            print(f"❌ 報告生成失敗: {e}")
    
    async def show_metrics_summary(self, component=None):
        """顯示指標摘要"""
        try:
            # 獲取最近1小時的數據
            start_time = datetime.now() - timedelta(hours=1)
            end_time = datetime.now()
            
            report = await self.monitoring_service.get_performance_report(start_time, end_time)
            
            print("📊 效能指標摘要 (最近1小時)")
            print("-" * 80)
            
            if not report.metrics:
                print("沒有找到效能指標數據")
                return
            
            # 按組件和指標分組
            metrics_by_component = {}
            for metric in report.metrics:
                if component and metric.component != component:
                    continue
                    
                if metric.component not in metrics_by_component:
                    metrics_by_component[metric.component] = {}
                
                if metric.metric_name not in metrics_by_component[metric.component]:
                    metrics_by_component[metric.component][metric.metric_name] = []
                
                metrics_by_component[metric.component][metric.metric_name].append(metric)
            
            # 顯示統計信息
            for comp, metric_groups in metrics_by_component.items():
                print(f"\n🔧 {comp.upper()}")
                
                for metric_name, metric_list in metric_groups.items():
                    if not metric_list:
                        continue
                    
                    values = [m.value for m in metric_list]
                    avg_value = sum(values) / len(values)
                    min_value = min(values)
                    max_value = max(values)
                    
                    # 最新狀態
                    latest_metric = max(metric_list, key=lambda x: x.timestamp)
                    status_icon = self._get_status_icon(latest_metric.status)
                    
                    print(f"  {status_icon} {metric_name:20} | "
                          f"平均: {avg_value:8.2f} | "
                          f"最小: {min_value:8.2f} | "
                          f"最大: {max_value:8.2f} | "
                          f"單位: {latest_metric.unit}")
                    
                    # 顯示閾值信息
                    if latest_metric.threshold_warning or latest_metric.threshold_critical:
                        thresholds = []
                        if latest_metric.threshold_warning:
                            thresholds.append(f"警告: {latest_metric.threshold_warning}")
                        if latest_metric.threshold_critical:
                            thresholds.append(f"嚴重: {latest_metric.threshold_critical}")
                        print(f"    閾值: {' | '.join(thresholds)}")
                
        except Exception as e:
            print(f"❌ 指標摘要生成失敗: {e}")
    
    async def check_thresholds(self):
        """檢查閾值違規"""
        print("⚠️  檢查效能閾值違規")
        print("-" * 80)
        
        try:
            # 收集最新指標
            metrics = await self.monitoring_service.collect_all_performance_metrics()
            
            violations = []
            for metric in metrics:
                if metric.status in [HealthStatus.WARNING, HealthStatus.CRITICAL]:
                    violations.append(metric)
            
            if not violations:
                print("✅ 所有效能指標都在正常範圍內")
                return
            
            print(f"發現 {len(violations)} 個閾值違規:")
            
            for metric in violations:
                status_icon = self._get_status_icon(metric.status)
                print(f"{status_icon} {metric.component}:{metric.metric_name}")
                print(f"   當前值: {metric.value} {metric.unit}")
                
                if metric.threshold_warning:
                    print(f"   警告閾值: {metric.threshold_warning} {metric.unit}")
                if metric.threshold_critical:
                    print(f"   嚴重閾值: {metric.threshold_critical} {metric.unit}")
                print()
                
        except Exception as e:
            print(f"❌ 閾值檢查失敗: {e}")
    
    async def collect_single_metric(self, metric_name):
        """收集單個指標"""
        try:
            metrics = await self.monitoring_service.collect_all_performance_metrics()
            
            target_metrics = [m for m in metrics if m.metric_name == metric_name]
            
            if not target_metrics:
                print(f"❌ 找不到指標: {metric_name}")
                return
            
            for metric in target_metrics:
                status_icon = self._get_status_icon(metric.status)
                timestamp = metric.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                
                print(f"{status_icon} {metric.component}:{metric.metric_name}")
                print(f"   值: {metric.value} {metric.unit}")
                print(f"   時間: {timestamp}")
                print(f"   狀態: {metric.status.value}")
                
                if metric.threshold_warning or metric.threshold_critical:
                    thresholds = []
                    if metric.threshold_warning:
                        thresholds.append(f"警告: {metric.threshold_warning}")
                    if metric.threshold_critical:
                        thresholds.append(f"嚴重: {metric.threshold_critical}")
                    print(f"   閾值: {' | '.join(thresholds)}")
                print()
                
        except Exception as e:
            print(f"❌ 指標收集失敗: {e}")
    
    def _output_report_text(self, report):
        """文本格式輸出效能報告"""
        print("\n" + "="*80)
        print("📈 效能監控報告")
        print("="*80)
        
        print(f"報告ID: {report.report_id}")
        print(f"生成時間: {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"時間範圍: {report.period_start.strftime('%Y-%m-%d %H:%M')} ~ "
              f"{report.period_end.strftime('%Y-%m-%d %H:%M')}")
        print(f"總指標數: {len(report.metrics)}")
        
        # 顯示摘要
        if report.summary:
            print(f"\n📊 報告摘要:")
            if 'alert_summary' in report.summary:
                alert_summary = report.summary['alert_summary']
                print(f"  警告數量: {alert_summary.get('warning_count', 0)}")
                print(f"  嚴重數量: {alert_summary.get('critical_count', 0)}")
        
        # 按組件顯示指標
        if report.metrics:
            components = {}
            for metric in report.metrics:
                if metric.component not in components:
                    components[metric.component] = []
                components[metric.component].append(metric)
            
            for component, metrics in components.items():
                print(f"\n🔧 {component.upper()}")
                print("-" * 40)
                
                # 只顯示最近的幾個指標
                recent_metrics = sorted(metrics, key=lambda x: x.timestamp, reverse=True)[:10]
                
                for metric in recent_metrics:
                    status_icon = self._get_status_icon(metric.status)
                    timestamp = metric.timestamp.strftime("%H:%M:%S")
                    print(f"  {status_icon} {timestamp} | {metric.metric_name:20} | "
                          f"{metric.value:8.2f} {metric.unit}")
        
        print("="*80)
    
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
    parser = argparse.ArgumentParser(description="Discord機器人效能監控工具")
    
    # 子命令
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 即時監控
    monitor_parser = subparsers.add_parser('monitor', help='即時效能監控')
    monitor_parser.add_argument('--interval', type=int, default=5, help='監控間隔（秒）')
    monitor_parser.add_argument('--duration', type=int, default=60, help='監控時長（秒）')
    
    # 生成報告
    report_parser = subparsers.add_parser('report', help='生成效能報告')
    report_parser.add_argument('--hours', type=int, default=24, help='報告時間範圍（小時）')
    report_parser.add_argument('--format', choices=['text', 'json'], default='text',
                              help='輸出格式')
    
    # 指標摘要
    summary_parser = subparsers.add_parser('summary', help='顯示指標摘要')
    summary_parser.add_argument('--component', help='特定組件名稱')
    
    # 閾值檢查
    threshold_parser = subparsers.add_parser('thresholds', help='檢查閾值違規')
    
    # 單個指標
    metric_parser = subparsers.add_parser('metric', help='收集單個指標')
    metric_parser.add_argument('name', help='指標名稱')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    tool = PerformanceMonitorTool()
    
    try:
        await tool.initialize()
        
        if args.command == 'monitor':
            await tool.monitor_realtime(args.interval, args.duration)
        elif args.command == 'report':
            await tool.generate_report(args.hours, args.format)
        elif args.command == 'summary':
            await tool.show_metrics_summary(args.component)
        elif args.command == 'thresholds':
            await tool.check_thresholds()
        elif args.command == 'metric':
            await tool.collect_single_metric(args.name)
        
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