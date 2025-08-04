#!/bin/bash
# Discord ADR Bot v2.0 - Installation Validation Script
# Health check and validation for Discord ADR Bot installation

set -euo pipefail

# Configuration
readonly SCRIPT_NAME="Discord ADR Bot Validator"
readonly SCRIPT_VERSION="2.1.0"
readonly BOT_NAME="discord-adr-bot"
readonly INSTALL_DIR="${HOME}/.local/share/discord-adr-bot"
readonly VENV_DIR="${INSTALL_DIR}/.venv"

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# Test results
TESTS_PASSED=0
TESTS_FAILED=0
WARNINGS=0

# Logging functions
info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

success() {
    echo -e "${GREEN}[PASS]${NC} $*"
    ((TESTS_PASSED++))
}

warning() {
    echo -e "${YELLOW}[WARN]${NC} $*"
    ((WARNINGS++))
}

error() {
    echo -e "${RED}[FAIL]${NC} $*"
    ((TESTS_FAILED++))
}

# Test functions
test_python_version() {
    info "Testing Python version..."
    
    if command -v python3 &> /dev/null; then
        local python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        
        if python3 -c "import sys; exit(0 if sys.version_info >= (3, 12) else 1)" 2>/dev/null; then
            success "Python ${python_version} is installed and compatible"
        else
            error "Python ${python_version} is too old. Requires Python 3.12+"
        fi
    else
        error "Python 3 is not installed or not in PATH"
    fi
}

test_uv_installation() {
    info "Testing uv package manager..."
    
    if command -v uv &> /dev/null; then
        local uv_version=$(uv --version | cut -d' ' -f2)
        success "uv ${uv_version} is installed"
    else
        error "uv package manager is not installed"
    fi
}

test_installation_directory() {
    info "Testing installation directory..."
    
    if [[ -d "$INSTALL_DIR" ]]; then
        success "Installation directory exists: $INSTALL_DIR"
        
        # Check permissions
        if [[ -r "$INSTALL_DIR" && -w "$INSTALL_DIR" ]]; then
            success "Installation directory has correct permissions"
        else
            error "Installation directory has incorrect permissions"
        fi
    else
        error "Installation directory not found: $INSTALL_DIR"
    fi
}

test_virtual_environment() {
    info "Testing virtual environment..."
    
    if [[ -d "$VENV_DIR" ]]; then
        success "Virtual environment directory exists"
        
        # Test activation
        if [[ -f "$VENV_DIR/bin/activate" ]]; then
            success "Virtual environment activation script exists"
        else
            error "Virtual environment activation script missing"
        fi
        
        # Test Python in venv
        if [[ -x "$VENV_DIR/bin/python" ]]; then
            success "Python interpreter exists in virtual environment"
        else
            error "Python interpreter missing in virtual environment"
        fi
    else
        error "Virtual environment directory not found: $VENV_DIR"
    fi
}

test_package_installation() {
    info "Testing package installation..."
    
    if [[ -d "$VENV_DIR" ]]; then
        cd "$INSTALL_DIR"
        if source .venv/bin/activate 2>/dev/null; then
            # Test import
            if python -c "import discord_adr_bot" 2>/dev/null; then
                success "Discord ADR Bot package is importable"
            else
                error "Discord ADR Bot package import failed"
            fi
            
            # Test version
            local bot_version=$(python -c "import discord_adr_bot; print(discord_adr_bot.__version__)" 2>/dev/null || echo "unknown")
            if [[ "$bot_version" != "unknown" ]]; then
                success "Bot version: $bot_version"
            else
                warning "Could not determine bot version"
            fi
            
            # Test dependencies
            local deps=("discord" "aiohttp" "aiosqlite" "pydantic")
            for dep in "${deps[@]}"; do
                if python -c "import $dep" 2>/dev/null; then
                    success "Dependency '$dep' is available"
                else
                    error "Dependency '$dep' is missing"
                fi
            done
            
            deactivate 2>/dev/null || true
        else
            error "Cannot activate virtual environment"
        fi
    else
        error "Virtual environment not found, skipping package tests"
    fi
}

test_configuration() {
    info "Testing configuration..."
    
    local env_file="$INSTALL_DIR/.env"
    if [[ -f "$env_file" ]]; then
        success "Configuration file exists: $env_file"
        
        # Check file permissions
        local perms=$(stat -c "%a" "$env_file" 2>/dev/null || stat -f "%p" "$env_file" 2>/dev/null | tail -c 3)
        if [[ "$perms" == "600" ]] || [[ "$perms" == "644" ]]; then
            success "Configuration file has secure permissions"
        else
            warning "Configuration file permissions should be 600 or 644 (current: $perms)"
        fi
        
        # Check for required variables
        local required_vars=("TOKEN")
        for var in "${required_vars[@]}"; do
            if grep -q "^${var}=" "$env_file"; then
                if grep -q "^${var}=.*your.*token.*here" "$env_file"; then
                    warning "Variable '$var' still has placeholder value"
                else
                    success "Variable '$var' is configured"
                fi
            else
                error "Required variable '$var' is missing from configuration"
            fi
        done
    else
        error "Configuration file not found: $env_file"
    fi
}

test_directories() {
    info "Testing directory structure..."
    
    local dirs=("$INSTALL_DIR" "$INSTALL_DIR/backups")
    for dir in "${dirs[@]}"; do
        if [[ -d "$dir" ]]; then
            success "Directory exists: $dir"
        else
            warning "Directory missing: $dir"
        fi
    done
}

test_scripts() {
    info "Testing startup scripts..."
    
    local scripts=("$INSTALL_DIR/start.sh")
    for script in "${scripts[@]}"; do
        if [[ -f "$script" ]]; then
            if [[ -x "$script" ]]; then
                success "Script exists and is executable: $(basename "$script")"
            else
                warning "Script exists but is not executable: $(basename "$script")"
            fi
        else
            warning "Script missing: $(basename "$script")"
        fi
    done
}

test_network_connectivity() {
    info "Testing network connectivity..."
    
    # Test basic internet connectivity
    if ping -c 1 8.8.8.8 &> /dev/null; then
        success "Basic internet connectivity works"
    else
        error "No internet connectivity"
        return
    fi
    
    # Test Discord API connectivity
    if command -v curl &> /dev/null; then
        if curl -s --max-time 10 -I https://discord.com/api/v10/gateway | grep -q "200 OK"; then
            success "Discord API is reachable"
        else
            error "Cannot reach Discord API"
        fi
    else
        warning "curl not available, skipping Discord API test"
    fi
}

test_system_resources() {
    info "Testing system resources..."
    
    # Check available memory
    if command -v free &> /dev/null; then
        local mem_mb=$(free -m | awk 'NR==2{printf "%.0f", $7}')
        if [[ $mem_mb -gt 512 ]]; then
            success "Sufficient memory available: ${mem_mb}MB"
        else
            warning "Low available memory: ${mem_mb}MB (recommended: 512MB+)"
        fi
    else
        warning "Cannot check memory usage (free command not available)"
    fi
    
    # Check disk space
    if command -v df &> /dev/null; then
        local disk_mb=$(df "$INSTALL_DIR" | awk 'NR==2 {print int($4/1024)}')
        if [[ $disk_mb -gt 100 ]]; then
            success "Sufficient disk space: ${disk_mb}MB available"
        else
            warning "Low disk space: ${disk_mb}MB available (recommended: 100MB+)"
        fi
    else
        warning "Cannot check disk usage (df command not available)"
    fi
}

test_file_permissions() {
    info "Testing file permissions..."
    
    # Test log directory
    local log_dir="$INSTALL_DIR/logs"
    if [[ -d "$log_dir" ]]; then
        if [[ -w "$log_dir" ]]; then
            success "Log directory is writable"
        else
            error "Log directory is not writable"
        fi
    else
        warning "Log directory does not exist: $log_dir"
    fi
    
    # Test data directory
    local data_dir="$INSTALL_DIR/data"
    if [[ -d "$data_dir" ]]; then
        if [[ -w "$data_dir" ]]; then
            success "Data directory is writable"
        else
            error "Data directory is not writable"
        fi
    else
        warning "Data directory does not exist: $data_dir"
    fi
}

run_health_check() {
    info "Running Discord ADR Bot health check..."
    
    if [[ -d "$VENV_DIR" ]]; then
        cd "$INSTALL_DIR"
        if source .venv/bin/activate 2>/dev/null; then
            # Try to run health check command
            if python -m discord_adr_bot health-check &> /dev/null; then
                success "Bot health check passed"
            else
                warning "Bot health check command not available or failed"
            fi
            
            deactivate 2>/dev/null || true
        else
            error "Cannot activate virtual environment for health check"
        fi
    else
        error "Virtual environment not found, skipping health check"
    fi
}

# Main validation function
main() {
    echo "=== $SCRIPT_NAME v$SCRIPT_VERSION ==="
    echo "Starting validation of Discord ADR Bot installation..."
    echo

    test_python_version
    test_uv_installation
    test_installation_directory
    test_virtual_environment
    test_package_installation
    test_configuration
    test_directories
    test_scripts
    test_network_connectivity
    test_system_resources
    test_file_permissions
    run_health_check

    echo
    echo "=== Validation Summary ==="
    echo -e "${GREEN}Tests passed: $TESTS_PASSED${NC}"
    
    if [[ $WARNINGS -gt 0 ]]; then
        echo -e "${YELLOW}Warnings: $WARNINGS${NC}"
    fi
    
    if [[ $TESTS_FAILED -gt 0 ]]; then
        echo -e "${RED}Tests failed: $TESTS_FAILED${NC}"
        echo
        echo "❌ Installation validation failed!"
        echo "Please check the failed tests above and refer to the troubleshooting guide."
        exit 1
    else
        echo
        if [[ $WARNINGS -gt 0 ]]; then
            echo "⚠️  Installation validation completed with warnings!"
            echo "The bot should work, but you may want to address the warnings above."
        else
            echo "✅ Installation validation successful!"
            echo "Discord ADR Bot is properly installed and ready to use."
        fi
        
        echo
        echo "Next steps:"
        echo "1. Edit the configuration file: $INSTALL_DIR/.env"
        echo "2. Add your Discord bot token"
        echo "3. Start the bot: $INSTALL_DIR/start.sh"
        
        exit 0
    fi
}

# Run validation
main "$@"