"""
Input Validation Module - PHASE 2
Comprehensive validation to prevent injection attacks, SQL injection, XSS
"""

import re
import json
from typing import Any, Dict, List
from enum import Enum

# ────────────────────────────────────────────────────────
# DANGEROUS PATTERNS (Injection Prevention)
# ────────────────────────────────────────────────────────

# Command Injection Patterns
COMMAND_INJECTION_PATTERNS = [
    r'\$\(.*\)',           # $(command)
    r'`.*`',               # `command`
    r'\|\s*[a-z]',         # | command
    r';\s*[a-z]',          # ; command
    r'&&\s*[a-z]',         # && command
    r'\|\|\s*[a-z]',       # || command
    r'>\s*/',              # > /file
    r'<\s*/',              # < /file
    r'&>',                 # &> file
]

# Code Injection Patterns
CODE_INJECTION_PATTERNS = [
    r'__import__',
    r'eval\s*\(',
    r'exec\s*\(',
    r'subprocess',
    r'os\.system',
    r'os\.popen',
    r'compile\s*\(',
    r'globals\s*\(',
    r'locals\s*\(',
    r'vars\s*\(',
    r'dir\s*\(',
    r'getattr\s*\(',
    r'setattr\s*\(',
    r'delattr\s*\(',
]

# LLM Prompt Injection Patterns
LLM_INJECTION_PATTERNS = [
    r'ignore\s+previous',
    r'forget\s+previous',
    r'disregard.*instruction',
    r'override.*instruction',
    r'system\s+prompt',
    r'admin\s+override',
    r'bypass\s+security',
    r'execute\s+(code|command)',
    r'run\s+(code|command)',
    r'act\s+as\s+',
    r'pretend\s+to\s+be',
]

# SQL Injection Patterns (for Elasticsearch queries)
SQL_INJECTION_PATTERNS = [
    r"'\s+OR\s+'",
    r"'\s+AND\s+'",
    r"--\s",
    r"/\*.*\*/",
    r'"\s+OR\s+"',
    r'"\s+AND\s+"',
    r'UNION\s*SELECT',
    r'DROP\s*TABLE',
    r'INSERT\s*INTO',
    r'DELETE\s*FROM',
]

# XSS Patterns
XSS_PATTERNS = [
    r'<script[^>]*>',
    r'javascript:',
    r'on\w+\s*=',  # onload=, onclick=, etc.
    r'<iframe',
    r'<embed',
    r'<object',
]

# ────────────────────────────────────────────────────────
# VALIDATION FUNCTIONS
# ────────────────────────────────────────────────────────

class ValidationError(Exception):
    """Custom validation error"""
    pass


def check_injection_patterns(text: str, patterns: List[str], pattern_name: str) -> None:
    """
    Check if text matches any dangerous patterns
    
    Args:
        text: Input text to validate
        patterns: List of regex patterns to check
        pattern_name: Name of pattern category (for error message)
    
    Raises:
        ValidationError: If dangerous pattern detected
    """
    if not isinstance(text, str):
        return
    
    text_lower = text.lower()
    for pattern in patterns:
        if re.search(pattern, text_lower, re.IGNORECASE):
            raise ValidationError(
                f"🚨 {pattern_name} detected: {pattern[:50]}... | Input: {text[:100]}"
            )


def sanitize_string(text: str, max_length: int = 1000) -> str:
    """
    Basic string sanitization
    
    Args:
        text: Input string
        max_length: Maximum allowed length
    
    Returns:
        Sanitized string
    
    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(text, str):
        raise ValidationError("Input must be string")
    
    if len(text) == 0:
        raise ValidationError("Input cannot be empty")
    
    if len(text) > max_length:
        raise ValidationError(f"Input exceeds maximum length of {max_length}")
    
    # Remove null bytes
    text = text.replace('\x00', '')
    
    # Remove excessive whitespace
    text = ' '.join(text.split())
    
    return text


def validate_query_input(text: str, allow_wildcards: bool = False) -> str:
    """
    Validate input for Elasticsearch/database queries
    
    Args:
        text: Input text
        allow_wildcards: Allow * and ? wildcards
    
    Returns:
        Validated text
    
    Raises:
        ValidationError: If validation fails
    """
    text = sanitize_string(text, max_length=500)
    
    # Check for injection patterns
    check_injection_patterns(text, SQL_INJECTION_PATTERNS, "SQL Injection")
    check_injection_patterns(text, COMMAND_INJECTION_PATTERNS, "Command Injection")
    check_injection_patterns(text, XSS_PATTERNS, "XSS")
    
    # Check for special characters that could break queries
    if not allow_wildcards:
        if any(char in text for char in ['*', '?', '@', '#', '$', '%', '^', '&']):
            raise ValidationError(
                f"Special characters not allowed in query: {text[:100]}"
            )
    
    return text


def validate_llm_input(text: str) -> str:
    """
    Validate input before sending to LLM (Gemini)
    
    Args:
        text: Input text for LLM
    
    Returns:
        Validated text
    
    Raises:
        ValidationError: If validation fails
    """
    text = sanitize_string(text, max_length=2000)
    
    # Check for prompt injection patterns
    check_injection_patterns(text, LLM_INJECTION_PATTERNS, "Prompt Injection")
    check_injection_patterns(text, CODE_INJECTION_PATTERNS, "Code Injection")
    check_injection_patterns(text, COMMAND_INJECTION_PATTERNS, "Command Injection")
    
    return text


def validate_alert_data(alert: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate alert/log data from Elasticsearch
    
    Args:
        alert: Alert data dictionary
    
    Returns:
        Validated alert data
    
    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(alert, dict):
        raise ValidationError("Alert must be a dictionary")
    
    if len(alert) == 0:
        raise ValidationError("Alert cannot be empty")
    
    if len(alert) > 1000:
        raise ValidationError("Alert data too large (max 1000 fields)")
    
    # Validate each field
    for key, value in alert.items():
        # Key validation
        if not isinstance(key, str):
            raise ValidationError(f"Alert key must be string, got {type(key)}")
        
        if len(key) > 200:
            raise ValidationError(f"Alert key too long: {key[:50]}")
        
        # Check for suspicious field names
        if any(pattern in key.lower() for pattern in ['__', 'eval', 'exec', 'import']):
            raise ValidationError(f"Suspicious field name: {key}")
        
        # Value validation
        if isinstance(value, str):
            if len(value) > 5000:
                raise ValidationError(f"Alert value too long for key '{key}'")
            
            # Check for injection patterns in values
            try:
                check_injection_patterns(value, CODE_INJECTION_PATTERNS, "Code Injection in Alert")
            except ValidationError:
                # Log but don't fail - logs might contain technical content
                pass
    
    return alert


def validate_json_response(response: str) -> Dict[str, Any]:
    """
    Validate and parse JSON response from LLM
    
    Args:
        response: Response string from LLM
    
    Returns:
        Parsed JSON as dictionary
    
    Raises:
        ValidationError: If validation fails
    """
    if not isinstance(response, str):
        raise ValidationError("Response must be string")
    
    if len(response) > 10000:
        raise ValidationError("Response too large (max 10KB)")
    
    try:
        parsed = json.loads(response)
    except json.JSONDecodeError as e:
        raise ValidationError(f"Invalid JSON response: {str(e)[:100]}")
    
    if not isinstance(parsed, dict):
        raise ValidationError("Response must be JSON object, not array or primitive")
    
    # Check for suspicious keys in response
    for key in parsed.keys():
        if any(pattern in key.lower() for pattern in ['__', 'eval', 'exec', 'import']):
            raise ValidationError(f"Suspicious key in response: {key}")
    
    return parsed


def validate_username(username: str) -> str:
    """Validate username format"""
    username = sanitize_string(username, max_length=50)
    
    if not re.match(r'^[a-zA-Z0-9_-]{3,50}$', username):
        raise ValidationError(
            "Username must be 3-50 characters, alphanumeric with _ or - only"
        )
    
    return username


def validate_email(email: str) -> str:
    """Validate email format"""
    email = sanitize_string(email, max_length=100)
    
    # Basic email validation
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        raise ValidationError("Invalid email format")
    
    return email


def validate_password(password: str) -> str:
    """Validate password strength"""
    if not isinstance(password, str):
        raise ValidationError("Password must be string")
    
    if len(password) < 8:
        raise ValidationError("Password must be at least 8 characters")
    
    if len(password) > 100:
        raise ValidationError("Password too long (max 100 characters)")
    
    # Check for high entropy (avoid simple passwords)
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(c in '!@#$%^&*_-+=[]{}|;:,.<>?' for c in password)
    
    if not (has_lower and has_upper and (has_digit or has_special)):
        raise ValidationError(
            "Password must contain uppercase, lowercase, and numbers or special chars"
        )
    
    return password


# ────────────────────────────────────────────────────────
# VALIDATION STATISTICS (For monitoring)
# ────────────────────────────────────────────────────────

class ValidationStats:
    """Track validation attempts and blocks"""
    total_attempts = 0
    total_blocked = 0
    blocked_by_pattern = {}
    
    @classmethod
    def record_attempt(cls):
        cls.total_attempts += 1
    
    @classmethod
    def record_block(cls, pattern_name: str):
        cls.total_blocked += 1
        cls.blocked_by_pattern[pattern_name] = cls.blocked_by_pattern.get(pattern_name, 0) + 1
    
    @classmethod
    def get_stats(cls) -> Dict[str, Any]:
        return {
            "total_attempts": cls.total_attempts,
            "total_blocked": cls.total_blocked,
            "blocked_by_pattern": cls.blocked_by_pattern,
            "block_rate": f"{(cls.total_blocked / max(cls.total_attempts, 1)) * 100:.2f}%"
        }
