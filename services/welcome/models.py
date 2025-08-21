"""
歡迎系統資料模型
Task ID: 9 - 重構現有模組以符合新架構

定義歡迎系統相關的資料結構
"""

from dataclasses import dataclass
from typing import Optional
from PIL import Image


@dataclass
class WelcomeSettings:
    """歡迎設定資料模型"""
    guild_id: int
    channel_id: Optional[int] = None
    title: str = "歡迎 {member.name}!"
    description: str = "很高興見到你～"
    message: str = "歡迎 {member.mention} 加入 {guild.name}！"
    avatar_x: int = 30
    avatar_y: int = 80
    title_y: int = 60
    description_y: int = 120
    title_font_size: int = 36
    desc_font_size: int = 22
    avatar_size: Optional[int] = None
    background_path: Optional[str] = None

    def __post_init__(self):
        """設定後處理"""
        if self.avatar_size is None:
            self.avatar_size = int(0.22 * 800)  # 預設基於 800px 寬度


@dataclass
class WelcomeImage:
    """歡迎圖片資料模型"""
    image: Image.Image
    guild_id: int
    member_id: Optional[int] = None
    cache_key: Optional[str] = None
    
    def to_bytes(self, format: str = 'PNG') -> bytes:
        """轉換為位元組"""
        import io
        buffer = io.BytesIO()
        self.image.save(buffer, format)
        buffer.seek(0)
        return buffer.getvalue()