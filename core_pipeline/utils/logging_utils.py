"""
HY-TUTOR: Logging Utilities
Provides consistent logging format across all commands for execution tracking.
"""

import sys
import time
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class LogLevel(Enum):
    """Logging levels for HY-TUTOR."""
    INIT = "INIT"
    PROCESS = "PROCESS"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    DEBUG = "DEBUG"
    STATE = "STATE"


# Color codes for terminal output (if supported)
COLORS = {
    LogLevel.INIT: "\033[94m",      # Blue
    LogLevel.PROCESS: "\033[96m",   # Cyan
    LogLevel.SUCCESS: "\033[92m",   # Green
    LogLevel.WARNING: "\033[93m",   # Yellow
    LogLevel.ERROR: "\033[91m",     # Red
    LogLevel.CRITICAL: "\033[95m",  # Magenta
    LogLevel.DEBUG: "\033[90m",     # Gray
    LogLevel.STATE: "\033[97m",     # White
}

RESET_COLOR = "\033[0m"

# Global flag for color output (can be disabled)
USE_COLORS = True


def set_colors(enabled: bool) -> None:
    """Enable or disable color output."""
    global USE_COLORS
    USE_COLORS = enabled


def _get_color(level: LogLevel) -> str:
    """Get color code for a log level."""
    if not USE_COLORS:
        return ""
    return COLORS.get(level, "")


def _get_reset() -> str:
    """Get color reset code."""
    if not USE_COLORS:
        return ""
    return RESET_COLOR


def log_message(
    level: LogLevel,
    message: str,
    command_name: Optional[str] = None,
    timestamp: bool = True,
    prefix: bool = True
) -> None:
    """
    Log a message with consistent formatting.
    
    Args:
        level: Log level (INIT, PROCESS, SUCCESS, WARNING, ERROR, etc.)
        message: The message to log
        command_name: Optional command name for context
        timestamp: Whether to include timestamp
        prefix: Whether to include level prefix
    """
    # Build prefix
    prefix_parts = []
    
    if timestamp:
        prefix_parts.append(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}]")
    
    if command_name:
        prefix_parts.append(f"[{command_name}]")
    
    if prefix and prefix_parts:
        full_prefix = " ".join(prefix_parts) + " "
    elif prefix:
        full_prefix = f"[{level.value}] "
    else:
        full_prefix = ""
    
    # Get color
    color = _get_color(level)
    reset = _get_reset()
    
    # Format message based on level
    if level in [LogLevel.ERROR, LogLevel.CRITICAL, LogLevel.WARNING]:
        formatted = f"{color}{full_prefix}{level.value}: {message}{reset}"
    elif level == LogLevel.SUCCESS:
        formatted = f"{color}{full_prefix}✓ {message}{reset}"
    elif level == LogLevel.INIT:
        formatted = f"{color}{full_prefix}→ {message}{reset}"
    elif level == LogLevel.STATE:
        formatted = f"{color}{full_prefix}≡ {message}{reset}"
    else:
        formatted = f"{color}{full_prefix}{message}{reset}"
    
    print(formatted, file=sys.stdout)


def log_init(command_name: str, message: str) -> None:
    """Log initialization message."""
    log_message(LogLevel.INIT, message, command_name)


def log_process(command_name: str, message: str) -> None:
    """Log process message."""
    log_message(LogLevel.PROCESS, message, command_name)


def log_success(command_name: str, message: str) -> None:
    """Log success message."""
    log_message(LogLevel.SUCCESS, message, command_name)


def log_warning(command_name: str, message: str) -> None:
    """Log warning message."""
    log_message(LogLevel.WARNING, message, command_name)


def log_error(command_name: str, message: str) -> None:
    """Log error message."""
    log_message(LogLevel.ERROR, message, command_name)


def log_critical(command_name: str, message: str) -> None:
    """Log critical error message."""
    log_message(LogLevel.CRITICAL, message, command_name)


def log_state(command_name: str, message: str) -> None:
    """Log state change message."""
    log_message(LogLevel.STATE, message, command_name)


def log_debug(command_name: str, message: str) -> None:
    """Log debug message."""
    log_message(LogLevel.DEBUG, message, command_name)


class CommandLogger:
    """
    Context manager and helper for command execution logging.
    
    Provides standardized logging for command lifecycle:
    - Initialization
    - Processing steps
    - Completion/Success
    - Errors
    """
    
    def __init__(self, command_name: str, description: str = ""):
        self.command_name = command_name
        self.description = description
        self.start_time = None
    
    def __enter__(self):
        """Log command start."""
        self.start_time = time.time()
        
        if self.description:
            log_init(self.command_name, f"{self.description}")
        else:
            log_init(self.command_name, "Command initialized")
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Log command completion."""
        duration = time.time() - self.start_time if self.start_time else 0
        
        if exc_type is None:
            log_success(self.command_name, f"Command completed in {duration:.2f}s")
        else:
            log_error(self.command_name, f"Command failed after {duration:.2f}s: {exc_val}")
    
    def step(self, step_name: str, details: str = "") -> None:
        """Log a processing step."""
        message = f"Step {step_name}"
        if details:
            message += f": {details}"
        log_process(self.command_name, message)
    
    def milestone(self, milestone: str) -> None:
        """Log a major milestone."""
        log_state(self.command_name, f"Milestone: {milestone}")
    
    def api_call(self, model: str, action: str) -> None:
        """Log an API call."""
        log_process(self.command_name, f"API Call: {action} with {model}")
    
    def file_operation(self, operation: str, file_path: str) -> None:
        """Log a file operation."""
        log_process(self.command_name, f"File {operation}: {file_path}")
    
    def data_info(self, name: str, count: int, details: str = "") -> None:
        """Log data information."""
        message = f"{name}: {count} items"
        if details:
            message += f" ({details})"
        log_debug(self.command_name, message)


# Convenience function for simple command logging
def run_with_logging(command_name: str, description: str = "", verbose: bool = True):
    """
    Context manager for simple command logging.
    
    Usage:
        with run_with_logging("command_1", "Building blueprint"):
            # command logic here
            pass
    """
    if not verbose:
        return lambda: None  # No-op context manager
    
    return CommandLogger(command_name, description)


# Legacy compatibility functions (matching existing print patterns)
def print_init(command_name: str, message: str) -> None:
    """Legacy: Print initialization message (blue)."""
    log_init(command_name, message)


def print_process(command_name: str, message: str) -> None:
    """Legacy: Print process message (cyan)."""
    log_process(command_name, message)


def print_success(command_name: str, message: str) -> None:
    """Legacy: Print success message (green)."""
    log_success(command_name, message)


def print_warning(command_name: str, message: str) -> None:
    """Legacy: Print warning message (yellow)."""
    log_warning(command_name, message)


def print_error(command_name: str, message: str) -> None:
    """Legacy: Print error message (red)."""
    log_error(command_name, message)


__all__ = [
    # Log levels
    'LogLevel',
    
    # Basic logging functions
    'log_message',
    'log_init',
    'log_process',
    'log_success',
    'log_warning',
    'log_error',
    'log_critical',
    'log_state',
    'log_debug',
    
    # Command logger
    'CommandLogger',
    'run_with_logging',
    
    # Legacy compatibility
    'print_init',
    'print_process',
    'print_success',
    'print_warning',
    'print_error',
    
    # Configuration
    'set_colors',
]
