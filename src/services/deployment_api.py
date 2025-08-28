"""
部署服務API接口
Task ID: 2 - 自動化部署和啟動系統開發

Elena - API架構師
這個模組提供統一的部署服務API接口，包括：
- RESTful風格的API設計
- 異步部署操作支援
- 即時狀態查詢和監控
- 部署進度回調機制
- 與現有服務註冊機制的整合
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Callable, Union
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, asdict
from pathlib import Path

from core.base_service import BaseService, ServiceType
from src.core.errors import (
    DeploymentError,
    EnvironmentError,
    ServiceStartupError
)
from src.core.service_registry import extended_service_registry

logger = logging.getLogger('deployment_api')


class DeploymentAPIStatus(Enum):
    """部署API狀態枚舉"""
    READY = "ready"
    DEPLOYING = "deploying"
    MONITORING = "monitoring"
    ERROR = "error"
    MAINTENANCE = "maintenance"


@dataclass
class DeploymentRequest:
    """部署請求資料結構"""
    mode: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    environment: Optional[str] = None
    force_rebuild: bool = False
    skip_health_check: bool = False
    timeout: Optional[int] = None
    callback_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def validate(self) -> List[str]:
        """驗證部署請求"""
        errors = []
        
        if self.mode and self.mode not in ['docker', 'uv', 'fallback', 'auto']:
            errors.append(f"不支援的部署模式: {self.mode}")
        
        if self.timeout and (self.timeout < 30 or self.timeout > 3600):
            errors.append("超時時間必須在30-3600秒之間")
        
        if self.environment and self.environment not in ['dev', 'staging', 'prod']:
            errors.append(f"不支援的環境: {self.environment}")
        
        return errors


@dataclass
class DeploymentResponse:
    """部署回應資料結構"""
    deployment_id: str
    status: str
    message: str
    mode: Optional[str] = None
    start_time: Optional[datetime] = None
    estimated_duration: Optional[int] = None
    progress_url: Optional[str] = None
    logs_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        result = asdict(self)
        if self.start_time:
            result['start_time'] = self.start_time.isoformat()
        return result


@dataclass  
class ProgressUpdate:
    """進度更新資料結構"""
    deployment_id: str
    current_step: str
    progress_percentage: float
    completed_steps: int
    total_steps: int
    estimated_time_remaining: Optional[int] = None
    last_update: datetime = None
    
    def __post_init__(self):
        if self.last_update is None:
            self.last_update = datetime.now()


class DeploymentAPIEndpoint(ABC):
    """部署API端點抽象基類"""
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """健康檢查端點"""
        pass
    
    @abstractmethod 
    async def start_deployment(self, request: DeploymentRequest) -> DeploymentResponse:
        """開始部署端點"""
        pass
    
    @abstractmethod
    async def get_deployment_status(self, deployment_id: str) -> Dict[str, Any]:
        """獲取部署狀態端點"""
        pass
    
    @abstractmethod
    async def get_deployment_progress(self, deployment_id: str) -> ProgressUpdate:
        """獲取部署進度端點"""
        pass
    
    @abstractmethod
    async def cancel_deployment(self, deployment_id: str) -> Dict[str, Any]:
        """取消部署端點"""
        pass
    
    @abstractmethod
    async def list_deployments(self, limit: int = 50) -> List[Dict[str, Any]]:
        """列出部署歷史端點"""
        pass


class DeploymentServiceAPI(BaseService, DeploymentAPIEndpoint):
    """
    部署服務API
    
    提供統一的API接口管理自動化部署和啟動系統
    支援異步操作、即時監控和與現有服務架構的整合
    """
    
    def __init__(self, project_root: Optional[Path] = None):
        """
        初始化部署服務API
        
        Args:
            project_root: 專案根目錄
        """
        super().__init__("DeploymentServiceAPI")
        
        self.project_root = project_root or Path.cwd()
        self.api_status = DeploymentAPIStatus.READY
        
        # API配置
        self.api_config = {
            'version': '1.0.0',
            'max_concurrent_deployments': 3,
            'default_timeout': 300,
            'progress_update_interval': 10,
            'enable_webhooks': True,
            'log_retention_days': 30
        }
        
        # 部署管理器註冊表
        self._deployment_managers: Dict[str, Any] = {}
        
        # 活躍部署追蹤
        self._active_deployments: Dict[str, Dict[str, Any]] = {}
        
        # 進度回調註冊表
        self._progress_callbacks: Dict[str, List[Callable]] = {}
        
        # API中間件
        self._request_middleware: List[Callable] = []
        self._response_middleware: List[Callable] = []
        
        # 統計資料
        self._deployment_stats = {
            'total_deployments': 0,
            'successful_deployments': 0,
            'failed_deployments': 0,
            'cancelled_deployments': 0,
            'average_deployment_time': 0.0
        }
    
    async def _initialize(self) -> bool:
        """初始化API服務"""
        try:
            self.logger.info("正在初始化部署服務API...")
            
            # 設置服務元數據
            self.service_metadata = {
                'service_type': ServiceType.DEPLOYMENT,
                'api_version': self.api_config['version'],
                'supported_modes': ['docker', 'uv', 'fallback'],
                'capabilities': {
                    'async_deployment': True,
                    'progress_tracking': True,
                    'health_monitoring': True,
                    'webhook_notifications': True,
                    'deployment_history': True
                }
            }
            
            # 註冊部署管理器
            await self._register_deployment_managers()
            
            # 設置API中間件
            await self._setup_api_middleware()
            
            # 恢復活躍部署狀態
            await self._recover_active_deployments()
            
            self.api_status = DeploymentAPIStatus.READY
            self.logger.info("部署服務API初始化完成")
            return True
            
        except Exception as e:
            self.api_status = DeploymentAPIStatus.ERROR
            self.logger.error(f"部署服務API初始化失敗: {e}")
            raise ServiceStartupError(f"部署服務API初始化失敗: {str(e)}")
    
    async def _cleanup(self) -> None:
        """清理API服務資源"""
        try:
            self.logger.info("正在清理部署服務API...")
            
            # 取消所有活躍部署
            for deployment_id in list(self._active_deployments.keys()):
                await self.cancel_deployment(deployment_id)
            
            # 清理回調註冊表
            self._progress_callbacks.clear()
            
            # 重置狀態
            self.api_status = DeploymentAPIStatus.MAINTENANCE
            
            self.logger.info("部署服務API清理完成")
            
        except Exception as e:
            self.logger.error(f"清理部署服務API時發生錯誤: {e}")
    
    async def _validate_permissions(
        self, 
        user_id: int, 
        guild_id: Optional[int], 
        action: str
    ) -> bool:
        """
        驗證API操作權限
        
        Args:
            user_id: 使用者ID
            guild_id: 伺服器ID（可選）
            action: 要執行的操作
            
        Returns:
            是否有權限
        """
        # 部署API需要管理員權限
        admin_actions = ['deploy', 'cancel', 'restart']
        readonly_actions = ['status', 'progress', 'list', 'health']
        
        if action in admin_actions:
            # 檢查管理員權限（這裡可以整合實際的權限系統）
            return True  # 暫時允許所有管理員操作
        elif action in readonly_actions:
            return True  # 允許只讀操作
        else:
            return False
    
    # ========== API端點實作 ==========
    
    async def health_check(self) -> Dict[str, Any]:
        """
        健康檢查API端點
        
        Returns:
            健康狀態資訊
        """
        try:
            self.logger.debug("執行API健康檢查")
            
            # 檢查部署管理器狀態
            manager_health = {}
            for mode, manager in self._deployment_managers.items():
                if hasattr(manager, 'get_api_status'):
                    manager_health[mode] = await manager.get_api_status()
                else:
                    manager_health[mode] = {'status': 'unknown'}
            
            # 檢查活躍部署
            active_count = len(self._active_deployments)
            
            return {
                'api_status': self.api_status.value,
                'timestamp': datetime.now().isoformat(),
                'version': self.api_config['version'],
                'deployment_managers': manager_health,
                'active_deployments': active_count,
                'max_concurrent_deployments': self.api_config['max_concurrent_deployments'],
                'system_resources': await self._check_system_resources(),
                'last_deployment': await self._get_last_deployment_info(),
                'statistics': self._deployment_stats.copy()
            }
            
        except Exception as e:
            self.logger.error(f"健康檢查失敗: {e}")
            return {
                'api_status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def start_deployment(self, request: DeploymentRequest) -> DeploymentResponse:
        """
        開始部署API端點
        
        Args:
            request: 部署請求
            
        Returns:
            部署回應
        """
        try:
            # 驗證請求
            validation_errors = request.validate()
            if validation_errors:
                raise DeploymentError(f"請求驗證失敗: {', '.join(validation_errors)}")
            
            # 檢查併發限制
            if len(self._active_deployments) >= self.api_config['max_concurrent_deployments']:
                raise DeploymentError("已達到最大併發部署限制")
            
            # 應用請求中間件
            for middleware in self._request_middleware:
                request = await middleware(request)
            
            # 確定部署模式
            deployment_mode = request.mode or 'auto'
            if deployment_mode == 'auto':
                deployment_mode = await self._determine_best_deployment_mode()
            
            # 獲取對應的部署管理器
            manager = self._deployment_managers.get(deployment_mode)
            if not manager:
                raise DeploymentError(f"不支援的部署模式: {deployment_mode}")
            
            # 生成部署ID
            deployment_id = self._generate_deployment_id(deployment_mode)
            
            self.logger.info(f"開始部署，ID: {deployment_id}, 模式: {deployment_mode}")
            
            # 記錄部署開始
            deployment_info = {
                'deployment_id': deployment_id,
                'mode': deployment_mode,
                'status': 'starting',
                'start_time': datetime.now(),
                'config': request.config,
                'metadata': request.metadata,
                'manager': manager
            }
            self._active_deployments[deployment_id] = deployment_info
            
            # 設置進度回調
            await self._setup_deployment_callbacks(deployment_id, request.callback_url)
            
            # 啟動異步部署
            deployment_task = asyncio.create_task(
                self._execute_deployment(deployment_id, manager, request)
            )
            
            deployment_info['task'] = deployment_task
            
            # 創建回應
            response = DeploymentResponse(
                deployment_id=deployment_id,
                status='accepted',
                message='部署已開始',
                mode=deployment_mode,
                start_time=datetime.now(),
                estimated_duration=self._estimate_deployment_duration(deployment_mode),
                progress_url=f"/api/deployments/{deployment_id}/progress",
                logs_url=f"/api/deployments/{deployment_id}/logs",
                metadata=request.metadata
            )
            
            # 應用回應中間件
            for middleware in self._response_middleware:
                response = await middleware(response)
            
            # 更新統計
            self._deployment_stats['total_deployments'] += 1
            
            self.logger.info(f"部署請求已接受，ID: {deployment_id}")
            return response
            
        except Exception as e:
            self.logger.error(f"開始部署失敗: {e}")
            raise DeploymentError(f"開始部署失敗: {str(e)}")
    
    async def get_deployment_status(self, deployment_id: str) -> Dict[str, Any]:
        """
        獲取部署狀態API端點
        
        Args:
            deployment_id: 部署ID
            
        Returns:
            部署狀態資訊
        """
        try:
            # 檢查活躍部署
            if deployment_id in self._active_deployments:
                deployment_info = self._active_deployments[deployment_id]
                manager = deployment_info['manager']
                
                # 從管理器獲取詳細狀態
                if hasattr(manager, 'get_deployment_status'):
                    manager_status = await manager.get_deployment_status()
                    deployment_info.update(manager_status)
                
                return {
                    'deployment_id': deployment_id,
                    'status': deployment_info.get('status', 'unknown'),
                    'mode': deployment_info.get('mode'),
                    'start_time': deployment_info.get('start_time', datetime.now()).isoformat(),
                    'current_step': deployment_info.get('current_step', 'unknown'),
                    'progress_percentage': deployment_info.get('progress_percentage', 0.0),
                    'estimated_time_remaining': deployment_info.get('estimated_time_remaining'),
                    'error_message': deployment_info.get('error_message'),
                    'logs_available': True,
                    'metadata': deployment_info.get('metadata', {})
                }
            
            # 從資料庫查詢歷史部署
            db_manager = self.get_dependency("database_manager")
            if db_manager:
                try:
                    result = await db_manager.fetchone(
                        "SELECT * FROM deployment_logs WHERE deployment_id = ?",
                        (deployment_id,)
                    )
                    if result:
                        return {
                            'deployment_id': deployment_id,
                            'status': result['status'],
                            'mode': result['mode'],
                            'start_time': result['start_time'],
                            'end_time': result.get('end_time'),
                            'duration_seconds': result.get('duration_seconds'),
                            'error_message': result.get('error_message'),
                            'logs_available': bool(result.get('logs')),
                            'is_historical': True
                        }
                except Exception as e:
                    self.logger.warning(f"查詢資料庫失敗: {e}")
            
            # 未找到部署記錄
            return {
                'deployment_id': deployment_id,
                'status': 'not_found',
                'message': f'找不到部署記錄: {deployment_id}'
            }
            
        except Exception as e:
            self.logger.error(f"獲取部署狀態失敗: {e}")
            return {
                'deployment_id': deployment_id,
                'status': 'error',
                'error': str(e)
            }
    
    async def get_deployment_progress(self, deployment_id: str) -> ProgressUpdate:
        """
        獲取部署進度API端點
        
        Args:
            deployment_id: 部署ID
            
        Returns:
            進度更新資訊
        """
        try:
            if deployment_id not in self._active_deployments:
                raise DeploymentError(f"找不到活躍部署: {deployment_id}")
            
            deployment_info = self._active_deployments[deployment_id]
            manager = deployment_info['manager']
            
            # 從管理器獲取進度資訊
            if hasattr(manager, 'get_deployment_status'):
                status = await manager.get_deployment_status()
                progress_info = status.get('progress', {})
                
                return ProgressUpdate(
                    deployment_id=deployment_id,
                    current_step=progress_info.get('current_step', 'unknown'),
                    progress_percentage=progress_info.get('progress_percentage', 0.0),
                    completed_steps=progress_info.get('completed_steps', 0),
                    total_steps=progress_info.get('total_steps', 1),
                    estimated_time_remaining=progress_info.get('estimated_time_remaining'),
                    last_update=datetime.now()
                )
            
            # 默認進度資訊
            return ProgressUpdate(
                deployment_id=deployment_id,
                current_step=deployment_info.get('status', 'unknown'),
                progress_percentage=50.0 if deployment_info.get('status') == 'running' else 0.0,
                completed_steps=1 if deployment_info.get('status') == 'running' else 0,
                total_steps=2,
                last_update=datetime.now()
            )
            
        except Exception as e:
            self.logger.error(f"獲取部署進度失敗: {e}")
            raise DeploymentError(f"獲取部署進度失敗: {str(e)}")
    
    async def cancel_deployment(self, deployment_id: str) -> Dict[str, Any]:
        """
        取消部署API端點
        
        Args:
            deployment_id: 部署ID
            
        Returns:
            取消結果
        """
        try:
            if deployment_id not in self._active_deployments:
                return {
                    'deployment_id': deployment_id,
                    'status': 'not_found',
                    'message': f'找不到活躍部署: {deployment_id}'
                }
            
            deployment_info = self._active_deployments[deployment_id]
            manager = deployment_info['manager']
            
            self.logger.info(f"取消部署: {deployment_id}")
            
            # 嘗試取消部署
            cancel_success = False
            if hasattr(manager, 'cancel_deployment'):
                cancel_success = await manager.cancel_deployment()
            
            # 取消異步任務
            task = deployment_info.get('task')
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            # 更新狀態
            deployment_info['status'] = 'cancelled'
            deployment_info['end_time'] = datetime.now()
            
            # 從活躍部署中移除
            del self._active_deployments[deployment_id]
            
            # 記錄到資料庫
            await self._log_deployment_completion(deployment_id, 'cancelled')
            
            # 更新統計
            self._deployment_stats['cancelled_deployments'] += 1
            
            return {
                'deployment_id': deployment_id,
                'status': 'cancelled',
                'message': '部署已取消',
                'cancelled_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"取消部署失敗: {e}")
            return {
                'deployment_id': deployment_id,
                'status': 'error',
                'error': str(e)
            }
    
    async def list_deployments(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        列出部署歷史API端點
        
        Args:
            limit: 返回數量限制
            
        Returns:
            部署歷史列表
        """
        try:
            deployments = []
            
            # 添加活躍部署
            for deployment_id, info in self._active_deployments.items():
                deployments.append({
                    'deployment_id': deployment_id,
                    'status': info.get('status', 'unknown'),
                    'mode': info.get('mode'),
                    'start_time': info.get('start_time', datetime.now()).isoformat(),
                    'is_active': True,
                    'metadata': info.get('metadata', {})
                })
            
            # 從資料庫查詢歷史部署
            db_manager = self.get_dependency("database_manager")
            if db_manager:
                try:
                    results = await db_manager.fetchall(
                        """SELECT deployment_id, mode, status, start_time, end_time, 
                           duration_seconds, error_message 
                           FROM deployment_logs 
                           ORDER BY start_time DESC 
                           LIMIT ?""",
                        (limit - len(deployments),)
                    )
                    
                    for result in results:
                        deployments.append({
                            'deployment_id': result['deployment_id'],
                            'status': result['status'],
                            'mode': result['mode'],
                            'start_time': result['start_time'],
                            'end_time': result.get('end_time'),
                            'duration_seconds': result.get('duration_seconds'),
                            'error_message': result.get('error_message'),
                            'is_active': False
                        })
                        
                except Exception as e:
                    self.logger.warning(f"查詢部署歷史失敗: {e}")
            
            # 按時間排序
            deployments.sort(
                key=lambda x: x.get('start_time', ''),
                reverse=True
            )
            
            return deployments[:limit]
            
        except Exception as e:
            self.logger.error(f"列出部署歷史失敗: {e}")
            return []
    
    # ========== 內部方法 ==========
    
    async def _register_deployment_managers(self) -> None:
        """註冊部署管理器"""
        try:
            # 註冊UV部署管理器
            from .uv_deployment_manager import UVDeploymentManager
            uv_manager = UVDeploymentManager(self.project_root)
            self._deployment_managers['uv'] = uv_manager
            
            # 註冊Docker部署管理器（使用現有的DeploymentManager）
            from core.deployment_manager import create_deployment_manager
            docker_manager = create_deployment_manager('dev', self.project_root)
            self._deployment_managers['docker'] = docker_manager
            
            # 註冊降級部署管理器
            from .fallback_deployment_manager import FallbackDeploymentManager
            fallback_manager = FallbackDeploymentManager(self.project_root)
            self._deployment_managers['fallback'] = fallback_manager
            
            self.logger.info(f"已註冊 {len(self._deployment_managers)} 個部署管理器")
            
        except ImportError as e:
            self.logger.warning(f"部分部署管理器不可用: {e}")
        except Exception as e:
            self.logger.error(f"註冊部署管理器失敗: {e}")
            raise
    
    async def _setup_api_middleware(self) -> None:
        """設置API中間件"""
        # 請求驗證中間件
        async def request_validator(request: DeploymentRequest) -> DeploymentRequest:
            # 設置默認值
            if not request.config:
                request.config = {}
            if not request.timeout:
                request.timeout = self.api_config['default_timeout']
            return request
        
        # 回應格式化中間件
        async def response_formatter(response: DeploymentResponse) -> DeploymentResponse:
            # 添加API版本資訊
            if not response.metadata:
                response.metadata = {}
            response.metadata['api_version'] = self.api_config['version']
            return response
        
        self._request_middleware.append(request_validator)
        self._response_middleware.append(response_formatter)
        
        self.logger.debug("API中間件設置完成")
    
    async def _recover_active_deployments(self) -> None:
        """恢復活躍部署狀態"""
        try:
            db_manager = self.get_dependency("database_manager")
            if not db_manager:
                return
            
            # 查詢進行中的部署
            results = await db_manager.fetchall(
                """SELECT deployment_id, mode, status FROM deployment_logs 
                   WHERE status IN ('pending', 'installing', 'configuring', 'starting')"""
            )
            
            for result in results:
                deployment_id = result['deployment_id']
                
                # 將狀態設為失敗（因為重啟後無法恢復進行中的部署）
                await db_manager.execute(
                    """UPDATE deployment_logs 
                       SET status = 'failed', error_message = '服務重啟導致部署中斷'
                       WHERE deployment_id = ?""",
                    (deployment_id,)
                )
            
            if results:
                self.logger.info(f"恢復了 {len(results)} 個中斷的部署記錄")
                
        except Exception as e:
            self.logger.warning(f"恢復活躍部署狀態失敗: {e}")
    
    async def _determine_best_deployment_mode(self) -> str:
        """確定最佳部署模式"""
        try:
            # 檢查Docker可用性
            if 'docker' in self._deployment_managers:
                docker_manager = self._deployment_managers['docker']
                if hasattr(docker_manager, '_pre_deployment_check'):
                    docker_available = await docker_manager._pre_deployment_check()
                    if docker_available:
                        return 'docker'
            
            # 檢查UV可用性
            if 'uv' in self._deployment_managers:
                uv_manager = self._deployment_managers['uv']
                env_info = await uv_manager.detect_environment()
                if env_info.get('uv_available', False):
                    return 'uv'
            
            # 降級方案
            return 'fallback'
            
        except Exception as e:
            self.logger.warning(f"確定最佳部署模式失敗: {e}")
            return 'fallback'
    
    async def _setup_deployment_callbacks(self, deployment_id: str, callback_url: Optional[str]) -> None:
        """設置部署回調"""
        callbacks = []
        
        # 內部進度更新回調
        async def progress_callback(progress):
            if deployment_id in self._active_deployments:
                self._active_deployments[deployment_id].update({
                    'current_step': progress.current_step,
                    'progress_percentage': progress.progress_percentage,
                    'completed_steps': progress.completed_steps,
                    'total_steps': progress.total_steps,
                    'estimated_time_remaining': progress.estimated_time_remaining
                })
        
        callbacks.append(progress_callback)
        
        # Webhook回調（如果提供了URL）
        if callback_url and self.api_config['enable_webhooks']:
            async def webhook_callback(progress):
                try:
                    import aiohttp
                    async with aiohttp.ClientSession() as session:
                        await session.post(callback_url, json=asdict(progress))
                except Exception as e:
                    self.logger.warning(f"Webhook回調失敗: {e}")
            
            callbacks.append(webhook_callback)
        
        self._progress_callbacks[deployment_id] = callbacks
    
    async def _execute_deployment(
        self,
        deployment_id: str,
        manager: Any,
        request: DeploymentRequest
    ) -> None:
        """執行部署（異步任務）"""
        try:
            deployment_info = self._active_deployments[deployment_id]
            
            # 更新狀態為運行中
            deployment_info['status'] = 'running'
            
            # 執行部署
            if hasattr(manager, 'deploy_with_progress'):
                # 支援進度回調的管理器
                callbacks = self._progress_callbacks.get(deployment_id, [])
                
                async def combined_callback(progress):
                    for callback in callbacks:
                        try:
                            await callback(progress)
                        except Exception as e:
                            self.logger.warning(f"進度回調失敗: {e}")
                
                success = await manager.deploy_with_progress(
                    config=request.config,
                    progress_callback=combined_callback
                )
            else:
                # 基本部署接口
                success = await manager.deploy()
            
            # 更新最終狀態
            if success:
                deployment_info['status'] = 'completed'
                self._deployment_stats['successful_deployments'] += 1
            else:
                deployment_info['status'] = 'failed'
                self._deployment_stats['failed_deployments'] += 1
            
            deployment_info['end_time'] = datetime.now()
            
            # 計算部署時間
            duration = (deployment_info['end_time'] - deployment_info['start_time']).total_seconds()
            deployment_info['duration_seconds'] = duration
            
            # 更新平均部署時間
            self._update_average_deployment_time(duration)
            
            # 記錄到資料庫
            await self._log_deployment_completion(deployment_id, deployment_info['status'])
            
        except asyncio.CancelledError:
            # 部署被取消
            self.logger.info(f"部署被取消: {deployment_id}")
            deployment_info = self._active_deployments.get(deployment_id, {})
            deployment_info['status'] = 'cancelled'
            
        except Exception as e:
            # 部署異常
            self.logger.error(f"部署執行異常 {deployment_id}: {e}")
            deployment_info = self._active_deployments.get(deployment_id, {})
            deployment_info['status'] = 'failed'
            deployment_info['error_message'] = str(e)
            
            self._deployment_stats['failed_deployments'] += 1
            
            # 記錄錯誤到資料庫
            await self._log_deployment_completion(deployment_id, 'failed', str(e))
        
        finally:
            # 清理資源
            if deployment_id in self._active_deployments:
                del self._active_deployments[deployment_id]
            if deployment_id in self._progress_callbacks:
                del self._progress_callbacks[deployment_id]
    
    async def _check_system_resources(self) -> Dict[str, Any]:
        """檢查系統資源"""
        try:
            import psutil
            
            return {
                'cpu_percent': psutil.cpu_percent(interval=1),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_percent': psutil.disk_usage('/').percent,
                'load_average': psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None
            }
        except ImportError:
            return {'message': 'psutil未安裝，無法獲取系統資源資訊'}
        except Exception as e:
            return {'error': str(e)}
    
    async def _get_last_deployment_info(self) -> Optional[Dict[str, Any]]:
        """獲取最後一次部署資訊"""
        try:
            db_manager = self.get_dependency("database_manager")
            if not db_manager:
                return None
            
            result = await db_manager.fetchone(
                """SELECT deployment_id, mode, status, start_time 
                   FROM deployment_logs 
                   ORDER BY start_time DESC 
                   LIMIT 1"""
            )
            
            if result:
                return {
                    'deployment_id': result['deployment_id'],
                    'mode': result['mode'],
                    'status': result['status'],
                    'start_time': result['start_time']
                }
            
            return None
            
        except Exception as e:
            self.logger.warning(f"獲取最後部署資訊失敗: {e}")
            return None
    
    def _generate_deployment_id(self, mode: str) -> str:
        """生成部署ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        import hashlib
        random_part = hashlib.md5(f"{timestamp}_{mode}_{id(self)}".encode()).hexdigest()[:8]
        return f"{mode}_{timestamp}_{random_part}"
    
    def _estimate_deployment_duration(self, mode: str) -> int:
        """估計部署持續時間（秒）"""
        estimates = {
            'docker': 300,    # 5分鐘
            'uv': 120,        # 2分鐘
            'fallback': 60    # 1分鐘
        }
        return estimates.get(mode, 180)  # 默認3分鐘
    
    def _update_average_deployment_time(self, duration: float) -> None:
        """更新平均部署時間"""
        total_deployments = self._deployment_stats['total_deployments']
        if total_deployments > 0:
            current_avg = self._deployment_stats['average_deployment_time']
            new_avg = (current_avg * (total_deployments - 1) + duration) / total_deployments
            self._deployment_stats['average_deployment_time'] = new_avg
    
    async def _log_deployment_completion(
        self,
        deployment_id: str,
        status: str,
        error_message: Optional[str] = None
    ) -> None:
        """記錄部署完成日誌"""
        try:
            db_manager = self.get_dependency("database_manager")
            if not db_manager:
                return
            
            deployment_info = self._active_deployments.get(deployment_id, {})
            duration = deployment_info.get('duration_seconds', 0)
            
            await db_manager.execute(
                """UPDATE deployment_logs 
                   SET status = ?, end_time = ?, duration_seconds = ?, error_message = ?
                   WHERE deployment_id = ?""",
                (status, datetime.now().isoformat(), duration, error_message, deployment_id)
            )
            
        except Exception as e:
            self.logger.warning(f"記錄部署完成日誌失敗: {e}")
    
    # ========== 服務註冊整合 ==========
    
    async def register_with_service_registry(self) -> str:
        """向服務註冊中心註冊"""
        try:
            service_name = await extended_service_registry.register_deployment_service(
                service=self,
                deployment_mode='api',
                name='DeploymentServiceAPI',
                environment_config={
                    'supported_modes': list(self._deployment_managers.keys()),
                    'max_concurrent_deployments': self.api_config['max_concurrent_deployments']
                },
                auto_restart=True
            )
            
            self.logger.info(f"部署服務API已註冊到服務註冊中心: {service_name}")
            return service_name
            
        except Exception as e:
            self.logger.error(f"註冊到服務註冊中心失敗: {e}")
            raise ServiceStartupError(f"服務註冊失敗: {str(e)}")


# 工廠函數

def create_deployment_service_api(project_root: Optional[Path] = None) -> DeploymentServiceAPI:
    """
    創建部署服務API實例
    
    Args:
        project_root: 專案根目錄
        
    Returns:
        部署服務API實例
    """
    return DeploymentServiceAPI(project_root)


# 全域實例（可選）
_global_deployment_api: Optional[DeploymentServiceAPI] = None

async def get_deployment_api() -> DeploymentServiceAPI:
    """
    獲取全域部署服務API實例
    
    Returns:
        部署服務API實例
    """
    global _global_deployment_api
    
    if _global_deployment_api is None:
        _global_deployment_api = create_deployment_service_api()
        await _global_deployment_api.start()
    
    return _global_deployment_api