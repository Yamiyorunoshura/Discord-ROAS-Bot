"""
Docker 測試框架效能基準管理和回歸檢測系統
Task ID: T1 - 效能優化專門化

Ethan 效能專家的基準管理核心實作：
- 效能基準建立和維護
- 自動化回歸檢測
- 歷史趨勢分析
- 效能退化告警
- 基準版本管理
"""

import time
import json
import logging
import statistics
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict, deque
import hashlib
import uuid

logger = logging.getLogger(__name__)


class PerformanceMetricType(Enum):
    """效能指標類型"""
    EXECUTION_TIME = "execution_time"
    MEMORY_USAGE = "memory_usage"
    CPU_USAGE = "cpu_usage"
    SUCCESS_RATE = "success_rate"
    THROUGHPUT = "throughput"
    LATENCY = "latency"
    RESOURCE_EFFICIENCY = "resource_efficiency"


class RegressionSeverity(Enum):
    """回歸嚴重程度"""
    NONE = "none"
    MINOR = "minor"         # 5-15% 退化
    MODERATE = "moderate"   # 15-30% 退化
    MAJOR = "major"         # 30-50% 退化
    CRITICAL = "critical"   # >50% 退化


@dataclass
class PerformanceMetric:
    """效能指標"""
    metric_type: PerformanceMetricType
    value: float
    unit: str
    timestamp: float
    test_context: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'metric_type': self.metric_type.value,
            'value': self.value,
            'unit': self.unit,
            'timestamp': self.timestamp,
            'test_context': self.test_context
        }


@dataclass
class PerformanceBaseline:
    """效能基準"""
    baseline_id: str
    version: str
    created_at: float
    test_suite_config: Dict[str, Any]
    metrics: Dict[PerformanceMetricType, Dict[str, float]]  # 統計數據 (mean, std, min, max)
    sample_size: int
    confidence_level: float = 0.95
    notes: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'baseline_id': self.baseline_id,
            'version': self.version,
            'created_at': self.created_at,
            'test_suite_config': self.test_suite_config,
            'metrics': {k.value: v for k, v in self.metrics.items()},
            'sample_size': self.sample_size,
            'confidence_level': self.confidence_level,
            'notes': self.notes
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PerformanceBaseline':
        metrics = {PerformanceMetricType(k): v for k, v in data['metrics'].items()}
        return cls(
            baseline_id=data['baseline_id'],
            version=data['version'],
            created_at=data['created_at'],
            test_suite_config=data['test_suite_config'],
            metrics=metrics,
            sample_size=data['sample_size'],
            confidence_level=data.get('confidence_level', 0.95),
            notes=data.get('notes', '')
        )


@dataclass
class RegressionDetectionResult:
    """回歸檢測結果"""
    metric_type: PerformanceMetricType
    baseline_value: float
    current_value: float
    regression_percent: float
    severity: RegressionSeverity
    is_regression: bool
    confidence: float
    statistical_significance: bool
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'metric_type': self.metric_type.value,
            'baseline_value': self.baseline_value,
            'current_value': self.current_value,
            'regression_percent': self.regression_percent,
            'severity': self.severity.value,
            'is_regression': self.is_regression,
            'confidence': self.confidence,
            'statistical_significance': self.statistical_significance
        }


class PerformanceBaselineManager:
    """效能基準管理器
    
    管理效能基準的建立、更新、版本控制：
    - 自動基準建立和維護
    - 版本化基準管理
    - 基準比較和選擇
    - 基準數據持久化
    """
    
    def __init__(self, storage_path: str = "/Users/tszkinlai/Coding/roas-bot/test_reports"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.baselines_file = self.storage_path / "performance_baselines.json"
        
        # 載入現有基準
        self.baselines: Dict[str, PerformanceBaseline] = {}
        self.load_baselines()
        
        # 基準建立配置
        self.min_sample_size = 10
        self.max_sample_size = 100
        self.confidence_level = 0.95
        
    def create_baseline_from_metrics(
        self, 
        version: str,
        raw_metrics: List[PerformanceMetric],
        test_suite_config: Dict[str, Any],
        notes: str = ""
    ) -> PerformanceBaseline:
        """從原始指標創建基準"""
        if len(raw_metrics) < self.min_sample_size:
            raise ValueError(f"樣本數量不足，需要至少 {self.min_sample_size} 個樣本")
        
        # 按指標類型分組
        metrics_by_type = defaultdict(list)
        for metric in raw_metrics:
            metrics_by_type[metric.metric_type].append(metric.value)
        
        # 計算統計數據
        baseline_metrics = {}
        for metric_type, values in metrics_by_type.items():
            if values:
                baseline_metrics[metric_type] = {
                    'mean': statistics.mean(values),
                    'std': statistics.stdev(values) if len(values) > 1 else 0.0,
                    'min': min(values),
                    'max': max(values),
                    'median': statistics.median(values),
                    'p95': self._calculate_percentile(values, 0.95),
                    'p99': self._calculate_percentile(values, 0.99)
                }
        
        # 創建基準
        baseline_id = self._generate_baseline_id(version, test_suite_config)
        baseline = PerformanceBaseline(
            baseline_id=baseline_id,
            version=version,
            created_at=time.time(),
            test_suite_config=test_suite_config,
            metrics=baseline_metrics,
            sample_size=len(raw_metrics),
            confidence_level=self.confidence_level,
            notes=notes
        )
        
        # 儲存基準
        self.baselines[baseline_id] = baseline
        self.save_baselines()
        
        logger.info(f"已創建效能基準: {baseline_id} (版本: {version}, 樣本: {len(raw_metrics)})")
        return baseline
    
    def create_baseline_from_test_results(
        self,
        version: str,
        test_results: Dict[str, Any],
        notes: str = ""
    ) -> PerformanceBaseline:
        """從測試結果創建基準"""
        raw_metrics = self._extract_metrics_from_test_results(test_results)
        test_suite_config = self._extract_test_config(test_results)
        
        return self.create_baseline_from_metrics(
            version=version,
            raw_metrics=raw_metrics,
            test_suite_config=test_suite_config,
            notes=notes
        )
    
    def get_baseline(self, baseline_id: Optional[str] = None, version: Optional[str] = None) -> Optional[PerformanceBaseline]:
        """獲取基準"""
        if baseline_id:
            return self.baselines.get(baseline_id)
        
        if version:
            # 查找指定版本的基準
            for baseline in self.baselines.values():
                if baseline.version == version:
                    return baseline
        
        # 返回最新的基準
        if self.baselines:
            latest_baseline = max(self.baselines.values(), key=lambda b: b.created_at)
            return latest_baseline
        
        return None
    
    def list_baselines(self) -> List[PerformanceBaseline]:
        """列出所有基準"""
        return sorted(self.baselines.values(), key=lambda b: b.created_at, reverse=True)
    
    def update_baseline(self, baseline_id: str, additional_metrics: List[PerformanceMetric]) -> PerformanceBaseline:
        """更新基準（增加更多樣本）"""
        if baseline_id not in self.baselines:
            raise ValueError(f"基準不存在: {baseline_id}")
        
        baseline = self.baselines[baseline_id]
        
        # 重新計算統計數據
        # 這裡簡化處理，實際實作可能需要更複雜的增量更新邏輯
        logger.info(f"基準更新功能暫不支援增量更新，建議重新創建基準")
        return baseline
    
    def delete_baseline(self, baseline_id: str) -> bool:
        """刪除基準"""
        if baseline_id in self.baselines:
            del self.baselines[baseline_id]
            self.save_baselines()
            logger.info(f"已刪除基準: {baseline_id}")
            return True
        return False
    
    def save_baselines(self) -> None:
        """儲存基準到文件"""
        baselines_data = {
            baseline_id: baseline.to_dict()
            for baseline_id, baseline in self.baselines.items()
        }
        
        with open(self.baselines_file, 'w', encoding='utf-8') as f:
            json.dump({
                'metadata': {
                    'version': '1.0',
                    'created_at': time.time(),
                    'total_baselines': len(baselines_data)
                },
                'baselines': baselines_data
            }, f, indent=2, ensure_ascii=False)
    
    def load_baselines(self) -> None:
        """從文件載入基準"""
        if not self.baselines_file.exists():
            return
        
        try:
            with open(self.baselines_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            baselines_data = data.get('baselines', {})
            self.baselines = {
                baseline_id: PerformanceBaseline.from_dict(baseline_data)
                for baseline_id, baseline_data in baselines_data.items()
            }
            
            logger.info(f"已載入 {len(self.baselines)} 個效能基準")
            
        except Exception as e:
            logger.error(f"載入基準失敗: {e}")
            self.baselines = {}
    
    def _extract_metrics_from_test_results(self, test_results: Dict[str, Any]) -> List[PerformanceMetric]:
        """從測試結果提取指標"""
        metrics = []
        current_time = time.time()
        
        # 從不同的結果結構中提取指標
        if 'execution_summary' in test_results:
            summary = test_results['execution_summary']
            
            # 執行時間指標
            if 'total_execution_time_seconds' in summary:
                metrics.append(PerformanceMetric(
                    metric_type=PerformanceMetricType.EXECUTION_TIME,
                    value=summary['total_execution_time_seconds'],
                    unit='seconds',
                    timestamp=current_time
                ))
            
            # 成功率指標
            if 'success_rate_percent' in summary:
                metrics.append(PerformanceMetric(
                    metric_type=PerformanceMetricType.SUCCESS_RATE,
                    value=summary['success_rate_percent'],
                    unit='percent',
                    timestamp=current_time
                ))
            
            # 吞吐量指標
            if 'total_tests' in summary and 'total_execution_time_seconds' in summary:
                throughput = summary['total_tests'] / summary['total_execution_time_seconds']
                metrics.append(PerformanceMetric(
                    metric_type=PerformanceMetricType.THROUGHPUT,
                    value=throughput,
                    unit='tests/second',
                    timestamp=current_time
                ))
        
        # 從效能分析中提取資源指標
        if 'performance_analysis' in test_results:
            analysis = test_results['performance_analysis']
            
            if 'resource_efficiency_analysis' in analysis:
                resource = analysis['resource_efficiency_analysis']
                
                # 記憶體指標
                if 'average_memory_usage_mb' in resource:
                    metrics.append(PerformanceMetric(
                        metric_type=PerformanceMetricType.MEMORY_USAGE,
                        value=resource['average_memory_usage_mb'],
                        unit='MB',
                        timestamp=current_time
                    ))
                
                # CPU 指標
                if 'average_cpu_usage_percent' in resource:
                    metrics.append(PerformanceMetric(
                        metric_type=PerformanceMetricType.CPU_USAGE,
                        value=resource['average_cpu_usage_percent'],
                        unit='percent',
                        timestamp=current_time
                    ))
        
        return metrics
    
    def _extract_test_config(self, test_results: Dict[str, Any]) -> Dict[str, Any]:
        """提取測試配置"""
        config = {}
        
        if 'execution_metadata' in test_results:
            metadata = test_results['execution_metadata']
            config['strategy'] = metadata.get('strategy')
            config['total_batches'] = metadata.get('total_batches')
            config['scalability_profile'] = metadata.get('scalability_profile')
        
        if 'execution_summary' in test_results:
            summary = test_results['execution_summary']
            config['total_tests'] = summary.get('total_tests')
        
        return config
    
    def _generate_baseline_id(self, version: str, config: Dict[str, Any]) -> str:
        """生成基準ID"""
        config_hash = hashlib.md5(json.dumps(config, sort_keys=True).encode()).hexdigest()[:8]
        return f"baseline_{version}_{config_hash}"
    
    def _calculate_percentile(self, values: List[float], percentile: float) -> float:
        """計算百分位數"""
        sorted_values = sorted(values)
        index = int(percentile * (len(sorted_values) - 1))
        return sorted_values[index]


class RegressionDetector:
    """效能回歸檢測器
    
    檢測效能回歸和改進：
    - 統計顯著性檢測
    - 趨勢分析
    - 多指標綜合評估
    - 智能告警機制
    """
    
    def __init__(self, baseline_manager: PerformanceBaselineManager):
        self.baseline_manager = baseline_manager
        
        # 回歸閾值配置
        self.regression_thresholds = {
            RegressionSeverity.MINOR: 0.05,      # 5%
            RegressionSeverity.MODERATE: 0.15,   # 15%
            RegressionSeverity.MAJOR: 0.30,      # 30%
            RegressionSeverity.CRITICAL: 0.50    # 50%
        }
        
        # 檢測歷史
        self.detection_history: List[Dict[str, Any]] = []
    
    def detect_regression(
        self, 
        current_metrics: List[PerformanceMetric],
        baseline_id: Optional[str] = None,
        significance_level: float = 0.05
    ) -> Dict[str, Any]:
        """檢測效能回歸"""
        
        # 獲取基準
        baseline = self.baseline_manager.get_baseline(baseline_id)
        if not baseline:
            logger.warning("未找到效能基準，無法進行回歸檢測")
            return {'error': '未找到效能基準'}
        
        logger.info(f"使用基準 {baseline.baseline_id} 進行回歸檢測")
        
        # 按指標類型分組當前指標
        current_metrics_by_type = defaultdict(list)
        for metric in current_metrics:
            current_metrics_by_type[metric.metric_type].append(metric.value)
        
        detection_results = []
        overall_regression_detected = False
        max_severity = RegressionSeverity.NONE
        
        # 檢測每個指標類型
        for metric_type, baseline_stats in baseline.metrics.items():
            if metric_type not in current_metrics_by_type:
                continue
            
            current_values = current_metrics_by_type[metric_type]
            current_mean = statistics.mean(current_values)
            baseline_mean = baseline_stats['mean']
            
            # 計算回歸百分比
            if baseline_mean != 0:
                regression_percent = (current_mean - baseline_mean) / baseline_mean
            else:
                regression_percent = 0.0
            
            # 判斷是否為回歸（根據指標類型決定方向）
            is_regression = self._is_regression_by_metric_type(metric_type, regression_percent)
            
            # 確定嚴重程度
            severity = self._determine_regression_severity(abs(regression_percent))
            
            # 統計顯著性檢測（簡化版）
            statistical_significance = self._test_statistical_significance(
                current_values, baseline_stats, significance_level
            )
            
            # 信心度計算
            confidence = self._calculate_confidence(
                current_values, baseline_stats, statistical_significance
            )
            
            result = RegressionDetectionResult(
                metric_type=metric_type,
                baseline_value=baseline_mean,
                current_value=current_mean,
                regression_percent=regression_percent * 100,  # 轉為百分比
                severity=severity,
                is_regression=is_regression,
                confidence=confidence,
                statistical_significance=statistical_significance
            )
            
            detection_results.append(result)
            
            if is_regression:
                overall_regression_detected = True
                if severity.value > max_severity.value:
                    max_severity = severity
        
        # 生成檢測報告
        detection_report = {
            'detection_metadata': {
                'timestamp': time.time(),
                'baseline_id': baseline.baseline_id,
                'baseline_version': baseline.version,
                'current_sample_size': len(current_metrics),
                'baseline_sample_size': baseline.sample_size
            },
            'overall_assessment': {
                'regression_detected': overall_regression_detected,
                'max_severity': max_severity.value,
                'total_metrics_analyzed': len(detection_results),
                'regressed_metrics_count': sum(1 for r in detection_results if r.is_regression)
            },
            'detailed_results': [result.to_dict() for result in detection_results],
            'recommendations': self._generate_regression_recommendations(detection_results)
        }
        
        # 記錄檢測歷史
        self.detection_history.append(detection_report)
        
        # 觸發告警
        if overall_regression_detected:
            self._trigger_regression_alert(detection_report)
        
        return detection_report
    
    def analyze_performance_trends(self, days: int = 30) -> Dict[str, Any]:
        """分析效能趨勢"""
        cutoff_time = time.time() - (days * 24 * 3600)
        recent_detections = [
            d for d in self.detection_history 
            if d['detection_metadata']['timestamp'] > cutoff_time
        ]
        
        if not recent_detections:
            return {'error': f'過去 {days} 天內無檢測數據'}
        
        # 分析趨勢
        trend_analysis = {
            'analysis_period_days': days,
            'total_detections': len(recent_detections),
            'regression_frequency': sum(1 for d in recent_detections if d['overall_assessment']['regression_detected']),
            'trend_by_metric': self._analyze_metric_trends(recent_detections),
            'severity_distribution': self._analyze_severity_distribution(recent_detections),
            'performance_stability_score': self._calculate_stability_score(recent_detections)
        }
        
        return trend_analysis
    
    def _is_regression_by_metric_type(self, metric_type: PerformanceMetricType, change_percent: float) -> bool:
        """根據指標類型判斷是否為回歸"""
        # 對於這些指標，增加代表退化
        degrading_metrics = {
            PerformanceMetricType.EXECUTION_TIME,
            PerformanceMetricType.MEMORY_USAGE,
            PerformanceMetricType.CPU_USAGE,
            PerformanceMetricType.LATENCY
        }
        
        # 對於這些指標，減少代表退化
        improving_metrics = {
            PerformanceMetricType.SUCCESS_RATE,
            PerformanceMetricType.THROUGHPUT,
            PerformanceMetricType.RESOURCE_EFFICIENCY
        }
        
        threshold = self.regression_thresholds[RegressionSeverity.MINOR]
        
        if metric_type in degrading_metrics:
            return change_percent > threshold
        elif metric_type in improving_metrics:
            return change_percent < -threshold
        else:
            # 預設行為：任何顯著變化都視為需要關注
            return abs(change_percent) > threshold
    
    def _determine_regression_severity(self, abs_change_percent: float) -> RegressionSeverity:
        """確定回歸嚴重程度"""
        if abs_change_percent >= self.regression_thresholds[RegressionSeverity.CRITICAL]:
            return RegressionSeverity.CRITICAL
        elif abs_change_percent >= self.regression_thresholds[RegressionSeverity.MAJOR]:
            return RegressionSeverity.MAJOR
        elif abs_change_percent >= self.regression_thresholds[RegressionSeverity.MODERATE]:
            return RegressionSeverity.MODERATE
        elif abs_change_percent >= self.regression_thresholds[RegressionSeverity.MINOR]:
            return RegressionSeverity.MINOR
        else:
            return RegressionSeverity.NONE
    
    def _test_statistical_significance(
        self, 
        current_values: List[float],
        baseline_stats: Dict[str, float],
        significance_level: float
    ) -> bool:
        """測試統計顯著性（簡化版）"""
        if len(current_values) < 3:
            return False
        
        current_mean = statistics.mean(current_values)
        current_std = statistics.stdev(current_values) if len(current_values) > 1 else 0
        baseline_mean = baseline_stats['mean']
        baseline_std = baseline_stats['std']
        
        # 簡化的 t-test 檢驗
        if current_std == 0 and baseline_std == 0:
            return abs(current_mean - baseline_mean) > 0.001
        
        # 合併標準誤差
        pooled_std = ((current_std ** 2) + (baseline_std ** 2)) ** 0.5
        if pooled_std == 0:
            return False
        
        # 計算 t 統計量
        t_stat = abs(current_mean - baseline_mean) / pooled_std
        
        # 簡化判斷：t > 2 認為顯著
        return t_stat > 2.0
    
    def _calculate_confidence(
        self, 
        current_values: List[float],
        baseline_stats: Dict[str, float],
        statistical_significance: bool
    ) -> float:
        """計算信心度"""
        base_confidence = 0.5
        
        # 樣本大小影響
        sample_size_factor = min(len(current_values) / 10, 1.0) * 0.2
        
        # 統計顯著性影響
        significance_factor = 0.3 if statistical_significance else 0.0
        
        # 變化幅度影響（變化越大，信心度越高）
        current_mean = statistics.mean(current_values)
        baseline_mean = baseline_stats['mean']
        if baseline_mean != 0:
            change_magnitude = abs((current_mean - baseline_mean) / baseline_mean)
            magnitude_factor = min(change_magnitude * 2, 0.3)
        else:
            magnitude_factor = 0.0
        
        confidence = base_confidence + sample_size_factor + significance_factor + magnitude_factor
        return min(confidence, 1.0)
    
    def _generate_regression_recommendations(self, results: List[RegressionDetectionResult]) -> List[str]:
        """生成回歸建議"""
        recommendations = []
        
        regressed_results = [r for r in results if r.is_regression]
        if not regressed_results:
            recommendations.append("未檢測到效能回歸，維持當前優化策略")
            return recommendations
        
        # 按嚴重程度分析
        critical_regressions = [r for r in regressed_results if r.severity == RegressionSeverity.CRITICAL]
        major_regressions = [r for r in regressed_results if r.severity == RegressionSeverity.MAJOR]
        
        if critical_regressions:
            recommendations.append(f"🚨 嚴重效能回歸: {len(critical_regressions)} 個指標，需立即調查和修復")
        
        if major_regressions:
            recommendations.append(f"⚠️ 重大效能回歸: {len(major_regressions)} 個指標，建議優先處理")
        
        # 具體指標建議
        for result in regressed_results:
            if result.severity in [RegressionSeverity.CRITICAL, RegressionSeverity.MAJOR]:
                if result.metric_type == PerformanceMetricType.EXECUTION_TIME:
                    recommendations.append("執行時間退化，檢查並行策略和資源分配")
                elif result.metric_type == PerformanceMetricType.MEMORY_USAGE:
                    recommendations.append("記憶體使用增加，檢查記憶體洩漏和清理機制")
                elif result.metric_type == PerformanceMetricType.SUCCESS_RATE:
                    recommendations.append("測試成功率下降，檢查測試穩定性和錯誤處理")
        
        return recommendations
    
    def _trigger_regression_alert(self, detection_report: Dict[str, Any]) -> None:
        """觸發回歸告警"""
        severity = detection_report['overall_assessment']['max_severity']
        regressed_count = detection_report['overall_assessment']['regressed_metrics_count']
        
        logger.warning(f"🚨 效能回歸告警: 嚴重程度={severity}, 影響指標={regressed_count}")
        
        # 這裡可以整合告警系統，如發送郵件、Slack 通知等
    
    def _analyze_metric_trends(self, recent_detections: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析指標趨勢"""
        metric_trends = {}
        
        # 收集每個指標的歷史數據
        for detection in recent_detections:
            for result in detection['detailed_results']:
                metric_type = result['metric_type']
                if metric_type not in metric_trends:
                    metric_trends[metric_type] = {
                        'values': [],
                        'regression_count': 0,
                        'timestamps': []
                    }
                
                metric_trends[metric_type]['values'].append(result['current_value'])
                metric_trends[metric_type]['timestamps'].append(detection['detection_metadata']['timestamp'])
                
                if result['is_regression']:
                    metric_trends[metric_type]['regression_count'] += 1
        
        # 計算趨勢
        for metric_type, data in metric_trends.items():
            values = data['values']
            if len(values) >= 2:
                # 簡單線性趨勢
                slope = (values[-1] - values[0]) / max(len(values) - 1, 1)
                metric_trends[metric_type]['trend_slope'] = slope
                metric_trends[metric_type]['trend_direction'] = 'increasing' if slope > 0 else 'decreasing' if slope < 0 else 'stable'
            else:
                metric_trends[metric_type]['trend_slope'] = 0
                metric_trends[metric_type]['trend_direction'] = 'insufficient_data'
        
        return metric_trends
    
    def _analyze_severity_distribution(self, recent_detections: List[Dict[str, Any]]) -> Dict[str, int]:
        """分析嚴重程度分佈"""
        severity_counts = defaultdict(int)
        
        for detection in recent_detections:
            severity = detection['overall_assessment']['max_severity']
            severity_counts[severity] += 1
        
        return dict(severity_counts)
    
    def _calculate_stability_score(self, recent_detections: List[Dict[str, Any]]) -> float:
        """計算效能穩定性評分（0-100）"""
        if not recent_detections:
            return 100.0
        
        total_detections = len(recent_detections)
        regression_detections = sum(1 for d in recent_detections if d['overall_assessment']['regression_detected'])
        
        # 基礎穩定性評分
        stability_score = ((total_detections - regression_detections) / total_detections) * 100
        
        # 根據回歸嚴重程度調整
        for detection in recent_detections:
            if detection['overall_assessment']['regression_detected']:
                severity = detection['overall_assessment']['max_severity']
                if severity == 'critical':
                    stability_score -= 10
                elif severity == 'major':
                    stability_score -= 5
                elif severity == 'moderate':
                    stability_score -= 2
        
        return max(0.0, stability_score)


# 便利函數和工廠
def create_baseline_management_system(storage_path: Optional[str] = None) -> Tuple[PerformanceBaselineManager, RegressionDetector]:
    """創建基準管理系統"""
    baseline_manager = PerformanceBaselineManager(storage_path or "/Users/tszkinlai/Coding/roas-bot/test_reports")
    regression_detector = RegressionDetector(baseline_manager)
    
    return baseline_manager, regression_detector


def establish_performance_baseline_from_current_results(
    test_results: Dict[str, Any],
    version: str = "v2.4.2",
    notes: str = ""
) -> PerformanceBaseline:
    """從當前測試結果建立效能基準"""
    baseline_manager, _ = create_baseline_management_system()
    
    return baseline_manager.create_baseline_from_test_results(
        version=version,
        test_results=test_results,
        notes=notes or f"基準建立於 {datetime.now().isoformat()}"
    )