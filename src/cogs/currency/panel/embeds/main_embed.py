"""Main Panel Embed Renderer.

主面板 Embed 渲染器,提供:
- 個人餘額顯示
- 排名資訊顯示
- 伺服器經濟統計概覽
- 快速操作指引
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import discord

logger = logging.getLogger(__name__)

# 財富等級常數
WEALTH_LEVEL_RICH = 100000  # 富豪
WEALTH_LEVEL_WEALTHY = 10000  # 富有
WEALTH_LEVEL_AVERAGE = 1000  # 一般
RANK_TOP_THREE = 3  # 前三名


class MainEmbedRenderer:
    """主面板 Embed 渲染器"""

    def __init__(
        self,
        user_balance: int,
        user_rank_info: dict[str, Any],
        guild_stats: dict[str, Any],
        user_id: int,
        guild_id: int,
    ):
        """
        初始化主面板渲染器

        Args:
            user_balance: 用戶餘額
            user_rank_info: 用戶排名資訊
            guild_stats: 伺服器統計資訊
            user_id: 用戶ID
            guild_id: 伺服器ID
        """
        self.user_balance = user_balance
        self.user_rank_info = user_rank_info or {}
        self.guild_stats = guild_stats or {}
        self.user_id = user_id
        self.guild_id = guild_id
        self.logger = logger

    async def render(self) -> discord.Embed:
        """
        渲染主面板 Embed

        Returns:
            discord.Embed: 主面板嵌入訊息
        """
        try:
            # 創建基礎嵌入
            embed = discord.Embed(
                title="💰 貨幣面板",
                description="你的個人貨幣資訊與快速操作",
                color=discord.Color.gold(),
                timestamp=datetime.utcnow(),
            )

            # 添加用戶餘額資訊
            self._add_balance_info(embed)

            # 添加排名資訊
            self._add_rank_info(embed)

            # 添加伺服器統計
            self._add_guild_stats(embed)

            # 添加操作指引
            self._add_operation_guide(embed)

            # 設置頁腳
            embed.set_footer(
                text=f"用戶 ID: {self.user_id} • 點擊下方按鈕進行操作",
                icon_url="https://cdn.discordapp.com/emojis/749358574832967832.png",
            )

            return embed

        except Exception as e:
            self.logger.error(f"渲染主面板 Embed 失敗: {e}")

            # 返回錯誤嵌入
            error_embed = discord.Embed(
                title="❌ 載入錯誤",
                description="無法載入貨幣面板資訊,請稍後再試",
                color=discord.Color.red(),
            )
            return error_embed

    def _add_balance_info(self, embed: discord.Embed):
        """添加餘額資訊"""
        try:
            # 格式化餘額顯示
            balance_display = f"**{self.user_balance:,}** 貨幣"

            # 添加餘額狀態圖示
            if self.user_balance >= WEALTH_LEVEL_RICH:
                balance_emoji = "💎"  # 富豪
            elif self.user_balance >= WEALTH_LEVEL_WEALTHY:
                balance_emoji = "💰"  # 富有
            elif self.user_balance >= WEALTH_LEVEL_AVERAGE:
                balance_emoji = "💵"  # 一般
            else:
                balance_emoji = "💸"  # 貧窮

            embed.add_field(
                name=f"{balance_emoji} 目前餘額", value=balance_display, inline=True
            )

        except Exception as e:
            self.logger.warning(f"添加餘額資訊失敗: {e}")
            embed.add_field(name="💰 目前餘額", value="載入中...", inline=True)

    def _add_rank_info(self, embed: discord.Embed):
        """添加排名資訊"""
        try:
            rank = self.user_rank_info.get("rank", 0)
            total_users = self.user_rank_info.get("total_users", 0)
            percentile = self.user_rank_info.get("percentile", 0)

            if rank > 0 and total_users > 0:
                # 添加排名圖示
                if rank <= RANK_TOP_THREE:
                    rank_emoji = ["🥇", "🥈", "🥉"][rank - 1]
                    rank_display = f"{rank_emoji} 第 **{rank}** 名"
                else:
                    rank_display = f"📊 第 **{rank}** 名"

                embed.add_field(
                    name="🏆 排名資訊",
                    value=f"{rank_display}\n"
                    + f"前 **{percentile:.1f}%** • 共 {total_users:,} 位用戶",
                    inline=True,
                )
            else:
                embed.add_field(
                    name="🏆 排名資訊",
                    value="尚未進入排行榜\n開始賺取貨幣吧!",
                    inline=True,
                )

        except Exception as e:
            self.logger.warning(f"添加排名資訊失敗: {e}")
            embed.add_field(name="🏆 排名資訊", value="載入中...", inline=True)

    def _add_guild_stats(self, embed: discord.Embed):
        """添加伺服器統計"""
        try:
            total_currency = self.guild_stats.get("total_currency", 0)
            total_users = self.guild_stats.get("total_users", 0)
            average_balance = self.guild_stats.get("average_balance", 0)

            if total_currency > 0:
                stats_text = (
                    f"💎 流通貨幣: **{total_currency:,}**\n"
                    f"👥 活躍用戶: **{total_users:,}** 位\n"
                    f"📊 平均餘額: **{average_balance:,.1f}**"
                )
            else:
                stats_text = "伺服器經濟系統正在啟動中..."

            embed.add_field(name="📈 伺服器經濟概況", value=stats_text, inline=False)

        except Exception as e:
            self.logger.warning(f"添加伺服器統計失敗: {e}")
            embed.add_field(name="📈 伺服器經濟概況", value="載入中...", inline=False)

    def _add_operation_guide(self, embed: discord.Embed):
        """添加操作指引"""
        try:
            guide_text = (
                "💸 **轉帳** - 向其他用戶轉移貨幣\n"
                "🏆 **排行榜** - 查看伺服器貨幣排名\n"
                "🔄 **重新整理** - 更新最新的資料\n"
                "❌ **關閉** - 關閉此面板"
            )

            embed.add_field(name="🎮 快速操作", value=guide_text, inline=False)

        except Exception as e:
            self.logger.warning(f"添加操作指引失敗: {e}")
            # 操作指引是靜態的,失敗時不需要特別處理
