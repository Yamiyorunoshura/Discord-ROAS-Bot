"""
System Management Commands
Task ID: T11 - Terminal interactive management mode

This module provides system management commands for monitoring and debugging
the ROAS bot system through the interactive terminal interface.
"""

import psutil
import sys
from typing import List, Dict, Any
from datetime import datetime, timedelta
import json

from .commands import BaseCommand, CommandResult
from src.core.logging import get_logger


class StatusCommand(BaseCommand):
    """
    Display system status information
    """
    
    def __init__(self, terminal_panel):
        super().__init__(
            name="status",
            description="Display comprehensive system status information"
        )
        self.terminal_panel = terminal_panel
        
    async def execute(self, args: List[str]) -> CommandResult:
        """Execute the status command"""
        try:
            # Get system information
            system_info = await self._gather_system_info()
            
            # Format status output
            status_text = self._format_status_output(system_info)
            
            return CommandResult(True, status_text)
            
        except Exception as e:
            self.logger.error(f"Error in status command: {e}", exc_info=True)
            return CommandResult(False, f"Error gathering system status: {str(e)}", error=e)
            
    async def _gather_system_info(self) -> Dict[str, Any]:
        """Gather comprehensive system information"""
        info = {}
        
        try:
            # Process information
            process = psutil.Process()
            info['process'] = {
                'pid': process.pid,
                'memory_percent': round(process.memory_percent(), 2),
                'cpu_percent': round(process.cpu_percent(), 2),
                'num_threads': process.num_threads(),
                'create_time': datetime.fromtimestamp(process.create_time()).isoformat(),
                'status': process.status()
            }
            
            # System information
            info['system'] = {
                'cpu_count': psutil.cpu_count(),
                'cpu_percent': round(psutil.cpu_percent(interval=1), 2),
                'memory_total': round(psutil.virtual_memory().total / (1024**3), 2),  # GB
                'memory_available': round(psutil.virtual_memory().available / (1024**3), 2),  # GB
                'memory_percent': round(psutil.virtual_memory().percent, 2),
                'boot_time': datetime.fromtimestamp(psutil.boot_time()).isoformat()
            }
            
            # Python environment
            info['python'] = {
                'version': sys.version.split()[0],
                'executable': sys.executable,
                'platform': sys.platform
            }
            
            # Terminal panel status
            if self.terminal_panel:
                info['terminal_panel'] = {
                    'initialized': self.terminal_panel.is_initialized(),
                    'running': getattr(self.terminal_panel, '_running', False)
                }
                
                # Service status
                services = {}
                if hasattr(self.terminal_panel, 'achievement_service'):
                    services['achievement'] = self.terminal_panel.achievement_service.is_initialized()
                if hasattr(self.terminal_panel, 'economy_service'):
                    services['economy'] = self.terminal_panel.economy_service.is_initialized()
                if hasattr(self.terminal_panel, 'government_service'):
                    services['government'] = self.terminal_panel.government_service.is_initialized()
                if hasattr(self.terminal_panel, 'test_orchestrator_service'):
                    services['test_orchestrator'] = self.terminal_panel.test_orchestrator_service.is_initialized()
                    
                info['services'] = services
            
        except Exception as e:
            self.logger.warning(f"Error gathering some system info: {e}")
            info['error'] = str(e)
            
        return info
        
    def _format_status_output(self, info: Dict[str, Any]) -> str:
        """Format system information into readable output"""
        output = "🔍 System Status Report\\n"
        output += "=" * 50 + "\\n\\n"
        
        # Process Information
        if 'process' in info:
            proc = info['process']
            uptime = self._calculate_uptime(proc.get('create_time'))
            
            output += "📊 Process Information:\\n"
            output += f"  PID: {proc.get('pid', 'N/A')}\\n"
            output += f"  Status: {proc.get('status', 'N/A')}\\n"
            output += f"  Uptime: {uptime}\\n"
            output += f"  CPU Usage: {proc.get('cpu_percent', 'N/A')}%\\n"
            output += f"  Memory Usage: {proc.get('memory_percent', 'N/A')}%\\n"
            output += f"  Threads: {proc.get('num_threads', 'N/A')}\\n\\n"
            
        # System Information
        if 'system' in info:
            sys_info = info['system']
            
            output += "💻 System Information:\\n"
            output += f"  CPU Cores: {sys_info.get('cpu_count', 'N/A')}\\n"
            output += f"  CPU Usage: {sys_info.get('cpu_percent', 'N/A')}%\\n"
            output += f"  Total Memory: {sys_info.get('memory_total', 'N/A')} GB\\n"
            output += f"  Available Memory: {sys_info.get('memory_available', 'N/A')} GB\\n"
            output += f"  Memory Usage: {sys_info.get('memory_percent', 'N/A')}%\\n\\n"
            
        # Python Environment
        if 'python' in info:
            py_info = info['python']
            
            output += "🐍 Python Environment:\\n"
            output += f"  Version: {py_info.get('version', 'N/A')}\\n"
            output += f"  Platform: {py_info.get('platform', 'N/A')}\\n"
            output += f"  Executable: {py_info.get('executable', 'N/A')}\\n\\n"
            
        # Services Status
        if 'services' in info:
            services = info['services']
            
            output += "🔧 Services Status:\\n"
            for service_name, is_init in services.items():
                status_icon = "✅" if is_init else "❌"
                output += f"  {status_icon} {service_name.title()} Service\\n"
            output += "\\n"
            
        # Terminal Panel Status
        if 'terminal_panel' in info:
            panel = info['terminal_panel']
            
            output += "⌨️  Terminal Panel:\\n"
            output += f"  Initialized: {'✅' if panel.get('initialized') else '❌'}\\n"
            output += f"  Running: {'✅' if panel.get('running') else '❌'}\\n"
            
        return output.strip()
        
    def _calculate_uptime(self, create_time_str: str) -> str:
        """Calculate uptime from creation time"""
        try:
            if not create_time_str:
                return "N/A"
                
            create_time = datetime.fromisoformat(create_time_str.replace('Z', '+00:00'))
            uptime_delta = datetime.now() - create_time.replace(tzinfo=None)
            
            days = uptime_delta.days
            hours, remainder = divmod(uptime_delta.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            if days > 0:
                return f"{days}d {hours}h {minutes}m"
            elif hours > 0:
                return f"{hours}h {minutes}m"
            else:
                return f"{minutes}m {seconds}s"
                
        except Exception:
            return "N/A"
            
    def get_help(self) -> str:
        """Get detailed help for the status command"""
        return """Display comprehensive system status information.

Usage:
  status            - Show complete system status

This command provides detailed information about:
- Process information (PID, uptime, resource usage)
- System resources (CPU, memory, disk)
- Python environment details
- Service initialization status
- Terminal panel status

The information helps with system monitoring and debugging."""
        
    def get_syntax(self) -> str:
        """Get command syntax"""
        return "status"


class LogsCommand(BaseCommand):
    """
    Display and manage system logs
    """
    
    def __init__(self):
        super().__init__(
            name="logs",
            description="Display and manage system logs"
        )
        
    async def execute(self, args: List[str]) -> CommandResult:
        """Execute the logs command"""
        try:
            # Parse arguments
            log_type = "main"
            lines = 20
            
            if args:
                if args[0] in ['main', 'error', 'database', 'achievement', 'economy', 'government']:
                    log_type = args[0]
                    if len(args) > 1:
                        try:
                            lines = int(args[1])
                            lines = max(1, min(lines, 1000))  # Limit between 1 and 1000
                        except ValueError:
                            return CommandResult(False, f"Invalid line count: {args[1]}")
                else:
                    try:
                        lines = int(args[0])
                        lines = max(1, min(lines, 1000))  # Limit between 1 and 1000
                    except ValueError:
                        return CommandResult(False, f"Invalid argument: {args[0]}. Use log type or line count.")
                        
            # Get logs (this is a placeholder - actual implementation would read log files)
            log_content = await self._get_log_content(log_type, lines)
            
            return CommandResult(True, log_content)
            
        except Exception as e:
            self.logger.error(f"Error in logs command: {e}", exc_info=True)
            return CommandResult(False, f"Error retrieving logs: {str(e)}", error=e)
            
    async def _get_log_content(self, log_type: str, lines: int) -> str:
        """Get log content (placeholder implementation)"""
        # This is a placeholder implementation
        # In a real system, this would read from actual log files
        
        output = f"📋 Recent {log_type.title()} Logs (last {lines} lines)\\n"
        output += "=" * 50 + "\\n\\n"
        
        # Sample log entries
        current_time = datetime.now()
        for i in range(min(lines, 10)):
            timestamp = (current_time - timedelta(minutes=i)).strftime("%Y-%m-%d %H:%M:%S")
            log_level = ["INFO", "DEBUG", "WARNING", "ERROR"][i % 4]
            message = f"Sample {log_type} log entry {10-i}"
            
            output += f"[{timestamp}] {log_level:>7} - {message}\\n"
            
        output += "\\n⚠️  Note: This is a placeholder implementation.\\n"
        output += "   Real log viewing will be implemented in future versions."
        
        return output
        
    def get_help(self) -> str:
        """Get detailed help for the logs command"""
        return """Display and manage system logs.

Usage:
  logs                    - Show last 20 lines of main log
  logs <type>             - Show last 20 lines of specific log type
  logs <lines>            - Show last N lines of main log
  logs <type> <lines>     - Show last N lines of specific log type

Log Types:
  main                    - Main application log
  error                   - Error log
  database                - Database operations log
  achievement             - Achievement service log
  economy                 - Economy service log
  government              - Government service log

Examples:
  logs                    - Show recent main log entries
  logs error              - Show recent error log entries
  logs 50                 - Show last 50 lines of main log
  logs database 100       - Show last 100 database log entries

Note: Line count is limited to 1-1000 lines."""
        
    def get_syntax(self) -> str:
        """Get command syntax"""
        return "logs [type] [lines]"


class ConfigCommand(BaseCommand):
    """
    Display configuration information
    """
    
    def __init__(self):
        super().__init__(
            name="config",
            description="Display system configuration information"
        )
        
    async def execute(self, args: List[str]) -> CommandResult:
        """Execute the config command"""
        try:
            # This is a placeholder implementation
            # Real implementation would load and display actual configuration
            
            config_info = {
                "logging": {
                    "level": "INFO",
                    "console_enabled": True,
                    "file_enabled": True,
                    "max_file_size": "10MB",
                    "backup_count": 5
                },
                "database": {
                    "type": "sqlite",
                    "path": "./data/roas_bot.db",
                    "pool_size": 10,
                    "timeout": 30
                },
                "terminal": {
                    "interactive_mode": True,
                    "auto_exit_non_interactive": True,
                    "command_history_size": 100
                }
            }
            
            # Format configuration output
            output = "⚙️  System Configuration\\n"
            output += "=" * 50 + "\\n\\n"
            
            output += json.dumps(config_info, indent=2, ensure_ascii=False)
            
            output += "\\n\\n⚠️  Note: This is a placeholder implementation.\\n"
            output += "   Real configuration display will show actual values."
            
            return CommandResult(True, output)
            
        except Exception as e:
            self.logger.error(f"Error in config command: {e}", exc_info=True)
            return CommandResult(False, f"Error retrieving configuration: {str(e)}", error=e)
            
    def get_help(self) -> str:
        """Get detailed help for the config command"""
        return """Display system configuration information.

Usage:
  config            - Show current system configuration

This command displays the current configuration settings for:
- Logging configuration
- Database settings
- Terminal interface settings
- Service configurations

The configuration is displayed in JSON format for easy reading.
Sensitive information (like passwords or tokens) is filtered out."""
        
    def get_syntax(self) -> str:
        """Get command syntax"""
        return "config"