"""
嵌入優化器 - 確保 Discord Embed 不超過 6000 字元限制
- 自動截斷過長的內容
- 智能分頁處理
- 保持格式美觀
"""

import logging
from typing import Any

import discord

from ..constants import ELLIPSIS_MIN_LENGTH

logger = logging.getLogger("activity_meter")


class EmbedOptimizer:
    """
    Discord Embed 優化器

    功能:
    - 檢查 embed 總字符數
    - 自動截斷過長內容
    - 智能分頁處理
    - 保持格式美觀
    """

    # Discord Embed 限制
    MAX_TOTAL_CHARS = 6000
    MAX_TITLE_CHARS = 256
    MAX_DESCRIPTION_CHARS = 4096
    MAX_FIELD_NAME_CHARS = 256
    MAX_FIELD_VALUE_CHARS = 1024
    MAX_FOOTER_CHARS = 2048
    MAX_AUTHOR_CHARS = 256
    MAX_FIELDS = 25

    def __init__(self):
        self.optimization_stats = {
            "total_optimized": 0,
            "title_truncated": 0,
            "description_truncated": 0,
            "fields_truncated": 0,
            "fields_removed": 0,
        }

    def optimize_embed(self, embed: discord.Embed) -> discord.Embed:
        """
        優化 embed 以符合 Discord 限制

        Args:
            embed: 要優化的 embed

        Returns:
            discord.Embed: 優化後的 embed
        """
        # 創建新的 embed 副本
        optimized = discord.Embed(
            title=embed.title,
            description=embed.description,
            color=embed.color,
            url=embed.url,
            timestamp=embed.timestamp,
        )

        # 複製作者信息
        if embed.author:
            optimized.set_author(
                name=self._truncate_text(embed.author.name, self.MAX_AUTHOR_CHARS),
                url=embed.author.url,
                icon_url=embed.author.icon_url,
            )

        # 複製縮圖和圖片
        if embed.thumbnail:
            optimized.set_thumbnail(url=embed.thumbnail.url)
        if embed.image:
            optimized.set_image(url=embed.image.url)

        # 優化標題
        if embed.title:
            optimized.title = self._truncate_text(embed.title, self.MAX_TITLE_CHARS)
            if len(embed.title) > self.MAX_TITLE_CHARS:
                self.optimization_stats["title_truncated"] += 1

        # 優化描述
        if embed.description:
            optimized.description = self._truncate_text(
                embed.description, self.MAX_DESCRIPTION_CHARS
            )
            if len(embed.description) > self.MAX_DESCRIPTION_CHARS:
                self.optimization_stats["description_truncated"] += 1

        # 優化欄位
        total_char_count = self._count_embed_chars(optimized)
        fields_added = 0

        for field in embed.fields:
            if fields_added >= self.MAX_FIELDS:
                self.optimization_stats["fields_removed"] += 1
                continue

            # 優化欄位名稱和值
            optimized_name = self._truncate_text(field.name, self.MAX_FIELD_NAME_CHARS)
            optimized_value = self._truncate_text(
                field.value, self.MAX_FIELD_VALUE_CHARS
            )

            # 檢查添加此欄位後是否會超過總字符限制
            field_char_count = len(optimized_name) + len(optimized_value)

            if total_char_count + field_char_count <= self.MAX_TOTAL_CHARS:
                optimized.add_field(
                    name=optimized_name, value=optimized_value, inline=field.inline
                )
                total_char_count += field_char_count
                fields_added += 1

                if (
                    len(field.name) > self.MAX_FIELD_NAME_CHARS
                    or len(field.value) > self.MAX_FIELD_VALUE_CHARS
                ):
                    self.optimization_stats["fields_truncated"] += 1
            else:
                self.optimization_stats["fields_removed"] += 1

        # 優化 footer
        if embed.footer:
            footer_text = self._truncate_text(embed.footer.text, self.MAX_FOOTER_CHARS)
            optimized.set_footer(text=footer_text, icon_url=embed.footer.icon_url)

        # 最終字符數檢查
        final_char_count = self._count_embed_chars(optimized)
        if final_char_count > self.MAX_TOTAL_CHARS:
            logger.warning(
                f"Embed 仍然超過字符限制: {final_char_count}/{self.MAX_TOTAL_CHARS}"
            )
            # 如果仍然超過限制, 進行更激進的截斷
            optimized = self._aggressive_truncate(optimized)

        if self._count_embed_chars(embed) > self.MAX_TOTAL_CHARS:
            self.optimization_stats["total_optimized"] += 1
            logger.info(
                f"Embed 優化完成: {self._count_embed_chars(embed)} -> {self._count_embed_chars(optimized)} 字符"
            )

        return optimized

    def create_paginated_embeds(
        self,
        content: list[dict[str, Any]],
        base_embed: discord.Embed,
        items_per_page: int = 10,
    ) -> list[discord.Embed]:
        """
        創建分頁 embed 列表

        Args:
            content: 內容列表
            base_embed: 基礎 embed
            items_per_page: 每頁項目數

        Returns:
            List[discord.Embed]: 分頁 embed 列表
        """
        pages = []
        total_pages = (len(content) + items_per_page - 1) // items_per_page

        for page_num in range(total_pages):
            start_idx = page_num * items_per_page
            end_idx = min(start_idx + items_per_page, len(content))
            page_content = content[start_idx:end_idx]

            # 創建當前頁面的 embed
            page_embed = discord.Embed(
                title=f"{base_embed.title} (第 {page_num + 1}/{total_pages} 頁)",
                description=base_embed.description,
                color=base_embed.color,
            )

            # 複製基礎 embed 的其他屬性
            if base_embed.author:
                page_embed.set_author(
                    name=base_embed.author.name,
                    url=base_embed.author.url,
                    icon_url=base_embed.author.icon_url,
                )

            if base_embed.thumbnail:
                page_embed.set_thumbnail(url=base_embed.thumbnail.url)

            # 添加內容到頁面
            for item in page_content:
                page_embed.add_field(
                    name=item.get("name", "項目"),
                    value=item.get("value", ""),
                    inline=item.get("inline", True),
                )

            # 添加頁面信息到 footer
            footer_text = f"第 {page_num + 1} 頁, 共 {total_pages} 頁"
            if base_embed.footer:
                footer_text = f"{base_embed.footer.text} | {footer_text}"

            page_embed.set_footer(text=footer_text)

            # 優化當前頁面
            optimized_page = self.optimize_embed(page_embed)
            pages.append(optimized_page)

        return pages

    def _truncate_text(self, text: str | None, max_length: int) -> str:
        """
        截斷文字並添加省略號

        Args:
            text: 要截斷的文字
            max_length: 最大長度

        Returns:
            str: 截斷後的文字
        """
        if not text:
            return ""

        if len(text) <= max_length:
            return text

        # 留出省略號的空間
        if max_length <= ELLIPSIS_MIN_LENGTH:
            return text[:max_length]

        return text[: max_length - 3] + "..."

    def _count_embed_chars(self, embed: discord.Embed) -> int:
        """
        計算 embed 的總字符數

        Args:
            embed: 要計算的 embed

        Returns:
            int: 總字符數
        """
        char_count = 0

        # 標題
        if embed.title:
            char_count += len(embed.title)

        # 描述
        if embed.description:
            char_count += len(embed.description)

        # 作者
        if embed.author and embed.author.name:
            char_count += len(embed.author.name)

        # 欄位
        for field in embed.fields:
            char_count += len(field.name) + len(field.value)

        # Footer
        if embed.footer and embed.footer.text:
            char_count += len(embed.footer.text)

        return char_count

    def _aggressive_truncate(self, embed: discord.Embed) -> discord.Embed:
        """
        激進截斷 embed 內容

        Args:
            embed: 要截斷的 embed

        Returns:
            discord.Embed: 截斷後的 embed
        """
        # 如果仍然超過限制, 移除一些欄位
        while self._count_embed_chars(embed) > self.MAX_TOTAL_CHARS and embed.fields:
            embed.remove_field(-1)  # 移除最後一個欄位
            self.optimization_stats["fields_removed"] += 1

        # 如果還是超過, 截斷描述
        if self._count_embed_chars(embed) > self.MAX_TOTAL_CHARS and embed.description:
            available_chars = self.MAX_TOTAL_CHARS - (
                self._count_embed_chars(embed) - len(embed.description)
            )
            embed.description = self._truncate_text(
                embed.description, max(available_chars, 100)
            )
            self.optimization_stats["description_truncated"] += 1

        return embed

    def get_optimization_stats(self) -> dict[str, int]:
        """獲取優化統計信息"""
        return self.optimization_stats.copy()

    def reset_stats(self) -> None:
        """重置優化統計信息"""
        for key in self.optimization_stats:
            self.optimization_stats[key] = 0

    def validate_embed(self, embed: discord.Embed) -> dict[str, Any]:
        """
        驗證 embed 是否符合 Discord 限制

        Args:
            embed: 要驗證的 embed

        Returns:
            Dict: 驗證結果
        """
        issues = []
        char_count = self._count_embed_chars(embed)

        if char_count > self.MAX_TOTAL_CHARS:
            issues.append(f"總字符數超過限制: {char_count}/{self.MAX_TOTAL_CHARS}")

        if embed.title and len(embed.title) > self.MAX_TITLE_CHARS:
            issues.append(f"標題過長: {len(embed.title)}/{self.MAX_TITLE_CHARS}")

        if embed.description and len(embed.description) > self.MAX_DESCRIPTION_CHARS:
            issues.append(
                f"描述過長: {len(embed.description)}/{self.MAX_DESCRIPTION_CHARS}"
            )

        if len(embed.fields) > self.MAX_FIELDS:
            issues.append(f"欄位過多: {len(embed.fields)}/{self.MAX_FIELDS}")

        for i, field in enumerate(embed.fields):
            if len(field.name) > self.MAX_FIELD_NAME_CHARS:
                issues.append(
                    f"欄位 {i + 1} 名稱過長: {len(field.name)}/{self.MAX_FIELD_NAME_CHARS}"
                )
            if len(field.value) > self.MAX_FIELD_VALUE_CHARS:
                issues.append(
                    f"欄位 {i + 1} 值過長: {len(field.value)}/{self.MAX_FIELD_VALUE_CHARS}"
                )

        if (
            embed.footer
            and embed.footer.text
            and len(embed.footer.text) > self.MAX_FOOTER_CHARS
        ):
            issues.append(
                f"Footer 過長: {len(embed.footer.text)}/{self.MAX_FOOTER_CHARS}"
            )

        return {
            "is_valid": len(issues) == 0,
            "char_count": char_count,
            "issues": issues,
        }


# 全局實例
embed_optimizer = EmbedOptimizer()


# 便捷函數
def optimize_embed(embed: discord.Embed) -> discord.Embed:
    """優化 embed 的便捷函數"""
    return embed_optimizer.optimize_embed(embed)


def create_paginated_embeds(
    content: list[dict[str, Any]], base_embed: discord.Embed, items_per_page: int = 10
) -> list[discord.Embed]:
    """創建分頁 embed 的便捷函數"""
    return embed_optimizer.create_paginated_embeds(content, base_embed, items_per_page)


def validate_embed(embed: discord.Embed) -> dict[str, Any]:
    """驗證 embed 的便捷函數"""
    return embed_optimizer.validate_embed(embed)
