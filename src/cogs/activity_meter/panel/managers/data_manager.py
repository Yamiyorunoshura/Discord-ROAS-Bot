"""
活躍度面板數據管理器
- 處理數據庫操作和緩存
- 提供統一的數據處理流程
- 實現智能緩存機制
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Any

from ...config import config
from ...database.database import ActivityDatabase

logger = logging.getLogger("activity_meter")


class DataManager:
    """
    數據管理器

    功能:
    - 處理數據庫操作和緩存
    - 提供統一的數據處理流程
    - 實現智能緩存機制
    """

    def __init__(self):
        """初始化數據管理器"""
        self.cache = {}
        self.cache_timeout = 300  # 5分鐘緩存超時
        self.db = ActivityDatabase()

    async def get_rankings(
        self, guild_id: int, time_range: str = "daily"
    ) -> list[dict]:
        """
        獲取排行榜數據

        Args:
            guild_id: 伺服器 ID
            time_range: 時間範圍 ("daily", "weekly", "monthly")

        Returns:
            List[Dict]: 排行榜數據
        """
        cache_key = f"rankings_{guild_id}_{time_range}"

        # 檢查緩存
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if time.time() - timestamp < self.cache_timeout:
                return cached_data

        # 從數據庫獲取數據
        data = await self.fetch_rankings_from_db(guild_id, time_range)

        # 更新緩存
        self.cache[cache_key] = (data, time.time())

        return data

    async def fetch_rankings_from_db(
        self, guild_id: int, time_range: str
    ) -> list[dict]:
        """
        從數據庫獲取排行榜數據

        Args:
            guild_id: 伺服器 ID
            time_range: 時間範圍

        Returns:
            List[Dict]: 排行榜數據
        """
        try:
            now = datetime.now(config.TW_TZ)

            if time_range == "daily":
                ymd = now.strftime(config.DAY_FMT)
                return await self.db.get_daily_rankings(ymd, guild_id, limit=10)
            elif time_range == "weekly":
                # 計算本週的開始日期
                week_start = now - timedelta(days=now.weekday())
                week_ymd = week_start.strftime(config.DAY_FMT)
                return await self.db.get_daily_rankings(week_ymd, guild_id, limit=10)
            elif time_range == "monthly":
                ym = now.strftime(config.MONTH_FMT)
                return await self.db.get_monthly_stats(ym, guild_id)
            else:
                logger.warning(f"未知的時間範圍: {time_range}")
                return []

        except Exception as e:
            logger.error(f"獲取排行榜數據失敗: {e}")
            return []

    async def get_settings(self, guild_id: int) -> dict[str, Any]:
        """
        獲取伺服器設定

        Args:
            guild_id: 伺服器 ID

        Returns:
            Dict[str, Any]: 設定數據
        """
        cache_key = f"settings_{guild_id}"

        # 檢查緩存
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if time.time() - timestamp < self.cache_timeout:
                return cached_data

        # 從數據庫獲取設定
        try:
            report_channels = await self.db.get_report_channels()
            channel_id = next(
                (ch_id for g_id, ch_id in report_channels if g_id == guild_id), None
            )

            settings = {
                "activity_gain": config.ACTIVITY_GAIN,
                "report_hour": config.ACT_REPORT_HOUR,
                "system_enabled": True,
                "channel_id": channel_id,
            }

            # 更新緩存
            self.cache[cache_key] = (settings, time.time())

            return settings

        except Exception as e:
            logger.error(f"獲取設定失敗: {e}")
            return {
                "activity_gain": config.ACTIVITY_GAIN,
                "report_hour": config.ACT_REPORT_HOUR,
                "system_enabled": True,
                "channel_id": None,
            }

    async def get_stats(self, guild_id: int) -> dict[str, Any]:
        """
        獲取統計數據

        Args:
            guild_id: 伺服器 ID

        Returns:
            Dict[str, Any]: 統計數據
        """
        cache_key = f"stats_{guild_id}"

        # 檢查緩存
        if cache_key in self.cache:
            cached_data, timestamp = self.cache[cache_key]
            if time.time() - timestamp < self.cache_timeout:
                return cached_data

        # 從數據庫獲取統計
        try:
            now = datetime.now(config.TW_TZ)
            today_ymd = now.strftime(config.DAY_FMT)
            yesterday_ymd = (now - timedelta(days=1)).strftime(config.DAY_FMT)
            current_month = now.strftime(config.MONTH_FMT)

            # 獲取各種統計數據
            today_rankings = await self.db.get_daily_rankings(
                today_ymd, guild_id, limit=5
            )
            yesterday_rankings = await self.db.get_daily_rankings(
                yesterday_ymd, guild_id, limit=5
            )
            monthly_stats = await self.db.get_monthly_stats(current_month, guild_id)

            stats = {
                "today_rankings": today_rankings,
                "yesterday_rankings": yesterday_rankings,
                "monthly_stats": monthly_stats,
                "total_messages": sum(monthly_stats.values()),
                "active_users": len(monthly_stats),
                "date": today_ymd,
            }

            # 更新緩存
            self.cache[cache_key] = (stats, time.time())

            return stats

        except Exception as e:
            logger.error(f"獲取統計數據失敗: {e}")
            return {
                "today_rankings": [],
                "yesterday_rankings": [],
                "monthly_stats": {},
                "total_messages": 0,
                "active_users": 0,
                "date": datetime.now(config.TW_TZ).strftime(config.DAY_FMT),
            }

    async def update_settings(self, guild_id: int, settings: dict[str, Any]) -> bool:
        """
        更新伺服器設定

        Args:
            guild_id: 伺服器 ID
            settings: 新設定

        Returns:
            bool: 是否更新成功
        """
        try:
            # 更新數據庫
            if "channel_id" in settings:
                await self.db.set_report_channel(guild_id, settings["channel_id"])

            # 清除相關緩存
            self.clear_cache(f"settings_{guild_id}")

            logger.info(f"設定已更新: {guild_id}")
            return True

        except Exception as e:
            logger.error(f"更新設定失敗: {e}")
            return False

    def clear_cache(self, pattern: str | None = None):
        """
        清除緩存

        Args:
            pattern: 緩存模式,如果為 None 則清除所有緩存
        """
        if pattern is None:
            self.cache.clear()
        else:
            keys_to_remove = [key for key in self.cache if pattern in key]
            for key in keys_to_remove:
                del self.cache[key]

        logger.info(f"緩存已清除: {pattern or 'all'}")

    def get_cache_info(self) -> dict[str, Any]:
        """
        獲取緩存信息

        Returns:
            Dict[str, Any]: 緩存信息
        """
        return {
            "cache_size": len(self.cache),
            "cache_keys": list(self.cache.keys()),
            "cache_timeout": self.cache_timeout,
        }
