"""Leaderboard Embed Renderer.

排行榜 Embed 渲染器,提供:
- 分頁排行榜顯示
- 用戶排名高亮
- 分頁導航資訊
- 排行榜統計
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import discord

# 排名常數
GOLD_MEDAL_RANK = 1
SILVER_MEDAL_RANK = 2
BRONZE_MEDAL_RANK = 3
MEDAL_TIER_MAX_RANK = 10
LEADERBOARD_SPLIT_THRESHOLD = 5

logger = logging.getLogger(__name__)

class LeaderboardEmbedRenderer:
    """排行榜 Embed 渲染器"""

    def __init__(
        self,
        leaderboard_data: dict[str, Any],
        current_page: int,
        per_page: int,
        user_id: int,
        guild_id: int,
    ):
        """
        初始化排行榜渲染器

        Args:
            leaderboard_data: 排行榜數據
            current_page: 當前頁面(從0開始)
            per_page: 每頁顯示數量
            user_id: 用戶ID(用於高亮)
            guild_id: 伺服器ID
        """
        self.leaderboard_data = leaderboard_data or {}
        self.current_page = current_page
        self.per_page = per_page
        self.user_id = user_id
        self.guild_id = guild_id
        self.logger = logger

    async def render(self) -> discord.Embed:
        """
        渲染排行榜 Embed

        Returns:
            discord.Embed: 排行榜嵌入訊息
        """
        try:
            entries = self.leaderboard_data.get("entries", [])
            total_count = self.leaderboard_data.get("total_count", 0)

            # 計算頁面資訊
            total_pages = max(1, (total_count + self.per_page - 1) // self.per_page)
            page_display = self.current_page + 1

            # 創建基礎嵌入
            embed = discord.Embed(
                title="🏆 伺服器貨幣排行榜",
                description=f"第 {page_display}/{total_pages} 頁 • 共 {total_count:,} 位用戶",
                color=discord.Color.gold(),
                timestamp=datetime.utcnow()
            )

            if not entries:
                # 空排行榜
                embed.add_field(
                    name="📝 排行榜",
                    value="還沒有用戶擁有貨幣\n快開始賺取第一筆貨幣吧!",
                    inline=False
                )
            else:
                # 渲染排行榜條目
                await self._add_leaderboard_entries(embed, entries)

            # 添加導航提示
            self._add_navigation_info(embed, total_pages)

            # 設置頁腳
            embed.set_footer(
                text="使用下方按鈕導航 • 點擊「我的排名」快速跳轉",
                icon_url="https://cdn.discordapp.com/emojis/749358574832967832.png"
            )

            return embed

        except Exception as e:
            self.logger.error(f"渲染排行榜 Embed 失敗: {e}")

            # 返回錯誤嵌入
            error_embed = discord.Embed(
                title="❌ 載入錯誤",
                description="無法載入排行榜資訊,請稍後再試",
                color=discord.Color.red()
            )
            return error_embed

    async def _add_leaderboard_entries(self, embed: discord.Embed, entries: list[dict]):
        """添加排行榜條目"""
        try:
            rank_lines = []

            for entry in entries:
                rank = entry.get("rank", 0)
                user_id = entry.get("user_id", 0)
                balance = entry.get("balance", 0)

                # 獲取排名圖示
                rank_emoji = self._get_rank_emoji(rank)

                # 格式化用戶顯示名稱
                user_display = await self._get_user_display_name(user_id)

                if user_id == self.user_id:
                    user_display = f"**{user_display}** ⭐"  # 高亮當前用戶

                # 格式化餘額
                balance_display = f"{balance:,} 貨幣"

                # 組合排名行
                rank_line = f"{rank_emoji} {user_display}: {balance_display}"
                rank_lines.append(rank_line)

            # 將排行榜條目添加到嵌入
            if rank_lines:
                # 如果條目太多,分成兩個欄位
                if len(rank_lines) > LEADERBOARD_SPLIT_THRESHOLD:
                    mid_point = len(rank_lines) // 2

                    embed.add_field(
                        name="📊 排名 (上半部)",
                        value="\n".join(rank_lines[:mid_point]),
                        inline=True
                    )

                    embed.add_field(
                        name="📊 排名 (下半部)",
                        value="\n".join(rank_lines[mid_point:]),
                        inline=True
                    )
                else:
                    embed.add_field(
                        name="📊 排名",
                        value="\n".join(rank_lines),
                        inline=False
                    )

        except Exception as e:
            self.logger.error(f"添加排行榜條目失敗: {e}")
            embed.add_field(
                name="📊 排名",
                value="載入排行榜時發生錯誤",
                inline=False
            )

    def _get_rank_emoji(self, rank: int) -> str:
        """獲取排名圖示"""
        if rank == GOLD_MEDAL_RANK:
            return "🥇"
        elif rank == SILVER_MEDAL_RANK:
            return "🥈"
        elif rank == BRONZE_MEDAL_RANK:
            return "🥉"
        elif rank <= MEDAL_TIER_MAX_RANK:
            return "🏅"
        else:
            return f"**{rank}.**"

    async def _get_user_display_name(self, user_id: int) -> str:
        """獲取用戶顯示名稱"""
        try:
            # 這裡應該通過某種方式獲取用戶名稱
            # 由於沒有直接的 bot 實例,我們使用簡化的顯示
            return f"用戶 {user_id}"

        except Exception as e:
            self.logger.warning(f"獲取用戶 {user_id} 顯示名稱失敗: {e}")
            return f"用戶 {user_id}"

    def _add_navigation_info(self, embed: discord.Embed, total_pages: int):
        """添加導航資訊"""
        try:
            # 計算顯示範圍
            start_rank = self.current_page * self.per_page + 1
            end_rank = min(
                (self.current_page + 1) * self.per_page,
                self.leaderboard_data.get("total_count", 0)
            )

            nav_info = f"📍 顯示排名 {start_rank}-{end_rank}\n"

            # 添加導航提示
            if total_pages > 1:
                nav_info += "⬅️ 上一頁 | 下一頁 ➡️\n"

            nav_info += "📊 點擊「我的排名」快速定位"

            embed.add_field(
                name="🧭 導航資訊",
                value=nav_info,
                inline=False
            )

        except Exception as e:
            self.logger.warning(f"添加導航資訊失敗: {e}")
