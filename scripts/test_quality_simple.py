#!/usr/bin/env python3
"""Simple Quality Check Test

Direct test of ruff and mypy tools without import issues.
"""

import subprocess
import sys
from pathlib import Path


def test_ruff_check():
    """Test ruff check"""
    print("[RUFF] Testing Ruff quality check...")
    
    try:
        result = subprocess.run([
            "ruff", "check", 
            "--config", "quality/ruff.toml",
            "src/core/quality"
        ], capture_output=True, text=True, cwd=Path.cwd())
        
        print(f"[RUFF] Return code: {result.returncode}")
        
        if result.stdout:
            lines = result.stdout.strip().split('\n')
            error_count = len([line for line in lines if line.strip()])
            print(f"[RUFF] Found {error_count} errors")
            
            # Show first 5 errors
            for line in lines[:5]:
                if line.strip():
                    print(f"   - {line}")
            if len(lines) > 5:
                print(f"   ... and {len(lines) - 5} more errors")
        else:
            print("[RUFF] Check passed!")
            
        return result.returncode == 0
        
    except Exception as e:
        print(f"[RUFF] Check failed: {e}")
        return False


def test_mypy_check():
    """Test mypy check"""
    print("\n[MYPY] Testing Mypy type check...")
    
    try:
        # Check specific file to avoid import issues
        result = subprocess.run([
            "mypy", 
            "--config-file", "quality/mypy_ci.ini",
            "--follow-imports", "silent",
            "--ignore-missing-imports",
            "src/core/quality/ci_runner.py"
        ], capture_output=True, text=True, cwd=Path.cwd())
        
        print(f"[MYPY] Return code: {result.returncode}")
        
        if result.stdout:
            lines = result.stdout.strip().split('\n')
            error_lines = [line for line in lines if 'error:' in line]
            print(f"[MYPY] Found {len(error_lines)} errors")
            
            # Show first 3 errors
            for line in error_lines[:3]:
                if line.strip():
                    print(f"   - {line}")
            if len(error_lines) > 3:
                print(f"   ... and {len(error_lines) - 3} more errors")
        else:
            print("[MYPY] Check passed!")
            
        return result.returncode == 0
        
    except Exception as e:
        print(f"[MYPY] Check failed: {e}")
        return False


def test_quality_gate():
    """Test quality gate"""
    print("\n[GATE] Testing quality gate...")
    
    ruff_passed = test_ruff_check()
    mypy_passed = test_mypy_check()
    
    print(f"\n[SUMMARY] Quality check summary:")
    print(f"   Ruff: {'[PASS]' if ruff_passed else '[FAIL]'}")
    print(f"   Mypy: {'[PASS]' if mypy_passed else '[FAIL]'}")
    
    if ruff_passed and mypy_passed:
        print("[SUCCESS] Quality gate check passed!")
        return True
    else:
        print("[ERROR] Quality gate check failed!")
        return False


if __name__ == "__main__":
    success = test_quality_gate()
    sys.exit(0 if success else 1)