"""
隨機交互測試 pytest 配置
Task ID: T5 - Discord testing: dpytest and random interactions

這個配置文件擴展了dpytest的基礎配置，
添加了隨機測試特有的命令行選項和fixture。
"""

import pytest
import sys
from pathlib import Path

# 添加項目根目錄到路徑，以便導入dpytest配置
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 導入dpytest的fixtures
pytest_plugins = ["tests.dpytest.conftest"]


def pytest_addoption(parser):
    """添加 pytest 命令行選項"""
    parser.addoption(
        "--seed", 
        action="store", 
        default=None, 
        type=int,
        help="Random seed for reproducible tests"
    )
    parser.addoption(
        "--max-steps", 
        action="store", 
        default=5, 
        type=int,
        help="Maximum number of interaction steps"
    )
    parser.addoption(
        "--random-runs",
        action="store",
        default=1,
        type=int,
        help="Number of random test runs to execute"
    )


@pytest.fixture
def test_seed(request):
    """提供測試種子"""
    return request.config.getoption("--seed")


@pytest.fixture  
def test_max_steps(request):
    """提供最大步數"""
    return request.config.getoption("--max-steps")


@pytest.fixture
def random_runs(request):
    """提供隨機測試執行次數"""
    return request.config.getoption("--random-runs")


@pytest.fixture(scope="session")
def configure_random_test_environment():
    """配置隨機測試環境"""
    # 確保測試報告目錄存在
    test_dirs = ["test_reports", "logs"]
    for dir_name in test_dirs:
        Path(dir_name).mkdir(parents=True, exist_ok=True)
    
    yield
    
    # 清理可在這裡添加