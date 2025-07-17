"""
歡迎系統面板視圖模組

此模組包含歡迎系統的主要設定面板視圖，作為 UI 協調中心
"""

import discord
import logging
import asyncio
from typing import Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..main import WelcomeCog

logger = logging.getLogger("welcome")


class SettingsView(discord.ui.View):
    """歡迎系統設定面板視圖"""
    
    def __init__(self, cog: "WelcomeCog"):
        """
        初始化設定面板視圖
        
        Args:
            cog: WelcomeCog 實例
        """
        super().__init__(timeout=300)  # 5分鐘超時
        self.cog = cog
        self.panel_msg: Optional[discord.Message] = None
    
    @discord.ui.select(
        placeholder="選擇要調整的設定項目",
        min_values=1, max_values=1,
        options=[
            discord.SelectOption(label="📺 設定歡迎頻道", description="設定歡迎訊息發送的頻道"),
            discord.SelectOption(label="📝 設定圖片標題", description="設定歡迎圖片上的標題文字"),
            discord.SelectOption(label="📄 設定圖片內容", description="設定歡迎圖片上的內容文字"),
            discord.SelectOption(label="🎨 上傳背景圖片", description="上傳自訂背景圖片（PNG/JPG）"),
            discord.SelectOption(label="💬 設定歡迎訊息", description="設定純文字歡迎訊息"),
            discord.SelectOption(label="📍 調整頭像 X 位置", description="調整頭像在圖片上的 X 座標"),
            discord.SelectOption(label="📍 調整頭像 Y 位置", description="調整頭像在圖片上的 Y 座標"),
            discord.SelectOption(label="📍 調整標題 Y 位置", description="調整標題的 Y 座標"),
            discord.SelectOption(label="📍 調整內容 Y 位置", description="調整內容的 Y 座標"),
            discord.SelectOption(label="🔤 調整標題字體大小", description="調整標題字體大小（像素）"),
            discord.SelectOption(label="🔤 調整內容字體大小", description="調整內容字體大小（像素）"),
            discord.SelectOption(label="🖼️ 調整頭像大小", description="調整頭像顯示的像素大小"),
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        """
        選擇器回調函數
        
        Args:
            interaction: Discord 互動物件
            select: 選擇器物件
        """
        try:
            if not interaction.guild_id:
                await interaction.response.send_message("❌ 此功能只能在伺服器中使用", ephemeral=True)
                return
            
            # 根據選擇的選項顯示不同的設定介面
            option = select.values[0]
            
            if "上傳背景圖片" in option:
                # 特殊處理：上傳背景圖片
                await interaction.response.send_message(
                    "請上傳一張背景圖片（PNG 或 JPG 格式，最大 5MB）",
                    ephemeral=True
                )
                
                # 等待使用者上傳圖片
                def check(m):
                    return (m.author.id == interaction.user.id and 
                            m.channel.id == interaction.channel_id and 
                            m.attachments)
                
                try:
                    msg = await self.cog.bot.wait_for('message', check=check, timeout=60.0)
                    
                    if msg.attachments:
                        attachment = msg.attachments[0]
                        success = await self.cog.handle_background_upload(interaction, attachment)
                        
                        if success:
                            # 刪除上傳的訊息
                            try:
                                await msg.delete()
                            except:
                                pass
                            
                            # 發送成功訊息
                            await interaction.followup.send("✅ 背景圖片已上傳並設定", ephemeral=True)
                            
                            # 更新面板
                            await self._refresh_panel()
                        
                except asyncio.TimeoutError:
                    await interaction.followup.send("❌ 上傳超時，請重新操作", ephemeral=True)
                
            else:
                # 其他設定項目：顯示對應的 Modal
                modal = None
                
                if "設定歡迎頻道" in option:
                    modal = self.cog.SetChannelModal(self.cog, self.panel_msg)
                elif "設定圖片標題" in option:
                    modal = self.cog.SetTitleModal(self.cog, self.panel_msg)
                elif "設定圖片內容" in option:
                    modal = self.cog.SetDescModal(self.cog, self.panel_msg)
                elif "設定歡迎訊息" in option:
                    modal = self.cog.SetMsgModal(self.cog, self.panel_msg)
                elif "調整頭像 X 位置" in option:
                    modal = self.cog.SetAvatarXModal(self.cog, self.panel_msg)
                elif "調整頭像 Y 位置" in option:
                    modal = self.cog.SetAvatarYModal(self.cog, self.panel_msg)
                elif "調整標題 Y 位置" in option:
                    modal = self.cog.SetTitleYModal(self.cog, self.panel_msg)
                elif "調整內容 Y 位置" in option:
                    modal = self.cog.SetDescYModal(self.cog, self.panel_msg)
                elif "調整標題字體大小" in option:
                    modal = self.cog.SetTitleFontSizeModal(self.cog, self.panel_msg)
                elif "調整內容字體大小" in option:
                    modal = self.cog.SetDescFontSizeModal(self.cog, self.panel_msg)
                elif "調整頭像大小" in option:
                    modal = self.cog.SetAvatarSizeModal(self.cog, self.panel_msg)
                
                if modal:
                    await interaction.response.send_modal(modal)
                else:
                    await interaction.response.send_message("❌ 未知的設定項目", ephemeral=True)
                    
        except Exception as exc:
            logger.error(f"選擇器回調失敗 [錯誤碼: 501]: {exc}", exc_info=True)
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ 操作失敗，請重試", ephemeral=True)
                else:
                    await interaction.followup.send("❌ 操作失敗，請重試", ephemeral=True)
            except:
                pass
    
    @discord.ui.button(label="預覽效果", style=discord.ButtonStyle.primary, emoji="👁️")
    async def preview_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        預覽按鈕回調函數
        
        Args:
            interaction: Discord 互動物件
            button: 按鈕物件
        """
        try:
            if not interaction.guild_id or not interaction.guild:
                await interaction.response.send_message("❌ 此功能只能在伺服器中使用", ephemeral=True)
                return
            
            await interaction.response.defer(ephemeral=True, thinking=True)
            
            # 確保使用者是成員物件
            if not isinstance(interaction.user, discord.Member):
                await interaction.followup.send("❌ 無法取得成員資訊", ephemeral=True)
                return
            
            # 生成預覽圖片
            member = interaction.user
            image = await self.cog._generate_welcome_image(
                interaction.guild_id, member, force_refresh=True
            )
            
            if image:
                # 取得設定
                settings = await self.cog.db.get_settings(interaction.guild_id)
                
                # 渲染訊息
                message = settings.get("message", "歡迎 {member.mention} 加入 {guild.name}！")
                
                # 確保頻道是文字頻道
                channel = None
                if isinstance(interaction.channel, discord.TextChannel):
                    channel = interaction.channel
                    
                rendered_message = self.cog.renderer.render_message(
                    member, interaction.guild, channel, message
                )
                
                await interaction.followup.send(
                    content=f"**預覽效果**\n{rendered_message}",
                    file=discord.File(fp=image, filename="welcome_preview.png"),
                    ephemeral=True
                )
            else:
                await interaction.followup.send("❌ 生成預覽圖片失敗", ephemeral=True)
                
        except Exception as exc:
            logger.error(f"預覽按鈕失敗 [錯誤碼: 502]: {exc}", exc_info=True)
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ 預覽失敗，請重試", ephemeral=True)
                else:
                    await interaction.followup.send("❌ 預覽失敗，請重試", ephemeral=True)
            except:
                pass
    
    @discord.ui.button(label="關閉", style=discord.ButtonStyle.secondary, emoji="❌")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        關閉按鈕回調函數
        
        Args:
            interaction: Discord 互動物件
            button: 按鈕物件
        """
        try:
            await interaction.response.defer()
            
            if self.panel_msg:
                await self.panel_msg.delete()
                self.panel_msg = None
                self.stop()
                
        except Exception as exc:
            logger.error(f"關閉按鈕失敗 [錯誤碼: 503]: {exc}", exc_info=True)
    
    async def _refresh_panel(self):
        """更新面板訊息"""
        if not self.panel_msg or not self.panel_msg.guild:
            return
        
        try:
            from ..panel.embeds.settings_embed import build_settings_embed
            
            # 取得設定
            settings = await self.cog.db.get_settings(self.panel_msg.guild.id)
            
            # 建立新的 Embed
            embed = await build_settings_embed(self.cog, self.panel_msg.guild, settings)
            
            # 更新訊息
            await self.panel_msg.edit(embed=embed, view=self)
            
        except Exception as exc:
            logger.error(f"更新設定面板失敗 [錯誤碼: 504]: {exc}", exc_info=True)
    
    async def on_timeout(self):
        """面板超時處理"""
        if self.panel_msg:
            try:
                await self.panel_msg.edit(view=None)
            except:
                pass
    
    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item) -> None:
        """處理視圖錯誤"""
        logger.error(f"視圖錯誤 [錯誤碼: 505]: {error}", exc_info=True)
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ 發生錯誤，請重試", ephemeral=True)
            else:
                await interaction.followup.send("❌ 發生錯誤，請重試", ephemeral=True)
        except:
            pass 