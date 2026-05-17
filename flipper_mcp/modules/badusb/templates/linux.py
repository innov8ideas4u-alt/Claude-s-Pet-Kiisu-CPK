"""Linux DuckyScript templates."""


def get_terminal_hello() -> str:
    """Simple terminal hello world."""
    return """REM Linux - Open Terminal and display message
DELAY 500
CTRL ALT t
DELAY 1000
STRING echo "Hello from Flipper Zero!"
ENTER
"""


def get_system_info() -> str:
    """Display system information."""
    return """REM Linux - Display System Information
DELAY 500
CTRL ALT t
DELAY 1000
STRING uname -a
ENTER
STRING lsb_release -a
ENTER
"""
