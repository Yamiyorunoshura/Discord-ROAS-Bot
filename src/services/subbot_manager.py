"""
SubBot管理器 - 子機器人實例池管理和協調
Task ID: 3 - 子機器人聊天功能和管理系統開發

這個模組提供完整的子機器人管理功能：
- 子機器人實例池管理和生命週期控制
- 故障隔離和自動恢復機制
- 並發協調和負載均衡
- 系統健康檢查和監控
- Discord.py集成和連線管理
"""

import asyncio
import logging
import weakref
from typing import Dict, Any, Optional, List, Set, Union, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from concurrent.futures import ThreadPoolExecutor
import json
import contextlib

# Discord.py imports
try:
    import discord
    from discord.ext import commands
    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False

from core.base_service import BaseService, ServiceType
from src.core.config import get_config
from src.core.errors import (
    SubBotError,
    SubBotCreationError, 
    SubBotTokenError,
    SubBotChannelError,
    SecurityError
)

logger = logging.getLogger('services.subbot_manager')


class InstanceStatus(Enum):
    """子機器人實例狀態"""
    CREATED = "created"           # 已創建但未啟動
    STARTING = "starting"         # 正在啟動
    RUNNING = "running"           # 正常運行
    DEGRADED = "degraded"         # 運行異常但可用
    STOPPING = "stopping"        # 正在停止
    STOPPED = "stopped"          # 已停止
    ERROR = "error"              # 錯誤狀態
    ISOLATED = "isolated"        # 已隔離（故障隔離）


class FailureType(Enum):
    """故障類型"""
    CONNECTION_ERROR = "connection_error"      # 連線錯誤
    AUTHENTICATION_ERROR = "auth_error"        # 認證錯誤
    RATE_LIMIT_ERROR = "rate_limit_error"     # 速率限制錯誤
    PERMISSION_ERROR = "permission_error"      # 權限錯誤
    NETWORK_ERROR = "network_error"            # 網路錯誤
    INTERNAL_ERROR = "internal_error"          # 內部錯誤
    TIMEOUT_ERROR = "timeout_error"            # 超時錯誤
    UNKNOWN_ERROR = "unknown_error"            # 未知錯誤


@dataclass
class InstanceMetrics:
    """子機器人實例指標"""
    bot_id: str
    messages_processed: int = 0
    errors_count: int = 0
    last_activity: datetime = field(default_factory=datetime.now)
    uptime: float = 0.0  # 運行時間（秒）
    average_response_time: float = 0.0  # 平均回應時間（毫秒）
    memory_usage: float = 0.0  # 記憶體使用量（MB）
    
    def update_activity(self):
        """更新活動時間"""
        self.last_activity = datetime.now()
    
    def record_error(self):
        """記錄錯誤"""
        self.errors_count += 1
        self.update_activity()
    
    def record_message(self, response_time: Optional[float] = None):
        """記錄訊息處理"""
        self.messages_processed += 1
        if response_time is not None:
            # 計算滾動平均
            self.average_response_time = (
                (self.average_response_time * (self.messages_processed - 1) + response_time)
                / self.messages_processed
            )
        self.update_activity()


@dataclass
class CircuitBreakerConfig:
    """斷路器配置"""
    failure_threshold: int = 5        # 失敗閾值
    recovery_timeout: int = 60        # 恢復超時（秒）
    half_open_max_calls: int = 3      # 半開狀態最大調用次數


class CircuitBreakerState(Enum):
    """斷路器狀態"""
    CLOSED = "closed"      # 關閉（正常）
    OPEN = "open"          # 打開（故障）
    HALF_OPEN = "half_open"  # 半開（測試恢復）


class CircuitBreaker:
    """斷路器實現 - 用於故障隔離"""
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.half_open_calls = 0
        
    def can_execute(self) -> bool:
        """檢查是否可以執行操作"""
        if self.state == CircuitBreakerState.CLOSED:
            return True
        elif self.state == CircuitBreakerState.OPEN:
            if (self.last_failure_time and 
                datetime.now() - self.last_failure_time > timedelta(seconds=self.config.recovery_timeout)):
                self.state = CircuitBreakerState.HALF_OPEN
                self.half_open_calls = 0
                logger.info("斷路器轉為半開狀態，開始測試恢復")
                return True
            return False
        else:  # HALF_OPEN
            return self.half_open_calls < self.config.half_open_max_calls
    
    def record_success(self):
        """記錄成功執行"""
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.half_open_calls += 1
            if self.half_open_calls >= self.config.half_open_max_calls:
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
                logger.info("斷路器恢復正常狀態")
        elif self.state == CircuitBreakerState.CLOSED:
            self.failure_count = max(0, self.failure_count - 1)  # 逐漸恢復
    
    def record_failure(self):
        """記錄失敗執行"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.state == CircuitBreakerState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                self.state = CircuitBreakerState.OPEN
                logger.warning(f"斷路器開啟，失敗次數: {self.failure_count}")
        elif self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.OPEN
            logger.warning("半開狀態測試失敗，斷路器重新開啟")


class SubBotInstance:
    """子機器人實例 - 包裝Discord客戶端和相關邏輯"""
    
    def __init__(self, bot_id: str, config: Dict[str, Any], manager: 'SubBotManager'):
        self.bot_id = bot_id
        self.config = config
        self.manager = weakref.ref(manager)  # 避免循環引用
        
        # 實例狀態
        self.status = InstanceStatus.CREATED
        self.created_at = datetime.now()
        self.started_at: Optional[datetime] = None
        
        # Discord客戶端
        self.client: Optional[Union[discord.Client, commands.Bot]] = None
        self.connection_task: Optional[asyncio.Task] = None
        
        # 指標和監控
        self.metrics = InstanceMetrics(bot_id)
        
        # 故障隔離
        self.circuit_breaker = CircuitBreaker(CircuitBreakerConfig())
        self.isolation_until: Optional[datetime] = None
        self.failure_history: List[Dict[str, Any]] = []
        
        # 並發控制
        self.operation_lock = asyncio.Lock()
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.rate_limiter = asyncio.Semaphore(config.get('rate_limit', 10))
        
        logger.info(f"SubBot實例已創建: {bot_id}")
    
    @property
    def is_healthy(self) -> bool:
        """檢查實例是否健康"""
        return (
            self.status in [InstanceStatus.RUNNING, InstanceStatus.DEGRADED] and
            self.circuit_breaker.state != CircuitBreakerState.OPEN and
            (not self.isolation_until or datetime.now() > self.isolation_until)
        )
    
    @property
    def uptime(self) -> float:
        """獲取運行時間（秒）"""
        if self.started_at:
            return (datetime.now() - self.started_at).total_seconds()
        return 0.0
    
    async def start(self) -> bool:
        """啟動子機器人實例"""
        async with self.operation_lock:
            try:
                if self.status != InstanceStatus.CREATED:
                    logger.warning(f"SubBot {self.bot_id} 狀態不正確，無法啟動: {self.status}")
                    return False
                
                logger.info(f"正在啟動 SubBot: {self.bot_id}")
                self.status = InstanceStatus.STARTING
                
                # 創建Discord客戶端
                success = await self._create_discord_client()
                if not success:
                    self.status = InstanceStatus.ERROR
                    return False
                
                # 啟動連線任務
                self.connection_task = asyncio.create_task(self._connection_monitor())
                
                # 啟動訊息處理任務
                asyncio.create_task(self._message_processor())
                
                self.status = InstanceStatus.RUNNING
                self.started_at = datetime.now()
                
                logger.info(f"SubBot {self.bot_id} 啟動成功")
                return True
                
            except Exception as e:
                logger.error(f"SubBot {self.bot_id} 啟動失敗: {e}")
                self.status = InstanceStatus.ERROR
                self.circuit_breaker.record_failure()
                await self._record_failure(FailureType.INTERNAL_ERROR, str(e))
                return False
    
    async def stop(self, graceful: bool = True) -> bool:
        """停止子機器人實例"""
        async with self.operation_lock:
            try:
                if self.status in [InstanceStatus.STOPPED, InstanceStatus.STOPPING]:
                    return True
                
                logger.info(f"正在停止 SubBot: {self.bot_id} (graceful: {graceful})")
                self.status = InstanceStatus.STOPPING
                
                if graceful:
                    # 優雅停止：等待當前操作完成
                    await self._drain_message_queue()
                
                # 停止連線任務
                if self.connection_task and not self.connection_task.done():
                    self.connection_task.cancel()
                    try:
                        await self.connection_task
                    except asyncio.CancelledError:
                        pass
                
                # 關閉Discord客戶端
                if self.client:
                    await self._close_discord_client()
                
                self.status = InstanceStatus.STOPPED
                logger.info(f"SubBot {self.bot_id} 已停止")
                return True
                
            except Exception as e:
                logger.error(f"SubBot {self.bot_id} 停止失敗: {e}")
                self.status = InstanceStatus.ERROR
                return False
    
    async def restart(self) -> bool:
        """重啟子機器人實例"""
        logger.info(f"正在重啟 SubBot: {self.bot_id}")
        
        # 先停止
        if not await self.stop(graceful=True):
            logger.error(f"SubBot {self.bot_id} 停止失敗，無法重啟")
            return False
        
        # 重置狀態
        self.status = InstanceStatus.CREATED
        self.started_at = None
        self.circuit_breaker = CircuitBreaker(CircuitBreakerConfig())
        
        # 重新啟動
        return await self.start()
    
    async def isolate(self, duration: int = 300) -> None:
        """隔離實例（用於故障恢復）"""
        self.status = InstanceStatus.ISOLATED
        self.isolation_until = datetime.now() + timedelta(seconds=duration)
        logger.warning(f"SubBot {self.bot_id} 已被隔離 {duration} 秒")
    
    async def handle_message(self, message_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """處理訊息（通過斷路器）"""
        if not self.circuit_breaker.can_execute():
            raise SubBotError(f"SubBot {self.bot_id} 斷路器開啟，拒絕處理訊息")
        
        try:
            async with self.rate_limiter:
                start_time = datetime.now()
                
                # 實際訊息處理邏輯
                result = await self._process_message(message_data)
                
                # 記錄成功指標
                response_time = (datetime.now() - start_time).total_seconds() * 1000
                self.metrics.record_message(response_time)
                self.circuit_breaker.record_success()
                
                return result
                
        except Exception as e:
            # 記錄失敗指標
            self.metrics.record_error()
            self.circuit_breaker.record_failure()
            await self._record_failure(FailureType.INTERNAL_ERROR, str(e))
            raise
    
    async def _create_discord_client(self) -> bool:
        """創建Discord客戶端"""
        if not DISCORD_AVAILABLE:
            logger.error("Discord.py 未安裝，無法創建客戶端")
            return False
        
        try:
            # 解密Token
            manager_ref = self.manager()
            if not manager_ref:
                logger.error("無法獲取管理器引用")
                return False
            
            subbot_service = manager_ref.get_dependency('subbot_service')
            if not subbot_service:
                logger.error("無法獲取SubBotService")
                return False
            
            token = subbot_service._decrypt_token(self.config['token_hash'])
            
            # 創建Discord Bot實例
            intents = discord.Intents.default()
            intents.message_content = True  # 需要讀取訊息內容
            
            if self.config.get('ai_enabled', False):
                # AI模式使用commands.Bot
                self.client = commands.Bot(command_prefix='!', intents=intents)
            else:
                # 簡單模式使用discord.Client
                self.client = discord.Client(intents=intents)
            
            # 設置事件處理器
            self._setup_discord_handlers()
            
            # 連線到Discord
            await self.client.login(token)
            logger.info(f"SubBot {self.bot_id} Discord客戶端創建成功")
            return True
            
        except Exception as e:
            logger.error(f"創建Discord客戶端失敗: {e}")
            await self._record_failure(FailureType.AUTHENTICATION_ERROR, str(e))
            return False
    
    def _setup_discord_handlers(self):
        """設置Discord事件處理器"""
        if not self.client:
            return
        
        @self.client.event
        async def on_ready():
            logger.info(f"SubBot {self.bot_id} 已連線到Discord: {self.client.user}")
        
        @self.client.event
        async def on_message(message):
            if message.author == self.client.user:
                return  # 忽略自己的訊息
            
            # 檢查頻道權限
            if message.channel.id not in self.config.get('target_channels', []):
                return
            
            try:
                # 將訊息加入處理佇列
                await self.message_queue.put({
                    'type': 'discord_message',
                    'message': message,
                    'channel_id': message.channel.id,
                    'user_id': message.author.id,
                    'content': message.content,
                    'timestamp': datetime.now().isoformat()
                })
                
            except Exception as e:
                logger.error(f"處理Discord訊息時發生錯誤: {e}")
                await self._record_failure(FailureType.INTERNAL_ERROR, str(e))
        
        @self.client.event
        async def on_error(event, *args, **kwargs):
            logger.error(f"SubBot {self.bot_id} Discord錯誤 - 事件: {event}")
            await self._record_failure(FailureType.UNKNOWN_ERROR, f"Discord事件錯誤: {event}")
    
    async def _close_discord_client(self):
        """關閉Discord客戶端"""
        if self.client:
            try:
                await self.client.close()
                logger.info(f"SubBot {self.bot_id} Discord客戶端已關閉")
            except Exception as e:
                logger.error(f"關閉Discord客戶端時發生錯誤: {e}")
            finally:
                self.client = None
    
    async def _connection_monitor(self):
        """連線監控任務"""
        try:
            # 啟動Discord客戶端
            if self.client:
                await self.client.start(self.client.http.token, reconnect=True)
        except asyncio.CancelledError:
            logger.info(f"SubBot {self.bot_id} 連線監控任務已取消")
        except Exception as e:
            logger.error(f"SubBot {self.bot_id} 連線監控發生錯誤: {e}")
            await self._record_failure(FailureType.CONNECTION_ERROR, str(e))
            self.status = InstanceStatus.ERROR
    
    async def _message_processor(self):
        """訊息處理器"""
        while self.status in [InstanceStatus.RUNNING, InstanceStatus.DEGRADED]:
            try:
                # 從佇列獲取訊息（帶超時）
                message_data = await asyncio.wait_for(
                    self.message_queue.get(), 
                    timeout=30.0
                )
                
                # 處理訊息
                await self.handle_message(message_data)
                
            except asyncio.TimeoutError:
                # 超時不是錯誤，繼續等待
                continue
            except Exception as e:
                logger.error(f"訊息處理器發生錯誤: {e}")
                await asyncio.sleep(1)  # 短暫延遲避免快速循環
    
    async def _process_message(self, message_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """實際訊息處理邏輯"""
        try:
            if message_data['type'] == 'discord_message':
                message = message_data['message']
                
                # 基本回應邏輯（可以擴展為AI集成）
                if self.config.get('ai_enabled', False):
                    # AI處理邏輯（待實現）
                    response = await self._generate_ai_response(message_data)
                else:
                    # 簡單回應邏輯
                    response = await self._generate_simple_response(message_data)
                
                # 發送回應
                if response and self.client:
                    await message.channel.send(response)
                
                return {'status': 'processed', 'response': response}
            
            return None
            
        except Exception as e:
            logger.error(f"處理訊息失敗: {e}")
            raise
    
    async def _generate_simple_response(self, message_data: Dict[str, Any]) -> Optional[str]:
        """生成簡單回應"""
        content = message_data.get('content', '').lower()
        
        # 簡單的關鍵字回應
        if 'hello' in content or '你好' in content:
            return f"Hello! I'm SubBot {self.bot_id}"
        elif 'help' in content or '幫助' in content:
            return "I'm here to help! This is a SubBot instance."
        elif 'status' in content or '狀態' in content:
            return f"SubBot {self.bot_id} is running normally."
        
        return None  # 不回應
    
    async def _generate_ai_response(self, message_data: Dict[str, Any]) -> Optional[str]:
        """生成AI回應（待實現）"""
        # 這裡可以集成AI服務
        # 目前返回占位符
        return f"[AI Response from SubBot {self.bot_id}] Processing your message..."
    
    async def _drain_message_queue(self):
        """清空訊息佇列（用於優雅停止）"""
        logger.info(f"正在清空 SubBot {self.bot_id} 的訊息佇列")
        
        # 設置超時避免無限等待
        deadline = datetime.now() + timedelta(seconds=30)
        
        while not self.message_queue.empty() and datetime.now() < deadline:
            try:
                message_data = await asyncio.wait_for(
                    self.message_queue.get(),
                    timeout=1.0
                )
                # 嘗試處理剩餘訊息
                await self.handle_message(message_data)
            except asyncio.TimeoutError:
                break
            except Exception as e:
                logger.warning(f"清空佇列時處理訊息失敗: {e}")
                continue
    
    async def _record_failure(self, failure_type: FailureType, details: str):
        """記錄故障資訊"""
        failure_record = {
            'type': failure_type.value,
            'details': details,
            'timestamp': datetime.now().isoformat(),
            'bot_id': self.bot_id
        }
        
        self.failure_history.append(failure_record)
        
        # 只保留最近50條記錄
        if len(self.failure_history) > 50:
            self.failure_history = self.failure_history[-50:]
        
        # 通知管理器
        manager_ref = self.manager()
        if manager_ref:
            await manager_ref._handle_instance_failure(self.bot_id, failure_type, details)
    
    def get_health_status(self) -> Dict[str, Any]:
        """獲取實例健康狀態"""
        return {
            'bot_id': self.bot_id,
            'status': self.status.value,
            'is_healthy': self.is_healthy,
            'uptime': self.uptime,
            'circuit_breaker_state': self.circuit_breaker.state.value,
            'metrics': {
                'messages_processed': self.metrics.messages_processed,
                'errors_count': self.metrics.errors_count,
                'average_response_time': self.metrics.average_response_time,
                'last_activity': self.metrics.last_activity.isoformat(),
            },
            'failure_count': len(self.failure_history),
            'isolation_until': self.isolation_until.isoformat() if self.isolation_until else None,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
        }


class SubBotManager(BaseService):
    """
    SubBot管理器 - 統一管理所有子機器人實例
    
    職責：
    1. 實例池管理和生命週期控制
    2. 故障隔離和自動恢復
    3. 負載均衡和並發協調
    4. 系統健康檢查和監控
    """
    
    def __init__(self):
        super().__init__("SubBotManager", ServiceType.SUB_BOT)
        
        # 實例池
        self.instances: Dict[str, SubBotInstance] = {}
        self.instance_lock = asyncio.Lock()
        
        # 配置
        self.config = {
            'max_instances': 10,                    # 最大實例數
            'health_check_interval': 30,            # 健康檢查間隔（秒）
            'auto_recovery_enabled': True,          # 是否啟用自動恢復
            'isolation_duration': 300,              # 隔離持續時間（秒）
            'restart_backoff_base': 2,              # 重啟退避基數（秒）
            'restart_backoff_max': 300,             # 最大退避時間（秒）
            'concurrent_operations': 5,             # 並發操作限制
        }
        
        # 管理任務
        self.health_check_task: Optional[asyncio.Task] = None
        self.recovery_task: Optional[asyncio.Task] = None
        
        # 並發控制
        self.operation_semaphore = asyncio.Semaphore(self.config['concurrent_operations'])
        
        # 統計資訊
        self.total_instances_created = 0
        self.total_failures_handled = 0
        self.recovery_attempts = 0
        
        logger.info("SubBotManager 已初始化")
    
    async def _initialize(self) -> bool:
        """初始化SubBot管理器"""
        try:
            logger.info("正在初始化 SubBotManager...")
            
            # 載入配置
            await self._load_configuration()
            
            # 啟動健康檢查任務
            self.health_check_task = asyncio.create_task(self._health_check_loop())
            
            # 啟動恢復任務
            if self.config['auto_recovery_enabled']:
                self.recovery_task = asyncio.create_task(self._recovery_loop())
            
            # 恢復已存在的子機器人實例
            await self._restore_instances()
            
            logger.info("SubBotManager 初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"SubBotManager 初始化失敗: {e}")
            return False
    
    async def _cleanup(self) -> None:
        """清理SubBot管理器"""
        try:
            logger.info("正在清理 SubBotManager...")
            
            # 停止管理任務
            if self.health_check_task and not self.health_check_task.done():
                self.health_check_task.cancel()
                try:
                    await self.health_check_task
                except asyncio.CancelledError:
                    pass
            
            if self.recovery_task and not self.recovery_task.done():
                self.recovery_task.cancel()
                try:
                    await self.recovery_task
                except asyncio.CancelledError:
                    pass
            
            # 停止所有實例
            await self.stop_all_instances(graceful=True)
            
            logger.info("SubBotManager 清理完成")
            
        except Exception as e:
            logger.error(f"SubBotManager 清理失敗: {e}")
    
    async def _validate_permissions(
        self, 
        user_id: int, 
        guild_id: Optional[int], 
        action: str
    ) -> bool:
        """驗證權限"""
        # SubBot管理需要管理員權限
        if action in ['create', 'delete', 'stop', 'restart']:
            # 這裡實現具體的權限檢查邏輯
            return True
        
        # 查詢操作允許一般用戶
        if action in ['status', 'list', 'health']:
            return True
        
        return False
    
    async def create_instance(self, bot_config: Dict[str, Any]) -> str:
        """創建新的子機器人實例"""
        async with self.operation_semaphore:
            async with self.instance_lock:
                try:
                    bot_id = bot_config['bot_id']
                    
                    # 檢查實例數限制
                    if len(self.instances) >= self.config['max_instances']:
                        raise SubBotCreationError(
                            bot_id, 
                            f"實例數已達上限 {self.config['max_instances']}"
                        )
                    
                    # 檢查實例是否已存在
                    if bot_id in self.instances:
                        raise SubBotCreationError(bot_id, "實例已存在")
                    
                    # 創建實例
                    instance = SubBotInstance(bot_id, bot_config, self)
                    self.instances[bot_id] = instance
                    self.total_instances_created += 1
                    
                    logger.info(f"SubBot實例已創建: {bot_id}")
                    return bot_id
                    
                except Exception as e:
                    logger.error(f"創建SubBot實例失敗: {e}")
                    raise
    
    async def start_instance(self, bot_id: str) -> bool:
        """啟動子機器人實例"""
        async with self.operation_semaphore:
            instance = self.instances.get(bot_id)
            if not instance:
                raise SubBotError(f"實例不存在: {bot_id}")
            
            return await instance.start()
    
    async def stop_instance(self, bot_id: str, graceful: bool = True) -> bool:
        """停止子機器人實例"""
        async with self.operation_semaphore:
            instance = self.instances.get(bot_id)
            if not instance:
                raise SubBotError(f"實例不存在: {bot_id}")
            
            return await instance.stop(graceful)
    
    async def restart_instance(self, bot_id: str) -> bool:
        """重啟子機器人實例"""
        async with self.operation_semaphore:
            instance = self.instances.get(bot_id)
            if not instance:
                raise SubBotError(f"實例不存在: {bot_id}")
            
            return await instance.restart()
    
    async def delete_instance(self, bot_id: str) -> bool:
        """刪除子機器人實例"""
        async with self.operation_semaphore:
            async with self.instance_lock:
                instance = self.instances.get(bot_id)
                if not instance:
                    return True  # 已經不存在
                
                # 先停止實例
                await instance.stop(graceful=True)
                
                # 從實例池移除
                del self.instances[bot_id]
                
                logger.info(f"SubBot實例已刪除: {bot_id}")
                return True
    
    async def get_instance_status(self, bot_id: str) -> Dict[str, Any]:
        """獲取實例狀態"""
        instance = self.instances.get(bot_id)
        if not instance:
            raise SubBotError(f"實例不存在: {bot_id}")
        
        return instance.get_health_status()
    
    async def list_instances(self) -> List[Dict[str, Any]]:
        """列出所有實例狀態"""
        instances_status = []
        
        for bot_id, instance in self.instances.items():
            try:
                status = instance.get_health_status()
                instances_status.append(status)
            except Exception as e:
                logger.error(f"獲取實例 {bot_id} 狀態失敗: {e}")
                instances_status.append({
                    'bot_id': bot_id,
                    'status': 'error',
                    'error': str(e)
                })
        
        return instances_status
    
    async def get_system_status(self) -> Dict[str, Any]:
        """獲取系統整體狀態"""
        instances = await self.list_instances()
        
        # 統計各狀態實例數
        status_counts = {}
        healthy_count = 0
        
        for instance in instances:
            status = instance.get('status', 'unknown')
            status_counts[status] = status_counts.get(status, 0) + 1
            
            if instance.get('is_healthy', False):
                healthy_count += 1
        
        return {
            'total_instances': len(instances),
            'healthy_instances': healthy_count,
            'unhealthy_instances': len(instances) - healthy_count,
            'status_distribution': status_counts,
            'system_metrics': {
                'total_created': self.total_instances_created,
                'total_failures_handled': self.total_failures_handled,
                'recovery_attempts': self.recovery_attempts,
            },
            'configuration': {k: v for k, v in self.config.items() if k != 'tokens'},
            'uptime': self.uptime,
            'timestamp': datetime.now().isoformat()
        }
    
    async def stop_all_instances(self, graceful: bool = True) -> Dict[str, bool]:
        """停止所有實例"""
        logger.info(f"正在停止所有實例 (graceful: {graceful})")
        
        results = {}
        
        # 並行停止所有實例
        tasks = []
        for bot_id, instance in self.instances.items():
            task = asyncio.create_task(instance.stop(graceful))
            tasks.append((bot_id, task))
        
        # 等待所有停止任務完成
        for bot_id, task in tasks:
            try:
                result = await task
                results[bot_id] = result
            except Exception as e:
                logger.error(f"停止實例 {bot_id} 失敗: {e}")
                results[bot_id] = False
        
        return results
    
    async def _health_check_loop(self):
        """健康檢查循環"""
        logger.info("健康檢查循環已啟動")
        
        while True:
            try:
                await asyncio.sleep(self.config['health_check_interval'])
                await self._perform_health_checks()
                
            except asyncio.CancelledError:
                logger.info("健康檢查循環已取消")
                break
            except Exception as e:
                logger.error(f"健康檢查循環發生錯誤: {e}")
                await asyncio.sleep(5)  # 短暫延遲避免快速循環
    
    async def _perform_health_checks(self):
        """執行健康檢查"""
        logger.debug("執行系統健康檢查...")
        
        unhealthy_instances = []
        
        for bot_id, instance in list(self.instances.items()):
            try:
                if not instance.is_healthy:
                    unhealthy_instances.append(bot_id)
                    logger.warning(f"檢測到不健康實例: {bot_id}")
                    
                    # 檢查是否需要隔離
                    if instance.circuit_breaker.state == CircuitBreakerState.OPEN:
                        await instance.isolate(self.config['isolation_duration'])
                
            except Exception as e:
                logger.error(f"檢查實例 {bot_id} 健康狀態失敗: {e}")
                unhealthy_instances.append(bot_id)
        
        if unhealthy_instances:
            logger.info(f"發現 {len(unhealthy_instances)} 個不健康實例")
    
    async def _recovery_loop(self):
        """自動恢復循環"""
        logger.info("自動恢復循環已啟動")
        
        while True:
            try:
                await asyncio.sleep(60)  # 每分鐘檢查一次
                await self._perform_recovery_actions()
                
            except asyncio.CancelledError:
                logger.info("自動恢復循環已取消")
                break
            except Exception as e:
                logger.error(f"自動恢復循環發生錯誤: {e}")
                await asyncio.sleep(10)
    
    async def _perform_recovery_actions(self):
        """執行恢復操作"""
        logger.debug("執行自動恢復檢查...")
        
        for bot_id, instance in list(self.instances.items()):
            try:
                # 檢查是否可以嘗試恢復
                if (instance.status == InstanceStatus.ERROR and
                    instance.circuit_breaker.state == CircuitBreakerState.OPEN):
                    
                    # 檢查隔離期是否結束
                    if (not instance.isolation_until or 
                        datetime.now() > instance.isolation_until):
                        
                        logger.info(f"嘗試恢復實例: {bot_id}")
                        self.recovery_attempts += 1
                        
                        # 嘗試重啟
                        success = await instance.restart()
                        if success:
                            logger.info(f"實例 {bot_id} 恢復成功")
                        else:
                            logger.warning(f"實例 {bot_id} 恢復失敗")
                            # 重新隔離
                            await instance.isolate(self.config['isolation_duration'] * 2)
                
            except Exception as e:
                logger.error(f"恢復實例 {bot_id} 時發生錯誤: {e}")
    
    async def _handle_instance_failure(self, bot_id: str, failure_type: FailureType, details: str):
        """處理實例故障"""
        logger.warning(f"處理實例故障: {bot_id} - {failure_type.value}: {details}")
        
        self.total_failures_handled += 1
        
        instance = self.instances.get(bot_id)
        if not instance:
            return
        
        # 根據故障類型決定處理策略
        if failure_type in [FailureType.AUTHENTICATION_ERROR, FailureType.PERMISSION_ERROR]:
            # 認證或權限錯誤通常需要人工介入
            instance.status = InstanceStatus.ERROR
            logger.error(f"實例 {bot_id} 發生認證/權限錯誤，需要人工檢查")
            
        elif failure_type == FailureType.RATE_LIMIT_ERROR:
            # 速率限制錯誤，暫時隔離
            await instance.isolate(300)  # 隔離5分鐘
            
        elif failure_type in [FailureType.CONNECTION_ERROR, FailureType.NETWORK_ERROR]:
            # 網路相關錯誤，可以嘗試自動重連
            if self.config['auto_recovery_enabled']:
                asyncio.create_task(self._delayed_restart(bot_id, 30))
        
        else:
            # 其他錯誤，短期隔離
            await instance.isolate(60)
    
    async def _delayed_restart(self, bot_id: str, delay: int):
        """延遲重啟實例"""
        try:
            logger.info(f"將在 {delay} 秒後重啟實例: {bot_id}")
            await asyncio.sleep(delay)
            
            instance = self.instances.get(bot_id)
            if instance and instance.status == InstanceStatus.ERROR:
                await instance.restart()
                
        except Exception as e:
            logger.error(f"延遲重啟實例 {bot_id} 失敗: {e}")
    
    async def _load_configuration(self):
        """載入配置"""
        try:
            config = get_config()
            if hasattr(config, 'subbot_manager'):
                self.config.update(config.subbot_manager)
                
        except Exception as e:
            logger.warning(f"載入配置失敗，使用預設配置: {e}")
    
    async def _restore_instances(self):
        """恢復已存在的實例（從資料庫或配置）"""
        try:
            # 從SubBotService獲取已註冊的子機器人
            subbot_service = self.get_dependency('subbot_service')
            if subbot_service:
                registered_bots = await subbot_service.list_sub_bots()
                
                for bot_config in registered_bots:
                    try:
                        bot_id = bot_config['bot_id']
                        
                        # 創建實例但不自動啟動
                        await self.create_instance(bot_config)
                        logger.info(f"已恢復SubBot實例: {bot_id}")
                        
                    except Exception as e:
                        logger.error(f"恢復SubBot實例失敗: {e}")
                        
        except Exception as e:
            logger.warning(f"恢復實例過程發生錯誤: {e}")