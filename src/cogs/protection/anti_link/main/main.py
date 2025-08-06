"""
反惡意連結保護模組主要邏輯協調中心
- 作為模組的核心,協調各個子模組的工作
- 處理惡意連結檢測和威脅情資更新
- 管理黑名單快取和白名單過濾
"""

import csv
import io
from collections import defaultdict
from typing import Any

import aiohttp
import discord
import tldextract
from discord import app_commands
from discord.ext import commands, tasks

# 使用統一的核心模塊
from ....core import create_error_handler, setup_module_logger
from ...base import ProtectionCog, admin_only
from ..config.config import (
    DEFAULT_WHITELIST,
    DEFAULTS,
    THREAT_FEEDS,
    URL_PATTERN,
    extract_domain,
    is_whitelisted,
    normalize_domain,
    parse_domain_list,
)
from ..database.database import AntiLinkDatabase
from ..panel.embeds.config_embed import ConfigEmbed
from ..panel.main_view import AntiLinkMainView

# 常數定義
HTTP_OK_STATUS = 200
MIN_CSV_COLUMNS = 2

# 設置模塊日誌記錄器
logger = setup_module_logger("anti_link")
error_handler = create_error_handler("anti_link", logger)


class AntiLink(ProtectionCog):
    """
    反惡意連結保護模組

    負責檢測和處理各種類型的惡意連結,包括:
    - URL 檢測和解析
    - 威脅情資整合
    - 白名單/黑名單管理
    - 自動更新黑名單
    """

    module_name = "anti_link"

    def __init__(self, bot: commands.Bot):
        """
        初始化反惡意連結保護系統

        Args:
            bot: Discord 機器人實例
        """
        super().__init__(bot)
        self.db = AntiLinkDatabase(self)

        # 快取管理
        self._remote_blacklist: set[str] = set()  # 遠端黑名單快取
        self._manual_blacklist: dict[int, set[str]] = {}  # 手動黑名單快取
        self._whitelist_cache: dict[int, set[str]] = {}  # 白名單快取

        # 統計資料
        self.stats: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    async def cog_load(self):
        """Cog 載入時的初始化"""
        try:
            await self.db.init_db()
            # 載入黑名單快取
            await self._refresh_blacklist()
            # 啟動背景任務
            self._refresh_task.start()
            logger.info("[反惡意連結]模組載入完成")
        except Exception as exc:
            logger.error(f"[反惡意連結]模組載入失敗: {exc}")
            raise

    async def cog_unload(self):
        """Cog 卸載時的清理"""
        try:
            # 停止背景任務
            self._refresh_task.cancel()
            logger.info("[反惡意連結]模組卸載完成")
        except Exception as exc:
            logger.error(f"[反惡意連結]模組卸載失敗: {exc}")

    # ───────── 事件處理 ─────────
    @commands.Cog.listener()
    async def on_message(self, msg: discord.Message):
        """處理新訊息事件,檢測惡意連結"""
        try:
            # 基本檢查
            if msg.author.bot or not msg.guild:
                return

            # 檢查模組是否啟用
            enabled = await self.get_config(
                msg.guild.id, "enabled", DEFAULTS["enabled"]
            )
            if not enabled or enabled.lower() != "true":
                return

            whitelist_admins = await self.get_config(
                msg.guild.id, "whitelist_admins", DEFAULTS["whitelist_admins"]
            )
            if (
                whitelist_admins
                and whitelist_admins.lower() == "true"
                and isinstance(msg.author, discord.Member)
                and msg.author.guild_permissions.manage_messages
            ):
                return

            # 檢測 URL
            urls = await self._extract_urls(msg)
            if not urls:
                return

            # 取得白名單和黑名單
            whitelist = await self._get_whitelist(msg.guild.id)
            manual_blacklist = await self._get_manual_blacklist(msg.guild.id)

            # 檢查每個 URL
            malicious_urls = []
            for url in urls:
                if await self._is_malicious_url(url, whitelist, manual_blacklist):
                    malicious_urls.append(url)

            # 處理惡意連結
            if malicious_urls:
                await self._handle_malicious_links(msg, malicious_urls)

        except Exception as exc:
            error_handler.log_error(
                exc, f"處理訊息事件 - {msg.author.id}", "MESSAGE_HANDLER_ERROR"
            )

    async def _extract_urls(self, msg: discord.Message) -> list[str]:
        """從訊息中提取所有 URL"""
        urls = []

        # 從訊息內容提取
        if msg.content:
            urls.extend(URL_PATTERN.findall(msg.content))

        # 檢查嵌入連結
        if msg.guild:
            check_embeds = await self.get_config(
                msg.guild.id, "check_embeds", DEFAULTS["check_embeds"]
            )
            if check_embeds and check_embeds.lower() == "true":
                for embed in msg.embeds:
                    if embed.url:
                        urls.append(embed.url)
                    if embed.author and embed.author.url:
                        urls.append(embed.author.url)
                    if embed.footer and embed.footer.icon_url:
                        urls.append(embed.footer.icon_url)
                    for field in embed.fields:
                        if field.value:
                            urls.extend(URL_PATTERN.findall(field.value))

        return list(set(urls))  # 去重

    async def _is_malicious_url(
        self, url: str, whitelist: set[str], manual_blacklist: set[str]
    ) -> bool:
        """檢查 URL 是否為惡意連結"""
        try:
            domain = extract_domain(url)
            if not domain:
                return False

            # 整合所有檢查邏輯
            checks = [
                lambda: is_whitelisted(domain, whitelist),
                lambda: domain in manual_blacklist or domain in self._remote_blacklist,
                lambda: self._check_registered_domain(domain, manual_blacklist),
            ]
            if checks[0]():
                return False

            # 黑名單檢查
            if checks[1]():
                return True

            # 註冊網域檢查
            return bool(checks[2]())

        except Exception as exc:
            logger.error(f"[反惡意連結]檢查 URL 失敗: {exc}")
            return False

    def _check_registered_domain(self, domain: str, manual_blacklist: set[str]) -> bool:
        """檢查註冊網域是否在黑名單中"""
        try:
            registered_domain = tldextract.extract(domain).registered_domain
            return (
                registered_domain
                and registered_domain != domain
                and (
                    registered_domain in manual_blacklist
                    or registered_domain in self._remote_blacklist
                )
            )
        except Exception:
            return False

    async def _handle_malicious_links(
        self, msg: discord.Message, malicious_urls: list[str]
    ):
        """處理惡意連結"""
        try:
            if not msg.guild:
                return

            # 刪除包含惡意連結的訊息
            try:
                await msg.delete()
            except discord.NotFound:
                pass
            except discord.Forbidden:
                logger.warning(f"[反惡意連結]無權刪除訊息: {msg.id}")

            # 記錄統計資料
            await self._add_stat(msg.guild.id, "links_blocked", len(malicious_urls))
            await self._add_stat(msg.guild.id, "messages_deleted")

            # 發送刪除訊息
            delete_message = await self.get_config(
                msg.guild.id, "delete_message", DEFAULTS["delete_message"]
            )
            if delete_message:
                try:
                    embed = discord.Embed(
                        description=delete_message, color=discord.Color.red()
                    )
                    await msg.channel.send(embed=embed, delete_after=10)
                except discord.Forbidden:
                    pass

            # 發送通知
            if msg.guild:
                notify_channel_id = await self.get_config(
                    msg.guild.id, "notify_channel", ""
                )
                if notify_channel_id:
                    try:
                        channel = msg.guild.get_channel(int(notify_channel_id))
                        if channel and isinstance(channel, discord.TextChannel):
                            channel_name = getattr(channel, "name", "未知頻道")
                            await channel.send(
                                f"⚠️ 在 #{channel_name} 攔截惡意連結:{', '.join(malicious_urls[:3])}"
                            )
                    except Exception:
                        pass

            # 記錄操作日誌
            await self.db.add_action_log(
                msg.guild.id,
                msg.author.id,
                "malicious_link_blocked",
                f"阻止了 {len(malicious_urls)} 個惡意連結",
            )

            logger.info(
                f"[反惡意連結]阻止惡意連結: {msg.author.id} - {len(malicious_urls)} 個連結"
            )

        except Exception as exc:
            error_handler.log_error(
                exc, f"處理惡意連結 - {msg.author.id}", "MALICIOUS_LINK_HANDLER_ERROR"
            )

    # ───────── 快取管理 ─────────
    async def _get_whitelist(self, guild_id: int) -> set[str]:
        """取得白名單"""
        if guild_id not in self._whitelist_cache:
            whitelist_str = await self.get_config(guild_id, "whitelist", "")
            custom_whitelist = parse_domain_list(whitelist_str or "")
            self._whitelist_cache[guild_id] = DEFAULT_WHITELIST | custom_whitelist

        return self._whitelist_cache[guild_id]

    async def _get_manual_blacklist(self, guild_id: int) -> set[str]:
        """取得手動黑名單"""
        if guild_id not in self._manual_blacklist:
            blacklist_str = await self.get_config(guild_id, "blacklist", "")
            self._manual_blacklist[guild_id] = parse_domain_list(blacklist_str or "")

        return self._manual_blacklist[guild_id]

    def _clear_cache(self, guild_id: int | None = None):
        """清理快取"""
        if guild_id:
            self._whitelist_cache.pop(guild_id, None)
            self._manual_blacklist.pop(guild_id, None)
        else:
            self._whitelist_cache.clear()
            self._manual_blacklist.clear()

    # ───────── 威脅情資更新 ─────────
    async def _refresh_blacklist(self):
        """刷新黑名單"""
        try:
            # 檢查自動更新設定
            auto_update = await self.get_config(
                0, "auto_update", DEFAULTS["auto_update"]
            )  # 使用 guild_id=0 作為全域設定
            if not auto_update or auto_update.lower() != "true":
                logger.info("[反惡意連結]自動更新已停用")
                return

            logger.info("[反惡意連結]開始更新威脅情資...")

            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=60)
            ) as session:
                all_domains = set()

                for feed_name, feed_config in THREAT_FEEDS.items():
                    if not feed_config.get("enabled", True):
                        continue

                    try:
                        domains = await self._fetch_threat_feed(
                            session, feed_name, feed_config
                        )
                        if domains:
                            all_domains.update(domains)
                            await self.db.update_blacklist_cache(domains, feed_name)
                            logger.info(
                                f"[反惡意連結]更新 {feed_name}: {len(domains)} 個網域"
                            )
                    except Exception as exc:
                        logger.error(f"[反惡意連結]更新 {feed_name} 失敗: {exc}")

                # 更新內存快取
                self._remote_blacklist = await self.db.get_blacklist_cache()

                logger.info(
                    f"[反惡意連結]威脅情資更新完成: 總計 {len(self._remote_blacklist)} 個惡意網域"
                )

        except Exception as exc:
            error_handler.log_error(exc, "威脅情資更新", "BLACKLIST_UPDATE_ERROR")

    async def _fetch_threat_feed(
        self,
        session: aiohttp.ClientSession,
        feed_name: str,
        feed_config: dict[str, Any],
    ) -> set[str]:
        """取得威脅情資"""
        try:
            url = feed_config["url"]
            format_type = feed_config.get("format", "text")

            async with session.get(url) as response:
                if response.status != HTTP_OK_STATUS:
                    logger.warning(
                        f"[反惡意連結]{feed_name} 回應狀態: {response.status}"
                    )
                    return set()

                content = await response.text()

                domains = set()

                if format_type == "text":
                    for raw_line in content.split("\n"):
                        line = raw_line.strip()
                        if line and not line.startswith("#"):
                            domain = extract_domain(line)
                            if domain:
                                domains.add(normalize_domain(domain))

                elif format_type == "csv":
                    reader = csv.reader(io.StringIO(content))
                    for row in reader:
                        if len(row) > MIN_CSV_COLUMNS and row[2]:  # 假設 URL 在第三列
                            domain = extract_domain(row[2])
                            if domain:
                                domains.add(normalize_domain(domain))

                return domains

        except Exception as exc:
            logger.error(f"[反惡意連結]取得 {feed_name} 失敗: {exc}")
            return set()

    # ───────── 統計管理 ─────────
    async def _add_stat(self, guild_id: int, stat_type: str, count: int = 1):
        """添加統計資料"""
        try:
            self.stats[guild_id][stat_type] += count
            await self.db.add_stat(guild_id, stat_type, count)
        except Exception as exc:
            logger.error(f"[反惡意連結]添加統計失敗: {exc}")

    # ───────── 斜線指令 ─────────
    @app_commands.command(name="連結保護面板", description="開啟反惡意連結保護設定面板")
    @admin_only()
    async def link_panel(self, interaction: discord.Interaction):
        """開啟反惡意連結保護設定面板"""
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ 本指令只能在伺服器中使用.", ephemeral=True
            )
            return

        try:
            # 創建配置嵌入
            config_embed = ConfigEmbed(self, interaction.guild.id)
            embed = await config_embed.create_embed()

            # 創建面板視圖
            view = AntiLinkMainView(self, interaction.guild.id, interaction.user.id)

            # 發送面板
            await interaction.response.send_message(
                embed=embed, view=view, ephemeral=True
            )
            logger.info(f"[反惡意連結]{interaction.user.id} 開啟了設定面板")

        except Exception as exc:
            error_handler.log_error(
                exc, f"開啟設定面板 - {interaction.user.id}", "PANEL_ERROR_562"
            )

            # 創建錯誤嵌入
            error_embed = discord.Embed(
                title="❌ 面板載入失敗",
                description="載入設定面板時發生錯誤,請稍後再試.\n錯誤碼: 562",
                color=discord.Color.red(),
            )

            # 顯示當前狀態作為備用資訊
            try:
                enabled = await self.get_config(
                    interaction.guild.id, "enabled", DEFAULTS["enabled"]
                )
                whitelist_count = len(await self._get_whitelist(interaction.guild.id))
                blacklist_count = len(
                    await self._get_manual_blacklist(interaction.guild.id)
                )

                error_embed.add_field(
                    name="📊 當前狀態",
                    value=(
                        f"模組狀態: {'✅ 啟用' if enabled and enabled.lower() == 'true' else '❌ 停用'}\n"
                        f"白名單: {whitelist_count} 個網域\n"
                        f"黑名單: {blacklist_count} 個網域\n"
                        f"威脅情資: {len(self._remote_blacklist)} 個網域"
                    ),
                    inline=False,
                )
            except Exception:
                pass

            try:
                await interaction.response.send_message(
                    embed=error_embed, ephemeral=True
                )
            except Exception:
                await interaction.followup.send(embed=error_embed, ephemeral=True)

    @app_commands.command(name="更新威脅情資", description="手動更新威脅情資黑名單")
    @admin_only()
    async def update_threats(self, interaction: discord.Interaction):
        """手動更新威脅情資"""
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ 本指令只能在伺服器中使用.", ephemeral=True
            )
            return

        try:
            await interaction.response.defer(ephemeral=True)

            # 執行更新
            await self._refresh_blacklist()

            embed = discord.Embed(
                title="✅ 威脅情資更新完成",
                description=f"已更新威脅情資,目前共有 {len(self._remote_blacklist)} 個惡意網域.",
                color=discord.Color.green(),
            )

            await interaction.followup.send(embed=embed)

            # 記錄操作
            await self.db.add_action_log(
                interaction.guild.id,
                interaction.user.id,
                "manual_update",
                "手動更新威脅情資",
            )

        except Exception as exc:
            error_handler.log_error(
                exc, f"手動更新威脅情資 - {interaction.user.id}", "MANUAL_UPDATE_ERROR"
            )
            embed = discord.Embed(
                title="❌ 更新失敗",
                description="更新威脅情資時發生錯誤,請稍後再試.",
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=embed)

    # ───────── 背景任務 ─────────
    @tasks.loop(hours=6)  # 每 6 小時更新一次
    async def _refresh_task(self):
        """定期更新威脅情資"""
        try:
            await self._refresh_blacklist()
            # 清理過期快取
            await self.db.cleanup_blacklist_cache(days=30)
            await self.db.cleanup_action_logs(0, days=30)  # 清理全域日誌
        except Exception as exc:
            logger.error(f"[反惡意連結]定期更新任務失敗: {exc}")

    @_refresh_task.before_loop
    async def _before_refresh_task(self):
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
            logger.error(f"[反惡意連結]取得統計失敗: {exc}")
            return {}

    async def add_to_whitelist(self, guild_id: int, domains: list[str]) -> int:
        """添加網域到白名單"""
        try:
            current_whitelist = await self.get_config(guild_id, "whitelist", "")
            current_domains = parse_domain_list(current_whitelist or "")

            new_domains = set()
            for domain in domains:
                normalized = normalize_domain(domain)
                if normalized and normalized not in current_domains:
                    new_domains.add(normalized)

            if new_domains:
                all_domains = current_domains | new_domains
                new_whitelist = ",".join(sorted(all_domains))
                await self.set_config(guild_id, "whitelist", new_whitelist)

                # 清理快取
                self._clear_cache(guild_id)

            return len(new_domains)

        except Exception as exc:
            logger.error(f"[反惡意連結]添加白名單失敗: {exc}")
            return 0

    async def add_to_blacklist(self, guild_id: int, domains: list[str]) -> int:
        """
        添加網域到黑名單

        Args:
            guild_id: 伺服器 ID
            domains: 網域列表

        Returns:
            成功添加的網域數量
        """
        try:
            current_blacklist = await self.get_config(guild_id, "blacklist", "")
            current_domains = parse_domain_list(current_blacklist or "")

            new_domains = set()
            for domain in domains:
                normalized = normalize_domain(domain)
                if normalized and normalized not in current_domains:
                    new_domains.add(normalized)

            if new_domains:
                all_domains = current_domains | new_domains
                new_blacklist = ",".join(sorted(all_domains))
                await self.set_config(guild_id, "blacklist", new_blacklist)

                # 清理快取
                self._clear_cache(guild_id)

            return len(new_domains)

        except Exception as exc:
            logger.error(f"[反惡意連結]添加黑名單失敗: {exc}")
            return 0

    # ───────── 面板系統適配方法 ─────────
    async def get_config(
        self, guild_id: int, key: str | None = None, default: Any = None
    ) -> Any:
        """
        獲取配置項目 - 面板系統適配方法

        Args:
            guild_id: 伺服器 ID
            key: 配置鍵(可選,如果為 None 則返回所有配置)
            default: 預設值

        Returns:
            配置值或所有配置字典
        """
        try:
            if key is None:
                # 返回所有配置
                return await self.db.get_all_config(guild_id)
            else:
                # 返回特定配置
                return await self.db.get_config(guild_id, key, default)
        except Exception as exc:
            logger.error(f"[反惡意連結]獲取配置失敗: {exc}")
            return default if key else {}

    async def set_config(self, guild_id: int, key: str, value: Any) -> None:
        """
        設置配置項目 - 面板系統適配方法

        Args:
            guild_id: 伺服器 ID
            key: 配置鍵
            value: 配置值
        """
        try:
            value_str = str(value) if value is not None else ""
            await self.db.set_config(guild_id, key, value_str)
        except Exception as exc:
            logger.error(f"[反惡意連結]設置配置失敗: {exc}")
            raise
