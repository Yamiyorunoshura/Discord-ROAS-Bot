"""
SubBot負載均衡器和性能管理組件
Task ID: 3 - 子機器人聊天功能和管理系統開發

這個模組提供：
- 智能負載均衡和流量分發
- 動態性能監控和調優
- 資源限制和配額管理
- 自適應擴縮容機制
"""

import asyncio
import logging
import statistics
from typing import Dict, Any, Optional, List, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import heapq
import json

logger = logging.getLogger('services.subbot_load_balancer')


class LoadBalancingStrategy(Enum):
    """負載均衡策略"""
    ROUND_ROBIN = "round_robin"           # 輪詢
    LEAST_CONNECTIONS = "least_connections" # 最少連線
    WEIGHTED_RESPONSE_TIME = "weighted_response_time"  # 加權回應時間
    RESOURCE_BASED = "resource_based"     # 基於資源使用率
    ADAPTIVE = "adaptive"                 # 自適應策略


class PerformanceTier(Enum):
    """性能等級"""
    PREMIUM = "premium"      # 高性能實例
    STANDARD = "standard"    # 標準實例
    ECONOMY = "economy"      # 經濟型實例


@dataclass
class LoadMetrics:
    """負載指標"""
    bot_id: str
    active_connections: int = 0
    pending_messages: int = 0
    response_time: float = 0.0  # 毫秒
    cpu_usage: float = 0.0      # 百分比
    memory_usage: float = 0.0   # MB
    error_rate: float = 0.0     # 百分比
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def load_score(self) -> float:
        """計算綜合負載評分（0-100，越低越好）"""
        # 基於多個指標的加權評分
        connection_score = min(self.active_connections * 2, 30)
        queue_score = min(self.pending_messages * 5, 25)
        response_score = min(self.response_time / 10, 20)
        resource_score = (self.cpu_usage + self.memory_usage / 10) * 0.2
        error_penalty = self.error_rate * 10
        
        return connection_score + queue_score + response_score + resource_score + error_penalty


@dataclass
class ResourceQuota:
    """資源配額"""
    max_concurrent_messages: int = 50
    max_memory_mb: int = 512
    max_cpu_percent: int = 80
    max_response_time_ms: int = 2000
    max_error_rate_percent: float = 5.0


class SubBotLoadBalancer:
    """子機器人負載均衡器"""
    
    def __init__(self, strategy: LoadBalancingStrategy = LoadBalancingStrategy.ADAPTIVE):
        self.strategy = strategy
        self.metrics: Dict[str, LoadMetrics] = {}
        self.weights: Dict[str, float] = {}  # 實例權重
        self.blacklist: set[str] = set()     # 黑名單（暫時不可用的實例）
        
        # 輪詢計數器
        self._round_robin_counter = 0
        
        # 性能歷史記錄
        self.performance_history: Dict[str, List[LoadMetrics]] = {}
        self.history_limit = 100  # 保留最近100次記錄
        
        # 自適應調整參數
        self.adaptation_interval = 60  # 自適應調整間隔（秒）
        self.last_adaptation = datetime.now()
        
        logger.info(f"負載均衡器已初始化，策略: {strategy.value}")
    
    def update_metrics(self, bot_id: str, metrics: LoadMetrics) -> None:
        """更新實例指標"""
        self.metrics[bot_id] = metrics
        
        # 更新性能歷史
        if bot_id not in self.performance_history:
            self.performance_history[bot_id] = []
        
        self.performance_history[bot_id].append(metrics)
        
        # 限制歷史記錄大小
        if len(self.performance_history[bot_id]) > self.history_limit:
            self.performance_history[bot_id] = self.performance_history[bot_id][-self.history_limit:]
        
        # 檢查是否需要加入黑名單
        self._check_blacklist_status(bot_id, metrics)
        
        # 自適應調整
        if self.strategy == LoadBalancingStrategy.ADAPTIVE:
            self._adaptive_adjustment()
    
    def select_instance(self, available_instances: List[str], message_context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """選擇最佳實例處理請求"""
        if not available_instances:
            return None
        
        # 過濾黑名單實例
        healthy_instances = [bot_id for bot_id in available_instances if bot_id not in self.blacklist]
        
        if not healthy_instances:
            logger.warning("所有可用實例都在黑名單中")
            return None
        
        # 根據策略選擇實例
        if self.strategy == LoadBalancingStrategy.ROUND_ROBIN:
            return self._round_robin_selection(healthy_instances)
        elif self.strategy == LoadBalancingStrategy.LEAST_CONNECTIONS:
            return self._least_connections_selection(healthy_instances)
        elif self.strategy == LoadBalancingStrategy.WEIGHTED_RESPONSE_TIME:
            return self._weighted_response_time_selection(healthy_instances)
        elif self.strategy == LoadBalancingStrategy.RESOURCE_BASED:
            return self._resource_based_selection(healthy_instances)
        elif self.strategy == LoadBalancingStrategy.ADAPTIVE:
            return self._adaptive_selection(healthy_instances, message_context)
        
        # 預設使用輪詢
        return self._round_robin_selection(healthy_instances)
    
    def _round_robin_selection(self, instances: List[str]) -> str:
        """輪詢選擇"""
        if not instances:
            return None
        
        selected = instances[self._round_robin_counter % len(instances)]
        self._round_robin_counter += 1
        
        return selected
    
    def _least_connections_selection(self, instances: List[str]) -> str:
        """最少連線選擇"""
        if not instances:
            return None
        
        best_instance = None
        min_connections = float('inf')
        
        for bot_id in instances:
            metrics = self.metrics.get(bot_id)
            if metrics:
                total_load = metrics.active_connections + metrics.pending_messages
                if total_load < min_connections:
                    min_connections = total_load
                    best_instance = bot_id
        
        return best_instance or instances[0]
    
    def _weighted_response_time_selection(self, instances: List[str]) -> str:
        """加權回應時間選擇"""
        if not instances:
            return None
        
        # 計算所有實例的權重（回應時間越低，權重越高）
        weights = []
        valid_instances = []
        
        for bot_id in instances:
            metrics = self.metrics.get(bot_id)
            if metrics and metrics.response_time > 0:
                # 權重 = 1 / 回應時間，避免除零
                weight = 1.0 / max(metrics.response_time, 1.0)
                weights.append(weight)
                valid_instances.append(bot_id)
        
        if not valid_instances:
            return instances[0]
        
        # 加權隨機選擇
        import random
        total_weight = sum(weights)
        if total_weight == 0:
            return valid_instances[0]
        
        # 使用累積權重進行選擇
        random_value = random.uniform(0, total_weight)
        cumulative_weight = 0
        
        for i, weight in enumerate(weights):
            cumulative_weight += weight
            if random_value <= cumulative_weight:
                return valid_instances[i]
        
        return valid_instances[-1]
    
    def _resource_based_selection(self, instances: List[str]) -> str:
        """基於資源使用率選擇"""
        if not instances:
            return None
        
        best_instance = None
        lowest_load = float('inf')
        
        for bot_id in instances:
            metrics = self.metrics.get(bot_id)
            if metrics:
                load_score = metrics.load_score
                if load_score < lowest_load:
                    lowest_load = load_score
                    best_instance = bot_id
        
        return best_instance or instances[0]
    
    def _adaptive_selection(self, instances: List[str], message_context: Optional[Dict[str, Any]]) -> str:
        """自適應選擇（綜合多種策略）"""
        if not instances:
            return None
        
        # 分析訊息上下文
        priority = message_context.get('priority', 'normal') if message_context else 'normal'
        message_type = message_context.get('type', 'text') if message_context else 'text'
        
        # 根據優先級和類型調整策略
        if priority == 'high' or message_type == 'urgent':
            # 高優先級使用回應時間策略
            return self._weighted_response_time_selection(instances)
        elif message_type == 'ai_processing':
            # AI處理使用資源基礎策略
            return self._resource_based_selection(instances)
        else:
            # 一般情況使用混合策略
            
            # 30%機率使用最少連線，70%使用資源基礎
            import random
            if random.random() < 0.3:
                return self._least_connections_selection(instances)
            else:
                return self._resource_based_selection(instances)
    
    def _check_blacklist_status(self, bot_id: str, metrics: LoadMetrics) -> None:
        """檢查並更新黑名單狀態"""
        # 檢查是否應該加入黑名單
        should_blacklist = (
            metrics.error_rate > 10.0 or  # 錯誤率超過10%
            metrics.response_time > 5000 or  # 回應時間超過5秒
            metrics.memory_usage > 1024 or  # 記憶體使用超過1GB
            metrics.cpu_usage > 95  # CPU使用率超過95%
        )
        
        if should_blacklist and bot_id not in self.blacklist:
            self.blacklist.add(bot_id)
            logger.warning(f"實例 {bot_id} 已加入黑名單，指標異常")
        
        # 檢查是否可以從黑名單移除
        elif bot_id in self.blacklist:
            should_remove = (
                metrics.error_rate < 2.0 and
                metrics.response_time < 2000 and
                metrics.memory_usage < 512 and
                metrics.cpu_usage < 70
            )
            
            if should_remove:
                self.blacklist.discard(bot_id)
                logger.info(f"實例 {bot_id} 已從黑名單移除")
    
    def _adaptive_adjustment(self) -> None:
        """自適應調整"""
        now = datetime.now()
        if (now - self.last_adaptation).total_seconds() < self.adaptation_interval:
            return
        
        self.last_adaptation = now
        
        # 分析性能趨勢並調整策略
        self._analyze_performance_trends()
    
    def _analyze_performance_trends(self) -> None:
        """分析性能趨勢"""
        try:
            # 收集最近的性能數據
            recent_metrics = []
            for bot_id, history in self.performance_history.items():
                if len(history) >= 5:  # 至少需要5個數據點
                    recent_metrics.extend(history[-10:])  # 取最近10次記錄
            
            if not recent_metrics:
                return
            
            # 計算平均指標
            avg_response_time = statistics.mean(m.response_time for m in recent_metrics)
            avg_error_rate = statistics.mean(m.error_rate for m in recent_metrics)
            avg_load_score = statistics.mean(m.load_score for m in recent_metrics)
            
            # 根據趨勢調整權重和策略
            logger.debug(f"性能趨勢分析 - 平均回應時間: {avg_response_time:.2f}ms, "
                        f"平均錯誤率: {avg_error_rate:.2f}%, "
                        f"平均負載評分: {avg_load_score:.2f}")
            
            # 這裡可以添加更複雜的調整邏輯
            
        except Exception as e:
            logger.error(f"性能趨勢分析失敗: {e}")
    
    def get_load_distribution(self) -> Dict[str, Any]:
        """獲取負載分佈情況"""
        distribution = {
            'total_instances': len(self.metrics),
            'blacklisted_instances': len(self.blacklist),
            'strategy': self.strategy.value,
            'instances': {}
        }
        
        for bot_id, metrics in self.metrics.items():
            distribution['instances'][bot_id] = {
                'load_score': metrics.load_score,
                'active_connections': metrics.active_connections,
                'pending_messages': metrics.pending_messages,
                'response_time': metrics.response_time,
                'is_blacklisted': bot_id in self.blacklist,
                'last_update': metrics.timestamp.isoformat()
            }
        
        return distribution
    
    def rebalance_if_needed(self, instances: Dict[str, Any]) -> List[str]:
        """檢查是否需要重新平衡，返回需要調整的實例列表"""
        if len(self.metrics) < 2:
            return []
        
        # 計算負載方差
        load_scores = [metrics.load_score for metrics in self.metrics.values()]
        if len(load_scores) < 2:
            return []
        
        load_variance = statistics.variance(load_scores)
        threshold = 25.0  # 方差閾值
        
        if load_variance > threshold:
            # 需要重新平衡
            logger.info(f"檢測到負載不平衡，方差: {load_variance:.2f}")
            
            # 找出負載最高的實例
            overloaded_instances = []
            avg_load = statistics.mean(load_scores)
            
            for bot_id, metrics in self.metrics.items():
                if metrics.load_score > avg_load * 1.5:  # 超過平均負載50%
                    overloaded_instances.append(bot_id)
            
            return overloaded_instances
        
        return []


class PerformanceManager:
    """性能管理器"""
    
    def __init__(self):
        self.resource_quotas: Dict[str, ResourceQuota] = {}
        self.performance_tiers: Dict[str, PerformanceTier] = {}
        self.scaling_rules: Dict[str, Dict[str, Any]] = {}
        
        # 性能監控
        self.monitoring_interval = 30  # 監控間隔（秒）
        self.monitoring_task: Optional[asyncio.Task] = None
        
        # 自動調優
        self.auto_tuning_enabled = True
        self.tuning_history: List[Dict[str, Any]] = []
        
        logger.info("性能管理器已初始化")
    
    def set_resource_quota(self, bot_id: str, quota: ResourceQuota) -> None:
        """設置資源配額"""
        self.resource_quotas[bot_id] = quota
        logger.info(f"已為實例 {bot_id} 設置資源配額")
    
    def set_performance_tier(self, bot_id: str, tier: PerformanceTier) -> None:
        """設置性能等級"""
        self.performance_tiers[bot_id] = tier
        
        # 根據等級設置預設配額
        if tier == PerformanceTier.PREMIUM:
            quota = ResourceQuota(
                max_concurrent_messages=100,
                max_memory_mb=1024,
                max_cpu_percent=90,
                max_response_time_ms=1000,
                max_error_rate_percent=2.0
            )
        elif tier == PerformanceTier.STANDARD:
            quota = ResourceQuota(
                max_concurrent_messages=50,
                max_memory_mb=512,
                max_cpu_percent=80,
                max_response_time_ms=2000,
                max_error_rate_percent=5.0
            )
        else:  # ECONOMY
            quota = ResourceQuota(
                max_concurrent_messages=25,
                max_memory_mb=256,
                max_cpu_percent=70,
                max_response_time_ms=3000,
                max_error_rate_percent=8.0
            )
        
        self.set_resource_quota(bot_id, quota)
        logger.info(f"已為實例 {bot_id} 設置性能等級: {tier.value}")
    
    def check_resource_limits(self, bot_id: str, current_metrics: LoadMetrics) -> Dict[str, Any]:
        """檢查資源限制"""
        quota = self.resource_quotas.get(bot_id)
        if not quota:
            return {'status': 'no_quota', 'violations': []}
        
        violations = []
        
        # 檢查各項指標
        if current_metrics.pending_messages > quota.max_concurrent_messages:
            violations.append({
                'type': 'concurrent_messages',
                'current': current_metrics.pending_messages,
                'limit': quota.max_concurrent_messages
            })
        
        if current_metrics.memory_usage > quota.max_memory_mb:
            violations.append({
                'type': 'memory_usage',
                'current': current_metrics.memory_usage,
                'limit': quota.max_memory_mb
            })
        
        if current_metrics.cpu_usage > quota.max_cpu_percent:
            violations.append({
                'type': 'cpu_usage',
                'current': current_metrics.cpu_usage,
                'limit': quota.max_cpu_percent
            })
        
        if current_metrics.response_time > quota.max_response_time_ms:
            violations.append({
                'type': 'response_time',
                'current': current_metrics.response_time,
                'limit': quota.max_response_time_ms
            })
        
        if current_metrics.error_rate > quota.max_error_rate_percent:
            violations.append({
                'type': 'error_rate',
                'current': current_metrics.error_rate,
                'limit': quota.max_error_rate_percent
            })
        
        status = 'ok' if not violations else 'violation'
        
        return {
            'status': status,
            'violations': violations,
            'bot_id': bot_id,
            'timestamp': datetime.now().isoformat()
        }
    
    def suggest_scaling_action(self, bot_id: str, metrics_history: List[LoadMetrics]) -> Optional[Dict[str, Any]]:
        """建議擴縮容動作"""
        if len(metrics_history) < 5:
            return None
        
        recent_metrics = metrics_history[-5:]
        
        # 計算趨勢
        load_scores = [m.load_score for m in recent_metrics]
        response_times = [m.response_time for m in recent_metrics]
        error_rates = [m.error_rate for m in recent_metrics]
        
        avg_load = statistics.mean(load_scores)
        avg_response_time = statistics.mean(response_times)
        avg_error_rate = statistics.mean(error_rates)
        
        # 判斷是否需要擴容
        if avg_load > 80 or avg_response_time > 3000 or avg_error_rate > 10:
            return {
                'action': 'scale_up',
                'reason': 'High load detected',
                'metrics': {
                    'avg_load': avg_load,
                    'avg_response_time': avg_response_time,
                    'avg_error_rate': avg_error_rate
                },
                'timestamp': datetime.now().isoformat()
            }
        
        # 判斷是否可以縮容
        elif avg_load < 20 and avg_response_time < 1000 and avg_error_rate < 2:
            return {
                'action': 'scale_down',
                'reason': 'Low load detected',
                'metrics': {
                    'avg_load': avg_load,
                    'avg_response_time': avg_response_time,
                    'avg_error_rate': avg_error_rate
                },
                'timestamp': datetime.now().isoformat()
            }
        
        return None
    
    async def start_monitoring(self, load_balancer: SubBotLoadBalancer) -> None:
        """啟動性能監控"""
        if self.monitoring_task and not self.monitoring_task.done():
            return
        
        self.monitoring_task = asyncio.create_task(
            self._monitoring_loop(load_balancer)
        )
        logger.info("性能監控已啟動")
    
    async def stop_monitoring(self) -> None:
        """停止性能監控"""
        if self.monitoring_task and not self.monitoring_task.done():
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        logger.info("性能監控已停止")
    
    async def _monitoring_loop(self, load_balancer: SubBotLoadBalancer) -> None:
        """監控循環"""
        while True:
            try:
                await asyncio.sleep(self.monitoring_interval)
                await self._perform_monitoring_check(load_balancer)
                
            except asyncio.CancelledError:
                logger.info("性能監控循環已取消")
                break
            except Exception as e:
                logger.error(f"性能監控循環發生錯誤: {e}")
                await asyncio.sleep(5)
    
    async def _perform_monitoring_check(self, load_balancer: SubBotLoadBalancer) -> None:
        """執行監控檢查"""
        try:
            # 檢查所有實例的資源限制
            for bot_id, metrics in load_balancer.metrics.items():
                limit_check = self.check_resource_limits(bot_id, metrics)
                
                if limit_check['status'] == 'violation':
                    logger.warning(f"實例 {bot_id} 違反資源限制: {limit_check['violations']}")
                    
                    # 如果啟用了自動調優，嘗試調整
                    if self.auto_tuning_enabled:
                        await self._auto_tune_instance(bot_id, limit_check)
            
            # 檢查整體負載平衡
            distribution = load_balancer.get_load_distribution()
            logger.debug(f"負載分佈檢查完成，共 {distribution['total_instances']} 個實例")
            
        except Exception as e:
            logger.error(f"監控檢查失敗: {e}")
    
    async def _auto_tune_instance(self, bot_id: str, violation_info: Dict[str, Any]) -> None:
        """自動調優實例"""
        try:
            tuning_actions = []
            
            for violation in violation_info['violations']:
                violation_type = violation['type']
                current_value = violation['current']
                limit_value = violation['limit']
                
                if violation_type == 'concurrent_messages':
                    # 增加消息處理並發度或限制新連接
                    action = {
                        'type': 'limit_connections',
                        'value': int(limit_value * 0.8)
                    }
                    tuning_actions.append(action)
                
                elif violation_type == 'memory_usage':
                    # 觸發垃圾回收或重啟實例
                    action = {
                        'type': 'memory_optimization',
                        'value': 'gc_and_cleanup'
                    }
                    tuning_actions.append(action)
                
                elif violation_type == 'response_time':
                    # 增加超時時間或優化處理流程
                    action = {
                        'type': 'timeout_adjustment',
                        'value': min(limit_value * 1.2, 5000)
                    }
                    tuning_actions.append(action)
            
            if tuning_actions:
                tuning_record = {
                    'bot_id': bot_id,
                    'timestamp': datetime.now().isoformat(),
                    'violations': violation_info['violations'],
                    'actions': tuning_actions,
                    'auto_tuned': True
                }
                
                self.tuning_history.append(tuning_record)
                
                # 限制歷史記錄大小
                if len(self.tuning_history) > 100:
                    self.tuning_history = self.tuning_history[-100:]
                
                logger.info(f"已為實例 {bot_id} 執行自動調優: {tuning_actions}")
        
        except Exception as e:
            logger.error(f"自動調優實例 {bot_id} 失敗: {e}")
    
    def get_performance_report(self) -> Dict[str, Any]:
        """獲取性能報告"""
        return {
            'resource_quotas': {
                bot_id: {
                    'max_concurrent_messages': quota.max_concurrent_messages,
                    'max_memory_mb': quota.max_memory_mb,
                    'max_cpu_percent': quota.max_cpu_percent,
                    'max_response_time_ms': quota.max_response_time_ms,
                    'max_error_rate_percent': quota.max_error_rate_percent
                }
                for bot_id, quota in self.resource_quotas.items()
            },
            'performance_tiers': {
                bot_id: tier.value
                for bot_id, tier in self.performance_tiers.items()
            },
            'tuning_history_count': len(self.tuning_history),
            'recent_tuning': self.tuning_history[-10:] if self.tuning_history else [],
            'auto_tuning_enabled': self.auto_tuning_enabled,
            'monitoring_interval': self.monitoring_interval
        }