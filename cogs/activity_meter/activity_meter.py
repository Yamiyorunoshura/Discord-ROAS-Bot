# /cogs/activity_meter/activity_meter.py
# ============================================================
# 活躍度系統模組
#  - 提供 0~100 分活躍度計算、每日/月排行榜、進度條圖片
#  - 支援自動播報、排行榜頻道設定、資料庫持久化
#  - 具備詳細錯誤處理與日誌記錄
# ============================================================

import asyncio, time, io, traceback, contextlib, logging
import aiosqlite, discord, config
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime as dt, timezone
from PIL import Image, ImageDraw, ImageFont

DAY_FMT, MONTH_FMT = "%Y%m%d", "%Y%m"

# ───────── Logger ─────────
logger = logging.getLogger("activity_meter")
if not logger.hasHandlers():
    fh = logging.FileHandler(f"{config.LOGS_DIR}/activity_meter.log", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.setLevel(logging.INFO)
    logger.addHandler(fh)

# ───────── 友善錯誤工具 ─────────
def _trace(exc, depth=3):
    """生成簡潔的錯誤追蹤資訊"""
    return "".join(traceback.TracebackException.from_exception(exc, limit=depth).format())

def _log(log, msg, exc=None, level=40):
    """統一錯誤日誌格式，附加追蹤碼與詳細資訊"""
    if exc:
        msg = f"{msg}\n原因：{type(exc).__name__}: {exc}\n{_trace(exc)}"
    log.log(level, msg, exc_info=bool(exc))

@contextlib.contextmanager
def handle_error(log, inter: discord.Interaction, user_msg="發生未知錯誤"):
    """Discord 互動指令專用錯誤處理，回報追蹤碼給用戶"""
    if log is None:
        log = logger
    code = dt.utcnow().strftime("%Y%m%d%H%M%S%f")
    try:
        yield
    except Exception as exc:
        _log(log, f"{user_msg} (追蹤碼: {code})", exc)
        reply = f"❌ {user_msg}\n追蹤碼：`{code}`，請聯絡管理員。"
        try:
            if inter.response.is_done():
                asyncio.create_task(inter.followup.send(reply))
            else:
                asyncio.create_task(inter.response.send_message(reply))
        except Exception:
            pass

# ───────── Cog ─────────
class ActivityMeter(commands.Cog):
    """
    活躍度系統 Cog
    - 計算用戶活躍度（0~100 分，隨時間衰減）
    - 提供每日/月排行榜查詢
    - 支援自動播報與排行榜頻道設定
    - 具備詳細錯誤處理與日誌
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.lock = asyncio.Lock()  # 全域鎖，避免資料競爭
        bot.loop.create_task(self._init_db())
        self.auto_report.start()

    # ---------- DB ----------
    def _db(self):
        """取得資料庫連線 coroutine"""
        return aiosqlite.connect(config.ACTIVITY_DB_PATH, isolation_level=None, timeout=20)

    async def _init_db(self):
        """初始化資料庫表結構"""
        async with self._db() as db:
            await db.executescript("""
            CREATE TABLE IF NOT EXISTS meter(
              guild_id INTEGER, user_id INTEGER,
              score REAL DEFAULT 0, last_msg INTEGER DEFAULT 0,
              PRIMARY KEY(guild_id, user_id)
            );
            CREATE TABLE IF NOT EXISTS daily(
              ymd TEXT, guild_id INTEGER, user_id INTEGER,
              msg_cnt INTEGER DEFAULT 0,
              PRIMARY KEY(ymd, guild_id, user_id)
            );
            CREATE TABLE IF NOT EXISTS report_channel(
              guild_id INTEGER PRIMARY KEY,
              channel_id INTEGER
            );
            """)
        logger.info("【活躍度】DB 初始化完成")

    # ---------- 工具 ----------
    @staticmethod
    def _decay(score: float, delta: int) -> float:
        """活躍度隨時間衰減計算"""
        if delta <= config.ACTIVITY_DECAY_AFTER:
            return score
        decay = (config.ACTIVITY_DECAY_PER_H / 3600) * (delta - config.ACTIVITY_DECAY_AFTER)
        return max(0, score - decay)

    def _render_bar(self, member: discord.Member, score: float) -> discord.File:
        """
        產生活躍度進度條圖片
        Args:
            member: Discord 成員物件
            score: 活躍度分數
        Returns:
            Discord File 物件（PNG 圖片）
        """
        w, h = config.ACT_BAR_WIDTH, config.ACT_BAR_HEIGHT
        img = Image.new("RGBA", (w, h), config.ACT_BAR_BG)
        draw = ImageDraw.Draw(img, "RGBA")
        draw.rectangle([(0, 0), (w - 1, h - 1)], outline=config.ACT_BAR_BORDER)

        fill_w = int((w - 2) * score / config.ACTIVITY_MAX_SCORE)
        if fill_w:
            draw.rectangle([(1, 1), (fill_w, h - 2)], fill=config.ACT_BAR_FILL)

        txt = f"{getattr(member, 'display_name', '未知用戶')} ‧ {score:.1f}/100"
        try:
            font = ImageFont.truetype(config.WELCOME_DEFAULT_FONT, 18)
        except Exception:
            font = ImageFont.load_default()

        try:  # Pillow ≥10
            tw = font.getlength(txt)
            tb = draw.textbbox((0, 0), txt, font=font)
            th = tb[3] - tb[1]
        except AttributeError:  # Pillow <10
            if hasattr(font, 'getsize'):
                tw, th = font.getsize(txt)  # type: ignore
            else:
                tw, th = 100, 20  # fallback

        draw.text(((w - tw) // 2, (h - th) // 2), txt, fill=(255, 255, 255, 255), font=font)

        buf = io.BytesIO()
        img.save(buf, "PNG")
        buf.seek(0)
        return discord.File(buf, filename="activity.png")

    async def _send_reply(self, inter, reply: str):
        """發送回覆訊息"""
        try:
            if inter.response.is_done():
                asyncio.create_task(inter.followup.send(reply))
            else:
                asyncio.create_task(inter.response.send_message(reply))
        except Exception as e:
            _log(logger, "發送回覆失敗", e)

    # ---------- 指令 ----------
    @app_commands.command(name="活躍度", description="查看活躍度（進度條）")
    async def 活躍度(self, inter: discord.Interaction, 成員: discord.Member | None = None):
        await inter.response.defer()
        member = 成員 or inter.user
        if not isinstance(member, discord.Member):
            await inter.followup.send("❌ 只能查詢伺服器成員的活躍度。")
            return
        with handle_error(logger, inter, "查詢活躍度失敗"):
            async with self._db() as db:
                cur = await db.execute(
                    "SELECT score, last_msg FROM meter WHERE guild_id=? AND user_id=?",
                    (getattr(inter.guild, 'id', 0), getattr(member, 'id', 0))
                )
                row = await cur.fetchone()
            score = 0 if not row else self._decay(row[0], int(time.time()) - row[1])
            await inter.followup.send(file=self._render_bar(member, score))

    @app_commands.command(name="今日排行榜", description="查看今日訊息數排行榜")
    async def 今日排行榜(self, inter: discord.Interaction, 名次: int = 10):
        await inter.response.defer()
        with handle_error(logger, inter, "查詢排行榜失敗"):
            ymd = dt.now(timezone.utc).astimezone(config.TW_TZ).strftime(DAY_FMT)
            async with self._db() as db:
                cur = await db.execute(
                    "SELECT user_id, msg_cnt FROM daily "
                    "WHERE ymd=? AND guild_id=? ORDER BY msg_cnt DESC LIMIT ?",
                    (ymd, getattr(inter.guild, 'id', 0), 名次)
                )
                rows = await cur.fetchall()
            if not rows:
                await inter.followup.send("今天還沒有人說話！")
                return

            ym = dt.now(config.TW_TZ).strftime(MONTH_FMT)
            async with self._db() as db:
                cur_m = await db.execute(
                    "SELECT user_id, SUM(msg_cnt) FROM daily "
                    "WHERE ymd LIKE ? || '%' AND guild_id=? GROUP BY user_id",
                    (ym, getattr(inter.guild, 'id', 0))
                )
                month_rows = {uid: total for uid, total in await cur_m.fetchall()}
            days = int(dt.now(config.TW_TZ).strftime("%d"))

            lines = []
            for rank, (uid, cnt) in enumerate(rows, 1):
                mavg = month_rows.get(uid, 0) / days if days else 0
                member = inter.guild.get_member(uid) if inter.guild else None
                name = member.display_name if member else f"<@{uid}>"
                lines.append(f"`#{rank:2}` {name:<20} ‧ 今日 {cnt} 則 ‧ 月均 {mavg:.1f}")

            embed = discord.Embed(
                title=f"📈 今日活躍排行榜 - {getattr(inter.guild, 'name', '未知伺服器')}",
                description="\n".join(lines),
                colour=discord.Colour.green()
            )
            await inter.followup.send(embed=embed)

    @app_commands.command(name="設定排行榜頻道", description="設定每日自動播報排行榜的頻道")
    @app_commands.describe(頻道="要播報到哪個文字頻道")
    async def 設定排行榜頻道(self, inter: discord.Interaction, 頻道: discord.TextChannel):
        if not config.is_allowed(inter, "設定排行榜頻道"):
            await inter.response.send_message("❌ 你沒有權限執行本指令。")
            return
        async with self._db() as db:
            await db.execute(
                "INSERT OR REPLACE INTO report_channel VALUES(?,?)",
                (getattr(inter.guild, 'id', 0), 頻道.id)
            )
        await inter.response.send_message(f"✅ 已設定為 {頻道.mention}")

    # ---------- 自動播報 ----------
    @tasks.loop(minutes=1)
    async def auto_report(self):
        now = dt.now(config.TW_TZ)
        if now.hour != config.ACT_REPORT_HOUR or now.minute != 0:
            return
        ymd, ym = now.strftime(DAY_FMT), now.strftime(MONTH_FMT)
        async with self._db() as db:
            cur = await db.execute("SELECT guild_id, channel_id FROM report_channel")
            for gid, ch_id in await cur.fetchall():
                guild = self.bot.get_guild(gid)
                channel = guild.get_channel(ch_id) if guild else None
                if not (channel and isinstance(channel, discord.TextChannel)):
                    continue
                cur_t = await db.execute(
                    "SELECT user_id, msg_cnt FROM daily "
                    "WHERE ymd=? AND guild_id=? ORDER BY msg_cnt DESC LIMIT 5",
                    (ymd, gid)
                )
                today_rows = await cur_t.fetchall()
                if not today_rows:
                    continue
                cur_m = await db.execute(
                    "SELECT user_id, SUM(msg_cnt) FROM daily "
                    "WHERE ymd LIKE ? || '%' AND guild_id=? GROUP BY user_id",
                    (ym, gid)
                )
                month_rows = {uid: total for uid, total in await cur_m.fetchall()}
                days = int(now.strftime("%d"))
                lines = []
                for rank, (uid, cnt) in enumerate(today_rows, 1):
                    mavg = month_rows.get(uid, 0) / days if days else 0
                    member = guild.get_member(uid) if guild else None
                    name = member.display_name if member else f"<@{uid}>"
                    lines.append(f"`#{rank:2}` {name:<20} ‧ 今日 {cnt} 則 ‧ 月均 {mavg:.1f}")
                embed = discord.Embed(
                    title=f"📈 今日活躍排行榜 - {getattr(guild, 'name', '未知伺服器')}",
                    description="\n".join(lines),
                    colour=discord.Colour.green()
                )
                try:
                    await channel.send(embed=embed)
                except Exception as exc:
                    _log(logger, f"自動播報排行榜失敗 (guild_id={gid}, channel_id={ch_id})", exc)

    @auto_report.before_loop
    async def _wait_ready(self):
        await self.bot.wait_until_ready()

    # ---------- 事件 ----------
    @commands.Cog.listener("on_message")
    async def on_message(self, msg: discord.Message):
        if msg.author.bot or not msg.guild:
            return
        now = int(time.time())
        ymd = dt.now(timezone.utc).astimezone(config.TW_TZ).strftime(DAY_FMT)

        async with self.lock:
            async with self._db() as db:
                cur = await db.execute(
                    "SELECT score, last_msg FROM meter WHERE guild_id=? AND user_id=?",
                    (getattr(msg.guild, 'id', 0), getattr(msg.author, 'id', 0))
                )
                row = await cur.fetchone()
                score, last_msg = (row if row else (0.0, 0))

                if now - last_msg < config.ACTIVITY_COOLDOWN:
                    await db.execute(
                        "INSERT INTO daily VALUES(?,?,?,1) "
                        "ON CONFLICT DO UPDATE SET msg_cnt = msg_cnt + 1",
                        (ymd, getattr(msg.guild, 'id', 0), getattr(msg.author, 'id', 0))
                    )
                    return

                score = min(self._decay(score, now - last_msg) + config.ACTIVITY_GAIN,
                            config.ACTIVITY_MAX_SCORE)

                await db.execute(
                    "INSERT INTO meter VALUES(?,?,?,?) "
                    "ON CONFLICT DO UPDATE SET score=?, last_msg=?",
                    (getattr(msg.guild, 'id', 0), getattr(msg.author, 'id', 0), score, now, score, now)
                )
                await db.execute(
                    "INSERT INTO daily VALUES(?,?,?,1) "
                    "ON CONFLICT DO UPDATE SET msg_cnt = msg_cnt + 1",
                    (ymd, getattr(msg.guild, 'id', 0), getattr(msg.author, 'id', 0))
                )

# ---------- setup ----------
async def setup(bot: commands.Bot):
    await bot.add_cog(ActivityMeter(bot))