import discord
from discord.ext import commands
from cogs import database

class Currency(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = database.Database() # 假設您有一個資料庫類別

    @commands.command()
    async def balance(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        balance = self.db.get_balance(member.id)
        await ctx.send(f"{member.name} 的奶茶餘額：{balance} 🥛")

    @commands.command()
    async def give(self, ctx, member: discord.Member, amount: int):
        if amount <= 0:
            await ctx.send("請輸入有效的奶茶數量。")
            return
        self.db.transfer(ctx.author.id, member.id, amount)
        await ctx.send(f"{ctx.author.name} 轉帳 {amount} 🥛 給 {member.name}。")

async def setup(bot):
    await bot.add_cog(Currency(bot))