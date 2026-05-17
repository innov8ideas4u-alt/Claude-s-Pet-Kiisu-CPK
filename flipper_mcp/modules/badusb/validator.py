"""Safety validator for BadUSB scripts."""

import re
from typing import Tuple


# NOTE: This is a basic pattern-matching validator for demonstration.
# In production, consider:
# - Semantic analysis of script intent
# - Sandboxed execution to detect behavior
# - Machine learning-based classification
# - User-defined safety policies
# - Integration with security scanners

class ScriptValidator:
    """
    Validates BadUSB scripts for safety.
    
    Checks scripts for dangerous operations that could cause harm.
    This is a basic implementation - production validators should be more sophisticated.
    """
    
    def __init__(self):
        """Initialize validator with dangerous patterns."""
        self.dangerous_patterns = [
            # System destruction
            r"rm\s+-rf\s+/",
            r"del\s+/f\s+/s\s+/q\s+C:\\",
            r"format\s+[cC]:",
            r"diskpart",
            
            # Malware-like behavior
            r"wget.*\|\s*sh",
            r"curl.*\|\s*bash",
            r"powershell.*-encodedcommand",
            r"invoke-expression",
            r"iex\s+",
            
            # Data exfiltration
            r"upload",
            r"exfil",
            
            # Registry damage
            r"reg\s+delete",
            r"regedit\s+/s",
        ]
        
        self.warning_patterns = [
            # Network operations
            r"wget",
            r"curl",
            r"net\s+user",
            r"netsh",
            
            # File operations
            r"rm\s+-rf",
            r"del\s+",
        ]
    
    def validate(self, script: str) -> Tuple[bool, str]:
        """
        Validate script for safety.
        
        Args:
            script: DuckyScript to validate
            
        Returns:
            (is_valid, error_message)
        """
        script_lower = script.lower()
        
        # Check for dangerous patterns
        for pattern in self.dangerous_patterns:
            if re.search(pattern, script_lower, re.IGNORECASE):
                return False, f"Dangerous pattern detected: {pattern}"
        
        # Check for warnings (allow but note)
        warnings = []
        for pattern in self.warning_patterns:
            if re.search(pattern, script_lower, re.IGNORECASE):
                warnings.append(pattern)
        
        if warnings:
            warning_msg = f"⚠️  Script contains: {', '.join(warnings)}"
            # Still valid, but warn
            return True, warning_msg
        
        return True, ""
    
    def sanitize(self, script: str) -> str:
        """
        Sanitize script by removing dangerous commands.
        
        Args:
            script: Script to sanitize
            
        Returns:
            Sanitized script
        """
        lines = script.split('\n')
        safe_lines = []
        
        for line in lines:
            is_safe = True
            for pattern in self.dangerous_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    is_safe = False
                    safe_lines.append(f"REM REMOVED DANGEROUS: {line}")
                    break
            
            if is_safe:
                safe_lines.append(line)
        
        return '\n'.join(safe_lines)
