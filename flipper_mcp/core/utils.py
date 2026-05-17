"""Utility functions for Flipper MCP."""

from typing import Any


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal.
    
    Args:
        filename: Filename to sanitize
        
    Returns:
        Sanitized filename
    """
    # Remove path separators
    filename = filename.replace("/", "_").replace("\\", "_")
    
    # Remove parent directory references
    filename = filename.replace("..", "_")
    
    return filename


def validate_path(path: str, base_path: str) -> bool:
    """
    Validate that path is within base path.
    
    Args:
        path: Path to validate
        base_path: Base path that must contain the path
        
    Returns:
        True if path is valid
    """
    # Normalize paths
    import os.path
    path = os.path.normpath(path)
    base_path = os.path.normpath(base_path)
    
    # Check if path starts with base_path
    return path.startswith(base_path)


def format_error(error: Exception) -> str:
    """
    Format exception for user display.
    
    Args:
        error: Exception to format
        
    Returns:
        Formatted error message
    """
    return f"❌ Error: {type(error).__name__}: {str(error)}"


def truncate_text(text: str, max_length: int = 1000) -> str:
    """
    Truncate text to maximum length.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length] + f"\n... (truncated, {len(text) - max_length} more characters)"
