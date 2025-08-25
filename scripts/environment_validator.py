#!/usr/bin/env python3
"""
環境檢查和驗證系統
Task ID: 1 - ROAS Bot v2.4.3 Docker啟動系統修復
"""

import os
import sys
import json
import asyncio
import subprocess
import logging
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime
from pathlib import Path
import yaml

# 配置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('environment_validation.log')
    ]
)
logger = logging.getLogger(__name__)

class EnvironmentValidator:
    """環境驗證器 - 確保所有必要條件都滿足"""
    
    def __init__(self, project_root: str = None):
        self.project_root = Path(project_root or os.getcwd())
        self.validation_results: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "checks": {},
            "overall_status": "pending",
            "errors": [],
            "warnings": []
        }
    
    def log_result(self, check_name: str, success: bool, message: str, details: Any = None):
        """記錄檢查結果"""
        self.validation_results["checks"][check_name] = {
            "success": success,
            "message": message,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        
        if success:
            logger.info(f"✅ {check_name}: {message}")
        else:
            logger.error(f"❌ {check_name}: {message}")
            self.validation_results["errors"].append(f"{check_name}: {message}")
    
    def log_warning(self, check_name: str, message: str):
        """記錄警告"""
        logger.warning(f"⚠️ {check_name}: {message}")
        self.validation_results["warnings"].append(f"{check_name}: {message}")
    
    def check_docker_installation(self) -> bool:
        """檢查Docker安裝狀態"""
        try:
            # 檢查Docker命令是否可用
            result = subprocess.run(['docker', '--version'], 
                                 capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                version_info = result.stdout.strip()
                self.log_result("docker_installation", True, 
                              f"Docker已正確安裝: {version_info}")
                
                # 檢查Docker服務是否運行
                try:
                    result = subprocess.run(['docker', 'info'], 
                                         capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        self.log_result("docker_service", True, "Docker服務運行正常")
                        return True
                    else:
                        self.log_result("docker_service", False, 
                                      "Docker服務未運行或無權限訪問")
                        return False
                except subprocess.TimeoutExpired:
                    self.log_result("docker_service", False, "Docker服務檢查超時")
                    return False
            else:
                self.log_result("docker_installation", False, "Docker未安裝或不在PATH中")
                return False
        except FileNotFoundError:
            self.log_result("docker_installation", False, "Docker命令未找到")
            return False
        except subprocess.TimeoutExpired:
            self.log_result("docker_installation", False, "Docker版本檢查超時")
            return False
    
    def check_docker_compose_installation(self) -> bool:
        """檢查Docker Compose安裝狀態"""
        try:
            # 嘗試新版本的docker compose命令
            result = subprocess.run(['docker', 'compose', 'version'], 
                                 capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                version_info = result.stdout.strip()
                self.log_result("docker_compose_installation", True, 
                              f"Docker Compose已正確安裝: {version_info}")
                return True
            
            # 嘗試舊版本的docker-compose命令
            result = subprocess.run(['docker-compose', '--version'], 
                                 capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                version_info = result.stdout.strip()
                self.log_result("docker_compose_installation", True, 
                              f"Docker Compose (舊版)已正確安裝: {version_info}")
                self.log_warning("docker_compose_version", 
                               "建議升級到Docker Compose V2 (docker compose)")
                return True
            
            self.log_result("docker_compose_installation", False, 
                          "Docker Compose未安裝")
            return False
        except FileNotFoundError:
            self.log_result("docker_compose_installation", False, 
                          "Docker Compose命令未找到")
            return False
        except subprocess.TimeoutExpired:
            self.log_result("docker_compose_installation", False, 
                          "Docker Compose版本檢查超時")
            return False
    
    def check_compose_file_syntax(self) -> bool:
        """檢查Docker Compose文件語法"""
        compose_files = [
            "docker-compose.dev.yml",
            "docker-compose.prod.yml", 
            "docker/compose.yaml"
        ]
        
        all_valid = True
        for compose_file in compose_files:
            file_path = self.project_root / compose_file
            if file_path.exists():
                try:
                    # 使用docker compose config驗證語法
                    result = subprocess.run(
                        ['docker', 'compose', '-f', str(file_path), 'config', '--quiet'],
                        capture_output=True, text=True, timeout=30
                    )
                    if result.returncode == 0:
                        self.log_result(f"compose_syntax_{compose_file.replace('/', '_')}", 
                                      True, f"{compose_file} 語法正確")
                    else:
                        self.log_result(f"compose_syntax_{compose_file.replace('/', '_')}", 
                                      False, f"{compose_file} 語法錯誤: {result.stderr}")
                        all_valid = False
                except subprocess.TimeoutExpired:
                    self.log_result(f"compose_syntax_{compose_file.replace('/', '_')}", 
                                  False, f"{compose_file} 語法檢查超時")
                    all_valid = False
            else:
                self.log_warning("missing_compose_file", f"{compose_file} 文件不存在")
        
        return all_valid
    
    def check_environment_variables(self) -> bool:
        """檢查必要環境變數"""
        required_vars = [
            "DISCORD_TOKEN",
        ]
        
        optional_vars = [
            "DISCORD_APPLICATION_ID",
            "ENVIRONMENT", 
            "DEBUG",
            "LOG_LEVEL",
            "DATABASE_URL",
            "MESSAGE_DATABASE_URL"
        ]
        
        all_present = True
        missing_required = []
        missing_optional = []
        
        for var in required_vars:
            if not os.getenv(var):
                missing_required.append(var)
                all_present = False
        
        for var in optional_vars:
            if not os.getenv(var):
                missing_optional.append(var)
        
        if missing_required:
            self.log_result("required_env_vars", False, 
                          f"缺少必要環境變數: {', '.join(missing_required)}")
        else:
            self.log_result("required_env_vars", True, "所有必要環境變數已設置")
        
        if missing_optional:
            self.log_warning("optional_env_vars", 
                           f"缺少可選環境變數: {', '.join(missing_optional)}")
        
        return all_present
    
    def check_file_structure(self) -> bool:
        """檢查專案文件結構"""
        required_files = [
            "Dockerfile",
            "main.py",
            "pyproject.toml",
            "core/__init__.py",
            "core/database_manager.py"
        ]
        
        required_dirs = [
            "core",
            "cogs", 
            "data",
            "logs",
            "scripts"
        ]
        
        all_present = True
        
        for file_path in required_files:
            full_path = self.project_root / file_path
            if not full_path.exists():
                self.log_result(f"file_structure_{file_path.replace('/', '_')}", 
                              False, f"缺少必要文件: {file_path}")
                all_present = False
            else:
                self.log_result(f"file_structure_{file_path.replace('/', '_')}", 
                              True, f"文件存在: {file_path}")
        
        for dir_path in required_dirs:
            full_path = self.project_root / dir_path
            if not full_path.exists():
                self.log_result(f"dir_structure_{dir_path}", False, 
                              f"缺少必要目錄: {dir_path}")
                # 嘗試創建目錄
                try:
                    full_path.mkdir(parents=True, exist_ok=True)
                    self.log_result(f"dir_creation_{dir_path}", True, 
                                  f"已創建目錄: {dir_path}")
                except Exception as e:
                    self.log_result(f"dir_creation_{dir_path}", False, 
                                  f"創建目錄失敗 {dir_path}: {str(e)}")
                    all_present = False
            else:
                self.log_result(f"dir_structure_{dir_path}", True, 
                              f"目錄存在: {dir_path}")
        
        return all_present
    
    def check_system_resources(self) -> bool:
        """檢查系統資源"""
        try:
            import shutil
            import psutil
            
            # 檢查磁盤空間
            total, used, free = shutil.disk_usage(str(self.project_root))
            free_gb = free // (1024**3)
            
            if free_gb < 5:
                self.log_result("disk_space", False, 
                              f"磁盤空間不足: {free_gb}GB 可用 (建議至少5GB)")
                return False
            else:
                self.log_result("disk_space", True, 
                              f"磁盤空間充足: {free_gb}GB 可用")
            
            # 檢查記憶體
            memory = psutil.virtual_memory()
            available_gb = memory.available // (1024**3)
            
            if available_gb < 2:
                self.log_result("memory", False, 
                              f"可用記憶體不足: {available_gb}GB (建議至少2GB)")
                return False
            else:
                self.log_result("memory", True, 
                              f"可用記憶體充足: {available_gb}GB")
            
            return True
            
        except ImportError:
            self.log_warning("system_resources", "psutil未安裝，跳過資源檢查")
            return True
        except Exception as e:
            self.log_result("system_resources", False, 
                          f"系統資源檢查失敗: {str(e)}")
            return False
    
    def check_network_connectivity(self) -> bool:
        """檢查網路連接"""
        import socket
        
        test_hosts = [
            ("discord.com", 443),
            ("docker.io", 443),
            ("github.com", 443)
        ]
        
        all_connected = True
        
        for host, port in test_hosts:
            try:
                socket.create_connection((host, port), timeout=10)
                self.log_result(f"network_{host.replace('.', '_')}", True, 
                              f"網路連接正常: {host}:{port}")
            except Exception as e:
                self.log_result(f"network_{host.replace('.', '_')}", False, 
                              f"網路連接失敗 {host}:{port}: {str(e)}")
                all_connected = False
        
        return all_connected
    
    def run_all_checks(self) -> Dict[str, Any]:
        """運行所有檢查"""
        logger.info("🔍 開始環境驗證...")
        
        checks = [
            ("Docker安裝檢查", self.check_docker_installation),
            ("Docker Compose安裝檢查", self.check_docker_compose_installation), 
            ("Compose文件語法檢查", self.check_compose_file_syntax),
            ("環境變數檢查", self.check_environment_variables),
            ("文件結構檢查", self.check_file_structure),
            ("系統資源檢查", self.check_system_resources),
            ("網路連接檢查", self.check_network_connectivity)
        ]
        
        passed_checks = 0
        total_checks = len(checks)
        
        for check_name, check_func in checks:
            logger.info(f"執行檢查: {check_name}")
            try:
                if check_func():
                    passed_checks += 1
            except Exception as e:
                logger.error(f"檢查執行失敗 {check_name}: {str(e)}")
                self.validation_results["errors"].append(f"{check_name}: 執行失敗 - {str(e)}")
        
        # 計算總體結果
        if passed_checks == total_checks:
            self.validation_results["overall_status"] = "success" 
            logger.info("✅ 所有環境檢查通過！")
        elif passed_checks >= total_checks * 0.8:
            self.validation_results["overall_status"] = "warning"
            logger.warning(f"⚠️ 部分檢查未通過 ({passed_checks}/{total_checks})")
        else:
            self.validation_results["overall_status"] = "failed"
            logger.error(f"❌ 多項檢查失敗 ({passed_checks}/{total_checks})")
        
        self.validation_results["passed_checks"] = passed_checks
        self.validation_results["total_checks"] = total_checks
        self.validation_results["completion_time"] = datetime.now().isoformat()
        
        return self.validation_results
    
    def save_results(self, filename: str = "environment_validation_report.json"):
        """保存檢查結果"""
        output_file = self.project_root / filename
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.validation_results, f, indent=2, ensure_ascii=False)
        logger.info(f"檢查結果已保存到: {output_file}")
    
    def generate_fix_suggestions(self) -> List[str]:
        """生成修復建議"""
        suggestions = []
        
        for error in self.validation_results["errors"]:
            if "Docker未安裝" in error:
                suggestions.append("安裝Docker Desktop: https://docs.docker.com/get-docker/")
            elif "Docker Compose未安裝" in error:
                suggestions.append("安裝Docker Compose: https://docs.docker.com/compose/install/")
            elif "DISCORD_TOKEN" in error:
                suggestions.append("設置DISCORD_TOKEN環境變數：export DISCORD_TOKEN=your_token_here")
            elif "磁盤空間不足" in error:
                suggestions.append("清理磁盤空間，確保至少5GB可用空間")
            elif "記憶體不足" in error:
                suggestions.append("關閉不必要的應用程序，確保至少2GB可用記憶體")
        
        return suggestions

def main():
    """主函數"""
    import argparse
    
    parser = argparse.ArgumentParser(description="ROAS Bot環境驗證工具")
    parser.add_argument("--project-root", type=str, help="專案根目錄路徑")
    parser.add_argument("--output", type=str, default="environment_validation_report.json", 
                       help="結果輸出文件名")
    parser.add_argument("--fix-suggestions", action="store_true", 
                       help="顯示修復建議")
    
    args = parser.parse_args()
    
    # 創建驗證器實例
    validator = EnvironmentValidator(project_root=args.project_root)
    
    # 運行所有檢查
    results = validator.run_all_checks()
    
    # 保存結果
    validator.save_results(args.output)
    
    # 顯示修復建議
    if args.fix_suggestions:
        suggestions = validator.generate_fix_suggestions()
        if suggestions:
            logger.info("\n🔧 修復建議:")
            for i, suggestion in enumerate(suggestions, 1):
                logger.info(f"  {i}. {suggestion}")
    
    # 設置退出碼
    if results["overall_status"] == "success":
        sys.exit(0)
    elif results["overall_status"] == "warning":
        sys.exit(1)
    else:
        sys.exit(2)

if __name__ == "__main__":
    main()