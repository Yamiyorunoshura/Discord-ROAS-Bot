#!/usr/bin/env python3
"""
Discord ADR Bot v1.6 部署腳本
============================

階段5任務5.3：部署優化與文檔更新的一部分
提供自動化部署功能

作者：Assistant
版本：1.6.0
更新：2025-01-25
"""

import os
import sys
import subprocess
import shutil
import json
import argparse
from pathlib import Path
from datetime import datetime

class DeploymentManager:
    """部署管理器"""
    
    def __init__(self):
        self.project_root = Path.cwd()
        self.venv_path = self.project_root / "venv"
        self.requirements_file = self.project_root / "requirement.txt"
        self.log_file = self.project_root / "deploy.log"
    
    def log(self, message, level="INFO"):
        """記錄日誌"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {level}: {message}"
        print(log_entry)
        
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(log_entry + "\n")
    
    def run_command(self, cmd, description):
        """運行命令"""
        self.log(f"執行: {description}")
        self.log(f"命令: {cmd}")
        
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                cwd=self.project_root
            )
            
            if result.returncode == 0:
                self.log(f"✅ {description} - 成功")
                if result.stdout:
                    self.log(f"輸出: {result.stdout.strip()}")
                return True
            else:
                self.log(f"❌ {description} - 失敗", "ERROR")
                if result.stderr:
                    self.log(f"錯誤: {result.stderr.strip()}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"💥 {description} - 異常: {e}", "ERROR")
            return False
    
    def check_environment(self):
        """檢查部署環境"""
        self.log("🔍 檢查部署環境...")
        
        # 檢查Python版本
        python_version = sys.version_info
        if python_version < (3, 8):
            self.log(f"❌ Python版本過低: {python_version.major}.{python_version.minor}", "ERROR")
            return False
        
        self.log(f"✅ Python版本: {python_version.major}.{python_version.minor}.{python_version.micro}")
        
        # 檢查必要文件
        required_files = [
            "main.py",
            "requirement.txt",
            "run_tests_optimized.py",
            "quality_check.py"
        ]
        
        for file_path in required_files:
            if not (self.project_root / file_path).exists():
                self.log(f"❌ 缺少必要文件: {file_path}", "ERROR")
                return False
            self.log(f"✅ 找到文件: {file_path}")
        
        # 檢查目錄結構
        required_dirs = [
            "cogs",
            "tests",
            "data",
            "logs",
            "dbs"
        ]
        
        for dir_path in required_dirs:
            dir_full_path = self.project_root / dir_path
            if not dir_full_path.exists():
                self.log(f"📁 創建目錄: {dir_path}")
                dir_full_path.mkdir(parents=True, exist_ok=True)
            else:
                self.log(f"✅ 目錄存在: {dir_path}")
        
        return True
    
    def setup_virtual_environment(self):
        """設置虛擬環境"""
        self.log("🐍 設置虛擬環境...")
        
        # 如果虛擬環境不存在，創建它
        if not self.venv_path.exists():
            self.log("創建虛擬環境...")
            if not self.run_command(f"python -m venv {self.venv_path}", "創建虛擬環境"):
                return False
        else:
            self.log("✅ 虛擬環境已存在")
        
        # 激活虛擬環境並安裝依賴
        if os.name == 'nt':  # Windows
            pip_cmd = f'"{self.venv_path}\\Scripts\\pip"'
        else:  # Unix/Linux/macOS
            pip_cmd = f'"{self.venv_path}/bin/pip"'
        
        # 升級pip
        if not self.run_command(f"{pip_cmd} install --upgrade pip", "升級pip"):
            return False
        
        # 安裝依賴
        if not self.run_command(f'{pip_cmd} install -r "{self.requirements_file}"', "安裝依賴"):
            return False
        
        return True
    
    def run_quality_checks(self):
        """運行品質檢查"""
        self.log("🔍 運行品質檢查...")
        
        # 激活虛擬環境
        if os.name == 'nt':  # Windows
            python_cmd = f'"{self.venv_path}\\Scripts\\python"'
        else:  # Unix/Linux/macOS
            python_cmd = f'"{self.venv_path}/bin/python"'
        
        # 運行品質檢查
        if not self.run_command(f"{python_cmd} quality_check.py", "代碼品質檢查"):
            self.log("⚠️ 品質檢查失敗，但繼續部署", "WARNING")
        
        return True
    
    def run_tests(self):
        """運行測試"""
        self.log("🧪 運行測試...")
        
        # 激活虛擬環境
        if os.name == 'nt':  # Windows
            python_cmd = f'"{self.venv_path}\\Scripts\\python"'
        else:  # Unix/Linux/macOS
            python_cmd = f'"{self.venv_path}/bin/python"'
        
        # 運行測試
        if not self.run_command(f"{python_cmd} run_tests_optimized.py", "運行測試套件"):
            self.log("⚠️ 測試失敗，但繼續部署", "WARNING")
        
        return True
    
    def create_systemd_service(self):
        """創建systemd服務文件"""
        self.log("⚙️ 創建systemd服務...")
        
        service_content = f"""[Unit]
Description=Discord ADR Bot v1.6
After=network.target

[Service]
Type=simple
User=discordbot
WorkingDirectory={self.project_root}
Environment=PATH={self.venv_path}/bin
ExecStart={self.venv_path}/bin/python main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
"""
        
        service_file = Path("/etc/systemd/system/discord-adr-bot.service")
        
        try:
            with open(service_file, "w") as f:
                f.write(service_content)
            self.log("✅ systemd服務文件已創建")
            
            # 重載systemd並啟用服務
            self.run_command("sudo systemctl daemon-reload", "重載systemd")
            self.run_command("sudo systemctl enable discord-adr-bot", "啟用服務")
            
            return True
        except PermissionError:
            self.log("⚠️ 無法創建systemd服務文件（需要sudo權限）", "WARNING")
            return False
        except Exception as e:
            self.log(f"❌ 創建systemd服務失敗: {e}", "ERROR")
            return False
    
    def create_backup(self):
        """創建備份"""
        self.log("💾 創建備份...")
        
        backup_dir = self.project_root / "backups"
        backup_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"discord_adr_bot_backup_{timestamp}.tar.gz"
        backup_path = backup_dir / backup_name
        
        # 創建備份
        if self.run_command(
            f'tar -czf "{backup_path}" --exclude=venv --exclude=__pycache__ --exclude=*.pyc .',
            "創建備份"
        ):
            self.log(f"✅ 備份已創建: {backup_path}")
            return True
        else:
            self.log("❌ 備份創建失敗", "ERROR")
            return False
    
    def deploy(self, skip_tests=False, skip_quality=False):
        """執行部署"""
        self.log("🚀 開始部署 Discord ADR Bot v1.6")
        
        # 檢查環境
        if not self.check_environment():
            self.log("❌ 環境檢查失敗", "ERROR")
            return False
        
        # 設置虛擬環境
        if not self.setup_virtual_environment():
            self.log("❌ 虛擬環境設置失敗", "ERROR")
            return False
        
        # 運行品質檢查
        if not skip_quality:
            self.run_quality_checks()
        
        # 運行測試
        if not skip_tests:
            self.run_tests()
        
        # 創建備份
        self.create_backup()
        
        # 創建systemd服務（如果在Linux上）
        if os.name == 'posix':
            self.create_systemd_service()
        
        self.log("🎉 部署完成！")
        self.log("📋 後續步驟:")
        self.log("   1. 配置 .env 文件")
        self.log("   2. 啟動服務: sudo systemctl start discord-adr-bot")
        self.log("   3. 檢查狀態: sudo systemctl status discord-adr-bot")
        self.log("   4. 查看日誌: sudo journalctl -u discord-adr-bot -f")
        
        return True

def main():
    """主函數"""
    parser = argparse.ArgumentParser(description="Discord ADR Bot v1.6 部署腳本")
    parser.add_argument("--skip-tests", action="store_true", help="跳過測試")
    parser.add_argument("--skip-quality", action="store_true", help="跳過品質檢查")
    
    args = parser.parse_args()
    
    deployer = DeploymentManager()
    
    try:
        success = deployer.deploy(
            skip_tests=args.skip_tests,
            skip_quality=args.skip_quality
        )
        
        if success:
            print("\n✅ 部署成功！")
            sys.exit(0)
        else:
            print("\n❌ 部署失敗！")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⚠️ 部署被用戶中斷")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 部署過程中發生異常: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 