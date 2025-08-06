"""
æ´»èºåº¦ç³»çµ±èæ¯ä»»å
- èçå®ææè¡æ¦æ´æ°åæ­å ±
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
    æ´»èºåº¦ç³»çµ±èæ¯ä»»åèçé¡å¥

    åè½:
    - å®ææè¡æ¦æ´æ°
    - èªåæ­å ±æè¡æ¦
    - æè¡æ¦åµå¥çæ
    """

    def __init__(self, bot: discord.Client, db: ActivityDatabase):
        """
        åå§åèæ¯ä»»åèçå¨

        Args:
            bot: Discord æ©å¨äººå¯¦ä¾
            db: æ´»èºåº¦è³æåº«å¯¦ä¾
        """
        self.bot = bot
        self.db = db
        self.auto_report_task = None

        # åå§åæ¹éè¨ç®æå
        self.batch_service = BatchCalculationService(db)

    def start(self):
        """ååææèæ¯ä»»å"""
        self.auto_report_task = self.auto_report.start()

    def stop(self):
        """åæ­¢ææèæ¯ä»»å"""
        if self.auto_report_task and self.auto_report.is_running():
            self.auto_report.cancel()

        # ééæ¹éè¨ç®æå
        shutdown_task = asyncio.create_task(self.batch_service.shutdown())
        # ç¢ºä¿ç°å¸¸ä¸æè¢«å¿½ç¥
        shutdown_task.add_done_callback(lambda t: t.exception())

    @tasks.loop(minutes=1)
    async def auto_report(self):
        """
        èªåæ­å ±æè¡æ¦ä»»å - ä½¿ç¨æ¹éè¨ç®åªå
        æ¯æ¥å¨æå®æéèªåç¼éæè¡æ¦å°è¨­å®çé »é
        """
        try:
            # æª¢æ¥æ¯å¦çºæå®æ­å ±æé
            now = datetime.now(config.TW_TZ)
            if now.hour != config.ACT_REPORT_HOUR or now.minute != 0:
                return

            # ç²åæ¥æå­ä¸²
            ymd = now.strftime(config.DAY_FMT)
            ym = now.strftime(config.MONTH_FMT)
            days = int(now.strftime("%d"))

            # ç²åææè¨­å®äºæ­å ±é »éçä¼ºæå¨
            report_channels = await self.db.get_report_channels()

            # æ¹éèçææä¼ºæå¨çèæ¯è¡°æ¸è¨ç®
            for guild_id, channel_id in report_channels:
                # å·è¡æ¹éè¡°æ¸è¨ç®ä»¥ç¢ºä¿æè¡æ¦æ¸ææºç¢º
                await self.batch_service.bulk_decay_all_users(guild_id)

                # æ´æ°æè¡æ¦è¨ç®
                await self.batch_service.bulk_update_rankings(guild_id, ymd)

                # èçæè¡æ¦æ­å ±
                await self._process_guild_report(guild_id, channel_id, ymd, ym, days)

            # å·è¡èæ¯è¨ç®åªåæª¢æ¥
            await self.batch_service.optimize_background_calculations()

        except Exception as e:
            logger.error(f"[æ´»èºåº¦]èªåæ­å ±ä»»åå·è¡å¤±æ: {e}")

    @auto_report.before_loop
    async def _wait_ready(self):
        """ç­å¾æ©å¨äººå°±ç·"""
        await self.bot.wait_until_ready()

    async def _process_guild_report(
        self, guild_id: int, channel_id: int, ymd: str, ym: str, days: int
    ):
        """
        èçå®ä¸ä¼ºæå¨çæè¡æ¦æ­å ±

        Args:
            guild_id: ä¼ºæå¨ ID
            channel_id: é »é ID
            ymd: æ¥æå­ä¸² (YYYYMMDD)
            ym: æä»½å­ä¸² (YYYYMM)
            days: ç¶æå¤©æ¸
        """
        try:
            # ç²åä¼ºæå¨åé »é
            guild = self.bot.get_guild(guild_id)
            if not guild:
                return

            channel = guild.get_channel(channel_id)
            if not channel or not isinstance(channel, discord.TextChannel):
                return

            # ç²åæè¡æ¦è³æ
            rankings = await self.db.get_daily_rankings(ymd, guild_id, limit=5)
            if not rankings:
                return

            # ç²åæåº¦çµ±è¨
            monthly_stats = await self.db.get_monthly_stats(ym, guild_id)

            # çææè¡æ¦åµå¥
            embed = self._create_ranking_embed(guild, rankings, monthly_stats, days)

            # ç¼éæè¡æ¦
            await channel.send(embed=embed)

        except Exception as e:
            logger.error(f"[æ´»èºåº¦]èçä¼ºæå¨ {guild_id} çæè¡æ¦æ­å ±å¤±æ: {e}")

    def _create_ranking_embed(
        self,
        guild: discord.Guild,
        rankings: list[dict[str, Any]],
        monthly_stats: dict[int, int],
        days: int,
    ) -> discord.Embed:
        """
        åµå»ºæè¡æ¦åµå¥

        Args:
            guild: Discord ä¼ºæå¨
            rankings: æè¡æ¦è³æ
            monthly_stats: æåº¦çµ±è¨è³æ
            days: ç¶æå¤©æ¸

        Returns:
            discord.Embed: æè¡æ¦åµå¥
        """
        lines = []

        for rank, data in enumerate(rankings, 1):
            user_id = data["user_id"]
            msg_cnt = data["msg_cnt"]

            # è¨ç®æå¹³å
            mavg = monthly_stats.get(user_id, 0) / days if days else 0

            # ç²åæå¡åç¨±
            member = guild.get_member(user_id)
            name = member.display_name if member else f"<@{user_id}>"

            # æ·»å æè¡æ¦é ç®
            lines.append(
                f"`#{rank:2}` {name:<20} â§ ä»æ¥ {msg_cnt} å â§ æå {mavg:.1f}"
            )

        # åµå»ºåµå¥
        embed = discord.Embed(
            title=f" ä»æ¥æ´»èºæè¡æ¦ - {guild.name}",
            description="\n".join(lines),
            colour=discord.Colour.green(),
        )

        return embed
