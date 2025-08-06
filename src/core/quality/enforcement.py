"""品質門檻執行模組

提供品質標準執行、策略配置和自動化控制功能。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from . import QualityCheckResult, QualityCheckStatus

__all__ = [
    "QualityGateEnforcer",
    "QualityGatePolicy",
    "QualityGateResult"
]


class QualityGatePolicy(Enum):
    """品質門檻策略"""
    STRICT = "strict"           # 嚴格模式：零錯誤 + 95% 覆蓋率
    STANDARD = "standard"       # 標準模式：<=5 錯誤 + 90% 覆蓋率
    RELAXED = "relaxed"         # 寬鬆模式：<=10 錯誤 + 80% 覆蓋率
    DEVELOPMENT = "development" # 開發模式：<=20 錯誤 + 70% 覆蓋率


@dataclass
class QualityGateResult:
    """品質門檻檢查結果"""
    passed: bool
    policy: QualityGatePolicy
    violations: list[str]
    recommendations: list[str]
    score: float
    details: dict[str, Any]


class QualityGateEnforcer:
    """品質門檻執行器
    
    根據不同策略執行品質標準檢查。
    """

    def __init__(self, default_policy: QualityGatePolicy = QualityGatePolicy.STANDARD) -> None:
        """初始化品質門檻執行器
        
        Args:
            default_policy: 預設策略
        """
        self.default_policy = default_policy
        self._gate_configs: dict[QualityGatePolicy, dict[str, Any]] = {
            QualityGatePolicy.STRICT: {
                "max_errors": 0,
                "min_coverage": 95.0,
                "allow_warnings": False,
                "score_weight": {"errors": 0.6, "coverage": 0.3, "warnings": 0.1}
            },
            QualityGatePolicy.STANDARD: {
                "max_errors": 5,
                "min_coverage": 90.0,
                "allow_warnings": True,
                "score_weight": {"errors": 0.5, "coverage": 0.4, "warnings": 0.1}
            },
            QualityGatePolicy.RELAXED: {
                "max_errors": 10,
                "min_coverage": 80.0,
                "allow_warnings": True,
                "score_weight": {"errors": 0.4, "coverage": 0.5, "warnings": 0.1}
            },
            QualityGatePolicy.DEVELOPMENT: {
                "max_errors": 20,
                "min_coverage": 70.0,
                "allow_warnings": True,
                "score_weight": {"errors": 0.3, "coverage": 0.6, "warnings": 0.1}
            }
        }

    def evaluate_quality_gate(
        self,
        results: QualityCheckResult,
        policy: QualityGatePolicy | None = None
    ) -> QualityGateResult:
        """評估品質門檻
        
        Args:
            results: 品質檢查結果
            policy: 使用的策略（可選）
            
        Returns:
            品質門檻檢查結果
        """
        policy = policy or self.default_policy
        config = self._gate_configs[policy]

        violations = []
        recommendations = []

        # 檢查錯誤數量
        if results.error_count > config["max_errors"]:
            violations.append(
                f"錯誤數量 ({results.error_count}) 超過限制 ({config['max_errors']})"
            )
            if results.error_count > config["max_errors"] * 2:
                recommendations.append("建議逐一修復型別錯誤，從最嚴重的開始")
            else:
                recommendations.append("接近錯誤限制，建議優先修復型別安全問題")

        # 檢查型別覆蓋率
        if results.type_coverage < config["min_coverage"]:
            violations.append(
                f"型別覆蓋率 ({results.type_coverage:.1f}%) 低於要求 ({config['min_coverage']}%)"
            )
            coverage_gap = config["min_coverage"] - results.type_coverage
            if coverage_gap > 10:
                recommendations.append("建議為核心函數添加型別註解以快速提升覆蓋率")
            else:
                recommendations.append("接近覆蓋率目標，建議補充剩餘函數的型別註解")

        # 檢查警告（如果策略不允許）
        if not config["allow_warnings"] and results.warning_count > 0:
            violations.append(f"包含 {results.warning_count} 個警告，嚴格模式不允許警告")

        # 檢查執行狀態
        if results.status == QualityCheckStatus.FAILED:
            violations.append("品質檢查執行失敗，請檢查配置和環境")
            recommendations.append("檢查 mypy 和 ruff 工具是否正確安裝和配置")

        # 計算品質分數
        score = self._calculate_quality_score(results, config)

        # 確定是否通過
        passed = len(violations) == 0

        return QualityGateResult(
            passed=passed,
            policy=policy,
            violations=violations,
            recommendations=recommendations,
            score=score,
            details={
                "config_used": config,
                "metrics": {
                    "error_count": results.error_count,
                    "type_coverage": results.type_coverage,
                    "warning_count": results.warning_count,
                    "status": results.status.value
                }
            }
        )
    def _calculate_quality_score(
        self,
        results: QualityCheckResult,
        config: dict[str, Any]
    ) -> float:
        """計算品質分數
        
        Args:
            results: 品質檢查結果
            config: 策略配置
            
        Returns:
            品質分數 (0-100)
        """
        weights = config["score_weight"]

        # 錯誤分數 (錯誤越少分數越高)
        max_errors = config["max_errors"] or 1  # 避免除零
        error_score = max(0, 100 - (results.error_count / max_errors) * 100)
        if results.error_count == 0:
            error_score = 100

        # 覆蓋率分數
        coverage_score = min(100, results.type_coverage)

        # 警告分數
        warning_score = max(0, 100 - results.warning_count * 5)

        # 加權計算總分
        total_score = (
            error_score * weights["errors"] +
            coverage_score * weights["coverage"] +
            warning_score * weights["warnings"]
        )

        return float(round(total_score, 2))

    def get_policy_recommendations(
        self,
        results: QualityCheckResult
    ) -> list[str]:
        """根據結果獲取策略建議
        
        Args:
            results: 品質檢查結果
            
        Returns:
            策略建議清單
        """
        recommendations = []

        # 基於錯誤數量的建議
        if results.error_count == 0:
            recommendations.append("優秀！可以考慮使用 STRICT 策略維持高品質標準")
        elif results.error_count <= 5:
            recommendations.append("品質良好，建議使用 STANDARD 策略")
        elif results.error_count <= 10:
            recommendations.append("需要改進，建議暫時使用 RELAXED 策略並逐步修復")
        else:
            recommendations.append("品質需要大幅改善，建議使用 DEVELOPMENT 策略並制定改進計劃")

        # 基於覆蓋率的建議
        if results.type_coverage >= 95:
            recommendations.append("型別覆蓋率優秀，已達到生產環境標準")
        elif results.type_coverage >= 80:
            recommendations.append("型別覆蓋率良好，建議繼續提升至 95% 以上")
        else:
            recommendations.append("型別覆蓋率過低，建議優先為核心功能添加型別註解")

        return recommendations

    def create_improvement_plan(
        self,
        results: QualityCheckResult,
        target_policy: QualityGatePolicy
    ) -> dict[str, Any]:
        """建立品質改善計劃
        
        Args:
            results: 當前品質檢查結果
            target_policy: 目標策略
            
        Returns:
            改善計劃
        """
        target_config = self._gate_configs[target_policy]
        current_gate = self.evaluate_quality_gate(results)

        plan: dict[str, Any] = {
            "current_status": {
                "policy": current_gate.policy.value,
                "score": current_gate.score,
                "passed": current_gate.passed
            },
            "target_status": {
                "policy": target_policy.value,
                "requirements": target_config
            },
            "improvement_tasks": [],
            "estimated_effort": "medium",
            "priority_order": []
        }

        # 錯誤改善任務
        if results.error_count > target_config["max_errors"]:
            error_gap = results.error_count - target_config["max_errors"]
            plan["improvement_tasks"].append({
                "task": "修復型別錯誤",
                "current": results.error_count,
                "target": target_config["max_errors"],
                "gap": error_gap,
                "priority": "high" if error_gap > 10 else "medium"
            })
            plan["priority_order"].append("型別錯誤修復")

        # 覆蓋率改善任務
        if results.type_coverage < target_config["min_coverage"]:
            coverage_gap = target_config["min_coverage"] - results.type_coverage
            plan["improvement_tasks"].append({
                "task": "提升型別覆蓋率",
                "current": f"{results.type_coverage:.1f}%",
                "target": f"{target_config['min_coverage']}%",
                "gap": f"{coverage_gap:.1f}%",
                "priority": "high" if coverage_gap > 15 else "medium"
            })
            plan["priority_order"].append("型別註解添加")

        # 估算工作量
        total_effort_score = 0
        for task in plan["improvement_tasks"]:
            if task["priority"] == "high":
                total_effort_score += 3
            elif task["priority"] == "medium":
                total_effort_score += 2
            else:
                total_effort_score += 1

        if total_effort_score <= 3:
            plan["estimated_effort"] = "low"
        elif total_effort_score <= 6:
            plan["estimated_effort"] = "medium"
        else:
            plan["estimated_effort"] = "high"

        return plan
