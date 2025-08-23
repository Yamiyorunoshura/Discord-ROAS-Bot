#!/usr/bin/env python3
"""
失敗重現報告生成器
Task ID: T5 - Discord testing: dpytest and random interactions

從測試結果中生成失敗重現報告，支援重新執行相同的失敗場景。
"""

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class FailureReportGenerator:
    """失敗重現報告生成器"""
    
    def __init__(self, test_results_path: Path, output_path: Path):
        self.test_results_path = test_results_path
        self.output_path = output_path
        
    def generate_report(self) -> Dict[str, Any]:
        """生成失敗重現報告"""
        
        failures = self._parse_test_results()
        
        if not failures:
            logger.info("No test failures found")
            return {"status": "no_failures", "failures": []}
            
        report = {
            "status": "failures_detected",
            "generated_at": datetime.now().isoformat(),
            "source_file": str(self.test_results_path),
            "total_failures": len(failures),
            "failures": failures,
            "reproduction_instructions": self._generate_reproduction_instructions(failures)
        }
        
        # 寫入報告檔案
        self._save_report(report)
        
        return report
    
    def _parse_test_results(self) -> List[Dict[str, Any]]:
        """解析測試結果XML檔案"""
        failures = []
        
        if not self.test_results_path.exists():
            logger.warning(f"Test results file not found: {self.test_results_path}")
            return failures
            
        try:
            tree = ET.parse(self.test_results_path)
            root = tree.getroot()
            
            # 處理 pytest 生成的 JUnit XML 格式
            for testcase in root.findall('.//testcase'):
                failure = testcase.find('failure')
                error = testcase.find('error')
                
                if failure is not None or error is not None:
                    failure_info = {
                        "test_name": testcase.get('name', 'unknown'),
                        "class_name": testcase.get('classname', 'unknown'),
                        "time": testcase.get('time', '0'),
                        "failure_type": None,
                        "failure_message": None,
                        "failure_details": None
                    }
                    
                    if failure is not None:
                        failure_info["failure_type"] = failure.get('type', 'AssertionError')
                        failure_info["failure_message"] = failure.get('message', '')
                        failure_info["failure_details"] = failure.text or ''
                        
                    elif error is not None:
                        failure_info["failure_type"] = error.get('type', 'Error')
                        failure_info["failure_message"] = error.get('message', '')
                        failure_info["failure_details"] = error.text or ''
                    
                    # 嘗試從測試名稱或詳情中提取種子資訊
                    seed = self._extract_seed_from_failure(failure_info)
                    if seed:
                        failure_info["seed"] = seed
                    
                    failures.append(failure_info)
                    
        except ET.ParseError as e:
            logger.error(f"Failed to parse XML test results: {e}")
        except Exception as e:
            logger.error(f"Unexpected error parsing test results: {e}")
            
        return failures
    
    def _extract_seed_from_failure(self, failure_info: Dict[str, Any]) -> Optional[int]:
        """嘗試從失敗資訊中提取種子值"""
        
        # 檢查測試名稱
        test_name = failure_info.get("test_name", "")
        if "seed" in test_name.lower():
            import re
            seed_match = re.search(r'seed[_=]?(\d+)', test_name.lower())
            if seed_match:
                return int(seed_match.group(1))
        
        # 檢查失敗詳情
        failure_details = failure_info.get("failure_details", "")
        if "seed=" in failure_details:
            import re
            seed_match = re.search(r'seed=(\d+)', failure_details)
            if seed_match:
                return int(seed_match.group(1))
                
        return None
    
    def _generate_reproduction_instructions(self, failures: List[Dict[str, Any]]) -> Dict[str, Any]:
        """生成重現指令"""
        
        instructions = {
            "general": {
                "setup": [
                    "cd /Users/tszkinlai/Coding/roas-bot",
                    "source venv/bin/activate  # if using virtual environment",
                    "pip install -e \".[dev]\""
                ],
                "environment": [
                    "export TESTING=true",
                    "export LOG_LEVEL=WARNING"
                ]
            },
            "specific_failures": []
        }
        
        for failure in failures:
            test_name = failure["test_name"]
            class_name = failure["class_name"]
            seed = failure.get("seed")
            
            # 建構測試路徑
            if class_name and class_name != "unknown":
                test_path = f"{class_name}::{test_name}"
            else:
                # 嘗試從類別名稱推斷文件路徑
                if "TestRandomInteractions" in class_name:
                    test_path = f"tests/random/test_random_interactions.py::{test_name}"
                elif "TestBasicDpytestFlows" in class_name:
                    test_path = f"tests/dpytest/test_basic_flows.py::{test_name}"
                else:
                    test_path = f"tests/**/*test*.py::{test_name}"
            
            # 建構命令
            base_command = f"python -m pytest {test_path} -v -s"
            
            if seed:
                base_command += f" --seed={seed}"
            
            # 添加其他可能有用的參數
            base_command += " --tb=long --capture=no"
            
            failure_instruction = {
                "test_name": test_name,
                "command": base_command,
                "seed": seed,
                "failure_type": failure["failure_type"],
                "description": f"Reproduce failure in {test_name}"
            }
            
            if seed:
                failure_instruction["note"] = f"This test uses seed {seed} for reproducibility"
            
            instructions["specific_failures"].append(failure_instruction)
        
        return instructions
    
    def _save_report(self, report: Dict[str, Any]):
        """保存報告到檔案"""
        try:
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
                
            logger.info(f"Failure report saved to: {self.output_path}")
            
        except Exception as e:
            logger.error(f"Failed to save report: {e}")
            raise


def main():
    """主函數"""
    parser = argparse.ArgumentParser(description="Generate failure reproduction report from test results")
    parser.add_argument("--test-results", required=True, 
                       help="Path to test results XML file")
    parser.add_argument("--output", required=True,
                       help="Output path for reproduction report JSON")
    parser.add_argument("--verbose", action="store_true",
                       help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # 設置日誌
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(levelname)s: %(message)s')
    
    # 生成報告
    try:
        generator = FailureReportGenerator(
            test_results_path=Path(args.test_results),
            output_path=Path(args.output)
        )
        
        report = generator.generate_report()
        
        if report["status"] == "no_failures":
            print("✅ No test failures detected")
        else:
            print(f"⚠️ {report['total_failures']} test failures detected")
            print(f"📄 Reproduction report saved to: {args.output}")
            
            # 顯示重現指令摘要
            for failure in report["reproduction_instructions"]["specific_failures"]:
                print(f"🔄 To reproduce '{failure['test_name']}': {failure['command']}")
        
    except Exception as e:
        logger.error(f"Failed to generate failure report: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())