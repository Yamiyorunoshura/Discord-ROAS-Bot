# Discord ADR Bot v2.0 - Windows PowerShell Installation Script
# Automated installation script with uv environment setup

param(
    [string]$InstallPath = "$env:LOCALAPPDATA\discord-adr-bot",
    [switch]$Force,
    [switch]$Verbose,
    [switch]$DryRun
)

# Script Configuration
$Script:ScriptName = "Discord ADR Bot Installer"
$Script:ScriptVersion = "2.1.0"
$Script:BotName = "discord-adr-bot"
$Script:VenvDir = "$InstallPath\.venv"
$Script:LogFile = "$InstallPath\install.log"
$Script:ErrorActionPreference = "Stop"

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

# Check if running as administrator
function Test-Administrator {
    $currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# Check system requirements
function Test-SystemRequirements {
    Write-Info "Checking system requirements..."
    
    # Check PowerShell version
    if ($PSVersionTable.PSVersion.Major -lt 5) {
        Write-Error "PowerShell 5.0 or later is required. Current version: $($PSVersionTable.PSVersion)"
        exit 1
    }
    
    # Check Python installation
    try {
        $pythonVersion = & python --version 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "Python not found"
        }
        
        # Extract version number
        $versionMatch = $pythonVersion -match "Python (\d+)\.(\d+)"
        if ($versionMatch) {
            $majorVersion = [int]$Matches[1]
            $minorVersion = [int]$Matches[2]
            
            if ($majorVersion -lt 3 -or ($majorVersion -eq 3 -and $minorVersion -lt 12)) {
                Write-Error "Python 3.12 or later is required. Found: Python $majorVersion.$minorVersion"
                Write-Error "Please install Python 3.12+ from https://python.org"
                exit 1
            }
        }
        
        Write-Success "Python $($pythonVersion -replace 'Python ', '') detected"
    } catch {
        Write-Error "Python 3.12+ is not installed or not in PATH"
        Write-Error "Please install Python 3.12+ from https://python.org"
        exit 1
    }
}

# Check and install uv
function Install-Uv {
    Write-Info "Checking uv package manager..."
    
    try {
        $uvVersion = & uv --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Success "uv is already installed: $($uvVersion -replace 'uv ', '')"
            return
        }
    } catch {
        # uv not found, continue with installation
    }
    
    Write-Info "Installing uv package manager..."
    
    try {
        # Download and install uv
        $uvInstaller = "$env:TEMP\install-uv.ps1"
        Invoke-WebRequest -Uri "https://astral.sh/uv/install.ps1" -OutFile $uvInstaller
        & powershell -ExecutionPolicy Bypass -File $uvInstaller
        
        # Add uv to PATH for current session
        $uvPath = "$env:USERPROFILE\.cargo\bin"
        if (Test-Path $uvPath) {
            $env:PATH = "$uvPath;$env:PATH"
        }
        
        # Verify installation
        $uvVersion = & uv --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Success "uv installed successfully: $($uvVersion -replace 'uv ', '')"
        } else {
            throw "uv installation verification failed"
        }
    } catch {
        Write-Error "Failed to install uv: $_"
        Write-Error "Please install uv manually from https://docs.astral.sh/uv/"
        exit 1
    }
}

# Create installation directory
function New-InstallDirectory {
    Write-Info "Creating installation directory..."
    
    if (Test-Path $InstallPath) {
        if ($Force) {
            Write-Warning "Removing existing installation..."
            Remove-Item -Path $InstallPath -Recurse -Force
        } else {
            Write-Warning "Installation directory already exists: $InstallPath"
            Write-Warning "Use -Force to overwrite existing installation"
            exit 1
        }
    }
    
    New-Item -ItemType Directory -Path $InstallPath -Force | Out-Null
    Write-Success "Installation directory created: $InstallPath"
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

# Verify package checksum
function Test-PackageIntegrity {
    param([string]$WheelFile)
    
    $checksumFile = "dist\SHA256SUMS"
    
    if (!(Test-Path $checksumFile)) {
        Write-Warning "Checksum file not found. Skipping verification."
        return
    }
    
    Write-Info "Verifying package integrity..."
    
    try {
        $expectedHash = Get-Content $checksumFile | Where-Object { $_ -match (Split-Path $WheelFile -Leaf) } | ForEach-Object { ($_ -split '\s+')[0] }
        $actualHash = (Get-FileHash -Path $WheelFile -Algorithm SHA256).Hash.ToLower()
        
        if ($expectedHash -eq $actualHash) {
            Write-Success "Package integrity verified"
        } else {
            Write-Error "Package integrity check failed"
            Write-Error "Expected: $expectedHash"
            Write-Error "Actual: $actualHash"
            exit 1
        }
    } catch {
        Write-Warning "Failed to verify package integrity: $_"
    }
}

# Setup virtual environment
function New-VirtualEnvironment {
    Write-Info "Setting up virtual environment..."
    
    if (Test-Path $Script:VenvDir) {
        Write-Warning "Removing existing virtual environment..."
        Remove-Item -Path $Script:VenvDir -Recurse -Force
    }
    
    Set-Location $InstallPath
    & uv venv .venv
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to create virtual environment"
        exit 1
    }
    
    Write-Success "Virtual environment created"
}

# Install package
function Install-Package {
    param([string]$WheelFile)
    
    Write-Info "Installing Discord ADR Bot..."
    
    Set-Location $InstallPath
    & uv pip install $WheelFile
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to install package"
        exit 1
    }
    
    Write-Success "Package installed successfully"
}

# Setup configuration
function New-Configuration {
    Write-Info "Setting up configuration..."
    
    $envTemplate = ".env.example"
    $envTarget = "$InstallPath\.env"
    
    if (Test-Path $envTemplate) {
        Copy-Item $envTemplate $envTarget
        Write-Info "Configuration template copied to: $envTarget"
    } else {
        # Create basic .env template
        $envContent = @"
# Discord ADR Bot Configuration
# Configure with your settings

# Discord Bot Token (Required)
TOKEN=your_discord_bot_token_here

# Environment (development, staging, production)
ENVIRONMENT=production

# Logging
DEBUG=false
LOG_LEVEL=INFO

# Database settings
DB_POOL_SIZE=10
DB_QUERY_TIMEOUT=30

# Security
SECURITY_RATE_LIMIT_ENABLED=true
"@
        Set-Content -Path $envTarget -Value $envContent -Encoding UTF8
        Write-Info "Basic configuration template created: $envTarget"
    }
    
    Write-Info "Please edit the configuration file and add your Discord bot token."
}

# Create startup scripts
function New-StartupScripts {
    Write-Info "Creating startup scripts..."
    
    # Create batch file for easy startup
    $batchScript = "$InstallPath\start.bat"
    $batchContent = @"
@echo off
cd /d "$InstallPath"
call .venv\Scripts\activate.bat
python -m discord_adr_bot run %*
"@
    Set-Content -Path $batchScript -Value $batchContent -Encoding ASCII
    
    # Create PowerShell script
    $psScript = "$InstallPath\start.ps1"
    $psContent = @"
# Discord ADR Bot Startup Script
Set-Location '$InstallPath'
& '.\venv\Scripts\Activate.ps1'
& python -m discord_adr_bot run @args
"@
    Set-Content -Path $psScript -Value $psContent -Encoding UTF8
    
    Write-Success "Startup scripts created:"
    Write-Info "  Batch file: $batchScript"
    Write-Info "  PowerShell: $psScript"
}

# Validate installation
function Test-Installation {
    Write-Info "Validating installation..."
    
    try {
        Set-Location $InstallPath
        & .\.venv\Scripts\python.exe -c "import discord_adr_bot; print('Import successful')"
        
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Installation validation successful"
        } else {
            throw "Import test failed"
        }
    } catch {
        Write-Error "Installation validation failed: $_"
        exit 1
    }
}

# Show completion message
function Show-CompletionMessage {
    Write-Host ""
    Write-Success "🎉 Discord ADR Bot installation completed successfully!"
    Write-Host ""
    Write-Info "📍 Installation location: $InstallPath"
    Write-Info "📝 Configuration file: $InstallPath\.env"
    Write-Info "📋 Log file: $Script:LogFile"
    Write-Host ""
    Write-Info "📚 Next steps:"
    Write-Host "   1. Edit the configuration file: $InstallPath\.env"
    Write-Host "   2. Add your Discord bot token"
    Write-Host "   3. Start the bot: $InstallPath\start.bat"
    Write-Host ""
    Write-Info "💡 Quick start commands:"
    Write-Host "   • Batch: $InstallPath\start.bat"
    Write-Host "   • PowerShell: $InstallPath\start.ps1"
    Write-Host ""
}

# Main installation function
function Invoke-Installation {
    Write-Host "=== $Script:ScriptName v$Script:ScriptVersion ===" -ForegroundColor Cyan
    Write-Host ""
    
    if ($DryRun) {
        Write-Warning "DRY RUN MODE - No actual changes will be made"
        Write-Host ""
    }
    
    Test-SystemRequirements
    Install-Uv
    
    if (-not $DryRun) {
        New-InstallDirectory
        
        $wheelFile = Find-WheelFile
        Test-PackageIntegrity -WheelFile $wheelFile
        New-VirtualEnvironment
        Install-Package -WheelFile $wheelFile
        New-Configuration
        New-StartupScripts
        Test-Installation
        Show-CompletionMessage
    } else {
        Write-Info "DRY RUN: Would install to $InstallPath"
        Write-Info "DRY RUN: Would use wheel file: $(Find-WheelFile)"
    }
}

# Error handling
trap {
    Write-Error "Installation failed: $_"
    Write-Error "Check $Script:LogFile for details."
    exit 1
}

# Main execution
try {
    Invoke-Installation
} catch {
    Write-Error "Installation failed: $_"
    exit 1
}