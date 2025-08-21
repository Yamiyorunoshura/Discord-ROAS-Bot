"""
成就系統Cog
Task ID: 7 - 實作成就系統使用者介面

這個模組提供成就系統的Discord斜線指令整合，包括：
- F4: 成就面板Cog整合 - 完整的Discord指令系統
- /achievement view - 查看個人成就列表
- /achievement details <id> - 查看特定成就詳情
- /achievement admin - 管理員成就管理面板
- 完整的錯誤處理和權限控制
- 響應時間<1秒的效能最佳化

關鍵特性：
- 與AchievementService完全整合
- 支援Discord互動超時限制
- 並發請求處理能力
- 優雅的錯誤處理和使用者反饋
"""

import asyncio
import logging
from typing import Optional, Dict, Any

import discord
from discord.ext import commands
from discord import app_commands

from panels.achievement.achievement_panel import AchievementPanel
from services.achievement.achievement_service import AchievementService
from core.base_service import service_registry
from core.exceptions import ServiceError, ValidationError, ServicePermissionError

# 設定專用日誌記錄器
logger = logging.getLogger('cogs.achievement')


class AchievementCog(commands.Cog):
    """
    成就系統Discord Cog
    
    提供完整的成就系統Discord整合，包括斜線指令、互動處理和權限控制。
    與AchievementPanel和AchievementService緊密整合，提供無縫的使用者體驗。
    """
    
    def __init__(self, bot: commands.Bot):
        """
        初始化成就Cog
        
        參數：
            bot: Discord Bot實例
        """
        self.bot = bot
        self.achievement_service: Optional[AchievementService] = None
        self.achievement_panel: Optional[AchievementPanel] = None
        
        # 效能監控
        self._command_stats: Dict[str, Dict[str, Any]] = {
            "view": {"count": 0, "total_time": 0.0, "errors": 0},
            "details": {"count": 0, "total_time": 0.0, "errors": 0},
            "admin": {"count": 0, "total_time": 0.0, "errors": 0}
        }
        
        logger.info("成就Cog初始化完成")
    
    async def cog_load(self):
        """Cog載入時執行"""
        try:
            # 獲取成就服務實例
            self.achievement_service = service_registry.get_service("AchievementService")
            if not self.achievement_service:
                logger.error("無法獲取成就服務實例")
                raise RuntimeError("成就服務不可用")
            
            # 建立成就面板實例
            self.achievement_panel = AchievementPanel()
            self.achievement_panel.add_service(self.achievement_service, "AchievementService")
            
            logger.info("成就Cog載入完成，依賴服務已初始化")
            
        except Exception as e:
            logger.exception(f"成就Cog載入失敗: {e}")
            raise
    
    async def cog_unload(self):
        """Cog卸載時執行"""
        try:
            # 清理資源
            self.achievement_service = None
            self.achievement_panel = None
            self._command_stats.clear()
            
            logger.info("成就Cog已卸載")
            
        except Exception as e:
            logger.exception(f"成就Cog卸載異常: {e}")
    
    # ==========================================================================
    # Discord斜線指令定義
    # ==========================================================================
    
    @app_commands.command(name="achievement", description="成就系統主指令")
    @app_commands.describe(
        action="要執行的動作",
        achievement_id="成就ID（查看詳情時需要）",
        user="指定使用者（預設為自己）"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="查看我的成就", value="view"),
        app_commands.Choice(name="查看成就詳情", value="details"),
        app_commands.Choice(name="管理員面板", value="admin")
    ])
    async def achievement(
        self,
        interaction: discord.Interaction,
        action: str,
        achievement_id: Optional[str] = None,
        user: Optional[discord.Member] = None
    ):
        """
        成就系統主指令
        
        參數：
            interaction: Discord互動
            action: 要執行的動作 (view, details, admin)
            achievement_id: 成就ID（查看詳情時需要）
            user: 指定使用者（預設為指令使用者）
        """
        import time
        start_time = time.time()
        
        try:
            # 基本驗證
            if not interaction.guild:
                await interaction.response.send_message(
                    "❌ 此指令只能在伺服器中使用",
                    ephemeral=True
                )
                return
            
            if not self.achievement_panel:
                await interaction.response.send_message(
                    "❌ 成就系統暫時不可用，請稍後再試",
                    ephemeral=True
                )
                return
            
            # 根據動作分發處理
            if action == "view":
                await self._handle_view_command(interaction, user)
            elif action == "details":
                await self._handle_details_command(interaction, achievement_id, user)
            elif action == "admin":
                await self._handle_admin_command(interaction)
            else:
                await interaction.response.send_message(
                    "❌ 無效的動作參數",
                    ephemeral=True
                )
                return
            
            # 記錄效能統計
            end_time = time.time()
            response_time = end_time - start_time
            self._update_command_stats(action, response_time, success=True)
            
            # 效能警告（響應時間>1秒）
            if response_time > 1.0:
                logger.warning(f"成就指令響應時間過長: {action} - {response_time:.2f}秒")
            
        except Exception as e:
            # 記錄錯誤統計
            end_time = time.time()
            response_time = end_time - start_time
            self._update_command_stats(action, response_time, success=False)
            
            logger.exception(f"成就指令處理異常: {action} - {e}")
            
            # 發送錯誤訊息（如果還沒回應）
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ 處理指令時發生錯誤，請稍後再試",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        "❌ 處理指令時發生錯誤，請稍後再試",
                        ephemeral=True
                    )
            except:
                pass  # 避免二次錯誤
    
    # ==========================================================================
    # 指令處理器
    # ==========================================================================
    
    async def _handle_view_command(
        self, 
        interaction: discord.Interaction, 
        target_user: Optional[discord.Member]
    ):
        """
        處理查看成就指令
        
        參數：
            interaction: Discord互動
            target_user: 目標使用者（None表示查看自己）
        """
        try:
            user_id = target_user.id if target_user else interaction.user.id
            
            # 權限檢查：只能查看自己的成就或管理員可以查看他人
            if target_user and target_user.id != interaction.user.id:
                # 檢查是否有管理員權限
                has_admin_permission = await self.achievement_panel.validate_permissions(
                    interaction, "view_others_achievements", "AchievementService"
                )
                
                if not has_admin_permission:
                    await interaction.response.send_message(
                        "❌ 您只能查看自己的成就",
                        ephemeral=True
                    )
                    return
            
            # 調用面板顯示成就列表
            await self.achievement_panel.show_user_achievements(
                interaction,
                user_id=user_id
            )
            
        except ServicePermissionError:
            await interaction.response.send_message(
                "❌ 您沒有權限執行此操作",
                ephemeral=True
            )
        except ServiceError as e:
            await interaction.response.send_message(
                f"❌ 服務錯誤：{e.message}",
                ephemeral=True
            )
        except Exception as e:
            logger.exception(f"查看成就指令處理異常: {e}")
            await interaction.response.send_message(
                "❌ 載入成就資料時發生錯誤，請稍後再試",
                ephemeral=True
            )
    
    async def _handle_details_command(
        self,
        interaction: discord.Interaction,
        achievement_id: Optional[str],
        target_user: Optional[discord.Member]
    ):
        """
        處理查看成就詳情指令
        
        參數：
            interaction: Discord互動
            achievement_id: 成就ID
            target_user: 目標使用者（None表示查看自己）
        """
        try:
            if not achievement_id or not achievement_id.strip():
                await interaction.response.send_message(
                    "❌ 請提供要查看的成就ID",
                    ephemeral=True
                )
                return
            
            user_id = target_user.id if target_user else interaction.user.id
            
            # 權限檢查：查看他人成就詳情需要權限
            if target_user and target_user.id != interaction.user.id:
                has_admin_permission = await self.achievement_panel.validate_permissions(
                    interaction, "view_others_achievements", "AchievementService"
                )
                
                if not has_admin_permission:
                    await interaction.response.send_message(
                        "❌ 您只能查看自己的成就詳情",
                        ephemeral=True
                    )
                    return
            
            # 調用面板顯示成就詳情
            await self.achievement_panel.show_achievement_details(
                interaction,
                achievement_id.strip(),
                user_id=user_id
            )
            
        except ValidationError as e:
            await interaction.response.send_message(
                f"❌ 輸入驗證錯誤：{e.message}",
                ephemeral=True
            )
        except ServiceError as e:
            await interaction.response.send_message(
                f"❌ 服務錯誤：{e.message}",
                ephemeral=True
            )
        except Exception as e:
            logger.exception(f"成就詳情指令處理異常: {e}")
            await interaction.response.send_message(
                "❌ 載入成就詳情時發生錯誤，請稍後再試",
                ephemeral=True
            )
    
    async def _handle_admin_command(self, interaction: discord.Interaction):
        """
        處理管理員面板指令
        
        參數：
            interaction: Discord互動
        """
        try:
            # 調用面板顯示管理員面板
            await self.achievement_panel.show_admin_panel(interaction)
            
        except ServicePermissionError:
            await interaction.response.send_message(
                "❌ 您沒有權限使用管理員面板",
                ephemeral=True
            )
        except ServiceError as e:
            await interaction.response.send_message(
                f"❌ 服務錯誤：{e.message}",
                ephemeral=True
            )
        except Exception as e:
            logger.exception(f"管理員面板指令處理異常: {e}")
            await interaction.response.send_message(
                "❌ 載入管理員面板時發生錯誤，請稍後再試",
                ephemeral=True
            )
    
    # ==========================================================================
    # 互動處理器（按鈕、選單等）
    # ==========================================================================
    
    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """
        監聽所有互動事件，處理成就相關的按鈕和選單
        
        參數：
            interaction: Discord互動
        """
        if interaction.type != discord.InteractionType.component:
            return
        
        custom_id = interaction.data.get("custom_id", "")
        
        # 只處理成就相關的互動
        if not custom_id.startswith("ach_"):
            return
        
        try:
            # 委託給成就面板處理
            if self.achievement_panel:
                await self.achievement_panel.handle_interaction(interaction)
            else:
                await interaction.response.send_message(
                    "❌ 成就系統暫時不可用",
                    ephemeral=True
                )
                
        except Exception as e:
            logger.exception(f"成就互動處理異常: {custom_id} - {e}")
            
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ 處理互動時發生錯誤，請稍後再試",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        "❌ 處理互動時發生錯誤，請稍後再試",
                        ephemeral=True
                    )
            except:
                pass
    
    # ==========================================================================
    # 事件監聽器
    # ==========================================================================
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Bot準備就緒時執行"""
        try:
            # 同步斜線指令
            await self.bot.tree.sync()
            logger.info("成就系統斜線指令同步完成")
            
        except Exception as e:
            logger.exception(f"斜線指令同步失敗: {e}")
    
    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        """指令錯誤處理"""
        if isinstance(error, commands.CommandNotFound):
            return  # 忽略未知指令
        
        logger.error(f"成就Cog指令錯誤: {error}")
        
        # 發送錯誤訊息給使用者
        try:
            await ctx.send("❌ 執行指令時發生錯誤", ephemeral=True)
        except:
            pass
    
    # ==========================================================================
    # 效能監控和診斷
    # ==========================================================================
    
    def _update_command_stats(self, command: str, response_time: float, success: bool):
        """更新指令統計"""
        if command in self._command_stats:
            stats = self._command_stats[command]
            stats["count"] += 1
            stats["total_time"] += response_time
            
            if not success:
                stats["errors"] += 1
    
    @app_commands.command(name="achievement-stats", description="查看成就系統統計（管理員專用）")
    async def achievement_stats(self, interaction: discord.Interaction):
        """
        查看成就系統統計資訊
        
        參數：
            interaction: Discord互動
        """
        try:
            # 權限檢查
            if not self.achievement_panel:
                await interaction.response.send_message(
                    "❌ 成就系統不可用",
                    ephemeral=True
                )
                return
            
            has_permission = await self.achievement_panel.validate_permissions(
                interaction, "view_statistics", "AchievementService"
            )
            
            if not has_permission:
                await interaction.response.send_message(
                    "❌ 您沒有權限查看系統統計",
                    ephemeral=True
                )
                return
            
            # 建立統計嵌入訊息
            embed = discord.Embed(
                title="📊 成就系統效能統計",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            
            # 指令統計
            for command, stats in self._command_stats.items():
                if stats["count"] > 0:
                    avg_time = stats["total_time"] / stats["count"]
                    error_rate = stats["errors"] / stats["count"] * 100
                    
                    embed.add_field(
                        name=f"🔧 /{command}",
                        value=f"執行次數: {stats['count']}\n"
                              f"平均響應: {avg_time:.3f}秒\n"
                              f"錯誤率: {error_rate:.1f}%",
                        inline=True
                    )
            
            # 系統狀態
            service_status = "✅ 正常" if self.achievement_service else "❌ 不可用"
            panel_status = "✅ 正常" if self.achievement_panel else "❌ 不可用"
            
            embed.add_field(
                name="🔗 系統狀態",
                value=f"成就服務: {service_status}\n"
                      f"面板系統: {panel_status}\n"
                      f"Bot延遲: {self.bot.latency*1000:.1f}ms",
                inline=True
            )
            
            embed.set_footer(text="任務 ID: 7 | 成就系統效能監控")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.exception(f"統計查看異常: {e}")
            await interaction.response.send_message(
                "❌ 載入統計資訊時發生錯誤",
                ephemeral=True
            )
    
    # ==========================================================================
    # 輔助方法
    # ==========================================================================
    
    def get_cog_info(self) -> Dict[str, Any]:
        """
        獲取Cog資訊
        
        返回：
            Cog狀態和統計資訊
        """
        return {
            "name": "AchievementCog",
            "status": "active" if self.achievement_service and self.achievement_panel else "inactive",
            "service_available": self.achievement_service is not None,
            "panel_available": self.achievement_panel is not None,
            "command_stats": self._command_stats.copy(),
            "bot_latency": self.bot.latency,
            "guild_count": len(self.bot.guilds) if self.bot.guilds else 0
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """
        健康檢查
        
        返回：
            系統健康狀態
        """
        health = {
            "cog_status": "healthy",
            "service_status": "unknown",
            "panel_status": "unknown",
            "recent_errors": sum(stats["errors"] for stats in self._command_stats.values()),
            "total_commands": sum(stats["count"] for stats in self._command_stats.values())
        }
        
        try:
            if self.achievement_service:
                service_health = await self.achievement_service.health_check()
                health["service_status"] = "healthy" if service_health.get("status") == "healthy" else "unhealthy"
            else:
                health["service_status"] = "unavailable"
                
            if self.achievement_panel:
                health["panel_status"] = "healthy"
            else:
                health["panel_status"] = "unavailable"
                
        except Exception as e:
            logger.exception(f"健康檢查異常: {e}")
            health["cog_status"] = "unhealthy"
            health["error"] = str(e)
        
        return health


# ==========================================================================
# Cog設定函數
# ==========================================================================

async def setup(bot: commands.Bot):
    """
    載入成就Cog
    
    參數：
        bot: Discord Bot實例
    """
    try:
        cog = AchievementCog(bot)
        await bot.add_cog(cog)
        logger.info("成就Cog載入成功")
        
    except Exception as e:
        logger.exception(f"成就Cog載入失敗: {e}")
        raise


async def teardown(bot: commands.Bot):
    """
    卸載成就Cog
    
    參數：
        bot: Discord Bot實例
    """
    try:
        await bot.remove_cog("AchievementCog")
        logger.info("成就Cog卸載完成")
        
    except Exception as e:
        logger.exception(f"成就Cog卸載異常: {e}")
        raise