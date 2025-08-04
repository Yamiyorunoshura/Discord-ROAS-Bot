# Discord ADR Bot v2.0 - Windows PowerShell Upgrade Script
# Automated upgrade script with version detection and rollback support

param(
    [string]$InstallPath = "$env:LOCALAPPDATA\discord-adr-bot",
    [switch]$Rollback,
    [switch]$Force,
    [switch]$DryRun,
    [switch]$Help
)

# Script Configuration
$Script:ScriptName = "Discord ADR Bot Upgrader"
$Script:ScriptVersion = "2.1.0"
$Script:BotName = "discord-adr-bot"
$Script:VenvDir = "$InstallPath\.venv"
$Script:BackupDir = "$InstallPath\backups"
$Script:LogFile = "$InstallPath\upgrade.log"
$Script:ErrorActionPreference = "Stop"

# Show help message
function Show-Help {
    Write-Host "$Script:ScriptName v$Script:ScriptVersion" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage: .\upgrade.ps1 [OPTIONS]" -ForegroundColor White
    Write-Host ""
    Write-Host "OPTIONS:" -ForegroundColor Yellow
    Write-Host "    -Rollback       Rollback to previous version"
    Write-Host "    -Force          Force upgrade/rollback even if versions match"
    Write-Host "    -DryRun         Show what would be done without making changes"
    Write-Host "    -InstallPath    Custom installation path (default: $env:LOCALAPPDATA\discord-adr-bot)"
    Write-Host "    -Help           Show this help message"
    Write-Host ""
    Write-Host "EXAMPLES:" -ForegroundColor Yellow
    Write-Host "    .\upgrade.ps1                    # Upgrade to latest version"
    Write-Host "    .\upgrade.ps1 -Rollback          # Rollback to previous version"
    Write-Host "    .\upgrade.ps1 -DryRun            # Preview upgrade actions"
}

if ($Help) {
    Show-Help
    exit 0
}

# Create log directory if it doesn't exist
$logDir = Split-Path $Script:LogFile -Parent
if (!(Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

# Logging functions
function Write-Log {
    param(
        [string]$Level,
        [string]$Message
    )
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logEntry = "$timestamp [$Level] $Message"
    
    # Write to console with colors
    switch ($Level) {
        "INFO" { Write-Host "[INFO] $Message" -ForegroundColor Blue }
        "SUCCESS" { Write-Host "[SUCCESS] $Message" -ForegroundColor Green }
        "WARNING" { Write-Host "[WARNING] $Message" -ForegroundColor Yellow }
        "ERROR" { Write-Host "[ERROR] $Message" -ForegroundColor Red }
    }
    
    # Write to log file
    try {
        Add-Content -Path $Script:LogFile -Value $logEntry -Encoding UTF8
    } catch {
        # If log file is not accessible, continue without logging
    }
}

function Write-Info { param([string]$Message) Write-Log -Level "INFO" -Message $Message }
function Write-Success { param([string]$Message) Write-Log -Level "SUCCESS" -Message $Message }
function Write-Warning { param([string]$Message) Write-Log -Level "WARNING" -Message $Message }
function Write-Error { param([string]$Message) Write-Log -Level "ERROR" -Message $Message }

# Check if installation exists
function Test-Installation {
    if (!(Test-Path $InstallPath)) {
        Write-Error "Discord ADR Bot is not installed in $InstallPath"
        Write-Error "Please run the install script first."
        exit 1
    }
    
    if (!(Test-Path $Script:VenvDir)) {
        Write-Error "Virtual environment not found in $Script:VenvDir"
        Write-Error "Installation appears to be corrupted. Please reinstall."
        exit 1
    }
}

# Get current installed version
function Get-CurrentVersion {
    $versionFile = "$InstallPath\version.txt"
    
    if (Test-Path $versionFile) {
        return Get-Content $versionFile -Raw | ForEach-Object { $_.Trim() }
    } else {
        # Try to get version from pip
        try {
            Set-Location $InstallPath
            & ".\venv\Scripts\pip.exe" show discord-adr-bot 2>$null | Where-Object { $_ -match "Version:" } | ForEach-Object { ($_ -split ":")[1].Trim() }
        } catch {
            return "unknown"
        }
    }
}

# Get new version from wheel file
function Get-NewVersion {
    param([string]$WheelFile)
    
    $filename = Split-Path $WheelFile -Leaf
    
    # Extract version from filename (format: discord_adr_bot-X.Y.Z-py3-none-any.whl)
    if ($filename -match "discord_adr_bot-(\d+\.\d+\.\d+)") {
        return $Matches[1]
    } else {
        return "unknown"
    }
}

# Find wheel file
function Find-WheelFile {
    Write-Info "Looking for package file..."
    
    $wheelFile = $null
    
    # Look in dist directory first
    if (Test-Path "dist") {
        $wheelFile = Get-ChildItem -Path "dist" -Filter "*.whl" | Select-Object -First 1 -ExpandProperty FullName
    }
    
    # Look in current directory if not found
    if (-not $wheelFile) {
        $wheelFile = Get-ChildItem -Path "." -Filter "*.whl" | Select-Object -First 1 -ExpandProperty FullName
    }
    
    if (-not $wheelFile) {
        Write-Error "No wheel (.whl) file found. Please run 'make dist' first."
        exit 1
    }
    
    Write-Info "Found package: $wheelFile"
    return $wheelFile
}

# Create backup
function New-Backup {
    param([string]$CurrentVersion)
    
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $backupPath = "$Script:BackupDir\v${CurrentVersion}_${timestamp}"
    
    Write-Info "Creating backup of current installation..."
    
    if ($DryRun) {
        Write-Info "DRY RUN: Would create backup at $backupPath"
        return $backupPath
    }
    
    New-Item -ItemType Directory -Path $backupPath -Force | Out-Null
    
    # Backup virtual environment
    if (Test-Path $Script:VenvDir) {
        Write-Info "Backing up virtual environment..."
        Copy-Item -Path $Script:VenvDir -Destination $backupPath -Recurse
    }
    
    # Backup configuration
    if (Test-Path "$InstallPath\.env") {
        Copy-Item -Path "$InstallPath\.env" -Destination $backupPath
    }
    
    # Backup version info
    Set-Content -Path "$backupPath\version.txt" -Value $CurrentVersion -Encoding UTF8
    
    # Save backup metadata
    $backupInfo = @"
Backup Date: $(Get-Date)
Original Version: $CurrentVersion
Backup Path: $backupPath
Created By: $Script:ScriptName v$Script:ScriptVersion
"@
    Set-Content -Path "$backupPath\backup_info.txt" -Value $backupInfo -Encoding UTF8
    
    Write-Success "Backup created: $backupPath"
    return $backupPath
}

# Find latest backup
function Find-LatestBackup {
    if (!(Test-Path $Script:BackupDir)) {
        Write-Error "No backups found in $Script:BackupDir"
        return $null
    }
    
    $latestBackup = Get-ChildItem -Path $Script:BackupDir -Directory | Where-Object { $_.Name -match "^v" } | Sort-Object Name -Descending | Select-Object -First 1
    
    if (-not $latestBackup) {
        Write-Error "No version backups found"
        return $null
    }
    
    return $latestBackup.FullName
}

# Restore from backup
function Restore-Backup {
    param([string]$BackupPath)
    
    if (!(Test-Path $BackupPath)) {
        Write-Error "Backup directory not found: $BackupPath"
        exit 1
    }
    
    Write-Info "Restoring from backup: $BackupPath"
    
    if ($DryRun) {
        Write-Info "DRY RUN: Would restore from $BackupPath"
        return
    }
    
    # Stop any running bot instances
    Write-Info "Stopping any running bot instances..."
    Get-Process | Where-Object { $_.ProcessName -like "*python*" -and $_.CommandLine -like "*discord_adr_bot*" } | Stop-Process -Force -ErrorAction SilentlyContinue
    
    # Remove current virtual environment
    if (Test-Path $Script:VenvDir) {
        Remove-Item -Path $Script:VenvDir -Recurse -Force
    }
    
    # Restore virtual environment
    $backupVenv = "$BackupPath\.venv"
    if (Test-Path $backupVenv) {
        Copy-Item -Path $backupVenv -Destination $Script:VenvDir -Recurse
    } else {
        Write-Error "Virtual environment not found in backup"
        exit 1
    }
    
    # Restore configuration (but don't overwrite if current exists)
    $backupEnv = "$BackupPath\.env"
    $currentEnv = "$InstallPath\.env"
    if ((Test-Path $backupEnv) -and !(Test-Path $currentEnv)) {
        Copy-Item -Path $backupEnv -Destination $currentEnv
    }
    
    # Update version file
    $backupVersion = "$BackupPath\version.txt"
    if (Test-Path $backupVersion) {
        Copy-Item -Path $backupVersion -Destination "$InstallPath\version.txt"
    }
    
    Write-Success "Rollback completed successfully"
}

# Perform upgrade
function Invoke-Upgrade {
    param(
        [string]$WheelFile,
        [string]$NewVersion
    )
    
    Write-Info "Upgrading to version $NewVersion..."
    
    if ($DryRun) {
        Write-Info "DRY RUN: Would upgrade to $NewVersion using $WheelFile"
        return
    }
    
    # Stop any running bot instances
    Write-Info "Stopping any running bot instances..."
    Get-Process | Where-Object { $_.ProcessName -like "*python*" -and $_.CommandLine -like "*discord_adr_bot*" } | Stop-Process -Force -ErrorAction SilentlyContinue
    
    # Upgrade package
    try {
        Set-Location $InstallPath
        & ".\venv\Scripts\uv.exe" pip install --upgrade $WheelFile
        
        if ($LASTEXITCODE -ne 0) {
            throw "Package upgrade failed"
        }
        
        # Update version file
        Set-Content -Path "$InstallPath\version.txt" -Value $NewVersion -Encoding UTF8
        
        Write-Success "Upgrade completed successfully"
    } catch {
        Write-Error "Upgrade failed: $_"
        throw
    }
}

# Validate installation
function Test-InstallationValidation {
    Write-Info "Validating installation..."
    
    try {
        Set-Location $InstallPath
        & ".\venv\Scripts\python.exe" -c "import discord_adr_bot; print('Import successful')"
        
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Installation validation successful"
            
            # Show version info
            $currentVersion = Get-CurrentVersion
            Write-Info "Current version: $currentVersion"
            return $true
        } else {
            Write-Error "Installation validation failed"
            return $false
        }
    } catch {
        Write-Error "Installation validation failed: $_"
        return $false
    }
}

# Clean old backups (keep last 5)
function Remove-OldBackups {
    if (!(Test-Path $Script:BackupDir)) {
        return
    }
    
    Write-Info "Cleaning up old backups..."
    
    $backups = Get-ChildItem -Path $Script:BackupDir -Directory | Where-Object { $_.Name -match "^v" } | Sort-Object Name
    
    if ($backups.Count -gt 5) {
        $oldBackups = $backups | Select-Object -First ($backups.Count - 5)
        
        foreach ($backup in $oldBackups) {
            Write-Info "Removing old backup: $($backup.Name)"
            if (-not $DryRun) {
                Remove-Item -Path $backup.FullName -Recurse -Force
            }
        }
    }
}

# Main upgrade function
function Invoke-MainUpgrade {
    $wheelFile = Find-WheelFile
    $currentVersion = Get-CurrentVersion
    $newVersion = Get-NewVersion -WheelFile $wheelFile
    
    Write-Info "Current version: $currentVersion"
    Write-Info "New version: $newVersion"
    
    # Version comparison
    if ($currentVersion -eq $newVersion -and -not $Force) {
        Write-Info "Already running the latest version ($newVersion)"
        Write-Info "Use -Force to reinstall the same version"
        exit 0
    }
    
    # Create backup
    $backupPath = New-Backup -CurrentVersion $currentVersion
    
    try {
        # Perform upgrade
        Invoke-Upgrade -WheelFile $wheelFile -NewVersion $newVersion
        
        # Validate
        if (Test-InstallationValidation) {
            Write-Success "🎉 Upgrade completed successfully!"
            Write-Info "Upgraded from $currentVersion to $newVersion"
            Write-Info "Backup created at: $backupPath"
            Remove-OldBackups
        } else {
            throw "Upgrade validation failed"
        }
    } catch {
        Write-Error "Upgrade failed: $_"
        Write-Error "Rolling back..."
        Restore-Backup -BackupPath $backupPath
        exit 1
    }
}

# Main rollback function
function Invoke-MainRollback {
    $currentVersion = Get-CurrentVersion
    $latestBackup = Find-LatestBackup
    
    if (-not $latestBackup) {
        Write-Error "No backups available for rollback"
        exit 1
    }
    
    $backupVersionFile = "$latestBackup\version.txt"
    $backupVersion = if (Test-Path $backupVersionFile) { Get-Content $backupVersionFile -Raw | ForEach-Object { $_.Trim() } } else { "unknown" }
    
    Write-Info "Current version: $currentVersion"
    Write-Info "Rollback to version: $backupVersion"
    Write-Info "Using backup: $latestBackup"
    
    if ($currentVersion -eq $backupVersion -and -not $Force) {
        Write-Info "Already running version $backupVersion"
        Write-Info "Use -Force to force rollback"
        exit 0
    }
    
    # Create backup of current state before rollback
    $preRollbackBackup = New-Backup -CurrentVersion $currentVersion
    
    try {
        # Perform rollback
        Restore-Backup -BackupPath $latestBackup
        
        # Validate
        if (Test-InstallationValidation) {
            Write-Success "🔄 Rollback completed successfully!"
            Write-Info "Rolled back from $currentVersion to $backupVersion"
            Write-Info "Current state backed up at: $preRollbackBackup"
        } else {
            throw "Rollback validation failed"
        }
    } catch {
        Write-Error "Rollback failed: $_"
        exit 1
    }
}

# Main function
function Invoke-Main {
    Write-Host "=== $Script:ScriptName v$Script:ScriptVersion ===" -ForegroundColor Cyan
    Write-Host ""
    
    if ($DryRun) {
        Write-Warning "DRY RUN MODE - No actual changes will be made"
        Write-Host ""
    }
    
    Test-Installation
    
    if ($Rollback) {
        Invoke-MainRollback
    } else {
        Invoke-MainUpgrade
    }
}

# Error handling
trap {
    Write-Error "Operation failed: $_"
    Write-Error "Check $Script:LogFile for details."
    exit 1
}

# Main execution
try {
    Invoke-Main
} catch {
    Write-Error "Operation failed: $_"
    exit 1
}