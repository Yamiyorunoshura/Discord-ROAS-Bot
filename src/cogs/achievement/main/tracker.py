"""成就事件監聽器模組.

實作成就系統的核心事件監聽和追蹤功能：
- Discord 事件監聽和過濾
- 事件資料結構化收集
- EventBus 系統整合
- 成就觸發事件處理
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from discord.ext import commands

from src.cogs.core.event_bus import Event, EventBus, EventPriority, get_global_event_bus

from ..database.repository import AchievementEventRepository
from .event_processor import EventDataProcessor

if TYPE_CHECKING:
    import discord

    from src.core.database import DatabasePool

    from ..database.models import AchievementEventData
    from ..services.achievement_service import AchievementService

logger = logging.getLogger(__name__)


class AchievementEventListener(commands.Cog):
    """成就事件監聽器.

    負責監聽 Discord 事件並將其轉換為成就系統可處理的事件：
    - 監聽 Discord 各種事件（訊息、反應、語音等）
    - 整合 EventBus 系統進行事件發布
    - 事件過濾和資料標準化
    - 與成就服務系統整合
    """

    def __init__(self, bot: commands.Bot):
        """初始化成就事件監聽器.

        Args:
            bot: Discord 機器人實例
        """
        self.bot = bot
        self.event_bus: EventBus | None = None
        self.achievement_service: AchievementService | None = None
        self.event_processor: EventDataProcessor | None = None
        self.event_repository: AchievementEventRepository | None = None

        # 事件類型常數
        self.EVENT_TYPES = {
            'MESSAGE_SENT': 'achievement.message_sent',
            'MESSAGE_EDITED': 'achievement.message_edited',
            'MESSAGE_DELETED': 'achievement.message_deleted',
            'REACTION_ADDED': 'achievement.reaction_added',
            'REACTION_REMOVED': 'achievement.reaction_removed',
            'VOICE_JOINED': 'achievement.voice_joined',
            'VOICE_LEFT': 'achievement.voice_left',
            'VOICE_MOVED': 'achievement.voice_moved',
            'MEMBER_JOINED': 'achievement.member_joined',
            'MEMBER_LEFT': 'achievement.member_left',
            'MEMBER_UPDATED': 'achievement.member_updated',
            'COMMAND_USED': 'achievement.command_used',
            'SLASH_COMMAND_USED': 'achievement.slash_command_used'
        }

        # 事件統計
        self._event_stats = {
            'total_events': 0,
            'processed_events': 0,
            'failed_events': 0,
            'last_event_time': None
        }

    async def initialize(self, achievement_service: AchievementService, database_pool: DatabasePool) -> None:
        """初始化事件監聽器.

        Args:
            achievement_service: 成就服務實例
            database_pool: 資料庫連線池
        """
        try:
            # 保存服務參考
            self.achievement_service = achievement_service

            # 初始化事件資料庫存取層
            self.event_repository = AchievementEventRepository(database_pool)

            # 初始化事件資料處理器
            self.event_processor = EventDataProcessor(
                batch_size=50,
                batch_timeout=5.0,
                max_memory_events=1000
            )

            # 獲取全域 EventBus
            self.event_bus = await get_global_event_bus()

            # 註冊事件監聽器到 EventBus
            await self._register_event_handlers()

            logger.info("【成就事件監聽器】初始化完成")

        except Exception as e:
            logger.error(f"【成就事件監聽器】初始化失敗: {e}")
            raise

    async def _register_event_handlers(self) -> None:
        """註冊事件處理器到 EventBus."""
        try:
            # 註冊成就事件處理器
            self.event_bus.subscribe(
                event_types=[
                    self.EVENT_TYPES['MESSAGE_SENT'],
                    self.EVENT_TYPES['MESSAGE_EDITED'],
                    self.EVENT_TYPES['MESSAGE_DELETED'],
                    self.EVENT_TYPES['REACTION_ADDED'],
                    self.EVENT_TYPES['REACTION_REMOVED'],
                    self.EVENT_TYPES['VOICE_JOINED'],
                    self.EVENT_TYPES['VOICE_LEFT'],
                    self.EVENT_TYPES['VOICE_MOVED'],
                    self.EVENT_TYPES['MEMBER_JOINED'],
                    self.EVENT_TYPES['MEMBER_LEFT'],
                    self.EVENT_TYPES['MEMBER_UPDATED'],
                    self.EVENT_TYPES['COMMAND_USED'],
                    self.EVENT_TYPES['SLASH_COMMAND_USED']
                ],
                handler=self._handle_achievement_event,
                priority=EventPriority.NORMAL,
                subscriber_id="achievement_event_processor"
            )

            logger.debug("【成就事件監聽器】EventBus 處理器註冊完成")

        except Exception as e:
            logger.error(f"【成就事件監聽器】EventBus 處理器註冊失敗: {e}")
            raise

    async def _handle_achievement_event(self, event: Event) -> None:
        """處理成就相關事件.

        Args:
            event: EventBus 事件物件
        """
        try:
            self._event_stats['total_events'] += 1
            self._event_stats['last_event_time'] = time.time()

            # 處理事件延遲不能超過 100ms
            start_time = time.time()

            # 準備事件資料給處理器
            event_data = {
                'user_id': event.data.get('user_id'),
                'guild_id': event.data.get('guild_id'),
                'event_type': event.event_type,
                'event_data': event.data,
                'timestamp': event.timestamp,
                'channel_id': event.data.get('channel_id'),
                'correlation_id': event.correlation_id
            }

            # 使用事件處理器處理事件
            if self.event_processor:
                # 嘗試加入批次處理
                batch_events = await self.event_processor.add_to_batch(event_data)

                if batch_events:
                    # 批次準備好了，持久化批次事件
                    await self._persist_event_batch(batch_events)

            processing_time = (time.time() - start_time) * 1000
            if processing_time > 100:
                logger.warning(
                    f"【成就事件監聽器】事件處理時間超限: {processing_time:.2f}ms"
                )

            self._event_stats['processed_events'] += 1

        except Exception as e:
            self._event_stats['failed_events'] += 1
            logger.error(f"【成就事件監聽器】處理事件失敗: {e}", exc_info=True)

    async def _persist_event_batch(self, batch_events: List[AchievementEventData]) -> None:
        """持久化事件批次.

        Args:
            batch_events: 事件批次列表
        """
        try:
            if not self.event_repository or not batch_events:
                return

            # 批次保存事件到資料庫
            saved_events = await self.event_repository.create_events_batch(batch_events)

            logger.debug(
                f"【成就事件監聽器】批次持久化完成: {len(saved_events)} 個事件已保存"
            )

            # 觸發成就進度更新
            await self._trigger_achievement_progress_updates(saved_events)

        except Exception as e:
            logger.error(f"【成就事件監聽器】事件持久化失敗: {e}", exc_info=True)

    def _is_achievement_relevant_event(self, event: Event) -> bool:
        """檢查事件是否與成就相關.

        Args:
            event: EventBus 事件物件

        Returns:
            bool: 事件是否與成就相關
        """
        # 檢查事件類型是否在成就相關類型中
        if not event.event_type.startswith('achievement.'):
            return False

        # 檢查必要的資料欄位
        required_fields = ['user_id', 'guild_id']
        for field in required_fields:
            if field not in event.data:
                return False

        # 檢查用戶是否為機器人（排除機器人事件）
        return not event.data.get('is_bot', False)

    def _validate_event_data(self, event: Event) -> bool:
        """驗證事件資料完整性.

        Args:
            event: EventBus 事件物件

        Returns:
            bool: 資料是否有效
        """
        try:
            # 基礎欄位驗證
            if not isinstance(event.data, dict):
                return False

            # 用戶ID驗證
            user_id = event.data.get('user_id')
            if not user_id or not isinstance(user_id, int):
                return False

            # 伺服器ID驗證
            guild_id = event.data.get('guild_id')
            if not guild_id or not isinstance(guild_id, int):
                return False

            # 時間戳驗證
            return isinstance(event.timestamp, int | float)

        except Exception as e:
            logger.error(f"【成就事件監聽器】事件資料驗證錯誤: {e}")
            return False

    # Discord 事件監聽器

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """監聽訊息事件.

        Args:
            message: Discord 訊息物件
        """
        try:
            # 過濾機器人訊息
            if message.author.bot:
                return

            # 確保在伺服器中
            if not message.guild:
                return

            # 建立成就事件
            event_data = {
                'user_id': message.author.id,
                'guild_id': message.guild.id,
                'channel_id': message.channel.id,
                'message_id': message.id,
                'content_length': len(message.content),
                'has_attachments': len(message.attachments) > 0,
                'has_embeds': len(message.embeds) > 0,
                'mention_count': len(message.mentions),
                'is_bot': message.author.bot
            }

            event = Event(
                event_type=self.EVENT_TYPES['MESSAGE_SENT'],
                data=event_data,
                source='discord.message',
                priority=EventPriority.NORMAL,
                timestamp=time.time()
            )

            # 發布事件
            if self.event_bus:
                await self.event_bus.publish(event)

        except Exception as e:
            logger.error(f"【成就事件監聽器】處理訊息事件失敗: {e}")

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        """監聽訊息編輯事件.

        Args:
            before: 編輯前的訊息
            after: 編輯後的訊息
        """
        try:
            if after.author.bot or not after.guild:
                return

            event_data = {
                'user_id': after.author.id,
                'guild_id': after.guild.id,
                'channel_id': after.channel.id,
                'message_id': after.id,
                'old_content_length': len(before.content),
                'new_content_length': len(after.content),
                'is_bot': after.author.bot
            }

            event = Event(
                event_type=self.EVENT_TYPES['MESSAGE_EDITED'],
                data=event_data,
                source='discord.message',
                priority=EventPriority.LOW,
                timestamp=time.time()
            )

            if self.event_bus:
                await self.event_bus.publish(event)

        except Exception as e:
            logger.error(f"【成就事件監聽器】處理訊息編輯事件失敗: {e}")

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        """監聽訊息刪除事件.

        Args:
            message: 被刪除的訊息
        """
        try:
            if message.author.bot or not message.guild:
                return

            event_data = {
                'user_id': message.author.id,
                'guild_id': message.guild.id,
                'channel_id': message.channel.id,
                'message_id': message.id,
                'content_length': len(message.content),
                'is_bot': message.author.bot
            }

            event = Event(
                event_type=self.EVENT_TYPES['MESSAGE_DELETED'],
                data=event_data,
                source='discord.message',
                priority=EventPriority.LOW,
                timestamp=time.time()
            )

            if self.event_bus:
                await self.event_bus.publish(event)

        except Exception as e:
            logger.error(f"【成就事件監聽器】處理訊息刪除事件失敗: {e}")

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.Member | discord.User) -> None:
        """監聽反應新增事件.

        Args:
            reaction: Discord 反應物件
            user: 新增反應的用戶
        """
        try:
            if user.bot or not reaction.message.guild:
                return

            event_data = {
                'user_id': user.id,
                'guild_id': reaction.message.guild.id,
                'channel_id': reaction.message.channel.id,
                'message_id': reaction.message.id,
                'message_author_id': reaction.message.author.id,
                'emoji': str(reaction.emoji),
                'is_custom_emoji': reaction.custom_emoji,
                'is_bot': user.bot
            }

            event = Event(
                event_type=self.EVENT_TYPES['REACTION_ADDED'],
                data=event_data,
                source='discord.reaction',
                priority=EventPriority.NORMAL,
                timestamp=time.time()
            )

            if self.event_bus:
                await self.event_bus.publish(event)

        except Exception as e:
            logger.error(f"【成就事件監聽器】處理反應新增事件失敗: {e}")

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction: discord.Reaction, user: discord.Member | discord.User) -> None:
        """監聽反應移除事件.

        Args:
            reaction: Discord 反應物件
            user: 移除反應的用戶
        """
        try:
            if user.bot or not reaction.message.guild:
                return

            event_data = {
                'user_id': user.id,
                'guild_id': reaction.message.guild.id,
                'channel_id': reaction.message.channel.id,
                'message_id': reaction.message.id,
                'message_author_id': reaction.message.author.id,
                'emoji': str(reaction.emoji),
                'is_custom_emoji': reaction.custom_emoji,
                'is_bot': user.bot
            }

            event = Event(
                event_type=self.EVENT_TYPES['REACTION_REMOVED'],
                data=event_data,
                source='discord.reaction',
                priority=EventPriority.LOW,
                timestamp=time.time()
            )

            if self.event_bus:
                await self.event_bus.publish(event)

        except Exception as e:
            logger.error(f"【成就事件監聽器】處理反應移除事件失敗: {e}")

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState
    ) -> None:
        """監聽語音狀態更新事件.

        Args:
            member: 變更語音狀態的成員
            before: 變更前的語音狀態
            after: 變更後的語音狀態
        """
        try:
            if member.bot:
                return

            # 判斷語音事件類型
            event_type = None
            event_data_extra = {}

            if before.channel is None and after.channel is not None:
                # 加入語音頻道
                event_type = self.EVENT_TYPES['VOICE_JOINED']
                event_data_extra = {
                    'joined_channel_id': after.channel.id,
                    'joined_channel_name': after.channel.name
                }
            elif before.channel is not None and after.channel is None:
                # 離開語音頻道
                event_type = self.EVENT_TYPES['VOICE_LEFT']
                event_data_extra = {
                    'left_channel_id': before.channel.id,
                    'left_channel_name': before.channel.name
                }
            elif before.channel != after.channel and after.channel is not None:
                # 移動語音頻道
                event_type = self.EVENT_TYPES['VOICE_MOVED']
                event_data_extra = {
                    'from_channel_id': before.channel.id if before.channel else None,
                    'from_channel_name': before.channel.name if before.channel else None,
                    'to_channel_id': after.channel.id,
                    'to_channel_name': after.channel.name
                }

            if event_type:
                event_data = {
                    'user_id': member.id,
                    'guild_id': member.guild.id,
                    'is_bot': member.bot,
                    **event_data_extra
                }

                event = Event(
                    event_type=event_type,
                    data=event_data,
                    source='discord.voice',
                    priority=EventPriority.NORMAL,
                    timestamp=time.time()
                )

                if self.event_bus:
                    await self.event_bus.publish(event)

        except Exception as e:
            logger.error(f"【成就事件監聽器】處理語音狀態事件失敗: {e}")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        """監聽成員加入事件.

        Args:
            member: 加入的成員
        """
        try:
            if member.bot:
                return

            event_data = {
                'user_id': member.id,
                'guild_id': member.guild.id,
                'join_timestamp': member.joined_at.timestamp() if member.joined_at else time.time(),
                'account_age_days': (time.time() - member.created_at.timestamp()) / 86400,
                'is_bot': member.bot
            }

            event = Event(
                event_type=self.EVENT_TYPES['MEMBER_JOINED'],
                data=event_data,
                source='discord.member',
                priority=EventPriority.HIGH,
                timestamp=time.time()
            )

            if self.event_bus:
                await self.event_bus.publish(event)

        except Exception as e:
            logger.error(f"【成就事件監聽器】處理成員加入事件失敗: {e}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        """監聽成員離開事件.

        Args:
            member: 離開的成員
        """
        try:
            if member.bot:
                return

            event_data = {
                'user_id': member.id,
                'guild_id': member.guild.id,
                'leave_timestamp': time.time(),
                'roles_count': len(member.roles) - 1,  # 排除 @everyone
                'is_bot': member.bot
            }

            event = Event(
                event_type=self.EVENT_TYPES['MEMBER_LEFT'],
                data=event_data,
                source='discord.member',
                priority=EventPriority.NORMAL,
                timestamp=time.time()
            )

            if self.event_bus:
                await self.event_bus.publish(event)

        except Exception as e:
            logger.error(f"【成就事件監聽器】處理成員離開事件失敗: {e}")

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        """監聽成員更新事件.

        Args:
            before: 更新前的成員資訊
            after: 更新後的成員資訊
        """
        try:
            if after.bot:
                return

            # 檢查是否有重要變更
            role_changes = set(after.roles) != set(before.roles)
            nickname_changes = before.nick != after.nick

            if role_changes or nickname_changes:
                event_data = {
                    'user_id': after.id,
                    'guild_id': after.guild.id,
                    'role_changes': role_changes,
                    'nickname_changes': nickname_changes,
                    'old_roles_count': len(before.roles) - 1,
                    'new_roles_count': len(after.roles) - 1,
                    'is_bot': after.bot
                }

                event = Event(
                    event_type=self.EVENT_TYPES['MEMBER_UPDATED'],
                    data=event_data,
                    source='discord.member',
                    priority=EventPriority.LOW,
                    timestamp=time.time()
                )

                if self.event_bus:
                    await self.event_bus.publish(event)

        except Exception as e:
            logger.error(f"【成就事件監聽器】處理成員更新事件失敗: {e}")

    @commands.Cog.listener()
    async def on_command(self, ctx: commands.Context) -> None:
        """監聽指令使用事件.

        Args:
            ctx: 指令上下文
        """
        try:
            if ctx.author.bot or not ctx.guild:
                return

            event_data = {
                'user_id': ctx.author.id,
                'guild_id': ctx.guild.id,
                'channel_id': ctx.channel.id,
                'command_name': ctx.command.name if ctx.command else 'unknown',
                'command_args': len(ctx.args) if ctx.args else 0,
                'is_bot': ctx.author.bot
            }

            event = Event(
                event_type=self.EVENT_TYPES['COMMAND_USED'],
                data=event_data,
                source='discord.command',
                priority=EventPriority.NORMAL,
                timestamp=time.time()
            )

            if self.event_bus:
                await self.event_bus.publish(event)

        except Exception as e:
            logger.error(f"【成就事件監聽器】處理指令事件失敗: {e}")

    @commands.Cog.listener()
    async def on_app_command_completion(
        self,
        interaction: discord.Interaction,
        command: discord.app_commands.Command | discord.app_commands.Group
    ) -> None:
        """監聽 Slash 指令完成事件.

        Args:
            interaction: Discord 互動物件
            command: 執行的指令物件
        """
        try:
            if interaction.user.bot or not interaction.guild:
                return

            event_data = {
                'user_id': interaction.user.id,
                'guild_id': interaction.guild.id,
                'channel_id': interaction.channel_id,
                'command_name': command.name,
                'command_type': 'slash',
                'is_bot': interaction.user.bot
            }

            event = Event(
                event_type=self.EVENT_TYPES['SLASH_COMMAND_USED'],
                data=event_data,
                source='discord.slash_command',
                priority=EventPriority.NORMAL,
                timestamp=time.time()
            )

            if self.event_bus:
                await self.event_bus.publish(event)

        except Exception as e:
            logger.error(f"【成就事件監聽器】處理 Slash 指令事件失敗: {e}")

    def get_event_stats(self) -> dict[str, Any]:
        """獲取事件統計資訊.

        Returns:
            dict: 事件統計資訊
        """
        stats = {
            **self._event_stats,
            'event_types': list(self.EVENT_TYPES.values()),
            'success_rate': (
                self._event_stats['processed_events'] / self._event_stats['total_events']
                if self._event_stats['total_events'] > 0 else 1.0
            )
        }

        # 添加處理器統計
        if self.event_processor:
            processor_stats = self.event_processor.get_processing_stats()
            stats['processor'] = processor_stats

        return stats

    async def _trigger_achievement_progress_updates(self, events: list) -> None:
        """觸發成就進度更新.

        Args:
            events: 已保存的事件列表
        """
        try:
            if not events:
                return

            # 按用戶分組事件以提高效率
            user_events = {}
            for event in events:
                user_id = event.get('user_id')
                if user_id:
                    if user_id not in user_events:
                        user_events[user_id] = []
                    user_events[user_id].append(event)

            # 為每個用戶更新成就進度
            for user_id, user_event_list in user_events.items():
                try:
                    await self._update_user_achievement_progress(user_id, user_event_list)
                except Exception as e:
                    logger.error(f"【成就進度更新】用戶 {user_id} 進度更新失敗: {e}")

            logger.debug(f"【成就進度更新】完成處理 {len(user_events)} 個用戶的進度更新")

        except Exception as e:
            logger.error(f"【成就進度更新】觸發進度更新失敗: {e}", exc_info=True)

    async def _update_user_achievement_progress(self, user_id: int, events: list) -> None:
        """更新單個用戶的成就進度.

        Args:
            user_id: 用戶 ID
            events: 用戶相關事件列表
        """
        try:
            # 如果有進度追蹤器，使用它來更新進度
            if hasattr(self, 'progress_tracker') and self.progress_tracker:
                for event in events:
                    await self.progress_tracker.track_event(
                        user_id=user_id,
                        event_type=event.get('event_type', ''),
                        event_data=event
                    )
            else:
                # 記錄警告但不阻止處理
                logger.warning(f"【成就進度更新】進度追蹤器不可用，跳過用戶 {user_id} 的進度更新")

        except Exception as e:
            logger.error(f"【成就進度更新】更新用戶 {user_id} 進度失敗: {e}")

    async def cleanup(self) -> None:
        """清理資源."""
        try:
            # 處理器清理
            if self.event_processor:
                # 處理剩餘的待處理事件
                pending_events = await self.event_processor.flush_pending_events()
                if pending_events:
                    logger.info(f"【成就事件監聽器】清理時處理剩餘事件: {len(pending_events)} 個")
                    # 持久化剩餘事件
                    await self._persist_event_batch(pending_events)

            # 取消 EventBus 訂閱
            if self.event_bus:
                self.event_bus.unsubscribe("achievement_event_processor")

            logger.info("【成就事件監聽器】清理完成")

        except Exception as e:
            logger.error(f"【成就事件監聽器】清理失敗: {e}")
