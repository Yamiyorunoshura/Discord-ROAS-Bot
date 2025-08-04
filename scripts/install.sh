#!/bin/bash
# Discord ADR Bot v2.0 - Linux/macOS Installation Script
# Automated installation script with uv environment setup

set -euo pipefail

# Configuration
readonly SCRIPT_NAME="Discord ADR Bot Installer"
readonly SCRIPT_VERSION="2.1.0"
readonly BOT_NAME="discord-adr-bot"
readonly INSTALL_DIR="${HOME}/.local/share/discord-adr-bot"
readonly VENV_DIR="${INSTALL_DIR}/.venv"
readonly LOG_FILE="${INSTALL_DIR}/install.log"

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# Logging function
log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${timestamp} [${level}] ${message}" | tee -a "${LOG_FILE}" 2>/dev/null || echo -e "${timestamp} [${level}] ${message}"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $*"
    log "INFO" "$*"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*"
    log "SUCCESS" "$*"
}

warn() {
    echo -e "${YELLOW}[WARNING]${NC} $*"
    log "WARNING" "$*"
}

error() {
    echo -e "${RED}[ERROR]${NC} $*" >&2
    log "ERROR" "$*"
}

# Check if running as root
check_not_root() {
    if [[ $EUID -eq 0 ]]; then
        error "This script should not be run as root for security reasons."
        error "Please run as a regular user."
        exit 1
    fi
}

# Check system requirements
check_system_requirements() {
    info "Checking system requirements..."
    
    # Check Python version
    if ! command -v python3 &> /dev/null; then
        error "Python 3 is not installed. Please install Python 3.12 or later."
        exit 1
    fi
    
    local python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    local required_version="3.12"
    
    if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 12) else 1)" 2>/dev/null; then
        error "Python ${required_version} or later is required. Found: ${python_version}"
        error "Please upgrade Python to version ${required_version} or later."
        exit 1
    fi
    
    success "Python ${python_version} detected"
}

# Check and install uv
check_uv() {
    info "Checking uv package manager..."
    
    if command -v uv &> /dev/null; then
        local uv_version=$(uv --version | cut -d' ' -f2)
        success "uv ${uv_version} is already installed"
        return 0
    fi
    
    info "uv not found. Installing uv..."
    if command -v curl &> /dev/null; then
        curl -LsSf https://astral.sh/uv/install.sh | sh
    elif command -v wget &> /dev/null; then
        wget -qO- https://astral.sh/uv/install.sh | sh
    else
        error "Neither curl nor wget is available. Please install one of them first."
        exit 1
    fi
    
    # Add uv to PATH for current session
    export PATH="$HOME/.cargo/bin:$PATH"
    
    if command -v uv &> /dev/null; then
        success "uv installed successfully"
    else
        error "Failed to install uv. Please install manually: https://docs.astral.sh/uv/"
        exit 1
    fi
}

# Create installation directory
create_install_dir() {
    info "Creating installation directory..."
    mkdir -p "${INSTALL_DIR}"
    mkdir -p "$(dirname "${LOG_FILE}")"
    success "Installation directory created: ${INSTALL_DIR}"
}

# Find wheel file
find_wheel_file() {
    local wheel_file=""
    
    # Look for wheel file in dist directory
    if [[ -d "dist" ]]; then
        wheel_file=$(find dist -name "*.whl" -type f | head -1)
    fi
    
    # If not found, look in current directory
    if [[ -z "$wheel_file" ]]; then
        wheel_file=$(find . -name "*.whl" -type f | head -1)
    fi
    
    if [[ -z "$wheel_file" ]]; then
        error "No wheel (.whl) file found. Please run 'make dist' first."
        exit 1
    fi
    
    echo "$wheel_file"
}

# Verify checksum
verify_checksum() {
    local wheel_file="$1"
    local checksum_file="dist/SHA256SUMS"
    
    if [[ ! -f "$checksum_file" ]]; then
        warn "Checksum file not found. Skipping verification."
        return 0
    fi
    
    info "Verifying package integrity..."
    
    if command -v sha256sum &> /dev/null; then
        if cd "$(dirname "$wheel_file")" && sha256sum -c "$checksum_file" &> /dev/null; then
            success "Package integrity verified"
        else
            error "Package integrity check failed"
            exit 1
        fi
    else
        warn "sha256sum not available. Skipping checksum verification."
    fi
}

# Setup virtual environment
setup_venv() {
    info "Setting up virtual environment..."
    
    if [[ -d "$VENV_DIR" ]]; then
        warn "Virtual environment already exists. Removing old environment..."
        rm -rf "$VENV_DIR"
    fi
    
    cd "$INSTALL_DIR"
    uv venv .venv
    success "Virtual environment created"
}

# Install package
install_package() {
    local wheel_file="$1"
    
    info "Installing Discord ADR Bot..."
    cd "$INSTALL_DIR"
    
    # Use absolute path for wheel file
    local abs_wheel_path
    if [[ "$wheel_file" == /* ]]; then
        abs_wheel_path="$wheel_file"
    else
        abs_wheel_path="$(pwd)/$wheel_file"
    fi
    
    uv pip install "$abs_wheel_path"
    success "Package installed successfully"
}

# Setup configuration
setup_config() {
    info "Setting up configuration..."
    
    local env_template=".env.example"
    local env_target="${INSTALL_DIR}/.env"
    
    if [[ -f "$env_template" ]]; then
        cp "$env_template" "$env_target"
        info "Configuration template copied to: $env_target"
        info "Please edit $env_target and add your Discord bot token."
    else
        # Create basic .env template
        cat > "$env_target" << 'EOF'
# Discord ADR Bot Configuration
# Copy this file and configure with your settings

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
EOF
        info "Basic configuration template created: $env_target"
        info "Please edit the configuration file and add your Discord bot token."
    fi
}

# Create startup script
create_startup_script() {
    info "Creating startup script..."
    
    local startup_script="${INSTALL_DIR}/start.sh"
    
    cat > "$startup_script" << EOF
#!/bin/bash
# Discord ADR Bot Startup Script

cd "${INSTALL_DIR}"
source .venv/bin/activate
exec python -m discord_adr_bot run "\$@"
EOF
    
    chmod +x "$startup_script"
    
    # Create symlink in user's local bin if it exists
    local local_bin="${HOME}/.local/bin"
    if [[ -d "$local_bin" ]]; then
        ln -sf "$startup_script" "${local_bin}/discord-adr-bot"
        success "Command 'discord-adr-bot' available in PATH"
    fi
    
    success "Startup script created: $startup_script"
}

# Validation
validate_installation() {
    info "Validating installation..."
    
    cd "$INSTALL_DIR"
    if source .venv/bin/activate && python -c "import discord_adr_bot; print('Import successful')" 2>/dev/null; then
        success "Installation validation successful"
    else
        error "Installation validation failed"
        exit 1
    fi
}

# Display completion message
show_completion_message() {
    echo
    success "🎉 Discord ADR Bot installation completed successfully!"
    echo
    info "📍 Installation location: $INSTALL_DIR"
    info "📝 Configuration file: $INSTALL_DIR/.env"
    info "📋 Log file: $LOG_FILE"
    echo
    info "📚 Next steps:"
    echo "   1. Edit the configuration file: $INSTALL_DIR/.env"
    echo "   2. Add your Discord bot token"
    echo "   3. Start the bot: $INSTALL_DIR/start.sh"
    echo
    if [[ -f "${HOME}/.local/bin/discord-adr-bot" ]]; then
        info "💡 Quick start: discord-adr-bot"
    fi
    echo
}

# Main installation function
main() {
    echo "=== $SCRIPT_NAME v$SCRIPT_VERSION ==="
    echo
    
    check_not_root
    check_system_requirements
    check_uv
    create_install_dir
    
    local wheel_file
    wheel_file=$(find_wheel_file)
    info "Found package: $wheel_file"
    
    verify_checksum "$wheel_file"
    setup_venv
    install_package "$wheel_file"
    setup_config
    create_startup_script
    validate_installation
    show_completion_message
}

# Error handling
trap 'error "Installation failed. Check $LOG_FILE for details."; exit 1' ERR

# Run main function
main "$@"