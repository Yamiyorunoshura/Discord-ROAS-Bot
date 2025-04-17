import discord
from discord.ext import commands
from discord import app_commands
from PIL import Image, ImageDraw, ImageFont
import io
import os
import logging
import aiohttp
import PIL

# 設定專案根目錄
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 設定日誌
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
log_dir = os.path.join(PROJECT_ROOT, 'logs')
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
handler = logging.FileHandler(os.path.join(log_dir, 'welcome.log'), encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
logger.addHandler(handler)

logger.debug(f"Pillow 版本: {PIL.__version__}")

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.database
        self.bot.avatar_distances = {}

        # 確保 backgrounds 目錄存在
        backgrounds_dir = os.path.join(PROJECT_ROOT, "data", "backgrounds")
        if not os.path.exists(backgrounds_dir):
            os.makedirs(backgrounds_dir)

    # ------------------- 輔助函式 -------------------

    async def _save_attachment(self, interaction, attachment, path, file_type_error_msg):
        """儲存附件檔案"""
        allowed_extensions = (".png", ".jpg", ".jpeg", ".gif")
        if not attachment.filename.lower().endswith(allowed_extensions):
            await interaction.response.send_message(file_type_error_msg, ephemeral=True)
            return False

        try:
            await attachment.save(path)
            return True
        except Exception as e:
            await interaction.response.send_message(f"儲存檔案時發生錯誤: {e}", ephemeral=True)
            logger.exception(f"伺服器 {interaction.guild.id}: 儲存檔案時發生錯誤")
            return False

    async def _fetch_avatar(self, avatar_url):
        """從 URL 異步獲取頭像圖片"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(avatar_url) as response:
                    if response.status == 200:
                        return await response.read()
                    else:
                        logger.error(f"下載頭像失敗，狀態碼: {response.status}")
                        return None
        except Exception as e:
            logger.exception(f"下載頭像時發生錯誤: {e}")
            return None

    def _paste_avatar(self, img, avatar_bytes, guild_id, width, height, avatar_x, avatar_y):
        """貼上頭像"""
        if not avatar_bytes:
            logger.warning(f"伺服器 {guild_id}: 無法獲取頭像")
            return

        avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
        max_size = (int(0.2 * width), int(0.2 * height))
        avatar.thumbnail(max_size)
        img.paste(avatar, (int(avatar_x), int(avatar_y)), avatar)

    async def _generate_welcome_image(self, guild_id, title, description, member=None):
        """生成歡迎圖片"""
        background_image_path = self.db.get_welcome_background(guild_id)
        try:
            if background_image_path:
                background_image_path = os.path.join(PROJECT_ROOT, background_image_path)
                img = Image.open(background_image_path).convert("RGBA")
            else:
                img = Image.new("RGBA", (800, 450), (255, 255, 255, 0))
                logger.info(f"伺服器 {guild_id}: 未設定背景圖片，使用預設背景")
        except FileNotFoundError:
            logger.error(f"找不到背景圖片：{background_image_path}")
            img = Image.new("RGBA", (800, 450), (255, 255, 255, 0))
        except Exception as e:
            logger.exception(f"處理圖片時發生錯誤: {e}")
            img = Image.new("RGBA", (800, 450), (255, 255, 255, 0))

        width, height = img.size

        x_divisions = 100
        y_divisions = 100
        x_unit = width / x_divisions
        y_unit = height / y_divisions

        draw = ImageDraw.Draw(img, "RGBA")

        # 設定文字樣式
        try:
            font_path = os.path.join(PROJECT_ROOT, "NotoSansCJKtc-Regular.otf")
            title_font = ImageFont.truetype(font_path, 30)
            description_font = ImageFont.truetype(font_path, 22)
        except IOError:
            logger.error("找不到中文字體檔案！請確認 NotoSansCJKtc-Regular.otf 存在於程式碼所在的目錄中，或者提供完整的路徑")
            try:
                font_path = os.path.join(PROJECT_ROOT, "arial.ttf")
                title_font = ImageFont.truetype(font_path, 30)
                description_font = ImageFont.truetype(font_path, 22)
            except IOError:
                logger.error("找不到 arial.ttf 字體檔案！")
                # 如果找不到字體檔案，則使用預設字體，但可能無法顯示中文
                title_font = ImageFont.load_default()
                description_font = ImageFont.load_default()

        text_color = "#FFFFFF"
        text_opacity = 255

        avatar_x_pos = 12
        avatar_y_pos = 56
        title_y_pos = 47
        description_y_pos = 88

        avatar_x = avatar_x_pos * x_unit
        avatar_y = avatar_y_pos * y_unit
        title_y = title_y_pos * y_unit
        description_y = description_y_pos * y_unit

        max_avatar_size = (int(0.3 * width), int(0.3 * height))
        avatar_width = max_avatar_size[0]
        avatar_center_x = avatar_x + avatar_width / 2

        title_offset = -70
        description_offset = -50

        color_rgba = text_color + hex(text_opacity)[2:].zfill(2)

        if member:
            avatar_url = member.avatar.url if member.avatar else member.default_avatar.url
            avatar_bytes = await self._fetch_avatar(avatar_url)
            if avatar_bytes:
                avatar = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
                avatar.thumbnail(max_avatar_size)

                mask = Image.new('L', avatar.size, 0)
                draw_mask = ImageDraw.Draw(mask)
                draw_mask.ellipse((0, 0, avatar.size[0], avatar.size[1]), fill=255)

                avatar.putalpha(mask)

                img.paste(avatar, (int(avatar_x), int(avatar_y)), avatar)

        if title is None:
            title = "歡迎 {member.name}!"

        if description is None:
            description = "感謝你的加入！"

        title_text = title.format(member=member, guild=member.guild)
        title_width = draw.textlength(title_text, font=title_font)

        title_x = avatar_center_x - title_width / 2 + title_offset

        description_width = draw.textlength(description, font=description_font)
        description_x = avatar_center_x - description_width / 2 + description_offset

        draw.text((title_x, title_y), title_text, fill=color_rgba, font=title_font)

        draw.text((description_x, description_y), description, fill=color_rgba, font=description_font)

        return img

    # ------------------- 指令 -------------------

    @app_commands.command(name="設定歡迎訊息", description="設定與歡迎圖片一起發送的文字信息")
    @app_commands.describe(
        頻道="歡迎訊息發送的頻道 (例如: #歡迎，請選擇一個文字頻道)",
        內容="歡迎訊息內容 (例如: 歡迎 {member.mention} 加入!，可以使用 {member.name}、{member.mention}、{guild.name})"
    )
    async def set_welcome_message(self, interaction: discord.Interaction, 頻道: discord.TextChannel, 內容: str):
        """
        設定歡迎訊息指令。
        管理者可以使用此指令設定當有新成員加入伺服器時，機器人發送的歡迎訊息。
        可以使用 {member.name}、{member.mention}、{guild.name} 等變數來動態顯示成員和伺服器資訊。
        """
        guild_id = interaction.guild.id
        try:
            self.db.update_welcome_message(guild_id, 頻道.id, 內容)
            await interaction.response.send_message("歡迎訊息已更新!", ephemeral=True)
            logger.info(f"伺服器 {guild_id}: 歡迎訊息已更新，頻道: {頻道.id}, 內容: {內容}")
        except Exception as e:
            await interaction.response.send_message(f"更新歡迎訊息時發生錯誤: {e}", ephemeral=True)
            logger.exception(f"伺服器 {interaction.guild.id}: 更新歡迎訊息時發生錯誤")

    @app_commands.command(name="設定歡迎背景圖片", description="設定歡迎訊息背景圖片")
    @app_commands.describe(
        圖片="背景圖片 (例如: background.png，請上傳一個圖片檔案)"
    )
    async def set_welcome_background(self, interaction: discord.Interaction, 圖片: discord.Attachment):
        """
        設定歡迎背景圖片指令。
        管理者可以使用此指令設定歡迎訊息的背景圖片，讓歡迎訊息更加生動。
        請上傳一個圖片檔案作為背景。
        """
        guild_id = interaction.guild.id
        if not 圖片.content_type.startswith('image'):
            await interaction.response.send_message("請上傳圖片檔案!", ephemeral=True)
            return

        image_path = os.path.join(PROJECT_ROOT, "data", "backgrounds", f"{guild_id}.png")
        if await self._save_attachment(interaction, 圖片, image_path, "請上傳圖片檔案!"):
            self.db.update_welcome_background(guild_id, image_path)
            await interaction.response.send_message("歡迎訊息背景圖片已更新!", ephemeral=True)
            logger.info(f"伺服器 {guild_id}: 歡迎訊息背景圖片已更新，圖片路徑: {image_path}")

    @app_commands.command(name="設定標題", description="設定歡迎圖片的標題文字")
    @app_commands.describe(
        標題="標題文字 (可以使用 {member.name}、{member.mention}、{guild.name})"
    )
    async def set_title(self, interaction: discord.Interaction, 標題: str):
        """
        設定歡迎標題指令。
        管理者可以使用此指令設定歡迎圖片的標題文字。
        可以使用 {member.name}、{member.mention}、{guild.name} 等變數。
        """
        guild_id = interaction.guild.id
        try:
            self.db.update_welcome_title(guild_id, 標題)
            await interaction.response.send_message("標題已更新!", ephemeral=True)
            logger.info(f"伺服器 {guild_id}: 標題已更新，標題: {標題}")
        except Exception as e:
            await interaction.response.send_message(f"更新標題時發生錯誤: {e}", ephemeral=True)
            logger.exception(f"伺服器 {interaction.guild.id}: 更新標題時發生錯誤")

    @app_commands.command(name="設定內容", description="設定歡迎圖片的內容文字")
    @app_commands.describe(
        內容="內容文字 (可以使用 {member.name}、{member.mention}、{guild.name})"
    )
    async def set_description(self, interaction: discord.Interaction, 內容: str):
        """
        設定歡迎內容指令。
        管理者可以使用此指令設定歡迎圖片的內容文字。
        可以使用 {member.name}、{member.mention}、{guild.name} 等變數。
        """
        guild_id = interaction.guild.id
        try:
            self.db.update_welcome_description(guild_id, 內容)
            await interaction.response.send_message("內容已更新!", ephemeral=True)
            logger.info(f"伺服器 {guild_id}: 內容已更新，內容: {內容}")
        except Exception as e:
            await interaction.response.send_message(f"更新內容時發生錯誤: {e}", ephemeral=True)
            logger.exception(f"伺服器 {interaction.guild.id}: 更新內容時發生錯誤")

    @app_commands.command(name="預覽歡迎訊息", description="預覽設定的歡迎訊息")
    async def preview_welcome_message(self, interaction: discord.Interaction):
        """
        預覽歡迎訊息指令。
        管理者可以使用此指令預覽目前設定的歡迎訊息，以確認顯示效果。
        """
        guild_id = interaction.guild.id
        settings = self.db.get_welcome_settings(guild_id)
        if not settings:
            await interaction.response.send_message("尚未設定歡迎訊息！", ephemeral=True)
            return

        title = settings.get('title', '歡迎 {member.name}!')
        description = settings.get('description', '感謝你的加入！')
        welcome_message = self.db.get_welcome_message(guild_id)

        # 盡可能早地延遲回覆
        try:
            await interaction.response.defer(ephemeral=False)  #  ephemeral=False 讓使用者知道機器人正在處理
        except discord.errors.NotFound as e:
            logger.error(f"延遲回覆失敗: {e}")
            await interaction.response.send_message("預覽歡迎訊息時發生錯誤，請稍後再試！", ephemeral=True)
            return

        try:
            img = await self._generate_welcome_image(guild_id, title, description, interaction.user)

            with io.BytesIO() as image_binary:
                img.save(image_binary, 'PNG')
                image_binary.seek(0)
                image = discord.File(fp=image_binary, filename='welcome_image.png')

            # 使用 followup 發送訊息
            await interaction.followup.send(file=image, content=welcome_message)
            logger.info(f"伺服器 {guild_id}: 預覽歡迎訊息已成功生成")

        except Exception as e:
            # 使用 followup 發送錯誤訊息
            await interaction.followup.send(f"預覽歡迎訊息時發生錯誤: {e}", ephemeral=True)
            logger.exception(f"伺服器 {interaction.guild.id}: 預覽歡迎訊息時發生錯誤")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild_id = member.guild.id
        settings = self.db.get_welcome_settings(guild_id)
        if not settings:
            logger.info(f"伺服器 {guild_id}: 未設定歡迎訊息，跳過")
            return

        channel_id = settings.get('channel_id')
        title = settings.get('title', '歡迎 {member.name}!')
        description = settings.get('description', '感謝你的加入！')
        welcome_message = self.db.get_welcome_message(guild_id)

        if title is None:
            title = "歡迎 {member.name}!"

        if description is None:
            description = "感謝你的加入！"

        try:
            img = await self._generate_welcome_image(guild_id, title, description, member)

            with io.BytesIO() as image_binary:
                img.save(image_binary, 'PNG')
                image_binary.seek(0)
                image = discord.File(fp=image_binary, filename='welcome_image.png')

            if channel_id is None:
                logger.warning(f"伺服器 {guild_id}: 未設定歡迎訊息發送頻道，跳過發送訊息")
                return

            channel = self.bot.get_channel(channel_id)
            if channel:
                welcome_message = self.db.get_welcome_message(guild_id)
                if welcome_message:
                    welcome_message = welcome_message.format(member=member, guild=member.guild, member_mention=member.mention)
                else:
                    welcome_message = f"歡迎 {member.mention} 加入伺服器！"

                await channel.send(file=image, content=welcome_message)
                logger.info(f"伺服器 {guild_id}: 歡迎訊息已發送到頻道 {channel_id}")
            else:
                logger.error(f"伺服器 {guild_id}: 找不到頻道 {channel_id}")

        except Exception as e:
            logger.exception(f"伺服器 {guild_id}: 處理 on_member_join 事件時發生錯誤")

async def setup(bot):
    await bot.add_cog(Welcome(bot))