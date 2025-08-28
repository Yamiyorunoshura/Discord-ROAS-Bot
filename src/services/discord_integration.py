"""
Discord.py集成架構
Task ID: 3 - 子機器人聊天功能和管理系統開發

這個模組提供：
- Discord.py客戶端管理和連接池
- 事件處理和消息路由
- 命令系統和權限管理
- 頻道管理和用戶互動
- 率限處理和連接恢復
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable, Union, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
import weakref

# Discord.py imports
try:
    import discord
    from discord.ext import commands, tasks
    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False

from src.core.errors import SubBotError, SubBotTokenError, SubBotChannelError

logger = logging.getLogger('services.discord_integration')


class ConnectionState(Enum):
    """連接狀態"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


class MessageType(Enum):
    """消息類型"""
    TEXT = "text"
    EMBED = "embed"
    FILE = "file"
    REACTION = "reaction"
    COMMAND = "command"


@dataclass
class DiscordMessage:
    """Discord消息數據結構"""
    message_id: int
    channel_id: int
    guild_id: Optional[int]
    author_id: int
    content: str
    message_type: MessageType
    timestamp: datetime
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    embeds: List[Dict[str, Any]] = field(default_factory=list)
    reactions: List[Dict[str, Any]] = field(default_factory=list)
    reply_to: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典"""
        return {
            'message_id': self.message_id,
            'channel_id': self.channel_id,
            'guild_id': self.guild_id,
            'author_id': self.author_id,
            'content': self.content,
            'message_type': self.message_type.value,
            'timestamp': self.timestamp.isoformat(),
            'attachments': self.attachments,
            'embeds': self.embeds,
            'reactions': self.reactions,
            'reply_to': self.reply_to
        }


@dataclass
class DiscordUser:
    """Discord用戶數據結構"""
    user_id: int
    username: str
    discriminator: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    is_bot: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典"""
        return {
            'user_id': self.user_id,
            'username': self.username,
            'discriminator': self.discriminator,
            'display_name': self.display_name,
            'avatar_url': self.avatar_url,
            'is_bot': self.is_bot
        }


class DiscordClient:
    """Discord客戶端封裝"""
    
    def __init__(self, bot_id: str, token: str, config: Dict[str, Any]):
        if not DISCORD_AVAILABLE:
            raise SubBotError("Discord.py 未安裝")
        
        self.bot_id = bot_id
        self.token = token
        self.config = config
        
        # 連接狀態
        self.state = ConnectionState.DISCONNECTED
        self.last_heartbeat: Optional[datetime] = None
        self.connection_attempts = 0
        self.max_connection_attempts = 5
        
        # 設置Discord客戶端
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.guild_messages = True
        intents.reactions = True
        
        # 根據配置選擇客戶端類型
        if config.get('ai_enabled', False):
            self.client = commands.Bot(
                command_prefix=config.get('command_prefix', '!'),
                intents=intents,
                help_command=None  # 禁用預設help命令
            )
        else:
            self.client = discord.Client(intents=intents)
        
        # 事件處理器
        self.message_handlers: List[Callable] = []
        self.command_handlers: Dict[str, Callable] = {}
        self.event_handlers: Dict[str, List[Callable]] = {}
        
        # 頻道和權限管理
        self.allowed_channels: Set[int] = set(config.get('target_channels', []))
        self.allowed_guilds: Set[int] = set(config.get('target_guilds', []))
        
        # 速率限制
        self.rate_limiter = DiscordRateLimiter(config.get('rate_limit', 10))
        
        # 統計資訊
        self.stats = {
            'messages_sent': 0,
            'messages_received': 0,
            'commands_executed': 0,
            'errors_count': 0,
            'connection_time': None,
            'last_activity': None
        }
        
        self._setup_events()
        logger.info(f"Discord客戶端已初始化: {bot_id}")
    
    def _setup_events(self):
        """設置Discord事件處理"""
        
        @self.client.event
        async def on_ready():
            self.state = ConnectionState.CONNECTED
            self.stats['connection_time'] = datetime.now()
            self.last_heartbeat = datetime.now()
            logger.info(f"SubBot {self.bot_id} 已連接到Discord: {self.client.user}")
            
            # 觸發自定義事件
            await self._trigger_event('bot_ready', {
                'bot_id': self.bot_id,
                'user': self.client.user,
                'guilds': len(self.client.guilds)
            })
        
        @self.client.event
        async def on_disconnect():
            self.state = ConnectionState.DISCONNECTED
            logger.warning(f"SubBot {self.bot_id} 已斷開Discord連接")
            
            await self._trigger_event('bot_disconnect', {
                'bot_id': self.bot_id
            })
        
        @self.client.event
        async def on_resumed():
            self.state = ConnectionState.CONNECTED
            self.last_heartbeat = datetime.now()
            logger.info(f"SubBot {self.bot_id} 已恢復Discord連接")
            
            await self._trigger_event('bot_resumed', {
                'bot_id': self.bot_id
            })
        
        @self.client.event
        async def on_message(message):
            await self._handle_message(message)
        
        @self.client.event
        async def on_message_edit(before, after):
            await self._handle_message_edit(before, after)
        
        @self.client.event
        async def on_reaction_add(reaction, user):
            await self._handle_reaction(reaction, user, 'add')
        
        @self.client.event
        async def on_reaction_remove(reaction, user):
            await self._handle_reaction(reaction, user, 'remove')
        
        @self.client.event
        async def on_error(event, *args, **kwargs):
            logger.error(f"SubBot {self.bot_id} Discord錯誤 - 事件: {event}")
            self.stats['errors_count'] += 1
            
            await self._trigger_event('discord_error', {
                'bot_id': self.bot_id,
                'event': event,
                'error': str(args[0]) if args else 'Unknown error'
            })
        
        # 如果是Bot客戶端，設置命令處理
        if isinstance(self.client, commands.Bot):
            @self.client.event
            async def on_command_error(ctx, error):
                await self._handle_command_error(ctx, error)
    
    async def start(self) -> bool:
        """啟動Discord連接"""
        try:
            self.state = ConnectionState.CONNECTING
            self.connection_attempts += 1
            
            logger.info(f"正在連接Discord: {self.bot_id} (嘗試 {self.connection_attempts})")
            
            # 啟動Discord客戶端
            await self.client.start(self.token, reconnect=True)
            
            return True
            
        except discord.LoginFailure as e:
            self.state = ConnectionState.FAILED
            logger.error(f"Discord登錄失敗 {self.bot_id}: {e}")
            raise SubBotTokenError(self.bot_id, f"登錄失敗: {str(e)}")
            
        except discord.ConnectionClosed as e:
            self.state = ConnectionState.FAILED
            logger.error(f"Discord連接關閉 {self.bot_id}: {e}")
            
            # 如果未達到最大嘗試次數，可以重試
            if self.connection_attempts < self.max_connection_attempts:
                await asyncio.sleep(2 ** self.connection_attempts)  # 指數退避
                return await self.start()
            
            raise SubBotError(f"Discord連接失敗，已嘗試 {self.connection_attempts} 次")
            
        except Exception as e:
            self.state = ConnectionState.FAILED
            logger.error(f"Discord啟動異常 {self.bot_id}: {e}")
            raise
    
    async def stop(self) -> None:
        """停止Discord連接"""
        try:
            if not self.client.is_closed():
                await self.client.close()
            
            self.state = ConnectionState.DISCONNECTED
            logger.info(f"SubBot {self.bot_id} Discord連接已關閉")
            
        except Exception as e:
            logger.error(f"關閉Discord連接失敗 {self.bot_id}: {e}")
    
    def add_message_handler(self, handler: Callable) -> None:
        """添加消息處理器"""
        self.message_handlers.append(handler)
        logger.debug(f"已添加消息處理器: {handler.__name__}")
    
    def add_command_handler(self, command: str, handler: Callable) -> None:
        """添加命令處理器"""
        self.command_handlers[command] = handler
        
        # 如果是Bot客戶端，註冊Discord命令
        if isinstance(self.client, commands.Bot):
            @self.client.command(name=command)
            async def discord_command(ctx, *args):
                await self._execute_command(ctx, command, args, handler)
        
        logger.debug(f"已添加命令處理器: {command}")
    
    def add_event_handler(self, event: str, handler: Callable) -> None:
        """添加事件處理器"""
        if event not in self.event_handlers:
            self.event_handlers[event] = []
        
        self.event_handlers[event].append(handler)
        logger.debug(f"已添加事件處理器: {event}")
    
    async def send_message(
        self, 
        channel_id: int, 
        content: Optional[str] = None,
        embed: Optional[discord.Embed] = None,
        file: Optional[discord.File] = None,
        reply_to: Optional[int] = None
    ) -> Optional[discord.Message]:
        """發送消息"""
        try:
            # 檢查速率限制
            if not await self.rate_limiter.acquire():
                logger.warning(f"SubBot {self.bot_id} 觸發速率限制")
                return None
            
            channel = self.client.get_channel(channel_id)
            if not channel:
                raise SubBotChannelError(
                    self.bot_id, 
                    str(channel_id), 
                    "send_message", 
                    "頻道不存在或無權限"
                )
            
            # 檢查頻道權限
            if not self._check_channel_permission(channel_id):
                raise SubBotChannelError(
                    self.bot_id,
                    str(channel_id),
                    "send_message",
                    "不允許在此頻道發送消息"
                )
            
            # 構建發送參數
            kwargs = {}
            if content:
                kwargs['content'] = content
            if embed:
                kwargs['embed'] = embed
            if file:
                kwargs['file'] = file
            
            # 處理回復
            if reply_to:
                try:
                    reference_message = await channel.fetch_message(reply_to)
                    kwargs['reference'] = reference_message
                except discord.NotFound:
                    logger.warning(f"回復消息不存在: {reply_to}")
            
            # 發送消息
            message = await channel.send(**kwargs)
            
            self.stats['messages_sent'] += 1
            self.stats['last_activity'] = datetime.now()
            
            logger.debug(f"SubBot {self.bot_id} 已發送消息到頻道 {channel_id}")
            
            return message
            
        except discord.Forbidden as e:
            raise SubBotChannelError(
                self.bot_id,
                str(channel_id),
                "send_message",
                f"權限不足: {str(e)}"
            )
        except discord.HTTPException as e:
            if e.status == 429:  # Rate limited
                logger.warning(f"SubBot {self.bot_id} 被Discord速率限制")
            raise SubBotError(f"發送消息失敗: {str(e)}")
        except Exception as e:
            logger.error(f"發送消息異常 {self.bot_id}: {e}")
            raise
    
    async def edit_message(
        self, 
        channel_id: int, 
        message_id: int,
        content: Optional[str] = None,
        embed: Optional[discord.Embed] = None
    ) -> Optional[discord.Message]:
        """編輯消息"""
        try:
            channel = self.client.get_channel(channel_id)
            if not channel:
                raise SubBotChannelError(
                    self.bot_id,
                    str(channel_id),
                    "edit_message",
                    "頻道不存在或無權限"
                )
            
            message = await channel.fetch_message(message_id)
            
            kwargs = {}
            if content is not None:
                kwargs['content'] = content
            if embed is not None:
                kwargs['embed'] = embed
            
            edited_message = await message.edit(**kwargs)
            
            logger.debug(f"SubBot {self.bot_id} 已編輯消息 {message_id}")
            
            return edited_message
            
        except discord.NotFound:
            raise SubBotError(f"消息不存在: {message_id}")
        except discord.Forbidden:
            raise SubBotError(f"無權限編輯消息: {message_id}")
        except Exception as e:
            logger.error(f"編輯消息異常 {self.bot_id}: {e}")
            raise
    
    async def delete_message(self, channel_id: int, message_id: int) -> bool:
        """刪除消息"""
        try:
            channel = self.client.get_channel(channel_id)
            if not channel:
                return False
            
            message = await channel.fetch_message(message_id)
            await message.delete()
            
            logger.debug(f"SubBot {self.bot_id} 已刪除消息 {message_id}")
            return True
            
        except discord.NotFound:
            logger.warning(f"要刪除的消息不存在: {message_id}")
            return False
        except discord.Forbidden:
            logger.warning(f"無權限刪除消息: {message_id}")
            return False
        except Exception as e:
            logger.error(f"刪除消息異常 {self.bot_id}: {e}")
            return False
    
    async def add_reaction(self, channel_id: int, message_id: int, emoji: Union[str, discord.Emoji]) -> bool:
        """添加反應"""
        try:
            channel = self.client.get_channel(channel_id)
            if not channel:
                return False
            
            message = await channel.fetch_message(message_id)
            await message.add_reaction(emoji)
            
            return True
            
        except Exception as e:
            logger.error(f"添加反應失敗 {self.bot_id}: {e}")
            return False
    
    def _check_channel_permission(self, channel_id: int) -> bool:
        """檢查頻道權限"""
        # 如果沒有設置限制，允許所有頻道
        if not self.allowed_channels:
            return True
        
        return channel_id in self.allowed_channels
    
    def _check_guild_permission(self, guild_id: Optional[int]) -> bool:
        """檢查伺服器權限"""
        if guild_id is None:  # DM
            return True
        
        # 如果沒有設置限制，允許所有伺服器
        if not self.allowed_guilds:
            return True
        
        return guild_id in self.allowed_guilds
    
    async def _handle_message(self, message: discord.Message) -> None:
        """處理收到的消息"""
        try:
            # 忽略自己的消息
            if message.author == self.client.user:
                return
            
            # 檢查權限
            if not self._check_channel_permission(message.channel.id):
                return
            
            if not self._check_guild_permission(message.guild.id if message.guild else None):
                return
            
            # 轉換為標準格式
            discord_message = DiscordMessage(
                message_id=message.id,
                channel_id=message.channel.id,
                guild_id=message.guild.id if message.guild else None,
                author_id=message.author.id,
                content=message.content,
                message_type=MessageType.TEXT,
                timestamp=message.created_at,
                attachments=[{
                    'filename': att.filename,
                    'url': att.url,
                    'size': att.size
                } for att in message.attachments],
                embeds=[embed.to_dict() for embed in message.embeds],
                reply_to=message.reference.message_id if message.reference else None
            )
            
            # 更新統計
            self.stats['messages_received'] += 1
            self.stats['last_activity'] = datetime.now()
            
            # 調用所有消息處理器
            for handler in self.message_handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(discord_message, message)
                    else:
                        handler(discord_message, message)
                except Exception as e:
                    logger.error(f"消息處理器失敗: {e}")
            
            # 觸發消息事件
            await self._trigger_event('message_received', {
                'bot_id': self.bot_id,
                'message': discord_message.to_dict(),
                'raw_message': message
            })
            
        except Exception as e:
            logger.error(f"處理消息異常 {self.bot_id}: {e}")
            self.stats['errors_count'] += 1
    
    async def _handle_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        """處理消息編輯"""
        try:
            await self._trigger_event('message_edited', {
                'bot_id': self.bot_id,
                'before': before,
                'after': after
            })
        except Exception as e:
            logger.error(f"處理消息編輯異常 {self.bot_id}: {e}")
    
    async def _handle_reaction(
        self, 
        reaction: discord.Reaction, 
        user: Union[discord.Member, discord.User],
        action: str
    ) -> None:
        """處理反應添加/移除"""
        try:
            await self._trigger_event(f'reaction_{action}', {
                'bot_id': self.bot_id,
                'reaction': {
                    'emoji': str(reaction.emoji),
                    'count': reaction.count,
                    'message_id': reaction.message.id,
                    'channel_id': reaction.message.channel.id
                },
                'user': {
                    'id': user.id,
                    'name': user.name,
                    'discriminator': user.discriminator
                }
            })
        except Exception as e:
            logger.error(f"處理反應異常 {self.bot_id}: {e}")
    
    async def _execute_command(
        self, 
        ctx: commands.Context, 
        command: str, 
        args: tuple,
        handler: Callable
    ) -> None:
        """執行命令"""
        try:
            self.stats['commands_executed'] += 1
            
            if asyncio.iscoroutinefunction(handler):
                await handler(ctx, *args)
            else:
                handler(ctx, *args)
            
            await self._trigger_event('command_executed', {
                'bot_id': self.bot_id,
                'command': command,
                'args': args,
                'user_id': ctx.author.id,
                'channel_id': ctx.channel.id
            })
            
        except Exception as e:
            logger.error(f"執行命令異常 {self.bot_id}: {e}")
            await self._handle_command_error(ctx, e)
    
    async def _handle_command_error(self, ctx: commands.Context, error: Exception) -> None:
        """處理命令錯誤"""
        try:
            self.stats['errors_count'] += 1
            
            error_message = "命令執行時發生錯誤"
            
            if isinstance(error, commands.CommandNotFound):
                return  # 忽略未知命令
            elif isinstance(error, commands.MissingRequiredArgument):
                error_message = f"缺少必要參數: {error.param.name}"
            elif isinstance(error, commands.BadArgument):
                error_message = "參數格式錯誤"
            elif isinstance(error, commands.CommandOnCooldown):
                error_message = f"命令冷卻中，請等待 {error.retry_after:.1f} 秒"
            elif isinstance(error, commands.MissingPermissions):
                error_message = "權限不足"
            
            await ctx.send(f"❌ {error_message}")
            
            await self._trigger_event('command_error', {
                'bot_id': self.bot_id,
                'command': ctx.command.name if ctx.command else 'unknown',
                'error': str(error),
                'user_id': ctx.author.id,
                'channel_id': ctx.channel.id
            })
            
        except Exception as e:
            logger.error(f"處理命令錯誤異常 {self.bot_id}: {e}")
    
    async def _trigger_event(self, event: str, data: Dict[str, Any]) -> None:
        """觸發自定義事件"""
        handlers = self.event_handlers.get(event, [])
        
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception as e:
                logger.error(f"事件處理器失敗 {event}: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """獲取客戶端狀態"""
        return {
            'bot_id': self.bot_id,
            'state': self.state.value,
            'connected': self.state == ConnectionState.CONNECTED,
            'user': {
                'id': self.client.user.id,
                'name': self.client.user.name,
                'discriminator': self.client.user.discriminator
            } if self.client.user else None,
            'guilds': len(self.client.guilds) if hasattr(self.client, 'guilds') else 0,
            'latency': self.client.latency * 1000 if hasattr(self.client, 'latency') else 0,
            'last_heartbeat': self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            'connection_attempts': self.connection_attempts,
            'stats': self.stats.copy(),
            'allowed_channels': list(self.allowed_channels),
            'allowed_guilds': list(self.allowed_guilds)
        }


class DiscordRateLimiter:
    """Discord速率限制器"""
    
    def __init__(self, rate_limit: int = 10):
        self.rate_limit = rate_limit  # 每分鐘最大請求數
        self.requests: List[datetime] = []
        self.lock = asyncio.Lock()
    
    async def acquire(self) -> bool:
        """獲取請求許可"""
        async with self.lock:
            now = datetime.now()
            
            # 清理過期的請求記錄
            cutoff_time = now - timedelta(minutes=1)
            self.requests = [req for req in self.requests if req > cutoff_time]
            
            # 檢查是否超過限制
            if len(self.requests) >= self.rate_limit:
                return False
            
            # 添加當前請求
            self.requests.append(now)
            return True
    
    def get_remaining(self) -> int:
        """獲取剩餘請求數"""
        now = datetime.now()
        cutoff_time = now - timedelta(minutes=1)
        active_requests = [req for req in self.requests if req > cutoff_time]
        return max(0, self.rate_limit - len(active_requests))


class DiscordManager:
    """Discord客戶端管理器"""
    
    def __init__(self):
        self.clients: Dict[str, DiscordClient] = {}
        self.connection_tasks: Dict[str, asyncio.Task] = {}
        self.global_handlers: Dict[str, List[Callable]] = {}
        
        # 統計資訊
        self.total_messages = 0
        self.total_commands = 0
        self.total_errors = 0
        
        logger.info("Discord管理器已初始化")
    
    async def create_client(
        self, 
        bot_id: str, 
        token: str, 
        config: Dict[str, Any]
    ) -> DiscordClient:
        """創建Discord客戶端"""
        if bot_id in self.clients:
            raise SubBotError(f"Discord客戶端已存在: {bot_id}")
        
        try:
            client = DiscordClient(bot_id, token, config)
            
            # 設置全局事件處理器
            self._setup_global_handlers(client)
            
            self.clients[bot_id] = client
            
            logger.info(f"Discord客戶端已創建: {bot_id}")
            return client
            
        except Exception as e:
            logger.error(f"創建Discord客戶端失敗 {bot_id}: {e}")
            raise
    
    async def start_client(self, bot_id: str) -> bool:
        """啟動Discord客戶端"""
        if bot_id not in self.clients:
            raise SubBotError(f"Discord客戶端不存在: {bot_id}")
        
        client = self.clients[bot_id]
        
        if bot_id in self.connection_tasks:
            logger.warning(f"Discord客戶端 {bot_id} 已在運行")
            return True
        
        try:
            # 創建連接任務
            self.connection_tasks[bot_id] = asyncio.create_task(
                self._run_client(client)
            )
            
            # 等待連接建立
            await asyncio.sleep(2)
            
            return client.state == ConnectionState.CONNECTED
            
        except Exception as e:
            logger.error(f"啟動Discord客戶端失敗 {bot_id}: {e}")
            return False
    
    async def stop_client(self, bot_id: str) -> bool:
        """停止Discord客戶端"""
        if bot_id not in self.clients:
            return False
        
        client = self.clients[bot_id]
        
        try:
            # 停止連接任務
            if bot_id in self.connection_tasks:
                task = self.connection_tasks[bot_id]
                task.cancel()
                
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                
                del self.connection_tasks[bot_id]
            
            # 關閉Discord連接
            await client.stop()
            
            logger.info(f"Discord客戶端已停止: {bot_id}")
            return True
            
        except Exception as e:
            logger.error(f"停止Discord客戶端失敗 {bot_id}: {e}")
            return False
    
    async def remove_client(self, bot_id: str) -> bool:
        """移除Discord客戶端"""
        if bot_id not in self.clients:
            return False
        
        # 先停止客戶端
        await self.stop_client(bot_id)
        
        # 移除客戶端
        del self.clients[bot_id]
        
        logger.info(f"Discord客戶端已移除: {bot_id}")
        return True
    
    def get_client(self, bot_id: str) -> Optional[DiscordClient]:
        """獲取Discord客戶端"""
        return self.clients.get(bot_id)
    
    def add_global_handler(self, event: str, handler: Callable) -> None:
        """添加全局事件處理器"""
        if event not in self.global_handlers:
            self.global_handlers[event] = []
        
        self.global_handlers[event].append(handler)
        
        # 為所有現有客戶端添加處理器
        for client in self.clients.values():
            client.add_event_handler(event, handler)
        
        logger.info(f"已添加全局事件處理器: {event}")
    
    def _setup_global_handlers(self, client: DiscordClient) -> None:
        """為客戶端設置全局處理器"""
        for event, handlers in self.global_handlers.items():
            for handler in handlers:
                client.add_event_handler(event, handler)
    
    async def _run_client(self, client: DiscordClient) -> None:
        """運行Discord客戶端"""
        try:
            await client.start()
        except asyncio.CancelledError:
            logger.info(f"Discord客戶端任務已取消: {client.bot_id}")
        except Exception as e:
            logger.error(f"Discord客戶端運行異常 {client.bot_id}: {e}")
            client.state = ConnectionState.FAILED
    
    async def broadcast_message(
        self, 
        channel_id: int,
        content: Optional[str] = None,
        embed: Optional[Dict[str, Any]] = None,
        exclude_bots: Optional[List[str]] = None
    ) -> Dict[str, bool]:
        """廣播消息到所有客戶端"""
        exclude_bots = exclude_bots or []
        results = {}
        
        discord_embed = None
        if embed:
            discord_embed = discord.Embed.from_dict(embed)
        
        for bot_id, client in self.clients.items():
            if bot_id in exclude_bots:
                continue
            
            try:
                message = await client.send_message(
                    channel_id, 
                    content=content, 
                    embed=discord_embed
                )
                results[bot_id] = message is not None
            except Exception as e:
                logger.error(f"廣播消息失敗 {bot_id}: {e}")
                results[bot_id] = False
        
        return results
    
    def get_system_status(self) -> Dict[str, Any]:
        """獲取系統狀態"""
        total_clients = len(self.clients)
        connected_clients = sum(
            1 for client in self.clients.values() 
            if client.state == ConnectionState.CONNECTED
        )
        
        client_statuses = {}
        for bot_id, client in self.clients.items():
            client_statuses[bot_id] = client.get_status()
        
        return {
            'total_clients': total_clients,
            'connected_clients': connected_clients,
            'connection_rate': connected_clients / max(total_clients, 1) * 100,
            'global_stats': {
                'total_messages': sum(c.stats['messages_received'] for c in self.clients.values()),
                'total_commands': sum(c.stats['commands_executed'] for c in self.clients.values()),
                'total_errors': sum(c.stats['errors_count'] for c in self.clients.values())
            },
            'clients': client_statuses
        }
    
    async def cleanup_all(self) -> None:
        """清理所有客戶端"""
        logger.info("正在清理所有Discord客戶端...")
        
        # 停止所有客戶端
        for bot_id in list(self.clients.keys()):
            try:
                await self.stop_client(bot_id)
            except Exception as e:
                logger.error(f"清理客戶端 {bot_id} 失敗: {e}")
        
        # 清空記錄
        self.clients.clear()
        self.connection_tasks.clear()
        
        logger.info("Discord客戶端清理完成")