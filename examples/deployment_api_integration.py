#!/usr/bin/env python3
"""
部署服務API整合範例
Task ID: 2 - 自動化部署和啟動系統開發

Elena - API架構師
這個範例展示如何在實際應用中整合和使用部署服務API
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional

# 導入部署服務API
from src.services.deployment_api import (
    DeploymentServiceAPI,
    DeploymentRequest,
    DeploymentResponse,
    create_deployment_service_api,
    get_deployment_api
)
from src.services.uv_deployment_manager import UVDeploymentManager
from src.services.fallback_deployment_manager import FallbackDeploymentManager
from src.core.service_registry import extended_service_registry
from src.core.errors import DeploymentError, EnvironmentError

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ROASBotDeploymentController:
    """
    ROAS Bot部署控制器
    
    這個類別展示如何整合部署服務API到實際的應用中
    """
    
    def __init__(self, project_root: Optional[Path] = None):
        """
        初始化部署控制器
        
        Args:
            project_root: 專案根目錄
        """
        self.project_root = project_root or Path.cwd()
        self.deployment_api: Optional[DeploymentServiceAPI] = None
        self.active_deployments: Dict[str, Dict[str, Any]] = {}
        
    async def initialize(self) -> bool:
        """
        初始化部署控制器
        
        Returns:
            初始化是否成功
        """
        try:
            logger.info("初始化ROAS Bot部署控制器...")
            
            # 創建部署API實例
            self.deployment_api = create_deployment_service_api(self.project_root)
            await self.deployment_api.start()
            
            # 註冊到服務註冊中心
            service_name = await self.deployment_api.register_with_service_registry()
            logger.info(f"部署API已註冊到服務註冊中心: {service_name}")
            
            # 檢查API健康狀態
            health = await self.deployment_api.health_check()
            logger.info(f"部署API健康狀態: {health['api_status']}")
            
            # 顯示可用的部署管理器
            managers = health['deployment_managers']
            logger.info("可用的部署管理器:")
            for mode, status in managers.items():
                logger.info(f"  - {mode}: {status.get('status', 'unknown')}")
            
            logger.info("部署控制器初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"初始化部署控制器失敗: {e}")
            return False
    
    async def deploy_bot(
        self,
        mode: Optional[str] = None,
        environment: str = 'dev',
        config: Optional[Dict[str, Any]] = None,
        user_id: int = 0
    ) -> Optional[str]:
        """
        部署ROAS Bot
        
        Args:
            mode: 部署模式 ('docker', 'uv', 'fallback', 'auto')
            environment: 環境 ('dev', 'staging', 'prod')
            config: 額外配置
            user_id: 發起部署的用戶ID
            
        Returns:
            部署ID或None（如果失敗）
        """
        try:
            logger.info(f"開始部署ROAS Bot，模式: {mode or 'auto'}，環境: {environment}")
            
            # 檢查權限（模擬）
            if not await self._check_deployment_permission(user_id):
                logger.error(f"用戶 {user_id} 沒有部署權限")
                return None
            
            # 準備部署配置
            deployment_config = await self._prepare_deployment_config(environment, config)
            
            # 創建部署請求
            request = DeploymentRequest(
                mode=mode or 'auto',
                config=deployment_config,
                environment=environment,
                timeout=600,  # 10分鐘
                force_rebuild=environment == 'prod',  # 生產環境強制重建
                callback_url=await self._get_webhook_url(),
                metadata={
                    'initiated_by': f'user_{user_id}',
                    'environment': environment,
                    'timestamp': asyncio.get_event_loop().time()
                }
            )
            
            # 提交部署
            response = await self.deployment_api.start_deployment(request)
            deployment_id = response.deployment_id
            
            # 記錄部署資訊
            self.active_deployments[deployment_id] = {
                'user_id': user_id,
                'environment': environment,
                'mode': response.mode,
                'start_time': response.start_time,
                'status': 'running'
            }
            
            logger.info(f"部署已開始，ID: {deployment_id}")
            
            # 啟動監控任務
            asyncio.create_task(self._monitor_deployment(deployment_id))
            
            return deployment_id
            
        except DeploymentError as e:
            logger.error(f"部署失敗: {e}")
            return None
        except Exception as e:
            logger.error(f"部署過程中發生未知錯誤: {e}")
            return None
    
    async def get_deployment_status(self, deployment_id: str) -> Optional[Dict[str, Any]]:
        """
        獲取部署狀態
        
        Args:
            deployment_id: 部署ID
            
        Returns:
            部署狀態資訊
        """
        try:
            status = await self.deployment_api.get_deployment_status(deployment_id)
            
            # 豐富狀態資訊
            if deployment_id in self.active_deployments:
                local_info = self.active_deployments[deployment_id]
                status.update({
                    'initiated_by': f"user_{local_info['user_id']}",
                    'environment': local_info['environment']
                })
            
            return status
            
        except Exception as e:
            logger.error(f"獲取部署狀態失敗: {e}")
            return None
    
    async def cancel_deployment(self, deployment_id: str, user_id: int) -> bool:
        """
        取消部署
        
        Args:
            deployment_id: 部署ID
            user_id: 發起取消的用戶ID
            
        Returns:
            取消是否成功
        """
        try:
            # 檢查權限
            if not await self._check_deployment_permission(user_id):
                logger.error(f"用戶 {user_id} 沒有取消部署的權限")
                return False
            
            # 檢查是否是部署發起者
            if deployment_id in self.active_deployments:
                initiator_id = self.active_deployments[deployment_id]['user_id']
                if user_id != initiator_id and not await self._is_admin_user(user_id):
                    logger.error(f"用戶 {user_id} 不能取消其他用戶的部署")
                    return False
            
            # 取消部署
            result = await self.deployment_api.cancel_deployment(deployment_id)
            
            if result['status'] == 'cancelled':
                logger.info(f"部署 {deployment_id} 已被用戶 {user_id} 取消")
                
                # 更新本地記錄
                if deployment_id in self.active_deployments:
                    self.active_deployments[deployment_id]['status'] = 'cancelled'
                
                return True
            else:
                logger.warning(f"取消部署失敗: {result.get('message', 'unknown error')}")
                return False
                
        except Exception as e:
            logger.error(f"取消部署過程中發生錯誤: {e}")
            return False
    
    async def list_recent_deployments(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        列出最近的部署
        
        Args:
            limit: 返回數量限制
            
        Returns:
            部署列表
        """
        try:
            deployments = await self.deployment_api.list_deployments(limit=limit)
            
            # 豐富部署資訊
            enriched_deployments = []
            for deployment in deployments:
                deployment_id = deployment['deployment_id']
                
                # 添加本地資訊
                if deployment_id in self.active_deployments:
                    local_info = self.active_deployments[deployment_id]
                    deployment.update({
                        'initiated_by': f"user_{local_info['user_id']}",
                        'environment': local_info['environment']
                    })
                
                enriched_deployments.append(deployment)
            
            return enriched_deployments
            
        except Exception as e:
            logger.error(f"獲取部署列表失敗: {e}")
            return []
    
    async def get_system_health(self) -> Dict[str, Any]:
        """
        獲取系統健康狀態
        
        Returns:
            系統健康資訊
        """
        try:
            health = await self.deployment_api.health_check()
            
            # 添加服務註冊信息
            service_stats = extended_service_registry.get_service_type_statistics()
            health['service_registry'] = {
                'total_services': service_stats['total_services'],
                'deployment_services': service_stats['new_service_types_v2_4_4']['deployment_services']
            }
            
            # 添加活躍部署統計
            health['local_deployments'] = {
                'active_count': len(self.active_deployments),
                'active_deployments': list(self.active_deployments.keys())
            }
            
            return health
            
        except Exception as e:
            logger.error(f"獲取系統健康狀態失敗: {e}")
            return {'error': str(e)}
    
    # ========== 內部方法 ==========
    
    async def _check_deployment_permission(self, user_id: int) -> bool:
        """檢查部署權限（模擬實作）"""
        # 在實際應用中，這裡會整合真正的權限系統
        # 這裡簡單模擬：用戶ID > 0 就有權限
        return user_id > 0
    
    async def _is_admin_user(self, user_id: int) -> bool:
        """檢查是否為管理員用戶（模擬實作）"""
        # 模擬：用戶ID > 1000 為管理員
        return user_id > 1000
    
    async def _prepare_deployment_config(
        self,
        environment: str,
        extra_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """準備部署配置"""
        base_config = {
            'environment_variables': {
                'ENVIRONMENT': environment,
                'LOG_LEVEL': 'DEBUG' if environment == 'dev' else 'INFO',
                'DATABASE_URL': f'sqlite:///roas_bot_{environment}.db'
            },
            'profile': environment,
            'notifications_enabled': True
        }
        
        # 環境特定配置
        if environment == 'prod':
            base_config['environment_variables'].update({
                'LOG_LEVEL': 'WARNING',
                'ENABLE_METRICS': 'true',
                'HEALTH_CHECK_INTERVAL': '30'
            })
        elif environment == 'dev':
            base_config['environment_variables'].update({
                'DEBUG': 'true',
                'HOT_RELOAD': 'true'
            })
        
        # 合併額外配置
        if extra_config:
            if 'environment_variables' in extra_config:
                base_config['environment_variables'].update(extra_config['environment_variables'])
                extra_config = {k: v for k, v in extra_config.items() if k != 'environment_variables'}
            base_config.update(extra_config)
        
        return base_config
    
    async def _get_webhook_url(self) -> Optional[str]:
        """獲取webhook URL（模擬實作）"""
        # 在實際應用中，這裡會返回真正的webhook URL
        return 'http://localhost:8000/webhook/deployment'
    
    async def _monitor_deployment(self, deployment_id: str) -> None:
        """監控部署進度"""
        try:
            logger.info(f"開始監控部署: {deployment_id}")
            
            while deployment_id in self.active_deployments:
                try:
                    # 獲取部署狀態
                    status = await self.deployment_api.get_deployment_status(deployment_id)
                    
                    if not status:
                        break
                    
                    current_status = status.get('status', 'unknown')
                    
                    # 如果部署結束，停止監控
                    if current_status in ['completed', 'failed', 'cancelled']:
                        logger.info(f"部署 {deployment_id} 已結束，狀態: {current_status}")
                        
                        # 更新本地記錄
                        if deployment_id in self.active_deployments:
                            self.active_deployments[deployment_id]['status'] = current_status
                            # 可以選擇從活躍部署中移除
                            # del self.active_deployments[deployment_id]
                        
                        # 發送通知（模擬）
                        await self._send_deployment_notification(deployment_id, current_status)
                        
                        break
                    
                    # 如果部署仍在進行，獲取進度
                    if current_status in ['running', 'installing', 'configuring', 'starting']:
                        try:
                            progress = await self.deployment_api.get_deployment_progress(deployment_id)
                            logger.info(f"部署 {deployment_id} 進度: {progress.progress_percentage:.1f}% - {progress.current_step}")
                        except Exception as e:
                            logger.debug(f"獲取進度失敗: {e}")
                    
                    # 等待下次檢查
                    await asyncio.sleep(10)
                    
                except Exception as e:
                    logger.warning(f"監控部署 {deployment_id} 時發生錯誤: {e}")
                    await asyncio.sleep(10)
                    
        except Exception as e:
            logger.error(f"監控部署 {deployment_id} 失敗: {e}")
    
    async def _send_deployment_notification(self, deployment_id: str, status: str) -> None:
        """發送部署通知（模擬實作）"""
        try:
            deployment_info = self.active_deployments.get(deployment_id, {})
            user_id = deployment_info.get('user_id', 'unknown')
            environment = deployment_info.get('environment', 'unknown')
            
            message = f"部署 {deployment_id} 在 {environment} 環境中已{status}"
            
            # 在實際應用中，這裡會發送Discord消息或其他通知
            logger.info(f"通知用戶 {user_id}: {message}")
            
        except Exception as e:
            logger.error(f"發送部署通知失敗: {e}")
    
    async def cleanup(self) -> None:
        """清理資源"""
        try:
            logger.info("清理部署控制器...")
            
            # 取消所有活躍部署
            for deployment_id in list(self.active_deployments.keys()):
                try:
                    await self.deployment_api.cancel_deployment(deployment_id)
                except Exception as e:
                    logger.warning(f"取消部署 {deployment_id} 失敗: {e}")
            
            # 停止API服務
            if self.deployment_api:
                await self.deployment_api.stop()
            
            logger.info("部署控制器清理完成")
            
        except Exception as e:
            logger.error(f"清理部署控制器失敗: {e}")


async def main():
    """主函數 - 演示部署控制器的使用"""
    controller = ROASBotDeploymentController()
    
    try:
        # 初始化控制器
        if not await controller.initialize():
            logger.error("初始化失敗")
            return
        
        # 檢查系統健康狀態
        health = await controller.get_system_health()
        logger.info(f"系統健康狀態: {health['api_status']}")
        
        # 模擬部署場景
        logger.info("=== 開始部署場景演示 ===")
        
        # 場景1：開發環境部署
        logger.info("場景1: 開發環境UV部署")
        deployment_id = await controller.deploy_bot(
            mode='uv',
            environment='dev',
            user_id=123,
            config={
                'environment_variables': {
                    'DISCORD_TOKEN': 'dev-token-here',
                    'DEBUG': 'true'
                }
            }
        )
        
        if deployment_id:
            logger.info(f"開發環境部署已啟動: {deployment_id}")
            
            # 等待一段時間觀察部署進度
            await asyncio.sleep(5)
            
            # 檢查部署狀態
            status = await controller.get_deployment_status(deployment_id)
            if status:
                logger.info(f"部署狀態: {status['status']}")
            
            # 演示取消部署
            logger.info("演示取消部署...")
            cancel_success = await controller.cancel_deployment(deployment_id, 123)
            logger.info(f"取消部署{'成功' if cancel_success else '失敗'}")
        
        # 場景2：生產環境自動模式部署
        logger.info("場景2: 生產環境自動部署")
        prod_deployment_id = await controller.deploy_bot(
            mode='auto',
            environment='prod',
            user_id=456,
            config={
                'environment_variables': {
                    'DISCORD_TOKEN': 'prod-token-here',
                    'LOG_LEVEL': 'WARNING'
                }
            }
        )
        
        if prod_deployment_id:
            logger.info(f"生產環境部署已啟動: {prod_deployment_id}")
            
            # 等待並監控
            await asyncio.sleep(3)
            
            # 檢查部署狀態
            status = await controller.get_deployment_status(prod_deployment_id)
            if status:
                logger.info(f"生產部署狀態: {status['status']}")
        
        # 場景3：查看部署歷史
        logger.info("場景3: 查看部署歷史")
        recent_deployments = await controller.list_recent_deployments(5)
        logger.info(f"最近部署數量: {len(recent_deployments)}")
        for deployment in recent_deployments:
            logger.info(f"  - {deployment['deployment_id']}: {deployment['status']} ({deployment.get('mode', 'unknown')})")
        
        # 場景4：系統健康檢查
        logger.info("場景4: 系統健康檢查")
        health = await controller.get_system_health()
        logger.info(f"活躍部署數量: {health['local_deployments']['active_count']}")
        logger.info(f"API狀態: {health['api_status']}")
        logger.info(f"部署管理器狀態: {list(health['deployment_managers'].keys())}")
        
        # 演示服務註冊整合
        logger.info("=== 服務註冊整合演示 ===")
        
        # 檢查服務註冊狀態
        services = extended_service_registry.list_services()
        deployment_services = [s for s in services if 'deployment' in s.lower()]
        logger.info(f"註冊的部署相關服務: {deployment_services}")
        
        # 獲取服務統計
        stats = extended_service_registry.get_service_type_statistics()
        logger.info(f"部署服務統計: {stats['new_service_types_v2_4_4']['deployment_services']}")
        
        # 執行完整系統健康檢查
        system_health = await extended_service_registry.perform_full_system_health_check()
        logger.info(f"系統整體健康度: {system_health['health_percentage']:.1f}%")
        
        logger.info("=== 演示完成 ===")
        
    except KeyboardInterrupt:
        logger.info("演示被用戶中斷")
    except Exception as e:
        logger.error(f"演示過程中發生錯誤: {e}")
    finally:
        # 清理資源
        await controller.cleanup()


class DeploymentWebhookHandler:
    """部署Webhook處理器（模擬）"""
    
    async def handle_webhook(self, webhook_data: Dict[str, Any]) -> None:
        """處理Webhook回調"""
        try:
            deployment_id = webhook_data.get('deployment_id')
            current_step = webhook_data.get('current_step', 'unknown')
            progress = webhook_data.get('progress_percentage', 0)
            
            logger.info(f"Webhook: 部署 {deployment_id} 進度更新 - {current_step} ({progress:.1f}%)")
            
            # 在實際應用中，這裡可以:
            # 1. 更新數據庫
            # 2. 發送Discord消息
            # 3. 更新Web界面
            # 4. 觸發其他自動化流程
            
        except Exception as e:
            logger.error(f"處理Webhook失敗: {e}")


if __name__ == "__main__":
    # 運行演示
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\\n程序被用戶中斷")