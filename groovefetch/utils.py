"""Utilities and helpers for GrooveFetch."""

import re
import ipaddress
from urllib.parse import urlparse
from typing import Optional


# Blocked private/reserved IP ranges for SSRF protection
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def validate_url(url: str) -> str:
    """Validate URL and block internal/SSRF targets.
    
    Args:
        url: URL to validate
        
    Returns:
        Cleaned URL string
        
    Raises:
        ValueError: If URL is invalid or points to internal network
    """
    if not url or not isinstance(url, str):
        raise ValueError("URL must be a non-empty string")
    
    # Basic scheme validation
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"URL scheme must be http or https, got: {parsed.scheme}")
    
    if not parsed.hostname:
        raise ValueError("URL must have a hostname")
    
    hostname = parsed.hostname.lower()
    
    # Block localhost variants
    if hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        raise ValueError(" URLs pointing to localhost are blocked for security")
    
    # Block IPs in host portion
    try:
        ip = ipaddress.ip_address(hostname)
        for network in _BLOCKED_NETWORKS:
            if ip in network:
                raise ValueError(f"URL points to blocked IP range: {ip}")
    except ValueError:
        pass  # Not an IP, that's fine
    
    return url


def redact_secrets(text: Optional[str]) -> str:
    """Redact common secret patterns from log output.
    
    Args:
        text: Text that may contain secrets
        
    Returns:
        Redacted text
    """
    if not text:
        return ""
    
    patterns = [
        (r'(?i)(api[_-]?key\s*[:=]\s*)[\w\-]{16,}', r'\1***REDACTED***'),
        (r'(?i)(token\s*[:=]\s*)[\w\-]{16,}', r'\1***REDACTED***'),
        (r'(?i)(password\s*[:=]\s*)[^\s&]+', r'\1***REDACTED***'),
        (r'(?i)(authorization\s*[:=]\s*(?:bearer\s+)?)[\w\-\.]+', r'\1***REDACTED***'),
        (r'([?&]key=)[\w\-]{16,}', r'\1***REDACTED***'),
        (r'([?&]api_key=)[\w\-]{16,}', r'\1***REDACTED***'),
        (r'([?&]token=)[\w\-]{16,}', r'\1***REDACTED***'),
    ]
    
    result = text
    for pattern, replacement in patterns:
        result = re.sub(pattern, replacement, result)
    
    return result


def sanitize_filename(name: str) -> str:
    """Sanitize a string for use as a filename.
    
    Args:
        name: Raw filename
        
    Returns:
        Safe filename
    """
    name = re.sub(r'[^\w\-_.]', '_', name)
    name = re.sub(r'_+', '_', name)
    return name.strip('._')


def domain_from_url(url: str) -> str:
    """Extract domain from URL.
    
    Args:
        url: Full URL
        
    Returns:
        Domain name
    """
    parsed = urlparse(url)
    return parsed.hostname or "unknown"
