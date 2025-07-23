#!/usr/bin/env python3.12
"""
Discord ADR Bot Python 3.12 升級腳本

功能：
- 自動升級 Union[Type1, Type2] 為 Type1 | Type2
- 自動升級 Optional[Type] 為 Type | None
- 移除不必要的 __future__ import annotations
- 更新依賴套件到支援 Python 3.12 的版本
- 生成升級報告

作者：Discord ADR Bot 架構師
版本：v1.0
"""

import os
import re
import sys
import subprocess
import shutil
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import json
import time

class Python312Upgrader:
    """Python 3.12 升級器"""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.backup_dir = self.project_root / "backup_python312_upgrade"
        self.upgrade_log = []
        self.stats = {
            "files_processed": 0,
            "union_upgrades": 0,
            "optional_upgrades": 0,
            "future_imports_removed": 0,
            "errors": 0
        }
        
        # 正則表達式模式
        self.union_pattern = re.compile(r'Union\[([^\]]+)\]')
        self.optional_pattern = re.compile(r'Optional\[([^\]]+)\]')
        self.future_import_pattern = re.compile(r'from __future__ import annotations\s*\n?', re.MULTILINE)
        
    def backup_project(self) -> bool:
        """備份項目"""
        try:
            print("📦 正在備份項目...")
            
            if self.backup_dir.exists():
                shutil.rmtree(self.backup_dir)
            
            # 創建備份目錄
            self.backup_dir.mkdir(exist_ok=True)
            
            # 複製項目文件（排除不需要的目錄）
            exclude_dirs = {'.git', '__pycache__', '.pytest_cache', '.mypy_cache', 
                          'htmlcov', 'venv', 'venv312', 'backup_python312_upgrade'}
            
            for item in self.project_root.iterdir():
                if item.name in exclude_dirs:
                    continue
                
                if item.is_file():
                    shutil.copy2(item, self.backup_dir / item.name)
                elif item.is_dir():
                    shutil.copytree(item, self.backup_dir / item.name, 
                                  ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            
            print(f"✅ 項目已備份到: {self.backup_dir}")
            return True
            
        except Exception as e:
            print(f"❌ 備份失敗: {e}")
            return False
    
    def find_python_files(self) -> List[Path]:
        """查找所有 Python 文件"""
        python_files = []
        exclude_dirs = {'.git', '__pycache__', '.pytest_cache', '.mypy_cache', 
                       'htmlcov', 'venv', 'venv312', 'backup_python312_upgrade'}
        
        for root, dirs, files in os.walk(self.project_root):
            # 排除不需要的目錄
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            for file in files:
                if file.endswith('.py'):
                    python_files.append(Path(root) / file)
        
        return python_files
    
    def upgrade_union_syntax(self, content: str) -> Tuple[str, int]:
        """升級 Union 語法"""
        upgrades = 0
        
        def replace_union(match):
            nonlocal upgrades
            types_str = match.group(1)
            
            # 解析類型列表
            types = [t.strip() for t in types_str.split(',')]
            
            # 處理嵌套的 Union
            processed_types = []
            for t in types:
                if 'Union[' in t:
                    # 遞歸處理嵌套的 Union
                    nested_match = self.union_pattern.search(t)
                    if nested_match:
                        nested_types = [nt.strip() for nt in nested_match.group(1).split(',')]
                        processed_types.extend(nested_types)
                    else:
                        processed_types.append(t)
                else:
                    processed_types.append(t)
            
            # 去重並排序
            unique_types = list(dict.fromkeys(processed_types))
            unique_types.sort()
            
            # 生成新的語法
            new_syntax = ' | '.join(unique_types)
            upgrades += 1
            
            return new_syntax
        
        upgraded_content = self.union_pattern.sub(replace_union, content)
        return upgraded_content, upgrades
    
    def upgrade_optional_syntax(self, content: str) -> Tuple[str, int]:
        """升級 Optional 語法"""
        upgrades = 0
        
        def replace_optional(match):
            nonlocal upgrades
            inner_type = match.group(1).strip()
            upgrades += 1
            return f"{inner_type} | None"
        
        upgraded_content = self.optional_pattern.sub(replace_optional, content)
        return upgraded_content, upgrades
    
    def remove_future_imports(self, content: str) -> Tuple[str, int]:
        """移除 __future__ import annotations"""
        removed = 0
        
        def remove_import(match):
            nonlocal removed
            removed += 1
            return ""
        
        upgraded_content = self.future_import_pattern.sub(remove_import, content)
        return upgraded_content, removed
    
    def upgrade_file(self, file_path: Path) -> Dict:
        """升級單個文件"""
        result = {
            "file": str(file_path),
            "union_upgrades": 0,
            "optional_upgrades": 0,
            "future_imports_removed": 0,
            "success": False,
            "error": None
        }
        
        try:
            # 讀取文件內容
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            # 升級 Union 語法
            content, union_count = self.upgrade_union_syntax(content)
            result["union_upgrades"] = union_count
            
            # 升級 Optional 語法
            content, optional_count = self.upgrade_optional_syntax(content)
            result["optional_upgrades"] = optional_count
            
            # 移除 __future__ imports
            content, future_count = self.remove_future_imports(content)
            result["future_imports_removed"] = future_count
            
            # 如果有變更，寫回文件
            if content != original_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                print(f"✅ 已升級: {file_path}")
                print(f"   Union 升級: {union_count}, Optional 升級: {optional_count}, 移除 imports: {future_count}")
            
            result["success"] = True
            self.stats["files_processed"] += 1
            self.stats["union_upgrades"] += union_count
            self.stats["optional_upgrades"] += optional_count
            self.stats["future_imports_removed"] += future_count
            
        except Exception as e:
            result["error"] = str(e)
            self.stats["errors"] += 1
            print(f"❌ 升級失敗 {file_path}: {e}")
        
        return result
    
    def upgrade_all_files(self) -> List[Dict]:
        """升級所有文件"""
        print("🚀 開始升級 Python 文件...")
        
        python_files = self.find_python_files()
        print(f"📁 找到 {len(python_files)} 個 Python 文件")
        
        results = []
        for i, file_path in enumerate(python_files, 1):
            print(f"🔄 處理文件 {i}/{len(python_files)}: {file_path.name}")
            result = self.upgrade_file(file_path)
            results.append(result)
            
            # 每處理 10 個文件顯示進度
            if i % 10 == 0:
                print(f"📊 進度: {i}/{len(python_files)} ({i/len(python_files)*100:.1f}%)")
        
        return results
    
    def update_requirements(self) -> bool:
        """更新 requirement.txt"""
        try:
            print("📦 更新依賴套件...")
            
            requirements_file = self.project_root / "requirement.txt"
            if not requirements_file.exists():
                print("⚠️  requirement.txt 不存在")
                return False
            
            # 讀取當前依賴
            with open(requirements_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 更新關鍵套件到支援 Python 3.12 的版本
            updates = {
                'discord.py': 'discord.py>=2.5.2',
                'aiosqlite': 'aiosqlite>=0.21.0',
                'Pillow': 'Pillow>=11.2.1',
                'python-dotenv': 'python-dotenv>=1.1.0',
                'aiohttp': 'aiohttp>=3.11.18',
                'uvloop': 'uvloop>=0.19.0; sys_platform != "win32"',
                'colorama': 'colorama>=0.4.6; sys_platform == "win32"',
                'python-json-logger': 'python-json-logger>=2.0.7',
                'python-dateutil': 'python-dateutil>=2.8.2',
                'regex': 'regex>=2023.12.25',
                'pydantic': 'pydantic>=2.5.0',
                'cachetools': 'cachetools>=5.3.2',
                'watchdog': 'watchdog>=3.0.0',
                'zstandard': 'zstandard>=0.22.0',
                'cryptography': 'cryptography>=41.0.0',
                'requests': 'requests>=2.31.0',
                'tldextract': 'tldextract>=3.7.0',
                'tqdm': 'tqdm>=4.66.0',
                'pytest': 'pytest>=7.4.0',
                'pytest-asyncio': 'pytest-asyncio>=0.21.0',
                'pytest-mock': 'pytest-mock>=3.12.0',
                'black': 'black>=23.12.0',
                'flake8': 'flake8>=6.1.0',
                'mypy': 'mypy>=1.8.0',
                'sphinx': 'sphinx>=7.2.0',
                'sphinx-rtd-theme': 'sphinx-rtd-theme>=2.0.0',
                'gunicorn': 'gunicorn>=21.2.0',
                'supervisor': 'supervisor>=4.2.5',
                'psutil': 'psutil>=5.9.0',
                'prometheus-client': 'prometheus-client>=0.19.0',
                'ipython': 'ipython>=8.18.0',
                'jupyter': 'jupyter>=1.0.0',
                'bandit': 'bandit>=1.7.5',
                'safety': 'safety>=2.3.0'
            }
            
            # 應用更新
            updated_content = content
            for old_pattern, new_version in updates.items():
                # 使用正則表達式更新版本
                pattern = rf'^{old_pattern}[^=]*=([^;\n]+)'
                replacement = new_version
                updated_content = re.sub(pattern, replacement, updated_content, flags=re.MULTILINE)
            
            # 寫回文件
            with open(requirements_file, 'w', encoding='utf-8') as f:
                f.write(updated_content)
            
            print("✅ 依賴套件已更新")
            return True
            
        except Exception as e:
            print(f"❌ 更新依賴套件失敗: {e}")
            return False
    
    def install_dependencies(self) -> bool:
        """安裝依賴套件"""
        try:
            print("📦 安裝依賴套件...")
            
            # 激活虛擬環境並安裝依賴
            cmd = f"source venv312/bin/activate && pip install -r requirement.txt"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ 依賴套件安裝成功")
                return True
            else:
                print(f"❌ 依賴套件安裝失敗: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ 安裝依賴套件失敗: {e}")
            return False
    
    def run_tests(self) -> bool:
        """運行測試"""
        try:
            print("🧪 運行測試...")
            
            # 激活虛擬環境並運行測試
            cmd = f"source venv312/bin/activate && python -m pytest tests/ -v"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ 測試通過")
                return True
            else:
                print(f"⚠️ 測試失敗: {result.stdout}")
                return False
                
        except Exception as e:
            print(f"❌ 運行測試失敗: {e}")
            return False
    
    def generate_report(self, results: List[Dict]) -> str:
        """生成升級報告"""
        report = {
            "upgrade_summary": {
                "total_files": len(results),
                "successful_upgrades": len([r for r in results if r["success"]]),
                "failed_upgrades": len([r for r in results if not r["success"]]),
                "total_union_upgrades": self.stats["union_upgrades"],
                "total_optional_upgrades": self.stats["optional_upgrades"],
                "total_future_imports_removed": self.stats["future_imports_removed"],
                "errors": self.stats["errors"]
            },
            "detailed_results": results,
            "timestamp": time.time(),
            "python_version": "3.12.11"
        }
        
        # 保存報告
        report_file = self.project_root / "python312_upgrade_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        return str(report_file)
    
    def run_upgrade(self) -> bool:
        """執行完整升級流程"""
        print("🎯 Discord ADR Bot Python 3.12 升級開始")
        print("=" * 60)
        
        # 步驟 1: 備份項目
        if not self.backup_project():
            return False
        
        # 步驟 2: 升級文件語法
        results = self.upgrade_all_files()
        
        # 步驟 3: 更新依賴套件
        if not self.update_requirements():
            return False
        
        # 步驟 4: 安裝依賴套件
        if not self.install_dependencies():
            return False
        
        # 步驟 5: 運行測試
        test_success = self.run_tests()
        
        # 步驟 6: 生成報告
        report_file = self.generate_report(results)
        
        # 顯示總結
        print("\n" + "=" * 60)
        print("🎉 Python 3.12 升級完成")
        print("=" * 60)
        print(f"📊 升級統計:")
        print(f"   處理文件: {self.stats['files_processed']}")
        print(f"   Union 升級: {self.stats['union_upgrades']}")
        print(f"   Optional 升級: {self.stats['optional_upgrades']}")
        print(f"   移除 imports: {self.stats['future_imports_removed']}")
        print(f"   錯誤: {self.stats['errors']}")
        print(f"   測試結果: {'✅ 通過' if test_success else '❌ 失敗'}")
        print(f"   報告文件: {report_file}")
        print(f"   備份目錄: {self.backup_dir}")
        
        return True

def main():
    """主函數"""
    if len(sys.argv) != 2:
        print("使用方法: python3.12 upgrade_to_python312.py <項目根目錄>")
        sys.exit(1)
    
    project_root = sys.argv[1]
    
    if not os.path.exists(project_root):
        print(f"❌ 項目目錄不存在: {project_root}")
        sys.exit(1)
    
    upgrader = Python312Upgrader(project_root)
    success = upgrader.run_upgrade()
    
    if success:
        print("\n🎉 升級成功完成！")
        sys.exit(0)
    else:
        print("\n❌ 升級失敗！")
        sys.exit(1)

if __name__ == "__main__":
    main() 