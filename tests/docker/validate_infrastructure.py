"""
Docker 測試框架基礎架構驗證腳本
Task ID: T1 - Docker 測試框架建立 (基礎架構部分)

驗證 Docker 測試框架的基礎架構組件是否正常運作
"""

import sys
from pathlib import Path
import importlib.util

def test_framework_imports():
    """測試框架模組導入"""
    print("🔍 測試 Docker 測試框架模組導入...")
    
    try:
        from tests.docker.conftest import (
            DockerTestFixture,
            DockerTestLogger,
            DockerTestError,
            ContainerHealthCheckError,
            DOCKER_TEST_CONFIG,
            wait_for_container_ready,
            get_container_logs
        )
        print("✅ 所有核心模組成功導入")
        return True
    except ImportError as e:
        print(f"❌ 模組導入失敗: {e}")
        return False

def test_config_validation():
    """測試配置驗證"""
    print("🔍 測試 Docker 測試配置...")
    
    try:
        from tests.docker.conftest import DOCKER_TEST_CONFIG
        
        required_keys = [
            'image_name',
            'container_name_prefix', 
            'test_timeout',
            'healthcheck_timeout',
            'container_memory_limit',
            'container_cpu_limit',
            'network_name',
            'volume_mount_path'
        ]
        
        for key in required_keys:
            if key not in DOCKER_TEST_CONFIG:
                print(f"❌ 缺少配置鍵: {key}")
                return False
                
        print("✅ 配置驗證通過")
        return True
    except Exception as e:
        print(f"❌ 配置驗證失敗: {e}")
        return False

def test_class_instantiation():
    """測試類別實例化（不需要 Docker）"""
    print("🔍 測試類別實例化...")
    
    try:
        from tests.docker.conftest import DockerTestLogger
        
        # 測試日誌記錄器
        logger = DockerTestLogger("test_validation")
        logger.log_info("測試日誌記錄")
        logger.log_error("測試錯誤記錄", Exception("測試異常"))
        
        report = logger.generate_report()
        assert "test_id" in report
        assert "test_name" in report
        assert report["test_name"] == "test_validation"
        
        print("✅ 類別實例化測試通過")
        return True
    except Exception as e:
        print(f"❌ 類別實例化失敗: {e}")
        return False

def test_directory_structure():
    """測試目錄結構"""
    print("🔍 測試目錄結構...")
    
    try:
        project_root = Path(__file__).parent.parent.parent
        docker_tests_dir = project_root / "tests" / "docker"
        
        required_files = [
            "__init__.py",
            "conftest.py", 
            "test_container_basics.py"
        ]
        
        for file_name in required_files:
            file_path = docker_tests_dir / file_name
            if not file_path.exists():
                print(f"❌ 缺少檔案: {file_path}")
                return False
                
        print("✅ 目錄結構驗證通過")
        return True
    except Exception as e:
        print(f"❌ 目錄結構驗證失敗: {e}")
        return False

def test_pytest_integration():
    """測試 pytest 整合"""
    print("🔍 測試 pytest 整合...")
    
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/docker/", "--collect-only", "-q"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0 and "collected" in result.stdout:
            print("✅ pytest 整合測試通過")
            return True
        else:
            print(f"❌ pytest 整合失敗: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ pytest 整合測試失敗: {e}")
        return False

def main():
    """主要驗證流程"""
    print("🚀 開始 Docker 測試框架基礎架構驗證")
    print("=" * 50)
    
    tests = [
        ("模組導入測試", test_framework_imports),
        ("配置驗證測試", test_config_validation), 
        ("類別實例化測試", test_class_instantiation),
        ("目錄結構測試", test_directory_structure),
        ("pytest 整合測試", test_pytest_integration)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}")
        if test_func():
            passed += 1
        else:
            print(f"❌ {test_name} 失敗")
    
    print("\n" + "=" * 50)
    print(f"📊 驗證結果: {passed}/{total} 測試通過")
    
    if passed == total:
        print("🎉 Docker 測試框架基礎架構驗證成功！")
        return 0
    else:
        print("⚠️  部分測試失敗，請檢查錯誤訊息")
        return 1

if __name__ == "__main__":
    sys.exit(main())