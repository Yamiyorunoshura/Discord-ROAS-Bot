"""
配置持久化存儲系統
- 保存用戶設定到資料庫
- 載入用戶設定
- 配置管理
"""

import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path
import aiofiles
import asyncio

logger = logging.getLogger("message_listener")

class PersistentConfig:
    """持久化配置管理器"""
    
    def __init__(self, config_dir: str = "data/message_listener"):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # 預設配置
        self.default_config = {
            # 渲染設定
            'render_settings': {
                'image_quality': 'high',
                'image_format': 'PNG',
                'image_width': 1000,
                'font_family': 'Noto Sans CJK',
                'font_size': 14,
                'line_height': 1.4,
                'color_theme': 'discord_default'
            },
            
            # 智能批量設定
            'batch_settings': {
                'enabled': True,
                'min_batch_size': 1,
                'max_batch_size': 50,
                'auto_adjust': True,
                'performance_tracking': True
            },
            
            # 監控設定
            'monitor_settings': {
                'monitor_edits': True,
                'monitor_deletes': True,
                'log_channel_id': None,
                'monitored_channels': []
            },
            
            # 預覽設定
            'preview_settings': {
                'default_quality': 'high',
                'preview_size': 'large',
                'cache_enabled': True,
                'quick_preview_enabled': True
            },
            
            # 主題配置
            'theme_configs': {
                'discord_default': {
                    'name': 'Discord 預設',
                    'background': '#36393f',
                    'message_bg': '#40444b',
                    'text_color': '#dcddde',
                    'accent': '#7289da'
                },
                'light_theme': {
                    'name': '明亮主題',
                    'background': '#ffffff',
                    'message_bg': '#f6f6f6',
                    'text_color': '#2c2f33',
                    'accent': '#5865f2'
                },
                'high_contrast': {
                    'name': '高對比主題',
                    'background': '#000000',
                    'message_bg': '#1a1a1a',
                    'text_color': '#ffffff',
                    'accent': '#ffff00'
                },
                'eye_care': {
                    'name': '護眼主題',
                    'background': '#1e2124',
                    'message_bg': '#2f3136',
                    'text_color': '#b9bbbe',
                    'accent': '#99aab5'
                },
                'rainbow': {
                    'name': '彩虹主題',
                    'background': '#2c2f33',
                    'message_bg': '#23272a',
                    'text_color': '#ffffff',
                    'accent': '#ff6b6b'
                }
            }
        }
        
        # 記憶體快取
        self._cache = {}
        self._cache_lock = asyncio.Lock()
    
    async def load_config(self, guild_id: int) -> Dict[str, Any]:
        """載入伺服器配置"""
        try:
            async with self._cache_lock:
                # 檢查快取
                if guild_id in self._cache:
                    return self._cache[guild_id]
                
                # 載入配置檔案
                config_file = self.config_dir / f"guild_{guild_id}.json"
                
                if config_file.exists():
                    async with aiofiles.open(config_file, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        config = json.loads(content)
                        
                        # 合併預設配置
                        merged_config = self._merge_config(self.default_config, config)
                        
                        # 快取配置
                        self._cache[guild_id] = merged_config
                        return merged_config
                else:
                    # 使用預設配置
                    self._cache[guild_id] = self.default_config.copy()
                    return self.default_config.copy()
                    
        except Exception as e:
            logger.error(f"載入配置失敗 (Guild {guild_id}): {e}")
            return self.default_config.copy()
    
    async def save_config(self, guild_id: int, config: Dict[str, Any]) -> bool:
        """保存伺服器配置"""
        try:
            async with self._cache_lock:
                # 更新快取
                self._cache[guild_id] = config
                
                # 保存到檔案
                config_file = self.config_dir / f"guild_{guild_id}.json"
                
                async with aiofiles.open(config_file, 'w', encoding='utf-8') as f:
                    content = json.dumps(config, indent=2, ensure_ascii=False)
                    await f.write(content)
                
                logger.info(f"配置已保存 (Guild {guild_id})")
                return True
                
        except Exception as e:
            logger.error(f"保存配置失敗 (Guild {guild_id}): {e}")
            return False
    
    async def update_setting(self, guild_id: int, category: str, key: str, value: Any) -> bool:
        """更新特定設定"""
        try:
            config = await self.load_config(guild_id)
            
            if category not in config:
                config[category] = {}
            
            config[category][key] = value
            
            return await self.save_config(guild_id, config)
            
        except Exception as e:
            logger.error(f"更新設定失敗 (Guild {guild_id}, {category}.{key}): {e}")
            return False
    
    async def get_setting(self, guild_id: int, category: str, key: str, default: Any = None) -> Any:
        """獲取特定設定"""
        try:
            config = await self.load_config(guild_id)
            return config.get(category, {}).get(key, default)
            
        except Exception as e:
            logger.error(f"獲取設定失敗 (Guild {guild_id}, {category}.{key}): {e}")
            return default
    
    async def get_render_settings(self, guild_id: int) -> Dict[str, Any]:
        """獲取渲染設定"""
        config = await self.load_config(guild_id)
        return config.get('render_settings', self.default_config['render_settings'])
    
    async def update_render_settings(self, guild_id: int, settings: Dict[str, Any]) -> bool:
        """更新渲染設定"""
        config = await self.load_config(guild_id)
        config['render_settings'].update(settings)
        return await self.save_config(guild_id, config)
    
    async def get_batch_settings(self, guild_id: int) -> Dict[str, Any]:
        """獲取批量設定"""
        config = await self.load_config(guild_id)
        return config.get('batch_settings', self.default_config['batch_settings'])
    
    async def update_batch_settings(self, guild_id: int, settings: Dict[str, Any]) -> bool:
        """更新批量設定"""
        config = await self.load_config(guild_id)
        config['batch_settings'].update(settings)
        return await self.save_config(guild_id, config)
    
    async def get_monitor_settings(self, guild_id: int) -> Dict[str, Any]:
        """獲取監控設定"""
        config = await self.load_config(guild_id)
        return config.get('monitor_settings', self.default_config['monitor_settings'])
    
    async def update_monitor_settings(self, guild_id: int, settings: Dict[str, Any]) -> bool:
        """更新監控設定"""
        config = await self.load_config(guild_id)
        config['monitor_settings'].update(settings)
        return await self.save_config(guild_id, config)
    
    async def get_preview_settings(self, guild_id: int) -> Dict[str, Any]:
        """獲取預覽設定"""
        config = await self.load_config(guild_id)
        return config.get('preview_settings', self.default_config['preview_settings'])
    
    async def update_preview_settings(self, guild_id: int, settings: Dict[str, Any]) -> bool:
        """更新預覽設定"""
        config = await self.load_config(guild_id)
        config['preview_settings'].update(settings)
        return await self.save_config(guild_id, config)
    
    async def get_theme_config(self, guild_id: int, theme_name: str) -> Dict[str, Any]:
        """獲取主題配置"""
        config = await self.load_config(guild_id)
        theme_configs = config.get('theme_configs', self.default_config['theme_configs'])
        return theme_configs.get(theme_name, theme_configs['discord_default'])
    
    async def reset_config(self, guild_id: int) -> bool:
        """重置配置為預設值"""
        try:
            async with self._cache_lock:
                # 清除快取
                if guild_id in self._cache:
                    del self._cache[guild_id]
                
                # 刪除配置檔案
                config_file = self.config_dir / f"guild_{guild_id}.json"
                if config_file.exists():
                    config_file.unlink()
                
                logger.info(f"配置已重置 (Guild {guild_id})")
                return True
                
        except Exception as e:
            logger.error(f"重置配置失敗 (Guild {guild_id}): {e}")
            return False
    
    async def export_config(self, guild_id: int) -> Optional[str]:
        """匯出配置為 JSON 字串"""
        try:
            config = await self.load_config(guild_id)
            return json.dumps(config, indent=2, ensure_ascii=False)
            
        except Exception as e:
            logger.error(f"匯出配置失敗 (Guild {guild_id}): {e}")
            return None
    
    async def import_config(self, guild_id: int, config_json: str) -> bool:
        """從 JSON 字串匯入配置"""
        try:
            config = json.loads(config_json)
            
            # 驗證配置結構
            if not isinstance(config, dict):
                raise ValueError("配置必須是 JSON 物件")
            
            # 合併預設配置
            merged_config = self._merge_config(self.default_config, config)
            
            return await self.save_config(guild_id, merged_config)
            
        except Exception as e:
            logger.error(f"匯入配置失敗 (Guild {guild_id}): {e}")
            return False
    
    def _merge_config(self, default: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
        """合併配置字典"""
        result = default.copy()
        
        for key, value in user.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value
        
        return result
    
    async def get_config_stats(self) -> Dict[str, Any]:
        """獲取配置統計資訊"""
        try:
            config_files = list(self.config_dir.glob("guild_*.json"))
            
            stats = {
                'total_configs': len(config_files),
                'cache_size': len(self._cache),
                'config_dir': str(self.config_dir),
                'default_config_size': len(json.dumps(self.default_config))
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"獲取配置統計失敗: {e}")
            return {}
    
    async def cleanup_cache(self):
        """清理記憶體快取"""
        try:
            async with self._cache_lock:
                self._cache.clear()
                logger.info("配置快取已清理")
                
        except Exception as e:
            logger.error(f"清理快取失敗: {e}")

# 全域配置管理器實例
config_manager = PersistentConfig()

# 便利函數
async def get_guild_config(guild_id: int) -> Dict[str, Any]:
    """獲取伺服器配置"""
    return await config_manager.load_config(guild_id)

async def save_guild_config(guild_id: int, config: Dict[str, Any]) -> bool:
    """保存伺服器配置"""
    return await config_manager.save_config(guild_id, config)

async def update_guild_setting(guild_id: int, category: str, key: str, value: Any) -> bool:
    """更新伺服器設定"""
    return await config_manager.update_setting(guild_id, category, key, value)

async def get_guild_setting(guild_id: int, category: str, key: str, default: Any = None) -> Any:
    """獲取伺服器設定"""
    return await config_manager.get_setting(guild_id, category, key, default) 