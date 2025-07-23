#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 驅動的智能 Prompt 生成器
直接使用 Desktop Commander 和 Context7 工具
"""

import os
import json
import re
import subprocess
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path


class AIPromptGenerator:
    """AI 驅動的智能提示詞生成器"""
    
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.project_analysis = {}
        self.tech_stack = {}
        self.requirements = {}
        self.context7_docs = {}
        
    def analyze_project_with_tools(self) -> Dict[str, Any]:
        """使用 Desktop Commander 工具分析項目"""
        analysis = {
            "project_type": "unknown",
            "tech_stack": [],
            "framework": None,
            "language": None,
            "build_tool": None,
            "database": None,
            "has_tests": False,
            "has_docs": False,
            "files": []
        }
        
        try:
            # 使用 Desktop Commander 列出目錄
            result = subprocess.run([
                "mcp_Desktop_Commander_list_directory",
                "--path", str(self.project_path)
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                # 解析目錄內容
                files = result.stdout.strip().split("\n")
                analysis["files"] = files
                
                # 檢測項目類型
                for file in files:
                    if "package.json" in file:
                        analysis["project_type"] = "nodejs"
                        analysis["build_tool"] = "npm"
                    elif "requirements.txt" in file:
                        analysis["project_type"] = "python"
                        analysis["build_tool"] = "pip"
                    elif "pom.xml" in file:
                        analysis["project_type"] = "java"
                        analysis["build_tool"] = "maven"
                    elif "Cargo.toml" in file:
                        analysis["project_type"] = "rust"
                        analysis["build_tool"] = "cargo"
                    elif "tests" in file or "test" in file:
                        analysis["has_tests"] = True
                    elif "README" in file:
                        analysis["has_docs"] = True
                        
        except Exception as e:
            print(f"分析項目結構時出錯: {e}")
            
        return analysis
    
    def search_tech_stack_with_tools(self) -> Dict[str, Any]:
        """使用 Desktop Commander 工具搜索技術棧"""
        tech_stack = {
            "frameworks": [],
            "libraries": [],
            "databases": [],
            "tools": []
        }
        
        try:
            # 搜索 package.json
            result = subprocess.run([
                "mcp_Desktop_Commander_search_files",
                "--path", str(self.project_path),
                "--pattern", "package.json"
            ], capture_output=True, text=True)
            
            if result.returncode == 0 and result.stdout.strip():
                # 讀取 package.json
                package_file = self.project_path / "package.json"
                if package_file.exists():
                    with open(package_file, "r") as f:
                        package_data = json.load(f)
                        dependencies = package_data.get("dependencies", {})
                        dev_dependencies = package_data.get("devDependencies", {})
                        
                        # 分析依賴
                        all_deps = {**dependencies, **dev_dependencies}
                        
                        # 分類技術棧
                        for dep, version in all_deps.items():
                            if dep in ["react", "vue", "angular", "svelte"]:
                                tech_stack["frameworks"].append(f"{dep}@{version}")
                            elif dep in ["express", "fastify", "koa"]:
                                tech_stack["frameworks"].append(f"{dep}@{version}")
                            elif dep in ["mysql", "postgresql", "mongodb", "redis"]:
                                tech_stack["databases"].append(f"{dep}@{version}")
                            else:
                                tech_stack["libraries"].append(f"{dep}@{version}")
                                
        except Exception as e:
            print(f"搜索技術棧時出錯: {e}")
            
        return tech_stack
    
    def extract_requirements_with_tools(self) -> Dict[str, Any]:
        """使用 Desktop Commander 工具提取需求"""
        requirements = {
            "core_features": [],
            "technical_requirements": [],
            "performance_requirements": [],
            "security_requirements": [],
            "user_scenarios": []
        }
        
        try:
            # 搜索 README 文件
            result = subprocess.run([
                "mcp_Desktop_Commander_search_files",
                "--path", str(self.project_path),
                "--pattern", "README"
            ], capture_output=True, text=True)
            
            if result.returncode == 0 and result.stdout.strip():
                # 讀取 README 文件
                readme_files = ["README.md", "README.txt", "readme.md"]
                for readme_file in readme_files:
                    readme_path = self.project_path / readme_file
                    if readme_path.exists():
                        # 使用 Desktop Commander 讀取文件
                        result = subprocess.run([
                            "mcp_Desktop_Commander_read_file",
                            "--path", str(readme_path)
                        ], capture_output=True, text=True)
                        
                        if result.returncode == 0:
                            content = result.stdout
                            
                            # 提取核心功能
                            feature_patterns = [
                                r"## Features\n(.*?)(?=\n##|\n#|\Z)",
                                r"## 功能\n(.*?)(?=\n##|\n#|\Z)",
                                r"## 特性\n(.*?)(?=\n##|\n#|\Z)"
                            ]
                            
                            for pattern in feature_patterns:
                                matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
                                if matches:
                                    features = matches[0].strip().split("\n")
                                    requirements["core_features"] = [
                                        f.strip("- ").strip() for f in features 
                                        if f.strip().startswith("-")
                                    ]
                                    break
                                    
                            # 提取技術要求
                            tech_patterns = [
                                r"## 技術要求\n(.*?)(?=\n##|\n#|\Z)",
                                r"## Technical Requirements\n(.*?)(?=\n##|\n#|\Z)"
                            ]
                            
                            for pattern in tech_patterns:
                                matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
                                if matches:
                                    tech_reqs = matches[0].strip().split("\n")
                                    requirements["technical_requirements"] = [
                                        req.strip("- ").strip() for req in tech_reqs 
                                        if req.strip().startswith("-")
                                    ]
                                    break
                                    
                        break
                        
        except Exception as e:
            print(f"提取需求時出錯: {e}")
            
        return requirements
    
    def get_context7_docs(self, library_name: str) -> Dict[str, Any]:
        """使用 Context7 工具獲取技術文檔"""
        docs = {
            "library": library_name,
            "docs": "",
            "best_practices": [],
            "api_reference": ""
        }
        
        try:
            # 使用 Context7 解析庫 ID
            result = subprocess.run([
                "mcp_Context7_resolve-library-id",
                "--libraryName", library_name
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                # 解析結果獲取庫 ID
                # 這裡需要根據實際的 Context7 工具輸出格式進行解析
                library_id = f"/{library_name}/{library_name}"  # 示例格式
                
                # 獲取庫文檔
                result = subprocess.run([
                    "mcp_Context7_get-library-docs",
                    "--context7CompatibleLibraryID", library_id,
                    "--topic", "getting-started",
                    "--tokens", "3000"
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    docs["docs"] = result.stdout
                    
        except Exception as e:
            print(f"獲取 {library_name} 文檔時出錯: {e}")
            
        return docs
    
    def generate_web_app_prompt(self) -> str:
        """生成 Web 應用提示詞"""
        return """# [Web 應用名稱] 開發提示詞

## 🎯 項目概述
### 項目背景
[項目背景和目標描述]

### 核心需求
{core_features}

### 業務價值
[項目實現的業務價值和目標]

### 用戶場景
[主要使用場景和用戶流程]

## 📋 技術要求
### 功能規格
- **主要功能**：[核心功能點]
- **次要功能**：[輔助功能點]
- **可選功能**：[擴展功能點]

### 技術規格
- **前端框架**：{framework}
- **狀態管理**：[Redux/Vuex/NgRx]
- **路由**：[React Router/Vue Router]
- **樣式**：[CSS/SCSS/Styled Components]
- **構建工具**：[Webpack/Vite]
- **測試框架**：[Jest/Vitest]

### 性能要求
- **響應時間**：[預期響應時間]
- **並發處理**：[並發用戶數]
- **資源使用**：[內存、CPU 限制]
- **SEO 優化**：[SEO 要求]

## 🔧 實現指導
### 階段 1：基礎架構搭建
- 初始化項目結構
- 配置開發環境
- 設置構建工具
- 配置測試框架

### 階段 2：核心功能開發
- 實現主要功能模組
- 開發用戶界面
- 實現狀態管理
- 配置路由系統

### 階段 3：優化與測試
- 性能優化
- 代碼測試
- 用戶體驗優化
- 部署準備

## ✅ 驗收標準
### 功能驗收
- [ ] 所有核心功能正常運作
- [ ] 用戶界面響應良好
- [ ] 狀態管理正確
- [ ] 路由功能正常

### 性能驗收
- [ ] 頁面加載時間 < 3秒
- [ ] 交互響應時間 < 100ms
- [ ] 支持 100+ 並發用戶
- [ ] 通過 Lighthouse 測試

### 安全驗收
- [ ] 輸入驗證完整
- [ ] XSS 防護到位
- [ ] CSRF 防護實現
- [ ] 敏感數據加密

## 🧪 測試要求
### 單元測試
- 組件測試覆蓋率：80%+
- 工具函數測試覆蓋率：90%+
- 使用 Jest 和 React Testing Library

### 整合測試
- API 整合測試
- 用戶流程測試
- 使用 Cypress 進行 E2E 測試

### 性能測試
- 使用 Lighthouse 進行性能測試
- 目標分數：90+
- 測試加載時間和交互響應

## 🚨 風險控制
### 技術風險
- **框架版本兼容性** - 使用穩定版本，避免 beta 版本
- **第三方依賴風險** - 定期更新依賴，監控安全漏洞
- **瀏覽器兼容性** - 測試主流瀏覽器，提供 polyfill

### 依賴風險
- **API 服務依賴** - 實現降級方案，監控服務狀態
- **CDN 依賴** - 提供本地備份，監控 CDN 可用性

## 📝 文檔要求
### 代碼文檔
- 所有組件和函數添加 JSDoc 註釋
- 複雜邏輯添加詳細註釋
- 維護 API 文檔

### 用戶文檔
- 編寫用戶使用指南
- 提供功能說明文檔
- 維護部署文檔

## 🔧 開發工具
### 推薦工具
- **IDE**：VS Code 或 WebStorm
- **調試工具**：React Developer Tools
- **性能監控**：Lighthouse CI
- **代碼質量**：ESLint + Prettier

### 最佳實踐
- 使用 TypeScript 進行類型檢查
- 實現組件懶加載
- 使用 React.memo 優化渲染
- 實現錯誤邊界處理

## 📚 技術文檔參考
{context7_docs}
"""
    
    def generate_api_service_prompt(self) -> str:
        """生成 API 服務提示詞"""
        return """# [API 服務名稱] 開發提示詞

## 🎯 項目概述
### 項目背景
[API 服務的背景和目標]

### 核心需求
{core_features}

### 業務價值
[API 服務的業務價值]

### 用戶場景
[API 使用場景和客戶端]

## 📋 技術要求
### 功能規格
- **主要功能**：[核心 API 功能]
- **次要功能**：[輔助 API 功能]
- **可選功能**：[擴展 API 功能]

### 技術規格
- **框架**：{framework}
- **數據庫**：[MySQL/PostgreSQL/MongoDB]
- **緩存**：[Redis/Memcached]
- **消息隊列**：[RabbitMQ/Apache Kafka]
- **認證**：[JWT/OAuth2]
- **文檔**：[Swagger/OpenAPI]

### 性能要求
- **響應時間**：平均 < 200ms
- **並發處理**：支持 1000+ QPS
- **可用性**：99.9%+
- **擴展性**：水平擴展支持

## 🔧 實現指導
### 階段 1：基礎架構
- 初始化項目結構
- 配置數據庫連接
- 設置認證系統
- 配置日誌系統

### 階段 2：核心 API 開發
- 實現 RESTful API
- 開發業務邏輯
- 實現數據驗證
- 配置錯誤處理

### 階段 3：優化與部署
- 性能優化
- 安全加固
- 監控配置
- 部署準備

## ✅ 驗收標準
### 功能驗收
- [ ] 所有 API 端點正常響應
- [ ] 數據驗證正確
- [ ] 錯誤處理完善
- [ ] 認證授權正常

### 性能驗收
- [ ] 響應時間 < 200ms
- [ ] 支持 1000+ QPS
- [ ] 內存使用穩定
- [ ] CPU 使用率 < 70%

### 安全驗收
- [ ] 輸入驗證完整
- [ ] SQL 注入防護
- [ ] 認證機制安全
- [ ] 敏感數據加密

## 🧪 測試要求
### 單元測試
- API 端點測試覆蓋率：90%+
- 業務邏輯測試覆蓋率：95%+
- 使用 Jest 或 pytest

### 整合測試
- 數據庫整合測試
- 第三方服務整合測試
- API 端到端測試

### 性能測試
- 使用 Apache Bench 或 wrk
- 測試並發性能
- 測試響應時間

## 🚨 風險控制
### 技術風險
- **數據庫性能** - 優化查詢，添加索引
- **第三方服務依賴** - 實現降級方案
- **安全漏洞** - 定期安全審計

### 依賴風險
- **數據庫服務** - 配置主從備份
- **外部 API** - 實現重試機制

## 📝 文檔要求
### API 文檔
- 使用 Swagger/OpenAPI 生成文檔
- 提供詳細的 API 說明
- 包含請求/響應示例

### 部署文檔
- 編寫部署指南
- 提供環境配置說明
- 維護監控文檔

## 🔧 開發工具
### 推薦工具
- **IDE**：VS Code 或 IntelliJ IDEA
- **API 測試**：Postman 或 Insomnia
- **性能監控**：Prometheus + Grafana
- **日誌管理**：ELK Stack

### 最佳實踐
- 使用環境變量管理配置
- 實現請求限流
- 添加健康檢查端點
- 使用結構化日誌

## 📚 技��文檔參考
{context7_docs}
"""
    
    def generate_mobile_app_prompt(self) -> str:
        """生成移動應用提示詞"""
        return """# [移動應用名稱] 開發提示詞

## 🎯 項目概述
### 項目背景
[移動應用的背景和目標]

### 核心需求
{core_features}

### 業務價值
[移動應用的業務價值]

### 用戶場景
[主要使用場景和用戶流程]

## 📋 技術要求
### 功能規格
- **主要功能**：[核心應用功能]
- **次要功能**：[輔助應用功能]
- **可選功能**：[擴展應用功能]

### 技術規格
- **框架**：{framework}
- **狀態管理**：[Redux/MobX/Zustand]
- **導航**：[React Navigation]
- **存儲**：[AsyncStorage/Realm]
- **推送通知**：[Firebase/OneSignal]
- **分析**：[Analytics SDK]

### 性能要求
- **啟動時間**：< 3秒
- **內存使用**：< 100MB
- **電池消耗**：優化電池使用
- **網絡優化**：離線功能支持

## 🔧 實現指導
### 階段 1：基礎架構
- 初始化項目結構
- 配置開發環境
- 設置導航系統
- 配置狀態管理

### 階段 2：核心功能開發
- 實現主要功能模組
- 開發用戶界面
- 實現數據存儲
- 配置網絡請求

### 階段 3：優化與測試
- 性能優化
- 平台適配
- 用戶體驗優化
- 應用商店準備

## ✅ 驗收標準
### 功能驗收
- [ ] 所有核心功能正常運作
- [ ] 用戶界面響應良好
- [ ] 數據同步正確
- [ ] 離線功能正常

### 性能驗收
- [ ] 啟動時間 < 3秒
- [ ] 內存使用 < 100MB
- [ ] 電池消耗優化
- [ ] 網絡請求優化

### 安全驗收
- [ ] 數據加密存儲
- [ ] 網絡通信安全
- [ ] 用戶隱私保護
- [ ] 代碼混淆

## 🧪 測試要求
### 單元測試
- 組件測試覆蓋率：80%+
- 工具函數測試覆蓋率：90%+
- 使用 Jest 和 React Native Testing Library

### 整合測試
- API 整合測試
- 用戶流程測試
- 使用 Detox 進行 E2E 測試

### 性能測試
- 使用 Flipper 進行性能分析
- 測試內存使用和電池消耗
- 測試網絡請求性能

## 🚨 風險控制
### 技術風險
- **平台兼容性** - 測試 iOS 和 Android
- **第三方依賴** - 選擇穩定版本
- **性能問題** - 定期性能優化

### 依賴風險
- **API 服務依賴** - 實現離線模式
- **推送服務依賴** - 提供備選方案

## 📝 文檔要求
### 代碼文檔
- 所有組件添加註釋
- 複雜邏輯詳細說明
- 維護 API 文檔

### 用戶文檔
- 編寫用戶使用指南
- 提供功能說明文檔
- 維護部署文檔

## 🔧 開發工具
### 推薦工具
- **IDE**：VS Code 或 Android Studio
- **調試工具**：Flipper
- **性能監控**：Firebase Performance
- **代碼質量**：ESLint + Prettier

### 最佳實踐
- 使用 TypeScript 進行類型檢查
- 實現組件懶加載
- 使用 React.memo 優化渲染
- 實現錯誤邊界處理

## 📚 技術文檔參考
{context7_docs}
"""
    
    def select_template(self) -> str:
        """根據項目類型選擇模板"""
        project_type = self.project_analysis.get("project_type", "unknown")
        framework = self.project_analysis.get("framework")
        
        if project_type == "nodejs":
            if framework in ["react", "vue", "angular"]:
                return self.generate_web_app_prompt()
            elif framework == "express":
                return self.generate_api_service_prompt()
            else:
                return self.generate_web_app_prompt()
        elif project_type == "python":
            return self.generate_api_service_prompt()
        elif project_type == "java":
            return self.generate_api_service_prompt()
        else:
            return self.generate_web_app_prompt()
    
    def fill_template(self, template: str) -> str:
        """填充模板內容"""
        # 填充核心功能
        core_features = "\n".join([
            f"- {feature}" for feature in self.requirements.get("core_features", [])
        ])
        template = template.replace("{core_features}", core_features)
        
        # 填充技術棧
        tech_stack = self.project_analysis.get("framework", "未知框架")
        template = template.replace("{framework}", tech_stack)
        
        # 填充 Context7 文檔
        context7_docs = ""
        for lib_name, docs in self.context7_docs.items():
            if docs.get("docs"):
                context7_docs += f"\n### {lib_name}\n{docs['docs'][:500]}...\n"
        
        template = template.replace("{context7_docs}", context7_docs)
        
        return template
    
    def generate_prompt_with_tools(self) -> str:
        """使用工具生成完整的提示詞"""
        print("🔍 開始分析項目...")
        
        # 1. 使用 Desktop Commander 分析項目
        self.project_analysis = self.analyze_project_with_tools()
        print(f"✅ 項目類型: {self.project_analysis.get('project_type', 'unknown')}")
        
        # 2. 使用 Desktop Commander 搜索技術棧
        self.tech_stack = self.search_tech_stack_with_tools()
        print(f"✅ 技術棧: {self.tech_stack.get('frameworks', [])}")
        
        # 3. 使用 Desktop Commander 提取需求
        self.requirements = self.extract_requirements_with_tools()
        print(f"✅ 核心功能: {len(self.requirements.get('core_features', []))} 個")
        
        # 4. 使用 Context7 獲取技術文檔
        print("📚 獲取技術文檔...")
        for framework in self.tech_stack.get("frameworks", []):
            lib_name = framework.split("@")[0]
            self.context7_docs[lib_name] = self.get_context7_docs(lib_name)
        
        # 5. 選擇模板
        template = self.select_template()
        
        # 6. 填充內容
        filled_template = self.fill_template(template)
        
        return filled_template
    
    def save_prompt_with_tools(self, prompt_content: str, output_path: str = "prompt.md"):
        """使用 Desktop Commander 工具保存提示詞"""
        output_file = self.project_path / output_path
        
        try:
            # 使用 Desktop Commander 寫入文件
            result = subprocess.run([
                "mcp_Desktop_Commander_write_file",
                "--path", str(output_file),
                "--content", prompt_content
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"✅ 提示詞已生成: {output_file}")
                return str(output_file)
            else:
                print(f"❌ 保存文件失敗: {result.stderr}")
                return None
                
        except Exception as e:
            print(f"❌ 保存文件時出錯: {e}")
            return None


def main():
    """主函數"""
    import sys
    
    if len(sys.argv) < 2:
        print("使用方法: python ai_prompt_generator.py <項目路徑> [輸出文件]")
        sys.exit(1)
    
    project_path = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else "prompt.md"
    
    # 創建 AI 生成器
    generator = AIPromptGenerator(project_path)
    
    # 使用工具生成提示詞
    prompt_content = generator.generate_prompt_with_tools()
    
    # 使用工具保存文件
    generator.save_prompt_with_tools(prompt_content, output_file)
    
    print("🎉 AI 提示詞生成完成！")


if __name__ == "__main__":
    main()