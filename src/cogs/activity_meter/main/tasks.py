"""
活躍度系統背景任務
- 處理定期排行榜更新和播報
"""

import asyncio
import logging
from datetime import datetime
from typing import Any

import discord
from discord.ext import tasks

from ..config import config
from ..database.database import ActivityDatabase
from ..service.batch_service import BatchCalculationService

logger = logging.getLogger("activity_meter")

class ActivityTasks:
    """
    活躍度系統背景任務處理類別

    功能:
    - 定期排行榜更新
    - 自動播報排行榜
    - 排行榜嵌入生成
    """

    def __init__(self, bot: discord.Client, db: ActivityDatabase):
        """
        初始化背景任務處理器

        Args:
            bot: Discord 機器人實例
            db: 活躍度資料庫實例
        """
        self.bot = bot
        self.db = db
        self.auto_report_task = None

        # 初始化批量計算服務
        self.batch_service = BatchCalculationService(db)

    def start(self):
        """啟動所有背景任務"""
        self.auto_report_task = self.auto_report.start()

    def stop(self):
        """停止所有背景任務"""
        if self.auto_report_task and self.auto_report.is_running():
            self.auto_report.cancel()

        # 關閉批量計算服務
        shutdown_task = asyncio.create_task(self.batch_service.shutdown())
        # 確保異常不會被忽略
        shutdown_task.add_done_callback(lambda t: t.exception())

    @tasks.loop(minutes=1)
    async def auto_report(self):
        """
        自動播報排行榜任務 - 使用批量計算優化
        每日在指定時間自動發送排行榜到設定的頻道
        """
        try:
            # 檢查是否為指定播報時間
            now = datetime.now(config.TW_TZ)
            if now.hour != config.ACT_REPORT_HOUR or now.minute != 0:
                return

            # 獲取日期字串
            ymd = now.strftime(config.DAY_FMT)
            ym = now.strftime(config.MONTH_FMT)
            days = int(now.strftime("%d"))

            # 獲取所有設定了播報頻道的伺服器
            report_channels = await self.db.get_report_channels()

            # 批量處理所有伺服器的背景衰減計算
            for guild_id, channel_id in report_channels:
                # 執行批量衰減計算以確保排行榜數據準確
                await self.batch_service.bulk_decay_all_users(guild_id)

                # 更新排行榜計算
                await self.batch_service.bulk_update_rankings(guild_id, ymd)

                # 處理排行榜播報
                await self._process_guild_report(guild_id, channel_id, ymd, ym, days)

            # 執行背景計算優化檢查
            await self.batch_service.optimize_background_calculations()

        except Exception as e:
            logger.error(f"[活躍度]自動播報任務執行失敗: {e}")

    @auto_report.before_loop
    async def _wait_ready(self):
        """等待機器人就緒"""
        await self.bot.wait_until_ready()

    async def _process_guild_report(
        self, guild_id: int, channel_id: int, ymd: str, ym: str, days: int
    ):
        """
        處理單一伺服器的排行榜播報

        Args:
            guild_id: 伺服器 ID
            channel_id: 頻道 ID
            ymd: 日期字串 (YYYYMMDD)
            ym: 月份字串 (YYYYMM)
            days: 當月天數
        """
        try:
            # 獲取伺服器和頻道
            guild = self.bot.get_guild(guild_id)
            if not guild:
                return

            channel = guild.get_channel(channel_id)
            if not channel or not isinstance(channel, discord.TextChannel):
                return

            # 獲取排行榜資料
            rankings = await self.db.get_daily_rankings(ymd, guild_id, limit=5)
            if not rankings:
                return

            # 獲取月度統計
            monthly_stats = await self.db.get_monthly_stats(ym, guild_id)

            # 生成排行榜嵌入
            embed = self._create_ranking_embed(guild, rankings, monthly_stats, days)

            # 發送排行榜
            await channel.send(embed=embed)

        except Exception as e:
            logger.error(f"[活躍度]處理伺服器 {guild_id} 的排行榜播報失敗: {e}")

    def _create_ranking_embed(
        self,
        guild: discord.Guild,
        rankings: list[dict[str, Any]],
        monthly_stats: dict[int, int],
        days: int,
    ) -> discord.Embed:
        """
        創建排行榜嵌入

        Args:
            guild: Discord 伺服器
            rankings: 排行榜資料
            monthly_stats: 月度統計資料
            days: 當月天數

        Returns:
            discord.Embed: 排行榜嵌入
        """
        lines = []

        for rank, data in enumerate(rankings, 1):
            user_id = data["user_id"]
            msg_cnt = data["msg_cnt"]

            # 計算月平均
            mavg = monthly_stats.get(user_id, 0) / days if days else 0

            # 獲取成員名稱
            member = guild.get_member(user_id)
            name = member.display_name if member else f"<@{user_id}>"

            # 添加排行榜項目
            lines.append(
                f"`#{rank:2}` {name:<20} ‧ 今日 {msg_cnt} 則 ‧ 月均 {mavg:.1f}"
            )

        # 創建嵌入
        embed = discord.Embed(
            title=f"📈 今日活躍排行榜 - {guild.name}",
            description="\n".join(lines),
            colour=discord.Colour.green(),
        )

        return embed
