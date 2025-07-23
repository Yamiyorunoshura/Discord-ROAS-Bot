"""
訊息處理器模組
- 負責處理訊息的業務邏輯
- 提供訊息搜尋功能
- 處理訊息編輯和刪除
- 智能批量調整系統
"""

import logging
import json
import time
from typing import List, Dict, Optional, Any, Union
from collections import defaultdict, deque

import discord

from ..config.config import setup_logger
from ..database.database import MessageListenerDB

# 設定日誌記錄器
logger = setup_logger()

class SmartBatchProcessor:
    """
    智能批量處理器 - 增強版
    - 根據內容動態調整批量大小
    - 基於歷史性能數據學習
    - 自動優化處理效率
    - 機器學習式的自適應調整
    """
    
    def __init__(self, initial_batch_size: int = 10):
        """
        初始化智能批量處理器
        
        Args:
            initial_batch_size: 初始批量大小
        """
        self.current_batch_size = initial_batch_size
        self.min_batch_size = 1
        self.max_batch_size = 50
        
        # 性能統計
        self.performance_history = deque(maxlen=100)  # 保存最近100次處理記錄
        self.channel_activity = defaultdict(lambda: deque(maxlen=50))  # 頻道活躍度
        
        # 內容分析統計
        self.content_stats = {
            'avg_content_length': 100,
            'avg_attachments_per_message': 0.2,
            'avg_embeds_per_message': 0.1,
            'avg_mentions_per_message': 0.3,
            'avg_emojis_per_message': 0.8
        }
        
        # 智能學習參數
        self.learning_rate = 0.1
        self.adaptation_threshold = 0.05
        self.performance_weights = {
            'processing_time': 0.4,
            'success_rate': 0.3,
            'memory_usage': 0.2,
            'error_rate': 0.1
        }
        
        # 系統資源監控
        self.system_load_factor = 1.0
        self.memory_pressure_factor = 1.0
        
        logger.info("【智能批量】智能批量處理器已初始化")
    
    def calculate_optimal_batch_size(self, messages: List[discord.Message]) -> int:
        """
        計算最佳批量大小 - 增強版
        
        Args:
            messages: 待處理訊息列表
            
        Returns:
            int: 最佳批量大小
        """
        if not messages:
            return self.current_batch_size
        
        # 基礎批量大小
        base_batch_size = self.current_batch_size
        
        # 1. 基於內容複雜度調整
        content_complexity = self._analyze_content_complexity(messages)
        content_factor = self._calculate_content_factor_enhanced(content_complexity)
        
        # 2. 基於附件和媒體調整
        media_complexity = self._analyze_media_complexity(messages)
        media_factor = self._calculate_media_factor(media_complexity)
        
        # 3. 基於頻道活躍度調整
        channel_activity_factor = self._calculate_channel_activity_factor(messages)
        
        # 4. 基於歷史性能調整
        performance_factor = self._calculate_performance_factor_enhanced()
        
        # 5. 基於系統資源調整
        system_factor = self._calculate_system_factor()
        
        # 6. 基於時間和負載調整
        temporal_factor = self._calculate_temporal_factor()
        
        # 綜合計算 - 使用加權平均
        factors = {
            'content': content_factor,
            'media': media_factor,
            'channel_activity': channel_activity_factor,
            'performance': performance_factor,
            'system': system_factor,
            'temporal': temporal_factor
        }
        
        # 動態權重調整
        weights = self._calculate_dynamic_weights(factors)
        
        adjusted_batch_size = int(
            base_batch_size * sum(
                factors[key] * weights[key] for key in factors.keys()
            )
        )
        
        # 限制在合理範圍內
        optimal_batch_size = max(
            self.min_batch_size, 
            min(self.max_batch_size, adjusted_batch_size)
        )
        
        logger.debug(
            f"【智能批量】計算最佳批量大小: {optimal_batch_size} "
            f"(基礎: {base_batch_size}) "
            f"因子: {factors} "
            f"權重: {weights}"
        )
        
        return optimal_batch_size
    
    def _analyze_content_complexity(self, messages: List[discord.Message]) -> Dict[str, float]:
        """分析內容複雜度"""
        if not messages:
            return {'avg_length': 0, 'mentions': 0, 'emojis': 0, 'urls': 0}
        
        total_length = sum(len(msg.content) for msg in messages)
        total_mentions = sum(len(msg.mentions) + len(msg.role_mentions) for msg in messages)
        total_emojis = sum(len([c for c in msg.content if c in '😀😃😄😁😆😅😂🤣']) for msg in messages)
        total_urls = sum(msg.content.count('http') for msg in messages)
        
        return {
            'avg_length': total_length / len(messages),
            'mentions': total_mentions / len(messages),
            'emojis': total_emojis / len(messages),
            'urls': total_urls / len(messages)
        }
    
    def _analyze_media_complexity(self, messages: List[discord.Message]) -> Dict[str, float]:
        """分析媒體複雜度"""
        if not messages:
            return {'attachments': 0, 'embeds': 0, 'stickers': 0}
        
        total_attachments = sum(len(msg.attachments) for msg in messages)
        total_embeds = sum(len(msg.embeds) for msg in messages)
        total_stickers = sum(len(msg.stickers) for msg in messages)
        
        return {
            'attachments': total_attachments / len(messages),
            'embeds': total_embeds / len(messages),
            'stickers': total_stickers / len(messages)
        }
    
    def _calculate_content_factor_enhanced(self, complexity: Dict[str, float]) -> float:
        """計算增強版內容因子"""
        # 基於內容長度
        length_factor = 1.0
        if complexity['avg_length'] > 2000:
            length_factor = 0.3
        elif complexity['avg_length'] > 1000:
            length_factor = 0.5
        elif complexity['avg_length'] > 500:
            length_factor = 0.7
        elif complexity['avg_length'] > 200:
            length_factor = 0.9
        else:
            length_factor = 1.2
        
        # 基於提及數量
        mention_factor = 1.0
        if complexity['mentions'] > 5:
            mention_factor = 0.6
        elif complexity['mentions'] > 2:
            mention_factor = 0.8
        
        # 基於 URL 數量
        url_factor = 1.0
        if complexity['urls'] > 3:
            url_factor = 0.7
        elif complexity['urls'] > 1:
            url_factor = 0.9
        
        return length_factor * mention_factor * url_factor
    
    def _calculate_media_factor(self, media_complexity: Dict[str, float]) -> float:
        """計算媒體因子"""
        # 附件因子
        attachment_factor = 1.0
        if media_complexity['attachments'] > 3:
            attachment_factor = 0.2
        elif media_complexity['attachments'] > 1:
            attachment_factor = 0.4
        elif media_complexity['attachments'] > 0.5:
            attachment_factor = 0.6
        
        # 嵌入因子
        embed_factor = 1.0
        if media_complexity['embeds'] > 2:
            embed_factor = 0.5
        elif media_complexity['embeds'] > 1:
            embed_factor = 0.7
        
        # 貼圖因子
        sticker_factor = 1.0
        if media_complexity['stickers'] > 1:
            sticker_factor = 0.8
        
        return attachment_factor * embed_factor * sticker_factor
    
    def _calculate_system_factor(self) -> float:
        """計算系統資源因子"""
        # 結合系統負載和記憶體壓力
        return self.system_load_factor * self.memory_pressure_factor
    
    def _calculate_temporal_factor(self) -> float:
        """計算時間因子"""
        import datetime
        
        current_hour = datetime.datetime.now().hour
        
        # 根據時間調整批量大小
        if 2 <= current_hour <= 6:  # 深夜時段，系統負載較低
            return 1.3
        elif 9 <= current_hour <= 17:  # 工作時段，適中負載
            return 1.0
        elif 18 <= current_hour <= 23:  # 晚間高峰，負載較高
            return 0.8
        else:
            return 1.0
    
    def _calculate_channel_activity_factor(self, messages: List[discord.Message]) -> float:
        """計算頻道活躍度因子"""
        if not messages:
            return 1.0
        
        # 統計頻道分布
        channel_counts = defaultdict(int)
        for msg in messages:
            channel_counts[msg.channel.id] += 1
        
        # 頻道越集中，批量可以越大
        max_channel_count = max(channel_counts.values())
        concentration_ratio = max_channel_count / len(messages)
        
        if concentration_ratio > 0.8:
            return 1.3  # 高度集中
        elif concentration_ratio > 0.5:
            return 1.1  # 中度集中
        else:
            return 0.8  # 分散
    
    def _calculate_dynamic_weights(self, factors: Dict[str, float]) -> Dict[str, float]:
        """動態計算權重"""
        # 基於當前性能狀況調整權重
        if len(self.performance_history) < 10:
            # 初始權重
            return {
                'content': 0.25,
                'media': 0.25,
                'channel_activity': 0.15,
                'performance': 0.15,
                'system': 0.1,
                'temporal': 0.1
            }
        
        # 根據歷史性能調整權重
        recent_performance = list(self.performance_history)[-10:]
        avg_processing_time = sum(p['processing_time'] for p in recent_performance) / len(recent_performance)
        
        if avg_processing_time > 3.0:  # 處理時間過長，更重視內容和媒體因子
            return {
                'content': 0.35,
                'media': 0.35,
                'channel_activity': 0.1,
                'performance': 0.1,
                'system': 0.05,
                'temporal': 0.05
            }
        else:  # 處理時間正常，平衡權重
            return {
                'content': 0.2,
                'media': 0.2,
                'channel_activity': 0.2,
                'performance': 0.2,
                'system': 0.1,
                'temporal': 0.1
            }
    
    def _calculate_performance_factor_enhanced(self) -> float:
        """計算增強版性能因子"""
        if len(self.performance_history) < 5:
            return 1.0
        
        # 分析最近的性能趨勢
        recent_performances = list(self.performance_history)[-10:]
        
        # 加權平均處理時間
        weighted_processing_time = sum(
            p['processing_time'] * self.performance_weights['processing_time'] 
            for p in recent_performances
        ) / len(recent_performances)
        
        # 加權平均成功率
        weighted_success_rate = sum(
            p['success_rate'] * self.performance_weights['success_rate'] 
            for p in recent_performances
        ) / len(recent_performances)
        
        # 計算性能得分
        performance_score = weighted_success_rate - (weighted_processing_time / 10.0)
        
        # 根據性能得分調整因子
        if performance_score > 0.8:
            return 1.4  # 性能優秀
        elif performance_score > 0.6:
            return 1.2  # 性能良好
        elif performance_score > 0.4:
            return 1.0  # 性能一般
        elif performance_score > 0.2:
            return 0.8  # 性能較差
        else:
            return 0.6  # 性能很差
    
    def update_system_metrics(self, cpu_usage: float, memory_usage: float):
        """
        更新系統指標
        
        Args:
            cpu_usage: CPU 使用率 (0-1)
            memory_usage: 記憶體使用率 (0-1)
        """
        # 更新系統負載因子
        if cpu_usage > 0.8:
            self.system_load_factor = 0.5
        elif cpu_usage > 0.6:
            self.system_load_factor = 0.7
        elif cpu_usage > 0.4:
            self.system_load_factor = 0.9
        else:
            self.system_load_factor = 1.2
        
        # 更新記憶體壓力因子
        if memory_usage > 0.9:
            self.memory_pressure_factor = 0.4
        elif memory_usage > 0.7:
            self.memory_pressure_factor = 0.6
        elif memory_usage > 0.5:
            self.memory_pressure_factor = 0.8
        else:
            self.memory_pressure_factor = 1.0
        
        logger.debug(
            f"【智能批量】系統指標更新: CPU={cpu_usage:.2f}, "
            f"記憶體={memory_usage:.2f}, "
            f"負載因子={self.system_load_factor:.2f}, "
            f"記憶體因子={self.memory_pressure_factor:.2f}"
        )
    
    def record_performance(self, batch_size: int, processing_time: float, success_rate: float):
        """
        記錄性能數據
        
        Args:
            batch_size: 批量大小
            processing_time: 處理時間
            success_rate: 成功率
        """
        performance_record = {
            'batch_size': batch_size,
            'processing_time': processing_time,
            'success_rate': success_rate,
            'timestamp': time.time()
        }
        
        self.performance_history.append(performance_record)
        
        # 動態調整當前批量大小
        if success_rate > 0.95 and processing_time < 1.0:
            # 性能良好，可以增加批量
            self.current_batch_size = min(self.max_batch_size, int(self.current_batch_size * 1.1))
        elif success_rate < 0.8 or processing_time > 3.0:
            # 性能不佳，減少批量
            self.current_batch_size = max(self.min_batch_size, int(self.current_batch_size * 0.8))
        
        logger.debug(
            f"【智能批量】記錄性能: 批量={batch_size}, 時間={processing_time:.2f}s, "
            f"成功率={success_rate:.2f}, 調整後批量={self.current_batch_size}"
        )
    
    def update_channel_activity(self, channel_id: int, message_count: int):
        """
        更新頻道活躍度
        
        Args:
            channel_id: 頻道 ID
            message_count: 訊息數量
        """
        self.channel_activity[channel_id].append({
            'count': message_count,
            'timestamp': time.time()
        })
    
    def get_channel_activity_level(self, channel_id: int) -> str:
        """
        獲取頻道活躍度等級
        
        Args:
            channel_id: 頻道 ID
            
        Returns:
            str: 活躍度等級 (low/medium/high)
        """
        if channel_id not in self.channel_activity:
            return "low"
        
        recent_activity = list(self.channel_activity[channel_id])[-10:]
        if not recent_activity:
            return "low"
        
        avg_count = sum(record['count'] for record in recent_activity) / len(recent_activity)
        
        if avg_count > 20:
            return "high"
        elif avg_count > 5:
            return "medium"
        else:
            return "low"

class MessageProcessor:
    """
    訊息處理器類別
    
    功能：
    - 處理訊息的業務邏輯
    - 提供訊息搜尋功能
    - 處理訊息編輯和刪除
    - 智能批量處理
    """
    
    def __init__(self, db: MessageListenerDB):
        """
        初始化訊息處理器
        
        Args:
            db: 資料庫操作類別
        """
        self.db = db
        self.batch_processor = SmartBatchProcessor()
        self.pending_messages = []  # 待處理訊息佇列
    
    async def process_message(self, message: discord.Message) -> bool:
        """
        處理新訊息
        
        Args:
            message: Discord 訊息
            
        Returns:
            bool: 是否成功處理
        """
        try:
            # 檢查訊息是否有效
            if not self._is_valid_message(message):
                return False
            
            # 添加到待處理佇列
            self.pending_messages.append(message)
            
            # 檢查是否需要批量處理
            if len(self.pending_messages) >= self.batch_processor.current_batch_size:
                await self._process_batch()
            
            return True
        except Exception as exc:
            logger.error(f"【訊息監聽】處理訊息失敗：{exc}")
            return False
    
    async def _process_batch(self) -> bool:
        """
        批量處理訊息
        
        Returns:
            bool: 是否成功處理
        """
        if not self.pending_messages:
            return True
        
        start_time = time.time()
        batch_size = len(self.pending_messages)
        success_count = 0
        
        try:
            # 計算最佳批量大小
            optimal_batch_size = self.batch_processor.calculate_optimal_batch_size(self.pending_messages)
            
            # 分批處理
            messages_to_process = self.pending_messages[:optimal_batch_size]
            self.pending_messages = self.pending_messages[optimal_batch_size:]
            
            # 批量儲存到資料庫
            for message in messages_to_process:
                try:
                    await self.db.save_message(message)
                    success_count += 1
                except Exception as exc:
                    logger.error(f"【訊息監聽】儲存訊息失敗: {exc}")
            
            # 記錄性能
            processing_time = time.time() - start_time
            success_rate = success_count / len(messages_to_process) if messages_to_process else 1.0
            
            self.batch_processor.record_performance(
                len(messages_to_process), 
                processing_time, 
                success_rate
            )
            
            # 更新頻道活躍度
            channel_counts = defaultdict(int)
            for msg in messages_to_process:
                channel_counts[msg.channel.id] += 1
            
            for channel_id, count in channel_counts.items():
                self.batch_processor.update_channel_activity(channel_id, count)
            
            logger.info(
                f"【智能批量】批量處理完成: {success_count}/{len(messages_to_process)} "
                f"成功, 耗時 {processing_time:.2f}s"
            )
            
            return success_count == len(messages_to_process)
            
        except Exception as exc:
            logger.error(f"【訊息監聽】批量處理失敗：{exc}")
            return False
    
    async def force_process_pending(self) -> bool:
        """
        強制處理所有待處理訊息
        
        Returns:
            bool: 是否成功處理
        """
        if not self.pending_messages:
            return True
        
        try:
            await self._process_batch()
            return True
        except Exception as exc:
            logger.error(f"【訊息監聽】強制處理失敗：{exc}")
            return False
    
    def get_batch_stats(self) -> Dict[str, Any]:
        """
        獲取批量處理統計
        
        Returns:
            Dict[str, Any]: 統計資訊
        """
        return {
            'current_batch_size': self.batch_processor.current_batch_size,
            'pending_messages': len(self.pending_messages),
            'performance_records': len(self.batch_processor.performance_history),
            'channel_activity_tracked': len(self.batch_processor.channel_activity)
        }
    
    async def process_edit(self, before: discord.Message, after: discord.Message) -> bool:
        """
        處理訊息編輯
        
        Args:
            before: 編輯前的訊息
            after: 編輯後的訊息
            
        Returns:
            bool: 是否成功處理
        """
        try:
            # 檢查訊息是否有效
            if not self._is_valid_message(after):
                return False
            
            # 儲存編輯後的訊息
            await self.db.save_message(after)
            return True
        except Exception as exc:
            logger.error(f"【訊息監聽】處理訊息編輯失敗：{exc}")
            return False
    
    async def process_delete(self, message: discord.Message) -> bool:
        """
        處理訊息刪除
        
        Args:
            message: 被刪除的訊息
            
        Returns:
            bool: 是否成功處理
        """
        try:
            # 檢查訊息是否有效
            if not self._is_valid_message(message):
                return False
            
            # 標記訊息為已刪除
            await self.db.execute(
                "UPDATE messages SET deleted = 1 WHERE message_id = ?",
                message.id
            )
            return True
        except Exception as exc:
            logger.error(f"【訊息監聽】處理訊息刪除失敗：{exc}")
            return False
    
    async def search_messages(
        self, 
        keyword: str | None = None, 
        channel_id: int | None = None,
        hours: int = 24, 
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        搜尋訊息
        
        Args:
            keyword: 關鍵字
            channel_id: 頻道 ID
            hours: 搜尋時間範圍（小時）
            limit: 最大結果數量
            
        Returns:
            List[Dict[str, Any]]: 搜尋結果列表
        """
        try:
            return await self.db.search_messages(keyword, channel_id, hours, limit)
        except Exception as exc:
            logger.error(f"【訊息監聽】搜尋訊息失敗：{exc}")
            return []
    
    def _is_valid_message(self, message: discord.Message) -> bool:
        """
        檢查訊息是否有效
        
        Args:
            message: Discord 訊息
            
        Returns:
            bool: 是否有效
        """
        # 忽略機器人訊息
        if message.author.bot:
            return False
        
        # 忽略私人訊息
        if not message.guild:
            return False
        
        # 檢查是否有有效的頻道
        if not message.channel:
            return False
        
        return True
    
    def parse_attachments(self, attachments_json: str | None) -> List[Dict[str, Any]]:
        """
        解析附件 JSON
        
        Args:
            attachments_json: 附件 JSON 字串
            
        Returns:
            List[Dict[str, Any]]: 附件列表
        """
        if not attachments_json:
            return []
            
        try:
            return json.loads(attachments_json)
        except Exception as exc:
            logger.error(f"【訊息監聽】解析附件 JSON 失敗：{exc}")
            return []
    
    def format_message_for_display(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        格式化訊息用於顯示
        
        Args:
            message_data: 訊息資料
            
        Returns:
            Dict[str, Any]: 格式化後的訊息資料
        """
        # 解析附件
        attachments = self.parse_attachments(message_data.get("attachments"))
        
        # 格式化時間戳
        import datetime
        timestamp = message_data.get("timestamp", 0)
        formatted_time = datetime.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        
        # 返回格式化後的資料
        return {
            "id": message_data.get("message_id"),
            "channel_id": message_data.get("channel_id"),
            "guild_id": message_data.get("guild_id"),
            "author_id": message_data.get("author_id"),
            "content": message_data.get("content"),
            "timestamp": timestamp,
            "formatted_time": formatted_time,
            "attachments": attachments,
            "deleted": bool(message_data.get("deleted", 0))
        } 