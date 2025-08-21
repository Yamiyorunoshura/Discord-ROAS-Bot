"""
面板基礎類別
Task ID: 1 - 建立核心架構基礎

這個模組提供了所有 Discord UI 面板的基礎抽象類別，包含：
- 統一的嵌入訊息建立
- 互動處理機制
- 標準化的錯誤和成功訊息發送
- 與服務層的清晰 API 介面
- 通用的權限檢查和輸入驗證
- 一致的使用者體驗設計模式
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Union, Callable
from datetime import datetime
import discord
from discord.ext import commands

from core.exceptions import (
    BotError,
    DiscordError,
    ValidationError,
    ServicePermissionError,
    discord_error_handler,
    handle_errors
)
from core.base_service import BaseService, service_registry

# 設定日誌記錄器
logger = logging.getLogger('panels.base_panel')


class PanelState:
    """
    面板狀態管理
    
    追蹤面板的當前狀態和上下文信息
    """
    
    def __init__(self, panel_name: str):
        self.panel_name = panel_name
        self.created_at = datetime.now()
        self.last_interaction: Optional[datetime] = None
        self.interaction_count = 0
        self.current_page = 0
        self.context: Dict[str, Any] = {}
        self.user_data: Dict[str, Any] = {}
    
    def update_interaction(self):
        """更新互動時間和計數"""
        self.last_interaction = datetime.now()
        self.interaction_count += 1
    
    def set_context(self, key: str, value: Any):
        """設定上下文資料"""
        self.context[key] = value
    
    def get_context(self, key: str, default: Any = None) -> Any:
        """獲取上下文資料"""
        return self.context.get(key, default)
    
    def set_user_data(self, user_id: int, key: str, value: Any):
        """設定使用者特定資料"""
        if user_id not in self.user_data:
            self.user_data[user_id] = {}
        self.user_data[user_id][key] = value
    
    def get_user_data(self, user_id: int, key: str, default: Any = None) -> Any:
        """獲取使用者特定資料"""
        return self.user_data.get(user_id, {}).get(key, default)


class BasePanel(ABC):
    """
    面板基礎抽象類別
    
    所有 Discord UI 面板都應該繼承此類別，提供統一的：
    - 嵌入訊息建立和格式化
    - 互動處理和狀態管理
    - 錯誤和成功訊息發送
    - 服務層整合介面
    - 權限驗證和輸入驗證
    """
    
    def __init__(
        self, 
        name: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        color: Optional[discord.Color] = None
    ):
        """
        初始化面板
        
        參數：
            name: 面板名稱，如果不提供則使用類別名稱
            title: 面板標題
            description: 面板描述
            color: 面板主色調
        """
        self.name = name or self.__class__.__name__
        self.title = title or self.name
        self.description = description
        self.color = color or discord.Color.blue()
        self.logger = logging.getLogger(f'panel.{self.name}')
        
        # 狀態管理
        self.state = PanelState(self.name)
        
        # 服務依賴
        self.services: Dict[str, BaseService] = {}
        
        # 互動處理器註冊表
        self.interaction_handlers: Dict[str, Callable] = {}
        
        # 預設設定
        self.default_timeout = 300  # 5分鐘
        self.max_embed_fields = 25
        self.max_embed_description_length = 4096
        self.max_field_value_length = 1024
    
    def add_service(self, service: BaseService, name: Optional[str] = None):
        """
        添加服務依賴
        
        參數：
            service: 服務實例
            name: 服務別名，如果不提供則使用服務名稱
        """
        service_name = name or service.name
        self.services[service_name] = service
        self.logger.debug(f"添加服務依賴：{service_name}")
    
    def get_service(self, name: str) -> Optional[BaseService]:
        """
        獲取服務實例
        
        參數：
            name: 服務名稱
            
        返回：
            服務實例，如果不存在則返回 None
        """
        return self.services.get(name)
    
    def register_interaction_handler(self, custom_id: str, handler: Callable):
        """
        註冊互動處理器
        
        參數：
            custom_id: 互動元件的自定義 ID
            handler: 處理函數
        """
        self.interaction_handlers[custom_id] = handler
        self.logger.debug(f"註冊互動處理器：{custom_id}")
    
    @handle_errors(log_errors=True)
    async def create_embed(
        self,
        title: Optional[str] = None,
        description: Optional[str] = None,
        color: Optional[discord.Color] = None,
        thumbnail_url: Optional[str] = None,
        image_url: Optional[str] = None,
        footer_text: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        fields: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> discord.Embed:
        """
        建立嵌入訊息
        
        參數：
            title: 標題
            description: 描述
            color: 顏色
            thumbnail_url: 縮圖 URL
            image_url: 圖片 URL
            footer_text: 頁腳文字
            timestamp: 時間戳
            fields: 欄位列表
            **kwargs: 其他參數
            
        返回：
            Discord 嵌入訊息
        """
        try:
            # 使用預設值或傳入的值
            embed_title = title or self.title
            embed_description = description or self.description
            embed_color = color or self.color
            
            # 檢查長度限制
            if embed_description and len(embed_description) > self.max_embed_description_length:
                embed_description = embed_description[:self.max_embed_description_length-3] + "..."
                self.logger.warning(f"嵌入描述過長，已截斷到 {self.max_embed_description_length} 字符")
            
            # 建立嵌入
            embed = discord.Embed(
                title=embed_title,
                description=embed_description,
                color=embed_color,
                timestamp=timestamp or datetime.now()
            )
            
            # 設定縮圖和圖片
            if thumbnail_url:
                embed.set_thumbnail(url=thumbnail_url)
            if image_url:
                embed.set_image(url=image_url)
            
            # 設定頁腳
            if footer_text:
                embed.set_footer(text=footer_text)
            else:
                embed.set_footer(text=f"{self.name} | 任務 ID: 1")
            
            # 添加欄位
            if fields:
                field_count = 0
                for field in fields:
                    if field_count >= self.max_embed_fields:
                        self.logger.warning(f"欄位數量超過限制 {self.max_embed_fields}，忽略後續欄位")
                        break
                    
                    field_name = field.get('name', '未命名')
                    field_value = str(field.get('value', ''))
                    field_inline = field.get('inline', False)
                    
                    # 檢查欄位值長度
                    if len(field_value) > self.max_field_value_length:
                        field_value = field_value[:self.max_field_value_length-3] + "..."
                        self.logger.warning(f"欄位值過長，已截斷到 {self.max_field_value_length} 字符")
                    
                    embed.add_field(
                        name=field_name,
                        value=field_value,
                        inline=field_inline
                    )
                    field_count += 1
            
            return embed
            
        except Exception as e:
            self.logger.exception(f"建立嵌入訊息時發生錯誤")
            raise DiscordError(
                f"建立嵌入訊息失敗：{str(e)}",
                discord_error=e if isinstance(e, discord.DiscordException) else None
            )
    
    @discord_error_handler(send_to_user=True, ephemeral=True)
    async def send_error(
        self,
        interaction: discord.Interaction,
        message: str,
        ephemeral: bool = True,
        delete_after: Optional[float] = None
    ) -> None:
        """
        發送錯誤訊息
        
        參數：
            interaction: Discord 互動
            message: 錯誤訊息
            ephemeral: 是否為私人訊息
            delete_after: 自動刪除時間（秒）
        """
        try:
            embed = await self.create_embed(
                title="❌ 錯誤",
                description=message,
                color=discord.Color.red()
            )
            
            if interaction.response.is_done():
                await interaction.followup.send(
                    embed=embed,
                    ephemeral=ephemeral,
                    delete_after=delete_after
                )
            else:
                await interaction.response.send_message(
                    embed=embed,
                    ephemeral=ephemeral,
                    delete_after=delete_after
                )
                
            self.logger.debug(f"發送錯誤訊息：{message}")
            
        except Exception as e:
            self.logger.exception(f"發送錯誤訊息時發生錯誤")
            raise DiscordError(f"發送錯誤訊息失敗：{str(e)}", discord_error=e)
    
    @discord_error_handler(send_to_user=True, ephemeral=True)
    async def send_success(
        self,
        interaction: discord.Interaction,
        message: str,
        ephemeral: bool = False,
        delete_after: Optional[float] = None
    ) -> None:
        """
        發送成功訊息
        
        參數：
            interaction: Discord 互動
            message: 成功訊息
            ephemeral: 是否為私人訊息
            delete_after: 自動刪除時間（秒）
        """
        try:
            embed = await self.create_embed(
                title="✅ 成功",
                description=message,
                color=discord.Color.green()
            )
            
            if interaction.response.is_done():
                await interaction.followup.send(
                    embed=embed,
                    ephemeral=ephemeral,
                    delete_after=delete_after
                )
            else:
                await interaction.response.send_message(
                    embed=embed,
                    ephemeral=ephemeral,
                    delete_after=delete_after
                )
                
            self.logger.debug(f"發送成功訊息：{message}")
            
        except Exception as e:
            self.logger.exception(f"發送成功訊息時發生錯誤")
            raise DiscordError(f"發送成功訊息失敗：{str(e)}", discord_error=e)
    
    @discord_error_handler(send_to_user=True, ephemeral=True)
    async def send_warning(
        self,
        interaction: discord.Interaction,
        message: str,
        ephemeral: bool = True,
        delete_after: Optional[float] = None
    ) -> None:
        """
        發送警告訊息
        
        參數：
            interaction: Discord 互動
            message: 警告訊息
            ephemeral: 是否為私人訊息
            delete_after: 自動刪除時間（秒）
        """
        try:
            embed = await self.create_embed(
                title="⚠️ 警告",
                description=message,
                color=discord.Color.orange()
            )
            
            if interaction.response.is_done():
                await interaction.followup.send(
                    embed=embed,
                    ephemeral=ephemeral,
                    delete_after=delete_after
                )
            else:
                await interaction.response.send_message(
                    embed=embed,
                    ephemeral=ephemeral,
                    delete_after=delete_after
                )
                
            self.logger.debug(f"發送警告訊息：{message}")
            
        except Exception as e:
            self.logger.exception(f"發送警告訊息時發生錯誤")
            raise DiscordError(f"發送警告訊息失敗：{str(e)}", discord_error=e)
    
    @handle_errors(log_errors=True)
    async def validate_permissions(
        self,
        interaction: discord.Interaction,
        action: str,
        service_name: Optional[str] = None
    ) -> bool:
        """
        驗證使用者權限
        
        參數：
            interaction: Discord 互動
            action: 要執行的動作
            service_name: 服務名稱，如果提供則使用該服務的權限驗證
            
        返回：
            是否有權限
        """
        try:
            user_id = interaction.user.id
            guild_id = interaction.guild.id if interaction.guild else None
            
            # 如果指定了服務，使用服務的權限驗證
            if service_name:
                service = self.get_service(service_name)
                if service:
                    return await service.validate_permissions(user_id, guild_id, action)
                else:
                    self.logger.warning(f"找不到服務 {service_name} 進行權限驗證")
                    # 找不到服務時，使用面板自己的權限驗證
                    return await self._validate_permissions(interaction, action)
            
            # 使用面板自己的權限驗證邏輯
            return await self._validate_permissions(interaction, action)
            
        except ServicePermissionError:
            await self.send_error(interaction, "您沒有執行此操作的權限。")
            return False
        except Exception as e:
            self.logger.exception(f"權限驗證時發生錯誤")
            await self.send_error(interaction, "權限驗證失敗，請稍後再試。")
            return False
    
    async def _validate_permissions(
        self,
        interaction: discord.Interaction,
        action: str
    ) -> bool:
        """
        子類別可以覆寫的權限驗證邏輯
        
        預設實作：允許所有操作
        
        參數：
            interaction: Discord 互動
            action: 要執行的動作
            
        返回：
            是否有權限
        """
        return True
    
    @handle_errors(log_errors=True)
    async def validate_input(
        self,
        interaction: discord.Interaction,
        input_data: Dict[str, Any],
        validation_rules: Dict[str, Any]
    ) -> bool:
        """
        驗證使用者輸入
        
        參數：
            interaction: Discord 互動
            input_data: 輸入資料
            validation_rules: 驗證規則
            
        返回：
            是否驗證通過
        """
        try:
            for field, rules in validation_rules.items():
                if field not in input_data:
                    if rules.get('required', False):
                        raise ValidationError(
                            f"缺少必要欄位：{field}",
                            field=field,
                            value=None,
                            expected="必要欄位"
                        )
                    continue
                
                value = input_data[field]
                
                # 檢查類型
                expected_type = rules.get('type')
                if expected_type and not isinstance(value, expected_type):
                    raise ValidationError(
                        f"欄位 {field} 類型錯誤",
                        field=field,
                        value=value,
                        expected=expected_type.__name__
                    )
                
                # 檢查長度
                if isinstance(value, (str, list, dict)):
                    min_length = rules.get('min_length')
                    max_length = rules.get('max_length')
                    
                    if min_length and len(value) < min_length:
                        raise ValidationError(
                            f"欄位 {field} 長度不足",
                            field=field,
                            value=value,
                            expected=f"至少 {min_length} 個字符"
                        )
                    
                    if max_length and len(value) > max_length:
                        raise ValidationError(
                            f"欄位 {field} 長度超限",
                            field=field,
                            value=value,
                            expected=f"最多 {max_length} 個字符"
                        )
                
                # 檢查數值範圍
                if isinstance(value, (int, float)):
                    min_value = rules.get('min_value')
                    max_value = rules.get('max_value')
                    
                    if min_value is not None and value < min_value:
                        raise ValidationError(
                            f"欄位 {field} 值過小",
                            field=field,
                            value=value,
                            expected=f"至少 {min_value}"
                        )
                    
                    if max_value is not None and value > max_value:
                        raise ValidationError(
                            f"欄位 {field} 值過大",
                            field=field,
                            value=value,
                            expected=f"最多 {max_value}"
                        )
                
                # 自定義驗證函數
                custom_validator = rules.get('validator')
                if custom_validator and callable(custom_validator):
                    if not custom_validator(value):
                        raise ValidationError(
                            f"欄位 {field} 驗證失敗",
                            field=field,
                            value=value,
                            expected="符合自定義驗證規則"
                        )
            
            return True
            
        except ValidationError as e:
            await self.send_error(interaction, e.user_message)
            return False
        except Exception as e:
            self.logger.exception(f"輸入驗證時發生錯誤")
            await self.send_error(interaction, "輸入驗證失敗，請檢查輸入格式。")
            return False
    
    @discord_error_handler(send_to_user=True, ephemeral=True)
    async def handle_interaction(self, interaction: discord.Interaction) -> None:
        """
        處理 Discord 互動
        
        這是主要的互動處理入口點，會根據互動類型分發到對應的處理方法
        
        參數：
            interaction: Discord 互動
        """
        try:
            # 更新面板狀態
            self.state.update_interaction()
            
            # 記錄互動
            self.logger.info(f"處理互動：{interaction.data.get('custom_id', 'unknown')} 來自用戶 {interaction.user.id}")
            
            # 根據互動類型分發處理
            if interaction.type == discord.InteractionType.application_command:
                await self._handle_application_command(interaction)
            elif interaction.type == discord.InteractionType.component:
                await self._handle_component_interaction(interaction)
            elif interaction.type == discord.InteractionType.modal_submit:
                await self._handle_modal_submit(interaction)
            else:
                self.logger.warning(f"未支援的互動類型：{interaction.type}")
                await self.send_error(interaction, "不支援的互動類型。")
                
        except Exception as e:
            self.logger.exception(f"處理互動時發生未預期的錯誤")
            await self.send_error(interaction, "處理請求時發生錯誤，請稍後再試。")
    
    async def _handle_application_command(self, interaction: discord.Interaction):
        """處理應用程式命令互動"""
        await self._handle_slash_command(interaction)
    
    async def _handle_component_interaction(self, interaction: discord.Interaction):
        """處理元件互動（按鈕、選單等）"""
        custom_id = interaction.data.get('custom_id')
        if custom_id and custom_id in self.interaction_handlers:
            handler = self.interaction_handlers[custom_id]
            await handler(interaction)
        else:
            await self._handle_component(interaction)
    
    async def _handle_modal_submit(self, interaction: discord.Interaction):
        """處理模態框提交"""
        await self._handle_modal(interaction)
    
    @abstractmethod
    async def _handle_slash_command(self, interaction: discord.Interaction):
        """
        子類別實作的斜線命令處理邏輯
        
        參數：
            interaction: Discord 互動
        """
        pass
    
    async def _handle_component(self, interaction: discord.Interaction):
        """
        子類別可以覆寫的元件互動處理邏輯
        
        預設實作：記錄警告
        
        參數：
            interaction: Discord 互動
        """
        custom_id = interaction.data.get('custom_id', 'unknown')
        self.logger.warning(f"未處理的元件互動：{custom_id}")
        await self.send_warning(interaction, "此功能尚未實現。")
    
    async def _handle_modal(self, interaction: discord.Interaction):
        """
        子類別可以覆寫的模態框處理邏輯
        
        預設實作：記錄警告
        
        參數：
            interaction: Discord 互動
        """
        custom_id = interaction.data.get('custom_id', 'unknown')
        self.logger.warning(f"未處理的模態框提交：{custom_id}")
        await self.send_warning(interaction, "此功能尚未實現。")
    
    def get_panel_info(self) -> Dict[str, Any]:
        """
        獲取面板信息
        
        返回：
            面板狀態和統計信息
        """
        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "color": str(self.color),
            "created_at": self.state.created_at.isoformat(),
            "last_interaction": self.state.last_interaction.isoformat() if self.state.last_interaction else None,
            "interaction_count": self.state.interaction_count,
            "current_page": self.state.current_page,
            "services": list(self.services.keys()),
            "registered_handlers": list(self.interaction_handlers.keys())
        }
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name='{self.name}', interactions={self.state.interaction_count})>"