#!/usr/bin/env python3
"""
T2 - 併發測試錯誤率監控和報告系統
提供實時的錯誤率監控、自動化測試報告生成和性能分析功能
"""

import asyncio
import json
import logging
import time
import statistics
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class ErrorRateMetric:
    """錯誤率指標"""
    timestamp: datetime
    total_operations: int
    successful_operations: int
    failed_operations: int
    error_rate_percentage: float
    error_types: Dict[str, int]
    response_time_ms: float
    concurrent_workers: int
    test_phase: str


@dataclass
class PerformanceThresholds:
    """性能閾值配置"""
    max_error_rate: float = 1.0  # 1%
    max_p95_response_time_ms: float = 50.0  # 50ms
    min_success_rate: float = 99.0  # 99%
    max_concurrent_failures: int = 5  # 最大連續失敗數
    alert_error_rate: float = 0.5  # 0.5% 開始警告
    
    def to_dict(self) -> Dict[str, float]:
        return asdict(self)


class ErrorRateMonitor:
    """錯誤率監控系統"""
    
    def __init__(self, thresholds: Optional[PerformanceThresholds] = None):
        self.thresholds = thresholds or PerformanceThresholds()
        self.metrics: List[ErrorRateMetric] = []
        self.current_phase = "initialization"
        self.consecutive_failures = 0
        self.alerts: List[str] = []
        self.logger = logging.getLogger('error_rate_monitor')
        
    def record_operation_batch(
        self,
        successful_ops: int,
        failed_ops: int,
        response_times: List[float],
        concurrent_workers: int,
        error_details: Optional[Dict[str, int]] = None,
        phase: str = "unknown"
    ):
        """記錄一批操作的結果"""
        total_ops = successful_ops + failed_ops
        error_rate = (failed_ops / total_ops * 100) if total_ops > 0 else 0
        avg_response_time = statistics.mean(response_times) if response_times else 0
        
        metric = ErrorRateMetric(
            timestamp=datetime.now(),
            total_operations=total_ops,
            successful_operations=successful_ops,
            failed_operations=failed_ops,
            error_rate_percentage=error_rate,
            error_types=error_details or {},
            response_time_ms=avg_response_time,
            concurrent_workers=concurrent_workers,
            test_phase=phase
        )
        
        self.metrics.append(metric)
        self.current_phase = phase
        
        # 檢查閾值違反
        self._check_thresholds(metric)
        
        self.logger.debug(
            f"記錄 {phase} 階段：{successful_ops}/{total_ops} 成功，"
            f"錯誤率 {error_rate:.2f}%，響應時間 {avg_response_time:.2f}ms"
        )
    
    def _check_thresholds(self, metric: ErrorRateMetric):
        """檢查性能閾值"""
        alerts = []
        
        # 檢查錯誤率
        if metric.error_rate_percentage > self.thresholds.max_error_rate:
            alerts.append(
                f"錯誤率 {metric.error_rate_percentage:.2f}% 超過閾值 {self.thresholds.max_error_rate}%"
            )
            self.consecutive_failures += 1
        else:
            self.consecutive_failures = 0
            
        # 檢查響應時間（需要 P95，這裡用平均時間估算）
        if metric.response_time_ms > self.thresholds.max_p95_response_time_ms:
            alerts.append(
                f"響應時間 {metric.response_time_ms:.2f}ms 可能超過 P95 閾值 {self.thresholds.max_p95_response_time_ms}ms"
            )
            
        # 檢查成功率
        success_rate = (metric.successful_operations / metric.total_operations * 100) if metric.total_operations > 0 else 0
        if success_rate < self.thresholds.min_success_rate:
            alerts.append(
                f"成功率 {success_rate:.2f}% 低於閾值 {self.thresholds.min_success_rate}%"
            )
            
        # 檢查連續失敗
        if self.consecutive_failures >= self.thresholds.max_concurrent_failures:
            alerts.append(
                f"連續 {self.consecutive_failures} 批次未達標準，可能需要停止測試"
            )
        
        # 記錄警告
        if alerts:
            timestamp = metric.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            for alert in alerts:
                alert_msg = f"[{timestamp}] {metric.test_phase}: {alert}"
                self.alerts.append(alert_msg)
                self.logger.warning(alert_msg)
    
    def get_current_stats(self) -> Dict[str, Any]:
        """獲取當前統計"""
        if not self.metrics:
            return {"error": "無監控資料"}
            
        recent_metrics = self.metrics[-10:]  # 最近 10 批
        
        total_ops = sum(m.total_operations for m in recent_metrics)
        total_successful = sum(m.successful_operations for m in recent_metrics)
        total_failed = sum(m.failed_operations for m in recent_metrics)
        
        return {
            "current_phase": self.current_phase,
            "metrics_count": len(self.metrics),
            "recent_stats": {
                "total_operations": total_ops,
                "successful_operations": total_successful,
                "failed_operations": total_failed,
                "error_rate_percentage": (total_failed / total_ops * 100) if total_ops > 0 else 0,
                "average_response_time_ms": statistics.mean([m.response_time_ms for m in recent_metrics]),
                "average_concurrent_workers": statistics.mean([m.concurrent_workers for m in recent_metrics])
            },
            "consecutive_failures": self.consecutive_failures,
            "active_alerts": len([a for a in self.alerts if "超過閾值" in a or "低於閾值" in a]),
            "threshold_compliance": self._check_overall_compliance()
        }
    
    def _check_overall_compliance(self) -> Dict[str, bool]:
        """檢查整體合規性"""
        if not self.metrics:
            return {"overall": False}
            
        recent_metrics = self.metrics[-5:]  # 最近5批
        
        # 計算整體指標
        total_ops = sum(m.total_operations for m in recent_metrics)
        total_successful = sum(m.successful_operations for m in recent_metrics)
        total_failed = sum(m.failed_operations for m in recent_metrics)
        
        overall_error_rate = (total_failed / total_ops * 100) if total_ops > 0 else 0
        overall_success_rate = (total_successful / total_ops * 100) if total_ops > 0 else 0
        avg_response_time = statistics.mean([m.response_time_ms for m in recent_metrics])
        
        return {
            "error_rate_ok": overall_error_rate <= self.thresholds.max_error_rate,
            "success_rate_ok": overall_success_rate >= self.thresholds.min_success_rate,
            "response_time_ok": avg_response_time <= self.thresholds.max_p95_response_time_ms,
            "no_consecutive_failures": self.consecutive_failures < self.thresholds.max_concurrent_failures,
            "overall": (
                overall_error_rate <= self.thresholds.max_error_rate and
                overall_success_rate >= self.thresholds.min_success_rate and
                avg_response_time <= self.thresholds.max_p95_response_time_ms and
                self.consecutive_failures < self.thresholds.max_concurrent_failures
            )
        }


class ConcurrencyTestReporter:
    """併發測試報告生成器"""
    
    def __init__(self, output_dir: str = "test_reports/concurrency"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger('test_reporter')
        
    def generate_comprehensive_report(
        self,
        monitor: ErrorRateMonitor,
        test_config: Dict[str, Any],
        test_duration: float
    ) -> Dict[str, Any]:
        """生成綜合測試報告"""
        
        if not monitor.metrics:
            return {"error": "無測試資料可生成報告"}
            
        # 基本統計
        total_ops = sum(m.total_operations for m in monitor.metrics)
        total_successful = sum(m.successful_operations for m in monitor.metrics)
        total_failed = sum(m.failed_operations for m in monitor.metrics)
        
        # 時間序列分析
        time_series = self._analyze_time_series(monitor.metrics)
        
        # 性能分析
        performance_analysis = self._analyze_performance(monitor.metrics)
        
        # 錯誤分析
        error_analysis = self._analyze_errors(monitor.metrics)
        
        # T2 合規性檢查
        t2_compliance = self._check_t2_compliance(monitor)
        
        report = {
            "report_metadata": {
                "generated_at": datetime.now().isoformat(),
                "test_duration_seconds": test_duration,
                "test_configuration": test_config,
                "metrics_count": len(monitor.metrics),
                "thresholds": monitor.thresholds.to_dict()
            },
            "executive_summary": {
                "total_operations": total_ops,
                "successful_operations": total_successful,
                "failed_operations": total_failed,
                "overall_success_rate_percent": (total_successful / total_ops * 100) if total_ops > 0 else 0,
                "overall_error_rate_percent": (total_failed / total_ops * 100) if total_ops > 0 else 0,
                "average_throughput_ops_per_sec": total_ops / test_duration if test_duration > 0 else 0,
                "test_phases": list(set(m.test_phase for m in monitor.metrics))
            },
            "time_series_analysis": time_series,
            "performance_analysis": performance_analysis,
            "error_analysis": error_analysis,
            "t2_compliance": t2_compliance,
            "alerts_summary": {
                "total_alerts": len(monitor.alerts),
                "critical_alerts": len([a for a in monitor.alerts if "超過閾值" in a]),
                "recent_alerts": monitor.alerts[-10:] if len(monitor.alerts) > 10 else monitor.alerts
            },
            "recommendations": self._generate_recommendations(monitor, performance_analysis, error_analysis)
        }
        
        # 保存報告
        report_file = self._save_report(report)
        self.logger.info(f"綜合報告已生成：{report_file}")
        
        return report
    
    def _analyze_time_series(self, metrics: List[ErrorRateMetric]) -> Dict[str, Any]:
        """時間序列分析"""
        if len(metrics) < 2:
            return {"insufficient_data": True}
            
        # 按階段分組
        phases = {}
        for metric in metrics:
            if metric.test_phase not in phases:
                phases[metric.test_phase] = []
            phases[metric.test_phase].append(metric)
        
        phase_analysis = {}
        for phase, phase_metrics in phases.items():
            error_rates = [m.error_rate_percentage for m in phase_metrics]
            response_times = [m.response_time_ms for m in phase_metrics]
            
            phase_analysis[phase] = {
                "metrics_count": len(phase_metrics),
                "duration_minutes": (phase_metrics[-1].timestamp - phase_metrics[0].timestamp).total_seconds() / 60,
                "error_rate_trend": {
                    "start": error_rates[0] if error_rates else 0,
                    "end": error_rates[-1] if error_rates else 0,
                    "max": max(error_rates) if error_rates else 0,
                    "average": statistics.mean(error_rates) if error_rates else 0
                },
                "response_time_trend": {
                    "start_ms": response_times[0] if response_times else 0,
                    "end_ms": response_times[-1] if response_times else 0,
                    "max_ms": max(response_times) if response_times else 0,
                    "average_ms": statistics.mean(response_times) if response_times else 0
                }
            }
        
        return {
            "total_duration_minutes": (metrics[-1].timestamp - metrics[0].timestamp).total_seconds() / 60,
            "phases_analyzed": len(phases),
            "phase_details": phase_analysis
        }
    
    def _analyze_performance(self, metrics: List[ErrorRateMetric]) -> Dict[str, Any]:
        """性能分析"""
        response_times = [m.response_time_ms for m in metrics]
        concurrent_workers = [m.concurrent_workers for m in metrics]
        throughputs = [m.total_operations / 1 for m in metrics]  # 估算每秒吞吐量
        
        return {
            "response_time_analysis": {
                "min_ms": min(response_times) if response_times else 0,
                "max_ms": max(response_times) if response_times else 0,
                "average_ms": statistics.mean(response_times) if response_times else 0,
                "median_ms": statistics.median(response_times) if response_times else 0,
                "std_dev_ms": statistics.stdev(response_times) if len(response_times) > 1 else 0
            },
            "concurrency_analysis": {
                "max_concurrent_workers": max(concurrent_workers) if concurrent_workers else 0,
                "average_concurrent_workers": statistics.mean(concurrent_workers) if concurrent_workers else 0
            },
            "throughput_analysis": {
                "max_ops_per_batch": max(throughputs) if throughputs else 0,
                "average_ops_per_batch": statistics.mean(throughputs) if throughputs else 0,
                "total_ops_all_batches": sum(throughputs) if throughputs else 0
            }
        }
    
    def _analyze_errors(self, metrics: List[ErrorRateMetric]) -> Dict[str, Any]:
        """錯誤分析"""
        # 合併所有錯誤類型統計
        all_error_types = {}
        total_errors = 0
        
        for metric in metrics:
            total_errors += metric.failed_operations
            for error_type, count in metric.error_types.items():
                if error_type not in all_error_types:
                    all_error_types[error_type] = 0
                all_error_types[error_type] += count
        
        # 計算錯誤模式
        error_patterns = []
        high_error_phases = [
            m.test_phase for m in metrics 
            if m.error_rate_percentage > 1.0
        ]
        
        if high_error_phases:
            error_patterns.append(f"高錯誤率階段：{', '.join(set(high_error_phases))}")
        
        # 找出最常見的錯誤類型
        most_common_error = max(all_error_types.items(), key=lambda x: x[1]) if all_error_types else None
        
        return {
            "total_errors": total_errors,
            "error_types_distribution": all_error_types,
            "most_common_error": {
                "type": most_common_error[0] if most_common_error else None,
                "count": most_common_error[1] if most_common_error else 0,
                "percentage": (most_common_error[1] / total_errors * 100) if most_common_error and total_errors > 0 else 0
            },
            "error_patterns": error_patterns,
            "high_error_rate_phases": list(set(high_error_phases))
        }
    
    def _check_t2_compliance(self, monitor: ErrorRateMonitor) -> Dict[str, Any]:
        """檢查 T2 標準合規性"""
        compliance = monitor._check_overall_compliance()
        
        # 詳細的合規性檢查
        recent_metrics = monitor.metrics[-10:] if len(monitor.metrics) >= 10 else monitor.metrics
        
        total_ops = sum(m.total_operations for m in recent_metrics)
        total_successful = sum(m.successful_operations for m in recent_metrics)
        total_failed = sum(m.failed_operations for m in recent_metrics)
        
        overall_error_rate = (total_failed / total_ops * 100) if total_ops > 0 else 0
        overall_success_rate = (total_successful / total_ops * 100) if total_ops > 0 else 0
        avg_response_time = statistics.mean([m.response_time_ms for m in recent_metrics]) if recent_metrics else 0
        
        return {
            "t2_standards": {
                "max_error_rate_percent": monitor.thresholds.max_error_rate,
                "min_success_rate_percent": monitor.thresholds.min_success_rate,
                "max_p95_response_time_ms": monitor.thresholds.max_p95_response_time_ms
            },
            "measured_performance": {
                "actual_error_rate_percent": overall_error_rate,
                "actual_success_rate_percent": overall_success_rate,
                "average_response_time_ms": avg_response_time
            },
            "compliance_status": compliance,
            "overall_t2_compliant": compliance.get("overall", False),
            "compliance_score": sum(1 for v in compliance.values() if v) / len(compliance) * 100
        }
    
    def _generate_recommendations(
        self,
        monitor: ErrorRateMonitor,
        performance_analysis: Dict[str, Any],
        error_analysis: Dict[str, Any]
    ) -> List[str]:
        """生成優化建議"""
        recommendations = []
        
        # 基於錯誤率的建議
        if error_analysis["total_errors"] > 0:
            error_rate = (error_analysis["total_errors"] / sum(m.total_operations for m in monitor.metrics)) * 100
            if error_rate > 1.0:
                recommendations.append(f"錯誤率 {error_rate:.2f}% 過高，建議檢查連線池配置和資料庫效能")
        
        # 基於響應時間的建議
        avg_response_time = performance_analysis["response_time_analysis"]["average_ms"]
        if avg_response_time > 20:
            recommendations.append(f"平均響應時間 {avg_response_time:.2f}ms 偏高，建議優化查詢或增加連線池大小")
        
        # 基於併發性的建議
        max_workers = performance_analysis["concurrency_analysis"]["max_concurrent_workers"]
        if max_workers > 15:
            recommendations.append(f"最大併發工作者 {max_workers} 較高，確保連線池配置足以支持此負載")
        
        # 基於錯誤模式的建議
        if error_analysis["high_error_rate_phases"]:
            recommendations.append(f"在 {', '.join(error_analysis['high_error_rate_phases'])} 階段錯誤率較高，需要特別關注")
        
        # 連續失敗的建議
        if monitor.consecutive_failures > 0:
            recommendations.append(f"檢測到 {monitor.consecutive_failures} 次連續失敗，建議檢查系統穩定性")
        
        # 默認建議
        if not recommendations:
            recommendations.append("系統效能表現良好，建議保持當前配置並定期監控")
        
        return recommendations
    
    def _save_report(self, report: Dict[str, Any]) -> str:
        """保存報告到文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"concurrency_test_report_{timestamp}.json"
        filepath = self.output_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        
        return str(filepath)


# 使用範例和測試工具
async def demo_monitoring_system():
    """演示監控系統"""
    print("🔍 併發測試監控系統演示")
    
    # 初始化監控器
    monitor = ErrorRateMonitor()
    reporter = ConcurrencyTestReporter()
    
    # 模擬一系列測試批次
    test_phases = [
        ("warm_up", 5, 0, 10),      # 預熱：5成功，0失敗，10個工作者
        ("load_test", 50, 2, 15),   # 負載測試：50成功，2失敗，15個工作者
        ("stress_test", 100, 8, 20), # 壓力測試：100成功，8失敗，20個工作者
        ("peak_load", 80, 15, 25),  # 峰值負載：80成功，15失敗，25個工作者
        ("cool_down", 20, 1, 10)    # 冷卻：20成功，1失敗，10個工作者
    ]
    
    start_time = time.time()
    
    for phase, successful, failed, workers in test_phases:
        # 模擬響應時間
        response_times = [10 + i * 2 + (failed * 5) for i in range(successful + failed)]
        
        # 模擬錯誤類型
        error_types = {
            "connection_timeout": failed // 2,
            "database_lock": failed - (failed // 2)
        } if failed > 0 else {}
        
        monitor.record_operation_batch(
            successful_ops=successful,
            failed_ops=failed,
            response_times=response_times,
            concurrent_workers=workers,
            error_details=error_types,
            phase=phase
        )
        
        print(f"📊 {phase}: {successful}/{successful + failed} 成功")
        
        # 短暫延遲模擬測試時間
        await asyncio.sleep(0.1)
    
    test_duration = time.time() - start_time
    
    # 生成報告
    test_config = {
        "test_type": "concurrency_demo",
        "phases": len(test_phases),
        "max_workers": 25
    }
    
    report = reporter.generate_comprehensive_report(monitor, test_config, test_duration)
    
    print("📋 測試報告摘要：")
    print(f"  總操作數：{report['executive_summary']['total_operations']}")
    print(f"  成功率：{report['executive_summary']['overall_success_rate_percent']:.2f}%")
    print(f"  T2合規：{'✅' if report['t2_compliance']['overall_t2_compliant'] else '❌'}")
    print(f"  建議數：{len(report['recommendations'])}")
    
    return report


if __name__ == "__main__":
    # 設定日誌
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 執行演示
    asyncio.run(demo_monitoring_system())