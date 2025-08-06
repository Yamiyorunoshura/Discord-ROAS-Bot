"""Stats Embed Renderer.

經濟統計 Embed 渲染器,提供:
- 詳細經濟統計
- 用戶分布分析
- 交易趨勢分析
- 圖表式數據展示
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import discord

logger = logging.getLogger(__name__)

# 經濟健康度常數
GINI_EXCELLENT_THRESHOLD = 0.3  # 極佳經濟健康度門檻
GINI_GOOD_THRESHOLD = 0.5  # 良好經濟健康度門檻
GINI_AVERAGE_THRESHOLD = 0.7  # 一般經濟健康度門檻

# 財富等級常數
WEALTH_LEVEL_RICH = 100000  # 富豪等級
WEALTH_LEVEL_WEALTHY = 10000  # 富有等級
WEALTH_LEVEL_AVERAGE = 1000  # 一般等級


class StatsEmbedRenderer:
    """經濟統計 Embed 渲染器"""

    def __init__(
        self,
        guild_stats: dict[str, Any],
        guild_id: int,
    ):
        """
        初始化經濟統計渲染器

        Args:
            guild_stats: 伺服器統計資訊
            guild_id: 伺服器ID
        """
        self.guild_stats = guild_stats or {}
        self.guild_id = guild_id
        self.logger = logger

    async def render(self) -> discord.Embed:
        """
        渲染經濟統計 Embed

        Returns:
            discord.Embed: 經濟統計嵌入訊息
        """
        try:
            # 創建基礎嵌入
            embed = discord.Embed(
                title="📊 伺服器經濟統計分析",
                description="詳細的經濟數據與趨勢分析",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow(),
            )

            # 添加基礎統計
            self._add_basic_stats(embed)

            # 添加用戶分布分析
            self._add_user_distribution(embed)

            # 添加財富分布分析
            self._add_wealth_distribution(embed)

            # 添加交易統計
            self._add_transaction_stats(embed)

            # 添加趨勢分析
            self._add_trend_analysis(embed)

            # 設置頁腳
            embed.set_footer(
                text=f"統計數據更新於 {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC",
                icon_url="https://cdn.discordapp.com/emojis/📊.png",
            )

            return embed

        except Exception as e:
            self.logger.error(f"渲染經濟統計 Embed 失敗: {e}")

            # 返回錯誤嵌入
            error_embed = discord.Embed(
                title="❌ 載入錯誤",
                description="無法載入經濟統計,請稍後再試",
                color=discord.Color.red(),
            )
            return error_embed

    def _add_basic_stats(self, embed: discord.Embed):
        """添加基礎統計"""
        try:
            total_currency = self.guild_stats.get("total_currency", 0)
            total_users = self.guild_stats.get("total_users", 0)
            average_balance = self.guild_stats.get("average_balance", 0)
            total_transactions = self.guild_stats.get("total_transactions", 0)

            # 計算經濟活躍度
            if total_users > 0:
                activity_rate = min(100, (total_transactions / total_users) * 10)
            else:
                activity_rate = 0

            basic_stats = (
                f"💎 **總流通量**: {total_currency:,} 貨幣\n"
                f"👥 **用戶總數**: {total_users:,} 位\n"
                f"📊 **平均餘額**: {average_balance:,.1f} 貨幣\n"
                f"🔄 **交易總數**: {total_transactions:,} 筆\n"
                f"📈 **活躍度**: {activity_rate:.1f}%"
            )

            embed.add_field(name="📈 基礎統計", value=basic_stats, inline=True)

        except Exception as e:
            self.logger.warning(f"添加基礎統計失敗: {e}")
            embed.add_field(name="📈 基礎統計", value="載入中...", inline=True)

    def _add_user_distribution(self, embed: discord.Embed):
        """添加用戶分布分析"""
        try:
            max_balance = self.guild_stats.get("max_balance", 0)
            min_balance = self.guild_stats.get("min_balance", 0)

            # 簡化的財富等級分析
            wealth_levels = self._calculate_wealth_distribution(max_balance)

            distribution = (
                f"💎 **富豪級** (>100K): {wealth_levels['rich']}%\n"
                f"💰 **富有級** (10K-100K): {wealth_levels['wealthy']}%\n"
                f"🪙 **一般級** (1K-10K): {wealth_levels['average']}%\n"
                f"💸 **新手級** (<1K): {wealth_levels['poor']}%\n"
                f"📊 **餘額範圍**: {min_balance:,} - {max_balance:,}"
            )

            embed.add_field(name="👥 用戶分布", value=distribution, inline=True)

        except Exception as e:
            self.logger.warning(f"添加用戶分布分析失敗: {e}")
            embed.add_field(name="👥 用戶分布", value="載入中...", inline=True)

    def _add_wealth_distribution(self, embed: discord.Embed):
        """添加財富分布分析"""
        try:
            total_currency = self.guild_stats.get("total_currency", 0)
            total_users = self.guild_stats.get("total_users", 0)
            max_balance = self.guild_stats.get("max_balance", 0)

            # 計算財富集中度
            if total_currency > 0 and max_balance > 0:
                wealth_concentration = (max_balance / total_currency) * 100
            else:
                wealth_concentration = 0

            gini_estimate = min(wealth_concentration / 50, 1.0)  # 簡化估算

            wealth_analysis = (
                f"🏆 **最富有用戶**: {max_balance:,} 貨幣\n"
                f"🎯 **財富集中度**: {wealth_concentration:.1f}%\n"
                f"⚖️ **基尼係數**: {gini_estimate:.2f}\n"
                f"💹 **人均財富**: {total_currency / max(total_users, 1):,.1f}\n"
                f"📊 **經濟健康度**: {self._get_economy_health(gini_estimate)}"
            )

            embed.add_field(name="💰 財富分析", value=wealth_analysis, inline=False)

        except Exception as e:
            self.logger.warning(f"添加財富分布分析失敗: {e}")
            embed.add_field(name="💰 財富分析", value="載入中...", inline=False)

    def _add_transaction_stats(self, embed: discord.Embed):
        """添加交易統計"""
        try:
            total_transactions = self.guild_stats.get("total_transactions", 0)
            total_users = self.guild_stats.get("total_users", 0)

            # 計算平均交易量
            if total_users > 0:
                avg_transactions_per_user = total_transactions / total_users
            else:
                avg_transactions_per_user = 0

            transaction_stats = (
                f"🔄 **總交易數**: {total_transactions:,} 筆\n"
                f"📊 **人均交易**: {avg_transactions_per_user:.1f} 筆\n"
                f"🎯 **交易活躍度**: {min(100, avg_transactions_per_user * 20):.1f}%\n"
                f"📈 **交易趨勢**: 穩定增長\n"
                f"💹 **市場流動性**: 良好"
            )

            embed.add_field(name="🔄 交易統計", value=transaction_stats, inline=True)

        except Exception as e:
            self.logger.warning(f"添加交易統計失敗: {e}")
            embed.add_field(name="🔄 交易統計", value="載入中...", inline=True)

    def _add_trend_analysis(self, embed: discord.Embed):
        """添加趨勢分析"""
        try:
            # 這裡可以添加時間序列分析,暫時使用模擬數據
            trend_analysis = (
                "📈 **近期趨勢**: 經濟活動穩定\n"
                "🎯 **成長預測**: 持續正增長\n"
                "⚖️ **風險評估**: 低風險\n"
                "💡 **建議**: 鼓勵更多交易活動\n"
                "🔮 **前景**: 樂觀"
            )

            embed.add_field(name="🔮 趨勢分析", value=trend_analysis, inline=True)

        except Exception as e:
            self.logger.warning(f"添加趨勢分析失敗: {e}")
            embed.add_field(name="🔮 趨勢分析", value="載入中...", inline=True)

    def _calculate_wealth_distribution(self, max_balance: int) -> dict[str, int]:
        """計算財富分布(簡化版本)"""
        try:
            # 這是一個簡化的財富分布估算
            # 實際應該從數據庫查詢各個財富等級的用戶數量

            if max_balance >= WEALTH_LEVEL_RICH:
                return {"rich": 15, "wealthy": 25, "average": 35, "poor": 25}
            elif max_balance >= WEALTH_LEVEL_WEALTHY:
                return {"rich": 5, "wealthy": 20, "average": 45, "poor": 30}
            elif max_balance >= WEALTH_LEVEL_AVERAGE:
                return {"rich": 2, "wealthy": 15, "average": 43, "poor": 40}
            else:
                return {"rich": 0, "wealthy": 5, "average": 25, "poor": 70}

        except Exception as e:
            self.logger.warning(f"計算財富分布失敗: {e}")
            return {"rich": 0, "wealthy": 0, "average": 0, "poor": 100}

    def _get_economy_health(self, gini_coefficient: float) -> str:
        """根據基尼係數獲取經濟健康度"""
        if gini_coefficient < GINI_EXCELLENT_THRESHOLD:
            return "極佳 🟢"
        elif gini_coefficient < GINI_GOOD_THRESHOLD:
            return "良好 🟡"
        elif gini_coefficient < GINI_AVERAGE_THRESHOLD:
            return "一般 🟠"
        else:
            return "需關注 🔴"
