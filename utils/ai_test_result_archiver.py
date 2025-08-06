"""
AI Agent 測試結果自動存檔器
負責將測試結果自動存檔到記憶庫中
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


class AITestResultArchiver:
    """AI Agent 測試結果自動存檔器"""

    def __init__(self, memory_bank_path: str = "memory_bank"):
        self.memory_bank_path = memory_bank_path
        self.result_file_path = f"{memory_bank_path}/result.md"
        self.test_history_path = f"{memory_bank_path}/test_history.json"

    def archive_test_results(self, comprehensive_report: dict[str, Any]) -> bool:
        """AI Agent 自動存檔測試結果"""
        try:
            print("💾 AI Agent 開始存檔測試結果...")

            # 1. 檢查並覆蓋舊的測試結果文檔
            self._check_and_remove_old_result()

            # 2. 生成新的測試結果報告
            result_content = self._generate_result_content(comprehensive_report)

            # 3. 存檔到記憶庫
            self._save_result_to_memory_bank(result_content)

            # 4. 更新測試歷史記錄
            self._update_test_history(comprehensive_report)

            print(f"✅ AI Agent 測試結果已存檔到: {self.result_file_path}")
            return True

        except Exception as e:
            print(f"❌ AI Agent 測試結果存檔失敗: {e}")
            return False

    def _check_and_remove_old_result(self):
        """檢查並移除舊的測試結果文檔"""
        if os.path.exists(self.result_file_path):
            print(f"📝 發現舊的測試結果文檔,正在覆蓋: {self.result_file_path}")
            Path(self.result_file_path).unlink()

    def _generate_result_content(self, comprehensive_report: dict[str, Any]) -> str:
        """AI Agent 生成測試結果內容"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 提取報告數據
        summary = comprehensive_report.get("summary", {})
        coverage_report = comprehensive_report.get("coverage_report", {})
        acceptance_report = comprehensive_report.get("acceptance_report", {})
        analysis = comprehensive_report.get("analysis", {})
        recommendations = comprehensive_report.get("recommendations", [])

        content = f"""# 🤖 AI Agent 測試結果報告

## 📊 測試執行摘要
- **執行時間**: {timestamp}
- **整體狀態**: {summary.get("overall_status", "unknown")}
- **測試覆蓋率**: {summary.get("coverage_percentage", 0):.1f}%
- **驗收通過率**: {summary.get("acceptance_pass_rate", 0):.1%}
- **總需求數**: {summary.get("total_requirements", 0)}

## 📈 詳細測試結果

### 覆蓋率分析
- **總需求數**: {coverage_report.get("total_requirements", 0)}
- **已覆蓋需求**: {coverage_report.get("covered_requirements", 0)}
- **未覆蓋需求**: {coverage_report.get("total_requirements", 0) - coverage_report.get("covered_requirements", 0)}
- **覆蓋率**: {coverage_report.get("coverage_percentage", 0):.1f}%

### 驗收測試結果
- **總需求數**: {acceptance_report.get("total_requirements", 0)}
- **通過需求**: {acceptance_report.get("passed_requirements", 0)}
- **失敗需求**: {acceptance_report.get("failed_requirements", 0)}
- **通過率**: {(acceptance_report.get("passed_requirements", 0) / max(acceptance_report.get("total_requirements", 1), 1)) * 100:.1f}%

## 🔍 關鍵發現
"""

        # 添加關鍵發現
        key_findings = summary.get("key_findings", [])
        for finding in key_findings:
            content += f"- {finding}\n"

        content += "\n## 💡 AI 建議\n"

        # 添加 AI 建議
        for rec in recommendations:
            priority_emoji = (
                "🔴"
                if rec.get("priority") == "high"
                else "🟡"
                if rec.get("priority") == "medium"
                else "🟢"
            )
            content += f"{priority_emoji} **{rec.get('category', 'UNKNOWN').upper()}** - {rec.get('priority', 'unknown').upper()}\n"
            content += f"   - {rec.get('message', '')}\n"
            content += f"   - 建議行動: {rec.get('action', '')}\n"
            content += f"   - 預計工作量: {rec.get('estimated_effort', '')}\n\n"

        content += "## 📋 下一步行動\n"

        # 添加下一步行動
        next_steps = summary.get("next_steps", [])
        for step in next_steps:
            content += f"- {step}\n"

        content += "\n## 📊 質量指標\n"

        # 添加質量指標
        quality_metrics = analysis.get("quality_metrics", {})
        content += f"- **整體質量分數**: {quality_metrics.get('overall_quality_score', 0):.2f}\n"
        content += (
            f"- **測試可靠性**: {quality_metrics.get('test_reliability', 0):.2f}\n"
        )
        content += f"- **需求完整性**: {quality_metrics.get('requirement_completeness', 0):.2f}\n"
        content += (
            f"- **實現質量**: {quality_metrics.get('implementation_quality', 0):.2f}\n"
        )

        content += "\n---\n"
        content += f"*此報告由 AI Agent 自動生成於 {timestamp}*"

        return content

    def _save_result_to_memory_bank(self, content: str):
        """AI Agent 保存結果到記憶庫"""
        # 確保記憶庫目錄存在
        os.makedirs(self.memory_bank_path, exist_ok=True)

        # 寫入測試結果文件
        with open(self.result_file_path, "w", encoding="utf-8") as f:
            f.write(content)

    def _update_test_history(self, comprehensive_report: dict[str, Any]):
        """AI Agent 更新測試歷史記錄"""
        summary = comprehensive_report.get("summary", {})
        acceptance_report = comprehensive_report.get("acceptance_report", {})
        analysis = comprehensive_report.get("analysis", {})

        history_data = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": summary.get("overall_status", "unknown"),
            "coverage_percentage": summary.get("coverage_percentage", 0),
            "acceptance_pass_rate": summary.get("acceptance_pass_rate", 0),
            "total_requirements": summary.get("total_requirements", 0),
            "passed_requirements": acceptance_report.get("passed_requirements", 0),
            "failed_requirements": acceptance_report.get("failed_requirements", 0),
            "quality_score": analysis.get("quality_metrics", {}).get(
                "overall_quality_score", 0
            ),
        }

        # 讀取現有歷史記錄
        existing_history = []
        if os.path.exists(self.test_history_path):
            try:
                with open(self.test_history_path, encoding="utf-8") as f:
                    existing_history = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                existing_history = []

        # 添加新的測試記錄
        existing_history.append(history_data)

        # 只保留最近 50 次測試記錄
        if len(existing_history) > 50:
            existing_history = existing_history[-50:]

        # 保存更新後的歷史記錄
        with open(self.test_history_path, "w", encoding="utf-8") as f:
            json.dump(existing_history, f, ensure_ascii=False, indent=2)

    def get_latest_test_result(self) -> dict:
        """AI Agent 獲取最新的測試結果"""
        if os.path.exists(self.result_file_path):
            with open(self.result_file_path, encoding="utf-8") as f:
                content = f.read()
                return {
                    "exists": True,
                    "content": content,
                    "file_path": self.result_file_path,
                }
        else:
            return {
                "exists": False,
                "content": None,
                "file_path": self.result_file_path,
            }

    def get_test_history(self) -> list[dict]:
        """AI Agent 獲取測試歷史"""
        if os.path.exists(self.test_history_path):
            with open(self.test_history_path, encoding="utf-8") as f:
                return json.load(f)
        else:
            return []
