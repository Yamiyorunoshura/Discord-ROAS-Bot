#!/usr/bin/env python3
"""
Discord ROAS Bot - 品質門檻執行與回滾機制
自動執行品質檢查並在失敗時觸發回滾
"""

import os
import sys
import json
import asyncio
import logging
import subprocess
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from datetime import datetime, timedelta
import tempfile
import yaml

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class QualityGateChecker:
    """品質門檻檢查器"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.quality_config_path = project_root / "quality"
        self.config = self._load_configuration()
        
    def _load_configuration(self) -> Dict[str, Any]:
        """載入品質門檻配置"""
        config_file = self.project_root / "config" / "quality-gates.json"
        
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        # 預設配置
        return {
            "thresholds": {
                "test_coverage": 70,
                "code_quality_score": 8.0,
                "security_issues": 0,
                "performance_score": 7.0
            },
            "checks": {
                "ruff": {"enabled": True, "max_violations": 0},
                "mypy": {"enabled": True, "max_errors": 0},
                "pytest": {"enabled": True, "min_coverage": 70},
                "bandit": {"enabled": True, "max_high_severity": 0},
                "safety": {"enabled": True, "max_vulnerabilities": 0}
            },
            "environments": {
                "development": {"strict": False, "allow_warnings": True},
                "testing": {"strict": True, "allow_warnings": False},
                "production": {"strict": True, "allow_warnings": False}
            }
        }
    
    async def run_quality_check(self, check_type: str, environment: str = "production") -> Dict[str, Any]:
        """執行特定的品質檢查"""
        check_config = self.config["checks"].get(check_type, {})
        if not check_config.get("enabled", True):
            return {"skipped": True, "reason": f"{check_type} check disabled"}
        
        env_config = self.config["environments"].get(environment, {})
        strict_mode = env_config.get("strict", True)
        
        logger.info(f"執行 {check_type} 品質檢查 (環境: {environment}, 嚴格模式: {strict_mode})")
        
        try:
            if check_type == "ruff":
                return await self._run_ruff_check(check_config, strict_mode)
            elif check_type == "mypy":
                return await self._run_mypy_check(check_config, strict_mode)
            elif check_type == "pytest":
                return await self._run_pytest_check(check_config, strict_mode)
            elif check_type == "bandit":
                return await self._run_bandit_check(check_config, strict_mode)
            elif check_type == "safety":
                return await self._run_safety_check(check_config, strict_mode)
            else:
                return {"error": f"Unknown check type: {check_type}"}
                
        except Exception as e:
            logger.error(f"{check_type} 檢查執行失敗: {str(e)}")
            return {"error": str(e), "failed": True}
    
    async def _run_ruff_check(self, config: Dict[str, Any], strict: bool) -> Dict[str, Any]:
        """執行 Ruff 代碼檢查"""
        ruff_config = self.quality_config_path / "ruff.toml"
        
        cmd = [
            "uv", "run", "ruff", "check", "src", "tests",
            "--config", str(ruff_config),
            "--output-format", "json"
        ]
        
        if not strict:
            cmd.append("--fix")
        
        result = await self._run_subprocess(cmd)
        
        if result["return_code"] == 0:
            return {"passed": True, "violations": 0}
        
        # 解析 JSON 輸出
        try:
            violations = json.loads(result["stdout"])
            violation_count = len(violations)
            max_violations = config.get("max_violations", 0)
            
            return {
                "passed": violation_count <= max_violations,
                "violations": violation_count,
                "max_allowed": max_violations,
                "details": violations[:10]  # 只保留前10個錯誤
            }
        except json.JSONDecodeError:
            return {"error": "Failed to parse ruff output", "raw_output": result["stdout"]}
    
    async def _run_mypy_check(self, config: Dict[str, Any], strict: bool) -> Dict[str, Any]:
        """執行 MyPy 類型檢查"""
        mypy_config = self.quality_config_path / "mypy_ci.ini"
        
        cmd = [
            "uv", "run", "mypy",
            "--config-file", str(mypy_config),
            "src/core", "src/cogs"
        ]
        
        result = await self._run_subprocess(cmd)
        
        # MyPy 成功時返回碼為 0
        if result["return_code"] == 0:
            return {"passed": True, "errors": 0}
        
        # 計算錯誤數量
        error_lines = [line for line in result["stderr"].split('\n') if ': error:' in line]
        error_count = len(error_lines)
        max_errors = config.get("max_errors", 0)
        
        return {
            "passed": error_count <= max_errors,
            "errors": error_count,
            "max_allowed": max_errors,
            "details": error_lines[:5]  # 只保留前5個錯誤
        }
    
    async def _run_pytest_check(self, config: Dict[str, Any], strict: bool) -> Dict[str, Any]:
        """執行 Pytest 測試和覆蓋率檢查"""
        cmd = [
            "uv", "run", "pytest", "tests/unit",
            "--cov=src", "--cov-report=json:coverage.json",
            "--tb=short", "-v"
        ]
        
        result = await self._run_subprocess(cmd)
        
        # 讀取覆蓋率報告
        coverage_file = self.project_root / "coverage.json"
        coverage_percent = 0
        
        if coverage_file.exists():
            try:
                with open(coverage_file, 'r') as f:
                    coverage_data = json.load(f)
                    coverage_percent = coverage_data.get("totals", {}).get("percent_covered", 0)
            except (json.JSONDecodeError, KeyError):
                logger.warning("無法解析覆蓋率報告")
        
        min_coverage = config.get("min_coverage", 70)
        tests_passed = result["return_code"] == 0
        coverage_passed = coverage_percent >= min_coverage
        
        return {
            "passed": tests_passed and coverage_passed,
            "tests_passed": tests_passed,
            "coverage_percent": coverage_percent,
            "min_coverage": min_coverage,
            "coverage_passed": coverage_passed
        }
    
    async def _run_bandit_check(self, config: Dict[str, Any], strict: bool) -> Dict[str, Any]:
        """執行 Bandit 安全檢查"""
        cmd = [
            "uv", "run", "bandit", "-r", "src",
            "-f", "json", "-ll"  # 只顯示中高風險問題
        ]
        
        result = await self._run_subprocess(cmd)
        
        try:
            bandit_data = json.loads(result["stdout"])
            high_severity = len([r for r in bandit_data.get("results", []) 
                               if r.get("issue_severity") == "HIGH"])
            max_high = config.get("max_high_severity", 0)
            
            return {
                "passed": high_severity <= max_high,
                "high_severity_issues": high_severity,
                "max_allowed": max_high,
                "total_issues": len(bandit_data.get("results", []))
            }
        except json.JSONDecodeError:
            return {"error": "Failed to parse bandit output"}
    
    async def _run_safety_check(self, config: Dict[str, Any], strict: bool) -> Dict[str, Any]:
        """執行 Safety 依賴安全檢查"""
        cmd = ["uv", "run", "safety", "check", "--json"]
        
        result = await self._run_subprocess(cmd)
        
        if result["return_code"] == 0:
            return {"passed": True, "vulnerabilities": 0}
        
        try:
            safety_data = json.loads(result["stdout"])
            vuln_count = len(safety_data)
            max_vulns = config.get("max_vulnerabilities", 0)
            
            return {
                "passed": vuln_count <= max_vulns,
                "vulnerabilities": vuln_count,
                "max_allowed": max_vulns,
                "details": safety_data[:3]  # 只保留前3個漏洞
            }
        except json.JSONDecodeError:
            return {"error": "Failed to parse safety output"}
    
    async def _run_subprocess(self, cmd: List[str]) -> Dict[str, Any]:
        """執行子進程"""
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.project_root
            )
            
            stdout, stderr = await process.communicate()
            
            return {
                "return_code": process.returncode,
                "stdout": stdout.decode('utf-8', errors='ignore'),
                "stderr": stderr.decode('utf-8', errors='ignore')
            }
        except Exception as e:
            logger.error(f"子進程執行失敗: {str(e)}")
            return {
                "return_code": 1,
                "stdout": "",
                "stderr": str(e)
            }
    
    async def run_all_checks(self, environment: str = "production") -> Dict[str, Any]:
        """執行所有品質檢查"""
        logger.info(f"開始執行所有品質檢查 (環境: {environment})")
        
        start_time = datetime.now()
        results = {}
        overall_passed = True
        
        # 執行各項檢查
        check_types = ["ruff", "mypy", "pytest", "bandit", "safety"]
        
        for check_type in check_types:
            logger.info(f"執行 {check_type} 檢查...")
            check_result = await self.run_quality_check(check_type, environment)
            results[check_type] = check_result
            
            if not check_result.get("passed", False) and not check_result.get("skipped", False):
                overall_passed = False
                logger.error(f"{check_type} 檢查失敗")
        
        duration = datetime.now() - start_time
        
        summary = {
            "overall_passed": overall_passed,
            "environment": environment,
            "duration": str(duration),
            "timestamp": datetime.utcnow().isoformat() + 'Z',
            "results": results
        }
        
        logger.info(f"品質檢查完成 - 總體結果: {'通過' if overall_passed else '失敗'}")
        return summary

class RollbackManager:
    """回滾管理器"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.rollback_config = self._load_rollback_config()
        self.deployment_history_file = project_root / "logs" / "deployment-history.json"
        
    def _load_rollback_config(self) -> Dict[str, Any]:
        """載入回滾配置"""
        config_file = self.project_root / "config" / "rollback.json"
        
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        return {
            "auto_rollback_enabled": True,
            "rollback_timeout": 300,
            "health_check_retries": 3,
            "environments": {
                "production": {"auto_rollback": True, "require_confirmation": False},
                "testing": {"auto_rollback": True, "require_confirmation": False},
                "development": {"auto_rollback": False, "require_confirmation": False}
            }
        }
    
    def save_deployment_record(self, environment: str, version: str, 
                             status: str, metadata: Dict[str, Any]) -> None:
        """保存部署記錄"""
        record = {
            "timestamp": datetime.utcnow().isoformat() + 'Z',
            "environment": environment,
            "version": version,
            "status": status,
            "metadata": metadata
        }
        
        # 確保日誌目錄存在
        self.deployment_history_file.parent.mkdir(exist_ok=True)
        
        # 讀取現有記錄
        history = []
        if self.deployment_history_file.exists():
            try:
                with open(self.deployment_history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                history = []
        
        history.append(record)
        
        # 只保留最近100個記錄
        if len(history) > 100:
            history = history[-100:]
        
        # 保存記錄
        with open(self.deployment_history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
        
        logger.info(f"部署記錄已保存: {environment} v{version} - {status}")
    
    def get_last_successful_deployment(self, environment: str) -> Optional[Dict[str, Any]]:
        """獲取最後一次成功的部署記錄"""
        if not self.deployment_history_file.exists():
            return None
        
        try:
            with open(self.deployment_history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
            
            # 找到該環境最後一次成功的部署
            for record in reversed(history):
                if (record.get("environment") == environment and 
                    record.get("status") == "success"):
                    return record
                    
        except (json.JSONDecodeError, FileNotFoundError):
            pass
        
        return None
    
    async def should_rollback(self, environment: str, quality_result: Dict[str, Any]) -> bool:
        """判斷是否應該執行回滾"""
        env_config = self.rollback_config["environments"].get(environment, {})
        
        if not env_config.get("auto_rollback", False):
            logger.info(f"環境 {environment} 未啟用自動回滾")
            return False
        
        if not quality_result.get("overall_passed", True):
            logger.warning(f"品質檢查失敗，建議回滾環境: {environment}")
            return True
        
        return False
    
    async def execute_rollback(self, environment: str, target_version: str = None) -> Dict[str, Any]:
        """執行回滾操作"""
        logger.info(f"開始執行回滾操作: {environment}")
        
        if not target_version:
            last_deployment = self.get_last_successful_deployment(environment)
            if not last_deployment:
                return {
                    "success": False,
                    "error": "No previous successful deployment found"
                }
            target_version = last_deployment["version"]
        
        logger.info(f"回滾到版本: {target_version}")
        
        # 執行回滾腳本
        deploy_script = self.project_root / "scripts" / "deploy" / "deploy.sh"
        
        cmd = [
            str(deploy_script),
            "--environment", environment,
            "--version", target_version,
            "--rollback"
        ]
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.project_root
            )
            
            stdout, stderr = await process.communicate()
            
            success = process.returncode == 0
            
            # 記錄回滾結果
            self.save_deployment_record(
                environment, target_version, 
                "rollback_success" if success else "rollback_failed",
                {"rollback": True, "original_error": stderr.decode() if not success else ""}
            )
            
            return {
                "success": success,
                "target_version": target_version,
                "output": stdout.decode(),
                "error": stderr.decode() if not success else ""
            }
            
        except Exception as e:
            logger.error(f"回滾執行失敗: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

class QualityGateOrchestrator:
    """品質門檻協調器 - 整合品質檢查和回滾機制"""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.quality_checker = QualityGateChecker(project_root)
        self.rollback_manager = RollbackManager(project_root)
        
    async def execute_quality_gates(self, environment: str, version: str) -> Dict[str, Any]:
        """執行完整的品質門檻流程"""
        logger.info(f"開始執行品質門檻流程: {environment} v{version}")
        
        start_time = datetime.now()
        
        # 1. 執行品質檢查
        quality_result = await self.quality_checker.run_all_checks(environment)
        
        # 2. 記錄部署狀態
        deployment_status = "success" if quality_result["overall_passed"] else "quality_failed"
        self.rollback_manager.save_deployment_record(
            environment, version, deployment_status, quality_result
        )
        
        # 3. 判斷是否需要回滾
        should_rollback = await self.rollback_manager.should_rollback(environment, quality_result)
        
        rollback_result = None
        if should_rollback:
            logger.warning("品質檢查失敗，觸發自動回滾")
            rollback_result = await self.rollback_manager.execute_rollback(environment)
        
        duration = datetime.now() - start_time
        
        return {
            "quality_gates_passed": quality_result["overall_passed"],
            "quality_result": quality_result,
            "rollback_triggered": should_rollback,
            "rollback_result": rollback_result,
            "duration": str(duration),
            "timestamp": datetime.utcnow().isoformat() + 'Z'
        }

# CLI 介面
async def main():
    """主程式入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='品質門檻執行與回滾機制')
    parser.add_argument('action', choices=['check', 'rollback', 'execute'])
    parser.add_argument('--environment', default='production', help='部署環境')
    parser.add_argument('--version', help='版本號')
    parser.add_argument('--check-type', choices=['ruff', 'mypy', 'pytest', 'bandit', 'safety'], 
                       help='特定檢查類型')
    
    args = parser.parse_args()
    
    project_root = Path(__file__).parent.parent.parent
    
    if args.action == 'check':
        checker = QualityGateChecker(project_root)
        if args.check_type:
            result = await checker.run_quality_check(args.check_type, args.environment)
        else:
            result = await checker.run_all_checks(args.environment)
        
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(0 if result.get("overall_passed", result.get("passed", False)) else 1)
        
    elif args.action == 'rollback':
        manager = RollbackManager(project_root)
        result = await manager.execute_rollback(args.environment, args.version)
        
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(0 if result["success"] else 1)
        
    elif args.action == 'execute':
        if not args.version:
            print("Error: --version is required for execute action")
            sys.exit(1)
            
        orchestrator = QualityGateOrchestrator(project_root)
        result = await orchestrator.execute_quality_gates(args.environment, args.version)
        
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(0 if result["quality_gates_passed"] else 1)

if __name__ == "__main__":
    asyncio.run(main())