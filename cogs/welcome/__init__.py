from .welcome import WelcomeCog

async def setup(bot):
    await bot.add_cog(WelcomeCog(bot))