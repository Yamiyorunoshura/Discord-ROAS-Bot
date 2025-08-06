#!/bin/bash

# Environment Configuration Loader
# Loads environment-specific configurations for deployment

set -euo pipefail

# Default values
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_CONFIG_DIR="$PROJECT_ROOT/.github/environments"

# Function: Load environment configuration
load_environment_config() {
    local environment="$1"
    local config_file="$ENV_CONFIG_DIR/$environment.yml"
    
    if [[ ! -f "$config_file" ]]; then
        echo "❌ Environment configuration not found: $config_file"
        exit 1
    fi
    
    echo "📋 Loading configuration for environment: $environment"
    
    # Export common environment variables
    export ENVIRONMENT="$environment"
    export CONFIG_FILE="$config_file"
    
    # Parse YAML and export variables (requires yq or python)
    if command -v yq >/dev/null 2>&1; then
        # Use yq if available
        while IFS='=' read -r key value; do
            if [[ -n "$key" && -n "$value" ]]; then
                export "$key"="$value"
                echo "  ✓ $key=$value"
            fi
        done < <(yq eval '.variables | to_entries | .[] | .key + "=" + .value' "$config_file" 2>/dev/null || true)
    else
        # Fallback to Python
        python3 -c "
import yaml
import os
import sys

try:
    with open('$config_file', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    variables = config.get('variables', {})
    for key, value in variables.items():
        os.environ[key] = str(value)
        print(f'  ✓ {key}={value}')
        
except Exception as e:
    print(f'❌ Error parsing configuration: {e}', file=sys.stderr)
    sys.exit(1)
"
    fi
}

# Function: Validate required secrets
validate_secrets() {
    local environment="$1"
    local config_file="$ENV_CONFIG_DIR/$environment.yml"
    
    echo "🔐 Validating required secrets for $environment..."
    
    # Get required secrets from config
    local secrets
    if command -v yq >/dev/null 2>&1; then
        secrets=$(yq eval '.secrets[]' "$config_file" 2>/dev/null || echo "")
    else
        secrets=$(python3 -c "
import yaml
try:
    with open('$config_file', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    secrets = config.get('secrets', [])
    for secret in secrets:
        print(secret)
except:
    pass
" 2>/dev/null || echo "")
    fi
    
    # Check each required secret
    local missing_secrets=()
    while IFS= read -r secret; do
        if [[ -n "$secret" ]]; then
            if [[ -z "${!secret:-}" ]]; then
                missing_secrets+=("$secret")
            else
                echo "  ✓ $secret is configured"
            fi
        fi
    done <<< "$secrets"
    
    if [[ ${#missing_secrets[@]} -gt 0 ]]; then
        echo "❌ Missing required secrets:"
        printf '  - %s\n' "${missing_secrets[@]}"
        echo ""
        echo "Please configure these secrets in GitHub repository settings:"
        echo "Settings → Secrets and variables → Actions → Environment secrets"
        return 1
    fi
    
    echo "✅ All required secrets are configured"
}

# Function: Get deployment strategy
get_deployment_strategy() {
    local environment="$1"
    local config_file="$ENV_CONFIG_DIR/$environment.yml"
    
    if command -v yq >/dev/null 2>&1; then
        yq eval '.deployment.strategy' "$config_file" 2>/dev/null || echo "rolling_update"
    else
        python3 -c "
import yaml
try:
    with open('$config_file', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    print(config.get('deployment', {}).get('strategy', 'rolling_update'))
except:
    print('rolling_update')
" 2>/dev/null || echo "rolling_update"
    fi
}

# Function: Get resource limits
get_resource_limits() {
    local environment="$1"
    local config_file="$ENV_CONFIG_DIR/$environment.yml"
    
    echo "📊 Resource configuration for $environment:"
    
    local memory_limit cpu_limit replica_count
    if command -v yq >/dev/null 2>&1; then
        memory_limit=$(yq eval '.variables.MEMORY_LIMIT' "$config_file" 2>/dev/null || echo "1Gi")
        cpu_limit=$(yq eval '.variables.CPU_LIMIT' "$config_file" 2>/dev/null || echo "1.0")
        replica_count=$(yq eval '.variables.REPLICA_COUNT' "$config_file" 2>/dev/null || echo "1")
    else
        memory_limit=$(python3 -c "
import yaml
try:
    with open('$config_file', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    print(config.get('variables', {}).get('MEMORY_LIMIT', '1Gi'))
except:
    print('1Gi')
" 2>/dev/null || echo "1Gi")
        
        cpu_limit=$(python3 -c "
import yaml
try:
    with open('$config_file', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    print(config.get('variables', {}).get('CPU_LIMIT', '1.0'))
except:
    print('1.0')
" 2>/dev/null || echo "1.0")
        
        replica_count=$(python3 -c "
import yaml
try:
    with open('$config_file', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    print(config.get('variables', {}).get('REPLICA_COUNT', '1'))
except:
    print('1')
" 2>/dev/null || echo "1")
    fi
    
    echo "  Memory: $memory_limit"
    echo "  CPU: $cpu_limit"
    echo "  Replicas: $replica_count"
    
    export MEMORY_LIMIT="$memory_limit"
    export CPU_LIMIT="$cpu_limit"
    export REPLICA_COUNT="$replica_count"
}

# Function: Display environment summary
display_environment_summary() {
    local environment="$1"
    
    echo ""
    echo "🎯 Environment Summary: $environment"
    echo "───────────────────────────────────────"
    echo "Registry: ${CONTAINER_REGISTRY:-ghcr.io}"
    echo "Namespace: ${DEPLOY_NAMESPACE:-default}"
    echo "Strategy: $(get_deployment_strategy "$environment")"
    echo "Debug Mode: ${DEBUG:-false}"
    echo "Log Level: ${LOG_LEVEL:-INFO}"
    echo "───────────────────────────────────────"
    echo ""
}

# Main execution
main() {
    local environment="${1:-}"
    
    if [[ -z "$environment" ]]; then
        echo "Usage: $0 <environment>"
        echo "Available environments:"
        for env_file in "$ENV_CONFIG_DIR"/*.yml; do
            if [[ -f "$env_file" ]]; then
                basename "$env_file" .yml | sed 's/^/  - /'
            fi
        done
        exit 1
    fi
    
    echo "🔧 Environment Configuration Loader"
    echo "===================================="
    
    load_environment_config "$environment"
    get_resource_limits "$environment"
    display_environment_summary "$environment"
    
    # Optional: Validate secrets if not in CI
    if [[ "${CI:-false}" != "true" ]]; then
        validate_secrets "$environment" || echo "⚠️ Secret validation failed (continuing anyway)"
    fi
    
    echo "✅ Environment configuration loaded successfully!"
}

# Execute if called directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi