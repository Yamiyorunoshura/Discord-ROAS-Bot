"""
T10文件驗證測試 - 確保文件更新的一致性與正確性
Task ID: T10
"""

import pytest
import re
import os
from pathlib import Path


class TestT10DocumentationValidation:
    """T10任務文件一致性驗證測試"""
    
    @pytest.fixture
    def project_root(self):
        """獲取專案根目錄"""
        return Path(__file__).parent.parent
    
    @pytest.mark.unit
    def test_version_consistency_across_files(self, project_root):
        """驗證所有文件版本號碼一致性 - N-1要求"""
        expected_version = "v2.4.1"
        
        # 定義需要檢查的文件和其版本模式
        files_to_check = {
            "README.md": r"# Discord ADR Bot (v[\d.]+)",
            "CHANGELOG.md": r"# Discord ADR Bot (v[\d.]+)", # 只檢查標題版本
            "pyproject.toml": r'version = "([\d.]+)"',
            "docs/developer/developer_guide.md": r"\*\*版本：\*\* (v[\d.]+)",
            "docs/run-with-docker.md": r"\*\*版本\*\*: ([\d.]+)"
        }
        
        version_mismatches = []
        
        for file_path, pattern in files_to_check.items():
            full_path = project_root / file_path
            if full_path.exists():
                content = full_path.read_text(encoding='utf-8')
                matches = re.findall(pattern, content)
                
                for match in matches:
                    # 處理不同格式的版本號
                    version = match if match.startswith('v') else f'v{match}'
                    if version != expected_version:
                        version_mismatches.append(f"{file_path}: found {version}, expected {expected_version}")
        
        assert not version_mismatches, f"版本不一致: {'; '.join(version_mismatches)}"
    
    @pytest.mark.unit 
    def test_readme_python_version_requirement(self, project_root):
        """驗證README.md包含Python 3.13+需求 - F-1要求"""
        readme_path = project_root / "README.md"
        assert readme_path.exists(), "README.md不存在"
        
        content = readme_path.read_text(encoding='utf-8')
        
        # 檢查Python版本需求
        assert "Python 3.13+" in content, "README.md未包含Python 3.13+需求"
        
        # 檢查uv包管理器提及
        assert "uv" in content.lower(), "README.md未提及uv包管理器"
    
    @pytest.mark.unit
    def test_developer_guide_uv_setup(self, project_root):
        """驗證開發者指南包含uv環境設定 - F-2要求"""
        dev_guide_path = project_root / "docs/developer/developer_guide.md"
        assert dev_guide_path.exists(), "developer_guide.md不存在"
        
        content = dev_guide_path.read_text(encoding='utf-8')
        
        # 檢查Python 3.13需求
        assert "Python 3.13" in content, "開發者指南未包含Python 3.13需求"
        
        # 檢查uv相關內容
        assert "uv" in content.lower(), "開發者指南未包含uv相關內容"
        assert "uv sync" in content or "uv install" in content, "開發者指南未包含uv安裝步驟"
    
    @pytest.mark.unit
    def test_docker_guide_cross_platform_support(self, project_root):
        """驗證Docker指南包含跨平台支援 - F-3要求"""
        docker_guide_path = project_root / "docs/run-with-docker.md"
        assert docker_guide_path.exists(), "run-with-docker.md不存在"
        
        content = docker_guide_path.read_text(encoding='utf-8')
        
        # 檢查三平台支援
        platforms = ["Windows", "macOS", "Linux"]
        for platform in platforms:
            assert platform in content, f"Docker指南未包含{platform}平台說明"
        
        # 檢查啟動腳本提及
        assert "start.sh" in content and "start.ps1" in content, "Docker指南未包含啟動腳本說明"
    
    @pytest.mark.unit
    def test_error_codes_completeness(self, project_root):
        """驗證錯誤代碼文件完整性 - F-4要求"""
        error_codes_path = project_root / "docs/error-codes.md"
        assert error_codes_path.exists(), "error-codes.md不存在"
        
        content = error_codes_path.read_text(encoding='utf-8')
        
        # 檢查T8錯誤代碼系統相關內容
        required_sections = [
            "錯誤代碼命名規範",
            "錯誤代碼分類體系", 
            "使用方式",
            "一致性檢查"
        ]
        
        for section in required_sections:
            assert section in content, f"錯誤代碼文件缺少{section}章節"
        
        # 檢查錯誤代碼格式
        error_patterns = ["APP_", "SVC_", "ACH_", "ECO_", "GOV_", "DB_"]
        found_patterns = any(pattern in content for pattern in error_patterns)
        assert found_patterns, "錯誤代碼文件未包含預期的錯誤代碼格式"
    
    @pytest.mark.unit
    def test_troubleshooting_enhanced_content(self, project_root):
        """驗證疑難排解指引增強 - F-5要求"""
        troubleshooting_path = project_root / "docs/troubleshooting/troubleshooting.md"
        if not troubleshooting_path.exists():
            # 備用路徑
            troubleshooting_path = project_root / "docs/troubleshooting.md"
        
        assert troubleshooting_path.exists(), "troubleshooting.md不存在"
        
        content = troubleshooting_path.read_text(encoding='utf-8')
        
        # 檢查錯誤代碼查詢相關內容
        error_code_indicators = ["錯誤代碼", "error code", "錯誤查詢"]
        has_error_code_content = any(indicator in content for indicator in error_code_indicators)
        assert has_error_code_content, "疑難排解指引未包含錯誤代碼查詢內容"
    
    @pytest.mark.unit
    def test_changelog_v241_entry(self, project_root):
        """驗證CHANGELOG.md包含v2.4.1條目 - F-6要求"""
        changelog_path = project_root / "CHANGELOG.md"
        assert changelog_path.exists(), "CHANGELOG.md不存在"
        
        content = changelog_path.read_text(encoding='utf-8')
        
        # 檢查v2.4.1條目存在
        assert "v2.4.1" in content or "[2.4.1]" in content, "CHANGELOG.md未包含v2.4.1條目"
        
        # 檢查T1-T9任務相關變更記錄
        task_indicators = ["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9"]
        found_tasks = sum(1 for task in task_indicators if task in content)
        assert found_tasks >= 5, f"CHANGELOG.md僅包含{found_tasks}個任務的變更記錄，預期至少5個"
    
    @pytest.mark.integration
    def test_documentation_links_validity(self, project_root):
        """驗證文件間交叉引用連結有效性"""
        docs_dir = project_root / "docs"
        if not docs_dir.exists():
            pytest.skip("docs目錄不存在")
        
        # 收集所有markdown文件
        md_files = list(docs_dir.rglob("*.md"))
        md_files.append(project_root / "README.md")
        md_files.append(project_root / "CHANGELOG.md")
        
        broken_links = []
        
        for md_file in md_files:
            if not md_file.exists():
                continue
                
            content = md_file.read_text(encoding='utf-8')
            
            # 找到相對路徑連結
            relative_links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', content)
            
            for link_text, link_path in relative_links:
                if link_path.startswith(('http', 'https', '#')):
                    continue  # 跳過外部連結和錨點
                
                # 解析相對路徑
                if link_path.startswith('./'):
                    link_path = link_path[2:]
                
                target_path = (md_file.parent / link_path).resolve()
                
                if not target_path.exists():
                    broken_links.append(f"{md_file.name}: {link_text} -> {link_path}")
        
        assert not broken_links, f"發現斷開的連結: {'; '.join(broken_links)}"
    
    @pytest.mark.integration
    def test_markdown_syntax_validity(self, project_root):
        """驗證Markdown語法正確性"""
        md_files = [
            project_root / "README.md",
            project_root / "CHANGELOG.md",
            project_root / "docs/developer/developer_guide.md",
            project_root / "docs/run-with-docker.md",
            project_root / "docs/error-codes.md"
        ]
        
        syntax_errors = []
        
        for md_file in md_files:
            if not md_file.exists():
                continue
                
            content = md_file.read_text(encoding='utf-8')
            
            # 檢查標題格式
            lines = content.split('\n')
            for i, line in enumerate(lines, 1):
                if line.startswith('#'):
                    # 檢查標題後是否有空格
                    if not re.match(r'^#+\s', line) and line.strip() != '#':
                        syntax_errors.append(f"{md_file.name}:{i} 標題格式錯誤: {line[:50]}")
                
                # 檢查代碼塊配對
                if line.strip().startswith('```'):
                    # 這是簡化檢查，實際應該更複雜
                    pass
        
        assert not syntax_errors, f"發現Markdown語法錯誤: {'; '.join(syntax_errors)}"
    
    @pytest.mark.performance
    def test_documentation_operability(self, project_root):
        """驗證文件中的操作步驟可執行性 - N-3要求"""
        # 這是概念性測試，實際實現需要更複雜的環境設置
        
        # 檢查README.md中的安裝步驟是否包含必要的命令
        readme_path = project_root / "README.md"
        if readme_path.exists():
            content = readme_path.read_text(encoding='utf-8')
            
            # 檢查是否包含基本的安裝命令
            essential_commands = ["uv sync", "python main.py", "git clone"]
            found_commands = sum(1 for cmd in essential_commands if cmd in content)
            
            assert found_commands >= 2, f"README.md僅包含{found_commands}個必要命令，預期至少2個"
        
        # 檢查開發者指南中的環境設置步驟
        dev_guide_path = project_root / "docs/developer/developer_guide.md"  
        if dev_guide_path.exists():
            content = dev_guide_path.read_text(encoding='utf-8')
            
            # 檢查環境設置相關命令
            setup_commands = ["venv", "activate", "install", "test"]
            found_setup = sum(1 for cmd in setup_commands if cmd in content.lower())
            
            assert found_setup >= 2, f"開發者指南僅包含{found_setup}個設置命令，預期至少2個"