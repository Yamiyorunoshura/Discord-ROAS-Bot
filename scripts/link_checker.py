#!/usr/bin/env python3
"""
連結檢查腳本範例
Task ID: T3 - 文檔連結有效性修復

演示如何使用連結檢查API服務的實用腳本
支援配置文件和CI環境整合
"""

import asyncio
import argparse
import json
import sys
import yaml
import os
from pathlib import Path
from typing import List, Optional, Dict, Any

# 假設服務已正確安裝
try:
    from services.documentation.api_endpoints import LinkCheckAPI
    from services.documentation.link_checker_models import LinkCheckConfig
except ImportError:
    print("錯誤：無法導入連結檢查服務，請確保已正確安裝")
    sys.exit(1)


def load_config(project_root: str = ".") -> Dict[str, Any]:
    """
    載入配置文件
    
    優先順序：
    1. CI專用配置 (.github/linkcheck-ci.json) - 如果在CI環境中
    2. 主配置文件 (.linkcheckrc.yml)
    3. 預設配置
    """
    config = {
        # 預設配置
        "check_settings": {
            "check_external_links": False,
            "check_anchors": True,
            "timeout_seconds": 10,
            "max_concurrent_checks": 3
        },
        "performance_optimization": {
            "max_execution_time_seconds": 300
        },
        "error_handling": {
            "max_broken_links_allowed": 0
        }
    }
    
    project_path = Path(project_root)
    
    # 檢查是否在CI環境
    is_ci = os.getenv("CI") == "true" or os.getenv("CI_LINK_CHECK") == "true"
    
    if is_ci:
        # 優先使用CI配置
        ci_config_path = project_path / ".github" / "linkcheck-ci.json"
        if ci_config_path.exists():
            try:
                with open(ci_config_path, 'r', encoding='utf-8') as f:
                    ci_config = json.load(f)
                    config.update(ci_config)
                    print(f"✅ 已載入CI配置: {ci_config_path}")
                    return config
            except Exception as e:
                print(f"⚠️  載入CI配置失敗: {e}")
    
    # 載入主配置文件
    main_config_path = project_path / ".linkcheckrc.yml"
    if main_config_path.exists():
        try:
            with open(main_config_path, 'r', encoding='utf-8') as f:
                yaml_config = yaml.safe_load(f)
                if yaml_config:
                    # 轉換YAML配置格式為統一格式
                    if 'base_settings' in yaml_config:
                        config['check_settings'].update(yaml_config['base_settings'])
                    if 'ci_settings' in yaml_config and is_ci:
                        config['check_settings'].update(yaml_config['ci_settings'])
                    print(f"✅ 已載入主配置: {main_config_path}")
        except Exception as e:
            print(f"⚠️  載入主配置失敗: {e}")
    
    return config


def load_ignore_rules(project_root: str = ".") -> List[str]:
    """載入忽略規則"""
    ignore_rules = []
    ignore_file = Path(project_root) / ".linkcheckignore"
    
    if ignore_file.exists():
        try:
            with open(ignore_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        ignore_rules.append(line)
            print(f"✅ 已載入 {len(ignore_rules)} 條忽略規則")
        except Exception as e:
            print(f"⚠️  載入忽略規則失敗: {e}")
    
    return ignore_rules


async def check_links_command(
    target_paths: List[str],
    check_external: bool = False,
    check_anchors: bool = True,
    output_format: str = "text",
    export_report: bool = False,
    project_root: str = "."
) -> None:
    """執行連結檢查命令"""
    
    # 載入配置
    config = load_config(project_root)
    ignore_rules = load_ignore_rules(project_root)
    
    # 從配置覆蓋參數
    check_settings = config.get('check_settings', {})
    if not check_external:  # 只有在未明確指定時才使用配置
        check_external = check_settings.get('check_external_links', False)
    if check_anchors is True:  # 使用配置值
        check_anchors = check_settings.get('check_anchors', True)
    
    print(f"🔍 開始檢查文檔連結...")
    print(f"📁 項目根目錄: {project_root}")
    print(f"📂 檢查路徑: {', '.join(target_paths)}")
    print(f"🌐 檢查外部連結: {'是' if check_external else '否'}")
    print(f"⚓ 檢查錨點連結: {'是' if check_anchors else '否'}")
    
    # 檢查執行時間限制（CI環境）
    max_execution_time = config.get('performance_optimization', {}).get('max_execution_time_seconds', 300)
    if os.getenv("CI_LINK_CHECK") == "true":
        print(f"⏱️  最大執行時間: {max_execution_time}秒")
    
    # 初始化API
    api = LinkCheckAPI(project_root)
    await api.initialize()
    
    try:
        # 設置執行時間限制
        async def run_check():
            return await api.check_links(
                target_paths=target_paths,
                check_external=check_external,
                check_anchors=check_anchors,
                output_format="json"  # 內部使用JSON格式
            )
        
        # 在CI環境中應用時間限制
        if os.getenv("CI_LINK_CHECK") == "true":
            result = await asyncio.wait_for(run_check(), timeout=max_execution_time)
        else:
            result = await run_check()
        
        if not result["success"]:
            print(f"❌ 檢查失敗: {result['error']['message']}")
            return
        
        # 解析結果
        data = result["data"]
        summary = data["summary"]
        
        # 顯示摘要
        print(f"\n📊 檢查結果摘要:")
        print(f"   📄 檢查文檔數: {summary['documents_checked']}")
        print(f"   🔗 總連結數: {summary['total_links']}")
        print(f"   ✅ 有效連結: {summary['valid_links']}")
        print(f"   ❌ 無效連結: {summary['broken_links']}")
        print(f"   📈 成功率: {summary['success_rate']:.1f}%")
        print(f"   ⏱️  執行時間: {summary['duration_ms']:.0f}ms")
        
        # 顯示連結類型分布
        if "details" in data:
            dist = data["details"]["link_distribution"]
            print(f"\n🔗 連結類型分布:")
            print(f"   📁 內部連結: {dist['internal_links']}")
            print(f"   🌐 外部連結: {dist['external_links']}")
            print(f"   ⚓ 錨點連結: {dist['anchor_links']}")
            print(f"   📄 檔案連結: {dist['file_links']}")
        
        # 顯示無效連結詳情
        if summary["has_failures"] and "details" in data:
            broken_links = data["details"]["broken_links"]
            print(f"\n❌ 無效連結詳情 ({len(broken_links)} 個):")
            
            for i, link in enumerate(broken_links[:10], 1):  # 最多顯示10個
                print(f"   {i}. [{link['text']}]({link['url']})")
                print(f"      📍 位置: 第 {link['line_number']} 行")
                print(f"      🔍 類型: {link['link_type']}")
                if link.get('error_message'):
                    print(f"      💬 錯誤: {link['error_message']}")
                print()
            
            if len(broken_links) > 10:
                print(f"   ... 還有 {len(broken_links) - 10} 個無效連結")
        
        # 顯示警告
        if "details" in data and data["details"]["warnings"]:
            warnings = data["details"]["warnings"]
            print(f"\n⚠️  警告信息 ({len(warnings)} 個):")
            for warning in warnings[:5]:
                print(f"   • {warning}")
        
        # 顯示建議
        if "recommendations" in data:
            recommendations = data["recommendations"]
            print(f"\n💡 修復建議:")
            for rec in recommendations:
                print(f"   • {rec}")
        
        # 匯出報告
        if export_report:
            print(f"\n📄 匯出報告...")
            
            formats = ["markdown", "json", "csv"] if output_format == "all" else [output_format]
            
            for fmt in formats:
                try:
                    export_result = await api.export_report(data["check_id"], fmt)
                    if export_result["success"]:
                        report_path = export_result["data"]["report_path"]
                        file_size = export_result["data"]["file_size"]
                        print(f"   ✅ {fmt.upper()} 報告已保存: {report_path} ({file_size} bytes)")
                    else:
                        print(f"   ❌ {fmt.upper()} 報告匯出失敗")
                except Exception as e:
                    print(f"   ❌ {fmt.upper()} 報告匯出錯誤: {e}")
        
        # 檢查CI環境的容忍度
        max_broken_allowed = config.get('error_handling', {}).get('max_broken_links_allowed', 0)
        
        # 返回狀態碼
        if summary["broken_links"] > max_broken_allowed:
            print(f"\n❌ 檢查完成但有 {summary['broken_links']} 個失敗項目")
            print(f"💥 超過允許的最大失敗數量 ({max_broken_allowed})")
            sys.exit(1)
        else:
            print(f"\n✅ 所有連結檢查通過！")
    
    except asyncio.TimeoutError:
        print(f"\n⏰ 檢查超時 (超過 {max_execution_time}秒)")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 檢查過程中發生錯誤: {e}")
        sys.exit(1)
    finally:
        await api.shutdown()


async def list_history_command(limit: int = 10, project_root: str = ".") -> None:
    """列出檢查歷史命令"""
    
    print(f"📜 檢查歷史記錄 (最近 {limit} 次)")
    
    api = LinkCheckAPI(project_root)
    await api.initialize()
    
    try:
        result = await api.list_check_history(limit=limit)
        
        if not result["success"]:
            print(f"❌ 獲取歷史失敗: {result['error']['message']}")
            return
        
        history = result["data"]["history"]
        
        if not history:
            print("📝 暫無檢查記錄")
            return
        
        print(f"\n📊 共找到 {len(history)} 條記錄:")
        print("-" * 80)
        
        for i, record in enumerate(history, 1):
            timestamp = record["timestamp"][:19].replace("T", " ")
            status = "✅ 通過" if not record["has_failures"] else "❌ 失敗"
            
            print(f"{i:2}. {timestamp} | {status} | "
                  f"文檔:{record['documents_checked']:2} | "
                  f"連結:{record['total_links']:3} | "
                  f"成功率:{record['success_rate']:5.1f}% | "
                  f"耗時:{record['duration_ms']:4.0f}ms")
    
    finally:
        await api.shutdown()


async def manage_schedule_command(
    action: str,
    name: Optional[str] = None,
    interval_hours: Optional[int] = None,
    schedule_id: Optional[str] = None,
    project_root: str = "."
) -> None:
    """管理定期檢查排程命令"""
    
    api = LinkCheckAPI(project_root)
    await api.initialize()
    
    try:
        if action == "create":
            if not name or not interval_hours:
                print("❌ 創建排程需要提供 --name 和 --interval 參數")
                return
            
            print(f"📅 創建定期檢查排程...")
            
            result = await api.create_periodic_schedule(
                name=name,
                interval_hours=interval_hours,
                target_directories=["docs/"]
            )
            
            if result["success"]:
                data = result["data"]
                print(f"✅ 排程創建成功!")
                print(f"   📋 排程ID: {data['schedule_id']}")
                print(f"   📛 名稱: {data['name']}")
                print(f"   ⏰ 間隔: {data['interval_hours']} 小時")
                print(f"   📁 目標: {', '.join(data['target_directories'])}")
            else:
                print(f"❌ 創建排程失敗: {result['error']['message']}")
        
        elif action == "list":
            print("📋 定期檢查排程列表")
            
            result = await api.list_schedules()
            
            if not result["success"]:
                print(f"❌ 獲取排程列表失敗: {result['error']['message']}")
                return
            
            schedules = result["data"]["schedules"]
            
            if not schedules:
                print("📝 暫無活躍排程")
                return
            
            print(f"\n📊 共找到 {len(schedules)} 個排程:")
            print("-" * 100)
            
            for i, schedule in enumerate(schedules, 1):
                status = "🟢 啟用" if schedule["enabled"] else "🔴 停用"
                next_check = schedule["next_check_time"][:19].replace("T", " ")
                last_check = "未執行"
                if schedule["last_check_time"]:
                    last_check = schedule["last_check_time"][:19].replace("T", " ")
                
                print(f"{i:2}. {schedule['name']:20} | {status} | "
                      f"間隔:{schedule['interval_hours']:2}h | "
                      f"下次:{next_check} | 上次:{last_check}")
        
        elif action == "cancel":
            if not schedule_id:
                print("❌ 取消排程需要提供 --schedule-id 參數")
                return
            
            print(f"🗑️  取消排程: {schedule_id}")
            
            result = await api.cancel_schedule(schedule_id)
            
            if result["success"]:
                print("✅ 排程已取消")
            else:
                print(f"❌ 取消排程失敗: {result['error']['message']}")
        
        else:
            print(f"❌ 不支援的排程操作: {action}")
    
    finally:
        await api.shutdown()


async def status_command(project_root: str = ".") -> None:
    """顯示服務狀態命令"""
    
    print("📊 連結檢查服務狀態")
    
    api = LinkCheckAPI(project_root)
    await api.initialize()
    
    try:
        result = await api.get_service_status()
        
        if not result["success"]:
            print(f"❌ 獲取狀態失敗: {result['error']['message']}")
            return
        
        data = result["data"]
        service = data["service"]
        cache = data["cache"]
        errors = data["errors"]
        
        print(f"\n🔧 服務狀態:")
        print(f"   📡 狀態: {'🟢 運行中' if service['initialized'] else '🔴 未初始化'}")
        print(f"   📁 基礎路徑: {service['base_path']}")
        print(f"   🔄 運行中檢查: {service['running_checks']}")
        print(f"   📅 定期排程: {service['periodic_schedules']} 個 ({service['active_schedules']} 個活躍)")
        print(f"   📜 歷史記錄: {service['history_count']} 條")
        
        print(f"\n💾 快取狀態:")
        print(f"   📈 命中率: {cache['hit_rate_percent']:.1f}% ({cache['hits']} 命中 / {cache['misses']} 未命中)")
        print(f"   📦 當前大小: {cache['current_size']} / {cache['max_size']}")
        
        print(f"\n⚠️  錯誤統計:")
        print(f"   📊 總錯誤數: {errors['total_errors']}")
        print(f"   🕐 最近1小時: {errors['recent_errors_1h']}")
        
        if errors.get('top_error_codes'):
            print(f"   🔝 常見錯誤:")
            for error in errors['top_error_codes'][:3]:
                print(f"      • {error['code']}: {error['count']} 次")
        
        print(f"\n🏷️  API版本: {data['api_version']}")
    
    finally:
        await api.shutdown()


def main():
    """主程式入口"""
    
    parser = argparse.ArgumentParser(
        description="文檔連結檢查工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用範例:
  %(prog)s check docs/                     # 檢查docs目錄
  %(prog)s check docs/ README.md --export # 檢查並匯出報告
  %(prog)s check docs/ --external         # 檢查包括外部連結
  %(prog)s history --limit 20             # 顯示最近20次檢查記錄
  %(prog)s schedule create --name daily --interval 24  # 創建每日排程
  %(prog)s schedule list                   # 列出所有排程
  %(prog)s status                         # 顯示服務狀態
        """
    )
    
    parser.add_argument("--project-root", default=".", help="項目根目錄 (預設: 當前目錄)")
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # 檢查命令
    check_parser = subparsers.add_parser("check", help="檢查文檔連結")
    check_parser.add_argument("paths", nargs="+", help="要檢查的文檔路徑")
    check_parser.add_argument("--external", action="store_true", help="檢查外部連結")
    check_parser.add_argument("--no-anchors", action="store_true", help="不檢查錨點連結")
    check_parser.add_argument("--export", action="store_true", help="匯出報告")
    check_parser.add_argument("--format", choices=["markdown", "json", "csv", "all"], 
                             default="markdown", help="報告格式")
    
    # 歷史命令
    history_parser = subparsers.add_parser("history", help="檢視檢查歷史")
    history_parser.add_argument("--limit", type=int, default=10, help="顯示記錄數量")
    
    # 排程命令
    schedule_parser = subparsers.add_parser("schedule", help="管理定期檢查排程")
    schedule_subparsers = schedule_parser.add_subparsers(dest="schedule_action", help="排程操作")
    
    create_parser = schedule_subparsers.add_parser("create", help="創建排程")
    create_parser.add_argument("--name", required=True, help="排程名稱")
    create_parser.add_argument("--interval", type=int, required=True, help="檢查間隔 (小時)")
    
    schedule_subparsers.add_parser("list", help="列出排程")
    
    cancel_parser = schedule_subparsers.add_parser("cancel", help="取消排程")
    cancel_parser.add_argument("--schedule-id", required=True, help="要取消的排程ID")
    
    # 狀態命令
    subparsers.add_parser("status", help="顯示服務狀態")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # 執行對應命令
    try:
        if args.command == "check":
            asyncio.run(check_links_command(
                target_paths=args.paths,
                check_external=args.external,
                check_anchors=not args.no_anchors,
                output_format=args.format,
                export_report=args.export,
                project_root=args.project_root
            ))
        
        elif args.command == "history":
            asyncio.run(list_history_command(
                limit=args.limit,
                project_root=args.project_root
            ))
        
        elif args.command == "schedule":
            if not args.schedule_action:
                schedule_parser.print_help()
                return
            
            asyncio.run(manage_schedule_command(
                action=args.schedule_action,
                name=getattr(args, "name", None),
                interval_hours=getattr(args, "interval", None),
                schedule_id=getattr(args, "schedule_id", None),
                project_root=args.project_root
            ))
        
        elif args.command == "status":
            asyncio.run(status_command(project_root=args.project_root))
    
    except KeyboardInterrupt:
        print("\n⏸️  操作已取消")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ 執行錯誤: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()