"""macOS DuckyScript templates."""


def get_terminal_hello() -> str:
    """Simple terminal hello world."""
    return """REM macOS - Open Terminal and display message
DELAY 500
COMMAND SPACE
DELAY 200
STRING terminal
ENTER
DELAY 1000
STRING echo "Hello from Flipper Zero!"
ENTER
"""


def get_system_info() -> str:
    """Display system information."""
    return """REM macOS - Display System Information
DELAY 500
COMMAND SPACE
DELAY 200
STRING terminal
ENTER
DELAY 1000
STRING system_profiler SPSoftwareDataType
ENTER
"""
