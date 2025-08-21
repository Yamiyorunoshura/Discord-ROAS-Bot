#!/usr/bin/env python3
# 監控儀表板報告生成工具
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

class DashboardTool:
    """監控儀表板工具"""
    
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
    
    async def generate_dashboard_report(self, output_file=None):
        """生成儀表板HTML報告"""
        try:
            print("📊 生成監控儀表板報告...")
            
            # 收集數據
            current_health = await self.monitoring_service.perform_full_health_check()
            
            # 獲取過去24小時的健康檢查歷史
            health_history = await self.monitoring_service.get_health_history(hours=24)
            
            # 獲取過去24小時的效能報告
            start_time = datetime.now() - timedelta(hours=24)
            performance_report = await self.monitoring_service.get_performance_report(
                start_time, datetime.now())
            
            # 獲取維護任務歷史
            maintenance_history = await self._get_recent_maintenance_tasks()
            
            # 生成HTML報告
            html_content = self._generate_html_report(
                current_health, health_history, performance_report, maintenance_history)
            
            # 輸出報告
            if output_file:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                print(f"✅ 儀表板報告已生成: {output_file}")
            else:
                # 輸出到控制台（簡化版本）
                self._print_dashboard_summary(current_health, health_history, 
                                            performance_report, maintenance_history)
                
        except Exception as e:
            print(f"❌ 儀表板報告生成失敗: {e}")
    
    async def generate_json_report(self):
        """生成JSON格式的監控報告"""
        try:
            print("📊 生成JSON監控報告...")
            
            # 收集所有數據
            current_health = await self.monitoring_service.perform_full_health_check()
            health_history = await self.monitoring_service.get_health_history(hours=24)
            
            start_time = datetime.now() - timedelta(hours=24)
            performance_report = await self.monitoring_service.get_performance_report(
                start_time, datetime.now())
            
            maintenance_history = await self._get_recent_maintenance_tasks()
            
            # 構建JSON報告
            report = {
                'generated_at': datetime.now().isoformat(),
                'report_type': 'dashboard_summary',
                'current_health': current_health.to_dict(),
                'health_history': [h.to_dict() for h in health_history],
                'performance_report': performance_report.to_dict(),
                'maintenance_history': maintenance_history,
                'summary': {
                    'overall_status': current_health.overall_status.value,
                    'total_components': current_health.total_checks,
                    'healthy_components': current_health.healthy_count,
                    'warning_components': current_health.warning_count,
                    'critical_components': current_health.critical_count,
                    'scan_duration_ms': current_health.scan_duration_ms,
                    'performance_metrics_count': len(performance_report.metrics),
                    'maintenance_tasks_count': len(maintenance_history)
                }
            }
            
            print(json.dumps(report, indent=2, ensure_ascii=False))
            
        except Exception as e:
            print(f"❌ JSON報告生成失敗: {e}")
    
    async def show_system_overview(self):
        """顯示系統概覽"""
        try:
            print("🖥️  系統監控概覽")
            print("="*80)
            
            # 當前健康狀態
            health = await self.monitoring_service.perform_full_health_check()
            
            overall_icon = self._get_status_icon(health.overall_status)
            print(f"系統整體狀態: {overall_icon} {health.overall_status.value.upper()}")
            print(f"檢查時間: {health.checked_at.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"掃描耗時: {health.scan_duration_ms:.2f} ms")
            
            # 組件狀態統計
            print(f"\n📊 組件狀態統計:")
            print(f"  正常: {health.healthy_count:2d} ✅")
            print(f"  警告: {health.warning_count:2d} ⚠️")
            print(f"  嚴重: {health.critical_count:2d} ❌")
            print(f"  總計: {health.total_checks:2d} 🔍")
            
            # 關鍵組件狀態
            print(f"\n🔧 關鍵組件狀態:")
            critical_components = ['database', 'discord_api', 'memory', 'disk_space']
            
            for result in health.components:
                if result.component in critical_components:
                    status_icon = self._get_status_icon(result.status)
                    print(f"  {status_icon} {result.component:15} | "
                          f"{result.response_time_ms:6.1f}ms | {result.message}")
            
            # 最近效能指標
            print(f"\n📈 最近效能指標:")
            metrics = await self.monitoring_service.collect_all_performance_metrics()
            
            for metric in metrics[:5]:  # 顯示前5個指標
                status_icon = self._get_status_icon(metric.status)
                print(f"  {status_icon} {metric.metric_name:20} | "
                      f"{metric.value:8.2f} {metric.unit}")
            
            # 近期維護任務
            maintenance_tasks = await self._get_recent_maintenance_tasks(days=1)
            if maintenance_tasks:
                print(f"\n🔧 近期維護任務:")
                for task in maintenance_tasks[-3:]:  # 顯示最近3個任務
                    status_icon = "✅" if task['status'] == 'completed' else "❌"
                    scheduled_time = datetime.fromisoformat(task['scheduled_at']).strftime('%H:%M')
                    print(f"  {status_icon} {scheduled_time} | {task['task_type']:15} | {task['title']}")
            
        except Exception as e:
            print(f"❌ 系統概覽生成失敗: {e}")
    
    async def show_alert_summary(self, hours=24):
        """顯示警報摘要"""
        try:
            print(f"🚨 警報摘要 (最近 {hours} 小時)")
            print("-"*60)
            
            start_time = datetime.now() - timedelta(hours=hours)
            
            # 獲取警報記錄
            alerts = await self.db_manager.fetchall("""
                SELECT alert_id, level, title, message, component, created_at, 
                       resolved_at, metadata
                FROM monitoring_alerts
                WHERE created_at >= ?
                ORDER BY created_at DESC
            """, (start_time,))
            
            if not alerts:
                print("✅ 沒有警報記錄")
                return
            
            # 統計警報
            alert_stats = {'info': 0, 'warning': 0, 'error': 0, 'critical': 0}
            unresolved_count = 0
            
            for alert in alerts:
                level = alert[1]
                resolved_at = alert[6]
                
                alert_stats[level] = alert_stats.get(level, 0) + 1
                if not resolved_at:
                    unresolved_count += 1
            
            print(f"📊 警報統計:")
            print(f"  總計: {len(alerts)}")
            print(f"  未解決: {unresolved_count}")
            print(f"  嚴重: {alert_stats.get('critical', 0)} ❌")
            print(f"  錯誤: {alert_stats.get('error', 0)} 🔴")
            print(f"  警告: {alert_stats.get('warning', 0)} ⚠️")
            print(f"  信息: {alert_stats.get('info', 0)} ℹ️")
            
            # 顯示最近的警報
            print(f"\n🔍 最近警報詳情:")
            
            for alert in alerts[:10]:  # 顯示最近10個警報
                alert_id, level, title, message, component, created_at, resolved_at, metadata = alert
                
                level_icon = {
                    'info': 'ℹ️',
                    'warning': '⚠️',
                    'error': '🔴',
                    'critical': '❌'
                }.get(level, '❓')
                
                created_time = datetime.fromisoformat(created_at).strftime('%m-%d %H:%M')
                status = "已解決" if resolved_at else "未解決"
                
                print(f"  {level_icon} {created_time} | {component:12} | {title}")
                print(f"      狀態: {status} | 訊息: {message}")
                
        except Exception as e:
            print(f"❌ 警報摘要生成失敗: {e}")
    
    async def _get_recent_maintenance_tasks(self, days=7):
        """獲取近期維護任務"""
        try:
            start_date = datetime.now() - timedelta(days=days)
            
            tasks = await self.db_manager.fetchall("""
                SELECT task_id, task_type, title, description, scheduled_at, 
                       executed_at, completed_at, status, result, error_message
                FROM monitoring_maintenance_tasks
                WHERE scheduled_at >= ?
                ORDER BY scheduled_at DESC
            """, (start_date,))
            
            return [{
                'task_id': task[0],
                'task_type': task[1],
                'title': task[2],
                'description': task[3],
                'scheduled_at': task[4],
                'executed_at': task[5],
                'completed_at': task[6],
                'status': task[7],
                'result': task[8],
                'error_message': task[9]
            } for task in tasks]
            
        except Exception as e:
            print(f"❌ 獲取維護任務失敗: {e}")
            return []
    
    def _generate_html_report(self, current_health, health_history, 
                            performance_report, maintenance_history):
        """生成HTML報告"""
        # 簡化的HTML報告模板
        html_template = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Discord機器人監控儀表板</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        .card { background: white; padding: 20px; margin: 20px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .header { text-align: center; color: #333; }
        .status-healthy { color: #28a745; }
        .status-warning { color: #ffc107; }
        .status-critical { color: #dc3545; }
        .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
        .metric-item { padding: 10px; border-left: 4px solid #007bff; background: #f8f9fa; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 8px 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #f8f9fa; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🖥️ Discord機器人監控儀表板</h1>
            <p>生成時間: {generated_time}</p>
        </div>
        
        <div class="card">
            <h2>🏥 系統健康狀態</h2>
            <div class="metrics-grid">
                <div class="metric-item">
                    <h3>整體狀態</h3>
                    <p class="status-{overall_status_class}">{overall_status}</p>
                </div>
                <div class="metric-item">
                    <h3>組件統計</h3>
                    <p>正常: {healthy_count} | 警告: {warning_count} | 嚴重: {critical_count}</p>
                </div>
                <div class="metric-item">
                    <h3>掃描資訊</h3>
                    <p>總檢查: {total_checks} | 耗時: {scan_duration:.2f}ms</p>
                </div>
            </div>
            
            <h3>組件詳情</h3>
            <table>
                <thead>
                    <tr><th>組件</th><th>狀態</th><th>響應時間</th><th>訊息</th></tr>
                </thead>
                <tbody>
                    {component_rows}
                </tbody>
            </table>
        </div>
        
        <div class="card">
            <h2>📈 效能指標</h2>
            <p>監控期間: {performance_period}</p>
            <p>總指標數: {metrics_count}</p>
            
            <h3>最近指標</h3>
            <table>
                <thead>
                    <tr><th>時間</th><th>組件</th><th>指標</th><th>數值</th><th>狀態</th></tr>
                </thead>
                <tbody>
                    {metrics_rows}
                </tbody>
            </table>
        </div>
        
        <div class="card">
            <h2>🔧 維護任務</h2>
            <p>近期任務數: {maintenance_count}</p>
            
            <table>
                <thead>
                    <tr><th>時間</th><th>類型</th><th>標題</th><th>狀態</th></tr>
                </thead>
                <tbody>
                    {maintenance_rows}
                </tbody>
            </table>
        </div>
        
        <div class="card">
            <h2>📊 健康趨勢</h2>
            <p>過去24小時健康檢查: {health_history_count} 次</p>
            <p>最後更新: {last_check_time}</p>
        </div>
    </div>
</body>
</html>
"""
        
        # 填充數據
        overall_status_class = current_health.overall_status.value.lower()
        
        # 組件行
        component_rows = ""
        for component in current_health.components:
            status_class = f"status-{component.status.value}"
            component_rows += f"""
                <tr>
                    <td>{component.component}</td>
                    <td><span class="{status_class}">{component.status.value}</span></td>
                    <td>{component.response_time_ms:.2f}ms</td>
                    <td>{component.message}</td>
                </tr>
            """
        
        # 效能指標行
        metrics_rows = ""
        for metric in performance_report.metrics[-10:]:  # 最近10個指標
            status_class = f"status-{metric.status.value}"
            timestamp = metric.timestamp.strftime('%H:%M:%S')
            metrics_rows += f"""
                <tr>
                    <td>{timestamp}</td>
                    <td>{metric.component}</td>
                    <td>{metric.metric_name}</td>
                    <td>{metric.value:.2f} {metric.unit}</td>
                    <td><span class="{status_class}">{metric.status.value}</span></td>
                </tr>
            """
        
        # 維護任務行
        maintenance_rows = ""
        for task in maintenance_history[-10:]:  # 最近10個任務
            scheduled_time = datetime.fromisoformat(task['scheduled_at']).strftime('%m-%d %H:%M')
            maintenance_rows += f"""
                <tr>
                    <td>{scheduled_time}</td>
                    <td>{task['task_type']}</td>
                    <td>{task['title']}</td>
                    <td>{task['status']}</td>
                </tr>
            """
        
        return html_template.format(
            generated_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            overall_status=current_health.overall_status.value.upper(),
            overall_status_class=overall_status_class,
            healthy_count=current_health.healthy_count,
            warning_count=current_health.warning_count,
            critical_count=current_health.critical_count,
            total_checks=current_health.total_checks,
            scan_duration=current_health.scan_duration_ms,
            component_rows=component_rows,
            performance_period=f"{performance_report.period_start.strftime('%m-%d %H:%M')} ~ {performance_report.period_end.strftime('%m-%d %H:%M')}",
            metrics_count=len(performance_report.metrics),
            metrics_rows=metrics_rows,
            maintenance_count=len(maintenance_history),
            maintenance_rows=maintenance_rows,
            health_history_count=len(health_history),
            last_check_time=current_health.checked_at.strftime('%Y-%m-%d %H:%M:%S')
        )
    
    def _print_dashboard_summary(self, current_health, health_history, 
                               performance_report, maintenance_history):
        """控制台輸出儀表板摘要"""
        print("\n" + "="*80)
        print("🖥️  監控儀表板摘要")
        print("="*80)
        
        # 系統狀態
        overall_icon = self._get_status_icon(current_health.overall_status)
        print(f"系統狀態: {overall_icon} {current_health.overall_status.value.upper()}")
        print(f"檢查時間: {current_health.checked_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"組件統計: 正常 {current_health.healthy_count} | "
              f"警告 {current_health.warning_count} | 嚴重 {current_health.critical_count}")
        
        # 效能摘要
        print(f"\n📈 效能摘要 ({performance_report.period_start.strftime('%m-%d %H:%M')} ~ "
              f"{performance_report.period_end.strftime('%m-%d %H:%M')}):")
        print(f"總指標數: {len(performance_report.metrics)}")
        
        if performance_report.summary:
            alert_summary = performance_report.summary.get('alert_summary', {})
            print(f"警告指標: {alert_summary.get('warning_count', 0)}")
            print(f"嚴重指標: {alert_summary.get('critical_count', 0)}")
        
        # 維護摘要
        print(f"\n🔧 維護摘要:")
        print(f"近期任務: {len(maintenance_history)}")
        
        completed_tasks = [t for t in maintenance_history if t['status'] == 'completed']
        failed_tasks = [t for t in maintenance_history if t['status'] == 'failed']
        
        print(f"已完成: {len(completed_tasks)}")
        print(f"失敗: {len(failed_tasks)}")
        
        # 健康趨勢
        print(f"\n📊 健康趨勢:")
        print(f"24小時檢查次數: {len(health_history)}")
        
        if health_history:
            recent_critical = len([h for h in health_history if h.status == HealthStatus.CRITICAL])
            recent_warning = len([h for h in health_history if h.status == HealthStatus.WARNING])
            print(f"近期嚴重問題: {recent_critical}")
            print(f"近期警告問題: {recent_warning}")
    
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
    parser = argparse.ArgumentParser(description="Discord機器人監控儀表板工具")
    
    # 子命令
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 儀表板報告
    dashboard_parser = subparsers.add_parser('dashboard', help='生成儀表板報告')
    dashboard_parser.add_argument('--output', help='輸出HTML文件路徑')
    
    # JSON報告
    json_parser = subparsers.add_parser('json', help='生成JSON報告')
    
    # 系統概覽
    overview_parser = subparsers.add_parser('overview', help='顯示系統概覽')
    
    # 警報摘要
    alerts_parser = subparsers.add_parser('alerts', help='顯示警報摘要')
    alerts_parser.add_argument('--hours', type=int, default=24, help='時間範圍（小時）')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    tool = DashboardTool()
    
    try:
        await tool.initialize()
        
        if args.command == 'dashboard':
            await tool.generate_dashboard_report(args.output)
        elif args.command == 'json':
            await tool.generate_json_report()
        elif args.command == 'overview':
            await tool.show_system_overview()
        elif args.command == 'alerts':
            await tool.show_alert_summary(args.hours)
        
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