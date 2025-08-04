"""Transfer Modal Component.

用戶轉帳 Modal 組件,提供:
- 收款人選擇
- 轉帳金額輸入
- 轉帳原因輸入(可選)
- 表單驗證
- 即時面板更新
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord.ui import Modal, TextInput

from src.cogs.currency.database import ConcurrencyError, InsufficientFundsError

if TYPE_CHECKING:
    from src.cogs.currency.service.currency_service import CurrencyService

    from ..user_view import CurrencyPanelView

logger = logging.getLogger(__name__)

class TransferModal(Modal):
    """用戶轉帳 Modal"""

    def __init__(
        self,
        currency_service: CurrencyService,
        currency_panel_view: CurrencyPanelView,
        guild_id: int,
        from_user_id: int,
    ):
        """
        初始化轉帳 Modal

        Args:
            currency_service: 貨幣服務實例
            currency_panel_view: 貨幣面板視圖實例
            guild_id: 伺服器ID
            from_user_id: 轉出用戶ID
        """
        super().__init__(
            title="💸 貨幣轉帳",
            timeout=300.0,
            custom_id="roas_currency_transfer_modal"
        )

        self.currency_service = currency_service
        self.currency_panel_view = currency_panel_view
        self.guild_id = guild_id
        self.from_user_id = from_user_id
        self.logger = logger

        # 添加輸入欄位
        self.recipient_input = TextInput(
            label="收款人",
            placeholder="請輸入收款人的用戶ID或@提及",
            style=discord.TextStyle.short,
            min_length=1,
            max_length=100,
            required=True,
            custom_id="roas_currency_recipient"
        )

        self.amount_input = TextInput(
            label="轉帳金額",
            placeholder="請輸入要轉帳的金額 (正整數)",
            style=discord.TextStyle.short,
            min_length=1,
            max_length=20,
            required=True,
            custom_id="roas_currency_amount"
        )

        self.reason_input = TextInput(
            label="轉帳原因 (可選)",
            placeholder="請輸入轉帳原因...",
            style=discord.TextStyle.paragraph,
            min_length=0,
            max_length=200,
            required=False,
            custom_id="roas_currency_reason"
        )

        # 添加欄位到 Modal
        self.add_item(self.recipient_input)
        self.add_item(self.amount_input)
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        """表單提交處理"""
        try:
            # 解析輸入
            recipient_id = await self._parse_recipient(interaction)
            if recipient_id is None:
                return  # 錯誤已在 _parse_recipient 中處理

            amount = await self._parse_amount(interaction)
            if amount is None:
                return  # 錯誤已在 _parse_amount 中處理

            reason = self.reason_input.value.strip() or "用戶轉帳"

            # 基本驗證
            if recipient_id == self.from_user_id:
                await self._send_error_response(interaction, "不能轉帳給自己")
                return

            # 檢查收款人是否為機器人
            try:
                recipient = interaction.guild.get_member(recipient_id)
                if recipient and recipient.bot:
                    await self._send_error_response(interaction, "不能轉帳給機器人")
                    return
            except Exception:
                pass  # 如果無法獲取成員信息, 繼續處理

            # 執行轉帳
            await interaction.response.defer(ephemeral=True)

            result = await self.currency_service.transfer(
                guild_id=self.guild_id,
                from_user_id=self.from_user_id,
                to_user_id=recipient_id,
                amount=amount,
                reason=reason
            )

            # 創建成功嵌入
            embed = discord.Embed(
                title="✅ 轉帳成功",
                color=discord.Color.green()
            )

            # 添加轉帳詳情
            embed.add_field(
                name="轉帳金額",
                value=f"{amount:,} 貨幣",
                inline=True
            )

            try:
                recipient = interaction.guild.get_member(recipient_id)
                recipient_display = recipient.display_name if recipient else f"用戶 {recipient_id}"
            except Exception:
                recipient_display = f"用戶 {recipient_id}"

            embed.add_field(
                name="收款人",
                value=recipient_display,
                inline=True
            )

            embed.add_field(
                name="你的餘額",
                value=f"{result['from_balance_after']:,} 貨幣",
                inline=True
            )

            if reason and reason != "用戶轉帳":
                embed.add_field(
                    name="轉帳原因",
                    value=reason,
                    inline=False
                )

            embed.set_footer(text=f"交易 ID: {result['transaction_id'][:8]}...")

            # 發送成功回應
            await interaction.followup.send(embed=embed, ephemeral=True)

            try:
                await self.currency_panel_view.refresh_after_transfer(interaction)
            except Exception as e:
                self.logger.warning(f"轉帳後刷新面板失敗: {e}")

        except InsufficientFundsError:
            await self._send_error_response(interaction, "餘額不足,無法完成轉帳")

        except ConcurrencyError:
            await self._send_error_response(interaction, "系統忙碌中,請稍後再試")

        except ValueError as e:
            await self._send_error_response(interaction, f"輸入錯誤: {e}")

        except Exception as e:
            self.logger.error(f"轉帳處理失敗: {e}")
            await self._send_error_response(interaction, "轉帳處理時發生錯誤,請稍後再試")

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        """Modal 錯誤處理"""
        self.logger.error(f"轉帳 Modal 錯誤: {error}")
        await self._send_error_response(interaction, "處理轉帳表單時發生錯誤")

    async def _parse_recipient(self, interaction: discord.Interaction) -> int | None:
        """解析收款人ID"""
        recipient_text = self.recipient_input.value.strip()

        try:
            # 嘗試直接解析為用戶ID
            if recipient_text.isdigit():
                return int(recipient_text)

            # 嘗試從提及中解析 (<@123456789> 或 <@!123456789>)
            if recipient_text.startswith("<@") and recipient_text.endswith(">"):
                # 移除 <@ 和 >,以及可能的 !
                user_id_str = recipient_text[2:-1].lstrip("!")
                if user_id_str.isdigit():
                    return int(user_id_str)

            # 如果都不是,返回錯誤
            await self._send_error_response(
                interaction,
                "收款人格式錯誤,請輸入用戶ID或使用@提及用戶"
            )
            return None

        except (ValueError, TypeError):
            await self._send_error_response(
                interaction,
                "收款人格式錯誤,請輸入有效的用戶ID"
            )
            return None

    async def _parse_amount(self, interaction: discord.Interaction) -> int | None:
        """解析轉帳金額"""
        amount_text = self.amount_input.value.strip()

        try:
            # 移除可能的千位分隔符
            amount_text = amount_text.replace(",", "").replace(" ", "")

            amount = int(amount_text)

            if amount <= 0:
                await self._send_error_response(interaction, "轉帳金額必須大於 0")
                return None

            MAX_AMOUNT = 1_000_000_000
            if amount > MAX_AMOUNT:  # 10億上限
                await self._send_error_response(interaction, "轉帳金額不能超過 10 億")
                return None

            return amount

        except (ValueError, TypeError):
            await self._send_error_response(
                interaction,
                "金額格式錯誤,請輸入有效的正整數"
            )
            return None

    async def _send_error_response(
        self,
        interaction: discord.Interaction,
        message: str
    ):
        """發送錯誤回應"""
        embed = discord.Embed(
            title="❌ 轉帳錯誤",
            description=message,
            color=discord.Color.red()
        )

        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            self.logger.error(f"發送錯誤回應失敗: {e}")
