"""Configuration Management Module"""

import os
import yaml
from typing import Dict, Any
from pathlib import Path
from dotenv import load_dotenv


def load_config(config_path: str = "config/config.yaml") -> Dict[str, Any]:
    """
    Load configuration from YAML file with environment variable substitution.
    
    Args:
        config_path: Path to configuration YAML file
        
    Returns:
        Dictionary containing configuration
    """
    # Load environment variables
    load_dotenv()
    
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
    
    # Substitute environment variables
    config = _substitute_env_vars(config)
    
    return config


def _substitute_env_vars(obj: Any) -> Any:
    """Recursively substitute environment variables in configuration."""
    if isinstance(obj, dict):
        return {k: _substitute_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_substitute_env_vars(item) for item in obj]
    elif isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
        env_var = obj[2:-1]
        return os.getenv(env_var, obj)
    else:
        return obj


def get_config_value(config: Dict[str, Any], key_path: str, default: Any = None) -> Any:
    """
    Get configuration value using dot-notation path.
    
    Args:
        config: Configuration dictionary
        key_path: Dot-separated path (e.g., "roostoo.api_key")
        default: Default value if key not found
        
    Returns:
        Configuration value or default
    """
    keys = key_path.split('.')
    value = config
    
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default
    
    return value

