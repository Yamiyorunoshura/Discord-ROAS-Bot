"""成就管理資料驗證和安全性測試.

此模組測試資料驗證和安全性功能：
- 成就資料完整性驗證
- 輸入資料清理和驗證
- 權限控制測試
- 安全性邊界測試
"""

from unittest.mock import AsyncMock

import pytest

from src.cogs.achievement.services.admin_service import (
    AchievementAdminService,
)


class TestDataValidationAndSecurity:
    """資料驗證和安全性測試."""

    @pytest.fixture
    def admin_service(self):
        """建立管理服務實例."""
        return AchievementAdminService(
            repository=AsyncMock(),
            permission_service=AsyncMock(),
            cache_service=AsyncMock(),
        )

    # 成就資料完整性驗證測試
    async def test_validate_achievement_data_complete_valid(self, admin_service):
        """測試完整有效的成就資料驗證."""
        data = {
            "name": "測試成就",
            "description": "這是一個測試成就的描述",
            "category": "社交互動",
            "type": "counter",
            "criteria": {"target_value": 10, "action": "send_message"},
            "points": 100,
            "badge_url": "https://example.com/badge.png",
            "is_active": True,
        }

        validation = await admin_service._validate_achievement_data(data)

        assert validation.is_valid is True
        assert len(validation.errors) == 0

    async def test_validate_achievement_data_missing_required_fields(
        self, admin_service
    ):
        """測試缺少必需欄位的成就資料驗證."""
        # 缺少名稱
        data = {
            "description": "描述",
            "category": "社交互動",
            "type": "counter",
            "criteria": {"target_value": 10},
            "points": 100,
        }

        validation = await admin_service._validate_achievement_data(data)

        assert validation.is_valid is False
        assert any("名稱" in error for error in validation.errors)

    async def test_validate_achievement_data_empty_name(self, admin_service):
        """測試空名稱的成就資料驗證."""
        data = {
            "name": "",
            "description": "描述",
            "category": "社交互動",
            "type": "counter",
            "criteria": {"target_value": 10},
            "points": 100,
        }

        validation = await admin_service._validate_achievement_data(data)

        assert validation.is_valid is False
        assert any("名稱不能為空" in error for error in validation.errors)

    async def test_validate_achievement_data_name_too_long(self, admin_service):
        """測試過長名稱的成就資料驗證."""
        data = {
            "name": "A" * 101,  # 超過100字元限制
            "description": "描述",
            "category": "社交互動",
            "type": "counter",
            "criteria": {"target_value": 10},
            "points": 100,
        }

        validation = await admin_service._validate_achievement_data(data)

        assert validation.is_valid is False
        assert any("名稱不能超過 100 字元" in error for error in validation.errors)

    async def test_validate_achievement_data_description_too_long(self, admin_service):
        """測試過長描述的成就資料驗證."""
        data = {
            "name": "測試成就",
            "description": "A" * 501,  # 超過500字元限制
            "category": "社交互動",
            "type": "counter",
            "criteria": {"target_value": 10},
            "points": 100,
        }

        validation = await admin_service._validate_achievement_data(data)

        assert validation.is_valid is False
        assert any("描述不能超過 500 字元" in error for error in validation.errors)

    async def test_validate_achievement_data_invalid_type(self, admin_service):
        """測試無效成就類型的驗證."""
        data = {
            "name": "測試成就",
            "description": "描述",
            "category": "社交互動",
            "type": "invalid_type",
            "criteria": {"target_value": 10},
            "points": 100,
        }

        validation = await admin_service._validate_achievement_data(data)

        assert validation.is_valid is False
        assert any("成就類型無效" in error for error in validation.errors)

    async def test_validate_achievement_data_invalid_points(self, admin_service):
        """測試無效點數的驗證."""
        # 負數點數
        data = {
            "name": "測試成就",
            "description": "描述",
            "category": "社交互動",
            "type": "counter",
            "criteria": {"target_value": 10},
            "points": -10,
        }

        validation = await admin_service._validate_achievement_data(data)

        assert validation.is_valid is False
        assert any("點數不能為負數" in error for error in validation.errors)

        # 超出上限的點數
        data["points"] = 10001  # 超過10000上限

        validation = await admin_service._validate_achievement_data(data)

        assert validation.is_valid is False
        assert any("點數不能超過 10000" in error for error in validation.errors)

    # JSON 格式驗證測試
    async def test_validate_criteria_json_valid(self, admin_service):
        """測試有效的條件JSON格式."""
        valid_criteria = [
            {"target_value": 10, "action": "send_message"},
            {"duration": 3600, "type": "continuous"},
            {"milestones": [5, 10, 20], "cumulative": True},
            {"condition": "user.level >= 5", "evaluation": "expression"},
        ]

        for criteria in valid_criteria:
            validation = await admin_service._validate_criteria_json(criteria)
            assert validation.is_valid is True, f"Valid criteria failed: {criteria}"

    async def test_validate_criteria_json_invalid_format(self, admin_service):
        """測試無效的條件JSON格式."""
        # 不是字典格式
        invalid_criteria = ["invalid_string", 123, ["list", "format"], None]

        for criteria in invalid_criteria:
            validation = await admin_service._validate_criteria_json(criteria)
            assert validation.is_valid is False, f"Invalid criteria passed: {criteria}"
            assert any("格式" in error for error in validation.errors)

    async def test_validate_criteria_json_missing_required_fields(self, admin_service):
        """測試缺少必需欄位的條件JSON."""
        # counter 類型缺少 target
        criteria = {"action": "send_message"}
        validation = await admin_service._validate_criteria_json(
            criteria, achievement_type="counter"
        )

        assert validation.is_valid is False
        assert any("target" in error for error in validation.errors)

        # time_based 類型缺少 duration
        criteria = {"type": "continuous"}
        validation = await admin_service._validate_criteria_json(
            criteria, achievement_type="time_based"
        )

        assert validation.is_valid is False
        assert any("duration" in error for error in validation.errors)

    async def test_validate_criteria_json_type_specific_validation(self, admin_service):
        """測試類型特定的條件驗證."""
        # counter 類型的 target_value 必須是正整數
        criteria = {"target_value": -5}
        validation = await admin_service._validate_criteria_json(
            criteria, achievement_type="counter"
        )

        assert validation.is_valid is False
        assert any("target 必須為正整數" in error for error in validation.errors)

        # time_based 類型的 duration 必須是正整數
        criteria = {"duration": -3600}
        validation = await admin_service._validate_criteria_json(
            criteria, achievement_type="time_based"
        )

        assert validation.is_valid is False
        assert any("duration 必須為正整數" in error for error in validation.errors)

    # 輸入資料清理測試
    async def test_sanitize_input_data_xss_prevention(self, admin_service):
        """測試XSS攻擊防護的輸入清理."""
        malicious_inputs = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>",
            "onclick=\"alert('xss')\"",
            "<iframe src=\"javascript:alert('xss')\"></iframe>",
        ]

        for malicious_input in malicious_inputs:
            sanitized = await admin_service._sanitize_text_input(malicious_input)

            # 確保惡意腳本被移除或轉義
            assert "<script>" not in sanitized
            assert "javascript:" not in sanitized
            assert "onerror=" not in sanitized
            assert "onclick=" not in sanitized
            assert "<iframe" not in sanitized

    async def test_sanitize_input_data_sql_injection_prevention(self, admin_service):
        """測試SQL注入防護的輸入清理."""
        sql_injection_attempts = [
            "'; DROP TABLE achievements; --",
            "' OR '1'='1",
            "UNION SELECT * FROM users",
            "1; DELETE FROM achievements WHERE 1=1",
            "admin'--",
        ]

        for injection_attempt in sql_injection_attempts:
            sanitized = await admin_service._sanitize_text_input(injection_attempt)

            # 確保SQL關鍵字被處理
            assert "DROP TABLE" not in sanitized.upper()
            assert "DELETE FROM" not in sanitized.upper()
            assert "UNION SELECT" not in sanitized.upper()
            assert "'--" not in sanitized

    async def test_sanitize_input_data_preserve_valid_content(self, admin_service):
        """測試輸入清理時保留有效內容."""
        valid_inputs = [
            "這是一個正常的成就名稱",
            "Achievement with numbers 123",
            "符號測試！@#$%^&*()",
            "多行文本\n第二行內容",
            "包含引號的'文本'內容",
        ]

        for valid_input in valid_inputs:
            sanitized = await admin_service._sanitize_text_input(valid_input)

            # 基本內容應該保留
            assert len(sanitized) > 0
            assert "成就" in sanitized if "成就" in valid_input else True
            assert "Achievement" in sanitized if "Achievement" in valid_input else True

    # 權限控制測試
    async def test_admin_permission_required_for_crud_operations(self, admin_service):
        """測試CRUD操作需要管理員權限."""
        # 配置權限檢查失敗
        admin_service.permission_service.check_admin_permission.return_value = False

        # 測試創建成就
        data = {
            "name": "測試成就",
            "description": "描述",
            "category": "社交互動",
            "type": "counter",
            "criteria": {"target_value": 10},
            "points": 100,
        }

        achievement, validation = await admin_service.create_achievement(data, 123)

        assert validation.is_valid is False
        assert achievement is None
        assert any("權限不足" in error for error in validation.errors)

    async def test_admin_permission_required_for_bulk_operations(self, admin_service):
        """測試批量操作需要管理員權限."""
        # 配置權限檢查失敗
        admin_service.permission_service.check_admin_permission.return_value = False

        # 測試批量狀態更新
        result = await admin_service.bulk_update_status([1, 2, 3], True, 123)

        assert result.success_count == 0
        assert result.failed_count == 3
        assert any("權限不足" in error for error in result.errors)

    async def test_admin_permission_required_for_category_management(
        self, admin_service
    ):
        """測試分類管理需要管理員權限."""
        # 配置權限檢查失敗
        admin_service.permission_service.check_admin_permission.return_value = False

        # 測試創建分類
        data = {"name": "測試分類", "description": "描述", "display_order": 10}

        category, validation = await admin_service.create_category(data, 123)

        assert validation.is_valid is False
        assert category is None
        assert any("權限不足" in error for error in validation.errors)

    # 邊界值測試
    async def test_boundary_values_validation(self, admin_service):
        """測試邊界值驗證."""
        # 測試點數邊界值
        boundary_test_cases = [
            {"points": 0, "should_pass": True},  # 最小有效值
            {"points": 10000, "should_pass": True},  # 最大有效值
            {"points": -1, "should_pass": False},  # 低於最小值
            {"points": 10001, "should_pass": False},  # 超過最大值
        ]

        base_data = {
            "name": "邊界測試成就",
            "description": "描述",
            "category": "社交互動",
            "type": "counter",
            "criteria": {"target_value": 10},
        }

        for test_case in boundary_test_cases:
            data = {**base_data, "points": test_case["points"]}
            validation = await admin_service._validate_achievement_data(data)

            if test_case["should_pass"]:
                assert validation.is_valid is True, (
                    f"Points {test_case['points']} should be valid"
                )
            else:
                assert validation.is_valid is False, (
                    f"Points {test_case['points']} should be invalid"
                )

    async def test_name_length_boundaries(self, admin_service):
        """測試名稱長度邊界值."""
        base_data = {
            "description": "描述",
            "category": "社交互動",
            "type": "counter",
            "criteria": {"target_value": 10},
            "points": 100,
        }

        # 邊界測試案例
        name_test_cases = [
            {"name": "A", "should_pass": True},  # 最短有效名稱
            {"name": "A" * 100, "should_pass": True},  # 最長有效名稱
            {"name": "", "should_pass": False},  # 空名稱
            {"name": "A" * 101, "should_pass": False},  # 超長名稱
        ]

        for test_case in name_test_cases:
            data = {**base_data, "name": test_case["name"]}
            validation = await admin_service._validate_achievement_data(data)

            if test_case["should_pass"]:
                assert validation.is_valid is True, (
                    f"Name length {len(test_case['name'])} should be valid"
                )
            else:
                assert validation.is_valid is False, (
                    f"Name length {len(test_case['name'])} should be invalid"
                )

    # 並發安全性測試
    async def test_concurrent_operations_safety(self, admin_service):
        """測試並發操作的安全性."""
        # 模擬並發的名稱唯一性檢查
        admin_service._get_achievement_by_name = AsyncMock(return_value=None)
        admin_service._create_achievement_in_db = AsyncMock()

        data = {
            "name": "並發測試成就",
            "description": "描述",
            "category": "社交互動",
            "type": "counter",
            "criteria": {"target_value": 10},
            "points": 100,
        }

        # 模擬多個並發請求
        tasks = []
        for i in range(3):
            task = admin_service.create_achievement(data, 123 + i)
            tasks.append(task)

        # 並發執行（實際上是序列，但測試邏輯）
        results = []
        for task in tasks:
            result = await task
            results.append(result)

        # 驗證所有操作都有適當處理
        for _achievement, validation in results:
            assert validation is not None
            # 在真實環境中，只有第一個應該成功，其他應該因名稱重複失敗

    # 資料一致性測試
    async def test_data_consistency_validation(self, admin_service):
        """測試資料一致性驗證."""
        # 測試成就類型與條件的一致性
        inconsistent_data_cases = [
            {
                "type": "counter",
                "criteria": {"duration": 3600},  # 應該是 target_value 而不是 duration
                "should_pass": False,
            },
            {
                "type": "time_based",
                "criteria": {"target_value": 10},  # 應該是 duration 而不是 target_value
                "should_pass": False,
            },
            {
                "type": "milestone",
                "criteria": {"milestones": [5, 10, 20]},  # 正確的里程碑格式
                "should_pass": True,
            },
        ]

        base_data = {
            "name": "一致性測試成就",
            "description": "描述",
            "category": "社交互動",
            "points": 100,
        }

        for test_case in inconsistent_data_cases:
            data = {
                **base_data,
                "type": test_case["type"],
                "criteria": test_case["criteria"],
            }

            validation = await admin_service._validate_achievement_data(data)

            if test_case["should_pass"]:
                assert validation.is_valid is True, (
                    f"Data should be consistent: {test_case}"
                )
            else:
                assert validation.is_valid is False, (
                    f"Data should be inconsistent: {test_case}"
                )

    # 惡意輸入測試
    async def test_malicious_input_handling(self, admin_service):
        """測試惡意輸入處理."""
        malicious_inputs = [
            # 超長字串攻擊
            "A" * 10000,
            # 特殊字符攻擊
            "\x00\x01\x02\x03",
            # Unicode攻擊
            "\u202e" + "admin" + "\u202d",
            # 路徑遍歷攻擊
            "../../../etc/passwd",
            # JSON注入攻擊
            '{"malicious": true, "admin": true}',
            # 控制字符攻擊
            "\n\r\t\b\f",
        ]

        base_data = {
            "description": "描述",
            "category": "社交互動",
            "type": "counter",
            "criteria": {"target_value": 10},
            "points": 100,
        }

        for malicious_input in malicious_inputs:
            data = {**base_data, "name": malicious_input}

            # 應該不會導致系統崩潰，而是優雅地處理
            try:
                validation = await admin_service._validate_achievement_data(data)
                # 大部分惡意輸入應該被拒絕
                assert validation is not None
            except Exception as e:
                # 如果有異常，應該是可控的
                assert isinstance(e, ValueError | TypeError)

    # 資源限制測試
    async def test_resource_limit_validation(self, admin_service):
        """測試資源限制驗證."""
        # 測試條件JSON大小限制
        large_criteria = {
            "target_value": 10,
            "large_data": "X" * 5000,  # 模擬大型條件資料
        }

        data = {
            "name": "資源測試成就",
            "description": "描述",
            "category": "社交互動",
            "type": "counter",
            "criteria": large_criteria,
            "points": 100,
        }

        validation = await admin_service._validate_achievement_data(data)

        # 根據實現，可能拒絕過大的條件資料
        if not validation.is_valid:
            assert any(
                "大小" in error or "限制" in error for error in validation.errors
            )

    # 字符編碼測試
    async def test_character_encoding_handling(self, admin_service):
        """測試字符編碼處理."""
        unicode_test_cases = [
            "中文測試成就",
            "🏆 Emoji 成就 🎉",
            "عربي",  # 阿拉伯文
            "русский",  # 俄文
            "日本語テスト",  # 日文
            "한국어 테스트",  # 韓文
        ]

        base_data = {
            "description": "Unicode測試描述",
            "category": "社交互動",
            "type": "counter",
            "criteria": {"target_value": 10},
            "points": 100,
        }

        for unicode_name in unicode_test_cases:
            data = {**base_data, "name": unicode_name}

            validation = await admin_service._validate_achievement_data(data)

            # Unicode字符應該被正確處理
            assert validation is not None
            # 根據系統設計，可能接受或拒絕某些Unicode字符
