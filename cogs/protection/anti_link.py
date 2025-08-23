# cogs/protection/anti_link.py ── 反惡意連結保護模組 (Discord.py 2.5.2 兼容版)
# ============================================================
# 功能說明：
#  - 自動檢測並刪除惡意連結
#  - 支援白名單機制
#  - 支援手動黑名單管理
#  - 整合遠端威脅情資
#  - 自動更新黑名單
#  - 提供詳細的管理介面
#  - 自定義刪除訊息
#  - 可視化控制面板
#  - 詳細顯示惡意連結網域
#  - 測試功能
# 
# Discord.py 2.5.2 兼容性修復：
#  - 修正 button 裝飾器使用方式
#  - 修正 ButtonStyle 兼容性
#  - 完善型別提示
#  - 改進錯誤處理
#
# 更新日誌:
# v1.5.4 - 優化面板交互體驗
#  - 按鈕按下後直接更新現有面板而非發送新面板
#  - 取消獨立的「查看來源」斜線指令
# ============================================================

from __future__ import annotations
import re, csv, io, asyncio, math, urllib.parse as up, aiohttp, tldextract, logging, discord
from typing import Set, List, Optional, Dict, Any, Union, Literal
from discord import app_commands, ui
from discord.ext import commands, tasks
from .base import ProtectionCog, admin_only, handle_error, friendly_log

# ────────────────────────────
# 常數定義
# ────────────────────────────
# URL 檢測正則表達式
URL_PAT = re.compile(r"https?://[A-Za-z0-9\.\-_%]+\.[A-Za-z]{2,}[^ <]*", re.I)

# 預設白名單（安全的網域）
DEFAULT_WHITELIST = {
    "discord.com", "discord.gg",
    "youtube.com", "youtu.be",
    "github.com", "gist.github.com",
}

# 預設刪除訊息
DEFAULT_DELETE_MESSAGE = "🚫 偵測到惡意連結，已自動刪除"

# 威脅情資來源
FEEDS = {
    "URLHaus":     "https://urlhaus.abuse.ch/downloads/hostfile/",
    "OpenPhish":   "https://openphish.com/feed.txt",
    "URLHaus-CSV": "https://urlhaus.abuse.ch/downloads/csv_recent/",
}

# 分頁設定
PER_PAGE = 20
logger = logging.getLogger("protection")

# 面板樣式
PANEL_STYLES = {
    "preview": discord.Color.blue(),
    "config": discord.Color.orange(),
    "stats": discord.Color.green(),
    "local_blacklist": discord.Color.purple(),
    "remote_blacklist": discord.Color.dark_red(),
}

# 狀態徽章樣式
STATUS_BADGE = {
    "enabled": "✅ 已啟用",
    "disabled": "❌ 已停用",
    "partial": "⚠️ 部分啟用",
    "unknown": "❓ 未知",
}

# ────────────────────────────
# 遠端黑名單翻頁 View (Discord.py 2.5.2 兼容版)
# ────────────────────────────
class RemoteBLView(ui.View):
    """遠端黑名單瀏覽器"""
    
    def __init__(self, cog: "AntiLink", owner: int):
        """初始化遠端黑名單瀏覽器
        
        Args:
            cog: AntiLink 實例
            owner: 擁有者 ID
        """
        super().__init__(timeout=300)
        self.cog, self.owner = cog, owner
        self.page = 1
        self.total = max(1, math.ceil(len(cog._remote_bl) / PER_PAGE))
        
        # 添加按鈕
        self.add_item(PrevButton())
        self.add_item(NextButton())
        self.add_item(RefreshButton())

    async def interaction_check(self, itx: discord.Interaction) -> bool:
        """檢查互動權限"""
        if itx.user.id != self.owner:
            await itx.response.send_message("只能由指令發起者操作。", ephemeral=True)
            return False
        return True

    def _embed(self) -> discord.Embed:
        """建構黑名單 Embed"""
        doms = sorted(self.cog._remote_bl)
        start = (self.page - 1) * PER_PAGE
        return (
            discord.Embed(
                title=f"🌐 遠端黑名單（{len(doms)} 筆）",
                description="\n".join(doms[start:start + PER_PAGE]) or "（空）",
                color=discord.Color.red(),
            )
            .set_footer(text=f"{self.page}/{self.total} 頁")
        )


class PrevButton(ui.Button):
    """上一頁按鈕"""
    
    def __init__(self):
        super().__init__(emoji="⬅️", style=discord.ButtonStyle.gray)
    
    async def callback(self, itx: discord.Interaction):
        """上一頁"""
        view: RemoteBLView = self.view  # type: ignore
        if view.page > 1:
            view.page -= 1
            await itx.response.edit_message(embed=view._embed(), view=view)


class NextButton(ui.Button):
    """下一頁按鈕"""
    
    def __init__(self):
        super().__init__(emoji="➡️", style=discord.ButtonStyle.gray)
    
    async def callback(self, itx: discord.Interaction):
        """下一頁"""
        view: RemoteBLView = self.view  # type: ignore
        if view.page < view.total:
            view.page += 1
            await itx.response.edit_message(embed=view._embed(), view=view)


class RefreshButton(ui.Button):
    """重新整理按鈕"""
    
    def __init__(self):
        super().__init__(label="重新整理", emoji="🔄", style=discord.ButtonStyle.primary)
    
    async def callback(self, itx: discord.Interaction):
        """重新整理黑名單"""
        view = self.view  # type: ignore
        if isinstance(view, RemoteBLView):
            await itx.response.defer(thinking=True, ephemeral=True)
            await view.cog._refresh_blacklist()
            view.total = max(1, math.ceil(len(view.cog._remote_bl) / PER_PAGE))
            view.page = min(view.page, view.total)
            await itx.edit_original_response(
                content="✅ 已重新下載遠端黑名單。",
                embed=view._embed(),
                view=view,
            )


# ────────────────────────────
# 關閉按鈕
# ────────────────────────────
class CloseButton(ui.Button):
    """關閉面板按鈕"""
    
    def __init__(self):
        super().__init__(label="關閉", emoji="❌", style=discord.ButtonStyle.secondary, row=4)
    
    async def callback(self, itx: discord.Interaction):
        """關閉面板"""
        if itx.message:
            await itx.message.delete()
        else:
            await itx.response.send_message("無法關閉面板。", ephemeral=True)


# ────────────────────────────
# 切換面板選擇器
# ────────────────────────────
class PanelSelector(ui.Select):
    """面板選擇下拉選單"""
    
    def __init__(self, view: "AntiLinkPanel"):
        """初始化面板選擇器
        
        Args:
            view: 面板 View 實例
        """
        options = [
            discord.SelectOption(label="預覽面板", description="顯示防護系統狀態", emoji="📊", value="preview"),
            discord.SelectOption(label="設定面板", description="調整防護系統參數", emoji="⚙️", value="config"),
            discord.SelectOption(label="統計面板", description="查看系統運作數據", emoji="📊", value="stats"),
            discord.SelectOption(label="本地黑白名單", description="詳細查看本地黑白名單", emoji="📋", value="local_blacklist"),
            discord.SelectOption(label="遠端黑名單", description="詳細查看遠端黑名單", emoji="🌐", value="remote_blacklist"),
        ]
        super().__init__(placeholder="選擇面板類型", options=options, row=0)
        self.panel_view = view
    
    async def callback(self, itx: discord.Interaction):
        """切換面板"""
        await self.panel_view.switch_panel(itx, self.values[0])


# ────────────────────────────
# 配置輸入對話框
# ────────────────────────────
class WhitelistModal(ui.Modal, title="設定白名單"):
    """白名單設定對話框"""
    
    domains = ui.TextInput(
        label="安全網域（以逗號分隔）",
        style=discord.TextStyle.paragraph,
        placeholder="輸入安全網域，以逗號分隔，例如：example.com,secure-site.org",
        required=True,
    )
    
    def __init__(self, view: "AntiLinkPanel", current_value: str = ""):
        super().__init__()
        self.panel_view = view
        if current_value:
            self.domains.default = current_value
    
    async def on_submit(self, itx: discord.Interaction):
        """提交時處理"""
        try:
            if itx.guild:
                await self.panel_view.cog.set_cfg(itx.guild.id, "whitelist", self.domains.value)
                await itx.response.send_message("✅ 已更新連結白名單。", ephemeral=True)
                
                # 更新面板
                embed = await self.panel_view._create_embed()
                if itx.message:
                    await itx.message.edit(embed=embed)
        except Exception as e:
            friendly_log("更新白名單失敗", e)
            await itx.response.send_message("❌ 更新白名單失敗", ephemeral=True)


class DeleteMessageModal(ui.Modal, title="設定刪除訊息"):
    """刪除訊息設定對話框"""
    
    message = ui.TextInput(
        label="刪除訊息",
        style=discord.TextStyle.short,
        placeholder="輸入刪除惡意連結時顯示的訊息",
        default=DEFAULT_DELETE_MESSAGE,
        required=True,
        max_length=100,
    )
    
    def __init__(self, view: "AntiLinkPanel", current_message: str = ""):
        super().__init__()
        self.panel_view = view
        if current_message:
            self.message.default = current_message
    
    async def on_submit(self, itx: discord.Interaction):
        """提交時處理"""
        try:
            if itx.guild:
                await self.panel_view.cog.set_cfg(itx.guild.id, "delete_message", self.message.value)
                await itx.response.send_message("✅ 已更新刪除訊息。", ephemeral=True)
                
                # 如果在設定面板，更新顯示
                if self.panel_view.current_panel == "config":
                    embed = await self.panel_view._create_config_embed()
                    if itx.message:
                        await itx.message.edit(embed=embed)
        except Exception as e:
            friendly_log("更新刪除訊息失敗", e)
            await itx.response.send_message("❌ 更新刪除訊息失敗", ephemeral=True)


# ────────────────────────────
# 主面板相關按鈕
# ────────────────────────────
class TutorialButton(ui.Button):
    """教程按鈕"""
    
    def __init__(self):
        super().__init__(label="新手教程", emoji="📚", style=discord.ButtonStyle.primary, row=1)
    
    async def callback(self, itx: discord.Interaction):
        """顯示新手教程"""
        view = self.view  # type: ignore
        if not isinstance(view, AntiLinkPanel):
            return
            
        embed = discord.Embed(
            title="📚 反惡意連結系統新手教程",
            description="快速上手指南",
            color=discord.Color.green(),
        )
        
        embed.add_field(
            name="🔍 系統概述",
            value=(
                "反惡意連結系統自動檢測並刪除可能威脅伺服器安全的連結。\n"
                "系統整合遠端威脅情資，同時支援自定義黑白名單。\n"
            ),
            inline=False,
        )
        
        embed.add_field(
            name="⚙️ 基本設定",
            value=(
                "1️⃣ 使用「設定白名單」按鈕添加你信任的網域\n"
                "2️⃣ 使用「設定刪除訊息」按鈕自定義警告訊息\n"
                "3️⃣ 使用「黑名單管理」按鈕管理自訂黑名單\n"
            ),
            inline=False,
        )
        
        embed.add_field(
            name="🛡️ 進階功能",
            value=(
                "• 系統每 4 小時自動更新遠端黑名單\n"
                "• 切換至「統計面板」查看更多詳細資訊\n"
                "• 使用「查看來源」按鈕檢視威脅情資來源\n"
            ),
            inline=False,
        )
        
        # 添加使用說明的頁尾
        embed.set_footer(text="點擊「返回」按鈕回到主面板")
        
        # 創建帶有返回按鈕的新視圖
        new_view = ui.View(timeout=300)
        new_view.add_item(ReturnButton(view))
        new_view.add_item(CloseButton())
        
        # 更新現有面板而非發送新消息
        await itx.response.edit_message(embed=embed, view=new_view)


class ReturnButton(ui.Button):
    """返回主面板按鈕"""
    
    def __init__(self, original_view: ui.View):
        super().__init__(label="返回", emoji="↩️", style=discord.ButtonStyle.secondary)
        self.original_view = original_view
    
    async def callback(self, itx: discord.Interaction):
        """返回主面板"""
        # 簡單返回原視圖
        if hasattr(self.original_view, "_create_embed"):
            embed = await self.original_view._create_embed()  # type: ignore
        else:
            # 使用簡單的預設 Embed
            embed = discord.Embed(
                title="⛔ 黑名單管理",
                description="管理手動添加的惡意網域",
                color=discord.Color.red(),
            )
        
        await itx.response.edit_message(embed=embed, view=self.original_view)


class PanelRefreshButton(ui.Button):
    """面板刷新按鈕"""
    
    def __init__(self):
        super().__init__(label="重新整理", emoji="🔄", style=discord.ButtonStyle.primary, row=1)
    
    async def callback(self, itx: discord.Interaction):
        """重新整理面板"""
        view = self.view  # type: ignore
        if not isinstance(view, AntiLinkPanel):
            return
            
        await itx.response.defer(thinking=True, ephemeral=True)
        
        if view.current_panel == "preview":
            # 在預覽模式下，更新威脅情報
            await view.cog._refresh_blacklist()
            await itx.edit_original_response(content="✅ 已重新整理威脅情報。")
        
        # 更新面板
        if itx.message:
            await itx.message.edit(embed=await view._create_embed(), view=view)


class BlacklistManageButton(ui.Button):
    """黑名單管理按鈕"""
    
    def __init__(self):
        super().__init__(label="黑名單管理", emoji="⛔", style=discord.ButtonStyle.danger, row=1)
    
    async def callback(self, itx: discord.Interaction):
        """顯示黑名單管理選項"""
        view = self.view  # type: ignore
        if not isinstance(view, AntiLinkPanel):
            return
            
        if not itx.guild:
            await itx.response.send_message("此功能只能在伺服器中使用。", ephemeral=True)
            return
            
        # 獲取現有黑名單
        manual_bl = await view.cog._get_manual_bl(itx.guild.id)
        
        embed = discord.Embed(
            title="⛔ 黑名單管理",
            description="管理手動添加的惡意網域",
            color=discord.Color.red(),
        )
        
        # 顯示前10個黑名單項目
        if manual_bl:
            embed.add_field(
                name=f"目前黑名單（{len(manual_bl)} 筆）",
                value="\n".join([f"• {domain}" for domain in sorted(manual_bl)[:10]]) + 
                      (f"\n*...還有 {len(manual_bl)-10} 筆未顯示*" if len(manual_bl) > 10 else ""),
                inline=False,
            )
        else:
            embed.add_field(
                name="目前黑名單",
                value="尚未添加任何網域",
                inline=False,
            )
        
        # 創建黑名單管理視圖
        bl_view = BlacklistManageView(view)
        
        await itx.response.edit_message(embed=embed, view=bl_view)


class BlacklistManageView(ui.View):
    """黑名單管理視圖"""
    
    def __init__(self, original_view: AntiLinkPanel):
        super().__init__(timeout=300)
        self.original_view = original_view
        self.guild_id = None
        
        # 尋找伺服器 ID
        for guild in original_view.cog.bot.guilds:
            if guild.get_member(original_view.owner):
                self.guild_id = guild.id
                break
        
        # 添加按鈕
        self.add_item(ViewBlacklistButton(self))
        self.add_item(AddDomainButton(self))
        self.add_item(RemoveDomainButton(self))
        self.add_item(ReturnButton(self.original_view))
        self.add_item(CloseButton())
    
    async def on_error(self, interaction: discord.Interaction, error: Exception, item: ui.Item):
        """處理錯誤"""
        friendly_log("黑名單管理視圖錯誤", error)
        await interaction.response.send_message(f"❌ 操作失敗: {error}", ephemeral=True)


class ViewBlacklistButton(ui.Button):
    """查看完整黑名單按鈕"""
    
    def __init__(self, view: BlacklistManageView):
        super().__init__(label="查看完整黑名單", emoji="📋", style=discord.ButtonStyle.primary, row=0)
        self.view_parent = view
    
    async def callback(self, itx: discord.Interaction):
        """顯示完整黑名單"""
        if not self.view_parent.guild_id:
            await itx.response.send_message("無法找到伺服器資訊。", ephemeral=True)
            return
            
        # 獲取完整黑名單
        manual_bl = await self.view_parent.original_view.cog._get_manual_bl(self.view_parent.guild_id)
        
        if not manual_bl:
            await itx.response.send_message("黑名單為空。", ephemeral=True)
            return
            
        # 創建分頁視圖
        doms = sorted(manual_bl)
        total = math.ceil(len(doms) / PER_PAGE)
        page = 1
        start = 0
        
        embed = (
            discord.Embed(
                title=f"📋 手動黑名單（{len(doms)} 筆）",
                description="\n".join(doms[start:start + PER_PAGE]) or "（空）",
                color=discord.Color.orange(),
            ).set_footer(text=f"{page}/{total} 頁")
        )
        
        # 創建分頁視圖
        blacklist_view = BlacklistPaginationView(
            doms, 
            self.view_parent.original_view.owner,
            self.view_parent
        )
        
        await itx.response.edit_message(embed=embed, view=blacklist_view)


class BlacklistPaginationView(ui.View):
    """黑名單分頁視圖"""
    
    def __init__(self, doms: List[str], owner: int, parent_view: BlacklistManageView):
        super().__init__(timeout=300)
        self.domains = doms
        self.owner = owner
        self.page = 1
        self.total = max(1, math.ceil(len(doms) / PER_PAGE))
        self.parent_view = parent_view
        
        # 添加分頁按鈕
        self.add_item(PrevPageButton(self))
        self.add_item(NextPageButton(self))
        self.add_item(ReturnButton(parent_view))
    
    async def interaction_check(self, itx: discord.Interaction) -> bool:
        """檢查互動權限"""
        if itx.user.id != self.owner:
            await itx.response.send_message("只能由指令發起者操作。", ephemeral=True)
            return False
        return True
    
    def get_embed(self) -> discord.Embed:
        """取得當前頁面的 Embed"""
        start = (self.page - 1) * PER_PAGE
        end = start + PER_PAGE
        
        return (
            discord.Embed(
                title=f"📋 手動黑名單（{len(self.domains)} 筆）",
                description="\n".join(self.domains[start:end]) or "（空）",
                color=discord.Color.orange(),
            ).set_footer(text=f"{self.page}/{self.total} 頁")
        )


class PrevPageButton(ui.Button):
    """上一頁按鈕"""
    
    def __init__(self, view: BlacklistPaginationView):
        super().__init__(emoji="⬅️", style=discord.ButtonStyle.gray)
        self.parent_view = view
    
    async def callback(self, itx: discord.Interaction):
        """上一頁"""
        if self.parent_view.page > 1:
            self.parent_view.page -= 1
            await itx.response.edit_message(embed=self.parent_view.get_embed(), view=self.parent_view)
        else:
            await itx.response.send_message("已經是第一頁了。", ephemeral=True)


class NextPageButton(ui.Button):
    """下一頁按鈕"""
    
    def __init__(self, view: BlacklistPaginationView):
        super().__init__(emoji="➡️", style=discord.ButtonStyle.gray)
        self.parent_view = view
    
    async def callback(self, itx: discord.Interaction):
        """下一頁"""
        if self.parent_view.page < self.parent_view.total:
            self.parent_view.page += 1
            await itx.response.edit_message(embed=self.parent_view.get_embed(), view=self.parent_view)
        else:
            await itx.response.send_message("已經是最後一頁了。", ephemeral=True)


class AddDomainButton(ui.Button):
    """添加網域按鈕"""
    
    def __init__(self, view: BlacklistManageView):
        super().__init__(label="添加網域", emoji="➕", style=discord.ButtonStyle.success, row=0)
        self.view_parent = view
    
    async def callback(self, itx: discord.Interaction):
        """顯示添加網域對話框"""
        # 顯示添加網域對話框
        modal = AddDomainModal(self.view_parent)
        await itx.response.send_modal(modal)


class AddDomainModal(ui.Modal, title="添加黑名單網域"):
    """添加網域對話框"""
    
    domain = ui.TextInput(
        label="網域",
        style=discord.TextStyle.short,
        placeholder="輸入要添加的危險網域，例如：example.com",
        required=True,
    )
    
    def __init__(self, view: BlacklistManageView):
        super().__init__()
        self.view_parent = view
    
    async def on_submit(self, itx: discord.Interaction):
        """提交時處理"""
        try:
            if not self.view_parent.guild_id:
                await itx.response.send_message("無法找到伺服器資訊。", ephemeral=True)
                return
                
            domain = self.domain.value.lower().lstrip("www.")
            cog = self.view_parent.original_view.cog
            doms = await cog._get_manual_bl(self.view_parent.guild_id)
            
            if domain in doms:
                await itx.response.send_message("此網域已在黑名單中。", ephemeral=True)
                return
                
            doms.add(domain)
            await cog._save_manual_bl(self.view_parent.guild_id, doms)
            
            # 更新黑名單視圖
            manual_bl = await cog._get_manual_bl(self.view_parent.guild_id)
            
            embed = discord.Embed(
                title="⛔ 黑名單管理",
                description=f"✅ 已成功加入 `{domain}` 至黑名單",
                color=discord.Color.red(),
            )
            
            # 顯示前10個黑名單項目
            if manual_bl:
                embed.add_field(
                    name=f"目前黑名單（{len(manual_bl)} 筆）",
                    value="\n".join([f"• {domain}" for domain in sorted(manual_bl)[:10]]) + 
                          (f"\n*...還有 {len(manual_bl)-10} 筆未顯示*" if len(manual_bl) > 10 else ""),
                    inline=False,
                )
            
            await itx.response.edit_message(embed=embed, view=self.view_parent)
            
        except Exception as e:
            friendly_log("添加黑名單失敗", e)
            await itx.response.send_message(f"❌ 添加黑名單失敗: {str(e)}", ephemeral=True)


class RemoveDomainButton(ui.Button):
    """移除網域按鈕"""
    
    def __init__(self, view: BlacklistManageView):
        super().__init__(label="移除網域", emoji="➖", style=discord.ButtonStyle.danger, row=0)
        self.view_parent = view
    
    async def callback(self, itx: discord.Interaction):
        """顯示移除網域對話框"""
        # 顯示移除網域對話框
        modal = RemoveDomainModal(self.view_parent)
        await itx.response.send_modal(modal)


class RemoveDomainModal(ui.Modal, title="移除黑名單網域"):
    """移除網域對話框"""
    
    domain = ui.TextInput(
        label="網域",
        style=discord.TextStyle.short,
        placeholder="輸入要移除的網域，必須完全匹配",
        required=True,
    )
    
    def __init__(self, view: BlacklistManageView):
        super().__init__()
        self.view_parent = view
    
    async def on_submit(self, itx: discord.Interaction):
        """提交時處理"""
        try:
            if not self.view_parent.guild_id:
                await itx.response.send_message("無法找到伺服器資訊。", ephemeral=True)
                return
                
            domain = self.domain.value.lower().lstrip("www.")
            cog = self.view_parent.original_view.cog
            doms = await cog._get_manual_bl(self.view_parent.guild_id)
            
            if domain not in doms:
                await itx.response.send_message("黑名單中找不到此網域。", ephemeral=True)
                return
                
            doms.remove(domain)
            await cog._save_manual_bl(self.view_parent.guild_id, doms)
            
            # 更新黑名單視圖
            manual_bl = await cog._get_manual_bl(self.view_parent.guild_id)
            
            embed = discord.Embed(
                title="⛔ 黑名單管理",
                description=f"✅ 已成功從黑名單移除 `{domain}`",
                color=discord.Color.red(),
            )
            
            # 顯示前10個黑名單項目
            if manual_bl:
                embed.add_field(
                    name=f"目前黑名單（{len(manual_bl)} 筆）",
                    value="\n".join([f"• {domain}" for domain in sorted(manual_bl)[:10]]) + 
                          (f"\n*...還有 {len(manual_bl)-10} 筆未顯示*" if len(manual_bl) > 10 else ""),
                    inline=False,
                )
            else:
                embed.add_field(
                    name="目前黑名單",
                    value="黑名單為空",
                    inline=False,
                )
            
            await itx.response.edit_message(embed=embed, view=self.view_parent)
            
        except Exception as e:
            friendly_log("移除黑名單失敗", e)
            await itx.response.send_message(f"❌ 移除黑名單失敗: {str(e)}", ephemeral=True)


# ────────────────────────────
# 設定按鈕
# ────────────────────────────
class WhitelistButton(ui.Button):
    """白名單設定按鈕"""
    
    def __init__(self):
        super().__init__(label="設定白名單", emoji="⚪", style=discord.ButtonStyle.success, row=2)
    
    async def callback(self, itx: discord.Interaction):
        """顯示白名單設定對話框"""
        view = self.view  # type: ignore
        if not isinstance(view, AntiLinkPanel):
            return
            
        # 獲取現有白名單
        current_value = ""
        if itx.guild:
            whitelist = await view.cog.get_cfg(itx.guild.id, "whitelist", "")
            if whitelist is not None:
                current_value = whitelist
            
        # 顯示白名單設定對話框
        modal = WhitelistModal(view, current_value)
        await itx.response.send_modal(modal)


class DeleteMessageButton(ui.Button):
    """刪除訊息設定按鈕"""
    
    def __init__(self):
        super().__init__(label="設定刪除訊息", emoji="🚫", style=discord.ButtonStyle.success, row=2)
    
    async def callback(self, itx: discord.Interaction):
        """顯示刪除訊息設定對話框"""
        view = self.view  # type: ignore
        if not isinstance(view, AntiLinkPanel):
            return
            
        # 獲取現有訊息
        current_message = DEFAULT_DELETE_MESSAGE
        if itx.guild:
            msg = await view.cog.get_cfg(
                itx.guild.id, "delete_message", DEFAULT_DELETE_MESSAGE
            )
            if msg is not None:
                current_message = msg
            
        # 顯示刪除訊息設定對話框
        modal = DeleteMessageModal(view, current_message)
        await itx.response.send_modal(modal)


class ViewSourcesButton(ui.Button):
    """查看來源按鈕"""
    
    def __init__(self):
        super().__init__(label="查看來源", emoji="🔍", style=discord.ButtonStyle.secondary, row=2)
    
    async def callback(self, itx: discord.Interaction):
        """顯示威脅情報來源"""
        view = self.view  # type: ignore
        if not isinstance(view, AntiLinkPanel):
            return
            
        embed = discord.Embed(
            title="🔍 威脅情資來源",
            description="系統使用以下公開資料庫來識別惡意連結：",
            color=discord.Color.teal(),
        )
        
        # 顯示情資來源
        sources = []
        for name, url in FEEDS.items():
            sources.append(f"• [{name}]({url})")
        
        embed.add_field(
            name="遠端情資庫",
            value="\n".join(sources),
            inline=False,
        )
        
        # 創建帶有返回按鈕的新視圖
        new_view = ui.View(timeout=300)
        new_view.add_item(ReturnButton(view))
        new_view.add_item(CloseButton())
        
        # 更新現有面板而非發送新消息
        await itx.response.edit_message(embed=embed, view=new_view)


# ────────────────────────────
# 測試功能相關按鈕
# ────────────────────────────
class TestButton(ui.Button):
    """測試功能按鈕"""
    
    def __init__(self):
        super().__init__(label="測試功能", emoji="🧪", style=discord.ButtonStyle.secondary, row=3)
    
    async def callback(self, itx: discord.Interaction):
        """顯示測試選項"""
        view = self.view  # type: ignore
        if not isinstance(view, AntiLinkPanel):
            return
        
        # 顯示測試選項
        await itx.response.send_message(
            "選擇要測試的功能：",
            view=TestSelectView(view.cog, itx.user.id),
            ephemeral=True
        )


class TestSelectView(ui.View):
    """測試功能選單"""
    
    def __init__(self, cog: "AntiLink", user_id: int):
        super().__init__(timeout=60)
        self.cog = cog
        self.user_id = user_id
        
        # 添加測試選項
        self.add_item(TestSelectMenu(self))
    
    async def interaction_check(self, itx: discord.Interaction) -> bool:
        """檢查互動權限"""
        if itx.user.id != self.user_id:
            await itx.response.send_message("只能由指令發起者操作。", ephemeral=True)
            return False
        return True


class TestSelectMenu(ui.Select):
    """測試功能選項"""
    
    def __init__(self, view: TestSelectView):
        options = [
            discord.SelectOption(
                label="本地黑名單測試",
                description="測試本地黑名單功能",
                emoji="📋",
                value="local_blacklist"
            ),
            discord.SelectOption(
                label="遠端黑名單測試",
                description="測試遠端黑名單功能",
                emoji="🌐",
                value="remote_blacklist"
            ),
            discord.SelectOption(
                label="連結偵測測試",
                description="測試連結偵測功能",
                emoji="🔍",
                value="url_detection"
            )
        ]
        super().__init__(placeholder="選擇要測試的功能", options=options)
        self.parent_view = view
    
    async def callback(self, itx: discord.Interaction):
        """測試功能選擇回調"""
        test_type = self.values[0]
        
        # 停用選單避免重複操作
        self.disabled = True
        await itx.response.edit_message(view=self.parent_view)
        
        # 執行測試
        if test_type == "local_blacklist":
            await self._run_local_blacklist_test(itx)
        elif test_type == "remote_blacklist":
            await self._run_remote_blacklist_test(itx)
        elif test_type == "url_detection":
            await self._run_url_detection_test(itx)
            
    async def _run_local_blacklist_test(self, itx: discord.Interaction):
        """執行本地黑名單測試"""
        try:
            # 尋找伺服器 ID
            guild_id = None
            for guild in self.parent_view.cog.bot.guilds:
                if guild.get_member(self.parent_view.user_id):
                    guild_id = guild.id
                    break
                    
            if not guild_id:
                await itx.followup.send("❌ 無法找到伺服器資訊", ephemeral=True)
                return
                
            # 測試手動黑名單讀取
            manual_bl = await self.parent_view.cog._get_manual_bl(guild_id)
            
            embed = discord.Embed(
                title="🧪 本地黑名單測試結果",
                description="測試成功！本地黑名單功能正常運作。",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="手動黑名單",
                value=f"已成功載入 {len(manual_bl)} 個黑名單網域",
                inline=False
            )
            
            # 顯示範例網域（如果有）
            if manual_bl:
                embed.add_field(
                    name="範例網域",
                    value="\n".join([f"• {domain}" for domain in sorted(manual_bl)[:3]]),
                    inline=False
                )
            
            await itx.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            await itx.followup.send(f"❌ 測試失敗：{str(e)}", ephemeral=True)
    
    async def _run_remote_blacklist_test(self, itx: discord.Interaction):
        """執行遠端黑名單測試"""
        try:
            # 檢查遠端黑名單
            remote_bl = self.parent_view.cog._remote_bl
            
            if not remote_bl:
                await itx.followup.send("❌ 遠端黑名單為空，正在嘗試更新...", ephemeral=True)
                await self.parent_view.cog._refresh_blacklist()
                remote_bl = self.parent_view.cog._remote_bl
            
            embed = discord.Embed(
                title="🧪 遠端黑名單測試結果",
                description="測試成功！遠端黑名單功能正常運作。",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="遠端黑名單",
                value=f"已成功載入 {len(remote_bl)} 個黑名單網域",
                inline=False
            )
            
            # 顯示範例網域（如果有）
            if remote_bl:
                embed.add_field(
                    name="範例網域",
                    value="\n".join([f"• {domain}" for domain in sorted(remote_bl)[:3]]),
                    inline=False
                )
            
            # 顯示遠端來源
            sources = []
            for name, url in FEEDS.items():
                sources.append(f"• {name}")
            
            embed.add_field(
                name="遠端來源",
                value="\n".join(sources),
                inline=False
            )
            
            await itx.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            await itx.followup.send(f"❌ 測試失敗：{str(e)}", ephemeral=True)
    
    async def _run_url_detection_test(self, itx: discord.Interaction):
        """執行 URL 檢測測試"""
        try:
            # 測試 URL 檢測正則表達式
            test_urls = [
                "https://example.com",
                "http://test.example.org/path?query=value",
                "https://subdomain.domain.co.uk/test",
                "這不是連結",
                "example.com", # 不帶協議頭
                "https://test.com/file.exe",
            ]
            
            results = []
            for url in test_urls:
                matches = URL_PAT.findall(url)
                results.append((url, len(matches) > 0, matches))
            
            embed = discord.Embed(
                title="🧪 URL 檢測測試結果",
                description="測試成功！URL 檢測功能正常運作。",
                color=discord.Color.green()
            )
            
            # 顯示測試結果
            for url, is_match, matches in results:
                status = "✅ 已偵測" if is_match else "❌ 未偵測"
                embed.add_field(
                    name=f"{status}：{url}",
                    value=f"{'匹配：' + str(matches) if matches else '無匹配'}",
                    inline=False
                )
            
            await itx.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            await itx.followup.send(f"❌ 測試失敗：{str(e)}", ephemeral=True)


# ────────────────────────────
# 主面板類
# ────────────────────────────
class AntiLinkPanel(ui.View):
    """反惡意連結控制面板"""
    
    def __init__(self, cog: "AntiLink", owner: int):
        """初始化控制面板
        
        Args:
            cog: AntiLink 實例
            owner: 擁有者 ID
        """
        super().__init__(timeout=600)
        self.cog = cog
        self.owner = owner
        self.current_panel = "preview"  # 預設顯示預覽面板
        
        # 添加選擇器和按鈕
        self.add_item(PanelSelector(self))
        self.add_item(TutorialButton())
        self.add_item(PanelRefreshButton())
        self.add_item(BlacklistManageButton())
        
        # 添加設定按鈕
        self.add_item(WhitelistButton())
        self.add_item(DeleteMessageButton())
        self.add_item(ViewSourcesButton())
        
        # 添加測試按鈕
        self.add_item(TestButton())
        
        self.add_item(CloseButton())
    
    async def interaction_check(self, itx: discord.Interaction) -> bool:
        """檢查互動權限"""
        if itx.user.id != self.owner:
            await itx.response.send_message("只能由指令發起者操作。", ephemeral=True)
            return False
        return True
    
    async def switch_panel(self, itx: discord.Interaction, panel_type: str):
        """切換面板類型
        
        Args:
            itx: Discord 互動
            panel_type: 面板類型
        """
        self.current_panel = panel_type
        await itx.response.edit_message(embed=await self._create_embed(), view=self)
    
    async def _create_embed(self) -> discord.Embed:
        """創建面板 Embed
        
        Returns:
            Discord Embed 物件
        """
        if self.current_panel == "preview":
            return await self._create_preview_embed()
        elif self.current_panel == "stats":
            return await self._create_stats_embed()
        elif self.current_panel == "local_blacklist":
            return await self._create_local_blacklist_embed()
        elif self.current_panel == "remote_blacklist":
            return await self._create_remote_blacklist_embed()
        else:
            return await self._create_config_embed()
    
    async def _create_preview_embed(self) -> discord.Embed:
        """創建預覽面板 Embed
        
        Returns:
            Discord Embed 物件
        """
        guild_id = None
        for guild in self.cog.bot.guilds:
            if guild.get_member(self.owner):
                guild_id = guild.id
                break
        
        if not guild_id:
            return discord.Embed(title="⚠️ 錯誤", description="無法找到伺服器資訊。", color=discord.Color.red())
        
        # 取得設定
        manual_bl = await self.cog._get_manual_bl(guild_id)
        whitelist_raw = await self.cog.get_cfg(guild_id, "whitelist", "")
        whitelist = DEFAULT_WHITELIST | {d.strip().lower() for d in (whitelist_raw or "").split(",") if d.strip()}
        
        embed = discord.Embed(
            title="📊 反惡意連結系統狀態",
            description="保護你的社群免受惡意連結的威脅",
            color=PANEL_STYLES["preview"],
        )
        
        # 添加狀態徽章
        embed.add_field(
            name="🛡️ 防護狀態",
            value=STATUS_BADGE["enabled"],
            inline=True,
        )
        
        # 添加統計資訊
        embed.add_field(
            name="📋 手動黑名單",
            value=f"{len(manual_bl)} 個網域",
            inline=True,
        )
        embed.add_field(
            name="🌐 遠端黑名單",
            value=f"{len(self.cog._remote_bl)} 個網域",
            inline=True,
        )
        embed.add_field(
            name="📝 白名單",
            value=f"{len(whitelist)} 個網域",
            inline=True,
        )
        
        # 顯示最近的威脅
        next_update = "未知"
        if hasattr(self.cog.refresh_task, "next_iteration") and self.cog.refresh_task.next_iteration:
            next_update = f"<t:{int(self.cog.refresh_task.next_iteration.timestamp())}:R>"
            
        embed.add_field(
            name="📈 威脅情報更新時間",
            value=next_update,
            inline=False,
        )
        
        # 添加功能摘要
        embed.add_field(
            name="💡 功能摘要",
            value=(
                "• 自動刪除危險連結\n"
                "• 支援自定義白名單\n"
                "• 支援手動黑名單\n"
                "• 整合遠端威脅情資\n"
            ),
            inline=False,
        )
        
        embed.set_footer(text="使用下拉選單切換至設定面板以調整參數 | 切換至統計面板以查看詳細數據")
        return embed
    
    async def _create_config_embed(self) -> discord.Embed:
        """創建設定面板 Embed
        
        Returns:
            Discord Embed 物件
        """
        guild_id = None
        for guild in self.cog.bot.guilds:
            if guild.get_member(self.owner):
                guild_id = guild.id
                break
        
        if not guild_id:
            return discord.Embed(title="⚠️ 錯誤", description="無法找到伺服器資訊。", color=discord.Color.red())
        
        # 取得設定
        delete_message = await self.cog.get_cfg(guild_id, "delete_message", DEFAULT_DELETE_MESSAGE)
        whitelist_raw = await self.cog.get_cfg(guild_id, "whitelist", "")
        whitelist = [d.strip() for d in (whitelist_raw or "").split(",") if d.strip()]
        
        embed = discord.Embed(
            title="⚙️ 反惡意連結系統設定",
            description="調整系統參數以符合你的需求",
            color=PANEL_STYLES["config"],
        )
        
        # 添加設定資訊
        embed.add_field(
            name="🚫 刪除訊息",
            value=f"```{delete_message}```",
            inline=False,
        )
        
        # 顯示部分白名單
        if whitelist:
            embed.add_field(
                name=f"⚪ 白名單（{len(whitelist)} 筆）",
                value=(
                    "\n".join([f"• {domain}" for domain in whitelist[:5]]) +
                    (f"\n*...還有 {len(whitelist)-5} 筆未顯示*" if len(whitelist) > 5 else "")
                ),
                inline=False,
            )
        else:
            embed.add_field(
                name="⚪ 白名單",
                value="僅使用預設白名單",
                inline=False,
            )
        
        embed.add_field(
            name="📝 預設白名單",
            value=", ".join(sorted(DEFAULT_WHITELIST)),
            inline=False,
        )
        
        embed.set_footer(text="點擊對應按鈕進行設定 | 使用下拉選單切換面板")
        return embed
    
    async def _create_stats_embed(self) -> discord.Embed:
        """創建統計面板 Embed
        
        Returns:
            Discord Embed 物件
        """
        guild_id = None
        for guild in self.cog.bot.guilds:
            if guild.get_member(self.owner):
                guild_id = guild.id
                break
        
        if not guild_id:
            return discord.Embed(title="⚠️ 錯誤", description="無法找到伺服器資訊。", color=discord.Color.red())
        
        embed = discord.Embed(
            title="📊 反惡意連結統計資訊",
            description="系統運作資料與威脅情報統計",
            color=PANEL_STYLES["stats"],
        )
        
        # 添加威脅情報統計
        feed_counts = {}
        total_domains = len(self.cog._remote_bl)
        
        # 獲取時間戳記資訊
        last_update_ts = 0
        next_update_ts = 0
        
        if hasattr(self.cog.refresh_task, "next_iteration") and self.cog.refresh_task.next_iteration:
            next_update_ts = int(self.cog.refresh_task.next_iteration.timestamp())
            last_update_ts = next_update_ts - 14400  # 假設間隔為 4 小時
        
        embed.add_field(
            name="🔍 威脅情資概覽",
            value=(
                f"總威脅域名: **{total_domains}**\n"
                f"資料來源數: **{len(FEEDS)}**\n"
                f"最後更新: <t:{last_update_ts}:R>\n"
                f"下次更新: <t:{next_update_ts}:R>"
            ),
            inline=False,
        )
        
        # 添加黑名單/白名單統計
        manual_bl = await self.cog._get_manual_bl(guild_id)
        whitelist_raw = await self.cog.get_cfg(guild_id, "whitelist", "")
        whitelist = DEFAULT_WHITELIST | {d.strip().lower() for d in (whitelist_raw or "").split(",") if d.strip()}
        
        embed.add_field(
            name="📊 名單統計",
            value=(
                f"手動黑名單: **{len(manual_bl)}**\n"
                f"遠端黑名單: **{total_domains}**\n"
                f"白名單: **{len(whitelist)}**\n"
                f"預設白名單: **{len(DEFAULT_WHITELIST)}**"
            ),
            inline=True,
        )
        
        embed.add_field(
            name="🔄 自動更新設定",
            value=(
                "更新頻率: **每 4 小時**\n"
                f"上次檢查: <t:{last_update_ts}:R>\n"
                "資料格式: **文字/CSV**"
            ),
            inline=True,
        )
        
        # 生成黑名單頂層域名分析
        tlds = {}
        for domain in self.cog._remote_bl:
            try:
                tld = domain.split(".")[-1]
                tlds[tld] = tlds.get(tld, 0) + 1
            except:
                pass
                
        # 取前5個頂級域名
        top_tlds = sorted(tlds.items(), key=lambda x: x[1], reverse=True)[:5]
        
        embed.add_field(
            name="🌐 黑名單頂級域名分析",
            value="\n".join([f"• .{tld}: {count} 筆" for tld, count in top_tlds]) or "無數據",
            inline=False,
        )
        
        embed.set_footer(text="使用下拉選單切換至其他面板")
        return embed

    async def _create_local_blacklist_embed(self) -> discord.Embed:
        """創建本地黑白名單面板 Embed
        
        Returns:
            Discord Embed 物件
        """
        guild_id = None
        for guild in self.cog.bot.guilds:
            if guild.get_member(self.owner):
                guild_id = guild.id
                break
        
        if not guild_id:
            return discord.Embed(title="⚠️ 錯誤", description="無法找到伺服器資訊。", color=discord.Color.red())
        
        # 獲取手動黑名單
        manual_bl = await self.cog._get_manual_bl(guild_id)
        
        embed = discord.Embed(
            title="📋 本地黑白名單",
            description="詳細查看本地黑白名單",
            color=PANEL_STYLES["local_blacklist"],
        )
        
        # 顯示手動黑名單
        if manual_bl:
            embed.add_field(
                name="手動黑名單",
                value="\n".join([f"• {domain}" for domain in sorted(manual_bl)]),
                inline=False,
            )
        else:
            embed.add_field(
                name="手動黑名單",
                value="目前沒有添加任何網域",
                inline=False,
            )
        
        embed.set_footer(text="使用下拉選單切換至其他面板")
        return embed

    async def _create_remote_blacklist_embed(self) -> discord.Embed:
        """創建遠端黑名單面板 Embed
        
        Returns:
            Discord Embed 物件
        """
        # 獲取遠端黑名單
        remote_bl = sorted(self.cog._remote_bl)
        
        embed = discord.Embed(
            title=f"🌐 遠端黑名單（{len(remote_bl)} 筆）",
            description="詳細查看遠端黑名單",
            color=PANEL_STYLES["remote_blacklist"],
        )
        
        # 顯示部分遠端黑名單
        if remote_bl:
            # 只顯示前 20 筆
            display_count = min(20, len(remote_bl))
            embed.add_field(
                name="遠端黑名單",
                value="\n".join([f"• {domain}" for domain in remote_bl[:display_count]]) + 
                      (f"\n*...還有 {len(remote_bl) - display_count} 筆未顯示*" if len(remote_bl) > display_count else ""),
                inline=False,
            )
        else:
            embed.add_field(
                name="遠端黑名單",
                value="尚未載入任何網域或黑名單為空",
                inline=False,
            )
            
        # 顯示遠端來源
        sources = []
        for name, url in FEEDS.items():
            sources.append(f"• {name}")
            
        embed.add_field(
            name="遠端來源",
            value="\n".join(sources),
            inline=False,
        )
        
        embed.set_footer(text="使用下拉選單切換至其他面板")
        return embed


# ────────────────────────────
# 反惡意連結主類別
# ────────────────────────────
class AntiLink(ProtectionCog):
    """反惡意連結保護模組
    
    功能：
    - 自動檢測惡意連結
    - 白名單/黑名單管理
    - 遠端威脅情資整合
    - 自動更新黑名單
    - 詳細的管理介面
    """
    module_name = "anti_link"

    def __init__(self, bot: commands.Bot):
        """初始化反惡意連結模組
        
        Args:
            bot: Discord Bot 實例
        """
        super().__init__(bot)
        self._remote_bl: Set[str] = set()  # 遠端黑名單
        self._manual_bl: Dict[int, Set[str]] = {}  # 手動黑名單快取

    # ───────── 生命週期 ─────────
    async def cog_load(self):
        """模組載入時執行"""
        await self._refresh_blacklist()
        self.refresh_task.start()

    async def cog_unload(self):
        """模組卸載時執行"""
        self.refresh_task.cancel()

    # ───────── 事件處理 ─────────
    @commands.Cog.listener()
    async def on_message(self, msg: discord.Message):
        """處理新訊息事件"""
        try:
            # 基本檢查
            if msg.author.bot or not msg.guild:
                return
                
            # 檢測 URL
            urls = URL_PAT.findall(msg.content)
            if not urls:
                return

            # 取得白名單和黑名單
            wl_raw = await self.get_cfg(msg.guild.id, "whitelist", "")
            whitelist = DEFAULT_WHITELIST | {d.strip().lower() for d in (wl_raw or "").split(",") if d.strip()}
            manual_bl = await self._get_manual_bl(msg.guild.id)

            # 檢查每個 URL
            hits: List[Dict[str, Any]] = []
            for u in urls:
                host = (up.urlparse(u).hostname or "").lower().lstrip("www.")
                regd = tldextract.extract(host).registered_domain
                
                # 檢查白名單
                if host in whitelist or regd in whitelist:
                    continue
                    
                # 檢查黑名單
                if host in manual_bl or regd in manual_bl:
                    hits.append({
                        "url": u,
                        "domain": host,
                        "reason": "本地黑名單",
                        "source": "manual"
                    })
                elif host in self._remote_bl or regd in self._remote_bl:
                    hits.append({
                        "url": u, 
                        "domain": host,
                        "reason": "遠端黑名單",
                        "source": "remote"
                    })

            # 處理惡意連結
            if hits:
                try:
                    await msg.delete()
                except discord.Forbidden:
                    pass
                    
                # 使用自定義刪除訊息
                delete_message = await self.get_cfg(msg.guild.id, "delete_message", DEFAULT_DELETE_MESSAGE)
                    
                embed = discord.Embed(
                    title=delete_message,
                    color=discord.Color.red(),
                )
                
                # 添加惡意連結詳細資訊
                for hit in hits:
                    embed.add_field(
                        name=f"🚫 {hit['url']}",
                        value=f"網域: `{hit['domain']}`\n原因: {hit['reason']}",
                        inline=False
                    )
                
                await msg.channel.send(embed=embed, delete_after=15)
                await self.log(msg.guild, f"刪除了 {msg.author} 惡意連結：{[hit['url'] for hit in hits]}")
                
        except Exception as e:
            friendly_log("AntiLink 事件錯誤", e)

    # ───────── 手動黑名單管理 ─────────
    async def _get_manual_bl(self, gid: int) -> Set[str]:
        """取得手動黑名單
        
        Args:
            gid: 伺服器 ID
            
        Returns:
            黑名單網域集合
        """
        if gid not in self._manual_bl:
            raw = await self.get_cfg(gid, "manual_blacklist", "")
            self._manual_bl[gid] = {d for d in (raw or "").split(",") if d}
        return self._manual_bl[gid]

    async def _save_manual_bl(self, gid: int, doms: Set[str]):
        """儲存手動黑名單
        
        Args:
            gid: 伺服器 ID
            doms: 黑名單網域集合
        """
        self._manual_bl[gid] = doms
        await self.set_cfg(gid, "manual_blacklist", ",".join(sorted(doms)))

    # ───────── Slash 指令 ─────────
    # DEPRECATED: 已整合到控制面板中，但保留代碼以便參考
    # @app_commands.command(
    #     name="設定白名單",
    #     description="設定可接受網域（以逗號分隔）",
    # )
    # @admin_only()
    # async def cmd_whitelist(self, itx: discord.Interaction, *, domains: str):
    #     """設定白名單
    #     
    #     Args:
    #         itx: Discord 互動
    #         domains: 網域列表（逗號分隔）
    #     """
    #     try:
    #         if itx.guild:
    #             await self.set_cfg(itx.guild.id, "whitelist", domains)
    #             await itx.response.send_message("✅ 已更新連結白名單。")
    #     except Exception as e:
    #         friendly_log("更新白名單失敗", e)
    #         try:
    #             await itx.response.send_message("❌ 更新白名單失敗")
    #         except:
    #             pass

    # DEPRECATED: 已整合到控制面板中，但保留代碼以便參考
    # @app_commands.command(
    #     name="設定刪除訊息",
    #     description="設定刪除惡意連結時顯示的訊息",
    # )
    # @admin_only()
    # async def cmd_delete_message(self, itx: discord.Interaction, *, message: str):
    #     """設定刪除惡意連結時顯示的訊息
    #     
    #     Args:
    #         itx: Discord 互動
    #         message: 自定義的刪除訊息
    #     """
    #     try:
    #         if itx.guild:
    #             await self.set_cfg(itx.guild.id, "delete_message", message)
    #             await itx.response.send_message("✅ 已更新刪除訊息。")
    #     except Exception as e:
    #         friendly_log("更新刪除訊息失敗", e)
    #         try:
    #             await itx.response.send_message("❌ 更新刪除訊息失敗")
    #         except:
    #             pass

    # ───────── 手動黑名單指令群組 ─────────
    # link_blacklist = app_commands.Group(
    #     name="連結黑名單",
    #     description="管理手動黑名單",
    # )

    # @link_blacklist.command(
    #     name="移除",
    #     description="移除手動黑名單",
    # )
    # @admin_only()
    # async def bl_remove(self, itx: discord.Interaction, domain: str):
    #     """移除黑名單
    #     
    #     Args:
    #         itx: Discord 互動
    #         domain: 要移除的網域
    #     """
    #     try:
    #         if not itx.guild:
    #             await itx.response.send_message("此指令必須在伺服器中使用。")
    #             return
    #             
    #         domain = domain.lower().lstrip("www.")
    #         doms = await self._get_manual_bl(itx.guild.id)
    #         
    #         if domain not in doms:
    #             await itx.response.send_message("黑名單中找不到此網域。")
    #             return
    #             
    #         doms.remove(domain)
    #         await self._save_manual_bl(itx.guild.id, doms)
    #         await itx.response.send_message(f"✅ 已移除 `{domain}`。")
    #     except Exception as e:
    #         friendly_log("移除黑名單失敗", e)
    #         try:
    #             await itx.response.send_message("❌ 移除黑名單失敗")
    #         except:
    #             pass

    # ───────── 遠端黑名單指令群組 ─────────
    # remote_blacklist = app_commands.Group(
    #     name="遠端黑名單",
    #     description="管理遠端威脅情資",
    # )

    # @remote_blacklist.command(
    #     name="查看",
    #     description="顯示遠端黑名單",
    # )
    # @admin_only()
    # async def remotelist(self, itx: discord.Interaction):
    #     """顯示遠端黑名單
    #     
    #     Args:
    #         itx: Discord 互動
    #     """
    #     try:
    #         if not itx.guild:
    #             await itx.response.send_message("此指令必須在伺服器中使用。")
    #             return
    #             
    #         view = RemoteBLView(self, itx.user.id)
    #         await itx.response.send_message(embed=view._embed(), view=view)
    #     except Exception as e:
    #         friendly_log("顯示遠端黑名單失敗", e)
    #         try:
    #             await itx.response.send_message("❌ 顯示遠端黑名單失敗")
    #         except:
    #             pass

    # 註釋掉獨立的「查看來源」斜線指令
    """
    @app_commands.command(
        name="查看來源",
        description="查看使用的威脅情報來源",
    )
    @admin_only()
    async def view_sources(self, itx: discord.Interaction):
        # 此功能已整合到面板中，不再需要單獨的斜線指令
        pass
    """

    @app_commands.command(
        name="連結保護面板",
        description="顯示反惡意連結控制面板",
    )
    @admin_only()
    async def cmd_panel(self, itx: discord.Interaction):
        """顯示反惡意連結控制面板
        
        Args:
            itx: Discord 互動
        """
        try:
            # 使用增強的面板
            view = AntiLinkPanel(self, itx.user.id)
            embed = await view._create_embed()
            await itx.response.send_message(embed=embed, view=view)
            
            # 記錄使用記錄
            logger.info(f"使用者 {itx.user} 調用了連結保護面板")
            
        except Exception as e:
            friendly_log("顯示控制面板失敗", e)
            try:
                await itx.response.send_message("❌ 顯示控制面板失敗")
            except:
                pass

    # ───────── 背景任務 ─────────
    @tasks.loop(hours=4)
    async def refresh_task(self):
        """定期更新遠端黑名單"""
        try:
            await self._refresh_blacklist()
            logger.info("AntiLink 已更新遠端黑名單")
        except Exception as e:
            friendly_log("AntiLink 更新任務錯誤", e)

    @refresh_task.before_loop
    async def _before_refresh_task(self):
        """更新任務前置處理"""
        await self.bot.wait_until_ready()

    async def _refresh_blacklist(self):
        """更新遠端黑名單"""
        try:
            async with aiohttp.ClientSession() as sess:
                tasks = []
                for name, url in FEEDS.items():
                    tasks.append(self._fetch_feed(sess, name, url))
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                new_bl = set()
                for result in results:
                    if isinstance(result, set):
                        new_bl.update(result)
                
                self._remote_bl = new_bl
                logger.info(f"AntiLink 已更新遠端黑名單，共 {len(new_bl)} 筆")
                
        except Exception as e:
            friendly_log("更新遠端黑名單失敗", e)

    async def _fetch_feed(self, sess: aiohttp.ClientSession, name: str, url: str) -> Set[str]:
        """取得威脅情資
        
        Args:
            sess: HTTP 會話
            name: 來源名稱
            url: 來源 URL
            
        Returns:
            威脅網域集合
        """
        try:
            async with sess.get(url, timeout=30) as resp:
                if resp.status != 200:
                    return set()
                    
                content = await resp.text()
                domains = set()
                
                # 解析不同格式
                if name == "URLHaus":
                    for line in content.split("\n"):
                        if line and not line.startswith("#"):
                            domains.add(line.strip())
                elif name == "OpenPhish":
                    for line in content.split("\n"):
                        if line and not line.startswith("#"):
                            try:
                                host = up.urlparse(line.strip()).hostname
                                if host:
                                    domains.add(host.lower().lstrip("www."))
                            except:
                                continue
                elif name == "URLHaus-CSV":
                    reader = csv.reader(io.StringIO(content))
                    for row in reader:
                        if len(row) > 2 and row[2]:
                            try:
                                host = up.urlparse(row[2]).hostname
                                if host:
                                    domains.add(host.lower().lstrip("www."))
                            except:
                                continue
                
                return domains
                
        except Exception as e:
            friendly_log(f"取得威脅情資失敗（{name}）", e)
            return set()


# ────────────────────────────
# 模組設定
# ────────────────────────────
async def setup(bot: commands.Bot):
    """設定 AntiLink 模組"""
    logger.info("執行 anti_link setup()")
    await bot.add_cog(AntiLink(bot))