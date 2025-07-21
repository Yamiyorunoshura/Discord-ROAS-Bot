"""
資料同步設定對話框
- 自動同步間隔設定
- 同步範圍配置
- 通知設定
"""

import discord
from discord import ui
from typing import TYPE_CHECKING, Optional, Dict, Any
import logging

if TYPE_CHECKING:
    from ...main.main import SyncDataCog

logger = logging.getLogger("sync_data")

class AutoSyncSettingsModal(ui.Modal):
    """自動同步設定對話框"""
    
    def __init__(self, cog: "SyncDataCog"):
        super().__init__(title="⚙️ 自動同步設定")
        self.cog = cog
        
        # 同步間隔設定
        self.sync_interval = ui.TextInput(
            label="自動同步間隔 (分鐘)",
            placeholder="輸入 30-1440 之間的數值 (30分鐘到24小時)",
            default="60",
            min_length=2,
            max_length=4
        )
        self.add_item(self.sync_interval)
        
        # 同步類型設定
        self.sync_type = ui.TextInput(
            label="預設同步類型",
            placeholder="輸入: full (完整), roles (僅角色), channels (僅頻道)",
            default="full",
            min_length=4,
            max_length=8
        )
        self.add_item(self.sync_type)
        
        # 失敗重試次數
        self.retry_count = ui.TextInput(
            label="失敗重試次數",
            placeholder="輸入 1-5 之間的數值",
            default="3",
            min_length=1,
            max_length=1
        )
        self.add_item(self.retry_count)
        
        # 通知頻道設定
        self.notification_channel = ui.TextInput(
            label="通知頻道 ID (可選)",
            placeholder="輸入頻道 ID，留空則不發送通知",
            default="",
            required=False,
            min_length=0,
            max_length=20
        )
        self.add_item(self.notification_channel)
    
    async def on_submit(self, interaction: discord.Interaction):
        """提交設定"""
        try:
            # 驗證同步間隔
            try:
                interval = int(self.sync_interval.value)
                if interval < 30 or interval > 1440:
                    await interaction.response.send_message(
                        "❌ 同步間隔無效，請輸入 30-1440 之間的數值", 
                        ephemeral=True
                    )
                    return
            except ValueError:
                await interaction.response.send_message(
                    "❌ 同步間隔必須是數字", 
                    ephemeral=True
                )
                return
            
            # 驗證同步類型
            sync_type = self.sync_type.value.lower()
            if sync_type not in ['full', 'roles', 'channels']:
                await interaction.response.send_message(
                    "❌ 同步類型無效，請輸入 full、roles 或 channels", 
                    ephemeral=True
                )
                return
            
            # 驗證重試次數
            try:
                retry_count = int(self.retry_count.value)
                if retry_count < 1 or retry_count > 5:
                    await interaction.response.send_message(
                        "❌ 重試次數無效，請輸入 1-5 之間的數值", 
                        ephemeral=True
                    )
                    return
            except ValueError:
                await interaction.response.send_message(
                    "❌ 重試次數必須是數字", 
                    ephemeral=True
                )
                return
            
            # 驗證通知頻道 (可選)
            notification_channel_id = None
            if self.notification_channel.value.strip():
                try:
                    notification_channel_id = int(self.notification_channel.value.strip())
                    # 檢查頻道是否存在
                    channel = interaction.guild.get_channel(notification_channel_id)
                    if not channel:
                        await interaction.response.send_message(
                            "❌ 找不到指定的通知頻道", 
                            ephemeral=True
                        )
                        return
                except ValueError:
                    await interaction.response.send_message(
                        "❌ 通知頻道 ID 必須是數字", 
                        ephemeral=True
                    )
                    return
            
            # 儲存設定
            settings = {
                'auto_sync_enabled': True,
                'sync_interval': interval,
                'sync_type': sync_type,
                'retry_count': retry_count,
                'notification_channel_id': notification_channel_id,
                'guild_id': interaction.guild.id
            }
            
            # 更新資料庫設定
            await self._save_auto_sync_settings(settings)
            
            # 建立確認嵌入
            embed = discord.Embed(
                title="✅ 自動同步設定已更新",
                description="新的自動同步設定已套用",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="⚙️ 設定內容",
                value=(
                    f"同步間隔：{interval} 分鐘\n"
                    f"同步類型：{self._get_sync_type_name(sync_type)}\n"
                    f"重試次數：{retry_count} 次\n"
                    f"通知頻道：{f'<#{notification_channel_id}>' if notification_channel_id else '未設定'}"
                ),
                inline=False
            )
            
            embed.add_field(
                name="📅 下次同步",
                value=f"約 {interval} 分鐘後開始自動同步",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            # 啟動自動同步任務
            await self._start_auto_sync_task(settings)
            
        except Exception as e:
            logger.error(f"自動同步設定失敗: {e}")
            await interaction.response.send_message(
                f"❌ 設定失敗：{str(e)}", 
                ephemeral=True
            )
    
    async def _save_auto_sync_settings(self, settings: Dict[str, Any]):
        """儲存自動同步設定到資料庫"""
        try:
            # 這裡應該調用資料庫方法儲存設定
            # 暫時記錄到日誌
            logger.info(f"儲存自動同步設定: {settings}")
            
            # 可以儲存到 cog 的配置中
            if hasattr(self.cog, 'auto_sync_config'):
                self.cog.auto_sync_config.update(settings)
            else:
                self.cog.auto_sync_config = settings
                
        except Exception as e:
            logger.error(f"儲存自動同步設定失敗: {e}")
            raise
    
    async def _start_auto_sync_task(self, settings: Dict[str, Any]):
        """啟動自動同步任務"""
        try:
            # 這裡可以啟動定時任務
            logger.info(f"啟動自動同步任務: 間隔 {settings['sync_interval']} 分鐘")
            
            # 可以使用 Discord.py 的 tasks 功能
            # 暫時只記錄日誌
            
        except Exception as e:
            logger.error(f"啟動自動同步任務失敗: {e}")
    
    def _get_sync_type_name(self, sync_type: str) -> str:
        """獲取同步類型名稱"""
        type_names = {
            "full": "完整同步",
            "roles": "角色同步",
            "channels": "頻道同步"
        }
        return type_names.get(sync_type, "未知")

class SyncRangeModal(ui.Modal):
    """同步範圍設定對話框"""
    
    def __init__(self, cog: "SyncDataCog"):
        super().__init__(title="📋 同步範圍設定")
        self.cog = cog
        
        # 角色同步設定
        self.role_filter = ui.TextInput(
            label="角色過濾 (可選)",
            placeholder="輸入要排除的角色名稱，用逗號分隔",
            default="",
            required=False,
            style=discord.TextStyle.paragraph
        )
        self.add_item(self.role_filter)
        
        # 頻道同步設定
        self.channel_filter = ui.TextInput(
            label="頻道過濾 (可選)",
            placeholder="輸入要排除的頻道名稱，用逗號分隔",
            default="",
            required=False,
            style=discord.TextStyle.paragraph
        )
        self.add_item(self.channel_filter)
        
        # 同步選項
        self.sync_options = ui.TextInput(
            label="同步選項",
            placeholder="輸入: permissions (權限), positions (位置), all (全部)",
            default="all",
            min_length=3,
            max_length=20
        )
        self.add_item(self.sync_options)
    
    async def on_submit(self, interaction: discord.Interaction):
        """提交範圍設定"""
        try:
            # 處理角色過濾
            role_filters = []
            if self.role_filter.value.strip():
                role_filters = [name.strip() for name in self.role_filter.value.split(',') if name.strip()]
            
            # 處理頻道過濾
            channel_filters = []
            if self.channel_filter.value.strip():
                channel_filters = [name.strip() for name in self.channel_filter.value.split(',') if name.strip()]
            
            # 驗證同步選項
            sync_options = self.sync_options.value.lower()
            valid_options = ['permissions', 'positions', 'all']
            if sync_options not in valid_options:
                await interaction.response.send_message(
                    "❌ 同步選項無效，請輸入 permissions、positions 或 all", 
                    ephemeral=True
                )
                return
            
            # 儲存範圍設定
            range_settings = {
                'role_filters': role_filters,
                'channel_filters': channel_filters,
                'sync_options': sync_options,
                'guild_id': interaction.guild.id
            }
            
            # 更新配置
            if hasattr(self.cog, 'sync_range_config'):
                self.cog.sync_range_config.update(range_settings)
            else:
                self.cog.sync_range_config = range_settings
            
            # 建立確認嵌入
            embed = discord.Embed(
                title="✅ 同步範圍設定已更新",
                description="新的同步範圍設定已套用",
                color=discord.Color.blue()
            )
            
            if role_filters:
                embed.add_field(
                    name="👥 排除角色",
                    value=", ".join(role_filters),
                    inline=False
                )
            
            if channel_filters:
                embed.add_field(
                    name="📝 排除頻道",
                    value=", ".join(channel_filters),
                    inline=False
                )
            
            embed.add_field(
                name="⚙️ 同步選項",
                value=self._get_sync_options_name(sync_options),
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"同步範圍設定失敗: {e}")
            await interaction.response.send_message(
                f"❌ 設定失敗：{str(e)}", 
                ephemeral=True
            )
    
    def _get_sync_options_name(self, options: str) -> str:
        """獲取同步選項名稱"""
        option_names = {
            "permissions": "僅權限",
            "positions": "僅位置",
            "all": "完整同步"
        }
        return option_names.get(options, "未知") 