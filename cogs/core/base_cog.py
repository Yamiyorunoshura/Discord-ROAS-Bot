"""
🏗️ 基礎Cog類別
Discord ADR Bot v1.6 - 提供依賴注入功能的基礎Cog

特性：
- 依賴注入支持
- 統一的初始化和清理邏輯
- 錯誤處理封裝
- 生命週期管理
- 標準面板視圖基類

作者：Discord ADR Bot 架構師
版本：v1.6
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Type, TypeVar, Optional, Any, Dict, List, Callable, Union, Tuple
import discord
from discord.ext import commands

from .dependency_container import get_global_container, DependencyContainer
from .error_handler import error_handler

# 設置日誌
logger = logging.getLogger(__name__)

# 類型變量
T = TypeVar('T')

class BaseCog(commands.Cog):
    """
    基礎Cog類別
    
    提供依賴注入功能和統一的生命週期管理
    所有業務Cog都應該繼承此類別
    """
    
    def __init__(self, bot: commands.Bot):
        """
        初始化基礎Cog
        
        Args:
            bot: Discord 機器人實例
        """
        self.bot = bot
        self._container: Optional[DependencyContainer] = None
        self._initialized = False
        self._services = {}  # 緩存解析的服務
        
        # 啟動初始化任務
        bot.loop.create_task(self._initialize_cog())
    
    async def _initialize_cog(self):
        """內部初始化方法"""
        try:
            # 獲取依賴容器
            self._container = await get_global_container()
            
            # 執行子類的初始化
            await self.initialize()
            
            self._initialized = True
            logger.info(f"【{self.__class__.__name__}】Cog 初始化完成")
            
        except Exception as e:
            logger.error(f"【{self.__class__.__name__}】Cog 初始化失敗: {e}")
            raise
    
    @abstractmethod
    async def initialize(self):
        """
        子類實現的初始化方法
        
        在此方法中進行：
        - 服務註冊
        - 資料庫初始化
        - 其他初始化邏輯
        """
        pass
    
    async def resolve_service(self, service_type: Type[T], scope: Optional[str] = None) -> T:
        """
        解析服務實例
        
        Args:
            service_type: 服務類型
            scope: 作用域名稱
            
        Returns:
            T: 服務實例
        """
        if not self._container:
            raise RuntimeError(f"【{self.__class__.__name__}】依賴容器未初始化")
        
        # 檢查緩存
        cache_key = f"{service_type.__name__}_{scope or 'default'}"
        if cache_key in self._services:
            return self._services[cache_key]
        
        # 解析服務
        service = await self._container.resolve(service_type, scope)
        
        # 緩存服務（僅對單例和作用域服務）
        descriptor = self._container._services.get(service_type)
        if descriptor and descriptor.lifetime.value in ['singleton', 'scoped']:
            self._services[cache_key] = service
        
        return service
    
    def register_service(self, service_type: Type[T], implementation_type: Optional[Type[T]] = None, 
                        lifetime: str = "transient") -> 'BaseCog':
        """
        註冊服務到依賴容器
        
        Args:
            service_type: 服務類型
            implementation_type: 實現類型
            lifetime: 生命週期 ("transient", "singleton", "scoped")
            
        Returns:
            BaseCog: 支持鏈式調用
        """
        if not self._container:
            raise RuntimeError(f"【{self.__class__.__name__}】依賴容器未初始化")
        
        if lifetime == "singleton":
            self._container.register_singleton(service_type, implementation_type)
        elif lifetime == "scoped":
            self._container.register_scoped(service_type, implementation_type)
        else:
            self._container.register_transient(service_type, implementation_type)
        
        logger.debug(f"【{self.__class__.__name__}】註冊服務: {service_type.__name__} ({lifetime})")
        return self
    
    def register_factory(self, service_type: Type[T], factory, lifetime: str = "transient") -> 'BaseCog':
        """
        註冊工廠方法服務
        
        Args:
            service_type: 服務類型
            factory: 工廠方法
            lifetime: 生命週期
            
        Returns:
            BaseCog: 支持鏈式調用
        """
        if not self._container:
            raise RuntimeError(f"【{self.__class__.__name__}】依賴容器未初始化")
        
        from .dependency_container import ServiceLifetime
        lifetime_enum = ServiceLifetime(lifetime)
        self._container.register_factory(service_type, factory, lifetime_enum)
        
        logger.debug(f"【{self.__class__.__name__}】註冊工廠服務: {service_type.__name__} ({lifetime})")
        return self
    
    def register_instance(self, service_type: Type[T], instance: T) -> 'BaseCog':
        """
        註冊實例服務
        
        Args:
            service_type: 服務類型
            instance: 實例
            
        Returns:
            BaseCog: 支持鏈式調用
        """
        if not self._container:
            raise RuntimeError(f"【{self.__class__.__name__}】依賴容器未初始化")
        
        self._container.register_instance(service_type, instance)
        logger.debug(f"【{self.__class__.__name__}】註冊實例服務: {service_type.__name__}")
        return self
    
    async def create_scope(self, scope_name: Optional[str] = None):
        """
        創建服務作用域
        
        Args:
            scope_name: 作用域名稱
            
        Returns:
            AsyncContextManager: 作用域上下文管理器
        """
        if not self._container:
            raise RuntimeError(f"【{self.__class__.__name__}】依賴容器未初始化")
        
        return self._container.create_scope(scope_name)
    
    def with_error_handler(self, interaction, error_message: str, error_code: int = 500):
        """
        錯誤處理裝飾器
        
        Args:
            interaction: Discord 互動
            error_message: 錯誤訊息
            error_code: 錯誤代碼
            
        Returns:
            Decorator: 錯誤處理裝飾器
        """
        return error_handler(interaction, error_message, error_code)
    
    async def cog_unload(self):
        """Cog卸載時的清理工作"""
        try:
            await self.cleanup()
            logger.info(f"【{self.__class__.__name__}】Cog 卸載完成")
        except Exception as e:
            logger.error(f"【{self.__class__.__name__}】Cog 卸載失敗: {e}")
    
    async def cleanup(self):
        """
        清理資源
        
        子類可以重寫此方法來執行特定的清理邏輯
        """
        # 清理服務緩存
        self._services.clear()
        self._initialized = False
    
    @property
    def is_initialized(self) -> bool:
        """檢查是否已初始化"""
        return self._initialized
    
    @property
    def container(self) -> Optional[DependencyContainer]:
        """獲取依賴容器"""
        return self._container
    
    def get_service_info(self) -> dict:
        """
        獲取服務信息
        
        Returns:
            dict: 服務信息字典
        """
        return {
            'initialized': self._initialized,
            'cached_services': len(self._services),
            'service_names': list(self._services.keys())
        }


class ServiceMixin:
    """
    服務混入類
    
    為非Cog類提供依賴注入功能
    """
    
    def __init__(self):
        self._container: Optional[DependencyContainer] = None
        self._services = {}
    
    async def _ensure_container(self):
        """確保依賴容器已初始化"""
        if not self._container:
            self._container = await get_global_container()
    
    async def resolve(self, service_type: Type[T], scope: Optional[str] = None) -> T:
        """
        解析服務實例
        
        Args:
            service_type: 服務類型
            scope: 作用域名稱
            
        Returns:
            T: 服務實例
        """
        await self._ensure_container()
        
        # 檢查緩存
        cache_key = f"{service_type.__name__}_{scope or 'default'}"
        if cache_key in self._services:
            return self._services[cache_key]
        
        # 解析服務
        service = await self._container.resolve(service_type, scope)
        
        # 緩存服務（僅對單例和作用域服務）
        descriptor = self._container._services.get(service_type)
        if descriptor and descriptor.lifetime.value in ['singleton', 'scoped']:
            self._services[cache_key] = service
        
        return service
    
    def clear_service_cache(self):
        """清理服務緩存"""
        self._services.clear()


async def inject_service(service_type: Type[T], scope: Optional[str] = None) -> T:
    """
    全局服務注入函數
    
    Args:
        service_type: 服務類型
        scope: 作用域名稱
        
    Returns:
        T: 服務實例
    """
    container = await get_global_container()
    return await container.resolve(service_type, scope)


def requires_service(service_type: Type[T], scope: Optional[str] = None):
    """
    服務依賴裝飾器
    
    Args:
        service_type: 服務類型
        scope: 作用域名稱
        
    Returns:
        Decorator: 服務注入裝飾器
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            service = await inject_service(service_type, scope)
            return await func(service, *args, **kwargs)
        return wrapper
    return decorator


class BasePanelView(discord.ui.View, ABC):
    """
    基礎面板視圖類別
    
    提供統一的面板架構：
    - 權限檢查
    - 錯誤處理
    - 響應管理
    - 標準組件
    """
    
    def __init__(
        self,
        *,
        timeout: float = 300.0,
        required_permissions: Optional[List[str]] = None,
        admin_only: bool = False,
        moderator_only: bool = False
    ):
        """
        初始化基礎面板視圖
        
        Args:
            timeout: 超時時間（秒）
            required_permissions: 需要的權限列表
            admin_only: 是否僅限管理員
            moderator_only: 是否僅限版主
        """
        super().__init__(timeout=timeout)
        
        self.required_permissions = required_permissions or []
        self.admin_only = admin_only
        self.moderator_only = moderator_only
        
        # 日誌記錄器
        self.logger = logging.getLogger(self.__class__.__module__)
        
        # 標準樣式
        self.styles = {
            'primary': discord.ButtonStyle.primary,
            'secondary': discord.ButtonStyle.secondary,
            'success': discord.ButtonStyle.success,
            'danger': discord.ButtonStyle.danger,
            'link': discord.ButtonStyle.link
        }
        
        # 標準表情符號
        self.emojis = {
            'success': '✅',
            'error': '❌',
            'warning': '⚠️',
            'info': 'ℹ️',
            'loading': '🔄',
            'close': '❌'
        }
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """
        統一權限檢查
        
        Args:
            interaction: Discord 互動
            
        Returns:
            bool: 是否有權限
        """
        try:
            # 檢查管理員權限
            if self.admin_only:
                if not hasattr(interaction.user, 'guild_permissions') or not interaction.user.guild_permissions.administrator:
                    await self._send_error_response(
                        interaction, 
                        "只有管理員可以使用此功能"
                    )
                    return False
            
            # 檢查版主權限
            if self.moderator_only:
                if not hasattr(interaction.user, 'guild_permissions') or not (
                    interaction.user.guild_permissions.manage_messages or 
                    interaction.user.guild_permissions.administrator
                ):
                    await self._send_error_response(
                        interaction, 
                        "只有版主或管理員可以使用此功能"
                    )
                    return False
            
            # 檢查特定權限
            if self.required_permissions:
                if not hasattr(interaction.user, 'guild_permissions'):
                    await self._send_error_response(
                        interaction,
                        "無法檢查權限"
                    )
                    return False
                
                user_permissions = interaction.user.guild_permissions
                missing_permissions = []
                
                for perm in self.required_permissions:
                    if not getattr(user_permissions, perm, False):
                        missing_permissions.append(perm)
                
                if missing_permissions:
                    await self._send_error_response(
                        interaction,
                        f"缺少必要權限: {', '.join(missing_permissions)}"
                    )
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"權限檢查失敗: {e}")
            await self._send_error_response(
                interaction,
                "權限檢查時發生錯誤"
            )
            return False
    
    async def on_timeout(self) -> None:
        """標準化超時處理"""
        try:
            # 禁用所有按鈕
            for item in self.children:
                if hasattr(item, 'disabled'):
                    item.disabled = True
            
            # 更新消息（如果可能）
            if hasattr(self, 'message') and self.message:
                try:
                    embed = discord.Embed(
                        title="⏰ 操作超時",
                        description="此面板已超時，請重新開啟",
                        color=discord.Color.orange()
                    )
                    await self.message.edit(embed=embed, view=self)
                except (discord.NotFound, discord.Forbidden):
                    pass  # 消息已被刪除或沒有權限編輯
                    
        except Exception as e:
            self.logger.error(f"超時處理失敗: {e}")
    
    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item) -> None:
        """標準化錯誤處理"""
        self.logger.error(f"面板錯誤: {error}", exc_info=True)
        
        # 發送錯誤響應
        await self._send_error_response(
            interaction,
            "操作時發生錯誤，請稍後再試"
        )
    
    async def _send_error_response(self, interaction: discord.Interaction, message: str) -> None:
        """
        發送標準化錯誤響應
        
        Args:
            interaction: Discord 交互對象
            message: 錯誤消息
        """
        embed = discord.Embed(
            title=f"{self.emojis['error']} 錯誤",
            description=message,
            color=discord.Color.red()
        )
        
        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            self.logger.error(f"發送錯誤響應失敗: {e}")
    
    async def _send_success_response(self, interaction: discord.Interaction, message: str) -> None:
        """
        發送標準化成功響應
        
        Args:
            interaction: Discord 交互對象
            message: 成功消息
        """
        embed = discord.Embed(
            title=f"{self.emojis['success']} 成功",
            description=message,
            color=discord.Color.green()
        )
        
        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            self.logger.error(f"發送成功響應失敗: {e}")
    
    async def _send_info_response(self, interaction: discord.Interaction, message: str) -> None:
        """
        發送標準化信息響應
        
        Args:
            interaction: Discord 交互對象
            message: 信息消息
        """
        embed = discord.Embed(
            title=f"{self.emojis['info']} 信息",
            description=message,
            color=discord.Color.blue()
        )
        
        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            self.logger.error(f"發送信息響應失敗: {e}")
    
    def create_standard_button(
        self,
        *,
        label: str,
        style: str = 'secondary',
        emoji: Optional[str] = None,
        disabled: bool = False,
        custom_id: Optional[str] = None,
        callback: Optional[Callable] = None
    ) -> discord.ui.Button:
        """
        創建標準化按鈕
        
        Args:
            label: 按鈕標籤
            style: 按鈕樣式
            emoji: 按鈕 emoji
            disabled: 是否禁用
            custom_id: 自定義 ID
            callback: 回調函數
            
        Returns:
            discord.ui.Button: 標準化按鈕
        """
        button_kwargs = {
            'label': label,
            'style': self.styles.get(style, discord.ButtonStyle.secondary),
            'emoji': emoji,
            'disabled': disabled
        }
        if custom_id is not None:
            button_kwargs['custom_id'] = custom_id
        
        button = discord.ui.Button(**button_kwargs)
        
        if callback:
            button.callback = callback
            
        return button
    
    def create_standard_select(
        self,
        *,
        placeholder: str,
        options: List[discord.SelectOption],
        min_values: int = 1,
        max_values: int = 1,
        disabled: bool = False,
        custom_id: Optional[str] = None,
        callback: Optional[Callable] = None
    ) -> discord.ui.Select:
        """
        創建標準化選擇器
        
        Args:
            placeholder: 佔位符文字
            options: 選項列表
            min_values: 最小選擇數量
            max_values: 最大選擇數量
            disabled: 是否禁用
            custom_id: 自定義 ID
            callback: 回調函數
            
        Returns:
            discord.ui.Select: 標準化選擇器
        """
        select = discord.ui.Select(
            placeholder=placeholder,
            options=options,
            min_values=min_values,
            max_values=max_values,
            disabled=disabled,
            custom_id=custom_id
        )
        
        if callback:
            select.callback = callback
            
        return select
    
    @abstractmethod
    async def get_main_embed(self) -> discord.Embed:
        """
        獲取主要嵌入消息
        
        Returns:
            discord.Embed: 主要嵌入消息
        """
        pass
    
    @abstractmethod
    async def refresh_view(self, interaction: discord.Interaction) -> None:
        """
        刷新視圖
        
        Args:
            interaction: Discord 交互對象
        """
        pass


class StandardPanelView(BasePanelView):
    """
    標準面板視圖基類
    
    提供統一的面板架構和功能：
    - 多頁面支援
    - 統一的組件管理
    - 響應式設計
    - 標準化操作流程
    """
    
    def __init__(
        self,
        *,
        timeout: float = 300.0,
        required_permissions: Optional[List[str]] = None,
        admin_only: bool = False,
        moderator_only: bool = False,
        author_id: Optional[int] = None,
        guild_id: Optional[int] = None
    ):
        """
        初始化標準面板視圖
        
        Args:
            timeout: 超時時間（秒）
            required_permissions: 需要的權限列表
            admin_only: 是否僅限管理員
            moderator_only: 是否僅限版主
            author_id: 作者 ID（用於權限檢查）
            guild_id: 伺服器 ID
        """
        super().__init__(
            timeout=timeout,
            required_permissions=required_permissions,
            admin_only=admin_only,
            moderator_only=moderator_only
        )
        
        self.author_id = author_id
        self.guild_id = guild_id
        self.current_page = "main"
        self.pages = {}
        self.page_data = {}
        self.operation_in_progress = False
        self.message: Optional[discord.Message] = None
        
        # 初始化頁面系統
        self._setup_pages()
        self._setup_components()
    
    def _setup_pages(self):
        """設置頁面系統 - 子類應重寫此方法"""
        self.pages = {
            "main": {
                "title": "主頁面",
                "description": "這是主頁面",
                "embed_builder": self.build_main_embed,
                "components": []
            }
        }
    
    def _setup_components(self):
        """設置組件 - 子類應重寫此方法"""
        # 基本控制按鈕
        self.add_item(self.create_standard_button(
            label="重新整理",
            style="secondary",
            emoji="🔄",
            callback=self.refresh_callback
        ))
        
        self.add_item(self.create_standard_button(
            label="關閉",
            style="danger",
            emoji="❌",
            callback=self.close_callback
        ))
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """
        擴展的權限檢查
        
        Args:
            interaction: Discord 互動
            
        Returns:
            bool: 是否有權限
        """
        # 首先執行基類的權限檢查
        if not await super().interaction_check(interaction):
            return False
        
        # 檢查是否為命令發起者
        if self.author_id and interaction.user.id != self.author_id:
            await self._send_error_response(interaction, "只有命令發起者可以操作此面板")
            return False
        
        return True
    
    async def start(self, interaction: discord.Interaction, page: str = "main"):
        """
        啟動面板
        
        Args:
            interaction: Discord 互動
            page: 初始頁面
        """
        try:
            self.current_page = page
            embed = await self.get_current_embed()
            
            await interaction.response.send_message(embed=embed, view=self, ephemeral=True)
            self.message = await interaction.original_response()
            
        except Exception as e:
            await self.on_error(interaction, e, None)
    
    async def change_page(self, interaction: discord.Interaction, page: str):
        """
        切換頁面
        
        Args:
            interaction: Discord 互動
            page: 目標頁面
        """
        if page not in self.pages:
            await self._send_error_response(interaction, f"頁面 '{page}' 不存在")
            return
        
        try:
            self.current_page = page
            embed = await self.get_current_embed()
            
            await interaction.response.edit_message(embed=embed, view=self)
            
        except Exception as e:
            await self.on_error(interaction, e, None)
    
    async def get_current_embed(self) -> discord.Embed:
        """
        獲取當前頁面的嵌入
        
        Returns:
            discord.Embed: 當前頁面的嵌入
        """
        page_info = self.pages.get(self.current_page)
        if not page_info:
            return StandardEmbedBuilder.create_error_embed(
                "錯誤",
                f"頁面 '{self.current_page}' 不存在"
            )
        
        try:
            embed_builder = page_info.get("embed_builder")
            if embed_builder:
                return await embed_builder()
            else:
                return StandardEmbedBuilder.create_info_embed(
                    page_info.get("title", "未知頁面"),
                    page_info.get("description", "此頁面尚未實現")
                )
        except Exception as e:
            return StandardEmbedBuilder.create_error_embed(
                "頁面載入錯誤",
                f"載入頁面時發生錯誤：{str(e)}"
            )
    
    async def build_main_embed(self) -> discord.Embed:
        """
        構建主頁面嵌入 - 子類應重寫此方法
        
        Returns:
            discord.Embed: 主頁面嵌入
        """
        return StandardEmbedBuilder.create_info_embed(
            "標準面板",
            "這是一個標準面板的主頁面"
        )
    
    async def refresh_callback(self, interaction: discord.Interaction):
        """重新整理回調"""
        try:
            embed = await self.get_current_embed()
            await interaction.response.edit_message(embed=embed, view=self)
            
        except Exception as e:
            await self.on_error(interaction, e, None)
    
    async def close_callback(self, interaction: discord.Interaction):
        """關閉回調"""
        try:
            embed = StandardEmbedBuilder.create_info_embed(
                "面板已關閉",
                "感謝使用！"
            )
            
            # 禁用所有組件
            for item in self.children:
                if hasattr(item, 'disabled'):
                    item.disabled = True
            
            await interaction.response.edit_message(embed=embed, view=self)
            self.stop()
            
        except Exception as e:
            await self.on_error(interaction, e, None)
    
    def add_page(self, page_id: str, title: str, description: str, 
                 embed_builder: Callable, components: Optional[List] = None):
        """
        添加頁面
        
        Args:
            page_id: 頁面 ID
            title: 頁面標題
            description: 頁面描述
            embed_builder: 嵌入構建器
            components: 頁面專用組件
        """
        self.pages[page_id] = {
            "title": title,
            "description": description,
            "embed_builder": embed_builder,
            "components": components or []
        }
    
    def set_page_data(self, page_id: str, data: Any):
        """
        設置頁面數據
        
        Args:
            page_id: 頁面 ID
            data: 頁面數據
        """
        self.page_data[page_id] = data
    
    def get_page_data(self, page_id: str) -> Any:
        """
        獲取頁面數據
        
        Args:
            page_id: 頁面 ID
            
        Returns:
            Any: 頁面數據
        """
        return self.page_data.get(page_id)
    
    async def execute_operation(self, interaction: discord.Interaction, 
                               operation: Callable, operation_name: str, 
                               *args, **kwargs):
        """
        執行操作（防止重複執行）
        
        Args:
            interaction: Discord 互動
            operation: 要執行的操作
            operation_name: 操作名稱
            *args: 操作參數
            **kwargs: 操作關鍵字參數
        """
        if self.operation_in_progress:
            await self._send_error_response(interaction, f"{operation_name}正在進行中，請稍後再試")
            return
        
        try:
            self.operation_in_progress = True
            
            # 禁用所有按鈕
            self._disable_all_buttons(True)
            
            # 顯示進行中狀態
            progress_embed = StandardEmbedBuilder.create_info_embed(
                f"{operation_name}中...",
                "請稍候，操作正在進行中..."
            )
            
            if not interaction.response.is_done():
                await interaction.response.edit_message(embed=progress_embed, view=self)
            else:
                await interaction.edit_original_response(embed=progress_embed, view=self)
            
            # 執行操作
            result = await operation(*args, **kwargs)
            
            # 恢復按鈕狀態
            self._disable_all_buttons(False)
            
            # 重新整理面板
            embed = await self.get_current_embed()
            await interaction.edit_original_response(embed=embed, view=self)
            
            return result
            
        except Exception as e:
            # 恢復按鈕狀態
            self._disable_all_buttons(False)
            await self.on_error(interaction, e, None)
            
        finally:
            self.operation_in_progress = False
    
    def _disable_all_buttons(self, disabled: bool):
        """
        禁用/啟用所有按鈕
        
        Args:
            disabled: 是否禁用
        """
        for item in self.children:
            if hasattr(item, 'disabled'):
                item.disabled = disabled
    
    async def on_timeout(self) -> None:
        """面板超時處理"""
        try:
            # 禁用所有組件
            self._disable_all_buttons(True)
            
            if self.message:
                timeout_embed = StandardEmbedBuilder.create_warning_embed(
                    "面板已超時",
                    "面板已因超時而停用。如需繼續使用，請重新開啟面板。"
                )
                await self.message.edit(embed=timeout_embed, view=self)
                
        except (discord.NotFound, discord.HTTPException):
            pass  # 訊息可能已被刪除
    
    async def get_main_embed(self) -> discord.Embed:
        """實現抽象方法"""
        return await self.build_main_embed()
    
    async def refresh_view(self, interaction: discord.Interaction) -> None:
        """實現抽象方法"""
        await self.refresh_callback(interaction)


class StandardEmbedBuilder:
    """
    標準化嵌入消息構建器
    
    提供一致的嵌入消息樣式和格式
    """
    
    @staticmethod
    def create_info_embed(title: str, description: str, **kwargs) -> discord.Embed:
        """創建信息嵌入"""
        embed = discord.Embed(
            title=f"ℹ️ {title}",
            description=description,
            color=kwargs.get('color', discord.Color.blue())
        )
        
        if 'footer' in kwargs:
            embed.set_footer(text=kwargs['footer'])
        
        if 'timestamp' in kwargs:
            embed.timestamp = kwargs['timestamp']
            
        return embed
    
    @staticmethod
    def create_success_embed(title: str, description: str, **kwargs) -> discord.Embed:
        """創建成功嵌入"""
        embed = discord.Embed(
            title=f"✅ {title}",
            description=description,
            color=kwargs.get('color', discord.Color.green())
        )
        
        if 'footer' in kwargs:
            embed.set_footer(text=kwargs['footer'])
        
        if 'timestamp' in kwargs:
            embed.timestamp = kwargs['timestamp']
            
        return embed
    
    @staticmethod
    def create_error_embed(title: str, description: str, **kwargs) -> discord.Embed:
        """創建錯誤嵌入"""
        embed = discord.Embed(
            title=f"❌ {title}",
            description=description,
            color=kwargs.get('color', discord.Color.red())
        )
        
        if 'footer' in kwargs:
            embed.set_footer(text=kwargs['footer'])
        
        if 'timestamp' in kwargs:
            embed.timestamp = kwargs['timestamp']
            
        return embed
    
    @staticmethod
    def create_warning_embed(title: str, description: str, **kwargs) -> discord.Embed:
        """創建警告嵌入"""
        embed = discord.Embed(
            title=f"⚠️ {title}",
            description=description,
            color=kwargs.get('color', discord.Color.orange())
        )
        
        if 'footer' in kwargs:
            embed.set_footer(text=kwargs['footer'])
        
        if 'timestamp' in kwargs:
            embed.timestamp = kwargs['timestamp']
            
        return embed
    
    @staticmethod
    def create_settings_embed(title: str, settings: Dict[str, Any], **kwargs) -> discord.Embed:
        """創建設置嵌入"""
        embed = discord.Embed(
            title=f"⚙️ {title}",
            color=kwargs.get('color', discord.Color.blue())
        )
        
        for key, value in settings.items():
            embed.add_field(
                name=key,
                value=str(value),
                inline=kwargs.get('inline', True)
            )
        
        if 'footer' in kwargs:
            embed.set_footer(text=kwargs['footer'])
        
        if 'timestamp' in kwargs:
            embed.timestamp = kwargs['timestamp']
            
        return embed
    
    @staticmethod
    def create_stats_embed(title: str, stats: Dict[str, Any], **kwargs) -> discord.Embed:
        """創建統計嵌入"""
        embed = discord.Embed(
            title=f"📊 {title}",
            color=kwargs.get('color', discord.Color.blue())
        )
        
        for key, value in stats.items():
            embed.add_field(
                name=key,
                value=str(value),
                inline=kwargs.get('inline', True)
            )
        
        if 'footer' in kwargs:
            embed.set_footer(text=kwargs['footer'])
        
        if 'timestamp' in kwargs:
            embed.timestamp = kwargs['timestamp']
            
        return embed 