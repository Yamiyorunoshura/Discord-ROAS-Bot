"""
活躍度系統面板
Task ID: 9 - 重構現有模組以符合新架構

提供活躍度系統的 Discord UI 介面：
- 活躍度進度條顯示
- 每日排行榜展示
- 活躍度設定面板
- 報告頻道設定
- 統計資訊顯示
"""

import io
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
import discord
from discord import app_commands

from panels.base_panel import BasePanel
from core.exceptions import handle_errors, ValidationError, BotError
from services.activity import ActivityService
from services.activity.models import ActivityReport, LeaderboardEntry, ActivityImage

logger = logging.getLogger('panels.activity')


class ActivityPanel(BasePanel):
    """
    活躍度系統面板
    
    負責處理活躍度相關的 Discord UI 互動
    """
    
    def __init__(self, activity_service: ActivityService, config: Optional[Dict[str, Any]] = None):
        """
        初始化活躍度面板
        
        參數：
            activity_service: 活躍度服務實例
            config: 配置參數
        """
        super().__init__(
            name="ActivityPanel",
            title="📈 活躍度系統",
            description="管理用戶活躍度和排行榜",
            color=discord.Color.blue()
        )
        
        self.activity_service = activity_service
        self.config = config or {}
        
        # 添加服務依賴
        self.add_service(activity_service, "activity")
        
        logger.info("ActivityPanel 初始化完成")
    
    async def _handle_slash_command(self, interaction: discord.Interaction):
        """處理斜線命令（由 Cog 層處理，這裡不需要實作）"""
        pass
    
    @handle_errors(log_errors=True)
    async def show_activity_bar(
        self, 
        interaction: discord.Interaction,
        member: Optional[discord.Member] = None
    ) -> None:
        """
        顯示活躍度進度條
        
        參數：
            interaction: Discord 互動
            member: 要查詢的成員，如果為 None 則查詢互動發起者
        """
        try:
            # 檢查權限
            if not await self.validate_permissions(interaction, "view_activity", "activity"):
                return
            
            # 確定要查詢的成員
            target_member = member or interaction.user
            
            # 檢查是否為伺服器成員
            if not isinstance(target_member, discord.Member):
                await self.send_error(interaction, "只能查詢伺服器成員的活躍度。")
                return
            
            if not interaction.guild:
                await self.send_error(interaction, "此指令只能在伺服器中使用。")
                return
            
            # 延遲回應（圖片生成可能需要時間）
            await interaction.response.defer()
            
            # 生成活躍度圖片
            activity_image = await self.activity_service.generate_activity_image(
                target_member.id,
                interaction.guild.id,
                target_member
            )
            
            # 發送圖片
            file = discord.File(
                io.BytesIO(activity_image.image_bytes),
                filename="activity.png"
            )
            
            # 建立嵌入訊息
            embed = await self.create_embed(
                title=f"📊 {target_member.display_name} 的活躍度",
                description=f"目前活躍度：**{activity_image.score:.1f}** / {activity_image.max_score:.0f} 分",
                color=discord.Color.blue()
            )
            
            # 添加進度百分比
            progress_percentage = activity_image.get_progress_percentage()
            embed.add_field(
                name="進度",
                value=f"{progress_percentage:.1f}%",
                inline=True
            )
            
            # 設定圖片
            embed.set_image(url="attachment://activity.png")
            
            await interaction.followup.send(embed=embed, file=file)
            
            logger.info(f"顯示活躍度進度條：用戶 {target_member.id} 在 {interaction.guild.id}")
            
        except Exception as e:
            logger.error(f"顯示活躍度進度條失敗：{e}")
            await self.send_error(interaction, "顯示活躍度進度條時發生錯誤。")
    
    @handle_errors(log_errors=True)
    async def display_leaderboard(
        self,
        interaction: discord.Interaction,
        limit: int = 10
    ) -> None:
        """
        顯示排行榜
        
        參數：
            interaction: Discord 互動
            limit: 顯示數量限制
        """
        try:
            # 檢查權限
            if not await self.validate_permissions(interaction, "view_leaderboard", "activity"):
                return
            
            if not interaction.guild:
                await self.send_error(interaction, "此指令只能在伺服器中使用。")
                return
            
            # 延遲回應
            await interaction.response.defer()
            
            # 獲取排行榜
            leaderboard = await self.activity_service.get_daily_leaderboard(
                interaction.guild.id,
                min(limit, 20)  # 最多20名
            )
            
            if not leaderboard:
                embed = await self.create_embed(
                    title="📈 今日活躍排行榜",
                    description="今天還沒有人說話！",
                    color=discord.Color.orange()
                )
                await interaction.followup.send(embed=embed)
                return
            
            # 建立排行榜文字
            leaderboard_lines = []
            for entry in leaderboard:
                # 嘗試獲取成員物件
                member = interaction.guild.get_member(entry.user_id)
                display_name = member.display_name if member else f"<@{entry.user_id}>"
                
                leaderboard_lines.append(
                    f"`#{entry.rank:2}` {display_name:<20} ‧ "
                    f"今日 {entry.daily_messages} 則 ‧ 月均 {entry.monthly_average:.1f}"
                )
            
            # 建立嵌入訊息
            embed = await self.create_embed(
                title=f"📈 今日活躍排行榜 - {interaction.guild.name}",
                description="\n".join(leaderboard_lines),
                color=discord.Color.green()
            )
            
            # 獲取月度統計
            try:
                monthly_stats = await self.activity_service.get_monthly_stats(interaction.guild.id)
                
                embed.add_field(
                    name="📊 本月統計",
                    value=(
                        f"📝 總訊息數：{monthly_stats.total_messages:,}\n"
                        f"👥 活躍用戶：{monthly_stats.active_users}\n"
                        f"📈 平均訊息：{monthly_stats.average_messages_per_user:.1f} 則/人"
                    ),
                    inline=False
                )
            except Exception as e:
                logger.warning(f"獲取月度統計失敗：{e}")
            
            await interaction.followup.send(embed=embed)
            
            logger.info(f"顯示排行榜：{interaction.guild.id}，限制 {limit} 名")
            
        except Exception as e:
            logger.error(f"顯示排行榜失敗：{e}")
            await self.send_error(interaction, "顯示排行榜時發生錯誤。")
    
    @handle_errors(log_errors=True)
    async def show_settings_panel(self, interaction: discord.Interaction) -> None:
        """
        顯示設定面板
        
        參數：
            interaction: Discord 互動
        """
        try:
            # 檢查權限
            if not await self.validate_permissions(interaction, "update_settings", "activity"):
                return
            
            if not interaction.guild:
                await self.send_error(interaction, "此指令只能在伺服器中使用。")
                return
            
            # 獲取目前設定
            settings = await self.activity_service.get_settings(interaction.guild.id)
            
            # 建立設定資訊
            settings_fields = [
                {
                    'name': '📺 自動播報頻道',
                    'value': f"<#{settings.report_channel_id}>" if settings.report_channel_id else "未設定",
                    'inline': True
                },
                {
                    'name': '🕐 播報時間',
                    'value': f"{settings.report_hour}:00",
                    'inline': True
                },
                {
                    'name': '🔘 自動播報',
                    'value': "✅ 已啟用" if settings.auto_report_enabled else "❌ 已停用",
                    'inline': True
                },
                {
                    'name': '⭐ 最大分數',
                    'value': f"{settings.max_score:.0f} 分",
                    'inline': True
                },
                {
                    'name': '📈 每則訊息增益',
                    'value': f"{settings.gain_per_message:.1f} 分",
                    'inline': True
                },
                {
                    'name': '⏱️ 冷卻時間',
                    'value': f"{settings.cooldown_seconds} 秒",
                    'inline': True
                },
                {
                    'name': '📉 衰減延遲',
                    'value': f"{settings.decay_after_seconds} 秒後開始衰減",
                    'inline': True
                },
                {
                    'name': '📉 衰減速率',
                    'value': f"{settings.decay_per_hour:.1f} 分/小時",
                    'inline': True
                }
            ]
            
            embed = await self.create_embed(
                title="⚙️ 活躍度系統設定",
                description="目前的活躍度系統設定如下：",
                color=discord.Color.blue(),
                fields=settings_fields
            )
            
            embed.set_footer(text="使用相應的設定指令來修改這些設定")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            logger.info(f"顯示設定面板：{interaction.guild.id}")
            
        except Exception as e:
            logger.error(f"顯示設定面板失敗：{e}")
            await self.send_error(interaction, "顯示設定面板時發生錯誤。")
    
    @handle_errors(log_errors=True)
    async def set_report_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel
    ) -> None:
        """
        設定自動播報頻道
        
        參數：
            interaction: Discord 互動
            channel: 目標頻道
        """
        try:
            # 檢查權限
            if not await self.validate_permissions(interaction, "update_settings", "activity"):
                return
            
            if not interaction.guild:
                await self.send_error(interaction, "此指令只能在伺服器中使用。")
                return
            
            # 設定播報頻道
            success = await self.activity_service.set_report_channel(
                interaction.guild.id,
                channel.id
            )
            
            if success:
                await self.send_success(
                    interaction,
                    f"✅ 已設定自動播報頻道為 {channel.mention}"
                )
                
                logger.info(f"設定播報頻道：{interaction.guild.id} -> {channel.id}")
            else:
                await self.send_error(interaction, "設定播報頻道失敗。")
                
        except Exception as e:
            logger.error(f"設定播報頻道失敗：{e}")
            await self.send_error(interaction, "設定播報頻道時發生錯誤。")
    
    @handle_errors(log_errors=True)
    async def send_activity_report(
        self,
        channel: discord.TextChannel,
        guild_id: int
    ) -> bool:
        """
        發送活躍度報告到指定頻道
        
        參數：
            channel: 目標頻道
            guild_id: 伺服器 ID
            
        返回：
            是否發送成功
        """
        try:
            # 生成報告
            report = await self.activity_service.generate_daily_report(guild_id)
            if not report:
                logger.info(f"沒有活躍度數據可報告：{guild_id}")
                return False
            
            # 建立嵌入訊息
            embed = await self.create_embed(
                title=f"📈 每日活躍度報告 - {channel.guild.name}",
                description=f"以下是 {datetime.now().strftime('%Y年%m月%d日')} 的活躍度統計：",
                color=discord.Color.green()
            )
            
            # 添加報告欄位
            report_fields = report.to_embed_fields()
            for field in report_fields:
                embed.add_field(**field)
            
            # 發送報告
            await channel.send(embed=embed)
            
            logger.info(f"成功發送活躍度報告到頻道 {channel.id}")
            return True
            
        except discord.Forbidden:
            logger.warning(f"沒有權限發送訊息到頻道 {channel.id}")
            return False
        except discord.HTTPException as e:
            logger.error(f"發送活躍度報告時發生 Discord 錯誤：{e}")
            return False
        except Exception as e:
            logger.error(f"發送活躍度報告時發生錯誤：{e}")
            return False
    
    @handle_errors(log_errors=True)
    async def update_setting_value(
        self,
        interaction: discord.Interaction,
        setting_key: str,
        value: Any
    ) -> None:
        """
        更新單一設定值
        
        參數：
            interaction: Discord 互動
            setting_key: 設定鍵
            value: 新值
        """
        try:
            # 檢查權限
            if not await self.validate_permissions(interaction, "update_settings", "activity"):
                return
            
            if not interaction.guild:
                await self.send_error(interaction, "此指令只能在伺服器中使用。")
                return
            
            # 驗證設定鍵
            valid_keys = [
                'report_hour', 'max_score', 'gain_per_message',
                'decay_after_seconds', 'decay_per_hour', 'cooldown_seconds',
                'auto_report_enabled'
            ]
            
            if setting_key not in valid_keys:
                await self.send_error(interaction, f"無效的設定鍵：{setting_key}")
                return
            
            # 驗證數值範圍
            validation_rules = {
                'report_hour': {'type': int, 'min_value': 0, 'max_value': 23},
                'max_score': {'type': float, 'min_value': 1.0, 'max_value': 1000.0},
                'gain_per_message': {'type': float, 'min_value': 0.1, 'max_value': 50.0},
                'decay_after_seconds': {'type': int, 'min_value': 0, 'max_value': 3600},
                'decay_per_hour': {'type': float, 'min_value': 0.0, 'max_value': 100.0},
                'cooldown_seconds': {'type': int, 'min_value': 0, 'max_value': 600},
                'auto_report_enabled': {'type': bool}
            }
            
            rules = validation_rules.get(setting_key, {})
            if not await self.validate_input(
                interaction,
                {setting_key: value},
                {setting_key: rules}
            ):
                return
            
            # 更新設定
            success = await self.activity_service.update_setting(
                interaction.guild.id,
                setting_key,
                value
            )
            
            if success:
                await self.send_success(
                    interaction,
                    f"✅ 已更新設定 `{setting_key}` 為 `{value}`"
                )
                
                logger.info(f"更新活躍度設定：{interaction.guild.id}.{setting_key} = {value}")
            else:
                await self.send_error(interaction, "更新設定失敗。")
                
        except Exception as e:
            logger.error(f"更新設定值失敗：{e}")
            await self.send_error(interaction, "更新設定時發生錯誤。")
    
    async def _validate_permissions(
        self,
        interaction: discord.Interaction,
        action: str
    ) -> bool:
        """
        面板層權限驗證
        
        參數：
            interaction: Discord 互動
            action: 要執行的動作
            
        返回：
            是否有權限
        """
        # 查看操作允許所有用戶
        if action in ['view_activity', 'view_leaderboard']:
            return True
        
        # 設定操作需要管理權限
        if action in ['update_settings', 'set_report_channel']:
            if not interaction.user.guild_permissions.manage_guild:
                return False
        
        return True