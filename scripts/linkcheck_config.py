#!/usr/bin/env python3
"""
連結檢查配置管理工具
Task ID: T3 - 文檔連結有效性修復

提供便捷的配置管理功能，支援忽略規則的動態管理
"""

import argparse
import sys
from pathlib import Path
from typing import List


def add_ignore_rule(rule: str, project_root: str = ".") -> None:
    """添加忽略規則到 .linkcheckignore 文件"""
    ignore_file = Path(project_root) / ".linkcheckignore"
    
    # 檢查規則是否已存在
    existing_rules = []
    if ignore_file.exists():
        with open(ignore_file, 'r', encoding='utf-8') as f:
            existing_rules = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    if rule in existing_rules:
        print(f"⚠️  規則已存在: {rule}")
        return
    
    # 添加新規則
    with open(ignore_file, 'a', encoding='utf-8') as f:
        f.write(f"\n# 自動添加的規則\n{rule}\n")
    
    print(f"✅ 已添加忽略規則: {rule}")


def remove_ignore_rule(rule: str, project_root: str = ".") -> None:
    """從 .linkcheckignore 文件中移除忽略規則"""
    ignore_file = Path(project_root) / ".linkcheckignore"
    
    if not ignore_file.exists():
        print("❌ .linkcheckignore 文件不存在")
        return
    
    # 讀取所有行
    with open(ignore_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 過濾掉指定規則
    filtered_lines = []
    rule_found = False
    
    for line in lines:
        if line.strip() == rule:
            rule_found = True
            continue
        filtered_lines.append(line)
    
    if not rule_found:
        print(f"⚠️  規則不存在: {rule}")
        return
    
    # 寫回文件
    with open(ignore_file, 'w', encoding='utf-8') as f:
        f.writelines(filtered_lines)
    
    print(f"✅ 已移除忽略規則: {rule}")


def list_ignore_rules(project_root: str = ".") -> None:
    """列出當前的忽略規則"""
    ignore_file = Path(project_root) / ".linkcheckignore"
    
    if not ignore_file.exists():
        print("📝 尚未創建 .linkcheckignore 文件")
        return
    
    print("📋 當前的忽略規則:")
    print("-" * 50)
    
    rule_count = 0
    with open(ignore_file, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.rstrip()
            if not line:
                continue
            elif line.startswith('#'):
                print(f"💬 {line}")
            else:
                rule_count += 1
                print(f"{rule_count:2}. {line}")
    
    print("-" * 50)
    print(f"總計 {rule_count} 條規則")


def add_file_ignore(file_path: str, project_root: str = ".") -> None:
    """添加文件路徑到忽略清單"""
    # 標準化路徑
    if file_path.startswith('./'):
        file_path = file_path[2:]
    elif file_path.startswith('/'):
        file_path = file_path[1:]
    
    add_ignore_rule(file_path, project_root)


def add_url_ignore(url: str, project_root: str = ".") -> None:
    """添加URL模式到忽略清單"""
    # 如果是完整URL，轉換為模式
    if url.startswith('http://') or url.startswith('https://'):
        if '*' not in url:
            url += '*'  # 添加通配符
    
    add_ignore_rule(url, project_root)


def create_default_ignore_file(project_root: str = ".") -> None:
    """創建預設的 .linkcheckignore 文件"""
    ignore_file = Path(project_root) / ".linkcheckignore"
    
    if ignore_file.exists():
        print("⚠️  .linkcheckignore 文件已存在")
        return
    
    default_content = '''# 連結檢查忽略文件
# Task ID: T3 - 文檔連結有效性修復

# === 常見忽略模式 ===

# 本地開發URL
http://localhost*
https://localhost*

# 佔位符URL
http://example.com*
https://example.org*

# 模板變量
*{{*}}*
*${*}*

# === 項目特定忽略 ===

# 在此添加項目特定的忽略規則
'''
    
    with open(ignore_file, 'w', encoding='utf-8') as f:
        f.write(default_content)
    
    print(f"✅ 已創建預設忽略文件: {ignore_file}")


def validate_config(project_root: str = ".") -> None:
    """驗證配置文件的有效性"""
    project_path = Path(project_root)
    
    print("🔍 驗證連結檢查配置...")
    print("-" * 50)
    
    # 檢查配置文件
    config_files = [
        (".linkcheckrc.yml", "主配置文件"),
        (".github/linkcheck-ci.json", "CI配置文件"),
        (".linkcheckignore", "忽略規則文件")
    ]
    
    for file_path, description in config_files:
        full_path = project_path / file_path
        if full_path.exists():
            print(f"✅ {description}: {file_path}")
        else:
            print(f"❌ {description}: {file_path} (不存在)")
    
    print("-" * 50)
    
    # 驗證腳本可執行性
    script_path = project_path / "scripts" / "link_checker.py"
    if script_path.exists():
        print(f"✅ 連結檢查腳本: {script_path}")
    else:
        print(f"❌ 連結檢查腳本: {script_path} (不存在)")
    
    print("\n📊 配置驗證完成")


def main():
    """主程式入口"""
    parser = argparse.ArgumentParser(
        description="連結檢查配置管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用範例:
  %(prog)s init                           # 創建預設忽略文件
  %(prog)s add-rule "http://example.com*" # 添加URL忽略規則
  %(prog)s add-file "docs/draft.md"       # 添加文件忽略規則
  %(prog)s remove "http://example.com*"   # 移除忽略規則
  %(prog)s list                           # 列出所有規則
  %(prog)s validate                       # 驗證配置
        """
    )
    
    parser.add_argument("--project-root", default=".", help="項目根目錄")
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # 初始化命令
    subparsers.add_parser("init", help="創建預設忽略文件")
    
    # 添加規則命令
    add_parser = subparsers.add_parser("add-rule", help="添加忽略規則")
    add_parser.add_argument("rule", help="忽略規則")
    
    # 添加文件命令
    file_parser = subparsers.add_parser("add-file", help="添加文件忽略")
    file_parser.add_argument("file_path", help="要忽略的文件路徑")
    
    # 添加URL命令
    url_parser = subparsers.add_parser("add-url", help="添加URL忽略")
    url_parser.add_argument("url", help="要忽略的URL")
    
    # 移除規則命令
    remove_parser = subparsers.add_parser("remove", help="移除忽略規則")
    remove_parser.add_argument("rule", help="要移除的規則")
    
    # 列出規則命令
    subparsers.add_parser("list", help="列出忽略規則")
    
    # 驗證配置命令
    subparsers.add_parser("validate", help="驗證配置文件")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        if args.command == "init":
            create_default_ignore_file(args.project_root)
        
        elif args.command == "add-rule":
            add_ignore_rule(args.rule, args.project_root)
        
        elif args.command == "add-file":
            add_file_ignore(args.file_path, args.project_root)
        
        elif args.command == "add-url":
            add_url_ignore(args.url, args.project_root)
        
        elif args.command == "remove":
            remove_ignore_rule(args.rule, args.project_root)
        
        elif args.command == "list":
            list_ignore_rules(args.project_root)
        
        elif args.command == "validate":
            validate_config(args.project_root)
    
    except Exception as e:
        print(f"❌ 執行錯誤: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()