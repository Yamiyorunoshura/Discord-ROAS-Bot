#!/usr/bin/env python3
"""
Discord ADR Bot v2.1 - 智能跨平台啟動腳本
支援自動虛擬環境檢測與創建，兼容 Windows/Linux/macOS
"""

import os
import platform
import subprocess
import sys
from pathlib import Path

# ANSI 顏色代碼 (跨平台支援)
if platform.system() == "Windows":
    try:
        import colorama

        colorama.init()
        COLORS_ENABLED = True
    except ImportError:
        COLORS_ENABLED = False
else:
    COLORS_ENABLED = True


class Colors:
    if COLORS_ENABLED:
        RED = "\033[91m"
        GREEN = "\033[92m"
        YELLOW = "\033[93m"
        BLUE = "\033[94m"
        MAGENTA = "\033[95m"
        CYAN = "\033[96m"
        WHITE = "\033[97m"
        BOLD = "\033[1m"
        UNDERLINE = "\033[4m"
        END = "\033[0m"
    else:
        RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = BOLD = UNDERLINE = (
            END
        ) = ""


def print_banner():
    """顯示啟動橫幅"""
    banner = f"""
{Colors.CYAN}{Colors.BOLD}╔══════════════════════════════════════════════════════════════╗
║                Discord ADR Bot v2.0                         ║
║                智能跨平台啟動腳本                             ║
║           支援自動虛擬環境檢測與創建                          ║
╚══════════════════════════════════════════════════════════════╝{Colors.END}
"""
    print(banner)


def log_info(message: str):
    """資訊日誌"""
    print(f"{Colors.BLUE}ℹ️  {message}{Colors.END}")


def log_success(message: str):
    """成功日誌"""
    print(f"{Colors.GREEN}✅ {message}{Colors.END}")


def log_warning(message: str):
    """警告日誌"""
    print(f"{Colors.YELLOW}⚠️  {message}{Colors.END}")


def log_error(message: str):
    """錯誤日誌"""
    print(f"{Colors.RED}❌ {message}{Colors.END}")


def log_step(step: int, total: int, message: str):
    """步驟日誌"""
    print(f"{Colors.MAGENTA}[{step}/{total}] {message}{Colors.END}")


def run_command(
    command: list[str], capture_output: bool = True, check: bool = True
) -> subprocess.CompletedProcess:
    """執行系統命令"""
    try:
        log_info(f"執行命令: {' '.join(command)}")
        result = subprocess.run(
            command,
            capture_output=capture_output,
            text=True,
            check=check,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode == 0 and result.stdout:
            log_success("命令執行成功")
        return result
    except subprocess.CalledProcessError as e:
        log_error(f"命令執行失敗: {e}")
        if e.stderr:
            print(f"{Colors.RED}錯誤輸出: {e.stderr}{Colors.END}")
        raise
    except FileNotFoundError:
        log_error(f"找不到命令: {command[0]}")
        raise


def check_python_version() -> bool:
    """檢查 Python 版本"""
    log_step(1, 7, "檢查 Python 版本")

    current_version = sys.version_info
    required_version = (3, 10)

    if current_version >= required_version:
        log_success(
            f"Python 版本: {current_version.major}.{current_version.minor}.{current_version.micro}"
        )
        return True
    else:
        log_error(
            f"需要 Python {required_version[0]}.{required_version[1]}+，當前版本: {current_version.major}.{current_version.minor}"
        )
        return False


def check_uv_installed() -> bool:
    """檢查 uv 是否已安裝"""
    log_step(2, 7, "檢查 uv 包管理器")

    try:
        result = run_command(["uv", "--version"])
        log_success(f"uv 已安裝: {result.stdout.strip()}")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        log_warning("uv 未安裝")
        return False


def install_uv() -> bool:
    """安裝 uv"""
    log_info("正在安裝 uv...")

    system = platform.system().lower()

    try:
        if system == "windows":
            # Windows 使用 PowerShell
            command = [
                "powershell",
                "-Command",
                "Invoke-RestMethod -Uri https://astral.sh/uv/install.ps1 | Invoke-Expression",
            ]
        else:
            # Unix 系統使用 curl
            command = ["curl", "-LsSf", "https://astral.sh/uv/install.sh", "|", "sh"]
            # 對於 shell 管道命令，需要使用 shell=True
            result = subprocess.run(
                "curl -LsSf https://astral.sh/uv/install.sh | sh",
                shell=True,
                capture_output=True,
                text=True,
                check=True,
            )

        if system != "windows":
            # 確保已執行安裝
            pass
        else:
            run_command(command, check=True)

        # 重新檢查是否安裝成功
        return check_uv_installed()

    except Exception as e:
        log_error(f"安裝 uv 失敗: {e}")
        log_info(
            "請手動安裝 uv: https://docs.astral.sh/uv/getting-started/installation/"
        )
        return False


def detect_virtual_environment() -> tuple[bool, Path | None]:
    """檢測虛擬環境"""
    log_step(3, 7, "檢測虛擬環境")

    # 檢查是否在虛擬環境中
    if hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    ):
        venv_path = Path(sys.prefix)
        log_success(f"已在虛擬環境中: {venv_path}")
        return True, venv_path

    # 檢查項目目錄中的常見虛擬環境位置
    project_root = Path.cwd()
    possible_venv_paths = [
        project_root / ".venv",
        project_root / "venv",
        project_root / ".env",
        project_root / "env",
    ]

    for venv_path in possible_venv_paths:
        if venv_path.exists():
            # 檢查是否是有效的虛擬環境
            python_exe = (
                venv_path
                / ("Scripts" if platform.system() == "Windows" else "bin")
                / ("python.exe" if platform.system() == "Windows" else "python")
            )
            if python_exe.exists():
                log_success(f"找到虛擬環境: {venv_path}")
                return True, venv_path

    log_warning("未找到虛擬環境")
    return False, None


def create_virtual_environment() -> Path | None:
    """使用 uv 創建虛擬環境"""
    log_step(4, 7, "創建虛擬環境")

    venv_path = Path.cwd() / ".venv"

    try:
        # 使用 uv 創建虛擬環境
        run_command(["uv", "venv", str(venv_path)])
        log_success(f"虛擬環境創建成功: {venv_path}")
        return venv_path
    except Exception as e:
        log_error(f"創建虛擬環境失敗: {e}")
        return None


def activate_virtual_environment(venv_path: Path) -> bool:
    """啟動虛擬環境"""
    log_step(5, 7, "啟動虛擬環境")

    system = platform.system()

    if system == "Windows":
        activate_script = venv_path / "Scripts" / "activate.bat"
        python_exe = venv_path / "Scripts" / "python.exe"
    else:
        activate_script = venv_path / "bin" / "activate"
        python_exe = venv_path / "bin" / "python"

    if not python_exe.exists():
        log_error(f"虛擬環境 Python 解釋器不存在: {python_exe}")
        return False

    # 更新 PATH 環境變數
    if system == "Windows":
        scripts_path = str(venv_path / "Scripts")
    else:
        scripts_path = str(venv_path / "bin")

    os.environ["PATH"] = f"{scripts_path}{os.pathsep}{os.environ['PATH']}"
    os.environ["VIRTUAL_ENV"] = str(venv_path)

    # 更新 Python 路徑
    sys.executable = str(python_exe)

    log_success(f"虛擬環境已啟動: {venv_path}")
    return True


def install_dependencies() -> bool:
    """安裝依賴套件"""
    log_step(6, 7, "安裝依賴套件")

    try:
        # 檢查 pyproject.toml 是否存在
        pyproject_path = Path("pyproject.toml")
        if not pyproject_path.exists():
            log_warning("未找到 pyproject.toml，跳過依賴安裝")
            return True

        # 使用 uv sync 安裝依賴
        run_command(["uv", "sync"])
        log_success("依賴套件安裝完成")
        return True

    except Exception as e:
        log_error(f"安裝依賴套件失敗: {e}")
        return False


def start_bot() -> bool:
    """啟動機器人"""
    log_step(7, 7, "啟動 Discord ADR Bot")

    try:
        # 檢查主要入口點
        main_script = Path("src/main.py")
        if not main_script.exists():
            log_error("找不到主程式 src/main.py")
            return False

        # 使用 uv run 啟動機器人
        log_info("正在啟動機器人...")
        run_command(
            ["uv", "run", "python", "-m", "src.main", "run"], capture_output=False
        )
        return True

    except KeyboardInterrupt:
        log_info("機器人已被用戶停止")
        return True
    except Exception as e:
        log_error(f"啟動機器人失敗: {e}")
        return False


def main():
    """主函數"""
    print_banner()

    try:
        # 1. 檢查 Python 版本
        if not check_python_version():
            sys.exit(1)

        # 2. 檢查並安裝 uv
        if not check_uv_installed():
            if not install_uv():
                log_error("無法安裝 uv，請手動安裝後重試")
                sys.exit(1)

        # 3. 檢測虛擬環境
        has_venv, venv_path = detect_virtual_environment()

        # 4. 如果沒有虛擬環境，創建一個
        if not has_venv:
            venv_path = create_virtual_environment()
            if not venv_path:
                log_error("無法創建虛擬環境")
                sys.exit(1)

        # 5. 啟動虛擬環境
        if not activate_virtual_environment(venv_path):
            log_error("無法啟動虛擬環境")
            sys.exit(1)

        # 6. 安裝依賴
        if not install_dependencies():
            log_error("依賴安裝失敗")
            sys.exit(1)

        # 7. 啟動機器人
        if not start_bot():
            log_error("機器人啟動失敗")
            sys.exit(1)

        log_success("機器人運行完成")

    except KeyboardInterrupt:
        log_info("啟動程序被用戶中斷")
    except Exception as e:
        log_error(f"未預期的錯誤: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
