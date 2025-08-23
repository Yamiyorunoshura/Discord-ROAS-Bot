# Discord機器人跨平台一鍵啟動腳本 - Windows PowerShell版本
# Task ID: T6 - Docker跨平台一鍵啟動腳本開發

#Requires -Version 5.1

param(
    [string]$EnvFile = "",
    [string]$Profile = "default", 
    [switch]$Verbose,
    [switch]$ForceRebuild,
    [switch]$Interactive,
    [switch]$Help
)

# 設定嚴格模式
Set-StrictMode -Version 3.0
$ErrorActionPreference = "Stop"

# 設定變數
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$ComposeFile = Join-Path $ProjectRoot "docker" "compose.yaml"
$DefaultEnvFile = Join-Path $ProjectRoot ".env"
$DefaultProfile = "default"

# 函數：顯示用法
function Show-Usage {
    Write-Host @"
使用方法: .\start.ps1 [參數]

參數:
  -EnvFile STRING        使用指定的環境變數檔案 (預設: .env)
  -Profile STRING        使用指定的Docker Compose profile (預設: default)
  -Verbose               顯示詳細輸出
  -ForceRebuild         強制重建Docker映像
  -Interactive          交互式模式（不使用-d執行）
  -Help                 顯示此說明

可用的profiles:
  default     - 基本服務 (bot + redis)
  dev         - 開發環境 (包含開發工具)
  prod        - 生產環境 (包含監控服務)  
  monitoring  - 僅監控服務 (prometheus + grafana)
  dev-tools   - 開發工具容器

範例:
  .\start.ps1                           # 使用預設配置啟動
  .\start.ps1 -Verbose                  # 詳細模式啟動
  .\start.ps1 -Profile prod -Verbose    # 啟動生產環境配置
  .\start.ps1 -EnvFile .env.prod -Profile prod  # 使用自訂環境檔案
  .\start.ps1 -ForceRebuild            # 強制重建後啟動
"@
}

# 函數：記錄訊息
function Write-Log {
    param(
        [Parameter(Mandatory)]
        [ValidateSet("INFO", "WARN", "ERROR", "SUCCESS", "DEBUG")]
        [string]$Level,
        
        [Parameter(Mandatory)]
        [string]$Message
    )
    
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    
    switch ($Level) {
        "INFO"    { Write-Host "[$Level] $timestamp - $Message" -ForegroundColor Blue }
        "WARN"    { Write-Host "[$Level] $timestamp - $Message" -ForegroundColor Yellow }
        "ERROR"   { Write-Host "[$Level] $timestamp - $Message" -ForegroundColor Red }
        "SUCCESS" { Write-Host "[$Level] $timestamp - $Message" -ForegroundColor Green }
        "DEBUG"   { 
            if ($Verbose) { 
                Write-Host "[$Level] $timestamp - $Message" -ForegroundColor Magenta 
            } 
        }
    }
}

# 函數：檢查系統需求
function Test-SystemRequirements {
    Write-Log -Level "INFO" -Message "檢查系統需求..."
    
    # 檢查PowerShell版本
    if ($PSVersionTable.PSVersion.Major -lt 5) {
        Write-Log -Level "ERROR" -Message "需要PowerShell 5.1或更新版本"
        exit 1
    }
    
    # 檢查Docker
    try {
        $null = Get-Command docker -ErrorAction Stop
        $dockerVersion = (docker --version) -replace '.*?(\d+\.\d+\.\d+).*', '$1'
        Write-Log -Level "DEBUG" -Message "發現Docker版本: $dockerVersion"
    }
    catch {
        Write-Log -Level "ERROR" -Message "Docker未安裝。請安裝Docker Desktop for Windows："
        Write-Host "  https://docs.docker.com/docker-for-windows/install/" -ForegroundColor Cyan
        exit 1
    }
    
    # 檢查Docker是否運行
    try {
        $null = docker version 2>$null
    }
    catch {
        Write-Log -Level "ERROR" -Message "Docker未運行。請啟動Docker Desktop"
        exit 1
    }
    
    # 檢查Docker Compose
    try {
        $null = docker compose version 2>$null
        $composeVersion = (docker compose version --short)
        Write-Log -Level "DEBUG" -Message "發現Docker Compose版本: $composeVersion"
    }
    catch {
        Write-Log -Level "ERROR" -Message "Docker Compose未安裝或版本過舊。請安裝Docker Compose V2"
        Write-Host "  https://docs.docker.com/compose/install/" -ForegroundColor Cyan
        exit 1
    }
    
    # 檢查可用磁碟空間 (至少需要2GB)
    $drive = (Get-Item $ProjectRoot).PSDrive
    $freeSpace = $drive.Free / 1GB
    if ($freeSpace -lt 2) {
        Write-Log -Level "WARN" -Message "可用磁碟空間不足2GB，可能影響構建過程"
    }
    
    Write-Log -Level "SUCCESS" -Message "系統需求檢查通過"
}

# 函數：檢查並載入環境變數  
function Import-Environment {
    $envFile = if ($EnvFile) { $EnvFile } else { $DefaultEnvFile }
    
    if (-not (Test-Path $envFile)) {
        Write-Log -Level "ERROR" -Message "環境變數檔案不存在: $envFile"
        Write-Log -Level "INFO" -Message "請建立環境變數檔案，範例："
        Write-Host @"
# Discord設定
DISCORD_TOKEN=your_bot_token_here
DISCORD_APPLICATION_ID=your_application_id_here

# 環境設定  
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG

# 安全設定
SECRET_KEY=your_secret_key_here
ENCRYPTION_KEY=your_encryption_key_here
"@ -ForegroundColor Gray
        exit 1
    }
    
    Write-Log -Level "INFO" -Message "載入環境變數檔案: $envFile"
    
    # 載入環境變數
    $envVars = @{}
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^([^#][^=]+)=(.*)$') {
            $envVars[$matches[1].Trim()] = $matches[2].Trim()
            [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
        }
    }
    
    # 檢查關鍵環境變數
    if (-not $envVars["DISCORD_TOKEN"]) {
        Write-Log -Level "ERROR" -Message "DISCORD_TOKEN未設定在環境變數檔案中"
        exit 1
    }
    
    if (-not $envVars["SECRET_KEY"]) {
        Write-Log -Level "WARN" -Message "SECRET_KEY未設定，將使用預設值（不建議用於生產環境）"
    }
    
    Write-Log -Level "SUCCESS" -Message "環境變數載入成功"
}

# 函數：檢查Docker Compose檔案
function Test-ComposeFile {
    if (-not (Test-Path $ComposeFile)) {
        Write-Log -Level "ERROR" -Message "Docker Compose檔案不存在: $ComposeFile"
        exit 1
    }
    
    Write-Log -Level "DEBUG" -Message "使用Docker Compose檔案: $ComposeFile"
    
    # 驗證Compose檔案語法
    try {
        $null = docker compose -f $ComposeFile config 2>$null
    }
    catch {
        Write-Log -Level "ERROR" -Message "Docker Compose檔案語法錯誤"
        if ($Verbose) {
            docker compose -f $ComposeFile config
        }
        exit 1
    }
    
    Write-Log -Level "SUCCESS" -Message "Docker Compose檔案驗證通過"
}

# 函數：構建和啟動服務
function Start-Services {
    Write-Log -Level "INFO" -Message "啟動Discord機器人服務..."
    
    Set-Location $ProjectRoot
    
    $composeArgs = @(
        "-f", $ComposeFile,
        "--profile", $Profile
    )
    
    if ($EnvFile) {
        $composeArgs += @("--env-file", $EnvFile)
    }
    
    # 強制重建映像
    if ($ForceRebuild) {
        Write-Log -Level "INFO" -Message "強制重建Docker映像..."
        & docker compose @composeArgs build --no-cache
        if ($LASTEXITCODE -ne 0) {
            Write-Log -Level "ERROR" -Message "Docker映像構建失敗"
            exit 1
        }
    }
    
    # 拉取最新映像
    Write-Log -Level "INFO" -Message "拉取最新映像..."
    & docker compose @composeArgs pull --ignore-pull-failures
    
    # 啟動服務
    $runArgs = @()
    if (-not $Interactive) {
        $runArgs += "-d"
    }
    
    if ($Verbose) {
        Write-Log -Level "DEBUG" -Message "執行命令: docker compose $($composeArgs -join ' ') up $($runArgs -join ' ')"
    }
    
    & docker compose @composeArgs up @runArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Log -Level "ERROR" -Message "服務啟動失敗"
        exit 1
    }
    
    if (-not $Interactive) {
        Write-Log -Level "SUCCESS" -Message "服務已在背景啟動"
        
        # 顯示服務狀態
        Start-Sleep -Seconds 5
        & docker compose @composeArgs ps
        
        Write-Log -Level "INFO" -Message "查看日誌: docker compose -f $ComposeFile --profile $Profile logs -f"
        Write-Log -Level "INFO" -Message "停止服務: docker compose -f $ComposeFile --profile $Profile down"
    }
}

# 主函數
function Main {
    # 處理Help參數
    if ($Help) {
        Show-Usage
        exit 0
    }
    
    # 設定Profile預設值
    if (-not $Profile) {
        $Profile = $DefaultProfile
    }
    
    Write-Log -Level "INFO" -Message "Discord機器人啟動腳本 v1.0 (T6)"
    Write-Log -Level "INFO" -Message "Project Root: $ProjectRoot"
    Write-Log -Level "INFO" -Message "Profile: $Profile"
    
    try {
        Test-SystemRequirements
        Import-Environment
        Test-ComposeFile
        Start-Services
        
        Write-Log -Level "SUCCESS" -Message "啟動完成！"
    }
    catch {
        Write-Log -Level "ERROR" -Message "腳本執行失敗: $($_.Exception.Message)"
        Write-Log -Level "DEBUG" -Message "錯誤詳細信息: $($_.Exception)"
        exit 1
    }
}

# 執行主函數
Main