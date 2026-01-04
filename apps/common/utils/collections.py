"""
Collection (dict/list) utilities.
"""
import hashlib
from typing import Any, Dict, List


# ==================== Hashing ====================

def hash_string(value: str, algorithm: str = 'sha256') -> str:
    """Hash a string value."""
    hasher = hashlib.new(algorithm)
    hasher.update(value.encode('utf-8'))
    return hasher.hexdigest()


def short_hash(value: str, length: int = 8) -> str:
    """Generate short hash for IDs."""
    return hash_string(value)[:length]


# ==================== Dict Utilities ====================

def deep_merge(base: Dict, override: Dict) -> Dict:
    """Deep merge two dictionaries."""
    result = base.copy()
    
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    
    return result


def pick(obj: Dict, keys: List[str]) -> Dict:
    """Pick specified keys from dict."""
    return {k: v for k, v in obj.items() if k in keys}


def omit(obj: Dict, keys: List[str]) -> Dict:
    """Omit specified keys from dict."""
    return {k: v for k, v in obj.items() if k not in keys}


# ==================== List Utilities ====================

def chunk(lst: List, size: int) -> List[List]:
    """Split list into chunks."""
    return [lst[i:i + size] for i in range(0, len(lst), size)]


def flatten(nested_list: List) -> List:
    """Flatten nested list."""
    result = []
    for item in nested_list:
        if isinstance(item, list):
            result.extend(flatten(item))
        else:
            result.append(item)
    return result


def unique(lst: List, key=None) -> List:
    """Get unique items from list."""
    seen = set()
    result = []
    
    for item in lst:
        k = key(item) if key else item
        if k not in seen:
            seen.add(k)
            result.append(item)
    
    return result
