"""
經濟系統 Discord Cog
Task ID: 12.1 - 移動並完善經濟系統Cog

這個模組提供經濟系統的 Discord 斜線指令整合，包括：
- 經濟面板主入口指令
- 餘額查詢指令
- 管理員面板指令
- 錯誤處理和參數驗證
"""

import logging
from typing import Optional
from datetime import datetime
import discord
from discord import app_commands
from discord.ext import commands

from panels.economy_panel import EconomyPanel
from services.economy.economy_service import EconomyService
from core.exceptions import ServiceError, ValidationError


class EconomyCog(commands.Cog):
    """
    經濟系統 Discord Cog
    
    提供完整的經濟系統 Discord 斜線指令整合
    """
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger('cogs.economy')
        
        # 服務依賴
        self.economy_service: Optional[EconomyService] = None
        self.economy_panel: Optional[EconomyPanel] = None
        
        # 初始化狀態
        self._initialized = False
    
    async def cog_load(self):
        """Cog 載入時的初始化"""
        try:
            await self._initialize_services()
            self.logger.info("經濟系統 Cog 載入完成")
            
        except Exception as e:
            self.logger.exception(f"經濟系統 Cog 載入失敗：{e}")
            raise
    
    async def cog_unload(self):
        """Cog 卸載時的清理"""
        try:
            self._initialized = False
            self.logger.info("經濟系統 Cog 已卸載")
            
        except Exception as e:
            self.logger.exception(f"經濟系統 Cog 卸載時發生錯誤：{e}")
    
    async def _initialize_services(self):
        """初始化服務依賴"""
        try:
            # 從服務註冊表獲取經濟服務
            from core.base_service import service_registry
            
            self.economy_service = service_registry.get_service("EconomyService")
            if not self.economy_service:
                raise ServiceError(
                    "找不到經濟服務實例",
                    service_name="EconomyCog",
                    operation="initialize"
                )
            
            # 等待服務初始化完成
            if not self.economy_service.is_initialized:
                await self.economy_service.initialize()
            
            # 建立並初始化經濟面板
            self.economy_panel = EconomyPanel()
            await self.economy_panel.initialize(self.economy_service)
            
            self._initialized = True
            self.logger.info("經濟系統服務依賴初始化完成")
            
        except Exception as e:
            self.logger.exception(f"初始化服務依賴失敗：{e}")
            raise ServiceError(
                f"經濟系統初始化失敗：{str(e)}",
                service_name="EconomyCog",
                operation="initialize"
            )
    
    def _check_initialization(self):
        """檢查服務是否已初始化"""
        if not self._initialized or not self.economy_service or not self.economy_panel:
            raise ServiceError(
                "經濟系統尚未初始化",
                service_name="EconomyCog",
                operation="command"
            )
    
    # ==========================================================================
    # 斜線指令定義
    # ==========================================================================
    
    @app_commands.command(
        name="economy",
        description="開啟經濟系統面板，查看餘額和交易記錄"
    )
    async def economy_command(self, interaction: discord.Interaction):
        """
        經濟系統主面板指令
        
        提供使用者經濟功能的入口點
        """
        try:
            self._check_initialization()
            
            self.logger.info(f"使用者 {interaction.user.id} 使用了 /economy 指令")
            
            # 委託給經濟面板處理
            await self.economy_panel.handle_interaction(interaction)
            
        except ServiceError as e:
            await self._send_service_error(interaction, e)
        except Exception as e:
            self.logger.exception(f"處理 /economy 指令時發生未預期錯誤：{e}")
            await self._send_generic_error(interaction)
    
    @app_commands.command(
        name="balance",
        description="查詢帳戶餘額"
    )
    @app_commands.describe(
        user="要查詢的使用者（可選，僅管理員可查詢其他人）"
    )
    async def balance_command(
        self, 
        interaction: discord.Interaction, 
        user: Optional[discord.Member] = None
    ):
        """
        餘額查詢指令
        
        參數：
            user: 要查詢的使用者（可選）
        """
        try:
            self._check_initialization()
            
            target_user = user or interaction.user
            self.logger.info(
                f"使用者 {interaction.user.id} 查詢使用者 {target_user.id} 的餘額"
            )
            
            # 設定互動資料以便面板處理
            if user:
                # 如果指定了使用者，需要在互動資料中設定
                if not hasattr(interaction, 'data'):
                    interaction.data = {}
                interaction.data['options'] = [{'value': user}]
            
            # 委託給經濟面板處理
            await self.economy_panel.handle_interaction(interaction)
            
        except ServiceError as e:
            await self._send_service_error(interaction, e)
        except Exception as e:
            self.logger.exception(f"處理 /balance 指令時發生未預期錯誤：{e}")
            await self._send_generic_error(interaction)
    
    @app_commands.command(
        name="economy_admin",
        description="開啟經濟系統管理面板（僅限管理員）"
    )
    @app_commands.default_permissions(administrator=True)
    async def economy_admin_command(self, interaction: discord.Interaction):
        """
        經濟系統管理面板指令
        
        僅限有管理員權限的使用者使用
        """
        try:
            self._check_initialization()
            
            self.logger.info(f"管理員 {interaction.user.id} 使用了 /economy_admin 指令")
            
            # 委託給經濟面板處理
            await self.economy_panel.handle_interaction(interaction)
            
        except ServiceError as e:
            await self._send_service_error(interaction, e)
        except Exception as e:
            self.logger.exception(f"處理 /economy_admin 指令時發生未預期錯誤：{e}")
            await self._send_generic_error(interaction)
    
    # ==========================================================================
    # 錯誤處理
    # ==========================================================================
    
    async def _send_service_error(self, interaction: discord.Interaction, error: ServiceError):
        """發送服務錯誤訊息"""
        try:
            error_embed = discord.Embed(
                title="❌ 服務錯誤",
                description=error.user_message or "經濟系統暫時無法使用，請稍後再試。",
                color=discord.Color.red()
            )
            
            error_embed.set_footer(text=f"錯誤代碼：{error.operation}")
            
            if interaction.response.is_done():
                await interaction.followup.send(embed=error_embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
                
        except Exception as e:
            self.logger.exception(f"發送服務錯誤訊息時發生錯誤：{e}")
    
    async def _send_generic_error(self, interaction: discord.Interaction):
        """發送通用錯誤訊息"""
        try:
            error_embed = discord.Embed(
                title="❌ 系統錯誤",
                description="處理您的請求時發生錯誤，請稍後再試。",
                color=discord.Color.red()
            )
            
            error_embed.set_footer(text="如果問題持續發生，請聯繫管理員")
            
            if interaction.response.is_done():
                await interaction.followup.send(embed=error_embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
                
        except Exception as e:
            self.logger.exception(f"發送通用錯誤訊息時發生錯誤：{e}")
    
    # ==========================================================================
    # 錯誤處理器
    # ==========================================================================
    
    async def cog_app_command_error(
        self, 
        interaction: discord.Interaction, 
        error: app_commands.AppCommandError
    ):
        """處理斜線指令錯誤"""
        try:
            self.logger.error(f"斜線指令錯誤：{error}")
            
            if isinstance(error, app_commands.CommandOnCooldown):
                await self._send_cooldown_error(interaction, error)
            elif isinstance(error, app_commands.MissingPermissions):
                await self._send_permission_error(interaction)
            elif isinstance(error, app_commands.BotMissingPermissions):
                await self._send_bot_permission_error(interaction, error)
            else:
                await self._send_generic_error(interaction)
                
        except Exception as e:
            self.logger.exception(f"處理指令錯誤時發生錯誤：{e}")
    
    async def _send_cooldown_error(
        self, 
        interaction: discord.Interaction, 
        error: app_commands.CommandOnCooldown
    ):
        """發送冷卻時間錯誤訊息"""
        try:
            cooldown_embed = discord.Embed(
                title="⏱️ 指令冷卻中",
                description=f"請等待 {error.retry_after:.1f} 秒後再試。",
                color=discord.Color.orange()
            )
            
            if interaction.response.is_done():
                await interaction.followup.send(embed=cooldown_embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=cooldown_embed, ephemeral=True)
                
        except Exception as e:
            self.logger.exception(f"發送冷卻錯誤訊息時發生錯誤：{e}")
    
    async def _send_permission_error(self, interaction: discord.Interaction):
        """發送權限不足錯誤訊息"""
        try:
            permission_embed = discord.Embed(
                title="🚫 權限不足",
                description="您沒有使用此指令的權限。",
                color=discord.Color.red()
            )
            
            if interaction.response.is_done():
                await interaction.followup.send(embed=permission_embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=permission_embed, ephemeral=True)
                
        except Exception as e:
            self.logger.exception(f"發送權限錯誤訊息時發生錯誤：{e}")
    
    async def _send_bot_permission_error(
        self, 
        interaction: discord.Interaction, 
        error: app_commands.BotMissingPermissions
    ):
        """發送機器人權限不足錯誤訊息"""
        try:
            missing_perms = ', '.join(error.missing_permissions)
            
            bot_permission_embed = discord.Embed(
                title="🤖 機器人權限不足",
                description=f"機器人缺少以下權限：{missing_perms}",
                color=discord.Color.red()
            )
            
            bot_permission_embed.add_field(
                name="解決方法",
                value="請聯繫伺服器管理員為機器人添加所需權限。",
                inline=False
            )
            
            if interaction.response.is_done():
                await interaction.followup.send(embed=bot_permission_embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=bot_permission_embed, ephemeral=True)
                
        except Exception as e:
            self.logger.exception(f"發送機器人權限錯誤訊息時發生錯誤：{e}")
    
    # ==========================================================================
    # 統計和監控
    # ==========================================================================
    
    @commands.command(name="economy_stats", hidden=True)
    @commands.is_owner()
    async def economy_stats_command(self, ctx: commands.Context):
        """
        經濟系統統計指令（僅限機器人擁有者）
        
        顯示經濟系統的運行統計資訊
        """
        try:
            self._check_initialization()
            
            # 獲取面板統計
            panel_info = self.economy_panel.get_panel_info()
            
            # 建立統計嵌入訊息
            stats_embed = discord.Embed(
                title="📊 經濟系統統計",
                color=discord.Color.blue()
            )
            
            stats_embed.add_field(
                name="面板資訊",
                value=f"**名稱：** {panel_info['name']}\n"
                      f"**互動次數：** {panel_info['interaction_count']}\n"
                      f"**當前頁面：** {panel_info['current_page']}\n"
                      f"**建立時間：** <t:{int(datetime.fromisoformat(panel_info['created_at']).timestamp())}:R>",
                inline=False
            )
            
            if panel_info['last_interaction']:
                stats_embed.add_field(
                    name="最後互動",
                    value=f"<t:{int(datetime.fromisoformat(panel_info['last_interaction']).timestamp())}:R>",
                    inline=True
                )
            
            stats_embed.add_field(
                name="已註冊處理器",
                value=f"{len(panel_info['registered_handlers'])} 個",
                inline=True
            )
            
            stats_embed.add_field(
                name="服務依賴",
                value=', '.join(panel_info['services']) or "無",
                inline=True
            )
            
            await ctx.send(embed=stats_embed)
            
        except Exception as e:
            self.logger.exception(f"處理統計指令時發生錯誤：{e}")
            await ctx.send("❌ 無法獲取統計資訊")


# =============================================================================
# Cog 設定函數
# =============================================================================

async def setup(bot: commands.Bot):
    """
    載入經濟系統 Cog 的設定函數
    
    參數：
        bot: Discord 機器人實例
    """
    try:
        cog = EconomyCog(bot)
        await bot.add_cog(cog)
        logging.getLogger('cogs.economy').info("經濟系統 Cog 已成功載入")
        
    except Exception as e:
        logging.getLogger('cogs.economy').exception(f"載入經濟系統 Cog 失敗：{e}")
        raise


async def teardown(bot: commands.Bot):
    """
    卸載經濟系統 Cog 的清理函數
    
    參數：
        bot: Discord 機器人實例
    """
    try:
        await bot.remove_cog("EconomyCog")
        logging.getLogger('cogs.economy').info("經濟系統 Cog 已成功卸載")
        
    except Exception as e:
        logging.getLogger('cogs.economy').exception(f"卸載經濟系統 Cog 失敗：{e}")
        raise