# ROAS Discord Bot v2.4.4 Windows 自動安裝腳本
# Task ID: 2 - 自動化部署和啟動系統開發
#
# Daniel - DevOps 專家  
# Windows PowerShell 版本的自動安裝腳本

param(
    [switch]$DockerOnly,
    [switch]$UVOnly,
    [switch]$PythonAlso,
    [switch]$All,
    [switch]$NoDocker,
    [switch]$NoUV,
    [switch]$Force,
    [switch]$DryRun,
    [switch]$Verbose,
    [switch]$CheckSystem,
    [switch]$Help
)

# 腳本元資料
$ScriptName = "ROAS Bot Auto Installer (Windows)"
$ScriptVersion = "2.4.4"
$SupportedPlatforms = "Windows 10/11, Windows Server 2019/2022"

# 顏色輸出函數
function Write-ColorOutput {
    param(
        [Parameter(Mandatory=$true)]
        [string]$Message,
        [Parameter(Mandatory=$true)]
        [ValidateSet("INFO", "WARN", "ERROR", "SUCCESS", "DEBUG")]
        [string]$Level
    )
    
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    
    switch ($Level) {
        "INFO" { 
            Write-Host "[INFO] $timestamp - $Message" -ForegroundColor Blue
        }
        "WARN" { 
            Write-Host "[WARN] $timestamp - $Message" -ForegroundColor Yellow
        }
        "ERROR" { 
            Write-Host "[ERROR] $timestamp - $Message" -ForegroundColor Red
        }
        "SUCCESS" { 
            Write-Host "[SUCCESS] $timestamp - $Message" -ForegroundColor Green
        }
        "DEBUG" { 
            if ($Verbose) {
                Write-Host "[DEBUG] $timestamp - $Message" -ForegroundColor Magenta
            }
        }
    }
}

# 顯示使用說明
function Show-Usage {
    Write-Host @"
$ScriptName v$ScriptVersion

用法: .\auto_install.ps1 [參數]

自動安裝選項:
  -DockerOnly        僅安裝 Docker Desktop
  -UVOnly           僅安裝 UV Package Manager
  -PythonAlso       同時安裝 Python（如果不存在）
  -All              安裝所有組件
  
安裝控制:
  -Force            強制重新安裝（即使已存在）
  -DryRun           模擬安裝，不實際執行
  -NoDocker         跳過 Docker 安裝
  -NoUV             跳過 UV 安裝
  
系統選項:
  -Verbose          顯示詳細安裝過程
  -Help             顯示此說明
  -CheckSystem      僅檢查系統相容性，不安裝
  
支援平台: $SupportedPlatforms

範例:
  .\auto_install.ps1                  # 自動安裝 Docker 和 UV
  .\auto_install.ps1 -DockerOnly      # 僅安裝 Docker
  .\auto_install.ps1 -All -Force      # 強制重新安裝所有組件
  .\auto_install.ps1 -DryRun -Verbose # 查看將要執行的安裝步驟
  .\auto_install.ps1 -CheckSystem     # 檢查系統相容性

注意: 此腳本需要管理員權限執行
"@
}

# 檢查管理員權限
function Test-AdminRights {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# 檢測系統環境
function Get-SystemInfo {
    Write-ColorOutput "檢測 Windows 系統環境..." "INFO"
    
    $osInfo = Get-WmiObject -Class Win32_OperatingSystem
    $cpuInfo = Get-WmiObject -Class Win32_Processor | Select-Object -First 1
    $memInfo = Get-WmiObject -Class Win32_ComputerSystem
    
    $systemInfo = @{
        OSName = $osInfo.Caption
        OSVersion = $osInfo.Version
        OSBuild = $osInfo.BuildNumber
        Architecture = $cpuInfo.Architecture
        TotalMemoryGB = [math]::Round($memInfo.TotalPhysicalMemory / 1GB, 2)
        Is64Bit = [Environment]::Is64BitOperatingSystem
        PowerShellVersion = $PSVersionTable.PSVersion.ToString()
    }
    
    Write-ColorOutput "系統資訊:" "DEBUG"
    Write-ColorOutput "  作業系統: $($systemInfo.OSName)" "DEBUG"
    Write-ColorOutput "  版本: $($systemInfo.OSVersion) (Build $($systemInfo.OSBuild))" "DEBUG"
    Write-ColorOutput "  架構: $(if($systemInfo.Is64Bit){'x64'}else{'x86'})" "DEBUG"
    Write-ColorOutput "  記憶體: $($systemInfo.TotalMemoryGB) GB" "DEBUG"
    Write-ColorOutput "  PowerShell: $($systemInfo.PowerShellVersion)" "DEBUG"
    
    return $systemInfo
}

# 檢查系統相容性
function Test-SystemCompatibility {
    Write-ColorOutput "檢查 Windows 系統相容性..." "INFO"
    
    $issues = @()
    $systemInfo = Get-SystemInfo
    
    # 檢查 Windows 版本
    $buildNumber = [int]$systemInfo.OSBuild
    if ($buildNumber -lt 14393) {  # Windows 10 version 1607
        $issues += "Windows 版本過舊，建議升級到 Windows 10 1607 或更新版本"
        Write-ColorOutput "Windows 版本過舊: Build $buildNumber" "WARN"
    } else {
        Write-ColorOutput "Windows 版本符合要求: Build $buildNumber" "SUCCESS"
    }
    
    # 檢查系統架構
    if (-not $systemInfo.Is64Bit) {
        $issues += "不支援 32 位元系統"
        Write-ColorOutput "不支援 32 位元系統" "ERROR"
    } else {
        Write-ColorOutput "64 位元系統支援" "SUCCESS"
    }
    
    # 檢查記憶體
    if ($systemInfo.TotalMemoryGB -lt 4) {
        $issues += "記憶體不足 4GB，可能影響效能"
        Write-ColorOutput "記憶體不足: $($systemInfo.TotalMemoryGB) GB" "WARN"
    } else {
        Write-ColorOutput "記憶體充足: $($systemInfo.TotalMemoryGB) GB" "SUCCESS"
    }
    
    # 檢查 PowerShell 版本
    $psVersion = $PSVersionTable.PSVersion
    if ($psVersion.Major -lt 5) {
        $issues += "PowerShell 版本過舊，建議升級到 5.0 或更新版本"
        Write-ColorOutput "PowerShell 版本過舊: $($psVersion.ToString())" "WARN"
    } else {
        Write-ColorOutput "PowerShell 版本合適: $($psVersion.ToString())" "SUCCESS"
    }
    
    # 檢查 Hyper-V 功能（Docker 需要）
    try {
        $hyperV = Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-All -ErrorAction SilentlyContinue
        if ($hyperV -and $hyperV.State -eq "Enabled") {
            Write-ColorOutput "Hyper-V 已啟用" "SUCCESS"
        } else {
            $issues += "Hyper-V 未啟用，Docker Desktop 可能需要啟用此功能"
            Write-ColorOutput "Hyper-V 未啟用" "WARN"
        }
    } catch {
        Write-ColorOutput "無法檢查 Hyper-V 狀態" "DEBUG"
    }
    
    # 檢查 WSL（可選）
    try {
        $wslStatus = wsl --status 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-ColorOutput "WSL 可用" "SUCCESS"
        } else {
            Write-ColorOutput "WSL 未安裝（可選）" "DEBUG"
        }
    } catch {
        Write-ColorOutput "WSL 未安裝（可選）" "DEBUG"
    }
    
    # 顯示相容性結果
    if ($issues.Count -eq 0) {
        Write-ColorOutput "系統相容性檢查通過" "SUCCESS"
        return $true
    } else {
        Write-ColorOutput "發現 $($issues.Count) 個相容性問題:" "WARN"
        foreach ($issue in $issues) {
            Write-ColorOutput "  - $issue" "WARN"
        }
        return $false
    }
}

# 檢查套件管理器
function Test-PackageManager {
    $managers = @()
    
    # 檢查 Chocolatey
    try {
        $chocoVersion = choco --version 2>$null
        if ($LASTEXITCODE -eq 0) {
            $managers += @{
                Name = "Chocolatey"
                Command = "choco"
                Version = $chocoVersion.Trim()
                Available = $true
            }
            Write-ColorOutput "找到 Chocolatey: $($chocoVersion.Trim())" "SUCCESS"
        }
    } catch {
        Write-ColorOutput "Chocolatey 未安裝" "DEBUG"
    }
    
    # 檢查 Scoop
    try {
        $scoopVersion = scoop --version 2>$null
        if ($LASTEXITCODE -eq 0) {
            $managers += @{
                Name = "Scoop"
                Command = "scoop"
                Version = $scoopVersion.Trim()
                Available = $true
            }
            Write-ColorOutput "找到 Scoop: $($scoopVersion.Trim())" "SUCCESS"
        }
    } catch {
        Write-ColorOutput "Scoop 未安裝" "DEBUG"
    }
    
    # 檢查 winget
    try {
        $wingetVersion = winget --version 2>$null
        if ($LASTEXITCODE -eq 0) {
            $managers += @{
                Name = "winget"
                Command = "winget"
                Version = $wingetVersion.Trim()
                Available = $true
            }
            Write-ColorOutput "找到 winget: $($wingetVersion.Trim())" "SUCCESS"
        }
    } catch {
        Write-ColorOutput "winget 未安裝" "DEBUG"
    }
    
    return $managers
}

# 安裝 Chocolatey
function Install-Chocolatey {
    if (-not $DryRun) {
        Write-ColorOutput "安裝 Chocolatey..." "INFO"
        Set-ExecutionPolicy Bypass -Scope Process -Force
        [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
        Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
        
        # 重新載入環境變數
        $env:ChocolateyInstall = Convert-Path "$((Get-Command choco).Path)\..\.."
        Import-Module "$env:ChocolateyInstall\helpers\chocolateyProfile.psm1"
        refreshenv
        
        Write-ColorOutput "Chocolatey 安裝完成" "SUCCESS"
    } else {
        Write-ColorOutput "[DRY RUN] 會執行 Chocolatey 安裝" "INFO"
    }
}

# 檢查 Python
function Test-Python {
    Write-ColorOutput "檢查 Python 環境..." "INFO"
    
    try {
        $pythonVersion = python --version 2>$null
        if ($LASTEXITCODE -eq 0) {
            $version = $pythonVersion -replace "Python ", ""
            $versionParts = $version.Split(".")
            $major = [int]$versionParts[0]
            $minor = [int]$versionParts[1]
            
            if ($major -ge 3 -and $minor -ge 8) {
                Write-ColorOutput "找到合適的 Python 版本: $version" "SUCCESS"
                return $true
            } else {
                Write-ColorOutput "Python 版本過舊: $version (需要 >= 3.8)" "WARN"
                return $false
            }
        }
    } catch {
        Write-ColorOutput "Python 未安裝" "INFO"
        return $false
    }
    
    return $false
}

# 安裝 Python
function Install-Python {
    if (-not (Test-Python) -or $Force) {
        Write-ColorOutput "安裝 Python..." "INFO"
        
        $managers = Test-PackageManager
        $chocoAvailable = $managers | Where-Object { $_.Name -eq "Chocolatey" }
        $wingetAvailable = $managers | Where-Object { $_.Name -eq "winget" }
        
        if ($chocoAvailable) {
            if ($DryRun) {
                Write-ColorOutput "[DRY RUN] 會執行: choco install python -y" "INFO"
            } else {
                choco install python -y
            }
        } elseif ($wingetAvailable) {
            if ($DryRun) {
                Write-ColorOutput "[DRY RUN] 會執行: winget install Python.Python.3" "INFO"
            } else {
                winget install Python.Python.3
            }
        } else {
            Write-ColorOutput "未找到套件管理器，嘗試安裝 Chocolatey..." "WARN"
            Install-Chocolatey
            if ($DryRun) {
                Write-ColorOutput "[DRY RUN] 會執行: choco install python -y" "INFO"
            } else {
                choco install python -y
            }
        }
        
        # 重新載入環境變數
        if (-not $DryRun) {
            $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        }
        
        if ($DryRun -or (Test-Python)) {
            Write-ColorOutput "Python 安裝成功" "SUCCESS"
        } else {
            Write-ColorOutput "Python 安裝失敗" "ERROR"
            return $false
        }
    } else {
        Write-ColorOutput "Python 已存在，跳過安裝" "INFO"
    }
    
    return $true
}

# 檢查 Docker
function Test-Docker {
    Write-ColorOutput "檢查 Docker Desktop..." "INFO"
    
    try {
        $dockerVersion = docker --version 2>$null
        if ($LASTEXITCODE -eq 0) {
            $version = $dockerVersion -replace "Docker version ", "" -replace ",.*", ""
            
            # 檢查 Docker 是否運行
            docker info >$null 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-ColorOutput "Docker Desktop 運行正常，版本: $version" "SUCCESS"
                return $true
            } else {
                Write-ColorOutput "Docker Desktop 已安裝但未運行，版本: $version" "WARN"
                return $false
            }
        }
    } catch {
        Write-ColorOutput "Docker Desktop 未安裝" "INFO"
        return $false
    }
    
    return $false
}

# 安裝 Docker Desktop
function Install-Docker {
    if (-not (Test-Docker) -or $Force) {
        Write-ColorOutput "安裝 Docker Desktop..." "INFO"
        
        $managers = Test-PackageManager
        $chocoAvailable = $managers | Where-Object { $_.Name -eq "Chocolatey" }
        $wingetAvailable = $managers | Where-Object { $_.Name -eq "winget" }
        
        if ($chocoAvailable) {
            if ($DryRun) {
                Write-ColorOutput "[DRY RUN] 會執行: choco install docker-desktop -y" "INFO"
            } else {
                choco install docker-desktop -y
            }
        } elseif ($wingetAvailable) {
            if ($DryRun) {
                Write-ColorOutput "[DRY RUN] 會執行: winget install Docker.DockerDesktop" "INFO"
            } else {
                winget install Docker.DockerDesktop
            }
        } else {
            Write-ColorOutput "未找到套件管理器，請手動下載 Docker Desktop" "ERROR"
            Write-ColorOutput "下載地址: https://docs.docker.com/desktop/windows/install/" "INFO"
            return $false
        }
        
        if (-not $DryRun) {
            Write-ColorOutput "Docker Desktop 安裝完成，請手動啟動應用程式" "SUCCESS"
            Write-ColorOutput "注意: 首次啟動可能需要重啟電腦" "WARN"
        }
        
        return $true
    } else {
        Write-ColorOutput "Docker Desktop 已正常運行，跳過安裝" "INFO"
        return $true
    }
}

# 檢查 UV
function Test-UV {
    Write-ColorOutput "檢查 UV Package Manager..." "INFO"
    
    try {
        $uvVersion = uv --version 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-ColorOutput "UV 已安裝，版本: $($uvVersion.Trim())" "SUCCESS"
            return $true
        }
    } catch {
        Write-ColorOutput "UV 未安裝" "INFO"
        return $false
    }
    
    return $false
}

# 安裝 UV
function Install-UV {
    if (-not (Test-UV) -or $Force) {
        Write-ColorOutput "安裝 UV Package Manager..." "INFO"
        
        if ($DryRun) {
            Write-ColorOutput "[DRY RUN] 會執行 UV 安裝腳本" "INFO"
        } else {
            # 使用官方安裝腳本
            Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
            
            # 重新載入環境變數
            $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        }
        
        if ($DryRun -or (Test-UV)) {
            Write-ColorOutput "UV 安裝成功" "SUCCESS"
        } else {
            Write-ColorOutput "UV 安裝失敗" "ERROR"
            return $false
        }
    } else {
        Write-ColorOutput "UV 已存在，跳過安裝" "INFO"
    }
    
    return $true
}

# 執行安裝後驗證
function Test-PostInstallation {
    Write-ColorOutput "執行安裝後驗證..." "INFO"
    
    $verificationPassed = $true
    
    # 驗證 Python
    if ($script:InstallPython) {
        if (Test-Python) {
            Write-ColorOutput "✓ Python 驗證通過" "SUCCESS"
        } else {
            Write-ColorOutput "✗ Python 驗證失敗" "ERROR"
            $verificationPassed = $false
        }
    }
    
    # 驗證 Docker
    if ($script:InstallDocker) {
        if (Test-Docker) {
            Write-ColorOutput "✓ Docker Desktop 驗證通過" "SUCCESS"
        } else {
            Write-ColorOutput "✗ Docker Desktop 驗證失敗（可能需要手動啟動）" "WARN"
        }
    }
    
    # 驗證 UV
    if ($script:InstallUV) {
        if (Test-UV) {
            Write-ColorOutput "✓ UV 驗證通過" "SUCCESS"
        } else {
            Write-ColorOutput "✗ UV 驗證失敗" "ERROR"
            $verificationPassed = $false
        }
    }
    
    return $verificationPassed
}

# 顯示安裝摘要
function Show-InstallationSummary {
    $systemInfo = Get-SystemInfo
    
    Write-Host ""
    Write-ColorOutput "====================================================" "INFO"
    Write-ColorOutput "$ScriptName 安裝摘要" "INFO"
    Write-ColorOutput "====================================================" "INFO"
    
    Write-Host "系統資訊:" -ForegroundColor Cyan
    Write-Host "  作業系統: $($systemInfo.OSName)"
    Write-Host "  版本: $($systemInfo.OSVersion) (Build $($systemInfo.OSBuild))"
    Write-Host "  記憶體: $($systemInfo.TotalMemoryGB) GB"
    
    Write-Host "`n安裝結果:" -ForegroundColor Cyan
    
    if ($script:InstallPython) {
        if (Test-Python) {
            $pythonVer = (python --version 2>$null) -replace "Python ", ""
            Write-Host "  Python: " -NoNewline
            Write-Host "已安裝 " -ForegroundColor Green -NoNewline
            Write-Host "($pythonVer)"
        } else {
            Write-Host "  Python: " -NoNewline
            Write-Host "安裝失敗" -ForegroundColor Red
        }
    } else {
        Write-Host "  Python: " -NoNewline
        Write-Host "跳過安裝" -ForegroundColor Yellow
    }
    
    if ($script:InstallDocker) {
        if (Test-Docker) {
            $dockerVer = (docker --version 2>$null) -replace "Docker version ", "" -replace ",.*", ""
            Write-Host "  Docker Desktop: " -NoNewline
            Write-Host "已安裝且運行中 " -ForegroundColor Green -NoNewline
            Write-Host "($dockerVer)"
        } else {
            Write-Host "  Docker Desktop: " -NoNewline
            Write-Host "已安裝但需要手動啟動" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  Docker Desktop: " -NoNewline
        Write-Host "跳過安裝" -ForegroundColor Yellow
    }
    
    if ($script:InstallUV) {
        if (Test-UV) {
            $uvVer = (uv --version 2>$null).Trim()
            Write-Host "  UV: " -NoNewline
            Write-Host "已安裝 " -ForegroundColor Green -NoNewline
            Write-Host "($uvVer)"
        } else {
            Write-Host "  UV: " -NoNewline
            Write-Host "安裝失敗" -ForegroundColor Red
        }
    } else {
        Write-Host "  UV: " -NoNewline
        Write-Host "跳過安裝" -ForegroundColor Yellow
    }
    
    Write-Host "`n下一步操作:" -ForegroundColor Cyan
    Write-Host "  1. 重新啟動 PowerShell 終端以載入環境變數"
    Write-Host "  2. 如果安裝了 Docker Desktop，請手動啟動應用程式"
    Write-Host "  3. 驗證安裝: .\scripts\start.sh --env-check (在 Git Bash 中)"
    Write-Host "  4. 開始部署: .\scripts\start.sh (在 Git Bash 中)"
    
    Write-Host "`nWindows 特別提示:" -ForegroundColor Yellow
    Write-Host "  - 建議使用 Git Bash 或 WSL 來執行部署腳本"
    Write-Host "  - Docker Desktop 首次啟動可能需要重啟電腦"
    Write-Host "  - 如果遇到權限問題，請以管理員身分執行"
}

# 主函數
function Main {
    # 處理參數
    if ($Help) {
        Show-Usage
        exit 0
    }
    
    # 檢查管理員權限
    if (-not (Test-AdminRights)) {
        Write-ColorOutput "此腳本需要管理員權限執行" "ERROR"
        Write-ColorOutput "請以管理員身分重新執行 PowerShell" "INFO"
        exit 1
    }
    
    # 設定安裝選項
    $script:InstallPython = $PythonAlso -or $All
    $script:InstallDocker = ($true -and -not $NoDocker) -or $DockerOnly -or $All
    $script:InstallUV = ($true -and -not $NoUV) -or $UVOnly -or $All
    
    if ($DockerOnly) {
        $script:InstallDocker = $true
        $script:InstallUV = $false
        $script:InstallPython = $false
    } elseif ($UVOnly) {
        $script:InstallDocker = $false
        $script:InstallUV = $true
        $script:InstallPython = $false
    }
    
    # 系統檢查模式
    if ($CheckSystem) {
        Get-SystemInfo | Out-Null
        Test-SystemCompatibility | Out-Null
        exit 0
    }
    
    # 顯示歡迎信息
    Write-Host ""
    Write-Host "====================================================" -ForegroundColor Blue
    Write-Host "  $ScriptName v$ScriptVersion" -ForegroundColor Blue
    Write-Host "  自動安裝 ROAS Discord Bot Windows 部署依賴" -ForegroundColor Blue
    Write-Host "====================================================" -ForegroundColor Blue
    Write-Host ""
    
    # 檢測系統
    Get-SystemInfo | Out-Null
    
    # 檢查系統相容性
    if (-not (Test-SystemCompatibility)) {
        Write-ColorOutput "發現相容性問題，但繼續安裝..." "WARN"
    }
    
    # 顯示安裝計劃
    Write-Host "安裝計劃:" -ForegroundColor Cyan
    if ($script:InstallPython) { Write-Host "  ✓ Python >= 3.8" }
    if ($script:InstallDocker) { Write-Host "  ✓ Docker Desktop" }
    if ($script:InstallUV) { Write-Host "  ✓ UV Package Manager" }
    
    if ($DryRun) {
        Write-Host "[DRY RUN 模式] 僅顯示將要執行的操作，不實際安裝" -ForegroundColor Yellow
    }
    
    if ($Force) {
        Write-Host "[強制模式] 將重新安裝已存在的組件" -ForegroundColor Yellow
    }
    
    Write-Host ""
    $continue = Read-Host "是否繼續安裝？[Y/n]"
    if ($continue -ne "" -and $continue -ne "Y" -and $continue -ne "y") {
        Write-ColorOutput "安裝已取消" "INFO"
        exit 0
    }
    
    # 開始安裝過程
    Write-ColorOutput "開始 Windows 自動安裝過程..." "INFO"
    
    # 檢查並安裝套件管理器
    $managers = Test-PackageManager
    if ($managers.Count -eq 0) {
        Write-ColorOutput "未找到套件管理器，安裝 Chocolatey..." "INFO"
        Install-Chocolatey
    }
    
    # 安裝 Python
    if ($script:InstallPython) {
        Install-Python
    }
    
    # 安裝 Docker
    if ($script:InstallDocker) {
        Install-Docker
    }
    
    # 安裝 UV
    if ($script:InstallUV) {
        Install-UV
    }
    
    # 執行安裝後驗證
    if (-not $DryRun) {
        Test-PostInstallation | Out-Null
    }
    
    # 顯示安裝摘要
    Show-InstallationSummary
    
    Write-ColorOutput "Windows 自動安裝完成！" "SUCCESS"
}

# 執行主函數
Main