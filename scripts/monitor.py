#!/usr/bin/env python3
# 監控工具統一入口
# Task ID: 11 - 建立文件和部署準備 - F11-4: 監控維護工具

import argparse
import subprocess
import sys
from pathlib import Path

class MonitoringToolsLauncher:
    """監控工具啟動器"""
    
    def __init__(self):
        self.script_dir = Path(__file__).parent
        self.tools = {
            'health': {
                'script': 'health_check.py',
                'description': '系統健康檢查工具'
            },
            'performance': {
                'script': 'performance_monitor.py', 
                'description': '效能監控工具'
            },
            'maintenance': {
                'script': 'maintenance.py',
                'description': '自動維護工具'
            },
            'dashboard': {
                'script': 'dashboard.py',
                'description': '監控儀表板工具'
            }
        }
    
    def show_help(self):
        """顯示幫助信息"""
        print("🔧 Discord機器人監控工具集")
        print("="*60)
        print()
        print("可用工具:")
        for tool_name, tool_info in self.tools.items():
            print(f"  {tool_name:12} - {tool_info['description']}")
        print()
        print("使用方法:")
        print("  monitor <工具名稱> [參數...]")
        print()
        print("範例:")
        print("  monitor health check                    # 執行健康檢查")
        print("  monitor performance monitor --interval 10  # 效能監控")
        print("  monitor maintenance all --dry-run      # 預覽維護任務")
        print("  monitor dashboard overview             # 顯示系統概覽")
        print()
        print("獲取特定工具幫助:")
        print("  monitor <工具名稱> --help")
    
    def launch_tool(self, tool_name, args):
        """啟動指定工具"""
        if tool_name not in self.tools:
            print(f"❌ 未知工具: {tool_name}")
            print(f"可用工具: {', '.join(self.tools.keys())}")
            return 1
        
        script_path = self.script_dir / self.tools[tool_name]['script']
        
        if not script_path.exists():
            print(f"❌ 工具腳本不存在: {script_path}")
            return 1
        
        # 構建命令
        cmd = [sys.executable, str(script_path)] + args
        
        try:
            # 執行工具
            result = subprocess.run(cmd, check=False)
            return result.returncode
        except KeyboardInterrupt:
            print("\n⏹️  操作已取消")
            return 130
        except Exception as e:
            print(f"❌ 工具執行失敗: {e}")
            return 1
    
    def quick_health_check(self):
        """快速健康檢查"""
        print("🚀 執行快速健康檢查...")
        return self.launch_tool('health', ['check'])
    
    def quick_system_status(self):
        """快速系統狀態檢查"""
        print("🚀 獲取系統狀態...")
        return self.launch_tool('dashboard', ['overview'])
    
    def emergency_maintenance(self):
        """緊急維護"""
        print("🚨 執行緊急維護（預覽模式）...")
        return self.launch_tool('maintenance', ['all', '--dry-run'])

def main():
    """主函數"""
    launcher = MonitoringToolsLauncher()
    
    if len(sys.argv) < 2:
        launcher.show_help()
        return 1
    
    tool_name = sys.argv[1]
    tool_args = sys.argv[2:] if len(sys.argv) > 2 else []
    
    # 特殊快捷命令
    if tool_name == 'help' or tool_name == '--help' or tool_name == '-h':
        launcher.show_help()
        return 0
    elif tool_name == 'quick-check':
        return launcher.quick_health_check()
    elif tool_name == 'status':
        return launcher.quick_system_status()
    elif tool_name == 'emergency':
        return launcher.emergency_maintenance()
    else:
        return launcher.launch_tool(tool_name, tool_args)

if __name__ == "__main__":
    sys.exit(main())