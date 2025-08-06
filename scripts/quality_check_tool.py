#!/usr/bin/env python3
"""Quality Check Tool

Enterprise-grade code quality checking using our built-in quality assurance system.
"""

import asyncio
import sys
from pathlib import Path
from typing import Any

from src.core.quality import QualityAssuranceService
from src.core.quality.enforcement import QualityGateEnforcer, QualityGatePolicy
from src.core.quality.metrics import QualityMetricsCollector


async def main() -> None:
    """Main execution function with proper error handling and Unicode support."""
    if len(sys.argv) < 2:
        print("Usage: python quality_check_tool.py <target_path>")
        sys.exit(1)
    
    target_path = sys.argv[1]
    if not Path(target_path).exists():
        print(f"Error: Path {target_path} does not exist")
        sys.exit(1)
    
    print(f"Checking path: {target_path}")
    print("=" * 50)
    
    # Initialize services
    quality_service = QualityAssuranceService()
    gate_enforcer = QualityGateEnforcer()
    metrics_collector = QualityMetricsCollector()
    
    try:
        # Execute quality checks
        print("Running quality checks...")
        result = await quality_service.run_quality_checks(target_path)
        
        # Generate reports
        print("Generating quality report...")
        report = quality_service.generate_quality_report(result, format="json")
        
        # Evaluate quality gates
        print("Evaluating quality gates...")
        gate_result = gate_enforcer.evaluate_quality_gate(result, QualityGatePolicy.STANDARD)
        
        # Collect metrics
        print("Collecting quality metrics...")
        metrics = metrics_collector.collect_metrics(
            project_path=target_path,
            type_coverage=result.type_coverage,
            mypy_error_count=len(result.mypy_errors),
            ruff_error_count=len(result.ruff_errors),
            total_files=result.total_files,
            checked_files=result.checked_files,
            execution_time=result.execution_time
        )
        
        # 顯示結果
        print("\n" + "=" * 50)
        print("Quality Check Results")
        print("=" * 50)
        
        print(f"Status: {result.status.value}")
        print(f"Type Coverage: {result.type_coverage:.1f}%")
        print(f"Mypy Errors: {len(result.mypy_errors)}")
        print(f"Ruff Errors: {len(result.ruff_errors)}")
        print(f"Execution Time: {result.execution_time:.2f}s")
        
        print(f"\nQuality Gate Evaluation:")
        print(f"Passed: {'Yes' if gate_result.passed else 'No'}")
        print(f"Quality Score: {gate_result.score:.1f}/100")
        print(f"Policy: {gate_result.policy.value}")
        
        if gate_result.violations:
            print(f"\nViolations:")
            for violation in gate_result.violations:
                print(f"  • {violation}")
        
        if gate_result.recommendations:
            print(f"\nRecommendations:")
            for recommendation in gate_result.recommendations:
                print(f"  • {recommendation}")
        
        # 如果有錯誤，顯示詳細信息
        if result.mypy_errors:
            print(f"\nMypy Error Details:")
            for error in result.mypy_errors[:5]:  # 只顯示前5個
                print(f"  {error}")
            if len(result.mypy_errors) > 5:
                print(f"  ... and {len(result.mypy_errors) - 5} more errors")
        
        if result.ruff_errors:
            print(f"\nRuff Error Details:")
            for error in result.ruff_errors[:5]:  # 只顯示前5個
                print(f"  {error}")
            if len(result.ruff_errors) > 5:
                print(f"  ... and {len(result.ruff_errors) - 5} more errors")
        
        print("\n" + "=" * 50)
        print("Quality check completed!")
        
        # 根據結果設定退出碼
        if gate_result.passed:
            sys.exit(0)
        else:
            sys.exit(1)
            
    except Exception as e:
        print(f"Error during quality check: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())