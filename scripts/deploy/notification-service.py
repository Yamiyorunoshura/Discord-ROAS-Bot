#!/usr/bin/env python3
"""
Discord ROAS Bot - 部署狀態通知服務
提供部署過程中的即時狀態通知和監控
"""

import json
import asyncio
import logging
import aiohttp
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
import os

# 配置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DeploymentNotificationService:
    """部署通知服務"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self._get_default_config_path()
        self.config = self._load_config()
        self.session: Optional[aiohttp.ClientSession] = None
        
    def _get_default_config_path(self) -> str:
        """獲取預設配置檔案路徑"""
        return str(Path(__file__).parent.parent.parent / "config" / "deployment-trigger.json")
    
    def _load_config(self) -> Dict[str, Any]:
        """載入配置"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"配置檔案不存在: {self.config_path}")
            return self._get_default_config()
        except json.JSONDecodeError as e:
            logger.error(f"配置檔案格式錯誤: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """預設配置"""
        return {
            "notification_webhook": "",
            "notification_templates": {
                "deployment_started": {
                    "title": "🚀 部署開始",
                    "color": "0x3498db"
                },
                "deployment_success": {
                    "title": "✅ 部署成功", 
                    "color": "0x2ecc71"
                },
                "deployment_failed": {
                    "title": "❌ 部署失敗",
                    "color": "0xe74c3c"
                }
            }
        }
    
    async def __aenter__(self):
        """異步上下文管理器進入"""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """異步上下文管理器退出"""
        if self.session:
            await self.session.close()
    
    def _format_template(self, template: Dict[str, Any], variables: Dict[str, str]) -> Dict[str, Any]:
        """格式化通知模板"""
        formatted = {}
        
        for key, value in template.items():
            if isinstance(value, str):
                try:
                    formatted[key] = value.format(**variables)
                except KeyError as e:
                    logger.warning(f"模板變數未找到: {e}")
                    formatted[key] = value
            elif isinstance(value, list):
                formatted[key] = []
                for item in value:
                    if isinstance(item, dict):
                        formatted_item = self._format_template(item, variables)
                        formatted[key].append(formatted_item)
                    else:
                        try:
                            formatted[key].append(str(item).format(**variables))
                        except KeyError:
                            formatted[key].append(str(item))
            elif isinstance(value, dict):
                formatted[key] = self._format_template(value, variables)
            else:
                formatted[key] = value
        
        return formatted
    
    async def send_notification(self, 
                              notification_type: str, 
                              environment: str,
                              variables: Dict[str, str]) -> bool:
        """發送通知"""
        webhook_url = self.config.get('notification_webhook') or os.getenv('DISCORD_WEBHOOK_URL')
        
        if not webhook_url:
            logger.warning("通知 Webhook URL 未配置")
            return False
        
        # 獲取通知模板
        template = self.config.get('notification_templates', {}).get(notification_type)
        if not template:
            logger.error(f"通知模板不存在: {notification_type}")
            return False
        
        # 添加預設變數
        default_variables = {
            'environment': environment,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'service': 'Discord ROAS Bot'
        }
        all_variables = {**default_variables, **variables}
        
        # 格式化模板
        formatted_template = self._format_template(template, all_variables)
        
        # 構建 Discord Embed
        embed = {
            "title": formatted_template.get('title', '部署通知'),
            "color": int(formatted_template.get('color', '0x3498db'), 16),
            "timestamp": all_variables['timestamp'],
            "footer": {
                "text": "Discord ROAS Bot CI/CD"
            }
        }
        
        # 添加欄位
        if 'fields' in formatted_template:
            embed['fields'] = formatted_template['fields']
        
        # 添加描述
        if 'description' in formatted_template:
            embed['description'] = formatted_template['description']
        
        # 發送通知
        payload = {"embeds": [embed]}
        
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            async with self.session.post(webhook_url, json=payload) as response:
                if response.status == 204:
                    logger.info(f"通知發送成功: {notification_type} -> {environment}")
                    return True
                else:
                    logger.error(f"通知發送失敗: {response.status}")
                    return False
                    
        except Exception as e:
            logger.error(f"發送通知時出錯: {str(e)}")
            return False
    
    async def notify_deployment_started(self, 
                                      environment: str,
                                      version: str,
                                      branch: str = "",
                                      commit: str = "",
                                      triggered_by: str = "") -> bool:
        """通知部署開始"""
        variables = {
            'version': version,
            'branch': branch or 'unknown',
            'commit': commit[:8] if commit else 'unknown',
            'triggered_by': triggered_by or 'system'
        }
        
        return await self.send_notification('deployment_started', environment, variables)
    
    async def notify_deployment_success(self,
                                      environment: str,
                                      version: str,
                                      duration: str = "",
                                      health_status: str = "通過") -> bool:
        """通知部署成功"""
        variables = {
            'version': version,
            'duration': duration or 'unknown',
            'health_status': health_status
        }
        
        return await self.send_notification('deployment_success', environment, variables)
    
    async def notify_deployment_failed(self,
                                     environment: str,
                                     version: str,
                                     failed_stage: str = "",
                                     error_message: str = "") -> bool:
        """通知部署失敗"""
        variables = {
            'version': version,
            'failed_stage': failed_stage or 'unknown',
            'error_message': error_message[:500] if error_message else 'No error details available'
        }
        
        return await self.send_notification('deployment_failed', environment, variables)
    
    async def notify_rollback_triggered(self,
                                      environment: str,
                                      failed_version: str,
                                      rollback_version: str,
                                      rollback_reason: str = "") -> bool:
        """通知回滾觸發"""
        variables = {
            'failed_version': failed_version,
            'rollback_version': rollback_version,
            'rollback_reason': rollback_reason or 'Health check failed'
        }
        
        return await self.send_notification('rollback_triggered', environment, variables)

class DeploymentStatusMonitor:
    """部署狀態監控器"""
    
    def __init__(self, notification_service: DeploymentNotificationService):
        self.notification_service = notification_service
        self.monitoring_config = notification_service.config.get('monitoring', {})
        
    async def check_health(self, base_url: str, timeout: int = 30) -> Dict[str, Any]:
        """檢查服務健康狀態"""
        endpoints = self.monitoring_config.get('health_check_endpoints', ['/health'])
        expected_codes = self.monitoring_config.get('expected_response_codes', [200])
        
        results = {}
        
        if not self.notification_service.session:
            self.notification_service.session = aiohttp.ClientSession()
        
        for endpoint in endpoints:
            url = f"{base_url.rstrip('/')}{endpoint}"
            
            try:
                async with self.notification_service.session.get(
                    url, timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    results[endpoint] = {
                        'status_code': response.status,
                        'healthy': response.status in expected_codes,
                        'response_time': response.headers.get('X-Response-Time', 'unknown'),
                        'timestamp': datetime.utcnow().isoformat() + 'Z'
                    }
                    
            except asyncio.TimeoutError:
                results[endpoint] = {
                    'healthy': False,
                    'error': 'Timeout',
                    'timestamp': datetime.utcnow().isoformat() + 'Z'
                }
            except Exception as e:
                results[endpoint] = {
                    'healthy': False,
                    'error': str(e),
                    'timestamp': datetime.utcnow().isoformat() + 'Z'
                }
        
        # 計算整體健康狀態
        overall_healthy = all(result.get('healthy', False) for result in results.values())
        
        return {
            'overall_healthy': overall_healthy,
            'endpoints': results,
            'checked_at': datetime.utcnow().isoformat() + 'Z'
        }
    
    async def monitor_deployment(self,
                               environment: str,
                               base_url: str,
                               max_wait_time: int = 300) -> bool:
        """監控部署狀態直到健康或超時"""
        start_time = datetime.utcnow()
        max_end_time = start_time + timedelta(seconds=max_wait_time)
        
        retry_attempts = self.monitoring_config.get('retry_attempts', 3)
        retry_delay = self.monitoring_config.get('retry_delay', 10)
        
        logger.info(f"開始監控 {environment} 環境部署狀態，最大等待時間: {max_wait_time}s")
        
        while datetime.utcnow() < max_end_time:
            health_result = await self.check_health(base_url)
            
            if health_result['overall_healthy']:
                duration = str(datetime.utcnow() - start_time)
                logger.info(f"部署健康檢查通過，耗時: {duration}")
                return True
            
            logger.info(f"健康檢查失敗，{retry_delay}s 後重試...")
            await asyncio.sleep(retry_delay)
        
        logger.error(f"部署監控超時: {max_wait_time}s")
        return False

# 使用範例和CLI介面
async def main():
    """主程式入口"""
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description='部署通知服務')
    parser.add_argument('action', choices=['start', 'success', 'failed', 'rollback', 'monitor'])
    parser.add_argument('--environment', required=True, help='部署環境')
    parser.add_argument('--version', required=True, help='版本')
    parser.add_argument('--branch', help='分支名稱')
    parser.add_argument('--commit', help='提交雜湊')
    parser.add_argument('--duration', help='部署耗時')
    parser.add_argument('--error', help='錯誤訊息')
    parser.add_argument('--stage', help='失敗階段')
    parser.add_argument('--url', help='服務 URL（用於健康檢查）')
    
    args = parser.parse_args()
    
    async with DeploymentNotificationService() as service:
        if args.action == 'start':
            success = await service.notify_deployment_started(
                args.environment, args.version, args.branch or '', args.commit or ''
            )
        elif args.action == 'success':
            success = await service.notify_deployment_success(
                args.environment, args.version, args.duration or ''
            )
        elif args.action == 'failed':
            success = await service.notify_deployment_failed(
                args.environment, args.version, args.stage or '', args.error or ''
            )
        elif args.action == 'rollback':
            success = await service.notify_rollback_triggered(
                args.environment, args.version, 'previous', args.error or ''
            )
        elif args.action == 'monitor' and args.url:
            monitor = DeploymentStatusMonitor(service)
            success = await monitor.monitor_deployment(args.environment, args.url)
        else:
            parser.print_help()
            sys.exit(1)
        
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())