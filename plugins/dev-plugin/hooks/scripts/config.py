#!/usr/bin/env python3
"""
Centralized configuration loader for dev-plugin.

Supports multiple config formats with priority:
1. .claude/dev-plugin.yaml (new format)
2. .claude/dev-plugin.local.md (legacy format with YAML frontmatter)
3. ~/.claude/plugins/dev-plugin/dev-plugin.yaml (global config)

Automatically loads secrets from .env files and supports environment variable expansion.
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional
import logging

# Setup logging
logger = logging.getLogger(__name__)


def load_env_file(env_path: Path) -> Dict[str, str]:
    """Load environment variables from .env file."""
    env_vars = {}
    if not env_path.exists():
        return env_vars

    try:
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue
                # Parse KEY=VALUE
                if '=' in line:
                    key, value = line.split('=', 1)
                    # Remove quotes if present
                    value = value.strip('"').strip("'")
                    env_vars[key.strip()] = value
    except Exception as e:
        logger.warning(f"Failed to load .env file {env_path}: {e}")

    return env_vars


def expand_env_vars(value: Any, env_vars: Dict[str, str]) -> Any:
    """Recursively expand ${VAR} references in config values."""
    if isinstance(value, str):
        # Expand ${VAR} syntax
        import re
        pattern = r'\$\{([^}]+)\}'

        def replace_var(match):
            var_name = match.group(1)
            # Check custom env_vars first, then os.environ
            return env_vars.get(var_name) or os.environ.get(var_name, match.group(0))

        return re.sub(pattern, replace_var, value)
    elif isinstance(value, dict):
        return {k: expand_env_vars(v, env_vars) for k, v in value.items()}
    elif isinstance(value, list):
        return [expand_env_vars(item, env_vars) for item in value]
    else:
        return value


def deep_merge(base: Dict, override: Dict) -> Dict:
    """Deep merge two dictionaries, with override taking precedence."""
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value

    return result


def load_yaml_file(yaml_path: Path) -> Optional[Dict]:
    """Load YAML configuration from a .yaml file."""
    if not yaml_path.exists():
        return None

    try:
        import yaml
        with open(yaml_path, 'r') as f:
            content = f.read()
            return yaml.safe_load(content) or {}
    except Exception as e:
        logger.warning(f"Failed to load YAML file {yaml_path}: {e}")
        return None


def load_legacy_md_file(md_path: Path) -> Optional[Dict]:
    """Load YAML frontmatter from legacy .local.md file."""
    if not md_path.exists():
        return None

    try:
        import yaml
        content = md_path.read_text()

        # Parse YAML frontmatter (between --- markers)
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 2:
                yaml_content = parts[1]
                config = yaml.safe_load(yaml_content) or {}

                # Show deprecation warning
                logger.warning(
                    f"\n⚠️  DEPRECATION WARNING: Using legacy config format (.local.md)\n"
                    f"   Location: {md_path}\n"
                    f"   Please migrate to YAML + .env format for better security.\n"
                    f"   Run: python plugins/dev-plugin/migrate-config.py\n"
                )

                return config
    except Exception as e:
        logger.warning(f"Failed to load legacy .md file {md_path}: {e}")
        return None

    return None


def get_default_config() -> Dict:
    """Return default configuration structure."""
    return {
        'enabled': True,
        'observability': {
            'enabled': False,
            'debug': False,
            'langfuse': {
                'enabled': False,
                'auto_setup': False,
                'auto_start': False,
                'host': 'http://localhost:3000',
                'public_key': '',
                'secret_key': '',
                'userId': '',
                'version': '1.0.0',
                'tags': [],
                'compose_path': ''
            }
        },
        'autoformat': {
            'enabled': True
        },
        'git_checkpoint': {
            'enabled': True
        },
        'notifications': {
            'enabled': True,
            'mac_notification': True,
            'use_dialog': False,
            'tts': False
        },
        'claude_md_management': {
            'auto_init': True,
            'auto_update': True,
            'update_threshold': 3,
            'max_file_size': 10240,
            'backup_before_update': True
        },
        'quality_check': {
            'enabled': True,
            'typescript': {
                'enabled': True,
                'command': 'npx tsc --noEmit'
            },
            'python': {
                'enabled': True,
                'command': 'mypy .'
            },
            'go': {
                'enabled': True,
                'command': 'go vet ./...'
            },
            'rust': {
                'enabled': True,
                'command': 'cargo check'
            }
        }
    }


def load_config(project_dir: Path) -> Dict:
    """
    Load configuration with two-tier priority system.

    Priority (highest to lowest):
    1. Project-level YAML: .claude/dev-plugin.yaml
    2. Project-level legacy: .claude/dev-plugin.local.md
    3. Global YAML: ~/.claude/plugins/dev-plugin/dev-plugin.yaml
    4. Global legacy: ~/.claude/plugins/dev-plugin/settings.local.md
    5. Default configuration

    Also loads environment variables from .env files:
    - .claude/.env (project-level)
    - ~/.claude/plugins/dev-plugin/.env (global)
    - System environment variables

    Args:
        project_dir: Path to the project directory

    Returns:
        Merged configuration dictionary
    """
    # Start with defaults
    config = get_default_config()

    # Define paths
    project_yaml = project_dir / '.claude' / 'dev-plugin.yaml'
    project_md = project_dir / '.claude' / 'dev-plugin.local.md'
    project_env = project_dir / '.claude' / '.env'

    global_dir = Path.home() / '.claude' / 'plugins' / 'dev-plugin'
    global_yaml = global_dir / 'dev-plugin.yaml'
    global_md = global_dir / 'settings.local.md'
    global_env = global_dir / '.env'

    # Load environment variables (global first, then project overrides)
    env_vars = {}
    env_vars.update(load_env_file(global_env))
    env_vars.update(load_env_file(project_env))

    # Load global config (YAML preferred, fallback to .md)
    global_config = load_yaml_file(global_yaml)
    if global_config is None:
        global_config = load_legacy_md_file(global_md)

    if global_config:
        config = deep_merge(config, global_config)

    # Load project config (YAML preferred, fallback to .md)
    project_config = load_yaml_file(project_yaml)
    if project_config is None:
        project_config = load_legacy_md_file(project_md)

    if project_config:
        config = deep_merge(config, project_config)

    # Expand environment variables in the final config
    config = expand_env_vars(config, env_vars)

    return config


def get_config_value(config: Dict, path: str, default: Any = None) -> Any:
    """
    Get a nested config value using dot notation.

    Example:
        get_config_value(config, 'observability.langfuse.enabled', False)

    Args:
        config: Configuration dictionary
        path: Dot-separated path (e.g., 'observability.langfuse.enabled')
        default: Default value if path not found

    Returns:
        Config value or default
    """
    keys = path.split('.')
    value = config

    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default

    return value


# Backward compatibility: allow scripts to import this as they did before
if __name__ == '__main__':
    # Test the config loader
    import json
    test_dir = Path.cwd()
    config = load_config(test_dir)
    print(json.dumps(config, indent=2))
