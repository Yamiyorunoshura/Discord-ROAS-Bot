"""
政府系統Discord Cog
Task ID: 5 - 實作政府系統使用者介面

Luna的整合設計：將精心設計的政府面板與Discord的斜線指令系統完美結合，
讓常任理事會能夠透過簡單的指令就能管理整個政府架構。
這是科技與治理的美好結合。

這個模組提供：
- /government 主指令：開啟政府管理面板
- /department 系列指令：快速部門操作
- 完整的互動事件處理
- 與GovernmentPanel的無縫整合
"""

import logging
from typing import Optional, Dict, Any

import discord
from discord.ext import commands
from discord import app_commands

from panels.government.government_panel import GovernmentPanel
from services.government.government_service import GovernmentService
from services.government.role_service import RoleService
from services.economy.economy_service import EconomyService
from core.exceptions import ServiceError, ValidationError, handle_errors


class GovernmentCog(commands.Cog):
    """
    政府系統Discord Cog
    
    Luna的指令設計：每個指令都是使用者與政府系統互動的入口，
    要確保響應快速、操作直觀、錯誤處理完善。
    """
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger('cogs.government')
        
        # 政府面板實例
        self.government_panel: Optional[GovernmentPanel] = None
        
        # 服務實例
        self.government_service: Optional[GovernmentService] = None
        self.role_service: Optional[RoleService] = None
        self.economy_service: Optional[EconomyService] = None
        
        # 初始化標記
        self._initialized = False
    
    async def cog_load(self):
        """Cog載入時的初始化"""
        try:
            await self._initialize_services()
            await self._initialize_panel()
            self._initialized = True
            self.logger.info("政府系統Cog已成功載入")
            
            # 在引擎準備完成後註冊事件監聽器
            if hasattr(self.bot, 'add_listener'):
                self.bot.add_listener(self.on_interaction_error, 'on_interaction')
            
        except Exception as e:
            self.logger.exception(f"政府系統Cog載入失敗：{e}")
            raise
    
    async def cog_unload(self):
        """Cog卸載時的清理"""
        self._initialized = False
        self.government_panel = None
        self.logger.info("政府系統Cog已卸載")
    
    async def _initialize_services(self):
        """
        初始化服務依賴
        
        Luna的服務整合：確保所有依賴的服務都正確初始化
        """
        self.logger.info("正在初始化政府系統服務依賴...")
        
        try:
            # 從服務註冊表獲取服務實例
            from core.base_service import service_registry
            
            self.government_service = service_registry.get_service("GovernmentService")
            if not self.government_service:
                self.logger.error("政府服務不可用")
                raise RuntimeError("政府服務初始化失敗")
            
            self.role_service = service_registry.get_service("RoleService")
            if not self.role_service:
                self.logger.error("身分組服務不可用")
                raise RuntimeError("身分組服務初始化失敗")
            
            self.economy_service = service_registry.get_service("EconomyService")
            if not self.economy_service:
                self.logger.error("經濟服務不可用")
                raise RuntimeError("經濟服務初始化失敗")
            
            self.logger.info("政府系統服務依賴初始化完成")
            
        except Exception as e:
            self.logger.exception(f"服務依賴初始化失敗：{e}")
            raise
    
    async def _initialize_panel(self):
        """
        初始化政府面板
        
        Luna的面板初始化：創建溫暖可靠的政府管理介面
        """
        self.government_panel = GovernmentPanel()
        
        # 將服務添加到面板
        if self.government_service:
            self.government_panel.add_service(self.government_service, "GovernmentService")
        if self.role_service:
            self.government_panel.add_service(self.role_service, "RoleService")
        if self.economy_service:
            self.government_panel.add_service(self.economy_service, "EconomyService")
        
        # 初始化面板服務
        panel_init_success = await self.government_panel.initialize_services()
        if not panel_init_success:
            self.logger.error("政府面板服務初始化失敗")
            raise RuntimeError("政府面板初始化失敗")
        
        self.logger.info("政府面板初始化完成")
    
    # ==================== 主要斜線指令 ====================
    
    @app_commands.command(
        name="government",
        description="🏛️ 開啟常任理事會政府管理系統"
    )
    async def government_command(self, interaction: discord.Interaction):
        """
        政府系統主指令
        
        Luna的主入口設計：這是使用者與政府系統的第一次接觸，
        要給人專業、可靠、易用的第一印象
        """
        try:
            # 檢查初始化狀態
            if not self._initialized or not self.government_panel:
                await interaction.response.send_message(
                    "❌ 政府系統尚未完全初始化，請稍後再試。",
                    ephemeral=True
                )
                return
            
            # 記錄指令使用
            self.logger.info(f"使用者 {interaction.user.id} 執行了 /government 指令")
            
            # 委託給政府面板處理
            await self.government_panel.handle_interaction(interaction)
            
        except Exception as e:
            self.logger.exception(f"處理 /government 指令時發生錯誤")
            
            # 友善的錯誤訊息
            error_embed = discord.Embed(
                title="❌ 系統錯誤",
                description="政府系統暫時無法使用，請稍後再試。",
                color=discord.Color.red()
            )
            error_embed.add_field(
                name="建議",
                value="如果問題持續發生，請聯繫系統管理員。",
                inline=False
            )
            
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(embed=error_embed, ephemeral=True)
                else:
                    await interaction.response.send_message(embed=error_embed, ephemeral=True)
            except:
                pass
    
    # ==================== 部門快速操作指令 ====================
    
    department_group = app_commands.Group(
        name="department",
        description="部門管理快速操作"
    )
    
    @department_group.command(
        name="create",
        description="🏢 快速建立新部門"
    )
    @app_commands.describe(
        name="部門名稱",
        head="部長使用者（可選）",
        level="部門級別（可選）"
    )
    async def department_create(
        self,
        interaction: discord.Interaction,
        name: str,
        head: Optional[discord.Member] = None,
        level: Optional[str] = None
    ):
        """
        快速建立部門指令
        
        Luna的快速操作：為熟練使用者提供命令列式的快速操作
        """
        try:
            if not self._initialized or not self.government_panel:
                await interaction.response.send_message(
                    "❌ 政府系統尚未初始化。",
                    ephemeral=True
                )
                return
            
            # 權限檢查
            if not await self.government_panel._validate_permissions(interaction, "create_department"):
                await interaction.response.send_message(
                    "❌ 您需要常任理事權限才能建立部門。",
                    ephemeral=True
                )
                return
            
            # 顯示處理中
            await interaction.response.send_message(
                f"⏳ 正在建立部門「{name}」，請稍等...",
                ephemeral=True
            )
            
            # 準備部門資料
            department_data = {
                "name": name.strip(),
                "head_user_id": head.id if head else None,
                "level_name": level.strip() if level else "",
                "description": ""
            }
            
            # 建立部門（需要確保服務可用）
            if self.government_service:
                department_id = await self.government_service.create_department(
                    interaction.guild,
                    department_data
                )
                
                # 成功回饋
                success_embed = discord.Embed(
                    title="✅ 部門建立成功",
                    description=f"部門「**{name}**」已成功建立！",
                    color=discord.Color.green()
                )
                
                success_embed.add_field(
                    name="部門資訊",
                    value=(
                        f"**ID**: {department_id}\n"
                        f"**部長**: {head.mention if head else '待指派'}\n"
                        f"**級別**: {level or '未設定'}"
                    ),
                    inline=False
                )
                
                await interaction.followup.send(embed=success_embed, ephemeral=False)
            else:
                await interaction.followup.send(
                    "❌ 政府服務暫時不可用，請使用面板操作。",
                    ephemeral=True
                )
            
        except ValidationError as e:
            await interaction.followup.send(
                f"❌ 輸入錯誤：{e.user_message}",
                ephemeral=True
            )
        except ServiceError as e:
            await interaction.followup.send(
                f"❌ 建立失敗：{e.user_message}",
                ephemeral=True
            )
        except Exception as e:
            self.logger.exception(f"快速建立部門時發生錯誤")
            await interaction.followup.send(
                "❌ 建立部門時發生系統錯誤。",
                ephemeral=True
            )
    
    @department_group.command(
        name="list",
        description="📋 查看部門列表"
    )
    async def department_list(self, interaction: discord.Interaction):
        """
        查看部門列表指令
        
        Luna的列表顯示：快速查看所有部門概況
        """
        try:
            if not self._initialized or not self.government_panel:
                await interaction.response.send_message(
                    "❌ 政府系統尚未初始化。",
                    ephemeral=True
                )
                return
            
            # 委託給面板的註冊表查看功能
            await self.government_panel._handle_view_registry(interaction)
            
        except Exception as e:
            self.logger.exception(f"查看部門列表時發生錯誤")
            await interaction.response.send_message(
                "❌ 無法載入部門列表。",
                ephemeral=True
            )
    
    @department_group.command(
        name="info",
        description="ℹ️ 查看特定部門詳情"
    )
    @app_commands.describe(department_id="部門ID")
    async def department_info(
        self,
        interaction: discord.Interaction,
        department_id: int
    ):
        """
        查看部門詳情指令
        
        Luna的詳情顯示：提供完整的部門資訊展示
        """
        try:
            if not self._initialized or not self.government_service:
                await interaction.response.send_message(
                    "❌ 政府系統尚未初始化。",
                    ephemeral=True
                )
                return
            
            # 獲取部門資訊
            department = await self.government_service.get_department_by_id(department_id)
            
            if not department:
                await interaction.response.send_message(
                    f"❌ 找不到ID為 {department_id} 的部門。",
                    ephemeral=True
                )
                return
            
            # 建立詳情嵌入
            embed = discord.Embed(
                title=f"🏢 {department['name']}",
                description="部門詳細資訊",
                color=discord.Color.blue()
            )
            
            # 基本資訊
            head_text = f"<@{department['head_user_id']}>" if department.get('head_user_id') else "待指派"
            embed.add_field(
                name="基本資訊",
                value=(
                    f"**部門ID**: {department['id']}\n"
                    f"**部長**: {head_text}\n"
                    f"**級別**: {department.get('level_name', '未設定')}"
                ),
                inline=False
            )
            
            # 時間資訊
            created_at = department.get('created_at', '未知')
            updated_at = department.get('updated_at', '未知')
            
            embed.add_field(
                name="時間資訊",
                value=(
                    f"**建立時間**: {created_at}\n"
                    f"**更新時間**: {updated_at}"
                ),
                inline=False
            )
            
            # 帳戶資訊
            if department.get('account_id'):
                embed.add_field(
                    name="財務資訊",
                    value=f"**帳戶ID**: {department['account_id']}",
                    inline=False
                )
            
            embed.set_footer(text=f"政府管理系統 | 任務 ID: 5")
            
            await interaction.response.send_message(embed=embed, ephemeral=False)
            
        except Exception as e:
            self.logger.exception(f"查看部門詳情時發生錯誤")
            await interaction.response.send_message(
                "❌ 無法載入部門詳情。",
                ephemeral=True
            )
    
    @commands.Cog.listener()
    async def on_interaction_error(self, interaction: discord.Interaction, error: Exception):
        """
        處理互動錯誤
        
        Luna的錯誤監控：監控所有政府相關的互動錯誤並提供適當的回駈
        """
        # 只處理政府相關的互動錯誤
        if (interaction.data and 
            interaction.data.get('custom_id', '').startswith('gov_')):
            
            self.logger.error(f"政府系統互動錯誤：{error}", exc_info=True)
            
            try:
                error_embed = discord.Embed(
                    title="⚠️ 互動錯誤",
                    description="政府系統處理您的操作時發生錯誤。",
                    color=discord.Color.orange()
                )
                
                error_embed.add_field(
                    name="建議解決方式",
                    value=(
                        "1. 請稍後再試一次\n"
                        "2. 如果問題持續，請使用 `/government` 指令重新開始\n"
                        "3. 若仍無法解決，請聯繫管理員"
                    ),
                    inline=False
                )
                
                if not interaction.response.is_done():
                    await interaction.response.send_message(embed=error_embed, ephemeral=True)
                else:
                    await interaction.followup.send(embed=error_embed, ephemeral=True)
                    
            except Exception as e:
                self.logger.error(f"無法發送錯誤回駈：{e}")
    
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """
        處理與政府面板相關的互動事件
        
        Luna的事件路由：確保所有政府相關的互動都能正確處理
        """
        try:
            # 只處理政府面板相關的互動
            if (interaction.type == discord.InteractionType.component and 
                interaction.data and 
                interaction.data.get('custom_id', '').startswith('gov_')):
                
                if not self._initialized or not self.government_panel:
                    await interaction.response.send_message(
                        "❌ 政府系統暫時不可用。",
                        ephemeral=True
                    )
                    return
                
                # 委託給政府面板處理
                await self.government_panel.handle_interaction(interaction)
            
            # 處理政府相關的模態框提交
            elif (interaction.type == discord.InteractionType.modal_submit and
                  interaction.data and
                  'government' in interaction.data.get('custom_id', '').lower()):
                
                if not self._initialized or not self.government_panel:
                    await interaction.response.send_message(
                        "❌ 政府系統暫時不可用。",
                        ephemeral=True
                    )
                    return
                
                # 委託給政府面板處理
                await self.government_panel.handle_interaction(interaction)
                
        except Exception as e:
            self.logger.exception(f"處理政府系統互動時發生錯誤")
            
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ 處理互動時發生錯誤。",
                        ephemeral=True
                    )
            except:
                pass
    
    # ==================== 管理指令 ====================
    
    @app_commands.command(
        name="gov-setup",
        description="🏛️ 設定常任理事會基礎設施（管理員專用）"
    )
    @app_commands.default_permissions(administrator=True)
    async def government_setup(self, interaction: discord.Interaction):
        """
        政府基礎設施設定指令
        
        Luna的基礎設施：為新伺服器建立完整的政府管理基礎
        """
        try:
            if not self._initialized or not self.government_service:
                await interaction.response.send_message(
                    "❌ 政府系統尚未初始化。",
                    ephemeral=True
                )
                return
            
            # 顯示處理中
            await interaction.response.send_message(
                "⏳ 正在設定常任理事會基礎設施...",
                ephemeral=True
            )
            
            # 建立基礎設施
            success = await self.government_service.ensure_council_infrastructure(interaction.guild)
            
            if success:
                success_embed = discord.Embed(
                    title="✅ 理事會設定完成",
                    description="常任理事會基礎設施已成功建立！",
                    color=discord.Color.green()
                )
                
                success_embed.add_field(
                    name="已建立項目",
                    value=(
                        "• 常任理事身分組\n"
                        "• 理事會專用帳戶\n"
                        "• 政府管理權限\n"
                        "• 基礎架構設定"
                    ),
                    inline=False
                )
                
                success_embed.add_field(
                    name="下一步",
                    value="現在您可以使用 `/government` 指令開始管理政府部門。",
                    inline=False
                )
                
                await interaction.followup.send(embed=success_embed, ephemeral=False)
            else:
                await interaction.followup.send(
                    "❌ 基礎設施建立失敗，請檢查機器人權限。",
                    ephemeral=True
                )
                
        except Exception as e:
            self.logger.exception(f"設定政府基礎設施時發生錯誤")
            await interaction.followup.send(
                "❌ 設定過程中發生錯誤。",
                ephemeral=True
            )
    
    # ==================== 錯誤處理 ====================
    
    async def cog_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError
    ):
        """
        Cog層級的應用程式指令錯誤處理
        
        Luna的錯誤處理：即使出錯也要給使用者溫暖的體驗
        """
        self.logger.error(f"政府系統指令錯誤：{error}")
        
        # 權限錯誤
        if isinstance(error, app_commands.MissingPermissions):
            error_msg = "❌ 您沒有執行此指令的權限。"
        
        # 參數錯誤
        elif isinstance(error, app_commands.CommandInvokeError):
            error_msg = "❌ 指令執行時發生錯誤，請稍後再試。"
        
        # 通用錯誤
        else:
            error_msg = "❌ 發生未知錯誤，請聯繫管理員。"
        
        try:
            if interaction.response.is_done():
                await interaction.followup.send(error_msg, ephemeral=True)
            else:
                await interaction.response.send_message(error_msg, ephemeral=True)
        except:
            # 如果連錯誤訊息都無法發送，只能記錄到日誌
            self.logger.error(f"無法發送錯誤訊息給使用者 {interaction.user.id}")


async def setup(bot: commands.Bot):
    """
    設定政府系統Cog
    
    Luna的模組載入：讓政府系統與Discord bot完美融合
    """
    await bot.add_cog(GovernmentCog(bot))