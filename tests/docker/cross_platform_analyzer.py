"""
跨平台效能差異分析器和報告生成器
Task ID: T1 - Docker 測試框架建立 (效能差異分析專門化)

Ethan 效能專家的跨平台效能分析策略：
- 平台間效能基準比較
- 效能瓶頸識別和分析
- 資源使用差異分析
- 效能優化建議生成
"""

import statistics
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class PlatformType(Enum):
    """平台類型"""
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "darwin"
    UNKNOWN = "unknown"


class PerformanceMetricType(Enum):
    """效能指標類型"""
    EXECUTION_TIME = "execution_time_seconds"
    MEMORY_USAGE = "memory_usage_mb"
    CPU_USAGE = "cpu_usage_percent"
    SUCCESS_RATE = "success_rate_percent"
    CONTAINER_STARTUP_TIME = "container_startup_seconds"
    CLEANUP_TIME = "cleanup_seconds"


@dataclass
class PlatformPerformanceData:
    """平台效能數據"""
    platform: str
    test_results: List[Dict[str, Any]]
    resource_metrics: List[Dict[str, Any]] = field(default_factory=list)
    system_info: Dict[str, Any] = field(default_factory=dict)
    
    def calculate_statistics(self, metric_type: PerformanceMetricType) -> Dict[str, float]:
        """計算指標統計"""
        values = []
        
        for result in self.test_results:
            if metric_type.value in result:
                values.append(result[metric_type.value])
        
        if not values:
            return {"count": 0, "mean": 0, "median": 0, "min": 0, "max": 0, "std_dev": 0}
        
        return {
            "count": len(values),
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "min": min(values),
            "max": max(values),
            "std_dev": statistics.stdev(values) if len(values) > 1 else 0
        }


class CrossPlatformPerformanceAnalyzer:
    """跨平台效能分析器
    
    提供深度的跨平台效能分析功能：
    - 效能基準比較
    - 瓶頸識別
    - 差異原因分析
    - 優化建議生成
    """
    
    def __init__(self):
        self.platform_data: Dict[str, PlatformPerformanceData] = {}
        self.baseline_platform: Optional[str] = None
        self.analysis_results: Dict[str, Any] = {}
    
    def add_platform_data(
        self, 
        platform: str, 
        test_results: List[Dict[str, Any]],
        resource_metrics: List[Dict[str, Any]] = None,
        system_info: Dict[str, Any] = None
    ) -> None:
        """添加平台效能數據"""
        self.platform_data[platform] = PlatformPerformanceData(
            platform=platform,
            test_results=test_results,
            resource_metrics=resource_metrics or [],
            system_info=system_info or {}
        )
        
        # 如果是第一個平台或是 Linux，設為基準平台
        if not self.baseline_platform or platform == "linux":
            self.baseline_platform = platform
        
        logger.info(f"已添加 {platform} 平台數據，測試結果數量: {len(test_results)}")
    
    def analyze_cross_platform_performance(self) -> Dict[str, Any]:
        """執行跨平台效能分析"""
        if len(self.platform_data) < 2:
            logger.warning("需要至少兩個平台的數據才能進行比較分析")
            return {"error": "需要至少兩個平台的數據"}
        
        logger.info(f"開始跨平台效能分析，平台數量: {len(self.platform_data)}")
        
        # 基礎統計分析
        platform_statistics = self._calculate_platform_statistics()
        
        # 效能基準比較
        performance_comparison = self._compare_platform_performance()
        
        # 效能差異分析
        performance_gaps = self._analyze_performance_gaps()
        
        # 資源使用分析
        resource_analysis = self._analyze_resource_usage_patterns()
        
        # 瓶頸識別
        bottleneck_analysis = self._identify_performance_bottlenecks()
        
        # 生成優化建議
        optimization_recommendations = self._generate_platform_optimization_recommendations()
        
        # 效能等級評估
        performance_ratings = self._calculate_platform_performance_ratings()
        
        self.analysis_results = {
            "analysis_metadata": {
                "analyzed_at": datetime.now().isoformat(),
                "platforms_analyzed": list(self.platform_data.keys()),
                "baseline_platform": self.baseline_platform,
                "total_test_results": sum(len(data.test_results) for data in self.platform_data.values())
            },
            "platform_statistics": platform_statistics,
            "performance_comparison": performance_comparison,
            "performance_gaps": performance_gaps,
            "resource_analysis": resource_analysis,
            "bottleneck_analysis": bottleneck_analysis,
            "optimization_recommendations": optimization_recommendations,
            "performance_ratings": performance_ratings,
            "summary": self._generate_analysis_summary()
        }
        
        logger.info("跨平台效能分析完成")
        return self.analysis_results
    
    def _calculate_platform_statistics(self) -> Dict[str, Dict[str, Any]]:
        """計算各平台統計數據"""
        statistics_data = {}
        
        for platform, data in self.platform_data.items():
            platform_stats = {}
            
            # 計算各項指標的統計
            for metric_type in PerformanceMetricType:
                platform_stats[metric_type.value] = data.calculate_statistics(metric_type)
            
            # 額外的統計信息
            platform_stats["test_count"] = len(data.test_results)
            platform_stats["success_count"] = sum(1 for r in data.test_results if r.get("success", False))
            platform_stats["failure_count"] = sum(1 for r in data.test_results if not r.get("success", True))
            
            statistics_data[platform] = platform_stats
        
        return statistics_data
    
    def _compare_platform_performance(self) -> Dict[str, Any]:
        """比較平台效能"""
        if not self.baseline_platform:
            return {"error": "未設定基準平台"}
        
        baseline_data = self.platform_data[self.baseline_platform]
        comparisons = {}
        
        for platform, data in self.platform_data.items():
            if platform == self.baseline_platform:
                continue
            
            platform_comparison = {}
            
            for metric_type in PerformanceMetricType:
                baseline_stats = baseline_data.calculate_statistics(metric_type)
                platform_stats = data.calculate_statistics(metric_type)
                
                if baseline_stats["mean"] > 0:
                    # 計算相對差異百分比
                    relative_diff = ((platform_stats["mean"] - baseline_stats["mean"]) / baseline_stats["mean"]) * 100
                    
                    platform_comparison[metric_type.value] = {
                        "baseline_mean": baseline_stats["mean"],
                        "platform_mean": platform_stats["mean"],
                        "relative_difference_percent": relative_diff,
                        "performance_impact": self._classify_performance_impact(metric_type, relative_diff)
                    }
            
            comparisons[platform] = platform_comparison
        
        return {
            "baseline_platform": self.baseline_platform,
            "comparisons": comparisons
        }
    
    def _analyze_performance_gaps(self) -> Dict[str, Any]:
        """分析效能差距"""
        gaps_analysis = {}
        
        # 找出效能差距最大的指標
        for metric_type in PerformanceMetricType:
            metric_values = {}
            
            for platform, data in self.platform_data.items():
                stats = data.calculate_statistics(metric_type)
                metric_values[platform] = stats["mean"]
            
            if len(metric_values) > 1:
                best_platform = min(metric_values, key=metric_values.get) if metric_type in [
                    PerformanceMetricType.EXECUTION_TIME,
                    PerformanceMetricType.MEMORY_USAGE,
                    PerformanceMetricType.CPU_USAGE
                ] else max(metric_values, key=metric_values.get)
                
                worst_platform = max(metric_values, key=metric_values.get) if metric_type in [
                    PerformanceMetricType.EXECUTION_TIME,
                    PerformanceMetricType.MEMORY_USAGE,
                    PerformanceMetricType.CPU_USAGE
                ] else min(metric_values, key=metric_values.get)
                
                best_value = metric_values[best_platform]
                worst_value = metric_values[worst_platform]
                
                gap_percentage = ((worst_value - best_value) / best_value) * 100 if best_value > 0 else 0
                
                gaps_analysis[metric_type.value] = {
                    "best_platform": best_platform,
                    "best_value": best_value,
                    "worst_platform": worst_platform,
                    "worst_value": worst_value,
                    "gap_percentage": gap_percentage,
                    "severity": self._classify_gap_severity(gap_percentage)
                }
        
        return gaps_analysis
    
    def _analyze_resource_usage_patterns(self) -> Dict[str, Any]:
        """分析資源使用模式"""
        resource_patterns = {}
        
        for platform, data in self.platform_data.items():
            if not data.resource_metrics:
                continue
            
            memory_usage = []
            cpu_usage = []
            
            for metric in data.resource_metrics:
                if "memory_usage_mb" in metric:
                    memory_usage.append(metric["memory_usage_mb"])
                if "cpu_usage_percent" in metric:
                    cpu_usage.append(metric["cpu_usage_percent"])
            
            platform_patterns = {}
            
            if memory_usage:
                platform_patterns["memory"] = {
                    "average_mb": statistics.mean(memory_usage),
                    "peak_mb": max(memory_usage),
                    "variance": statistics.variance(memory_usage) if len(memory_usage) > 1 else 0
                }
            
            if cpu_usage:
                platform_patterns["cpu"] = {
                    "average_percent": statistics.mean(cpu_usage),
                    "peak_percent": max(cpu_usage),
                    "variance": statistics.variance(cpu_usage) if len(cpu_usage) > 1 else 0
                }
            
            resource_patterns[platform] = platform_patterns
        
        return resource_patterns
    
    def _identify_performance_bottlenecks(self) -> Dict[str, List[str]]:
        """識別效能瓶頸"""
        bottlenecks = {}
        
        for platform, data in self.platform_data.items():
            platform_bottlenecks = []
            
            # 分析執行時間瓶頸
            exec_time_stats = data.calculate_statistics(PerformanceMetricType.EXECUTION_TIME)
            if exec_time_stats["mean"] > 120:  # 超過 2 分鐘
                platform_bottlenecks.append(f"執行時間過長 (平均 {exec_time_stats['mean']:.1f}s)")
            
            # 分析記憶體瓶頸
            memory_stats = data.calculate_statistics(PerformanceMetricType.MEMORY_USAGE)
            if memory_stats["mean"] > 1024:  # 超過 1GB
                platform_bottlenecks.append(f"記憶體使用過高 (平均 {memory_stats['mean']:.1f}MB)")
            
            # 分析 CPU 瓶頸
            cpu_stats = data.calculate_statistics(PerformanceMetricType.CPU_USAGE)
            if cpu_stats["mean"] > 80:  # 超過 80%
                platform_bottlenecks.append(f"CPU 使用率過高 (平均 {cpu_stats['mean']:.1f}%)")
            
            # 分析成功率瓶頸
            success_rate = (sum(1 for r in data.test_results if r.get("success", False)) / len(data.test_results)) * 100 if data.test_results else 0
            if success_rate < 95:
                platform_bottlenecks.append(f"測試成功率偏低 ({success_rate:.1f}%)")
            
            # 分析變異性瓶頸
            if exec_time_stats["std_dev"] > 30:  # 標準差超過 30 秒
                platform_bottlenecks.append(f"執行時間不穩定 (標準差 {exec_time_stats['std_dev']:.1f}s)")
            
            bottlenecks[platform] = platform_bottlenecks
        
        return bottlenecks
    
    def _generate_platform_optimization_recommendations(self) -> Dict[str, List[str]]:
        """生成平台優化建議"""
        recommendations = {}
        
        for platform, data in self.platform_data.items():
            platform_recommendations = []
            
            # 基於統計數據生成建議
            exec_time_stats = data.calculate_statistics(PerformanceMetricType.EXECUTION_TIME)
            memory_stats = data.calculate_statistics(PerformanceMetricType.MEMORY_USAGE)
            
            # 執行時間優化建議
            if exec_time_stats["mean"] > 90:
                platform_recommendations.append("優化容器啟動時間，考慮使用更輕量的基礎鏡像")
            
            if exec_time_stats["std_dev"] > 20:
                platform_recommendations.append("提高執行穩定性，檢查平台特定的資源爭用問題")
            
            # 記憶體優化建議
            if memory_stats["mean"] > 800:
                platform_recommendations.append("優化記憶體使用，啟用記憶體高效模式")
            
            # 平台特定建議
            if platform == "windows":
                platform_recommendations.extend([
                    "考慮調整 Windows 容器的資源限制",
                    "優化 Windows 平台的容器清理流程"
                ])
            elif platform == "darwin":
                platform_recommendations.extend([
                    "考慮 Docker Desktop for Mac 的特定優化",
                    "監控 macOS 的檔案系統效能"
                ])
            elif platform == "linux":
                platform_recommendations.extend([
                    "利用 Linux 容器的原生效能優勢",
                    "考慮啟用更高的並行度"
                ])
            
            # 成功率改善建議
            success_rate = (sum(1 for r in data.test_results if r.get("success", False)) / len(data.test_results)) * 100 if data.test_results else 0
            if success_rate < 95:
                platform_recommendations.append(f"調查測試失敗原因，目前成功率僅 {success_rate:.1f}%")
            
            recommendations[platform] = platform_recommendations or ["效能表現良好，無需額外優化"]
        
        return recommendations
    
    def _calculate_platform_performance_ratings(self) -> Dict[str, Dict[str, Any]]:
        """計算平台效能評級"""
        ratings = {}
        
        for platform, data in self.platform_data.items():
            # 各項指標評分（1-10 分）
            scores = {}
            
            # 執行時間評分（越短越好）
            exec_time = data.calculate_statistics(PerformanceMetricType.EXECUTION_TIME)["mean"]
            scores["execution_time"] = max(1, 10 - (exec_time / 12))  # 120s = 1分, 0s = 10分
            
            # 記憶體使用評分（越少越好）
            memory = data.calculate_statistics(PerformanceMetricType.MEMORY_USAGE)["mean"]
            scores["memory_efficiency"] = max(1, 10 - (memory / 200))  # 2000MB = 1分, 0MB = 10分
            
            # CPU 使用評分（越少越好）
            cpu = data.calculate_statistics(PerformanceMetricType.CPU_USAGE)["mean"]
            scores["cpu_efficiency"] = max(1, 10 - (cpu / 10))  # 100% = 1分, 0% = 10分
            
            # 成功率評分
            success_rate = (sum(1 for r in data.test_results if r.get("success", False)) / len(data.test_results)) * 100 if data.test_results else 0
            scores["reliability"] = success_rate / 10  # 100% = 10分, 0% = 0分
            
            # 穩定性評分（標準差越小越好）
            stability_score = max(1, 10 - (exec_time / 30))  # 300s標準差 = 1分
            scores["stability"] = stability_score
            
            # 計算總分（加權平均）
            weights = {
                "execution_time": 0.3,
                "memory_efficiency": 0.2,
                "cpu_efficiency": 0.2,
                "reliability": 0.2,
                "stability": 0.1
            }
            
            overall_score = sum(scores[metric] * weight for metric, weight in weights.items())
            
            ratings[platform] = {
                "individual_scores": scores,
                "overall_score": round(overall_score, 2),
                "grade": self._score_to_grade(overall_score),
                "ranking_factors": {
                    "strengths": self._identify_platform_strengths(scores),
                    "weaknesses": self._identify_platform_weaknesses(scores)
                }
            }
        
        return ratings
    
    def _classify_performance_impact(self, metric_type: PerformanceMetricType, relative_diff: float) -> str:
        """分類效能影響"""
        abs_diff = abs(relative_diff)
        
        if abs_diff <= 5:
            return "negligible"  # 可忽略
        elif abs_diff <= 15:
            return "minor"       # 輕微
        elif abs_diff <= 30:
            return "moderate"    # 中等
        elif abs_diff <= 50:
            return "significant" # 顯著
        else:
            return "critical"    # 嚴重
    
    def _classify_gap_severity(self, gap_percentage: float) -> str:
        """分類差距嚴重程度"""
        if gap_percentage <= 10:
            return "low"
        elif gap_percentage <= 25:
            return "medium"
        elif gap_percentage <= 50:
            return "high"
        else:
            return "critical"
    
    def _score_to_grade(self, score: float) -> str:
        """分數轉等級"""
        if score >= 9:
            return "A+"
        elif score >= 8:
            return "A"
        elif score >= 7:
            return "B+"
        elif score >= 6:
            return "B"
        elif score >= 5:
            return "C+"
        elif score >= 4:
            return "C"
        else:
            return "D"
    
    def _identify_platform_strengths(self, scores: Dict[str, float]) -> List[str]:
        """識別平台優勢"""
        strengths = []
        for metric, score in scores.items():
            if score >= 8:
                strengths.append(metric.replace("_", " ").title())
        return strengths or ["無明顯優勢"]
    
    def _identify_platform_weaknesses(self, scores: Dict[str, float]) -> List[str]:
        """識別平台弱點"""
        weaknesses = []
        for metric, score in scores.items():
            if score <= 4:
                weaknesses.append(metric.replace("_", " ").title())
        return weaknesses or ["無明顯弱點"]
    
    def _generate_analysis_summary(self) -> Dict[str, Any]:
        """生成分析摘要"""
        if not self.analysis_results:
            return {}
        
        platforms = list(self.platform_data.keys())
        
        # 找出最佳和最差平台
        ratings = self.analysis_results.get("performance_ratings", {})
        if ratings:
            best_platform = max(ratings, key=lambda p: ratings[p]["overall_score"])
            worst_platform = min(ratings, key=lambda p: ratings[p]["overall_score"])
            
            best_score = ratings[best_platform]["overall_score"]
            worst_score = ratings[worst_platform]["overall_score"]
        else:
            best_platform = worst_platform = platforms[0] if platforms else "unknown"
            best_score = worst_score = 0
        
        # 識別主要效能問題
        bottlenecks = self.analysis_results.get("bottleneck_analysis", {})
        critical_issues = []
        for platform, issues in bottlenecks.items():
            if issues:
                critical_issues.extend([f"{platform}: {issue}" for issue in issues])
        
        return {
            "platforms_analyzed": len(platforms),
            "best_performing_platform": {
                "name": best_platform,
                "score": best_score,
                "grade": ratings.get(best_platform, {}).get("grade", "N/A")
            },
            "worst_performing_platform": {
                "name": worst_platform,
                "score": worst_score,
                "grade": ratings.get(worst_platform, {}).get("grade", "N/A")
            },
            "performance_spread": best_score - worst_score,
            "critical_issues_count": len(critical_issues),
            "critical_issues": critical_issues[:5],  # 顯示前 5 個關鍵問題
            "overall_assessment": self._generate_overall_assessment(best_score, worst_score, critical_issues)
        }
    
    def _generate_overall_assessment(self, best_score: float, worst_score: float, critical_issues: List[str]) -> str:
        """生成總體評估"""
        if best_score >= 8 and worst_score >= 6:
            return "所有平台效能表現優秀，跨平台相容性良好"
        elif best_score >= 7 and worst_score >= 5:
            return "平台效能表現良好，存在一些可優化的地方"
        elif best_score >= 6 and worst_score >= 4:
            return "平台效能表現中等，需要針對性優化"
        elif len(critical_issues) > 0:
            return "存在嚴重的跨平台效能問題，需要立即處理"
        else:
            return "跨平台效能表現不佳，建議全面檢視和優化"
    
    def generate_performance_report(self, format_type: str = "detailed") -> str:
        """生成效能分析報告"""
        if not self.analysis_results:
            self.analyze_cross_platform_performance()
        
        if format_type == "json":
            return json.dumps(self.analysis_results, indent=2, ensure_ascii=False)
        elif format_type == "summary":
            return self._generate_summary_report()
        else:
            return self._generate_detailed_report()
    
    def _generate_summary_report(self) -> str:
        """生成摘要報告"""
        summary = self.analysis_results.get("summary", {})
        
        report = f"""
跨平台效能分析摘要報告
==========================================

分析概況：
- 分析平台數量: {summary.get('platforms_analyzed', 0)}
- 最佳效能平台: {summary.get('best_performing_platform', {}).get('name', 'N/A')} (得分: {summary.get('best_performing_platform', {}).get('score', 0):.1f})
- 效能差距: {summary.get('performance_spread', 0):.1f} 分

關鍵問題數量: {summary.get('critical_issues_count', 0)}

總體評估: {summary.get('overall_assessment', 'N/A')}
"""
        return report.strip()
    
    def _generate_detailed_report(self) -> str:
        """生成詳細報告"""
        # 這裡可以生成更詳細的 Markdown 格式報告
        # 為簡潔起見，返回 JSON 格式
        return json.dumps(self.analysis_results, indent=2, ensure_ascii=False)


# === 輔助函數 ===

def create_cross_platform_analyzer_from_test_results(
    test_results_by_platform: Dict[str, List[Dict[str, Any]]]
) -> CrossPlatformPerformanceAnalyzer:
    """從測試結果創建跨平台分析器"""
    analyzer = CrossPlatformPerformanceAnalyzer()
    
    for platform, results in test_results_by_platform.items():
        analyzer.add_platform_data(platform, results)
    
    return analyzer