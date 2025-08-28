"""
SubBot擴展系統 - 插件化架構和模塊化設計
Task ID: 3 - 子機器人聊天功能和管理系統開發

這個模組提供：
- 插件系統架構和動態加載
- 模塊化組件設計
- 事件驅動架構
- API擴展和自定義處理器
- 配置管理和熱重載
"""

import asyncio
import logging
import importlib
import inspect
import sys
from typing import Dict, Any, Optional, List, Callable, Type, Protocol, Union
from dataclasses import dataclass, field
from datetime import datetime
from abc import ABC, abstractmethod
from enum import Enum
import weakref
import json
import os
from pathlib import Path

logger = logging.getLogger('services.subbot_extensions')


class PluginType(Enum):
    """插件類型"""
    MESSAGE_PROCESSOR = "message_processor"      # 消息處理器
    AI_PROVIDER = "ai_provider"                 # AI提供商
    CHANNEL_HANDLER = "channel_handler"         # 頻道處理器
    EVENT_LISTENER = "event_listener"           # 事件監聽器
    COMMAND_HANDLER = "command_handler"         # 命令處理器
    MIDDLEWARE = "middleware"                   # 中間件
    INTEGRATION = "integration"                 # 外部集成


class EventType(Enum):
    """事件類型"""
    MESSAGE_RECEIVED = "message_received"
    MESSAGE_SENT = "message_sent"
    BOT_STARTED = "bot_started"
    BOT_STOPPED = "bot_stopped"
    ERROR_OCCURRED = "error_occurred"
    USER_JOINED = "user_joined"
    USER_LEFT = "user_left"
    COMMAND_EXECUTED = "command_executed"
    AI_RESPONSE_GENERATED = "ai_response_generated"


@dataclass
class PluginMetadata:
    """插件元數據"""
    name: str
    version: str
    author: str
    description: str
    plugin_type: PluginType
    dependencies: List[str] = field(default_factory=list)
    min_bot_version: str = "2.4.4"
    enabled: bool = True
    config_schema: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class EventData:
    """事件數據"""
    event_type: EventType
    source: str  # 事件來源（bot_id）
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    processed_by: List[str] = field(default_factory=list)


class SubBotPlugin(ABC):
    """SubBot插件基礎類別"""
    
    def __init__(self, metadata: PluginMetadata):
        self.metadata = metadata
        self.enabled = metadata.enabled
        self.config: Dict[str, Any] = {}
        self.logger = logging.getLogger(f'plugin.{metadata.name}')
        
    @abstractmethod
    async def initialize(self, config: Dict[str, Any]) -> bool:
        """初始化插件"""
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """清理插件"""
        pass
    
    async def reload_config(self, config: Dict[str, Any]) -> bool:
        """重新載入配置"""
        self.config = config
        return True
    
    def get_info(self) -> Dict[str, Any]:
        """獲取插件信息"""
        return {
            'name': self.metadata.name,
            'version': self.metadata.version,
            'author': self.metadata.author,
            'description': self.metadata.description,
            'type': self.metadata.plugin_type.value,
            'enabled': self.enabled,
            'dependencies': self.metadata.dependencies
        }


class MessageProcessor(SubBotPlugin):
    """消息處理器插件"""
    
    @abstractmethod
    async def process_message(self, message_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """處理消息"""
        pass
    
    @abstractmethod
    def can_handle(self, message_data: Dict[str, Any]) -> bool:
        """檢查是否可以處理此消息"""
        pass


class AIProvider(SubBotPlugin):
    """AI提供商插件"""
    
    @abstractmethod
    async def generate_response(
        self, 
        message: str, 
        context: Dict[str, Any]
    ) -> Optional[str]:
        """生成AI回應"""
        pass
    
    @abstractmethod
    def get_models(self) -> List[str]:
        """獲取支援的模型列表"""
        pass


class EventListener(SubBotPlugin):
    """事件監聽器插件"""
    
    @abstractmethod
    async def handle_event(self, event: EventData) -> None:
        """處理事件"""
        pass
    
    @abstractmethod
    def get_subscribed_events(self) -> List[EventType]:
        """獲取訂閱的事件類型"""
        pass


class CommandHandler(SubBotPlugin):
    """命令處理器插件"""
    
    @abstractmethod
    async def handle_command(
        self, 
        command: str, 
        args: List[str], 
        context: Dict[str, Any]
    ) -> Optional[str]:
        """處理命令"""
        pass
    
    @abstractmethod
    def get_commands(self) -> List[str]:
        """獲取支援的命令列表"""
        pass


class PluginRegistry:
    """插件註冊表"""
    
    def __init__(self):
        self.plugins: Dict[str, SubBotPlugin] = {}
        self.plugin_types: Dict[PluginType, List[str]] = {}
        self.dependencies: Dict[str, List[str]] = {}
        self.load_order: List[str] = []
        
        # 初始化插件類型字典
        for plugin_type in PluginType:
            self.plugin_types[plugin_type] = []
    
    def register(self, plugin: SubBotPlugin) -> bool:
        """註冊插件"""
        try:
            plugin_name = plugin.metadata.name
            
            if plugin_name in self.plugins:
                logger.warning(f"插件 {plugin_name} 已存在，將被覆蓋")
            
            self.plugins[plugin_name] = plugin
            
            # 按類型分類
            plugin_type = plugin.metadata.plugin_type
            if plugin_name not in self.plugin_types[plugin_type]:
                self.plugin_types[plugin_type].append(plugin_name)
            
            # 記錄依賴關係
            self.dependencies[plugin_name] = plugin.metadata.dependencies
            
            logger.info(f"插件 {plugin_name} 已註冊")
            return True
            
        except Exception as e:
            logger.error(f"註冊插件失敗: {e}")
            return False
    
    def unregister(self, plugin_name: str) -> bool:
        """取消註冊插件"""
        try:
            if plugin_name not in self.plugins:
                return True
            
            plugin = self.plugins[plugin_name]
            
            # 從類型列表中移除
            plugin_type = plugin.metadata.plugin_type
            if plugin_name in self.plugin_types[plugin_type]:
                self.plugin_types[plugin_type].remove(plugin_name)
            
            # 移除依賴關係
            if plugin_name in self.dependencies:
                del self.dependencies[plugin_name]
            
            # 從加載順序中移除
            if plugin_name in self.load_order:
                self.load_order.remove(plugin_name)
            
            # 移除插件
            del self.plugins[plugin_name]
            
            logger.info(f"插件 {plugin_name} 已取消註冊")
            return True
            
        except Exception as e:
            logger.error(f"取消註冊插件失敗: {e}")
            return False
    
    def get_plugin(self, plugin_name: str) -> Optional[SubBotPlugin]:
        """獲取插件"""
        return self.plugins.get(plugin_name)
    
    def get_plugins_by_type(self, plugin_type: PluginType) -> List[SubBotPlugin]:
        """按類型獲取插件"""
        plugin_names = self.plugin_types.get(plugin_type, [])
        return [self.plugins[name] for name in plugin_names if name in self.plugins]
    
    def list_plugins(self) -> List[Dict[str, Any]]:
        """列出所有插件"""
        return [plugin.get_info() for plugin in self.plugins.values()]
    
    def calculate_load_order(self) -> List[str]:
        """計算插件加載順序（拓撲排序）"""
        visited = set()
        temp_visited = set()
        order = []
        
        def visit(plugin_name: str):
            if plugin_name in temp_visited:
                raise ValueError(f"檢測到循環依賴: {plugin_name}")
            if plugin_name in visited:
                return
            
            temp_visited.add(plugin_name)
            
            # 訪問所有依賴
            dependencies = self.dependencies.get(plugin_name, [])
            for dep in dependencies:
                if dep in self.plugins:
                    visit(dep)
            
            temp_visited.remove(plugin_name)
            visited.add(plugin_name)
            order.append(plugin_name)
        
        # 訪問所有插件
        for plugin_name in self.plugins.keys():
            if plugin_name not in visited:
                visit(plugin_name)
        
        self.load_order = order
        return order


class EventBus:
    """事件總線"""
    
    def __init__(self):
        self.listeners: Dict[EventType, List[Callable]] = {}
        self.event_history: List[EventData] = []
        self.history_limit = 1000
        
        # 為所有事件類型初始化監聽器列表
        for event_type in EventType:
            self.listeners[event_type] = []
    
    def subscribe(self, event_type: EventType, listener: Callable) -> None:
        """訂閱事件"""
        if event_type not in self.listeners:
            self.listeners[event_type] = []
        
        self.listeners[event_type].append(listener)
        logger.debug(f"事件監聽器已訂閱: {event_type.value}")
    
    def unsubscribe(self, event_type: EventType, listener: Callable) -> None:
        """取消訂閱事件"""
        if event_type in self.listeners:
            try:
                self.listeners[event_type].remove(listener)
                logger.debug(f"事件監聽器已取消訂閱: {event_type.value}")
            except ValueError:
                pass
    
    async def publish(self, event: EventData) -> None:
        """發佈事件"""
        logger.debug(f"發佈事件: {event.event_type.value} from {event.source}")
        
        # 添加到歷史記錄
        self.event_history.append(event)
        if len(self.event_history) > self.history_limit:
            self.event_history = self.event_history[-self.history_limit:]
        
        # 通知所有監聽器
        listeners = self.listeners.get(event.event_type, [])
        
        for listener in listeners[:]:  # 使用副本避免修改中的列表問題
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(event)
                else:
                    listener(event)
                
                event.processed_by.append(str(listener))
                
            except Exception as e:
                logger.error(f"事件監聽器處理失敗: {e}")
    
    def get_event_history(
        self, 
        event_type: Optional[EventType] = None,
        limit: int = 100
    ) -> List[EventData]:
        """獲取事件歷史"""
        if event_type:
            filtered_events = [
                event for event in self.event_history 
                if event.event_type == event_type
            ]
            return filtered_events[-limit:]
        
        return self.event_history[-limit:]


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_dir: str = "configs"):
        self.config_dir = Path(config_dir)
        self.configs: Dict[str, Dict[str, Any]] = {}
        self.watchers: Dict[str, asyncio.Task] = {}
        
        # 確保配置目錄存在
        self.config_dir.mkdir(exist_ok=True)
    
    def load_config(self, plugin_name: str) -> Dict[str, Any]:
        """載入插件配置"""
        config_file = self.config_dir / f"{plugin_name}.json"
        
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                self.configs[plugin_name] = config
                logger.info(f"已載入插件 {plugin_name} 的配置")
                return config
            except Exception as e:
                logger.error(f"載入插件配置失敗: {e}")
        
        # 返回空配置
        default_config = {}
        self.configs[plugin_name] = default_config
        return default_config
    
    def save_config(self, plugin_name: str, config: Dict[str, Any]) -> bool:
        """保存插件配置"""
        try:
            config_file = self.config_dir / f"{plugin_name}.json"
            
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            self.configs[plugin_name] = config
            logger.info(f"已保存插件 {plugin_name} 的配置")
            return True
            
        except Exception as e:
            logger.error(f"保存插件配置失敗: {e}")
            return False
    
    def get_config(self, plugin_name: str) -> Dict[str, Any]:
        """獲取插件配置"""
        return self.configs.get(plugin_name, {})
    
    async def watch_config(self, plugin_name: str, callback: Callable) -> None:
        """監控配置文件變化"""
        config_file = self.config_dir / f"{plugin_name}.json"
        
        # 如果已經在監控，先停止
        if plugin_name in self.watchers:
            self.watchers[plugin_name].cancel()
        
        # 啟動新的監控任務
        self.watchers[plugin_name] = asyncio.create_task(
            self._watch_file(config_file, callback)
        )
    
    async def _watch_file(self, file_path: Path, callback: Callable) -> None:
        """監控文件變化"""
        last_modified = None
        
        while True:
            try:
                if file_path.exists():
                    current_modified = file_path.stat().st_mtime
                    
                    if last_modified is not None and current_modified != last_modified:
                        logger.info(f"配置文件已變化: {file_path}")
                        
                        # 重新載入配置
                        plugin_name = file_path.stem
                        new_config = self.load_config(plugin_name)
                        
                        # 調用回調
                        if asyncio.iscoroutinefunction(callback):
                            await callback(plugin_name, new_config)
                        else:
                            callback(plugin_name, new_config)
                    
                    last_modified = current_modified
                
                await asyncio.sleep(1)  # 每秒檢查一次
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"監控配置文件失敗: {e}")
                await asyncio.sleep(5)


class PluginLoader:
    """插件載入器"""
    
    def __init__(self, plugin_dir: str = "plugins"):
        self.plugin_dir = Path(plugin_dir)
        self.loaded_modules: Dict[str, Any] = {}
        
        # 確保插件目錄存在
        self.plugin_dir.mkdir(exist_ok=True)
    
    def discover_plugins(self) -> List[Dict[str, Any]]:
        """發現插件"""
        plugins = []
        
        for plugin_file in self.plugin_dir.glob("*.py"):
            if plugin_file.name.startswith("__"):
                continue
            
            try:
                plugin_info = self._analyze_plugin_file(plugin_file)
                if plugin_info:
                    plugins.append(plugin_info)
            except Exception as e:
                logger.error(f"分析插件文件失敗 {plugin_file}: {e}")
        
        return plugins
    
    def load_plugin(self, plugin_file: Path) -> Optional[SubBotPlugin]:
        """載入單個插件"""
        try:
            module_name = f"plugins.{plugin_file.stem}"
            
            # 如果模組已載入，先移除
            if module_name in sys.modules:
                del sys.modules[module_name]
            
            # 動態載入模組
            spec = importlib.util.spec_from_file_location(module_name, plugin_file)
            if not spec or not spec.loader:
                logger.error(f"無法載入插件規範: {plugin_file}")
                return None
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # 尋找插件類別
            plugin_class = None
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and 
                    issubclass(obj, SubBotPlugin) and 
                    obj != SubBotPlugin):
                    plugin_class = obj
                    break
            
            if not plugin_class:
                logger.error(f"插件文件中未找到有效的插件類別: {plugin_file}")
                return None
            
            # 獲取插件元數據
            metadata = getattr(plugin_class, 'metadata', None)
            if not metadata:
                logger.error(f"插件類別缺少元數據: {plugin_file}")
                return None
            
            # 創建插件實例
            plugin_instance = plugin_class(metadata)
            
            self.loaded_modules[module_name] = module
            logger.info(f"插件載入成功: {metadata.name}")
            
            return plugin_instance
            
        except Exception as e:
            logger.error(f"載入插件失敗 {plugin_file}: {e}")
            return None
    
    def _analyze_plugin_file(self, plugin_file: Path) -> Optional[Dict[str, Any]]:
        """分析插件文件"""
        try:
            with open(plugin_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 簡單的元數據提取
            plugin_info = {
                'file': str(plugin_file),
                'name': plugin_file.stem,
                'size': plugin_file.stat().st_size,
                'modified': datetime.fromtimestamp(plugin_file.stat().st_mtime)
            }
            
            # 這裡可以添加更複雜的分析邏輯
            # 例如解析文檔字符串中的元數據
            
            return plugin_info
            
        except Exception as e:
            logger.error(f"分析插件文件失敗: {e}")
            return None


class ExtensionManager:
    """擴展管理器 - 統一管理插件系統"""
    
    def __init__(self, plugin_dir: str = "plugins", config_dir: str = "configs"):
        self.registry = PluginRegistry()
        self.event_bus = EventBus()
        self.config_manager = ConfigManager(config_dir)
        self.plugin_loader = PluginLoader(plugin_dir)
        
        # 運行狀態
        self.initialized = False
        self.plugins_loaded = False
        
        # 統計信息
        self.load_stats = {
            'total_discovered': 0,
            'successfully_loaded': 0,
            'failed_to_load': 0,
            'last_load_time': None
        }
        
        logger.info("擴展管理器已初始化")
    
    async def initialize(self) -> bool:
        """初始化擴展管理器"""
        try:
            logger.info("正在初始化擴展管理器...")
            
            # 發現並載入所有插件
            await self.load_all_plugins()
            
            # 設置配置監控
            await self._setup_config_watching()
            
            self.initialized = True
            logger.info("擴展管理器初始化完成")
            
            return True
            
        except Exception as e:
            logger.error(f"擴展管理器初始化失敗: {e}")
            return False
    
    async def cleanup(self) -> None:
        """清理擴展管理器"""
        try:
            logger.info("正在清理擴展管理器...")
            
            # 清理所有插件
            for plugin_name, plugin in list(self.registry.plugins.items()):
                try:
                    await plugin.cleanup()
                except Exception as e:
                    logger.error(f"清理插件 {plugin_name} 失敗: {e}")
            
            # 停止配置監控
            for task in self.config_manager.watchers.values():
                task.cancel()
            
            self.initialized = False
            logger.info("擴展管理器清理完成")
            
        except Exception as e:
            logger.error(f"擴展管理器清理失敗: {e}")
    
    async def load_all_plugins(self) -> Dict[str, Any]:
        """載入所有插件"""
        logger.info("開始載入所有插件...")
        
        # 發現插件
        discovered_plugins = self.plugin_loader.discover_plugins()
        self.load_stats['total_discovered'] = len(discovered_plugins)
        
        loaded_count = 0
        failed_count = 0
        
        for plugin_info in discovered_plugins:
            try:
                plugin_file = Path(plugin_info['file'])
                
                # 載入插件
                plugin = self.plugin_loader.load_plugin(plugin_file)
                if not plugin:
                    failed_count += 1
                    continue
                
                # 註冊插件
                if self.registry.register(plugin):
                    # 載入配置
                    config = self.config_manager.load_config(plugin.metadata.name)
                    
                    # 初始化插件
                    if await plugin.initialize(config):
                        loaded_count += 1
                        logger.info(f"插件 {plugin.metadata.name} 載入成功")
                    else:
                        failed_count += 1
                        logger.error(f"插件 {plugin.metadata.name} 初始化失敗")
                else:
                    failed_count += 1
                
            except Exception as e:
                logger.error(f"載入插件失敗: {e}")
                failed_count += 1
        
        # 計算載入順序
        try:
            load_order = self.registry.calculate_load_order()
            logger.info(f"插件載入順序: {' -> '.join(load_order)}")
        except Exception as e:
            logger.error(f"計算插件載入順序失敗: {e}")
        
        # 更新統計信息
        self.load_stats.update({
            'successfully_loaded': loaded_count,
            'failed_to_load': failed_count,
            'last_load_time': datetime.now()
        })
        
        self.plugins_loaded = True
        
        # 發佈載入完成事件
        await self.event_bus.publish(EventData(
            event_type=EventType.BOT_STARTED,
            source="extension_manager",
            data={
                'plugins_loaded': loaded_count,
                'plugins_failed': failed_count,
                'total_plugins': len(discovered_plugins)
            }
        ))
        
        logger.info(f"插件載入完成：成功 {loaded_count}，失敗 {failed_count}")
        
        return self.load_stats
    
    async def reload_plugin(self, plugin_name: str) -> bool:
        """重新載入插件"""
        try:
            logger.info(f"重新載入插件: {plugin_name}")
            
            # 獲取現有插件
            old_plugin = self.registry.get_plugin(plugin_name)
            if old_plugin:
                await old_plugin.cleanup()
                self.registry.unregister(plugin_name)
            
            # 重新載入
            plugin_file = self.plugin_loader.plugin_dir / f"{plugin_name}.py"
            if not plugin_file.exists():
                logger.error(f"插件文件不存在: {plugin_file}")
                return False
            
            new_plugin = self.plugin_loader.load_plugin(plugin_file)
            if not new_plugin:
                logger.error(f"重新載入插件失敗: {plugin_name}")
                return False
            
            # 註冊並初始化
            if self.registry.register(new_plugin):
                config = self.config_manager.get_config(plugin_name)
                if await new_plugin.initialize(config):
                    logger.info(f"插件 {plugin_name} 重新載入成功")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"重新載入插件失敗: {e}")
            return False
    
    async def process_message(self, message_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """通過所有消息處理器處理消息"""
        results = []
        
        processors = self.registry.get_plugins_by_type(PluginType.MESSAGE_PROCESSOR)
        
        for processor in processors:
            if isinstance(processor, MessageProcessor) and processor.enabled:
                try:
                    if processor.can_handle(message_data):
                        result = await processor.process_message(message_data)
                        if result:
                            results.append(result)
                except Exception as e:
                    logger.error(f"消息處理器 {processor.metadata.name} 處理失敗: {e}")
        
        return results
    
    async def generate_ai_response(
        self, 
        message: str, 
        context: Dict[str, Any],
        preferred_provider: Optional[str] = None
    ) -> Optional[str]:
        """生成AI回應"""
        providers = self.registry.get_plugins_by_type(PluginType.AI_PROVIDER)
        
        # 如果指定了提供商，優先使用
        if preferred_provider:
            for provider in providers:
                if (isinstance(provider, AIProvider) and 
                    provider.metadata.name == preferred_provider and 
                    provider.enabled):
                    try:
                        return await provider.generate_response(message, context)
                    except Exception as e:
                        logger.error(f"AI提供商 {preferred_provider} 處理失敗: {e}")
        
        # 否則嘗試第一個可用的提供商
        for provider in providers:
            if isinstance(provider, AIProvider) and provider.enabled:
                try:
                    return await provider.generate_response(message, context)
                except Exception as e:
                    logger.error(f"AI提供商 {provider.metadata.name} 處理失敗: {e}")
                    continue
        
        return None
    
    async def execute_command(
        self, 
        command: str, 
        args: List[str], 
        context: Dict[str, Any]
    ) -> Optional[str]:
        """執行命令"""
        handlers = self.registry.get_plugins_by_type(PluginType.COMMAND_HANDLER)
        
        for handler in handlers:
            if isinstance(handler, CommandHandler) and handler.enabled:
                try:
                    if command in handler.get_commands():
                        return await handler.handle_command(command, args, context)
                except Exception as e:
                    logger.error(f"命令處理器 {handler.metadata.name} 執行失敗: {e}")
        
        return None
    
    async def _setup_config_watching(self) -> None:
        """設置配置監控"""
        for plugin_name in self.registry.plugins.keys():
            await self.config_manager.watch_config(
                plugin_name, 
                self._on_config_changed
            )
    
    async def _on_config_changed(self, plugin_name: str, new_config: Dict[str, Any]) -> None:
        """配置變化處理"""
        logger.info(f"插件 {plugin_name} 配置已變化")
        
        plugin = self.registry.get_plugin(plugin_name)
        if plugin:
            try:
                await plugin.reload_config(new_config)
                logger.info(f"插件 {plugin_name} 配置重新載入成功")
            except Exception as e:
                logger.error(f"插件 {plugin_name} 配置重新載入失敗: {e}")
    
    def get_system_status(self) -> Dict[str, Any]:
        """獲取系統狀態"""
        return {
            'initialized': self.initialized,
            'plugins_loaded': self.plugins_loaded,
            'load_stats': self.load_stats,
            'plugin_count': len(self.registry.plugins),
            'plugin_types': {
                plugin_type.value: len(plugins)
                for plugin_type, plugins in self.registry.plugin_types.items()
            },
            'event_history_count': len(self.event_bus.event_history),
            'config_watchers': len(self.config_manager.watchers)
        }