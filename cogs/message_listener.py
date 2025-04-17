import discord
from discord.ext import commands
from discord import app_commands
import logging
import os
from dotenv import load_dotenv

# 設定專案根目錄
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

# 設定日誌
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
log_dir = os.path.join(PROJECT_ROOT, 'logs')
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
handler = logging.FileHandler(os.path.join(log_dir, 'message_listener.log'), encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
logger.addHandler(handler)

class MessageListener(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.database
        self.log_channel_id = self.get_log_channel_id()
        self.log_edits = self.get_log_edits()
        self.log_deletes = self.get_log_deletes()
        self.monitored_channels = self.get_monitored_channels()

    def get_log_channel_id(self):
        """從資料庫獲取日誌頻道 ID"""
        try:
            query = "SELECT log_channel_id FROM settings WHERE setting_name = 'log_channel_id'"
            result = self.db._execute_select_query(query)
            if result and result[0]:
                return result[0][0]
            else:
                return None
        except Exception as e:
            logger.error(f"獲取日誌頻道 ID 失敗: {e}")
            return None

    def set_log_channel_id(self, channel_id):
        """將日誌頻道 ID 儲存到資料庫"""
        try:
            query = "INSERT OR REPLACE INTO settings (setting_name, log_channel_id) VALUES (?, ?)"
            self.db._execute_query(query, ("log_channel_id", channel_id))
            self.log_channel_id = channel_id
        except Exception as e:
            logger.error(f"設定日誌頻道 ID 失敗: {e}")

    def get_log_edits(self):
        """從資料庫獲取 log_edits 設定"""
        try:
            query = "SELECT log_edits FROM settings WHERE setting_name = 'log_edits'"
            result = self.db._execute_select_query(query)
            if result and result[0]:
                return bool(result[0][0])
            else:
                return True
        except Exception as e:
            logger.error(f"獲取 log_edits 設定失敗: {e}")
            return True

    def set_log_edits(self, value):
        """將 log_edits 設定儲存到資料庫"""
        try:
            query = "INSERT OR REPLACE INTO settings (setting_name, log_edits) VALUES (?, ?)"
            self.db._execute_query(query, ("log_edits", int(value)))
        except Exception as e:
            logger.error(f"設定 log_edits 失敗: {e}")

    def get_log_deletes(self):
        """從資料庫獲取 log_deletes 設定"""
        try:
            query = "SELECT log_deletes FROM settings WHERE setting_name = 'log_deletes'"
            result = self.db._execute_select_query(query)
            if result and result[0]:
                return bool(result[0][0])
            else:
                return True
        except Exception as e:
            logger.error(f"獲取 log_deletes 設定失敗: {e}")
            return True

    def set_log_deletes(self, value):
        """將 log_deletes 設定儲存到資料庫"""
        try:
            query = "INSERT OR REPLACE INTO settings (setting_name, log_deletes) VALUES (?, ?)"
            self.db._execute_query(query, ("log_deletes", int(value)))
        except Exception as e:
            logger.error(f"設定 log_deletes 失敗: {e}")

    def get_monitored_channels(self):
        """從資料庫獲取需要監聽的頻道列表"""
        try:
            query = "SELECT channel_id FROM monitored_channels"
            results = self.db._execute_select_query(query)
            if results:
                return [result[0][0] for result in results]
            else:
                return []
        except Exception as e:
            logger.error(f"獲取需要監聽的頻道列表失敗: {e}")
            return []

    def add_monitored_channel(self, channel_id):
        """將頻道新增到需要監聽的頻道列表"""
        try:
            query = "INSERT INTO monitored_channels (channel_id) VALUES (?)"
            self.db._execute_query(query, (channel_id,))
            self.monitored_channels.append(channel_id)
        except Exception as e:
            logger.error(f"新增需要監聽的頻道失敗: {e}")

    def remove_monitored_channel(self, channel_id):
        """將頻道從需要監聽的頻道列表中移除"""
        try:
            query = "DELETE FROM monitored_channels WHERE channel_id = ?"
            self.db._execute_query(query, (channel_id,))
            if channel_id in self.monitored_channels:
                self.monitored_channels.remove(channel_id)
        except Exception as e:
            logger.error(f"移除需要監聽的頻道失敗: {e}")

    async def send_log_message(self, guild, message):
        """發送日誌訊息到指定頻道"""
        log_channel = self.bot.get_channel(self.log_channel_id)
        if log_channel:
            embed = discord.Embed(title="訊息日誌", description=message, color=discord.Color.blue())
            embed.set_footer(text=f"伺服器: {guild.name} ({guild.id})")
            try:
                await log_channel.send(embed=embed)
            except discord.errors.Forbidden:
                logger.error(f"沒有發送訊息到頻道 {self.log_channel_id} 的權限")
            except Exception as e:
                logger.exception(f"發送日誌訊息時發生錯誤: {e}")
        else:
            logger.error(f"找不到日誌頻道 {self.log_channel_id}")

    message_log_group = app_commands.Group(name="訊息日誌", description="訊息日誌設定")

    @message_log_group.command(name="設定頻道", description="設定用於接收訊息日誌的頻道")
    @app_commands.describe(頻道="用於接收訊息日誌的頻道 (例如: #訊息日誌)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_channel(self, interaction: discord.Interaction, 頻道: discord.TextChannel):
        """設定日誌頻道指令"""
        self.set_log_channel_id(頻道.id)
        self.log_channel_id = 頻道.id
        await interaction.response.send_message(f"已將日誌頻道設定為 {頻道.mention}", ephemeral=True)
        logger.info(f"伺服器 {interaction.guild.id}: 已將日誌頻道設定為 {頻道.id}")

    @message_log_group.command(name="切換編輯日誌", description="開啟/關閉記錄訊息編輯事件")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def toggle_edits(self, interaction: discord.Interaction):
        """切換訊息編輯日誌指令"""
        self.log_edits = not self.log_edits
        self.set_log_edits(self.log_edits)
        status = "開啟" if self.log_edits else "關閉"
        await interaction.response.send_message(f"訊息編輯日誌已{status}", ephemeral=True)
        logger.info(f"伺服器 {interaction.guild.id}: 訊息編輯日誌已{status}")

    @message_log_group.command(name="切換刪除日誌", description="開啟/關閉記錄訊息刪除事件")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def toggle_deletes(self, interaction: discord.Interaction):
        """切換訊息刪除日誌指令"""
        self.log_deletes = not self.log_deletes
        self.set_log_deletes(self.log_deletes)
        status = "開啟" if self.log_deletes else "關閉"
        await interaction.response.send_message(f"訊息刪除日誌已{status}", ephemeral=True)
        logger.info(f"伺服器 {interaction.guild.id}: 訊息刪除日誌已{status}")

    @message_log_group.command(name="新增頻道", description="新增需要監聽的頻道")
    @app_commands.describe(頻道="需要監聽的頻道 (例如: #general #random)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def add_channel(self, interaction: discord.Interaction, 頻道: str):
        """新增需要監聽的頻道指令"""
        channel_ids = 頻道.split()
        added_channels = []
        already_monitored = []

        for channel_id_str in channel_ids:
            try:
                channel_id = int(channel_id_str.strip('<#>'))
                channel = self.bot.get_channel(channel_id)
                if channel and channel_id not in self.monitored_channels:
                    self.add_monitored_channel(channel_id)
                    added_channels.append(channel.mention)
                    logger.info(f"伺服器 {interaction.guild.id}: 已新增 {channel_id} 到需要監聽的頻道列表")
                else:
                    already_monitored.append(f"<#{channel_id}>")
            except ValueError:
                await interaction.response.send_message(f"無效的頻道 ID: {channel_id_str}", ephemeral=True)
                return
            except Exception as e:
                logger.error(f"新增頻道 {channel_id_str} 失敗: {e}")
                await interaction.response.send_message(f"新增頻道 {channel_id_str} 失敗", ephemeral=True)
                return

        if added_channels:
            added_channels_str = ", ".join(added_channels)
            message = f"已新增 {added_channels_str} 到需要監聽的頻道列表"
            await interaction.response.send_message(message, ephemeral=True)
        if already_monitored:
            already_monitored_str = ", ".join(already_monitored)
            message = f"{already_monitored_str} 已經在需要監聽的頻道列表中"
            await interaction.response.send_message(message, ephemeral=True)
        if not added_channels and not already_monitored:
            await interaction.response.send_message("沒有新增任何頻道", ephemeral=True)

    @message_log_group.command(name="移除頻道", description="移除需要監聽的頻道")
    @app_commands.describe(頻道="需要移除監聽的頻道 (例如: #general)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def remove_channel(self, interaction: discord.Interaction, 頻道: discord.TextChannel):
        """移除需要監聽的頻道指令"""
        if 頻道.id in self.monitored_channels:
            self.remove_monitored_channel(頻道.id)
            await interaction.response.send_message(f"已從需要監聽的頻道列表移除 {頻道.mention}", ephemeral=True)
            logger.info(f"伺服器 {interaction.guild.id}: 已從需要監聽的頻道列表移除 {頻道.id}")
        else:
            await interaction.response.send_message(f"{頻道.mention} 不在需要監聽的頻道列表中", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message):
        """監聽訊息事件"""
        if message.author.bot:
            return

        if message.channel.id not in self.monitored_channels:
            return

        guild_id = message.guild.id
        channel_id = message.channel.id
        author_id = message.author.id
        message_id = message.id
        content = message.content
        timestamp = message.created_at.timestamp()

        # 儲存訊息到資料庫
        try:
            query = "INSERT INTO messages (message_id, channel_id, guild_id, author_id, content, timestamp) VALUES (?, ?, ?, ?, ?, ?)"
            params = (message_id, channel_id, guild_id, author_id, content, timestamp)
            self.db._execute_query(query, params)

            # 格式化日誌訊息
            log_message = (
                f"# 訊息已發送\n"
                f"**作者：**{message.author.mention}\n"
                f"**頻道：**{message.channel.mention}\n"
                f"**內容：**\n{content}"
            )

            logger.info(f"伺服器 {guild_id}: 訊息已發送 (ID: {message_id}, 作者: {author_id}, 頻道: {channel_id}, 內容: {content})")
            await self.send_log_message(message.guild, log_message)
        except Exception as e:
            logger.error(f"伺服器 {guild_id}: 儲存訊息失敗 (ID: {message_id}, 作者: {author_id}, 內容: {content}): {e}")

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        """監聽訊息編輯事件"""
        if not self.log_edits or before.author.bot:
            return

        if before.channel.id not in self.monitored_channels:
            return

        guild_id = before.guild.id
        channel_id = before.channel.id
        author_id = before.author.id
        message_id = before.id
        old_content = before.content
        new_content = after.content
        timestamp = after.edited_at.timestamp()

        # 更新資料庫中的訊息
        try:
            query = "UPDATE messages SET content = ?, timestamp = ? WHERE message_id = ?"
            params = (new_content, timestamp, message_id)
            self.db._execute_query(query, params)

            # 格式化日誌訊息
            log_message = (
                f"# 訊息已編輯\n"
                f"**作者：**{before.author.mention}\n"
                f"**頻道：**{before.channel.mention}\n"
                f"**原始內容：**\n{old_content}\n"
                f"**新內容：**\n{new_content}"
            )

            logger.info(f"伺服器 {guild_id}: 訊息已編輯 (ID: {message_id}, 作者: {author_id}, 頻道: {channel_id}, 原始內容: {old_content}, 新內容: {new_content})")
            await self.send_log_message(before.guild, log_message)
        except Exception as e:
            logger.error(f"伺服器 {guild_id}: 更新訊息失敗 (ID: {message_id}, 作者: {author_id}, 原始內容: {old_content}, 新內容: {new_content}): {e}")

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        """監聽訊息刪除事件"""
        if not self.log_deletes or message.author.bot:
            return

        if message.channel.id not in self.monitored_channels:
            return

        guild_id = message.guild.id
        channel_id = message.channel.id
        author_id = message.author.id
        message_id = message.id
        content = message.content
        timestamp = message.created_at.timestamp()

        # 從資料庫中刪除訊息
        try:
            query = "DELETE FROM messages WHERE message_id = ?"
            params = (message_id,)
            self.db._execute_query(query, params)

            # 格式化日誌訊息
            log_message = (
                f"# 訊息已刪除\n"
                f"**作者：**{message.author.mention}\n"
                f"**頻道：**{message.channel.mention}\n"
                f"**內容：**\n{content}"
            )

            logger.info(f"伺服器 {guild_id}: 訊息已刪除 (ID: {message_id}, 作者: {author_id}, 頻道: {channel_id}, 內容: {content})")
            await self.send_log_message(message.guild, log_message)

        except Exception as e:
            logger.error(f"伺服器 {guild_id}: 刪除訊息失敗 (ID: {message_id}, 作者: {author_id}, 內容: {content}): {e}")

async def setup(bot):
    await bot.add_cog(MessageListener(bot))