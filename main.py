import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import asyncio
import sys
import logging

# 設定專案根目錄
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# 設定日誌
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(os.path.join(PROJECT_ROOT, 'logs', 'main.log'), encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
logger.addHandler(handler)

# 明確指定需要的 Intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

load_dotenv()

bot = commands.Bot(command_prefix=commands.when_mentioned_or('!'), intents=intents)

async def load_extensions():
    cogs = ['cogs.database', 'cogs.message_listener', 'cogs.sync_data', 'cogs.welcome']
    for cog in cogs:
        try:
            await bot.load_extension(cog)
            print(f"Loaded cog: {cog}")
            logger.info(f"Loaded cog: {cog}")
            if cog == 'cogs.database':
                bot.database = bot.get_cog('Database')
        except Exception as e:
            print(f"Failed to load cog {cog}: {e}")
            logger.exception(f"Failed to load cog {cog}: {e}")

@bot.event
async def on_ready():
    print(f'機器人已啟動，名稱為 {bot.user.name}')
    logger.info(f'機器人已啟動，名稱為 {bot.user.name}')
    bot.welcome_channel = None

    await load_extensions()

    await asyncio.sleep(5)

    bot.guild_ids = [guild.id for guild in bot.guilds]
    print(f"機器人已加入以下伺服器：{bot.guild_ids}")
    logger.info(f"機器人已加入以下伺服器：{bot.guild_ids}")

    try:
        if os.getenv("ENVIRONMENT") == "development":
            YOUR_GUILD_ID = int(os.getenv("GUILD_ID"))
            synced = await bot.tree.sync(guild=discord.Object(id=YOUR_GUILD_ID))
            print(f"Synced {len(synced)} command(s) to guild {YOUR_GUILD_ID}")
            logger.info(f"Synced {len(synced)} command(s) to guild {YOUR_GUILD_ID}")
        else:
            synced = await bot.tree.sync()
            print(f"全域同步 {len(synced)} 個指令")
            logger.info(f"全域同步 {len(synced)} 個指令")
    except Exception as e:
        print(f"Error syncing commands: {e}")
        logger.exception(f"Error syncing commands: {e}")

@bot.event
async def on_message(message):
    print(f"Message from {message.author}: {message.content}")
    logger.info(f"Message from {message.author}: {message.content}")
    try:
        await bot.process_commands(message)
    except Exception as e:
        print(f"Error processing message: {e}")
        logger.exception(f"Error processing message: {e}")

token = os.getenv('TOKEN')
if token is None:
    print("錯誤：無法讀取機器人 Token。請檢查 .env 檔案是否正確設定。")
    logger.error("錯誤：無法讀取機器人 Token。請檢查 .env 檔案是否正確設定。")
else:
    print(f"成功讀取機器人 Token：{token}")
    logger.info(f"成功讀取機器人 Token：{token}")
    bot.run(token)