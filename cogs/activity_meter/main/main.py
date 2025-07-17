"""
活躍度系統主要邏輯協調中心
- 作為模組的核心，協調各個子模組的工作
- 處理指令和事件
"""

import asyncio
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Union

import discord
from discord import app_commands
from discord.ext import commands

from ..config import config
from ..database.database import ActivityDatabase
from .calculator import ActivityCalculator
from .renderer import ActivityRenderer
from .tasks import ActivityTasks

# 使用統一的核心模塊
from ...core import create_error_handler, setup_module_logger, ErrorCodes

# 設置模塊日誌記錄器
logger = setup_module_logger("activity_meter")
error_handler = create_error_handler("activity_meter", logger)

class ActivityMeter(commands.Cog):
    """
    活躍度系統 Cog
    - 計算用戶活躍度（0~100 分，隨時間衰減）
    - 提供每日/月排行榜查詢
    - 支援自動播報與排行榜頻道設定
    - 具備詳細錯誤處理與日誌
    """

    def __init__(self, bot: commands.Bot):
        """
        初始化活躍度系統
        
        Args:
            bot: Discord 機器人實例
        """
        self.bot = bot
        self.lock = asyncio.Lock()  # 全域鎖，避免資料競爭
        
        # 初始化子模組
        self.db = ActivityDatabase()
        self.calculator = ActivityCalculator()
        self.renderer = ActivityRenderer()
        self.tasks = ActivityTasks(bot, self.db)
        
        # 啟動初始化和背景任務
        bot.loop.create_task(self._init_module())
    
    async def _init_module(self):
        """模組初始化"""
        try:
            await self.db.init_db()
            self.tasks.start()
            logger.info("【活躍度】模組初始化完成")
        except Exception as e:
            logger.error(f"【活躍度】模組初始化失敗: {e}")
    
    async def cog_unload(self):
        """模組卸載時的清理工作"""
        try:
            self.tasks.stop()
            await self.db.close()
            logger.info("【活躍度】模組已卸載")
        except Exception as e:
            logger.error(f"【活躍度】模組卸載時發生錯誤: {e}")
    
    # -------- 指令 --------
    @app_commands.command(name="活躍度", description="查看活躍度（進度條）")
    async def activity(self, inter: discord.Interaction, 成員: discord.Member | None = None):
        """
        查看活躍度指令
        
        Args:
            inter: Discord 互動
            成員: 要查詢的成員，預設為指令執行者
        """
        await inter.response.defer()
        member = 成員 or inter.user
        
        if not isinstance(member, discord.Member):
            await inter.followup.send("❌ 只能查詢伺服器成員的活躍度。")
            return
        
        with error_handler.handle_error(inter, "查詢活躍度失敗", ErrorCodes.MODULE_ERROR[0]):
            # 獲取活躍度資料
            score, last_msg = await self.db.get_user_activity(
                getattr(inter.guild, 'id', 0), 
                getattr(member, 'id', 0)
            )
            
            # 計算衰減後的活躍度
            current_score = self.calculator.decay(score, int(time.time()) - last_msg)
            
            # 生成並發送進度條圖片
            activity_bar = self.renderer.render_progress_bar(
                getattr(member, 'display_name', '未知用戶'), 
                current_score
            )
            await inter.followup.send(file=activity_bar)
    
    @app_commands.command(name="今日排行榜", description="查看今日訊息數排行榜")
    async def daily_ranking(self, inter: discord.Interaction, 名次: int = 10):
        """
        查看今日排行榜指令
        
        Args:
            inter: Discord 互動
            名次: 顯示的排名數量
        """
        await inter.response.defer()
        
        with error_handler.handle_error(inter, "查詢排行榜失敗", ErrorCodes.MODULE_ERROR[0]):
            # 獲取今日日期
            ymd = datetime.now(timezone.utc).astimezone(config.TW_TZ).strftime(config.DAY_FMT)
            
            # 獲取排行榜資料
            rankings = await self.db.get_daily_rankings(
                ymd, 
                getattr(inter.guild, 'id', 0), 
                limit=名次
            )
            
            if not rankings:
                await inter.followup.send("今天還沒有人說話！")
                return
            
            # 獲取月度統計
            ym = datetime.now(config.TW_TZ).strftime(config.MONTH_FMT)
            monthly_stats = await self.db.get_monthly_stats(
                ym, 
                getattr(inter.guild, 'id', 0)
            )
            
            days = int(datetime.now(config.TW_TZ).strftime("%d"))
            
            # 生成排行榜
            lines = []
            for rank, data in enumerate(rankings, 1):
                user_id = data["user_id"]
                msg_cnt = data["msg_cnt"]
                
                mavg = monthly_stats.get(user_id, 0) / days if days else 0
                member = inter.guild.get_member(user_id) if inter.guild else None
                name = member.display_name if member else f"<@{user_id}>"
                
                lines.append(f"`#{rank:2}` {name:<20} ‧ 今日 {msg_cnt} 則 ‧ 月均 {mavg:.1f}")
            
            # 創建嵌入
            embed = discord.Embed(
                title=f"📈 今日活躍排行榜 - {getattr(inter.guild, 'name', '未知伺服器')}",
                description="\n".join(lines),
                colour=discord.Colour.green()
            )
            
            await inter.followup.send(embed=embed)
    
    @app_commands.command(name="設定排行榜頻道", description="設定每日自動播報排行榜的頻道")
    @app_commands.describe(頻道="要播報到哪個文字頻道")
    async def set_report_channel(self, inter: discord.Interaction, 頻道: discord.TextChannel):
        """
        設定排行榜頻道指令
        
        Args:
            inter: Discord 互動
            頻道: 要設定的頻道
        """
        if not config.is_allowed(inter, "設定排行榜頻道"):
            await inter.response.send_message("❌ 你沒有權限執行本指令。")
            return
        
        with error_handler.handle_error(inter, "設定排行榜頻道失敗", ErrorCodes.MODULE_ERROR[0]):
            await self.db.set_report_channel(
                getattr(inter.guild, 'id', 0), 
                頻道.id
            )
            await inter.response.send_message(f"✅ 已設定為 {頻道.mention}")
    
    @app_commands.command(name="活躍度面板", description="開啟活躍度系統設定面板")
    async def activity_panel(self, interaction: discord.Interaction):
        """
        活躍度面板指令
        
        Args:
            interaction: Discord 互動
        """
        # 權限檢查
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ 此指令只能在伺服器中使用",
                ephemeral=True
            )
            return
            
        if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ 需要「管理伺服器」權限才能使用此指令",
                ephemeral=True
            )
            return
        
        try:
            # 導入面板視圖
            from ..panel.main_view import ActivityPanelView
            
            # 創建面板視圖
            view = ActivityPanelView(self.bot, interaction.guild.id, interaction.user.id)
            
            # 啟動面板
            await view.start(interaction)
            
        except Exception as exc:
            # 如果面板載入失敗，使用簡單的 Embed
            embed = discord.Embed(
                title="📊 活躍度系統",
                description="管理活躍度系統設定和統計資訊",
                color=discord.Color.blue()
            )
            
            # 獲取基本統計
            try:
                report_channels = await self.db.get_report_channels()
                channel_id = next((ch_id for g_id, ch_id in report_channels if g_id == interaction.guild.id), None)
                
                if channel_id:
                    channel = interaction.guild.get_channel(channel_id)
                    embed.add_field(
                        name="📢 播報頻道",
                        value=channel.mention if channel else "頻道已刪除",
                        inline=True
                    )
                else:
                    embed.add_field(
                        name="📢 播報頻道",
                        value="未設定",
                        inline=True
                    )
                    
            except Exception:
                embed.add_field(
                    name="📢 播報頻道",
                    value="無法載入",
                    inline=True
                )
            
            embed.set_footer(text=f"面板載入失敗: {exc}")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # -------- 事件 --------
    @commands.Cog.listener("on_message")
    async def on_message(self, msg: discord.Message):
        """
        訊息事件處理
        
        Args:
            msg: Discord 訊息
        """
        # 忽略機器人和私訊
        if msg.author.bot or not msg.guild:
            return
        
        now = int(time.time())
        ymd = datetime.now(timezone.utc).astimezone(config.TW_TZ).strftime(config.DAY_FMT)
        
        # 使用鎖確保資料一致性
        async with self.lock:
            try:
                # 獲取當前活躍度
                score, last_msg = await self.db.get_user_activity(
                    getattr(msg.guild, 'id', 0), 
                    getattr(msg.author, 'id', 0)
                )
                
                # 檢查是否需要更新活躍度（冷卻時間）
                if not self.calculator.should_update(last_msg, now):
                    # 只增加訊息計數，不更新活躍度
                    await self.db.increment_daily_message_count(
                        ymd, 
                        getattr(msg.guild, 'id', 0), 
                        getattr(msg.author, 'id', 0)
                    )
                    return
                
                # 計算新的活躍度分數
                new_score = self.calculator.calculate_new_score(score, last_msg, now)
                
                # 更新活躍度
                await self.db.update_user_activity(
                    getattr(msg.guild, 'id', 0), 
                    getattr(msg.author, 'id', 0), 
                    new_score, 
                    now
                )
                
                # 更新訊息計數
                await self.db.increment_daily_message_count(
                    ymd, 
                    getattr(msg.guild, 'id', 0), 
                    getattr(msg.author, 'id', 0)
                )
            
            except Exception as e:
                logger.error(f"【活躍度】處理訊息時發生錯誤: {e}") 