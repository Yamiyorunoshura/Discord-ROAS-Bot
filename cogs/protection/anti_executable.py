# cogs/protection/anti_executable.py ── 反可執行檔案保護模組 (Discord.py 2.5.2 兼容版)
# ============================================================
# 功能說明：
#  - 自動檢測並刪除可執行檔案
#  - 支援多種檔案格式檢測
#  - 支援白名單機制
#  - 提供詳細的管理介面
#  - 整合檔案特徵檢測
# 
# Discord.py 2.5.2 兼容性修復：
#  - 修正 button 裝飾器使用方式
#  - 修正 ButtonStyle 兼容性
#  - 完善型別提示
#  - 改進錯誤處理
#
# 更新日誌:
# v1.5.3 - 優化斜線指令使用體驗
#  - 更改指令名稱為「執行檔保護面板」
#  - 將面板設為公開可見
#  - 添加面板自動更新功能
#  - 取消註冊已整合到面板中的單獨指令
# v1.5.4 - 優化面板交互體驗
#  - 按鈕按下後直接更新現有面板而非發送新面板
#  - 將「支援格式」功能整合到設定面板中
#  - 取消獨立的「支援格式」斜線指令
# v1.5.5 - 增強管理功能
#  - 添加白名單、黑名單管理按鈕和對話框
#  - 添加自定義檔案格式管理功能
#  - 支持伺服器自定義可檢測的檔案類型
# ============================================================

from __future__ import annotations
import re, asyncio, logging, discord, aiohttp
from typing import Set, List, Optional, Dict, Any, Union, cast
from discord import app_commands, ui
from discord.ext import commands
from .base import ProtectionCog, admin_only, handle_error, friendly_log

# ────────────────────────────
# 常數定義
# ────────────────────────────
# 可執行檔案副檔名
DEFAULT_EXECUTABLE_EXTENSIONS = {
    # Windows 可執行檔
    "exe", "msi", "bat", "cmd", "com", "pif", "scr", "vbs", "js", "wsf", "hta",
    # Linux/Unix 可執行檔
    "sh", "bash", "zsh", "fish", "py", "pl", "rb", "php", "jar", "deb", "rpm",
    # macOS 可執行檔
    "app", "dmg", "pkg", "command", "tool",
    # 其他危險格式
    "lnk", "url", "reg", "inf", "sys", "dll", "ocx", "cab", "iso", "img",
}

# 全局變量，由每個伺服器的配置更新
EXECUTABLE_EXTENSIONS = set(DEFAULT_EXECUTABLE_EXTENSIONS)

# 檔案特徵檢測（魔術數字）
MAGIC_SIGNATURES = {
    b"MZ": "Windows PE",  # Windows 可執行檔
    b"\x7fELF": "ELF",    # Linux 可執行檔
    b"#!": "Shell Script", # Shell 腳本
    b"PK\x03\x04": "ZIP Archive", # ZIP 檔案
    b"Rar!": "RAR Archive", # RAR 檔案
}

# 檔案大小限制（MB）
MAX_FILE_SIZE = 50

logger = logging.getLogger("protection")


# ────────────────────────────
# 設定面板 View (Discord.py 2.5.2 兼容版)
# ────────────────────────────
class ExecutableSettingsView(ui.View):
    """可執行檔案設定面板"""
    
    def __init__(self, cog: "AntiExecutable", owner: int):
        """初始化設定面板
        
        Args:
            cog: AntiExecutable 實例
            owner: 擁有者 ID
        """
        super().__init__(timeout=300)
        self.cog, self.owner = cog, owner
        self.message = None  # 儲存面板消息的引用
        
        # 添加按鈕
        self.add_item(WhitelistButton())
        self.add_item(BlacklistButton())
        self.add_item(StatusButton())
        self.add_item(HelpButton())  # 新手教學按鈕
        self.add_item(TestButton())  # 功能測試按鈕
        self.add_item(FormatsButton())  # 新增支援格式按鈕
        self.add_item(ToggleButton())  # 啟用/停用按鈕
        self.add_item(CloseButton())  # 關閉面板按鈕
        
        # 開始自動更新
        self.update_task = None

    async def start_auto_update(self, message):
        """開始自動更新面板
        
        Args:
            message: 面板消息
        """
        self.message = message
        if self.update_task:
            self.update_task.cancel()
        self.update_task = asyncio.create_task(self._update_loop())
    
    async def _update_loop(self):
        """自動更新面板循環"""
        try:
            while True:
                await asyncio.sleep(60)  # 每分鐘更新一次
                if self.message and not self.is_finished():
                    await self.update_panel()
        except asyncio.CancelledError:
            pass  # 任務被取消
        except Exception as e:
            friendly_log("面板自動更新錯誤", e)
    
    async def update_panel(self):
        """更新面板內容"""
        try:
            if not self.message or not self.message.guild:
                return
            
            # 創建新的 Embed 來更新內容
            guild = self.message.guild
            enabled = await self.cog.get_cfg(guild.id, "enabled", "true")
            whitelist = await self.cog.get_cfg(guild.id, "whitelist", "")
            blacklist = await self.cog.get_cfg(guild.id, "blacklist", "")
            
            whitelist_count = len([d for d in whitelist.split(",") if d.strip()]) if whitelist else 0
            blacklist_count = len([d for d in blacklist.split(",") if d.strip()]) if blacklist else 0
            
            embed = discord.Embed(
                title="⚙️ 可執行檔案保護設定",
                description="此面板可協助您管理可執行檔案保護功能，防止惡意軟體透過Discord傳播。",
                color=discord.Color.blue(),
            )
            
            embed.add_field(
                name="📋 白名單管理",
                value="管理可信任的網域，這些網域的檔案將不會被檢查。",
                inline=True
            )
            
            embed.add_field(
                name="🚫 黑名單管理",
                value="管理不可信任的網域，這些網域的檔案將被直接刪除。",
                inline=True
            )
            
            embed.add_field(
                name="📊 狀態查看",
                value="查看目前模組的運作狀態及相關設定。",
                inline=True
            )
            
            embed.add_field(
                name="模組狀態",
                value="✅ 啟用" if enabled and enabled.lower() == "true" else "❌ 停用",
                inline=True
            )
            
            embed.add_field(
                name="白名單/黑名單",
                value=f"白名單: {whitelist_count} 項 / 黑名單: {blacklist_count} 項",
                inline=True
            )
            
            embed.add_field(
                name="上次更新",
                value=f"<t:{int(discord.utils.utcnow().timestamp())}:R>",
                inline=True
            )
            
            # 更新面板消息
            await self.message.edit(embed=embed)
        except Exception as e:
            friendly_log("更新面板失敗", e)
    
    async def on_timeout(self):
        """面板超時處理"""
        try:
            # 取消自動更新任務
            if self.update_task:
                self.update_task.cancel()
                
            # 更新消息添加超時提示
            if self.message:
                # 因為 ui.Button 的 disabled 屬性在某些版本可能無法直接訪問
                # 所以我們只添加一個超時提示而不禁用按鈕
                await self.message.edit(content="⏰ 面板已過期，請重新開啟")
        except Exception as e:
            friendly_log("面板超時處理錯誤", e)

    async def interaction_check(self, itx: discord.Interaction) -> bool:
        """檢查互動權限"""
        if itx.user.id != self.owner:
            await itx.response.send_message("只能由指令發起者操作。", ephemeral=True)
            return False
        return True


class WhitelistButton(ui.Button):
    """白名單管理按鈕"""
    
    def __init__(self):
        super().__init__(label="📋 白名單", style=discord.ButtonStyle.success)
    
    async def callback(self, itx: discord.Interaction):
        """顯示白名單管理"""
        view: ExecutableSettingsView = self.view  # type: ignore
        try:
            if not itx.guild:
                await itx.response.send_message("此功能必須在伺服器中使用。", ephemeral=True)
                return
                
            # 使用斷言和 cast 來讓 linter 知道 guild 存在
            assert itx.guild is not None
            guild = cast(discord.Guild, itx.guild)
                
            whitelist = await view.cog.get_cfg(guild.id, "whitelist", "")
            domains = [d.strip() for d in whitelist.split(",") if d.strip()] if whitelist else []
            
            embed = discord.Embed(
                title="📋 可執行檔案白名單",
                description="從這些網域下載的可執行檔案將被信任（不會被檢查）：",
                color=discord.Color.green(),
            )
            
            if domains:
                embed.add_field(
                    name="受信任下載來源",
                    value="\n".join(f"• {domain}" for domain in domains),
                    inline=False
                )
            else:
                embed.add_field(
                    name="受信任下載來源",
                    value="（目前為空）",
                    inline=False
                )
            
            # 更新現有面板而非發送新消息
            if itx.message:
                # 創建白名單管理視圖
                whitelist_view = ui.View(timeout=300)
                whitelist_view.add_item(AddWhitelistButton(view))
                whitelist_view.add_item(RemoveWhitelistButton(view))
                whitelist_view.add_item(ReturnButton(view))
                whitelist_view.add_item(CloseButton())
                
                await itx.response.edit_message(embed=embed, view=whitelist_view)
            else:
                await itx.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            friendly_log("顯示白名單失敗", e)
            await itx.response.send_message("❌ 顯示白名單失敗", ephemeral=True)


class AddWhitelistButton(ui.Button):
    """添加白名單按鈕"""
    
    def __init__(self, original_view: ui.View):
        super().__init__(label="添加網域", emoji="➕", style=discord.ButtonStyle.success)
        self.original_view = original_view
    
    async def callback(self, itx: discord.Interaction):
        """顯示添加白名單對話框"""
        view: ExecutableSettingsView = self.original_view  # type: ignore
        
        # 顯示添加白名單對話框
        modal = AddWhitelistModal(view)
        await itx.response.send_modal(modal)


class RemoveWhitelistButton(ui.Button):
    """移除白名單按鈕"""
    
    def __init__(self, original_view: ui.View):
        super().__init__(label="移除網域", emoji="➖", style=discord.ButtonStyle.danger)
        self.original_view = original_view
    
    async def callback(self, itx: discord.Interaction):
        """顯示移除白名單對話框"""
        view: ExecutableSettingsView = self.original_view  # type: ignore
        
        # 顯示移除白名單對話框
        modal = RemoveWhitelistModal(view)
        await itx.response.send_modal(modal)


class AddWhitelistModal(ui.Modal, title="添加白名單網域"):
    """添加白名單對話框"""
    
    domain = ui.TextInput(
        label="網域",
        style=discord.TextStyle.short,
        placeholder="輸入要添加的信任網域，例如：example.com",
        required=True,
    )
    
    def __init__(self, view: ExecutableSettingsView):
        super().__init__()
        self.view = view
    
    async def on_submit(self, itx: discord.Interaction):
        """提交時處理"""
        try:
            if not itx.guild:
                await itx.response.send_message("無法找到伺服器資訊。", ephemeral=True)
                return
                
            # 使用斷言和 cast 來讓 linter 知道 guild 存在
            assert itx.guild is not None
            guild = cast(discord.Guild, itx.guild)
                
            domain = self.domain.value.lower().lstrip("www.")
            whitelist = await self.view.cog.get_cfg(guild.id, "whitelist", "")
            domains = [d.strip() for d in whitelist.split(",") if d.strip()] if whitelist else []
            
            if domain in domains:
                await itx.response.send_message("此網域已在白名單中。", ephemeral=True)
                return
                
            domains.append(domain)
            await self.view.cog.set_cfg(guild.id, "whitelist", ",".join(domains))
            
            # 更新白名單視圖
            whitelist = await self.view.cog.get_cfg(guild.id, "whitelist", "")
            updated_domains = [d.strip() for d in whitelist.split(",") if d.strip()] if whitelist else []
            
            embed = discord.Embed(
                title="📋 可執行檔案白名單",
                description=f"✅ 已成功加入 `{domain}` 至白名單",
                color=discord.Color.green(),
            )
            
            # 顯示白名單
            if updated_domains:
                embed.add_field(
                    name=f"受信任下載來源（{len(updated_domains)} 筆）",
                    value="\n".join(f"• {domain}" for domain in updated_domains),
                    inline=False
                )
            
            # 更新面板
            whitelist_view = ui.View(timeout=300)
            whitelist_view.add_item(AddWhitelistButton(self.view))
            whitelist_view.add_item(RemoveWhitelistButton(self.view))
            whitelist_view.add_item(ReturnButton(self.view))
            whitelist_view.add_item(CloseButton())
            
            await itx.response.edit_message(embed=embed, view=whitelist_view)
            
        except Exception as e:
            friendly_log("添加白名單失敗", e)
            await itx.response.send_message(f"❌ 添加白名單失敗: {str(e)}", ephemeral=True)


class RemoveWhitelistModal(ui.Modal, title="移除白名單網域"):
    """移除白名單對話框"""
    
    domain = ui.TextInput(
        label="網域",
        style=discord.TextStyle.short,
        placeholder="輸入要移除的網域，必須完全匹配",
        required=True,
    )
    
    def __init__(self, view: ExecutableSettingsView):
        super().__init__()
        self.view = view
    
    async def on_submit(self, itx: discord.Interaction):
        """提交時處理"""
        try:
            if not itx.guild:
                await itx.response.send_message("無法找到伺服器資訊。", ephemeral=True)
                return
                
            # 使用斷言和 cast 來讓 linter 知道 guild 存在
            assert itx.guild is not None
            guild = cast(discord.Guild, itx.guild)
                
            domain = self.domain.value.lower().lstrip("www.")
            whitelist = await self.view.cog.get_cfg(guild.id, "whitelist", "")
            domains = [d.strip() for d in whitelist.split(",") if d.strip()] if whitelist else []
            
            if domain not in domains:
                await itx.response.send_message("白名單中找不到此網域。", ephemeral=True)
                return
                
            domains.remove(domain)
            await self.view.cog.set_cfg(guild.id, "whitelist", ",".join(domains))
            
            # 更新白名單視圖
            whitelist = await self.view.cog.get_cfg(guild.id, "whitelist", "")
            updated_domains = [d.strip() for d in whitelist.split(",") if d.strip()] if whitelist else []
            
            embed = discord.Embed(
                title="📋 可執行檔案白名單",
                description=f"✅ 已成功從白名單移除 `{domain}`",
                color=discord.Color.green(),
            )
            
            # 顯示白名單
            if updated_domains:
                embed.add_field(
                    name=f"受信任下載來源（{len(updated_domains)} 筆）",
                    value="\n".join(f"• {domain}" for domain in updated_domains),
                    inline=False
                )
            else:
                embed.add_field(
                    name="受信任下載來源",
                    value="（目前為空）",
                    inline=False
                )
            
            # 更新面板
            whitelist_view = ui.View(timeout=300)
            whitelist_view.add_item(AddWhitelistButton(self.view))
            whitelist_view.add_item(RemoveWhitelistButton(self.view))
            whitelist_view.add_item(ReturnButton(self.view))
            whitelist_view.add_item(CloseButton())
            
            await itx.response.edit_message(embed=embed, view=whitelist_view)
            
        except Exception as e:
            friendly_log("移除白名單失敗", e)
            await itx.response.send_message(f"❌ 移除白名單失敗: {str(e)}", ephemeral=True)


class BlacklistButton(ui.Button):
    """黑名單管理按鈕"""
    
    def __init__(self):
        super().__init__(label="🚫 黑名單", style=discord.ButtonStyle.danger)
    
    async def callback(self, itx: discord.Interaction):
        """顯示黑名單管理"""
        view: ExecutableSettingsView = self.view  # type: ignore
        try:
            if not itx.guild:
                await itx.response.send_message("此功能必須在伺服器中使用。", ephemeral=True)
                return
                
            # 使用斷言和 cast 來讓 linter 知道 guild 存在
            assert itx.guild is not None
            guild = cast(discord.Guild, itx.guild)
                
            blacklist = await view.cog.get_cfg(guild.id, "blacklist", "")
            domains = [d.strip() for d in blacklist.split(",") if d.strip()] if blacklist else []
            
            embed = discord.Embed(
                title="🚫 可執行檔案黑名單",
                description="目前黑名單中的網域：",
                color=discord.Color.red(),
            )
            
            if domains:
                embed.add_field(
                    name="黑名單網域",
                    value="\n".join(f"• {domain}" for domain in domains),
                    inline=False
                )
            else:
                embed.add_field(
                    name="黑名單網域",
                    value="（目前為空）",
                    inline=False
                )
            
            # 更新現有面板而非發送新消息
            if itx.message:
                # 創建黑名單管理視圖
                blacklist_view = ui.View(timeout=300)
                blacklist_view.add_item(AddBlacklistButton(view))
                blacklist_view.add_item(RemoveBlacklistButton(view))
                blacklist_view.add_item(ReturnButton(view))
                blacklist_view.add_item(CloseButton())
                
                await itx.response.edit_message(embed=embed, view=blacklist_view)
            else:
                await itx.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            friendly_log("顯示黑名單失敗", e)
            await itx.response.send_message("❌ 顯示黑名單失敗", ephemeral=True)


class AddBlacklistButton(ui.Button):
    """添加黑名單按鈕"""
    
    def __init__(self, original_view: ui.View):
        super().__init__(label="添加網域", emoji="➕", style=discord.ButtonStyle.success)
        self.original_view = original_view
    
    async def callback(self, itx: discord.Interaction):
        """顯示添加黑名單對話框"""
        view: ExecutableSettingsView = self.original_view  # type: ignore
        
        # 顯示添加黑名單對話框
        modal = AddBlacklistModal(view)
        await itx.response.send_modal(modal)


class RemoveBlacklistButton(ui.Button):
    """移除黑名單按鈕"""
    
    def __init__(self, original_view: ui.View):
        super().__init__(label="移除網域", emoji="➖", style=discord.ButtonStyle.danger)
        self.original_view = original_view
    
    async def callback(self, itx: discord.Interaction):
        """顯示移除黑名單對話框"""
        view: ExecutableSettingsView = self.original_view  # type: ignore
        
        # 顯示移除黑名單對話框
        modal = RemoveBlacklistModal(view)
        await itx.response.send_modal(modal)


class AddBlacklistModal(ui.Modal, title="添加黑名單網域"):
    """添加黑名單對話框"""
    
    domain = ui.TextInput(
        label="網域",
        style=discord.TextStyle.short,
        placeholder="輸入要添加的危險網域，例如：malware.com",
        required=True,
    )
    
    def __init__(self, view: ExecutableSettingsView):
        super().__init__()
        self.view = view
    
    async def on_submit(self, itx: discord.Interaction):
        """提交時處理"""
        try:
            if not itx.guild:
                await itx.response.send_message("無法找到伺服器資訊。", ephemeral=True)
                return
                
            # 使用斷言和 cast 來讓 linter 知道 guild 存在
            assert itx.guild is not None
            guild = cast(discord.Guild, itx.guild)
                
            domain = self.domain.value.lower().lstrip("www.")
            blacklist = await self.view.cog.get_cfg(guild.id, "blacklist", "")
            domains = [d.strip() for d in blacklist.split(",") if d.strip()] if blacklist else []
            
            if domain in domains:
                await itx.response.send_message("此網域已在黑名單中。", ephemeral=True)
                return
                
            domains.append(domain)
            await self.view.cog.set_cfg(guild.id, "blacklist", ",".join(domains))
            
            # 更新黑名單視圖
            blacklist = await self.view.cog.get_cfg(guild.id, "blacklist", "")
            updated_domains = [d.strip() for d in blacklist.split(",") if d.strip()] if blacklist else []
            
            embed = discord.Embed(
                title="🚫 可執行檔案黑名單",
                description=f"✅ 已成功加入 `{domain}` 至黑名單",
                color=discord.Color.red(),
            )
            
            # 顯示黑名單
            if updated_domains:
                embed.add_field(
                    name=f"黑名單網域（{len(updated_domains)} 筆）",
                    value="\n".join(f"• {domain}" for domain in updated_domains),
                    inline=False
                )
            
            # 更新面板
            blacklist_view = ui.View(timeout=300)
            blacklist_view.add_item(AddBlacklistButton(self.view))
            blacklist_view.add_item(RemoveBlacklistButton(self.view))
            blacklist_view.add_item(ReturnButton(self.view))
            blacklist_view.add_item(CloseButton())
            
            await itx.response.edit_message(embed=embed, view=blacklist_view)
            
        except Exception as e:
            friendly_log("添加黑名單失敗", e)
            await itx.response.send_message(f"❌ 添加黑名單失敗: {str(e)}", ephemeral=True)


class RemoveBlacklistModal(ui.Modal, title="移除黑名單網域"):
    """移除黑名單對話框"""
    
    domain = ui.TextInput(
        label="網域",
        style=discord.TextStyle.short,
        placeholder="輸入要移除的網域，必須完全匹配",
        required=True,
    )
    
    def __init__(self, view: ExecutableSettingsView):
        super().__init__()
        self.view = view
    
    async def on_submit(self, itx: discord.Interaction):
        """提交時處理"""
        try:
            if not itx.guild:
                await itx.response.send_message("無法找到伺服器資訊。", ephemeral=True)
                return
                
            # 使用斷言和 cast 來讓 linter 知道 guild 存在
            assert itx.guild is not None
            guild = cast(discord.Guild, itx.guild)
                
            domain = self.domain.value.lower().lstrip("www.")
            blacklist = await self.view.cog.get_cfg(guild.id, "blacklist", "")
            domains = [d.strip() for d in blacklist.split(",") if d.strip()] if blacklist else []
            
            if domain not in domains:
                await itx.response.send_message("黑名單中找不到此網域。", ephemeral=True)
                return
                
            domains.remove(domain)
            await self.view.cog.set_cfg(guild.id, "blacklist", ",".join(domains))
            
            # 更新黑名單視圖
            blacklist = await self.view.cog.get_cfg(guild.id, "blacklist", "")
            updated_domains = [d.strip() for d in blacklist.split(",") if d.strip()] if blacklist else []
            
            embed = discord.Embed(
                title="🚫 可執行檔案黑名單",
                description=f"✅ 已成功從黑名單移除 `{domain}`",
                color=discord.Color.red(),
            )
            
            # 顯示黑名單
            if updated_domains:
                embed.add_field(
                    name=f"黑名單網域（{len(updated_domains)} 筆）",
                    value="\n".join(f"• {domain}" for domain in updated_domains),
                    inline=False
                )
            else:
                embed.add_field(
                    name="黑名單網域",
                    value="（目前為空）",
                    inline=False
                )
            
            # 更新面板
            blacklist_view = ui.View(timeout=300)
            blacklist_view.add_item(AddBlacklistButton(self.view))
            blacklist_view.add_item(RemoveBlacklistButton(self.view))
            blacklist_view.add_item(ReturnButton(self.view))
            blacklist_view.add_item(CloseButton())
            
            await itx.response.edit_message(embed=embed, view=blacklist_view)
            
        except Exception as e:
            friendly_log("移除黑名單失敗", e)
            await itx.response.send_message(f"❌ 移除黑名單失敗: {str(e)}", ephemeral=True)


class StatusButton(ui.Button):
    """狀態查看按鈕"""
    
    def __init__(self):
        super().__init__(label="📊 狀態", style=discord.ButtonStyle.primary)
    
    async def callback(self, itx: discord.Interaction):
        """顯示模組狀態"""
        view: ExecutableSettingsView = self.view  # type: ignore
        try:
            if not itx.guild:
                await itx.response.send_message("此功能必須在伺服器中使用。", ephemeral=True)
                return
                
            enabled = await view.cog.get_cfg(itx.guild.id, "enabled", "true")
            whitelist = await view.cog.get_cfg(itx.guild.id, "whitelist", "")
            blacklist = await view.cog.get_cfg(itx.guild.id, "blacklist", "")
            
            whitelist_count = len([d for d in whitelist.split(",") if d.strip()]) if whitelist else 0
            blacklist_count = len([d for d in blacklist.split(",") if d.strip()]) if blacklist else 0
            
            embed = discord.Embed(
                title="📊 反可執行檔案模組狀態",
                color=discord.Color.blue(),
            )
            
            embed.add_field(
                name="模組狀態",
                value="✅ 啟用" if enabled and enabled.lower() == "true" else "❌ 停用",
                inline=True
            )
            embed.add_field(
                name="白名單數量",
                value=str(whitelist_count),
                inline=True
            )
            embed.add_field(
                name="黑名單數量",
                value=str(blacklist_count),
                inline=True
            )
            embed.add_field(
                name="支援格式",
                value=f"{len(EXECUTABLE_EXTENSIONS)} 種",
                inline=True
            )
            embed.add_field(
                name="檔案大小限制",
                value=f"{MAX_FILE_SIZE} MB",
                inline=True
            )
            
            # 更新現有面板而非發送新消息
            if itx.message:
                # 創建返回按鈕的 View
                return_view = ui.View(timeout=300)
                return_view.add_item(ReturnButton(view))
                return_view.add_item(CloseButton())
                
                await itx.response.edit_message(embed=embed, view=return_view)
            else:
                await itx.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            friendly_log("顯示狀態失敗", e)
            await itx.response.send_message("❌ 顯示狀態失敗", ephemeral=True)


class HelpButton(ui.Button):
    """新手教學按鈕"""
    
    def __init__(self):
        super().__init__(label="📖 新手教學", style=discord.ButtonStyle.secondary)
    
    async def callback(self, itx: discord.Interaction):
        """顯示新手教學"""
        view: ExecutableSettingsView = self.view  # type: ignore
        try:
            embed = discord.Embed(
                title="📖 反可執行檔案模組使用教學",
                description="本教學將幫助您了解如何使用反可執行檔案保護功能。",
                color=discord.Color.gold(),
            )
            
            embed.add_field(
                name="🔍 模組功能",
                value="自動檢測並刪除可執行檔案，防止惡意軟體透過Discord傳播。",
                inline=False
            )
            
            embed.add_field(
                name="⚙️ 基本設定",
                value=(
                    "1. 使用 `/執行檔保護面板` 開啟此設定介面\n"
                    "2. 使用狀態按鈕查看目前設定\n"
                    "3. 使用白名單/黑名單管理可信任/禁止的網域"
                ),
                inline=False
            )
            
            embed.add_field(
                name="📋 白名單管理",
                value=(
                    "- 添加可信任的網域，這些網域的檔案將不會被檢查\n"
                    "- 例如: `example.com`, `trusted-files.org`"
                ),
                inline=False
            )
            
            embed.add_field(
                name="🚫 黑名單管理",
                value=(
                    "- 添加不可信任的網域，這些網域的檔案將被直接刪除\n"
                    "- 例如: `malware.com`, `virus-download.net`"
                ),
                inline=False
            )
            
            embed.add_field(
                name="💡 使用提示",
                value=(
                    "- 建議將常用的安全下載網站加入白名單\n"
                    "- 可使用功能測試按鈕檢查模組是否正常運作\n"
                    "- 模組支援檢測多種可執行檔案格式，包括隱藏的可執行檔"
                ),
                inline=False
            )
            
            # 更新現有面板而非發送新消息
            if itx.message:
                # 創建返回按鈕的 View
                return_view = ui.View(timeout=300)
                return_view.add_item(ReturnButton(view))
                return_view.add_item(CloseButton())
                
                await itx.response.edit_message(embed=embed, view=return_view)
            else:
                await itx.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            friendly_log("顯示新手教學失敗", e)
            await itx.response.send_message("❌ 顯示新手教學失敗", ephemeral=True)


class TestButton(ui.Button):
    """功能測試按鈕"""
    
    def __init__(self):
        super().__init__(label="🛠️ 功能測試", style=discord.ButtonStyle.secondary)
    
    async def callback(self, itx: discord.Interaction):
        """執行功能測試"""
        view: ExecutableSettingsView = self.view  # type: ignore
        try:
            if not itx.guild:
                await itx.response.send_message("此功能必須在伺服器中使用。", ephemeral=True)
                return
                
            # 檢查模組是否啟用
            enabled = await view.cog.get_cfg(itx.guild.id, "enabled", "true")
            if not enabled or enabled.lower() != "true":
                await itx.response.send_message("⚠️ 模組目前處於停用狀態，請先啟用模組。", ephemeral=True)
                return
                
            # 模擬檢測過程
            await itx.response.defer(ephemeral=True)
            
            test_results = []
            
            # 測試 1: 檢查設定載入
            try:
                whitelist = await view.cog.get_cfg(itx.guild.id, "whitelist", "")
                blacklist = await view.cog.get_cfg(itx.guild.id, "blacklist", "")
                test_results.append("✅ 設定載入測試: 成功")
            except:
                test_results.append("❌ 設定載入測試: 失敗")
                
            # 測試 2: 檢查檔案副檔名檢測
            test_filename = "test.exe"
            if any(test_filename.lower().endswith(f".{ext}") for ext in EXECUTABLE_EXTENSIONS):
                test_results.append("✅ 副檔名檢測測試: 成功")
            else:
                test_results.append("❌ 副檔名檢測測試: 失敗")
                
            # 測試 3: 檢查白名單功能
            test_whitelist = {"example.com"}
            test_filename = "example.com/file.exe"
            if any(domain in test_filename for domain in test_whitelist):
                test_results.append("✅ 白名單功能測試: 成功")
            else:
                test_results.append("❌ 白名單功能測試: 失敗")
                
            # 測試 4: 檢查黑名單功能
            test_blacklist = {"malware.com"}
            test_filename = "malware.com/file.txt"
            if any(domain in test_filename for domain in test_blacklist):
                test_results.append("✅ 黑名單功能測試: 成功")
            else:
                test_results.append("❌ 黑名單功能測試: 失敗")
                
            # 顯示測試結果
            embed = discord.Embed(
                title="🛠️ 功能測試結果",
                description="\n".join(test_results),
                color=discord.Color.blue(),
            )
            
            embed.add_field(
                name="總結",
                value="✅ 模組運作正常" if all("✅" in result for result in test_results) else "⚠️ 模組可能存在問題",
                inline=False
            )
            
            await itx.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            friendly_log("執行功能測試失敗", e)
            await itx.followup.send("❌ 執行功能測試失敗", ephemeral=True)


# 添加返回按鈕類，用於從子面板返回主面板
class ReturnButton(ui.Button):
    """返回主面板按鈕"""
    
    def __init__(self, original_view: ui.View):
        super().__init__(label="返回", emoji="↩️", style=discord.ButtonStyle.secondary)
        self.original_view = original_view
    
    async def callback(self, itx: discord.Interaction):
        """返回主面板"""
        # 返回原始視圖
        view: ExecutableSettingsView = self.original_view  # type: ignore
        
        # 重新創建主面板 Embed
        if itx.guild:
            enabled = await view.cog.get_cfg(itx.guild.id, "enabled", "true")
            whitelist = await view.cog.get_cfg(itx.guild.id, "whitelist", "")
            blacklist = await view.cog.get_cfg(itx.guild.id, "blacklist", "")
            
            whitelist_count = len([d for d in whitelist.split(",") if d.strip()]) if whitelist else 0
            blacklist_count = len([d for d in blacklist.split(",") if d.strip()]) if blacklist else 0
            
            embed = discord.Embed(
                title="⚙️ 可執行檔案保護設定",
                description="此面板可協助您管理可執行檔案保護功能，防止惡意軟體透過Discord傳播。",
                color=discord.Color.blue(),
            )
            
            embed.add_field(
                name="📋 白名單管理",
                value="管理可信任的網域，這些網域的檔案將不會被檢查。",
                inline=True
            )
            
            embed.add_field(
                name="🚫 黑名單管理",
                value="管理不可信任的網域，這些網域的檔案將被直接刪除。",
                inline=True
            )
            
            embed.add_field(
                name="📊 狀態查看",
                value="查看目前模組的運作狀態及相關設定。",
                inline=True
            )
            
            embed.add_field(
                name="模組狀態",
                value="✅ 啟用" if enabled and enabled.lower() == "true" else "❌ 停用",
                inline=True
            )
            
            embed.add_field(
                name="白名單/黑名單",
                value=f"白名單: {whitelist_count} 項 / 黑名單: {blacklist_count} 項",
                inline=True
            )
            
            embed.add_field(
                name="上次更新",
                value=f"<t:{int(discord.utils.utcnow().timestamp())}:R>",
                inline=True
            )
            
            # 更新現有面板
            await itx.response.edit_message(embed=embed, view=view)
        else:
            await itx.response.send_message("❌ 無法獲取伺服器資訊", ephemeral=True)


class FormatsButton(ui.Button):
    """查看支援格式按鈕"""
    
    def __init__(self):
        super().__init__(label="📋 支援格式", style=discord.ButtonStyle.secondary)
    
    async def callback(self, itx: discord.Interaction):
        """顯示支援的檔案格式"""
        view: ExecutableSettingsView = self.view  # type: ignore
        try:
            if not itx.guild:
                await itx.response.send_message("此功能必須在伺服器中使用。", ephemeral=True)
                return
                
            # 使用斷言和 cast 來讓 linter 知道 guild 存在
            assert itx.guild is not None
            guild = cast(discord.Guild, itx.guild)
            
            # 獲取自定義格式
            custom_formats = await view.cog.get_cfg(guild.id, "custom_formats", "")
            
            embed = discord.Embed(
                title="📋 支援的可執行檔案格式",
                description="本模組可檢測以下檔案格式：",
                color=discord.Color.blue(),
            )
            
            # 分類顯示
            categories = {
                "Windows": ["exe", "msi", "bat", "cmd", "com", "pif", "scr", "vbs", "js", "wsf", "hta"],
                "Linux/Unix": ["sh", "bash", "zsh", "fish", "py", "pl", "rb", "php", "jar", "deb", "rpm"],
                "macOS": ["app", "dmg", "pkg", "command", "tool"],
                "其他": ["lnk", "url", "reg", "inf", "sys", "dll", "ocx", "cab", "iso", "img"],
            }
            
            # 添加自定義格式
            custom_formats_list = [fmt.strip() for fmt in custom_formats.split(",") if fmt.strip()] if custom_formats else []
            if custom_formats_list:
                categories["自定義"] = custom_formats_list
            
            for category, formats in categories.items():
                embed.add_field(
                    name=f"{category} 格式",
                    value=", ".join(formats),
                    inline=False
                )
            
            # 更新現有面板而非發送新消息
            if itx.message:
                # 創建格式管理視圖
                formats_view = ui.View(timeout=300)
                formats_view.add_item(AddFormatButton(view))
                formats_view.add_item(RemoveFormatButton(view))
                formats_view.add_item(ReturnButton(view))
                formats_view.add_item(CloseButton())
                
                await itx.response.edit_message(embed=embed, view=formats_view)
            else:
                await itx.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            friendly_log("顯示支援格式失敗", e)
            await itx.response.send_message("❌ 顯示支援格式失敗", ephemeral=True)


class AddFormatButton(ui.Button):
    """添加檔案格式按鈕"""
    
    def __init__(self, original_view: ui.View):
        super().__init__(label="添加格式", emoji="➕", style=discord.ButtonStyle.success)
        self.original_view = original_view
    
    async def callback(self, itx: discord.Interaction):
        """顯示添加檔案格式對話框"""
        view: ExecutableSettingsView = self.original_view  # type: ignore
        
        # 顯示添加檔案格式對話框
        modal = AddFormatModal(view)
        await itx.response.send_modal(modal)


class RemoveFormatButton(ui.Button):
    """移除檔案格式按鈕"""
    
    def __init__(self, original_view: ui.View):
        super().__init__(label="移除格式", emoji="➖", style=discord.ButtonStyle.danger)
        self.original_view = original_view
    
    async def callback(self, itx: discord.Interaction):
        """顯示移除檔案格式對話框"""
        view: ExecutableSettingsView = self.original_view  # type: ignore
        
        # 顯示移除檔案格式對話框
        modal = RemoveFormatModal(view)
        await itx.response.send_modal(modal)


class AddFormatModal(ui.Modal, title="添加自定義檔案格式"):
    """添加檔案格式對話框"""
    
    format = ui.TextInput(
        label="檔案格式",
        style=discord.TextStyle.short,
        placeholder="輸入要添加的檔案格式，例如：ps1（不含點）",
        required=True,
    )
    
    def __init__(self, view: ExecutableSettingsView):
        super().__init__()
        self.view = view
    
    async def on_submit(self, itx: discord.Interaction):
        """提交時處理"""
        try:
            if not itx.guild:
                await itx.response.send_message("無法找到伺服器資訊。", ephemeral=True)
                return
                
            # 使用斷言和 cast 來讓 linter 知道 guild 存在
            assert itx.guild is not None
            guild = cast(discord.Guild, itx.guild)
                
            fmt = self.format.value.lower().strip().lstrip(".")
            if not fmt:
                await itx.response.send_message("請輸入有效的檔案格式。", ephemeral=True)
                return
                
            # 檢查格式是否已存在於預設格式中
            if fmt in DEFAULT_EXECUTABLE_EXTENSIONS:
                await itx.response.send_message("此格式已是預設支援格式。", ephemeral=True)
                return
                
            # 獲取自定義格式
            custom_formats = await self.view.cog.get_cfg(guild.id, "custom_formats", "")
            formats = [f.strip() for f in custom_formats.split(",") if f.strip()] if custom_formats else []
            
            if fmt in formats:
                await itx.response.send_message("此格式已在自定義格式中。", ephemeral=True)
                return
                
            formats.append(fmt)
            await self.view.cog.set_cfg(guild.id, "custom_formats", ",".join(formats))
            
            # 更新檢測用全局變量
            global EXECUTABLE_EXTENSIONS
            EXECUTABLE_EXTENSIONS = set(DEFAULT_EXECUTABLE_EXTENSIONS) | set(formats)
            
            # 更新格式視圖
            custom_formats = await self.view.cog.get_cfg(guild.id, "custom_formats", "")
            updated_formats = [f.strip() for f in custom_formats.split(",") if f.strip()] if custom_formats else []
            
            embed = discord.Embed(
                title="📋 支援的可執行檔案格式",
                description=f"✅ 已成功添加 `{fmt}` 檔案格式",
                color=discord.Color.blue(),
            )
            
            # 分類顯示
            categories = {
                "Windows": ["exe", "msi", "bat", "cmd", "com", "pif", "scr", "vbs", "js", "wsf", "hta"],
                "Linux/Unix": ["sh", "bash", "zsh", "fish", "py", "pl", "rb", "php", "jar", "deb", "rpm"],
                "macOS": ["app", "dmg", "pkg", "command", "tool"],
                "其他": ["lnk", "url", "reg", "inf", "sys", "dll", "ocx", "cab", "iso", "img"],
            }
            
            if updated_formats:
                categories["自定義"] = updated_formats
            
            for category, formats in categories.items():
                embed.add_field(
                    name=f"{category} 格式",
                    value=", ".join(formats),
                    inline=False
                )
            
            # 更新面板
            formats_view = ui.View(timeout=300)
            formats_view.add_item(AddFormatButton(self.view))
            formats_view.add_item(RemoveFormatButton(self.view))
            formats_view.add_item(ReturnButton(self.view))
            formats_view.add_item(CloseButton())
            
            await itx.response.edit_message(embed=embed, view=formats_view)
            
        except Exception as e:
            friendly_log("添加檔案格式失敗", e)
            await itx.response.send_message(f"❌ 添加檔案格式失敗: {str(e)}", ephemeral=True)


class RemoveFormatModal(ui.Modal, title="移除自定義檔案格式"):
    """移除檔案格式對話框"""
    
    format = ui.TextInput(
        label="檔案格式",
        style=discord.TextStyle.short,
        placeholder="輸入要移除的檔案格式，例如：ps1（不含點）",
        required=True,
    )
    
    def __init__(self, view: ExecutableSettingsView):
        super().__init__()
        self.view = view
    
    async def on_submit(self, itx: discord.Interaction):
        """提交時處理"""
        try:
            if not itx.guild:
                await itx.response.send_message("無法找到伺服器資訊。", ephemeral=True)
                return
                
            # 使用斷言和 cast 來讓 linter 知道 guild 存在
            assert itx.guild is not None
            guild = cast(discord.Guild, itx.guild)
                
            fmt = self.format.value.lower().strip().lstrip(".")
            if not fmt:
                await itx.response.send_message("請輸入有效的檔案格式。", ephemeral=True)
                return
                
            # 檢查格式是否是預設格式
            if fmt in DEFAULT_EXECUTABLE_EXTENSIONS:
                await itx.response.send_message("無法移除預設支援格式，這些格式為系統內建。", ephemeral=True)
                return
                
            # 獲取自定義格式
            custom_formats = await self.view.cog.get_cfg(guild.id, "custom_formats", "")
            formats = [f.strip() for f in custom_formats.split(",") if f.strip()] if custom_formats else []
            
            if fmt not in formats:
                await itx.response.send_message("找不到此自定義格式。", ephemeral=True)
                return
                
            formats.remove(fmt)
            await self.view.cog.set_cfg(guild.id, "custom_formats", ",".join(formats))
            
            # 更新檢測用全局變量
            global EXECUTABLE_EXTENSIONS
            EXECUTABLE_EXTENSIONS = set(DEFAULT_EXECUTABLE_EXTENSIONS) | set(formats)
            
            # 更新格式視圖
            custom_formats = await self.view.cog.get_cfg(guild.id, "custom_formats", "")
            updated_formats = [f.strip() for f in custom_formats.split(",") if f.strip()] if custom_formats else []
            
            embed = discord.Embed(
                title="📋 支援的可執行檔案格式",
                description=f"✅ 已成功移除 `{fmt}` 檔案格式",
                color=discord.Color.blue(),
            )
            
            # 分類顯示
            categories = {
                "Windows": ["exe", "msi", "bat", "cmd", "com", "pif", "scr", "vbs", "js", "wsf", "hta"],
                "Linux/Unix": ["sh", "bash", "zsh", "fish", "py", "pl", "rb", "php", "jar", "deb", "rpm"],
                "macOS": ["app", "dmg", "pkg", "command", "tool"],
                "其他": ["lnk", "url", "reg", "inf", "sys", "dll", "ocx", "cab", "iso", "img"],
            }
            
            if updated_formats:
                categories["自定義"] = updated_formats
            
            for category, formats in categories.items():
                embed.add_field(
                    name=f"{category} 格式",
                    value=", ".join(formats),
                    inline=False
                )
            
            # 更新面板
            formats_view = ui.View(timeout=300)
            formats_view.add_item(AddFormatButton(self.view))
            formats_view.add_item(RemoveFormatButton(self.view))
            formats_view.add_item(ReturnButton(self.view))
            formats_view.add_item(CloseButton())
            
            await itx.response.edit_message(embed=embed, view=formats_view)
            
        except Exception as e:
            friendly_log("移除檔案格式失敗", e)
            await itx.response.send_message(f"❌ 移除檔案格式失敗: {str(e)}", ephemeral=True)


class ToggleButton(ui.Button):
    """啟用/停用按鈕"""
    
    def __init__(self):
        super().__init__(label="🔄 啟用/停用", style=discord.ButtonStyle.secondary)
    
    async def callback(self, itx: discord.Interaction):
        """啟用/停用模組"""
        view: ExecutableSettingsView = self.view  # type: ignore
        try:
            if not itx.guild:
                await itx.response.send_message("此功能必須在伺服器中使用。", ephemeral=True)
                return
                
            enabled = await view.cog.get_cfg(itx.guild.id, "enabled", "true")
            if enabled and enabled.lower() == "true":
                await view.cog.set_cfg(itx.guild.id, "enabled", "false")
                await itx.response.send_message("✅ 已停用可執行檔案保護。", ephemeral=True)
            else:
                await view.cog.set_cfg(itx.guild.id, "enabled", "true")
                await itx.response.send_message("✅ 已啟用可執行檔案保護。", ephemeral=True)
            
            # 更新面板
            await view.update_panel()
        except Exception as e:
            friendly_log("啟用/停用模組失敗", e)
            await itx.response.send_message("❌ 啟用/停用模組失敗", ephemeral=True)


class CloseButton(ui.Button):
    """關閉面板按鈕"""
    
    def __init__(self):
        super().__init__(label="❌ 關閉面板", style=discord.ButtonStyle.danger)
    
    async def callback(self, itx: discord.Interaction):
        """關閉面板"""
        try:
            # 檢查消息是否存在
            if itx.message:
                await itx.message.delete()
                await itx.response.send_message("✅ 已關閉設定面板", ephemeral=True)
            else:
                await itx.response.send_message("✅ 已關閉設定面板", ephemeral=True)
        except Exception as e:
            friendly_log("關閉面板失敗", e)
            await itx.response.send_message("❌ 關閉面板失敗", ephemeral=True)


# ────────────────────────────
# 反可執行檔案主類別
# ────────────────────────────
class AntiExecutable(ProtectionCog):
    """反可執行檔案保護模組
    
    功能：
    - 自動檢測可執行檔案
    - 支援多種檔案格式
    - 白名單/黑名單管理
    - 檔案特徵檢測
    - 詳細的管理介面
    """
    module_name = "anti_executable"

    def __init__(self, bot: commands.Bot):
        """初始化反可執行檔案模組
        
        Args:
            bot: Discord Bot 實例
        """
        super().__init__(bot)
        self._custom_formats_cache = {}  # 伺服器自定義格式快取

    # ───────── 事件處理 ─────────
    @commands.Cog.listener()
    async def on_message(self, msg: discord.Message):
        """處理新訊息事件"""
        try:
            # 基本檢查
            if msg.author.bot or not msg.guild:
                return
                
            # 檢查附件
            if not msg.attachments:
                return
                
            # 檢查模組是否啟用
            enabled = await self.get_cfg(msg.guild.id, "enabled", "true")
            if not enabled or enabled.lower() != "true":
                return

            # 取得白名單和黑名單
            wl_raw = await self.get_cfg(msg.guild.id, "whitelist", "")
            bl_raw = await self.get_cfg(msg.guild.id, "blacklist", "")
            
            whitelist = {d.strip().lower() for d in (wl_raw or "").split(",") if d.strip()}
            blacklist = {d.strip().lower() for d in (bl_raw or "").split(",") if d.strip()}

            # 取得並更新自定義格式
            await self._update_custom_formats(msg.guild.id)
            
            # 檢查每個附件
            hits: List[discord.Attachment] = []
            for attachment in msg.attachments:
                if await self._is_executable(attachment, whitelist, blacklist):
                    hits.append(attachment)

            # 處理可執行檔案
            if hits:
                try:
                    await msg.delete()
                except discord.Forbidden:
                    pass
                    
                embed = discord.Embed(
                    title="🚫 偵測到可執行檔案，已自動刪除",
                    description="\n".join(f"• {att.filename} ({att.size} bytes)" for att in hits),
                    color=discord.Color.red(),
                )
                await msg.channel.send(embed=embed, delete_after=15)
                await self.log(msg.guild, f"刪除了 {msg.author} 可執行檔案：{[att.filename for att in hits]}")
                
        except Exception as e:
            friendly_log("AntiExecutable 事件錯誤", e)

    # ───────── 檔案檢測 ─────────
    async def _is_executable(self, attachment: discord.Attachment, whitelist: Set[str], blacklist: Set[str]) -> bool:
        """檢查是否為可執行檔案
        
        Args:
            attachment: Discord 附件
            whitelist: 白名單網域集合
            blacklist: 黑名單網域集合
            
        Returns:
            是否為可執行檔案
        """
        try:
            # 檢查檔案大小
            if attachment.size > MAX_FILE_SIZE * 1024 * 1024:
                return False
                
            # 檢查副檔名
            filename = attachment.filename.lower()
            extension = filename.split(".")[-1] if "." in filename else ""
            
            if extension in EXECUTABLE_EXTENSIONS:
                # 檢查白名單
                if any(domain in filename for domain in whitelist):
                    return False
                    
                # 檢查黑名單
                if any(domain in filename for domain in blacklist):
                    return True
                    
                # 檢查檔案特徵
                return await self._check_file_signature(attachment)
                
            return False
            
        except Exception as e:
            friendly_log("檢查可執行檔案失敗", e)
            return False
            
    async def _update_custom_formats(self, guild_id: int):
        """更新自定義格式
        
        Args:
            guild_id: 伺服器 ID
        """
        try:
            # 取得伺服器自定義格式
            custom_formats = await self.get_cfg(guild_id, "custom_formats", "")
            formats = [f.strip() for f in custom_formats.split(",") if f.strip()] if custom_formats else []
            
            # 更新全局變量
            global EXECUTABLE_EXTENSIONS
            EXECUTABLE_EXTENSIONS = set(DEFAULT_EXECUTABLE_EXTENSIONS) | set(formats)
            
            # 更新快取
            self._custom_formats_cache[guild_id] = formats
            
        except Exception as e:
            friendly_log("更新自定義格式失敗", e)
            EXECUTABLE_EXTENSIONS = set(DEFAULT_EXECUTABLE_EXTENSIONS)

    async def _check_file_signature(self, attachment: discord.Attachment) -> bool:
        """檢查檔案特徵
        
        Args:
            attachment: Discord 附件
            
        Returns:
            是否為可執行檔案
        """
        try:
            # 下載檔案前幾個位元組
            async with aiohttp.ClientSession() as session:
                # 添加 headers 參數，只請求前 16 bytes
                headers = {"Range": "bytes=0-15"}
                async with session.get(attachment.url, headers=headers) as resp:
                    if resp.status != 200 and resp.status != 206:  # 206 表示部分內容響應成功
                        logger.debug(f"下載檔案失敗，HTTP狀態碼：{resp.status}")
                        return False
                        
                    # 讀取全部內容，然後取前 8 個位元組
                    content = await resp.read()
                    header = content[:8]
                    
                    # 檢查魔術數字
                    for signature, description in MAGIC_SIGNATURES.items():
                        if header.startswith(signature):
                            logger.info(f"檢測到 {description} 檔案：{attachment.filename}")
                            return True
                            
                    return False
                
        except Exception as e:
            friendly_log(f"檢查檔案特徵失敗（檔案：{attachment.filename}）", e)
            logger.debug(f"檔案 URL：{attachment.url}，大小：{attachment.size} 位元組")
            return False

    # ───────── Slash 指令 ─────────
    @app_commands.command(
        name="執行檔保護面板",
        description="開啟可執行檔案保護設定面板",
    )
    @admin_only()
    async def cmd_panel(self, itx: discord.Interaction):
        """開啟設定面板
        
        Args:
            itx: Discord 互動
        """
        try:
            if not itx.guild:
                await itx.response.send_message("此指令必須在伺服器中使用。")
                return
                
            view = ExecutableSettingsView(self, itx.user.id)
            embed = discord.Embed(
                title="⚙️ 可執行檔案保護設定",
                description="此面板可協助您管理可執行檔案保護功能，防止惡意軟體透過Discord傳播。",
                color=discord.Color.blue(),
            )
            
            # 添加功能說明
            embed.add_field(
                name="📋 白名單管理",
                value="管理可信任的網域，這些網域的檔案將不會被檢查。",
                inline=True
            )
            
            embed.add_field(
                name="🚫 黑名單管理",
                value="管理不可信任的網域，這些網域的檔案將被直接刪除。",
                inline=True
            )
            
            embed.add_field(
                name="📊 狀態查看",
                value="查看目前模組的運作狀態及相關設定。",
                inline=True
            )
            
            embed.add_field(
                name="📖 新手教學",
                value="提供模組的詳細使用說明及建議。",
                inline=True
            )
            
            embed.add_field(
                name="🛠️ 功能測試",
                value="測試模組的各項功能是否正常運作。",
                inline=True
            )
            
            embed.add_field(
                name="🔄 啟用/停用",
                value="啟用或停用模組。",
                inline=True
            )
            
            embed.add_field(
                name="❌ 關閉面板",
                value="關閉此設定面板。",
                inline=True
            )
            
            # 設為公開可見 (ephemeral=False)
            await itx.response.send_message(embed=embed, view=view, ephemeral=False)
            
            # 設置自動更新
            message = await itx.original_response()
            await view.start_auto_update(message)
            
        except Exception as e:
            friendly_log("開啟設定面板失敗", e)
            try:
                await itx.response.send_message("❌ 開啟設定面板失敗")
            except:
                pass

    # ───────── 白名單指令群組 ─────────
    # 這些指令已整合到設定面板，為了精簡系統，予以註釋取消注冊
    """
    exec_whitelist = app_commands.Group(
        name="執行檔白名單",
        description="管理可執行檔案白名單",
    )

    @exec_whitelist.command(
        name="加入",
        description="加入白名單網域",
    )
    @admin_only()
    async def wl_add(self, itx: discord.Interaction, domain: str):
        # 省略函數內容
        pass

    @exec_whitelist.command(
        name="移除",
        description="移除白名單網域",
    )
    @admin_only()
    async def wl_remove(self, itx: discord.Interaction, domain: str):
        # 省略函數內容
        pass

    @exec_whitelist.command(
        name="查看",
        description="查看白名單",
    )
    @admin_only()
    async def wl_list(self, itx: discord.Interaction):
        # 省略函數內容
        pass
    """

    # ───────── 黑名單指令群組 ─────────
    # 這些指令已整合到設定面板，為了精簡系統，予以註釋取消注冊
    """
    exec_blacklist = app_commands.Group(
        name="執行檔黑名單",
        description="管理可執行檔案黑名單",
    )

    @exec_blacklist.command(
        name="加入",
        description="加入黑名單網域",
    )
    @admin_only()
    async def bl_add(self, itx: discord.Interaction, domain: str):
        # 省略函數內容
        pass

    @exec_blacklist.command(
        name="移除",
        description="移除黑名單網域",
    )
    @admin_only()
    async def bl_remove(self, itx: discord.Interaction, domain: str):
        # 省略函數內容
        pass

    @exec_blacklist.command(
        name="查看",
        description="查看黑名單",
    )
    @admin_only()
    async def bl_list(self, itx: discord.Interaction):
        # 省略函數內容
        pass
    """

    # ───────── 模組控制指令 ─────────
    # 這些指令已整合到設定面板，為了精簡系統，予以註釋取消注冊
    """
    @app_commands.command(
        name="啟用",
        description="啟用可執行檔案保護",
    )
    @admin_only()
    async def cmd_enable(self, itx: discord.Interaction):
        # 省略函數內容
        pass

    @app_commands.command(
        name="停用",
        description="停用可執行檔案保護",
    )
    @admin_only()
    async def cmd_disable(self, itx: discord.Interaction):
        # 省略函數內容
        pass
    """

    # 註釋掉獨立的「支援格式」斜線指令
    """
    @app_commands.command(
        name="支援格式",
        description="查看支援的檔案格式",
    )
    async def cmd_formats(self, itx: discord.Interaction):
        # 此功能已整合到面板中，不再需要單獨的斜線指令
        pass
    """


# ────────────────────────────
# 模組設定
# ────────────────────────────
async def setup(bot: commands.Bot):
    """設定 AntiExecutable 模組"""
    logger.info("執行 anti_executable setup()")
    try:
        await bot.add_cog(AntiExecutable(bot))
        logger.info("AntiExecutable 模組已載入 (v1.5.5 - 增強管理功能)")
    except Exception as e:
        logger.error(f"AntiExecutable 載入失敗: {e}")
        raise e