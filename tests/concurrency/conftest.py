"""
併發測試配置檔案
pytest 配置和 fixtures 定義
"""

import pytest
import tempfile
import asyncio
from pathlib import Path


@pytest.fixture(scope="session")
def event_loop():
    """建立事件循環 fixture"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_db_path():
    """臨時資料庫路徑 fixture"""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test_concurrency.db"
    yield str(db_path)
    
    # 清理
    try:
        if db_path.exists():
            db_path.unlink()
    except:
        pass


@pytest.fixture
def test_results_dir():
    """測試結果目錄 fixture"""
    results_dir = Path("test_reports/concurrency")
    results_dir.mkdir(parents=True, exist_ok=True)
    return str(results_dir)


# pytest markers
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.concurrency,
]