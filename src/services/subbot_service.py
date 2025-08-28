"""
子機器人服務
Task ID: 1 - 核心架構和基礎設施建置

這個模組提供子機器人管理和聊天服務：
- 子機器人創建和配置管理
- Token加密存儲和安全管理
- 頻道權限控制和路由
- AI對話集成支援
- 活動監控和統計
"""

import asyncio
import logging
import json
import os
import hashlib
import base64
from typing import Dict, List, Optional, Any, Set, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

# Discord API管理
try:
    from .discord_rate_limiter import DiscordAPIManager, DiscordRateLimiter, DiscordRetryManager
    DISCORD_RATE_LIMITER_AVAILABLE = True
except ImportError:
    DISCORD_RATE_LIMITER_AVAILABLE = False
    DiscordAPIManager = None
    DiscordRateLimiter = None
    DiscordRetryManager = None

# 輸入驗證和安全管理
try:
    from .subbot_validator import InputValidator, SecurityPolicy, ConcurrencyManager, default_validator, default_concurrency_manager
    VALIDATOR_AVAILABLE = True
except ImportError:
    VALIDATOR_AVAILABLE = False
    InputValidator = None
    SecurityPolicy = None
    ConcurrencyManager = None
    default_validator = None
    default_concurrency_manager = None

# Discord.py imports
try:
    import discord
    from discord.ext import commands
    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False
    discord = None
    commands = None

# 加密相關imports
try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False

# Fallback to Fernet if available
try:
    from cryptography.fernet import Fernet
    FERNET_AVAILABLE = True
except ImportError:
    FERNET_AVAILABLE = False

from core.base_service import BaseService
from src.core.config import get_config
from src.core.errors import (
    SubBotError,
    SubBotCreationError, 
    SubBotTokenError,
    SubBotChannelError,
    SecurityError
)

# 導入新的管理器組件
try:
    from .subbot_manager import SubBotManager
    from .subbot_load_balancer import SubBotLoadBalancer, PerformanceManager
    from .subbot_extensions import ExtensionManager
    ADVANCED_COMPONENTS_AVAILABLE = True
except ImportError:
    ADVANCED_COMPONENTS_AVAILABLE = False

logger = logging.getLogger('services.subbot')


class SubBotClient(commands.Bot if DISCORD_AVAILABLE else object):
    """
    子機器人Discord客戶端
    
    繼承discord.py的commands.Bot，提供自定義的事件處理和功能
    """
    
    def __init__(self, bot_id: str, config: Dict[str, Any], subbot_service: 'SubBotService', **kwargs):
        if not DISCORD_AVAILABLE:
            raise ImportError("Discord.py未安裝，無法創建Discord客戶端")
            
        # 設定Discord客戶端意圖
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.guild_messages = True
        
        # 初始化Bot
        super().__init__(
            command_prefix=kwargs.get('command_prefix', '!'),
            intents=intents,
            case_insensitive=True,
            strip_after_prefix=True
        )
        
        # 子機器人配置
        self.bot_id = bot_id
        self.config = config
        self.subbot_service = subbot_service
        self.logger = logging.getLogger(f'subbot.{bot_id}')
        
        # Discord API管理器
        if DISCORD_RATE_LIMITER_AVAILABLE:
            rate_limiter = DiscordRateLimiter()
            retry_manager = DiscordRetryManager(
                max_retries=config.get('max_retries', 3),
                base_delay=config.get('retry_base_delay', 1.0)
            )
            self.api_manager = DiscordAPIManager(rate_limiter, retry_manager)
            self.logger.info("已啟用Discord API速率限制和重試機制")
        else:
            self.api_manager = None
            self.logger.warning("Discord API管理器不可用，將使用基本API調用")
        
        # 統計資訊
        self.message_count = 0
        self.start_time = None
        self.last_activity = None
        
        # 速率限制
        self.rate_limit = config.get('rate_limit', 10)
        self.rate_limit_bucket = {}
        
        # AI功能配置
        self.ai_enabled = config.get('ai_enabled', False)
        self.ai_model = config.get('ai_model')
        self.personality = config.get('personality')
        
        # 頻道權限
        self.channel_restrictions = set(config.get('channel_restrictions', []))
    
    async def on_ready(self):
        """當機器人準備就緒時觸發"""
        self.start_time = datetime.now()
        self.logger.info(f"子機器人 {self.bot_id} 已連線: {self.user}")
        
        # 通知服務更新狀態
        if hasattr(self.subbot_service, '_on_bot_ready'):
            await self.subbot_service._on_bot_ready(self.bot_id, self.user)
    
    async def on_message(self, message):
        """處理收到的訊息"""
        # 忽略自己的訊息
        if message.author == self.user:
            return
        
        # 檢查頻道權限
        if self.channel_restrictions and message.channel.id not in self.channel_restrictions:
            return
        
        # 速率限制檢查
        if not await self._check_rate_limit(message.author.id):
            self.logger.warning(f"用戶 {message.author.id} 達到速率限制")
            return
        
        # 更新統計
        self.message_count += 1
        self.last_activity = datetime.now()
        
        # 記錄訊息
        self.logger.debug(f"收到訊息 from {message.author}: {message.content[:100]}")
        
        # 處理指令
        await self.process_commands(message)
        
        # AI處理（如果啟用）
        if self.ai_enabled and not message.content.startswith(self.command_prefix):
            await self._handle_ai_response(message)
        
        # 通知服務有新訊息
        if hasattr(self.subbot_service, '_on_message_received'):
            await self.subbot_service._on_message_received(self.bot_id, message)
    
    async def on_error(self, event, *args, **kwargs):
        """處理錯誤事件"""
        self.logger.exception(f"子機器人 {self.bot_id} 發生錯誤 in event {event}")
        
        # 通知服務發生錯誤
        if hasattr(self.subbot_service, '_on_bot_error'):
            await self.subbot_service._on_bot_error(self.bot_id, event, args, kwargs)
    
    async def _check_rate_limit(self, user_id: int) -> bool:
        """檢查速率限制"""
        now = datetime.now().timestamp()
        bucket_key = f"{self.bot_id}:{user_id}"
        
        if bucket_key not in self.rate_limit_bucket:
            self.rate_limit_bucket[bucket_key] = []
        
        # 清理過期的請求
        self.rate_limit_bucket[bucket_key] = [
            timestamp for timestamp in self.rate_limit_bucket[bucket_key]
            if now - timestamp < 60  # 1分鐘內的請求
        ]
        
        # 檢查是否超過限制
        if len(self.rate_limit_bucket[bucket_key]) >= self.rate_limit:
            return False
        
        # 記錄這次請求
        self.rate_limit_bucket[bucket_key].append(now)
        return True
    
    async def _handle_ai_response(self, message):
        """處理AI回應（預留接口）"""
        if not self.ai_enabled:
            return
        
        # 這裡可以集成AI服務
        # 例如調用OpenAI、Anthropic等API
        self.logger.debug(f"AI處理中... (Model: {self.ai_model}, Personality: {self.personality})")
        
        try:
            # 簡單的回應示例
            if "hello" in message.content.lower():
                response_content = f"Hello {message.author.mention}! 我是 {self.user.display_name}"
                
                # 使用安全的API調用
                if self.api_manager:
                    await self.api_manager.send_message_safe(message.channel, response_content)
                else:
                    await message.channel.send(response_content)
                    
        except Exception as e:
            self.logger.error(f"AI回應處理失敗: {e}")
    
    async def safe_send_message(self, channel, content: str, **kwargs):
        """安全發送訊息的包裝方法"""
        if self.api_manager:
            return await self.api_manager.send_message_safe(channel, content, **kwargs)
        else:
            return await channel.send(content, **kwargs)
    
    def get_stats(self) -> Dict[str, Any]:
        """獲取子機器人統計資訊"""
        uptime = None
        if self.start_time:
            uptime = (datetime.now() - self.start_time).total_seconds()
        
        return {
            'bot_id': self.bot_id,
            'user_id': self.user.id if self.user else None,
            'username': str(self.user) if self.user else None,
            'message_count': self.message_count,
            'uptime_seconds': uptime,
            'last_activity': self.last_activity.isoformat() if self.last_activity else None,
            'guild_count': len(self.guilds),
            'latency': self.latency,
            'is_ready': self.is_ready(),
            'is_closed': self.is_closed()
        }


class SubBotStatus(Enum):
    """子機器人狀態枚舉"""
    OFFLINE = "offline"
    ONLINE = "online"
    CONNECTING = "connecting"
    ERROR = "error"
    MAINTENANCE = "maintenance"


class SubBotService(BaseService):
    """
    子機器人服務 - 增強版
    
    負責管理和協調所有子機器人的創建、配置和運行
    整合了SubBotManager、負載均衡器和擴展系統
    """
    
    def __init__(self, encryption_key: Optional[str] = None):
        """
        初始化子機器人服務
        
        Args:
            encryption_key: Token加密密鑰，如果不提供將使用配置系統
        """
        super().__init__("SubBotService")
        
        # 驗證加密庫可用性
        if not CRYPTOGRAPHY_AVAILABLE and not FERNET_AVAILABLE:
            raise SecurityError("缺少加密庫：請安裝 cryptography 套件 (pip install cryptography)")
        
        # 加密配置 - 優先級：參數 > 環境變數 > 配置文件 > 自動生成
        try:
            config = get_config()
            self._encryption_key = (
                encryption_key or 
                config.security.encryption_key or 
                self._generate_default_key()
            )
            # 使用配置中的加密算法設定
            self._preferred_algorithm = config.security.token_encryption_algorithm
            self._key_rotation_enabled = config.security.key_rotation_enabled
        except Exception as e:
            self.logger.warning(f"無法載入配置，使用預設設定: {e}")
            self._encryption_key = encryption_key or self._generate_default_key()
            self._preferred_algorithm = "AES-GCM"
            self._key_rotation_enabled = True
            
        self._init_encryption()
        
        # 輸入驗證器和並發管理器
        if VALIDATOR_AVAILABLE:
            self.validator = default_validator
            self.concurrency_manager = default_concurrency_manager
            self.logger.info("已啟用輸入驗證和並發安全管理")
        else:
            self.validator = None
            self.concurrency_manager = None
            self.logger.warning("輸入驗證模組不可用")
        
        # 子機器人註冊表（保持向後相容）
        self.registered_bots: Dict[str, Dict[str, Any]] = {}
        self.active_connections: Dict[str, Any] = {}
        
        # 新增：高級管理器組件
        self.manager: Optional[SubBotManager] = None
        self.load_balancer: Optional[SubBotLoadBalancer] = None
        self.performance_manager: Optional[PerformanceManager] = None
        self.extension_manager: Optional[ExtensionManager] = None
        
        # 服務配置
        self.config = {
            'max_sub_bots': 10,           # 最大子機器人數量
            'default_rate_limit': 10,     # 預設速率限制
            'health_check_interval': 60,  # 健康檢查間隔（秒）
            'connection_timeout': 30,     # 連線超時時間（秒）
            'encryption_algorithm': self._cipher_type,  # 加密算法
            'key_rotation_enabled': self._key_rotation_enabled,  # 是否啟用密鑰輪換
            'key_rotation_interval': 86400 * 30,  # 密鑰輪換間隔（30天）
            'key_backup_count': 3,  # 保留的舊密鑰數量
            
            # 新增：高級功能配置
            'enable_advanced_features': ADVANCED_COMPONENTS_AVAILABLE,
            'enable_load_balancing': True,
            'enable_performance_management': True,
            'enable_extensions': True,
            'auto_scaling': False,  # 自動擴縮容（實驗性功能）
        }
        
        # 密鑰管理
        self._key_rotation_task: Optional[asyncio.Task] = None
        self._key_version = 1  # 當前密鑰版本
        self._legacy_keys: Dict[int, str] = {}  # 舊版本密鑰保存，用於解密舊數據
    
    def __str__(self) -> str:
        """字符串表示，隱藏敏感資訊"""
        return f"SubBotService(algorithm={self._cipher_type}, bots={len(self.registered_bots)}, active={len(self.active_connections)})"
    
    def __repr__(self) -> str:
        """對象表示，隱藏敏感資訊"""
        return f"SubBotService(cipher_type='{self._cipher_type}', registered_bots={len(self.registered_bots)}, key_version={self._key_version})"
    
    def get_safe_dict(self) -> Dict[str, Any]:
        """獲取不包含敏感資訊的字典表示"""
        safe_dict = {
            'name': self.name,
            'cipher_type': self._cipher_type,
            'registered_bots_count': len(self.registered_bots),
            'active_connections_count': len(self.active_connections),
            'key_version': self._key_version,
            'legacy_keys_count': len(self._legacy_keys),
            'config': {k: v for k, v in self.config.items() if k != 'encryption_key'}
        }
        return safe_dict
    
    async def _initialize(self) -> bool:
        """初始化子機器人服務"""
        try:
            self.logger.info("正在初始化子機器人服務...")
            
            # 檢查加密密鑰
            if not self._encryption_key:
                raise SecurityError("缺少Token加密密鑰")
            
            # 載入已註冊的子機器人
            await self._load_registered_bots()
            
            # 初始化高級管理器組件
            if self.config['enable_advanced_features']:
                await self._initialize_advanced_components()
            
            # 啟動健康檢查任務
            asyncio.create_task(self._health_check_loop())
            
            # 啟動密鑰輪換任務（如果啟用）
            if self.config['key_rotation_enabled']:
                self._key_rotation_task = asyncio.create_task(self._key_rotation_loop())
                self.logger.info("已啟動密鑰輪換任務")
            
            self.logger.info(f"子機器人服務初始化完成，已載入 {len(self.registered_bots)} 個子機器人")
            return True
            
        except Exception as e:
            self.logger.error(f"子機器人服務初始化失敗: {e}")
            raise SubBotError(f"子機器人服務初始化失敗: {str(e)}")
    
    async def _initialize_advanced_components(self) -> None:
        """初始化高級管理器組件"""
        try:
            self.logger.info("正在初始化高級管理器組件...")
            
            # 初始化SubBotManager
            if ADVANCED_COMPONENTS_AVAILABLE:
                self.manager = SubBotManager()
                self.manager.add_dependency(self, "subbot_service")
                
                if not await self.manager.initialize():
                    raise SubBotError("SubBotManager初始化失敗")
                
                # 初始化負載均衡器
                if self.config['enable_load_balancing']:
                    from .subbot_load_balancer import LoadBalancingStrategy
                    self.load_balancer = SubBotLoadBalancer(
                        strategy=LoadBalancingStrategy.ADAPTIVE
                    )
                    
                # 初始化性能管理器
                if self.config['enable_performance_management']:
                    self.performance_manager = PerformanceManager()
                    
                    # 如果有負載均衡器，啟動性能監控
                    if self.load_balancer:
                        await self.performance_manager.start_monitoring(self.load_balancer)
                
                # 初始化擴展管理器
                if self.config['enable_extensions']:
                    self.extension_manager = ExtensionManager()
                    
                    if not await self.extension_manager.initialize():
                        self.logger.warning("擴展管理器初始化失敗，將繼續使用基本功能")
                        self.extension_manager = None
                
                self.logger.info("高級管理器組件初始化完成")
            else:
                self.logger.warning("高級組件不可用，將使用基本功能")
                
        except Exception as e:
            self.logger.error(f"初始化高級管理器組件失敗: {e}")
            # 不拋出異常，允許服務在基本模式下運行
    
    async def _cleanup(self) -> None:
        """清理子機器人服務資源"""
        try:
            self.logger.info("正在清理子機器人服務...")
            
            # 清理高級管理器組件
            if self.manager:
                await self.manager._cleanup()
            
            if self.performance_manager:
                await self.performance_manager.stop_monitoring()
                
            if self.extension_manager:
                await self.extension_manager.cleanup()
            
            # 停止密鑰輪換任務
            if self._key_rotation_task and not self._key_rotation_task.done():
                self._key_rotation_task.cancel()
                try:
                    await self._key_rotation_task
                except asyncio.CancelledError:
                    pass
                self.logger.info("已停止密鑰輪換任務")
            
            # 斷開所有活躍連線
            for bot_id, connection in list(self.active_connections.items()):
                try:
                    await self._disconnect_bot(bot_id)
                except Exception as e:
                    self.logger.warning(f"斷開子機器人 {bot_id} 連線時發生錯誤: {e}")
            
            # 清理資源
            self.registered_bots.clear()
            self.active_connections.clear()
            
            # 清理敏感資料
            self._legacy_keys.clear()
            
            self.logger.info("子機器人服務清理完成")
            
        except Exception as e:
            self.logger.error(f"清理子機器人服務時發生錯誤: {e}")
    
    async def _validate_permissions(
        self, 
        user_id: int, 
        guild_id: Optional[int], 
        action: str
    ) -> bool:
        """
        驗證子機器人操作權限
        
        Args:
            user_id: 使用者ID
            guild_id: 伺服器ID（可選）
            action: 要執行的操作
            
        Returns:
            是否有權限
        """
        try:
            # 系統管理員總是有權限（部署者/擁有者）
            system_admin_ids = self._get_system_admin_ids()
            if user_id in system_admin_ids:
                logger.info(f"系統管理員 {user_id} 執行操作 {action}")
                return True
            
            # 根據操作類型檢查權限
            if action in ['create', 'delete', 'configure']:
                return await self._check_admin_permissions(user_id, guild_id, action)
            elif action in ['status', 'list']:
                return await self._check_read_permissions(user_id, guild_id, action)
            elif action in ['start', 'stop', 'restart']:
                return await self._check_control_permissions(user_id, guild_id, action)
            else:
                logger.warning(f"未知操作類型: {action}")
                return False
                
        except Exception as e:
            logger.error(f"權限驗證失敗: {e}")
            return False  # 出錯時拒絕訪問
    
    def _get_system_admin_ids(self) -> Set[int]:
        """
        獲取系統管理員ID列表
        
        Returns:
            系統管理員ID集合
        """
        try:
            # 從配置獲取系統管理員ID
            admin_ids_str = os.getenv('DISCORD_ADMIN_IDS', '')
            admin_ids = set()
            
            if admin_ids_str:
                for admin_id in admin_ids_str.split(','):
                    try:
                        admin_ids.add(int(admin_id.strip()))
                    except ValueError:
                        logger.warning(f"無效的管理員ID: {admin_id}")
            
            # 如果沒有配置管理員，記錄警告
            if not admin_ids:
                logger.warning("未配置系統管理員ID，所有管理操作將被拒絕")
            
            return admin_ids
            
        except Exception as e:
            logger.error(f"獲取系統管理員ID失敗: {e}")
            return set()
    
    async def _check_admin_permissions(self, user_id: int, guild_id: Optional[int], action: str) -> bool:
        """
        檢查管理員權限（創建、刪除、配置子機器人）
        
        Args:
            user_id: 使用者ID
            guild_id: 伺服器ID（可選）
            action: 操作類型
            
        Returns:
            是否有權限
        """
        try:
            # 檢查是否為子機器人擁有者
            if action in ['delete', 'configure'] and guild_id:
                subbot_data = await self._get_subbot_by_guild(guild_id)
                if subbot_data and subbot_data.get('owner_id') == user_id:
                    return True
            
            # 檢查Discord伺服器管理權限（如果在伺服器內）
            if guild_id:
                return await self._check_discord_admin_permissions(user_id, guild_id)
            
            # 如果不在伺服器內，需要是系統管理員
            return False
            
        except Exception as e:
            logger.error(f"檢查管理員權限失敗: {e}")
            return False
    
    async def _check_read_permissions(self, user_id: int, guild_id: Optional[int], action: str) -> bool:
        """
        檢查讀取權限（查看狀態、列出子機器人）
        
        Args:
            user_id: 使用者ID
            guild_id: 伺服器ID（可選）
            action: 操作類型
            
        Returns:
            是否有權限
        """
        try:
            # 讀取權限相對寬鬆，但仍需基本驗證
            if guild_id:
                # 必須是伺服器成員
                return await self._check_guild_membership(user_id, guild_id)
            else:
                # 全域查詢需要管理權限
                return await self._check_admin_permissions(user_id, guild_id, action)
                
        except Exception as e:
            logger.error(f"檢查讀取權限失敗: {e}")
            return False
    
    async def _check_control_permissions(self, user_id: int, guild_id: Optional[int], action: str) -> bool:
        """
        檢查控制權限（啟動、停止、重啟子機器人）
        
        Args:
            user_id: 使用者ID
            guild_id: 伺服器ID（可選）
            action: 操作類型
            
        Returns:
            是否有權限
        """
        try:
            # 控制操作需要管理權限
            return await self._check_admin_permissions(user_id, guild_id, action)
            
        except Exception as e:
            logger.error(f"檢查控制權限失敗: {e}")
            return False
    
    async def _check_discord_admin_permissions(self, user_id: int, guild_id: int) -> bool:
        """
        檢查Discord伺服器管理權限
        
        Args:
            user_id: 使用者ID
            guild_id: 伺服器ID
            
        Returns:
            是否有管理權限
        """
        try:
            # 這裡需要Discord API調用來檢查實際權限
            # 由於這是後端服務，先實施基本邏輯
            
            # 檢查資料庫中是否記錄了此用戶的管理權限
            if hasattr(self, 'db_manager'):
                result = await self.db_manager.fetch_one(
                    """
                    SELECT has_admin_permission 
                    FROM user_guild_permissions 
                    WHERE user_id = ? AND guild_id = ?
                    """,
                    (user_id, guild_id)
                )
                
                if result:
                    return bool(result['has_admin_permission'])
            
            # 如果沒有記錄，暫時拒絕（安全優先）
            logger.warning(f"找不到用戶 {user_id} 在伺服器 {guild_id} 的權限記錄")
            return False
            
        except Exception as e:
            logger.error(f"檢查Discord管理權限失敗: {e}")
            return False
    
    async def _check_guild_membership(self, user_id: int, guild_id: int) -> bool:
        """
        檢查用戶是否為伺服器成員
        
        Args:
            user_id: 使用者ID
            guild_id: 伺服器ID
            
        Returns:
            是否為伺服器成員
        """
        try:
            # 檢查用戶是否在伺服器成員列表中
            if hasattr(self, 'db_manager'):
                result = await self.db_manager.fetch_one(
                    """
                    SELECT 1 
                    FROM guild_members 
                    WHERE user_id = ? AND guild_id = ? AND is_active = 1
                    """,
                    (user_id, guild_id)
                )
                
                return result is not None
            
            # 如果沒有資料庫連接，暫時允許（但記錄警告）
            logger.warning("無法驗證伺服器成員身份，暫時允許訪問")
            return True
            
        except Exception as e:
            logger.error(f"檢查伺服器成員身份失敗: {e}")
            return False
    
    async def _get_subbot_by_guild(self, guild_id: int) -> Optional[Dict[str, Any]]:
        """
        根據伺服器ID獲取子機器人資料
        
        Args:
            guild_id: 伺服器ID
            
        Returns:
            子機器人資料或None
        """
        try:
            if hasattr(self, 'db_manager'):
                result = await self.db_manager.fetch_one(
                    """
                    SELECT * 
                    FROM subbots 
                    WHERE guild_id = ? AND is_active = 1
                    """,
                    (guild_id,)
                )
                
                return dict(result) if result else None
            
            return None
            
        except Exception as e:
            logger.error(f"獲取子機器人資料失敗: {e}")
            return None
    
    async def create_subbot(
        self, 
        name: str, 
        token: str, 
        owner_id: int,
        channel_restrictions: Optional[List[int]] = None,
        ai_enabled: bool = False,
        ai_model: Optional[str] = None,
        personality: Optional[str] = None,
        rate_limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        創建新的子機器人
        
        Args:
            name: 子機器人名稱
            token: Discord Bot Token
            owner_id: 子機器人擁有者ID
            channel_restrictions: 限制的頻道ID列表（可選）
            ai_enabled: 是否啟用AI功能
            ai_model: AI模型名稱
            personality: AI人格設定
            rate_limit: 速率限制
            
        Returns:
            創建結果字典，包含success和bot_id
        """
        try:
            # 輸入驗證
            if self.validator:
                validation_result = await self.validator.validate_bot_creation_input(
                    name=name,
                    token=token,
                    owner_id=owner_id,
                    channel_restrictions=channel_restrictions,
                    ai_model=ai_model,
                    personality=personality
                )
                
                if not validation_result['is_valid']:
                    raise SubBotCreationError(
                        bot_id="未知",
                        reason=f"輸入驗證失敗: {'; '.join(validation_result['errors'])}"
                    )
                
                if validation_result['warnings']:
                    for warning in validation_result['warnings']:
                        self.logger.warning(f"創建子機器人警告: {warning}")
            
            # 檢查數量限制
            if len(self.registered_bots) >= self.config['max_sub_bots']:
                raise SubBotCreationError(bot_id="未知", reason=f"子機器人數量已達上限 {self.config['max_sub_bots']}")
            
            # 驗證Token格式
            if not self._validate_token_format(token):
                raise SubBotTokenError(bot_id="未知", token_issue="無效的Discord Bot Token格式")
            
            # 驗證擁有者ID
            if not owner_id:
                raise SubBotCreationError(
                    bot_id="未知",
                    reason="必須指定擁有者ID"
                )
            
            # 生成子機器人ID
            bot_id = self._generate_bot_id(name)
            
            # 加密存儲Token
            token_hash = self._encrypt_token(token)
            
            # 創建子機器人配置
            bot_config = {
                'bot_id': bot_id,
                'name': name,
                'token_hash': token_hash,
                'owner_id': owner_id,
                'channel_restrictions': channel_restrictions or [],
                'ai_enabled': ai_enabled,
                'ai_model': ai_model,
                'personality': personality,
                'rate_limit': rate_limit or self.config['default_rate_limit'],
                'status': SubBotStatus.OFFLINE.value,
                'created_at': datetime.now().isoformat(),
                'message_count': 0
            }
            
            # 保存到資料庫
            await self._save_bot_to_database(bot_config)
            
            # 註冊到內存
            self.registered_bots[bot_id] = bot_config
            
            # 配置頻道權限（如果有限制）
            if channel_restrictions:
                await self._configure_bot_channels(bot_id, channel_restrictions)
            
            self.logger.info(f"成功創建子機器人: {bot_id} ({name})")
            return {
                'success': True,
                'bot_id': bot_id,
                'name': name,
                'owner_id': owner_id,
                'status': SubBotStatus.OFFLINE.value
            }
            
        except Exception as e:
            self.logger.error(f"創建子機器人失敗: {e}")
            if isinstance(e, (SubBotCreationError, SubBotTokenError, SubBotChannelError)):
                raise
            raise SubBotCreationError(bot_id="未知", reason=str(e))
    
    async def delete_sub_bot(self, bot_id: str) -> bool:
        """
        刪除子機器人
        
        Args:
            bot_id: 子機器人ID
            
        Returns:
            是否成功刪除
        """
        try:
            # 檢查子機器人是否存在
            if bot_id not in self.registered_bots:
                raise SubBotError(f"子機器人不存在: {bot_id}")
            
            # 如果正在運行，先斷開連線
            if bot_id in self.active_connections:
                await self._disconnect_bot(bot_id)
            
            # 從資料庫刪除
            await self._delete_bot_from_database(bot_id)
            
            # 從內存中移除
            del self.registered_bots[bot_id]
            
            self.logger.info(f"成功刪除子機器人: {bot_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"刪除子機器人失敗: {e}")
            raise
    
    async def connect_subbot(self, bot_id: str) -> Dict[str, Any]:
        """
        連線子機器人到Discord
        
        Args:
            bot_id: 子機器人ID
            
        Returns:
            連線結果字典
        """
        try:
            # 檢查子機器人是否存在
            if bot_id not in self.registered_bots:
                raise SubBotError(f"子機器人不存在: {bot_id}")
            
            bot_config = self.registered_bots[bot_id]
            
            # 檢查是否已經在運行
            if bot_id in self.active_connections:
                self.logger.warning(f"子機器人 {bot_id} 已經在運行")
                return {
                    'success': True,
                    'bot_id': bot_id,
                    'status': 'already_connected',
                    'message': '子機器人已經連線'
                }
            
            # 解密Token
            token = self._decrypt_token(bot_config['token_hash'])
            
            # 創建Discord客戶端（這裡需要實際的Discord.py集成）
            # 暫時模擬連線成功
            success = await self._create_discord_connection(bot_id, token, bot_config)
            
            if success:
                # 更新狀態
                bot_config['status'] = SubBotStatus.ONLINE.value
                bot_config['last_active_at'] = datetime.now().isoformat()
                
                # 更新資料庫
                await self._update_bot_status(bot_id, SubBotStatus.ONLINE.value)
                
                self.logger.info(f"成功啟動子機器人: {bot_id}")
                return {
                    'success': True,
                    'bot_id': bot_id,
                    'status': SubBotStatus.ONLINE.value,
                    'connected_at': datetime.now().isoformat()
                }
            else:
                raise SubBotError(f"無法建立Discord連線: {bot_id}")
                
        except Exception as e:
            self.logger.error(f"啟動子機器人失敗: {e}")
            # 更新狀態為錯誤
            if bot_id in self.registered_bots:
                await self._update_bot_status(bot_id, SubBotStatus.ERROR.value)
            if isinstance(e, SubBotError):
                raise
            raise SubBotError(f"連線子機器人失敗: {str(e)}", bot_id=bot_id)
    
    async def disconnect_subbot(self, bot_id: str) -> Dict[str, Any]:
        """
        斷開子機器人連線
        
        Args:
            bot_id: 子機器人ID
            
        Returns:
            斷開連線結果字典
        """
        try:
            if bot_id not in self.registered_bots:
                raise SubBotError(f"子機器人不存在: {bot_id}")
            
            # 斷開連線
            success = await self._disconnect_bot(bot_id)
            
            if success:
                # 更新狀態
                self.registered_bots[bot_id]['status'] = SubBotStatus.OFFLINE.value
                await self._update_bot_status(bot_id, SubBotStatus.OFFLINE.value)
                
                self.logger.info(f"成功停止子機器人: {bot_id}")
                return {
                    'success': True,
                    'bot_id': bot_id,
                    'status': SubBotStatus.OFFLINE.value,
                    'disconnected_at': datetime.now().isoformat()
                }
            
            return {
                'success': False,
                'bot_id': bot_id,
                'error': '斷開連線失敗'
            }
            
        except Exception as e:
            self.logger.error(f"停止子機器人失敗: {e}")
            if isinstance(e, SubBotError):
                raise
            raise SubBotError(f"斷開子機器人連線失敗: {str(e)}", bot_id=bot_id)
    
    async def get_bot_status(self, bot_id: str) -> Dict[str, Any]:
        """
        獲取子機器人狀態
        
        Args:
            bot_id: 子機器人ID
            
        Returns:
            子機器人狀態資訊
        """
        if bot_id not in self.registered_bots:
            raise SubBotError(f"子機器人不存在: {bot_id}")
        
        bot_config = self.registered_bots[bot_id].copy()
        
        # 移除敏感資訊
        if 'token_hash' in bot_config:
            del bot_config['token_hash']
        
        # 添加運行時資訊
        bot_config['is_connected'] = bot_id in self.active_connections
        
        return bot_config
    
    async def list_sub_bots(self) -> List[Dict[str, Any]]:
        """
        列出所有子機器人
        
        Returns:
            子機器人列表
        """
        bot_list = []
        
        for bot_id, bot_config in self.registered_bots.items():
            # 獲取狀態資訊（不包含敏感資料）
            status = await self.get_bot_status(bot_id)
            bot_list.append(status)
        
        return bot_list
    
    # 私有方法
    
    def _generate_default_key(self) -> str:
        """生成預設加密密鑰"""
        import secrets
        # 生成256位（32字節）的強隨機密鑰
        key = secrets.token_hex(32)
        self.logger.warning("使用自動生成的加密密鑰。生產環境請設定 ROAS_ENCRYPTION_KEY 環境變數")
        return key
    
    def _encrypt_token_aes_gcm(self, token: str) -> str:
        """使用AES-256-GCM加密Token"""
        # 生成隨機IV
        iv = os.urandom(12)  # GCM建議使用12字節IV
        
        # 從密鑰派生加密密鑰
        key = self._derive_key(iv)
        
        # 創建加密器
        cipher = Cipher(
            algorithms.AES(key),
            modes.GCM(iv),
            backend=default_backend()
        )
        
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(token.encode('utf-8')) + encryptor.finalize()
        
        # 組合: iv + auth_tag + ciphertext
        encrypted_data = iv + encryptor.tag + ciphertext
        
        # Base64編碼返回
        return base64.b64encode(encrypted_data).decode('ascii')
    
    def _decrypt_token_aes_gcm(self, encrypted_token: str) -> str:
        """使用AES-256-GCM解密Token"""
        try:
            # Base64解碼
            encrypted_data = base64.b64decode(encrypted_token.encode('ascii'))
            
            # 分解組件
            iv = encrypted_data[:12]
            auth_tag = encrypted_data[12:28]
            ciphertext = encrypted_data[28:]
            
            # 從密鑰派生加密密鑰
            key = self._derive_key(iv)
            
            # 創建解密器
            cipher = Cipher(
                algorithms.AES(key),
                modes.GCM(iv, auth_tag),
                backend=default_backend()
            )
            
            decryptor = cipher.decryptor()
            plaintext = decryptor.update(ciphertext) + decryptor.finalize()
            
            return plaintext.decode('utf-8')
            
        except Exception as e:
            self.logger.error(f"AES-GCM解密失敗: {e}")
            raise SubBotTokenError(bot_id="AES解密錯誤", token_issue=f"Token解密失敗: 數據可能已損壞")
    
    def _encrypt_token_fernet(self, token: str) -> str:
        """使用Fernet加密Token"""
        encrypted = self._fernet.encrypt(token.encode('utf-8'))
        return base64.b64encode(encrypted).decode('ascii')
    
    def _decrypt_token_fernet(self, encrypted_token: str) -> str:
        """使用Fernet解密Token"""
        try:
            encrypted_data = base64.b64decode(encrypted_token.encode('ascii'))
            decrypted = self._fernet.decrypt(encrypted_data)
            return decrypted.decode('utf-8')
        except Exception as e:
            self.logger.error(f"Fernet解密失敗: {e}")
            raise SubBotTokenError(bot_id="AES解密錯誤", token_issue=f"Token解密失敗: 數據可能已損壞")
    
    def _derive_key(self, salt: bytes) -> bytes:
        """從主密鑰派生加密密鑰"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # 256位密鑰
            salt=salt,
            iterations=100000,  # 推薦的最小迭代次數
            backend=default_backend()
        )
        return kdf.derive(self._encryption_key.encode('utf-8'))
    
    def _generate_bot_id(self, name: str) -> str:
        """生成唯一的子機器人ID"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        name_hash = hashlib.md5(name.encode()).hexdigest()[:8]
        return f"subbot_{timestamp}_{name_hash}"
    
    def _validate_token(self, token: str) -> bool:
        """
        驗證Discord Token格式（擴展版本）
        支援更嚴格的Token格式驗證
        
        Args:
            token: Discord Bot Token
            
        Returns:
            是否為有效Token格式
        """
        if not token or not isinstance(token, str):
            return False
            
        # 基本長度檢查
        if len(token) < 50:
            return False
            
        # Discord Bot Token 通常由三部分組成，以點分隔
        token_parts = token.split('.')
        if len(token_parts) != 3:
            return False
            
        # 第一部分：Bot ID (Base64編碼)
        # 第二部分：時間戳
        # 第三部分：HMAC簽名
        try:
            import base64
            # 嘗試解碼第一部分 (Bot ID)
            base64.b64decode(token_parts[0] + '==')  # 添加padding
            return True
        except Exception:
            # 如果解碼失敗，可能是舊格式的Token，使用基本驗證
            return self._validate_token_format(token)
    
    def _validate_token_format(self, token: str) -> bool:
        """驗證Discord Token格式"""
        if not token or len(token) < 50:
            return False
        
        # Discord Bot Token 通常以特定前綴開始
        # 這裡可以添加更詳細的驗證邏輯
        return True
    
    def _init_encryption(self) -> None:
        """初始化加密組件"""
        # 根據配置和可用性選擇加密方法
        if (self._preferred_algorithm == "AES-GCM" and CRYPTOGRAPHY_AVAILABLE) or \
           (not FERNET_AVAILABLE and CRYPTOGRAPHY_AVAILABLE):
            # 使用AES-256-GCM，最安全的選項
            self._cipher_type = "AES-GCM"
            self.logger.info("使用 AES-256-GCM 加密 Token")
        elif FERNET_AVAILABLE:
            # Fallback到Fernet
            self._cipher_type = "Fernet"
            # 確保密鑰格式正確
            if isinstance(self._encryption_key, str):
                key_bytes = self._encryption_key.encode()[:32].ljust(32, b'\0')
                self._fernet_key = base64.urlsafe_b64encode(key_bytes)
                self._fernet = Fernet(self._fernet_key)
            self.logger.info("使用 Fernet 加密 Token")
        else:
            raise SecurityError("無可用的加密後端")
    
    def _encrypt_token(self, token: str) -> str:
        """使用AES-256-GCM或Fernet加密Token"""
        try:
            if self._cipher_type == "AES-GCM" and CRYPTOGRAPHY_AVAILABLE:
                return self._encrypt_token_aes_gcm(token)
            elif self._cipher_type == "Fernet" and FERNET_AVAILABLE:
                return self._encrypt_token_fernet(token)
            else:
                raise SecurityError("無可用的加密方法")
        except Exception as e:
            self.logger.error(f"Token加密失敗: {e}")
            raise SubBotTokenError(bot_id="加密錯誤", token_issue=f"Token加密失敗: {str(e)}")
    
    def _decrypt_token(self, encrypted_token: str) -> str:
        """解密Token"""
        try:
            if self._cipher_type == "AES-GCM" and CRYPTOGRAPHY_AVAILABLE:
                return self._decrypt_token_aes_gcm(encrypted_token)
            elif self._cipher_type == "Fernet" and FERNET_AVAILABLE:
                return self._decrypt_token_fernet(encrypted_token)
            else:
                raise SecurityError("無可用的解密方法")
        except Exception as e:
            self.logger.error(f"Token解密失敗: {e}")
            raise SubBotTokenError(bot_id="解密錯誤", token_issue=f"Token解密失敗: {str(e)}")
    
    async def _load_registered_bots(self) -> None:
        """從資料庫載入已註冊的子機器人"""
        db_manager = self.get_dependency("database_manager")
        if db_manager:
            try:
                bots = await db_manager.fetchall("SELECT * FROM sub_bots")
                for bot in bots:
                    bot_dict = dict(bot)
                    # 將資料庫的 target_channels 轉換為內部使用的 channel_restrictions
                    if 'target_channels' in bot_dict:
                        try:
                            bot_dict['channel_restrictions'] = json.loads(bot_dict['target_channels'])
                        except (json.JSONDecodeError, TypeError):
                            bot_dict['channel_restrictions'] = []
                        # 保留原始資料庫欄位以供相容性
                        # del bot_dict['target_channels']  # 可選：如果不需要保留原始欄位
                    
                    self.registered_bots[bot_dict['bot_id']] = bot_dict
                
                self.logger.info(f"從資料庫載入了 {len(bots)} 個子機器人")
            except Exception as e:
                self.logger.warning(f"載入子機器人資料失敗: {e}")
    
    async def _save_bot_to_database(self, bot_config: Dict[str, Any]) -> None:
        """保存子機器人配置到資料庫"""
        db_manager = self.get_dependency("database_manager")
        if db_manager:
            try:
                await db_manager.execute(
                    """INSERT INTO sub_bots 
                       (bot_id, name, token_hash, target_channels, ai_enabled, ai_model, 
                        personality, rate_limit, status, created_at, message_count)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        bot_config['bot_id'],
                        bot_config['name'], 
                        bot_config['token_hash'],
                        json.dumps(bot_config.get('channel_restrictions', [])),  # 內部使用 channel_restrictions，存儲為 target_channels
                        bot_config['ai_enabled'],
                        bot_config['ai_model'],
                        bot_config['personality'],
                        bot_config['rate_limit'],
                        bot_config['status'],
                        bot_config['created_at'],
                        bot_config['message_count']
                    )
                )
            except Exception as e:
                self.logger.error(f"保存子機器人到資料庫失敗: {e}")
                raise
    
    async def _delete_bot_from_database(self, bot_id: str) -> None:
        """從資料庫刪除子機器人"""
        db_manager = self.get_dependency("database_manager")
        if db_manager:
            try:
                await db_manager.execute("DELETE FROM sub_bots WHERE bot_id = ?", (bot_id,))
                # 同時刪除相關的頻道配置
                await db_manager.execute("DELETE FROM sub_bot_channels WHERE sub_bot_id = (SELECT id FROM sub_bots WHERE bot_id = ?)", (bot_id,))
            except Exception as e:
                self.logger.error(f"從資料庫刪除子機器人失敗: {e}")
                raise
    
    async def _update_bot_status(self, bot_id: str, status: str) -> None:
        """更新子機器人狀態"""
        db_manager = self.get_dependency("database_manager")
        if db_manager:
            try:
                await db_manager.execute(
                    "UPDATE sub_bots SET status = ?, updated_at = ? WHERE bot_id = ?",
                    (status, datetime.now().isoformat(), bot_id)
                )
            except Exception as e:
                self.logger.warning(f"更新子機器人狀態失敗: {e}")
    
    async def _configure_bot_channels(self, bot_id: str, channel_ids: List[int]) -> None:
        """配置子機器人頻道權限"""
        db_manager = self.get_dependency("database_manager")
        if db_manager:
            try:
                # 首先獲取sub_bot的數據庫ID
                result = await db_manager.fetchone("SELECT id FROM sub_bots WHERE bot_id = ?", (bot_id,))
                if result:
                    sub_bot_db_id = result['id']
                    
                    # 為每個頻道創建配置記錄
                    for channel_id in channel_ids:
                        await db_manager.execute(
                            "INSERT INTO sub_bot_channels (sub_bot_id, channel_id, channel_type, permissions) VALUES (?, ?, ?, ?)",
                            (sub_bot_db_id, channel_id, 'text', json.dumps({'send_messages': True, 'read_messages': True}))
                        )
            except Exception as e:
                self.logger.warning(f"配置子機器人頻道權限失敗: {e}")
    
    async def _create_discord_connection(self, bot_id: str, token: str, config: Dict[str, Any]) -> bool:
        """創建Discord連線（實際實作）"""
        if not DISCORD_AVAILABLE:
            self.logger.error("Discord.py未安裝，無法創建Discord連線")
            return False
        
        try:
            # 創建子機器人客戶端
            client = SubBotClient(bot_id, config, self)
            
            # 創建異步任務來運行機器人
            async def run_bot():
                try:
                    await client.start(token)
                except Exception as e:
                    self.logger.error(f"子機器人 {bot_id} 連線失敗: {e}")
                    raise
            
            # 啟動機器人（非阻塞）
            bot_task = asyncio.create_task(run_bot())
            
            # 等待機器人準備就緒（最多等待30秒）
            ready_timeout = self.config.get('connection_timeout', 30)
            
            try:
                await asyncio.wait_for(client.wait_until_ready(), timeout=ready_timeout)
                
                # 保存連線資訊
                self.active_connections[bot_id] = {
                    'client': client,
                    'task': bot_task,
                    'connected_at': datetime.now(),
                    'token_last_4': token[-4:] if len(token) > 4 else "****"  # 只保存最後4位用於調試
                }
                
                self.logger.info(f"子機器人 {bot_id} 成功連線到Discord")
                return True
                
            except asyncio.TimeoutError:
                self.logger.error(f"子機器人 {bot_id} 連線超時")
                bot_task.cancel()
                try:
                    await bot_task
                except asyncio.CancelledError:
                    pass
                return False
                
        except Exception as e:
            self.logger.error(f"創建Discord連線失敗: {e}")
            return False
    
    async def _disconnect_bot(self, bot_id: str) -> bool:
        """斷開子機器人連線"""
        if bot_id in self.active_connections:
            try:
                connection = self.active_connections[bot_id]
                
                # 關閉Discord客戶端
                if 'client' in connection and connection['client']:
                    client = connection['client']
                    if not client.is_closed():
                        await client.close()
                        self.logger.info(f"子機器人 {bot_id} Discord客戶端已關閉")
                
                # 取消異步任務
                if 'task' in connection and connection['task']:
                    task = connection['task']
                    if not task.done():
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass
                        self.logger.info(f"子機器人 {bot_id} 異步任務已取消")
                
                # 從活躍連線中移除
                del self.active_connections[bot_id]
                return True
                
            except Exception as e:
                self.logger.error(f"斷開連線失敗: {e}")
                return False
        
        return True
    
    # Discord事件處理方法
    
    async def _on_bot_ready(self, bot_id: str, user):
        """當子機器人準備就緒時調用"""
        if bot_id in self.registered_bots:
            self.registered_bots[bot_id]['discord_user_id'] = user.id
            self.registered_bots[bot_id]['discord_username'] = str(user)
            self.registered_bots[bot_id]['ready_at'] = datetime.now().isoformat()
            
            # 更新資料庫狀態
            await self._update_bot_status(bot_id, SubBotStatus.ONLINE.value)
            
            self.logger.info(f"子機器人 {bot_id} 準備完成: {user}")
    
    async def _on_message_received(self, bot_id: str, message):
        """當子機器人收到訊息時調用"""
        if bot_id in self.registered_bots:
            # 更新訊息統計
            self.registered_bots[bot_id]['message_count'] += 1
            self.registered_bots[bot_id]['last_message_at'] = datetime.now().isoformat()
            
            # 可以在這裡添加訊息日誌記錄
            self.logger.debug(f"子機器人 {bot_id} 收到訊息來自 {message.author}")
    
    async def _on_bot_error(self, bot_id: str, event: str, args: tuple, kwargs: dict):
        """當子機器人發生錯誤時調用"""
        error_info = {
            'bot_id': bot_id,
            'event': event,
            'timestamp': datetime.now().isoformat(),
            'error_details': str(args) if args else None
        }
        
        self.logger.error(f"子機器人 {bot_id} 錯誤事件 {event}: {error_info}")
        
        # 如果是嚴重錯誤，可以考慮重新連線或標記為錯誤狀態
        if event in ['on_ready', 'on_connect']:
            await self._update_bot_status(bot_id, SubBotStatus.ERROR.value)
    
    async def get_bot_connection_info(self, bot_id: str) -> Optional[Dict[str, Any]]:
        """獲取子機器人連線詳細資訊"""
        if bot_id not in self.active_connections:
            return None
            
        connection = self.active_connections[bot_id]
        client = connection.get('client')
        
        if not client:
            return None
        
        stats = client.get_stats()
        connection_info = {
            'bot_id': bot_id,
            'connected_at': connection.get('connected_at').isoformat() if connection.get('connected_at') else None,
            'is_ready': client.is_ready() if hasattr(client, 'is_ready') else False,
            'is_closed': client.is_closed() if hasattr(client, 'is_closed') else True,
            'latency_ms': round(client.latency * 1000, 2) if hasattr(client, 'latency') else None,
            'guild_count': len(client.guilds) if hasattr(client, 'guilds') else 0,
            **stats
        }
        
        return connection_info
    
    async def send_message_to_channel(self, bot_id: str, channel_id: int, content: str, **kwargs) -> Optional[Dict[str, Any]]:
        """使用子機器人發送訊息到指定頻道"""
        if bot_id not in self.active_connections:
            raise SubBotError(f"子機器人 {bot_id} 未連線", bot_id=bot_id)
        
        connection = self.active_connections[bot_id]
        client = connection.get('client')
        
        if not client or client.is_closed():
            raise SubBotError(f"子機器人 {bot_id} 客戶端未就緒", bot_id=bot_id)
        
        try:
            channel = client.get_channel(channel_id)
            if not channel:
                raise SubBotChannelError(
                    bot_id=bot_id,
                    channel_id=str(channel_id),
                    operation="send_message",
                    reason="找不到指定的頻道"
                )
            
            # 檢查頻道權限
            if hasattr(client, 'channel_restrictions') and client.channel_restrictions:
                if channel_id not in client.channel_restrictions:
                    raise SubBotChannelError(
                        bot_id=bot_id,
                        channel_id=str(channel_id),
                        operation="send_message",
                        reason="沒有權限在此頻道發送訊息"
                    )
            
            message = await client.safe_send_message(channel, content, **kwargs)
            
            return {
                'success': True,
                'message_id': message.id,
                'channel_id': channel_id,
                'content_length': len(content),
                'sent_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"子機器人 {bot_id} 發送訊息失敗: {e}")
            if isinstance(e, SubBotChannelError):
                raise
            raise SubBotError(f"發送訊息失敗: {str(e)}", bot_id=bot_id)
    
    # ========== 服務間通訊API ==========
    
    async def get_service_status(self) -> Dict[str, Any]:
        """獲取子機器人服務整體狀態"""
        try:
            total_bots = len(self.registered_bots)
            online_bots = len([bot for bot in self.registered_bots.values() 
                             if bot.get('status') == SubBotStatus.ONLINE.value])
            error_bots = len([bot for bot in self.registered_bots.values() 
                            if bot.get('status') == SubBotStatus.ERROR.value])
            
            service_status = {
                'service_name': self.name,
                'initialized': self.is_initialized,
                'uptime_seconds': self.uptime,
                'total_bots': total_bots,
                'online_bots': online_bots,
                'error_bots': error_bots,
                'active_connections': len(self.active_connections),
                'encryption_info': self.get_encryption_info(),
                'health_status': 'healthy' if online_bots == total_bots else 'degraded' if online_bots > 0 else 'critical',
                'last_updated': datetime.now().isoformat()
            }
            
            return service_status
            
        except Exception as e:
            self.logger.error(f"獲取服務狀態失敗: {e}")
            return {
                'service_name': self.name,
                'health_status': 'error',
                'error': str(e),
                'last_updated': datetime.now().isoformat()
            }
    
    async def get_all_bot_statuses(self) -> List[Dict[str, Any]]:
        """獲取所有子機器人的詳細狀態"""
        statuses = []
        
        for bot_id, bot_config in self.registered_bots.items():
            try:
                # 基本配置信息
                status = {
                    'bot_id': bot_id,
                    'name': bot_config.get('name'),
                    'status': bot_config.get('status', SubBotStatus.OFFLINE.value),
                    'created_at': bot_config.get('created_at'),
                    'message_count': bot_config.get('message_count', 0),
                    'ai_enabled': bot_config.get('ai_enabled', False),
                    'is_connected': bot_id in self.active_connections
                }
                
                # 連線詳細信息
                connection_info = await self.get_bot_connection_info(bot_id)
                if connection_info:
                    status['connection_info'] = connection_info
                
                statuses.append(status)
                
            except Exception as e:
                self.logger.warning(f"獲取子機器人 {bot_id} 狀態時發生錯誤: {e}")
                statuses.append({
                    'bot_id': bot_id,
                    'status': 'error',
                    'error': str(e)
                })
        
        return statuses
    
    async def broadcast_message_to_all(self, content: str, channel_filter: Optional[List[int]] = None) -> Dict[str, Any]:
        """向所有在線的子機器人廣播訊息"""
        results = {
            'success_count': 0,
            'error_count': 0,
            'results': []
        }
        
        for bot_id in list(self.active_connections.keys()):
            try:
                connection = self.active_connections[bot_id]
                client = connection.get('client')
                
                if not client or client.is_closed():
                    continue
                
                # 發送到機器人的第一個可用頻道（示例邏輯）
                if client.guilds:
                    for guild in client.guilds:
                        for channel in guild.text_channels:
                            # 如果有頻道過濾器，檢查頻道是否在列表中
                            if channel_filter and channel.id not in channel_filter:
                                continue
                                
                            # 檢查權限
                            if channel.permissions_for(guild.me).send_messages:
                                try:
                                    await client.safe_send_message(channel, content)
                                    results['results'].append({
                                        'bot_id': bot_id,
                                        'channel_id': channel.id,
                                        'success': True
                                    })
                                    results['success_count'] += 1
                                    break  # 只發送到第一個可用頻道
                                    
                                except Exception as e:
                                    results['results'].append({
                                        'bot_id': bot_id,
                                        'channel_id': channel.id,
                                        'success': False,
                                        'error': str(e)
                                    })
                                    results['error_count'] += 1
                        
                        if any(r['bot_id'] == bot_id and r['success'] for r in results['results']):
                            break  # 如果已經成功發送，跳出公會循環
                            
            except Exception as e:
                self.logger.error(f"廣播到子機器人 {bot_id} 失敗: {e}")
                results['results'].append({
                    'bot_id': bot_id,
                    'success': False,
                    'error': str(e)
                })
                results['error_count'] += 1
        
        return results
    
    async def restart_bot(self, bot_id: str) -> Dict[str, Any]:
        """重啟指定的子機器人"""
        try:
            if bot_id not in self.registered_bots:
                raise SubBotError(f"子機器人不存在: {bot_id}")
            
            # 如果正在運行，先斷開
            if bot_id in self.active_connections:
                disconnect_result = await self.disconnect_subbot(bot_id)
                if not disconnect_result.get('success', False):
                    raise SubBotError(f"無法斷開子機器人 {bot_id}")
                
                # 等待一段時間讓資源完全釋放
                await asyncio.sleep(2)
            
            # 重新連線
            connect_result = await self.connect_subbot(bot_id)
            
            return {
                'success': True,
                'bot_id': bot_id,
                'message': '子機器人重啟成功',
                'status': connect_result.get('status'),
                'restarted_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"重啟子機器人 {bot_id} 失敗: {e}")
            return {
                'success': False,
                'bot_id': bot_id,
                'error': str(e),
                'attempted_at': datetime.now().isoformat()
            }
    
    async def batch_operation(self, operation: str, bot_ids: List[str], **kwargs) -> Dict[str, Any]:
        """批次操作多個子機器人"""
        supported_operations = ['connect', 'disconnect', 'restart', 'status']
        
        if operation not in supported_operations:
            raise ValueError(f"不支持的操作: {operation}。支持的操作: {supported_operations}")
        
        results = {
            'operation': operation,
            'total_requested': len(bot_ids),
            'success_count': 0,
            'error_count': 0,
            'results': []
        }
        
        for bot_id in bot_ids:
            try:
                if operation == 'connect':
                    result = await self.connect_subbot(bot_id)
                elif operation == 'disconnect':
                    result = await self.disconnect_subbot(bot_id)
                elif operation == 'restart':
                    result = await self.restart_bot(bot_id)
                elif operation == 'status':
                    result = await self.get_bot_status(bot_id)
                    result['success'] = True  # status操作總是成功的
                
                if result.get('success', False):
                    results['success_count'] += 1
                else:
                    results['error_count'] += 1
                
                results['results'].append({
                    'bot_id': bot_id,
                    **result
                })
                
            except Exception as e:
                self.logger.error(f"批次操作 {operation} 對子機器人 {bot_id} 失敗: {e}")
                results['error_count'] += 1
                results['results'].append({
                    'bot_id': bot_id,
                    'success': False,
                    'error': str(e)
                })
        
        return results
    
    async def _health_check_loop(self) -> None:
        """健康檢查循環"""
        while True:
            try:
                await asyncio.sleep(self.config['health_check_interval'])
                
                # 檢查所有活躍連線的健康狀態
                for bot_id in list(self.active_connections.keys()):
                    try:
                        # 實作健康檢查邏輯
                        await self._check_bot_health(bot_id)
                    except Exception as e:
                        self.logger.warning(f"子機器人 {bot_id} 健康檢查失敗: {e}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"健康檢查循環錯誤: {e}")
    
    async def _check_bot_health(self, bot_id: str) -> bool:
        """檢查單個子機器人的健康狀態"""
        # 實作具體的健康檢查邏輯
        # 例如：檢查WebSocket連線、延遲測試等
        return True
    
    async def _key_rotation_loop(self) -> None:
        """密鑰輪換循環"""
        while True:
            try:
                await asyncio.sleep(self.config['key_rotation_interval'])
                
                if self.config['key_rotation_enabled']:
                    await self._rotate_encryption_key()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"密鑰輪換循環錯誤: {e}")
    
    async def _rotate_encryption_key(self) -> bool:
        """執行密鑰輪換"""
        try:
            self.logger.info("開始執行密鑰輪換...")
            
            # 保存當前密鑰作為舊版本
            old_version = self._key_version
            self._legacy_keys[old_version] = self._encryption_key
            
            # 生成新密鑰
            new_key = self._generate_default_key()
            
            # 更新密鑰版本
            self._key_version += 1
            self._encryption_key = new_key
            
            # 重新初始化加密組件
            self._init_encryption()
            
            # 重新加密所有存儲的Token（如果需要）
            await self._reencrypt_stored_tokens(old_version)
            
            # 清理過期的舊密鑰
            self._cleanup_legacy_keys()
            
            self.logger.info(f"密鑰輪換完成，新版本: {self._key_version}")
            return True
            
        except Exception as e:
            self.logger.error(f"密鑰輪換失敗: {e}")
            return False
    
    async def _reencrypt_stored_tokens(self, old_version: int) -> None:
        """使用新密鑰重新加密所有存儲的Token"""
        try:
            # 這裡需要與資料庫服務配合，重新加密所有Token
            # 由於這是安全關鍵操作，需要原子性執行
            for bot_id, bot_config in list(self.registered_bots.items()):
                if 'token_hash' in bot_config:
                    # 使用舊密鑰解密
                    old_key = self._legacy_keys.get(old_version)
                    if old_key:
                        # 臨時切換到舊密鑰進行解密
                        current_key = self._encryption_key
                        self._encryption_key = old_key
                        self._init_encryption()
                        
                        try:
                            # 解密Token
                            plaintext_token = self._decrypt_token(bot_config['token_hash'])
                            
                            # 切換回新密鑰並重新加密
                            self._encryption_key = current_key
                            self._init_encryption()
                            new_encrypted_token = self._encrypt_token(plaintext_token)
                            
                            # 更新配置
                            bot_config['token_hash'] = new_encrypted_token
                            bot_config['key_version'] = self._key_version
                            
                            self.logger.debug(f"已重新加密子機器人 {bot_id} 的Token")
                            
                        except Exception as e:
                            # 恢復當前密鑰
                            self._encryption_key = current_key
                            self._init_encryption()
                            raise e
                            
        except Exception as e:
            self.logger.error(f"重新加密Token時發生錯誤: {e}")
            raise SubBotTokenError(bot_id=bot_id, token_issue=f"Token重新加密失敗: {str(e)}")
    
    def _cleanup_legacy_keys(self) -> None:
        """清理過期的舊密鑰"""
        max_backup_count = self.config.get('key_backup_count', 3)
        
        # 只保留最新的N個版本
        if len(self._legacy_keys) > max_backup_count:
            # 按版本號排序，保留最新的N個
            sorted_versions = sorted(self._legacy_keys.keys(), reverse=True)
            versions_to_keep = sorted_versions[:max_backup_count]
            
            for version in list(self._legacy_keys.keys()):
                if version not in versions_to_keep:
                    del self._legacy_keys[version]
                    self.logger.info(f"已清理舊密鑰版本: {version}")
    
    def get_encryption_info(self) -> Dict[str, Any]:
        """獲取加密相關資訊（用於監控和除錯）"""
        return {
            'algorithm': self._cipher_type,
            'key_version': self._key_version,
            'legacy_key_count': len(self._legacy_keys),
            'rotation_enabled': self.config['key_rotation_enabled'],
            'rotation_interval': self.config['key_rotation_interval']
        }
    
    # ========== 增強功能API方法 ==========
    
    async def create_sub_bot_with_manager(
        self, 
        name: str, 
        token: str, 
        target_channels: List[int],
        ai_enabled: bool = False,
        ai_model: Optional[str] = None,
        personality: Optional[str] = None,
        rate_limit: Optional[int] = None,
        performance_tier: str = "standard"
    ) -> Dict[str, Any]:
        """
        使用高級管理器創建子機器人
        
        Args:
            name: 子機器人名稱
            token: Discord Bot Token
            target_channels: 目標頻道ID列表
            ai_enabled: 是否啟用AI功能
            ai_model: AI模型名稱
            personality: AI人格設定
            rate_limit: 速率限制
            performance_tier: 性能等級 ('economy', 'standard', 'premium')
            
        Returns:
            創建結果字典
        """
        try:
            # 首先使用原有方法創建基礎配置
            result = await self.create_subbot(
                name, token, 0, target_channels, ai_enabled, ai_model, personality, rate_limit
            )
            
            if not result.get('success'):
                return result
            
            bot_id = result['bot_id']
            
            # 如果有高級管理器，進行額外配置
            if self.manager:
                try:
                    bot_config = self.registered_bots[bot_id]
                    await self.manager.create_instance(bot_config)
                    
                    # 設置性能等級
                    if self.performance_manager:
                        from .subbot_load_balancer import PerformanceTier
                        tier_map = {
                            'economy': PerformanceTier.ECONOMY,
                            'standard': PerformanceTier.STANDARD,
                            'premium': PerformanceTier.PREMIUM
                        }
                        tier = tier_map.get(performance_tier, PerformanceTier.STANDARD)
                        self.performance_manager.set_performance_tier(bot_id, tier)
                    
                    result['enhanced_features'] = True
                    result['performance_tier'] = performance_tier
                    
                except Exception as e:
                    self.logger.warning(f"配置高級功能失敗: {e}")
                    result['enhanced_features'] = False
            else:
                result['enhanced_features'] = False
            
            return result
            
        except Exception as e:
            self.logger.error(f"使用高級管理器創建子機器人失敗: {e}")
            return {'success': False, 'error': str(e)}
    
    async def start_sub_bot_with_balancing(self, bot_id: str) -> Dict[str, Any]:
        """
        使用負載均衡啟動子機器人
        
        Args:
            bot_id: 子機器人ID
            
        Returns:
            啟動結果字典
        """
        try:
            # 首先使用原有方法啟動
            result = await self.start_sub_bot(bot_id)
            
            if result.get('success') and self.manager:
                # 使用高級管理器啟動
                manager_result = await self.manager.start_instance(bot_id)
                
                return {
                    'success': manager_result,
                    'bot_id': bot_id,
                    'started_with_manager': True,
                    'load_balancing_enabled': self.load_balancer is not None
                }
            
            return result
            
        except Exception as e:
            self.logger.error(f"使用負載均衡啟動子機器人失敗: {e}")
            return {'success': False, 'error': str(e)}
    
    async def get_system_status_advanced(self) -> Dict[str, Any]:
        """
        獲取增強的系統狀態資訊
        
        Returns:
            系統狀態字典
        """
        try:
            # 獲取基礎狀態
            basic_status = {
                'total_bots': len(self.registered_bots),
                'active_connections': len(self.active_connections),
                'encryption_info': self.get_encryption_info(),
                'config': {k: v for k, v in self.config.items() if 'key' not in k.lower()}
            }
            
            # 如果有高級管理器，獲取詳細狀態
            if self.manager:
                manager_status = await self.manager.get_system_status()
                basic_status.update({
                    'advanced_features': True,
                    'manager_status': manager_status
                })
                
                # 負載均衡狀態
                if self.load_balancer:
                    basic_status['load_balancer'] = self.load_balancer.get_load_distribution()
                
                # 性能管理狀態
                if self.performance_manager:
                    basic_status['performance_manager'] = self.performance_manager.get_performance_report()
                
                # 擴展系統狀態
                if self.extension_manager:
                    basic_status['extension_manager'] = self.extension_manager.get_system_status()
            else:
                basic_status['advanced_features'] = False
            
            return basic_status
            
        except Exception as e:
            self.logger.error(f"獲取系統狀態失敗: {e}")
            return {
                'error': str(e),
                'basic_info': {
                    'total_bots': len(self.registered_bots),
                    'active_connections': len(self.active_connections)
                }
            }
    
    async def process_message_with_extensions(
        self, 
        bot_id: str, 
        message_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        使用擴展系統處理消息
        
        Args:
            bot_id: 子機器人ID
            message_data: 消息數據
            
        Returns:
            處理結果字典
        """
        try:
            # 基本處理結果
            result = {
                'bot_id': bot_id,
                'message_id': message_data.get('id'),
                'processed': False,
                'responses': []
            }
            
            # 如果有擴展管理器，使用插件處理
            if self.extension_manager:
                try:
                    plugin_results = await self.extension_manager.process_message(message_data)
                    result['responses'].extend(plugin_results)
                    result['processed'] = len(plugin_results) > 0
                    result['used_extensions'] = True
                    
                    # 如果啟用了AI且有AI插件
                    if message_data.get('needs_ai_response'):
                        ai_response = await self.extension_manager.generate_ai_response(
                            message_data.get('content', ''),
                            {'bot_id': bot_id, 'channel_id': message_data.get('channel_id')}
                        )
                        if ai_response:
                            result['responses'].append({
                                'type': 'ai_response',
                                'content': ai_response
                            })
                    
                except Exception as e:
                    self.logger.error(f"擴展系統處理消息失敗: {e}")
                    result['extension_error'] = str(e)
                    result['used_extensions'] = False
            else:
                result['used_extensions'] = False
            
            # 如果沒有處理結果，使用基本處理邏輯
            if not result['processed']:
                # 這裡可以添加基本的消息處理邏輯
                basic_response = self._generate_basic_response(message_data)
                if basic_response:
                    result['responses'].append({
                        'type': 'basic_response',
                        'content': basic_response
                    })
                    result['processed'] = True
            
            # 更新負載均衡器指標
            if self.load_balancer:
                from .subbot_load_balancer import LoadMetrics
                # 這裡可以更新實際的指標
                pass
            
            return result
            
        except Exception as e:
            self.logger.error(f"處理消息失敗: {e}")
            return {
                'bot_id': bot_id,
                'processed': False,
                'error': str(e)
            }
    
    def _generate_basic_response(self, message_data: Dict[str, Any]) -> Optional[str]:
        """生成基本回應"""
        content = message_data.get('content', '').lower()
        
        # 簡單的關鍵字回應
        if any(greeting in content for greeting in ['hello', 'hi', '你好', '嗨']):
            return "Hello! I'm a SubBot powered by ROAS Bot v2.4.4"
        elif any(help_word in content for help_word in ['help', '幫助', '協助']):
            return "I'm here to help! This SubBot supports advanced features like AI integration and load balancing."
        elif any(status_word in content for status_word in ['status', '狀態', '情況']):
            return f"SubBot is running with {len(self.registered_bots)} total instances."
        
        return None
    
    async def reload_plugin(self, plugin_name: str) -> Dict[str, Any]:
        """
        重新載入插件
        
        Args:
            plugin_name: 插件名稱
            
        Returns:
            重新載入結果
        """
        if not self.extension_manager:
            return {
                'success': False,
                'error': '擴展管理器未啟用'
            }
        
        try:
            result = await self.extension_manager.reload_plugin(plugin_name)
            
            return {
                'success': result,
                'plugin_name': plugin_name,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"重新載入插件 {plugin_name} 失敗: {e}")
            return {
                'success': False,
                'plugin_name': plugin_name,
                'error': str(e)
            }
    
    async def get_performance_metrics(self, bot_id: Optional[str] = None) -> Dict[str, Any]:
        """
        獲取性能指標
        
        Args:
            bot_id: 子機器人ID，如果為None則返回所有實例的指標
            
        Returns:
            性能指標字典
        """
        if not self.load_balancer:
            return {
                'available': False,
                'reason': '負載均衡器未啟用'
            }
        
        try:
            if bot_id:
                # 獲取特定實例的指標
                metrics = self.load_balancer.metrics.get(bot_id)
                if metrics:
                    return {
                        'available': True,
                        'bot_id': bot_id,
                        'metrics': {
                            'load_score': metrics.load_score,
                            'active_connections': metrics.active_connections,
                            'pending_messages': metrics.pending_messages,
                            'response_time': metrics.response_time,
                            'cpu_usage': metrics.cpu_usage,
                            'memory_usage': metrics.memory_usage,
                            'error_rate': metrics.error_rate,
                            'last_update': metrics.timestamp.isoformat()
                        }
                    }
                else:
                    return {
                        'available': False,
                        'bot_id': bot_id,
                        'reason': '實例指標不存在'
                    }
            else:
                # 獲取所有實例的指標
                distribution = self.load_balancer.get_load_distribution()
                return {
                    'available': True,
                    'distribution': distribution,
                    'timestamp': datetime.now().isoformat()
                }
        
        except Exception as e:
            self.logger.error(f"獲取性能指標失敗: {e}")
            return {
                'available': False,
                'error': str(e)
            }
    
    async def optimize_performance(self, bot_id: str) -> Dict[str, Any]:
        """
        優化特定實例的性能
        
        Args:
            bot_id: 子機器人ID
            
        Returns:
            優化結果字典
        """
        if not self.performance_manager:
            return {
                'success': False,
                'reason': '性能管理器未啟用'
            }
        
        try:
            # 檢查資源限制
            if bot_id in self.load_balancer.metrics:
                current_metrics = self.load_balancer.metrics[bot_id]
                limit_check = self.performance_manager.check_resource_limits(bot_id, current_metrics)
                
                if limit_check['status'] == 'violation':
                    # 執行自動調優
                    await self.performance_manager._auto_tune_instance(bot_id, limit_check)
                    
                    return {
                        'success': True,
                        'bot_id': bot_id,
                        'action': 'auto_tuned',
                        'violations_resolved': limit_check['violations'],
                        'timestamp': datetime.now().isoformat()
                    }
                else:
                    return {
                        'success': True,
                        'bot_id': bot_id,
                        'action': 'no_optimization_needed',
                        'status': limit_check['status']
                    }
            else:
                return {
                    'success': False,
                    'bot_id': bot_id,
                    'reason': '實例指標不存在'
                }
                
        except Exception as e:
            self.logger.error(f"優化實例 {bot_id} 性能失敗: {e}")
            return {
                'success': False,
                'bot_id': bot_id,
                'error': str(e)
            }