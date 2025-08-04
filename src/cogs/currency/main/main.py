"""Currency Cog for Discord ROAS Bot v2.0.

此模組提供貨幣系統的 Discord 指令介面, 支援:
- 餘額查詢與管理
- 用戶間轉帳交易
- 伺服器排行榜顯示
- 管理員貨幣操作
- 經濟統計查看
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands

if TYPE_CHECKING:
    from discord.ext import commands

from src.cogs.core.base_cog import BaseCog
from src.cogs.currency.database import (
    ConcurrencyError,
    InsufficientFundsError,
)
from src.cogs.currency.panel import (
    CurrencyAdminPanelView,
    CurrencyPanelView,
)
from src.cogs.currency.service import get_currency_service

logger = logging.getLogger(__name__)

class CurrencyCog(BaseCog):
    """貨幣系統 Cog.

    提供完整的 Discord 貨幣系統功能, 包括餘額管理、轉帳和排行榜.
    """

    def __init__(self, bot: commands.Bot):
        """初始化貨幣 Cog.

        Args:
            bot: Discord 機器人實例
        """
        super().__init__(bot)
        self.currency_service = get_currency_service()
        self.logger = logger

    async def initialize(self):
        """初始化 Cog 特定邏輯."""
        self.logger.info("Currency Cog 初始化完成")

    # =============================================================================
    # 新的統一面板指令
    # =============================================================================

    @app_commands.command(name="貨幣面板", description="開啟貨幣系統用戶面板")
    async def currency_panel(self, interaction: discord.Interaction):
        """開啟貨幣系統用戶面板."""
        try:
            # 創建用戶面板
            panel_view = CurrencyPanelView(
                currency_service=self.currency_service,
                author_id=interaction.user.id,
                guild_id=interaction.guild_id,
            )

            # 啟動面板
            await panel_view.start(interaction)

        except Exception as e:
            self.logger.error(f"開啟貨幣面板失敗: {e}")
            embed = discord.Embed(
                title="❌ 錯誤",
                description="開啟貨幣面板時發生錯誤, 請稍後再試",
                color=discord.Color.red(),
            )
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="貨幣管理面板", description="開啟貨幣系統管理員面板")
    @app_commands.default_permissions(administrator=True)
    async def currency_admin_panel(self, interaction: discord.Interaction):
        """開啟貨幣系統管理員面板."""
        try:
            # 檢查管理員權限
            if not interaction.user.guild_permissions.administrator:
                embed = discord.Embed(
                    title="❌ 權限不足",
                    description="只有管理員可以使用貨幣管理面板",
                    color=discord.Color.red(),
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            # 創建管理員面板
            admin_panel_view = CurrencyAdminPanelView(
                currency_service=self.currency_service,
                author_id=interaction.user.id,
                guild_id=interaction.guild_id,
            )

            # 啟動面板
            await admin_panel_view.start(interaction)

        except Exception as e:
            self.logger.error(f"開啟管理員面板失敗: {e}")
            embed = discord.Embed(
                title="❌ 錯誤",
                description="開啟管理員面板時發生錯誤, 請稍後再試",
                color=discord.Color.red(),
            )
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)

    # =============================================================================
    # 舊版指令組 - 將在面板穩定後移除
    # =============================================================================

    # 注意: 以下指令將在面板系統穩定後移除,請使用新的面板指令
    currency_group = app_commands.Group(name="currency", description="貨幣系統指令 (即將移除, 請使用 /貨幣面板)")

    @currency_group.command(name="balance", description="查詢你的貨幣餘額")
    async def balance(self, interaction: discord.Interaction):
        """查詢用戶餘額."""
        try:
            await interaction.response.defer(ephemeral=True)

            guild_id = interaction.guild_id
            user_id = interaction.user.id

            balance = await self.currency_service.get_balance(guild_id, user_id)

            embed = discord.Embed(
                title="💰 你的餘額",
                description=f"**{balance:,}** 貨幣",
                color=discord.Color.gold(),
            )
            embed.set_footer(text=f"用戶 ID: {user_id}")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            self.logger.error(f"查詢餘額失敗: {e}")
            embed = discord.Embed(
                title="❌ 錯誤",
                description="查詢餘額時發生錯誤, 請稍後再試",
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @currency_group.command(name="transfer", description="轉帳給其他用戶")
    @app_commands.describe(
        target="要轉帳的目標用戶", amount="轉帳金額", reason="轉帳原因(可選)"
    )
    async def transfer(
        self,
        interaction: discord.Interaction,
        target: discord.Member,
        amount: int,
        reason: str | None = None,
    ):
        """用戶間轉帳."""
        try:
            await interaction.response.defer(ephemeral=True)

            # 基本驗證
            if amount <= 0:
                embed = discord.Embed(
                    title="❌ 錯誤",
                    description="轉帳金額必須大於 0",
                    color=discord.Color.red(),
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            if target.id == interaction.user.id:
                embed = discord.Embed(
                    title="❌ 錯誤",
                    description="不能轉帳給自己",
                    color=discord.Color.red(),
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            if target.bot:
                embed = discord.Embed(
                    title="❌ 錯誤",
                    description="不能轉帳給機器人",
                    color=discord.Color.red(),
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            guild_id = interaction.guild_id
            from_user_id = interaction.user.id
            to_user_id = target.id

            # 執行轉帳
            result = await self.currency_service.transfer(
                guild_id, from_user_id, to_user_id, amount, reason
            )

            # 成功回應
            embed = discord.Embed(title="✅ 轉帳成功", color=discord.Color.green())
            embed.add_field(name="轉帳金額", value=f"{amount:,} 貨幣", inline=True)
            embed.add_field(name="接收者", value=target.mention, inline=True)
            embed.add_field(
                name="你的餘額",
                value=f"{result['from_balance_after']:,} 貨幣",
                inline=True,
            )

            if reason:
                embed.add_field(name="轉帳原因", value=reason, inline=False)

            embed.set_footer(text=f"交易 ID: {result['transaction_id'][:8]}...")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except InsufficientFundsError:
            embed = discord.Embed(
                title="❌ 餘額不足",
                description="你的餘額不足以完成此次轉帳",
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

        except ConcurrencyError:
            embed = discord.Embed(
                title="❌ 系統忙碌",
                description="系統正在處理其他交易, 請稍後再試",
                color=discord.Color.orange(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

        except ValueError as e:
            embed = discord.Embed(
                title="❌ 輸入錯誤", description=str(e), color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            self.logger.error(f"轉帳失敗: {e}")
            embed = discord.Embed(
                title="❌ 錯誤",
                description="轉帳時發生錯誤, 請稍後再試",
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @currency_group.command(name="top", description="查看伺服器貨幣排行榜")
    @app_commands.describe(limit="顯示數量(預設 10,最多 25)")
    async def leaderboard(
        self, interaction: discord.Interaction, limit: int | None = 10
    ):
        """顯示伺服器排行榜."""
        try:
            await interaction.response.defer()

            # 限制查詢數量
            limit = max(1, min(limit or 10, 25))

            guild_id = interaction.guild_id

            # 獲取排行榜資料
            leaderboard_data = await self.currency_service.get_leaderboard(
                guild_id, limit=limit
            )

            embed = discord.Embed(
                title="🏆 伺服器貨幣排行榜", color=discord.Color.gold()
            )

            if not leaderboard_data["entries"]:
                embed.description = "還沒有用戶擁有貨幣"
            else:
                description_lines = []
                for entry in leaderboard_data["entries"]:
                    rank = entry["rank"]
                    user_id = entry["user_id"]
                    balance = entry["balance"]

                    # 嘗試獲取用戶名稱
                    try:
                        user = self.bot.get_user(user_id) or await self.bot.fetch_user(
                            user_id
                        )
                        user_display = user.display_name
                    except Exception:
                        user_display = f"用戶 {user_id}"

                    # 添加排名圖示
                    if rank == 1:
                        rank_emoji = "🥇"
                    elif rank == 2:  # noqa: PLR2004
                        rank_emoji = "🥈"
                    elif rank == 3:  # noqa: PLR2004
                        rank_emoji = "🥉"
                    else:
                        rank_emoji = f"**{rank}.**"

                    description_lines.append(
                        f"{rank_emoji} {user_display}: **{balance:,}** 貨幣"
                    )

                embed.description = "\n".join(description_lines)

            embed.set_footer(
                text=f"顯示前 {len(leaderboard_data['entries'])} 名 • "
                f"總共 {leaderboard_data['total_count']} 位用戶"
            )

            await interaction.followup.send(embed=embed)

        except Exception as e:
            self.logger.error(f"獲取排行榜失敗: {e}")
            embed = discord.Embed(
                title="❌ 錯誤",
                description="獲取排行榜時發生錯誤, 請稍後再試",
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @currency_group.command(name="rank", description="查看你在排行榜中的排名")
    async def rank(self, interaction: discord.Interaction):
        """查看用戶排名."""
        try:
            await interaction.response.defer(ephemeral=True)

            guild_id = interaction.guild_id
            user_id = interaction.user.id

            rank_data = await self.currency_service.get_user_rank(guild_id, user_id)

            embed = discord.Embed(title="📊 你的排名資訊", color=discord.Color.blue())
            embed.add_field(
                name="目前排名", value=f"第 **{rank_data['rank']}** 名", inline=True
            )
            embed.add_field(
                name="目前餘額", value=f"**{rank_data['balance']:,}** 貨幣", inline=True
            )
            embed.add_field(
                name="百分位數",
                value=f"前 **{rank_data['percentile']:.1f}%**",
                inline=True,
            )
            embed.set_footer(text=f"總共 {rank_data['total_users']} 位用戶")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            self.logger.error(f"獲取排名失敗: {e}")
            embed = discord.Embed(
                title="❌ 錯誤",
                description="獲取排名時發生錯誤, 請稍後再試",
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    # =============================================================================
    # 管理員指令組 - /admin-currency
    # =============================================================================

    # 注意: 以下指令將在面板系統穩定後移除,請使用新的面板指令
    admin_currency_group = app_commands.Group(
        name="admin-currency", description="管理員貨幣系統指令 (即將移除,請使用 /貨幣管理面板)"
    )

    @admin_currency_group.command(name="add", description="增加用戶貨幣")
    @app_commands.describe(target="目標用戶", amount="增加的金額", reason="操作原因")
    @app_commands.default_permissions(manage_guild=True)
    async def admin_add(
        self,
        interaction: discord.Interaction,
        target: discord.Member,
        amount: int,
        reason: str = "管理員操作",
    ):
        """管理員增加用戶貨幣."""
        try:
            await interaction.response.defer(ephemeral=True)

            if amount <= 0:
                embed = discord.Embed(
                    title="❌ 錯誤",
                    description="增加金額必須大於 0",
                    color=discord.Color.red(),
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            guild_id = interaction.guild_id
            target_id = target.id
            admin_id = interaction.user.id

            result = await self.currency_service.add_balance(
                guild_id, target_id, amount, reason, admin_id
            )

            embed = discord.Embed(title="✅ 貨幣增加成功", color=discord.Color.green())
            embed.add_field(name="目標用戶", value=target.mention, inline=True)
            embed.add_field(name="增加金額", value=f"{amount:,} 貨幣", inline=True)
            embed.add_field(
                name="更新後餘額", value=f"{result['new_balance']:,} 貨幣", inline=True
            )
            embed.add_field(name="操作原因", value=reason, inline=False)
            embed.set_footer(text=f"操作者: {interaction.user.display_name}")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            self.logger.error(f"管理員增加貨幣失敗: {e}")
            embed = discord.Embed(
                title="❌ 錯誤",
                description="增加貨幣時發生錯誤, 請稍後再試",
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @admin_currency_group.command(name="remove", description="扣除用戶貨幣")
    @app_commands.describe(target="目標用戶", amount="扣除的金額", reason="操作原因")
    @app_commands.default_permissions(manage_guild=True)
    async def admin_remove(
        self,
        interaction: discord.Interaction,
        target: discord.Member,
        amount: int,
        reason: str = "管理員操作",
    ):
        """管理員扣除用戶貨幣."""
        try:
            await interaction.response.defer(ephemeral=True)

            if amount <= 0:
                embed = discord.Embed(
                    title="❌ 錯誤",
                    description="扣除金額必須大於 0",
                    color=discord.Color.red(),
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            guild_id = interaction.guild_id
            target_id = target.id
            admin_id = interaction.user.id

            result = await self.currency_service.add_balance(
                guild_id, target_id, -amount, reason, admin_id
            )

            embed = discord.Embed(title="✅ 貨幣扣除成功", color=discord.Color.green())
            embed.add_field(name="目標用戶", value=target.mention, inline=True)
            embed.add_field(name="扣除金額", value=f"{amount:,} 貨幣", inline=True)
            embed.add_field(
                name="更新後餘額", value=f"{result['new_balance']:,} 貨幣", inline=True
            )
            embed.add_field(name="操作原因", value=reason, inline=False)
            embed.set_footer(text=f"操作者: {interaction.user.display_name}")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            self.logger.error(f"管理員扣除貨幣失敗: {e}")
            embed = discord.Embed(
                title="❌ 錯誤",
                description="扣除貨幣時發生錯誤, 請稍後再試",
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @admin_currency_group.command(name="stats", description="查看伺服器經濟統計")
    @app_commands.default_permissions(manage_guild=True)
    async def admin_stats(self, interaction: discord.Interaction):
        """查看伺服器經濟統計."""
        try:
            await interaction.response.defer(ephemeral=True)

            guild_id = interaction.guild_id
            stats = await self.currency_service.get_guild_statistics(guild_id)

            embed = discord.Embed(title="📈 伺服器經濟統計", color=discord.Color.blue())
            embed.add_field(
                name="總用戶數", value=f"{stats['total_users']:,}", inline=True
            )
            embed.add_field(
                name="流通貨幣", value=f"{stats['total_currency']:,}", inline=True
            )
            embed.add_field(
                name="平均餘額", value=f"{stats['average_balance']:,.1f}", inline=True
            )
            embed.add_field(
                name="最高餘額", value=f"{stats['max_balance']:,}", inline=True
            )
            embed.add_field(
                name="最低餘額", value=f"{stats['min_balance']:,}", inline=True
            )
            embed.add_field(
                name="總交易次數", value=f"{stats['total_transactions']:,}", inline=True
            )

            embed.set_footer(text=f"統計更新時間: {stats.get('last_updated', 'N/A')}")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            self.logger.error(f"獲取統計失敗: {e}")
            embed = discord.Embed(
                title="❌ 錯誤",
                description="獲取統計時發生錯誤, 請稍後再試",
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    # =============================================================================
    # 錯誤處理
    # =============================================================================

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        """處理應用程式指令錯誤."""
        if isinstance(error, app_commands.MissingPermissions):
            embed = discord.Embed(
                title="❌ 權限不足",
                description="你沒有執行此指令的權限",
                color=discord.Color.red(),
            )
        elif isinstance(error, app_commands.CommandOnCooldown):
            embed = discord.Embed(
                title="⏰ 指令冷卻中",
                description=f"請等待 {error.retry_after:.1f} 秒後再試",
                color=discord.Color.orange(),
            )
        else:
            self.logger.error(f"指令錯誤: {error}")
            embed = discord.Embed(
                title="❌ 錯誤",
                description="執行指令時發生錯誤, 請稍後再試",
                color=discord.Color.red(),
            )

        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            self.logger.error(f"發送錯誤回應失敗: {e}")

async def setup(bot: commands.Bot):
    """設置 Cog."""
    await bot.add_cog(CurrencyCog(bot))
