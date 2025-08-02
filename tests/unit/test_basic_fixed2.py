# 修復後的錯誤處理測試 - 第二版
import asyncio

import pytest

from tests.conftest import assert_async_no_exception


class TestErrorHandling:
    """🔧 測試錯誤處理機制"""

    @pytest.mark.asyncio
    async def test_async_error_handling(self):
        """🔄 測試異步錯誤處理"""

        async def successful_function():
            await asyncio.sleep(0.01)
            return "成功"

        # 測試成功的異步函數
        result = await assert_async_no_exception(successful_function())
        assert result == "成功", "成功的函數應該返回正確結果"

        async def failing_function():
            raise ValueError("測試錯誤")

        # 測試失敗的異步函數 - 這裡期望函數會拋出異常
        # pytest.fail 會拋出 Failed 異常，這是 Exception 的子類
        with pytest.raises(pytest.fail.Exception):  # 捕捉 pytest.fail 拋出的異常
            await assert_async_no_exception(failing_function())

        # 或者，我們可以直接測試函數會拋出異常
        with pytest.raises(ValueError, match="測試錯誤"):
            await failing_function()
