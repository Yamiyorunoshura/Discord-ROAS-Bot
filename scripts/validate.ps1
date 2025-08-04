# Discord ADR Bot v2.0 - Windows PowerShell Validation Script
# Health check and validation for Discord ADR Bot installation

param(
    [string]$InstallPath = "$env:LOCALAPPDATA\discord-adr-bot",
    [switch]$Verbose,
    [switch]$Help
)

# Script Configuration
$Script:ScriptName = "Discord ADR Bot Validator"
$Script:ScriptVersion = "2.1.0"
$Script:BotName = "discord-adr-bot"
$Script:VenvDir = "$InstallPath\.venv"
$Script:ErrorActionPreference = "Continue"

# Test counters
$Script:TestsPassed = 0
$Script:TestsFailed = 0
$Script:Warnings = 0

# Show help message
function Show-Help {
    Write-Host "$Script:ScriptName v$Script:ScriptVersion" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage: .\validate.ps1 [OPTIONS]" -ForegroundColor White
    Write-Host ""
    Write-Host "OPTIONS:" -ForegroundColor Yellow
    Write-Host "    -InstallPath    Custom installation path (default: $env:LOCALAPPDATA\discord-adr-bot)"
    Write-Host "    -Verbose        Show detailed output"
    Write-Host "    -Help           Show this help message"
    Write-Host ""
    Write-Host "EXAMPLES:" -ForegroundColor Yellow
    Write-Host "    .\validate.ps1                    # Validate default installation"
    Write-Host "    .\validate.ps1 -Verbose           # Show detailed output"
}

if ($Help) {
    Show-Help
    exit 0
}

# Logging functions
function Write-Info { 
    param([string]$Message) 
    Write-Host "[INFO] $Message" -ForegroundColor Blue 
}

function Write-Success { 
    param([string]$Message) 
    Write-Host "[PASS] $Message" -ForegroundColor Green 
    $Script:TestsPassed++
}

function Write-Warning { 
    param([string]$Message) 
    Write-Host "[WARN] $Message" -ForegroundColor Yellow 
    $Script:Warnings++
}

function Write-Error { 
    param([string]$Message) 
    Write-Host "[FAIL] $Message" -ForegroundColor Red 
    $Script:TestsFailed++
}

# Test functions
function Test-PythonVersion {
    Write-Info "Testing Python version..."
    
    try {
        $pythonVersion = & python --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            $versionMatch = $pythonVersion -match "Python (\d+)\.(\d+)"
            if ($versionMatch) {
                $majorVersion = [int]$Matches[1]
                $minorVersion = [int]$Matches[2]
                
                if ($majorVersion -gt 3 -or ($majorVersion -eq 3 -and $minorVersion -ge 12)) {
                    Write-Success "Python $($pythonVersion -replace 'Python ', '') is installed and compatible"
                } else {
                    Write-Error "Python $majorVersion.$minorVersion is too old. Requires Python 3.12+"
                }
            } else {
                Write-Warning "Could not parse Python version: $pythonVersion"
            }
        } else {
            Write-Error "Python is not installed or not in PATH"
        }
    } catch {
        Write-Error "Python is not installed or not in PATH"
    }
}

function Test-UvInstallation {
    Write-Info "Testing uv package manager..."
    
    try {
        $uvVersion = & uv --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Success "uv is installed: $($uvVersion -replace 'uv ', '')"
        } else {
            Write-Error "uv package manager is not installed"
        }
    } catch {
        Write-Error "uv package manager is not installed"
    }
}

function Test-InstallationDirectory {
    Write-Info "Testing installation directory..."
    
    if (Test-Path $InstallPath) {
        Write-Success "Installation directory exists: $InstallPath"
        
        # Check permissions
        try {
            $testFile = "$InstallPath\test_write.tmp"
            "test" | Out-File -FilePath $testFile -Encoding UTF8
            Remove-Item $testFile -Force
            Write-Success "Installation directory has write permissions"
        } catch {
            Write-Error "Installation directory is not writable"
        }
    } else {
        Write-Error "Installation directory not found: $InstallPath"
    }
}

function Test-VirtualEnvironment {
    Write-Info "Testing virtual environment..."
    
    if (Test-Path $Script:VenvDir) {
        Write-Success "Virtual environment directory exists"
        
        # Test activation script
        $activateScript = "$Script:VenvDir\Scripts\Activate.ps1"
        if (Test-Path $activateScript) {
            Write-Success "Virtual environment activation script exists"
        } else {
            Write-Error "Virtual environment activation script missing"
        }
        
        # Test Python in venv
        $pythonExe = "$Script:VenvDir\Scripts\python.exe"
        if (Test-Path $pythonExe) {
            Write-Success "Python interpreter exists in virtual environment"
        } else {
            Write-Error "Python interpreter missing in virtual environment"
        }
    } else {
        Write-Error "Virtual environment directory not found: $Script:VenvDir"
    }
}

function Test-PackageInstallation {
    Write-Info "Testing package installation..."
    
    if (Test-Path $Script:VenvDir) {
        try {
            Set-Location $InstallPath
            & "$Script:VenvDir\Scripts\Activate.ps1"
            
            # Test import
            $importTest = & python -c "import discord_adr_bot; print('OK')" 2>&1
            if ($LASTEXITCODE -eq 0 -and $importTest -eq "OK") {
                Write-Success "Discord ADR Bot package is importable"
            } else {
                Write-Error "Discord ADR Bot package import failed"
            }
            
            # Test version
            $botVersion = & python -c "import discord_adr_bot; print(discord_adr_bot.__version__)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $botVersion) {
                Write-Success "Bot version: $botVersion"
            } else {
                Write-Warning "Could not determine bot version"
            }
            
            # Test dependencies
            $deps = @("discord", "aiohttp", "aiosqlite", "pydantic")
            foreach ($dep in $deps) {
                $depTest = & python -c "import $dep; print('OK')" 2>$null
                if ($LASTEXITCODE -eq 0 -and $depTest -eq "OK") {
                    Write-Success "Dependency '$dep' is available"
                } else {
                    Write-Error "Dependency '$dep' is missing"
                }
            }
            
        } catch {
            Write-Error "Cannot test package installation: $_"
        }
    } else {
        Write-Error "Virtual environment not found, skipping package tests"
    }
}

function Test-Configuration {
    Write-Info "Testing configuration..."
    
    $envFile = "$InstallPath\.env"
    if (Test-Path $envFile) {
        Write-Success "Configuration file exists: $envFile"
        
        # Check for required variables
        $requiredVars = @("TOKEN")
        $envContent = Get-Content $envFile -Raw
        
        foreach ($var in $requiredVars) {
            if ($envContent -match "^$var=") {
                if ($envContent -match "^$var=.*your.*token.*here") {
                    Write-Warning "Variable '$var' still has placeholder value"
                } else {
                    Write-Success "Variable '$var' is configured"
                }
            } else {
                Write-Error "Required variable '$var' is missing from configuration"
            }
        }
    } else {
        Write-Error "Configuration file not found: $envFile"
    }
}

function Test-Directories {
    Write-Info "Testing directory structure..."
    
    $dirs = @("$InstallPath", "$InstallPath\backups")
    foreach ($dir in $dirs) {
        if (Test-Path $dir) {
            Write-Success "Directory exists: $dir"
        } else {
            Write-Warning "Directory missing: $dir"
        }
    }
}

function Test-Scripts {
    Write-Info "Testing startup scripts..."
    
    $scripts = @("$InstallPath\start.bat", "$InstallPath\start.ps1")
    foreach ($script in $scripts) {
        if (Test-Path $script) {
            Write-Success "Script exists: $(Split-Path $script -Leaf)"
        } else {
            Write-Warning "Script missing: $(Split-Path $script -Leaf)"
        }
    }
}

function Test-NetworkConnectivity {
    Write-Info "Testing network connectivity..."
    
    # Test basic internet connectivity
    try {
        $ping = Test-Connection -ComputerName "8.8.8.8" -Count 1 -Quiet
        if ($ping) {
            Write-Success "Basic internet connectivity works"
        } else {
            Write-Error "No internet connectivity"
            return
        }
    } catch {
        Write-Error "No internet connectivity"
        return
    }
    
    # Test Discord API connectivity
    try {
        $response = Invoke-WebRequest -Uri "https://discord.com/api/v10/gateway" -TimeoutSec 10 -UseBasicParsing
        if ($response.StatusCode -eq 200) {
            Write-Success "Discord API is reachable"
        } else {
            Write-Error "Cannot reach Discord API (Status: $($response.StatusCode))"
        }
    } catch {
        Write-Error "Cannot reach Discord API: $_"
    }
}

function Test-SystemResources {
    Write-Info "Testing system resources..."
    
    # Check available memory
    try {
        $memory = Get-CimInstance -ClassName Win32_OperatingSystem
        $availableMemoryMB = [math]::Round($memory.FreePhysicalMemory / 1024)
        
        if ($availableMemoryMB -gt 512) {
            Write-Success "Sufficient memory available: ${availableMemoryMB}MB"
        } else {
            Write-Warning "Low available memory: ${availableMemoryMB}MB (recommended: 512MB+)"
        }
    } catch {
        Write-Warning "Cannot check memory usage: $_"
    }
    
    # Check disk space
    try {
        $drive = (Get-Item $InstallPath).PSDrive
        $freeSpaceMB = [math]::Round($drive.Free / 1MB)
        
        if ($freeSpaceMB -gt 100) {
            Write-Success "Sufficient disk space: ${freeSpaceMB}MB available"
        } else {
            Write-Warning "Low disk space: ${freeSpaceMB}MB available (recommended: 100MB+)"
        }
    } catch {
        Write-Warning "Cannot check disk usage: $_"
    }
}

function Test-FilePermissions {
    Write-Info "Testing file permissions..."
    
    # Test log directory
    $logDir = "$InstallPath\logs"
    if (Test-Path $logDir) {
        try {
            $testFile = "$logDir\test_write.tmp"
            "test" | Out-File -FilePath $testFile -Encoding UTF8
            Remove-Item $testFile -Force
            Write-Success "Log directory is writable"
        } catch {
            Write-Error "Log directory is not writable"
        }
    } else {
        Write-Warning "Log directory does not exist: $logDir"
    }
    
    # Test data directory
    $dataDir = "$InstallPath\data"
    if (Test-Path $dataDir) {
        try {
            $testFile = "$dataDir\test_write.tmp"
            "test" | Out-File -FilePath $testFile -Encoding UTF8
            Remove-Item $testFile -Force
            Write-Success "Data directory is writable"
        } catch {
            Write-Error "Data directory is not writable"
        }
    } else {
        Write-Warning "Data directory does not exist: $dataDir"
    }
}

function Invoke-HealthCheck {
    Write-Info "Running Discord ADR Bot health check..."
    
    if (Test-Path $Script:VenvDir) {
        try {
            Set-Location $InstallPath
            & "$Script:VenvDir\Scripts\Activate.ps1"
            
            # Try to run health check command
            $healthCheck = & python -m discord_adr_bot health-check 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Success "Bot health check passed"
            } else {
                Write-Warning "Bot health check command not available or failed"
            }
        } catch {
            Write-Error "Cannot run health check: $_"
        }
    } else {
        Write-Error "Virtual environment not found, skipping health check"
    }
}

# Main validation function
function Invoke-Main {
    Write-Host "=== $Script:ScriptName v$Script:ScriptVersion ===" -ForegroundColor Cyan
    Write-Host "Starting validation of Discord ADR Bot installation..." -ForegroundColor White
    Write-Host ""

    Test-PythonVersion
    Test-UvInstallation
    Test-InstallationDirectory
    Test-VirtualEnvironment
    Test-PackageInstallation
    Test-Configuration
    Test-Directories
    Test-Scripts
    Test-NetworkConnectivity
    Test-SystemResources
    Test-FilePermissions
    Invoke-HealthCheck

    Write-Host ""
    Write-Host "=== Validation Summary ===" -ForegroundColor Cyan
    Write-Host "Tests passed: $Script:TestsPassed" -ForegroundColor Green
    
    if ($Script:Warnings -gt 0) {
        Write-Host "Warnings: $Script:Warnings" -ForegroundColor Yellow
    }
    
    if ($Script:TestsFailed -gt 0) {
        Write-Host "Tests failed: $Script:TestsFailed" -ForegroundColor Red
        Write-Host ""
        Write-Host "❌ Installation validation failed!" -ForegroundColor Red
        Write-Host "Please check the failed tests above and refer to the troubleshooting guide."
        exit 1
    } else {
        Write-Host ""
        if ($Script:Warnings -gt 0) {
            Write-Host "⚠️  Installation validation completed with warnings!" -ForegroundColor Yellow
            Write-Host "The bot should work, but you may want to address the warnings above."
        } else {
            Write-Host "✅ Installation validation successful!" -ForegroundColor Green
            Write-Host "Discord ADR Bot is properly installed and ready to use."
        }
        
        Write-Host ""
        Write-Host "Next steps:" -ForegroundColor Yellow
        Write-Host "1. Edit the configuration file: $InstallPath\.env"
        Write-Host "2. Add your Discord bot token"
        Write-Host "3. Start the bot: $InstallPath\start.bat"
        
        exit 0
    }
}

# Main execution
try {
    Invoke-Main
} catch {
    Write-Host "Validation failed with error: $_" -ForegroundColor Red
    exit 1
}