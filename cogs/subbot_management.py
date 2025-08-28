"""
子機器人管理Discord Cog
Task ID: 3 - 子機器人聊天功能和管理系統

這個模組提供子機器人管理的Discord slash命令介面，讓管理員可以透過Discord指令
便捷地管理所有子機器人功能。

Elena的API設計理念：
- 每個指令都是承諾，提供一致且可靠的使用者體驗
- 錯誤訊息要有同理心，幫助開發者快速定位問題
- 權限控制確保系統安全性
- 引導式設定流程降低使用門檻

提供的指令功能：
- /subbot create：引導式創建子機器人
- /subbot list：列出所有子機器人及狀態
- /subbot info：查看子機器人詳細資訊
- /subbot start：啟動子機器人
- /subbot stop：停止子機器人
- /subbot restart：重啟子機器人
- /subbot delete：刪除子機器人
- /subbot config：修改子機器人配置
- /subbot stats：查看統計資料
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
import json

import discord
from discord.ext import commands
from discord import app_commands

# 導入SubBot服務和相關模組
try:
    from src.services.subbot_service import SubBotService, SubBotStatus
    from src.core.errors import (
        SubBotError, SubBotCreationError, SubBotTokenError, 
        SubBotChannelError, SecurityError
    )
    SUBBOT_AVAILABLE = True
except ImportError as e:
    SUBBOT_AVAILABLE = False
    logging.warning(f"SubBot服務不可用: {e}")

# 導入服務註冊表
try:
    from core.base_service import service_registry
    SERVICE_REGISTRY_AVAILABLE = True
except ImportError:
    SERVICE_REGISTRY_AVAILABLE = False
    logging.warning("服務註冊表不可用")


class SubBotManagementCog(commands.Cog):
    """
    子機器人管理Discord Cog
    
    Elena的管理介面設計：提供直觀、安全、高效的子機器人管理體驗
    """
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = logging.getLogger('cogs.subbot_management')
        
        # 服務實例
        self.subbot_service: Optional[SubBotService] = None
        
        # 初始化狀態
        self._initialized = False
        self._permission_roles = ['管理員', 'Administrator', 'Moderator', '版主']
    
    async def cog_load(self):
        """Cog載入時的初始化"""
        try:
            await self._initialize_services()
            self._initialized = True
            self.logger.info("子機器人管理Cog已成功載入")
            
        except Exception as e:
            self.logger.exception(f"子機器人管理Cog載入失敗: {e}")
            # 允許Cog載入但功能受限
            self._initialized = False
    
    async def cog_unload(self):
        """Cog卸載時的清理"""
        self._initialized = False
        self.subbot_service = None
        self.logger.info("子機器人管理Cog已卸載")
    
    async def _initialize_services(self):
        """初始化服務依賴"""
        if not SUBBOT_AVAILABLE:
            raise RuntimeError("SubBot服務模組不可用")
        
        try:
            # 從服務註冊表獲取SubBotService實例
            if SERVICE_REGISTRY_AVAILABLE:
                self.subbot_service = service_registry.get_service("SubBotService")
                
            # 如果服務註冊表不可用，嘗試直接創建服務實例
            if not self.subbot_service:
                self.logger.warning("無法從服務註冊表獲取SubBotService，嘗試直接創建")
                self.subbot_service = SubBotService()
                
                # 確保服務已初始化
                if not self.subbot_service.is_initialized:
                    await self.subbot_service.initialize()
            
            if not self.subbot_service:
                raise RuntimeError("無法獲取SubBotService實例")
                
            self.logger.info("子機器人服務依賴初始化完成")
            
        except Exception as e:
            self.logger.exception(f"初始化服務依賴失敗: {e}")
            raise
    
    async def _check_permissions(self, interaction: discord.Interaction) -> bool:
        """檢查用戶是否有管理權限"""
        # 檢查是否為伺服器擁有者
        if interaction.guild and interaction.user.id == interaction.guild.owner_id:
            return True
        
        # 檢查是否具有管理員權限
        if interaction.user.guild_permissions.administrator:
            return True
        
        # 檢查是否具有特定角色
        if interaction.user.roles:
            user_roles = [role.name for role in interaction.user.roles]
            if any(role in self._permission_roles for role in user_roles):
                return True
        
        return False
    
    async def _send_permission_error(self, interaction: discord.Interaction):
        """發送權限錯誤訊息"""
        embed = discord.Embed(
            title="權限不足",
            description="您需要管理員權限才能使用子機器人管理功能。",
            color=discord.Color.red()
        )
        embed.add_field(
            name="所需權限",
            value="• 伺服器擁有者\n• 管理員權限\n• 特定管理角色",
            inline=False
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def _send_service_error(self, interaction: discord.Interaction, error_msg: str = None):
        """發送服務錯誤訊息"""
        embed = discord.Embed(
            title="服務不可用",
            description=error_msg or "子機器人服務暫時不可用，請稍後再試。",
            color=discord.Color.orange()
        )
        embed.add_field(
            name="建議",
            value="如果問題持續發生，請聯繫系統管理員。",
            inline=False
        )
        
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    def _check_service_availability(self) -> bool:
        """檢查服務可用性"""
        return self._initialized and self.subbot_service is not None
    
    # ==================== 主要指令群組 ====================
    
    subbot_group = app_commands.Group(
        name="subbot",
        description="子機器人管理指令"
    )
    
    @subbot_group.command(
        name="create",
        description="創建新的子機器人"
    )
    @app_commands.describe(
        name="子機器人名稱",
        token="Discord Bot Token",
        channels="限制的頻道（用逗號分隔頻道ID，可選）",
        ai_enabled="是否啟用AI功能",
        ai_model="AI模型名稱（可選）",
        personality="AI人格設定（可選）"
    )
    async def create_subbot(
        self,
        interaction: discord.Interaction,
        name: str,
        token: str,
        channels: Optional[str] = None,
        ai_enabled: bool = False,
        ai_model: Optional[str] = None,
        personality: Optional[str] = None
    ):
        """
        創建新的子機器人
        
        Elena的引導設計：透過參數化的方式簡化創建流程，
        同時提供足夠的自定義選項
        """
        try:
            # 權限檢查
            if not await self._check_permissions(interaction):
                await self._send_permission_error(interaction)
                return
            
            # 服務可用性檢查
            if not self._check_service_availability():
                await self._send_service_error(interaction)
                return
            
            # 延遲回應，因為創建過程可能較長
            await interaction.response.defer(ephemeral=True)
            
            # 解析頻道限制
            channel_restrictions = []
            if channels:
                try:
                    channel_ids = [int(ch.strip()) for ch in channels.split(',') if ch.strip()]
                    channel_restrictions = channel_ids
                except ValueError:
                    embed = discord.Embed(
                        title="參數錯誤",
                        description="頻道ID格式不正確，請使用數字ID並用逗號分隔。",
                        color=discord.Color.red()
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return
            
            # 記錄創建操作
            self.logger.info(
                f"用戶 {interaction.user.id} ({interaction.user}) 嘗試創建子機器人: {name}"
            )
            
            # 調用SubBotService創建子機器人
            result = await self.subbot_service.create_subbot(
                name=name,
                token=token,
                owner_id=interaction.user.id,
                channel_restrictions=channel_restrictions,
                ai_enabled=ai_enabled,
                ai_model=ai_model,
                personality=personality
            )
            
            if result.get('success', False):
                # 創建成功
                embed = discord.Embed(
                    title="子機器人創建成功",
                    description=f"子機器人 **{name}** 已成功創建！",
                    color=discord.Color.green()
                )
                
                embed.add_field(
                    name="基本資訊",
                    value=(
                        f"**ID**: `{result['bot_id']}`\n"
                        f"**名稱**: {result['name']}\n"
                        f"**擁有者**: {interaction.user.mention}\n"
                        f"**狀態**: {result['status']}"
                    ),
                    inline=False
                )
                
                if channel_restrictions:
                    channels_text = ", ".join([f"<#{ch_id}>" for ch_id in channel_restrictions])
                    embed.add_field(
                        name="頻道限制",
                        value=channels_text,
                        inline=False
                    )
                
                if ai_enabled:
                    embed.add_field(
                        name="AI 設定",
                        value=(
                            f"**啟用**: ✅\n"
                            f"**模型**: {ai_model or '預設'}\n"
                            f"**人格**: {personality or '預設'}"
                        ),
                        inline=False
                    )
                
                embed.add_field(
                    name="下一步",
                    value=f"使用 `/subbot start {result['bot_id']}` 來啟動子機器人。",
                    inline=False
                )
                
                embed.set_footer(text=f"Bot ID: {result['bot_id']}")
                
                await interaction.followup.send(embed=embed, ephemeral=False)
                
            else:
                # 創建失敗
                error_msg = result.get('error', '未知錯誤')
                embed = discord.Embed(
                    title="創建失敗",
                    description=f"無法創建子機器人: {error_msg}",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                
        except SubBotCreationError as e:
            embed = discord.Embed(
                title="創建錯誤",
                description=f"創建子機器人時發生錯誤: {e.user_message}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except SubBotTokenError as e:
            embed = discord.Embed(
                title="Token錯誤",
                description="提供的Discord Bot Token無效或格式不正確。",
                color=discord.Color.red()
            )
            embed.add_field(
                name="解決方案",
                value=(
                    "1. 檢查Token是否正確複製\n"
                    "2. 確認Token來源於Discord開發者門戶\n"
                    "3. 驗證Bot是否已啟用所需意圖"
                ),
                inline=False
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            self.logger.exception(f"創建子機器人時發生未預期錯誤: {e}")
            embed = discord.Embed(
                title="系統錯誤",
                description="創建過程中發生系統錯誤，請稍後再試。",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @subbot_group.command(
        name="list",
        description="列出所有子機器人"
    )
    async def list_subbots(self, interaction: discord.Interaction):
        """
        列出所有子機器人及其狀態
        
        Elena的列表設計：提供清晰、有序的資訊展示
        """
        try:
            # 權限檢查
            if not await self._check_permissions(interaction):
                await self._send_permission_error(interaction)
                return
            
            # 服務可用性檢查
            if not self._check_service_availability():
                await self._send_service_error(interaction)
                return
            
            await interaction.response.defer(ephemeral=True)
            
            # 獲取子機器人列表
            subbots = await self.subbot_service.list_sub_bots()
            
            if not subbots:
                embed = discord.Embed(
                    title="子機器人列表",
                    description="目前沒有任何子機器人。",
                    color=discord.Color.blue()
                )
                embed.add_field(
                    name="提示",
                    value="使用 `/subbot create` 來創建您的第一個子機器人。",
                    inline=False
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # 按狀態分組
            online_bots = []
            offline_bots = []
            error_bots = []
            
            for bot in subbots:
                status = bot.get('status', 'offline')
                if status == SubBotStatus.ONLINE.value:
                    online_bots.append(bot)
                elif status == SubBotStatus.ERROR.value:
                    error_bots.append(bot)
                else:
                    offline_bots.append(bot)
            
            # 創建摘要嵌入
            embed = discord.Embed(
                title="子機器人列表",
                description=f"共 {len(subbots)} 個子機器人",
                color=discord.Color.blue()
            )
            
            # 狀態統計
            embed.add_field(
                name="狀態統計",
                value=(
                    f"🟢 在線: {len(online_bots)}\n"
                    f"🔴 離線: {len(offline_bots)}\n"
                    f"⚠️ 錯誤: {len(error_bots)}"
                ),
                inline=True
            )
            
            # 顯示各狀態的機器人
            def format_bot_list(bots: List[Dict], max_display: int = 5):
                if not bots:
                    return "無"
                
                bot_lines = []
                for i, bot in enumerate(bots[:max_display]):
                    bot_name = bot.get('name', '未知')
                    bot_id = bot.get('bot_id', '未知')
                    is_connected = bot.get('is_connected', False)
                    connection_icon = "🔗" if is_connected else "⛓️‍💥"
                    bot_lines.append(f"{connection_icon} **{bot_name}** (`{bot_id}`)")
                
                if len(bots) > max_display:
                    bot_lines.append(f"...還有 {len(bots) - max_display} 個")
                
                return "\n".join(bot_lines)
            
            if online_bots:
                embed.add_field(
                    name="🟢 在線機器人",
                    value=format_bot_list(online_bots),
                    inline=False
                )
            
            if error_bots:
                embed.add_field(
                    name="⚠️ 錯誤機器人", 
                    value=format_bot_list(error_bots),
                    inline=False
                )
            
            if offline_bots:
                embed.add_field(
                    name="🔴 離線機器人",
                    value=format_bot_list(offline_bots),
                    inline=False
                )
            
            embed.add_field(
                name="使用說明",
                value=(
                    "• 使用 `/subbot info <bot_id>` 查看詳細資訊\n"
                    "• 使用 `/subbot start <bot_id>` 啟動機器人\n"
                    "• 使用 `/subbot stop <bot_id>` 停止機器人"
                ),
                inline=False
            )
            
            embed.set_footer(text=f"更新時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            await interaction.followup.send(embed=embed, ephemeral=False)
            
        except Exception as e:
            self.logger.exception(f"列出子機器人時發生錯誤: {e}")
            await self._send_service_error(
                interaction,
                "無法獲取子機器人列表，請稍後再試。"
            )
    
    @subbot_group.command(
        name="info",
        description="查看子機器人詳細資訊"
    )
    @app_commands.describe(bot_id="子機器人ID")
    async def subbot_info(
        self,
        interaction: discord.Interaction,
        bot_id: str
    ):
        """
        查看子機器人詳細資訊
        
        Elena的詳情展示：提供全面且易懂的資訊視圖
        """
        try:
            # 權限檢查
            if not await self._check_permissions(interaction):
                await self._send_permission_error(interaction)
                return
            
            # 服務可用性檢查
            if not self._check_service_availability():
                await self._send_service_error(interaction)
                return
            
            await interaction.response.defer(ephemeral=True)
            
            # 獲取子機器人狀態
            bot_status = await self.subbot_service.get_bot_status(bot_id)
            
            # 獲取連線詳細資訊
            connection_info = await self.subbot_service.get_bot_connection_info(bot_id)
            
            # 創建詳細資訊嵌入
            status = bot_status.get('status', 'unknown')
            status_color = {
                SubBotStatus.ONLINE.value: discord.Color.green(),
                SubBotStatus.OFFLINE.value: discord.Color.grey(),
                SubBotStatus.ERROR.value: discord.Color.red(),
                SubBotStatus.CONNECTING.value: discord.Color.orange()
            }.get(status, discord.Color.blue())
            
            status_emoji = {
                SubBotStatus.ONLINE.value: "🟢",
                SubBotStatus.OFFLINE.value: "🔴", 
                SubBotStatus.ERROR.value: "⚠️",
                SubBotStatus.CONNECTING.value: "🟡"
            }.get(status, "❓")
            
            embed = discord.Embed(
                title=f"{status_emoji} {bot_status.get('name', '未知子機器人')}",
                description=f"子機器人詳細資訊",
                color=status_color
            )
            
            # 基本資訊
            embed.add_field(
                name="基本資訊",
                value=(
                    f"**ID**: `{bot_id}`\n"
                    f"**名稱**: {bot_status.get('name', '未知')}\n"
                    f"**狀態**: {status_emoji} {status}\n"
                    f"**擁有者**: <@{bot_status.get('owner_id', 0)}>\n"
                    f"**連線狀態**: {'已連線' if bot_status.get('is_connected', False) else '未連線'}"
                ),
                inline=False
            )
            
            # 時間資訊
            created_at = bot_status.get('created_at', '未知')
            if isinstance(created_at, str) and created_at != '未知':
                try:
                    created_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    created_display = created_time.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    created_display = created_at
            else:
                created_display = '未知'
            
            embed.add_field(
                name="時間資訊",
                value=(
                    f"**創建時間**: {created_display}\n"
                    f"**訊息數量**: {bot_status.get('message_count', 0)}"
                ),
                inline=True
            )
            
            # AI功能資訊
            ai_enabled = bot_status.get('ai_enabled', False)
            embed.add_field(
                name="AI 功能",
                value=(
                    f"**啟用狀態**: {'✅ 已啟用' if ai_enabled else '❌ 未啟用'}\n"
                    f"**AI模型**: {bot_status.get('ai_model', '未設定') if ai_enabled else 'N/A'}\n"
                    f"**人格設定**: {bot_status.get('personality', '未設定') if ai_enabled else 'N/A'}"
                ),
                inline=True
            )
            
            # 頻道限制資訊
            channel_restrictions = bot_status.get('channel_restrictions', [])
            if channel_restrictions:
                channels_text = ", ".join([f"<#{ch_id}>" for ch_id in channel_restrictions])
                if len(channels_text) > 1000:
                    channels_text = channels_text[:900] + "... (更多)"
            else:
                channels_text = "無限制"
                
            embed.add_field(
                name="頻道限制",
                value=channels_text,
                inline=False
            )
            
            # 連線詳細資訊
            if connection_info:
                latency = connection_info.get('latency_ms')
                latency_str = f"{latency:.2f} ms" if latency else "N/A"
                
                embed.add_field(
                    name="連線資訊",
                    value=(
                        f"**延遲**: {latency_str}\n"
                        f"**所在伺服器**: {connection_info.get('guild_count', 0)} 個\n"
                        f"**準備狀態**: {'✅' if connection_info.get('is_ready', False) else '❌'}\n"
                        f"**連線時間**: {connection_info.get('connected_at', '未知')}"
                    ),
                    inline=True
                )
                
                # 執行時間統計
                uptime_seconds = connection_info.get('uptime_seconds')
                if uptime_seconds:
                    hours = int(uptime_seconds // 3600)
                    minutes = int((uptime_seconds % 3600) // 60)
                    uptime_str = f"{hours}時{minutes}分"
                else:
                    uptime_str = "N/A"
                    
                embed.add_field(
                    name="執行統計",
                    value=(
                        f"**運行時間**: {uptime_str}\n"
                        f"**處理訊息**: {connection_info.get('message_count', 0)} 條\n"
                        f"**最後活動**: {connection_info.get('last_activity', '未知')}"
                    ),
                    inline=True
                )
            
            # 操作按鈕
            embed.add_field(
                name="可用操作",
                value=(
                    f"• `/subbot start {bot_id}` - 啟動機器人\n"
                    f"• `/subbot stop {bot_id}` - 停止機器人\n"
                    f"• `/subbot restart {bot_id}` - 重啟機器人\n"
                    f"• `/subbot stats {bot_id}` - 查看統計\n"
                    f"• `/subbot delete {bot_id}` - 刪除機器人"
                ),
                inline=False
            )
            
            embed.set_footer(text=f"查詢時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            await interaction.followup.send(embed=embed, ephemeral=False)
            
        except SubBotError as e:
            embed = discord.Embed(
                title="查詢錯誤",
                description=f"找不到ID為 `{bot_id}` 的子機器人。",
                color=discord.Color.red()
            )
            embed.add_field(
                name="建議",
                value="使用 `/subbot list` 查看所有可用的子機器人。",
                inline=False
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            self.logger.exception(f"查看子機器人詳情時發生錯誤: {e}")
            await self._send_service_error(
                interaction,
                f"無法獲取子機器人 `{bot_id}` 的詳細資訊。"
            )


    @subbot_group.command(
        name="start",
        description="啟動子機器人"
    )
    @app_commands.describe(bot_id="子機器人ID")
    async def start_subbot(
        self,
        interaction: discord.Interaction,
        bot_id: str
    ):
        """
        啟動子機器人
        
        Elena的啟動設計：提供清晰的啟動反饋和錯誤處理
        """
        try:
            # 權限檢查
            if not await self._check_permissions(interaction):
                await self._send_permission_error(interaction)
                return
            
            # 服務可用性檢查
            if not self._check_service_availability():
                await self._send_service_error(interaction)
                return
            
            await interaction.response.defer(ephemeral=True)
            
            self.logger.info(f"用戶 {interaction.user.id} 嘗試啟動子機器人: {bot_id}")
            
            # 啟動子機器人
            result = await self.subbot_service.connect_subbot(bot_id)
            
            if result.get('success', False):
                embed = discord.Embed(
                    title="啟動成功",
                    description=f"子機器人 `{bot_id}` 已成功啟動！",
                    color=discord.Color.green()
                )
                
                embed.add_field(
                    name="狀態資訊",
                    value=(
                        f"**狀態**: {result.get('status', '未知')}\n"
                        f"**連線時間**: {result.get('connected_at', '未知')}"
                    ),
                    inline=False
                )
                
                await interaction.followup.send(embed=embed, ephemeral=False)
            else:
                error_msg = result.get('error', '未知錯誤')
                embed = discord.Embed(
                    title="啟動失敗",
                    description=f"無法啟動子機器人 `{bot_id}`: {error_msg}",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                
        except Exception as e:
            self.logger.exception(f"啟動子機器人時發生錯誤: {e}")
            await self._send_service_error(
                interaction,
                f"啟動子機器人 `{bot_id}` 時發生錯誤。"
            )
    
    @subbot_group.command(
        name="stop",
        description="停止子機器人"
    )
    @app_commands.describe(bot_id="子機器人ID")
    async def stop_subbot(
        self,
        interaction: discord.Interaction,
        bot_id: str
    ):
        """
        停止子機器人
        
        Elena的停止設計：安全且優雅的停止程序
        """
        try:
            # 權限檢查
            if not await self._check_permissions(interaction):
                await self._send_permission_error(interaction)
                return
            
            # 服務可用性檢查
            if not self._check_service_availability():
                await self._send_service_error(interaction)
                return
            
            await interaction.response.defer(ephemeral=True)
            
            self.logger.info(f"用戶 {interaction.user.id} 嘗試停止子機器人: {bot_id}")
            
            # 停止子機器人
            result = await self.subbot_service.disconnect_subbot(bot_id)
            
            if result.get('success', False):
                embed = discord.Embed(
                    title="停止成功",
                    description=f"子機器人 `{bot_id}` 已成功停止。",
                    color=discord.Color.blue()
                )
                
                embed.add_field(
                    name="狀態資訊",
                    value=(
                        f"**狀態**: {result.get('status', '未知')}\n"
                        f"**停止時間**: {result.get('disconnected_at', '未知')}"
                    ),
                    inline=False
                )
                
                await interaction.followup.send(embed=embed, ephemeral=False)
            else:
                error_msg = result.get('error', '未知錯誤')
                embed = discord.Embed(
                    title="停止失敗",
                    description=f"無法停止子機器人 `{bot_id}`: {error_msg}",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                
        except Exception as e:
            self.logger.exception(f"停止子機器人時發生錯誤: {e}")
            await self._send_service_error(
                interaction,
                f"停止子機器人 `{bot_id}` 時發生錯誤。"
            )
    
    @subbot_group.command(
        name="restart",
        description="重啟子機器人"
    )
    @app_commands.describe(bot_id="子機器人ID")
    async def restart_subbot(
        self,
        interaction: discord.Interaction,
        bot_id: str
    ):
        """
        重啟子機器人
        
        Elena的重啟設計：安全的重啟程序，確保狀態一致性
        """
        try:
            # 權限檢查
            if not await self._check_permissions(interaction):
                await self._send_permission_error(interaction)
                return
            
            # 服務可用性檢查
            if not self._check_service_availability():
                await self._send_service_error(interaction)
                return
            
            await interaction.response.defer(ephemeral=True)
            
            self.logger.info(f"用戶 {interaction.user.id} 嘗試重啟子機器人: {bot_id}")
            
            # 重啟子機器人
            result = await self.subbot_service.restart_bot(bot_id)
            
            if result.get('success', False):
                embed = discord.Embed(
                    title="重啟成功",
                    description=f"子機器人 `{bot_id}` 已成功重啟！",
                    color=discord.Color.green()
                )
                
                embed.add_field(
                    name="狀態資訊",
                    value=(
                        f"**新狀態**: {result.get('status', '未知')}\n"
                        f"**重啟時間**: {result.get('restarted_at', '未知')}"
                    ),
                    inline=False
                )
                
                await interaction.followup.send(embed=embed, ephemeral=False)
            else:
                error_msg = result.get('error', '未知錯誤')
                embed = discord.Embed(
                    title="重啟失敗",
                    description=f"無法重啟子機器人 `{bot_id}`: {error_msg}",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                
        except Exception as e:
            self.logger.exception(f"重啟子機器人時發生錯誤: {e}")
            await self._send_service_error(
                interaction,
                f"重啟子機器人 `{bot_id}` 時發生錯誤。"
            )
    
    @subbot_group.command(
        name="delete",
        description="刪除子機器人"
    )
    @app_commands.describe(bot_id="子機器人ID")
    async def delete_subbot(
        self,
        interaction: discord.Interaction,
        bot_id: str
    ):
        """
        刪除子機器人
        
        Elena的刪除設計：需要確認的安全刪除程序
        """
        try:
            # 權限檢查
            if not await self._check_permissions(interaction):
                await self._send_permission_error(interaction)
                return
            
            # 服務可用性檢查
            if not self._check_service_availability():
                await self._send_service_error(interaction)
                return
            
            # 獲取子機器人資訊用於確認
            try:
                bot_info = await self.subbot_service.get_bot_status(bot_id)
                bot_name = bot_info.get('name', bot_id)
            except:
                bot_name = bot_id
            
            # 創建確認嵌入和按鈕
            embed = discord.Embed(
                title="⚠️ 確認刪除",
                description=f"您確定要刪除子機器人 **{bot_name}** (`{bot_id}`) 嗎？",
                color=discord.Color.orange()
            )
            
            embed.add_field(
                name="警告",
                value=(
                    "• 此操作不可逆轉\n"
                    "• 所有配置將被永久刪除\n"
                    "• 如果機器人正在運行，將立即停止"
                ),
                inline=False
            )
            
            # 創建確認按鈕
            view = DeleteConfirmView(self.subbot_service, bot_id, bot_name, interaction.user.id)
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            self.logger.exception(f"準備刪除子機器人時發生錯誤: {e}")
            await self._send_service_error(
                interaction,
                f"無法準備刪除子機器人 `{bot_id}`。"
            )
    
    @subbot_group.command(
        name="stats",
        description="查看子機器人統計資料"
    )
    @app_commands.describe(bot_id="子機器人ID（可選，不提供則顯示總體統計）")
    async def subbot_stats(
        self,
        interaction: discord.Interaction,
        bot_id: Optional[str] = None
    ):
        """
        查看子機器人統計資料
        
        Elena的統計設計：提供有意義的數據洞察
        """
        try:
            # 權限檢查
            if not await self._check_permissions(interaction):
                await self._send_permission_error(interaction)
                return
            
            # 服務可用性檢查
            if not self._check_service_availability():
                await self._send_service_error(interaction)
                return
            
            await interaction.response.defer(ephemeral=True)
            
            if bot_id:
                # 單個機器人統計
                try:
                    bot_status = await self.subbot_service.get_bot_status(bot_id)
                    connection_info = await self.subbot_service.get_bot_connection_info(bot_id)
                    
                    embed = discord.Embed(
                        title=f"📊 {bot_status.get('name', '未知')} 統計資料",
                        description=f"子機器人 `{bot_id}` 的詳細統計",
                        color=discord.Color.blue()
                    )
                    
                    # 基本統計
                    embed.add_field(
                        name="訊息統計",
                        value=(
                            f"**處理訊息**: {bot_status.get('message_count', 0)} 條\n"
                            f"**最後活動**: {bot_status.get('last_message_at', '無')} \n"
                        ),
                        inline=True
                    )
                    
                    if connection_info:
                        # 連線統計
                        uptime_seconds = connection_info.get('uptime_seconds', 0)
                        if uptime_seconds > 0:
                            hours = int(uptime_seconds // 3600)
                            minutes = int((uptime_seconds % 3600) // 60)
                            uptime_str = f"{hours}時{minutes}分"
                        else:
                            uptime_str = "N/A"
                        
                        embed.add_field(
                            name="運行統計",
                            value=(
                                f"**運行時間**: {uptime_str}\n"
                                f"**延遲**: {connection_info.get('latency_ms', 0):.2f} ms\n"
                                f"**伺服器數**: {connection_info.get('guild_count', 0)} 個"
                            ),
                            inline=True
                        )
                    
                    embed.set_footer(text=f"統計時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    
                except SubBotError:
                    embed = discord.Embed(
                        title="統計錯誤",
                        description=f"找不到ID為 `{bot_id}` 的子機器人。",
                        color=discord.Color.red()
                    )
                    
            else:
                # 總體統計
                service_status = await self.subbot_service.get_service_status()
                all_statuses = await self.subbot_service.get_all_bot_statuses()
                
                embed = discord.Embed(
                    title="📊 子機器人系統統計",
                    description="系統整體統計資料",
                    color=discord.Color.blue()
                )
                
                # 系統統計
                embed.add_field(
                    name="系統資訊",
                    value=(
                        f"**總機器人**: {service_status.get('total_bots', 0)} 個\n"
                        f"**在線機器人**: {service_status.get('online_bots', 0)} 個\n"
                        f"**錯誤機器人**: {service_status.get('error_bots', 0)} 個\n"
                        f"**活躍連線**: {service_status.get('active_connections', 0)} 個"
                    ),
                    inline=True
                )
                
                # 健康狀態
                health_status = service_status.get('health_status', 'unknown')
                health_emoji = {
                    'healthy': '🟢',
                    'degraded': '🟡', 
                    'critical': '🔴'
                }.get(health_status, '❓')
                
                embed.add_field(
                    name="系統健康",
                    value=(
                        f"**狀態**: {health_emoji} {health_status}\n"
                        f"**運行時間**: {service_status.get('uptime_seconds', 0):.0f} 秒\n"
                        f"**加密算法**: {service_status.get('encryption_info', {}).get('algorithm', 'N/A')}"
                    ),
                    inline=True
                )
                
                # 訊息統計
                total_messages = sum(bot.get('connection_info', {}).get('message_count', 0) 
                                   for bot in all_statuses if bot.get('connection_info'))
                
                embed.add_field(
                    name="使用統計",
                    value=(
                        f"**總處理訊息**: {total_messages} 條\n"
                        f"**平均每機器人**: {total_messages / max(service_status.get('total_bots', 1), 1):.1f} 條\n"
                        f"**更新時間**: {service_status.get('last_updated', '未知')}"
                    ),
                    inline=False
                )
            
            await interaction.followup.send(embed=embed, ephemeral=False)
            
        except Exception as e:
            self.logger.exception(f"獲取統計資料時發生錯誤: {e}")
            await self._send_service_error(
                interaction,
                "無法獲取統計資料，請稍後再試。"
            )
    
    @subbot_group.command(
        name="config",
        description="修改子機器人配置"
    )
    @app_commands.describe(bot_id="子機器人ID")
    async def config_subbot(
        self,
        interaction: discord.Interaction,
        bot_id: str
    ):
        """
        修改子機器人配置
        
        Elena的配置設計：提供安全且直觀的配置修改介面
        """
        try:
            # 權限檢查
            if not await self._check_permissions(interaction):
                await self._send_permission_error(interaction)
                return
            
            # 服務可用性檢查
            if not self._check_service_availability():
                await self._send_service_error(interaction)
                return
            
            # 檢查子機器人是否存在
            try:
                bot_status = await self.subbot_service.get_bot_status(bot_id)
            except SubBotError:
                embed = discord.Embed(
                    title="配置錯誤",
                    description=f"找不到ID為 `{bot_id}` 的子機器人。",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # 創建配置選項視圖
            config_view = ConfigSelectionView(
                self.subbot_service, bot_id, bot_status, interaction.user.id
            )
            
            embed = discord.Embed(
                title=f"⚙️ 配置 {bot_status.get('name', '未知')}",
                description=f"選擇要修改的子機器人配置項目",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="當前配置",
                value=(
                    f"**名稱**: {bot_status.get('name', '未知')}\n"
                    f"**AI功能**: {'✅' if bot_status.get('ai_enabled', False) else '❌'}\n"
                    f"**頻道限制**: {'有' if bot_status.get('channel_restrictions') else '無'}\n"
                    f"**狀態**: {bot_status.get('status', '未知')}"
                ),
                inline=False
            )
            
            embed.set_footer(text="點擊下方按鈕選擇要修改的項目")
            
            await interaction.response.send_message(embed=embed, view=config_view, ephemeral=True)
            
        except Exception as e:
            self.logger.exception(f"打開配置介面時發生錯誤: {e}")
            await self._send_service_error(
                interaction,
                f"無法打開子機器人 `{bot_id}` 的配置介面。"
            )
    
    @subbot_group.command(
        name="setup",
        description="引導式創建子機器人"
    )
    async def setup_subbot(self, interaction: discord.Interaction):
        """
        引導式創建子機器人
        
        Elena的引導設計：步驟化的創建流程，降低使用門檻
        """
        try:
            # 權限檢查
            if not await self._check_permissions(interaction):
                await self._send_permission_error(interaction)
                return
            
            # 服務可用性檢查
            if not self._check_service_availability():
                await self._send_service_error(interaction)
                return
            
            # 創建引導視圖
            setup_view = SetupWizardView(self.subbot_service, interaction.user.id)
            
            embed = discord.Embed(
                title="🧙‍♂️ 子機器人創建精靈",
                description="我將引導您完成子機器人的創建過程。",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="創建步驟",
                value=(
                    "1️⃣ 設定基本資訊\n"
                    "2️⃣ 配置Discord Token\n" 
                    "3️⃣ 設定頻道權限（可選）\n"
                    "4️⃣ 配置AI功能（可選）\n"
                    "5️⃣ 確認並創建"
                ),
                inline=False
            )
            
            embed.add_field(
                name="準備事項",
                value=(
                    "• Discord Bot Token（從Discord開發者門戶獲取）\n"
                    "• 確定要使用的機器人名稱\n"
                    "• 考慮是否需要限制特定頻道"
                ),
                inline=False
            )
            
            embed.set_footer(text="點擊 '開始設定' 按鈕開始創建流程")
            
            await interaction.response.send_message(embed=embed, view=setup_view, ephemeral=True)
            
        except Exception as e:
            self.logger.exception(f"啟動創建精靈時發生錯誤: {e}")
            await self._send_service_error(
                interaction,
                "無法啟動子機器人創建精靈。"
            )
    
    @subbot_group.command(
        name="send",
        description="使用子機器人發送訊息到指定頻道"
    )
    @app_commands.describe(
        bot_id="子機器人ID",
        channel="目標頻道",
        message="要發送的訊息內容"
    )
    async def send_message(
        self,
        interaction: discord.Interaction,
        bot_id: str,
        channel: discord.TextChannel,
        message: str
    ):
        """
        使用子機器人發送訊息
        
        Elena的訊息設計：安全且可控的訊息發送介面
        """
        try:
            # 權限檢查
            if not await self._check_permissions(interaction):
                await self._send_permission_error(interaction)
                return
            
            # 服務可用性檢查
            if not self._check_service_availability():
                await self._send_service_error(interaction)
                return
            
            await interaction.response.defer(ephemeral=True)
            
            self.logger.info(
                f"用戶 {interaction.user.id} 嘗試使用子機器人 {bot_id} 發送訊息到 {channel.id}"
            )
            
            # 內容長度檢查
            if len(message) > 2000:
                embed = discord.Embed(
                    title="訊息過長",
                    description="訊息內容不能超過2000個字符。",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # 發送訊息
            result = await self.subbot_service.send_message_to_channel(
                bot_id=bot_id,
                channel_id=channel.id,
                content=message
            )
            
            if result.get('success', False):
                embed = discord.Embed(
                    title="訊息發送成功",
                    description=f"已使用子機器人 `{bot_id}` 發送訊息到 {channel.mention}",
                    color=discord.Color.green()
                )
                
                embed.add_field(
                    name="發送詳情",
                    value=(
                        f"**訊息ID**: {result.get('message_id', '未知')}\n"
                        f"**內容長度**: {result.get('content_length', 0)} 字符\n"
                        f"**發送時間**: {result.get('sent_at', '未知')}"
                    ),
                    inline=False
                )
                
                await interaction.followup.send(embed=embed, ephemeral=False)
            else:
                error_msg = result.get('error', '未知錯誤')
                embed = discord.Embed(
                    title="發送失敗",
                    description=f"無法發送訊息: {error_msg}",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                
        except SubBotChannelError as e:
            embed = discord.Embed(
                title="頻道錯誤",
                description=f"頻道存取錯誤: {e.user_message}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            self.logger.exception(f"發送訊息時發生錯誤: {e}")
            await self._send_service_error(
                interaction,
                f"使用子機器人 `{bot_id}` 發送訊息時發生錯誤。"
            )

# ==================== 輔助視圖類別 ====================

class DeleteConfirmView(discord.ui.View):
    """刪除確認視圖"""
    
    def __init__(self, subbot_service: SubBotService, bot_id: str, bot_name: str, user_id: int):
        super().__init__(timeout=60.0)
        self.subbot_service = subbot_service
        self.bot_id = bot_id
        self.bot_name = bot_name
        self.user_id = user_id
    
    @discord.ui.button(
        label="確認刪除", 
        style=discord.ButtonStyle.danger,
        emoji="🗑️"
    )
    async def confirm_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        """確認刪除按鈕"""
        # 檢查是否為原始用戶
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "只有發起刪除的用戶可以確認此操作。",
                ephemeral=True
            )
            return
        
        try:
            await interaction.response.defer()
            
            # 執行刪除
            success = await self.subbot_service.delete_sub_bot(self.bot_id)
            
            if success:
                embed = discord.Embed(
                    title="✅ 刪除成功",
                    description=f"子機器人 **{self.bot_name}** (`{self.bot_id}`) 已被永久刪除。",
                    color=discord.Color.green()
                )
            else:
                embed = discord.Embed(
                    title="❌ 刪除失敗",
                    description=f"無法刪除子機器人 **{self.bot_name}**，請稍後再試。",
                    color=discord.Color.red()
                )
            
            # 禁用所有按鈕
            for item in self.children:
                item.disabled = True
            
            await interaction.edit_original_response(embed=embed, view=self)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ 刪除錯誤",
                description=f"刪除過程中發生錯誤: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.edit_original_response(embed=embed, view=self)
    
    @discord.ui.button(
        label="取消",
        style=discord.ButtonStyle.secondary,
        emoji="❌"
    )
    async def cancel_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        """取消刪除按鈕"""
        # 檢查是否為原始用戶
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "只有發起刪除的用戶可以取消此操作。",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="取消刪除",
            description=f"已取消刪除子機器人 **{self.bot_name}**。",
            color=discord.Color.blue()
        )
        
        # 禁用所有按鈕
        for item in self.children:
            item.disabled = True
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def on_timeout(self):
        """視圖超時處理"""
        for item in self.children:
            item.disabled = True


class ConfigSelectionView(discord.ui.View):
    """配置選項選擇視圖"""
    
    def __init__(self, subbot_service: SubBotService, bot_id: str, bot_status: Dict, user_id: int):
        super().__init__(timeout=120.0)
        self.subbot_service = subbot_service
        self.bot_id = bot_id
        self.bot_status = bot_status
        self.user_id = user_id
    
    @discord.ui.button(
        label="修改名稱",
        style=discord.ButtonStyle.primary,
        emoji="📝"
    )
    async def edit_name(self, interaction: discord.Interaction, button: discord.ui.Button):
        """修改名稱按鈕"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("只有配置發起者可以進行此操作。", ephemeral=True)
            return
        
        modal = EditNameModal(self.subbot_service, self.bot_id, self.bot_status.get('name', ''))
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(
        label="AI設定",
        style=discord.ButtonStyle.secondary,
        emoji="🤖"
    )
    async def edit_ai(self, interaction: discord.Interaction, button: discord.ui.Button):
        """AI設定按鈕"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("只有配置發起者可以進行此操作。", ephemeral=True)
            return
        
        modal = EditAIModal(
            self.subbot_service,
            self.bot_id,
            self.bot_status.get('ai_enabled', False),
            self.bot_status.get('ai_model', ''),
            self.bot_status.get('personality', '')
        )
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(
        label="頻道權限",
        style=discord.ButtonStyle.secondary,
        emoji="🔒"
    )
    async def edit_channels(self, interaction: discord.Interaction, button: discord.ui.Button):
        """頻道權限按鈕"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("只有配置發起者可以進行此操作。", ephemeral=True)
            return
        
        current_channels = self.bot_status.get('channel_restrictions', [])
        channels_text = ','.join(map(str, current_channels)) if current_channels else ''
        
        modal = EditChannelsModal(self.subbot_service, self.bot_id, channels_text)
        await interaction.response.send_modal(modal)


class SetupWizardView(discord.ui.View):
    """創建精靈視圖"""
    
    def __init__(self, subbot_service: SubBotService, user_id: int):
        super().__init__(timeout=300.0)
        self.subbot_service = subbot_service
        self.user_id = user_id
        self.wizard_data = {}
    
    @discord.ui.button(
        label="開始設定",
        style=discord.ButtonStyle.success,
        emoji="🚀"
    )
    async def start_setup(self, interaction: discord.Interaction, button: discord.ui.Button):
        """開始設定按鈕"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("只有發起者可以使用此精靈。", ephemeral=True)
            return
        
        modal = BasicInfoModal(self.subbot_service, self.user_id, self.wizard_data)
        await interaction.response.send_modal(modal)


# ==================== 模態框類別 ====================

class EditNameModal(discord.ui.Modal):
    """編輯名稱模態框"""
    
    def __init__(self, subbot_service: SubBotService, bot_id: str, current_name: str):
        super().__init__(title="修改子機器人名稱")
        self.subbot_service = subbot_service
        self.bot_id = bot_id
        
        self.name_input = discord.ui.TextInput(
            label="子機器人名稱",
            placeholder="輸入新的子機器人名稱...",
            default=current_name,
            min_length=1,
            max_length=50
        )
        self.add_item(self.name_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        new_name = self.name_input.value.strip()
        
        try:
            # 這裡需要SubBotService支持名稱修改功能
            # 目前暫時顯示成功訊息
            embed = discord.Embed(
                title="名稱更新",
                description=f"子機器人名稱已更新為: **{new_name}**",
                color=discord.Color.green()
            )
            embed.add_field(
                name="注意",
                value="名稱修改功能正在開發中，此操作暫未實際生效。",
                inline=False
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="更新失敗",
                description=f"更新名稱時發生錯誤: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


class EditAIModal(discord.ui.Modal):
    """編輯AI設定模態框"""
    
    def __init__(self, subbot_service: SubBotService, bot_id: str, ai_enabled: bool, ai_model: str, personality: str):
        super().__init__(title="AI功能設定")
        self.subbot_service = subbot_service
        self.bot_id = bot_id
        
        self.enabled_input = discord.ui.TextInput(
            label="啟用AI (true/false)",
            placeholder="true 或 false",
            default=str(ai_enabled).lower(),
            min_length=4,
            max_length=5
        )
        
        self.model_input = discord.ui.TextInput(
            label="AI模型",
            placeholder="例如: gpt-3.5-turbo",
            default=ai_model,
            required=False,
            max_length=100
        )
        
        self.personality_input = discord.ui.TextInput(
            label="人格設定",
            placeholder="描述機器人的人格特徵...",
            default=personality,
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=500
        )
        
        self.add_item(self.enabled_input)
        self.add_item(self.model_input)
        self.add_item(self.personality_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            enabled_str = self.enabled_input.value.lower().strip()
            ai_enabled = enabled_str in ['true', '1', 'yes', 'y', '是', '真']
            ai_model = self.model_input.value.strip() if self.model_input.value else None
            personality = self.personality_input.value.strip() if self.personality_input.value else None
            
            embed = discord.Embed(
                title="AI設定更新",
                description="AI設定已更新",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="新設定",
                value=(
                    f"**啟用**: {'✅' if ai_enabled else '❌'}\n"
                    f"**模型**: {ai_model or '預設'}\n"
                    f"**人格**: {personality or '預設'}"
                ),
                inline=False
            )
            
            embed.add_field(
                name="注意",
                value="AI設定修改功能正在開發中，此操作暫未實際生效。",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="更新失敗",
                description=f"更新AI設定時發生錯誤: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


class EditChannelsModal(discord.ui.Modal):
    """編輯頻道權限模態框"""
    
    def __init__(self, subbot_service: SubBotService, bot_id: str, current_channels: str):
        super().__init__(title="頻道權限設定")
        self.subbot_service = subbot_service
        self.bot_id = bot_id
        
        self.channels_input = discord.ui.TextInput(
            label="允許的頻道ID",
            placeholder="用逗號分隔頻道ID，留空表示不限制",
            default=current_channels,
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=500
        )
        self.add_item(self.channels_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            channels_text = self.channels_input.value.strip()
            
            if channels_text:
                try:
                    channel_ids = [int(ch.strip()) for ch in channels_text.split(',') if ch.strip()]
                    channels_display = ", ".join([f"<#{ch_id}>" for ch_id in channel_ids])
                except ValueError:
                    embed = discord.Embed(
                        title="格式錯誤",
                        description="頻道ID格式不正確，請使用數字ID並用逗號分隔。",
                        color=discord.Color.red()
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return
            else:
                channels_display = "無限制"
            
            embed = discord.Embed(
                title="頻道權限更新",
                description="頻道權限設定已更新",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="新設定",
                value=f"**允許頻道**: {channels_display}",
                inline=False
            )
            
            embed.add_field(
                name="注意",
                value="頻道權限修改功能正在開發中，此操作暫未實際生效。",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="更新失敗",
                description=f"更新頻道權限時發生錯誤: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


class BasicInfoModal(discord.ui.Modal):
    """基本資訊輸入模態框"""
    
    def __init__(self, subbot_service: SubBotService, user_id: int, wizard_data: Dict):
        super().__init__(title="步驟 1/3: 基本資訊")
        self.subbot_service = subbot_service
        self.user_id = user_id
        self.wizard_data = wizard_data
        
        self.name_input = discord.ui.TextInput(
            label="子機器人名稱",
            placeholder="為您的子機器人取個名字...",
            min_length=1,
            max_length=50
        )
        
        self.token_input = discord.ui.TextInput(
            label="Discord Bot Token",
            placeholder="從Discord開發者門戶複製Token...",
            min_length=50,
            max_length=200
        )
        
        self.add_item(self.name_input)
        self.add_item(self.token_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            name = self.name_input.value.strip()
            token = self.token_input.value.strip()
            
            # 儲存基本資訊
            self.wizard_data.update({
                'name': name,
                'token': token
            })
            
            # 進入下一步：可選配置
            view = OptionalConfigView(self.subbot_service, self.user_id, self.wizard_data)
            
            embed = discord.Embed(
                title="✅ 基本資訊已設定",
                description=f"子機器人名稱: **{name}**",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="步驟 2/3: 可選配置",
                value="現在您可以配置頻道限制和AI功能，或直接創建機器人。",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="設定錯誤",
                description=f"處理基本資訊時發生錯誤: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


class OptionalConfigView(discord.ui.View):
    """可選配置視圖"""
    
    def __init__(self, subbot_service: SubBotService, user_id: int, wizard_data: Dict):
        super().__init__(timeout=180.0)
        self.subbot_service = subbot_service
        self.user_id = user_id
        self.wizard_data = wizard_data
    
    @discord.ui.button(
        label="設定頻道限制",
        style=discord.ButtonStyle.secondary,
        emoji="🔒"
    )
    async def set_channels(self, interaction: discord.Interaction, button: discord.ui.Button):
        """設定頻道限制"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("只有創建者可以進行此操作。", ephemeral=True)
            return
        
        modal = ChannelConfigModal(self.subbot_service, self.user_id, self.wizard_data)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(
        label="設定AI功能",
        style=discord.ButtonStyle.secondary,
        emoji="🤖"
    )
    async def set_ai(self, interaction: discord.Interaction, button: discord.ui.Button):
        """設定AI功能"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("只有創建者可以進行此操作。", ephemeral=True)
            return
        
        modal = AIConfigModal(self.subbot_service, self.user_id, self.wizard_data)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(
        label="完成創建",
        style=discord.ButtonStyle.success,
        emoji="✅"
    )
    async def finish_creation(self, interaction: discord.Interaction, button: discord.ui.Button):
        """完成創建"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("只有創建者可以進行此操作。", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        try:
            # 創建子機器人
            result = await self.subbot_service.create_subbot(
                name=self.wizard_data['name'],
                token=self.wizard_data['token'],
                owner_id=self.user_id,
                channel_restrictions=self.wizard_data.get('channels', []),
                ai_enabled=self.wizard_data.get('ai_enabled', False),
                ai_model=self.wizard_data.get('ai_model'),
                personality=self.wizard_data.get('personality')
            )
            
            if result.get('success', False):
                embed = discord.Embed(
                    title="🎉 創建成功！",
                    description=f"子機器人 **{self.wizard_data['name']}** 已成功創建！",
                    color=discord.Color.green()
                )
                
                embed.add_field(
                    name="機器人資訊",
                    value=(
                        f"**ID**: `{result['bot_id']}`\n"
                        f"**名稱**: {result['name']}\n"
                        f"**狀態**: {result['status']}"
                    ),
                    inline=False
                )
                
                embed.add_field(
                    name="下一步",
                    value=f"使用 `/subbot start {result['bot_id']}` 來啟動您的子機器人！",
                    inline=False
                )
                
                # 禁用所有按鈕
                for item in self.children:
                    item.disabled = True
                    
                await interaction.edit_original_response(embed=embed, view=self)
                
            else:
                embed = discord.Embed(
                    title="創建失敗",
                    description=f"創建失敗: {result.get('error', '未知錯誤')}",
                    color=discord.Color.red()
                )
                await interaction.edit_original_response(embed=embed, view=self)
                
        except Exception as e:
            embed = discord.Embed(
                title="創建錯誤",
                description=f"創建過程中發生錯誤: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.edit_original_response(embed=embed, view=self)


class ChannelConfigModal(discord.ui.Modal):
    """頻道配置模態框"""
    
    def __init__(self, subbot_service: SubBotService, user_id: int, wizard_data: Dict):
        super().__init__(title="頻道限制設定")
        self.subbot_service = subbot_service
        self.user_id = user_id
        self.wizard_data = wizard_data
        
        self.channels_input = discord.ui.TextInput(
            label="允許的頻道ID",
            placeholder="用逗號分隔頻道ID，留空表示不限制",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=500
        )
        self.add_item(self.channels_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            channels_text = self.channels_input.value.strip()
            
            if channels_text:
                try:
                    channel_ids = [int(ch.strip()) for ch in channels_text.split(',') if ch.strip()]
                    self.wizard_data['channels'] = channel_ids
                    channels_display = ", ".join([f"<#{ch_id}>" for ch_id in channel_ids])
                except ValueError:
                    embed = discord.Embed(
                        title="格式錯誤",
                        description="頻道ID格式不正確，請使用數字ID並用逗號分隔。",
                        color=discord.Color.red()
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return
            else:
                self.wizard_data['channels'] = []
                channels_display = "無限制"
            
            # 更新視圖
            view = OptionalConfigView(self.subbot_service, self.user_id, self.wizard_data)
            
            embed = discord.Embed(
                title="✅ 頻道限制已設定",
                description=f"允許的頻道: {channels_display}",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="繼續配置",
                value="您可以繼續設定AI功能，或直接完成創建。",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="設定錯誤",
                description=f"設定頻道限制時發生錯誤: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


class AIConfigModal(discord.ui.Modal):
    """AI配置模態框"""
    
    def __init__(self, subbot_service: SubBotService, user_id: int, wizard_data: Dict):
        super().__init__(title="AI功能設定")
        self.subbot_service = subbot_service
        self.user_id = user_id
        self.wizard_data = wizard_data
        
        self.enabled_input = discord.ui.TextInput(
            label="啟用AI (true/false)",
            placeholder="true 或 false",
            default="false",
            min_length=4,
            max_length=5
        )
        
        self.model_input = discord.ui.TextInput(
            label="AI模型（可選）",
            placeholder="例如: gpt-3.5-turbo",
            required=False,
            max_length=100
        )
        
        self.personality_input = discord.ui.TextInput(
            label="人格設定（可選）",
            placeholder="描述機器人的人格特徵...",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=500
        )
        
        self.add_item(self.enabled_input)
        self.add_item(self.model_input)
        self.add_item(self.personality_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            enabled_str = self.enabled_input.value.lower().strip()
            ai_enabled = enabled_str in ['true', '1', 'yes', 'y', '是', '真']
            ai_model = self.model_input.value.strip() if self.model_input.value else None
            personality = self.personality_input.value.strip() if self.personality_input.value else None
            
            # 更新精靈數據
            self.wizard_data.update({
                'ai_enabled': ai_enabled,
                'ai_model': ai_model,
                'personality': personality
            })
            
            # 更新視圖
            view = OptionalConfigView(self.subbot_service, self.user_id, self.wizard_data)
            
            embed = discord.Embed(
                title="✅ AI設定已完成",
                description="AI功能配置已設定完成",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="AI設定",
                value=(
                    f"**啟用**: {'✅' if ai_enabled else '❌'}\n"
                    f"**模型**: {ai_model or '預設'}\n"
                    f"**人格**: {personality or '預設'}"
                ),
                inline=False
            )
            
            embed.add_field(
                name="完成創建",
                value="所有設定已完成，您可以點擊 '完成創建' 來創建子機器人。",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="設定錯誤",
                description=f"設定AI功能時發生錯誤: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    """
    設定子機器人管理Cog
    
    Elena的模組載入：確保子機器人管理功能與Discord bot完美整合
    """
    await bot.add_cog(SubBotManagementCog(bot))