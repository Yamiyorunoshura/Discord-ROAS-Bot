"""
訊息監聽系統工具函數模組
- 提供字型管理和下載功能
- 錯誤處理和重試機制
- 文件操作和清理工具
- 文本處理和驗證工具
- 時間處理和格式化工具
- 網路請求和下載工具
"""

import os
import re
import time
import asyncio
import aiohttp
import logging
import tempfile
import hashlib
import requests
from typing import Optional, List, Dict, Any, Tuple, Union
from datetime import datetime, timedelta
from pathlib import Path

import discord
from PIL import Image, ImageFont

from ..config.config import (
    FONT_PATH, CHINESE_FONTS, FONT_DOWNLOAD_URLS, TW_TZ,
    DEFAULT_FONT_SIZE, USERNAME_FONT_SIZE, TIMESTAMP_FONT_SIZE,
    setup_logger
)

# 設定日誌記錄器
logger = setup_logger()

# ═══════════════════════════════════════════════════════════════════════════════════════════
# 字型管理工具
# ═══════════════════════════════════════════════════════════════════════════════════════════

def find_available_font() -> str:
    """
    尋找可用的字型檔案
    
    Returns:
        str: 字型檔案路徑
    """
    # 記錄嘗試過的路徑，用於診斷
    tried_paths = []
    
    # 先檢查自定義字型目錄 (最優先)
    for font_name in CHINESE_FONTS:
        font_path = os.path.join(FONT_PATH, font_name)
        tried_paths.append(font_path)
        
        if os.path.exists(font_path):
            logger.info(f"【訊息監聽】找到字型檔案: {font_path}")
            return font_path
            
    # 檢查系統字型目錄
    system_font_dirs = get_system_font_dirs()
    
    # 在系統字型目錄中尋找
    for font_dir in system_font_dirs:
        if not os.path.exists(font_dir):
            continue
            
        for font_name in CHINESE_FONTS:
            font_path = os.path.join(font_dir, font_name)
            tried_paths.append(font_path)
            
            if os.path.exists(font_path):
                logger.info(f"【訊息監聽】找到系統字型: {font_path}")
                return font_path
    
    # 如果找不到中文字型，嘗試下載
    for font_name, url in FONT_DOWNLOAD_URLS.items():
        target_path = os.path.join(FONT_PATH, font_name)
        if download_font(url, target_path):
            logger.info(f"【訊息監聽】已下載字型: {target_path}")
            return target_path
    
    # 如果都找不到，使用預設字型
    logger.warning(f"【訊息監聽】找不到合適的中文字型，嘗試過以下路徑: {tried_paths}")
    
    # 嘗試找到任何可用的字型
    system_fonts = find_system_fonts()
    if system_fonts:
        logger.info(f"【訊息監聽】使用系統字型: {system_fonts[0]}")
        return system_fonts[0]
    
    # 最後的備用方案
    return "arial.ttf"

def get_system_font_dirs() -> List[str]:
    """
    取得系統字型目錄列表
    
    Returns:
        List[str]: 系統字型目錄列表
    """
    system_font_dirs = []
    
    if os.name == "nt":  # Windows
        system_font_dirs.append(os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts"))
    elif os.name == "posix":  # Linux/Mac
        system_font_dirs.extend([
            "/usr/share/fonts",
            "/usr/local/share/fonts",
            "/usr/share/fonts/truetype",
            "/usr/share/fonts/opentype",
            "/usr/share/fonts/TTF",
            "/usr/share/fonts/OTF",
            os.path.expanduser("~/.fonts"),
            "/Library/Fonts",  # macOS
            os.path.expanduser("~/Library/Fonts"),  # macOS 用戶字型
        ])
    
    return system_font_dirs

def find_system_fonts() -> List[str]:
    """
    尋找系統字型，不依賴 matplotlib
    
    Returns:
        List[str]: 系統字型列表
    """
    fonts = []
    
    # 檢查常見字型路徑
    common_fonts = [
        "arial.ttf",
        "times.ttf",
        "cour.ttf",
        "verdana.ttf",
        "tahoma.ttf"
    ]
    
    # 檢查系統字型目錄
    system_font_dirs = get_system_font_dirs()
    
    # 在系統字型目錄中尋找常見字型
    for font_dir in system_font_dirs:
        if not os.path.exists(font_dir):
            continue
            
        for font_name in common_fonts:
            font_path = os.path.join(font_dir, font_name)
            if os.path.exists(font_path):
                fonts.append(font_path)
    
    return fonts

def download_font(url: str, target_path: str) -> bool:
    """
    下載字型檔案
    
    Args:
        url: 字型下載 URL
        target_path: 目標路徑
        
    Returns:
        bool: 是否下載成功
    """
    try:
        response = requests.get(url, stream=True, timeout=30)
        if response.status_code == 200:
            # 確保目標目錄存在
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            
            with open(target_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            # 驗證下載的檔案是否為有效的字型檔案
            if validate_font_file(target_path):
                logger.info(f"【訊息監聽】成功下載字型: {target_path}")
                return True
            else:
                logger.error(f"【訊息監聽】下載的字型檔案無效: {target_path}")
                safe_remove_file(target_path)
                return False
        else:
            logger.error(f"【訊息監聽】下載字型失敗，HTTP狀態碼: {response.status_code}")
            return False
    except Exception as exc:
        logger.error(f"【訊息監聽】下載字型失敗: {exc}")
        return False

def validate_font_file(font_path: str) -> bool:
    """
    驗證字型檔案是否有效
    
    Args:
        font_path: 字型檔案路徑
        
    Returns:
        bool: 是否有效
    """
    try:
        # 嘗試載入字型
        font = ImageFont.truetype(font_path, DEFAULT_FONT_SIZE)
        
        # 測試字型是否能正常使用
        test_text = "測試"
        from PIL import ImageDraw, Image
        test_image = Image.new('RGB', (100, 100), (255, 255, 255))
        draw = ImageDraw.Draw(test_image)
        draw.text((10, 10), test_text, font=font, fill=(0, 0, 0))
        
        return True
    except Exception as exc:
        logger.error(f"【訊息監聽】驗證字型檔案失敗: {exc}")
        return False

def test_font_chinese_support(font_path: str) -> bool:
    """
    測試字型是否支援中文
    
    Args:
        font_path: 字型檔案路徑
        
    Returns:
        bool: 是否支援中文
    """
    try:
        font = ImageFont.truetype(font_path, DEFAULT_FONT_SIZE)
        
        # 測試常見中文字符
        test_chars = ["測", "試", "中", "文", "字", "型"]
        
        for char in test_chars:
            try:
                # 嘗試獲取字符的邊界框
                bbox = font.getbbox(char)
                if bbox[2] - bbox[0] <= 0:  # 寬度為0表示字符不存在
                    logger.warning(f"【訊息監聽】字型 {font_path} 不支援字符: {char}")
                    return False
            except Exception:
                logger.warning(f"【訊息監聽】字型 {font_path} 不支援字符: {char}")
                return False
        
        logger.info(f"【訊息監聽】字型 {font_path} 支援中文")
        return True
    except Exception as exc:
        logger.error(f"【訊息監聽】測試字型中文支援失敗: {exc}")
        return False

# ═══════════════════════════════════════════════════════════════════════════════════════════
# 錯誤處理工具
# ═══════════════════════════════════════════════════════════════════════════════════════════

def safe_execute(func, *args, default=None, max_retries: int = 3, **kwargs):
    """
    安全執行函數，包含重試機制
    
    Args:
        func: 要執行的函數
        *args: 函數參數
        default: 失敗時的預設返回值
        max_retries: 最大重試次數
        **kwargs: 函數關鍵字參數
        
    Returns:
        Any: 函數執行結果或預設值
    """
    for attempt in range(max_retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            if attempt == max_retries:
                logger.error(f"【訊息監聽】執行函數 {func.__name__} 失敗，已達最大重試次數: {exc}")
                return default
            else:
                logger.warning(f"【訊息監聽】執行函數 {func.__name__} 失敗，重試 {attempt + 1}/{max_retries}: {exc}")
                time.sleep(2 ** attempt)  # 指數退避

async def safe_execute_async(func, *args, default=None, max_retries: int = 3, **kwargs):
    """
    安全執行異步函數，包含重試機制
    
    Args:
        func: 要執行的異步函數
        *args: 函數參數
        default: 失敗時的預設返回值
        max_retries: 最大重試次數
        **kwargs: 函數關鍵字參數
        
    Returns:
        Any: 函數執行結果或預設值
    """
    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as exc:
            if attempt == max_retries:
                logger.error(f"【訊息監聽】執行異步函數 {func.__name__} 失敗，已達最大重試次數: {exc}")
                return default
            else:
                logger.warning(f"【訊息監聽】執行異步函數 {func.__name__} 失敗，重試 {attempt + 1}/{max_retries}: {exc}")
                await asyncio.sleep(2 ** attempt)  # 指數退避

def log_error_with_context(error: Exception, context: str, extra_info: Dict[str, Any] = None):
    """
    記錄錯誤並包含上下文信息
    
    Args:
        error: 錯誤對象
        context: 上下文描述
        extra_info: 額外信息
    """
    error_msg = f"【訊息監聽】{context}: {error}"
    
    if extra_info:
        error_msg += f" | 額外信息: {extra_info}"
    
    logger.error(error_msg, exc_info=True)

# ═══════════════════════════════════════════════════════════════════════════════════════════
# 文件操作工具
# ═══════════════════════════════════════════════════════════════════════════════════════════

def safe_remove_file(file_path: str) -> bool:
    """
    安全刪除檔案
    
    Args:
        file_path: 檔案路徑
        
    Returns:
        bool: 是否成功刪除
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.debug(f"【訊息監聽】已刪除檔案: {file_path}")
            return True
        return False
    except Exception as exc:
        logger.error(f"【訊息監聽】刪除檔案失敗 {file_path}: {exc}")
        return False

def ensure_directory_exists(directory: str) -> bool:
    """
    確保目錄存在
    
    Args:
        directory: 目錄路徑
        
    Returns:
        bool: 是否成功創建或已存在
    """
    try:
        os.makedirs(directory, exist_ok=True)
        return True
    except Exception as exc:
        logger.error(f"【訊息監聽】創建目錄失敗 {directory}: {exc}")
        return False

def get_file_size(file_path: str) -> int:
    """
    取得檔案大小
    
    Args:
        file_path: 檔案路徑
        
    Returns:
        int: 檔案大小（字節），失敗時返回 -1
    """
    try:
        return os.path.getsize(file_path)
    except Exception as exc:
        logger.error(f"【訊息監聽】取得檔案大小失敗 {file_path}: {exc}")
        return -1

def get_file_hash(file_path: str, algorithm: str = "md5") -> str | None:
    """
    計算檔案哈希值
    
    Args:
        file_path: 檔案路徑
        algorithm: 哈希算法 (md5, sha1, sha256)
        
    Returns:
        str | None: 哈希值，失敗時返回 None
    """
    try:
        hash_obj = hashlib.new(algorithm)
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_obj.update(chunk)
        
        return hash_obj.hexdigest()
    except Exception as exc:
        logger.error(f"【訊息監聽】計算檔案哈希失敗 {file_path}: {exc}")
        return None

def create_temp_file(suffix: str = "", prefix: str = "msg_listener_") -> str:
    """
    創建臨時檔案
    
    Args:
        suffix: 檔案後綴
        prefix: 檔案前綴
        
    Returns:
        str: 臨時檔案路徑
    """
    try:
        fd, temp_path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
        os.close(fd)  # 關閉檔案描述符
        return temp_path
    except Exception as exc:
        logger.error(f"【訊息監聽】創建臨時檔案失敗: {exc}")
        return ""

# ═══════════════════════════════════════════════════════════════════════════════════════════
# 文本處理工具
# ═══════════════════════════════════════════════════════════════════════════════════════════

def sanitize_filename(filename: str) -> str:
    """
    清理檔案名稱，移除不安全字符
    
    Args:
        filename: 原始檔案名稱
        
    Returns:
        str: 清理後的檔案名稱
    """
    # 移除或替換不安全字符
    unsafe_chars = r'[<>:"/\\|?*]'
    safe_filename = re.sub(unsafe_chars, '_', filename)
    
    # 移除前後空格和點
    safe_filename = safe_filename.strip('. ')
    
    # 限制檔案名長度
    if len(safe_filename) > 200:
        safe_filename = safe_filename[:200]
    
    # 確保不是空檔案名
    if not safe_filename:
        safe_filename = "untitled"
    
    return safe_filename

def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    截斷文本到指定長度
    
    Args:
        text: 原始文本
        max_length: 最大長度
        suffix: 截斷後的後綴
        
    Returns:
        str: 截斷後的文本
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix

def extract_urls(text: str) -> List[str]:
    """
    從文本中提取 URL
    
    Args:
        text: 文本內容
        
    Returns:
        List[str]: URL 列表
    """
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    return re.findall(url_pattern, text)

def extract_mentions(text: str) -> Tuple[List[str], List[str], List[str]]:
    """
    從文本中提取提及信息
    
    Args:
        text: 文本內容
        
    Returns:
        Tuple[List[str], List[str], List[str]]: (用戶ID列表, 角色ID列表, 頻道ID列表)
    """
    user_mentions = re.findall(r'<@!?(\d+)>', text)
    role_mentions = re.findall(r'<@&(\d+)>', text)
    channel_mentions = re.findall(r'<#(\d+)>', text)
    
    return user_mentions, role_mentions, channel_mentions

def extract_custom_emojis(text: str) -> List[Dict[str, str]]:
    """
    從文本中提取自定義表情符號
    
    Args:
        text: 文本內容
        
    Returns:
        List[Dict[str, str]]: 表情符號信息列表
    """
    emoji_pattern = r'<(a?):([^:]+):(\d+)>'
    matches = re.findall(emoji_pattern, text)
    
    emojis = []
    for animated, name, emoji_id in matches:
        emojis.append({
            'animated': bool(animated),
            'name': name,
            'id': emoji_id,
            'url': f"https://cdn.discordapp.com/emojis/{emoji_id}.{'gif' if animated else 'png'}"
        })
    
    return emojis

def clean_discord_formatting(text: str) -> str:
    """
    清理 Discord 格式化標記
    
    Args:
        text: 原始文本
        
    Returns:
        str: 清理後的文本
    """
    # 移除 Discord 格式化標記
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # 粗體
    text = re.sub(r'\*(.*?)\*', r'\1', text)      # 斜體
    text = re.sub(r'__(.*?)__', r'\1', text)      # 底線
    text = re.sub(r'~~(.*?)~~', r'\1', text)      # 刪除線
    text = re.sub(r'`(.*?)`', r'\1', text)        # 行內代碼
    text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)  # 代碼塊
    text = re.sub(r'> (.*?)(?=\n|$)', r'\1', text)  # 引用
    
    return text.strip()

# ═══════════════════════════════════════════════════════════════════════════════════════════
# 時間處理工具
# ═══════════════════════════════════════════════════════════════════════════════════════════

def format_timestamp(timestamp: datetime, format_type: str = "default") -> str:
    """
    格式化時間戳
    
    Args:
        timestamp: 時間戳
        format_type: 格式類型 (default, short, long, relative)
        
    Returns:
        str: 格式化後的時間字符串
    """
    try:
        # 確保時間戳有時區信息
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=TW_TZ)
        else:
            timestamp = timestamp.astimezone(TW_TZ)
        
        if format_type == "short":
            return timestamp.strftime("%m/%d %H:%M")
        elif format_type == "long":
            return timestamp.strftime("%Y年%m月%d日 %H:%M:%S")
        elif format_type == "relative":
            return get_relative_time(timestamp)
        else:  # default
            return timestamp.strftime("%Y/%m/%d %H:%M")
    except Exception as exc:
        logger.error(f"【訊息監聽】格式化時間戳失敗: {exc}")
        return "未知時間"

def get_relative_time(timestamp: datetime) -> str:
    """
    取得相對時間描述
    
    Args:
        timestamp: 時間戳
        
    Returns:
        str: 相對時間描述
    """
    try:
        now = datetime.now(TW_TZ)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=TW_TZ)
        
        diff = now - timestamp
        
        if diff.days > 0:
            return f"{diff.days}天前"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours}小時前"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes}分鐘前"
        else:
            return "剛剛"
    except Exception as exc:
        logger.error(f"【訊息監聽】計算相對時間失敗: {exc}")
        return "未知時間"

def parse_time_duration(duration_str: str) -> timedelta | None:
    """
    解析時間持續時間字符串
    
    Args:
        duration_str: 時間字符串 (例如: "1h", "30m", "2d")
        
    Returns:
        timedelta | None: 時間間隔對象，解析失敗時返回 None
    """
    try:
        # 正則表達式匹配時間格式
        pattern = r'(\d+)([smhd])'
        matches = re.findall(pattern, duration_str.lower())
        
        if not matches:
            return None
        
        total_seconds = 0
        for value, unit in matches:
            value = int(value)
            if unit == 's':
                total_seconds += value
            elif unit == 'm':
                total_seconds += value * 60
            elif unit == 'h':
                total_seconds += value * 3600
            elif unit == 'd':
                total_seconds += value * 86400
        
        return timedelta(seconds=total_seconds)
    except Exception as exc:
        logger.error(f"【訊息監聽】解析時間持續時間失敗: {exc}")
        return None

# ═══════════════════════════════════════════════════════════════════════════════════════════
# 網路請求工具
# ═══════════════════════════════════════════════════════════════════════════════════════════

async def download_file_async(url: str, target_path: str, max_size: int = 50 * 1024 * 1024) -> bool:
    """
    異步下載檔案
    
    Args:
        url: 下載 URL
        target_path: 目標路徑
        max_size: 最大檔案大小（字節）
        
    Returns:
        bool: 是否下載成功
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    logger.error(f"【訊息監聽】下載檔案失敗，HTTP狀態碼: {response.status}")
                    return False
                
                # 檢查檔案大小
                content_length = response.headers.get('content-length')
                if content_length and int(content_length) > max_size:
                    logger.error(f"【訊息監聽】檔案太大，超過限制: {content_length} > {max_size}")
                    return False
                
                # 確保目標目錄存在
                ensure_directory_exists(os.path.dirname(target_path))
                
                # 下載檔案
                with open(target_path, 'wb') as f:
                    downloaded = 0
                    async for chunk in response.content.iter_chunked(8192):
                        downloaded += len(chunk)
                        if downloaded > max_size:
                            logger.error(f"【訊息監聽】檔案太大，下載中止: {downloaded} > {max_size}")
                            safe_remove_file(target_path)
                            return False
                        f.write(chunk)
                
                logger.info(f"【訊息監聽】成功下載檔案: {target_path}")
                return True
                
    except Exception as exc:
        logger.error(f"【訊息監聽】異步下載檔案失敗: {exc}")
        safe_remove_file(target_path)
        return False

async def get_url_content_type(url: str) -> str | None:
    """
    取得 URL 的內容類型
    
    Args:
        url: 目標 URL
        
    Returns:
        str | None: 內容類型，失敗時返回 None
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.head(url) as response:
                return response.headers.get('content-type')
    except Exception as exc:
        logger.error(f"【訊息監聽】取得 URL 內容類型失敗: {exc}")
        return None

async def check_url_accessible(url: str, timeout: int = 10) -> bool:
    """
    檢查 URL 是否可訪問
    
    Args:
        url: 目標 URL
        timeout: 超時時間（秒）
        
    Returns:
        bool: 是否可訪問
    """
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
            async with session.head(url) as response:
                return response.status == 200
    except Exception as exc:
        logger.debug(f"【訊息監聽】URL 不可訪問: {url} - {exc}")
        return False

# ═══════════════════════════════════════════════════════════════════════════════════════════
# Discord 相關工具
# ═══════════════════════════════════════════════════════════════════════════════════════════

def get_user_display_name(user: discord.Member | discord.User) -> str:
    """
    取得用戶顯示名稱
    
    Args:
        user: Discord 用戶或成員
        
    Returns:
        str: 顯示名稱
    """
    if isinstance(user, discord.Member) and user.nick:
        return user.nick
    elif hasattr(user, 'global_name') and user.global_name:
        return user.global_name
    else:
        return user.name

def get_channel_display_name(channel: discord.CategoryChannel | discord.TextChannel | discord.VoiceChannel) -> str:
    """
    取得頻道顯示名稱
    
    Args:
        channel: Discord 頻道
        
    Returns:
        str: 顯示名稱
    """
    if isinstance(channel, discord.TextChannel):
        return f"#{channel.name}"
    elif isinstance(channel, discord.VoiceChannel):
        return f"🔊{channel.name}"
    elif isinstance(channel, discord.CategoryChannel):
        return f"📁{channel.name}"
    else:
        return channel.name

def is_image_attachment(attachment: discord.Attachment) -> bool:
    """
    檢查附件是否為圖片
    
    Args:
        attachment: Discord 附件
        
    Returns:
        bool: 是否為圖片
    """
    if hasattr(attachment, 'content_type') and attachment.content_type:
        return attachment.content_type.startswith('image/')
    
    # 如果沒有 content_type，根據副檔名判斷
    image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}
    return any(attachment.filename.lower().endswith(ext) for ext in image_extensions)

def get_message_jump_url(message: discord.Message) -> str:
    """
    取得訊息跳轉 URL
    
    Args:
        message: Discord 訊息
        
    Returns:
        str: 跳轉 URL
    """
    if message.guild:
        return f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}"
    else:
        return f"https://discord.com/channels/@me/{message.channel.id}/{message.id}"

# ═══════════════════════════════════════════════════════════════════════════════════════════
# 數據驗證工具
# ═══════════════════════════════════════════════════════════════════════════════════════════

def validate_discord_id(discord_id: int | str) -> bool:
    """
    驗證 Discord ID 格式
    
    Args:
        discord_id: Discord ID
        
    Returns:
        bool: 是否有效
    """
    try:
        id_int = int(discord_id)
        # Discord ID 應該是 64 位正整數
        return 0 < id_int < 2**63
    except (ValueError, TypeError):
        return False

def validate_channel_id(channel_id: int | str) -> bool:
    """
    驗證頻道 ID 格式
    
    Args:
        channel_id: 頻道 ID
        
    Returns:
        bool: 是否有效
    """
    return validate_discord_id(channel_id)

def validate_message_content(content: str) -> bool:
    """
    驗證訊息內容
    
    Args:
        content: 訊息內容
        
    Returns:
        bool: 是否有效
    """
    # Discord 訊息長度限制
    return len(content) <= 2000

def validate_setting_value(key: str, value: str) -> bool:
    """
    驗證設定值
    
    Args:
        key: 設定鍵
        value: 設定值
        
    Returns:
        bool: 是否有效
    """
    try:
        if key.endswith('_id'):
            return validate_discord_id(value)
        elif key.endswith('_days'):
            days = int(value)
            return 1 <= days <= 365
        elif key.endswith('_limit'):
            limit = int(value)
            return 1 <= limit <= 1000
        elif key.endswith('_enabled'):
            return value.lower() in ['true', 'false', '1', '0']
        else:
            return len(value) <= 1000
    except (ValueError, TypeError):
        return False 