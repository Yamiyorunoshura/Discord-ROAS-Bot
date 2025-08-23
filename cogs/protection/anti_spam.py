# anti_spam.py  ── 反垃圾訊息保護模組 (Discord.py 2.5.2 兼容版)
# ============================================================
# 主要功能：
#  - 智能垃圾訊息檢測（頻率、重複、相似度）
#  - 貼圖濫用防護
#  - 管理員通知系統
#  - 互動式設定面板
#  - 自定義回復訊息
# 
# Discord.py 2.5.2 兼容性修復：
#  - 修正 Modal 定義語法
#  - 改進回應機制避免逾時
#  - 完善錯誤處理
# ============================================================

import asyncio
import datetime as dt
import logging
import logging.handlers
import re
import traceback
import typing as t
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict
from difflib import SequenceMatcher
import contextlib

import aiosqlite
import discord
from discord import app_commands, ui
from discord.ext import commands, tasks

from .base import ProtectionCog, admin_only, handle_error, friendly_log
from config import TW_TZ

# ────────────────────────────
# 日誌設定
# ────────────────────────────
file_handler = logging.handlers.RotatingFileHandler(
    "logs/anti_spam.log", mode="a", encoding="utf-8",
    maxBytes=2 * 1024 * 1024, backupCount=2
)
file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))

logger = logging.getLogger("anti_spam")
logger.setLevel(logging.INFO)
if not logger.hasHandlers():
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

# ────────────────────────────
# 配置常數
# ────────────────────────────
DEFAULTS = {
    "spam_freq_limit": 5,      # 頻率限制（訊息數）
    "spam_freq_window": 10,    # 頻率窗口（秒）
    "spam_identical_limit": 3, # 重複訊息限制
    "spam_identical_window": 30, # 重複窗口（秒）
    "spam_similar_limit": 3,   # 相似訊息限制
    "spam_similar_window": 60, # 相似窗口（秒）
    "spam_similar_threshold": 0.8, # 相似度閾值
    "spam_sticker_limit": 5,   # 貼圖限制
    "spam_sticker_window": 30, # 貼圖窗口（秒）
    "spam_timeout_minutes": 5, # 違規超時（分鐘）
    "spam_notify_channel": "", # 通知頻道 ID
    "spam_response_message": "您已觸發洗版限制，請注意您的行為。", # 自定義回復訊息
    "spam_response_enabled": "true", # 是否啟用自定義回復
}

CH_NAMES = {
    "spam_freq_limit": "頻率限制",
    "spam_freq_window": "頻率窗口",
    "spam_identical_limit": "重複限制",
    "spam_identical_window": "重複窗口",
    "spam_similar_limit": "相似限制",
    "spam_similar_window": "相似窗口",
    "spam_similar_threshold": "相似度閾值",
    "spam_sticker_limit": "貼圖限制",
    "spam_sticker_window": "貼圖窗口",
    "spam_timeout_minutes": "超時分鐘",
    "spam_notify_channel": "通知頻道",
    "spam_response_message": "回復訊息",
    "spam_response_enabled": "啟用回復",
}

# ────────────────────────────
# 進階配置結構 (新增)
# ────────────────────────────
CONFIG_CATEGORIES = {
    "frequency": {
        "name": "洗版頻率",
        "desc": "設定訊息頻率限制，防止短時間內發送大量訊息",
        "items": [
            {
                "key": "spam_freq_limit",
                "name": "頻率限制",
                "desc": "在指定時間窗口內，超過此數量的訊息將被視為洗版",
                "recommend": "5-8 (一般伺服器) / 3-5 (嚴格模式)",
                "type": "int"
            },
            {
                "key": "spam_freq_window",
                "name": "頻率窗口",
                "desc": "檢查洗版行為的時間窗口（秒）",
                "recommend": "10-15 秒",
                "type": "int"
            }
        ]
    },
    "repeat": {
        "name": "重複/相似訊息",
        "desc": "設定重複或相似內容的訊息限制",
        "items": [
            {
                "key": "spam_identical_limit",
                "name": "重複限制",
                "desc": "在指定時間內，發送相同訊息超過此數量將被視為洗版",
                "recommend": "3 次",
                "type": "int"
            },
            {
                "key": "spam_identical_window",
                "name": "重複窗口",
                "desc": "檢查重複訊息的時間窗口（秒）",
                "recommend": "30-60 秒",
                "type": "int"
            },
            {
                "key": "spam_similar_limit",
                "name": "相似限制",
                "desc": "在指定時間內，發送相似訊息超過此數量將被視為洗版",
                "recommend": "3-5 次",
                "type": "int"
            },
            {
                "key": "spam_similar_window",
                "name": "相似窗口",
                "desc": "檢查相似訊息的時間窗口（秒）",
                "recommend": "60-120 秒",
                "type": "int"
            },
            {
                "key": "spam_similar_threshold",
                "name": "相似度閾值",
                "desc": "判定訊息相似的閾值（0-1之間的小數，越大表示越相似）",
                "recommend": "0.7-0.8",
                "type": "float"
            }
        ]
    },
    "sticker": {
        "name": "貼圖限制",
        "desc": "設定貼圖使用頻率限制",
        "items": [
            {
                "key": "spam_sticker_limit",
                "name": "貼圖限制",
                "desc": "在指定時間內，發送貼圖超過此數量將被視為濫用",
                "recommend": "5-8 次",
                "type": "int"
            },
            {
                "key": "spam_sticker_window",
                "name": "貼圖窗口",
                "desc": "檢查貼圖使用的時間窗口（秒）",
                "recommend": "30-60 秒",
                "type": "int"
            }
        ]
    },
    "action": {
        "name": "處理動作",
        "desc": "設定對洗版行為的處理方式",
        "items": [
            {
                "key": "spam_timeout_minutes",
                "name": "超時分鐘",
                "desc": "觸發洗版保護時，禁言的時間長度（分鐘）",
                "recommend": "3-10 分鐘",
                "type": "int"
            },
            {
                "key": "spam_notify_channel",
                "name": "通知頻道",
                "desc": "洗版事件的通知頻道ID（輸入頻道ID或none來清除）",
                "recommend": "管理頻道ID",
                "type": "channel"
            },
            {
                "key": "spam_response_enabled",
                "name": "啟用回復",
                "desc": "是否在用戶觸發洗版限制時發送回復訊息",
                "recommend": "true 或 false",
                "type": "bool"
            },
            {
                "key": "spam_response_message",
                "name": "回復訊息",
                "desc": "當用戶觸發洗版限制時的回復訊息",
                "recommend": "自訂警告文字",
                "type": "str"
            }
        ]
    }
}

# 建立反向映射，從設定鍵名快速找到對應的分類和設定項
CONFIG_KEY_MAP = {}
for category_id, category in CONFIG_CATEGORIES.items():
    for item in category["items"]:
        CONFIG_KEY_MAP[item["key"]] = {
            "category": category_id,
            "item": item
        }

# ────────────────────────────
# 工具函數
# ────────────────────────────
def _similar(a: str, b: str) -> float:
    """計算兩個字串的相似度"""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

# ────────────────────────────
# 主要類別
# ────────────────────────────
class AntiSpam(ProtectionCog):
    """反垃圾訊息保護模組"""
    
    module_name = "anti_spam"  # 設定模組名稱用於資料庫
    
    def __init__(self, bot: commands.Bot):
        super().__init__(bot)
        self.violate: Dict[int, int] = defaultdict(int)  # 用戶違規次數
        self.message_history: Dict[int, List[Tuple[float, str]]] = defaultdict(list)  # 用戶訊息歷史
        self.sticker_history: Dict[int, List[float]] = defaultdict(list)  # 用戶貼圖歷史
        
        # 新增：統計資料
        self.stats: Dict[int, Dict[str, int]] = defaultdict(lambda: defaultdict(int))  # 伺服器統計資料
        self.action_logs: Dict[int, List[Dict[str, Any]]] = defaultdict(list)  # 伺服器操作日誌
        
        # 啟動背景任務
        self._reset_task.start()

    @commands.Cog.listener()
    async def on_message(self, msg: discord.Message):
        """訊息事件處理"""
        try:
            # 忽略機器人訊息
            if msg.author.bot:
                return
                
            # 忽略私訊
            if not msg.guild:
                return
                
            # 檢查權限
            if not msg.guild.me.guild_permissions.manage_messages:
                return
                
            # 檢查用戶權限
            if isinstance(msg.author, discord.Member) and msg.author.guild_permissions.manage_messages:
                return
                
            now = dt.datetime.now(TW_TZ).timestamp()
            user_id = msg.author.id
            
            # 清理舊記錄
            self._cleanup_history(user_id, now)
            
            # 檢查各種違規
            violations = []
            
            # 頻率檢查
            if await self._match_freq_limit(msg.guild.id, (user_id, 0), now):
                violations.append("頻率過高")
                
            # 重複訊息檢查
            if await self._match_identical(msg.guild.id, (user_id, 1), now):
                violations.append("重複訊息")
                
            # 相似訊息檢查
            if await self._match_similar(msg.guild.id, (user_id, 2), now):
                violations.append("相似訊息")
                
            # 貼圖檢查
            if msg.stickers and await self._match_sticker(msg.guild.id, (user_id, 3), now):
                violations.append("貼圖濫用")
            
            # 記錄訊息
            self.message_history[user_id].append((now, msg.content))
            
            # 記錄貼圖
            if msg.stickers:
                self.sticker_history[user_id].append(now)
            
            # 處理違規
            if violations:
                await self._handle_violation(msg, violations)
                
        except Exception as e:
            friendly_log("訊息處理失敗", e)

    async def _match_freq_limit(self, gid: int, key: Tuple[int, int], now: float) -> bool:
        """檢查頻率限制"""
        try:
            limit = int(await self.get_cfg(gid, "spam_freq_limit") or DEFAULTS["spam_freq_limit"])
            window = float(await self.get_cfg(gid, "spam_freq_window") or DEFAULTS["spam_freq_window"])
            
            user_id = key[0]
            recent_messages = [t for t, _ in self.message_history[user_id] if now - t <= window]
            return len(recent_messages) >= limit
        except Exception as e:
            friendly_log("頻率檢查失敗", e)
            return False

    async def _match_identical(self, gid: int, key: Tuple[int, int], now: float) -> bool:
        """檢查重複訊息"""
        try:
            limit = int(await self.get_cfg(gid, "spam_identical_limit") or DEFAULTS["spam_identical_limit"])
            window = float(await self.get_cfg(gid, "spam_identical_window") or DEFAULTS["spam_identical_window"])
            
            user_id = key[0]
            recent_messages = [(t, content) for t, content in self.message_history[user_id] if now - t <= window]
            
            if len(recent_messages) < limit:
                return False
                
            # 檢查是否有重複
            contents = [content for _, content in recent_messages]
            return len(set(contents)) == 1 and len(contents) >= limit
        except Exception as e:
            friendly_log("重複檢查失敗", e)
            return False

    async def _match_similar(self, gid: int, key: Tuple[int, int], now: float) -> bool:
        """檢查相似訊息"""
        try:
            limit = int(await self.get_cfg(gid, "spam_similar_limit") or DEFAULTS["spam_similar_limit"])
            window = float(await self.get_cfg(gid, "spam_similar_window") or DEFAULTS["spam_similar_window"])
            threshold = float(await self.get_cfg(gid, "spam_similar_threshold") or DEFAULTS["spam_similar_threshold"])
            
            user_id = key[0]
            recent_messages = [(t, content) for t, content in self.message_history[user_id] if now - t <= window]
            
            if len(recent_messages) < limit:
                return False
                
            # 檢查相似度
            contents = [content for _, content in recent_messages]
            for i in range(len(contents)):
                for j in range(i + 1, len(contents)):
                    if _similar(contents[i], contents[j]) >= threshold:
                        return True
            return False
        except Exception as e:
            friendly_log("相似度檢查失敗", e)
            return False

    async def _match_sticker(self, gid: int, key: Tuple[int, int], now: float) -> bool:
        """檢查貼圖濫用"""
        try:
            limit = int(await self.get_cfg(gid, "spam_sticker_limit") or DEFAULTS["spam_sticker_limit"])
            window = float(await self.get_cfg(gid, "spam_sticker_window") or DEFAULTS["spam_sticker_window"])
            
            user_id = key[0]
            recent_stickers = [t for t in self.sticker_history[user_id] if now - t <= window]
            return len(recent_stickers) >= limit
        except Exception as e:
            friendly_log("貼圖檢查失敗", e)
            return False

    def _cleanup_history(self, user_id: int, now: float):
        """清理舊的歷史記錄"""
        try:
            # 清理訊息歷史（保留最近 5 分鐘）
            self.message_history[user_id] = [
                (t, content) for t, content in self.message_history[user_id] 
                if now - t <= 300
            ]
            
            # 清理貼圖歷史（保留最近 5 分鐘）
            self.sticker_history[user_id] = [
                t for t in self.sticker_history[user_id] 
                if now - t <= 300
            ]
        except Exception as e:
            friendly_log("歷史清理失敗", e)

    async def _handle_violation(self, msg: discord.Message, violations: List[str]):
        """處理違規"""
        try:
            # 刪除違規訊息
            try:
                await msg.delete()
            except discord.NotFound:
                pass  # 訊息已被刪除
            except Exception as e:
                friendly_log("刪除違規訊息失敗", e)
            
            # 增加違規次數
            if msg.author.id:
                self.violate[msg.author.id] += 1
            
            # 取得超時設定
            if msg.guild is None:
                return
                
            # 新增：記錄統計 
            for violation in violations:
                stat_key = f"violation_{violation}"
                await self._add_stat(msg.guild.id, stat_key)
            
            timeout_minutes = int(await self.get_cfg(msg.guild.id, "spam_timeout_minutes") or DEFAULTS["spam_timeout_minutes"])
            
            # 執行超時
            timeout_applied = False
            if isinstance(msg.author, discord.Member) and await self._timeout_member(msg.author, timeout_minutes):
                timeout_msg = f"⏰ {msg.author.mention} 因 {', '.join(violations)} 被禁言 {timeout_minutes} 分鐘"
                timeout_applied = True
                # 記錄禁言統計
                await self._add_stat(msg.guild.id, "timeout_applied")
            else:
                timeout_msg = f"⚠️ {msg.author.mention} 因 {', '.join(violations)} 被警告"
                # 記錄警告統計
                await self._add_stat(msg.guild.id, "warning_issued")
            
            # 新增：記錄操作日誌
            action = "timeout" if timeout_applied else "warning"
            details = f"用戶 {msg.author.name}#{msg.author.discriminator}({msg.author.id}) 因 {', '.join(violations)} 被{'禁言' if timeout_applied else '警告'}"
            await self._add_action_log(msg.guild.id, msg.author.id, action, details)
            
            # 發送通知
            if msg.guild:
                await self._send_notification(msg.guild, timeout_msg)
            
            # 新增：發送自定義回復訊息
            response_enabled = await self.get_cfg(msg.guild.id, "spam_response_enabled")
            if response_enabled and response_enabled.lower() != "false":
                try:
                    response_message = await self.get_cfg(msg.guild.id, "spam_response_message") or DEFAULTS["spam_response_message"]
                    await msg.channel.send(f"{msg.author.mention} {response_message}")
                    # 記錄發送回復訊息的統計
                    await self._add_stat(msg.guild.id, "response_sent")
                except Exception as e:
                    friendly_log("發送自定義回復訊息失敗", e)
            
        except Exception as e:
            friendly_log("違規處理失敗", e)

    async def _timeout_member(self, member: discord.Member, minutes: int) -> bool:
        """對成員執行超時"""
        try:
            if not member.guild.me.guild_permissions.moderate_members:
                return False
                
            timeout_until = dt.datetime.now(TW_TZ) + dt.timedelta(minutes=minutes)
            await member.timeout(timeout_until, reason="Anti-Spam 違規")
            return True
        except Exception as e:
            friendly_log("執行超時失敗", e)
            return False

    async def _send_notification(self, guild: discord.Guild, message: str):
        """發送通知"""
        try:
            channel_id = await self.get_cfg(guild.id, "spam_notify_channel")
            if not channel_id:
                return
                
            channel = guild.get_channel(int(channel_id))
            if not channel or not isinstance(channel, discord.TextChannel):
                return
                
            if not channel.permissions_for(guild.me).send_messages:
                return
                
            await channel.send(message)
        except Exception as e:
            friendly_log("發送通知失敗", e)

    # 新增：統計和日誌方法
    async def _add_stat(self, guild_id: int, stat_type: str):
        """增加統計計數"""
        self.stats[guild_id][stat_type] += 1
        self.stats[guild_id]["total"] += 1
        
    async def _add_action_log(self, guild_id: int, user_id: int, action: str, details: str):
        """記錄操作日誌"""
        log_entry = {
            "timestamp": dt.datetime.now(TW_TZ).timestamp(),
            "user_id": user_id,
            "action": action,
            "details": details
        }
        
        # 加入日誌並保持最多 100 筆記錄
        self.action_logs[guild_id].append(log_entry)
        if len(self.action_logs[guild_id]) > 100:
            self.action_logs[guild_id].pop(0)
            
    async def _log_config_change(self, guild_id: int, user_id: int, key: str, old_value: str, new_value: str):
        """記錄設定變更"""
        item_info = CONFIG_KEY_MAP.get(key, {"item": {"name": key}})
        item_name = item_info.get("item", {}).get("name", key)
        await self._add_action_log(
            guild_id,
            user_id,
            "config_change",
            f"變更了「{item_name}」設定：{old_value} → {new_value}"
        )

    # ───────── 指令 ─────────
    @app_commands.command(name="洗版設定面板", description="開啟 Anti-Spam 設定面板")
    @admin_only()
    async def spam_panel(self, itx: discord.Interaction):
        """開啟洗版設定面板"""
        try:
            # 立即回應避免逾時
            await itx.response.defer()
            
            if not itx.guild:
                await itx.followup.send("❌ 此功能只能在伺服器中使用")
                return
                
            # 檢查權限
            if not itx.guild.me.guild_permissions.manage_messages:
                await itx.followup.send("❌ 機器人缺少管理訊息權限")
                return
            
            # 建立面板
            embed = await self._build_embed(itx.guild, "all")  # 預設顯示主面板
            view = _ConfigView(self, itx.guild)
            
            await itx.followup.send(embed=embed, view=view)
            
        except Exception as e:
            friendly_log("開啟洗版設定面板失敗", e)
            try:
                if not itx.response.is_done():
                    await itx.response.send_message("❌ 開啟設定面板失敗", ephemeral=True)
                else:
                    await itx.followup.send("❌ 開啟設定面板失敗")
            except Exception as send_exc:
                friendly_log("發送錯誤訊息失敗", send_exc)

    # ───────── 輔助方法 ─────────
    async def _build_embed(self, guild: discord.Guild, category_id: str = "all") -> discord.Embed:
        """建立設定面板 Embed
        
        Args:
            guild: Discord 伺服器
            category_id: 設定分類ID，為"all"時顯示所有設定
        """
        if category_id == "all":
            embed = discord.Embed(
                title="🛡️ 洗版保護設定面板",
                description="請從下方選單選擇要設定的分類，或點擊按鈕進行操作",
                color=discord.Color.blue(),
                timestamp=dt.datetime.now(TW_TZ)
            )
            
            # 添加基本說明
            embed.add_field(
                name="📋 使用說明",
                value="本面板提供洗版保護相關設定\n請從下拉選單選擇想要設定的類別",
                inline=False
            )
            
            # 顯示設定分類
            for cat_id, cat_data in CONFIG_CATEGORIES.items():
                embed.add_field(
                    name=f"{cat_data['name']}",
                    value=cat_data["desc"],
                    inline=True
                )
            
            # 顯示統計資訊
            stats_data = self.stats.get(guild.id, {})
            total = stats_data.get("total", 0)
            timeouts = stats_data.get("timeout_applied", 0)
            warnings = stats_data.get("warning_issued", 0)
            responses = stats_data.get("response_sent", 0)
            
            stats_text = f"🔢 總觸發次數: **{total}**\n"
            stats_text += f"⏰ 禁言次數: **{timeouts}**\n"
            stats_text += f"⚠️ 警告次數: **{warnings}**\n"
            stats_text += f"💬 回復次數: **{responses}**\n"
            
            embed.add_field(
                name="📊 統計資訊",
                value=stats_text,
                inline=False
            )
        else:
            # 顯示特定分類設定
            category = CONFIG_CATEGORIES.get(category_id)
            if not category:
                return await self._build_embed(guild, "all")
                
            embed = discord.Embed(
                title=f"🛡️ {category['name']}設定",
                description=category["desc"],
                color=discord.Color.blue(),
                timestamp=dt.datetime.now(TW_TZ)
            )
            
            # 添加該分類的所有設定項目
            for item in category["items"]:
                key = item["key"]
                name = item["name"]
                desc = item["desc"]
                recommend = item["recommend"]
                
                try:
                    val = await self._cfg(guild.id, key)
                    if key == "spam_notify_channel":
                        if val and val.isdigit():
                            channel = guild.get_channel(int(val))
                            display_val = channel.mention if channel else f"<#{val}>"
                        else:
                            display_val = "未設定"
                    else:
                        display_val = str(val) if val is not None else "未設定"
                    
                    field_value = f"**當前值**: {display_val}\n"
                    field_value += f"**說明**: {desc}\n"
                    field_value += f"**建議值**: {recommend}"
                    
                    embed.add_field(
                        name=name,
                        value=field_value,
                        inline=False
                    )
                except Exception as e:
                    friendly_log(f"取得設定值失敗（{key}）", e)
                    embed.add_field(
                        name=name,
                        value="❌ 讀取失敗",
                        inline=True
                    )
        
        embed.set_footer(text="設定面板將在 10 分鐘後自動關閉")
        return embed

    async def _cfg(self, gid: int, key: str) -> Any:
        """取得配置值"""
        try:
            val = await self.get_cfg(gid, key)
            if val is None:
                return DEFAULTS.get(key, None)
            elif key == "spam_notify_channel":
                return val if val else None
            elif isinstance(DEFAULTS.get(key), int):
                try:
                    return int(val)
                except (ValueError, TypeError):
                    return DEFAULTS.get(key, 0)
            elif isinstance(DEFAULTS.get(key), float):
                try:
                    return float(val)
                except (ValueError, TypeError):
                    return DEFAULTS.get(key, 0.0)
            else:
                return str(val) if val is not None else DEFAULTS.get(key, None)
                
        except Exception as e:
            friendly_log(f"取得配置失敗（{key}）", e)
            return DEFAULTS.get(key, None)

    # ───────── 每日重置 ─────────
    @tasks.loop(hours=24)
    async def _reset_task(self):
        """每日重置違規次數的背景任務"""
        try:
            self.violate.clear()
            logger.info("AntiSpam 已重置違規次數")
        except Exception as e:
            friendly_log("AntiSpam 重置任務錯誤", e)

    @_reset_task.before_loop
    async def _before_reset_task(self):
        """重置任務前置處理"""
        await self.bot.wait_until_ready()


# ────────────────────────────
# 設定面板 UI (Discord.py 2.5.2 兼容版)
# ────────────────────────────
class _ConfigView(ui.View):
    """反垃圾訊息設定面板"""
    
    def __init__(self, cog: AntiSpam, guild: discord.Guild):
        """初始化設定面板"""
        super().__init__(timeout=600)
        self.cog = cog
        self.guild = guild
        self._processing = False
        self._processing_user: Optional[int] = None
        self.current_category = "all"  # 當前顯示的分類
        
        # 添加分類選單
        self.add_item(_CategorySelect(self))
        
        # 添加按鈕
        if self.current_category == "all":
            # 在主面板添加功能按鈕
            self.add_item(_CloseButton())
            self.add_item(_ResetButton())
            self.add_item(_HelpButton())
            self.add_item(_TestButton())
            self.add_item(_LogButton())
        else:
            # 在分類面板添加設定按鈕
            category = CONFIG_CATEGORIES.get(self.current_category)
            if category:
                for item in category["items"]:
                    self.add_item(_EditButton(item["key"]))
                    
    async def refresh(self, interaction: Optional[discord.Interaction] = None):
        """重新整理面板"""
        # 移除舊項目
        self.clear_items()
        
        # 添加分類選單
        self.add_item(_CategorySelect(self))
        
        # 根據當前分類添加按鈕
        if self.current_category == "all":
            # 在主面板添加功能按鈕
            self.add_item(_CloseButton())
            self.add_item(_ResetButton())
            self.add_item(_HelpButton())
            self.add_item(_TestButton())
            self.add_item(_LogButton())
        else:
            # 在分類面板添加返回按鈕
            self.add_item(_BackButton())
            
            # 添加設定按鈕
            category = CONFIG_CATEGORIES.get(self.current_category)
            if category:
                for item in category["items"]:
                    self.add_item(_EditButton(item["key"]))
        
        # 更新 Embed
        embed = await self.cog._build_embed(self.guild, self.current_category)
        
        # 更新訊息
        if interaction:
            if interaction.response.is_done():
                await interaction.edit_original_response(embed=embed, view=self)
            else:
                await interaction.response.edit_message(embed=embed, view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """互動檢查"""
        try:
            # 檢查是否正在處理
            if self._processing and self._processing_user != interaction.user.id:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "⏳ 其他用戶正在操作中，請稍候...",
                        ephemeral=True
                    )
                return False
                
            # 檢查伺服器
            if not interaction.guild:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ 此功能只能在伺服器中使用",
                        ephemeral=True
                    )
                return False
                
            # 檢查權限
            if not interaction.guild.me.guild_permissions.manage_messages:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ 機器人缺少管理訊息權限",
                        ephemeral=True
                    )
                return False
                
            return True
        except Exception as e:
            friendly_log("互動檢查失敗", e)
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ 權限檢查失敗",
                        ephemeral=True
                    )
            except:
                pass
            return False

    async def on_timeout(self):
        """面板逾時處理"""
        try:
            # 只記錄日誌，不嘗試修改按鈕
            logger.info("洗版設定面板已逾時")
            self.stop()  # 停止視圖
        except Exception as e:
            friendly_log("面板逾時處理失敗", e)


# 分類選單
class _CategorySelect(ui.Select):
    """設定分類選單"""
    
    def __init__(self, view: _ConfigView):
        """初始化分類選單"""
        self.config_view = view
        
        # 建立選項
        options = [
            discord.SelectOption(
                label="全部設定",
                description="顯示所有設定分類",
                value="all",
                default=view.current_category == "all"
            )
        ]
        
        # 添加分類選項
        for cat_id, cat_data in CONFIG_CATEGORIES.items():
            options.append(
                discord.SelectOption(
                    label=cat_data["name"],
                    description=cat_data["desc"][:50], # 限制長度
                    value=cat_id,
                    default=view.current_category == cat_id
                )
            )
            
        super().__init__(
            placeholder="請選擇設定分類...",
            options=options,
            row=0
        )
        
    async def callback(self, interaction: discord.Interaction):
        """選單回調"""
        self.config_view.current_category = self.values[0]
        await self.config_view.refresh(interaction)


# 關閉按鈕
class _CloseButton(ui.Button):
    """關閉面板按鈕"""
    
    def __init__(self):
        """初始化關閉按鈕"""
        super().__init__(
            label="關閉面板",
            style=discord.ButtonStyle.red,
            row=1
        )
        
    async def callback(self, interaction: discord.Interaction):
        """按鈕回調"""
        view: _ConfigView = self.view  # type: ignore
        
        # 創建一個新的空視窗替換舊的
        new_view = ui.View()
        new_view.stop()  # 立即停止新視窗，使其所有元素無法互動
                
        # 修改訊息
        embed = discord.Embed(
            title="🛡️ 洗版保護設定面板",
            description="⚫ 此面板已關閉",
            color=discord.Color.dark_gray()
        )
        await interaction.response.edit_message(embed=embed, view=new_view)
        
        # 停止原視窗
        view.stop()


# 重置按鈕
class _ResetButton(ui.Button):
    """重置設定按鈕"""
    
    def __init__(self):
        """初始化重置按鈕"""
        super().__init__(
            label="重置設定",
            style=discord.ButtonStyle.danger,
            row=1
        )
        
    async def callback(self, interaction: discord.Interaction):
        """按鈕回調"""
        view: _ConfigView = self.view  # type: ignore
        
        # 創建確認視窗
        confirm_view = _ConfirmView(
            view.cog, 
            view.guild, 
            interaction.user.id, 
            "reset_all", 
            "確定要重置所有設定為預設值嗎？這將無法復原"
        )
        await interaction.response.send_message("確認重置", view=confirm_view, ephemeral=True)


# 教學按鈕
class _HelpButton(ui.Button):
    """教學按鈕"""
    
    def __init__(self):
        """初始化教學按鈕"""
        super().__init__(
            label="新手教學",
            style=discord.ButtonStyle.primary,
            row=1
        )
        
    async def callback(self, interaction: discord.Interaction):
        """按鈕回調"""
        view: _ConfigView = self.view  # type: ignore
        
        # 建立教學 Embed
        embed = discord.Embed(
            title="🔰 洗版保護設定教學",
            description="本模組可以保護伺服器免受洗版、垃圾訊息和貼圖濫用的影響",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="🔄 設定流程",
            value=(
                "1. 從下拉選單選擇想要設定的分類\n"
                "2. 點擊對應設定項旁的按鈕進行修改\n"
                "3. 在彈出的視窗中輸入新值\n"
                "4. 完成後可以使用「測試」功能驗證設定效果"
            ),
            inline=False
        )
        
        embed.add_field(
            name="📊 各分類說明",
            value=(
                "**洗版頻率**：控制用戶短時間內發送訊息的頻率\n"
                "**重複/相似訊息**：檢測短時間內的重複或相似訊息\n"
                "**貼圖限制**：防止貼圖濫用\n"
                "**處理動作**：設定違規後的處理方式、通知頻道和自定義回復訊息"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🛠️ 推薦設定",
            value=(
                "一般伺服器：頻率限制 5-8 訊息/10秒，重複限制 3 則/30秒\n"
                "活躍伺服器：頻率限制 8-10 訊息/10秒，重複限制 3-5 則/30秒\n"
                "嚴格管理：頻率限制 3-5 訊息/10秒，重複限制 2 則/30秒"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💬 自定義回復",
            value=(
                "您可以在「處理動作」分類中設定自定義回復訊息：\n"
                "1. 啟用或停用回復訊息功能（啟用回復）\n"
                "2. 設定自訂回復內容（回復訊息）\n"
                "當用戶觸發洗版限制時，機器人將會自動回覆此訊息"
            ),
            inline=False
        )
        
        embed.set_footer(text="如有更多問題，請聯絡機器人管理員")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


# 測試按鈕
class _TestButton(ui.Button):
    """測試功能按鈕"""
    
    def __init__(self):
        """初始化測試按鈕"""
        super().__init__(
            label="測試設定",
            style=discord.ButtonStyle.secondary,
            row=1
        )
        
    async def callback(self, interaction: discord.Interaction):
        """按鈕回調"""
        view: _ConfigView = self.view  # type: ignore
        
        # 第一步回應
        await interaction.response.send_message(
            "⚙️ 洗版保護設定測試工具\n請選擇要測試的功能：",
            view=_TestSelectView(view.cog, view.guild),
            ephemeral=True
        )


# 日誌按鈕
class _LogButton(ui.Button):
    """查看日誌按鈕"""
    
    def __init__(self):
        """初始化日誌按鈕"""
        super().__init__(
            label="操作日誌",
            style=discord.ButtonStyle.secondary,
            row=1
        )
        
    async def callback(self, interaction: discord.Interaction):
        """按鈕回調"""
        view: _ConfigView = self.view  # type: ignore
        
        # 建立日誌 Embed
        logs = view.cog.action_logs.get(view.guild.id, [])
        
        embed = discord.Embed(
            title="📋 洗版保護操作日誌",
            description=f"最近 {len(logs)} 筆操作記錄",
            color=discord.Color.blue()
        )
        
        # 取最近 10 筆日誌
        recent_logs = logs[-10:] if logs else []
        
        if not recent_logs:
            embed.add_field(
                name="無日誌記錄",
                value="暫無任何操作記錄",
                inline=False
            )
        else:
            for i, log in enumerate(recent_logs):
                timestamp = dt.datetime.fromtimestamp(log["timestamp"], TW_TZ)
                time_str = timestamp.strftime("%Y/%m/%d %H:%M")
                
                user_id = log["user_id"]
                user = view.guild.get_member(user_id)
                user_name = user.display_name if user else f"用戶 (ID: {user_id})"
                
                embed.add_field(
                    name=f"{i+1}. {time_str} - {log['action']}",
                    value=f"{user_name}: {log['details']}",
                    inline=False
                )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


# 返回按鈕
class _BackButton(ui.Button):
    """返回主面板按鈕"""
    
    def __init__(self):
        """初始化返回按鈕"""
        super().__init__(
            label="返回主面板",
            style=discord.ButtonStyle.secondary,
            row=1
        )
        
    async def callback(self, interaction: discord.Interaction):
        """按鈕回調"""
        view: _ConfigView = self.view  # type: ignore
        view.current_category = "all"
        await view.refresh(interaction)


class _EditButton(ui.Button):
    """設定編輯按鈕"""
    
    def __init__(self, key: str):
        """初始化編輯按鈕"""
        # 取得設定項目資訊
        item_info = CONFIG_KEY_MAP.get(key, {"item": {"name": CH_NAMES.get(key, key)}})
        item = item_info.get("item", {"name": CH_NAMES.get(key, key)})
        
        super().__init__(label=f"設定 {item['name']}", style=discord.ButtonStyle.primary)
        self.key = key

    async def callback(self, interaction: discord.Interaction):
        """按鈕回調"""
        view: _ConfigView = self.view  # type: ignore
        
        try:
            # 檢查互動權限
            if not await view.interaction_check(interaction):
                return
                
            # 設定處理狀態
            view._processing = True
            view._processing_user = interaction.user.id
            
            # 創建模態框
            modal = _EditModal(view, self.key)
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            friendly_log("按鈕回調失敗", e)
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ 開啟設定面板失敗", ephemeral=True)
                else:
                    await interaction.followup.send("❌ 開啟設定面板失敗", ephemeral=True)
            except:
                pass
            finally:
                # 清除處理狀態
                view._processing = False
                view._processing_user = None


# 確認視窗
class _ConfirmView(ui.View):
    """確認操作視窗"""
    
    def __init__(self, cog: AntiSpam, guild: discord.Guild, user_id: int, action: str, confirm_text: str):
        """初始化確認視窗
        
        Args:
            cog: AntiSpam 實例
            guild: Discord 伺服器
            user_id: 使用者 ID
            action: 操作類型
            confirm_text: 確認訊息
        """
        super().__init__(timeout=60)
        self.cog = cog
        self.guild = guild
        self.user_id = user_id
        self.action = action
        self.confirm_text = confirm_text
        self.confirmed = False
        
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """檢查互動是否來自同一用戶"""
        return interaction.user.id == self.user_id
        
    @ui.button(label="確認", style=discord.ButtonStyle.danger, row=0)
    async def confirm_button(self, interaction: discord.Interaction, button: ui.Button):
        """確認按鈕回調"""
        self.confirmed = True
        
        if self.action == "reset_all":
            # 重置所有設定
            await self._reset_all_settings(interaction)
        
        # 創建一個新的空視窗替換舊的
        view = ui.View()
        view.stop()  # 立即停止新視窗，使其所有元素無法互動
            
        await interaction.response.edit_message(content="✅ 已確認操作", view=view)
        self.stop()  # 停止原視窗
        
    @ui.button(label="取消", style=discord.ButtonStyle.secondary, row=0)
    async def cancel_button(self, interaction: discord.Interaction, button: ui.Button):
        """取消按鈕回調"""
        # 創建一個新的空視窗替換舊的
        view = ui.View()
        view.stop()  # 立即停止新視窗，使其所有元素無法互動
            
        await interaction.response.edit_message(content="❌ 已取消操作", view=view)
        self.stop()  # 停止原視窗
        
    async def _reset_all_settings(self, interaction: discord.Interaction):
        """重置所有設定為預設值"""
        try:
            # 記錄舊值
            old_values = {}
            for key in DEFAULTS.keys():
                old_values[key] = await self.cog.get_cfg(self.guild.id, key)
            
            # 重置為預設值
            for key, default_value in DEFAULTS.items():
                await self.cog.set_cfg(self.guild.id, key, str(default_value))
            
            # 記錄操作日誌
            await self.cog._add_action_log(
                self.guild.id,
                interaction.user.id,
                "reset_settings",
                f"已將所有設定重置為預設值"
            )
            
            await interaction.followup.send("✅ 所有設定已重置為預設值", ephemeral=True)
        except Exception as e:
            friendly_log("重置設定失敗", e)
            await interaction.followup.send("❌ 重置設定失敗，請重試", ephemeral=True)


# 測試功能選單
class _TestSelectView(ui.View):
    """測試功能選單"""
    
    def __init__(self, cog: AntiSpam, guild: discord.Guild):
        """初始化測試選單"""
        super().__init__(timeout=60)
        self.cog = cog
        self.guild = guild
    
    @ui.select(
        placeholder="選擇要測試的功能",
        options=[
            discord.SelectOption(
                label="訊息頻率測試",
                description="測試目前的頻率限制設定",
                value="frequency"
            ),
            discord.SelectOption(
                label="重複訊息測試",
                description="測試目前的重複訊息限制",
                value="identical"
            ),
            discord.SelectOption(
                label="相似訊息測試",
                description="測試目前的相似訊息檢測",
                value="similar"
            ),
            discord.SelectOption(
                label="貼圖限制測試",
                description="測試目前的貼圖限制",
                value="sticker"
            )
        ]
    )
    async def select_test(self, interaction: discord.Interaction, select: ui.Select):
        """測試功能選擇回調"""
        test_type = select.values[0]
        
        # 停用選單避免重複操作
        select.disabled = True
        await interaction.response.edit_message(view=self)
        
        # 根據選擇的測試類型顯示對應的設定值和執行模擬測試
        if test_type == "frequency":
            limit = await self.cog._cfg(self.guild.id, "spam_freq_limit")
            window = await self.cog._cfg(self.guild.id, "spam_freq_window")
            await self._run_simulation_test(
                interaction,
                "訊息頻率測試", 
                f"目前設定為：每 {window} 秒內最多 {limit} 則訊息\n\n",
                test_type
            )
        elif test_type == "identical":
            limit = await self.cog._cfg(self.guild.id, "spam_identical_limit")
            window = await self.cog._cfg(self.guild.id, "spam_identical_window")
            await self._run_simulation_test(
                interaction,
                "重複訊息測試", 
                f"目前設定為：每 {window} 秒內最多 {limit} 則相同內容的訊息\n\n",
                test_type
            )
        elif test_type == "similar":
            limit = await self.cog._cfg(self.guild.id, "spam_similar_limit")
            window = await self.cog._cfg(self.guild.id, "spam_similar_window")
            threshold = await self.cog._cfg(self.guild.id, "spam_similar_threshold")
            await self._run_simulation_test(
                interaction,
                "相似訊息測試", 
                f"目前設定為：每 {window} 秒內最多 {limit} 則相似度超過 {threshold} 的訊息\n\n",
                test_type
            )
        elif test_type == "sticker":
            limit = await self.cog._cfg(self.guild.id, "spam_sticker_limit")
            window = await self.cog._cfg(self.guild.id, "spam_sticker_window")
            await self._run_simulation_test(
                interaction,
                "貼圖限制測試", 
                f"目前設定為：每 {window} 秒內最多 {limit} 則含貼圖的訊息\n\n",
                test_type
            )
    
    async def _run_simulation_test(self, interaction: discord.Interaction, title: str, config_info: str, test_type: str):
        """執行模擬測試"""
        try:
            # 使用安全的方式獲取用戶ID和當前時間
            try:
                user_id = interaction.user.id if interaction.user else 0
                if user_id == 0:
                    await interaction.followup.send("❌ 無法獲取使用者資訊", ephemeral=True)
                    return
                
                # 檢查 guild
                if not interaction.guild:
                    await interaction.followup.send("❌ 此功能只能在伺服器中使用", ephemeral=True)
                    return
                    
                guild_id = interaction.guild.id
            except Exception:
                await interaction.followup.send("❌ 無法獲取使用者或伺服器資訊", ephemeral=True)
                return
            
            # 獲取當前時間戳    
            now = dt.datetime.now(TW_TZ).timestamp()
            result = False  # 預設結果為失敗
                
            try:
                # 根據測試類型執行不同的模擬測試
                if test_type == "frequency":
                    # 獲取頻率限制設定
                    limit = int(await self.cog._cfg(guild_id, "spam_freq_limit"))
                    window = float(await self.cog._cfg(guild_id, "spam_freq_window"))
                    
                    # 清空訊息歷史
                    with contextlib.suppress(Exception):
                        if user_id in self.cog.message_history:
                            self.cog.message_history[user_id].clear()
                    
                    # 模擬快速發送訊息
                    try:
                        for i in range(limit + 1):
                            self.cog.message_history[user_id].append((now, f"模擬測試訊息 {i+1}"))
                        
                        # 檢查是否觸發限制
                        result = await self.cog._match_freq_limit(guild_id, (user_id, 0), now)
                    except Exception as e:
                        friendly_log(f"頻率測試失敗: {e}", e)
                        
                elif test_type == "identical":
                    # 獲取重複訊息限制設定
                    limit = int(await self.cog._cfg(guild_id, "spam_identical_limit"))
                    window = float(await self.cog._cfg(guild_id, "spam_identical_window"))
                    
                    # 清空訊息歷史
                    with contextlib.suppress(Exception):
                        if user_id in self.cog.message_history:
                            self.cog.message_history[user_id].clear()
                    
                    # 模擬發送重複訊息
                    try:
                        for i in range(limit + 1):
                            self.cog.message_history[user_id].append((now, "重複的測試訊息"))
                        
                        # 檢查是否觸發限制
                        result = await self.cog._match_identical(guild_id, (user_id, 1), now)
                    except Exception as e:
                        friendly_log(f"重複訊息測試失敗: {e}", e)
                        
                elif test_type == "similar":
                    # 獲取相似訊息限制設定
                    limit = int(await self.cog._cfg(guild_id, "spam_similar_limit"))
                    window = float(await self.cog._cfg(guild_id, "spam_similar_window"))
                    threshold = float(await self.cog._cfg(guild_id, "spam_similar_threshold"))
                    
                    # 清空訊息歷史
                    with contextlib.suppress(Exception):
                        if user_id in self.cog.message_history:
                            self.cog.message_history[user_id].clear()
                    
                    # 模擬發送相似訊息
                    try:
                        base_msg = "這是一條測試訊息，檢測相似度功能"
                        for i in range(limit + 1):
                            self.cog.message_history[user_id].append((now, f"{base_msg} {i+1}"))
                        
                        # 檢查是否觸發限制
                        result = await self.cog._match_similar(guild_id, (user_id, 2), now)
                    except Exception as e:
                        friendly_log(f"相似訊息測試失敗: {e}", e)
                        
                elif test_type == "sticker":
                    # 獲取貼圖限制設定
                    limit = int(await self.cog._cfg(guild_id, "spam_sticker_limit"))
                    window = float(await self.cog._cfg(guild_id, "spam_sticker_window"))
                    
                    # 清空貼圖歷史
                    with contextlib.suppress(Exception):
                        if user_id in self.cog.sticker_history:
                            self.cog.sticker_history[user_id].clear()
                    
                    # 模擬發送含貼圖訊息
                    try:
                        for i in range(limit + 1):
                            self.cog.sticker_history[user_id].append(now)
                        
                        # 檢查是否觸發限制
                        result = await self.cog._match_sticker(guild_id, (user_id, 3), now)
                    except Exception as e:
                        friendly_log(f"貼圖限制測試失敗: {e}", e)
                
                # 顯示測試結果
                embed = discord.Embed(
                    title=f"⚙️ {title}結果",
                    description=config_info + (
                        f"✅ **測試成功！** 檢測系統已正確識別出違規行為。\n\n"
                        f"在實際情況中，繼續發送此類訊息將導致訊息被刪除，並可能觸發警告或禁言措施。"
                        if result else
                        f"❌ **測試失敗！** 檢測系統沒有識別出違規行為。\n\n"
                        f"請檢查您的設定值是否太寬鬆，或聯絡技術支援進行協助。"
                    ),
                    color=discord.Color.green() if result else discord.Color.red()
                )
                
                # 獲取回復訊息設定
                response_enabled = await self.cog.get_cfg(guild_id, "spam_response_enabled")
                response_message = await self.cog.get_cfg(guild_id, "spam_response_message") or DEFAULTS["spam_response_message"]
                response_status = "已啟用" if response_enabled and response_enabled.lower() != "false" else "已停用"
                
                embed.add_field(
                    name="📋 技術資訊",
                    value=(
                        f"測試類型: {test_type}\n"
                        f"結果: {'已觸發保護' if result else '未觸發保護'}\n"
                        f"時間戳: {dt.datetime.now(TW_TZ).strftime('%Y-%m-%d %H:%M:%S')}"
                    ),
                    inline=False
                )
                
                embed.add_field(
                    name="💬 回復訊息設定",
                    value=(
                        f"狀態: **{response_status}**\n"
                        f"訊息內容: {response_message}"
                    ),
                    inline=False
                )
                
                # 清理測試數據
                with contextlib.suppress(Exception):
                    if test_type != "sticker":
                        if user_id in self.cog.message_history:
                            self.cog.message_history[user_id].clear()
                    else:
                        if user_id in self.cog.sticker_history:
                            self.cog.sticker_history[user_id].clear()
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                
                # 記錄測試日誌
                try:
                    await self.cog._add_action_log(
                        self.guild.id,
                        user_id,
                        "simulation_test",
                        f"執行了 {title}，結果：{'成功' if result else '失敗'}"
                    )
                except Exception as e:
                    friendly_log(f"記錄測試日誌失敗: {e}", e)
                    
            except Exception as e:
                friendly_log(f"測試執行中發生錯誤: {e}", e)
                error_embed = discord.Embed(
                    title="⚠️ 測試執行錯誤",
                    description=f"執行測試時發生意外錯誤。錯誤類型：{type(e).__name__}",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=error_embed, ephemeral=True)
                
        except Exception as e:
            friendly_log(f"執行模擬測試失敗（{test_type}）", e)
            try:
                error_embed = discord.Embed(
                    title="⚠️ 測試執行失敗",
                    description=f"執行 {title} 時發生錯誤。請向管理員報告此問題。\n\n錯誤類型：{type(e).__name__}",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=error_embed, ephemeral=True)
            except:
                pass


# 更新版的編輯模態框
class _EditModal(ui.Modal):
    """設定編輯模態框"""
    
    def __init__(self, view: _ConfigView, key: str):
        """初始化模態框"""
        # 獲取設定項詳細資訊
        item_info = CONFIG_KEY_MAP.get(key, {"item": {"name": CH_NAMES.get(key, key)}})
        item_data = item_info.get("item", {"name": CH_NAMES.get(key, key), "desc": "請輸入設定值"})
        
        super().__init__(title=f"設定 {item_data['name']}")
        self.view = view
        self.key = key
        self.item_data = item_data
        
        # 取得當前值
        self.old_value = None  # 初始化，將在提交時獲取實際值
        
        # 創建文字輸入欄位（帶說明）
        placeholder = f"{item_data.get('desc', '請輸入值')}，建議值: {item_data.get('recommend', '視情況而定')}"
        self.new_value = ui.TextInput(
            label=f"{item_data['name']} 設定", 
            required=True,
            placeholder=placeholder[:100],  # 限制長度
            max_length=100
        )
        self.add_item(self.new_value)
        
    async def on_submit(self, interaction: discord.Interaction):
        """模態框提交處理"""
        try:
            # 立即回應避免逾時
            await interaction.response.defer(ephemeral=True)
            
            try:
                # 獲取舊值
                self.old_value = await self.view.cog.get_cfg(self.view.guild.id, self.key)
                val = self.new_value.value.strip()
                
                # 根據設定類型處理
                if self.key == "spam_notify_channel":
                    if val.lower() in ["none", "無", "0", ""]:
                        await self.view.cog.set_cfg(self.view.guild.id, self.key, "")
                        await interaction.followup.send("✅ 通知頻道已清除")
                        
                        # 記錄變更
                        await self.view.cog._log_config_change(
                            self.view.guild.id, 
                            interaction.user.id,
                            self.key, 
                            self.old_value or "無", 
                            "已清除"
                        )
                    elif val.isdigit():
                        channel = self.view.guild.get_channel(int(val))
                        if channel and isinstance(channel, discord.TextChannel):
                            await self.view.cog.set_cfg(self.view.guild.id, self.key, val)
                            await interaction.followup.send(f"✅ 通知頻道已設定為 {channel.mention}")
                            
                            # 記錄變更
                            await self.view.cog._log_config_change(
                                self.view.guild.id, 
                                interaction.user.id,
                                self.key, 
                                self.old_value or "無", 
                                f"{channel.name} ({val})"
                            )
                        else:
                            await interaction.followup.send("❌ 找不到指定的文字頻道")
                            return
                    else:
                        await interaction.followup.send("❌ 請輸入頻道 ID 或 'none'")
                        return
                
                elif self.key == "spam_response_enabled":
                    val_lower = val.lower()
                    if val_lower in ["true", "yes", "開啟", "啟用", "1"]:
                        await self.view.cog.set_cfg(self.view.guild.id, self.key, "true")
                        await interaction.followup.send("✅ 已啟用自定義回復訊息")
                        
                        # 記錄變更
                        await self.view.cog._log_config_change(
                            self.view.guild.id,
                            interaction.user.id,
                            self.key,
                            self.old_value or "預設值",
                            "true"
                        )
                    elif val_lower in ["false", "no", "關閉", "停用", "0"]:
                        await self.view.cog.set_cfg(self.view.guild.id, self.key, "false")
                        await interaction.followup.send("✅ 已停用自定義回復訊息")
                        
                        # 記錄變更
                        await self.view.cog._log_config_change(
                            self.view.guild.id,
                            interaction.user.id,
                            self.key,
                            self.old_value or "預設值",
                            "false"
                        )
                    else:
                        await interaction.followup.send("❌ 請輸入 true 或 false")
                        return
                        
                elif self.item_data.get("type") == "int" or isinstance(DEFAULTS.get(self.key), int):
                    try:
                        int_val = int(val)
                        if int_val < 0:
                            await interaction.followup.send("❌ 數值不能為負數")
                            return
                        await self.view.cog.set_cfg(self.view.guild.id, self.key, str(int_val))
                        await interaction.followup.send(f"✅ {self.item_data['name']} 已更新為 {int_val}")
                        
                        # 記錄變更
                        await self.view.cog._log_config_change(
                            self.view.guild.id, 
                            interaction.user.id,
                            self.key, 
                            self.old_value or "預設值", 
                            str(int_val)
                        )
                    except ValueError:
                        await interaction.followup.send("❌ 請輸入有效的整數")
                        return
                        
                elif self.item_data.get("type") == "float" or isinstance(DEFAULTS.get(self.key), float):
                    try:
                        float_val = float(val)
                        if self.key == "spam_similar_threshold" and (float_val < 0 or float_val > 1):
                            await interaction.followup.send("❌ 相似度閾值必須在 0-1 之間")
                            return
                        await self.view.cog.set_cfg(self.view.guild.id, self.key, str(float_val))
                        await interaction.followup.send(f"✅ {self.item_data['name']} 已更新為 {float_val}")
                        
                        # 記錄變更
                        await self.view.cog._log_config_change(
                            self.view.guild.id, 
                            interaction.user.id,
                            self.key, 
                            self.old_value or "預設值", 
                            str(float_val)
                        )
                    except ValueError:
                        await interaction.followup.send("❌ 請輸入有效的小數")
                        return
                        
                else:
                    await self.view.cog.set_cfg(self.view.guild.id, self.key, val)
                    await interaction.followup.send(f"✅ {self.item_data['name']} 已更新為 {val}")
                    
                    # 記錄變更
                    await self.view.cog._log_config_change(
                        self.view.guild.id, 
                        interaction.user.id,
                        self.key, 
                        self.old_value or "預設值", 
                        val
                    )
                
                # 如果正在分類視圖，刷新面板
                if self.view.current_category != "all":
                    await self.view.refresh(interaction)
                    
            except Exception as e:
                friendly_log(f"更新設定失敗（{self.key}）", e)
                await interaction.followup.send("❌ 更新設定失敗，請檢查輸入格式")
                
        except Exception as e:
            friendly_log(f"模態框提交處理失敗（{self.key}）", e)
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ 處理失敗，請重試", ephemeral=True)
                else:
                    await interaction.followup.send("❌ 處理失敗，請重試", ephemeral=True)
            except:
                pass
        finally:
            # 清除處理狀態
            self.view._processing = False
            self.view._processing_user = None


# ────────────────────────────
# 模組設定
# ────────────────────────────
async def setup(bot: commands.Bot):
    """設定 AntiSpam 模組"""
    logger.info("執行 anti_spam setup()")
    try:
        cog = AntiSpam(bot)
        await bot.add_cog(cog)
        logger.info("Anti-Spam 模組已載入，版本 1.5.1 (自定義回復訊息)")
    except Exception as e:
        logger.error(f"Anti-Spam 模組載入失敗: {e}")
        raise e