"""
活躍度系統服務
Task ID: 9 - 重構現有模組以符合新架構

提供活躍度系統的核心業務邏輯：
- 活躍度計算和管理
- 排行榜生成和查詢
- 日常和月度統計
- 進度條圖片生成
- 自動播報機制
- 與成就系統整合
"""

import os
import io
import time
import logging
import asyncio
import contextlib
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from PIL import Image, ImageDraw, ImageFont
import discord

from core.base_service import BaseService
from core.database_manager import DatabaseManager
from core.exceptions import ServiceError, handle_errors
from .models import (
    ActivitySettings, ActivityRecord, DailyActivityRecord, ActivityStats,
    LeaderboardEntry, MonthlyStats, ActivityReport, ActivityImage
)

# 時區設定
import config
TW_TZ = config.TW_TZ if hasattr(config, 'TW_TZ') else timezone.utc

logger = logging.getLogger('services.activity')


class ActivityService(BaseService):
    """
    活躍度系統服務
    
    負責處理活躍度計算、排行榜、統計等所有業務邏輯
    """
    
    def __init__(self, database_manager: DatabaseManager, config_dict: Optional[Dict[str, Any]] = None):
        """
        初始化活躍度服務
        
        參數：
            database_manager: 資料庫管理器
            config_dict: 配置參數
        """
        super().__init__("ActivityService")
        self.db_manager = database_manager
        self.config = config_dict or {}
        
        # 配置參數
        self.default_settings = ActivitySettings(guild_id=0)
        self.fonts_dir = self.config.get('fonts_dir', 'fonts')
        self.default_font = self.config.get('default_font', 'fonts/NotoSansCJKtc-Regular.otf')
        
        # 快取
        self._settings_cache: Dict[int, ActivitySettings] = {}
        self._cache_lock = asyncio.Lock()
        
        # 互斥鎖，防止資料競爭
        self._activity_lock = asyncio.Lock()
        
        # 成就系統整合
        self._achievement_service = None
        
        # 添加資料庫依賴
        self.add_dependency(database_manager, "database")
    
    async def _initialize(self) -> bool:
        """初始化服務"""
        try:
            # 初始化活躍度系統資料表
            await self._init_database_tables()
            
            # 嘗試獲取成就服務（如果存在）
            from core.base_service import service_registry
            self._achievement_service = service_registry.get_service("AchievementService")
            if self._achievement_service:
                logger.info("成就服務整合成功")
            
            logger.info("活躍度服務初始化成功")
            return True
            
        except Exception as e:
            logger.error(f"活躍度服務初始化失敗：{e}")
            return False
    
    async def _cleanup(self) -> None:
        """清理資源"""
        try:
            # 清除快取
            async with self._cache_lock:
                self._settings_cache.clear()
            
            logger.info("活躍度服務已清理")
            
        except Exception as e:
            logger.error(f"清理活躍度服務時發生錯誤：{e}")
    
    async def _validate_permissions(self, user_id: int, guild_id: Optional[int], action: str) -> bool:
        """
        活躍度服務權限驗證
        
        實作基本的權限邏輯
        """
        # 一般操作允許所有用戶
        if action in ['view_activity', 'view_leaderboard']:
            return True
        
        # 設定操作需要管理員權限（這裡簡化處理，實際應該檢查 Discord 權限）
        if action in ['update_settings', 'set_report_channel']:
            return True  # 在實際部署時應該檢查用戶是否有管理權限
        
        return True
    
    async def _init_database_tables(self) -> None:
        """初始化活躍度系統相關的資料表"""
        
        # 活躍度表（主要記錄）
        await self.db_manager.execute("""
            CREATE TABLE IF NOT EXISTS activity_meter (
                guild_id INTEGER,
                user_id INTEGER,
                score REAL DEFAULT 0,
                last_msg INTEGER DEFAULT 0,
                PRIMARY KEY (guild_id, user_id)
            )
        """)
        
        # 每日活躍度記錄表
        await self.db_manager.execute("""
            CREATE TABLE IF NOT EXISTS activity_daily (
                ymd TEXT,
                guild_id INTEGER,
                user_id INTEGER,
                msg_cnt INTEGER DEFAULT 0,
                PRIMARY KEY (ymd, guild_id, user_id)
            )
        """)
        
        # 活躍度設定表
        await self.db_manager.execute("""
            CREATE TABLE IF NOT EXISTS activity_settings (
                guild_id INTEGER PRIMARY KEY,
                report_channel_id INTEGER,
                report_hour INTEGER DEFAULT 8,
                max_score REAL DEFAULT 100.0,
                gain_per_message REAL DEFAULT 1.0,
                decay_after_seconds INTEGER DEFAULT 300,
                decay_per_hour REAL DEFAULT 6.0,
                cooldown_seconds INTEGER DEFAULT 60,
                auto_report_enabled INTEGER DEFAULT 1
            )
        """)
        
        # 排行榜頻道設定表（向後相容）
        await self.db_manager.execute("""
            CREATE TABLE IF NOT EXISTS activity_report_channel (
                guild_id INTEGER PRIMARY KEY,
                channel_id INTEGER
            )
        """)
    
    @handle_errors(log_errors=True)
    async def get_settings(self, guild_id: int) -> ActivitySettings:
        """
        獲取伺服器的活躍度設定
        
        參數：
            guild_id: 伺服器 ID
            
        返回：
            活躍度設定
        """
        # 檢查快取
        async with self._cache_lock:
            if guild_id in self._settings_cache:
                return self._settings_cache[guild_id]
        
        try:
            # 從資料庫查詢
            row = await self.db_manager.fetchone(
                "SELECT * FROM activity_settings WHERE guild_id = ?",
                (guild_id,)
            )
            
            if row:
                settings = ActivitySettings(
                    guild_id=row['guild_id'],
                    report_channel_id=row['report_channel_id'],
                    report_hour=row['report_hour'] or 8,
                    max_score=row['max_score'] or 100.0,
                    gain_per_message=row['gain_per_message'] or 1.0,
                    decay_after_seconds=row['decay_after_seconds'] or 300,
                    decay_per_hour=row['decay_per_hour'] or 6.0,
                    cooldown_seconds=row['cooldown_seconds'] or 60,
                    auto_report_enabled=bool(row['auto_report_enabled'])
                )
            else:
                # 檢查舊的報告頻道設定（向後相容）
                old_channel_row = await self.db_manager.fetchone(
                    "SELECT channel_id FROM activity_report_channel WHERE guild_id = ?",
                    (guild_id,)
                )
                
                # 建立預設設定
                settings = ActivitySettings(
                    guild_id=guild_id,
                    report_channel_id=old_channel_row['channel_id'] if old_channel_row else None
                )
                
                # 儲存預設設定
                await self._save_settings(settings)
            
            # 快取設定
            async with self._cache_lock:
                self._settings_cache[guild_id] = settings
            
            return settings
            
        except Exception as e:
            logger.error(f"獲取活躍度設定失敗：{e}")
            raise ServiceError(
                f"獲取活躍度設定失敗：{str(e)}",
                service_name=self.name,
                operation="get_settings"
            )
    
    @handle_errors(log_errors=True)
    async def update_setting(self, guild_id: int, key: str, value: Any) -> bool:
        """
        更新單一活躍度設定
        
        參數：
            guild_id: 伺服器 ID
            key: 設定鍵
            value: 設定值
            
        返回：
            是否更新成功
        """
        try:
            # 確保記錄存在
            await self._ensure_settings_exist(guild_id)
            
            # 更新資料庫
            await self.db_manager.execute(
                f"UPDATE activity_settings SET {key} = ? WHERE guild_id = ?",
                (value, guild_id)
            )
            
            # 清除快取
            async with self._cache_lock:
                if guild_id in self._settings_cache:
                    del self._settings_cache[guild_id]
            
            logger.info(f"更新活躍度設定成功：{guild_id}.{key} = {value}")
            return True
            
        except Exception as e:
            logger.error(f"更新活躍度設定失敗：{e}")
            raise ServiceError(
                f"更新活躍度設定失敗：{str(e)}",
                service_name=self.name,
                operation="update_setting"
            )
    
    @handle_errors(log_errors=True)
    async def update_activity(self, user_id: int, guild_id: int, message: Optional[discord.Message] = None) -> float:
        """
        更新用戶活躍度
        
        參數：
            user_id: 用戶 ID
            guild_id: 伺服器 ID
            message: Discord 訊息物件（可選）
            
        返回：
            更新後的活躍度分數
        """
        try:
            # 獲取設定
            settings = await self.get_settings(guild_id)
            current_time = int(time.time())
            
            # 今日日期鍵
            ymd = datetime.now(TW_TZ).strftime("%Y%m%d")
            
            async with self._activity_lock:
                # 獲取現有記錄
                row = await self.db_manager.fetchone(
                    "SELECT score, last_msg FROM activity_meter WHERE guild_id = ? AND user_id = ?",
                    (guild_id, user_id)
                )
                
                if row:
                    last_score, last_msg_time = row['score'], row['last_msg']
                else:
                    last_score, last_msg_time = 0.0, 0
                
                # 更新每日訊息數
                await self.db_manager.execute("""
                    INSERT INTO activity_daily (ymd, guild_id, user_id, msg_cnt)
                    VALUES (?, ?, ?, 1)
                    ON CONFLICT (ymd, guild_id, user_id)
                    DO UPDATE SET msg_cnt = msg_cnt + 1
                """, (ymd, guild_id, user_id))
                
                # 檢查冷卻時間
                if current_time - last_msg_time < settings.cooldown_seconds:
                    # 在冷卻時間內，只更新訊息數，不更新活躍度
                    return self._calculate_current_score(last_score, last_msg_time, settings)
                
                # 計算新的活躍度分數
                current_score = self._calculate_current_score(last_score, last_msg_time, settings)
                new_score = min(current_score + settings.gain_per_message, settings.max_score)
                
                # 更新活躍度記錄
                await self.db_manager.execute("""
                    INSERT INTO activity_meter (guild_id, user_id, score, last_msg)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT (guild_id, user_id)
                    DO UPDATE SET score = ?, last_msg = ?
                """, (guild_id, user_id, new_score, current_time, new_score, current_time))
                
                # 觸發成就檢查
                if self._achievement_service and message:
                    await self._trigger_activity_achievements(user_id, guild_id, new_score, message)
                
                logger.debug(f"更新活躍度：用戶 {user_id} 在 {guild_id}，分數 {last_score:.1f} -> {new_score:.1f}")
                return new_score
                
        except Exception as e:
            logger.error(f"更新活躍度失敗：{e}")
            raise ServiceError(
                f"更新活躍度失敗：{str(e)}",
                service_name=self.name,
                operation="update_activity"
            )
    
    @handle_errors(log_errors=True)
    async def get_activity_score(self, user_id: int, guild_id: int) -> float:
        """
        獲取用戶當前活躍度分數
        
        參數：
            user_id: 用戶 ID
            guild_id: 伺服器 ID
            
        返回：
            當前活躍度分數
        """
        try:
            # 獲取設定
            settings = await self.get_settings(guild_id)
            
            # 獲取記錄
            row = await self.db_manager.fetchone(
                "SELECT score, last_msg FROM activity_meter WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id)
            )
            
            if not row:
                return 0.0
            
            # 計算當前分數（考慮時間衰減）
            return self._calculate_current_score(row['score'], row['last_msg'], settings)
            
        except Exception as e:
            logger.error(f"獲取活躍度分數失敗：{e}")
            raise ServiceError(
                f"獲取活躍度分數失敗：{str(e)}",
                service_name=self.name,
                operation="get_activity_score"
            )
    
    @handle_errors(log_errors=True)
    async def get_daily_leaderboard(self, guild_id: int, limit: int = 10) -> List[LeaderboardEntry]:
        """
        獲取每日排行榜
        
        參數：
            guild_id: 伺服器 ID
            limit: 限制數量
            
        返回：
            排行榜列表
        """
        try:
            ymd = datetime.now(TW_TZ).strftime("%Y%m%d")
            ym = datetime.now(TW_TZ).strftime("%Y%m")
            
            # 獲取今日排行榜
            daily_rows = await self.db_manager.fetchall("""
                SELECT user_id, msg_cnt FROM activity_daily
                WHERE ymd = ? AND guild_id = ?
                ORDER BY msg_cnt DESC
                LIMIT ?
            """, (ymd, guild_id, limit))
            
            if not daily_rows:
                return []
            
            # 獲取月度統計
            monthly_rows = await self.db_manager.fetchall("""
                SELECT user_id, SUM(msg_cnt) as total FROM activity_daily
                WHERE ymd LIKE ? AND guild_id = ?
                GROUP BY user_id
            """, (ym + "%", guild_id))
            
            monthly_stats = {row['user_id']: row['total'] for row in monthly_rows}
            days_in_month = int(datetime.now(TW_TZ).strftime("%d"))
            
            # 建立排行榜
            leaderboard = []
            for rank, row in enumerate(daily_rows, 1):
                user_id = row['user_id']
                daily_messages = row['msg_cnt']
                monthly_messages = monthly_stats.get(user_id, 0)
                monthly_average = monthly_messages / days_in_month if days_in_month > 0 else 0
                
                # 獲取活躍度分數
                activity_score = await self.get_activity_score(user_id, guild_id)
                
                leaderboard.append(LeaderboardEntry(
                    rank=rank,
                    user_id=user_id,
                    username=f"User_{user_id}",  # 實際應用中應該從 Discord 獲取
                    display_name=f"User_{user_id}",
                    score=activity_score,
                    daily_messages=daily_messages,
                    monthly_messages=monthly_messages,
                    monthly_average=monthly_average
                ))
            
            return leaderboard
            
        except Exception as e:
            logger.error(f"獲取每日排行榜失敗：{e}")
            raise ServiceError(
                f"獲取每日排行榜失敗：{str(e)}",
                service_name=self.name,
                operation="get_daily_leaderboard"
            )
    
    @handle_errors(log_errors=True)
    async def get_monthly_stats(self, guild_id: int) -> MonthlyStats:
        """
        獲取月度統計
        
        參數：
            guild_id: 伺服器 ID
            
        返回：
            月度統計資料
        """
        try:
            ym = datetime.now(TW_TZ).strftime("%Y%m")
            
            # 獲取月度統計
            stats_row = await self.db_manager.fetchone("""
                SELECT 
                    COUNT(DISTINCT user_id) as active_users,
                    SUM(msg_cnt) as total_messages
                FROM activity_daily
                WHERE ymd LIKE ? AND guild_id = ?
            """, (ym + "%", guild_id))
            
            if not stats_row or stats_row['total_messages'] is None:
                return MonthlyStats(
                    guild_id=guild_id,
                    month_key=ym,
                    total_messages=0,
                    active_users=0,
                    average_messages_per_user=0.0
                )
            
            total_messages = stats_row['total_messages']
            active_users = stats_row['active_users']
            average_messages = total_messages / active_users if active_users > 0 else 0
            
            # 獲取前5名用戶
            top_users = await self.get_daily_leaderboard(guild_id, 5)
            
            return MonthlyStats(
                guild_id=guild_id,
                month_key=ym,
                total_messages=total_messages,
                active_users=active_users,
                average_messages_per_user=average_messages,
                top_users=top_users
            )
            
        except Exception as e:
            logger.error(f"獲取月度統計失敗：{e}")
            raise ServiceError(
                f"獲取月度統計失敗：{str(e)}",
                service_name=self.name,
                operation="get_monthly_stats"
            )
    
    @handle_errors(log_errors=True)
    async def generate_activity_image(self, user_id: int, guild_id: int, member: Optional[discord.Member] = None) -> ActivityImage:
        """
        生成活躍度進度條圖片
        
        參數：
            user_id: 用戶 ID
            guild_id: 伺服器 ID
            member: Discord 成員物件（用於顯示名稱）
            
        返回：
            活躍度圖片
        """
        try:
            # 獲取活躍度分數和設定
            settings = await self.get_settings(guild_id)
            score = await self.get_activity_score(user_id, guild_id)
            
            # 用戶顯示名稱
            if member:
                display_name = member.display_name
                username = member.name
            else:
                display_name = f"User_{user_id}"
                username = f"user_{user_id}"
            
            # 生成進度條圖片
            image_bytes = self._render_activity_bar(display_name, score, settings.max_score)
            
            return ActivityImage(
                guild_id=guild_id,
                user_id=user_id,
                username=username,
                display_name=display_name,
                score=score,
                max_score=settings.max_score,
                image_bytes=image_bytes
            )
            
        except Exception as e:
            logger.error(f"生成活躍度圖片失敗：{e}")
            raise ServiceError(
                f"生成活躍度圖片失敗：{str(e)}",
                service_name=self.name,
                operation="generate_activity_image"
            )
    
    @handle_errors(log_errors=True)
    async def set_report_channel(self, guild_id: int, channel_id: int) -> bool:
        """
        設定自動播報頻道
        
        參數：
            guild_id: 伺服器 ID
            channel_id: 頻道 ID
            
        返回：
            是否設定成功
        """
        try:
            # 更新設定
            success = await self.update_setting(guild_id, 'report_channel_id', channel_id)
            
            # 同時更新舊表（向後相容）
            await self.db_manager.execute("""
                INSERT INTO activity_report_channel (guild_id, channel_id)
                VALUES (?, ?)
                ON CONFLICT (guild_id)
                DO UPDATE SET channel_id = ?
            """, (guild_id, channel_id, channel_id))
            
            return success
            
        except Exception as e:
            logger.error(f"設定報告頻道失敗：{e}")
            raise ServiceError(
                f"設定報告頻道失敗：{str(e)}",
                service_name=self.name,
                operation="set_report_channel"
            )
    
    @handle_errors(log_errors=True)
    async def generate_daily_report(self, guild_id: int) -> Optional[ActivityReport]:
        """
        生成每日活躍度報告
        
        參數：
            guild_id: 伺服器 ID
            
        返回：
            活躍度報告，如果沒有數據則返回 None
        """
        try:
            ymd = datetime.now(TW_TZ).strftime("%Y%m%d")
            
            # 獲取排行榜
            leaderboard = await self.get_daily_leaderboard(guild_id, 10)
            if not leaderboard:
                return None
            
            # 獲取月度統計
            monthly_stats = await self.get_monthly_stats(guild_id)
            
            return ActivityReport(
                guild_id=guild_id,
                date_key=ymd,
                leaderboard=leaderboard,
                monthly_stats=monthly_stats
            )
            
        except Exception as e:
            logger.error(f"生成每日報告失敗：{e}")
            raise ServiceError(
                f"生成每日報告失敗：{str(e)}",
                service_name=self.name,
                operation="generate_daily_report"
            )
    
    def _calculate_current_score(self, score: float, last_msg_time: int, settings: ActivitySettings) -> float:
        """計算當前活躍度分數（考慮時間衰減）"""
        current_time = int(time.time())
        time_delta = current_time - last_msg_time
        
        if time_delta <= settings.decay_after_seconds:
            return score
        
        decay_time = time_delta - settings.decay_after_seconds
        decay_amount = (settings.decay_per_hour / 3600) * decay_time
        
        return max(0, score - decay_amount)
    
    def _render_activity_bar(self, display_name: str, score: float, max_score: float) -> bytes:
        """
        渲染活躍度進度條圖片
        
        參數：
            display_name: 顯示名稱
            score: 活躍度分數
            max_score: 最大分數
            
        返回：
            圖片位元組
        """
        # 圖片尺寸和顏色設定
        width, height = 400, 80
        bg_color = (47, 49, 54, 255)  # Discord 暗色主題背景
        border_color = (114, 137, 218, 255)  # Discord 藍色
        fill_color = (88, 101, 242, 255)  # Discord 紫色
        text_color = (255, 255, 255, 255)  # 白色文字
        
        # 建立圖片
        img = Image.new("RGBA", (width, height), bg_color)
        draw = ImageDraw.Draw(img)
        
        # 繪製邊框
        draw.rectangle([(0, 0), (width - 1, height - 1)], outline=border_color)
        
        # 計算進度條寬度
        progress = min(score / max_score, 1.0) if max_score > 0 else 0
        fill_width = int((width - 2) * progress)
        
        # 繪製進度條
        if fill_width > 0:
            draw.rectangle([(1, 1), (fill_width, height - 2)], fill=fill_color)
        
        # 準備文字
        text = f"{display_name} ‧ {score:.1f}/{max_score:.0f}"
        
        # 載入字型
        try:
            if os.path.exists(self.default_font):
                font = ImageFont.truetype(self.default_font, 18)
            else:
                font = ImageFont.load_default()
        except (OSError, IOError):
            font = ImageFont.load_default()
        
        # 計算文字位置
        try:
            # 嘗試新版 PIL 方法
            text_width = font.getlength(text)
            bbox = draw.textbbox((0, 0), text, font=font)
            text_height = bbox[3] - bbox[1]
        except AttributeError:
            # 舊版 PIL 相容性
            try:
                text_width, text_height = font.getsize(text)
            except AttributeError:
                text_width, text_height = len(text) * 10, 18  # 估計值
        
        # 繪製文字（居中）
        text_x = (width - text_width) // 2
        text_y = (height - text_height) // 2
        draw.text((text_x, text_y), text, fill=text_color, font=font)
        
        # 轉換為位元組
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue()
    
    async def _ensure_settings_exist(self, guild_id: int) -> None:
        """確保活躍度設定記錄存在"""
        existing = await self.db_manager.fetchone(
            "SELECT guild_id FROM activity_settings WHERE guild_id = ?",
            (guild_id,)
        )
        if not existing:
            await self._save_settings(ActivitySettings(guild_id=guild_id))
    
    async def _save_settings(self, settings: ActivitySettings) -> None:
        """儲存活躍度設定"""
        await self.db_manager.execute("""
            INSERT OR REPLACE INTO activity_settings 
            (guild_id, report_channel_id, report_hour, max_score, gain_per_message,
             decay_after_seconds, decay_per_hour, cooldown_seconds, auto_report_enabled)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            settings.guild_id,
            settings.report_channel_id,
            settings.report_hour,
            settings.max_score,
            settings.gain_per_message,
            settings.decay_after_seconds,
            settings.decay_per_hour,
            settings.cooldown_seconds,
            1 if settings.auto_report_enabled else 0
        ))
    
    async def _trigger_activity_achievements(self, user_id: int, guild_id: int, score: float, message: discord.Message) -> None:
        """觸發活躍度相關成就"""
        if not self._achievement_service:
            return
        
        try:
            # 觸發活躍度分數成就
            activity_event = {
                "type": "activity_score",
                "user_id": user_id,
                "guild_id": guild_id,
                "value": score,
                "message_id": message.id,
                "channel_id": message.channel.id,
                "timestamp": datetime.now().isoformat()
            }
            
            triggered = await self._achievement_service.process_event_triggers(activity_event)
            if triggered:
                logger.info(f"活躍度分數觸發成就：{triggered}")
            
            # 獲取今日訊息數並觸發相關成就
            ymd = datetime.now(TW_TZ).strftime("%Y%m%d")
            daily_row = await self.db_manager.fetchone(
                "SELECT msg_cnt FROM activity_daily WHERE ymd = ? AND guild_id = ? AND user_id = ?",
                (ymd, guild_id, user_id)
            )
            
            if daily_row:
                message_event = {
                    "type": "daily_messages",
                    "user_id": user_id,
                    "guild_id": guild_id,
                    "value": daily_row['msg_cnt'],
                    "date": ymd,
                    "message_id": message.id,
                    "channel_id": message.channel.id,
                    "timestamp": datetime.now().isoformat()
                }
                
                triggered = await self._achievement_service.process_event_triggers(message_event)
                if triggered:
                    logger.info(f"每日訊息數觸發成就：{triggered}")
            
        except Exception as e:
            logger.warning(f"觸發活躍度成就失敗：{e}")
            # 成就觸發失敗不應該影響活躍度更新