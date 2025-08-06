#!/usr/bin/env python3
"""
Discord ROAS Bot - 自動化部署觸發器
支援多種觸發方式：GitHub Webhook、手動觸發、定時任務
"""

import os
import sys
import json
import hmac
import hashlib
import logging
import asyncio
import argparse
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime
import subprocess
import tempfile

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('deployment-trigger.log')
    ]
)
logger = logging.getLogger(__name__)

class DeploymentTrigger:
    """自動化部署觸發器類別"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.project_root = Path(__file__).parent.parent.parent
        self.deploy_script = self.project_root / "scripts" / "deploy" / "deploy.sh"
        
    def verify_github_signature(self, payload: bytes, signature: str) -> bool:
        """驗證 GitHub Webhook 簽名"""
        secret = self.config.get('webhook_secret', '').encode()
        if not secret:
            logger.warning("Webhook secret not configured, skipping verification")
            return True
            
        expected_signature = 'sha256=' + hmac.new(
            secret, payload, hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature, signature)
    
    def should_trigger_deployment(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """判斷是否應該觸發部署"""
        result = {
            'should_deploy': False,
            'environment': None,
            'reason': '',
            'branch': None,
            'commit': None
        }
        
        # 處理 push 事件
        if webhook_data.get('ref'):
            branch = webhook_data['ref'].replace('refs/heads/', '')
            result['branch'] = branch
            result['commit'] = webhook_data.get('after', '')
            
            # 根據分支決定環境
            if branch == 'main':
                result['environment'] = 'production'
                result['should_deploy'] = True
                result['reason'] = f'Push to {branch} branch'
            elif branch == 'develop':
                result['environment'] = 'development'
                result['should_deploy'] = True
                result['reason'] = f'Push to {branch} branch'
            elif branch.startswith('release/'):
                result['environment'] = 'testing'
                result['should_deploy'] = True
                result['reason'] = f'Push to release branch: {branch}'
            else:
                result['reason'] = f'Branch {branch} not configured for auto-deployment'
        
        # 處理 pull request 事件
        elif webhook_data.get('pull_request'):
            pr = webhook_data['pull_request']
            if pr.get('merged') and pr.get('base', {}).get('ref') == 'main':
                result['environment'] = 'production'
                result['should_deploy'] = True
                result['reason'] = 'Pull request merged to main'
                result['branch'] = 'main'
                result['commit'] = pr.get('merge_commit_sha', '')
        
        # 處理 release 事件
        elif webhook_data.get('release'):
            if webhook_data['action'] == 'published':
                result['environment'] = 'production'
                result['should_deploy'] = True
                result['reason'] = f"Release published: {webhook_data['release']['tag_name']}"
                result['branch'] = 'main'
        
        return result
    
    async def execute_deployment(self, environment: str, version: str = None, commit: str = None) -> Dict[str, Any]:
        """執行部署"""
        logger.info(f"開始部署到環境: {environment}")
        
        # 準備部署參數
        deploy_args = [
            str(self.deploy_script),
            '--environment', environment
        ]
        
        if version:
            deploy_args.extend(['--version', version])
        
        # 設定環境變數
        env = os.environ.copy()
        if commit:
            env['BUILD_COMMIT'] = commit
        env['BUILD_DATE'] = datetime.utcnow().isoformat() + 'Z'
        
        # 創建日誌文件
        log_file = self.project_root / "logs" / f"deployment-{environment}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
        log_file.parent.mkdir(exist_ok=True)
        
        try:
            # 執行部署腳本
            logger.info(f"執行部署命令: {' '.join(deploy_args)}")
            
            with open(log_file, 'w') as f:
                process = await asyncio.create_subprocess_exec(
                    *deploy_args,
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    env=env,
                    cwd=self.project_root
                )
                
                return_code = await process.wait()
            
            # 讀取日誌輸出
            with open(log_file, 'r') as f:
                output = f.read()
            
            result = {
                'success': return_code == 0,
                'return_code': return_code,
                'log_file': str(log_file),
                'output': output[-2000:],  # 最後 2000 字元
                'environment': environment,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }
            
            if result['success']:
                logger.info(f"部署成功: {environment}")
            else:
                logger.error(f"部署失敗: {environment}, 退出碼: {return_code}")
            
            return result
            
        except Exception as e:
            logger.error(f"部署執行錯誤: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'log_file': str(log_file),
                'environment': environment,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }
    
    async def send_notification(self, deployment_result: Dict[str, Any], trigger_info: Dict[str, Any]):
        """發送部署通知"""
        webhook_url = self.config.get('notification_webhook')
        if not webhook_url:
            logger.info("通知 Webhook 未配置，跳過通知")
            return
        
        # 準備通知內容
        status_emoji = "✅" if deployment_result['success'] else "❌"
        environment = deployment_result['environment']
        
        message = {
            "embeds": [{
                "title": f"{status_emoji} 部署通知",
                "description": f"環境: **{environment}**",
                "color": 0x00ff00 if deployment_result['success'] else 0xff0000,
                "fields": [
                    {
                        "name": "狀態",
                        "value": "成功" if deployment_result['success'] else "失敗",
                        "inline": True
                    },
                    {
                        "name": "觸發原因",
                        "value": trigger_info.get('reason', '未知'),
                        "inline": True
                    },
                    {
                        "name": "分支",
                        "value": trigger_info.get('branch', '未知'),
                        "inline": True
                    }
                ],
                "timestamp": deployment_result['timestamp']
            }]
        }
        
        if not deployment_result['success']:
            # 添加錯誤詳情
            error_output = deployment_result.get('output', '')
            if error_output:
                message["embeds"][0]["fields"].append({
                    "name": "錯誤輸出",
                    "value": f"```\n{error_output[-500:]}\n```",
                    "inline": False
                })
        
        try:
            import requests
            response = requests.post(webhook_url, json=message, timeout=10)
            if response.status_code == 204:
                logger.info("通知發送成功")
            else:
                logger.warning(f"通知發送失敗: {response.status_code}")
        except Exception as e:
            logger.error(f"發送通知時出錯: {str(e)}")
    
    async def handle_webhook(self, payload: bytes, headers: Dict[str, str]) -> Dict[str, Any]:
        """處理 GitHub Webhook"""
        # 驗證簽名
        signature = headers.get('X-Hub-Signature-256', '')
        if not self.verify_github_signature(payload, signature):
            return {'error': 'Invalid signature', 'status': 401}
        
        try:
            webhook_data = json.loads(payload.decode('utf-8'))
        except json.JSONDecodeError:
            return {'error': 'Invalid JSON payload', 'status': 400}
        
        # 判斷是否需要部署
        trigger_decision = self.should_trigger_deployment(webhook_data)
        
        if not trigger_decision['should_deploy']:
            logger.info(f"跳過部署: {trigger_decision['reason']}")
            return {
                'message': 'Deployment not triggered',
                'reason': trigger_decision['reason'],
                'status': 200
            }
        
        # 執行部署
        deployment_result = await self.execute_deployment(
            environment=trigger_decision['environment'],
            version=trigger_decision.get('commit', '')[:7],
            commit=trigger_decision.get('commit')
        )
        
        # 發送通知
        await self.send_notification(deployment_result, trigger_decision)
        
        return {
            'message': 'Deployment triggered',
            'deployment_result': deployment_result,
            'status': 200 if deployment_result['success'] else 500
        }

def load_config() -> Dict[str, Any]:
    """載入配置"""
    config_file = Path(__file__).parent.parent.parent / "config" / "deployment-trigger.json"
    
    if config_file.exists():
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    # 預設配置
    return {
        'webhook_secret': os.getenv('GITHUB_WEBHOOK_SECRET', ''),
        'notification_webhook': os.getenv('DISCORD_WEBHOOK_URL', ''),
        'allowed_environments': ['development', 'testing', 'production']
    }

async def main():
    """主程式入口"""
    parser = argparse.ArgumentParser(description='Discord ROAS Bot 部署觸發器')
    parser.add_argument('--webhook-file', help='包含 webhook payload 的檔案')
    parser.add_argument('--manual', choices=['development', 'testing', 'production'], 
                       help='手動觸發部署到指定環境')
    parser.add_argument('--version', help='指定部署版本')
    
    args = parser.parse_args()
    
    config = load_config()
    trigger = DeploymentTrigger(config)
    
    if args.manual:
        # 手動觸發
        logger.info(f"手動觸發部署到: {args.manual}")
        result = await trigger.execute_deployment(args.manual, args.version)
        
        if result['success']:
            logger.info("手動部署成功完成")
            sys.exit(0)
        else:
            logger.error("手動部署失敗")
            sys.exit(1)
    
    elif args.webhook_file:
        # 從檔案讀取 webhook payload
        with open(args.webhook_file, 'rb') as f:
            payload = f.read()
        
        result = await trigger.handle_webhook(payload, {})
        logger.info(f"Webhook 處理結果: {result['message']}")
        sys.exit(0 if result['status'] == 200 else 1)
    
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())