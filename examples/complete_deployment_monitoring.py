#!/usr/bin/env python3
"""
完整的部署監控系統集成範例
Task ID: 2 - 自動化部署和啟動系統開發

Daniel - DevOps 專家
展示如何集成智能部署協調器和監控系統
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

# 導入所有部署服務
from src.services.deployment_coordinator import (
    DeploymentCoordinator, DeploymentStrategy, DeploymentMode
)
from src.services.deployment_monitor_integration import (
    DeploymentMonitorIntegration, MonitoringConfig, MonitoringIntensity
)
from src.services.docker_deployment_manager import DockerDeploymentConfig, DockerProfile
from src.services.uv_deployment_manager import UVEnvironmentConfig, ApplicationConfig
from src.core.config import AppConfig
from core.database_manager import DatabaseManager

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class IntegratedDeploymentSystem:
    """
    整合的部署系統
    
    展示如何將智能部署協調器和監控系統完整整合
    """
    
    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path.cwd()
        
        # 核心服務
        self.coordinator: Optional[DeploymentCoordinator] = None
        self.monitor_integration: Optional[DeploymentMonitorIntegration] = None
        self.db_manager: Optional[DatabaseManager] = None
        
        # 配置
        self.app_config = AppConfig()
        self.monitoring_config = MonitoringConfig(
            intensity=MonitoringIntensity.STANDARD,
            real_time_logging=True,
            database_logging=True,
            enable_alerts=True
        )
        
    async def initialize(self) -> bool:
        """初始化整合系統"""
        try:
            logger.info("初始化整合部署系統...")
            
            # 1. 初始化資料庫管理器
            self.db_manager = DatabaseManager()
            await self.db_manager.start()
            
            # 2. 初始化部署協調器
            self.coordinator = DeploymentCoordinator(str(self.project_root))
            await self.coordinator.start()
            
            # 3. 初始化監控整合服務
            self.monitor_integration = DeploymentMonitorIntegration(
                coordinator=self.coordinator,
                config=self.app_config,
                db_manager=self.db_manager,
                monitoring_config=self.monitoring_config
            )
            await self.monitor_integration.start()
            
            # 4. 建立服務間連接
            self.coordinator.set_monitor_integration(self.monitor_integration)
            
            # 5. 設置告警回調
            self.monitor_integration.add_alert_callback(self._handle_deployment_alert)
            
            logger.info("整合部署系統初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"系統初始化失敗: {e}")
            return False
    
    async def shutdown(self) -> None:
        """關閉整合系統"""
        try:
            logger.info("關閉整合部署系統...")
            
            # 按相反順序關閉服務
            if self.monitor_integration:
                await self.monitor_integration.stop()
            
            if self.coordinator:
                await self.coordinator.stop()
            
            if self.db_manager:
                await self.db_manager.stop()
            
            logger.info("整合部署系統已關閉")
            
        except Exception as e:
            logger.error(f"系統關閉失敗: {e}")
    
    async def deploy_with_monitoring(
        self,
        strategy: DeploymentStrategy = DeploymentStrategy.AUTO_DETECT,
        environment: str = 'dev',
        monitoring_intensity: MonitoringIntensity = MonitoringIntensity.STANDARD
    ) -> Dict[str, Any]:
        """
        執行帶完整監控的部署
        
        Args:
            strategy: 部署策略
            environment: 環境名稱
            monitoring_intensity: 監控強度
            
        Returns:
            部署結果
        """
        try:
            logger.info(f"開始帶監控的部署，策略: {strategy.value}，環境: {environment}")
            
            # 設置監控強度
            self.monitoring_config.intensity = monitoring_intensity
            
            # 準備部署配置
            docker_config = DockerDeploymentConfig(
                profile=DockerProfile(environment),
                detached=True
            )
            
            uv_env_config = UVEnvironmentConfig(
                requirements_file='pyproject.toml' if (self.project_root / 'pyproject.toml').exists() else 'requirements.txt'
            )
            
            uv_app_config = ApplicationConfig(
                main_module='main.py'
            )
            
            # 執行部署
            result = await self.coordinator.deploy(
                strategy=strategy,
                docker_config=docker_config,
                uv_env_config=uv_env_config,
                uv_app_config=uv_app_config
            )
            
            # 顯示結果
            if result['success']:
                logger.info(f"✅ 部署成功！")
                logger.info(f"   部署ID: {result['deployment_id']}")
                logger.info(f"   部署模式: {result['deployment_mode']}")
            else:
                logger.error(f"❌ 部署失敗: {result.get('error_message', 'Unknown error')}")
            
            return result
            
        except Exception as e:
            logger.error(f"帶監控部署失敗: {e}")
            return {
                'success': False,
                'error_message': str(e)
            }
    
    async def get_deployment_dashboard(self, deployment_id: Optional[str] = None) -> Dict[str, Any]:
        """獲取部署儀表板數據"""
        try:
            dashboard_data = {
                'system_health': {},
                'active_deployments': {},
                'global_statistics': {},
                'deployment_details': {},
                'generated_at': datetime.now().isoformat()
            }
            
            # 系統健康狀態
            coordinator_health = await self.coordinator.health_check()
            monitor_health = await self.monitor_integration.health_check()
            
            dashboard_data['system_health'] = {
                'coordinator': coordinator_health.get('status', 'unknown'),
                'monitoring': monitor_health.get('status', 'unknown'),
                'overall_status': 'healthy' if all([
                    coordinator_health.get('status') == 'healthy',
                    monitor_health.get('status') == 'healthy'
                ]) else 'degraded'
            }
            
            # 活躍部署
            dashboard_data['active_deployments'] = await self.monitor_integration.get_active_deployments()
            
            # 全域統計
            dashboard_data['global_statistics'] = await self.monitor_integration.get_global_statistics()
            
            # 特定部署詳情
            if deployment_id:
                dashboard_data['deployment_details'] = {
                    'metrics': await self.monitor_integration.get_deployment_metrics(deployment_id),
                    'events': await self.monitor_integration.get_deployment_events(deployment_id, limit=50),
                    'performance': await self.monitor_integration.get_performance_metrics(deployment_id),
                    'report': await self.monitor_integration.generate_deployment_report(deployment_id)
                }
            
            return dashboard_data
            
        except Exception as e:
            logger.error(f"獲取儀表板數據失敗: {e}")
            return {'error': str(e)}
    
    async def demonstrate_monitoring_features(self) -> None:
        """展示監控功能"""
        logger.info("=== 開始監控功能展示 ===")
        
        try:
            # 1. 執行部署
            logger.info("1. 執行自動部署...")
            result = await self.deploy_with_monitoring(
                strategy=DeploymentStrategy.AUTO_DETECT,
                environment='dev',
                monitoring_intensity=MonitoringIntensity.INTENSIVE
            )
            
            if not result['success']:
                logger.error("部署失敗，無法繼續展示")
                return
            
            deployment_id = result['deployment_id']
            
            # 等待部署進行一段時間
            await asyncio.sleep(5)
            
            # 2. 獲取部署狀態
            logger.info("2. 獲取部署狀態...")
            status = await self.coordinator.get_deployment_status()
            logger.info(f"   協調器狀態: {status['coordinator_status']}")
            logger.info(f"   當前部署模式: {status['current_deployment_mode']}")
            
            # 3. 獲取監控指標
            logger.info("3. 獲取監控指標...")
            metrics = await self.monitor_integration.get_deployment_metrics(deployment_id)
            if metrics:
                logger.info(f"   成功率: {metrics.success_rate:.1f}%")
                logger.info(f"   執行時間: {metrics.total_duration_seconds:.1f}秒")
                logger.info(f"   完成步驟: {metrics.steps_completed}/{metrics.steps_total}")
            
            # 4. 獲取事件日誌
            logger.info("4. 獲取事件日誌...")
            events = await self.monitor_integration.get_deployment_events(deployment_id, limit=10)
            logger.info(f"   最近 {len(events)} 個事件:")
            for event in events[:5]:
                logger.info(f"     - [{event.get('event_level', 'info').upper()}] {event.get('event_message', 'No message')}")
            
            # 5. 生成部署報告
            logger.info("5. 生成部署報告...")
            report = await self.monitor_integration.generate_deployment_report(deployment_id)
            if 'error' not in report:
                logger.info(f"   報告生成成功，包含:")
                logger.info(f"     - 事件統計: {report['event_statistics']['total_events']} 個事件")
                logger.info(f"     - 性能概覽: {report['performance_overview']['total_metrics']} 個指標")
                logger.info(f"     - 最近事件: {len(report['recent_events'])} 個")
            
            # 6. 獲取系統儀表板
            logger.info("6. 獲取系統儀表板...")
            dashboard = await self.get_deployment_dashboard(deployment_id)
            if 'error' not in dashboard:
                logger.info(f"   系統整體狀態: {dashboard['system_health']['overall_status']}")
                logger.info(f"   活躍部署數量: {len(dashboard['active_deployments'])}")
                logger.info(f"   全域成功率: {dashboard['global_statistics'].get('success_rate', 0):.1f}%")
            
        except Exception as e:
            logger.error(f"監控功能展示失敗: {e}")
        
        logger.info("=== 監控功能展示完成 ===")
    
    def _handle_deployment_alert(self, event) -> None:
        """處理部署告警"""
        try:
            logger.warning(f"🚨 部署告警: {event.event_message}")
            logger.warning(f"   部署ID: {event.deployment_id}")
            logger.warning(f"   事件類型: {event.event_type.value}")
            logger.warning(f"   嚴重程度: {event.event_level.value}")
            
            # 在實際應用中，這裡可以:
            # 1. 發送Discord通知
            # 2. 發送郵件告警
            # 3. 觸發自動修復流程
            # 4. 記錄到監控系統
            
        except Exception as e:
            logger.error(f"處理告警失敗: {e}")


async def main():
    """主函數 - 演示完整的監控整合系統"""
    system = IntegratedDeploymentSystem()
    
    try:
        # 初始化系統
        logger.info("🚀 啟動完整監控整合系統演示")
        
        if not await system.initialize():
            logger.error("系統初始化失敗")
            return
        
        # 展示監控功能
        await system.demonstrate_monitoring_features()
        
        # 保持運行一段時間以觀察監控
        logger.info("💡 系統將繼續運行30秒以展示持續監控...")
        await asyncio.sleep(30)
        
    except KeyboardInterrupt:
        logger.info("演示被用戶中斷")
    except Exception as e:
        logger.error(f"演示過程中發生錯誤: {e}")
    finally:
        # 清理系統
        await system.shutdown()
        logger.info("🏁 監控整合系統演示完成")


if __name__ == "__main__":
    # 運行完整演示
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n程序被用戶中斷")
    except Exception as e:
        print(f"程序執行失敗: {e}")