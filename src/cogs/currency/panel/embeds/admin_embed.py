"""Admin Panel Embed Renderer.

管理員面板 Embed 渲染器,提供:
- 管理員控台概覽
- 系統狀態顯示
- 快速統計資訊
- 管理操作指引
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import discord

logger = logging.getLogger(__name__)


class AdminEmbedRenderer:
    """管理員面板 Embed 渲染器"""

    def __init__(
        self,
        guild_stats: dict[str, Any],
        total_users: int,
        total_transactions: int,
        admin_id: int,
        guild_id: int,
    ):
        """
        初始化管理員面板渲染器

        Args:
            guild_stats: 伺服器統計資訊
            total_users: 總用戶數
            total_transactions: 總交易數
            admin_id: 管理員ID
            guild_id: 伺服器ID
        """
        self.guild_stats = guild_stats or {}
        self.total_users = total_users
        self.total_transactions = total_transactions
        self.admin_id = admin_id
        self.guild_id = guild_id
        self.logger = logger

    async def render(self) -> discord.Embed:
        """
        渲染管理員面板 Embed

        Returns:
            discord.Embed: 管理員面板嵌入訊息
        """
        try:
            # 創建基礎嵌入
            embed = discord.Embed(
                title="🔒 貨幣系統管理員控台",
                description="歡迎使用貨幣系統管理介面",
                color=discord.Color.red(),
                timestamp=datetime.utcnow(),
            )

            # 添加系統概覽
            self._add_system_overview(embed)

            # 添加快速統計
            self._add_quick_stats(embed)

            # 添加管理功能指引
            self._add_admin_features(embed)

            # 添加安全提醒
            self._add_security_notice(embed)

            # 設置頁腳
            embed.set_footer(
                text=f"管理員: {self.admin_id} • 請謹慎使用管理功能",
                icon_url="https://cdn.discordapp.com/emojis/⚠️.png",
            )

            return embed

        except Exception as e:
            self.logger.error(f"渲染管理員面板 Embed 失敗: {e}")

            # 返回錯誤嵌入
            error_embed = discord.Embed(
                title="❌ 載入錯誤",
                description="無法載入管理員控台,請稍後再試",
                color=discord.Color.red(),
            )
            return error_embed

    def _add_system_overview(self, embed: discord.Embed):
        """添加系統概覽"""
        try:
            total_currency = self.guild_stats.get("total_currency", 0)
            active_users = self.guild_stats.get("total_users", 0)

            overview_text = (
                f"💎 **流通貨幣**: {total_currency:,}\n"
                f"👥 **活躍用戶**: {active_users:,} 位\n"
                f"📊 **可管理用戶**: {self.total_users:,} 位\n"
                f"📋 **交易記錄**: {self.total_transactions:,} 筆"
            )

            embed.add_field(name="📈 系統概覽", value=overview_text, inline=True)

        except Exception as e:
            self.logger.warning(f"添加系統概覽失敗: {e}")
            embed.add_field(name="📈 系統概覽", value="載入中...", inline=True)

    def _add_quick_stats(self, embed: discord.Embed):
        """添加快速統計"""
        try:
            max_balance = self.guild_stats.get("max_balance", 0)
            min_balance = self.guild_stats.get("min_balance", 0)
            average_balance = self.guild_stats.get("average_balance", 0)

            stats_text = (
                f"📊 **平均餘額**: {average_balance:,.1f}\n"
                f"⬆️ **最高餘額**: {max_balance:,}\n"
                f"⬇️ **最低餘額**: {min_balance:,}\n"
                f"🔄 **系統狀態**: 正常運行"
            )

            embed.add_field(name="📊 快速統計", value=stats_text, inline=True)

        except Exception as e:
            self.logger.warning(f"添加快速統計失敗: {e}")
            embed.add_field(name="📊 快速統計", value="載入中...", inline=True)

    def _add_admin_features(self, embed: discord.Embed):
        """添加管理功能指引"""
        try:
            features_text = (
                "👥 **用戶管理** - 查看和管理用戶餘額\n"
                "📊 **經濟統計** - 深入的經濟分析報告\n"
                "📋 **審計記錄** - 交易記錄查詢與導出\n"
                "⚡ **批量操作** - 批量修改用戶餘額\n"
                "🔄 **重新整理** - 更新最新的數據\n"
                "❌ **關閉面板** - 安全關閉管理介面"
            )

            embed.add_field(name="🛠️ 管理功能", value=features_text, inline=False)

        except Exception as e:
            self.logger.warning(f"添加管理功能指引失敗: {e}")

    def _add_security_notice(self, embed: discord.Embed):
        """添加安全提醒"""
        try:
            security_text = (
                "⚠️ **所有管理操作都會被記錄到系統日誌中**\n"
                "🔒 **請確保操作的必要性和正確性**\n"
                "📝 **建議在操作時填寫詳細的原因說明**"
            )

            embed.add_field(name="🔐 安全提醒", value=security_text, inline=False)

        except Exception as e:
            self.logger.warning(f"添加安全提醒失敗: {e}")
