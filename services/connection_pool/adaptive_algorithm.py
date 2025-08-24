"""
T2 - 高併發連線競爭修復 - 自適應動態調整算法
Task ID: T2

專業效能優化算法實現：
- 預測性擴縮容決策引擎
- 競爭感知連線調度器
- 適應性負載平衡算法
- 智慧資源配置優化器

作者: Ethan - 效能優化專家
"""

import asyncio
import logging
import statistics
import time
from typing import Dict, List, Optional, Tuple, Deque
from datetime import datetime, timedelta
from collections import deque
from dataclasses import dataclass
from enum import Enum
import math

logger = logging.getLogger('adaptive_algorithm')


class ScalingDecision(Enum):
    """擴縮容決策類型"""
    SCALE_UP = "scale_up"           # 擴容
    SCALE_DOWN = "scale_down"       # 縮容
    MAINTAIN = "maintain"           # 維持現狀
    EMERGENCY_SCALE = "emergency"   # 緊急擴容


@dataclass
class LoadPrediction:
    """負載預測資料"""
    predicted_load: float           # 預測負載 (0-100)
    confidence: float               # 預測信心度 (0-1)  
    trend_direction: float          # 趨勢方向 (-1 to 1)
    predicted_response_time: float  # 預測響應時間
    recommended_capacity: int       # 建議連線數


@dataclass
class PerformanceProfile:
    """效能特徵描述"""
    avg_response_time: float        # 平均響應時間
    p95_response_time: float        # P95響應時間
    throughput_rps: float           # 吞吐量
    error_rate: float               # 錯誤率
    connection_efficiency: float     # 連線效率
    resource_utilization: float     # 資源利用率


class AdaptiveScalingAlgorithm:
    """
    自適應動態擴縮容算法
    
    核心特性：
    1. 預測性負載分析
    2. 多維度效能評估
    3. 漸進式調整策略
    4. 異常檢測與恢復
    5. 成本效益優化
    """
    
    def __init__(self, min_connections: int = 2, max_connections: int = 20):
        self.min_connections = min_connections
        self.max_connections = max_connections
        
        # 歷史數據追蹤
        self.load_history: Deque[float] = deque(maxlen=300)      # 5分鐘歷史
        self.response_history: Deque[float] = deque(maxlen=300)   
        self.throughput_history: Deque[float] = deque(maxlen=60)  # 1分鐘歷史
        self.connection_history: Deque[int] = deque(maxlen=300)
        
        # 效能特徵學習
        self.performance_profiles: Dict[str, PerformanceProfile] = {}
        self.peak_hours: List[int] = []  # 高峰時段
        self.baseline_performance = None
        
        # 調整策略參數
        self.adjustment_threshold = 0.15    # 調整閾值
        self.emergency_threshold = 0.85     # 緊急擴容閾值
        self.scale_factor = 1.5             # 擴容因子
        self.cooldown_period = timedelta(seconds=30)  # 冷卻期
        
        # 狀態追蹤
        self.last_scaling_time = datetime.now()
        self.consecutive_decisions = 0
        self.current_trend = 0.0
        
        logger.info("自適應擴縮容算法已初始化")
    
    def analyze_and_decide(
        self, 
        current_stats: Dict,
        load_metrics: Dict
    ) -> Tuple[ScalingDecision, int, float]:
        """
        分析當前狀況並做出擴縮容決策
        
        返回:
            (決策類型, 建議連線數, 信心度)
        """
        try:
            # 更新歷史數據
            self._update_history(current_stats, load_metrics)
            
            # 計算負載預測
            prediction = self._predict_load()
            
            # 分析效能趨勢
            performance_trend = self._analyze_performance_trend()
            
            # 檢測異常狀況
            anomaly_score = self._detect_anomaly()
            
            # 制定擴縮容決策
            decision, target_size, confidence = self._make_scaling_decision(
                prediction, performance_trend, anomaly_score, current_stats
            )
            
            # 更新決策歷史
            self._update_decision_history(decision)
            
            logger.debug(
                f"擴縮容分析完成 - 決策: {decision.value}, "
                f"目標大小: {target_size}, 信心度: {confidence:.2f}"
            )
            
            return decision, target_size, confidence
            
        except Exception as e:
            logger.error(f"擴縮容分析失敗: {e}")
            return ScalingDecision.MAINTAIN, current_stats.get('active_connections', 2), 0.0
    
    def _update_history(self, current_stats: Dict, load_metrics: Dict):
        """更新歷史數據"""
        # 計算當前負載分數
        load_score = self._calculate_load_score(current_stats, load_metrics)
        self.load_history.append(load_score)
        
        # 更新響應時間歷史
        avg_response_time = current_stats.get('average_wait_time_ms', 0)
        self.response_history.append(avg_response_time)
        
        # 更新連線數歷史
        total_connections = (
            current_stats.get('active_connections', 0) + 
            current_stats.get('idle_connections', 0)
        )
        self.connection_history.append(total_connections)
        
        # 更新吞吐量歷史
        throughput = self._estimate_throughput(current_stats)
        self.throughput_history.append(throughput)
    
    def _calculate_load_score(self, current_stats: Dict, load_metrics: Dict) -> float:
        """計算綜合負載分數 (0-100)"""
        weights = {
            'active_ratio': 0.4,      # 活躍連線比例
            'queue_pressure': 0.3,     # 排隊壓力
            'response_time': 0.2,      # 響應時間
            'error_rate': 0.1          # 錯誤率
        }
        
        total_connections = (
            current_stats.get('active_connections', 0) + 
            current_stats.get('idle_connections', 0)
        )
        
        # 活躍連線比例分數
        active_ratio = 0
        if total_connections > 0:
            active_ratio = current_stats.get('active_connections', 0) / total_connections
        active_score = active_ratio * 100
        
        # 排隊壓力分數
        waiting_requests = current_stats.get('waiting_requests', 0)
        queue_score = min(waiting_requests * 20, 100)  # 5個排隊請求 = 100分
        
        # 響應時間分數 (以50ms為基準)
        response_time = current_stats.get('average_wait_time_ms', 0)
        response_score = min((response_time / 50) * 100, 100)
        
        # 錯誤率分數
        success_rate = current_stats.get('success_rate', 100)
        error_score = (100 - success_rate) * 5  # 放大錯誤率影響
        
        # 加權計算總分
        total_score = (
            active_score * weights['active_ratio'] +
            queue_score * weights['queue_pressure'] +
            response_score * weights['response_time'] +
            error_score * weights['error_rate']
        )
        
        return min(max(total_score, 0), 100)
    
    def _predict_load(self) -> LoadPrediction:
        """預測未來負載"""
        if len(self.load_history) < 5:
            return LoadPrediction(
                predicted_load=50.0,
                confidence=0.1,
                trend_direction=0.0,
                predicted_response_time=0.0,
                recommended_capacity=self.min_connections
            )
        
        # 使用移動平均和趨勢分析進行預測
        recent_loads = list(self.load_history)[-30:]  # 最近30個數據點
        
        # 計算移動平均
        short_ma = statistics.mean(recent_loads[-5:])   # 短期平均
        long_ma = statistics.mean(recent_loads[-15:])   # 長期平均
        
        # 趨勢分析
        trend = (short_ma - long_ma) / long_ma if long_ma > 0 else 0
        trend = max(min(trend, 1.0), -1.0)  # 限制在-1到1之間
        
        # 預測未來5分鐘負載
        predicted_load = short_ma * (1 + trend * 0.2)  # 加入趨勢影響
        predicted_load = max(min(predicted_load, 100), 0)
        
        # 計算信心度（基於數據穩定性）
        load_variance = statistics.variance(recent_loads) if len(recent_loads) > 1 else 0
        confidence = max(0.1, 1.0 - (load_variance / 1000))  # 方差越小信心度越高
        
        # 預測響應時間
        predicted_response_time = self._predict_response_time(predicted_load)
        
        # 建議容量
        recommended_capacity = self._calculate_optimal_capacity(predicted_load)
        
        return LoadPrediction(
            predicted_load=predicted_load,
            confidence=confidence,
            trend_direction=trend,
            predicted_response_time=predicted_response_time,
            recommended_capacity=recommended_capacity
        )
    
    def _predict_response_time(self, predicted_load: float) -> float:
        """根據負載預測響應時間"""
        if not self.response_history:
            return 0.0
        
        # 使用指數模型：響應時間隨負載指數增長
        base_response_time = statistics.mean(list(self.response_history)[-10:])
        load_factor = predicted_load / 100.0
        
        # 當負載超過80%時響應時間急劇增加
        if load_factor > 0.8:
            multiplier = math.exp((load_factor - 0.8) * 3)
        else:
            multiplier = 1 + load_factor * 0.5
        
        return base_response_time * multiplier
    
    def _calculate_optimal_capacity(self, predicted_load: float) -> int:
        """計算最佳連線數"""
        # 基於負載計算基礎容量需求
        base_capacity = math.ceil((predicted_load / 100.0) * self.max_connections)
        
        # 考慮突發流量的緩衝
        if predicted_load > 70:
            buffer_factor = 1.3
        elif predicted_load > 50:
            buffer_factor = 1.2
        else:
            buffer_factor = 1.1
        
        optimal_capacity = math.ceil(base_capacity * buffer_factor)
        
        return max(self.min_connections, min(optimal_capacity, self.max_connections))
    
    def _analyze_performance_trend(self) -> float:
        """分析效能趨勢 (-1到1, 負值表示效能下降)"""
        if len(self.response_history) < 10:
            return 0.0
        
        recent_responses = list(self.response_history)[-10:]
        earlier_responses = list(self.response_history)[-20:-10] if len(self.response_history) >= 20 else recent_responses
        
        recent_avg = statistics.mean(recent_responses)
        earlier_avg = statistics.mean(earlier_responses)
        
        if earlier_avg == 0:
            return 0.0
        
        # 響應時間增加表示效能下降
        performance_change = (earlier_avg - recent_avg) / earlier_avg
        return max(min(performance_change, 1.0), -1.0)
    
    def _detect_anomaly(self) -> float:
        """檢測異常狀況 (0-1, 1表示嚴重異常)"""
        if len(self.response_history) < 20:
            return 0.0
        
        recent_data = list(self.response_history)[-10:]
        historical_data = list(self.response_history)[:-10]
        
        # 計算Z-score檢測異常
        if not historical_data:
            return 0.0
        
        historical_mean = statistics.mean(historical_data)
        historical_std = statistics.stdev(historical_data) if len(historical_data) > 1 else 0
        
        if historical_std == 0:
            return 0.0
        
        recent_mean = statistics.mean(recent_data)
        z_score = abs((recent_mean - historical_mean) / historical_std)
        
        # 將Z-score映射到0-1範圍
        anomaly_score = min(z_score / 3.0, 1.0)  # 3個標準差為最大異常
        
        return anomaly_score
    
    def _make_scaling_decision(
        self,
        prediction: LoadPrediction,
        performance_trend: float,
        anomaly_score: float,
        current_stats: Dict
    ) -> Tuple[ScalingDecision, int, float]:
        """制定擴縮容決策"""
        
        current_total = (
            current_stats.get('active_connections', 0) + 
            current_stats.get('idle_connections', 0)
        )
        
        # 檢查冷卻期
        if datetime.now() - self.last_scaling_time < self.cooldown_period:
            return ScalingDecision.MAINTAIN, current_total, 0.5
        
        # 緊急情況檢測
        if (prediction.predicted_load > 90 or 
            anomaly_score > 0.8 or 
            current_stats.get('waiting_requests', 0) > 5):
            
            emergency_capacity = min(
                current_total + math.ceil(current_total * 0.5),
                self.max_connections
            )
            return ScalingDecision.EMERGENCY_SCALE, emergency_capacity, 0.9
        
        # 正常擴縮容決策
        recommended_capacity = prediction.recommended_capacity
        
        # 決策邏輯
        capacity_diff = recommended_capacity - current_total
        relative_diff = capacity_diff / current_total if current_total > 0 else 0
        
        # 綜合評分
        decision_score = (
            prediction.predicted_load / 100.0 * 0.4 +          # 預測負載權重
            max(0, -performance_trend) * 0.3 +                   # 效能下降權重  
            anomaly_score * 0.2 +                                # 異常情況權重
            max(0, relative_diff) * 0.1                         # 容量差異權重
        )
        
        # 制定決策
        if decision_score > 0.7 and recommended_capacity > current_total:
            decision = ScalingDecision.SCALE_UP
            target_size = min(recommended_capacity, self.max_connections)
            confidence = prediction.confidence * 0.8
            
        elif decision_score < 0.3 and recommended_capacity < current_total:
            decision = ScalingDecision.SCALE_DOWN  
            target_size = max(recommended_capacity, self.min_connections)
            confidence = prediction.confidence * 0.6
            
        else:
            decision = ScalingDecision.MAINTAIN
            target_size = current_total
            confidence = 0.5
        
        return decision, target_size, confidence
    
    def _update_decision_history(self, decision: ScalingDecision):
        """更新決策歷史"""
        if hasattr(self, 'last_decision') and self.last_decision == decision:
            self.consecutive_decisions += 1
        else:
            self.consecutive_decisions = 1
        
        self.last_decision = decision
        
        if decision != ScalingDecision.MAINTAIN:
            self.last_scaling_time = datetime.now()
    
    def _estimate_throughput(self, current_stats: Dict) -> float:
        """估算當前吞吐量"""
        # 基於請求數和時間窗口估算
        total_served = current_stats.get('total_requests_served', 0)
        
        if hasattr(self, 'last_total_served') and hasattr(self, 'last_measurement_time'):
            time_diff = (datetime.now() - self.last_measurement_time).total_seconds()
            if time_diff > 0:
                throughput = (total_served - self.last_total_served) / time_diff
            else:
                throughput = 0.0
        else:
            throughput = 0.0
        
        self.last_total_served = total_served
        self.last_measurement_time = datetime.now()
        
        return max(throughput, 0.0)
    
    def get_algorithm_status(self) -> Dict[str, Any]:
        """獲取算法狀態資訊"""
        return {
            'load_history_size': len(self.load_history),
            'response_history_size': len(self.response_history),
            'current_trend': self.current_trend,
            'consecutive_decisions': self.consecutive_decisions,
            'last_scaling_time': self.last_scaling_time.isoformat(),
            'performance_profiles_count': len(self.performance_profiles),
            'algorithm_version': "v2.0-adaptive"
        }


class CompetitionAwareScheduler:
    """
    競爭感知連線調度器
    
    專門處理高併發場景下的連線分配競爭問題
    """
    
    def __init__(self):
        self.request_queue: List[Tuple[float, asyncio.Future]] = []
        self.processing_lock = asyncio.Lock()
        self.fair_share_enabled = True
        
        # 統計資料
        self.total_wait_time = 0.0
        self.request_count = 0
        self.competition_events = 0
        
        logger.info("競爭感知調度器已初始化")
    
    async def schedule_connection_request(
        self, 
        priority: float = 1.0
    ) -> asyncio.Future:
        """
        調度連線請求
        
        使用公平調度算法減少競爭
        """
        future = asyncio.Future()
        request_time = time.time()
        
        async with self.processing_lock:
            self.request_queue.append((priority + request_time * 0.001, future))
            self.request_queue.sort(key=lambda x: x[0], reverse=True)  # 高優先級優先
        
        return future
    
    async def fulfill_next_request(self, connection) -> bool:
        """
        完成下一個連線請求
        
        返回是否成功分配連線
        """
        async with self.processing_lock:
            if not self.request_queue:
                return False
            
            priority, future = self.request_queue.pop(0)
            
            if not future.cancelled():
                future.set_result(connection)
                self.request_count += 1
                return True
            
        return False
    
    def get_scheduler_stats(self) -> Dict[str, Any]:
        """獲取調度器統計資訊"""
        avg_wait_time = 0.0
        if self.request_count > 0:
            avg_wait_time = self.total_wait_time / self.request_count
        
        return {
            'pending_requests': len(self.request_queue),
            'total_requests_processed': self.request_count,
            'average_wait_time_ms': avg_wait_time * 1000,
            'competition_events': self.competition_events,
            'fair_share_enabled': self.fair_share_enabled
        }