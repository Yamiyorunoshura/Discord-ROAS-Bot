"""
訊息系統資料模型
Task ID: 9 - 重構現有模組以符合新架構

定義訊息系統相關的資料結構
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime


@dataclass
class MessageRecord:
    """訊息記錄資料模型"""
    message_id: int
    channel_id: int
    guild_id: int
    author_id: int
    content: str
    timestamp: float
    attachments: Optional[str] = None
    
    @classmethod
    def from_discord_message(cls, message) -> 'MessageRecord':
        """從 Discord 訊息建立記錄"""
        import json
        
        attachments_data = None
        if message.attachments:
            attachments_data = json.dumps([{
                'filename': att.filename,
                'url': att.url,
                'size': att.size
            } for att in message.attachments])
        
        return cls(
            message_id=message.id,
            channel_id=message.channel.id,
            guild_id=message.guild.id if message.guild else 0,
            author_id=message.author.id,
            content=message.content,
            timestamp=message.created_at.timestamp(),
            attachments=attachments_data
        )


@dataclass
class MessageCacheItem:
    """訊息快取項目"""
    message: Any  # discord.Message
    channel_id: int
    cached_at: datetime
    processed: bool = False
    
    def __post_init__(self):
        if self.cached_at is None:
            self.cached_at = datetime.now()


@dataclass
class RenderConfig:
    """圖片渲染配置"""
    chat_width: int = 800
    max_height: int = 2000
    avatar_size: int = 40
    message_padding: int = 10
    content_padding: int = 50
    bg_color: tuple = (54, 57, 63)
    text_color: tuple = (220, 221, 222)
    embed_color: tuple = (78, 80, 88)
    default_font_size: int = 14
    username_font_size: int = 16
    timestamp_font_size: int = 12
    max_cached_messages: int = 10
    max_cache_time: int = 600  # 10分鐘


@dataclass
class MonitorSettings:
    """監聽設定"""
    enabled: bool = True
    log_channel_id: Optional[int] = None
    monitored_channels: List[int] = field(default_factory=list)
    record_edits: bool = True
    record_deletes: bool = True
    retention_days: int = 7
    render_mode: str = "batch"  # batch, immediate, disabled


@dataclass 
class SearchQuery:
    """搜尋查詢參數"""
    keyword: Optional[str] = None
    channel_id: Optional[int] = None
    author_id: Optional[int] = None
    guild_id: Optional[int] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: int = 20
    offset: int = 0
    include_attachments: bool = False


@dataclass
class SearchResult:
    """搜尋結果"""
    records: List[MessageRecord]
    total_count: int
    has_more: bool
    query: SearchQuery