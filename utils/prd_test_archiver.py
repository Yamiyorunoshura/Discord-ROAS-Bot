"""
PRD測試結果存檔工具
- 自動存檔PRD需求驗證測試結果
- 生成測試結果報告
- 更新測試記憶
- 追蹤測試進度
"""

import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

# 添加項目根目錄到Python路徑
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 導入PRD測試驗證器
try:
    from utils.prd_test_validator import (
        PRDRequirementStatus,
        PRDTestReport,
        PRDTestValidator,
    )
except ImportError:
    # 如果相對導入失敗,嘗試直接導入
    from prd_test_validator import PRDRequirementStatus, PRDTestReport, PRDTestValidator


@dataclass
class PRDTestArchive:
    """PRD測試存檔數據結構"""

    archive_id: str
    timestamp: datetime
    test_report: PRDTestReport
    archive_path: str
    summary: dict[str, Any]


class PRDTestArchiver:
    """PRD測試結果存檔器"""

    def __init__(self, archive_dir: str = "test_results"):
        self.archive_dir = archive_dir
        self.validator = PRDTestValidator()

        # 確保存檔目錄存在
        os.makedirs(archive_dir, exist_ok=True)

    async def archive_prd_test_results(self) -> PRDTestArchive:
        """存檔PRD測試結果"""
        print("📦 開始存檔 PRD 測試結果...")

        # 1. 執行PRD需求驗證測試
        test_report = await self.validator.run_prd_validation_tests()

        # 2. 生成存檔摘要
        archive_summary = self._generate_archive_summary(test_report)

        # 3. 保存測試報告到JSON文件
        archive_path = self._save_test_report_json(test_report)

        # 4. 生成存檔記錄
        archive = PRDTestArchive(
            archive_id=f"PRD_ARCHIVE_{int(time.time())}",
            timestamp=datetime.now(),
            test_report=test_report,
            archive_path=archive_path,
            summary=archive_summary,
        )

        # 5. 更新測試記憶
        await self._update_test_memory(archive)

        # 6. 生成存檔報告
        self._generate_archive_report(archive)

        return archive

    def _generate_archive_summary(self, test_report: PRDTestReport) -> dict[str, Any]:
        """生成存檔摘要"""
        return {
            "total_requirements": test_report.total_requirements,
            "implemented_requirements": test_report.implemented_requirements,
            "tested_requirements": test_report.tested_requirements,
            "verified_requirements": test_report.verified_requirements,
            "coverage_percentage": test_report.coverage_percentage,
            "pass_rate": test_report.pass_rate,
            "overall_status": test_report.overall_status,
            "timestamp": test_report.timestamp.isoformat(),
            "report_id": test_report.report_id,
        }

    def _save_test_report_json(self, test_report: PRDTestReport) -> str:
        """保存測試報告到JSON文件"""
        timestamp = test_report.timestamp.strftime("%Y%m%d_%H%M%S")
        filename = f"prd_test_report_{timestamp}.json"
        filepath = os.path.join(self.archive_dir, filename)

        # 轉換測試報告為可序列化的格式
        report_data = {
            "report_id": test_report.report_id,
            "timestamp": test_report.timestamp.isoformat(),
            "total_requirements": test_report.total_requirements,
            "implemented_requirements": test_report.implemented_requirements,
            "tested_requirements": test_report.tested_requirements,
            "verified_requirements": test_report.verified_requirements,
            "requirements": [
                {
                    "requirement_id": req.requirement_id,
                    "requirement_name": req.requirement_name,
                    "description": req.description,
                    "category": req.category,
                    "priority": req.priority,
                    "status": req.status.value,
                    "implementation_details": req.implementation_details,
                    "test_results": req.test_results,
                    "last_updated": req.last_updated,
                }
                for req in test_report.requirements
            ],
            "test_summary": test_report.test_summary,
            "coverage_percentage": test_report.coverage_percentage,
            "pass_rate": test_report.pass_rate,
            "overall_status": test_report.overall_status,
        }

        # 保存到JSON文件
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)

        print(f"✅ 測試報告已保存: {filepath}")
        return filepath

    async def _update_test_memory(self, archive: PRDTestArchive):
        """更新測試記憶"""
        print("🧠 更新測試記憶...")

        # 創建測試記憶文件
        memory_file = os.path.join("memory_bank", "prd_test_memory.md")
        os.makedirs("memory_bank", exist_ok=True)

        # 讀取現有記憶或創建新的
        if os.path.exists(memory_file):
            with open(memory_file, encoding="utf-8") as f:
                memory_content = f.read()
        else:
            memory_content = self._create_memory_template()

        # 更新記憶內容
        updated_memory = self._update_memory_content(memory_content, archive)

        # 保存更新後的記憶
        with open(memory_file, "w", encoding="utf-8") as f:
            f.write(updated_memory)

        print(f"✅ 測試記憶已更新: {memory_file}")

    def _create_memory_template(self) -> str:
        """創建記憶模板"""
        return """# 🧠 PRD測試記憶

## 📊 測試歷史記錄

## 📈 進度追蹤

## 🔄 更新歷史

"""

    def _update_memory_content(
        self, memory_content: str, archive: PRDTestArchive
    ) -> str:
        """更新記憶內容"""
        timestamp = archive.timestamp.strftime("%Y-%m-%d %H:%M:%S")

        # 添加新的測試記錄
        new_record = f"""
### {timestamp} - {archive.archive_id}
- **測試報告ID**: {archive.test_report.report_id}
- **總需求數**: {archive.test_report.total_requirements}
- **已實現需求**: {archive.test_report.implemented_requirements}
- **已測試需求**: {archive.test_report.tested_requirements}
- **已驗證需求**: {archive.test_report.verified_requirements}
- **需求覆蓋率**: {archive.test_report.coverage_percentage:.1f}%
- **測試通過率**: {archive.test_report.pass_rate:.1f}%
- **整體狀態**: {archive.test_report.overall_status}
- **存檔路徑**: {archive.archive_path}

#### 詳細需求狀況:
"""

        # 添加需求詳細狀況
        for req in archive.test_report.requirements:
            status_emoji = (
                "✅"
                if req.status == PRDRequirementStatus.VERIFIED
                else "❌"
                if req.status == PRDRequirementStatus.NOT_IMPLEMENTED
                else "🟡"
            )
            new_record += (
                f"- {status_emoji} {req.requirement_id}: {req.requirement_name}\n"
            )

        # 更新記憶內容
        updated_content = memory_content + new_record

        return updated_content

    def _generate_archive_report(self, archive: PRDTestArchive):
        """生成存檔報告"""
        print("\n" + "=" * 60)
        print("📦 PRD測試結果存檔報告")
        print("=" * 60)
        print(f"存檔ID: {archive.archive_id}")
        print(f"存檔時間: {archive.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"測試報告ID: {archive.test_report.report_id}")
        print(f"存檔路徑: {archive.archive_path}")
        print(f"總需求數: {archive.test_report.total_requirements}")
        print(f"已實現需求: {archive.test_report.implemented_requirements}")
        print(f"已測試需求: {archive.test_report.tested_requirements}")
        print(f"已驗證需求: {archive.test_report.verified_requirements}")
        print(f"需求覆蓋率: {archive.test_report.coverage_percentage:.1f}%")
        print(f"測試通過率: {archive.test_report.pass_rate:.1f}%")
        print(f"整體狀態: {archive.test_report.overall_status}")
        print("=" * 60)

        # 輸出詳細需求狀況
        print("\n📋 需求實現狀況:")
        for req in archive.test_report.requirements:
            status_emoji = (
                "✅"
                if req.status == PRDRequirementStatus.VERIFIED
                else "❌"
                if req.status == PRDRequirementStatus.NOT_IMPLEMENTED
                else "🟡"
            )
            print(f"{status_emoji} {req.requirement_id}: {req.requirement_name}")

        print("\n🎯 改進建議:")
        self._generate_improvement_suggestions(archive.test_report)

    def _generate_improvement_suggestions(self, test_report: PRDTestReport):
        """生成改進建議"""
        suggestions = []

        # 分析未實現的需求
        not_implemented = [
            req
            for req in test_report.requirements
            if req.status == PRDRequirementStatus.NOT_IMPLEMENTED
        ]
        if not_implemented:
            suggestions.append(f"🔧 優先實現 {len(not_implemented)} 個未實現的核心需求")
            for req in not_implemented:
                suggestions.append(f"   - {req.requirement_id}: {req.requirement_name}")

        # 分析需要測試的需求
        implemented_not_tested = [
            req
            for req in test_report.requirements
            if req.status == PRDRequirementStatus.IMPLEMENTED
        ]
        if implemented_not_tested:
            suggestions.append(
                f"🧪 為 {len(implemented_not_tested)} 個已實現需求添加測試"
            )
            for req in implemented_not_tested:
                suggestions.append(f"   - {req.requirement_id}: {req.requirement_name}")

        # 分析覆蓋率
        if test_report.coverage_percentage < 80:
            suggestions.append(
                f"📊 提高需求覆蓋率 (當前: {test_report.coverage_percentage:.1f}%, 目標: 80%+)"
            )

        # 分析通過率
        if test_report.pass_rate < 90:
            suggestions.append(
                f"✅ 提高測試通過率 (當前: {test_report.pass_rate:.1f}%, 目標: 90%+)"
            )

        # 輸出建議
        for suggestion in suggestions:
            print(suggestion)

    async def close(self):
        """關閉存檔器"""
        await self.validator.close()


async def main():
    """主函數"""
    archiver = PRDTestArchiver()

    try:
        # 執行PRD測試結果存檔
        archive = await archiver.archive_prd_test_results()

        print("\n✅ PRD測試結果存檔完成!")
        print(f"📁 存檔位置: {archive.archive_path}")
        print("🧠 記憶更新: memory_bank/prd_test_memory.md")

    except Exception as e:
        print(f"❌ PRD測試結果存檔失敗: {e}")

    finally:
        await archiver.close()


if __name__ == "__main__":
    asyncio.run(main())
