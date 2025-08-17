# message_listener.py  ── 訊息監控與日誌模組 (圖片渲染版 v1.62)
# ============================================================
# 主要功能：
#  - 訊息圖片日誌：將訊息以Discord聊天框風格圖片呈現
#  - 批次處理：每累積10條訊息或超過10分鐘自動渲染發送
#  - 支援回覆關係、表情符號、附件圖片顯示
#  - 訊息搜尋：最近 24h 關鍵字 / 頻道查詢，支援分頁
#  - 訊息日誌設定：日誌頻道、是否記錄編輯 / 刪除、監聽清單
#  - v1.62 新功能：
#    * 修復 Linux 中文渲染：增強字型檢測與載入機制
#    * 自動下載字型：缺少字型時自動下載
#    * 字型載入診斷：詳細日誌協助排查問題
#    * 備用字型機制：確保在任何環境下都能顯示中文
#    * 字型檢測優化：優先使用專案字型目錄
#    * 增強錯誤處理：提供更詳細的錯誤信息
# 
# 效能優化：
#  - 資料庫連線池化
#  - 批次處理減少 I/O 操作
#  - 快取機制避免重複查詢
#  - 非同步操作優化
# ============================================================

from __future__ import annotations

import datetime as dt
import io
import logging
import logging.handlers
import re
import traceback
import contextlib
import asyncio
import datetime as _dt
import typing as _t
import os
import textwrap
import tempfile
import time
import math
import shutil
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass
from collections import defaultdict

import aiohttp
import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.ui import Button, ChannelSelect, Select, View, Modal, TextInput
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont, ImageColor, ImageOps

from config import MESSAGE_DB_PATH, MESSAGE_LOG_PATH, is_allowed

load_dotenv()

# ────────────────────────────
# 圖片日誌設定
# ────────────────────────────
# 訊息緩存設定 (全域變數)
MAX_CACHED_MESSAGES = 10  # 每頻道最大緩存訊息數
MAX_CACHE_TIME = 600      # 緩存最大時間 (10分鐘)

# 圖片渲染設定
CHAT_WIDTH = 800          # 聊天框寬度
MAX_HEIGHT = 2000         # 最大高度
AVATAR_SIZE = 40          # 頭像大小
MESSAGE_PADDING = 10      # 訊息間距
CONTENT_PADDING = 50      # 內容左側留白
BG_COLOR = (54, 57, 63)   # Discord 背景顏色
TEXT_COLOR = (220, 221, 222)  # 文字顏色
EMBED_COLOR = (78, 80, 88)    # 內嵌訊息背景

# 字型設定 (v1.62: 增強中文顯示支援)
DEFAULT_FONT = "arial.ttf"
DEFAULT_FONT_SIZE = 14
FONT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "fonts")
USERNAME_FONT_SIZE = 16
TIMESTAMP_FONT_SIZE = 12

# 字型下載 URL (v1.62: 新增自動下載功能)
FONT_DOWNLOAD_URLS = {
    "NotoSansTC-Regular.otf": "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/TraditionalChinese/NotoSansTC-Regular.otf",
    "NotoSansSC-Regular.otf": "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansSC-Regular.otf",
    "wqy-microhei.ttc": "https://github.com/anthonyfok/fonts-wqy-microhei/raw/master/wqy-microhei.ttc"
}

# 中文字型列表 (按優先順序排序)
CHINESE_FONTS = [
    "NotoSansTC-Regular.otf",    # Google Noto Sans TC (繁體中文)
    "NotoSansSC-Regular.otf",    # Google Noto Sans SC (簡體中文)
    "wqy-microhei.ttc",          # 文泉驛微米黑 (Linux)
    "wqy-zenhei.ttc",            # 文泉驛正黑 (Linux)
    "msyh.ttc",                  # 微軟雅黑 (Windows)
    "msjh.ttc",                  # 微軟正黑體 (Windows)
    "simhei.ttf",                # 黑體 (Windows)
    "simsun.ttc",                # 宋體 (Windows)
    "mingliu.ttc",               # 細明體 (Windows)
    "AppleGothic.ttf",           # Apple Gothic (macOS)
    "DroidSansFallback.ttf"      # Droid Sans Fallback (Android)
]

# ────────────────────────────
# 日誌設定 (優化版)
# ────────────────────────────
file_handler = logging.handlers.RotatingFileHandler(
    MESSAGE_LOG_PATH, mode="a", encoding="utf-8",
    maxBytes=2 * 1024 * 1024, backupCount=2
)
file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))

logger = logging.getLogger("message_listener")
logger.setLevel(logging.INFO)
if not logger.hasHandlers():
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)


# ────────────────────────────
# 錯誤處理工具 (優化版)
# ────────────────────────────
def friendly_trace(exc: BaseException, depth: int = 3) -> str:
    """生成友善的錯誤追蹤資訊"""
    return "".join(traceback.TracebackException.from_exception(exc, limit=depth).format())


def friendly_log(msg: str, exc: BaseException | None = None, level=logging.ERROR):
    """記錄友善的錯誤訊息，包含追蹤碼和詳細資訊"""
    if exc:
        msg += f"\n原因：{exc.__class__.__name__}: {exc}\n{friendly_trace(exc)}"
    logger.log(level, msg, exc_info=bool(exc))


@contextlib.contextmanager
def handle_error(ctx_or_itx: _t.Any | None, user_msg: str = "發生未知錯誤"):
    """統一的錯誤處理上下文管理器"""
    track_code = _dt.datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    try:
        yield
    except Exception as exc:
        friendly_log(user_msg, exc)
        reply = f"❌ {user_msg}。\n追蹤碼：`{track_code}`\n請將此碼提供給管理員。"
        try:
            if isinstance(ctx_or_itx, discord.Interaction):
                if ctx_or_itx.response.is_done():
                    asyncio.create_task(ctx_or_itx.followup.send(reply))
                else:
                    asyncio.create_task(ctx_or_itx.response.send_message(reply))
            elif isinstance(ctx_or_itx, commands.Context):
                asyncio.create_task(ctx_or_itx.reply(reply, mention_author=False))
        except Exception:
            pass


# ────────────────────────────
# 字型初始化 (v1.62: 增強版)
# ────────────────────────────
# 確保字型目錄存在
os.makedirs(FONT_PATH, exist_ok=True)

# v1.62: 增強字型選擇邏輯
def find_available_font(font_list, fallback=DEFAULT_FONT):
    """尋找可用的字型檔案
    
    Args:
        font_list: 字型檔案名稱列表
        fallback: 找不到時的預設字型
        
    Returns:
        str: 字型檔案路徑
    """
    # 記錄嘗試過的路徑，用於診斷
    tried_paths = []
    
    # 先檢查自定義字型目錄 (最優先)
    for font_name in font_list:
        font_path = os.path.join(FONT_PATH, font_name)
        tried_paths.append(font_path)
        
        if os.path.exists(font_path):
            logger.info(f"【訊息監聽】找到字型檔案: {font_path}")
            return font_path
            
    # 檢查系統字型目錄
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
            os.path.expanduser("~/Library/Fonts")  # macOS
        ])
        
    for font_dir in system_font_dirs:
        if os.path.exists(font_dir):
            # 遞迴搜尋字型目錄
            for root, _, files in os.walk(font_dir):
                for font_name in font_list:
                    if font_name in files:
                        font_path = os.path.join(root, font_name)
                        tried_paths.append(font_path)
                        
                        if os.path.exists(font_path):
                            logger.info(f"【訊息監聽】找到系統字型: {font_path}")
                            
                            # v1.62: 複製到專案字型目錄以便未來使用
                            try:
                                dest_path = os.path.join(FONT_PATH, font_name)
                                if not os.path.exists(dest_path):
                                    shutil.copy2(font_path, dest_path)
                                    logger.info(f"【訊息監聽】已複製字型到專案目錄: {dest_path}")
                            except Exception as e:
                                logger.warning(f"【訊息監聽】複製字型檔案失敗: {e}")
                            
                            return font_path
    
    # v1.62: 如果找不到，嘗試下載字型
    for font_name, url in FONT_DOWNLOAD_URLS.items():
        if font_name in font_list:
            try:
                font_path = os.path.join(FONT_PATH, font_name)
                if not os.path.exists(font_path):
                    logger.info(f"【訊息監聽】嘗試下載字型: {font_name}")
                    
                    # 同步下載字型檔案
                    import requests
                    response = requests.get(url, stream=True)
                    if response.status_code == 200:
                        with open(font_path, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                f.write(chunk)
                        
                        logger.info(f"【訊息監聽】成功下載字型: {font_path}")
                        return font_path
            except Exception as e:
                logger.warning(f"【訊息監聽】下載字型失敗 {font_name}: {e}")
    
    # 記錄診斷信息
    logger.warning(f"【訊息監聽】無法找到任何中文字型，嘗試過以下路徑: {tried_paths}")
    logger.warning(f"【訊息監聽】使用預設字型: {fallback}")
    
    return fallback

# v1.62: 測試字型是否支援中文
def test_font_chinese_support(font_path):
    """測試字型是否支援中文
    
    Args:
        font_path: 字型檔案路徑
        
    Returns:
        bool: 是否支援中文
    """
    try:
        font = ImageFont.truetype(font_path, 16)
        # 嘗試渲染中文字元
        test_chars = "你好世界"
        for char in test_chars:
            try:
                # 檢查字型是否有這個字元的資訊
                if hasattr(font, "getmask"):
                    font.getmask(char)
                else:
                    # PIL 8.0.0+ 使用不同的 API
                    font.getbbox(char)
            except Exception:
                return False
        return True
    except Exception as e:
        logger.warning(f"【訊息監聽】測試字型失敗 {font_path}: {e}")
        return False

# 初始化字型
try:
    # 選擇並測試字型
    username_font_path = find_available_font(CHINESE_FONTS, DEFAULT_FONT)
    text_font_path = username_font_path  # 使用相同的字型
    
    # 測試字型是否支援中文
    if username_font_path != DEFAULT_FONT:
        if test_font_chinese_support(username_font_path):
            logger.info(f"【訊息監聽】已確認字型支援中文: {username_font_path}")
        else:
            logger.warning(f"【訊息監聽】所選字型不支援中文，嘗試其他字型")
            # 嘗試其他字型
            for font_name in CHINESE_FONTS:
                font_path = os.path.join(FONT_PATH, font_name)
                if os.path.exists(font_path) and test_font_chinese_support(font_path):
                    username_font_path = font_path
                    text_font_path = font_path
                    logger.info(f"【訊息監聽】找到支援中文的替代字型: {font_path}")
                    break
    
    # 設定最終使用的字型路徑
    USERNAME_FONT = username_font_path
    TEXT_FONT = text_font_path
    
    logger.info(f"【訊息監聽】最終選擇字型: {USERNAME_FONT}")
    
except Exception as exc:
    logger.error(f"【訊息監聽】字型初始化失敗: {exc}")
    USERNAME_FONT = DEFAULT_FONT
    TEXT_FONT = DEFAULT_FONT

# ────────────────────────────
# 資料庫管理 (優化版)
# ────────────────────────────
@dataclass
class MessageRecord:
    """訊息記錄資料類別"""
    message_id: int
    channel_id: int
    guild_id: int
    author_id: int
    content: str
    timestamp: float
    attachments: Optional[str] = None


class MessageListenerDB:
    """訊息監聽資料庫管理類別
    
    負責管理訊息記錄的儲存、查詢和清理，
    使用連線池優化資料庫操作效能。
    """
    
    def __init__(self, db_path: str = MESSAGE_DB_PATH):
        self.db_path = db_path
        self._connection_pool: Dict[str, aiosqlite.Connection] = {}
        logger.info(f"【訊息監聽】資料庫初始化：{db_path}")

    async def _get_connection(self) -> aiosqlite.Connection:
        """取得資料庫連線（使用連線池）"""
        if self.db_path not in self._connection_pool:
            conn = await aiosqlite.connect(self.db_path)
            await conn.execute("PRAGMA journal_mode=WAL;")
            await conn.execute("PRAGMA synchronous=NORMAL;")
            await conn.execute("PRAGMA cache_size=10000;")
            conn.row_factory = aiosqlite.Row
            self._connection_pool[self.db_path] = conn
        return self._connection_pool[self.db_path]

    async def close(self):
        """關閉所有資料庫連線"""
        for conn in self._connection_pool.values():
            await conn.close()
        self._connection_pool.clear()
        logger.info("【訊息監聽】資料庫連線已關閉")

    async def init_db(self):
        """初始化資料庫表格結構"""
        try:
            conn = await self._get_connection()
            await conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    setting_name TEXT PRIMARY KEY,
                    setting_value TEXT
                );
                CREATE TABLE IF NOT EXISTS monitored_channels (
                    channel_id INTEGER PRIMARY KEY
                );
                CREATE TABLE IF NOT EXISTS messages (
                    message_id  INTEGER PRIMARY KEY,
                    channel_id  INTEGER NOT NULL,
                    guild_id    INTEGER NOT NULL,
                    author_id   INTEGER NOT NULL,
                    content     TEXT,
                    timestamp   REAL NOT NULL,
                    attachments TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_timestamp ON messages (timestamp);
                CREATE INDEX IF NOT EXISTS idx_channel_id ON messages (channel_id);
                CREATE INDEX IF NOT EXISTS idx_guild_id ON messages (guild_id);
                CREATE INDEX IF NOT EXISTS idx_author_id ON messages (author_id);
                """
            )
            await conn.commit()
            logger.info("【訊息監聽】資料庫表格初始化完成")
        except Exception as exc:
            friendly_log("【訊息監聽】資料庫初始化失敗", exc)
            raise

    async def execute(self, query: str, *args):
        """執行 SQL 指令（INSERT/UPDATE/DELETE）"""
        try:
            conn = await self._get_connection()
            await conn.execute(query, args)
            await conn.commit()
        except Exception as exc:
            friendly_log(f"【訊息監聽】執行 SQL 失敗：{query}", exc)
            raise

    async def select(self, query: str, params: tuple = ()) -> List[aiosqlite.Row]:
        """
        執行查詢指令（SELECT）
        Args:
            query: SQL 查詢語句
            params: 查詢參數
        Returns:
            查詢結果列表，若失敗則回傳空列表
        """
        try:
            conn = await self._get_connection()
            async with conn.execute(query, params) as cur:
                return list(await cur.fetchall())
        except Exception as exc:
            friendly_log(f"【訊息監聽】查詢失敗：{query}", exc)
            return []

    async def save_message(self, message: Optional[discord.Message]):
        """
        儲存訊息到資料庫
        Args:
            message: Discord 訊息物件，若為 None 則不處理
        """
        if not message or not hasattr(message, 'id') or not hasattr(message, 'channel'):
            logger.warning("【訊息監聽】save_message 收到無效 message 物件，已忽略")
            return
        try:
            attachments = None
            if getattr(message, 'attachments', None):
                attachments = "|".join([f"{att.filename}:{att.url}" for att in message.attachments])
            await self.execute(
                "INSERT OR REPLACE INTO messages (message_id, channel_id, guild_id, author_id, content, timestamp, attachments) VALUES (?, ?, ?, ?, ?, ?, ?)",
                getattr(message, 'id', 0),
                getattr(message.channel, 'id', 0),
                getattr(getattr(message, 'guild', None), 'id', 0) if getattr(message, 'guild', None) else 0,
                getattr(getattr(message, 'author', None), 'id', 0) if getattr(message, 'author', None) else 0,
                getattr(message, 'content', "") or "",
                getattr(message, 'created_at', dt.datetime.utcnow()).timestamp() if hasattr(message, 'created_at') else dt.datetime.utcnow().timestamp(),
                attachments
            )
        except Exception as exc:
            friendly_log(f"【訊息監聽】儲存訊息失敗：{getattr(message, 'id', '未知')}", exc)

    async def search_messages(self, keyword: Optional[str] = None, channel_id: Optional[int] = None, 
                            hours: int = 24, limit: int = 50) -> List[Dict[str, Any]]:
        """
        搜尋訊息（優化版）
        Args:
            keyword: 關鍵字
            channel_id: 頻道 ID
            hours: 幾小時內
            limit: 最大筆數
        Returns:
            查詢結果字典列表
        """
        try:
            # 構建查詢條件
            conditions = ["timestamp >= ?"]
            params: list[Any] = [float(_dt.datetime.utcnow().timestamp() - (hours * 3600))]
            if keyword:
                conditions.append("content LIKE ?")
                params.append(f"%{keyword}%")
            if channel_id:
                conditions.append("channel_id = ?")
                params.append(channel_id)
            where_clause = " AND ".join(conditions)
            query = f"""
                SELECT message_id, channel_id, guild_id, author_id, content, timestamp, attachments
                FROM messages
                WHERE {where_clause}
                ORDER BY timestamp DESC
                LIMIT ?
            """
            params.append(int(limit))
            rows = await self.select(query, tuple(params))
            return [dict(row) for row in rows]
        except Exception as exc:
            friendly_log("【訊息監聽】搜尋訊息失敗", exc)
            return []

    async def purge_old_messages(self, days: int = 7):
        """清理舊訊息（優化版）"""
        try:
            cutoff_time = _dt.datetime.utcnow().timestamp() - (days * 24 * 3600)
            await self.execute("DELETE FROM messages WHERE timestamp < ?", cutoff_time)
            logger.info(f"【訊息監聽】已清理 {days} 天前的舊訊息")
        except Exception as exc:
            friendly_log("【訊息監聽】清理舊訊息失敗", exc)


# ────────────────────────────
# 訊息緩存與圖片渲染 (v1.6新增)
# ────────────────────────────
class MessageCache:
    """訊息緩存管理器
    
    負責暫存訊息直到達到條件時渲染為圖片，
    支援按頻道分組和時間限制。
    """
    
    def __init__(self):
        self.messages: Dict[int, List[discord.Message]] = defaultdict(list)  # 頻道ID -> 訊息列表
        self.last_message_time: Dict[int, float] = {}  # 頻道ID -> 最早訊息時間戳
        
    def add_message(self, message: discord.Message) -> bool:
        """添加訊息到緩存，如果達到處理條件則回傳 True
        
        Args:
            message: Discord 訊息物件
            
        Returns:
            bool: 是否達到處理條件
        """
        global MAX_CACHED_MESSAGES  # 正確聲明全域變數
        channel_id = message.channel.id
        
        # 記錄第一條訊息的時間
        if channel_id not in self.last_message_time:
            self.last_message_time[channel_id] = time.time()
            
        # 添加訊息
        self.messages[channel_id].append(message)
        
        # 檢查是否達到處理條件
        if len(self.messages[channel_id]) >= MAX_CACHED_MESSAGES:
            return True
            
        return False
    
    def should_process(self, channel_id: int) -> bool:
        """檢查是否應該處理頻道訊息
        
        Args:
            channel_id: 頻道ID
            
        Returns:
            bool: 是否應該處理
        """
        global MAX_CACHED_MESSAGES, MAX_CACHE_TIME  # 正確聲明全域變數
        # 沒有訊息則不處理
        if channel_id not in self.messages or not self.messages[channel_id]:
            return False
            
        # 達到數量上限時處理
        if len(self.messages[channel_id]) >= MAX_CACHED_MESSAGES:
            return True
            
        # 超過時間限制時處理
        if time.time() - self.last_message_time.get(channel_id, time.time()) > MAX_CACHE_TIME:
            return True
            
        return False
    
    def get_messages(self, channel_id: int) -> List[discord.Message]:
        """取得頻道訊息並清空緩存
        
        Args:
            channel_id: 頻道ID
            
        Returns:
            List[discord.Message]: 訊息列表
        """
        messages = self.messages.get(channel_id, [])
        self.clear_channel(channel_id)
        return messages
    
    def clear_channel(self, channel_id: int):
        """清空頻道緩存
        
        Args:
            channel_id: 頻道ID
        """
        if channel_id in self.messages:
            self.messages[channel_id] = []
        if channel_id in self.last_message_time:
            del self.last_message_time[channel_id]
    
    def check_all_channels(self) -> List[int]:
        """檢查所有頻道，回傳應處理的頻道ID列表
        
        Returns:
            List[int]: 應該處理的頻道ID列表
        """
        global MAX_CACHED_MESSAGES, MAX_CACHE_TIME  # 正確聲明全域變數
        to_process = []
        for channel_id in list(self.messages.keys()):  # 使用列表複製避免修改時錯誤
            if self.should_process(channel_id):
                to_process.append(channel_id)
        return to_process


class MessageRenderer:
    """訊息渲染器
    
    將訊息列表渲染為 Discord 風格的聊天圖片，
    支援用戶頭像、名稱、訊息內容和附件顯示。
    """
    
    def __init__(self):
        # v1.62: 增強字型載入錯誤處理
        self.username_font = None
        self.text_font = None
        self.timestamp_font = None
        
        # 嘗試載入字型
        try:
            logger.info(f"【訊息監聽】嘗試載入用戶名稱字型: {USERNAME_FONT}")
            self.username_font = ImageFont.truetype(USERNAME_FONT, USERNAME_FONT_SIZE)
            
            logger.info(f"【訊息監聽】嘗試載入文本字型: {TEXT_FONT}")
            self.text_font = ImageFont.truetype(TEXT_FONT, DEFAULT_FONT_SIZE)
            
            logger.info(f"【訊息監聽】嘗試載入時間戳字型: {TEXT_FONT}")
            self.timestamp_font = ImageFont.truetype(TEXT_FONT, TIMESTAMP_FONT_SIZE)
            
            # 測試字型是否支援中文
            test_text = "測試中文"
            logger.info(f"【訊息監聽】測試字型中文支援: {test_text}")
            
            # 測試渲染中文
            if hasattr(self.text_font, "getmask"):
                self.text_font.getmask(test_text)
            else:
                # PIL 8.0.0+ 使用不同的 API
                self.text_font.getbbox(test_text)
                
            logger.info("【訊息監聽】字型載入成功，支援中文")
            
        except Exception as exc:
            friendly_log("【訊息監聽】載入字型失敗，使用預設字型", exc)
            
            # 嘗試使用系統預設字型
            try:
                logger.warning("【訊息監聽】嘗試使用系統預設字型")
                self.username_font = ImageFont.load_default()
                self.text_font = ImageFont.load_default()
                self.timestamp_font = ImageFont.load_default()
            except Exception as e:
                logger.error(f"【訊息監聽】載入預設字型也失敗: {e}")
                # 最後的備用方案 - 確保 ImageFont 正確引用
                try:
                    from PIL import ImageFont as PILImageFont
                    self.username_font = PILImageFont.load_default()
                    self.text_font = PILImageFont.load_default()
                    self.timestamp_font = PILImageFont.load_default()
                except Exception as e2:
                    logger.critical(f"【訊息監聽】無法載入任何字型，渲染可能會失敗: {e2}")
            
        # 頭像快取 (用戶ID -> 頭像圖片)
        self.avatar_cache: Dict[int, Image.Image] = {}
    
    async def get_avatar(self, user: discord.User | discord.Member) -> Image.Image:
        """取得使用者頭像圖片
        
        Args:
            user: Discord 使用者或成員物件
            
        Returns:
            Image.Image: 頭像圖片物件 (v1.61: 圓形裁剪)
        """
        # 檢查快取
        if user.id in self.avatar_cache:
            return self.avatar_cache[user.id]
            
        # 下載頭像
        try:
            async with aiohttp.ClientSession() as session:
                avatar_url = user.display_avatar.url
                async with session.get(avatar_url) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        # 載入並處理為圓形
                        avatar = Image.open(io.BytesIO(data))
                        avatar = avatar.resize((AVATAR_SIZE, AVATAR_SIZE))
                        
                        # v1.61: 裁剪頭像為圓形
                        mask = Image.new("L", (AVATAR_SIZE, AVATAR_SIZE), 0)
                        draw = ImageDraw.Draw(mask)
                        draw.ellipse((0, 0, AVATAR_SIZE, AVATAR_SIZE), fill=255)
                        
                        # 套用圓形遮罩
                        avatar = ImageOps.fit(avatar, (AVATAR_SIZE, AVATAR_SIZE))
                        avatar.putalpha(mask)
                        
                        # 創建背景與套用合成
                        final_avatar = Image.new("RGBA", (AVATAR_SIZE, AVATAR_SIZE), (0, 0, 0, 0))
                        final_avatar.paste(avatar, (0, 0), avatar)
                        
                        # 快取
                        self.avatar_cache[user.id] = final_avatar
                        return final_avatar
        except Exception as exc:
            friendly_log(f"【訊息監聽】下載頭像失敗：{user}", exc)
            
        # 失敗時使用預設圖示
        default_avatar = Image.new("RGBA", (AVATAR_SIZE, AVATAR_SIZE), (128, 128, 128, 0))
        # 創建圓形預設頭像
        mask = Image.new("L", (AVATAR_SIZE, AVATAR_SIZE), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, AVATAR_SIZE, AVATAR_SIZE), fill=255)
        default_avatar.putalpha(mask)
        return default_avatar
    
    async def download_attachment(self, attachment: discord.Attachment) -> Optional[Image.Image]:
        """下載並轉換附件為圖片
        
        Args:
            attachment: Discord 附件物件
            
        Returns:
            Optional[Image.Image]: 圖片物件，如果失敗則為 None
        """
        if not attachment.content_type or not attachment.content_type.startswith("image/"):
            return None  # 非圖片附件
            
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(attachment.url) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        img = Image.open(io.BytesIO(data))
                        
                        # 調整大小以適應聊天框寬度
                        max_width = CHAT_WIDTH - CONTENT_PADDING - MESSAGE_PADDING * 2
                        if img.width > max_width:
                            ratio = max_width / img.width
                            new_height = int(img.height * ratio)
                            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
                        return img
        except Exception as exc:
            friendly_log(f"【訊息監聽】下載附件圖片失敗：{attachment.url}", exc)
        
        return None
    
    def format_timestamp(self, timestamp: _dt.datetime) -> str:
        """格式化時間戳
        
        Args:
            timestamp: 時間戳
            
        Returns:
            str: 格式化後的時間字串
        """
        return timestamp.strftime("%Y-%m-%d %H:%M:%S")
    
    async def render_message(self, 
                            draw: ImageDraw.ImageDraw, 
                            message: discord.Message, 
                            y_pos: int,
                            show_reply: bool = True) -> Tuple[int, Image.Image, Tuple[int, int], List[Tuple[Image.Image, int]]]:
        """渲染單條訊息
        
        Args:
            draw: ImageDraw 物件
            message: 訊息物件
            y_pos: 起始 Y 座標
            show_reply: 是否顯示回覆訊息
            
        Returns:
            Tuple[int, Image.Image, Tuple[int, int], List[Tuple[Image.Image, int]]]: 
            (新的Y座標, 頭像圖片, 頭像位置, 附件圖片及位置列表)
        """
        original_y = y_pos
        attachment_images = []
        
        # 取得頭像
        avatar = await self.get_avatar(message.author)
        
        # 繪製頭像
        avatar_pos = (MESSAGE_PADDING, y_pos)
        
        # 繪製用戶名
        name_color = message.author.color.to_rgb() if hasattr(message.author, "color") and message.author.color.value else (255, 255, 255)
        draw.text((MESSAGE_PADDING + AVATAR_SIZE + 10, y_pos), 
                  message.author.display_name, 
                  font=self.username_font, 
                  fill=name_color)
        
        # v1.62: 安全計算文字寬度
        def get_text_width(text, font):
            """安全計算文字寬度，處理字型可能為 None 的情況"""
            if font is None:
                # 如果字型為 None，使用估計值
                return len(text) * 8  # 估計每個字元 8 像素寬
                
            try:
                if hasattr(font, "getlength"):
                    return font.getlength(text)
                elif hasattr(font, "getsize"):
                    return font.getsize(text)[0]
                else:
                    # PIL 8.0.0+ 使用不同的 API
                    bbox = font.getbbox(text)
                    if bbox:
                        return bbox[2] - bbox[0]
                    return len(text) * 8
            except Exception:
                # 發生錯誤時使用估計值
                return len(text) * 8
        
        # 繪製時間戳
        timestamp = self.format_timestamp(message.created_at)
        name_width = get_text_width(message.author.display_name, self.username_font)
        draw.text((MESSAGE_PADDING + AVATAR_SIZE + 15 + name_width, y_pos + 2), 
                  timestamp, 
                  font=self.timestamp_font, 
                  fill=(160, 160, 160))
        
        y_pos += 25  # 用戶名高度
        
        # 處理回覆訊息
        if show_reply and message.reference and isinstance(message.reference.resolved, discord.Message):
            reply_to = message.reference.resolved
            reply_text = f"回覆 @{reply_to.author.display_name}: {reply_to.content[:50]}{'...' if len(reply_to.content) > 50 else ''}"
            
            # 繪製回覆引用
            draw.rectangle(
                [(MESSAGE_PADDING + AVATAR_SIZE + 10, y_pos), 
                 (MESSAGE_PADDING + AVATAR_SIZE + 14, y_pos + 20)], 
                fill=(114, 137, 218)
            )
            
            # 繪製回覆文字
            draw.text((MESSAGE_PADDING + AVATAR_SIZE + 20, y_pos), 
                      reply_text, 
                      font=self.timestamp_font, 
                      fill=(170, 170, 180))
                      
            y_pos += 25  # 回覆高度
        
        # 處理訊息內容
        if message.content:
            # 內文換行處理
            lines = []
            max_width = CHAT_WIDTH - CONTENT_PADDING - MESSAGE_PADDING * 2
            for line in message.content.split("\n"):
                if get_text_width(line, self.text_font) <= max_width:
                    lines.append(line)
                else:
                    wrapped = textwrap.wrap(
                        line, 
                        width=int(max_width / (DEFAULT_FONT_SIZE * 0.5)),  # 估計寬度
                        replace_whitespace=False, 
                        break_long_words=True
                    )
                    lines.extend(wrapped)
            
            # 繪製文字
            for i, line in enumerate(lines):
                draw.text((MESSAGE_PADDING + AVATAR_SIZE + 10, y_pos), 
                          line, 
                          font=self.text_font, 
                          fill=TEXT_COLOR)
                y_pos += DEFAULT_FONT_SIZE + 4  # 行高
            
            y_pos += 5  # 內容底部間隔
        
        # 處理附件
        for attachment in message.attachments:
            # 圖片附件直接顯示
            if attachment.content_type and attachment.content_type.startswith("image/"):
                img = await self.download_attachment(attachment)
                if img:
                    attachment_images.append((img, y_pos))
                    y_pos += img.height + 5
            else:
                # 非圖片附件顯示連結
                attachment_text = f"📎 {attachment.filename} ({attachment.url})"
                draw.text((MESSAGE_PADDING + AVATAR_SIZE + 10, y_pos), 
                          attachment_text, 
                          font=self.text_font, 
                          fill=(114, 137, 218))  # 連結顏色
                y_pos += DEFAULT_FONT_SIZE + 4
        
        # 處理貼圖
        for sticker in message.stickers:
            sticker_text = f"🔖 {sticker.name}"
            draw.text((MESSAGE_PADDING + AVATAR_SIZE + 10, y_pos), 
                      sticker_text, 
                      font=self.text_font, 
                      fill=TEXT_COLOR)
            y_pos += DEFAULT_FONT_SIZE + 4
        
        return y_pos, avatar, avatar_pos, attachment_images
    
    async def render_messages(self, messages: List[discord.Message]) -> Optional[str]:
        """渲染多條訊息為圖片
        
        Args:
            messages: 訊息列表
            
        Returns:
            Optional[str]: 臨時文件路徑，如失敗則為 None
        """
        if not messages:
            return None
            
        try:
            # 第一次掃描計算高度
            height = 0
            for _ in messages:
                height += 100  # 估計每條訊息至少 100px 高
            
            height = min(height, MAX_HEIGHT)  # 限制最大高度
            
            # 創建畫布
            image = Image.new("RGB", (CHAT_WIDTH, height), BG_COLOR)
            draw = ImageDraw.Draw(image)
            
            # 繪製訊息
            y_pos = MESSAGE_PADDING
            attachment_data = []
            
            for message in messages:
                new_y, avatar, avatar_pos, attachments = await self.render_message(draw, message, y_pos)
                
                # 保存附件資料
                attachment_data.append((avatar, avatar_pos))
                for img, pos in attachments:
                    attachment_data.append((img, (MESSAGE_PADDING + AVATAR_SIZE + 10, pos)))
                
                y_pos = new_y + MESSAGE_PADDING
                
                # 檢查是否需要調整畫布大小
                if y_pos > height - 100:
                    new_height = min(y_pos + 200, MAX_HEIGHT)  # 增加空間但不超過最大高度
                    new_image = Image.new("RGB", (CHAT_WIDTH, new_height), BG_COLOR)
                    new_image.paste(image, (0, 0))
                    image = new_image
                    draw = ImageDraw.Draw(image)
                    height = new_height
            
            # 貼上頭像和附件圖片
            for img, pos in attachment_data:
                image.paste(img, pos)
            
            # 如果內容少於最小高度，調整圖片大小
            if y_pos < height:
                image = image.crop((0, 0, CHAT_WIDTH, y_pos))
            
            # 保存為臨時文件
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            image.save(temp_file.name)
            return temp_file.name
            
        except Exception as exc:
            friendly_log("【訊息監聽】渲染訊息圖片失敗", exc)
            return None


# ────────────────────────────
# Webhook 與表情處理 (優化版)
# ────────────────────────────
_emoji_re = re.compile(r"<(a?):([A-Za-z0-9_~]+):(\d+)>")

def sanitize_external_emoji(text: str, guild: Optional[discord.Guild]) -> str:
    """智能處理外服表情
    
    如果表情在目標伺服器中可用 → 保留原樣
    否則 → 退化為 :name: 格式
    
    Args:
        text: 包含表情的訊息文字
        guild: 目標伺服器
        
    Returns:
        處理後的文字
    """
    def repl(m: re.Match[str]) -> str:
        emoji_id = int(m.group(3))
        # 檢查表情是否在目標伺服器中存在
        if guild and guild.get_emoji(emoji_id):
            return m.group(0)  # 保留原表情
        else:
            return f":{m.group(2)}:"  # 退化為文字格式
    
    return _emoji_re.sub(repl, text)


# ────────────────────────────
# 主要 Cog 類別 (圖片渲染版)
# ────────────────────────────
class MessageListenerCog(commands.Cog):
    """訊息監聽與日誌管理 Cog
    
    提供完整的訊息監控、記錄、搜尋和轉播功能，
    支援多頻道監聽和智能表情處理。
    """
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = MessageListenerDB()
        self._settings_cache: Dict[str, str] = {}
        self._last_refresh = 0
        self.monitored_channels: List[int] = []  # 監聽頻道快取
        
        # 新增訊息緩存和圖片渲染系統
        self.message_cache = MessageCache()
        self.renderer = MessageRenderer()
        
        logger.info("【訊息監聽】MessageListenerCog 初始化完成")

    async def cog_load(self):
        """Cog 載入時的初始化"""
        try:
            await self.db.init_db()
            await self.refresh_settings()
            await self.refresh_monitored_channels()  # 初始化監聽頻道快取
            self.purge_task.start()  # 啟動清理任務
            self.check_cache_task.start()  # 啟動緩存檢查任務
            logger.info("【訊息監聽】Cog 載入完成")
        except Exception as exc:
            friendly_log("【訊息監聽】Cog 載入失敗", exc)
            raise

    async def cog_unload(self):
        """Cog 卸載時的清理"""
        try:
            self.purge_task.cancel()  # 停止清理任務
            self.check_cache_task.cancel()  # 停止緩存檢查任務
            await self.db.close()
            logger.info("【訊息監聽】Cog 卸載完成")
        except Exception as exc:
            friendly_log("【訊息監聽】Cog 卸載失敗", exc)

    async def refresh_settings(self):
        """重新整理設定（含快取機制）"""
        try:
            # 避免頻繁重新整理
            current_time = _dt.datetime.utcnow().timestamp()
            if current_time - self._last_refresh < 60:  # 1分鐘內不重複整理
                return
                
            rows = await self.db.select("SELECT setting_name, setting_value FROM settings")
            self._settings_cache = {row['setting_name']: row['setting_value'] for row in rows}
            self._last_refresh = current_time
            logger.debug("【訊息監聽】設定快取已更新")
        except Exception as exc:
            friendly_log("【訊息監聽】重新整理設定失敗", exc)

    async def refresh_monitored_channels(self):
        """重新整理監聽頻道快取"""
        try:
            rows = await self.db.select("SELECT channel_id FROM monitored_channels")
            self.monitored_channels = [row['channel_id'] for row in rows]
            logger.debug(f"【訊息監聽】監聽頻道快取已更新：{len(self.monitored_channels)} 個頻道")
        except Exception as exc:
            friendly_log("【訊息監聽】重新整理監聽頻道失敗", exc)

    async def get_setting(self, key: str, default: str = "") -> str:
        """取得設定值（使用快取）"""
        await self.refresh_settings()
        return self._settings_cache.get(key, default)

    async def set_setting(self, key: str, value: str):
        """設定值"""
        try:
            await self.db.execute("INSERT OR REPLACE INTO settings (setting_name, setting_value) VALUES (?, ?)", key, value)
            self._settings_cache[key] = value
        except Exception as exc:
            friendly_log(f"【訊息監聽】設定值失敗：{key}", exc)

    async def save_message(self, message: discord.Message):
        """儲存訊息到資料庫"""
        try:
            await self.db.save_message(message)
        except Exception as exc:
            friendly_log(f"【訊息監聽】儲存訊息失敗：{message.id}", exc)

    @tasks.loop(time=dt.time(hour=0, minute=0))
    async def purge_task(self):
        """每日清理舊訊息任務"""
        try:
            retention_days = int(await self.get_setting("retention_days", "7"))
            await self.db.purge_old_messages(retention_days)
        except Exception as exc:
            friendly_log("【訊息監聽】清理任務失敗", exc)

    @tasks.loop(seconds=30)
    async def check_cache_task(self):
        """定期檢查緩存，處理超時訊息"""
        global MAX_CACHED_MESSAGES, MAX_CACHE_TIME  # 正確聲明全域變數
        try:
            # 檢查所有需要處理的頻道
            for channel_id in self.message_cache.check_all_channels():
                await self.process_channel_messages(channel_id)
        except Exception as exc:
            friendly_log("【訊息監聽】檢查訊息緩存失敗", exc)

    async def process_channel_messages(self, channel_id: int):
        """處理頻道緩存的訊息，渲染並發送圖片
        
        Args:
            channel_id: 頻道ID
        """
        global MAX_CACHED_MESSAGES  # 正確聲明全域變數
        try:
            # 取得緩存的訊息
            messages = self.message_cache.get_messages(channel_id)
            if not messages:
                return
                
            # 取得日誌頻道
            guild = self.bot.get_guild(messages[0].guild.id) if messages[0].guild else None
            log_channel = await self._get_log_channel(guild)
            if not log_channel:
                logger.warning(f"【訊息監聽】找不到日誌頻道，無法處理頻道 {channel_id} 的訊息")
                return
                
            # 渲染圖片
            image_path = await self.renderer.render_messages(messages)
            if not image_path:
                logger.error(f"【訊息監聽】渲染頻道 {channel_id} 的訊息失敗")
                return
                
            try:
                # 取得來源頻道資訊
                source_channel = self.bot.get_channel(channel_id)
                channel_name = f"#{source_channel.name}" if isinstance(source_channel, discord.TextChannel) else f"頻道 {channel_id}"
                
                # 發送圖片
                await log_channel.send(
                    f"📢 **{len(messages)} 條來自 {channel_name} 的訊息**",
                    file=discord.File(image_path)
                )
                
                logger.info(f"【訊息監聽】已渲染並發送頻道 {channel_id} 的 {len(messages)} 條訊息")
            finally:
                # 清理臨時檔案
                try:
                    os.unlink(image_path)
                except Exception:
                    pass
                
        except Exception as exc:
            friendly_log(f"【訊息監聽】處理頻道 {channel_id} 的訊息失敗", exc)
            # 發生錯誤時清空緩存，避免重複處理
            self.message_cache.clear_channel(channel_id)

    # ───────── Slash 指令 ─────────
    @app_commands.command(name="訊息日誌設定", description="設定訊息日誌功能")
    async def cmd_setting(self, interaction: discord.Interaction):
        """訊息日誌設定指令"""
        if not is_allowed(interaction, "訊息日誌設定"):
            await interaction.response.send_message("❌ 你沒有權限執行本指令。")
            return
            
        with handle_error(interaction, "載入設定失敗"):
            # 確保快取是最新的
            await self.refresh_settings()
            await self.refresh_monitored_channels()
            
            embed = self._build_settings_embed()
            view = MessageListenerCog.SettingsView(self)
            await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="搜尋訊息", description="查詢最近訊息（支援關鍵字、頻道篩選和截圖搜尋）")
    @app_commands.describe(
        keyword="關鍵字（可空）", 
        channel="限制搜尋的頻道（可空）",
        hours="搜尋時間範圍（小時，預設24）",
        render_image="是否渲染為截圖（預設為否）"
    )
    async def cmd_search(
        self,
        interaction: discord.Interaction,
        keyword: Optional[str] = None,
        channel: Optional[discord.TextChannel] = None,
        hours: int = 24,
        render_image: bool = False,
    ):
        """搜尋訊息指令（v1.61: 增加截圖搜尋和權限優化）"""
        # v1.61: 改進權限檢查 - 允許在日誌頻道中使用或有指定權限
        log_channel_id = await self.get_setting("log_channel_id", "")
        is_in_log_channel = log_channel_id and str(interaction.channel_id) == log_channel_id
        has_permission = is_allowed(interaction, "搜尋訊息")
        
        if not (has_permission or is_in_log_channel):
            await interaction.response.send_message("❌ 你沒有權限執行本指令。必須在日誌頻道中使用或擁有搜尋權限。")
            return
            
        with handle_error(interaction, "搜尋訊息失敗"):
            await interaction.response.defer()
            
            # 執行搜尋
            results = await self.db.search_messages(
                keyword=keyword,
                channel_id=channel.id if channel else None,
                hours=hours,
                limit=100
            )
            
            if not results:
                await interaction.followup.send("🔍 沒有找到符合條件的訊息。")
                return
            
            # v1.61: 處理截圖渲染請求
            if render_image and results:
                await interaction.followup.send("🖼️ 正在渲染搜尋結果截圖...")
                
                try:
                    # v1.61: 自定義模擬訊息類別
                    class MockMessage:
                        def __init__(self, id, content, author, channel, guild, created_at):
                            self.id = id
                            self.content = content
                            self.author = author
                            self.channel = channel
                            self.guild = guild
                            self.created_at = created_at
                            self.attachments = []
                            self.stickers = []
                            self.reference = None
                    
                    # 最多渲染前5條訊息
                    messages_to_render = []
                    count = 0
                    
                    # 取得原始訊息物件
                    for result in results[:5]:
                        try:
                            # 嘗試在快取中找到訊息
                            channel_id = result['channel_id']
                            message_id = result['message_id']
                            channel_obj = self.bot.get_channel(channel_id)
                            
                            if channel_obj and isinstance(channel_obj, discord.TextChannel):
                                try:
                                    # 嘗試從 Discord API 獲取訊息
                                    message = await channel_obj.fetch_message(message_id)
                                    messages_to_render.append(message)
                                    count += 1
                                except (discord.NotFound, discord.Forbidden):
                                    # 如果無法獲取訊息，創建模擬訊息
                                    try:
                                        mock_author = await self.bot.fetch_user(result['author_id'])
                                    except:
                                        # 如果無法獲取用戶，創建模擬用戶
                                        class MockUser:
                                            def __init__(self, id):
                                                self.id = id
                                                self.display_name = f"未知用戶 ({id})"
                                                self.bot = False
                                                # 修復 Asset 創建
                                                class MockAsset:
                                                    def __init__(self):
                                                        self.url = ""
                                                        
                                                self.display_avatar = MockAsset()
                                                self.color = discord.Color.default()
                                        
                                        mock_author = MockUser(result['author_id'])
                                    
                                    # 創建模擬訊息
                                    mock_message = MockMessage(
                                        id=message_id,
                                        content=result['content'],
                                        author=mock_author,
                                        channel=channel_obj,
                                        guild=channel_obj.guild,
                                        created_at=dt.datetime.fromtimestamp(result['timestamp'])
                                    )
                                    
                                    # 添加到渲染列表
                                    messages_to_render.append(mock_message)
                                    count += 1
                        except Exception as e:
                            logger.warning(f"無法處理訊息 {result.get('message_id', '未知')}: {e}")
                    
                    if messages_to_render:
                        # 渲染圖片
                        image_path = await self.renderer.render_messages(messages_to_render)
                        
                        if image_path:
                            search_info = f"關鍵字：{keyword}" if keyword else ""
                            channel_info = f"頻道：{channel.mention}" if channel else ""
                            time_info = f"時間範圍：{hours}小時內"
                            
                            info_text = " | ".join(filter(None, [search_info, channel_info, time_info]))
                            await interaction.followup.send(
                                f"🔍 **搜尋結果截圖** ({count}/{len(results)})\n{info_text}",
                                file=discord.File(image_path)
                            )
                            os.unlink(image_path)
                            
                            # 如果結果超過渲染的數量，提供完整分頁視圖
                            if len(results) > count:
                                await interaction.followup.send("🔄 以上僅顯示前幾條結果的截圖，完整搜尋結果如下：")
                    else:
                        await interaction.followup.send("⚠️ 無法渲染訊息截圖，可能是訊息已被刪除或無權限讀取。")
                        
                except Exception as e:
                    logger.error(f"渲染搜尋結果失敗: {e}")
                    await interaction.followup.send("⚠️ 渲染訊息截圖失敗，將顯示文字結果。")
            
            # 建立分頁視圖
            view = MessageListenerCog.SearchPaginationView(self, results, interaction.user.id)
            await interaction.followup.send(
                embed=view.build_page_embed(),
                view=view,
            )

    # ───────── 工具方法 ─────────
    def _build_settings_embed(self) -> discord.Embed:
        """建構設定面板 Embed"""
        embed = discord.Embed(
            title="📝 訊息日誌設定",
            description="設定訊息監控和日誌功能",
            color=discord.Color.blue()
        )
        
        # 取得當前設定
        log_channel_id = self._settings_cache.get("log_channel_id", "未設定")
        log_edits = self._settings_cache.get("log_edits", "false")
        log_deletes = self._settings_cache.get("log_deletes", "false")
        batch_size = self._settings_cache.get("batch_size", str(MAX_CACHED_MESSAGES))
        batch_time = self._settings_cache.get("batch_time", str(MAX_CACHE_TIME))
        
        embed.add_field(
            name="📺 日誌頻道",
            value=f"<#{log_channel_id}>" if log_channel_id != "未設定" else "❌ 未設定",
            inline=False
        )
        embed.add_field(
            name="✏️ 記錄編輯",
            value="✅ 啟用" if log_edits == "true" else "❌ 停用",
            inline=True
        )
        embed.add_field(
            name="🗑️ 記錄刪除",
            value="✅ 啟用" if log_deletes == "true" else "❌ 停用",
            inline=True
        )
        embed.add_field(
            name="📡 監聽頻道",
            value=f"目前監聽 {len(self.monitored_channels)} 個頻道",
            inline=False
        )
        embed.add_field(
            name="🖼️ 圖片設定",
            value=f"每批 {batch_size} 條訊息或 {int(int(batch_time) / 60)} 分鐘",
            inline=True
        )
        
        return embed

    async def _get_log_channel(self, guild: Optional[discord.Guild]) -> Optional[discord.TextChannel]:
        """取得日誌頻道"""
        try:
            if not guild:
                return None
            channel_id = await self.get_setting("log_channel_id")
            if channel_id:
                channel = guild.get_channel(int(channel_id))
                if isinstance(channel, discord.TextChannel):
                    return channel
        except Exception as exc:
            friendly_log("【訊息監聽】取得日誌頻道失敗", exc)
        return None

    # ───────── 事件監聽器 ─────────
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """訊息事件監聽器"""
        try:
            # 忽略機器人訊息
            if message.author.bot:
                return
                
            # 檢查是否為監聽頻道（使用快取）
            if message.channel.id not in self.monitored_channels:
                return
            
            # 儲存訊息到資料庫
            await self.save_message(message)
            
            # 將訊息添加到緩存
            if self.message_cache.add_message(message):
                # 若達到條件，則立即處理該頻道訊息
                await self.process_channel_messages(message.channel.id)
                
        except Exception as exc:
            friendly_log("【訊息監聽】處理訊息事件失敗", exc)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """訊息編輯事件監聽器"""
        try:
            if before.author.bot or not await self.get_setting("log_edits", "false") == "true":
                return
                
            # 儲存更新後的訊息
            await self.save_message(after)
            
            # 訊息編輯直接單獨處理
            guild = after.guild
            log_channel = await self._get_log_channel(guild)
            if log_channel:
                # 建立編輯訊息說明
                channel_info = ""
                if isinstance(after.channel, (discord.DMChannel, discord.GroupChannel)):
                    channel_info = "(私人訊息)"
                else:
                    channel_info = f"(來自 {after.channel.mention})"
                    
                edit_note = f"📝 **訊息已編輯** {channel_info}"
                
                # 渲染單條訊息
                messages = [after]
                image_path = await self.renderer.render_messages(messages)
                
                if image_path:
                    try:
                        await log_channel.send(
                            f"{edit_note}\n**作者:** {after.author.mention}",
                            file=discord.File(image_path)
                        )
                    finally:
                        try:
                            os.unlink(image_path)
                        except Exception:
                            pass
                
        except Exception as exc:
            friendly_log("【訊息監聽】處理訊息編輯事件失敗", exc)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """訊息刪除事件監聽器"""
        try:
            if message.author.bot or not await self.get_setting("log_deletes", "false") == "true":
                return
                
            guild = message.guild
            log_channel = await self._get_log_channel(guild)
            if log_channel:
                # 建立刪除訊息說明
                channel_info = ""
                if isinstance(message.channel, (discord.DMChannel, discord.GroupChannel)):
                    channel_info = "(私人訊息)"
                else:
                    channel_info = f"(來自 {message.channel.mention})"
                    
                delete_note = f"🗑️ **訊息已刪除** {channel_info}"
                
                # 渲染單條訊息
                messages = [message]
                image_path = await self.renderer.render_messages(messages)
                
                if image_path:
                    try:
                        await log_channel.send(
                            f"{delete_note}\n**作者:** {message.author.mention}",
                            file=discord.File(image_path)
                        )
                    finally:
                        try:
                            os.unlink(image_path)
                        except Exception:
                            pass
                
        except Exception as exc:
            friendly_log("【訊息監聽】處理訊息刪除事件失敗", exc)

    # ────────────────────────────
    # UI 組件 (圖片渲染版)
    # ────────────────────────────
    class SettingsView(View):
        """設定面板視圖"""
        
        def __init__(self, cog: "MessageListenerCog"):
            super().__init__(timeout=300)
            self.cog = cog
            
            # 新增所有 UI 元件
            self.add_item(MessageListenerCog._LogChannelSelect(cog))
            self.add_item(MessageListenerCog._AddMonitoredSelect(cog))
            self.remove_select = MessageListenerCog._RemoveMonitoredSelect(cog)
            self.add_item(self.remove_select)
            self.add_item(MessageListenerCog._ToggleEdits(cog))
            self.add_item(MessageListenerCog._ToggleDeletes(cog))
            
            # 新增圖片設定按鈕
            self.add_item(MessageListenerCog._AdjustBatchSize(cog))
            self.add_item(MessageListenerCog._AdjustBatchTime(cog))
            
            # v1.61: 添加幫助按鈕
            self.add_item(MessageListenerCog._HelpButton())

        async def on_timeout(self):
            """視圖超時處理"""
            logger.debug("【訊息監聽】設定面板超時")

        async def refresh(self, interaction: Optional[discord.Interaction] = None):
            """重新整理設定面板"""
            try:
                await self.cog.refresh_settings()
                await self.cog.refresh_monitored_channels()
                embed = self.cog._build_settings_embed()
                
                # 重新整理移除選單
                self.remove_select.refresh_options()
                
                if interaction:
                    await interaction.response.edit_message(embed=embed, view=self)
            except Exception as exc:
                friendly_log("【訊息監聽】重新整理設定面板失敗", exc)
    
    # v1.61: 添加幫助按鈕
    class _HelpButton(Button):
        """幫助按鈕"""
        
        def __init__(self):
            super().__init__(label="❓ 使用幫助", style=discord.ButtonStyle.success)
            
        async def callback(self, interaction: discord.Interaction):
            # 創建並發送幫助嵌入消息
            embed = discord.Embed(
                title="📝 訊息日誌系統使用幫助",
                description="詳細功能說明與操作指南",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="📺 日誌頻道設定",
                value=(
                    "選擇接收訊息日誌的頻道，所有監聽到的訊息將以圖片形式發送到此頻道。\n"
                    "➡️ 使用「選擇日誌頻道」下拉選單進行設定"
                ),
                inline=False
            )
            
            embed.add_field(
                name="📡 監聽頻道管理",
                value=(
                    "選擇要監聽哪些頻道的訊息。\n"
                    "➡️ 使用「新增監聽頻道」添加\n"
                    "➡️ 使用「移除監聽頻道」刪除"
                ),
                inline=False
            )
            
            embed.add_field(
                name="✏️ 編輯與刪除監控",
                value=(
                    "設定是否要記錄訊息的編輯和刪除事件。\n"
                    "➡️ 使用「記錄編輯」和「記錄刪除」按鈕切換"
                ),
                inline=False
            )
            
            embed.add_field(
                name="⚙️ 批次處理設定",
                value=(
                    "調整訊息批次處理的參數：\n"
                    "➡️ 批次大小：累積多少條訊息才一起處理 (1-50條)\n"
                    "➡️ 批次時間：最長等待多久就處理一次 (1-60分鐘)"
                ),
                inline=False
            )
            
            embed.add_field(
                name="🔍 搜尋訊息功能",
                value=(
                    "使用 `/搜尋訊息` 指令可以查詢歷史訊息：\n"
                    "➡️ 支援關鍵字搜尋\n"
                    "➡️ 可按頻道過濾\n"
                    "➡️ 可設定時間範圍\n"
                    "➡️ 可生成搜尋結果截圖"
                ),
                inline=False
            )
            
            embed.add_field(
                name="🆕 v1.61 新功能",
                value=(
                    "✅ 支援中文名稱顯示\n"
                    "✅ 圓形頭像顯示\n"
                    "✅ 擴展搜尋權限\n"
                    "✅ 搜尋結果截圖\n"
                    "✅ 自定義批次設定\n"
                    "✅ 功能教學說明"
                ),
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)

    class _AdjustBatchSize(Button):
        """調整批次大小按鈕"""
        
        def __init__(self, cog: "MessageListenerCog"):
            super().__init__(label="⚙️ 調整批次大小", style=discord.ButtonStyle.secondary)
            self.cog = cog

        async def callback(self, interaction: discord.Interaction):
            """按鈕回調"""
            # v1.61: 使用模態框實現自定義輸入
            modal = MessageListenerCog._BatchSizeModal(self.cog)
            await interaction.response.send_modal(modal)
        
    # v1.61: 添加批次大小模態框類別
    class _BatchSizeModal(Modal):
        def __init__(self, cog: "MessageListenerCog"):
            super().__init__(title="設定批次大小")
            self.cog = cog
            
            # 獲取當前值
            self.current_value = int(cog._settings_cache.get("batch_size", str(MAX_CACHED_MESSAGES)))
            
            # 創建輸入欄位
            self.batch_size = TextInput(
                label="每批訊息數量 (範圍: 1-50)",
                placeholder=f"目前: {self.current_value} 條訊息",
                default=str(self.current_value),
                required=True,
                min_length=1,
                max_length=2
            )
            
            # 添加到視圖
            self.add_item(self.batch_size)
            
        async def on_submit(self, interaction: discord.Interaction):
            global MAX_CACHED_MESSAGES  # 正確宣告全域變數
            
            try:
                # 解析輸入值
                new_value = int(self.batch_size.value)
                
                # 檢查範圍
                if new_value < 1:
                    new_value = 1
                elif new_value > 50:
                    new_value = 50
                
                # 儲存新設定
                await self.cog.set_setting("batch_size", str(new_value))
                
                # 更新全域變數
                MAX_CACHED_MESSAGES = new_value
                
                await interaction.response.send_message(
                    f"✅ 批次大小已設定為 **{new_value}** 條訊息",
                    ephemeral=True
                )
                
            except ValueError:
                await interaction.response.send_message(
                    "❌ 輸入無效，請輸入 1-50 之間的數字",
                    ephemeral=True
                )

    class _AdjustBatchTime(Button):
        """調整批次時間按鈕"""
        
        def __init__(self, cog: "MessageListenerCog"):
            super().__init__(label="⏱️ 調整批次時間", style=discord.ButtonStyle.secondary)
            self.cog = cog

        async def callback(self, interaction: discord.Interaction):
            """按鈕回調"""
            # v1.61: 使用模態框實現自定義輸入
            modal = MessageListenerCog._BatchTimeModal(self.cog)
            await interaction.response.send_modal(modal)
        
    # v1.61: 添加批次時間模態框類別
    class _BatchTimeModal(Modal):
        def __init__(self, cog: "MessageListenerCog"):
            super().__init__(title="設定批次時間")
            self.cog = cog
            
            # 獲取當前值 (秒轉分鐘)
            current_seconds = int(cog._settings_cache.get("batch_time", str(MAX_CACHE_TIME)))
            self.current_value = current_seconds // 60
            
            # 創建輸入欄位
            self.batch_time = TextInput(
                label="訊息處理時間間隔 (分鐘, 範圍: 1-60)",
                placeholder=f"目前: {self.current_value} 分鐘",
                default=str(self.current_value),
                required=True,
                min_length=1,
                max_length=2
            )
            
            # 添加到視圖
            self.add_item(self.batch_time)
            
        async def on_submit(self, interaction: discord.Interaction):
            global MAX_CACHE_TIME  # 正確宣告全域變數
            
            try:
                # 解析輸入值 (分鐘)
                new_value_min = int(self.batch_time.value)
                
                # 檢查範圍
                if new_value_min < 1:
                    new_value_min = 1
                elif new_value_min > 60:
                    new_value_min = 60
                
                # 轉換為秒並儲存
                new_value_sec = new_value_min * 60
                await self.cog.set_setting("batch_time", str(new_value_sec))
                
                # 更新全域變數
                MAX_CACHE_TIME = new_value_sec
                
                await interaction.response.send_message(
                    f"✅ 批次時間已設定為 **{new_value_min}** 分鐘",
                    ephemeral=True
                )
                
            except ValueError:
                await interaction.response.send_message(
                    "❌ 輸入無效，請輸入 1-60 之間的數字",
                    ephemeral=True
                )

    class _PageButton(Button):
        """分頁按鈕"""
        def __init__(self, parent_view: "MessageListenerCog.SearchPaginationView", delta: int, label: str):
            super().__init__(label=label, style=discord.ButtonStyle.primary)
            self.parent_view = parent_view
            self.delta = delta

        async def callback(self, interaction: discord.Interaction):
            if not hasattr(self, 'parent_view') or not hasattr(self.parent_view, 'current_page'):
                await interaction.response.send_message("❌ 分頁狀態異常，請重新查詢。")
                return
            self.parent_view.current_page += self.delta
            await self.parent_view.update(interaction)

    class SearchPaginationView(View):
        """搜尋結果分頁視圖"""
        def __init__(self, cog: "MessageListenerCog", results: List[dict], owner_id: int):
            super().__init__(timeout=300)
            self.cog = cog
            self.results = results
            self.owner_id = owner_id
            self.current_page = 0
            self.items_per_page = 20  # 恢復為 20 筆
            self._update_buttons()

        def build_page_embed(self) -> discord.Embed:
            """建構當前頁面的 Embed（恢復豐富顯示）"""
            start_idx = self.current_page * self.items_per_page
            end_idx = start_idx + self.items_per_page
            page_results = self.results[start_idx:end_idx]
            
            embed = discord.Embed(
                title="🔍 訊息搜尋結果",
                description=f"找到 {len(self.results)} 條訊息",
                color=discord.Color.green()
            )
            
            for result in page_results:
                timestamp = _dt.datetime.fromtimestamp(result['timestamp'])
                content = result['content'][:200] + "..." if len(result['content']) > 200 else result['content']
                
                # 頻道 mention 處理
                channel_mention = f"<#{result['channel_id']}>" if result.get('channel_id') else "未知頻道"
                
                # 建立訊息連結
                message_link = f"https://discord.com/channels/{result.get('guild_id', 0)}/{result['channel_id']}/{result['message_id']}"
                
                # 相對時間顯示
                time_ago = _dt.datetime.utcnow() - timestamp
                if time_ago.days > 0:
                    time_str = f"{time_ago.days}天前"
                elif time_ago.seconds > 3600:
                    time_str = f"{time_ago.seconds // 3600}小時前"
                elif time_ago.seconds > 60:
                    time_str = f"{time_ago.seconds // 60}分鐘前"
                else:
                    time_str = "剛剛"
                
                embed.add_field(
                    name=f"📝 {channel_mention} - {time_str}",
                    value=f"**<@{result.get('author_id', '未知用戶')}>**: {content}\n[查看訊息]({message_link})",
                    inline=False
                )
            
            embed.set_footer(text=f"第 {self.current_page + 1} 頁，共 {(len(self.results) - 1) // self.items_per_page + 1} 頁")
            return embed

        async def update(self, interaction: discord.Interaction):
            embed = self.build_page_embed()
            self._update_buttons()
            await interaction.response.edit_message(embed=embed, view=self)

        def _update_buttons(self):
            """更新按鈕狀態"""
            total_pages = (len(self.results) - 1) // self.items_per_page + 1
            # 先移除舊按鈕
            self.clear_items()
            # 新增上一頁按鈕
            self.add_item(MessageListenerCog._PageButton(self, -1, "⬅️ 上一頁"))
            # 新增下一頁按鈕
            self.add_item(MessageListenerCog._PageButton(self, 1, "下一頁 ➡️"))
            # 根據頁數啟用/停用
            for child in self.children:
                if isinstance(child, MessageListenerCog._PageButton):
                    if child.delta == -1:
                        child.disabled = self.current_page == 0
                    elif child.delta == 1:
                        child.disabled = self.current_page >= total_pages - 1

        async def interaction_check(self, interaction: discord.Interaction) -> bool:
            """檢查互動權限"""
            if interaction.user.id != self.owner_id:
                await interaction.response.send_message("❌ 只有搜尋者可以使用此面板。")
                return False
            return True

        async def on_timeout(self):
            """視圖超時處理"""
            logger.debug("【訊息監聽】搜尋分頁視圖超時")

    class _LogChannelSelect(ChannelSelect):
        """日誌頻道選擇器"""
        
        def __init__(self, cog: "MessageListenerCog"):
            super().__init__(
                placeholder="📺 選擇日誌頻道",
                channel_types=[discord.ChannelType.text]
            )
            self.cog = cog

        async def callback(self, interaction: discord.Interaction):
            """選擇回調"""
            try:
                channel = self.values[0]
                await self.cog.set_setting("log_channel_id", str(channel.id))
                await self.cog.refresh_settings()
                await interaction.response.send_message(f"✅ 日誌頻道已設定為 {channel.mention}")
            except Exception as exc:
                friendly_log("【訊息監聽】設定日誌頻道失敗", exc)
                await interaction.response.send_message("❌ 設定失敗，請稍後再試。")

    class _AddMonitoredSelect(ChannelSelect):
        """新增監聽頻道選擇器"""
        
        def __init__(self, cog: "MessageListenerCog"):
            super().__init__(
                placeholder="➕ 選擇要監聽的頻道",
                channel_types=[discord.ChannelType.text]
            )
            self.cog = cog

        async def callback(self, interaction: discord.Interaction):
            """選擇回調"""
            try:
                for channel in self.values:
                    await self.cog.db.execute(
                        "INSERT OR IGNORE INTO monitored_channels (channel_id) VALUES (?)",
                        channel.id
                    )
                
                # 重新整理快取
                await self.cog.refresh_monitored_channels()
                
                await interaction.response.send_message(
                    f"✅ 已新增 {len(self.values)} 個監聽頻道"
                )
            except Exception as exc:
                friendly_log("【訊息監聽】新增監聽頻道失敗", exc)
                await interaction.response.send_message("❌ 新增失敗，請稍後再試。")

    class _RemoveMonitoredSelect(Select):
        """移除監聽頻道選擇器（修復版）"""
        
        def __init__(self, cog: "MessageListenerCog"):
            self.cog = cog
            super().__init__(
                placeholder="❌ 移除監聽頻道 (可複選)",
                options=self._build_options(),
                min_values=0,
                max_values=min(25, len(cog.monitored_channels) or 1),
            )

        def _build_options(self):
            """建構選項（同步方式）"""
            if not self.cog.monitored_channels:
                return [discord.SelectOption(label="（目前無監聽頻道）", value="none", default=True)]
            
            opts = []
            for cid in self.cog.monitored_channels[:25]:
                ch = self.cog.bot.get_channel(cid)
                label = f"#{ch.name}" if isinstance(ch, discord.TextChannel) else str(cid)
                opts.append(discord.SelectOption(label=label, value=str(cid)))
            return opts

        def refresh_options(self):
            """重新整理選項"""
            self.options = self._build_options()
            self.max_values = max(1, len(self.options))

        async def callback(self, interaction: discord.Interaction):
            """選擇回調"""
            try:
                if "none" in self.values:
                    await interaction.response.send_message("✅ 沒有需要移除的頻道")
                    return
                
                removed_count = 0
                for option in self.values:
                    channel_id = int(option)
                    await self.cog.db.execute(
                        "DELETE FROM monitored_channels WHERE channel_id = ?",
                        channel_id
                    )
                    removed_count += 1
                
                # 重新整理快取
                await self.cog.refresh_monitored_channels()
                
                await interaction.response.send_message(
                    f"✅ 已移除 {removed_count} 個監聽頻道"
                )
            except Exception as exc:
                friendly_log("【訊息監聽】移除監聽頻道失敗", exc)
                await interaction.response.send_message("❌ 移除失敗，請稍後再試。")

    class _ToggleEdits(Button):
        """切換編輯記錄按鈕"""
        
        def __init__(self, cog: "MessageListenerCog"):
            super().__init__(label="✏️ 切換編輯記錄", style=discord.ButtonStyle.secondary)
            self.cog = cog

        async def callback(self, interaction: discord.Interaction):
            """按鈕回調"""
            try:
                current = await self.cog.get_setting("log_edits", "false")
                new_value = "true" if current == "false" else "false"
                await self.cog.set_setting("log_edits", new_value)
                await interaction.response.send_message(
                    f"✅ 編輯記錄已{'啟用' if new_value == 'true' else '停用'}"
                )
            except Exception as exc:
                friendly_log("【訊息監聽】切換編輯記錄失敗", exc)
                await interaction.response.send_message("❌ 切換失敗，請稍後再試。")

    class _ToggleDeletes(Button):
        """切換刪除記錄按鈕"""
        
        def __init__(self, cog: "MessageListenerCog"):
            super().__init__(label="🗑️ 切換刪除記錄", style=discord.ButtonStyle.secondary)
            self.cog = cog

        async def callback(self, interaction: discord.Interaction):
            """按鈕回調"""
            try:
                current = await self.cog.get_setting("log_deletes", "false")
                new_value = "true" if current == "false" else "false"
                await self.cog.set_setting("log_deletes", new_value)
                await interaction.response.send_message(
                    f"✅ 刪除記錄已{'啟用' if new_value == 'true' else '停用'}"
                )
            except Exception as exc:
                friendly_log("【訊息監聽】切換刪除記錄失敗", exc)
                await interaction.response.send_message("❌ 切換失敗，請稍後再試。")


# ────────────────────────────
# 模組載入
# ────────────────────────────
async def setup(bot: commands.Bot):
    """載入 MessageListenerCog 到機器人"""
    await bot.add_cog(MessageListenerCog(bot))
    logger.info("【訊息監聽】MessageListenerCog 已載入到機器人")