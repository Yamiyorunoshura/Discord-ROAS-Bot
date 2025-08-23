"""
錯誤代碼一致性整合測試套件
Task ID: T8 - 錯誤代碼系統統一化

這個測試套件驗證錯誤代碼系統的一致性，包括：
- 錯誤代碼唯一性檢查
- 使用者訊息完整性驗證
- 錯誤處理格式一致性測試
- 服務模組錯誤採用率檢查
"""

import pytest
import asyncio
import sys
import os
from typing import Dict, Any, List
from unittest.mock import Mock

# 添加項目根目錄到路徑
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.core.error_codes import ErrorCode, get_user_message, map_exception_to_error_code
from src.core.errors import ServiceError, ValidationError, DatabaseError, AppError
from src.core.error_middleware import (
    ErrorCodeValidator, ConsistencyChecker, validate_error_handling_consistency,
    standardized_error_handling
)


class TestErrorCodeUniqueness:
    """測試錯誤代碼唯一性"""
    
    def test_error_code_uniqueness(self):
        """驗證所有錯誤代碼都是唯一的"""
        validator = ErrorCodeValidator()
        duplicates = validator.validate_error_code_uniqueness()
        
        assert len(duplicates) == 0, f"發現重複的錯誤代碼: {duplicates}"
    
    def test_error_code_format(self):
        """驗證錯誤代碼格式符合規範"""
        validator = ErrorCodeValidator()
        invalid_formats = validator.validate_error_code_format()
        
        assert len(invalid_formats) == 0, f"錯誤代碼格式不正確: {invalid_formats}"
    
    def test_error_code_naming_convention(self):
        """驗證錯誤代碼命名規範"""
        expected_prefixes = {
            'APP_', 'SVC_', 'ACH_', 'ECO_', 'GOV_', 'DB_', 
            'VAL_', 'PERM_', 'NF_', 'CFG_', 'EXT_', 'TEST_',
            'ACT_', 'MON_', 'DEP_', 'DOC_'
        }
        
        for error_code in ErrorCode:
            value = error_code.value
            prefix = value.split('_')[0] + '_'
            assert prefix in expected_prefixes, f"未知的錯誤代碼前綴: {prefix} in {value}"


class TestMessageCompleteness:
    """測試使用者訊息完整性"""
    
    def test_all_error_codes_have_messages(self):
        """驗證所有錯誤代碼都有對應的使用者訊息"""
        validator = ErrorCodeValidator()
        missing_messages = validator.validate_message_completeness()
        
        assert len(missing_messages) == 0, f"缺少使用者訊息的錯誤代碼: {missing_messages}"
    
    def test_user_messages_are_chinese(self):
        """驗證使用者訊息都是繁體中文"""
        for error_code in ErrorCode:
            message = get_user_message(error_code)
            # 簡單檢查：訊息不應該是英文或空白
            assert message is not None and len(message) > 0, f"錯誤代碼 {error_code.name} 的訊息為空"
            assert not message.isascii() or any(char in message for char in ['，', '：', '。']), \
                f"錯誤代碼 {error_code.name} 的訊息可能不是中文: {message}"
    
    def test_message_context_formatting(self):
        """測試訊息上下文格式化"""
        # 測試包含上下文的訊息格式化
        context = {"user_id": 12345, "amount": 100}
        message = get_user_message(ErrorCode.INSUFFICIENT_BALANCE, context)
        
        assert message is not None
        assert len(message) > 0


class TestExceptionMapping:
    """測試異常映射功能"""
    
    def test_app_error_mapping(self):
        """測試自定義應用錯誤的映射"""
        service_error = ServiceError("測試錯誤", "TestService", "test_operation")
        mapped_code = map_exception_to_error_code(service_error)
        assert mapped_code == ErrorCode.SERVICE_ERROR
        
        validation_error = ValidationError("field", "invalid_value", "validation_rule")
        mapped_code = map_exception_to_error_code(validation_error)
        assert mapped_code == ErrorCode.VALIDATION_ERROR
        
        db_error = DatabaseError("query", "查詢失敗")
        mapped_code = map_exception_to_error_code(db_error)
        assert mapped_code == ErrorCode.DATABASE_QUERY_ERROR
    
    def test_builtin_exception_mapping(self):
        """測試內建異常的映射"""
        value_error = ValueError("無效值")
        mapped_code = map_exception_to_error_code(value_error)
        assert mapped_code == ErrorCode.INVALID_INPUT
        
        key_error = KeyError("不存在的鍵")
        mapped_code = map_exception_to_error_code(key_error)
        assert mapped_code == ErrorCode.NOT_FOUND
        
        timeout_error = TimeoutError("操作逾時")
        mapped_code = map_exception_to_error_code(timeout_error)
        assert mapped_code == ErrorCode.TIMEOUT_ERROR
    
    def test_unknown_exception_mapping(self):
        """測試未知異常的映射"""
        unknown_error = RuntimeError("未知錯誤")
        mapped_code = map_exception_to_error_code(unknown_error)
        assert mapped_code == ErrorCode.UNKNOWN_ERROR


class TestStandardizedErrorHandling:
    """測試標準化錯誤處理裝飾器"""
    
    def test_decorator_with_service_error(self):
        """測試裝飾器處理服務錯誤"""
        @standardized_error_handling(ErrorCode.SERVICE_ERROR)
        async def test_method():
            raise ServiceError("測試服務錯誤", "TestService", "test_method")
        
        with pytest.raises(ServiceError):
            asyncio.run(test_method())
    
    def test_decorator_with_generic_exception(self):
        """測試裝飾器處理通用異常"""
        class MockService:
            name = "TestService"
            logger = Mock()
        
        service = MockService()
        
        @standardized_error_handling(ErrorCode.SERVICE_ERROR)
        async def test_method(self):
            raise ValueError("測試異常")
        
        with pytest.raises(ServiceError) as exc_info:
            asyncio.run(test_method(service))
        
        assert exc_info.value.service_name == "TestService"
        assert exc_info.value.operation == "test_method"


class TestConsistencyChecker:
    """測試一致性檢查器"""
    
    def test_service_error_adoption_check(self):
        """測試服務錯誤採用檢查"""
        # 創建模擬服務
        class MockService:
            name = "TestService"
            
            @standardized_error_handling()
            async def method_with_standard_handling(self):
                pass
            
            def method_without_standard_handling(self):
                pass
        
        service = MockService()
        checker = ConsistencyChecker()
        result = checker.check_service_error_adoption(service)
        
        assert result["service_name"] == "TestService"
        assert "method_with_standard_handling" in result["error_handling_methods"]
        assert result["uses_standard_errors"] is True


class TestSystemWideConsistency:
    """測試系統級一致性"""
    
    def test_overall_consistency_validation(self):
        """測試整體一致性驗證"""
        results = validate_error_handling_consistency()
        
        assert results["overall_status"] in ["PASS", "FAIL"]
        assert "checks" in results
        assert "error_code_uniqueness" in results["checks"]
        assert "message_completeness" in results["checks"]
        assert "format_validation" in results["checks"]
    
    def test_consistency_report_structure(self):
        """測試一致性報告結構"""
        results = validate_error_handling_consistency()
        
        # 檢查必要的欄位
        required_fields = ["timestamp", "overall_status", "checks"]
        for field in required_fields:
            assert field in results
        
        # 檢查每個檢查項目都有狀態
        for check_name, check_result in results["checks"].items():
            assert "status" in check_result
            assert check_result["status"] in ["PASS", "FAIL"]


class TestErrorCodeCoverage:
    """測試錯誤代碼覆蓋率"""
    
    def test_module_error_code_coverage(self):
        """測試各模組的錯誤代碼覆蓋情況"""
        module_prefixes = {
            'APP': '通用應用程式',
            'SVC': '服務層',
            'ACH': '成就系統',
            'ECO': '經濟系統',
            'GOV': '政府系統',
            'DB': '資料庫',
            'VAL': '驗證',
            'PERM': '權限',
            'NF': '資源查找',
            'CFG': '配置',
            'EXT': '外部服務',
            'TEST': '測試',
            'ACT': '活動系統',
            'MON': '監控系統',
            'DEP': '部署系統',
            'DOC': '文檔系統'
        }
        
        coverage = {}
        for error_code in ErrorCode:
            prefix = error_code.value.split('_')[0]
            if prefix not in coverage:
                coverage[prefix] = 0
            coverage[prefix] += 1
        
        # 確保每個定義的模組都有錯誤代碼
        for prefix, description in module_prefixes.items():
            assert prefix in coverage, f"{description} ({prefix}) 沒有定義錯誤代碼"
            assert coverage[prefix] > 0, f"{description} ({prefix}) 錯誤代碼數量為零"


if __name__ == "__main__":
    # 執行一致性檢查並產生報告
    print("執行錯誤代碼一致性檢查...")
    
    results = validate_error_handling_consistency()
    
    print(f"\\n整體狀態: {results['overall_status']}")
    print(f"檢查時間: {results['timestamp']}")
    
    for check_name, check_result in results["checks"].items():
        status = check_result["status"]
        print(f"\\n{check_name}: {status}")
        
        if status == "FAIL":
            # 打印詳細的失敗信息
            for key, value in check_result.items():
                if key != "status" and value:
                    print(f"  {key}: {value}")
    
    # 運行測試
    pytest.main([__file__, "-v"])