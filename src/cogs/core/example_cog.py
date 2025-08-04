"""
📝 示例Cog
Discord ADR Bot v1.6 - 展示依賴注入使用方式的示例

此Cog展示了:
- 如何繼承BaseCog
- 如何註冊和解析服務
- 如何使用依賴注入模式

作者:Discord ADR Bot 架構師
版本:v1.6
"""

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands

from .base_cog import BaseCog

# 常數定義
MAX_SERVICES_DISPLAY = 5

if TYPE_CHECKING:
    from .database_pool import DatabaseConnectionPool

# 設置日誌
logger = logging.getLogger(__name__)

# 示例服務類別
class ExampleService:
    """示例服務類別"""

    def __init__(self):
        self.name = "ExampleService"
        self.initialized = False

    async def initialize(self):
        """異步初始化"""
        self.initialized = True
        logger.info("[ExampleService]服務初始化完成")

    def get_message(self) -> str:
        """獲取示例訊息"""
        return f"Hello from {self.name}! Initialized: {self.initialized}"

class DatabaseService:
    """資料庫服務類別"""

    def __init__(self):
        self.pool: DatabaseConnectionPool | None = None

    async def initialize(self):
        """初始化資料庫連接"""
        from .database_pool import get_global_pool  # noqa: PLC0415

        self.pool = await get_global_pool()
        logger.info("[DatabaseService]資料庫服務初始化完成")

    async def get_connection_info(self) -> dict:
        """獲取連接池信息"""
        if not self.pool:
            return {"error": "資料庫連接池未初始化"}

        status = await self.pool.get_pool_status()
        return {
            "pool_initialized": True,
            "total_connections": status.get("total_connections", 0),
            "active_connections": status.get("active_connections", 0),
            "available_connections": status.get("available_connections", 0),
        }

class ExampleCog(BaseCog):
    """
    示例Cog - 展示依賴注入的使用方式
    """

    async def initialize(self):
        """初始化示例Cog"""
        logger.info("[ExampleCog]開始初始化...")

        # 註冊服務
        self.register_service(ExampleService, lifetime="singleton")
        self.register_service(DatabaseService, lifetime="singleton")

        # 預先解析服務以確保它們被初始化
        await self.resolve_service(ExampleService)
        await self.resolve_service(DatabaseService)

        logger.info("[ExampleCog]初始化完成")

    async def cleanup(self):
        """清理資源"""
        logger.info("[ExampleCog]清理完成")

    @app_commands.command(name="示例服務", description="測試依賴注入服務")
    async def example_service_command(self, interaction: discord.Interaction):
        """示例服務指令"""
        await interaction.response.defer()

        try:
            # 解析服務
            example_service = await self.resolve_service(ExampleService)

            # 使用服務
            message = example_service.get_message()

            # 創建嵌入
            embed = discord.Embed(
                title="🔧 依賴注入示例",
                description=message,
                color=discord.Color.green(),
            )

            embed.add_field(
                name="服務狀態",
                value=f"✅ 已初始化: {example_service.initialized}",
                inline=False,
            )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"[ExampleCog]示例服務指令失敗: {e}")
            await interaction.followup.send(f"❌ 執行失敗: {e}")

    @app_commands.command(name="資料庫狀態", description="查看資料庫連接池狀態")
    async def database_status_command(self, interaction: discord.Interaction):
        """資料庫狀態指令"""
        await interaction.response.defer()

        try:
            # 解析資料庫服務
            db_service = await self.resolve_service(DatabaseService)

            # 獲取連接池信息
            connection_info = await db_service.get_connection_info()

            # 創建嵌入
            embed = discord.Embed(
                title="🗄️ 資料庫連接池狀態", color=discord.Color.blue()
            )

            if "error" in connection_info:
                embed.add_field(
                    name="錯誤", value=connection_info["error"], inline=False
                )
                embed.color = discord.Color.red()
            else:
                embed.add_field(
                    name="總連接數",
                    value=str(connection_info.get("total_connections", "未知")),
                    inline=True,
                )
                embed.add_field(
                    name="活躍連接",
                    value=str(connection_info.get("active_connections", "未知")),
                    inline=True,
                )
                embed.add_field(
                    name="可用連接",
                    value=str(connection_info.get("available_connections", "未知")),
                    inline=True,
                )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"[ExampleCog]資料庫狀態指令失敗: {e}")
            await interaction.followup.send(f"❌ 執行失敗: {e}")

    @app_commands.command(name="服務信息", description="查看依賴注入容器信息")
    async def service_info_command(self, interaction: discord.Interaction):
        """服務信息指令"""
        await interaction.response.defer()

        try:
            # 獲取服務信息
            service_info = self.get_service_info()

            # 創建嵌入
            embed = discord.Embed(
                title="🔧 依賴注入容器信息", color=discord.Color.purple()
            )

            embed.add_field(
                name="Cog名稱", value=service_info.get("cog_name", "未知"), inline=True
            )

            embed.add_field(
                name="初始化狀態",
                value="✅ 已初始化"
                if service_info.get("initialized")
                else "❌ 未初始化",
                inline=True,
            )

            embed.add_field(
                name="緩存服務數",
                value=str(service_info.get("cached_services", 0)),
                inline=True,
            )

            # 容器信息
            container_info = service_info.get("container_info", {})
            if container_info:
                embed.add_field(
                    name="總服務數",
                    value=str(container_info.get("total_services", 0)),
                    inline=True,
                )

                embed.add_field(
                    name="單例服務數",
                    value=str(container_info.get("singletons", 0)),
                    inline=True,
                )

                # 服務列表
                services = container_info.get("services", [])
                if services:
                    service_names = [
                        s.get("service_type", "未知") for s in services[:MAX_SERVICES_DISPLAY]
                    ]  # 只顯示前幾個
                    embed.add_field(
                        name="註冊的服務",
                        value="\n".join(service_names)
                        + ("..." if len(services) > MAX_SERVICES_DISPLAY else ""),
                        inline=False,
                    )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"[ExampleCog]服務信息指令失敗: {e}")
            await interaction.followup.send(f"❌ 執行失敗: {e}")

    @app_commands.command(name="作用域測試", description="測試服務作用域功能")
    async def scope_test_command(self, interaction: discord.Interaction):
        """作用域測試指令"""
        await interaction.response.defer()

        try:
            # 註冊作用域服務
            class ScopedTestService:
                def __init__(self):
                    self.id = id(self)
                    self.message = f"作用域服務實例 {self.id}"

            self.register_service(ScopedTestService, lifetime="scoped")

            # 在不同作用域中解析服務
            async with await self.create_scope("test_scope_1") as scope1:
                service1_a = await self.resolve_service(ScopedTestService, scope=scope1)
                service1_b = await self.resolve_service(ScopedTestService, scope=scope1)

            async with await self.create_scope("test_scope_2") as scope2:
                service2_a = await self.resolve_service(ScopedTestService, scope=scope2)
                service2_b = await self.resolve_service(ScopedTestService, scope=scope2)

            # 創建結果嵌入
            embed = discord.Embed(title="🔄 作用域測試結果", color=discord.Color.gold())

            embed.add_field(
                name="作用域1 - 服務A", value=f"ID: {service1_a.id}", inline=True
            )

            embed.add_field(
                name="作用域1 - 服務B", value=f"ID: {service1_b.id}", inline=True
            )

            embed.add_field(
                name="相同作用域",
                value="✅ 是" if service1_a.id == service1_b.id else "❌ 否",
                inline=True,
            )

            embed.add_field(
                name="作用域2 - 服務A", value=f"ID: {service2_a.id}", inline=True
            )

            embed.add_field(
                name="作用域2 - 服務B", value=f"ID: {service2_b.id}", inline=True
            )

            embed.add_field(
                name="相同作用域",
                value="✅ 是" if service2_a.id == service2_b.id else "❌ 否",
                inline=True,
            )

            embed.add_field(
                name="跨作用域隔離",
                value="✅ 是" if service1_a.id != service2_a.id else "❌ 否",
                inline=False,
            )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"[ExampleCog]作用域測試指令失敗: {e}")
            await interaction.followup.send(f"❌ 執行失敗: {e}")

# 設置函數
async def setup(bot):
    """設置ExampleCog"""
    await bot.add_cog(ExampleCog(bot))
