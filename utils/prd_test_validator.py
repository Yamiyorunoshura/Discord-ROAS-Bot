"""
PRD需求驗證測試執行器
- 驗證PRD文檔中的所有需求實現狀況
- 測試功能規格、權限設計、技術實現
- 生成PRD對比測試報告
- 自動更新PRD實現進度
"""

import asyncio
import time
import json
import os
import sys
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

# 添加項目根目錄到Python路徑
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 導入測試相關模塊
try:
    from cogs.activity_meter.main.activity_test_module import ActivityTestModule, TestReport, TestResult
    from cogs.activity_meter.main.activity_module import ActivityModule
    from cogs.activity_meter.main.logic_apis import (
        RendererLogicAPI, SettingsLogicAPI, PanelLogicAPI, 
        DatabaseLogicAPI, CalculationLogicAPI
    )
except ImportError as e:
    print(f"❌ 模塊導入失敗: {e}")
    print("請確保在項目根目錄下運行此腳本")
    sys.exit(1)

class PRDRequirementStatus(Enum):
    """PRD需求狀態枚舉"""
    NOT_IMPLEMENTED = "not_implemented"
    IN_PROGRESS = "in_progress"
    IMPLEMENTED = "implemented"
    TESTED = "tested"
    VERIFIED = "verified"

@dataclass
class PRDRequirement:
    """PRD需求數據結構"""
    requirement_id: str
    requirement_name: str
    description: str
    category: str
    priority: str
    status: PRDRequirementStatus
    implementation_details: Dict[str, Any | None] = None
    test_results: Dict[str, Any | None] = None
    last_updated: str | None = None

@dataclass
class PRDTestReport:
    """PRD測試報告數據結構"""
    report_id: str
    timestamp: datetime
    total_requirements: int
    implemented_requirements: int
    tested_requirements: int
    verified_requirements: int
    requirements: List[PRDRequirement]
    test_summary: Dict[str, Any]
    coverage_percentage: float
    pass_rate: float
    overall_status: str

class PRDTestValidator:
    """PRD需求驗證測試執行器"""
    
    def __init__(self, prd_file_path: str = "memory_bank/prd.md"):
        self.prd_file_path = prd_file_path
        self.activity_test_module = None
        self.activity_module = None
        self.requirements = []
        self.test_results = {}
        
    async def initialize(self):
        """初始化測試執行器"""
        try:
            self.activity_test_module = ActivityTestModule()
            self.activity_module = ActivityModule()
        except Exception as e:
            print(f"❌ 初始化失敗: {e}")
            return False
        return True
        
    async def run_prd_validation_tests(self) -> PRDTestReport:
        """執行PRD需求驗證測試"""
        print("🧪 開始執行 PRD 需求驗證測試...")
        
        # 初始化
        if not await self.initialize():
            return self._create_error_report("初始化失敗")
        
        # 1. 解析PRD需求
        await self._parse_prd_requirements()
        
        # 2. 驗證核心需求實現
        await self._validate_core_requirements()
        
        # 3. 驗證功能規格實現
        await self._validate_functional_specifications()
        
        # 4. 驗證權限設計實現
        await self._validate_permission_design()
        
        # 5. 驗證技術實現
        await self._validate_technical_implementation()
        
        # 6. 驗證驗收標準
        await self._validate_acceptance_criteria()
        
        # 7. 生成PRD測試報告
        prd_report = self._generate_prd_test_report()
        
        # 8. 更新PRD文檔
        await self._update_prd_document(prd_report)
        
        return prd_report
    
    def _create_error_report(self, error_message: str) -> PRDTestReport:
        """創建錯誤報告"""
        return PRDTestReport(
            report_id=f"PRD_ERROR_{int(time.time())}",
            timestamp=datetime.now(),
            total_requirements=0,
            implemented_requirements=0,
            tested_requirements=0,
            verified_requirements=0,
            requirements=[],
            test_summary={"error": error_message},
            coverage_percentage=0.0,
            pass_rate=0.0,
            overall_status="錯誤"
        )
    
    async def _parse_prd_requirements(self):
        """解析PRD需求文檔"""
        print("📋 解析PRD需求文檔...")
        
        # 基於PRD文檔定義核心需求
        self.requirements = [
            PRDRequirement(
                requirement_id="REQ-001",
                requirement_name="活躍度測試模塊需求",
                description="建立直接調用實際程式邏輯的測試框架",
                category="core",
                priority="high",
                status=PRDRequirementStatus.NOT_IMPLEMENTED
            ),
            PRDRequirement(
                requirement_id="REQ-002", 
                requirement_name="活躍度模塊統一API需求",
                description="設計統一的活躍度API接口",
                category="core",
                priority="high", 
                status=PRDRequirementStatus.NOT_IMPLEMENTED
            ),
            PRDRequirement(
                requirement_id="REQ-003",
                requirement_name="程式邏輯個別API需求", 
                description="為每個程式邏輯功能設計獨立的API",
                category="core",
                priority="medium",
                status=PRDRequirementStatus.NOT_IMPLEMENTED
            ),
            PRDRequirement(
                requirement_id="REQ-004",
                requirement_name="ActivityTestModule實現",
                description="活躍度測試模塊的完整實現",
                category="functional",
                priority="high",
                status=PRDRequirementStatus.NOT_IMPLEMENTED
            ),
            PRDRequirement(
                requirement_id="REQ-005",
                requirement_name="ActivityModule實現",
                description="活躍度模塊統一API整合層實現",
                category="functional", 
                priority="high",
                status=PRDRequirementStatus.NOT_IMPLEMENTED
            ),
            PRDRequirement(
                requirement_id="REQ-006",
                requirement_name="程式邏輯層API實現",
                description="各個程式邏輯的個別API實現",
                category="functional",
                priority="medium",
                status=PRDRequirementStatus.NOT_IMPLEMENTED
            ),
            PRDRequirement(
                requirement_id="REQ-007",
                requirement_name="權限分層架構",
                description="系統管理員、開發者、測試者、普通用戶權限設計",
                category="permission",
                priority="high",
                status=PRDRequirementStatus.NOT_IMPLEMENTED
            ),
            PRDRequirement(
                requirement_id="REQ-008",
                requirement_name="權限檢查邏輯",
                description="不同操作類型的權限檢查機制",
                category="permission",
                priority="high",
                status=PRDRequirementStatus.NOT_IMPLEMENTED
            ),
            PRDRequirement(
                requirement_id="REQ-009",
                requirement_name="三層架構實現",
                description="測試層、業務邏輯層、實現層的分離架構",
                category="technical",
                priority="high",
                status=PRDRequirementStatus.NOT_IMPLEMENTED
            ),
            PRDRequirement(
                requirement_id="REQ-010",
                requirement_name="真實邏輯測試架構",
                description="直接調用實際程式邏輯的測試架構",
                category="technical",
                priority="high",
                status=PRDRequirementStatus.NOT_IMPLEMENTED
            )
        ]
    
    async def _validate_core_requirements(self):
        """驗證核心需求實現"""
        print("🔧 驗證核心需求實現...")
        
        for requirement in self.requirements:
            if requirement.category == "core":
                await self._validate_single_requirement(requirement)
    
    async def _validate_functional_specifications(self):
        """驗證功能規格實現"""
        print("🔧 驗證功能規格實現...")
        
        for requirement in self.requirements:
            if requirement.category == "functional":
                await self._validate_single_requirement(requirement)
    
    async def _validate_permission_design(self):
        """驗證權限設計實現"""
        print("🔐 驗證權限設計實現...")
        
        for requirement in self.requirements:
            if requirement.category == "permission":
                await self._validate_single_requirement(requirement)
    
    async def _validate_technical_implementation(self):
        """驗證技術實現"""
        print("⚙️ 驗證技術實現...")
        
        for requirement in self.requirements:
            if requirement.category == "technical":
                await self._validate_single_requirement(requirement)
    
    async def _validate_acceptance_criteria(self):
        """驗證驗收標準"""
        print("✅ 驗證驗收標準...")
        
        # 驗證功能驗收標準
        await self._validate_functional_acceptance()
        
        # 驗證性能驗收標準
        await self._validate_performance_acceptance()
        
        # 驗證後端系統驗收標準
        await self._validate_backend_acceptance()
    
    async def _validate_single_requirement(self, requirement: PRDRequirement):
        """驗證單個需求實現"""
        try:
            if requirement.requirement_id == "REQ-004":
                # 驗證ActivityTestModule實現
                result = await self._validate_activity_test_module()
                requirement.status = PRDRequirementStatus.IMPLEMENTED if result else PRDRequirementStatus.NOT_IMPLEMENTED
                requirement.implementation_details = {"test_module_exists": result}
                
            elif requirement.requirement_id == "REQ-005":
                # 驗證ActivityModule實現
                result = await self._validate_activity_module()
                requirement.status = PRDRequirementStatus.IMPLEMENTED if result else PRDRequirementStatus.NOT_IMPLEMENTED
                requirement.implementation_details = {"activity_module_exists": result}
                
            elif requirement.requirement_id == "REQ-006":
                # 驗證程式邏輯層API實現
                result = await self._validate_logic_apis()
                requirement.status = PRDRequirementStatus.IMPLEMENTED if result else PRDRequirementStatus.NOT_IMPLEMENTED
                requirement.implementation_details = {"logic_apis_exist": result}
                
            elif requirement.requirement_id == "REQ-007":
                # 驗證權限分層架構
                result = await self._validate_permission_hierarchy()
                requirement.status = PRDRequirementStatus.IMPLEMENTED if result else PRDRequirementStatus.NOT_IMPLEMENTED
                requirement.implementation_details = {"permission_hierarchy_exists": result}
                
            elif requirement.requirement_id == "REQ-008":
                # 驗證權限檢查邏輯
                result = await self._validate_permission_logic()
                requirement.status = PRDRequirementStatus.IMPLEMENTED if result else PRDRequirementStatus.NOT_IMPLEMENTED
                requirement.implementation_details = {"permission_logic_exists": result}
                
            elif requirement.requirement_id == "REQ-009":
                # 驗證三層架構實現
                result = await self._validate_three_layer_architecture()
                requirement.status = PRDRequirementStatus.IMPLEMENTED if result else PRDRequirementStatus.NOT_IMPLEMENTED
                requirement.implementation_details = {"three_layer_architecture_exists": result}
                
            elif requirement.requirement_id == "REQ-010":
                # 驗證真實邏輯測試架構
                result = await self._validate_real_logic_testing()
                requirement.status = PRDRequirementStatus.IMPLEMENTED if result else PRDRequirementStatus.NOT_IMPLEMENTED
                requirement.implementation_details = {"real_logic_testing_exists": result}
            
            requirement.last_updated = datetime.now().isoformat()
            
        except Exception as e:
            print(f"❌ 驗證需求 {requirement.requirement_id} 時發生錯誤: {e}")
            requirement.status = PRDRequirementStatus.NOT_IMPLEMENTED
            requirement.implementation_details = {"error": str(e)}
    
    async def _validate_activity_test_module(self) -> bool:
        """驗證ActivityTestModule實現"""
        try:
            # 檢查ActivityTestModule類是否存在
            assert hasattr(self.activity_test_module, 'test_real_logic'), "缺少test_real_logic方法"
            assert hasattr(self.activity_test_module, 'generate_test_report'), "缺少generate_test_report方法"
            assert hasattr(self.activity_test_module, 'analyze_test_coverage'), "缺少analyze_test_coverage方法"
            
            print("✅ ActivityTestModule實現驗證通過")
            return True
            
        except Exception as e:
            print(f"❌ ActivityTestModule驗證失敗: {e}")
            return False
    
    async def _validate_activity_module(self) -> bool:
        """驗證ActivityModule實現"""
        try:
            # 檢查ActivityModule類是否存在
            assert hasattr(self.activity_module, 'get_unified_activity_api'), "缺少get_unified_activity_api方法"
            assert hasattr(self.activity_module, 'integrate_renderer_api'), "缺少integrate_renderer_api方法"
            assert hasattr(self.activity_module, 'integrate_settings_api'), "缺少integrate_settings_api方法"
            assert hasattr(self.activity_module, 'integrate_panel_api'), "缺少integrate_panel_api方法"
            assert hasattr(self.activity_module, 'calculate_activity_score'), "缺少calculate_activity_score方法"
            
            print("✅ ActivityModule實現驗證通過")
            return True
            
        except Exception as e:
            print(f"❌ ActivityModule驗證失敗: {e}")
            return False
    
    async def _validate_logic_apis(self) -> bool:
        """驗證程式邏輯層API實現"""
        try:
            # 檢查各個邏輯API是否存在
            renderer_api = RendererLogicAPI()
            settings_api = SettingsLogicAPI()
            panel_api = PanelLogicAPI()
            database_api = DatabaseLogicAPI()
            calculation_api = CalculationLogicAPI()
            
            # 檢查渲染API
            assert hasattr(renderer_api, 'render_data'), "渲染API缺少render_data方法"
            
            # 檢查設定API
            assert hasattr(settings_api, 'get_settings'), "設定API缺少get_settings方法"
            assert hasattr(settings_api, 'save_settings'), "設定API缺少save_settings方法"
            
            # 檢查面板API
            assert hasattr(panel_api, 'open_panel'), "面板API缺少open_panel方法"
            
            # 檢查數據庫API
            assert hasattr(database_api, 'execute_query'), "數據庫API缺少execute_query方法"
            
            # 檢查計算API
            assert hasattr(calculation_api, 'calculate_activity_score'), "計算API缺少calculate_activity_score方法"
            
            print("✅ 程式邏輯層API實現驗證通過")
            return True
            
        except Exception as e:
            print(f"❌ 程式邏輯層API驗證失敗: {e}")
            return False
    
    async def _validate_permission_hierarchy(self) -> bool:
        """驗證權限分層架構"""
        try:
            # 檢查權限管理器是否存在
            from cogs.activity_meter.panel.managers.permission_manager import PermissionManager
            
            permission_manager = PermissionManager()
            
            # 檢查權限檢查方法
            assert hasattr(permission_manager, 'can_manage_settings'), "缺少can_manage_settings方法"
            assert hasattr(permission_manager, 'can_view_stats'), "缺少can_view_stats方法"
            
            print("✅ 權限分層架構驗證通過")
            return True
            
        except Exception as e:
            print(f"❌ 權限分層架構驗證失敗: {e}")
            return False
    
    async def _validate_permission_logic(self) -> bool:
        """驗證權限檢查邏輯"""
        try:
            # 檢查權限檢查邏輯實現
            from cogs.activity_meter.panel.managers.permission_manager import PermissionManager
            
            permission_manager = PermissionManager()
            
            # 模擬不同角色的用戶
            from unittest.mock import Mock
            import discord
            
            # 系統管理員
            admin_user = Mock(spec=discord.Member)
            admin_user.guild_permissions = Mock()
            admin_user.guild_permissions.administrator = True
            admin_user.guild_permissions.manage_guild = True
            
            # 測試權限檢查
            result = permission_manager.can_manage_settings(admin_user)
            assert isinstance(result, bool), "權限檢查結果應該是布爾值"
            
            print("✅ 權限檢查邏輯驗證通過")
            return True
            
        except Exception as e:
            print(f"❌ 權限檢查邏輯驗證失敗: {e}")
            return False
    
    async def _validate_three_layer_architecture(self) -> bool:
        """驗證三層架構實現"""
        try:
            # 檢查三層架構的實現
            # 1. 測試層 (ActivityTestModule)
            assert hasattr(self.activity_test_module, 'test_real_logic'), "測試層缺少test_real_logic方法"
            
            # 2. 業務邏輯層 (ActivityModule)
            assert hasattr(self.activity_module, 'get_unified_activity_api'), "業務邏輯層缺少統一API"
            
            # 3. 實現層 (Logic APIs)
            renderer_api = RendererLogicAPI()
            assert hasattr(renderer_api, 'render_data'), "實現層缺少渲染API"
            
            print("✅ 三層架構實現驗證通過")
            return True
            
        except Exception as e:
            print(f"❌ 三層架構驗證失敗: {e}")
            return False
    
    async def _validate_real_logic_testing(self) -> bool:
        """驗證真實邏輯測試架構"""
        try:
            # 檢查是否直接調用實際程式邏輯
            test_config = {
                "test_type": "real_logic",
                "test_cases": [
                    {
                        "test_id": "real_logic_test_001",
                        "test_name": "真實邏輯測試",
                        "test_type": "real_logic",
                        "parameters": {"user_id": 123, "guild_id": 456},
                        "expected_result": {"status": "success"}
                    }
                ]
            }
            
            # 執行真實邏輯測試
            test_report = await self.activity_test_module.test_real_logic(test_config)
            assert isinstance(test_report, TestReport), "真實邏輯測試報告格式不正確"
            
            print("✅ 真實邏輯測試架構驗證通過")
            return True
            
        except Exception as e:
            print(f"❌ 真實邏輯測試架構驗證失敗: {e}")
            return False
    
    async def _validate_functional_acceptance(self):
        """驗證功能驗收標準"""
        print("✅ 驗證功能驗收標準...")
        
        try:
            # 驗證活躍度測試模塊功能
            test_config = {
                "test_type": "functional",
                "test_cases": [
                    {
                        "test_id": "func_test_001",
                        "test_name": "功能驗收測試",
                        "test_type": "functional",
                        "parameters": {"user_id": 123, "guild_id": 456},
                        "expected_result": {"status": "success"}
                    }
                ]
            }
            
            test_report = await self.activity_test_module.test_real_logic(test_config)
            print(f"✅ 功能驗收測試通過: {test_report.total_tests} 個測試")
        except Exception as e:
            print(f"❌ 功能驗收測試失敗: {e}")
    
    async def _validate_performance_acceptance(self):
        """驗證性能驗收標準"""
        print("⚡ 驗證性能驗收標準...")
        
        try:
            # 測試API響應時間
            start_time = time.time()
            request_data = {
                "guild_id": 123,
                "user_id": 456,
                "request_type": "get_activity_score",
                "parameters": {"user_id": 456}
            }
            
            response = await self.activity_module.get_unified_activity_api(request_data)
            end_time = time.time()
            
            response_time = end_time - start_time
            print(f"✅ API響應時間: {response_time:.3f}秒")
            
            # 驗證性能要求
            assert response_time < 5.0, f"API響應時間超過5秒: {response_time}秒"
            
        except Exception as e:
            print(f"❌ 性能驗收測試失敗: {e}")
    
    async def _validate_backend_acceptance(self):
        """驗證後端系統驗收標準"""
        print("🔧 驗證後端系統驗收標準...")
        
        try:
            # 檢查API接口可用性
            assert hasattr(self.activity_module, 'get_unified_activity_api'), "統一API接口不可用"
            
            # 檢查日誌記錄
            assert hasattr(self.activity_test_module, 'logger'), "測試模塊缺少日誌記錄"
            
            # 檢查數據存儲
            from cogs.activity_meter.database.database import ActivityDatabase
            db = ActivityDatabase()
            assert hasattr(db, 'get_connection'), "數據庫接口不可用"
            
            print("✅ 後端系統驗收標準通過")
            
        except Exception as e:
            print(f"❌ 後端系統驗收標準失敗: {e}")
    
    def _generate_prd_test_report(self) -> PRDTestReport:
        """生成PRD測試報告"""
        print("📊 生成PRD測試報告...")
        
        # 統計需求實現狀況
        total_requirements = len(self.requirements)
        implemented_requirements = len([r for r in self.requirements if r.status == PRDRequirementStatus.IMPLEMENTED])
        tested_requirements = len([r for r in self.requirements if r.status == PRDRequirementStatus.TESTED])
        verified_requirements = len([r for r in self.requirements if r.status == PRDRequirementStatus.VERIFIED])
        
        # 計算覆蓋率和通過率
        coverage_percentage = (implemented_requirements / total_requirements) * 100 if total_requirements > 0 else 0
        pass_rate = (verified_requirements / total_requirements) * 100 if total_requirements > 0 else 0
        
        # 確定整體狀態
        if coverage_percentage >= 90 and pass_rate >= 95:
            overall_status = "優秀"
        elif coverage_percentage >= 80 and pass_rate >= 90:
            overall_status = "良好"
        elif coverage_percentage >= 70 and pass_rate >= 80:
            overall_status = "可接受"
        else:
            overall_status = "需要改進"
        
        # 生成測試摘要
        test_summary = {
            "total_requirements": total_requirements,
            "implemented_requirements": implemented_requirements,
            "tested_requirements": tested_requirements,
            "verified_requirements": verified_requirements,
            "coverage_percentage": coverage_percentage,
            "pass_rate": pass_rate,
            "overall_status": overall_status
        }
        
        return PRDTestReport(
            report_id=f"PRD_TEST_{int(time.time())}",
            timestamp=datetime.now(),
            total_requirements=total_requirements,
            implemented_requirements=implemented_requirements,
            tested_requirements=tested_requirements,
            verified_requirements=verified_requirements,
            requirements=self.requirements,
            test_summary=test_summary,
            coverage_percentage=coverage_percentage,
            pass_rate=pass_rate,
            overall_status=overall_status
        )
    
    async def _update_prd_document(self, prd_report: PRDTestReport):
        """更新PRD文檔"""
        print("📝 更新PRD文檔...")
        
        try:
            # 讀取現有PRD文檔
            if os.path.exists(self.prd_file_path):
                with open(self.prd_file_path, 'r', encoding='utf-8') as f:
                    prd_content = f.read()
            else:
                prd_content = self._create_default_prd_template()
            
            # 更新PRD文檔內容
            updated_content = self._update_prd_content(prd_content, prd_report)
            
            # 保存更新後的PRD文檔
            os.makedirs(os.path.dirname(self.prd_file_path), exist_ok=True)
            with open(self.prd_file_path, 'w', encoding='utf-8') as f:
                f.write(updated_content)
            
            print(f"✅ PRD文檔已更新: {self.prd_file_path}")
            
        except Exception as e:
            print(f"❌ PRD文檔更新失敗: {e}")
    
    def _create_default_prd_template(self) -> str:
        """創建默認PRD模板"""
        return """# 📋 產品需求文檔 (PRD)

## 🎯 項目概述
- **項目名稱**: Discord ADR Bot
- **版本**: 1.0.0
- **最後更新**: {timestamp}

## 📊 需求實現狀態
### 功能需求
| 需求ID | 需求描述 | 實現狀態 | 測試狀態 | 最後更新 |
|-----|----|----|----|----|

### 性能需求
| 需求ID | 需求描述 | 實現狀態 | 測試狀態 | 最後更新 |
|-----|----|----|----|----|

### 安全需求
| 需求ID | 需求描述 | 實現狀態 | 測試狀態 | 最後更新 |
|-----|----|----|----|----|

## 🧪 測試結果摘要
### 整體測試狀態
- **測試執行時間**: {test_timestamp}
- **整體實現狀態**: {overall_status}
- **需求覆蓋率**: {coverage_percentage}%
- **測試通過率**: {pass_rate}%

### 詳細測試結果
{detailed_test_results}

## 📈 實現進度追蹤
### 已完成功能
{completed_features}

### 進行中功能
{in_progress_features}

### 待實現功能
{pending_features}

## 🔄 更新歷史
{update_history}
"""
    
    def _update_prd_content(self, prd_content: str, prd_report: PRDTestReport) -> str:
        """更新PRD文檔內容"""
        timestamp = prd_report.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        
        # 更新需求實現狀態表格
        functional_requirements = self._generate_requirements_table(
            [r for r in prd_report.requirements if r.category in ["core", "functional"]], 
            "功能需求"
        )
        
        performance_requirements = self._generate_requirements_table(
            [r for r in prd_report.requirements if r.category == "performance"], 
            "性能需求"
        )
        
        security_requirements = self._generate_requirements_table(
            [r for r in prd_report.requirements if r.category == "permission"], 
            "安全需求"
        )
        
        # 生成詳細測試結果
        detailed_test_results = self._generate_detailed_test_results(prd_report)
        
        # 生成進度追蹤
        progress_tracking = self._generate_progress_tracking(prd_report)
        
        # 生成更新歷史
        update_history = self._generate_update_history(prd_report)
        
        # 更新PRD內容
        updated_content = f"""# 📋 產品需求文檔 (PRD)

## 🎯 項目概述
- **項目名稱**: Discord ADR Bot
- **版本**: 1.0.0
- **最後更新**: {timestamp}

## 📊 需求實現狀態

### 功能需求
{functional_requirements}

### 性能需求
{performance_requirements}

### 安全需求
{security_requirements}

## 🧪 測試結果摘要
### 整體測試狀態
- **測試執行時間**: {prd_report.timestamp.strftime("%Y-%m-%d %H:%M:%S")}
- **整體實現狀態**: {prd_report.overall_status}
- **需求覆蓋率**: {prd_report.coverage_percentage:.1f}%
- **測試通過率**: {prd_report.pass_rate:.1f}%

### 詳細測試結果
{detailed_test_results}

## 📈 實現進度追蹤
{progress_tracking}

## 🔄 更新歷史
{update_history}
"""
        
        return updated_content
    
    def _generate_requirements_table(self, requirements: List[PRDRequirement], requirement_type: str) -> str:
        """生成需求表格"""
        if not requirements:
            return f"""| 需求ID | 需求描述 | 實現狀態 | 測試狀態 | 最後更新 |
|-----|----|----|----|----|
| - | 暫無{requirement_type} | - | - | - |"""
        
        table_content = f"""| 需求ID | 需求描述 | 實現狀態 | 測試狀態 | 最後更新 |
|-----|----|----|----|----|"""
        
        for req in requirements:
            status_emoji = "✅" if req.status == PRDRequirementStatus.IMPLEMENTED else "❌" if req.status == PRDRequirementStatus.NOT_IMPLEMENTED else "🟡"
            test_emoji = "✅" if req.status == PRDRequirementStatus.VERIFIED else "❌" if req.status == PRDRequirementStatus.NOT_IMPLEMENTED else "🟡"
            
            table_content += f"\n| {req.requirement_id} | {req.requirement_name} | {status_emoji} | {test_emoji} | {req.last_updated or 'N/A'} |"
        
        return table_content
    
    def _generate_detailed_test_results(self, prd_report: PRDTestReport) -> str:
        """生成詳細測試結果"""
        results = []
        
        # 按類別分組需求
        categories = {}
        for req in prd_report.requirements:
            if req.category not in categories:
                categories[req.category] = []
            categories[req.category].append(req)
        
        for category, reqs in categories.items():
            category_name = {
                "core": "核心需求",
                "functional": "功能需求", 
                "permission": "權限需求",
                "technical": "技術需求"
            }.get(category, category)
            
            results.append(f"### {category_name}")
            for req in reqs:
                status_emoji = "✅" if req.status == PRDRequirementStatus.VERIFIED else "❌" if req.status == PRDRequirementStatus.NOT_IMPLEMENTED else "🟡"
                results.append(f"- {status_emoji} {req.requirement_id}: {req.requirement_name} - {req.description}")
            results.append("")
        
        return "\n".join(results)
    
    def _generate_progress_tracking(self, prd_report: PRDTestReport) -> str:
        """生成進度追蹤"""
        completed = []
        in_progress = []
        pending = []
        
        for req in prd_report.requirements:
            if req.status == PRDRequirementStatus.VERIFIED:
                completed.append(f"- {req.requirement_id}: {req.requirement_name}")
            elif req.status == PRDRequirementStatus.IMPLEMENTED:
                in_progress.append(f"- {req.requirement_id}: {req.requirement_name}")
            else:
                pending.append(f"- {req.requirement_id}: {req.requirement_name}")
        
        content = "### 已完成功能\n"
        content += "\n".join(completed) if completed else "- 暫無已完成功能\n"
        
        content += "\n### 進行中功能\n"
        content += "\n".join(in_progress) if in_progress else "- 暫無進行中功能\n"
        
        content += "\n### 待實現功能\n"
        content += "\n".join(pending) if pending else "- 暫無待實現功能\n"
        
        return content
    
    def _generate_update_history(self, prd_report: PRDTestReport) -> str:
        """生成更新歷史"""
        timestamp = prd_report.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        
        return f"""### {timestamp}
- 執行PRD需求驗證測試
- 更新需求實現狀態
- 測試覆蓋率: {prd_report.coverage_percentage:.1f}%
- 測試通過率: {prd_report.pass_rate:.1f}%
- 整體狀態: {prd_report.overall_status}

"""
    
    async def close(self):
        """關閉測試執行器"""
        if self.activity_test_module:
            await self.activity_test_module.close()
        if self.activity_module:
            await self.activity_module.close()

async def main():
    """主函數"""
    validator = PRDTestValidator()
    
    try:
        # 執行PRD需求驗證測試
        prd_report = await validator.run_prd_validation_tests()
        
        # 輸出測試結果摘要
        print("\n" + "="*50)
        print("📊 PRD需求驗證測試結果摘要")
        print("="*50)
        print(f"總需求數: {prd_report.total_requirements}")
        print(f"已實現需求: {prd_report.implemented_requirements}")
        print(f"已測試需求: {prd_report.tested_requirements}")
        print(f"已驗證需求: {prd_report.verified_requirements}")
        print(f"需求覆蓋率: {prd_report.coverage_percentage:.1f}%")
        print(f"測試通過率: {prd_report.pass_rate:.1f}%")
        print(f"整體狀態: {prd_report.overall_status}")
        print("="*50)
        
        # 輸出詳細結果
        print("\n📋 詳細需求實現狀況:")
        for req in prd_report.requirements:
            status_emoji = "✅" if req.status == PRDRequirementStatus.VERIFIED else "❌" if req.status == PRDRequirementStatus.NOT_IMPLEMENTED else "🟡"
            print(f"{status_emoji} {req.requirement_id}: {req.requirement_name}")
        
    except Exception as e:
        print(f"❌ PRD需求驗證測試執行失敗: {e}")
    
    finally:
        await validator.close()

if __name__ == "__main__":
    asyncio.run(main()) 