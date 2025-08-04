"""Panel button components.

政府面板按鈕組件,提供統一的按鈕樣式和行為.
"""

from __future__ import annotations

import discord


class PanelButtons:
    """面板按鈕工廠類別."""

    @staticmethod
    def create_refresh_button() -> discord.ui.Button:
        """創建重新整理按鈕."""
        return discord.ui.Button(
            label="🔄 重新整理",
            style=discord.ButtonStyle.secondary,
            custom_id="roas_gov_refresh",
            row=0
        )

    @staticmethod
    def create_search_button() -> discord.ui.Button:
        """創建搜尋按鈕."""
        return discord.ui.Button(
            label="🔍 搜尋",
            style=discord.ButtonStyle.primary,
            custom_id="roas_gov_search",
            row=0
        )

    @staticmethod
    def create_filter_button() -> discord.ui.Button:
        """創建篩選按鈕."""
        return discord.ui.Button(
            label="📋 篩選",
            style=discord.ButtonStyle.secondary,
            custom_id="roas_gov_filter",
            row=0
        )

    @staticmethod
    def create_prev_button() -> discord.ui.Button:
        """創建上一頁按鈕."""
        return discord.ui.Button(
            label="◀️ 上一頁",
            style=discord.ButtonStyle.secondary,
            custom_id="roas_gov_prev",
            row=1
        )

    @staticmethod
    def create_next_button() -> discord.ui.Button:
        """創建下一頁按鈕."""
        return discord.ui.Button(
            label="下一頁 ▶️",
            style=discord.ButtonStyle.secondary,
            custom_id="roas_gov_next",
            row=1
        )

    @staticmethod
    def create_department_select_button(department_id: str, department_name: str) -> discord.ui.Button:
        """創建部門選擇按鈕."""
        return discord.ui.Button(
            label=f"📁 {department_name}",
            style=discord.ButtonStyle.secondary,
            custom_id=f"roas_gov_select_{department_id}",
            row=2
        )
