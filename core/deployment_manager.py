#!/usr/bin/env python3
"""
部署管理器 - 統一管理Docker服務的啟動、停止和狀態檢查
Task ID: 1 - ROAS Bot v2.4.3 Docker啟動系統修復

這個模組負責管理整個Docker服務的生命週期，包括啟動、停止、健康檢查和故障恢復。
"""

import asyncio
import json
import logging
import os
import signal
import subprocess
import time
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Callable
import yaml
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    """服務狀態枚舉"""
    UNKNOWN = "unknown"
    STARTING = "starting"
    RUNNING = "running"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass
class ServiceInfo:
    """服務資訊"""
    name: str
    container_id: Optional[str]
    status: ServiceStatus
    health_status: Optional[str]
    ports: List[str]
    created_at: Optional[str]
    started_at: Optional[str]
    message: Optional[str] = None


@dataclass
class DeploymentResult:
    """部署結果"""
    success: bool
    message: str
    services: List[ServiceInfo]
    duration_seconds: float
    timestamp: str
    errors: List[str]
    warnings: List[str]


class DeploymentManager:
    """
    部署管理器 - 統一管理Docker服務的啟動、停止和狀態檢查
    
    負責處理：
    - Docker Compose服務編排
    - 服務健康檢查和監控
    - 故障檢測和自動恢復
    - 部署狀態追蹤
    - 日誌收集和分析
    """
    
    def __init__(self, project_root: Optional[Path] = None, compose_file: Optional[str] = None):
        self.project_root = project_root or Path.cwd()
        self.compose_file = compose_file
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.deployment_timeout = 300  # 5分鐘
        self.health_check_timeout = 60  # 1分鐘
        self.retry_attempts = 3
        self.retry_delay = 10  # 10秒
        
    def _get_compose_command(self) -> List[str]:
        """獲取Docker Compose命令"""
        base_cmd = ['docker', 'compose']
        if self.compose_file:
            base_cmd.extend(['-f', self.compose_file])
        return base_cmd
    
    async def start_services(self, detach: bool = True, build: bool = True, 
                           pull: bool = True, recreate: bool = False) -> Tuple[bool, str]:
        """
        啟動服務
        
        Args:
            detach: 是否在背景執行
            build: 是否重新建置映像
            pull: 是否拉取最新映像  
            recreate: 是否重新創建容器
            
        Returns:
            Tuple[bool, str]: (是否成功, 結果訊息)
        """
        start_time = time.time()
        self.logger.info("開始啟動Docker服務")
        
        try:
            # 環境檢查
            env_check_result = await self._pre_deployment_check()
            if not env_check_result:
                return False, "環境檢查失敗"
            
            # 停止現有服務（如果recreate=True）
            if recreate:
                self.logger.info("重新創建容器，先停止現有服務")
                await self._stop_services_internal()
            
            # 拉取映像
            if pull:
                await self._pull_images()
            
            # 建置映像
            if build:
                await self._build_images()
            
            # 啟動服務
            success = await self._start_services_internal(detach)
            if not success:
                return False, "服務啟動失敗"
            
            # 等待服務啟動完成
            await self._wait_for_services()
            
            # 健康檢查
            health_success, health_message = await self._comprehensive_health_check()
            if not health_success:
                self.logger.error(f"健康檢查失敗: {health_message}")
                return False, f"服務啟動失敗: {health_message}"
            
            duration = time.time() - start_time
            success_message = f"所有服務啟動成功，耗時 {duration:.1f} 秒"
            self.logger.info(success_message)
            return True, success_message
            
        except Exception as e:
            duration = time.time() - start_time
            error_message = f"服務啟動異常: {str(e)}"
            self.logger.error(error_message, exc_info=True)
            return False, error_message
    
    async def stop_services(self, timeout: int = 30) -> Tuple[bool, str]:
        """
        停止服務
        
        Args:
            timeout: 停止超時時間（秒）
            
        Returns:
            Tuple[bool, str]: (是否成功, 結果訊息)
        """
        self.logger.info("開始停止Docker服務")
        
        try:
            success = await self._stop_services_internal(timeout)
            if success:
                return True, "所有服務已成功停止"
            else:
                return False, "部分服務停止失敗"
        except Exception as e:
            error_message = f"服務停止異常: {str(e)}"
            self.logger.error(error_message, exc_info=True)
            return False, error_message
    
    async def restart_services(self, timeout: int = 30) -> Tuple[bool, str]:
        """
        重啟服務
        
        Args:
            timeout: 重啟超時時間（秒）
            
        Returns:
            Tuple[bool, str]: (是否成功, 結果訊息)
        """
        self.logger.info("開始重啟Docker服務")
        
        try:
            # 先停止
            stop_success, stop_message = await self.stop_services(timeout)
            if not stop_success:
                return False, f"停止服務失敗: {stop_message}"
            
            # 等待一下確保完全停止
            await asyncio.sleep(5)
            
            # 再啟動
            start_success, start_message = await self.start_services()
            return start_success, f"重啟完成: {start_message}"
            
        except Exception as e:
            error_message = f"服務重啟異常: {str(e)}"
            self.logger.error(error_message, exc_info=True)
            return False, error_message
    
    async def health_check(self) -> Dict[str, Any]:
        """
        執行健康檢查
        
        Returns:
            Dict[str, Any]: 健康檢查結果
        """
        self.logger.debug("執行服務健康檢查")
        
        result = {
            'timestamp': time.time(),
            'overall_healthy': False,
            'services': {},
            'summary': {
                'total': 0,
                'healthy': 0,
                'unhealthy': 0,
                'unknown': 0
            }
        }
        
        try:
            services_info = await self._get_services_info()
            result['services'] = {service.name: {
                'status': service.status.value,
                'health_status': service.health_status,
                'container_id': service.container_id,
                'message': service.message
            } for service in services_info}
            
            # 統計摘要
            for service in services_info:
                result['summary']['total'] += 1
                if service.status == ServiceStatus.HEALTHY:
                    result['summary']['healthy'] += 1
                elif service.status in [ServiceStatus.UNHEALTHY, ServiceStatus.FAILED]:
                    result['summary']['unhealthy'] += 1
                else:
                    result['summary']['unknown'] += 1
            
            # 判斷整體健康狀態
            result['overall_healthy'] = (
                result['summary']['total'] > 0 and 
                result['summary']['unhealthy'] == 0 and
                result['summary']['healthy'] == result['summary']['total']
            )
            
        except Exception as e:
            self.logger.error(f"健康檢查執行失敗: {str(e)}", exc_info=True)
            result['error'] = str(e)
        
        return result
    
    async def get_service_logs(self, service_name: Optional[str] = None, 
                             tail: int = 100, follow: bool = False) -> str:
        """
        獲取服務日誌
        
        Args:
            service_name: 服務名稱，None表示所有服務
            tail: 顯示最後N行
            follow: 是否持續跟蹤日誌
            
        Returns:
            str: 日誌內容
        """
        try:
            cmd = self._get_compose_command() + ['logs', f'--tail={tail}']
            if follow:
                cmd.append('-f')
            if service_name:
                cmd.append(service_name)
            
            result = subprocess.run(cmd, capture_output=True, text=True, 
                                  timeout=30, cwd=self.project_root)
            
            if result.returncode == 0:
                return result.stdout
            else:
                return f"獲取日誌失敗: {result.stderr}"
                
        except Exception as e:
            return f"獲取日誌異常: {str(e)}"
    
    async def get_deployment_status(self) -> Dict[str, Any]:
        """
        獲取部署狀態資訊
        
        Returns:
            Dict[str, Any]: 部署狀態
        """
        try:
            services_info = await self._get_services_info()
            
            status = {
                'timestamp': time.time(),
                'compose_file': self.compose_file,
                'project_root': str(self.project_root),
                'services': [],
                'summary': {
                    'total_services': len(services_info),
                    'running_services': 0,
                    'healthy_services': 0,
                    'failed_services': 0
                }
            }
            
            for service in services_info:
                service_data = asdict(service)
                service_data['status'] = service.status.value  # 轉換枚舉為字串
                status['services'].append(service_data)
                
                if service.status == ServiceStatus.RUNNING:
                    status['summary']['running_services'] += 1
                elif service.status == ServiceStatus.HEALTHY:
                    status['summary']['healthy_services'] += 1
                elif service.status in [ServiceStatus.FAILED, ServiceStatus.UNHEALTHY]:
                    status['summary']['failed_services'] += 1
            
            return status
            
        except Exception as e:
            self.logger.error(f"獲取部署狀態失敗: {str(e)}", exc_info=True)
            return {'error': str(e), 'timestamp': time.time()}
    
    # === 內部方法 ===
    
    async def _pre_deployment_check(self) -> bool:
        """部署前檢查"""
        try:
            # 檢查Compose檔案存在
            if self.compose_file:
                compose_path = self.project_root / self.compose_file
                if not compose_path.exists():
                    self.logger.error(f"Compose檔案不存在: {compose_path}")
                    return False
            
            # 檢查Docker服務可用性
            result = subprocess.run(['docker', 'info'], capture_output=True, timeout=10)
            if result.returncode != 0:
                self.logger.error("Docker服務不可用")
                return False
            
            # 檢查必要環境變數
            if not os.getenv('DISCORD_TOKEN'):
                self.logger.error("缺少DISCORD_TOKEN環境變數")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"部署前檢查失敗: {str(e)}")
            return False
    
    async def _pull_images(self) -> bool:
        """拉取映像"""
        try:
            self.logger.info("拉取最新映像")
            cmd = self._get_compose_command() + ['pull']
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.project_root
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), 
                timeout=300  # 5分鐘拉取超時
            )
            
            if process.returncode == 0:
                self.logger.info("映像拉取完成")
                return True
            else:
                self.logger.error(f"映像拉取失敗: {stderr.decode()}")
                return False
                
        except asyncio.TimeoutError:
            self.logger.error("映像拉取超時")
            return False
        except Exception as e:
            self.logger.error(f"映像拉取異常: {str(e)}")
            return False
    
    async def _build_images(self) -> bool:
        """建置映像"""
        try:
            self.logger.info("建置應用映像")
            cmd = self._get_compose_command() + ['build']
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.project_root
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=600  # 10分鐘建置超時
            )
            
            if process.returncode == 0:
                self.logger.info("映像建置完成")
                return True
            else:
                self.logger.error(f"映像建置失敗: {stderr.decode()}")
                return False
                
        except asyncio.TimeoutError:
            self.logger.error("映像建置超時")
            return False
        except Exception as e:
            self.logger.error(f"映像建置異常: {str(e)}")
            return False
    
    async def _start_services_internal(self, detach: bool = True) -> bool:
        """內部啟動服務方法"""
        try:
            cmd = self._get_compose_command() + ['up']
            if detach:
                cmd.append('-d')
            
            self.logger.info(f"執行命令: {' '.join(cmd)}")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.project_root
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.deployment_timeout
            )
            
            if process.returncode == 0:
                self.logger.info("服務啟動命令執行成功")
                return True
            else:
                self.logger.error(f"服務啟動失敗: {stderr.decode()}")
                return False
                
        except asyncio.TimeoutError:
            self.logger.error(f"服務啟動超時（{self.deployment_timeout}秒）")
            return False
        except Exception as e:
            self.logger.error(f"服務啟動異常: {str(e)}")
            return False
    
    async def _stop_services_internal(self, timeout: int = 30) -> bool:
        """內部停止服務方法"""
        try:
            cmd = self._get_compose_command() + ['down', '--timeout', str(timeout)]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.project_root
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout + 30  # 額外30秒緩衝
            )
            
            if process.returncode == 0:
                self.logger.info("服務停止完成")
                return True
            else:
                self.logger.error(f"服務停止失敗: {stderr.decode()}")
                return False
                
        except asyncio.TimeoutError:
            self.logger.error("服務停止超時")
            return False
        except Exception as e:
            self.logger.error(f"服務停止異常: {str(e)}")
            return False
    
    async def _wait_for_services(self, max_wait_time: int = 120) -> bool:
        """等待服務啟動完成"""
        self.logger.info(f"等待服務啟動完成（最多{max_wait_time}秒）")
        
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            try:
                services_info = await self._get_services_info()
                
                # 檢查是否有服務失敗
                failed_services = [s for s in services_info if s.status == ServiceStatus.FAILED]
                if failed_services:
                    self.logger.error(f"服務啟動失敗: {[s.name for s in failed_services]}")
                    return False
                
                # 檢查是否所有服務都在運行
                running_services = [s for s in services_info 
                                  if s.status in [ServiceStatus.RUNNING, ServiceStatus.HEALTHY]]
                
                if len(running_services) == len(services_info) and len(services_info) > 0:
                    self.logger.info(f"所有服務啟動完成，耗時 {time.time() - start_time:.1f} 秒")
                    return True
                
                self.logger.debug(f"等待中... {len(running_services)}/{len(services_info)} 服務已啟動")
                await asyncio.sleep(5)
                
            except Exception as e:
                self.logger.warning(f"等待過程中發生錯誤: {str(e)}")
                await asyncio.sleep(5)
        
        self.logger.error(f"等待服務啟動超時（{max_wait_time}秒）")
        return False
    
    async def _comprehensive_health_check(self) -> Tuple[bool, str]:
        """綜合健康檢查"""
        self.logger.info("執行綜合健康檢查")
        
        try:
            # 等待健康檢查穩定
            await asyncio.sleep(10)
            
            health_result = await self.health_check()
            
            if health_result.get('overall_healthy', False):
                healthy_count = health_result['summary']['healthy']
                total_count = health_result['summary']['total']
                return True, f"健康檢查通過 ({healthy_count}/{total_count} 服務健康)"
            else:
                unhealthy_services = []
                for name, info in health_result.get('services', {}).items():
                    if info['status'] not in ['running', 'healthy']:
                        unhealthy_services.append(f"{name}: {info['status']}")
                
                return False, f"健康檢查失敗: {'; '.join(unhealthy_services)}"
                
        except Exception as e:
            return False, f"健康檢查異常: {str(e)}"
    
    async def _get_services_info(self) -> List[ServiceInfo]:
        """獲取服務資訊"""
        try:
            cmd = self._get_compose_command() + ['ps', '--format', 'json']
            
            result = subprocess.run(cmd, capture_output=True, text=True, 
                                  timeout=30, cwd=self.project_root)
            
            if result.returncode != 0:
                self.logger.error(f"獲取服務資訊失敗: {result.stderr}")
                return []
            
            services_info = []
            
            # 解析JSON輸出
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                try:
                    service_data = json.loads(line)
                    
                    # 解析服務狀態
                    state = service_data.get('State', '').lower()
                    health = service_data.get('Health', '').lower()
                    
                    if state == 'running':
                        if health == 'healthy':
                            status = ServiceStatus.HEALTHY
                        elif health == 'unhealthy':
                            status = ServiceStatus.UNHEALTHY
                        else:
                            status = ServiceStatus.RUNNING
                    elif state in ['exited', 'dead']:
                        status = ServiceStatus.FAILED
                    elif state == 'restarting':
                        status = ServiceStatus.STARTING
                    else:
                        status = ServiceStatus.UNKNOWN
                    
                    service_info = ServiceInfo(
                        name=service_data.get('Name', 'unknown'),
                        container_id=service_data.get('ID'),
                        status=status,
                        health_status=health if health else None,
                        ports=service_data.get('Publishers', []),
                        created_at=service_data.get('CreatedAt'),
                        started_at=None,  # 需要額外查詢
                        message=service_data.get('Status', '')
                    )
                    
                    services_info.append(service_info)
                    
                except json.JSONDecodeError as e:
                    self.logger.warning(f"解析服務資訊失敗: {line}, 錯誤: {str(e)}")
                    continue
            
            return services_info
            
        except Exception as e:
            self.logger.error(f"獲取服務資訊異常: {str(e)}")
            return []


# 工廠方法和工具函數

def create_deployment_manager(environment: str = 'dev', project_root: Optional[Path] = None) -> DeploymentManager:
    """
    創建部署管理器實例
    
    Args:
        environment: 環境類型 (dev, prod)
        project_root: 專案根目錄
        
    Returns:
        DeploymentManager: 部署管理器實例
    """
    if project_root is None:
        project_root = Path.cwd()
    
    compose_file_map = {
        'dev': 'docker-compose.dev.yml',
        'development': 'docker-compose.dev.yml',
        'simple': 'docker-compose.simple.yml',  # 新增簡化配置
        'prod': 'docker-compose.prod.yml',
        'production': 'docker-compose.prod.yml'
    }
    
    compose_file = compose_file_map.get(environment, 'docker-compose.dev.yml')
    
    return DeploymentManager(project_root=project_root, compose_file=compose_file)


async def quick_deployment_check(environment: str = 'dev') -> Dict[str, Any]:
    """
    快速部署狀態檢查
    
    Args:
        environment: 環境類型
        
    Returns:
        Dict[str, Any]: 檢查結果
    """
    manager = create_deployment_manager(environment)
    return await manager.health_check()


# 命令行介面
async def main():
    """主函數 - 用於獨立執行部署管理"""
    import argparse
    
    parser = argparse.ArgumentParser(description='ROAS Bot 部署管理工具')
    parser.add_argument('command', choices=['start', 'stop', 'restart', 'status', 'health', 'logs'],
                       help='執行的命令')
    parser.add_argument('--environment', '-e', default='dev', choices=['dev', 'prod'],
                       help='部署環境')
    parser.add_argument('--service', '-s', help='指定服務名稱（僅用於logs命令）')
    parser.add_argument('--follow', '-f', action='store_true', help='跟蹤日誌（僅用於logs命令）')
    parser.add_argument('--verbose', '-v', action='store_true', help='詳細輸出')
    
    args = parser.parse_args()
    
    # 設置日誌
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # 創建部署管理器
    manager = create_deployment_manager(args.environment)
    
    # 執行命令
    try:
        if args.command == 'start':
            success, message = await manager.start_services()
            print(f"{'✅' if success else '❌'} {message}")
            return 0 if success else 1
            
        elif args.command == 'stop':
            success, message = await manager.stop_services()
            print(f"{'✅' if success else '❌'} {message}")
            return 0 if success else 1
            
        elif args.command == 'restart':
            success, message = await manager.restart_services()
            print(f"{'✅' if success else '❌'} {message}")
            return 0 if success else 1
            
        elif args.command == 'status':
            status = await manager.get_deployment_status()
            print(json.dumps(status, indent=2, ensure_ascii=False))
            return 0
            
        elif args.command == 'health':
            health = await manager.health_check()
            print(f"整體狀態: {'✅ 健康' if health['overall_healthy'] else '❌ 異常'}")
            print(f"服務統計: {health['summary']}")
            for name, info in health.get('services', {}).items():
                status_icon = '✅' if info['status'] in ['running', 'healthy'] else '❌'
                print(f"  {status_icon} {name}: {info['status']}")
            return 0 if health['overall_healthy'] else 1
            
        elif args.command == 'logs':
            logs = await manager.get_service_logs(args.service, follow=args.follow)
            print(logs)
            return 0
            
    except KeyboardInterrupt:
        print("\n操作已取消")
        return 130
    except Exception as e:
        print(f"❌ 執行失敗: {str(e)}")
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(asyncio.run(main()))