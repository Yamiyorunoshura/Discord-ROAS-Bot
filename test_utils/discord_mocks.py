"""
Discord API模擬類別
Task ID: 10 - 建立系統整合測試

提供測試環境所需的Discord API模擬對象，支援：
- Guild（伺服器）模擬
- Member（成員）模擬  
- TextChannel（文字頻道）模擬
- Message（訊息）模擬
- Interaction（互動）模擬
"""
from __future__ import annotations

import asyncio
from typing import Any, Optional, List, Dict, Union
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime
import discord
from discord.ext import commands


class MockPermissions:
    """模擬Discord權限對象"""
    
    def __init__(self, **permissions):
        # 設定預設權限
        self.manage_guild = permissions.get('manage_guild', False)
        self.manage_channels = permissions.get('manage_channels', False) 
        self.manage_messages = permissions.get('manage_messages', False)
        self.manage_roles = permissions.get('manage_roles', False)
        self.administrator = permissions.get('administrator', False)
        self.send_messages = permissions.get('send_messages', True)
        self.read_messages = permissions.get('read_messages', True)
        self.use_slash_commands = permissions.get('use_slash_commands', True)


class MockRole:
    """模擬Discord身分組對象"""
    
    def __init__(self, role_id: int, name: str, **kwargs):
        self.id = role_id
        self.name = name
        self.position = kwargs.get('position', 0)
        self.permissions = MockPermissions(**kwargs.get('permissions', {}))
        self.color = kwargs.get('color', 0)
        self.mentionable = kwargs.get('mentionable', True)
        self.managed = kwargs.get('managed', False)


class MockMember:
    """模擬Discord成員對象"""
    
    def __init__(self, user_id: int, name: str, display_name: str, guild: 'MockGuild', **kwargs):
        self.id = user_id
        self.name = name
        self.display_name = display_name
        self.guild = guild
        self.bot = kwargs.get('bot', False)
        
        # 權限系統
        self.guild_permissions = MockPermissions(**kwargs.get('permissions', {}))
        
        # 身分組
        self._roles = [MockRole(guild.id, "@everyone")]  # 每個成員都有@everyone身分組
        if 'roles' in kwargs:
            self._roles.extend(kwargs['roles'])
            
        # Discord用戶屬性
        self.discriminator = kwargs.get('discriminator', '0001')
        self.avatar = kwargs.get('avatar', None)
        self.created_at = kwargs.get('created_at', datetime.now())
        self.joined_at = kwargs.get('joined_at', datetime.now())
    
    @property
    def roles(self) -> List[MockRole]:
        return self._roles
    
    @property
    def mention(self) -> str:
        return f"<@{self.id}>"
    
    def __str__(self) -> str:
        return f"{self.name}#{self.discriminator}"


class MockTextChannel:
    """模擬Discord文字頻道對象"""
    
    def __init__(self, channel_id: int, name: str, guild: 'MockGuild', **kwargs):
        self.id = channel_id
        self.name = name
        self.guild = guild
        self.type = discord.ChannelType.text
        self.position = kwargs.get('position', 0)
        self.topic = kwargs.get('topic', None)
        self.nsfw = kwargs.get('nsfw', False)
        
        # 訊息歷史（用於測試）
        self._messages: List[MockMessage] = []
    
    @property
    def mention(self) -> str:
        return f"<#{self.id}>"
    
    async def send(self, content=None, **kwargs) -> 'MockMessage':
        """模擬發送訊息"""
        # 創建一個系統訊息
        bot_member = MockMember(
            user_id=12345, 
            name="TestBot", 
            display_name="測試機器人",
            guild=self.guild,
            bot=True
        )
        
        message = MockMessage(
            message_id=len(self._messages) + 1000,
            content=content or "",
            author=bot_member,
            channel=self,
            **kwargs
        )
        self._messages.append(message)
        return message
    
    def permissions_for(self, member: MockMember) -> MockPermissions:
        """獲取成員在此頻道的權限"""
        return member.guild_permissions


class MockMessage:
    """模擬Discord訊息對象"""
    
    def __init__(self, message_id: int, content: str, author: MockMember, channel: Optional[MockTextChannel], **kwargs):
        self.id = message_id
        self.content = content
        self.author = author
        self.channel = channel
        self.guild = channel.guild if channel else author.guild
        
        # 訊息屬性
        self.created_at = kwargs.get('created_at', datetime.now())
        self.edited_at = kwargs.get('edited_at', None)
        self.pinned = kwargs.get('pinned', False)
        self.mention_everyone = kwargs.get('mention_everyone', False)
        
        # 訊息組件
        self.attachments = kwargs.get('attachments', [])
        self.embeds = kwargs.get('embeds', [])
        self.reactions = kwargs.get('reactions', [])
        
        # 引用和回覆
        self.reference = kwargs.get('reference', None)
        self.mentions = kwargs.get('mentions', [])
    
    async def delete(self):
        """模擬刪除訊息"""
        if self.channel and self in self.channel._messages:
            self.channel._messages.remove(self)
    
    async def edit(self, **kwargs):
        """模擬編輯訊息"""
        if 'content' in kwargs:
            self.content = kwargs['content']
        if 'embed' in kwargs:
            self.embeds = [kwargs['embed']]


class MockGuild:
    """模擬Discord伺服器對象"""
    
    def __init__(self, guild_id: int, name: str, **kwargs):
        self.id = guild_id
        self.name = name
        self.owner_id = kwargs.get('owner_id', 111111)
        self.description = kwargs.get('description', None)
        self.icon = kwargs.get('icon', None)
        
        # 成員和頻道管理
        self._members: Dict[int, MockMember] = {}
        self._channels: Dict[int, MockTextChannel] = {}
        self._roles: Dict[int, MockRole] = {}
        
        # 預設身分組
        everyone_role = MockRole(guild_id, "@everyone")
        self._roles[guild_id] = everyone_role
        
        # 伺服器設定
        self.member_count = kwargs.get('member_count', 0)
        self.created_at = kwargs.get('created_at', datetime.now())
        
        # 系統功能
        self.system_channel = kwargs.get('system_channel', None)
        self.preferred_locale = kwargs.get('preferred_locale', 'zh-TW')
    
    def get_member(self, user_id: int) -> Optional[MockMember]:
        """獲取成員"""
        return self._members.get(user_id)
    
    def get_channel(self, channel_id: int) -> Optional[MockTextChannel]:
        """獲取頻道"""
        return self._channels.get(channel_id)
    
    def get_role(self, role_id: int) -> Optional[MockRole]:
        """獲取身分組"""
        return self._roles.get(role_id)
    
    @property
    def members(self) -> List[MockMember]:
        return list(self._members.values())
    
    @property
    def channels(self) -> List[MockTextChannel]:
        return list(self._channels.values())
    
    @property
    def roles(self) -> List[MockRole]:
        return list(self._roles.values())
    
    def add_member(self, member: MockMember):
        """添加成員"""
        self._members[member.id] = member
        member.guild = self
        self.member_count = len(self._members)
    
    def add_channel(self, channel: MockTextChannel):
        """添加頻道"""
        self._channels[channel.id] = channel
        channel.guild = self
    
    def add_role(self, role: MockRole):
        """添加身分組"""
        self._roles[role.id] = role


class MockInteractionResponse:
    """模擬互動回應對象"""
    
    def __init__(self, interaction: 'MockInteraction'):
        self.interaction = interaction
        self._deferred = False
        self._responded = False
        
        # 模擬方法
        self.defer = AsyncMock()
        self.send_message = AsyncMock()
        self.edit_message = AsyncMock()
    
    async def defer(self, ephemeral: bool = False):
        """延遲回應"""
        self._deferred = True
    
    async def send_message(self, content=None, **kwargs):
        """發送回應訊息"""
        self._responded = True
        # 可以記錄發送的內容用於測試驗證
        return MockMessage(
            message_id=99999,
            content=content or "",
            author=self.interaction.client.user,
            channel=self.interaction.channel
        )


class MockInteractionFollowup:
    """模擬互動後續對象"""
    
    def __init__(self, interaction: 'MockInteraction'):
        self.interaction = interaction
        
        # 模擬方法
        self.send = AsyncMock()
        self.edit = AsyncMock()
    
    async def send(self, content=None, **kwargs):
        """發送後續訊息"""
        return MockMessage(
            message_id=99998,
            content=content or "",
            author=self.interaction.client.user,
            channel=self.interaction.channel
        )


class MockInteraction:
    """模擬Discord互動對象（斜線指令、按鈕等）"""
    
    def __init__(self, guild: MockGuild, user: MockMember, **kwargs):
        self.guild = guild
        self.user = user
        self.channel = kwargs.get('channel', None)
        
        # 互動屬性
        self.id = kwargs.get('interaction_id', 777888999)
        self.token = kwargs.get('token', "mock_token")
        self.type = kwargs.get('type', discord.InteractionType.application_command)
        self.created_at = kwargs.get('created_at', datetime.now())
        
        # 指令資料
        self.data = kwargs.get('data', {})
        self.command = kwargs.get('command', None)
        
        # 模擬客戶端
        self.client = MockBot()
        
        # 回應系統
        self.response = MockInteractionResponse(self)
        self.followup = MockInteractionFollowup(self)
    
    @property
    def guild_id(self) -> Optional[int]:
        return self.guild.id if self.guild else None
    
    @property
    def channel_id(self) -> Optional[int]:
        return self.channel.id if self.channel else None


class MockBot:
    """模擬Discord機器人對象"""
    
    def __init__(self, **kwargs):
        # 創建一個臨時公會用於機器人用戶
        temp_guild = MockGuild(999999999, "BotGuild")
        self.user = MockMember(
            user_id=kwargs.get('bot_id', 123456789),
            name=kwargs.get('bot_name', "TestBot"),
            display_name=kwargs.get('bot_display_name', "測試機器人"),
            guild=temp_guild,
            bot=True
        )
        
        self.guilds: List[MockGuild] = []
        self.latency = kwargs.get('latency', 0.1)
        self.is_ready = kwargs.get('is_ready', True)
    
    def get_guild(self, guild_id: int) -> Optional[MockGuild]:
        """獲取公會"""
        for guild in self.guilds:
            if guild.id == guild_id:
                return guild
        return None
    
    def add_guild(self, guild: MockGuild):
        """添加公會"""
        self.guilds.append(guild)


# === 便利工具函數 ===

def create_mock_guild_with_members(guild_id: int = 123456789, member_count: int = 5) -> MockGuild:
    """創建帶有成員的模擬伺服器"""
    guild = MockGuild(guild_id, "測試伺服器")
    
    for i in range(member_count):
        member = MockMember(
            user_id=1000 + i,
            name=f"user_{i}",
            display_name=f"用戶{i}",
            guild=guild
        )
        guild.add_member(member)
    
    return guild


def create_mock_guild_with_channels(guild_id: int = 123456789) -> MockGuild:
    """創建帶有頻道的模擬伺服器"""
    guild = MockGuild(guild_id, "測試伺服器")
    
    # 添加一些基本頻道
    channels = [
        ("general", "一般"),
        ("random", "隨機"),
        ("bot-commands", "機器人指令")
    ]
    
    for i, (name_en, name_zh) in enumerate(channels):
        channel = MockTextChannel(
            channel_id=5000 + i,
            name=name_zh,
            guild=guild
        )
        guild.add_channel(channel)
    
    return guild


def create_test_interaction(guild: MockGuild, user: MockMember, channel: Optional[MockTextChannel] = None) -> MockInteraction:
    """創建測試用互動對象"""
    if channel is None and guild.channels:
        channel = guild.channels[0]
    
    return MockInteraction(guild, user, channel=channel)


def create_admin_member(guild: MockGuild, user_id: int = 999) -> MockMember:
    """創建管理員成員"""
    return MockMember(
        user_id=user_id,
        name="admin",
        display_name="管理員",
        guild=guild,
        permissions={
            'administrator': True,
            'manage_guild': True,
            'manage_channels': True,
            'manage_messages': True,
            'manage_roles': True
        }
    )


# === 預設測試資料 ===

DEFAULT_TEST_GUILD = create_mock_guild_with_members()
DEFAULT_TEST_CHANNEL = MockTextChannel(555666777, "測試頻道", DEFAULT_TEST_GUILD)
DEFAULT_TEST_GUILD.add_channel(DEFAULT_TEST_CHANNEL)

print("✅ Discord模擬類別載入完成")