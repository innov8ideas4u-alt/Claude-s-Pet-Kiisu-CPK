"""DuckyScript generator for BadUSB module."""

from typing import Dict, Callable


class DuckyScriptGenerator:
    """
    AI-powered DuckyScript generator.
    
    Converts natural language descriptions into DuckyScript payloads.
    This is a simplified implementation - in production, this could use
    LLM-based generation or template matching.
    """
    
    def __init__(self):
        """Initialize generator with templates."""
        self.templates: Dict[str, Callable[[str], str]] = {
            "windows": self._generate_windows,
            "macos": self._generate_macos,
            "linux": self._generate_linux,
        }
    
    def generate(self, description: str, target_os: str = "windows") -> str:
        """
        Generate DuckyScript from description.
        
        Args:
            description: Natural language description
            target_os: Target operating system
            
        Returns:
            DuckyScript payload
        """
        generator = self.templates.get(target_os.lower(), self._generate_windows)
        return generator(description)
    
    def _generate_windows(self, description: str) -> str:
        """Generate Windows-specific script."""
        desc_lower = description.lower()
        
        # Simple pattern matching (in production, use LLM or better NLP)
        if "notepad" in desc_lower or "text" in desc_lower:
            return self._notepad_script(description)
        elif "powershell" in desc_lower or "command" in desc_lower:
            return self._powershell_script(description)
        elif "calculator" in desc_lower or "calc" in desc_lower:
            return """REM Open Calculator
DELAY 500
GUI r
DELAY 200
STRING calc
ENTER
"""
        else:
            # Generic template
            return f"""REM Generated script: {description}
DELAY 500
GUI r
DELAY 200
STRING cmd
ENTER
DELAY 500
STRING echo {description}
ENTER
"""
    
    def _notepad_script(self, description: str) -> str:
        """Generate notepad demo script."""
        return f"""REM Open Notepad and type message
DELAY 500
GUI r
DELAY 200
STRING notepad
ENTER
DELAY 1000
STRING Hello from Flipper Zero!
ENTER
STRING {description}
ENTER
"""
    
    def _powershell_script(self, description: str) -> str:
        """Generate PowerShell script."""
        return f"""REM Open PowerShell
DELAY 500
GUI r
DELAY 200
STRING powershell
ENTER
DELAY 1000
REM {description}
STRING echo "Flipper Zero - {description}"
ENTER
"""
    
    def _generate_macos(self, description: str) -> str:
        """Generate macOS-specific script."""
        desc_lower = description.lower()
        
        if "terminal" in desc_lower or "command" in desc_lower:
            return f"""REM Open Terminal on macOS
DELAY 500
COMMAND SPACE
DELAY 200
STRING terminal
ENTER
DELAY 1000
STRING echo "{description}"
ENTER
"""
        else:
            return f"""REM macOS script: {description}
DELAY 500
COMMAND SPACE
DELAY 200
STRING {description}
ENTER
"""
    
    def _generate_linux(self, description: str) -> str:
        """Generate Linux-specific script."""
        return f"""REM Linux script: {description}
DELAY 500
CTRL ALT t
DELAY 1000
STRING echo "{description}"
ENTER
"""
