"""
AI 服務
Task ID: 1 - 核心架構和基礎設施建置

這個模組提供AI集成和對話管理服務：
- 多AI提供商集成（OpenAI、Anthropic、Google等）
- 配額管理和使用限制
- 對話記錄和成本追蹤
- 內容安全過濾
- 速率限制和錯誤處理
"""

import asyncio
import logging
import json
import hashlib
from datetime import datetime, date, timedelta
from typing import Dict, Any, Optional, List, Union, Tuple
from enum import Enum
from decimal import Decimal

from core.base_service import BaseService
from src.core.errors import (
    AIServiceError,
    AIProviderError, 
    AIQuotaExceededError,
    AIResponseError,
    ContentFilterError,
    ValidationError
)

logger = logging.getLogger('services.ai')


class AIProvider(Enum):
    """AI提供商枚舉"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


class QuotaType(Enum):
    """配額類型枚舉"""
    DAILY = "daily"
    WEEKLY = "weekly" 
    MONTHLY = "monthly"
    TOTAL_COST = "total_cost"


class AIService(BaseService):
    """
    AI服務
    
    負責管理AI對話、配額控制和多提供商集成
    """
    
    def __init__(self, default_provider: str = "openai"):
        """
        初始化AI服務
        
        Args:
            default_provider: 預設AI提供商
        """
        super().__init__("AIService")
        
        self.default_provider = default_provider
        self.providers: Dict[str, Dict[str, Any]] = {}
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        
        # 服務配置
        self.config = {
            'max_message_length': 4000,      # 最大消息長度
            'max_response_tokens': 2000,     # 最大響應token數
            'default_model': 'gpt-3.5-turbo', # 預設模型
            'rate_limit_window': 60,         # 速率限制時間窗口（秒）
            'max_requests_per_window': 10,   # 時間窗口內最大請求數
            'response_timeout': 30,          # 響應超時時間（秒）
            'content_filter_enabled': True,  # 是否啟用內容過濾
            'cost_tracking_enabled': True    # 是否啟用成本追蹤
        }
        
        # 速率限制追蹤
        self.rate_limit_tracker: Dict[int, List[datetime]] = {}
    
    async def _initialize(self) -> bool:
        """初始化AI服務"""
        try:
            self.logger.info("正在初始化AI服務...")
            
            # 載入AI提供商配置
            await self._load_providers()
            
            # 檢查是否有可用的提供商
            if not self.providers:
                self.logger.warning("未找到可用的AI提供商配置")
            
            # 啟動配額重置任務
            asyncio.create_task(self._quota_reset_loop())
            
            # 啟動速率限制清理任務
            asyncio.create_task(self._rate_limit_cleanup_loop())
            
            self.logger.info(f"AI服務初始化完成，載入 {len(self.providers)} 個提供商")
            return True
            
        except Exception as e:
            self.logger.error(f"AI服務初始化失敗: {e}")
            raise AIServiceError(f"AI服務初始化失敗: {str(e)}")
    
    async def _cleanup(self) -> None:
        """清理AI服務資源"""
        try:
            self.logger.info("正在清理AI服務...")
            
            # 清理活躍會話
            self.active_sessions.clear()
            self.rate_limit_tracker.clear()
            
            self.logger.info("AI服務清理完成")
        except Exception as e:
            self.logger.error(f"清理AI服務時發生錯誤: {e}")
    
    async def _validate_permissions(
        self, 
        user_id: int, 
        guild_id: Optional[int], 
        action: str
    ) -> bool:
        """
        驗證AI服務操作權限
        
        Args:
            user_id: 使用者ID
            guild_id: 伺服器ID（可選）
            action: 要執行的操作
            
        Returns:
            是否有權限
        """
        # AI服務權限相對寬鬆，主要通過配額控制
        if action in ['chat', 'query']:
            return True  # 所有用戶都可以使用AI對話
        
        # 管理操作需要更高權限
        if action in ['configure_provider', 'set_quota', 'reset_usage']:
            return True  # 暫時允許，實際部署時需要實現權限檢查
        
        return False
    
    async def chat(
        self, 
        user_id: int, 
        message: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        sub_bot_id: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        AI對話接口
        
        Args:
            user_id: 使用者ID
            message: 用戶消息
            provider: AI提供商
            model: AI模型
            sub_bot_id: 子機器人ID（如果通過子機器人調用）
            context: 對話上下文
            
        Returns:
            AI響應結果
        """
        try:
            # 驗證消息長度
            if len(message) > self.config['max_message_length']:
                raise ValidationError(
                    field="message",
                    value=message,
                    validation_rule=f"消息長度不能超過 {self.config['max_message_length']} 字符"
                )
            
            # 檢查速率限制
            if not await self._check_rate_limit(user_id):
                raise AIServiceError("已達到速率限制，請稍後再試")
            
            # 檢查用戶配額
            if not await self._check_user_quota(user_id):
                raise AIQuotaExceededError("已達到使用配額限制")
            
            # 內容安全檢查
            if self.config['content_filter_enabled']:
                if not await self._content_filter(message):
                    raise ContentFilterError("消息內容不符合安全規範")
            
            # 選擇AI提供商
            selected_provider = provider or self.default_provider
            if selected_provider not in self.providers:
                raise AIProviderError(f"AI提供商不可用: {selected_provider}")
            
            provider_config = self.providers[selected_provider]
            selected_model = model or provider_config.get('default_model', self.config['default_model'])
            
            # 發送AI請求
            start_time = datetime.now()
            ai_response = await self._make_ai_request(
                provider=selected_provider,
                model=selected_model,
                message=message,
                context=context or {}
            )
            response_time = (datetime.now() - start_time).total_seconds()
            
            # 計算成本
            tokens_used = ai_response.get('usage', {}).get('total_tokens', 0)
            cost = self._calculate_cost(selected_provider, tokens_used)
            
            # 記錄對話
            conversation_id = await self._log_conversation(
                user_id=user_id,
                sub_bot_id=sub_bot_id,
                provider=selected_provider,
                model=selected_model,
                user_message=message,
                ai_response=ai_response['content'],
                tokens_used=tokens_used,
                cost=cost,
                response_time=response_time
            )
            
            # 更新用戶使用統計
            await self._update_user_usage(user_id, tokens_used, cost)
            
            # 記錄速率限制
            self._record_request(user_id)
            
            return {
                'conversation_id': conversation_id,
                'response': ai_response['content'],
                'provider': selected_provider,
                'model': selected_model,
                'tokens_used': tokens_used,
                'cost': float(cost),
                'response_time': response_time
            }
            
        except Exception as e:
            self.logger.error(f"AI對話處理失敗: {e}")
            raise
    
    async def get_user_quota_status(self, user_id: int) -> Dict[str, Any]:
        """
        獲取用戶配額狀態
        
        Args:
            user_id: 使用者ID
            
        Returns:
            配額狀態資訊
        """
        db_manager = self.get_dependency("database_manager")
        if not db_manager:
            return {'error': '資料庫服務不可用'}
        
        try:
            # 查詢用戶配額資訊
            quota = await db_manager.fetchone(
                "SELECT * FROM ai_usage_quotas WHERE user_id = ?",
                (user_id,)
            )
            
            if not quota:
                # 創建預設配額
                await self._create_default_quota(user_id)
                quota = await db_manager.fetchone(
                    "SELECT * FROM ai_usage_quotas WHERE user_id = ?",
                    (user_id,)
                )
            
            if quota:
                return {
                    'user_id': quota['user_id'],
                    'daily': {
                        'limit': quota['daily_limit'],
                        'used': quota['daily_used'],
                        'remaining': quota['daily_limit'] - quota['daily_used']
                    },
                    'weekly': {
                        'limit': quota['weekly_limit'],
                        'used': quota['weekly_used'],
                        'remaining': quota['weekly_limit'] - quota['weekly_used']
                    },
                    'monthly': {
                        'limit': quota['monthly_limit'],
                        'used': quota['monthly_used'],
                        'remaining': quota['monthly_limit'] - quota['monthly_used']
                    },
                    'cost': {
                        'limit': float(quota['total_cost_limit']),
                        'used': float(quota['total_cost_used']),
                        'remaining': float(quota['total_cost_limit'] - quota['total_cost_used'])
                    },
                    'last_reset': {
                        'daily': quota['last_reset_daily'],
                        'weekly': quota['last_reset_weekly'],
                        'monthly': quota['last_reset_monthly']
                    }
                }
            
            return {'error': '無法獲取配額資訊'}
            
        except Exception as e:
            self.logger.error(f"獲取用戶配額狀態失敗: {e}")
            return {'error': str(e)}
    
    async def set_user_quota(
        self, 
        user_id: int, 
        quota_type: str, 
        limit: Union[int, float]
    ) -> bool:
        """
        設置用戶配額
        
        Args:
            user_id: 使用者ID
            quota_type: 配額類型（daily, weekly, monthly, total_cost）
            limit: 配額限制值
            
        Returns:
            是否設置成功
        """
        try:
            db_manager = self.get_dependency("database_manager")
            if not db_manager:
                return False
            
            # 驗證配額類型
            if quota_type not in ['daily_limit', 'weekly_limit', 'monthly_limit', 'total_cost_limit']:
                raise ValidationError(
                    field="quota_type",
                    value=quota_type,
                    validation_rule="必須是有效的配額類型"
                )
            
            # 確保用戶配額記錄存在
            quota = await db_manager.fetchone(
                "SELECT id FROM ai_usage_quotas WHERE user_id = ?",
                (user_id,)
            )
            
            if not quota:
                await self._create_default_quota(user_id)
            
            # 更新配額限制
            await db_manager.execute(
                f"UPDATE ai_usage_quotas SET {quota_type} = ?, updated_at = ? WHERE user_id = ?",
                (limit, datetime.now().isoformat(), user_id)
            )
            
            self.logger.info(f"已更新用戶 {user_id} 的 {quota_type} 配額為 {limit}")
            return True
            
        except Exception as e:
            self.logger.error(f"設置用戶配額失敗: {e}")
            return False
    
    async def reset_user_usage(self, user_id: int, quota_type: str) -> bool:
        """
        重置用戶使用量
        
        Args:
            user_id: 使用者ID
            quota_type: 配額類型
            
        Returns:
            是否重置成功
        """
        try:
            db_manager = self.get_dependency("database_manager")
            if not db_manager:
                return False
            
            usage_field = quota_type.replace('_limit', '_used')
            reset_field = f"last_reset_{quota_type.replace('_limit', '')}"
            
            await db_manager.execute(
                f"UPDATE ai_usage_quotas SET {usage_field} = 0, {reset_field} = ?, updated_at = ? WHERE user_id = ?",
                (date.today().isoformat(), datetime.now().isoformat(), user_id)
            )
            
            self.logger.info(f"已重置用戶 {user_id} 的 {quota_type} 使用量")
            return True
            
        except Exception as e:
            self.logger.error(f"重置用戶使用量失敗: {e}")
            return False
    
    async def get_conversation_history(
        self, 
        user_id: int, 
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        獲取用戶對話歷史
        
        Args:
            user_id: 使用者ID
            limit: 返回記錄數限制
            offset: 偏移量
            
        Returns:
            對話歷史列表
        """
        try:
            db_manager = self.get_dependency("database_manager")
            if not db_manager:
                return []
            
            conversations = await db_manager.fetchall(
                """SELECT * FROM ai_conversations 
                   WHERE user_id = ? 
                   ORDER BY created_at DESC 
                   LIMIT ? OFFSET ?""",
                (user_id, limit, offset)
            )
            
            return [dict(conv) for conv in conversations]
            
        except Exception as e:
            self.logger.error(f"獲取對話歷史失敗: {e}")
            return []
    
    # 私有方法
    
    async def _load_providers(self) -> None:
        """載入AI提供商配置"""
        db_manager = self.get_dependency("database_manager")
        if db_manager:
            try:
                providers = await db_manager.fetchall(
                    "SELECT * FROM ai_providers WHERE is_active = 1 ORDER BY priority"
                )
                
                for provider in providers:
                    self.providers[provider['provider_name']] = {
                        'id': provider['id'],
                        'api_key_hash': provider['api_key_hash'],
                        'base_url': provider['base_url'],
                        'rate_limit_per_minute': provider['rate_limit_per_minute'],
                        'cost_per_token': float(provider['cost_per_token']),
                        'default_model': self._get_default_model(provider['provider_name'])
                    }
                
                self.logger.info(f"載入了 {len(self.providers)} 個AI提供商配置")
                
            except Exception as e:
                self.logger.warning(f"載入AI提供商配置失敗: {e}")
    
    def _get_default_model(self, provider_name: str) -> str:
        """獲取提供商的預設模型"""
        defaults = {
            'openai': 'gpt-3.5-turbo',
            'anthropic': 'claude-3-sonnet-20240229',
            'google': 'gemini-pro'
        }
        return defaults.get(provider_name, 'gpt-3.5-turbo')
    
    async def _check_rate_limit(self, user_id: int) -> bool:
        """檢查速率限制"""
        current_time = datetime.now()
        window_start = current_time - timedelta(seconds=self.config['rate_limit_window'])
        
        # 清理過期的請求記錄
        if user_id in self.rate_limit_tracker:
            self.rate_limit_tracker[user_id] = [
                req_time for req_time in self.rate_limit_tracker[user_id]
                if req_time > window_start
            ]
        
        # 檢查當前窗口內的請求數
        request_count = len(self.rate_limit_tracker.get(user_id, []))
        return request_count < self.config['max_requests_per_window']
    
    def _record_request(self, user_id: int) -> None:
        """記錄請求時間"""
        if user_id not in self.rate_limit_tracker:
            self.rate_limit_tracker[user_id] = []
        
        self.rate_limit_tracker[user_id].append(datetime.now())
    
    async def _check_user_quota(self, user_id: int) -> bool:
        """檢查用戶配額"""
        quota_status = await self.get_user_quota_status(user_id)
        
        if 'error' in quota_status:
            return False
        
        # 檢查各項配額
        return (quota_status['daily']['remaining'] > 0 and
                quota_status['weekly']['remaining'] > 0 and
                quota_status['monthly']['remaining'] > 0 and
                quota_status['cost']['remaining'] > 0)
    
    async def _content_filter(self, message: str) -> bool:
        """內容安全過濾"""
        # 實作內容過濾邏輯
        # 這裡可以集成第三方內容審查服務
        
        # 簡單的關鍵詞過濾
        forbidden_words = ['spam', 'abuse']  # 實際部署時需要更完善的詞庫
        message_lower = message.lower()
        
        for word in forbidden_words:
            if word in message_lower:
                return False
        
        return True
    
    async def _make_ai_request(
        self, 
        provider: str, 
        model: str, 
        message: str, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """發送AI請求（模擬實作）"""
        # 實際實作需要整合各AI提供商的API
        # 這裡暫時返回模擬響應
        
        await asyncio.sleep(0.5)  # 模擬網絡延遲
        
        return {
            'content': f"這是來自 {provider} ({model}) 的模擬回應：{message}",
            'usage': {
                'prompt_tokens': len(message.split()) * 1.3,  # 粗略估算
                'completion_tokens': 50,
                'total_tokens': len(message.split()) * 1.3 + 50
            }
        }
    
    def _calculate_cost(self, provider: str, tokens: int) -> Decimal:
        """計算AI請求成本"""
        if provider not in self.providers:
            return Decimal('0')
        
        cost_per_token = Decimal(str(self.providers[provider]['cost_per_token']))
        return cost_per_token * Decimal(str(tokens))
    
    async def _log_conversation(
        self,
        user_id: int,
        sub_bot_id: Optional[int],
        provider: str,
        model: str,
        user_message: str,
        ai_response: str,
        tokens_used: int,
        cost: Decimal,
        response_time: float
    ) -> Optional[int]:
        """記錄對話到資料庫"""
        db_manager = self.get_dependency("database_manager")
        if not db_manager:
            return None
        
        try:
            await db_manager.execute(
                """INSERT INTO ai_conversations 
                   (user_id, sub_bot_id, provider, model, user_message, ai_response, 
                    tokens_used, cost, response_time, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    user_id, sub_bot_id, provider, model,
                    user_message, ai_response, tokens_used,
                    float(cost), response_time, datetime.now().isoformat()
                )
            )
            
            # 返回記錄ID（在實際實作中可能需要查詢最後插入的ID）
            return 1  # 暫時返回固定值
            
        except Exception as e:
            self.logger.error(f"記錄對話失敗: {e}")
            return None
    
    async def _update_user_usage(self, user_id: int, tokens: int, cost: Decimal) -> None:
        """更新用戶使用統計"""
        db_manager = self.get_dependency("database_manager")
        if not db_manager:
            return
        
        try:
            # 確保用戶配額記錄存在
            quota = await db_manager.fetchone(
                "SELECT id FROM ai_usage_quotas WHERE user_id = ?",
                (user_id,)
            )
            
            if not quota:
                await self._create_default_quota(user_id)
            
            # 更新使用量
            await db_manager.execute(
                """UPDATE ai_usage_quotas 
                   SET daily_used = daily_used + 1,
                       weekly_used = weekly_used + 1,
                       monthly_used = monthly_used + 1,
                       total_cost_used = total_cost_used + ?,
                       updated_at = ?
                   WHERE user_id = ?""",
                (float(cost), datetime.now().isoformat(), user_id)
            )
            
        except Exception as e:
            self.logger.error(f"更新用戶使用統計失敗: {e}")
    
    async def _create_default_quota(self, user_id: int) -> None:
        """創建預設配額記錄"""
        db_manager = self.get_dependency("database_manager")
        if db_manager:
            try:
                today = date.today().isoformat()
                await db_manager.execute(
                    """INSERT INTO ai_usage_quotas 
                       (user_id, daily_limit, weekly_limit, monthly_limit,
                        daily_used, weekly_used, monthly_used,
                        total_cost_limit, total_cost_used,
                        last_reset_daily, last_reset_weekly, last_reset_monthly,
                        created_at, updated_at)
                       VALUES (?, 50, 200, 1000, 0, 0, 0, 10.0, 0.0, ?, ?, ?, ?, ?)""",
                    (
                        user_id, today, today, today,
                        datetime.now().isoformat(),
                        datetime.now().isoformat()
                    )
                )
            except Exception as e:
                self.logger.error(f"創建預設配額記錄失敗: {e}")
    
    async def _quota_reset_loop(self) -> None:
        """配額重置循環任務"""
        while True:
            try:
                await asyncio.sleep(3600)  # 每小時檢查一次
                await self._reset_expired_quotas()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"配額重置循環錯誤: {e}")
    
    async def _reset_expired_quotas(self) -> None:
        """重置過期的配額"""
        db_manager = self.get_dependency("database_manager")
        if not db_manager:
            return
        
        try:
            today = date.today()
            
            # 重置日配額
            await db_manager.execute(
                """UPDATE ai_usage_quotas 
                   SET daily_used = 0, last_reset_daily = ?
                   WHERE last_reset_daily < ?""",
                (today.isoformat(), today.isoformat())
            )
            
            # 重置週配額（假設週一重置）
            days_since_monday = today.weekday()
            week_start = today - timedelta(days=days_since_monday)
            
            await db_manager.execute(
                """UPDATE ai_usage_quotas 
                   SET weekly_used = 0, last_reset_weekly = ?
                   WHERE last_reset_weekly < ?""",
                (week_start.isoformat(), week_start.isoformat())
            )
            
            # 重置月配額
            month_start = today.replace(day=1)
            
            await db_manager.execute(
                """UPDATE ai_usage_quotas 
                   SET monthly_used = 0, last_reset_monthly = ?
                   WHERE last_reset_monthly < ?""",
                (month_start.isoformat(), month_start.isoformat())
            )
            
        except Exception as e:
            self.logger.error(f"重置過期配額失敗: {e}")
    
    async def _rate_limit_cleanup_loop(self) -> None:
        """速率限制清理循環任務"""
        while True:
            try:
                await asyncio.sleep(300)  # 每5分鐘清理一次
                
                current_time = datetime.now()
                window_start = current_time - timedelta(seconds=self.config['rate_limit_window'])
                
                # 清理過期的速率限制記錄
                for user_id in list(self.rate_limit_tracker.keys()):
                    self.rate_limit_tracker[user_id] = [
                        req_time for req_time in self.rate_limit_tracker[user_id]
                        if req_time > window_start
                    ]
                    
                    # 如果沒有記錄了，刪除用戶條目
                    if not self.rate_limit_tracker[user_id]:
                        del self.rate_limit_tracker[user_id]
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"速率限制清理循環錯誤: {e}")