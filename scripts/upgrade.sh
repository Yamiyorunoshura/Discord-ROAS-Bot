#!/bin/bash
# Discord ADR Bot v2.0 - Linux/macOS Upgrade Script
# Automated upgrade script with version detection and rollback support

set -euo pipefail

# Configuration
readonly SCRIPT_NAME="Discord ADR Bot Upgrader"
readonly SCRIPT_VERSION="2.1.0"
readonly BOT_NAME="discord-adr-bot"
readonly INSTALL_DIR="${HOME}/.local/share/discord-adr-bot"
readonly VENV_DIR="${INSTALL_DIR}/.venv"
readonly BACKUP_DIR="${INSTALL_DIR}/backups"
readonly LOG_FILE="${INSTALL_DIR}/upgrade.log"

# Command line options
ROLLBACK=false
FORCE=false
DRY_RUN=false

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --rollback)
                ROLLBACK=true
                shift
                ;;
            --force)
                FORCE=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

# Show help message
show_help() {
    cat << EOF
$SCRIPT_NAME v$SCRIPT_VERSION

Usage: $0 [OPTIONS]

OPTIONS:
    --rollback      Rollback to previous version
    --force         Force upgrade/rollback even if versions match
    --dry-run       Show what would be done without making changes
    -h, --help      Show this help message

EXAMPLES:
    $0                  # Upgrade to latest version
    $0 --rollback       # Rollback to previous version
    $0 --dry-run        # Preview upgrade actions
EOF
}

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

# Check if installation exists
check_installation() {
    if [[ ! -d "$INSTALL_DIR" ]]; then
        error "Discord ADR Bot is not installed in $INSTALL_DIR"
        error "Please run the install script first."
        exit 1
    fi
    
    if [[ ! -d "$VENV_DIR" ]]; then
        error "Virtual environment not found in $VENV_DIR"
        error "Installation appears to be corrupted. Please reinstall."
        exit 1
    fi
}

# Get current installed version
get_current_version() {
    if [[ -f "$INSTALL_DIR/version.txt" ]]; then
        cat "$INSTALL_DIR/version.txt"
    else
        # Try to get version from pip
        cd "$INSTALL_DIR"
        if source .venv/bin/activate 2>/dev/null && command -v pip >/dev/null; then
            pip show discord-adr-bot 2>/dev/null | grep "Version:" | cut -d' ' -f2 || echo "unknown"
        else
            echo "unknown"
        fi
    fi
}

# Get new version from wheel file
get_new_version() {
    local wheel_file="$1"
    local filename=$(basename "$wheel_file")
    
    # Extract version from filename (format: discord_adr_bot-X.Y.Z-py3-none-any.whl)
    if [[ "$filename" =~ discord_adr_bot-([0-9]+\.[0-9]+\.[0-9]+) ]]; then
        echo "${BASH_REMATCH[1]}"
    else
        echo "unknown"
    fi
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

# Create backup
create_backup() {
    local current_version="$1"
    local backup_path="${BACKUP_DIR}/v${current_version}_$(date +%Y%m%d_%H%M%S)"
    
    info "Creating backup of current installation..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        info "DRY RUN: Would create backup at $backup_path"
        return 0
    fi
    
    mkdir -p "$backup_path"
    
    # Backup virtual environment
    if [[ -d "$VENV_DIR" ]]; then
        info "Backing up virtual environment..."
        cp -r "$VENV_DIR" "$backup_path/"
    fi
    
    # Backup configuration
    if [[ -f "$INSTALL_DIR/.env" ]]; then
        cp "$INSTALL_DIR/.env" "$backup_path/"
    fi
    
    # Backup version info
    echo "$current_version" > "$backup_path/version.txt"
    
    # Save backup metadata
    cat > "$backup_path/backup_info.txt" << EOF
Backup Date: $(date)
Original Version: $current_version
Backup Path: $backup_path
Created By: $SCRIPT_NAME v$SCRIPT_VERSION
EOF
    
    success "Backup created: $backup_path"
    echo "$backup_path"
}

# Find latest backup
find_latest_backup() {
    if [[ ! -d "$BACKUP_DIR" ]]; then
        error "No backups found in $BACKUP_DIR"
        return 1
    fi
    
    local latest_backup=$(find "$BACKUP_DIR" -maxdepth 1 -type d -name "v*" | sort -r | head -1)
    
    if [[ -z "$latest_backup" ]]; then
        error "No version backups found"
        return 1
    fi
    
    echo "$latest_backup"
}

# Restore from backup
restore_backup() {
    local backup_path="$1"
    
    if [[ ! -d "$backup_path" ]]; then
        error "Backup directory not found: $backup_path"
        exit 1
    fi
    
    info "Restoring from backup: $backup_path"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        info "DRY RUN: Would restore from $backup_path"
        return 0
    fi
    
    # Stop any running bot instances
    info "Stopping any running bot instances..."
    pkill -f "python.*discord_adr_bot" || true
    
    # Remove current virtual environment
    if [[ -d "$VENV_DIR" ]]; then
        rm -rf "$VENV_DIR"
    fi
    
    # Restore virtual environment
    if [[ -d "$backup_path/.venv" ]]; then
        cp -r "$backup_path/.venv" "$VENV_DIR"
    else
        error "Virtual environment not found in backup"
        exit 1
    fi
    
    # Restore configuration (but don't overwrite if current exists)
    if [[ -f "$backup_path/.env" && ! -f "$INSTALL_DIR/.env" ]]; then
        cp "$backup_path/.env" "$INSTALL_DIR/"
    fi
    
    # Update version file
    if [[ -f "$backup_path/version.txt" ]]; then
        cp "$backup_path/version.txt" "$INSTALL_DIR/"
    fi
    
    success "Rollback completed successfully"
}

# Perform upgrade
perform_upgrade() {
    local wheel_file="$1"
    local new_version="$2"
    
    info "Upgrading to version $new_version..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        info "DRY RUN: Would upgrade to $new_version using $wheel_file"
        return 0
    fi
    
    # Stop any running bot instances
    info "Stopping any running bot instances..."
    pkill -f "python.*discord_adr_bot" || true
    
    # Upgrade package
    cd "$INSTALL_DIR"
    source .venv/bin/activate
    
    # Use absolute path for wheel file
    local abs_wheel_path
    if [[ "$wheel_file" == /* ]]; then
        abs_wheel_path="$wheel_file"
    else
        abs_wheel_path="$(cd "$(dirname "$wheel_file")" && pwd)/$(basename "$wheel_file")"
    fi
    
    uv pip install --upgrade "$abs_wheel_path"
    
    # Update version file
    echo "$new_version" > "$INSTALL_DIR/version.txt"
    
    success "Upgrade completed successfully"
}

# Validate installation
validate_installation() {
    info "Validating installation..."
    
    cd "$INSTALL_DIR"
    if source .venv/bin/activate && python -c "import discord_adr_bot; print('Import successful')" 2>/dev/null; then
        success "Installation validation successful"
        
        # Show version info
        local current_version=$(get_current_version)
        info "Current version: $current_version"
    else
        error "Installation validation failed"
        return 1
    fi
}

# Clean old backups (keep last 5)
cleanup_backups() {
    if [[ ! -d "$BACKUP_DIR" ]]; then
        return 0
    fi
    
    info "Cleaning up old backups..."
    
    local backup_count=$(find "$BACKUP_DIR" -maxdepth 1 -type d -name "v*" | wc -l)
    
    if [[ $backup_count -gt 5 ]]; then
        local old_backups=$(find "$BACKUP_DIR" -maxdepth 1 -type d -name "v*" | sort | head -n $((backup_count - 5)))
        
        if [[ -n "$old_backups" ]]; then
            echo "$old_backups" | while read -r backup; do
                info "Removing old backup: $(basename "$backup")"
                if [[ "$DRY_RUN" == "false" ]]; then
                    rm -rf "$backup"
                fi
            done
        fi
    fi
}

# Main upgrade function
main_upgrade() {
    local wheel_file=$(find_wheel_file)
    local current_version=$(get_current_version)
    local new_version=$(get_new_version "$wheel_file")
    
    info "Current version: $current_version"
    info "New version: $new_version"
    
    # Version comparison
    if [[ "$current_version" == "$new_version" && "$FORCE" == "false" ]]; then
        info "Already running the latest version ($new_version)"
        info "Use --force to reinstall the same version"
        exit 0
    fi
    
    # Create backup
    local backup_path=$(create_backup "$current_version")
    
    # Perform upgrade
    perform_upgrade "$wheel_file" "$new_version"
    
    # Validate
    if validate_installation; then
        success "🎉 Upgrade completed successfully!"
        info "Upgraded from $current_version to $new_version"
        info "Backup created at: $backup_path"
        cleanup_backups
    else
        error "Upgrade validation failed. Rolling back..."
        restore_backup "$backup_path"
        exit 1
    fi
}

# Main rollback function
main_rollback() {
    local current_version=$(get_current_version)
    local latest_backup=$(find_latest_backup)
    
    if [[ -z "$latest_backup" ]]; then
        error "No backups available for rollback"
        exit 1
    fi
    
    local backup_version=""
    if [[ -f "$latest_backup/version.txt" ]]; then
        backup_version=$(cat "$latest_backup/version.txt")
    fi
    
    info "Current version: $current_version"
    info "Rollback to version: $backup_version"
    info "Using backup: $latest_backup"
    
    if [[ "$current_version" == "$backup_version" && "$FORCE" == "false" ]]; then
        info "Already running version $backup_version"
        info "Use --force to force rollback"
        exit 0
    fi
    
    # Create backup of current state before rollback
    local pre_rollback_backup=$(create_backup "$current_version")
    
    # Perform rollback
    restore_backup "$latest_backup"
    
    # Validate
    if validate_installation; then
        success "🔄 Rollback completed successfully!"
        info "Rolled back from $current_version to $backup_version"
        info "Current state backed up at: $pre_rollback_backup"
    else
        error "Rollback validation failed"
        exit 1
    fi
}

# Main function
main() {
    echo "=== $SCRIPT_NAME v$SCRIPT_VERSION ==="
    echo
    
    parse_args "$@"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        warn "DRY RUN MODE - No actual changes will be made"
        echo
    fi
    
    check_installation
    
    # Create log directory
    mkdir -p "$(dirname "$LOG_FILE")"
    
    if [[ "$ROLLBACK" == "true" ]]; then
        main_rollback
    else
        main_upgrade
    fi
}

# Error handling
trap 'error "Operation failed. Check $LOG_FILE for details."; exit 1' ERR

# Run main function
main "$@"