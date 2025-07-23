#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自動Prompt生成器
基於記憶庫中的PRD文件自動生成標準化的prompt.md文件
"""

import os
import shutil
import time
from datetime import datetime
from typing import List, Dict, Optional
import re

class AutoPromptGenerator:
    """自動Prompt生成器類"""
    
    def __init__(self, project_path: str = "."):
        self.project_path = project_path
        self.memory_bank_path = os.path.join(project_path, "memory_bank")
        # 修正：prompt文件應該存儲在memory_bank目錄下
        self.prompt_file = os.path.join(project_path, "memory_bank", "prompt.md")
    
    def detect_prd_files(self) -> List[str]:
        """
        自動檢測記憶庫中的PRD文件
        返回: List[str] - PRD文件列表
        """
        prd_files = []
        if not os.path.exists(self.memory_bank_path):
            print(f"記憶庫目錄不存在: {self.memory_bank_path}")
            return prd_files
        
        for file in os.listdir(self.memory_bank_path):
            if 'prd' in file.lower() and file.endswith('.md'):
                prd_files.append(file)
        
        return prd_files
    
    def get_latest_prd_file(self, prd_files: List[str]) -> str | None:
        """
        獲取最新修改的PRD文件
        參數: prd_files - PRD文件列表
        返回: str | None - 最新的PRD文件名
        """
        if not prd_files:
            return None
        
        latest_file = None
        latest_time = 0
        
        for file in prd_files:
            file_path = os.path.join(self.memory_bank_path, file)
            if os.path.exists(file_path):
                file_time = os.path.getmtime(file_path)
                if file_time > latest_time:
                    latest_time = file_time
                    latest_file = file
        
        return latest_file
    
    def parse_prd_content(self, prd_file_path: str) -> Dict:
        """
        解析PRD文件內容，提取關鍵信息
        參數: prd_file_path - PRD文件路徑
        返回: dict - 解析後的PRD內容結構
        """
        try:
            with open(prd_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"讀取PRD文件失敗: {e}")
            return {}
        
        # 提取項目名稱
        project_name = self.extract_project_name(content)
        
        # 提取核心需求
        core_requirements = self.extract_core_requirements(content)
        
        # 提取技術規格
        technical_specs = self.extract_technical_specs(content)
        
        # 提取驗收標準
        acceptance_criteria = self.extract_acceptance_criteria(content)
        
        # 提取實施計劃
        implementation_plan = self.extract_implementation_plan(content)
        
        # 提取風險評估
        risk_assessment = self.extract_risk_assessment(content)
        
        return {
            'project_name': project_name,
            'core_requirements': core_requirements,
            'technical_specs': technical_specs,
            'acceptance_criteria': acceptance_criteria,
            'implementation_plan': implementation_plan,
            'risk_assessment': risk_assessment
        }
    
    def extract_project_name(self, content: str) -> str:
        """提取項目名稱"""
        # 查找PRD標題
        title_match = re.search(r'#\s*(.+?)\s*PRD', content, re.IGNORECASE)
        if title_match:
            return title_match.group(1).strip()
        
        # 查找項目概述
        overview_match = re.search(r'##\s*項目概述\s*\n\s*###\s*背景\s*\n(.+?)\s*Bot', content)
        if overview_match:
            return overview_match.group(1).strip()
        
        return "未知項目"
    
    def extract_core_requirements(self, content: str) -> List[str]:
        """提取核心需求"""
        requirements = []
        
        # 查找核心需求部分
        core_section = re.search(r'##\s*🎯\s*核心需求\s*\n(.*?)(?=\n##|\Z)', content, re.DOTALL)
        if core_section:
            section_content = core_section.group(1)
            
            # 提取需求項目
            req_matches = re.findall(r'###\s*\d+\.\s*(.+?)\s*\n(.*?)(?=\n###|\Z)', section_content, re.DOTALL)
            for title, description in req_matches:
                requirements.append(f"{title.strip()}: {description.strip()}")
        
        return requirements
    
    def extract_technical_specs(self, content: str) -> Dict:
        """提取技術規格"""
        specs = {}
        
        # 查找技術實現部分
        tech_section = re.search(r'##\s*🔧\s*技術實現\s*\n(.*?)(?=\n##|\Z)', content, re.DOTALL)
        if tech_section:
            section_content = tech_section.group(1)
            
            # 提取架構設計
            arch_match = re.search(r'###\s*架構設計\s*\n(.*?)(?=\n###|\Z)', section_content, re.DOTALL)
            if arch_match:
                specs['架構設計'] = arch_match.group(1).strip()
            
            # 提取核心組件
            components_match = re.search(r'###\s*核心組件\s*\n(.*?)(?=\n###|\Z)', section_content, re.DOTALL)
            if components_match:
                specs['核心組件'] = components_match.group(1).strip()
        
        return specs
    
    def extract_acceptance_criteria(self, content: str) -> List[str]:
        """提取驗收標準"""
        criteria = []
        
        # 查找驗收標準部分
        criteria_section = re.search(r'##\s*📝\s*驗收標準\s*\n(.*?)(?=\n##|\Z)', content, re.DOTALL)
        if criteria_section:
            section_content = criteria_section.group(1)
            
            # 提取功能驗收
            func_match = re.search(r'###\s*功能驗收\s*\n(.*?)(?=\n###|\Z)', section_content, re.DOTALL)
            if func_match:
                func_criteria = re.findall(r'- \[ \] (.+?)(?=\n-|\Z)', func_match.group(1))
                criteria.extend(func_criteria)
            
            # 提取性能驗收
            perf_match = re.search(r'###\s*性能驗收\s*\n(.*?)(?=\n###|\Z)', section_content, re.DOTALL)
            if perf_match:
                perf_criteria = re.findall(r'- \[ \] (.+?)(?=\n-|\Z)', perf_match.group(1))
                criteria.extend(perf_criteria)
        
        return criteria
    
    def extract_implementation_plan(self, content: str) -> Dict:
        """提取實施計劃"""
        plan = {}
        
        # 查找實施計劃部分
        plan_section = re.search(r'##\s*🚀\s*實施計劃\s*\n(.*?)(?=\n##|\Z)', content, re.DOTALL)
        if plan_section:
            section_content = plan_section.group(1)
            
            # 提取階段
            phases = re.findall(r'###\s*Phase\s*\d+:\s*(.+?)\s*\((\d+-\d+天\))\s*\n(.*?)(?=\n###|\Z)', section_content, re.DOTALL)
            for phase_name, duration, tasks in phases:
                plan[phase_name.strip()] = {
                    'duration': duration,
                    'tasks': re.findall(r'- \[ \] (.+?)(?=\n-|\Z)', tasks)
                }
        
        return plan
    
    def extract_risk_assessment(self, content: str) -> List[str]:
        """提取風險評估"""
        risks = []
        
        # 查找風險評估部分
        risk_section = re.search(r'風險評估與應對\s*\n(.*?)(?=\n##|\Z)', content, re.DOTALL)
        if risk_section:
            section_content = risk_section.group(1)
            
            # 提取風險項目
            risk_matches = re.findall(r'\|(.+?)\|(.+?)\|(.+?)\|(.+?)\|', section_content)
            for risk_type, risk_desc, impact, measure in risk_matches:
                if risk_type.strip() and risk_desc.strip():
                    risks.append(f"{risk_type.strip()}: {risk_desc.strip()}")
        
        return risks
    
    def check_and_backup_old_prompt(self) -> bool:
        """
        檢查是否存在舊的prompt文件並備份
        返回: bool - 是否需要覆蓋
        """
        # 確保memory_bank目錄存在
        os.makedirs(self.memory_bank_path, exist_ok=True)
        
        if os.path.exists(self.prompt_file):
            # 創建備份
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = f"{self.prompt_file}.backup_{timestamp}"
            shutil.copy2(self.prompt_file, backup_file)
            print(f"舊文件已備份至: {backup_file}")
            return True
        
        return False
    
    def generate_prd_based_prompt(self, prd_data: Dict) -> str:
        """
        基於PRD數據生成智能prompt
        參數: prd_data - 解析後的PRD數據
        返回: str - 生成的prompt內容
        """
        project_name = prd_data.get('project_name', '未知項目')
        core_requirements = prd_data.get('core_requirements', [])
        technical_specs = prd_data.get('technical_specs', {})
        acceptance_criteria = prd_data.get('acceptance_criteria', [])
        implementation_plan = prd_data.get('implementation_plan', {})
        risk_assessment = prd_data.get('risk_assessment', [])
        
        # 格式化核心需求
        formatted_requirements = ""
        for i, req in enumerate(core_requirements, 1):
            formatted_requirements += f"- **需求{i}**: {req}\n"
        
        # 格式化技術規格
        formatted_specs = ""
        for key, value in technical_specs.items():
            formatted_specs += f"- **{key}**: {value}\n"
        
        # 格式化驗收標準
        formatted_criteria = ""
        for i, criterion in enumerate(acceptance_criteria, 1):
            formatted_criteria += f"- [ ] {criterion}\n"
        
        # 格式化實施計劃
        formatted_plan = ""
        for phase_name, phase_data in implementation_plan.items():
            formatted_plan += f"### {phase_name} ({phase_data['duration']})\n"
            for task in phase_data['tasks']:
                formatted_plan += f"- [ ] {task}\n"
            formatted_plan += "\n"
        
        # 格式化風險評估
        formatted_risks = ""
        for i, risk in enumerate(risk_assessment, 1):
            formatted_risks += f"- **風險{i}**: {risk}\n"
        
        prompt_template = f"""# {project_name} 開發提示詞

## 🎯 功能概述
### 核心需求
{formatted_requirements}

### 業務價值
基於PRD文檔的業務需求，實現功能完整性和用戶體驗優化

### 用戶場景
根據PRD中定義的用戶使用場景和操作流程

## 📋 技術要求
### 功能規格
- **主要功能**: 實現PRD中定義的核心功能
- **次要功能**: 實現PRD中定義的輔助功能
- **可選功能**: 實現PRD中定義的擴展功能

### 技術規格
{formatted_specs}

### 性能要求
- **響應時間**: 根據PRD中的性能指標
- **並發處理**: 根據PRD中的並發要求
- **資源使用**: 根據PRD中的資源限制

## 🔧 實現指導
{formatted_plan}

## ✅ 驗收標準
### 功能驗收
{formatted_criteria}

### 性能驗收
- [ ] 響應時間符合PRD要求
- [ ] 並發處理能力達標
- [ ] 資源使用效率優化

### 安全驗收
- [ ] 數據安全保護措施完善
- [ ] 權限控制機制有效
- [ ] 錯誤處理機制健全

## 🧪 測試要求
### 單元測試
- 核心功能模組 - 預期覆蓋率 80%+
- 輔助功能模組 - 預期覆蓋率 70%+

### 整合測試
- 模組間協作測試 - 測試數據完整
- 端到端流程測試 - 測試場景全面

### 性能測試
- 負載測試場景
- 壓力測試場景

## 🚨 風險控制
### 技術風險
{formatted_risks}

### 依賴風險
- 外部庫依賴風險 - 版本鎖定和備選方案
- API接口變更風險 - 版本兼容性處理

## 📝 文檔要求
### 代碼文檔
- 所有函數和類包含完整的文檔字符串
- 複雜邏輯包含詳細的註釋說明

### 用戶文檔
- 功能使用說明文檔
- 配置和部署指南
- 故障排除手冊

---
*此提示詞基於記憶庫中的PRD文件自動生成，生成時間: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*
"""
        
        return prompt_template
    
    def auto_generate_prompt(self) -> bool:
        """
        自動從記憶庫PRD文件生成prompt的完整流程
        返回: bool - 是否成功生成
        """
        print("開始自動生成Prompt...")
        
        # 1. 檢測記憶庫中的PRD文件
        prd_files = self.detect_prd_files()
        
        if not prd_files:
            print("未找到PRD文件，無法生成prompt")
            return False
        
        print(f"找到 {len(prd_files)} 個PRD文件: {prd_files}")
        
        # 2. 選擇最新的PRD文件
        latest_prd = self.get_latest_prd_file(prd_files)
        if not latest_prd:
            print("無法確定最新的PRD文件")
            return False
        
        print(f"使用最新的PRD文件: {latest_prd}")
        
        # 3. 解析PRD文件內容
        prd_file_path = os.path.join(self.memory_bank_path, latest_prd)
        prd_data = self.parse_prd_content(prd_file_path)
        
        if not prd_data:
            print("PRD文件解析失敗")
            return False
        
        print("PRD文件解析成功")
        
        # 4. 檢查並備份舊的prompt文件
        self.check_and_backup_old_prompt()
        
        # 5. 生成新的prompt內容
        prompt_content = self.generate_prd_based_prompt(prd_data)
        
        # 6. 寫入標準化的prompt.md文件
        try:
            # 確保memory_bank目錄存在
            os.makedirs(os.path.dirname(self.prompt_file), exist_ok=True)
            
            with open(self.prompt_file, 'w', encoding='utf-8') as f:
                f.write(prompt_content)
            print(f"Prompt文件已生成: {self.prompt_file}")
            return True
        except Exception as e:
            print(f"寫入prompt文件失敗: {e}")
            return False

def main():
    """主函數"""
    generator = AutoPromptGenerator()
    success = generator.auto_generate_prompt()
    
    if success:
        print("✅ Prompt生成完成！")
    else:
        print("❌ Prompt生成失敗！")

if __name__ == "__main__":
    main()