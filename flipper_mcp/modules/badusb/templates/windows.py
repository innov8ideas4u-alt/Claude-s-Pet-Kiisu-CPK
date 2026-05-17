"""Windows DuckyScript templates."""


def get_notepad_hello() -> str:
    """Simple notepad hello world."""
    return """REM Windows - Open Notepad and type message
DELAY 500
GUI r
DELAY 200
STRING notepad
ENTER
DELAY 1000
STRING Hello from Flipper Zero!
ENTER
STRING This is a test BadUSB script for Windows.
"""


def get_system_info() -> str:
    """Display system information."""
    return """REM Windows - Display System Information
DELAY 500
GUI r
DELAY 200
STRING cmd
ENTER
DELAY 500
STRING systeminfo
ENTER
"""


def get_network_info() -> str:
    """Display network information."""
    return """REM Windows - Display Network Information
DELAY 500
GUI r
DELAY 200
STRING cmd
ENTER
DELAY 500
STRING ipconfig /all
ENTER
"""
