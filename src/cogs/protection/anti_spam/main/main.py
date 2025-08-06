"""
反垃圾訊息保護模組主要邏輯協調中心
- 作為模組的核心,協調各個子模組的工作
- 處理垃圾訊息檢測和違規處理
- 管理用戶行為歷史和統計資料
"""

import contextlib
import datetime as dt
import time
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands, tasks

# 使用統一的核心模塊
from ....core import create_error_handler, setup_module_logger
from ...base import ProtectionCog, admin_only
from ..config.config import DEFAULTS
from ..database.database import AntiSpamDatabase
from ..panel.embeds.settings_embed import create_settings_embed
from ..panel.main_view import AntiSpamMainView

# 常數定義
MAX_ACTION_LOGS = 100

# 設置模塊日誌記錄器
logger = setup_module_logger("anti_spam")
error_handler = create_error_handler("anti_spam", logger)


# 相似度計算函數
def _similar(a: str, b: str) -> float:
    """計算兩個字串的相似度"""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


class AntiSpam(ProtectionCog):
    """
    反垃圾訊息保護模組

    負責檢測和處理各種類型的垃圾訊息行為,包括:
    - 高頻率訊息檢測
    - 重複/相似訊息檢測
    - 貼圖濫用檢測
    - 違規行為處理和記錄
    """

    module_name = "anti_spam"

    def __init__(self, bot: commands.Bot):
        """
        初始化反垃圾訊息保護系統

        Args:
            bot: Discord 機器人實例
        """
        super().__init__(bot)
        self.db = AntiSpamDatabase(self)

        # 用戶行為追蹤
        self.violate: dict[int, int] = defaultdict(int)  # 用戶違規次數
        self.message_history: dict[int, list[tuple[float, str]]] = defaultdict(
            list
        )  # 用戶訊息歷史
        self.sticker_history: dict[int, list[float]] = defaultdict(list)  # 用戶貼圖歷史

        # 統計資料
        self.stats: dict[int, dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )  # 伺服器統計資料
        self.action_logs: dict[int, list[dict[str, Any]]] = defaultdict(
            list
        )  # 伺服器操作日誌

    async def cog_load(self):
        """Cog 載入時的初始化"""
        try:
            await self.db.init_db()
            # 啟動背景任務
            self._reset_task.start()
            logger.info("[反垃圾訊息]模組載入完成")
        except Exception as exc:
            logger.error(f"[反垃圾訊息]模組載入失敗: {exc}")
            raise

    async def cog_unload(self):
        """Cog 卸載時的清理"""
        try:
            # 停止背景任務
            self._reset_task.cancel()
            logger.info("[反垃圾訊息]模組卸載完成")
        except Exception as exc:
            logger.error(f"[反垃圾訊息]模組卸載失敗: {exc}")

    # ───────── 事件處理 ─────────
    @commands.Cog.listener()
    async def on_message(self, msg: discord.Message):
        """處理新訊息事件,檢測垃圾訊息行為"""
        try:
            # 基本檢查
            if msg.author.bot or not msg.guild:
                return

            # 檢查模組是否啟用
            enabled = await self.get_cfg(msg.guild.id, "enabled", "true")
            if not enabled or enabled.lower() != "true":
                return

            if (
                isinstance(msg.author, discord.Member)
                and msg.author.guild_permissions.manage_messages
            ):
                return

            # 記錄訊息到歷史
            now = time.time()
            user_id = msg.author.id

            # 記錄一般訊息
            if msg.content:
                self.message_history[user_id].append((now, msg.content))

            # 記錄貼圖
            if msg.stickers:
                self.sticker_history[user_id].append(now)

            # 清理舊歷史記錄
            self._cleanup_history(user_id, now)

            # 檢測各種垃圾訊息行為
            violations = []
            key = (user_id, msg.guild.id)

            # 檢查頻率限制
            if await self._match_freq_limit(msg.guild.id, key, now):
                violations.append("頻率限制")

            # 檢查重複訊息
            if msg.content and await self._match_identical(msg.guild.id, key, now):
                violations.append("重複訊息")

            # 檢查相似訊息
            if msg.content and await self._match_similar(msg.guild.id, key, now):
                violations.append("相似訊息")

            # 檢查貼圖濫用
            if msg.stickers and await self._match_sticker(msg.guild.id, key, now):
                violations.append("貼圖濫用")

            # 處理違規行為
            if violations:
                await self._handle_violation(msg, violations)

        except Exception as exc:
            error_handler.log_error(
                exc, f"處理訊息事件 - {msg.author.id}", "MESSAGE_HANDLER_ERROR"
            )

    # ───────── 檢測邏輯 ─────────
    async def _match_freq_limit(
        self, guild_id: int, key: tuple[int, int], now: float
    ) -> bool:
        """檢查頻率限制"""
        try:
            limit_str = await self.get_cfg(
                guild_id, "spam_freq_limit", str(DEFAULTS["spam_freq_limit"])
            )
            window_str = await self.get_cfg(
                guild_id, "spam_freq_window", str(DEFAULTS["spam_freq_window"])
            )

            limit = int(limit_str or DEFAULTS["spam_freq_limit"])
            window = float(window_str or DEFAULTS["spam_freq_window"])

            user_id = key[0]
            recent_messages = [
                t for t, _ in self.message_history[user_id] if now - t <= window
            ]

            return len(recent_messages) >= limit

        except Exception as exc:
            logger.error(f"[反垃圾訊息]頻率檢查失敗: {exc}")
            return False

    async def _match_identical(
        self, guild_id: int, key: tuple[int, int], now: float
    ) -> bool:
        """檢查重複訊息"""
        try:
            limit_str = await self.get_cfg(
                guild_id, "spam_identical_limit", str(DEFAULTS["spam_identical_limit"])
            )
            window_str = await self.get_cfg(
                guild_id,
                "spam_identical_window",
                str(DEFAULTS["spam_identical_window"]),
            )

            limit = int(limit_str or DEFAULTS["spam_identical_limit"])
            window = float(window_str or DEFAULTS["spam_identical_window"])

            user_id = key[0]
            recent_messages = [
                (t, content)
                for t, content in self.message_history[user_id]
                if now - t <= window
            ]

            if len(recent_messages) < limit:
                return False

            # 檢查是否有重複內容
            content_counts = defaultdict(int)
            for _, content in recent_messages:
                content_counts[content] += 1
                if content_counts[content] >= limit:
                    return True

            return False

        except Exception as exc:
            logger.error(f"[反垃圾訊息]重複檢查失敗: {exc}")
            return False

    async def _match_similar(
        self, guild_id: int, key: tuple[int, int], now: float
    ) -> bool:
        """檢查相似訊息"""
        try:
            limit_str = await self.get_cfg(
                guild_id, "spam_similar_limit", str(DEFAULTS["spam_similar_limit"])
            )
            window_str = await self.get_cfg(
                guild_id, "spam_similar_window", str(DEFAULTS["spam_similar_window"])
            )
            threshold_str = await self.get_cfg(
                guild_id,
                "spam_similar_threshold",
                str(DEFAULTS["spam_similar_threshold"]),
            )

            limit = int(limit_str or DEFAULTS["spam_similar_limit"])
            window = float(window_str or DEFAULTS["spam_similar_window"])
            threshold = float(threshold_str or DEFAULTS["spam_similar_threshold"])

            user_id = key[0]
            recent_messages = [
                (t, content)
                for t, content in self.message_history[user_id]
                if now - t <= window
            ]

            if len(recent_messages) < limit:
                return False

            # 檢查相似度
            contents = [content for _, content in recent_messages]
            similar_count = 0

            for i in range(len(contents)):
                for j in range(i + 1, len(contents)):
                    if _similar(contents[i], contents[j]) >= threshold:
                        similar_count += 1
                        if similar_count >= limit:
                            return True

            return False

        except Exception as exc:
            logger.error(f"[反垃圾訊息]相似度檢查失敗: {exc}")
            return False

    async def _match_sticker(
        self, guild_id: int, key: tuple[int, int], now: float
    ) -> bool:
        """檢查貼圖濫用"""
        try:
            limit_str = await self.get_cfg(
                guild_id, "spam_sticker_limit", str(DEFAULTS["spam_sticker_limit"])
            )
            window_str = await self.get_cfg(
                guild_id, "spam_sticker_window", str(DEFAULTS["spam_sticker_window"])
            )

            limit = int(limit_str or DEFAULTS["spam_sticker_limit"])
            window = float(window_str or DEFAULTS["spam_sticker_window"])

            user_id = key[0]
            recent_stickers = [
                t for t in self.sticker_history[user_id] if now - t <= window
            ]

            return len(recent_stickers) >= limit

        except Exception as exc:
            logger.error(f"[反垃圾訊息]貼圖檢查失敗: {exc}")
            return False

    def _cleanup_history(self, user_id: int, now: float):
        """清理過期的歷史記錄"""
        try:
            # 清理訊息歷史(保留最近 10 分鐘)
            cutoff = now - 600  # 10 分鐘
            self.message_history[user_id] = [
                (t, content)
                for t, content in self.message_history[user_id]
                if t > cutoff
            ]

            # 清理貼圖歷史
            self.sticker_history[user_id] = [
                t for t in self.sticker_history[user_id] if t > cutoff
            ]

            # 如果歷史記錄為空,從字典中移除
            if not self.message_history[user_id]:
                del self.message_history[user_id]
            if not self.sticker_history[user_id]:
                del self.sticker_history[user_id]

        except Exception as exc:
            logger.error(f"[反垃圾訊息]清理歷史失敗: {exc}")

    # ───────── 違規處理 ─────────
    async def _handle_violation(self, msg: discord.Message, violations: list[str]):
        """處理違規行為"""
        try:
            # 刪除違規訊息
            try:
                await msg.delete()
            except discord.NotFound:
                pass
            except discord.Forbidden:
                logger.warning(f"[反垃圾訊息]無權刪除訊息: {msg.id}")

            # 增加違規次數
            self.violate[msg.author.id] += 1
            violation_count = self.violate[msg.author.id]

            # 確保有 guild
            if not msg.guild:
                return

            # 記錄統計資料
            for violation in violations:
                await self._add_stat(msg.guild.id, f"violation_{violation.lower()}")

            # 處理超時
            timeout_str = await self.get_cfg(
                msg.guild.id,
                "spam_timeout_minutes",
                str(DEFAULTS["spam_timeout_minutes"]),
            )
            timeout_minutes = int(timeout_str or DEFAULTS["spam_timeout_minutes"])

            if timeout_minutes > 0 and isinstance(msg.author, discord.Member):
                success = await self._timeout_member(msg.author, timeout_minutes)
                if success:
                    await self._add_stat(msg.guild.id, "timeouts")

            # 發送回復訊息
            response_enabled = await self.get_cfg(
                msg.guild.id, "spam_response_enabled", DEFAULTS["spam_response_enabled"]
            )
            if response_enabled and response_enabled.lower() == "true":
                response_message = await self.get_cfg(
                    msg.guild.id,
                    "spam_response_message",
                    DEFAULTS["spam_response_message"],
                )
                with contextlib.suppress(discord.Forbidden):
                    await msg.channel.send(
                        f"{msg.author.mention} {response_message or DEFAULTS['spam_response_message']}",
                        delete_after=10,
                    )

            # 發送管理員通知
            channel_mention = getattr(
                msg.channel, "mention", f"#{getattr(msg.channel, 'name', 'unknown')}"
            )
            notify_text = (
                f"🚫 **反垃圾訊息警報**\n"
                f"用戶:{msg.author.mention} ({msg.author.id})\n"
                f"頻道:{channel_mention}\n"
                f"違規類型:{', '.join(violations)}\n"
                f"累計違規:{violation_count} 次\n"
                f"處理:訊息已刪除"
            )

            if timeout_minutes > 0:
                notify_text += f",用戶已被禁言 {timeout_minutes} 分鐘"

            await self._send_notification(msg.guild, notify_text)

            # 記錄操作日誌
            await self._add_action_log(
                msg.guild.id,
                msg.author.id,
                "violation",
                f"違規類型: {', '.join(violations)}, 累計: {violation_count} 次",
            )

            logger.info(
                f"[反垃圾訊息]處理違規: {msg.author.id} - {', '.join(violations)}"
            )

        except Exception as exc:
            error_handler.log_error(
                exc, f"處理違規行為 - {msg.author.id}", "VIOLATION_HANDLER_ERROR"
            )

    async def _timeout_member(self, member: discord.Member, minutes: int) -> bool:
        """對成員進行超時處理"""
        try:
            timeout_duration = dt.timedelta(minutes=minutes)
            await member.timeout(timeout_duration, reason="反垃圾訊息保護")
            return True
        except discord.Forbidden:
            logger.warning(f"[反垃圾訊息]無權限對用戶 {member.id} 進行超時")
            return False
        except Exception as exc:
            logger.error(f"[反垃圾訊息]超時處理失敗: {exc}")
            return False

    async def _send_notification(self, guild: discord.Guild, message: str):
        """發送管理員通知"""
        try:
            notify_channel_id = await self.get_cfg(guild.id, "spam_notify_channel", "")
            if not notify_channel_id:
                return

            try:
                channel_id = int(notify_channel_id)
                channel = guild.get_channel(channel_id)
                if channel and isinstance(channel, discord.TextChannel):
                    embed = discord.Embed(
                        description=message,
                        color=discord.Color.red(),
                        timestamp=dt.datetime.now(),
                    )
                    await channel.send(embed=embed)
            except (ValueError, AttributeError):
                logger.warning(f"[反垃圾訊息]無效的通知頻道ID: {notify_channel_id}")

        except Exception as exc:
            logger.error(f"[反垃圾訊息]發送通知失敗: {exc}")

    # ───────── 統計和日誌 ─────────
    async def _add_stat(self, guild_id: int, stat_type: str):
        """添加統計資料"""
        try:
            self.stats[guild_id][stat_type] += 1
            # 同時記錄到資料庫
            await self.db.add_stat(guild_id, stat_type)
        except Exception as exc:
            logger.error(f"[反垃圾訊息]添加統計失敗: {exc}")

    async def _add_action_log(
        self, guild_id: int, user_id: int, action: str, details: str
    ):
        """添加操作日誌"""
        try:
            log_entry = {
                "timestamp": dt.datetime.now().isoformat(),
                "user_id": user_id,
                "action": action,
                "details": details,
            }

            # 添加到內存日誌
            self.action_logs[guild_id].append(log_entry)

            # 保持最近的記錄
            if len(self.action_logs[guild_id]) > MAX_ACTION_LOGS:
                self.action_logs[guild_id] = self.action_logs[guild_id][
                    -MAX_ACTION_LOGS:
                ]

            # 記錄到資料庫
            await self.db.add_action_log(guild_id, user_id, action, details)

        except Exception as exc:
            logger.error(f"[反垃圾訊息]添加操作日誌失敗: {exc}")

    # ───────── 斜線指令 ─────────
    @app_commands.command(name="洗版設定面板", description="開啟反垃圾訊息設定面板")
    @admin_only()
    async def spam_panel(self, interaction: discord.Interaction):
        """開啟反垃圾訊息設定面板"""
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ 本指令只能在伺服器中使用.", ephemeral=True
            )
            return

        try:
            # 創建設定嵌入
            embed = await create_settings_embed(self, interaction.guild, "all")

            # 創建面板視圖
            view = AntiSpamMainView(self, interaction.user.id, interaction.guild)

            # 發送面板
            await interaction.response.send_message(
                embed=embed, view=view, ephemeral=True
            )
            logger.info(f"[反垃圾訊息]{interaction.user.id} 開啟了設定面板")

        except Exception as exc:
            error_handler.log_error(
                exc, f"開啟設定面板 - {interaction.user.id}", "PANEL_ERROR_532"
            )

            # 創建錯誤嵌入
            error_embed = discord.Embed(
                title="❌ 面板載入失敗",
                description="載入設定面板時發生錯誤,請稍後再試.\n錯誤碼: 532",
                color=discord.Color.red(),
            )

            try:
                await interaction.response.send_message(
                    embed=error_embed, ephemeral=True
                )
            except Exception:
                await interaction.followup.send(embed=error_embed, ephemeral=True)

    # ───────── 背景任務 ─────────
    @tasks.loop(hours=24)
    async def _reset_task(self):
        """每日重置任務"""
        try:
            # 清理違規計數
            self.violate.clear()

            # 清理過期的歷史記錄
            now = time.time()
            cutoff = now - 3600  # 1 小時

            for user_id in list(self.message_history.keys()):
                self.message_history[user_id] = [
                    (t, content)
                    for t, content in self.message_history[user_id]
                    if t > cutoff
                ]
                if not self.message_history[user_id]:
                    del self.message_history[user_id]

            for user_id in list(self.sticker_history.keys()):
                self.sticker_history[user_id] = [
                    t for t in self.sticker_history[user_id] if t > cutoff
                ]
                if not self.sticker_history[user_id]:
                    del self.sticker_history[user_id]

            # 清理操作日誌(保留最近 7 天)
            cutoff_date = dt.datetime.now() - dt.timedelta(days=7)
            for guild_id in list(self.action_logs.keys()):
                self.action_logs[guild_id] = [
                    log
                    for log in self.action_logs[guild_id]
                    if dt.datetime.fromisoformat(log["timestamp"]) > cutoff_date
                ]
                if not self.action_logs[guild_id]:
                    del self.action_logs[guild_id]

            logger.info("[反垃圾訊息]每日重置任務完成")

        except Exception as exc:
            logger.error(f"[反垃圾訊息]每日重置任務失敗: {exc}")

    @_reset_task.before_loop
    async def _before_reset_task(self):
        """等待機器人準備就緒"""
        await self.bot.wait_until_ready()

    # ───────── 工具方法 ─────────
    async def get_stats(self, guild_id: int) -> dict[str, int]:
        """取得統計資料"""
        try:
            # 合併內存和資料庫統計
            memory_stats = self.stats.get(guild_id, {})
            db_stats = await self.db.get_stats(guild_id)

            # 合併統計資料
            combined_stats = defaultdict(int)
            for key, value in memory_stats.items():
                combined_stats[key] += value
            for key, value in db_stats.items():
                combined_stats[key] += value

            return dict(combined_stats)

        except Exception as exc:
            logger.error(f"[反垃圾訊息]取得統計失敗: {exc}")
            return {}

    async def get_action_logs(
        self, guild_id: int, limit: int = 50
    ) -> list[dict[str, Any]]:
        """取得操作日誌"""
        try:
            # 合併內存和資料庫日誌
            memory_logs = self.action_logs.get(guild_id, [])
            db_logs = await self.db.get_action_logs(guild_id, limit)

            # 合併並排序
            all_logs = memory_logs + db_logs
            all_logs.sort(key=lambda x: x["timestamp"], reverse=True)

            return all_logs[:limit]

        except Exception as exc:
            logger.error(f"[反垃圾訊息]取得操作日誌失敗: {exc}")
            return []
