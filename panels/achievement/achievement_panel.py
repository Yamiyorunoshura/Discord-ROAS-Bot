"""
成就面板實作
Task ID: 7 - 實作成就系統使用者介面

這個模組實作完整的成就系統使用者介面，包括：
- F1: 成就面板基礎結構 - 繼承BasePanel，提供標準化UI介面
- F2: 使用者成就面板功能 - 成就查看、進度追蹤、詳情顯示
- F3: 管理員成就面板功能 - 成就管理、建立編輯、統計分析
- 完整的錯誤處理、權限檢查和效能最佳化

關鍵特性：
- 響應時間: 成就列表載入<2秒，管理操作<1秒
- 並發支援: 同時處理50個互動請求
- 分頁系統: 每頁最多10個成就
- 即時更新: 成就狀態變更即時反映
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List, Union
from math import ceil

import discord
from discord.ext import commands

from panels.base_panel import BasePanel
from services.achievement.achievement_service import AchievementService
from services.achievement.models import (
    Achievement, AchievementProgress, AchievementReward, TriggerCondition,
    AchievementType, TriggerType, RewardType, AchievementStatus
)
from core.exceptions import (
    ServiceError, ValidationError, ServicePermissionError,
    handle_errors, discord_error_handler
)

# 設定專用日誌記錄器
logger = logging.getLogger('panels.achievement')


class AchievementEmbedBuilder:
    """成就嵌入訊息建構器 - 統一管理所有UI樣式"""
    
    @staticmethod
    def create_achievement_list_embed(
        user_achievements: List[Dict[str, Any]],
        page: int = 0,
        per_page: int = 10,
        user_name: str = "使用者",
        total_count: int = 0
    ) -> discord.Embed:
        """建立成就列表嵌入訊息"""
        
        # 計算分頁資訊
        total_pages = max(1, ceil(total_count / per_page))
        start_index = page * per_page
        end_index = min(start_index + per_page, total_count)
        
        embed = discord.Embed(
            title=f"🏆 {user_name} 的成就",
            description=f"顯示第 {page + 1}/{total_pages} 頁 ({start_index + 1}-{end_index}/{total_count})",
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
        
        if not user_achievements:
            embed.add_field(
                name="📋 暫無成就記錄",
                value="開始在伺服器中活動以獲得成就吧！",
                inline=False
            )
            return embed
        
        # 分類成就
        completed_achievements = []
        in_progress_achievements = []
        
        for achievement in user_achievements[start_index:end_index]:
            if achievement["completed"]:
                completed_achievements.append(achievement)
            else:
                in_progress_achievements.append(achievement)
        
        # 顯示已完成的成就
        if completed_achievements:
            completed_text = ""
            for ach in completed_achievements:
                completed_date = "未知"
                if ach.get("completed_at"):
                    try:
                        completed_date = ach["completed_at"].strftime("%m/%d")
                    except:
                        completed_date = "最近"
                
                completed_text += f"✅ **{ach['achievement_name']}** ({completed_date})\n"
                completed_text += f"   _{ach['achievement_description']}_\n\n"
            
            if completed_text:
                embed.add_field(
                    name="🎉 已完成成就",
                    value=completed_text[:1024],  # Discord限制
                    inline=False
                )
        
        # 顯示進行中的成就
        if in_progress_achievements:
            progress_text = ""
            for ach in in_progress_achievements:
                # 計算進度百分比（簡化版本）
                progress_percent = AchievementEmbedBuilder._calculate_progress_percent(ach)
                progress_bar = AchievementEmbedBuilder._create_progress_bar(progress_percent)
                
                progress_text += f"⏳ **{ach['achievement_name']}** {progress_bar} {progress_percent:.1f}%\n"
                progress_text += f"   _{ach['achievement_description']}_\n\n"
            
            if progress_text:
                embed.add_field(
                    name="🔄 進行中成就",
                    value=progress_text[:1024],  # Discord限制
                    inline=False
                )
        
        # 添加統計資訊
        completed_count = len([a for a in user_achievements if a["completed"]])
        embed.add_field(
            name="📊 統計",
            value=f"已完成: {completed_count}\n進行中: {total_count - completed_count}",
            inline=True
        )
        
        # 添加分頁控制提示
        if total_pages > 1:
            embed.add_field(
                name="📄 分頁導航",
                value=f"使用按鈕切換頁面 (第{page + 1}頁，共{total_pages}頁)",
                inline=True
            )
        
        embed.set_footer(text="任務 ID: 7 | 成就系統使用者介面")
        return embed
    
    @staticmethod
    def create_achievement_details_embed(
        achievement: Achievement,
        progress: Optional[AchievementProgress] = None,
        user_name: str = "使用者"
    ) -> discord.Embed:
        """建立成就詳情嵌入訊息"""
        
        # 根據成就狀態設定顏色
        if progress and progress.completed:
            color = discord.Color.green()
            status_icon = "✅"
            status_text = "已完成"
        else:
            color = discord.Color.blue()
            status_icon = "⏳"
            status_text = "進行中"
        
        embed = discord.Embed(
            title=f"{status_icon} {achievement.name}",
            description=achievement.description,
            color=color,
            timestamp=datetime.now()
        )
        
        # 成就基本資訊
        type_emoji = {
            AchievementType.MILESTONE: "🎯",
            AchievementType.RECURRING: "🔄",
            AchievementType.HIDDEN: "🔍",
            AchievementType.PROGRESSIVE: "📈"
        }.get(achievement.achievement_type, "🏆")
        
        embed.add_field(
            name="🏷️ 成就資訊",
            value=f"**類型**: {type_emoji} {achievement.achievement_type.value.title()}\n"
                  f"**狀態**: {status_text}\n"
                  f"**ID**: `{achievement.id}`",
            inline=True
        )
        
        # 進度資訊
        if progress:
            if progress.completed and progress.completed_at:
                progress_info = f"完成時間: {progress.completed_at.strftime('%Y-%m-%d %H:%M')}"
            else:
                progress_percent = progress.get_progress_percentage(achievement)
                progress_bar = AchievementEmbedBuilder._create_progress_bar(progress_percent)
                progress_info = f"進度: {progress_bar} {progress_percent:.1f}%"
            
            embed.add_field(
                name="📊 進度狀況",
                value=progress_info,
                inline=True
            )
        else:
            embed.add_field(
                name="📊 進度狀況",
                value="尚未開始",
                inline=True
            )
        
        # 觸發條件
        if achievement.trigger_conditions:
            conditions_text = ""
            for i, condition in enumerate(achievement.trigger_conditions):
                trigger_type_name = AchievementEmbedBuilder._get_trigger_display_name(condition.trigger_type)
                conditions_text += f"{i+1}. {trigger_type_name} {condition.comparison_operator} {condition.target_value}\n"
            
            embed.add_field(
                name="🎯 完成條件",
                value=conditions_text[:1024],
                inline=False
            )
        
        # 獎勵資訊
        if achievement.rewards:
            rewards_text = ""
            for reward in achievement.rewards:
                reward_emoji = {
                    RewardType.CURRENCY: "💰",
                    RewardType.ROLE: "🎭",
                    RewardType.BADGE: "🏅",
                    RewardType.CUSTOM: "🎁"
                }.get(reward.reward_type, "🎁")
                
                rewards_text += f"{reward_emoji} {reward.reward_type.value.title()}: {reward.value}\n"
            
            embed.add_field(
                name="🎁 獎勵",
                value=rewards_text[:1024],
                inline=False
            )
        
        # 當前進度詳情（如果有）
        if progress and progress.current_progress and not progress.completed:
            progress_details = ""
            for key, value in progress.current_progress.items():
                display_name = AchievementEmbedBuilder._get_progress_display_name(key)
                progress_details += f"**{display_name}**: {value}\n"
            
            if progress_details:
                embed.add_field(
                    name="📋 當前進度",
                    value=progress_details[:1024],
                    inline=False
                )
        
        embed.set_footer(text=f"任務 ID: 7 | {user_name} 的成就詳情")
        return embed
    
    @staticmethod
    def create_admin_panel_embed(
        guild_name: str = "伺服器",
        stats: Optional[Dict[str, Any]] = None
    ) -> discord.Embed:
        """建立管理員面板嵌入訊息"""
        
        embed = discord.Embed(
            title=f"⚙️ {guild_name} 成就管理面板",
            description="選擇下方按鈕進行成就管理操作",
            color=discord.Color.purple(),
            timestamp=datetime.now()
        )
        
        if stats:
            embed.add_field(
                name="📊 伺服器統計",
                value=f"**總成就數**: {stats.get('total_achievements', 0)}\n"
                      f"**啟用成就**: {stats.get('active_achievements', 0)}\n"
                      f"**總完成次數**: {stats.get('total_completions', 0)}\n"
                      f"**平均完成率**: {stats.get('completion_rate', 0):.1%}",
                inline=True
            )
        
        embed.add_field(
            name="🔧 可用操作",
            value="• 📝 建立新成就\n"
                  "• 📋 管理現有成就\n"
                  "• 📊 查看詳細統計\n"
                  "• ⚡ 批量操作\n"
                  "• 🔄 系統設定",
            inline=True
        )
        
        embed.add_field(
            name="⚠️ 注意事項",
            value="• 成就修改會立即生效\n"
                  "• 刪除成就會清除所有進度\n"
                  "• 請謹慎操作避免影響使用者體驗",
            inline=False
        )
        
        embed.set_footer(text="任務 ID: 7 | 成就系統管理面板")
        return embed
    
    @staticmethod
    def create_error_embed(
        error_title: str = "發生錯誤",
        error_message: str = "系統發生未知錯誤，請稍後再試。",
        error_code: Optional[str] = None
    ) -> discord.Embed:
        """建立錯誤訊息嵌入"""
        
        embed = discord.Embed(
            title=f"❌ {error_title}",
            description=error_message,
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        
        if error_code:
            embed.add_field(
                name="🔍 錯誤代碼",
                value=f"`{error_code}`",
                inline=True
            )
        
        embed.add_field(
            name="💡 建議",
            value="• 檢查輸入是否正確\n• 確認您有足夠權限\n• 稍後再次嘗試\n• 聯絡管理員協助",
            inline=False
        )
        
        embed.set_footer(text="任務 ID: 7 | 成就系統錯誤處理")
        return embed
    
    @staticmethod
    def _calculate_progress_percent(achievement_data: Dict[str, Any]) -> float:
        """計算進度百分比（簡化版本）"""
        # 這是一個簡化的進度計算，實際會根據觸發條件計算
        current_progress = achievement_data.get("current_progress", {})
        
        # 嘗試找到第一個數值進度
        for key, value in current_progress.items():
            if isinstance(value, (int, float)) and "count" in key:
                # 簡單估算：假設目標是100
                return min(value / 100, 1.0)
        
        return 0.0
    
    @staticmethod
    def _create_progress_bar(percentage: float, length: int = 10) -> str:
        """建立進度條字符串"""
        filled_length = int(length * percentage)
        bar = '█' * filled_length + '░' * (length - filled_length)
        return f"[{bar}]"
    
    @staticmethod
    def _get_trigger_display_name(trigger_type: Union[TriggerType, str]) -> str:
        """獲取觸發類型的顯示名稱"""
        display_names = {
            TriggerType.MESSAGE_COUNT: "訊息數量",
            TriggerType.VOICE_TIME: "語音時間",
            TriggerType.REACTION_COUNT: "反應次數",
            TriggerType.CUSTOM_EVENT: "自訂事件",
            TriggerType.LOGIN_STREAK: "連續登入",
            TriggerType.COMMAND_USAGE: "指令使用"
        }
        
        if isinstance(trigger_type, TriggerType):
            return display_names.get(trigger_type, trigger_type.value)
        else:
            return str(trigger_type).replace("_", " ").title()
    
    @staticmethod
    def _get_progress_display_name(progress_key: str) -> str:
        """獲取進度鍵值的顯示名稱"""
        display_names = {
            "message_count": "訊息數量",
            "voice_time": "語音時間(秒)",
            "reaction_count": "反應次數",
            "login_streak": "連續登入天數",
            "command_count": "指令使用次數"
        }
        
        return display_names.get(progress_key, progress_key.replace("_", " ").title())


class AchievementUIComponents:
    """成就UI元件 - 按鈕、選單等互動元件"""
    
    @staticmethod
    def create_pagination_view(current_page: int, total_pages: int, user_id: int) -> discord.ui.View:
        """建立分頁控制元件"""
        view = discord.ui.View(timeout=300)  # 5分鐘超時
        
        # 上一頁按鈕
        prev_button = discord.ui.Button(
            label="⬅️ 上一頁",
            style=discord.ButtonStyle.secondary,
            disabled=(current_page <= 0),
            custom_id=f"ach_prev_{user_id}_{current_page}"
        )
        
        # 下一頁按鈕
        next_button = discord.ui.Button(
            label="下一頁 ➡️",
            style=discord.ButtonStyle.secondary,
            disabled=(current_page >= total_pages - 1),
            custom_id=f"ach_next_{user_id}_{current_page}"
        )
        
        # 頁面資訊
        page_info = discord.ui.Button(
            label=f"{current_page + 1}/{total_pages}",
            style=discord.ButtonStyle.primary,
            disabled=True
        )
        
        view.add_item(prev_button)
        view.add_item(page_info)
        view.add_item(next_button)
        
        return view
    
    @staticmethod
    def create_admin_panel_view() -> discord.ui.View:
        """建立管理員面板操作元件"""
        view = discord.ui.View(timeout=600)  # 10分鐘超時
        
        # 建立成就按鈕
        create_button = discord.ui.Button(
            label="📝 建立成就",
            style=discord.ButtonStyle.green,
            custom_id="ach_admin_create"
        )
        
        # 管理成就按鈕
        manage_button = discord.ui.Button(
            label="📋 管理成就",
            style=discord.ButtonStyle.primary,
            custom_id="ach_admin_manage"
        )
        
        # 統計資訊按鈕
        stats_button = discord.ui.Button(
            label="📊 統計資訊",
            style=discord.ButtonStyle.secondary,
            custom_id="ach_admin_stats"
        )
        
        view.add_item(create_button)
        view.add_item(manage_button)
        view.add_item(stats_button)
        
        return view
    
    @staticmethod
    def create_achievement_filter_select(selected_filter: str = "all") -> discord.ui.Select:
        """建立成就篩選選單"""
        options = [
            discord.SelectOption(
                label="所有成就",
                value="all",
                description="顯示所有成就",
                emoji="🏆",
                default=(selected_filter == "all")
            ),
            discord.SelectOption(
                label="已完成",
                value="completed",
                description="只顯示已完成的成就",
                emoji="✅",
                default=(selected_filter == "completed")
            ),
            discord.SelectOption(
                label="進行中",
                value="in_progress",
                description="只顯示進行中的成就",
                emoji="⏳",
                default=(selected_filter == "in_progress")
            )
        ]
        
        select = discord.ui.Select(
            placeholder="選擇要顯示的成就類型...",
            options=options,
            custom_id="ach_filter_select"
        )
        
        return select


class AchievementPanel(BasePanel):
    """
    成就面板主類別
    
    提供完整的成就系統使用者介面，包括使用者檢視和管理員管理功能。
    繼承自BasePanel確保標準化的UI體驗和錯誤處理。
    """
    
    def __init__(self):
        super().__init__(
            name="AchievementPanel",
            title="🏆 成就系統",
            description="成就查看與管理介面",
            color=discord.Color.gold()
        )
        
        # 成就系統專用設定
        self.achievements_per_page = 10
        self.admin_timeout = 600  # 10分鐘管理員面板超時
        self.user_timeout = 300   # 5分鐘使用者面板超時
        
        # 效能優化設定
        self._user_cache_ttl = 60  # 使用者資料快取1分鐘
        self._admin_cache_ttl = 30  # 管理員統計快取30秒
        self._user_cache: Dict[str, Dict[str, Any]] = {}
        self._admin_cache: Dict[int, Dict[str, Any]] = {}
        
        # 註冊互動處理器
        self._register_interaction_handlers()
        
        logger.info("成就面板初始化完成")
    
    def _register_interaction_handlers(self):
        """註冊所有互動處理器"""
        # 分頁控制
        self.register_interaction_handler("ach_prev", self._handle_prev_page)
        self.register_interaction_handler("ach_next", self._handle_next_page)
        
        # 管理員操作
        self.register_interaction_handler("ach_admin_create", self._handle_admin_create)
        self.register_interaction_handler("ach_admin_manage", self._handle_admin_manage)
        self.register_interaction_handler("ach_admin_stats", self._handle_admin_stats)
        
        # 篩選控制
        self.register_interaction_handler("ach_filter_select", self._handle_filter_change)
    
    async def _handle_slash_command(self, interaction: discord.Interaction):
        """處理斜線指令 - BasePanel的抽象方法實作"""
        command_name = interaction.data.get("name", "")
        
        if command_name == "achievement":
            subcommand = interaction.data.get("options", [{}])[0].get("name", "")
            
            if subcommand == "view":
                await self.show_user_achievements(interaction)
            elif subcommand == "details":
                achievement_id = interaction.data.get("options", [{}])[0].get("options", [{}])[0].get("value", "")
                await self.show_achievement_details(interaction, achievement_id)
            elif subcommand == "admin":
                await self.show_admin_panel(interaction)
            else:
                await self.send_error(interaction, "未知的子指令")
        else:
            await self.send_error(interaction, "未知的指令")
    
    # ==========================================================================
    # F2: 使用者成就面板功能
    # ==========================================================================
    
    @handle_errors(log_errors=True)
    @discord_error_handler(send_to_user=True, ephemeral=True)
    async def show_user_achievements(
        self,
        interaction: discord.Interaction,
        page: int = 0,
        completed_only: bool = False,
        user_id: Optional[int] = None
    ) -> None:
        """
        顯示使用者成就列表
        
        參數：
            interaction: Discord互動
            page: 頁面編號（從0開始）
            completed_only: 是否只顯示已完成成就
            user_id: 指定使用者ID（預設為互動使用者）
        """
        try:
            target_user_id = user_id or interaction.user.id
            guild_id = interaction.guild.id if interaction.guild else None
            
            if not guild_id:
                await self.send_error(interaction, "此功能只能在伺服器中使用")
                return
            
            # 獲取成就服務
            achievement_service = self._get_achievement_service()
            
            # 獲取使用者成就資料（帶快取）
            cache_key = f"{target_user_id}_{guild_id}_{completed_only}"
            user_achievements = await self._get_cached_user_achievements(
                cache_key, target_user_id, guild_id, completed_only, achievement_service
            )
            
            # 計算分頁
            total_count = len(user_achievements)
            total_pages = max(1, ceil(total_count / self.achievements_per_page))
            
            # 驗證頁面編號
            if page < 0 or page >= total_pages:
                page = 0
            
            # 獲取使用者名稱
            user_name = interaction.user.display_name
            if user_id and user_id != interaction.user.id:
                try:
                    target_user = interaction.guild.get_member(user_id)
                    user_name = target_user.display_name if target_user else f"使用者 {user_id}"
                except:
                    user_name = f"使用者 {user_id}"
            
            # 建立嵌入訊息
            embed = AchievementEmbedBuilder.create_achievement_list_embed(
                user_achievements=user_achievements,
                page=page,
                per_page=self.achievements_per_page,
                user_name=user_name,
                total_count=total_count
            )
            
            # 建立互動元件
            view = None
            if total_pages > 1:
                view = AchievementUIComponents.create_pagination_view(
                    current_page=page,
                    total_pages=total_pages,
                    user_id=target_user_id
                )
            
            # 發送回應
            await self._send_response(interaction, embed=embed, view=view)
            
            # 記錄統計
            self.state.set_context("last_achievement_view", {
                "user_id": target_user_id,
                "page": page,
                "total_count": total_count,
                "completed_only": completed_only
            })
            
            logger.info(f"成就列表顯示成功 - 使用者: {target_user_id}, 頁面: {page}, 總數: {total_count}")
            
        except ServiceError as e:
            await self.send_error(interaction, f"服務錯誤：{e.message}")
            logger.error(f"成就列表服務錯誤: {e}")
        except Exception as e:
            await self.send_error(interaction, "載入成就列表時發生錯誤，請稍後再試")
            logger.exception(f"成就列表顯示異常: {e}")
    
    @handle_errors(log_errors=True)
    @discord_error_handler(send_to_user=True, ephemeral=True)
    async def show_achievement_details(
        self,
        interaction: discord.Interaction,
        achievement_id: str,
        user_id: Optional[int] = None
    ) -> None:
        """
        顯示成就詳情
        
        參數：
            interaction: Discord互動
            achievement_id: 成就ID
            user_id: 指定使用者ID（預設為互動使用者）
        """
        try:
            if not achievement_id or not achievement_id.strip():
                await self.send_error(interaction, "請提供有效的成就ID")
                return
            
            target_user_id = user_id or interaction.user.id
            guild_id = interaction.guild.id if interaction.guild else None
            
            if not guild_id:
                await self.send_error(interaction, "此功能只能在伺服器中使用")
                return
            
            # 獲取成就服務
            achievement_service = self._get_achievement_service()
            
            # 並行獲取成就和進度資料
            achievement_task = achievement_service.get_achievement(achievement_id)
            progress_task = achievement_service.get_user_progress(target_user_id, achievement_id)
            
            achievement, progress = await asyncio.gather(
                achievement_task, progress_task, return_exceptions=True
            )
            
            # 處理獲取結果
            if isinstance(achievement, Exception):
                raise achievement
            if isinstance(progress, Exception):
                logger.warning(f"獲取進度失敗: {progress}")
                progress = None
            
            if not achievement:
                await self.send_error(
                    interaction, 
                    f"找不到成就：{achievement_id}",
                    ephemeral=True
                )
                return
            
            # 獲取使用者名稱
            user_name = interaction.user.display_name
            if user_id and user_id != interaction.user.id:
                try:
                    target_user = interaction.guild.get_member(user_id)
                    user_name = target_user.display_name if target_user else f"使用者 {user_id}"
                except:
                    user_name = f"使用者 {user_id}"
            
            # 建立詳情嵌入訊息
            embed = AchievementEmbedBuilder.create_achievement_details_embed(
                achievement=achievement,
                progress=progress,
                user_name=user_name
            )
            
            # 發送回應
            await self._send_response(interaction, embed=embed)
            
            logger.info(f"成就詳情顯示成功 - 成就: {achievement_id}, 使用者: {target_user_id}")
            
        except ValidationError as e:
            await self.send_error(interaction, f"輸入驗證錯誤：{e.message}")
            logger.warning(f"成就詳情輸入錯誤: {e}")
        except ServiceError as e:
            await self.send_error(interaction, f"服務錯誤：{e.message}")
            logger.error(f"成就詳情服務錯誤: {e}")
        except Exception as e:
            await self.send_error(interaction, "載入成就詳情時發生錯誤，請稍後再試")
            logger.exception(f"成就詳情顯示異常: {e}")
    
    # ==========================================================================
    # F3: 管理員成就面板功能
    # ==========================================================================
    
    @handle_errors(log_errors=True)
    @discord_error_handler(send_to_user=True, ephemeral=True)
    async def show_admin_panel(self, interaction: discord.Interaction) -> None:
        """
        顯示管理員面板
        
        參數：
            interaction: Discord互動
        """
        try:
            guild_id = interaction.guild.id if interaction.guild else None
            user_id = interaction.user.id
            
            if not guild_id:
                await self.send_error(interaction, "此功能只能在伺服器中使用")
                return
            
            # 驗證管理員權限
            has_permission = await self.validate_permissions(
                interaction, "manage_achievements", "AchievementService"
            )
            
            if not has_permission:
                await self.send_error(
                    interaction,
                    "您沒有權限使用管理員面板。需要管理成就的權限。",
                    ephemeral=True
                )
                return
            
            # 獲取統計資料
            achievement_service = self._get_achievement_service()
            stats = await self._get_cached_admin_stats(guild_id, achievement_service)
            
            # 建立管理員面板嵌入訊息
            guild_name = interaction.guild.name if interaction.guild else "伺服器"
            embed = AchievementEmbedBuilder.create_admin_panel_embed(
                guild_name=guild_name,
                stats=stats
            )
            
            # 建立管理操作元件
            view = AchievementUIComponents.create_admin_panel_view()
            
            # 發送回應
            await self._send_response(interaction, embed=embed, view=view, ephemeral=True)
            
            logger.info(f"管理員面板顯示成功 - 管理員: {user_id}, 伺服器: {guild_id}")
            
        except ServicePermissionError as e:
            await self.send_error(interaction, f"權限錯誤：{e.message}", ephemeral=True)
            logger.warning(f"管理員面板權限錯誤: {e}")
        except ServiceError as e:
            await self.send_error(interaction, f"服務錯誤：{e.message}", ephemeral=True)
            logger.error(f"管理員面板服務錯誤: {e}")
        except Exception as e:
            await self.send_error(interaction, "載入管理員面板時發生錯誤，請稍後再試", ephemeral=True)
            logger.exception(f"管理員面板顯示異常: {e}")
    
    @handle_errors(log_errors=True)
    async def create_achievement_modal(self, interaction: discord.Interaction) -> None:
        """
        顯示成就建立模態對話框
        
        參數：
            interaction: Discord互動
        """
        try:
            # 建立模態對話框
            modal = AchievementCreationModal()
            await interaction.response.send_modal(modal)
            
            logger.info(f"成就建立模態顯示成功 - 管理員: {interaction.user.id}")
            
        except Exception as e:
            await self.send_error(interaction, "顯示建立表單時發生錯誤", ephemeral=True)
            logger.exception(f"成就建立模態異常: {e}")
    
    @handle_errors(log_errors=True)
    async def handle_achievement_creation(
        self, 
        interaction: discord.Interaction, 
        form_data: Dict[str, str]
    ) -> None:
        """
        處理成就建立表單提交
        
        參數：
            interaction: Discord互動
            form_data: 表單資料
        """
        try:
            guild_id = interaction.guild.id if interaction.guild else None
            if not guild_id:
                await self.send_error(interaction, "無法確定伺服器ID", ephemeral=True)
                return
            
            # 驗證權限
            has_permission = await self.validate_permissions(
                interaction, "create_achievement", "AchievementService"
            )
            
            if not has_permission:
                await self.send_error(
                    interaction,
                    "您沒有權限建立成就",
                    ephemeral=True
                )
                return
            
            # 解析表單資料並建立成就物件
            achievement = await self._parse_achievement_form_data(form_data, guild_id)
            
            # 建立成就
            achievement_service = self._get_achievement_service()
            created_achievement = await achievement_service.create_achievement(achievement)
            
            # 清理快取
            self._clear_admin_cache(guild_id)
            
            await self.send_success(
                interaction,
                f"✅ 成就「{created_achievement.name}」建立成功！\n成就ID: `{created_achievement.id}`",
                ephemeral=True
            )
            
            logger.info(f"成就建立成功 - ID: {created_achievement.id}, 管理員: {interaction.user.id}")
            
        except ValidationError as e:
            await self.send_error(interaction, f"表單驗證錯誤：{e.message}", ephemeral=True)
            logger.warning(f"成就建立驗證錯誤: {e}")
        except ServiceError as e:
            await self.send_error(interaction, f"建立失敗：{e.message}", ephemeral=True)
            logger.error(f"成就建立服務錯誤: {e}")
        except Exception as e:
            await self.send_error(interaction, "建立成就時發生錯誤，請稍後再試", ephemeral=True)
            logger.exception(f"成就建立異常: {e}")
    
    @handle_errors(log_errors=True)
    async def show_achievement_statistics(self, interaction: discord.Interaction) -> None:
        """
        顯示成就統計資訊
        
        參數：
            interaction: Discord互動
        """
        try:
            guild_id = interaction.guild.id if interaction.guild else None
            if not guild_id:
                await self.send_error(interaction, "此功能只能在伺服器中使用", ephemeral=True)
                return
            
            # 驗證權限
            has_permission = await self.validate_permissions(
                interaction, "view_statistics", "AchievementService"
            )
            
            if not has_permission:
                await self.send_error(
                    interaction,
                    "您沒有權限查看統計資訊",
                    ephemeral=True
                )
                return
            
            # 獲取詳細統計資料
            achievement_service = self._get_achievement_service()
            stats = await achievement_service.get_guild_achievement_stats(guild_id)
            
            # 建立統計嵌入訊息
            embed = self._create_statistics_embed(stats, interaction.guild.name)
            
            await self._send_response(interaction, embed=embed, ephemeral=True)
            
            logger.info(f"統計資訊顯示成功 - 管理員: {interaction.user.id}, 伺服器: {guild_id}")
            
        except Exception as e:
            await self.send_error(interaction, "載入統計資訊時發生錯誤", ephemeral=True)
            logger.exception(f"統計資訊顯示異常: {e}")
    
    @handle_errors(log_errors=True)
    async def toggle_achievement_visibility(
        self,
        interaction: discord.Interaction,
        achievement_id: str,
        new_status: AchievementStatus
    ) -> None:
        """
        切換成就可見性狀態
        
        參數：
            interaction: Discord互動
            achievement_id: 成就ID
            new_status: 新狀態
        """
        try:
            # 驗證權限
            has_permission = await self.validate_permissions(
                interaction, "update_achievement", "AchievementService"
            )
            
            if not has_permission:
                await self.send_error(
                    interaction,
                    "您沒有權限修改成就狀態",
                    ephemeral=True
                )
                return
            
            achievement_service = self._get_achievement_service()
            
            # 獲取現有成就
            achievement = await achievement_service.get_achievement(achievement_id)
            if not achievement:
                await self.send_error(interaction, f"找不到成就：{achievement_id}", ephemeral=True)
                return
            
            # 更新狀態
            achievement.status = new_status
            updated_achievement = await achievement_service.update_achievement(achievement)
            
            # 清理快取
            self._clear_admin_cache(interaction.guild.id)
            
            status_text = {
                AchievementStatus.ACTIVE: "啟用",
                AchievementStatus.DISABLED: "停用",
                AchievementStatus.ARCHIVED: "封存"
            }.get(new_status, "未知")
            
            await self.send_success(
                interaction,
                f"✅ 成就「{achievement.name}」狀態已更改為：{status_text}",
                ephemeral=True
            )
            
            logger.info(f"成就狀態切換成功 - ID: {achievement_id}, 狀態: {new_status.value}")
            
        except Exception as e:
            await self.send_error(interaction, "切換成就狀態時發生錯誤", ephemeral=True)
            logger.exception(f"成就狀態切換異常: {e}")
    
    # ==========================================================================
    # 互動處理器
    # ==========================================================================
    
    async def _handle_prev_page(self, interaction: discord.Interaction):
        """處理上一頁按鈕"""
        custom_id_parts = interaction.data.get("custom_id", "").split("_")
        if len(custom_id_parts) >= 4:
            user_id = int(custom_id_parts[2])
            current_page = int(custom_id_parts[3])
            new_page = max(0, current_page - 1)
            
            await self.show_user_achievements(interaction, page=new_page, user_id=user_id)
    
    async def _handle_next_page(self, interaction: discord.Interaction):
        """處理下一頁按鈕"""
        custom_id_parts = interaction.data.get("custom_id", "").split("_")
        if len(custom_id_parts) >= 4:
            user_id = int(custom_id_parts[2])
            current_page = int(custom_id_parts[3])
            new_page = current_page + 1
            
            await self.show_user_achievements(interaction, page=new_page, user_id=user_id)
    
    async def _handle_admin_create(self, interaction: discord.Interaction):
        """處理建立成就按鈕"""
        await self.create_achievement_modal(interaction)
    
    async def _handle_admin_manage(self, interaction: discord.Interaction):
        """處理管理成就按鈕"""
        # TODO: 實作成就管理介面
        await self.send_warning(interaction, "成就管理介面開發中", ephemeral=True)
    
    async def _handle_admin_stats(self, interaction: discord.Interaction):
        """處理統計資訊按鈕"""
        await self.show_achievement_statistics(interaction)
    
    async def _handle_filter_change(self, interaction: discord.Interaction):
        """處理篩選變更"""
        selected_filter = interaction.data.get("values", ["all"])[0]
        completed_only = (selected_filter == "completed")
        
        await self.show_user_achievements(
            interaction, 
            completed_only=completed_only
        )
    
    # ==========================================================================
    # 輔助方法和快取機制
    # ==========================================================================
    
    def _get_achievement_service(self) -> AchievementService:
        """獲取成就服務實例"""
        service = self.get_service("AchievementService")
        if not service:
            raise ServiceError(
                "成就服務不可用，請稍後再試",
                service_name="achievement_panel",
                operation="get_service"
            )
        return service
    
    async def _get_cached_user_achievements(
        self,
        cache_key: str,
        user_id: int,
        guild_id: int,
        completed_only: bool,
        service: AchievementService
    ) -> List[Dict[str, Any]]:
        """獲取帶快取的使用者成就資料"""
        now = datetime.now()
        
        # 檢查快取
        if cache_key in self._user_cache:
            cache_data = self._user_cache[cache_key]
            cache_time = cache_data.get("timestamp", now)
            if (now - cache_time).total_seconds() < self._user_cache_ttl:
                return cache_data["data"]
        
        # 從服務獲取資料
        achievements = await service.list_user_achievements(user_id, guild_id, completed_only)
        
        # 更新快取
        self._user_cache[cache_key] = {
            "data": achievements,
            "timestamp": now
        }
        
        # 清理過期快取
        self._cleanup_user_cache()
        
        return achievements
    
    async def _get_cached_admin_stats(
        self,
        guild_id: int,
        service: AchievementService
    ) -> Dict[str, Any]:
        """獲取帶快取的管理員統計資料"""
        now = datetime.now()
        
        # 檢查快取
        if guild_id in self._admin_cache:
            cache_data = self._admin_cache[guild_id]
            cache_time = cache_data.get("timestamp", now)
            if (now - cache_time).total_seconds() < self._admin_cache_ttl:
                return cache_data["data"]
        
        # 從服務獲取統計資料
        stats = await service.get_guild_achievement_stats(guild_id)
        
        # 更新快取
        self._admin_cache[guild_id] = {
            "data": stats,
            "timestamp": now
        }
        
        return stats
    
    def _cleanup_user_cache(self):
        """清理過期的使用者快取"""
        now = datetime.now()
        expired_keys = []
        
        for key, cache_data in self._user_cache.items():
            cache_time = cache_data.get("timestamp", now)
            if (now - cache_time).total_seconds() > self._user_cache_ttl * 2:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._user_cache[key]
    
    def _clear_admin_cache(self, guild_id: int):
        """清理指定伺服器的管理員快取"""
        if guild_id in self._admin_cache:
            del self._admin_cache[guild_id]
    
    async def _send_response(
        self,
        interaction: discord.Interaction,
        embed: discord.Embed,
        view: Optional[discord.ui.View] = None,
        ephemeral: bool = False
    ):
        """統一的回應發送方法"""
        try:
            if interaction.response.is_done():
                await interaction.followup.send(
                    embed=embed,
                    view=view,
                    ephemeral=ephemeral
                )
            else:
                await interaction.response.send_message(
                    embed=embed,
                    view=view,
                    ephemeral=ephemeral
                )
        except discord.InteractionResponded:
            # 如果回應已處理，使用followup
            await interaction.followup.send(
                embed=embed,
                view=view,
                ephemeral=ephemeral
            )
    
    async def _parse_achievement_form_data(
        self, 
        form_data: Dict[str, str], 
        guild_id: int
    ) -> Achievement:
        """解析成就建立表單資料"""
        # TODO: 實作完整的表單解析邏輯
        # 這是簡化版本，實際實作會包含完整的驗證和轉換
        
        name = form_data.get("name", "").strip()
        description = form_data.get("description", "").strip()
        achievement_type = AchievementType(form_data.get("achievement_type", "milestone"))
        
        if not name:
            raise ValidationError("成就名稱不能為空", field="name")
        if not description:
            raise ValidationError("成就描述不能為空", field="description")
        
        # 建立基本成就物件（簡化版本）
        achievement = Achievement(
            id=f"custom_{name.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            name=name,
            description=description,
            achievement_type=achievement_type,
            guild_id=guild_id,
            trigger_conditions=[
                TriggerCondition(
                    trigger_type=TriggerType.MESSAGE_COUNT,
                    target_value=10,
                    comparison_operator=">="
                )
            ],
            rewards=[]
        )
        
        return achievement
    
    def _create_statistics_embed(
        self, 
        stats: Dict[str, Any], 
        guild_name: str
    ) -> discord.Embed:
        """建立統計資訊嵌入訊息"""
        embed = discord.Embed(
            title=f"📊 {guild_name} 成就系統統計",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="🏆 成就總覽",
            value=f"**總成就數**: {stats.get('total_achievements', 0)}\n"
                  f"**啟用成就**: {stats.get('active_achievements', 0)}\n"
                  f"**停用成就**: {stats.get('disabled_achievements', 0)}",
            inline=True
        )
        
        embed.add_field(
            name="✅ 完成統計",
            value=f"**總完成次數**: {stats.get('total_completions', 0)}\n"
                  f"**平均完成率**: {stats.get('completion_rate', 0):.1%}\n"
                  f"**活躍使用者**: {stats.get('active_users', 0)}",
            inline=True
        )
        
        embed.add_field(
            name="📈 趨勢資訊",
            value=f"**本週新完成**: {stats.get('weekly_completions', 0)}\n"
                  f"**本月新完成**: {stats.get('monthly_completions', 0)}\n"
                  f"**成長率**: {stats.get('growth_rate', 0):.1%}",
            inline=True
        )
        
        embed.set_footer(text="任務 ID: 7 | 成就系統統計資訊")
        return embed


class AchievementCreationModal(discord.ui.Modal):
    """成就建立模態對話框"""
    
    def __init__(self):
        super().__init__(title="建立新成就")
        
        # 成就名稱
        self.add_item(discord.ui.TextInput(
            label="成就名稱",
            placeholder="輸入成就名稱（必填）",
            required=True,
            max_length=200
        ))
        
        # 成就描述
        self.add_item(discord.ui.TextInput(
            label="成就描述",
            placeholder="輸入成就描述（必填）",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=1000
        ))
        
        # 成就類型
        self.add_item(discord.ui.TextInput(
            label="成就類型",
            placeholder="milestone, recurring, hidden, progressive",
            required=True,
            default="milestone"
        ))
    
    async def on_submit(self, interaction: discord.Interaction):
        """處理模態對話框提交"""
        form_data = {
            "name": self.children[0].value,
            "description": self.children[1].value,
            "achievement_type": self.children[2].value
        }
        
        # 獲取成就面板實例並處理建立
        # 這需要從父級獲取面板實例，實際實作中會有更好的方式
        try:
            panel = AchievementPanel()  # 簡化版本
            await panel.handle_achievement_creation(interaction, form_data)
        except Exception as e:
            logger.exception(f"模態對話框處理異常: {e}")
            await interaction.response.send_message(
                "處理表單時發生錯誤，請稍後再試",
                ephemeral=True
            )