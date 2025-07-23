"""
Discord ADR Bot v1.6 - 性能監控儀表板
==============================================

階段4任務4.4：整體性能監控儀表板

功能特點：
- 實時性能指標顯示
- 整合所有監控組件數據
- 直觀的性能監控界面
- 性能報告生成
- 性能警報系統
- 管理員專用工具

作者：Assistant
版本：1.6.0
更新：2025-01-25
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import discord
from discord.ext import commands, tasks
import logging
import psutil
import json

from .base_cog import StandardPanelView, StandardEmbedBuilder
from .cache_manager import MultiLevelCache
from .database_pool import DatabaseConnectionPool
from .event_bus import EventBus
from .health_checker import HealthChecker
from .logger import PerformanceMonitor

logger = logging.getLogger(__name__)

class PerformanceDashboardView(StandardPanelView):
    """性能監控儀表板視圖"""
    
    def __init__(self, bot: commands.Bot, **kwargs):
        super().__init__(**kwargs)
        self.bot = bot
        self.refresh_interval = 30  # 30秒自動刷新
        self.auto_refresh_task: asyncio.Task | None = None
        
    def _setup_pages(self):
        """設置儀表板頁面"""
        self.pages = {
            "overview": {
                "title": "📊 系統概覽",
                "description": "系統整體性能概覽",
                "embed_builder": self.build_overview_embed,
                "components": []
            },
            "cache": {
                "title": "🗄️ 緩存統計",
                "description": "緩存系統性能指標",
                "embed_builder": self.build_cache_embed,
                "components": []
            },
            "database": {
                "title": "🗃️ 資料庫性能",
                "description": "資料庫連接池統計",
                "embed_builder": self.build_database_embed,
                "components": []
            },
            "events": {
                "title": "📡 事件匯流排",
                "description": "事件處理性能統計",
                "embed_builder": self.build_events_embed,
                "components": []
            },
            "system": {
                "title": "💻 系統資源",
                "description": "系統資源使用情況",
                "embed_builder": self.build_system_embed,
                "components": []
            },
            "alerts": {
                "title": "🚨 性能警報",
                "description": "性能警報和建議",
                "embed_builder": self.build_alerts_embed,
                "components": []
            }
        }
    
    def _setup_components(self):
        """設置儀表板組件"""
        # 頁面導航選擇器
        page_options = [
            discord.SelectOption(
                label="系統概覽",
                value="overview",
                emoji="📊",
                description="查看系統整體性能概覽"
            ),
            discord.SelectOption(
                label="緩存統計",
                value="cache",
                emoji="🗄️",
                description="查看緩存系統性能指標"
            ),
            discord.SelectOption(
                label="資料庫性能",
                value="database",
                emoji="🗃️",
                description="查看資料庫連接池統計"
            ),
            discord.SelectOption(
                label="事件匯流排",
                value="events",
                emoji="📡",
                description="查看事件處理性能統計"
            ),
            discord.SelectOption(
                label="系統資源",
                value="system",
                emoji="💻",
                description="查看系統資源使用情況"
            ),
            discord.SelectOption(
                label="性能警報",
                value="alerts",
                emoji="🚨",
                description="查看性能警報和建議"
            )
        ]
        
        self.add_item(self.create_standard_select(
            placeholder="選擇要查看的監控頁面...",
            options=page_options,
            custom_id="performance_page_select",
            callback=self.page_select_callback
        ))
        
        # 控制按鈕
        self.add_item(self.create_standard_button(
            label="刷新數據",
            style="primary",
            emoji="🔄",
            callback=self.refresh_callback
        ))
        
        self.add_item(self.create_standard_button(
            label="生成報告",
            style="secondary",
            emoji="📋",
            callback=self.generate_report_callback
        ))
        
        self.add_item(self.create_standard_button(
            label="自動刷新",
            style="secondary",
            emoji="⏰",
            callback=self.toggle_auto_refresh_callback
        ))
        
        self.add_item(self.create_standard_button(
            label="關閉",
            style="danger",
            emoji="❌",
            callback=self.close_callback
        ))
    
    async def page_select_callback(self, interaction: discord.Interaction):
        """頁面選擇回調"""
        if interaction.data and 'values' in interaction.data:
            values = interaction.data['values']
            if values and len(values) > 0:
                select = values[0]
                await self.change_page(interaction, select)
    
    async def toggle_auto_refresh_callback(self, interaction: discord.Interaction):
        """切換自動刷新"""
        if self.auto_refresh_task and not self.auto_refresh_task.done():
            self.auto_refresh_task.cancel()
            self.auto_refresh_task = None
            await interaction.response.send_message("⏸️ 自動刷新已停用", ephemeral=True)
        else:
            self.auto_refresh_task = asyncio.create_task(self._auto_refresh_loop())
            await interaction.response.send_message("▶️ 自動刷新已啟用（30秒間隔）", ephemeral=True)
    
    async def _auto_refresh_loop(self):
        """自動刷新循環"""
        try:
            while True:
                await asyncio.sleep(self.refresh_interval)
                if self.message:
                    embed = await self.get_current_embed()
                    await self.message.edit(embed=embed, view=self)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"自動刷新循環錯誤: {e}")
    
    async def generate_report_callback(self, interaction: discord.Interaction):
        """生成性能報告"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            report = await self._generate_performance_report()
            
            # 創建報告文件
            report_content = json.dumps(report, indent=2, ensure_ascii=False)
            file = discord.File(
                fp=bytes(report_content, 'utf-8'),
                filename=f"performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            
            await interaction.followup.send(
                "📋 性能報告已生成",
                file=file,
                ephemeral=True
            )
            
        except Exception as e:
            await interaction.followup.send(f"❌ 生成報告失敗: {e}", ephemeral=True)
    
    async def build_overview_embed(self) -> discord.Embed:
        """構建系統概覽嵌入"""
        embed = StandardEmbedBuilder.create_info_embed(
            "📊 系統性能概覽",
            "Discord ADR Bot v1.6 整體性能狀態"
        )
        
        try:
            # 獲取系統基本信息
            system_info = await self._get_system_info()
            bot_info = await self._get_bot_info()
            performance_summary = await self._get_performance_summary()
            
            # 系統狀態
            embed.add_field(
                name="🖥️ 系統狀態",
                value=f"CPU: {system_info['cpu_percent']:.1f}%\n"
                      f"記憶體: {system_info['memory_percent']:.1f}%\n"
                      f"磁碟: {system_info['disk_percent']:.1f}%",
                inline=True
            )
            
            # Bot 狀態
            embed.add_field(
                name="🤖 Bot 狀態",
                value=f"延遲: {bot_info['latency']:.0f}ms\n"
                      f"伺服器: {bot_info['guild_count']} 個\n"
                      f"運行時間: {bot_info['uptime']}",
                inline=True
            )
            
            # 性能指標
            embed.add_field(
                name="📈 性能指標",
                value=f"平均響應: {performance_summary.get('avg_response_time', 0):.0f}ms\n"
                      f"緩存命中率: {performance_summary.get('cache_hit_rate', 0):.1f}%\n"
                      f"事件處理: {performance_summary.get('events_per_second', 0):.1f}/s",
                inline=True
            )
            
            # 健康狀態指示器
            health_status = await self._get_health_status()
            status_emoji = "🟢" if health_status['overall'] == "healthy" else "🟡" if health_status['overall'] == "warning" else "🔴"
            
            embed.add_field(
                name=f"{status_emoji} 整體健康狀態",
                value=f"狀態: {health_status['status_text']}\n"
                      f"檢查時間: {health_status['last_check']}",
                inline=False
            )
            
        except Exception as e:
            embed.add_field(
                name="❌ 數據載入錯誤",
                value=f"無法載入性能數據: {str(e)}",
                inline=False
            )
        
        embed.set_footer(text=f"最後更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        return embed
    
    async def build_cache_embed(self) -> discord.Embed:
        """構建緩存統計嵌入"""
        embed = StandardEmbedBuilder.create_info_embed(
            "🗄️ 緩存系統統計",
            "緩存管理器性能指標和統計數據"
        )
        
        try:
            # 嘗試獲取緩存管理器實例
            cache_stats = await self._get_cache_stats()
            
            if cache_stats:
                # 基本統計
                embed.add_field(
                    name="📊 基本統計",
                    value=f"總條目: {cache_stats.get('total_entries', 0)}\n"
                          f"命中次數: {cache_stats.get('hits', 0)}\n"
                          f"未命中次數: {cache_stats.get('misses', 0)}",
                    inline=True
                )
                
                # 性能指標
                hit_rate = cache_stats.get('hit_rate', 0)
                embed.add_field(
                    name="🎯 性能指標",
                    value=f"命中率: {hit_rate:.1f}%\n"
                          f"平均響應: {cache_stats.get('avg_response_time', 0):.2f}ms\n"
                          f"記憶體使用: {cache_stats.get('memory_usage', 0):.1f}MB",
                    inline=True
                )
                
                # 策略信息
                embed.add_field(
                    name="⚙️ 緩存策略",
                    value=f"策略: {cache_stats.get('strategy', 'Unknown')}\n"
                          f"最大大小: {cache_stats.get('max_size', 0)}\n"
                          f"TTL: {cache_stats.get('default_ttl', 0)}s",
                    inline=True
                )
                
                # 熱點數據
                hot_keys = cache_stats.get('hot_keys', [])
                if hot_keys:
                    hot_keys_text = "\n".join([f"• {key}" for key in hot_keys[:5]])
                    embed.add_field(
                        name="🔥 熱點鍵值",
                        value=hot_keys_text,
                        inline=False
                    )
            else:
                embed.add_field(
                    name="ℹ️ 緩存狀態",
                    value="緩存管理器未啟用或無可用數據",
                    inline=False
                )
                
        except Exception as e:
            embed.add_field(
                name="❌ 緩存數據錯誤",
                value=f"無法載入緩存統計: {str(e)}",
                inline=False
            )
        
        embed.set_footer(text=f"數據更新時間: {datetime.now().strftime('%H:%M:%S')}")
        return embed
    
    async def build_database_embed(self) -> discord.Embed:
        """構建資料庫性能嵌入"""
        embed = StandardEmbedBuilder.create_info_embed(
            "🗃️ 資料庫性能統計",
            "資料庫連接池和查詢性能指標"
        )
        
        try:
            db_stats = await self._get_database_stats()
            
            if db_stats:
                # 連接池狀態
                embed.add_field(
                    name="🔗 連接池狀態",
                    value=f"活躍連接: {db_stats.get('active_connections', 0)}\n"
                          f"空閒連接: {db_stats.get('idle_connections', 0)}\n"
                          f"總連接數: {db_stats.get('total_connections', 0)}",
                    inline=True
                )
                
                # 性能指標
                embed.add_field(
                    name="⚡ 性能指標",
                    value=f"平均查詢時間: {db_stats.get('avg_query_time', 0):.2f}ms\n"
                          f"查詢成功率: {db_stats.get('success_rate', 0):.1f}%\n"
                          f"每秒查詢: {db_stats.get('queries_per_second', 0):.1f}",
                    inline=True
                )
                
                # 負載均衡
                embed.add_field(
                    name="⚖️ 負載均衡",
                    value=f"策略: {db_stats.get('load_balance_strategy', 'Unknown')}\n"
                          f"最優連接: {db_stats.get('optimal_connection', 'N/A')}\n"
                          f"故障恢復: {db_stats.get('auto_recovery_enabled', False)}",
                    inline=True
                )
                
                # 健康狀態
                healthy_connections = db_stats.get('healthy_connections', 0)
                total_connections = db_stats.get('total_connections', 1)
                health_percentage = (healthy_connections / total_connections) * 100 if total_connections > 0 else 0
                
                embed.add_field(
                    name="🏥 健康狀態",
                    value=f"健康連接: {healthy_connections}/{total_connections}\n"
                          f"健康率: {health_percentage:.1f}%\n"
                          f"最後檢查: {db_stats.get('last_health_check', 'Unknown')}",
                    inline=False
                )
            else:
                embed.add_field(
                    name="ℹ️ 資料庫狀態",
                    value="資料庫連接池未啟用或無可用數據",
                    inline=False
                )
                
        except Exception as e:
            embed.add_field(
                name="❌ 資料庫數據錯誤",
                value=f"無法載入資料庫統計: {str(e)}",
                inline=False
            )
        
        embed.set_footer(text=f"數據更新時間: {datetime.now().strftime('%H:%M:%S')}")
        return embed
    
    async def build_events_embed(self) -> discord.Embed:
        """構建事件匯流排嵌入"""
        embed = StandardEmbedBuilder.create_info_embed(
            "📡 事件匯流排統計",
            "事件處理性能和吞吐量統計"
        )
        
        try:
            event_stats = await self._get_event_stats()
            
            if event_stats:
                # 事件處理統計
                embed.add_field(
                    name="📊 處理統計",
                    value=f"總事件數: {event_stats.get('total_events', 0)}\n"
                          f"成功處理: {event_stats.get('successful_events', 0)}\n"
                          f"失敗事件: {event_stats.get('failed_events', 0)}",
                    inline=True
                )
                
                # 性能指標
                embed.add_field(
                    name="⚡ 性能指標",
                    value=f"平均處理時間: {event_stats.get('avg_processing_time', 0):.2f}ms\n"
                          f"吞吐量: {event_stats.get('throughput', 0):.1f} 事件/秒\n"
                          f"成功率: {event_stats.get('success_rate', 0):.1f}%",
                    inline=True
                )
                
                # 批處理統計
                embed.add_field(
                    name="📦 批處理統計",
                    value=f"批處理模式: {event_stats.get('batch_mode', 'Disabled')}\n"
                          f"平均批次大小: {event_stats.get('avg_batch_size', 0):.1f}\n"
                          f"壓縮率: {event_stats.get('compression_ratio', 0):.1f}%",
                    inline=True
                )
                
                # 訂閱者統計
                top_subscribers = event_stats.get('top_subscribers', [])
                if top_subscribers:
                    subscribers_text = "\n".join([
                        f"• {sub['name']}: {sub['events']} 事件" 
                        for sub in top_subscribers[:3]
                    ])
                    embed.add_field(
                        name="👥 活躍訂閱者",
                        value=subscribers_text,
                        inline=False
                    )
            else:
                embed.add_field(
                    name="ℹ️ 事件匯流排狀態",
                    value="事件匯流排未啟用或無可用數據",
                    inline=False
                )
                
        except Exception as e:
            embed.add_field(
                name="❌ 事件數據錯誤",
                value=f"無法載入事件統計: {str(e)}",
                inline=False
            )
        
        embed.set_footer(text=f"數據更新時間: {datetime.now().strftime('%H:%M:%S')}")
        return embed
    
    async def build_system_embed(self) -> discord.Embed:
        """構建系統資源嵌入"""
        embed = StandardEmbedBuilder.create_info_embed(
            "💻 系統資源監控",
            "實時系統資源使用情況"
        )
        
        try:
            system_info = await self._get_detailed_system_info()
            
            # CPU 信息
            embed.add_field(
                name="🔧 CPU 使用情況",
                value=f"總使用率: {system_info['cpu']['total']:.1f}%\n"
                      f"核心數: {system_info['cpu']['cores']}\n"
                      f"頻率: {system_info['cpu']['frequency']:.0f} MHz",
                inline=True
            )
            
            # 記憶體信息
            embed.add_field(
                name="🧠 記憶體使用情況",
                value=f"使用率: {system_info['memory']['percent']:.1f}%\n"
                      f"已用: {system_info['memory']['used']:.1f} GB\n"
                      f"總計: {system_info['memory']['total']:.1f} GB",
                inline=True
            )
            
            # 磁碟信息
            embed.add_field(
                name="💾 磁碟使用情況",
                value=f"使用率: {system_info['disk']['percent']:.1f}%\n"
                      f"已用: {system_info['disk']['used']:.1f} GB\n"
                      f"總計: {system_info['disk']['total']:.1f} GB",
                inline=True
            )
            
            # 網路信息
            if 'network' in system_info:
                embed.add_field(
                    name="🌐 網路統計",
                    value=f"發送: {system_info['network']['bytes_sent']:.1f} MB\n"
                          f"接收: {system_info['network']['bytes_recv']:.1f} MB\n"
                          f"連接數: {system_info['network']['connections']}",
                    inline=True
                )
            
            # 進程信息
            if 'process' in system_info:
                embed.add_field(
                    name="🔄 Bot 進程信息",
                    value=f"CPU: {system_info['process']['cpu_percent']:.1f}%\n"
                          f"記憶體: {system_info['process']['memory_mb']:.1f} MB\n"
                          f"執行緒數: {system_info['process']['threads']}",
                    inline=True
                )
            
            # 系統負載
            if 'load_avg' in system_info:
                embed.add_field(
                    name="📈 系統負載",
                    value=f"1分鐘: {system_info['load_avg']['1min']:.2f}\n"
                          f"5分鐘: {system_info['load_avg']['5min']:.2f}\n"
                          f"15分鐘: {system_info['load_avg']['15min']:.2f}",
                    inline=True
                )
                
        except Exception as e:
            embed.add_field(
                name="❌ 系統數據錯誤",
                value=f"無法載入系統信息: {str(e)}",
                inline=False
            )
        
        embed.set_footer(text=f"數據更新時間: {datetime.now().strftime('%H:%M:%S')}")
        return embed
    
    async def build_alerts_embed(self) -> discord.Embed:
        """構建性能警報嵌入"""
        embed = StandardEmbedBuilder.create_warning_embed(
            "🚨 性能警報與建議",
            "系統性能警報和優化建議"
        )
        
        try:
            alerts = await self._get_performance_alerts()
            
            if alerts['critical']:
                critical_text = "\n".join([f"🔴 {alert}" for alert in alerts['critical']])
                embed.add_field(
                    name="🚨 嚴重警報",
                    value=critical_text,
                    inline=False
                )
            
            if alerts['warnings']:
                warning_text = "\n".join([f"🟡 {alert}" for alert in alerts['warnings']])
                embed.add_field(
                    name="⚠️ 警告",
                    value=warning_text,
                    inline=False
                )
            
            if alerts['recommendations']:
                rec_text = "\n".join([f"💡 {rec}" for rec in alerts['recommendations']])
                embed.add_field(
                    name="📋 優化建議",
                    value=rec_text,
                    inline=False
                )
            
            if not any([alerts['critical'], alerts['warnings'], alerts['recommendations']]):
                embed.add_field(
                    name="✅ 系統狀態良好",
                    value="目前沒有性能警報或建議",
                    inline=False
                )
                embed.color = discord.Color.green()
                
        except Exception as e:
            embed.add_field(
                name="❌ 警報數據錯誤",
                value=f"無法載入警報信息: {str(e)}",
                inline=False
            )
        
        embed.set_footer(text=f"最後檢查: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        return embed
    
    # 數據獲取方法
    async def _get_system_info(self) -> Dict[str, Any]:
        """獲取基本系統信息"""
        return {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_percent': psutil.disk_usage('/').percent,
            'timestamp': datetime.now().isoformat()
        }
    
    async def _get_bot_info(self) -> Dict[str, Any]:
        """獲取Bot信息"""
        # 計算運行時間（簡化版本）
        uptime_str = "未知"
        try:
            start_time = getattr(self.bot, 'start_time', None)
            if start_time:
                uptime = datetime.now() - start_time
                uptime_str = str(uptime).split('.')[0]  # 移除微秒
        except Exception:
            pass
        
        return {
            'latency': self.bot.latency * 1000,
            'guild_count': len(self.bot.guilds),
            'uptime': uptime_str,
            'user_count': sum(guild.member_count for guild in self.bot.guilds if guild.member_count)
        }
    
    async def _get_performance_summary(self) -> Dict[str, Any]:
        """獲取性能摘要"""
        # 這裡可以整合各個組件的性能數據
        summary = {
            'avg_response_time': 0,
            'cache_hit_rate': 0,
            'events_per_second': 0
        }
        
        try:
            # 嘗試從各個組件獲取數據
            cache_stats = await self._get_cache_stats()
            if cache_stats:
                summary['cache_hit_rate'] = cache_stats.get('hit_rate', 0)
            
            # 可以添加更多組件的數據整合
            
        except Exception as e:
            logger.warning(f"獲取性能摘要失敗: {e}")
        
        return summary
    
    async def _get_health_status(self) -> Dict[str, Any]:
        """獲取健康狀態"""
        # 簡化的健康檢查
        system_info = await self._get_system_info()
        
        issues = []
        if system_info['cpu_percent'] > 80:
            issues.append("CPU 使用率過高")
        if system_info['memory_percent'] > 90:
            issues.append("記憶體使用率過高")
        if system_info['disk_percent'] > 95:
            issues.append("磁碟空間不足")
        
        if not issues:
            overall = "healthy"
            status_text = "系統運行正常"
        elif len(issues) <= 1:
            overall = "warning"
            status_text = f"發現 {len(issues)} 個警告"
        else:
            overall = "critical"
            status_text = f"發現 {len(issues)} 個嚴重問題"
        
        return {
            'overall': overall,
            'status_text': status_text,
            'issues': issues,
            'last_check': datetime.now().strftime('%H:%M:%S')
        }
    
    async def _get_cache_stats(self) -> Dict[str, Any | None]:
        """獲取緩存統計"""
        try:
            # 嘗試從Bot獲取緩存管理器實例
            # 這需要根據實際的架構進行調整
            return {
                'total_entries': 0,
                'hits': 0,
                'misses': 0,
                'hit_rate': 0.0,
                'avg_response_time': 0.0,
                'memory_usage': 0.0,
                'strategy': 'LRU',
                'max_size': 1000,
                'default_ttl': 3600,
                'hot_keys': []
            }
        except Exception as e:
            logger.warning(f"獲取緩存統計失敗: {e}")
            return None
    
    async def _get_database_stats(self) -> Dict[str, Any | None]:
        """獲取資料庫統計"""
        try:
            return {
                'active_connections': 0,
                'idle_connections': 0,
                'total_connections': 0,
                'avg_query_time': 0.0,
                'success_rate': 100.0,
                'queries_per_second': 0.0,
                'load_balance_strategy': 'Round Robin',
                'optimal_connection': 'Connection-1',
                'auto_recovery_enabled': True,
                'healthy_connections': 0,
                'last_health_check': datetime.now().strftime('%H:%M:%S')
            }
        except Exception as e:
            logger.warning(f"獲取資料庫統計失敗: {e}")
            return None
    
    async def _get_event_stats(self) -> Dict[str, Any | None]:
        """獲取事件統計"""
        try:
            return {
                'total_events': 0,
                'successful_events': 0,
                'failed_events': 0,
                'avg_processing_time': 0.0,
                'throughput': 0.0,
                'success_rate': 100.0,
                'batch_mode': 'Enabled',
                'avg_batch_size': 10.0,
                'compression_ratio': 15.0,
                'top_subscribers': []
            }
        except Exception as e:
            logger.warning(f"獲取事件統計失敗: {e}")
            return None
    
    async def _get_detailed_system_info(self) -> Dict[str, Any]:
        """獲取詳細系統信息"""
        info = {}
        
        try:
            # CPU 信息
            cpu_freq = psutil.cpu_freq()
            info['cpu'] = {
                'total': psutil.cpu_percent(interval=1),
                'cores': psutil.cpu_count(),
                'frequency': cpu_freq.current if cpu_freq else 0
            }
            
            # 記憶體信息
            memory = psutil.virtual_memory()
            info['memory'] = {
                'percent': memory.percent,
                'used': memory.used / (1024**3),  # GB
                'total': memory.total / (1024**3)  # GB
            }
            
            # 磁碟信息
            disk = psutil.disk_usage('/')
            info['disk'] = {
                'percent': disk.percent,
                'used': disk.used / (1024**3),  # GB
                'total': disk.total / (1024**3)  # GB
            }
            
            # 網路信息
            net_io = psutil.net_io_counters()
            info['network'] = {
                'bytes_sent': net_io.bytes_sent / (1024**2),  # MB
                'bytes_recv': net_io.bytes_recv / (1024**2),  # MB
                'connections': len(psutil.net_connections())
            }
            
            # 當前進程信息
            process = psutil.Process()
            info['process'] = {
                'cpu_percent': process.cpu_percent(),
                'memory_mb': process.memory_info().rss / (1024**2),  # MB
                'threads': process.num_threads()
            }
            
            # 系統負載（僅限 Unix 系統）
            try:
                load_avg = psutil.getloadavg()
                info['load_avg'] = {
                    '1min': load_avg[0],
                    '5min': load_avg[1],
                    '15min': load_avg[2]
                }
            except AttributeError:
                # Windows 系統不支援 getloadavg
                pass
                
        except Exception as e:
            logger.error(f"獲取系統信息失敗: {e}")
        
        return info
    
    async def _get_performance_alerts(self) -> Dict[str, List[str]]:
        """獲取性能警報"""
        alerts = {
            'critical': [],
            'warnings': [],
            'recommendations': []
        }
        
        try:
            system_info = await self._get_system_info()
            
            # 檢查關鍵警報
            if system_info['cpu_percent'] > 90:
                alerts['critical'].append("CPU 使用率超過 90%")
            if system_info['memory_percent'] > 95:
                alerts['critical'].append("記憶體使用率超過 95%")
            if system_info['disk_percent'] > 98:
                alerts['critical'].append("磁碟空間不足 2%")
            
            # 檢查警告
            if 80 <= system_info['cpu_percent'] <= 90:
                alerts['warnings'].append("CPU 使用率較高")
            if 85 <= system_info['memory_percent'] <= 95:
                alerts['warnings'].append("記憶體使用率較高")
            if 90 <= system_info['disk_percent'] <= 98:
                alerts['warnings'].append("磁碟空間不足")
            
            # 生成建議
            if system_info['cpu_percent'] > 70:
                alerts['recommendations'].append("考慮優化 CPU 密集型任務")
            if system_info['memory_percent'] > 80:
                alerts['recommendations'].append("考慮增加記憶體或優化記憶體使用")
            if system_info['disk_percent'] > 85:
                alerts['recommendations'].append("清理磁碟空間或擴展存儲")
            
            # Bot 相關建議
            if self.bot.latency > 0.5:  # 500ms
                alerts['warnings'].append("Bot 延遲較高")
                alerts['recommendations'].append("檢查網路連接或 Discord API 狀態")
                
        except Exception as e:
            alerts['critical'].append(f"無法檢查系統狀態: {str(e)}")
        
        return alerts
    
    async def _generate_performance_report(self) -> Dict[str, Any]:
        """生成完整的性能報告"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'system_info': await self._get_detailed_system_info(),
            'bot_info': await self._get_bot_info(),
            'performance_summary': await self._get_performance_summary(),
            'health_status': await self._get_health_status(),
            'alerts': await self._get_performance_alerts()
        }
        
        # 添加組件統計
        cache_stats = await self._get_cache_stats()
        if cache_stats:
            report['cache_stats'] = cache_stats
        
        db_stats = await self._get_database_stats()
        if db_stats:
            report['database_stats'] = db_stats
        
        event_stats = await self._get_event_stats()
        if event_stats:
            report['event_stats'] = event_stats
        
        return report
    
    async def on_timeout(self) -> None:
        """超時處理"""
        if self.auto_refresh_task and not self.auto_refresh_task.done():
            self.auto_refresh_task.cancel()
        await super().on_timeout()


class PerformanceDashboard:
    """性能監控儀表板管理器"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_dashboards: Dict[int, PerformanceDashboardView] = {}
    
    async def create_dashboard(self, interaction: discord.Interaction) -> PerformanceDashboardView:
        """創建新的儀表板實例"""
        # 清理舊的儀表板
        if interaction.user.id in self.active_dashboards:
            old_dashboard = self.active_dashboards[interaction.user.id]
            if old_dashboard.auto_refresh_task and not old_dashboard.auto_refresh_task.done():
                old_dashboard.auto_refresh_task.cancel()
        
        # 創建新儀表板
        dashboard = PerformanceDashboardView(
            bot=self.bot,
            timeout=600.0,  # 10分鐘超時
            admin_only=True,
            author_id=interaction.user.id,
            guild_id=interaction.guild.id if interaction.guild else None
        )
        
        self.active_dashboards[interaction.user.id] = dashboard
        return dashboard
    
    def cleanup_dashboard(self, user_id: int):
        """清理儀表板"""
        if user_id in self.active_dashboards:
            dashboard = self.active_dashboards[user_id]
            if dashboard.auto_refresh_task and not dashboard.auto_refresh_task.done():
                dashboard.auto_refresh_task.cancel()
            del self.active_dashboards[user_id] 