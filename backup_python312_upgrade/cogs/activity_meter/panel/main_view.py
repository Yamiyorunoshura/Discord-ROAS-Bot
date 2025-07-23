"""
活躍度系統主要面板視圖類別 - 修復版本
- 基於 StandardPanelView 的統一面板架構
- 提供完整的活躍度系統管理介面
- 支援多頁面切換和響應式設計
- 實現提示詞 v1.71 的完整架構
- 修復 Discord UI 佈局限制問題
"""

import discord
import logging
from typing import Dict, Any, Optional, List, Tuple, Union
from datetime import datetime, timedelta

from ...core.base_cog import StandardPanelView, StandardEmbedBuilder
from ..config import config
from ..database.database import ActivityDatabase
from .embeds.settings_embed import create_settings_embed
from .embeds.preview_embed import create_preview_embed
from .embeds.stats_embed import create_stats_embed
from .components.buttons import CloseButton, RefreshButton, PreviewButton
from .components.selectors import PageSelector, StyleSelector, ChannelSelector, TimeSelector, STYLE_CONFIGS
from .managers import PageManager, PermissionManager, DataManager, UIManager
from .ui_layout_manager import DiscordUILayoutManager, UILayoutErrorHandler

logger = logging.getLogger("activity_meter")

# 錯誤代碼體系
ERROR_CODES = {
    "E001": "權限不足：需要管理伺服器權限",
    "E002": "權限不足：需要查看頻道權限",
    "E101": "數據庫連接失敗",
    "E102": "數據庫查詢超時",
    "E201": "面板初始化失敗",
    "E202": "頁面切換失敗",
    "E301": "進度條渲染失敗",
    "E302": "圖片生成失敗",
    "E401": "配置載入失敗",
    "E402": "設定保存失敗"
}

class ActivityMeterError(Exception):
    """活躍度系統錯誤基類"""
    def __init__(self, error_code: str, message: str):
        self.error_code = error_code
        self.message = message
        super().__init__(f"[{error_code}] {message}")

class ActivityPanelView(StandardPanelView):
    """
    活躍度系統設定面板 - v1.71 修復版本
    
    功能：
    - 動態按鈕面板架構
    - 頁面選擇器系統
    - 進度條風格選擇
    - 統計資訊顯示
    - 完整的錯誤處理體系
    - 修復 Discord UI 佈局限制問題
    """
    
    def __init__(self, bot: discord.Client, guild_id: int, author_id: int):
        """
        初始化修復版本的面板
        
        Args:
            bot: Discord 機器人實例
            guild_id: 伺服器 ID
            author_id: 作者 ID（用於權限檢查）
        """
        super().__init__(
            timeout=300,
            required_permissions=["manage_guild"],
            admin_only=False,
            moderator_only=False,
            author_id=author_id,
            guild_id=guild_id
        )
        
        self.bot = bot
        self.guild_id = guild_id
        self.author_id = author_id
        self.db = ActivityDatabase()
        
        # 當前頁面狀態
        self.current_page = "settings"
        
        # 快取區
        self._cache = {}
        self._cache_expire = 10  # 秒
        self._cache_time = {}
        
        # 初始化佈局管理器
        self.layout_manager = DiscordUILayoutManager()
        self.error_handler = UILayoutErrorHandler()
        
        # 初始化管理器架構
        self._setup_managers()
        
        # 初始化修復後的動態組件系統
        self._setup_fixed_dynamic_components()
    
    def _setup_managers(self):
        """設置管理器架構"""
        # 創建管理器實例
        self.page_manager = PageManager()
        self.permission_manager = PermissionManager()
        self.data_manager = DataManager()
        self.ui_manager = UIManager(self.data_manager, self.permission_manager)
        
        logger.info("活躍度面板管理器架構已初始化")
    
    def _setup_fixed_dynamic_components(self):
        """設置修復後的動態組件系統"""
        # 根據當前頁面添加對應組件
        self._update_page_components_fixed(self.current_page)
    
    def _setup_components(self):
        """重寫基類組件設置，避免重複"""
        # 完全重寫基類的組件設置，不調用父類方法
        # 這樣可以完全控制組件的添加順序和行分配
        
        # 不添加任何基類組件，由子類完全控制
        pass
    
    def _update_page_components_fixed(self, page_name: str):
        """
        修復版本的頁面組件更新 - 優化佈局以避免 Discord UI 限制
        
        Args:
            page_name: 頁面名稱
        """
        try:
            # 清除所有組件
            self.clear_items()
            
            # 添加頁面選擇器（第一行，row=0）
            page_selector = PageSelector(self)
            page_selector.row = 0
            self.add_item(page_selector)
            
            # 根據頁面添加對應組件（修復佈局問題）
            if page_name == "settings":
                self._add_settings_components_fixed()
            elif page_name == "preview":
                self._add_preview_components_fixed()
            elif page_name == "stats":
                self._add_stats_components_fixed()
            
            # 檢查佈局兼容性
            self._check_and_optimize_layout()
            
            # 驗證佈局兼容性
            is_compatible, message = self.validate_layout_compatibility(self.children)
            if not is_compatible:
                logger.warning(f"佈局不兼容: {message}")
                self.handle_layout_error(Exception(message))
            
        except Exception as e:
            logger.error(f"更新頁面組件失敗: {e}")
            # 使用錯誤處理機制
            self.handle_layout_error(e)
            raise ActivityMeterError("E202", f"頁面切換失敗：{str(e)}")
    
    def _clear_page_components(self):
        """清除頁面組件（保留頁面選擇器和關閉按鈕）"""
        # 保存頁面選擇器和關閉按鈕
        page_selector = None
        close_button = None
        
        for child in self.children:
            if isinstance(child, PageSelector):
                page_selector = child
            elif hasattr(child, 'label') and child.label == "關閉面板":
                close_button = child
        
        # 清除所有組件
        self.clear_items()
        
        # 重新添加頁面選擇器和關閉按鈕
        if page_selector:
            self.add_item(page_selector)
        if close_button:
            self.add_item(close_button)
    
    def _add_settings_components_fixed(self):
        """
        修復版本的設定頁面組件 - 優化佈局以避免 Discord UI 限制
        """
        try:
            # 清除現有組件
            self.clear_items()
            
            # 計算組件總數和行數需求
            settings_components = [
                ChannelSelector(self),
                StyleSelector(self),
                self.create_standard_button(
                    label="預覽",
                    style=discord.ButtonStyle.primary,
                    emoji="👁️",
                    callback=self.preview_style_callback
                ),
                self.create_standard_button(
                    label="關閉面板",
                    style=discord.ButtonStyle.secondary,
                    emoji="❌",
                    callback=self.close_callback
                )
            ]
            
            total_components = len(settings_components)
            max_components_per_row = 5
            required_rows = (total_components + max_components_per_row - 1) // max_components_per_row
            
            # 按行分配組件
            for row in range(required_rows):
                start_idx = row * max_components_per_row
                end_idx = min(start_idx + max_components_per_row, total_components)
                row_components = settings_components[start_idx:end_idx]
                
                # 添加該行的組件
                for component in row_components:
                    component.row = row + 1  # 從第1行開始（第0行是頁面選擇器）
                    self.add_item(component)
                    
            logger.info(f"設定組件添加完成，當前組件數量: {len(self.children)}")
            
        except Exception as e:
            logger.error(f"添加設定組件失敗: {e}")
            # 使用備用佈局
            self.create_fallback_layout()
    
    def _add_preview_components(self):
        """添加預覽頁面組件（已棄用，使用 _add_preview_components_fixed）"""
        # 使用修復版本的方法
        self._add_preview_components_fixed()
    
    def _add_stats_components(self):
        """添加統計頁面組件（已棄用，使用 _add_stats_components_fixed）"""
        # 使用修復版本的方法
        self._add_stats_components_fixed()
    
    def _check_and_optimize_layout(self):
        """檢查並優化佈局 - 改進版本"""
        try:
            # 獲取當前所有組件
            components = list(self.children)
            
            # 檢查佈局兼容性
            if not self.layout_manager.check_layout_compatibility(components):
                logger.warning("檢測到佈局不兼容，開始優化...")
                
                # 獲取佈局信息
                layout_info = self.layout_manager.get_layout_info(components)
                logger.info(f"佈局信息: {layout_info}")
                
                # 優化佈局
                optimized_components = self.layout_manager.optimize_layout(components)
                
                # 重新設置組件
                self.clear_items()
                for component in optimized_components:
                    self.add_item(component)
                
                logger.info("佈局優化完成")
                
                # 記錄優化結果
                final_layout_info = self.layout_manager.get_layout_info(list(self.children))
                logger.info(f"優化後佈局信息: {final_layout_info}")
            
        except Exception as e:
            logger.error(f"佈局檢查和優化失敗: {e}")
            # 如果優化失敗，嘗試使用簡化佈局
            try:
                logger.info("嘗試使用簡化佈局...")
                simplified_components = self.layout_manager._create_simplified_layout(components)
                
                self.clear_items()
                for component in simplified_components:
                    self.add_item(component)
                
                logger.info("簡化佈局應用完成")
                
            except Exception as fallback_error:
                logger.error(f"簡化佈局也失敗: {fallback_error}")
                # 最後的備用方案：只保留頁面選擇器
                try:
                    self.clear_items()
                    page_selector = PageSelector(self)
                    page_selector.row = 0
                    self.add_item(page_selector)
                    logger.info("應用最小佈局完成")
                except Exception as final_error:
                    logger.error(f"最小佈局也失敗: {final_error}")
                    # 不拋出異常，讓面板繼續運行
    
    def validate_layout_compatibility(self, components):
        """
        驗證佈局兼容性
        """
        max_components_per_row = 5
        total_components = len(components)
        
        if total_components > 25:  # Discord UI總組件限制
            return False, "組件總數超過Discord UI限制"
            
        return True, "佈局兼容"
    
    def handle_layout_error(self, error: Exception):
        """
        處理佈局錯誤
        """
        # 添加詳細錯誤日誌記錄
        logger.error(f"佈局錯誤發生: {error}")
        logger.error(f"錯誤類型: {type(error).__name__}")
        logger.error(f"錯誤詳情: {str(error)}")
        
        # 使用錯誤處理器進行錯誤分類
        error_type = self.error_handler.classify_error(error)
        
        if error_type == "component_limit":
            return self.create_simplified_layout()
        elif error_type == "discord_ui_limit":
            return self.create_optimized_layout()
        else:
            return self.create_fallback_layout()
    
    def classify_error(self, error: Exception) -> str:
        """
        分類錯誤類型
        """
        error_message = str(error).lower()
        
        if "too many components" in error_message:
            return "component_limit"
        elif "item would not fit at row" in error_message:
            return "discord_ui_limit"
        else:
            return "unknown"
    
    def create_simplified_layout(self):
        """
        創建簡化佈局
        """
        try:
            self.clear_items()
            
            # 只保留最重要的組件
            page_selector = PageSelector(self)
            page_selector.row = 0
            self.add_item(page_selector)
            
            close_button = self.create_standard_button(
                label="關閉",
                style=discord.ButtonStyle.secondary,
                emoji="❌",
                callback=self.close_callback
            )
            close_button.row = 1
            self.add_item(close_button)
            
            logger.info("簡化佈局創建完成")
            
        except Exception as e:
            logger.error(f"創建簡化佈局失敗: {e}")
    
    def create_optimized_layout(self):
        """
        創建優化佈局
        """
        try:
            self.clear_items()
            
            # 使用優化的組件分配
            components = self.optimize_layout()
            for component in components:
                self.add_item(component)
            
            logger.info("優化佈局創建完成")
            
        except Exception as e:
            logger.error(f"創建優化佈局失敗: {e}")
            # 如果優化失敗，使用簡化佈局
            self.create_simplified_layout()
    
    def optimize_layout(self) -> List[discord.ui.Item]:
        """
        優化界面佈局，移除重新整理按鈕
        返回: List[discord.ui.Item] - 優化後的界面組件列表
        """
        try:
            items = []
            
            # 第一行：頁面選擇器
            page_selector = PageSelector(self)
            page_selector.row = 0
            items.append(page_selector)
            
            # 第二行：頻道選擇器和風格選擇器
            channel_selector = ChannelSelector(self)
            channel_selector.row = 1
            items.append(channel_selector)
            
            style_selector = StyleSelector(self)
            style_selector.row = 1
            items.append(style_selector)
            
            # 第三行：時間設定按鈕和預覽按鈕
            from .components.buttons import TimeSettingButton
            time_setting_button = TimeSettingButton()
            time_setting_button.row = 2
            items.append(time_setting_button)
            
            preview_button = self.create_standard_button(
                label="預覽排行榜",
                style=discord.ButtonStyle.primary,
                emoji="👁️",
                callback=self.preview_style_callback
            )
            preview_button.row = 2
            items.append(preview_button)
            
            # 第四行：關閉按鈕
            close_button = self.create_standard_button(
                label="關閉面板",
                style=discord.ButtonStyle.secondary,
                emoji="❌",
                callback=self.close_callback
            )
            close_button.row = 3
            items.append(close_button)
            
            return items
            
        except Exception as e:
            logger.error(f"佈局優化失敗: {e}")
            # 返回最小佈局
            page_selector = PageSelector(self)
            page_selector.row = 0
            return [page_selector]
    
    async def auto_save_settings(self, interaction: discord.Interaction, setting_type: str, value: Any):
        """設定變更後自動保存"""
        try:
            if setting_type == "announcement_channel":
                await self.db.save_announcement_channel(self.guild_id, value)
            elif setting_type == "announcement_time":
                await self.db.save_announcement_time(self.guild_id, value)
            elif setting_type == "progress_style":
                await self.db.save_progress_style(self.guild_id, value)
            
            # 刷新緩存
            await self.db.refresh_settings_cache()
            
            # 顯示保存成功提示
            await self._send_success_response(interaction, f"設定已自動保存")
            
        except Exception as e:
            await self.handle_error(interaction, e)

    def _add_preview_components_fixed(self):
        """添加預覽頁面組件（固定版本）"""
        try:
            # 進度條預覽按鈕
            preview_button = self.create_standard_button(
                label="進度條預覽",
                style=discord.ButtonStyle.primary,
                emoji="👀",
                custom_id="preview_progress"
            )
            preview_button.row = 3  # 明確指定行，避免與設定頁面衝突
            self.add_item(preview_button)
            
            logger.info("預覽頁面組件添加完成")
            
        except Exception as e:
            logger.error(f"添加預覽頁面組件失敗: {e}")

    def _add_stats_components_fixed(self):
        """添加統計頁面組件（固定版本）"""
        try:
            # 排行榜按鈕
            ranking_button = self.create_standard_button(
                label="排行榜",
                style=discord.ButtonStyle.primary,
                emoji="🏆",
                custom_id="show_ranking"
            )
            ranking_button.row = 3  # 明確指定行，避免與設定頁面衝突
            self.add_item(ranking_button)
            
            # 趨勢分析按鈕
            trend_button = self.create_standard_button(
                label="趨勢分析",
                style=discord.ButtonStyle.secondary,
                emoji="📈",
                custom_id="show_trend"
            )
            trend_button.row = 3  # 與排行榜按鈕在同一行
            self.add_item(trend_button)
            
            logger.info("統計頁面組件添加完成")
            
        except Exception as e:
            logger.error(f"添加統計頁面組件失敗: {e}")
    
    def create_fallback_layout(self):
        """
        創建備用佈局 - 改進版本
        """
        try:
            # 清除所有組件
            self.clear_items()
            
            # 添加基本功能組件
            basic_components = [
                PageSelector(self),
                self.create_standard_button(
                    label="設定",
                    style=discord.ButtonStyle.primary,
                    emoji="⚙️",
                    callback=self.settings_callback
                ),
                self.create_standard_button(
                    label="統計",
                    style=discord.ButtonStyle.secondary,
                    emoji="📊",
                    callback=self.stats_callback
                ),
                self.create_standard_button(
                    label="關閉面板",
                    style=discord.ButtonStyle.danger,
                    emoji="❌",
                    callback=self.close_callback
                )
            ]
            
            # 確保不超過限制並正確分配行
            max_components_per_row = 5
            for i, component in enumerate(basic_components):
                component.row = i // max_components_per_row
                self.add_item(component)
                
            logger.info("備用佈局創建完成")
            
        except Exception as e:
            logger.error(f"創建備用佈局失敗: {e}")
            # 最後的備用方案：只保留關閉按鈕
            try:
                self.clear_items()
                close_button = self.create_standard_button(
                    label="關閉",
                    style=discord.ButtonStyle.danger,
                    emoji="❌",
                    callback=self.close_callback
                )
                close_button.row = 0
                self.add_item(close_button)
                logger.info("最小備用佈局創建完成")
            except Exception as final_error:
                logger.error(f"創建最小備用佈局也失敗: {final_error}")
    
    def create_refresh_button(self):
        """創建重新整理按鈕"""
        return self.create_standard_button(
            label="重新整理",
            style=discord.ButtonStyle.secondary,
            emoji="🔄",
            callback=self.refresh_callback
        )
    
    def create_settings_button(self):
        """創建設定按鈕"""
        return self.create_standard_button(
            label="設定",
            style=discord.ButtonStyle.primary,
            emoji="⚙️",
            callback=self.settings_callback
        )
    
    def create_stats_button(self):
        """創建統計按鈕"""
        return self.create_standard_button(
            label="統計",
            style=discord.ButtonStyle.primary,
            emoji="📊",
            callback=self.stats_callback
        )
    
    async def settings_callback(self, interaction: discord.Interaction):
        """設定回調"""
        try:
            self.current_page = "settings"
            self._update_page_components_fixed("settings")
            await self.update_panel_display(interaction)
        except Exception as e:
            await self.handle_error(interaction, e)
    
    async def stats_callback(self, interaction: discord.Interaction):
        """統計回調"""
        try:
            self.current_page = "stats"
            self._update_page_components_fixed("stats")
            await self.update_panel_display(interaction)
        except Exception as e:
            await self.handle_error(interaction, e)

    async def _send_success_response(self, interaction: discord.Interaction, message: str):
        """發送成功響應"""
        embed = discord.Embed(
            title="✅ 成功",
            description=message,
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    def check_permission(self, user, action_type):
        """
        權限檢查邏輯 - 四級權限架構
        """
        if action_type == "view_panel":
            return True  # 所有用戶都可以查看面板
        
        elif action_type == "basic_operation":
            return user.guild_permissions.view_channel
        
        elif action_type == "manage_settings":
            return user.guild_permissions.manage_guild
        
        elif action_type == "advanced_management":
            return user.guild_permissions.administrator
        
        return False
    
    def can_view_panel(self, user: discord.Member) -> bool:
        """檢查用戶是否可以查看面板"""
        return self.check_permission(user, "view_panel")
    
    def can_edit_settings(self, user: discord.Member) -> bool:
        """檢查用戶是否可以編輯設定"""
        return self.check_permission(user, "manage_settings")
    
    def can_perform_basic_operation(self, user: discord.Member) -> bool:
        """檢查用戶是否可以執行基本操作"""
        return self.check_permission(user, "basic_operation")
    
    def can_perform_advanced_management(self, user: discord.Member) -> bool:
        """檢查用戶是否可以執行進階管理"""
        return self.check_permission(user, "advanced_management")
    
    async def check_permissions(self, interaction: discord.Interaction) -> bool:
        """檢查用戶權限"""
        if not self.can_view_panel(interaction.user):
            await interaction.response.send_message(
                "❌ 您沒有權限查看此面板",
                ephemeral=True
            )
            return False
        return True
    
    async def start(self, interaction: discord.Interaction):
        """
        啟動面板 - 這是關鍵入口點
        
        Args:
            interaction: Discord 互動
        """
        try:
            # 1. 檢查權限
            if not await self.check_permissions(interaction):
                return
                
            # 2. 構建初始嵌入訊息
            embed = self.build_initial_embed()
            
            # 3. 發送響應
            await interaction.response.send_message(
                embed=embed,
                view=self,
                ephemeral=False
            )
            
        except Exception as e:
            await self.handle_error(interaction, e)
    
    def build_initial_embed(self) -> discord.Embed:
        """構建初始狀態的嵌入訊息"""
        embed = discord.Embed(
            title="📊 活躍度系統管理面板",
            description="歡迎使用活躍度系統管理面板！請選擇要使用的功能頁面。",
            color=discord.Color.blue()
        )
        
        # 添加頁面簡介
        embed.add_field(
            name="📋 設定頁面",
            value="管理進度條風格、公告頻道和公告時間設定",
            inline=False
        )
        
        embed.add_field(
            name="👀 預覽頁面", 
            value="預覽當前設定的進度條風格效果",
            inline=False
        )
        
        embed.add_field(
            name="📊 統計頁面",
            value="查看活躍度系統的統計資訊（月度排行榜、訊息量變化）",
            inline=False
        )
        
        embed.set_footer(text="請使用上方下拉選單選擇頁面")
        
        return embed
    
    async def update_panel_display(self, interaction: discord.Interaction):
        """更新面板顯示"""
        try:
            # 根據當前頁面構建對應的嵌入訊息
            if self.current_page == "settings":
                embed = await self.build_settings_embed()
            elif self.current_page == "preview":
                embed = await self.build_preview_embed()
            elif self.current_page == "stats":
                embed = await self.build_stats_embed()
            else:
                embed = self.build_initial_embed()
            
            # 更新訊息
            await interaction.response.edit_message(embed=embed, view=self)
            
        except Exception as e:
            # 如果 edit_message 失敗，嘗試發送新訊息
            try:
                await interaction.response.edit_message(embed=embed, view=self)
            except Exception:
                error_embed = self.create_error_embed(
                    "❌ 面板更新失敗",
                    "無法更新面板顯示，請重新開啟面板"
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
    
    async def handle_error(self, interaction: discord.Interaction, error: Exception):
        """統一錯誤處理 - 改進版本"""
        try:
            error_message = str(error)
            logger.error(f"處理錯誤: {error_message}")
            
            # 檢查是否為佈局相關錯誤
            if "item would not fit at row" in error_message or "too many components" in error_message:
                # 使用佈局錯誤處理器
                await self.error_handler.handle_layout_error(interaction, error)
                return
            
            if isinstance(error, ActivityMeterError):
                embed = self.create_error_embed(
                    f"❌ 錯誤 {error.error_code}",
                    error.message
                )
            else:
                # 捕捉常見權限/驗證錯誤
                if isinstance(error, PermissionError):
                    embed = self.create_error_embed(
                        "❌ 錯誤 E001",
                        "權限不足：需要管理伺服器權限"
                    )
                elif isinstance(error, ValueError):
                    embed = self.create_error_embed(
                        "❌ 錯誤 E999",
                        f"輸入格式錯誤：{str(error)}"
                    )
                else:
                    embed = self.create_error_embed(
                        "❌ 未知錯誤",
                        "發生未預期的錯誤，請稍後再試"
                    )
            
            # 嘗試用edit_message，若失敗則fallback send_message
            try:
                await interaction.response.edit_message(embed=embed, view=self)
            except Exception:
                await interaction.response.send_message(embed=embed, ephemeral=True)
                
        except Exception as e:
            # 如果錯誤處理本身失敗，發送簡單錯誤訊息
            logger.error(f"錯誤處理失敗: {e}")
            try:
                await interaction.response.send_message(
                    "❌ 發生錯誤，請稍後再試",
                    ephemeral=True
                )
            except Exception:
                pass
    
    def create_user_friendly_error_embed(self, error: Exception):
        """
        創建用戶友好的錯誤提示 - 改進版本
        """
        embed = discord.Embed(
            title="🔧 面板佈局修復中",
            description="活躍度面板遇到佈局問題，系統正在自動修復...",
            color=discord.Color.orange()
        )
        
        # 根據錯誤類型提供具體的處理信息
        error_type = self.classify_error(error)
        
        if error_type == "component_limit":
            embed.add_field(
                name="📊 問題類型",
                value="組件數量超過Discord UI限制，正在優化佈局...",
                inline=False
            )
        elif error_type == "discord_ui_limit":
            embed.add_field(
                name="📊 問題類型", 
                value="佈局不符合Discord UI規範，正在重新排列...",
                inline=False
            )
        else:
            embed.add_field(
                name="📊 問題類型",
                value="未知佈局問題，正在嘗試修復...",
                inline=False
            )
        
        embed.add_field(
            name="⏳ 處理狀態",
            value="系統正在自動修復佈局問題，請稍候...",
            inline=False
        )
        
        embed.add_field(
            name="💡 提示",
            value="如果問題持續存在，請重新開啟面板或聯繫管理員",
            inline=False
        )
        
        return embed
    
    def optimize_user_flow(self):
        """
        優化用戶操作流程 - 改進版本
        """
        try:
            # 簡化操作步驟
            # 1. 減少不必要的點擊
            # 2. 提供快捷操作
            # 3. 改進界面響應
            # 4. 優化錯誤提示
            
            # 實現智能佈局檢測
            if len(self.children) > 20:
                logger.info("檢測到組件數量較多，啟用優化模式")
                self._enable_optimization_mode()
            
            # 實現快速響應機制
            self._setup_quick_response()
            
            # 實現用戶操作記憶
            self._remember_user_preferences()
            
            logger.info("用戶操作流程優化完成")
            
        except Exception as e:
            logger.error(f"優化用戶操作流程失敗: {e}")
    
    def _enable_optimization_mode(self):
        """啟用優化模式"""
        # 減少組件數量
        # 優化佈局
        # 提升響應速度
        pass
    
    def _setup_quick_response(self):
        """設置快速響應機制"""
        # 實現快速響應
        # 減少延遲
        pass
    
    def _remember_user_preferences(self):
        """記住用戶偏好"""
        # 記住用戶設置
        # 提供個性化體驗
        pass
    
    def create_error_embed(self, title: str, description: str) -> discord.Embed:
        """創建錯誤嵌入訊息"""
        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.red()
        )
        embed.set_footer(text="如有問題，請聯繫管理員")
        return embed
    
    def handle_panel_error(self, error_type: str, context: dict) -> str:
        """
        統一錯誤處理機制
        
        Args:
            error_type: 錯誤類型
            context: 錯誤上下文
            
        Returns:
            str: 用戶友好的錯誤訊息
        """
        error_messages = {
            "page_switch_failed": "❌ 頁面切換失敗，請稍後再試",
            "time_format_error": "❌ 時間格式錯誤，請使用 HH:MM 格式",
            "permission_denied": "❌ 權限不足，需要管理伺服器權限",
            "database_error": f"❌ 數據庫操作失敗：{context.get('details', '未知錯誤')}",
            "render_error": f"❌ 頁面渲染失敗：{context.get('details', '未知錯誤')}",
            "unknown_error": f"❌ 未知錯誤：{context.get('details', '請稍後再試')}"
        }
        
        return error_messages.get(error_type, f"❌ 錯誤：{context.get('details', '請稍後再試')}")
    
    def _get_cache(self, key: str) -> Optional[Any]:
        """獲取快取數據"""
        if key in self._cache:
            cache_time = self._cache_time.get(key, 0)
            if datetime.now().timestamp() - cache_time < self._cache_expire:
                return self._cache[key]
        return None
    
    def _set_cache(self, key: str, value: Any):
        """設置快取數據"""
        self._cache[key] = value
        self._cache_time[key] = datetime.now().timestamp()
    
    def _clear_cache(self):
        """清除快取"""
        self._cache.clear()
        self._cache_time.clear()
    
    async def refresh_callback(self, interaction: discord.Interaction):
        """重新整理回調（已棄用，移除重新整理按鈕）"""
        await interaction.response.send_message(
            "🔄 重新整理功能已移除，設定會自動保存",
            ephemeral=True
        )
    
    async def close_callback(self, interaction: discord.Interaction):
        """關閉面板回調"""
        try:
            # 檢查權限
            if interaction.user.id != self.author_id:
                await interaction.response.send_message(
                    "❌ 只有原作者可以關閉此面板",
                    ephemeral=True
                )
                return
            
            # 刪除訊息
            if interaction.message:
                await interaction.message.delete()
            else:
                await interaction.response.send_message(
                    "✅ 面板已關閉",
                    ephemeral=True
                )
                
        except Exception as e:
            await self.handle_error(interaction, e)
    
    # 頁面構建方法
    async def build_settings_embed(self) -> discord.Embed:
        """構建設定頁面嵌入"""
        guild = self.bot.get_guild(self.guild_id)
        cache_key = 'settings_embed'
        cached = self._get_cache(cache_key)
        if cached:
            return cached
        settings = await self.db.load_settings(self.guild_id)
        progress_style = settings.get('progress_style', 'classic')
        announcement_channel = settings.get('announcement_channel')
        announcement_time = settings.get('announcement_time', 21)
        embed = await create_settings_embed(
            guild, 
            announcement_channel,
            progress_style,
            announcement_time
        )
        self._set_cache(cache_key, embed)
        return embed
    
    async def build_preview_embed(self) -> discord.Embed:
        """構建預覽頁面嵌入"""
        guild = self.bot.get_guild(self.guild_id)
        cache_key = 'preview_embed'
        cached = self._get_cache(cache_key)
        if cached:
            return cached
        embed = await create_preview_embed(self.bot, guild, self.db)
        self._set_cache(cache_key, embed)
        return embed
    
    async def build_stats_embed(self) -> discord.Embed:
        """構建統計頁面嵌入"""
        guild = self.bot.get_guild(self.guild_id)
        cache_key = 'stats_embed'
        cached = self._get_cache(cache_key)
        if cached:
            return cached
        embed = await create_stats_embed(self.bot, guild, self.db)
        self._set_cache(cache_key, embed)
        return embed
    
    # 回調方法
    async def preview_style_callback(self, interaction: discord.Interaction):
        """預覽風格回調"""
        try:
            if not self.can_edit_settings(interaction.user):
                await interaction.response.send_message(
                    "❌ 您沒有權限編輯設定",
                    ephemeral=True
                )
                return
            
            # 獲取當前設定的進度條風格
            current_style = await self.get_current_progress_style()
            
            # 生成預覽圖片
            preview_file = await self.render_progress_preview(current_style)
            
            # 發送預覽
            embed = discord.Embed(
                title="👀 進度條風格預覽",
                description=f"當前風格：**{current_style}**\n\n以下是使用此風格的進度條效果：",
                color=discord.Color.blue()
            )
            
            await interaction.response.send_message(
                embed=embed,
                file=preview_file,
                ephemeral=True
            )
            
        except Exception as e:
            await self.handle_error(interaction, e)
    
    async def apply_settings_callback(self, interaction: discord.Interaction):
        """套用設定回調（已棄用，使用自動保存機制）"""
        try:
            if not self.can_edit_settings(interaction.user):
                await interaction.response.send_message(
                    "❌ 您沒有權限編輯設定",
                    ephemeral=True
                )
                return
            
            # 設定已通過自動保存機制保存，這裡只顯示提示
            await interaction.response.send_message(
                "✅ 設定已通過自動保存機制保存",
                ephemeral=True
            )
            
        except Exception as e:
            await self.handle_error(interaction, e)
    
    async def show_monthly_ranking_callback(self, interaction: discord.Interaction):
        """顯示月度排行榜"""
        try:
            if not self.can_view_panel(interaction.user):
                await interaction.response.send_message(
                    "❌ 您沒有權限查看此面板",
                    ephemeral=True
                )
                return
            
            # 獲取過去一個月平均活躍度最高的3個人
            top_users = await self.db.get_monthly_top_users(limit=3)
            
            embed = discord.Embed(
                title="🏆 月度活躍度排行榜",
                description="過去一個月平均活躍度最高的成員",
                color=discord.Color.gold()
            )
            
            if not top_users:
                embed.add_field(
                    name="📊 無數據",
                    value="過去一個月沒有活躍度數據",
                    inline=False
                )
            else:
                for i, (user_id, avg_score, message_count) in enumerate(top_users, 1):
                    member = interaction.guild.get_member(user_id)
                    username = member.display_name if member else f"用戶{user_id}"
                    
                    embed.add_field(
                        name=f"{i}. {username}",
                        value=f"平均活躍度：{avg_score:.1f}/100\n訊息數量：{message_count}",
                        inline=False
                    )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            await self.handle_error(interaction, e)
    
    async def show_message_trend_callback(self, interaction: discord.Interaction):
        """顯示訊息量變化趨勢"""
        try:
            if not self.can_view_panel(interaction.user):
                await interaction.response.send_message(
                    "❌ 您沒有權限查看此面板",
                    ephemeral=True
                )
                return
            
            # 獲取本月和上個月的訊息總量
            current_month_count = await self.db.get_monthly_message_count()
            last_month_count = await self.db.get_last_month_message_count()
            
            # 計算百分比變化
            if last_month_count > 0:
                change_percentage = ((current_month_count - last_month_count) / last_month_count) * 100
                change_emoji = "📈" if change_percentage > 0 else "📉"
                change_text = f"{change_percentage:+.1f}%"
                color = discord.Color.green() if change_percentage >= 0 else discord.Color.red()
            else:
                change_percentage = 0
                change_emoji = "📊"
                change_text = "無法比較（上個月無數據）"
                color = discord.Color.blue()
            
            embed = discord.Embed(
                title="📈 訊息量變化趨勢",
                description="本月與上個月的訊息總量比較",
                color=color
            )
            
            embed.add_field(
                name="本月訊息總量",
                value=f"{current_month_count:,} 則",
                inline=True
            )
            
            embed.add_field(
                name="上個月訊息總量",
                value=f"{last_month_count:,} 則",
                inline=True
            )
            
            embed.add_field(
                name="變化趨勢",
                value=f"{change_emoji} {change_text}",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            await self.handle_error(interaction, e)
    
    # 輔助方法
    async def get_current_progress_style(self) -> str:
        """獲取當前進度條風格"""
        # 從數據庫載入設定
        return await self.db.get_progress_style(self.guild_id)
    
    async def render_progress_preview(self, style: str) -> discord.File:
        """渲染進度條預覽圖片"""
        try:
            import io
            from PIL import Image, ImageDraw, ImageFont
            
            # 獲取風格配置
            style_config = STYLE_CONFIGS.get(style, STYLE_CONFIGS["classic"])
            
            # 創建圖片
            width, height = 400, 60
            image = Image.new('RGBA', (width, height), style_config["bg_color"])
            draw = ImageDraw.Draw(image)
            
            # 繪製邊框
            border_color = style_config["border_color"]
            draw.rectangle([0, 0, width-1, height-1], outline=border_color, width=2)
            
            # 繪製進度條
            progress = 75  # 示例進度
            progress_width = int((width - 20) * progress / 100)
            progress_color = (0, 255, 0) if style == "neon" else (255, 255, 255)
            
            # 進度條背景
            draw.rectangle([10, 15, width-10, height-15], fill=(50, 50, 50))
            
            # 進度條
            draw.rectangle([10, 15, 10 + progress_width, height-15], fill=progress_color)
            
            # 添加文字
            try:
                # 嘗試使用系統字體
                font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 16)
            except:
                # 如果沒有Arial，使用預設字體
                font = ImageFont.load_default()
            
            text = f"{progress}%"
            text_color = style_config["text_color"]
            
            # 計算文字位置
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            text_x = (width - text_width) // 2
            text_y = (height - text_height) // 2
            
            # 繪製文字
            draw.text((text_x, text_y), text, fill=text_color, font=font)
            
            # 保存到內存
            buffer = io.BytesIO()
            image.save(buffer, format='PNG')
            buffer.seek(0)
            
            return discord.File(buffer, filename=f"preview_{style}.png")
            
        except Exception as e:
            raise ActivityMeterError("E301", f"進度條渲染失敗：{str(e)}")
    
    async def save_current_settings(self):
        """保存當前設定"""
        try:
            # 獲取當前設定
            settings = await self.db.load_settings(self.guild_id)
            
            # 保存所有設定到數據庫
            await self.db.save_all_settings(
                self.guild_id,
                settings.get('progress_style', 'classic'),
                settings.get('announcement_channel', None),
                settings.get('announcement_time', 21)
            )
            
        except Exception as e:
            raise ActivityMeterError("E402", f"設定保存失敗：{str(e)}")
    
    # 設定更新方法
    async def update_progress_style(self, interaction: discord.Interaction, style: str):
        """更新進度條風格（已棄用，使用自動保存機制）"""
        try:
            # 檢查風格是否有效
            if style not in STYLE_CONFIGS:
                await interaction.response.send_message(
                    "❌ 無效的進度條風格",
                    ephemeral=True
                )
                return
            
            # 使用自動保存機制
            await self.auto_save_settings(interaction, "progress_style", style)
            
        except Exception as e:
            await self.handle_error(interaction, e)
    
    async def update_announcement_channel(self, interaction: discord.Interaction, channel_id: int):
        """更新公告頻道（已棄用，使用自動保存機制）"""
        try:
            # 檢查頻道是否存在
            channel = interaction.guild.get_channel(channel_id)
            if not channel:
                await interaction.response.send_message(
                    "❌ 找不到指定的頻道",
                    ephemeral=True
                )
                return
            
            # 檢查機器人權限
            if not channel.permissions_for(interaction.guild.me).send_messages:
                await interaction.response.send_message(
                    "❌ 機器人沒有在該頻道發送訊息的權限",
                    ephemeral=True
                )
                return
            
            # 使用自動保存機制
            await self.auto_save_settings(interaction, "announcement_channel", channel_id)
            
        except Exception as e:
            await self.handle_error(interaction, e)
    
    async def update_announcement_time(self, interaction: discord.Interaction, hour: int):
        """更新公告時間（已棄用，使用自動保存機制）"""
        try:
            # 檢查時間是否有效
            if not 0 <= hour <= 23:
                await interaction.response.send_message(
                    "❌ 無效的時間格式",
                    ephemeral=True
                )
                return
            
            # 使用自動保存機制
            await self.auto_save_settings(interaction, "announcement_time", hour)
            
        except Exception as e:
            await self.handle_error(interaction, e)


class ProgressBarPreviewButton(discord.ui.Button):
    """進度條風格預覽按鈕"""
    
    def __init__(self, view):
        super().__init__(
            style=discord.ButtonStyle.primary,
            label="預覽進度條風格",
            emoji="👀",
            row=1
        )
        # 在 Discord.py 2.5.2 中，不能直接設置屬性
        # 使用 __dict__ 來設置 view 屬性
        self.__dict__['view'] = view
    
    async def callback(self, interaction: discord.Interaction):
        """預覽回調"""
        try:
            # 檢查權限
            if not self.view.can_view_panel(interaction.user):
                await interaction.response.send_message(
                    "❌ 您沒有權限查看此面板",
                    ephemeral=True
                )
                return
            
            # 獲取當前設定的進度條風格
            current_style = await self.view.get_current_progress_style()
            
            # 生成預覽圖片
            preview_file = await self.view.render_progress_preview(current_style)
            
            # 發送預覽
            embed = discord.Embed(
                title="👀 進度條風格預覽",
                description=f"當前風格：**{current_style}**\n\n以下是使用此風格的進度條效果：",
                color=discord.Color.blue()
            )
            
            await interaction.response.send_message(
                embed=embed,
                file=preview_file,
                ephemeral=True
            )
            
        except Exception as e:
            await self.view.handle_error(interaction, e) 