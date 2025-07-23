"""
AI Agent 測試結果檢查器
負責檢查現有測試結果和提供查詢接口
"""

import os
import re
from typing import Dict, List, Any


class AITestResultChecker:
    """AI Agent 測試結果檢查器"""
    
    def __init__(self, memory_bank_path: str = "memory_bank"):
        self.memory_bank_path = memory_bank_path
        self.result_file_path = f"{memory_bank_path}/result.md"
        from .ai_test_result_archiver import AITestResultArchiver
        self.archiver = AITestResultArchiver(memory_bank_path)
    
    def check_existing_test_result(self) -> dict:
        """AI Agent 檢查現有的測試結果"""
        latest_result = self.archiver.get_latest_test_result()
        
        if latest_result["exists"]:
            print(f"📋 AI Agent 發現現有測試結果: {latest_result['file_path']}")
            print("🔄 AI Agent 將在下次測試時覆蓋此結果")
            return {
                "exists": True,
                "file_path": latest_result["file_path"],
                "will_be_overwritten": True
            }
        else:
            print("📝 AI Agent 未發現現有測試結果，將創建新的結果文檔")
            return {
                "exists": False,
                "file_path": self.result_file_path,
                "will_be_overwritten": False
            }
    
    def get_test_result_summary(self) -> dict:
        """AI Agent 獲取測試結果摘要"""
        latest_result = self.archiver.get_latest_test_result()
        
        if not latest_result["exists"]:
            return {
                "has_result": False,
                "message": "暫無測試結果"
            }
        
        # 解析現有結果內容
        content = latest_result["content"]
        
        # 提取關鍵信息
        summary = {
            "has_result": True,
            "file_path": latest_result["file_path"],
            "last_updated": self._extract_timestamp(content),
            "overall_status": self._extract_overall_status(content),
            "coverage_percentage": self._extract_coverage_percentage(content),
            "acceptance_pass_rate": self._extract_acceptance_pass_rate(content)
        }
        
        return summary
    
    def _extract_timestamp(self, content: str) -> str:
        """AI Agent 提取時間戳"""
        timestamp_pattern = r"執行時間: (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"
        match = re.search(timestamp_pattern, content)
        return match.group(1) if match else "未知"
    
    def _extract_overall_status(self, content: str) -> str:
        """AI Agent 提取整體狀態"""
        status_pattern = r"整體狀態: (\w+)"
        match = re.search(status_pattern, content)
        return match.group(1) if match else "未知"
    
    def _extract_coverage_percentage(self, content: str) -> float:
        """AI Agent 提取覆蓋率"""
        coverage_pattern = r"測試覆蓋率: ([\d.]+)%"
        match = re.search(coverage_pattern, content)
        return float(match.group(1)) if match else 0.0
    
    def _extract_acceptance_pass_rate(self, content: str) -> float:
        """AI Agent 提取驗收通過率"""
        rate_pattern = r"驗收通過率: ([\d.]+)%"
        match = re.search(rate_pattern, content)
        return float(match.group(1)) if match else 0.0


class AITestResultQuery:
    """AI Agent 測試結果查詢接口"""
    
    def __init__(self, memory_bank_path: str = "memory_bank"):
        self.memory_bank_path = memory_bank_path
        self.result_checker = AITestResultChecker(memory_bank_path)
        from .ai_test_result_archiver import AITestResultArchiver
        self.archiver = AITestResultArchiver(memory_bank_path)
    
    def get_latest_test_result(self) -> dict:
        """AI Agent 獲取最新測試結果"""
        return self.result_checker.get_test_result_summary()
    
    def get_test_history(self) -> List[dict]:
        """AI Agent 獲取測試歷史"""
        return self.archiver.get_test_history()
    
    def get_test_trends(self) -> dict:
        """AI Agent 分析測試趨勢"""
        history = self.get_test_history()
        
        if len(history) < 2:
            return {"message": "測試歷史不足，無法分析趨勢"}
        
        # 分析覆蓋率趨勢
        coverage_trend = self._analyze_coverage_trend(history)
        
        # 分析驗收率趨勢
        acceptance_trend = self._analyze_acceptance_trend(history)
        
        # 分析質量分數趨勢
        quality_trend = self._analyze_quality_trend(history)
        
        return {
            "coverage_trend": coverage_trend,
            "acceptance_trend": acceptance_trend,
            "quality_trend": quality_trend,
            "overall_trend": self._calculate_overall_trend(coverage_trend, acceptance_trend, quality_trend)
        }
    
    def _analyze_coverage_trend(self, history: List[dict]) -> str:
        """AI Agent 分析覆蓋率趨勢"""
        if len(history) < 2:
            return "stable"
        
        recent_coverage = history[-1]["coverage_percentage"]
        previous_coverage = history[-2]["coverage_percentage"]
        
        if recent_coverage > previous_coverage:
            return "improving"
        elif recent_coverage < previous_coverage:
            return "declining"
        else:
            return "stable"
    
    def _analyze_acceptance_trend(self, history: List[dict]) -> str:
        """AI Agent 分析驗收率趨勢"""
        if len(history) < 2:
            return "stable"
        
        recent_acceptance = history[-1]["acceptance_pass_rate"]
        previous_acceptance = history[-2]["acceptance_pass_rate"]
        
        if recent_acceptance > previous_acceptance:
            return "improving"
        elif recent_acceptance < previous_acceptance:
            return "declining"
        else:
            return "stable"
    
    def _analyze_quality_trend(self, history: List[dict]) -> str:
        """AI Agent 分析質量分數趨勢"""
        if len(history) < 2:
            return "stable"
        
        recent_quality = history[-1]["quality_score"]
        previous_quality = history[-2]["quality_score"]
        
        if recent_quality > previous_quality:
            return "improving"
        elif recent_quality < previous_quality:
            return "declining"
        else:
            return "stable"
    
    def _calculate_overall_trend(self, coverage_trend: str, acceptance_trend: str, quality_trend: str) -> str:
        """AI Agent 計算整體趨勢"""
        improving_count = sum(1 for trend in [coverage_trend, acceptance_trend, quality_trend] if trend == "improving")
        declining_count = sum(1 for trend in [coverage_trend, acceptance_trend, quality_trend] if trend == "declining")
        
        if improving_count > declining_count:
            return "improving"
        elif declining_count > improving_count:
            return "declining"
        else:
            return "stable"