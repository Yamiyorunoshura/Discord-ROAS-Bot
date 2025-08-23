from .sync_data import SyncDataCog

async def setup(bot):
    await bot.add_cog(SyncDataCog(bot))