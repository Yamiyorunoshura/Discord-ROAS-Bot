"""
經濟系統面板
Task ID: 3 - 實作經濟系統使用者介面

這個模組提供經濟系統的Discord UI面板，包括：
- 使用者餘額查詢和交易記錄查看
- 管理員餘額管理和貨幣設定
- 統一的權限驗證和錯誤處理
- Discord UI組件的互動處理
"""

import asyncio
import logging
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, timedelta
import discord
from discord.ext import commands

from panels.base_panel import BasePanel
from services.economy.economy_service import EconomyService
from services.economy.models import (
    Account, Transaction, CurrencyConfig, AccountType, TransactionType,
    format_currency, validate_user_id, validate_guild_id
)
from core.exceptions import ServiceError, ValidationError, ServicePermissionError


class EconomyPanel(BasePanel):
    """
    經濟系統面板
    
    提供完整的經濟系統Discord使用者介面，包括：
    - 使用者功能：餘額查詢、交易記錄查看
    - 管理員功能：餘額管理、貨幣設定
    - 統一的權限驗證和錯誤處理
    """
    
    def __init__(self):
        super().__init__(
            name="EconomyPanel",
            title="💰 經濟系統",
            description="管理伺服器經濟系統",
            color=discord.Color.gold()
        )
        
        # 服務依賴
        self.economy_service: Optional[EconomyService] = None
        
        # UI設定
        self.transactions_per_page = 10
        self.max_balance_display_length = 20
        
        # 權限配置
        self.admin_permissions = ["administrator", "manage_guild"]
        
    async def initialize(self, economy_service: EconomyService):
        """
        初始化面板並設定服務依賴
        
        參數：
            economy_service: 經濟服務實例
        """
        try:
            self.economy_service = economy_service
            self.add_service(economy_service, "economy")
            
            # 註冊互動處理器
            self._register_interaction_handlers()
            
            self.logger.info("經濟面板初始化完成")
            
        except Exception as e:
            self.logger.exception(f"經濟面板初始化失敗：{e}")
            raise ServiceError(
                f"經濟面板初始化失敗：{str(e)}",
                service_name=self.name,
                operation="initialize"
            )
    
    def _register_interaction_handlers(self):
        """註冊互動處理器"""
        # 使用者功能按鈕
        self.register_interaction_handler("economy_show_balance", self._handle_show_balance)
        self.register_interaction_handler("economy_show_transactions", self._handle_show_transactions)
        self.register_interaction_handler("economy_transaction_prev", self._handle_transaction_prev)
        self.register_interaction_handler("economy_transaction_next", self._handle_transaction_next)
        
        # 管理員功能按鈕
        self.register_interaction_handler("economy_admin_panel", self._handle_admin_panel)
        self.register_interaction_handler("economy_manage_balance", self._handle_manage_balance)
        self.register_interaction_handler("economy_currency_settings", self._handle_currency_settings)
        self.register_interaction_handler("economy_audit_log", self._handle_audit_log)
        
        # 模態框處理器
        self.register_interaction_handler("balance_management_modal", self._handle_balance_management_modal)
        self.register_interaction_handler("currency_settings_modal", self._handle_currency_settings_modal)
    
    # ==========================================================================
    # 主要面板功能
    # ==========================================================================
    
    async def _handle_slash_command(self, interaction: discord.Interaction):
        """處理斜線指令互動"""
        try:
            command_name = interaction.data.get('name', '')
            
            if command_name == 'economy':
                await self._show_main_panel(interaction)
            elif command_name == 'balance':
                await self._handle_balance_command(interaction)
            elif command_name == 'economy_admin':
                # 檢查管理員權限
                if not await self._check_admin_permissions(interaction):
                    await self.send_error(interaction, "您沒有使用管理員功能的權限。")
                    return
                await self._show_admin_panel(interaction)
            else:
                await self.send_error(interaction, f"未知的指令：{command_name}")
                
        except Exception as e:
            self.logger.exception(f"處理斜線指令時發生錯誤：{e}")
            await self.send_error(interaction, "處理指令時發生錯誤，請稍後再試。")
    
    async def _show_main_panel(self, interaction: discord.Interaction):
        """顯示主經濟面板"""
        try:
            # 獲取使用者帳戶資訊
            user_id = interaction.user.id
            guild_id = interaction.guild.id
            account_id = f"user_{user_id}_{guild_id}"
            
            # 檢查或建立使用者帳戶
            account = await self.economy_service.get_account(account_id)
            if not account:
                account = await self.economy_service.create_account(
                    guild_id=guild_id,
                    account_type=AccountType.USER,
                    user_id=user_id,
                    initial_balance=0.0
                )
            
            # 獲取貨幣配置
            currency_config = await self.economy_service.get_currency_config(guild_id)
            
            # 建立主面板嵌入訊息
            embed = await self.create_balance_embed(account, currency_config)
            
            # 建立UI組件
            view = UserEconomyView(self, account, currency_config)
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            self.logger.exception(f"顯示主面板時發生錯誤：{e}")
            await self.send_error(interaction, "無法載入經濟面板，請稍後再試。")
    
    async def _handle_balance_command(self, interaction: discord.Interaction):
        """處理餘額查詢指令"""
        try:
            # 獲取目標使用者（如果有指定）
            target_user = interaction.data.get('options', [{}])[0].get('value') if interaction.data.get('options') else None
            target_user_id = target_user.id if target_user else interaction.user.id
            
            # 檢查權限（只有管理員可以查看其他人的餘額）
            if target_user_id != interaction.user.id:
                if not await self._check_admin_permissions(interaction):
                    await self.send_error(interaction, "您沒有查看其他使用者餘額的權限。")
                    return
            
            guild_id = interaction.guild.id
            account_id = f"user_{target_user_id}_{guild_id}"
            
            # 獲取帳戶資訊
            account = await self.economy_service.get_account(account_id)
            if not account:
                if target_user_id == interaction.user.id:
                    account = await self.economy_service.create_account(
                        guild_id=guild_id,
                        account_type=AccountType.USER,
                        user_id=target_user_id,
                        initial_balance=0.0
                    )
                else:
                    await self.send_error(interaction, "目標使用者尚未建立帳戶。")
                    return
            
            # 獲取貨幣配置
            currency_config = await self.economy_service.get_currency_config(guild_id)
            
            # 建立餘額顯示嵌入訊息
            embed = await self.create_simple_balance_embed(account, currency_config, target_user)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            self.logger.exception(f"處理餘額指令時發生錯誤：{e}")
            await self.send_error(interaction, "無法查詢餘額，請稍後再試。")
    
    # ==========================================================================
    # 嵌入訊息建立功能
    # ==========================================================================
    
    async def create_balance_embed(
        self, 
        account: Account, 
        currency_config: CurrencyConfig,
        user: Optional[discord.Member] = None
    ) -> discord.Embed:
        """
        建立餘額顯示嵌入訊息
        
        參數：
            account: 帳戶物件
            currency_config: 貨幣配置
            user: Discord成員物件（可選）
            
        返回：
            Discord嵌入訊息
        """
        try:
            # 格式化餘額
            formatted_balance = format_currency(account.balance, currency_config)
            
            # 建立嵌入訊息
            embed = await self.create_embed(
                title=f"{currency_config.currency_symbol} 個人錢包",
                color=discord.Color.gold()
            )
            
            # 添加餘額欄位
            embed.add_field(
                name="💰 當前餘額",
                value=f"**{formatted_balance}**",
                inline=True
            )
            
            # 添加帳戶類型
            embed.add_field(
                name="📋 帳戶類型",
                value=account.account_type.display_name,
                inline=True
            )
            
            # 添加建立時間
            embed.add_field(
                name="📅 帳戶建立",
                value=f"<t:{int(account.created_at.timestamp())}:R>",
                inline=True
            )
            
            # 設定使用者頭像（如果提供）
            if user:
                embed.set_thumbnail(url=user.display_avatar.url)
            
            return embed
            
        except Exception as e:
            self.logger.exception(f"建立餘額嵌入訊息時發生錯誤：{e}")
            return await self.create_embed(
                title="❌ 錯誤",
                description="無法載入餘額資訊",
                color=discord.Color.red()
            )
    
    async def create_simple_balance_embed(
        self, 
        account: Account, 
        currency_config: CurrencyConfig,
        user: Optional[discord.Member] = None
    ) -> discord.Embed:
        """建立簡單的餘額顯示嵌入訊息"""
        try:
            formatted_balance = format_currency(account.balance, currency_config)
            user_mention = user.mention if user else "<@未知使用者>"
            
            embed = await self.create_embed(
                title="💰 餘額查詢",
                description=f"{user_mention} 的當前餘額為 **{formatted_balance}**",
                color=discord.Color.blue()
            )
            
            return embed
            
        except Exception as e:
            self.logger.exception(f"建立簡單餘額嵌入訊息時發生錯誤：{e}")
            return await self.create_embed(
                title="❌ 錯誤",
                description="無法載入餘額資訊",
                color=discord.Color.red()
            )
    
    async def create_transaction_embed(
        self, 
        transactions: List[Transaction], 
        currency_config: CurrencyConfig,
        page: int = 0,
        total_pages: int = 1
    ) -> discord.Embed:
        """
        建立交易記錄嵌入訊息
        
        參數：
            transactions: 交易記錄列表
            currency_config: 貨幣配置
            page: 當前頁面
            total_pages: 總頁數
            
        返回：
            Discord嵌入訊息
        """
        try:
            embed = await self.create_embed(
                title="📊 交易記錄",
                description=f"頁面 {page + 1}/{total_pages}",
                color=discord.Color.blue()
            )
            
            if not transactions:
                embed.add_field(
                    name="📝 記錄",
                    value="尚無交易記錄",
                    inline=False
                )
                return embed
            
            # 添加交易記錄
            for i, transaction in enumerate(transactions):
                # 格式化金額
                formatted_amount = format_currency(transaction.amount, currency_config)
                
                # 確定交易方向和圖示（先提取使用者ID）
                user_account_prefix = f"user_{transaction.from_account.split('_')[1] if transaction.from_account else ''}"
                
                if transaction.transaction_type == TransactionType.TRANSFER:
                    if transaction.from_account and transaction.to_account:
                        direction = "➡️ 轉出" if transaction.from_account.startswith(user_account_prefix) else "⬅️ 轉入"
                    else:
                        direction = "🔄 轉帳"
                elif transaction.transaction_type == TransactionType.DEPOSIT:
                    direction = "⬆️ 存款"
                elif transaction.transaction_type == TransactionType.WITHDRAW:
                    direction = "⬇️ 提款"
                else:
                    direction = f"🔧 {transaction.transaction_type.display_name}"
                
                # 格式化時間
                time_str = f"<t:{int(transaction.created_at.timestamp())}:R>"
                
                # 建立欄位值
                field_value = f"{direction} **{formatted_amount}**\n"
                if transaction.reason:
                    field_value += f"原因：{transaction.reason}\n"
                field_value += f"時間：{time_str}"
                
                embed.add_field(
                    name=f"#{transaction.id or i+1}",
                    value=field_value,
                    inline=True
                )
            
            return embed
            
        except Exception as e:
            self.logger.exception(f"建立交易記錄嵌入訊息時發生錯誤：{e}")
            return await self.create_embed(
                title="❌ 錯誤",
                description="無法載入交易記錄",
                color=discord.Color.red()
            )
    
    # ==========================================================================
    # 權限驗證功能
    # ==========================================================================
    
    async def _check_admin_permissions(self, interaction: discord.Interaction) -> bool:
        """
        檢查使用者是否有管理員權限
        
        參數：
            interaction: Discord互動
            
        返回：
            是否有管理員權限
        """
        try:
            # 檢查使用者是否有管理員權限
            user = interaction.user
            if isinstance(user, discord.Member):
                return (
                    user.guild_permissions.administrator or 
                    user.guild_permissions.manage_guild
                )
            
            return False
            
        except Exception as e:
            self.logger.exception(f"檢查管理員權限時發生錯誤：{e}")
            return False
    
    async def _validate_permissions(self, interaction: discord.Interaction, action: str) -> bool:
        """
        覆寫基礎類別的權限驗證邏輯
        
        參數：
            interaction: Discord互動
            action: 要執行的動作
            
        返回：
            是否有權限
        """
        try:
            # 管理員動作需要特殊權限
            admin_actions = [
                "admin_panel", "manage_balance", "currency_settings", 
                "audit_log", "admin_transfer", "admin_deposit", "admin_withdraw"
            ]
            
            if action in admin_actions:
                return await self._check_admin_permissions(interaction)
            
            # 一般動作允許所有使用者
            return True
            
        except Exception as e:
            self.logger.exception(f"權限驗證時發生錯誤：{e}")
            return False    
    # ==========================================================================
    # 使用者功能處理器
    # ==========================================================================
    
    async def _handle_show_balance(self, interaction: discord.Interaction):
        """處理顯示餘額按鈕"""
        try:
            await self._show_main_panel(interaction)
            
        except Exception as e:
            self.logger.exception(f"處理顯示餘額時發生錯誤：{e}")
            await self.send_error(interaction, "無法載入餘額資訊，請稍後再試。")
    
    async def _handle_show_transactions(self, interaction: discord.Interaction):
        """處理顯示交易記錄按鈕"""
        try:
            user_id = interaction.user.id
            guild_id = interaction.guild.id
            account_id = f"user_{user_id}_{guild_id}"
            
            # 獲取交易記錄
            transactions = await self.economy_service.get_transaction_history(
                account_id=account_id,
                limit=self.transactions_per_page
            )
            
            # 獲取貨幣配置
            currency_config = await self.economy_service.get_currency_config(guild_id)
            
            # 計算總頁數
            total_transactions = len(transactions)  # 簡化版，實際應該查詢總數
            total_pages = max(1, (total_transactions + self.transactions_per_page - 1) // self.transactions_per_page)
            
            # 建立交易記錄嵌入訊息
            embed = await self.create_transaction_embed(
                transactions=transactions,
                currency_config=currency_config,
                page=0,
                total_pages=total_pages
            )
            
            # 建立分頁UI組件
            view = TransactionHistoryView(self, account_id, currency_config, 0, total_pages)
            
            await interaction.response.edit_message(embed=embed, view=view)
            
        except Exception as e:
            self.logger.exception(f"處理顯示交易記錄時發生錯誤：{e}")
            await self.send_error(interaction, "無法載入交易記錄，請稍後再試。")
    
    async def _handle_transaction_prev(self, interaction: discord.Interaction):
        """處理交易記錄上一頁"""
        try:
            # 從互動中提取當前頁面資訊
            current_page = self.state.get_user_data(interaction.user.id, "transaction_page", 0)
            if current_page > 0:
                current_page -= 1
                self.state.set_user_data(interaction.user.id, "transaction_page", current_page)
                await self._show_transaction_page(interaction, current_page)
            else:
                await self.send_warning(interaction, "已經是第一頁了。")
                
        except Exception as e:
            self.logger.exception(f"處理交易記錄上一頁時發生錯誤：{e}")
            await self.send_error(interaction, "無法載入上一頁，請稍後再試。")
    
    async def _handle_transaction_next(self, interaction: discord.Interaction):
        """處理交易記錄下一頁"""
        try:
            # 從互動中提取當前頁面資訊
            current_page = self.state.get_user_data(interaction.user.id, "transaction_page", 0)
            total_pages = self.state.get_user_data(interaction.user.id, "total_pages", 1)
            
            if current_page < total_pages - 1:
                current_page += 1
                self.state.set_user_data(interaction.user.id, "transaction_page", current_page)
                await self._show_transaction_page(interaction, current_page)
            else:
                await self.send_warning(interaction, "已經是最後一頁了。")
                
        except Exception as e:
            self.logger.exception(f"處理交易記錄下一頁時發生錯誤：{e}")
            await self.send_error(interaction, "無法載入下一頁，請稍後再試。")
    
    async def _show_transaction_page(self, interaction: discord.Interaction, page: int):
        """顯示指定頁面的交易記錄"""
        try:
            user_id = interaction.user.id
            guild_id = interaction.guild.id
            account_id = f"user_{user_id}_{guild_id}"
            
            # 計算偏移量
            offset = page * self.transactions_per_page
            
            # 獲取交易記錄（這裡簡化實作，實際需要支援偏移量）
            transactions = await self.economy_service.get_transaction_history(
                account_id=account_id,
                limit=self.transactions_per_page
            )
            
            # 模擬分頁（實際應該在服務層實作）
            start_idx = offset
            end_idx = start_idx + self.transactions_per_page
            page_transactions = transactions[start_idx:end_idx]
            
            # 獲取貨幣配置
            currency_config = await self.economy_service.get_currency_config(guild_id)
            
            # 計算總頁數
            total_pages = self.state.get_user_data(interaction.user.id, "total_pages", 1)
            
            # 建立交易記錄嵌入訊息
            embed = await self.create_transaction_embed(
                transactions=page_transactions,
                currency_config=currency_config,
                page=page,
                total_pages=total_pages
            )
            
            # 建立分頁UI組件
            view = TransactionHistoryView(self, account_id, currency_config, page, total_pages)
            
            await interaction.response.edit_message(embed=embed, view=view)
            
        except Exception as e:
            self.logger.exception(f"顯示交易記錄頁面時發生錯誤：{e}")
            await self.send_error(interaction, "無法載入交易記錄，請稍後再試。")
    
    # ==========================================================================
    # 管理員功能處理器
    # ==========================================================================
    
    async def _show_admin_panel(self, interaction: discord.Interaction):
        """顯示管理員面板"""
        try:
            guild_id = interaction.guild.id
            
            # 獲取伺服器經濟統計
            guild_accounts = await self.economy_service.get_guild_accounts(guild_id)
            currency_config = await self.economy_service.get_currency_config(guild_id)
            
            # 計算統計資料
            total_accounts = len(guild_accounts)
            total_balance = sum(account.balance for account in guild_accounts)
            avg_balance = total_balance / total_accounts if total_accounts > 0 else 0
            
            # 建立管理員面板嵌入訊息
            embed = await self.create_embed(
                title="🛠️ 經濟系統管理面板",
                description="管理伺服器經濟系統設定和使用者帳戶",
                color=discord.Color.orange()
            )
            
            embed.add_field(
                name="📊 伺服器統計",
                value=f"**帳戶總數：** {total_accounts}\n"
                      f"**總流通量：** {format_currency(total_balance, currency_config)}\n"
                      f"**平均餘額：** {format_currency(avg_balance, currency_config)}",
                inline=False
            )
            
            embed.add_field(
                name="💰 貨幣設定",
                value=f"**名稱：** {currency_config.currency_name}\n"
                      f"**符號：** {currency_config.currency_symbol}\n"
                      f"**小數位：** {currency_config.decimal_places}",
                inline=True
            )
            
            embed.add_field(
                name="⚙️ 轉帳限制",
                value=f"**最小金額：** {format_currency(currency_config.min_transfer_amount, currency_config)}\n"
                      f"**最大金額：** {format_currency(currency_config.max_transfer_amount, currency_config) if currency_config.max_transfer_amount else '無限制'}\n"
                      f"**每日限額：** {format_currency(currency_config.daily_transfer_limit, currency_config) if currency_config.daily_transfer_limit else '無限制'}",
                inline=True
            )
            
            # 建立管理員UI組件
            view = AdminEconomyView(self, currency_config)
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            self.logger.exception(f"顯示管理員面板時發生錯誤：{e}")
            await self.send_error(interaction, "無法載入管理員面板，請稍後再試。")
    
    async def _handle_admin_panel(self, interaction: discord.Interaction):
        """處理管理員面板按鈕"""
        try:
            # 檢查權限
            if not await self.validate_permissions(interaction, "admin_panel"):
                return
            
            await self._show_admin_panel(interaction)
            
        except Exception as e:
            self.logger.exception(f"處理管理員面板時發生錯誤：{e}")
            await self.send_error(interaction, "無法載入管理員面板，請稍後再試。")
    
    async def _handle_manage_balance(self, interaction: discord.Interaction):
        """處理餘額管理按鈕"""
        try:
            # 檢查權限
            if not await self.validate_permissions(interaction, "manage_balance"):
                return
            
            # 顯示餘額管理模態框
            modal = BalanceManagementModal(self)
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            self.logger.exception(f"處理餘額管理時發生錯誤：{e}")
            await self.send_error(interaction, "無法開啟餘額管理，請稍後再試。")
    
    async def _handle_currency_settings(self, interaction: discord.Interaction):
        """處理貨幣設定按鈕"""
        try:
            # 檢查權限
            if not await self.validate_permissions(interaction, "currency_settings"):
                return
            
            guild_id = interaction.guild.id
            currency_config = await self.economy_service.get_currency_config(guild_id)
            
            # 顯示貨幣設定模態框
            modal = CurrencySettingsModal(self, currency_config)
            await interaction.response.send_modal(modal)
            
        except Exception as e:
            self.logger.exception(f"處理貨幣設定時發生錯誤：{e}")
            await self.send_error(interaction, "無法開啟貨幣設定，請稍後再試。")
    
    async def _handle_audit_log(self, interaction: discord.Interaction):
        """處理審計日誌按鈕"""
        try:
            # 檢查權限
            if not await self.validate_permissions(interaction, "audit_log"):
                return
            
            # TODO: 實作審計日誌查看功能
            await self.send_warning(interaction, "審計日誌功能將在後續版本中實作。")
            
        except Exception as e:
            self.logger.exception(f"處理審計日誌時發生錯誤：{e}")
            await self.send_error(interaction, "無法載入審計日誌，請稍後再試。")
    
    # ==========================================================================
    # 模態框處理器
    # ==========================================================================
    
    async def _handle_balance_management_modal(self, interaction: discord.Interaction):
        """處理餘額管理模態框提交"""
        try:
            # 檢查權限
            if not await self.validate_permissions(interaction, "manage_balance"):
                return
            
            # 提取表單資料
            data = interaction.data.get('components', [])
            target_user_id = None
            action = None
            amount = None
            reason = None
            
            for component_row in data:
                for component in component_row.get('components', []):
                    custom_id = component.get('custom_id')
                    value = component.get('value', '').strip()
                    
                    if custom_id == 'target_user_id':
                        try:
                            target_user_id = int(value)
                        except ValueError:
                            await self.send_error(interaction, "無效的使用者ID格式。")
                            return
                    elif custom_id == 'action':
                        action = value.lower()
                    elif custom_id == 'amount':
                        try:
                            amount = float(value)
                        except ValueError:
                            await self.send_error(interaction, "無效的金額格式。")
                            return
                    elif custom_id == 'reason':
                        reason = value
            
            # 驗證必要欄位
            if not target_user_id or not action or not amount:
                await self.send_error(interaction, "請填寫所有必要欄位。")
                return
            
            if action not in ['deposit', 'withdraw']:
                await self.send_error(interaction, "動作必須是 'deposit' 或 'withdraw'。")
                return
            
            if amount <= 0:
                await self.send_error(interaction, "金額必須大於零。")
                return
            
            # 執行餘額管理操作
            guild_id = interaction.guild.id
            account_id = f"user_{target_user_id}_{guild_id}"
            admin_user_id = interaction.user.id
            
            # 確保目標帳戶存在
            account = await self.economy_service.get_account(account_id)
            if not account:
                account = await self.economy_service.create_account(
                    guild_id=guild_id,
                    account_type=AccountType.USER,
                    user_id=target_user_id,
                    initial_balance=0.0
                )
            
            # 執行操作
            if action == 'deposit':
                transaction = await self.economy_service.deposit(
                    account_id=account_id,
                    amount=amount,
                    reason=reason or f"管理員存款（由 <@{admin_user_id}> 執行）",
                    created_by=admin_user_id
                )
                action_text = "存款"
            else:  # withdraw
                transaction = await self.economy_service.withdraw(
                    account_id=account_id,
                    amount=amount,
                    reason=reason or f"管理員提款（由 <@{admin_user_id}> 執行）",
                    created_by=admin_user_id
                )
                action_text = "提款"
            
            # 獲取更新後的餘額
            updated_balance = await self.economy_service.get_balance(account_id)
            currency_config = await self.economy_service.get_currency_config(guild_id)
            
            await self.send_success(
                interaction,
                f"✅ {action_text}成功！\n"
                f"對象：<@{target_user_id}>\n"
                f"金額：{format_currency(amount, currency_config)}\n"
                f"當前餘額：{format_currency(updated_balance, currency_config)}"
            )
            
        except ServiceError as e:
            await self.send_error(interaction, f"操作失敗：{e.user_message}")
        except Exception as e:
            self.logger.exception(f"處理餘額管理模態框時發生錯誤：{e}")
            await self.send_error(interaction, "處理餘額管理時發生錯誤，請稍後再試。")
    
    async def _handle_currency_settings_modal(self, interaction: discord.Interaction):
        """處理貨幣設定模態框提交"""
        try:
            # 檢查權限
            if not await self.validate_permissions(interaction, "currency_settings"):
                return
            
            # 提取表單資料
            data = interaction.data.get('components', [])
            currency_name = None
            currency_symbol = None
            decimal_places = None
            min_transfer_amount = None
            
            for component_row in data:
                for component in component_row.get('components', []):
                    custom_id = component.get('custom_id')
                    value = component.get('value', '').strip()
                    
                    if custom_id == 'currency_name' and value:
                        currency_name = value
                    elif custom_id == 'currency_symbol' and value:
                        currency_symbol = value
                    elif custom_id == 'decimal_places' and value:
                        try:
                            decimal_places = int(value)
                        except ValueError:
                            await self.send_error(interaction, "無效的小數位數格式。")
                            return
                    elif custom_id == 'min_transfer_amount' and value:
                        try:
                            min_transfer_amount = float(value)
                        except ValueError:
                            await self.send_error(interaction, "無效的最小轉帳金額格式。")
                            return
            
            # 更新貨幣配置
            guild_id = interaction.guild.id
            admin_user_id = interaction.user.id
            
            updated_config = await self.economy_service.set_currency_config(
                guild_id=guild_id,
                currency_name=currency_name,
                currency_symbol=currency_symbol,
                decimal_places=decimal_places,
                min_transfer_amount=min_transfer_amount,
                updated_by=admin_user_id
            )
            
            await self.send_success(
                interaction,
                f"✅ 貨幣設定已更新！\n"
                f"名稱：{updated_config.currency_name}\n"
                f"符號：{updated_config.currency_symbol}\n"
                f"小數位：{updated_config.decimal_places}\n"
                f"最小轉帳：{format_currency(updated_config.min_transfer_amount, updated_config)}"
            )
            
        except ServiceError as e:
            await self.send_error(interaction, f"設定失敗：{e.user_message}")
        except Exception as e:
            self.logger.exception(f"處理貨幣設定模態框時發生錯誤：{e}")
            await self.send_error(interaction, "處理貨幣設定時發生錯誤，請稍後再試。")


# =============================================================================
# Discord UI 組件類別
# =============================================================================

class UserEconomyView(discord.ui.View):
    """
    使用者經濟面板UI組件
    
    提供使用者可使用的經濟功能按鈕
    """
    
    def __init__(self, panel: EconomyPanel, account: Account, currency_config: CurrencyConfig):
        super().__init__(timeout=300)
        self.panel = panel
        self.account = account
        self.currency_config = currency_config
    
    @discord.ui.button(label="💰 查看餘額", style=discord.ButtonStyle.primary, custom_id="economy_show_balance")
    async def show_balance_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """餘額查看按鈕"""
        await self.panel._handle_show_balance(interaction)
    
    @discord.ui.button(label="📊 交易記錄", style=discord.ButtonStyle.secondary, custom_id="economy_show_transactions")
    async def show_transactions_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """交易記錄查看按鈕"""
        await self.panel._handle_show_transactions(interaction)
    
    async def on_timeout(self):
        """處理視圖超時"""
        # 禁用所有按鈕
        for child in self.children:
            child.disabled = True


class TransactionHistoryView(discord.ui.View):
    """
    交易記錄分頁UI組件
    
    提供交易記錄的分頁導航功能
    """
    
    def __init__(self, panel: EconomyPanel, account_id: str, currency_config: CurrencyConfig, current_page: int, total_pages: int):
        super().__init__(timeout=300)
        self.panel = panel
        self.account_id = account_id
        self.currency_config = currency_config
        self.current_page = current_page
        self.total_pages = total_pages
        
        # 根據當前頁面狀態設定按鈕狀態
        self.children[0].disabled = (current_page <= 0)  # 上一頁按鈕
        self.children[1].disabled = (current_page >= total_pages - 1)  # 下一頁按鈕
    
    @discord.ui.button(label="⬅️ 上一頁", style=discord.ButtonStyle.secondary, custom_id="economy_transaction_prev")
    async def prev_page_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """上一頁按鈕"""
        await self.panel._handle_transaction_prev(interaction)
    
    @discord.ui.button(label="➡️ 下一頁", style=discord.ButtonStyle.secondary, custom_id="economy_transaction_next")
    async def next_page_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """下一頁按鈕"""
        await self.panel._handle_transaction_next(interaction)
    
    @discord.ui.button(label="🔄 重新整理", style=discord.ButtonStyle.primary, custom_id="economy_show_transactions")
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """重新整理按鈕"""
        await self.panel._handle_show_transactions(interaction)
    
    async def on_timeout(self):
        """處理視圖超時"""
        for child in self.children:
            child.disabled = True


class AdminEconomyView(discord.ui.View):
    """
    管理員經濟面板UI組件
    
    提供管理員可使用的經濟管理功能按鈕
    """
    
    def __init__(self, panel: EconomyPanel, currency_config: CurrencyConfig):
        super().__init__(timeout=600)  # 管理員面板超時時間較長
        self.panel = panel
        self.currency_config = currency_config
    
    @discord.ui.button(label="💼 餘額管理", style=discord.ButtonStyle.primary, custom_id="economy_manage_balance")
    async def manage_balance_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """餘額管理按鈕"""
        await self.panel._handle_manage_balance(interaction)
    
    @discord.ui.button(label="⚙️ 貨幣設定", style=discord.ButtonStyle.secondary, custom_id="economy_currency_settings")
    async def currency_settings_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """貨幣設定按鈕"""
        await self.panel._handle_currency_settings(interaction)
    
    @discord.ui.button(label="📋 審計日誌", style=discord.ButtonStyle.secondary, custom_id="economy_audit_log")
    async def audit_log_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """審計日誌按鈕"""
        await self.panel._handle_audit_log(interaction)
    
    async def on_timeout(self):
        """處理視圖超時"""
        for child in self.children:
            child.disabled = True


class BalanceManagementModal(discord.ui.Modal):
    """
    餘額管理模態框
    
    提供管理員修改使用者餘額的表單界面
    """
    
    def __init__(self, panel: EconomyPanel):
        super().__init__(title="💼 餘額管理", custom_id="balance_management_modal")
        self.panel = panel
        
        # 目標使用者ID輸入框
        self.target_user_id = discord.ui.TextInput(
            label="目標使用者ID",
            placeholder="請輸入使用者的Discord ID",
            custom_id="target_user_id",
            required=True,
            max_length=20
        )
        self.add_item(self.target_user_id)
        
        # 操作類型輸入框
        self.action = discord.ui.TextInput(
            label="操作類型",
            placeholder="輸入 'deposit' （存款）或 'withdraw' （提款）",
            custom_id="action",
            required=True,
            max_length=10
        )
        self.add_item(self.action)
        
        # 金額輸入框
        self.amount = discord.ui.TextInput(
            label="金額",
            placeholder="請輸入金額（僅數字）",
            custom_id="amount",
            required=True,
            max_length=20
        )
        self.add_item(self.amount)
        
        # 原因輸入框
        self.reason = discord.ui.TextInput(
            label="操作原因",
            placeholder="請輸入操作原因（可選）",
            custom_id="reason",
            required=False,
            max_length=200,
            style=discord.TextStyle.paragraph
        )
        self.add_item(self.reason)
    
    async def on_submit(self, interaction: discord.Interaction):
        """處理模態框提交"""
        await self.panel._handle_balance_management_modal(interaction)


class CurrencySettingsModal(discord.ui.Modal):
    """
    貨幣設定模態框
    
    提供管理員修改伺服器貨幣配置的表單界面
    """
    
    def __init__(self, panel: EconomyPanel, current_config: CurrencyConfig):
        super().__init__(title="⚙️ 貨幣設定", custom_id="currency_settings_modal")
        self.panel = panel
        self.current_config = current_config
        
        # 貨幣名稱輸入框
        self.currency_name = discord.ui.TextInput(
            label="貨幣名稱",
            placeholder="例如：金幣、銀幣等",
            custom_id="currency_name",
            default=current_config.currency_name,
            required=False,
            max_length=50
        )
        self.add_item(self.currency_name)
        
        # 貨幣符號輸入框
        self.currency_symbol = discord.ui.TextInput(
            label="貨幣符號",
            placeholder="例如：💰、💎、🪙等",
            custom_id="currency_symbol",
            default=current_config.currency_symbol,
            required=False,
            max_length=10
        )
        self.add_item(self.currency_symbol)
        
        # 小數位數輸入框
        self.decimal_places = discord.ui.TextInput(
            label="小數位數",
            placeholder="0-8之間的整數",
            custom_id="decimal_places",
            default=str(current_config.decimal_places),
            required=False,
            max_length=1
        )
        self.add_item(self.decimal_places)
        
        # 最小轉帳金額輸入框
        self.min_transfer_amount = discord.ui.TextInput(
            label="最小轉帳金額",
            placeholder="例如：1.0",
            custom_id="min_transfer_amount",
            default=str(current_config.min_transfer_amount),
            required=False,
            max_length=20
        )
        self.add_item(self.min_transfer_amount)
    
    async def on_submit(self, interaction: discord.Interaction):
        """處理模態框提交"""
        await self.panel._handle_currency_settings_modal(interaction)