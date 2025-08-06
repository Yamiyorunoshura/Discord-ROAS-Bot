"""
Discord UI 佈局管理器
- 處理 Discord UI 佈局限制
- 優化組件排列
- 提供佈局錯誤處理
"""

import contextlib
import logging
from typing import Any

import discord

logger = logging.getLogger("activity_meter")


class DiscordUILayoutManager:
    """
    Discord UI 佈局管理器

    處理 Discord UI 的佈局限制:
    - 每行最多 5 個組件
    - 最多 5 行
    - 總共最多 25 個組件
    """

    # 類屬性定義
    max_components_per_row = 5
    max_rows = 5
    max_total_components = 25

    def __init__(self):
        pass

    def check_layout_compatibility(self, components: list[discord.ui.Item]) -> bool:
        """
        檢查佈局兼容性

        Args:
            components: 組件列表

        Returns:
            bool: 是否兼容
        """
        # 檢查組件總數
        if len(components) > DiscordUILayoutManager.max_total_components:
            logger.warning(
                f"組件總數超過限制: {len(components)} > {DiscordUILayoutManager.max_total_components}"
            )
            return False

        # 檢查每行的組件數量
        row_counts = {}
        for component in components:
            row = getattr(component, "row", 0)
            row_counts[row] = row_counts.get(row, 0) + 1
            if row_counts[row] > DiscordUILayoutManager.max_components_per_row:
                logger.warning(
                    f"第 {row} 行組件數量超過限制: {row_counts[row]} > {DiscordUILayoutManager.max_components_per_row}"
                )
                return False

        # 檢查行數是否超過限制
        if row_counts and max(row_counts.keys()) >= DiscordUILayoutManager.max_rows:
            logger.warning(
                f"行數超過限制: {max(row_counts.keys())} >= {DiscordUILayoutManager.max_rows}"
            )
            return False

        return True

    def optimize_layout(
        self, components: list[discord.ui.Item]
    ) -> list[discord.ui.Item]:
        """
        優化佈局 - 改進版本

        Args:
            components: 原始組件列表

        Returns:
            List[discord.ui.Item]: 優化後的組件列表
        """
        if self.check_layout_compatibility(components):
            return components

        logger.info("開始優化佈局...")

        # 按行分組
        rows = {}
        for component in components:
            row = getattr(component, "row", 0)
            if row not in rows:
                rows[row] = []
            rows[row].append(component)

        # 重新分配組件
        optimized_components = []
        current_row = 0

        for row_num in sorted(rows.keys()):
            row_components = rows[row_num]

            # 如果當前行組件數量超過限制,需要重新分配
            if len(row_components) > DiscordUILayoutManager.max_components_per_row:
                # 將超出的組件移到下一行
                for i, component in enumerate(row_components):
                    if i < DiscordUILayoutManager.max_components_per_row:
                        # 保持在當前行
                        component.row = current_row
                        optimized_components.append(component)
                    else:
                        # 移到下一行
                        next_row = current_row + 1

                        # 檢查下一行是否還有空間
                        if next_row < DiscordUILayoutManager.max_rows:
                            component.row = next_row
                            optimized_components.append(component)
                        else:
                            # 如果沒有空間,跳過這個組件
                            logger.warning(f"組件 {component} 無法放置,跳過")

                current_row = next_row + 1
            else:
                # 當前行組件數量正常,直接添加
                for component in row_components:
                    component.row = current_row
                    optimized_components.append(component)
                current_row += 1

        logger.info(f"佈局優化完成,組件數量: {len(optimized_components)}")
        return optimized_components

    def _create_simplified_layout(
        self, components: list[discord.ui.Item]
    ) -> list[discord.ui.Item]:
        """
        創建簡化佈局 - 當優化失敗時的備用方案

        Args:
            components: 原始組件列表

        Returns:
            List[discord.ui.Item]: 簡化後的組件列表
        """
        logger.info("創建簡化佈局...")

        # 只保留最重要的組件
        essential_components = []
        current_row = 0

        for component in components:
            # 優先保留頁面選擇器和關閉按鈕
            if (
                isinstance(component, discord.ui.Select) or hasattr(component, "label")
            ) and current_row < DiscordUILayoutManager.max_rows:
                component.row = current_row
                essential_components.append(component)
                current_row += 1

        logger.info(f"簡化佈局完成,組件數量: {len(essential_components)}")
        return essential_components

    def get_layout_info(self, components: list[discord.ui.Item]) -> dict[str, Any]:
        """
        獲取佈局信息

        Args:
            components: 組件列表

        Returns:
            Dict[str, Any]: 佈局信息
        """
        row_counts = {}
        total_components = len(components)

        for component in components:
            row = getattr(component, "row", 0)
            row_counts[row] = row_counts.get(row, 0) + 1

        return {
            "total_components": total_components,
            "row_counts": row_counts,
            "max_components_per_row": DiscordUILayoutManager.max_components_per_row,
            "max_rows": DiscordUILayoutManager.max_rows,
            "max_total_components": DiscordUILayoutManager.max_total_components,
            "is_compatible": self.check_layout_compatibility(components),
        }


class UILayoutErrorHandler:
    """
    UI 佈局錯誤處理器
    """

    def __init__(self):
        self.error_codes = {
            "E203": "UI 佈局錯誤:組件數量超過限制",
            "E204": "UI 佈局錯誤:行寬度超過限制",
            "E205": "UI 佈局錯誤:總組件數超過限制",
        }

    def classify_error(self, error: Exception) -> str:
        """
        分類錯誤類型

        Args:
            error: 錯誤對象

        Returns:
            str: 錯誤類型
        """
        error_message = str(error).lower()

        if "too many components" in error_message:
            return "component_limit"
        elif "item would not fit at row" in error_message:
            return "discord_ui_limit"
        else:
            return "unknown"

    async def handle_layout_error(
        self, interaction: discord.Interaction, error: Exception
    ):
        """
        處理佈局錯誤 - 改進版本

        Args:
            interaction: Discord 互動
            error: 錯誤對象
        """
        try:
            error_message = str(error)

            if "item would not fit at row" in error_message:
                # UI 佈局錯誤
                logger.error(f"檢測到佈局錯誤: {error_message}")
                embed = self.create_layout_error_embed()
                await interaction.response.send_message(embed=embed, ephemeral=True)

                # 嘗試自動恢復
                await self.attempt_layout_recovery(interaction)
            elif "too many components" in error_message:
                # 組件數量過多錯誤
                logger.error(f"檢測到組件數量錯誤: {error_message}")
                embed = self.create_component_count_error_embed()
                await interaction.response.send_message(embed=embed, ephemeral=True)

                # 嘗試自動恢復
                await self.attempt_layout_recovery(interaction)
            else:
                # 其他錯誤
                logger.error(f"檢測到一般錯誤: {error_message}")
                await self.handle_general_error(interaction, error)

        except Exception as e:
            # 如果錯誤處理本身失敗
            logger.error(f"錯誤處理失敗: {e}")
            await self.send_fallback_error(interaction)

    async def attempt_layout_recovery(self, interaction: discord.Interaction):
        """
        嘗試佈局恢復 - 改進版本

        Args:
            interaction: Discord 互動
        """
        try:
            # 發送恢復開始訊息
            embed = discord.Embed(
                title="正在修復佈局",
                description="系統正在自動調整組件佈局,請稍候...",
                color=discord.Color.orange(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

            # 這裡可以實現更詳細的自動恢復邏輯
            # 例如:重新創建面板、調整組件佈局等
            # 目前先發送提示訊息,實際恢復邏輯在面板類中實現

        except Exception as e:
            logger.error(f"佈局恢復失敗: {e}")
            # 如果恢復失敗,發送錯誤訊息
            try:
                error_embed = discord.Embed(
                    title="佈局恢復失敗",
                    description="無法自動修復佈局問題,請重新開啟面板",
                    color=discord.Color.red(),
                )
                await interaction.followup.send(embed=error_embed, ephemeral=True)
            except Exception:
                pass

    def create_layout_error_embed(self) -> discord.Embed:
        """
        創建佈局錯誤嵌入訊息

        Returns:
            discord.Embed: 錯誤嵌入訊息
        """
        embed = discord.Embed(
            title="UI 佈局錯誤",
            description="面板組件數量超過 Discord 限制,正在嘗試自動修復...",
            color=discord.Color.red(),
        )
        embed.add_field(name="錯誤代碼", value="E203/E204", inline=True)
        embed.add_field(name="解決方案", value="系統將自動調整組件佈局", inline=True)
        embed.set_footer(text="如果問題持續,請聯繫管理員")
        return embed

    def create_component_count_error_embed(self) -> discord.Embed:
        """
        創建組件數量錯誤嵌入訊息

        Returns:
            discord.Embed: 錯誤嵌入訊息
        """
        embed = discord.Embed(
            title="組件數量錯誤",
            description="面板組件數量超過 Discord 限制(最多25個組件),正在嘗試自動修復...",
            color=discord.Color.red(),
        )
        embed.add_field(name="錯誤代碼", value="E205", inline=True)
        embed.add_field(name="解決方案", value="系統將自動簡化組件佈局", inline=True)
        embed.set_footer(text="如果問題持續,請聯繫管理員")
        return embed

    async def handle_general_error(
        self, interaction: discord.Interaction, error: Exception
    ):
        """
        處理一般錯誤

        Args:
            interaction: Discord 互動
            error: 錯誤對象
        """
        embed = discord.Embed(
            title="發生錯誤",
            description=f"產生未預期的錯誤:{error!s}",
            color=discord.Color.red(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def send_fallback_error(self, interaction: discord.Interaction):
        """
        發送後備錯誤訊息

        Args:
            interaction: Discord 互動
        """
        with contextlib.suppress(Exception):
            await interaction.response.send_message(
                "發生錯誤,請稍後再試", ephemeral=True
            )
