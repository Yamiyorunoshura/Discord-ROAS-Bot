"""
歡迎系統對話框元件模組

此模組包含歡迎系統設定面板使用的所有對話框元件
"""

import discord
import logging
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ...main import WelcomeCog

logger = logging.getLogger("welcome")


class BaseModal(discord.ui.Modal):
    """設定對話框的基礎類別"""
    
    def __init__(self, cog: "WelcomeCog", panel_msg: Optional[discord.Message], *args, **kwargs):
        """
        初始化對話框
        
        Args:
            cog: WelcomeCog 實例
            panel_msg: 面板訊息物件
        """
        super().__init__(*args, **kwargs)
        self.cog = cog
        self.panel_msg = panel_msg
    
    async def _after_update(self, interaction: discord.Interaction):
        """
        更新設定後的共用處理
        
        Args:
            interaction: Discord 互動物件
        """
        # 回應使用者
        await interaction.response.send_message("✅ 設定已更新", ephemeral=True)
        
        # 清除圖片快取
        if interaction.guild_id:
            self.cog.clear_image_cache(interaction.guild_id)
        
        # 更新面板
        if self.panel_msg and self.panel_msg.guild:
            try:
                from ..embeds.settings_embed import build_settings_embed
                
                # 取得設定
                settings = await self.cog.db.get_settings(self.panel_msg.guild.id)
                
                # 建立新的 Embed
                embed = await build_settings_embed(self.cog, self.panel_msg.guild, settings)
                
                # 更新訊息
                await self.panel_msg.edit(embed=embed)
                
            except Exception as exc:
                logger.error("更新設定面板失敗", exc_info=True)


class SetChannelModal(BaseModal):
    """設定歡迎頻道對話框"""
    
    def __init__(self, cog: "WelcomeCog", panel_msg: Optional[discord.Message]):
        super().__init__(cog, panel_msg, title="設定歡迎頻道")
        
        self.channel = discord.ui.TextInput(
            label="頻道 ID 或名稱",
            placeholder="輸入頻道 ID 或名稱（例如：general 或 123456789）",
            required=True
        )
        self.add_item(self.channel)
    
    async def on_submit(self, interaction: discord.Interaction):
        """提交處理"""
        if not interaction.guild_id:
            await interaction.response.send_message("❌ 此功能只能在伺服器中使用", ephemeral=True)
            return
        
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("❌ 無法取得伺服器資訊", ephemeral=True)
            return
        
        # 嘗試解析頻道
        channel_input = self.channel.value.strip()
        channel = None
        
        # 嘗試通過 ID 查找
        if channel_input.isdigit():
            channel = guild.get_channel(int(channel_input))
        
        # 嘗試通過名稱查找
        if not channel:
            # 移除 # 前綴
            if channel_input.startswith("#"):
                channel_input = channel_input[1:]
                
            # 查找頻道
            for ch in guild.text_channels:
                if ch.name.lower() == channel_input.lower():
                    channel = ch
                    break
        
        if not channel:
            await interaction.response.send_message(
                "❌ 找不到指定的頻道，請確認頻道名稱或 ID 是否正確",
                ephemeral=True
            )
            return
        
        # 檢查權限
        bot_member = guild.get_member(interaction.client.user.id)
        if not bot_member:
            await interaction.response.send_message("❌ 無法取得機器人成員資訊", ephemeral=True)
            return
            
        permissions = channel.permissions_for(bot_member)
        if not (permissions.send_messages and permissions.attach_files):
            await interaction.response.send_message(
                "❌ 機器人在該頻道沒有發送訊息或附加檔案的權限",
                ephemeral=True
            )
            return
        
        # 更新設定
        await self.cog.db.update_setting(interaction.guild_id, "channel_id", channel.id)
        
        # 共用處理
        await self._after_update(interaction)


class SetTitleModal(BaseModal):
    """設定圖片標題對話框"""
    
    def __init__(self, cog: "WelcomeCog", panel_msg: Optional[discord.Message]):
        super().__init__(cog, panel_msg, title="設定圖片標題")
        
        self.title_txt = discord.ui.TextInput(
            label="圖片標題",
            placeholder="例如：歡迎 {member.name}!",
            required=True,
            max_length=100
        )
        self.add_item(self.title_txt)
    
    async def on_submit(self, interaction: discord.Interaction):
        """提交處理"""
        if not interaction.guild_id:
            await interaction.response.send_message("❌ 此功能只能在伺服器中使用", ephemeral=True)
            return
        
        # 更新設定
        await self.cog.db.update_setting(interaction.guild_id, "title", self.title_txt.value)
        
        # 共用處理
        await self._after_update(interaction)


class SetDescModal(BaseModal):
    """設定圖片內容對話框"""
    
    def __init__(self, cog: "WelcomeCog", panel_msg: Optional[discord.Message]):
        super().__init__(cog, panel_msg, title="設定圖片內容")
        
        self.desc_txt = discord.ui.TextInput(
            label="圖片內容",
            placeholder="例如：很高興見到你～",
            required=True,
            max_length=200,
            style=discord.TextStyle.paragraph
        )
        self.add_item(self.desc_txt)
    
    async def on_submit(self, interaction: discord.Interaction):
        """提交處理"""
        if not interaction.guild_id:
            await interaction.response.send_message("❌ 此功能只能在伺服器中使用", ephemeral=True)
            return
        
        # 更新設定
        await self.cog.db.update_setting(interaction.guild_id, "description", self.desc_txt.value)
        
        # 共用處理
        await self._after_update(interaction)


class SetMsgModal(BaseModal):
    """設定歡迎訊息對話框"""
    
    def __init__(self, cog: "WelcomeCog", panel_msg: Optional[discord.Message]):
        super().__init__(cog, panel_msg, title="設定歡迎訊息")
        
        self.msg_txt = discord.ui.TextInput(
            label="歡迎訊息",
            placeholder="例如：歡迎 {member.mention} 加入 {guild.name}！",
            required=True,
            max_length=500,
            style=discord.TextStyle.paragraph
        )
        self.add_item(self.msg_txt)
    
    async def on_submit(self, interaction: discord.Interaction):
        """提交處理"""
        if not interaction.guild_id:
            await interaction.response.send_message("❌ 此功能只能在伺服器中使用", ephemeral=True)
            return
        
        # 更新設定
        await self.cog.db.update_setting(interaction.guild_id, "message", self.msg_txt.value)
        
        # 共用處理
        await self._after_update(interaction)


class SetAvatarXModal(BaseModal):
    """調整頭像 X 位置對話框"""
    
    def __init__(self, cog: "WelcomeCog", panel_msg: Optional[discord.Message]):
        super().__init__(cog, panel_msg, title="調整頭像 X 位置")
        
        self.x_txt = discord.ui.TextInput(
            label="X 座標（像素）",
            placeholder="例如：30",
            required=True,
            max_length=4
        )
        self.add_item(self.x_txt)
    
    async def on_submit(self, interaction: discord.Interaction):
        """提交處理"""
        if not interaction.guild_id:
            await interaction.response.send_message("❌ 此功能只能在伺服器中使用", ephemeral=True)
            return
        
        # 檢查輸入是否為數字
        if not self.x_txt.value.isdigit():
            await interaction.response.send_message("❌ X 座標必須是數字", ephemeral=True)
            return
        
        # 更新設定
        await self.cog.db.update_setting(interaction.guild_id, "avatar_x", int(self.x_txt.value))
        
        # 共用處理
        await self._after_update(interaction)


class SetAvatarYModal(BaseModal):
    """調整頭像 Y 位置對話框"""
    
    def __init__(self, cog: "WelcomeCog", panel_msg: Optional[discord.Message]):
        super().__init__(cog, panel_msg, title="調整頭像 Y 位置")
        
        self.y_txt = discord.ui.TextInput(
            label="Y 座標（像素）",
            placeholder="例如：80",
            required=True,
            max_length=4
        )
        self.add_item(self.y_txt)
    
    async def on_submit(self, interaction: discord.Interaction):
        """提交處理"""
        if not interaction.guild_id:
            await interaction.response.send_message("❌ 此功能只能在伺服器中使用", ephemeral=True)
            return
        
        # 檢查輸入是否為數字
        if not self.y_txt.value.isdigit():
            await interaction.response.send_message("❌ Y 座標必須是數字", ephemeral=True)
            return
        
        # 更新設定
        await self.cog.db.update_setting(interaction.guild_id, "avatar_y", int(self.y_txt.value))
        
        # 共用處理
        await self._after_update(interaction)


class SetTitleYModal(BaseModal):
    """調整標題 Y 位置對話框"""
    
    def __init__(self, cog: "WelcomeCog", panel_msg: Optional[discord.Message]):
        super().__init__(cog, panel_msg, title="調整標題 Y 位置")
        
        self.y_txt = discord.ui.TextInput(
            label="Y 座標（像素）",
            placeholder="例如：60",
            required=True,
            max_length=4
        )
        self.add_item(self.y_txt)
    
    async def on_submit(self, interaction: discord.Interaction):
        """提交處理"""
        if not interaction.guild_id:
            await interaction.response.send_message("❌ 此功能只能在伺服器中使用", ephemeral=True)
            return
        
        # 檢查輸入是否為數字
        if not self.y_txt.value.isdigit():
            await interaction.response.send_message("❌ Y 座標必須是數字", ephemeral=True)
            return
        
        # 更新設定
        await self.cog.db.update_setting(interaction.guild_id, "title_y", int(self.y_txt.value))
        
        # 共用處理
        await self._after_update(interaction)


class SetDescYModal(BaseModal):
    """調整內容 Y 位置對話框"""
    
    def __init__(self, cog: "WelcomeCog", panel_msg: Optional[discord.Message]):
        super().__init__(cog, panel_msg, title="調整內容 Y 位置")
        
        self.y_txt = discord.ui.TextInput(
            label="Y 座標（像素）",
            placeholder="例如：120",
            required=True,
            max_length=4
        )
        self.add_item(self.y_txt)
    
    async def on_submit(self, interaction: discord.Interaction):
        """提交處理"""
        if not interaction.guild_id:
            await interaction.response.send_message("❌ 此功能只能在伺服器中使用", ephemeral=True)
            return
        
        # 檢查輸入是否為數字
        if not self.y_txt.value.isdigit():
            await interaction.response.send_message("❌ Y 座標必須是數字", ephemeral=True)
            return
        
        # 更新設定
        await self.cog.db.update_setting(interaction.guild_id, "description_y", int(self.y_txt.value))
        
        # 共用處理
        await self._after_update(interaction)


class SetTitleFontSizeModal(BaseModal):
    """調整標題字體大小對話框"""
    
    def __init__(self, cog: "WelcomeCog", panel_msg: Optional[discord.Message]):
        super().__init__(cog, panel_msg, title="調整標題字體大小")
        
        self.size_txt = discord.ui.TextInput(
            label="字體大小（像素）",
            placeholder="例如：36",
            required=True,
            max_length=3
        )
        self.add_item(self.size_txt)
    
    async def on_submit(self, interaction: discord.Interaction):
        """提交處理"""
        if not interaction.guild_id:
            await interaction.response.send_message("❌ 此功能只能在伺服器中使用", ephemeral=True)
            return
        
        # 檢查輸入是否為數字
        if not self.size_txt.value.isdigit():
            await interaction.response.send_message("❌ 字體大小必須是數字", ephemeral=True)
            return
        
        # 檢查字體大小範圍
        font_size = int(self.size_txt.value)
        if font_size < 10 or font_size > 100:
            await interaction.response.send_message("❌ 字體大小必須在 10 到 100 之間", ephemeral=True)
            return
        
        # 更新設定
        await self.cog.db.update_setting(interaction.guild_id, "title_font_size", font_size)
        
        # 共用處理
        await self._after_update(interaction)


class SetDescFontSizeModal(BaseModal):
    """調整內容字體大小對話框"""
    
    def __init__(self, cog: "WelcomeCog", panel_msg: Optional[discord.Message]):
        super().__init__(cog, panel_msg, title="調整內容字體大小")
        
        self.size_txt = discord.ui.TextInput(
            label="字體大小（像素）",
            placeholder="例如：22",
            required=True,
            max_length=3
        )
        self.add_item(self.size_txt)
    
    async def on_submit(self, interaction: discord.Interaction):
        """提交處理"""
        if not interaction.guild_id:
            await interaction.response.send_message("❌ 此功能只能在伺服器中使用", ephemeral=True)
            return
        
        # 檢查輸入是否為數字
        if not self.size_txt.value.isdigit():
            await interaction.response.send_message("❌ 字體大小必須是數字", ephemeral=True)
            return
        
        # 檢查字體大小範圍
        font_size = int(self.size_txt.value)
        if font_size < 10 or font_size > 100:
            await interaction.response.send_message("❌ 字體大小必須在 10 到 100 之間", ephemeral=True)
            return
        
        # 更新設定
        await self.cog.db.update_setting(interaction.guild_id, "desc_font_size", font_size)
        
        # 共用處理
        await self._after_update(interaction)


class SetAvatarSizeModal(BaseModal):
    """調整頭像大小對話框"""
    
    def __init__(self, cog: "WelcomeCog", panel_msg: Optional[discord.Message]):
        super().__init__(cog, panel_msg, title="調整頭像大小")
        
        self.size_txt = discord.ui.TextInput(
            label="頭像大小（像素）",
            placeholder="例如：80（留空表示使用預設大小）",
            required=False,
            max_length=3
        )
        self.add_item(self.size_txt)
    
    async def on_submit(self, interaction: discord.Interaction):
        """提交處理"""
        if not interaction.guild_id:
            await interaction.response.send_message("❌ 此功能只能在伺服器中使用", ephemeral=True)
            return
        
        # 檢查輸入
        if self.size_txt.value.strip():
            # 檢查輸入是否為數字
            if not self.size_txt.value.isdigit():
                await interaction.response.send_message("❌ 頭像大小必須是數字", ephemeral=True)
                return
            
            # 檢查頭像大小範圍
            avatar_size = int(self.size_txt.value)
            if avatar_size < 30 or avatar_size > 200:
                await interaction.response.send_message("❌ 頭像大小必須在 30 到 200 之間", ephemeral=True)
                return
            
            # 更新設定
            await self.cog.db.update_setting(interaction.guild_id, "avatar_size", avatar_size)
        else:
            # 使用預設大小（設為 NULL）
            await self.cog.db.update_setting(interaction.guild_id, "avatar_size", None)
        
        # 共用處理
        await self._after_update(interaction) 