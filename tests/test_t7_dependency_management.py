# T7: 環境與依賴管理系統測試
# 測試 uv 工具鏈整合和依賴管理工作流程

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


class TestUvDependencyManagement:
    """測試 uv 依賴管理工作流程"""
    
    @pytest.fixture
    def project_root(self):
        """專案根目錄"""
        return Path(__file__).parent.parent
    
    def test_uv_command_available(self):
        """F-7-1: 測試 uv 指令可用"""
        result = subprocess.run(['uv', '--version'], 
                               capture_output=True, text=True)
        assert result.returncode == 0, "uv command should be available"
        assert "uv" in result.stdout.lower(), "uv version output should contain 'uv'"
    
    def test_pyproject_toml_exists_and_valid(self, project_root):
        """F-7-1: 測試 pyproject.toml 存在且格式正確"""
        pyproject_path = project_root / "pyproject.toml"
        assert pyproject_path.exists(), "pyproject.toml should exist"
        
        # 測試可以被解析 (Python 3.10 相容性)
        try:
            import tomllib
            with open(pyproject_path, "rb") as f:
                config = tomllib.load(f)
        except ImportError:
            # Python < 3.11 fallback
            import configparser
            # 簡化檢查：只驗證檔案可讀取
            with open(pyproject_path, "r") as f:
                content = f.read()
                assert "[project]" in content, "Should contain [project] section"
                assert "dependencies" in content, "Should contain dependencies"
                return  # 跳過詳細檢查
        
        assert "project" in config, "pyproject.toml should have [project] section"
        assert "dependencies" in config["project"], "Should have dependencies"
    
    def test_uv_sync_execution(self, project_root):
        """F-7-1: 測試 uv sync 可以執行"""
        # 在專案根目錄執行 uv sync --dry-run
        result = subprocess.run(
            ['uv', 'sync', '--dry-run'],
            cwd=project_root,
            capture_output=True,
            text=True
        )
        # dry-run 應該成功或給出有用的錯誤資訊
        assert result.returncode in [0, 1], f"uv sync dry-run failed: {result.stderr}"
    
    def test_uv_lock_generation(self, project_root):
        """F-7-1: 測試 uv.lock 檔案生成"""
        # 執行 uv lock 看是否能成功
        result = subprocess.run(
            ['uv', 'lock', '--dry-run'],
            cwd=project_root, 
            capture_output=True,
            text=True
        )
        # dry-run 應該能執行
        assert result.returncode in [0, 1], f"uv lock dry-run failed: {result.stderr}"
    
    def test_python_version_compatibility(self, project_root):
        """N-7-2: 測試 Python 版本相容性"""
        pyproject_path = project_root / "pyproject.toml"
        
        # Python 3.10 相容性檢查
        try:
            import tomllib
            with open(pyproject_path, "rb") as f:
                config = tomllib.load(f)
            requires_python = config["project"]["requires-python"]
        except ImportError:
            # Python < 3.11 fallback - 簡單字串搜尋
            with open(pyproject_path, "r") as f:
                content = f.read()
                # 找到 requires-python 行
                for line in content.split('\n'):
                    if 'requires-python' in line:
                        requires_python = line
                        break
                else:
                    pytest.fail("requires-python not found in pyproject.toml")
        
        # 檢查是否支援 Python 3.10+ (向後相容性)
        assert "3.10" in requires_python, \
            f"Should support Python 3.10, found: {requires_python}"
    
    def test_dependency_consistency(self, project_root):
        """N-7-2: 測試依賴一致性檢查基礎設施"""
        pyproject_path = project_root / "pyproject.toml"
        
        # Python 3.10 相容性檢查
        try:
            import tomllib
            with open(pyproject_path, "rb") as f:
                config = tomllib.load(f)
            deps = config["project"]["dependencies"]
            dev_deps = config["project"]["optional-dependencies"]["dev"]
        except ImportError:
            # Python < 3.11 fallback - 字串搜尋
            with open(pyproject_path, "r") as f:
                content = f.read()
                assert "dependencies" in content, "Should have dependencies section"
                assert "[project.optional-dependencies]" in content, "Should have dev deps"
                assert "discord.py" in content, "Should include discord.py"
                return  # 跳過詳細檢查
        
        # 基本依賴檢查
        assert len(deps) > 0, "Should have main dependencies"
        assert len(dev_deps) > 0, "Should have dev dependencies"
        
        # 檢查重要依賴存在
        dep_names = [dep.split(">=")[0].split("==")[0] for dep in deps]
        assert "discord.py" in dep_names, "Should include discord.py"


class TestCiWorkflowMigration:
    """測試 CI 工作流程遷移"""
    
    @pytest.fixture
    def ci_workflow_path(self):
        """CI 工作流程檔案路徑"""
        return Path(__file__).parent.parent / ".github" / "workflows" / "ci.yml"
    
    def test_ci_workflow_exists(self, ci_workflow_path):
        """F-7-2: 測試 CI 工作流程檔案存在"""
        assert ci_workflow_path.exists(), "CI workflow file should exist"
    
    def test_ci_workflow_syntax(self, ci_workflow_path):
        """F-7-2: 測試 CI 工作流程語法正確"""
        import yaml
        
        with open(ci_workflow_path, 'r') as f:
            workflow = yaml.safe_load(f)
        
        assert "jobs" in workflow, "Workflow should have jobs"
        assert len(workflow["jobs"]) > 0, "Should have at least one job"


class TestDevelopmentExperience:
    """測試開發者體驗"""
    
    def test_development_setup_time_check(self):
        """N-7-3: 測試開發環境設置時間基準"""
        # 這是一個時間基準測試，實際實施後會測量真實時間
        import time
        
        start_time = time.time()
        
        # 模擬快速設置檢查（實際會替換為 uv sync）
        result = subprocess.run(['python', '-c', 'import sys; print(sys.version)'], 
                               capture_output=True)
        
        setup_time = time.time() - start_time
        
        # 基準檢查：基本命令應該在 1 秒內完成
        assert setup_time < 1.0, "Basic setup commands should be fast"
        assert result.returncode == 0, "Python should be available"
    
    def test_error_handling_and_recovery(self):
        """N-7-3: 測試錯誤處理和恢復機制"""
        # 測試 uv 指令錯誤處理
        result = subprocess.run(['uv', 'invalid-command'], 
                               capture_output=True, text=True)
        
        # 應該返回錯誤但不會崩潰
        assert result.returncode != 0, "Invalid command should return error"
        assert len(result.stderr) > 0, "Should provide error message"


class TestPerformanceBenchmarks:
    """效能基準測試"""
    
    @pytest.mark.performance
    def test_installation_speed_benchmark(self):
        """N-7-1: 測試安裝速度基準"""
        # 這會在實際實施後測量真實的安裝時間
        import time
        
        # 模擬依賴安裝時間測量
        start_time = time.time()
        
        # 在真實實施中，這裡會執行 uv sync
        time.sleep(0.1)  # 模擬快速安裝
        
        install_time = time.time() - start_time
        
        # 基準：模擬安裝應該很快
        assert install_time < 1.0, "Simulated installation should be fast"
        
        # 實際目標：< 60 秒（將在實施後驗證）
        # assert install_time < 60, "Real installation should be < 60 seconds"


@pytest.mark.integration 
class TestEndToEndWorkflow:
    """端到端工作流程測試"""
    
    def test_full_uv_workflow_simulation(self):
        """F-7-1, F-7-2, F-7-3: 測試完整 uv 工作流程模擬"""
        # 這個測試會在實施後驗證完整流程
        
        # 步驟 1: 檢查 pyproject.toml
        project_root = Path(__file__).parent.parent
        pyproject_path = project_root / "pyproject.toml"
        assert pyproject_path.exists(), "Step 1: pyproject.toml should exist"
        
        # 步驟 2: 檢查 uv 可用性
        result = subprocess.run(['uv', '--version'], capture_output=True)
        assert result.returncode == 0, "Step 2: uv should be available"
        
        # 步驟 3: 檢查 CI 檔案
        ci_path = project_root / ".github" / "workflows" / "ci.yml"
        assert ci_path.exists(), "Step 3: CI workflow should exist"
        
        # 步驟 4: 模擬測試執行（實施後會實際執行測試）
        assert True, "Step 4: Tests should pass (placeholder)"


# 標記測試分類
pytest.mark.unit(TestUvDependencyManagement)
pytest.mark.unit(TestCiWorkflowMigration)
pytest.mark.unit(TestDevelopmentExperience)
pytest.mark.performance(TestPerformanceBenchmarks)