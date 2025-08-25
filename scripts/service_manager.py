#!/usr/bin/env python3
"""
ROAS Bot 服務管理器
Task ID: 1 - ROAS Bot v2.4.3 Docker啟動系統修復

提供完整的服務生命週期管理，包括啟動、停止、重啟、監控和維護功能。
這是一個統一的服務管理入口點，整合了所有已開發的整合組件。
"""

import asyncio
import argparse
import json
import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from contextlib import asynccontextmanager
import subprocess
import signal
import os

# 添加核心模組到路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.service_integration_coordinator import ServiceIntegrationCoordinator
from core.unified_health_checker import UnifiedHealthChecker
from core.unified_logging_integration import create_logger, get_log_handler
from core.monitoring_collector import MonitoringCollector
from core.deployment_manager import create_deployment_manager
from core.environment_validator import EnvironmentValidator

logger = logging.getLogger(__name__)


class ServiceAction:
    """服務操作定義"""
    START = "start"
    STOP = "stop"
    RESTART = "restart"
    STATUS = "status"
    HEALTH = "health"
    LOGS = "logs"
    MONITOR = "monitor"
    CLEAN = "clean"
    BACKUP = "backup"
    RESTORE = "restore"


class ServiceManager:
    """服務管理器"""
    
    def __init__(self, project_root: Path, environment: str = 'dev'):
        self.project_root = project_root
        self.environment = environment
        self.service_logger = create_logger("service-manager", "management")
        
        # 初始化組件
        self.coordinator = ServiceIntegrationCoordinator(project_root, environment)
        self.health_checker = UnifiedHealthChecker(project_root)
        self.monitoring_collector = MonitoringCollector(project_root)
        self.deployment_manager = create_deployment_manager(environment, project_root)
        self.environment_validator = EnvironmentValidator(project_root)
        self.log_handler = get_log_handler()
        
        # 運行時狀態
        self.monitoring_task = None
        self.is_monitoring = False
    
    async def execute_action(self, action: str, services: List[str] = None, 
                           **kwargs) -> Dict[str, Any]:
        """執行服務操作"""
        self.service_logger.info(f"執行操作: {action}")
        
        try:
            with self.service_logger.context(f"service-{action}") as ctx:
                
                if action == ServiceAction.START:
                    return await self._start_services(services, **kwargs)
                elif action == ServiceAction.STOP:
                    return await self._stop_services(services, **kwargs)
                elif action == ServiceAction.RESTART:
                    return await self._restart_services(services, **kwargs)
                elif action == ServiceAction.STATUS:
                    return await self._get_status(**kwargs)
                elif action == ServiceAction.HEALTH:
                    return await self._check_health(**kwargs)
                elif action == ServiceAction.LOGS:
                    return await self._get_logs(services, **kwargs)
                elif action == ServiceAction.MONITOR:
                    return await self._start_monitoring(**kwargs)
                elif action == ServiceAction.CLEAN:
                    return await self._clean_services(**kwargs)
                elif action == ServiceAction.BACKUP:
                    return await self._backup_data(**kwargs)
                elif action == ServiceAction.RESTORE:
                    return await self._restore_data(**kwargs)
                else:
                    raise ValueError(f"不支持的操作: {action}")
                    
        except Exception as e:
            self.service_logger.error(f"操作 {action} 失敗", exception=e)
            return {
                'success': False,
                'action': action,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def _start_services(self, services: List[str] = None, 
                            force: bool = False, **kwargs) -> Dict[str, Any]:
        """啟動服務"""
        self.service_logger.info("啟動服務")
        
        # 環境檢查
        if not force:
            passed, errors = await self.environment_validator.validate_environment()
            if not passed:
                return {
                    'success': False,
                    'action': ServiceAction.START,
                    'error': 'Environment validation failed',
                    'validation_errors': errors
                }
        
        # 使用部署管理器啟動
        success, message = await self.deployment_manager.start_services()
        
        if success:
            # 等待服務穩定
            await asyncio.sleep(5)
            
            # 檢查健康狀況
            health_report = await self.health_checker.check_all_services()
            
            return {
                'success': True,
                'action': ServiceAction.START,
                'message': message,
                'health_report': {
                    'overall_status': health_report.overall_status.value,
                    'health_score': health_report.health_score,
                    'healthy_services': len([
                        s for s in health_report.service_results.values()
                        if s.status.value == 'healthy'
                    ])
                },
                'timestamp': datetime.now().isoformat()
            }
        else:
            return {
                'success': False,
                'action': ServiceAction.START,
                'error': message,
                'timestamp': datetime.now().isoformat()
            }
    
    async def _stop_services(self, services: List[str] = None, 
                           graceful: bool = True, **kwargs) -> Dict[str, Any]:
        """停止服務"""
        self.service_logger.info("停止服務")
        
        # 停止監控
        if self.is_monitoring:
            await self._stop_monitoring()
        
        # 使用部署管理器停止
        success, message = await self.deployment_manager.stop_services()
        
        return {
            'success': success,
            'action': ServiceAction.STOP,
            'message': message,
            'timestamp': datetime.now().isoformat()
        }
    
    async def _restart_services(self, services: List[str] = None, 
                              **kwargs) -> Dict[str, Any]:
        """重啟服務"""
        self.service_logger.info("重啟服務")
        
        # 先停止
        stop_result = await self._stop_services(services, **kwargs)
        
        if not stop_result['success']:
            return stop_result
        
        # 等待完全停止
        await asyncio.sleep(3)
        
        # 再啟動
        start_result = await self._start_services(services, **kwargs)
        
        return {
            'success': start_result['success'],
            'action': ServiceAction.RESTART,
            'stop_result': stop_result,
            'start_result': start_result,
            'timestamp': datetime.now().isoformat()
        }
    
    async def _get_status(self, **kwargs) -> Dict[str, Any]:
        """獲取服務狀態"""
        self.service_logger.info("檢查服務狀態")
        
        # 獲取部署狀態
        deployment_status = await self.deployment_manager.get_deployment_status()
        
        # 獲取監控指標
        monitoring_metrics = await self.monitoring_collector.collect_metrics()
        
        return {
            'success': True,
            'action': ServiceAction.STATUS,
            'deployment_status': deployment_status,
            'monitoring_metrics': monitoring_metrics,
            'timestamp': datetime.now().isoformat()
        }
    
    async def _check_health(self, **kwargs) -> Dict[str, Any]:
        """檢查服務健康"""
        self.service_logger.info("檢查服務健康")
        
        health_report = await self.health_checker.check_all_services()
        
        return {
            'success': True,
            'action': ServiceAction.HEALTH,
            'health_report': {
                'overall_status': health_report.overall_status.value,
                'health_score': health_report.health_score,
                'service_results': {
                    name: {
                        'status': result.status.value,
                        'response_time_ms': result.response_time_ms,
                        'last_check': result.last_check.isoformat(),
                        'error': result.error
                    }
                    for name, result in health_report.service_results.items()
                },
                'critical_issues': health_report.critical_issues,
                'warnings': health_report.warnings,
                'recommendations': health_report.recommendations
            },
            'timestamp': datetime.now().isoformat()
        }
    
    async def _get_logs(self, services: List[str] = None, 
                       lines: int = 100, follow: bool = False, 
                       **kwargs) -> Dict[str, Any]:
        """獲取服務日誌"""
        self.service_logger.info("獲取服務日誌")
        
        if follow:
            # 實時跟隨日誌
            return await self._follow_logs(services, lines)
        else:
            # 獲取日誌內容
            logs = await self.deployment_manager.get_service_logs(
                service_name=services[0] if services else None,
                tail=lines
            )
            
            return {
                'success': True,
                'action': ServiceAction.LOGS,
                'logs': logs,
                'lines_requested': lines,
                'timestamp': datetime.now().isoformat()
            }
    
    async def _follow_logs(self, services: List[str] = None, lines: int = 100) -> Dict[str, Any]:
        """跟隨日誌輸出"""
        print(f"跟隨日誌輸出 (按 Ctrl+C 停止)...")
        
        compose_file = self.project_root / f'docker-compose.{self.environment}.yml'
        
        cmd = ['docker-compose', '-f', str(compose_file), 'logs', '-f', f'--tail={lines}']
        
        if services:
            cmd.extend(services)
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            # 設置信號處理
            def signal_handler(signum, frame):
                process.terminate()
                print("\\n日誌跟隨已停止")
            
            signal.signal(signal.SIGINT, signal_handler)
            
            # 輸出日誌
            for line in process.stdout:
                print(line, end='')
            
            process.wait()
            
        except KeyboardInterrupt:
            process.terminate()
            print("\\n日誌跟隨已停止")
        
        return {
            'success': True,
            'action': ServiceAction.LOGS,
            'mode': 'follow',
            'timestamp': datetime.now().isoformat()
        }
    
    async def _start_monitoring(self, duration: int = 300, interval: int = 30, 
                               **kwargs) -> Dict[str, Any]:
        """啟動監控"""
        self.service_logger.info(f"啟動監控 (持續時間: {duration}秒, 間隔: {interval}秒)")
        
        if self.is_monitoring:
            return {
                'success': False,
                'action': ServiceAction.MONITOR,
                'error': 'Monitoring is already running',
                'timestamp': datetime.now().isoformat()
            }
        
        self.is_monitoring = True
        self.monitoring_task = asyncio.create_task(
            self._monitoring_loop(duration, interval)
        )
        
        return {
            'success': True,
            'action': ServiceAction.MONITOR,
            'duration_seconds': duration,
            'check_interval_seconds': interval,
            'status': 'started',
            'timestamp': datetime.now().isoformat()
        }
    
    async def _monitoring_loop(self, duration: int, interval: int):
        """監控循環"""
        start_time = time.time()
        end_time = start_time + duration
        
        print(f"🔍 開始監控 (持續 {duration/60:.1f} 分鐘)")
        print("="*60)
        
        try:
            while time.time() < end_time and self.is_monitoring:
                # 收集指標
                metrics = await self.monitoring_collector.collect_metrics()
                
                # 健康檢查
                health_report = await self.health_checker.check_all_services()
                
                # 顯示監控信息
                current_time = datetime.now().strftime('%H:%M:%S')
                print(f"[{current_time}] 系統狀態: {metrics.get('overall_status', 'unknown')}")
                print(f"  健康分數: {health_report.health_score:.1f}")
                print(f"  健康服務: {len([s for s in health_report.service_results.values() if s.status.value == 'healthy'])}/{len(health_report.service_results)}")
                
                # 顯示關鍵問題
                if health_report.critical_issues:
                    print(f"  ⚠️  關鍵問題: {len(health_report.critical_issues)}")
                    for issue in health_report.critical_issues[:3]:
                        print(f"    • {issue}")
                
                print("-" * 60)
                
                # 等待下次檢查
                await asyncio.sleep(interval)
        
        except Exception as e:
            self.service_logger.error("監控循環異常", exception=e)
        
        finally:
            self.is_monitoring = False
            print("監控已結束")
    
    async def _stop_monitoring(self):
        """停止監控"""
        if self.is_monitoring:
            self.is_monitoring = False
            if self.monitoring_task:
                self.monitoring_task.cancel()
                try:
                    await self.monitoring_task
                except asyncio.CancelledError:
                    pass
    
    async def _clean_services(self, **kwargs) -> Dict[str, Any]:
        """清理服務"""
        self.service_logger.info("清理服務資源")
        
        # 停止服務
        await self._stop_services(**kwargs)
        
        # 清理資源
        cleanup_result = await self.deployment_manager.cleanup_resources()
        
        return {
            'success': True,
            'action': ServiceAction.CLEAN,
            'cleanup_result': cleanup_result,
            'timestamp': datetime.now().isoformat()
        }
    
    async def _backup_data(self, **kwargs) -> Dict[str, Any]:
        """備份數據"""
        self.service_logger.info("備份服務數據")
        
        backup_timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        backup_dir = self.project_root / 'backups' / f'backup-{backup_timestamp}'
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # 備份配置文件
        config_files = [
            f'docker-compose.{self.environment}.yml',
            'pyproject.toml',
            'Dockerfile'
        ]
        
        backed_up_files = []
        for config_file in config_files:
            source_file = self.project_root / config_file
            if source_file.exists():
                target_file = backup_dir / config_file
                target_file.parent.mkdir(parents=True, exist_ok=True)
                
                import shutil
                shutil.copy2(source_file, target_file)
                backed_up_files.append(config_file)
        
        # 備份數據目錄
        data_dir = self.project_root / 'data'
        if data_dir.exists():
            import shutil
            shutil.copytree(data_dir, backup_dir / 'data', dirs_exist_ok=True)
            backed_up_files.append('data/')
        
        # 備份日誌
        logs_dir = self.project_root / 'logs'
        if logs_dir.exists():
            import shutil
            shutil.copytree(logs_dir, backup_dir / 'logs', dirs_exist_ok=True)
            backed_up_files.append('logs/')
        
        return {
            'success': True,
            'action': ServiceAction.BACKUP,
            'backup_directory': str(backup_dir),
            'backed_up_files': backed_up_files,
            'backup_size_mb': self._get_directory_size(backup_dir) / (1024 * 1024),
            'timestamp': datetime.now().isoformat()
        }
    
    async def _restore_data(self, backup_path: str, **kwargs) -> Dict[str, Any]:
        """恢復數據"""
        self.service_logger.info(f"從備份恢復數據: {backup_path}")
        
        backup_dir = Path(backup_path)
        if not backup_dir.exists():
            return {
                'success': False,
                'action': ServiceAction.RESTORE,
                'error': f'Backup directory does not exist: {backup_path}',
                'timestamp': datetime.now().isoformat()
            }
        
        # 停止服務
        await self._stop_services(**kwargs)
        
        # 恢復文件
        restored_files = []
        
        # 恢復數據目錄
        backup_data_dir = backup_dir / 'data'
        if backup_data_dir.exists():
            target_data_dir = self.project_root / 'data'
            if target_data_dir.exists():
                import shutil
                shutil.rmtree(target_data_dir)
            shutil.copytree(backup_data_dir, target_data_dir)
            restored_files.append('data/')
        
        return {
            'success': True,
            'action': ServiceAction.RESTORE,
            'backup_source': backup_path,
            'restored_files': restored_files,
            'timestamp': datetime.now().isoformat()
        }
    
    def _get_directory_size(self, directory: Path) -> int:
        """獲取目錄大小（位元組）"""
        total_size = 0
        for file_path in directory.rglob('*'):
            if file_path.is_file():
                total_size += file_path.stat().st_size
        return total_size


async def main():
    """主函數"""
    parser = argparse.ArgumentParser(description='ROAS Bot 服務管理器')
    parser.add_argument('action', choices=[
        'start', 'stop', 'restart', 'status', 'health', 
        'logs', 'monitor', 'clean', 'backup', 'restore'
    ], help='要執行的操作')
    
    parser.add_argument('--environment', '-e', default='dev', choices=['dev', 'prod'],
                       help='環境設置')
    parser.add_argument('--services', '-s', nargs='*', help='指定服務名稱')
    parser.add_argument('--force', '-f', action='store_true', help='強制執行')
    parser.add_argument('--verbose', '-v', action='store_true', help='詳細輸出')
    
    # 日誌相關參數
    parser.add_argument('--lines', type=int, default=100, help='日誌行數')
    parser.add_argument('--follow', action='store_true', help='跟隨日誌輸出')
    
    # 監控相關參數
    parser.add_argument('--duration', type=int, default=300, help='監控持續時間(秒)')
    parser.add_argument('--interval', type=int, default=30, help='監控間隔(秒)')
    
    # 備份/恢復相關參數
    parser.add_argument('--backup-path', help='備份路徑 (用於恢復)')
    
    # 其他參數
    parser.add_argument('--graceful', action='store_true', help='優雅停止')
    parser.add_argument('--output', '-o', help='輸出文件路徑')
    
    args = parser.parse_args()
    
    # 設置日誌
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 確定專案根目錄
    project_root = Path.cwd()
    
    print(f"🔧 ROAS Bot v2.4.3 服務管理器")
    print(f"操作: {args.action}")
    print(f"環境: {args.environment}")
    print(f"專案根目錄: {project_root}")
    print(f"時間: {datetime.now()}")
    print("=" * 50)
    
    try:
        # 創建服務管理器
        service_manager = ServiceManager(project_root, args.environment)
        
        # 構建參數
        action_kwargs = {
            'force': args.force,
            'graceful': args.graceful,
            'lines': args.lines,
            'follow': args.follow,
            'duration': args.duration,
            'interval': args.interval
        }
        
        if args.backup_path:
            action_kwargs['backup_path'] = args.backup_path
        
        # 執行操作
        result = await service_manager.execute_action(
            args.action, 
            args.services,
            **action_kwargs
        )
        
        # 輸出結果
        if result['success']:
            print(f"✅ 操作 '{args.action}' 成功完成")
        else:
            print(f"❌ 操作 '{args.action}' 失敗")
            if 'error' in result:
                print(f"錯誤: {result['error']}")
        
        # 顯示詳細結果
        if args.verbose or not result['success']:
            print(f"\\n詳細結果:")
            print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        
        # 保存輸出
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False, default=str)
            print(f"結果已保存到: {args.output}")
        
        # 針對特定操作的額外輸出
        if args.action == 'status' and result['success']:
            deployment_status = result.get('deployment_status', {})
            services = deployment_status.get('services', [])
            if services:
                print(f"\\n服務狀態:")
                for service in services:
                    status = service.get('status', 'unknown')
                    name = service.get('name', 'unknown')
                    print(f"  • {name}: {status}")
        
        elif args.action == 'health' and result['success']:
            health_report = result.get('health_report', {})
            overall_status = health_report.get('overall_status', 'unknown')
            health_score = health_report.get('health_score', 0)
            print(f"\\n健康狀況:")
            print(f"  整體狀態: {overall_status}")
            print(f"  健康分數: {health_score:.1f}")
            
            critical_issues = health_report.get('critical_issues', [])
            if critical_issues:
                print(f"  關鍵問題:")
                for issue in critical_issues:
                    print(f"    • {issue}")
        
        return 0 if result['success'] else 1
        
    except KeyboardInterrupt:
        print("\\n操作已取消")
        return 130
    except Exception as e:
        print(f"❌ 服務管理器異常: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))