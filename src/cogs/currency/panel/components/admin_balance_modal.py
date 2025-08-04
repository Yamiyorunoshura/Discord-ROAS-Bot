"""Admin Balance Modal Component.

管理員餘額操作 Modal 組件,提供:
- 用戶ID輸入
- 操作類型選擇(增加/減少/設定)
- 金額輸入
- 操作原因輸入
- 操作日誌記錄
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord.ui import Modal, TextInput

if TYPE_CHECKING:
    from src.cogs.currency.service.currency_service import CurrencyService

    from ..admin_view import CurrencyAdminPanelView

logger = logging.getLogger(__name__)

class AdminBalanceModal(Modal):
    """管理員餘額操作 Modal"""

    def __init__(
        self,
        currency_service: CurrencyService,
        admin_panel_view: CurrencyAdminPanelView,
        guild_id: int,
        admin_id: int,
    ):
        """
        初始化管理員餘額操作 Modal

        Args:
            currency_service: 貨幣服務實例
            admin_panel_view: 管理員面板視圖實例
            guild_id: 伺服器ID
            admin_id: 管理員ID
        """
        super().__init__(
            title="💰 管理員餘額操作",
            timeout=300.0,
            custom_id="roas_currency_admin_balance_modal"
        )

        self.currency_service = currency_service
        self.admin_panel_view = admin_panel_view
        self.guild_id = guild_id
        self.admin_id = admin_id
        self.logger = logger

        # 添加輸入欄位
        self.target_user_input = TextInput(
            label="目標用戶",
            placeholder="請輸入目標用戶的用戶ID或@提及",
            style=discord.TextStyle.short,
            min_length=1,
            max_length=100,
            required=True,
            custom_id="roas_currency_admin_target_user"
        )

        self.operation_input = TextInput(
            label="操作類型",
            placeholder="add=增加, remove=減少, set=設定 (例如: add)",
            style=discord.TextStyle.short,
            min_length=3,
            max_length=10,
            required=True,
            custom_id="roas_currency_admin_operation"
        )

        self.amount_input = TextInput(
            label="操作金額",
            placeholder="請輸入金額 (正整數)",
            style=discord.TextStyle.short,
            min_length=1,
            max_length=20,
            required=True,
            custom_id="roas_currency_admin_amount"
        )

        self.reason_input = TextInput(
            label="操作原因",
            placeholder="請輸入操作原因,將記錄到操作日誌中...",
            style=discord.TextStyle.paragraph,
            min_length=1,
            max_length=200,
            required=True,
            custom_id="roas_currency_admin_reason"
        )

        # 添加欄位到 Modal
        self.add_item(self.target_user_input)
        self.add_item(self.operation_input)
        self.add_item(self.amount_input)
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        """表單提交處理"""
        try:
            # 解析和驗證輸入
            validation_result = await self._validate_all_inputs(interaction)
            if not validation_result:
                return  # 錯誤已處理

            target_user_id, operation, amount, reason = validation_result

            # 執行操作
            await interaction.response.defer(ephemeral=True)
            result, operation_display = await self._execute_balance_operation(
                target_user_id, operation, amount, reason
            )

            # 發送成功回應
            await self._send_success_response(
                interaction, target_user_id, operation_display, amount, result, reason
            )

            # 刷新面板
            await self._refresh_admin_panel(interaction)

        except ValueError as e:
            await self._send_error_response(interaction, f"輸入錯誤: {e}")
        except Exception as e:
            self.logger.error(f"管理員餘額操作失敗: {e}")
            await self._send_error_response(interaction, "餘額操作時發生錯誤,請稍後再試")

    async def _validate_all_inputs(self, interaction: discord.Interaction) -> tuple | None:
        """驗證所有輸入並返回解析結果"""
        # 驗證邏輯整合
        validations = [
            (lambda: self._parse_target_user(interaction), None),
            (lambda: self._parse_operation(interaction), None),
            (lambda: self._parse_amount(interaction), None),
        ]

        results = []
        for validation_func, _ in validations:
            result = await validation_func()
            if result is None:
                return None
            results.append(result)

        target_user_id, operation, amount = results

        # 檢查操作原因
        reason = self.reason_input.value.strip()
        if not reason:
            await self._send_error_response(interaction, "操作原因不能為空")
            return None

        # 執行額外驗證
        error_checks = [
            (target_user_id == self.admin_id, "不能對自己執行餘額操作"),
            (await self._is_target_bot(interaction, target_user_id), "不能對機器人執行餘額操作"),
        ]

        for condition, error_msg in error_checks:
            if condition:
                await self._send_error_response(interaction, error_msg)
                return None

        return target_user_id, operation, amount, reason

    async def _is_target_bot(self, interaction: discord.Interaction, target_user_id: int) -> bool:
        """檢查目標用戶是否為機器人"""
        try:
            target_user = interaction.guild.get_member(target_user_id)
            return target_user and target_user.bot
        except Exception:
            return False

    async def _execute_balance_operation(self, target_user_id: int, operation: str,
                                       amount: int, reason: str) -> tuple:
        """執行餘額操作並返回結果"""
        operation_map = {
            "add": ("增加", lambda: self.currency_service.add_balance(
                guild_id=self.guild_id,
                user_id=target_user_id,
                amount=amount,
                reason=reason,
                admin_id=self.admin_id
            )),
            "remove": ("減少", lambda: self.currency_service.add_balance(
                guild_id=self.guild_id,
                user_id=target_user_id,
                amount=-amount,
                reason=reason,
                admin_id=self.admin_id
            )),
            "set": ("設定為", lambda: self.currency_service.set_balance(
                guild_id=self.guild_id,
                user_id=target_user_id,
                new_balance=amount,
                reason=reason,
                admin_user_id=self.admin_id
            ))
        }

        operation_display, operation_func = operation_map[operation]
        result = await operation_func()
        return result, operation_display

    async def _send_success_response(self, interaction: discord.Interaction,
                                   target_user_id: int, operation_display: str,
                                   amount: int, result: dict, reason: str):
        """發送成功回應"""
        embed = discord.Embed(
            title="✅ 餘額操作成功",
            color=discord.Color.green()
        )

        # 獲取目標用戶顯示名稱
        target_display = self._get_target_display_name(interaction, target_user_id)

        embed.add_field(name="目標用戶", value=target_display, inline=True)
        embed.add_field(name="操作類型", value=f"{operation_display} {amount:,} 貨幣", inline=True)
        embed.add_field(name="操作後餘額", value=f"{result['new_balance']:,} 貨幣", inline=True)
        embed.add_field(name="操作原因", value=reason, inline=False)
        embed.set_footer(text=f"操作者: {interaction.user.display_name}")

        await interaction.followup.send(embed=embed, ephemeral=True)

    def _get_target_display_name(self, interaction: discord.Interaction, target_user_id: int) -> str:
        """獲取目標用戶的顯示名稱"""
        try:
            target_user = interaction.guild.get_member(target_user_id)
            return target_user.display_name if target_user else f"用戶 {target_user_id}"
        except Exception:
            return f"用戶 {target_user_id}"

    async def _refresh_admin_panel(self, interaction: discord.Interaction):
        """刷新管理員面板"""
        try:
            await self.admin_panel_view.refresh_data_and_view(interaction)
        except Exception as e:
            self.logger.warning(f"操作後刷新管理員面板失敗: {e}")

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        """Modal 錯誤處理"""
        self.logger.error(f"管理員餘額操作 Modal 錯誤: {error}")
        await self._send_error_response(interaction, "處理餘額操作表單時發生錯誤")

    async def _parse_target_user(self, interaction: discord.Interaction) -> int | None:
        """解析目標用戶ID"""
        user_text = self.target_user_input.value.strip()

        try:
            # 嘗試直接解析為用戶ID
            if user_text.isdigit():
                return int(user_text)

            # 嘗試從提及中解析 (<@123456789> 或 <@!123456789>)
            if user_text.startswith("<@") and user_text.endswith(">"):
                # 移除 <@ 和 >,以及可能的 !
                user_id_str = user_text[2:-1].lstrip("!")
                if user_id_str.isdigit():
                    return int(user_id_str)

            # 如果都不是,返回錯誤
            await self._send_error_response(
                interaction,
                "目標用戶格式錯誤,請輸入用戶ID或使用@提及用戶"
            )
            return None

        except (ValueError, TypeError):
            await self._send_error_response(
                interaction,
                "目標用戶格式錯誤,請輸入有效的用戶ID"
            )
            return None

    async def _parse_operation(self, interaction: discord.Interaction) -> str | None:
        """解析操作類型"""
        operation_text = self.operation_input.value.strip().lower()

        valid_operations = ["add", "remove", "set"]

        if operation_text in valid_operations:
            return operation_text

        # 支援中文別名
        operation_aliases = {
            "增加": "add",
            "添加": "add",
            "加": "add",
            "減少": "remove",
            "扣除": "remove",
            "減": "remove",
            "設定": "set",
            "設置": "set",
            "設": "set",
        }

        if operation_text in operation_aliases:
            return operation_aliases[operation_text]

        await self._send_error_response(
            interaction,
            "操作類型錯誤,請輸入: add(增加), remove(減少), set(設定)"
        )
        return None

    async def _parse_amount(self, interaction: discord.Interaction) -> int | None:
        """解析操作金額"""
        amount_text = self.amount_input.value.strip()

        try:
            # 移除可能的千位分隔符
            amount_text = amount_text.replace(",", "").replace(" ", "")

            amount = int(amount_text)

            if amount <= 0:
                await self._send_error_response(interaction, "操作金額必須大於 0")
                return None

            MAX_AMOUNT = 1_000_000_000
            if amount > MAX_AMOUNT:  # 10億上限
                await self._send_error_response(interaction, "操作金額不能超過 10 億")
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
            title="❌ 餘額操作錯誤",
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
