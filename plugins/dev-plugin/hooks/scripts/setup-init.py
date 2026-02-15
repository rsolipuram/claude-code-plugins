#!/usr/bin/env python3
"""
Setup Hook - Init Mode
Initializes dev-plugin environment: config files, dependencies, and optional Langfuse.
Triggered by: claude --init or claude --init-only
"""

import json
import os
import secrets
import subprocess
import sys
import shutil
import time
import urllib.request
from pathlib import Path
from typing import Dict, List, Tuple


def log(message: str, prefix: str = "ℹ") -> None:
    """Print formatted log message to stderr."""
    print(f"{prefix} {message}", file=sys.stderr)


def get_project_root() -> Path:
    """Get project root (current working directory)."""
    return Path.cwd()


def get_plugin_root() -> Path:
    """Get plugin root directory from environment variable."""
    plugin_root = os.environ.get('CLAUDE_PLUGIN_ROOT')
    if not plugin_root:
        log("CLAUDE_PLUGIN_ROOT not set", prefix="⚠")
        return Path(__file__).parent.parent.parent
    return Path(plugin_root)


def create_claude_directory(project_root: Path) -> Path:
    """Create .claude directory if it doesn't exist."""
    claude_dir = project_root / ".claude"
    claude_dir.mkdir(exist_ok=True)
    return claude_dir


def copy_template(template_name: str, dest_path: Path, force: bool = False) -> bool:
    """Copy template file to destination if it doesn't exist."""
    if dest_path.exists() and not force:
        log(f"Already exists: {dest_path.name}", prefix="⏭")
        return False

    plugin_root = get_plugin_root()
    template_path = plugin_root / "hooks" / "scripts" / "templates" / template_name

    if not template_path.exists():
        log(f"Template not found: {template_path}", prefix="⚠")
        return False

    try:
        shutil.copy(template_path, dest_path)
        log(f"Created: {dest_path.name}", prefix="✓")
        return True
    except Exception as e:
        log(f"Failed to copy template {template_name}: {e}", prefix="✗")
        return False


def install_dependency(package: str) -> bool:
    """Install Python package using pip."""
    log(f"Installing {package}...", prefix="⏳")
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'install', package, '--quiet'],
            capture_output=True,
            timeout=120
        )
        if result.returncode == 0:
            log(f"Installed: {package}", prefix="✓")
            return True
        else:
            log(f"Failed to install {package}: {result.stderr.decode()}", prefix="✗")
            return False
    except Exception as e:
        log(f"Error installing {package}: {e}", prefix="✗")
        return False


def check_dependency_installed(package: str) -> bool:
    """Check if a Python package is installed."""
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'show', package],
            capture_output=True,
            timeout=10
        )
        return result.returncode == 0
    except Exception:
        return False


def get_global_config_dir() -> Path:
    """Get stable global configuration directory (NOT cache)."""
    return Path.home() / '.claude' / 'plugins' / 'dev-plugin'


def detect_existing_configs() -> Dict[str, bool]:
    """
    Check what config files already exist.

    Returns:
        Dictionary with existence flags for each config location
    """
    project_root = get_project_root()
    global_dir = get_global_config_dir()

    return {
        'global_yaml': (global_dir / 'dev-plugin.yaml').exists(),
        'global_env': (global_dir / '.env').exists(),
        'project_yaml': (project_root / '.claude' / 'dev-plugin.yaml').exists(),
        'project_env': (project_root / '.claude' / '.env').exists(),
    }


def validate_config_locations() -> List[str]:
    """
    Check for config files in wrong locations and return warnings.

    Returns:
        List of warning messages for misplaced configs
    """
    warnings = []

    # Check for config in cache directory (will be lost on updates)
    cache_base = Path.home() / '.claude' / 'plugins' / 'cache'
    if cache_base.exists():
        for cache_dir in cache_base.glob('dev-plugin*'):
            yaml_in_cache = cache_dir / 'dev-plugin.yaml'
            env_in_cache = cache_dir / '.env'

            if yaml_in_cache.exists():
                warnings.append(
                    f"⚠️  Config found in cache: {yaml_in_cache}\n"
                    f"   This will be WIPED on plugin updates!\n"
                    f"   Move to: ~/.claude/plugins/dev-plugin/dev-plugin.yaml"
                )

            if env_in_cache.exists():
                warnings.append(
                    f"⚠️  Environment file found in cache: {env_in_cache}\n"
                    f"   This will be WIPED on plugin updates!\n"
                    f"   Move to: ~/.claude/plugins/dev-plugin/.env"
                )

    return warnings


def prompt_setup_scope(existing: Dict[str, bool]) -> str:
    """
    Prompt user for setup scope based on existing configuration.

    Args:
        existing: Dict with existence flags for configs

    Returns:
        'global', 'project', or 'both'
    """
    # Smart prompting based on what already exists
    if existing['global_yaml'] and existing['global_env']:
        if existing['project_yaml']:
            log("Both global and project configs already exist.", prefix="ℹ")
            return 'skip'
        else:
            log("Global config exists. Project config missing.", prefix="ℹ")
            print("\nWould you like to:", file=sys.stderr)
            print("  1. Keep global only (recommended)", file=sys.stderr)
            print("  2. Add project overrides", file=sys.stderr)
            choice = input("Choose [1/2]: ").strip() or "1"
            return 'project' if choice == "2" else 'skip'

    elif existing['project_yaml']:
        log("Project config exists. Global config missing.", prefix="ℹ")
        print("\nWould you like to:", file=sys.stderr)
        print("  1. Keep project only", file=sys.stderr)
        print("  2. Migrate to global (recommended)", file=sys.stderr)
        print("  3. Add global + keep project overrides", file=sys.stderr)
        choice = input("Choose [1/2/3]: ").strip() or "2"
        return {'1': 'skip', '2': 'global', '3': 'both'}.get(choice, 'global')

    else:
        # Fresh install
        log("No existing configuration found.", prefix="ℹ")
        print("\nSetup scope:", file=sys.stderr)
        print("  1. Global (recommended) - One-time setup for all projects", file=sys.stderr)
        print("  2. Project only - Just this project", file=sys.stderr)
        print("  3. Both - Global defaults + project overrides", file=sys.stderr)
        choice = input("Choose [1/2/3]: ").strip() or "1"
        return {'1': 'global', '2': 'project', '3': 'both'}.get(choice, 'global')


def setup_global_config() -> Tuple[bool, List[str]]:
    """
    Setup global configuration files in STABLE location.

    CRITICAL: Creates in ~/.claude/plugins/dev-plugin/ (stable)
              NOT in ~/.claude/plugins/cache/dev-plugin/ (ephemeral)

    Returns:
        Tuple of (success, list of created files)
    """
    created_files = []

    # Get stable global directory (NOT cache)
    global_dir = get_global_config_dir()
    global_dir.mkdir(parents=True, exist_ok=True)

    log(f"Setting up global configuration in: {global_dir}")

    # Copy global yaml template
    config_path = global_dir / "dev-plugin.yaml"
    if copy_template("dev-plugin.global.yaml.template", config_path):
        created_files.append(f"~/.claude/plugins/dev-plugin/dev-plugin.yaml")

    # Copy global env template
    env_path = global_dir / ".env"
    if copy_template("env.global.template", env_path):
        created_files.append(f"~/.claude/plugins/dev-plugin/.env")

    return len(created_files) > 0, created_files


def setup_config_files(claude_dir: Path) -> Tuple[bool, List[str]]:
    """Setup project-level configuration files from templates."""
    created_files = []

    # Copy dev-plugin.yaml template
    config_path = claude_dir / "dev-plugin.yaml"
    if copy_template("dev-plugin.yaml.template", config_path):
        created_files.append(".claude/dev-plugin.yaml")

    # Copy .env template
    env_path = claude_dir / ".env"
    if copy_template("env.template", env_path):
        created_files.append(".claude/.env")

    return len(created_files) > 0, created_files


def setup_dependencies() -> Tuple[bool, List[str], List[str]]:
    """Install required Python dependencies."""
    installed = []
    failed = []

    # PyYAML is critical - must be installed
    if not check_dependency_installed('pyyaml'):
        if install_dependency('pyyaml'):
            installed.append('pyyaml')
        else:
            failed.append('pyyaml')
    else:
        log("Already installed: pyyaml", prefix="⏭")

    return len(failed) == 0, installed, failed


def download_langfuse_compose(target_dir: Path) -> bool:
    """Download official docker-compose.yml from GitHub."""
    url = "https://raw.githubusercontent.com/langfuse/langfuse/main/docker-compose.yml"
    compose_file = target_dir / "docker-compose.yml"

    target_dir.mkdir(parents=True, exist_ok=True)

    try:
        log(f"Downloading Langfuse docker-compose.yml...")
        urllib.request.urlretrieve(url, compose_file)
        log("Downloaded docker-compose.yml", prefix="✓")
        return True
    except Exception as e:
        log(f"Failed to download docker-compose.yml: {e}", prefix="✗")
        return False


def generate_langfuse_env(env_file: Path) -> bool:
    """Generate complete .env file with all Docker secrets."""
    postgres_password = secrets.token_hex(20)
    minio_password = secrets.token_hex(20)

    env_content = f"""# Auto-generated by dev-plugin Setup hook
# Langfuse Docker Compose Environment Variables

# Core Auth & Encryption
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET={secrets.token_hex(32)}
SALT={secrets.token_hex(16)}
ENCRYPTION_KEY={secrets.token_hex(32)}

# PostgreSQL
POSTGRES_USER=postgres
POSTGRES_PASSWORD={postgres_password}
DATABASE_URL=postgresql://postgres:{postgres_password}@postgres:5432/postgres

# ClickHouse
CLICKHOUSE_USER=clickhouse
CLICKHOUSE_PASSWORD={secrets.token_hex(20)}

# Redis
REDIS_AUTH={secrets.token_hex(20)}

# MinIO
MINIO_ROOT_USER=minio
MINIO_ROOT_PASSWORD={minio_password}
"""

    try:
        env_file.write_text(env_content)
        env_file.chmod(0o600)  # Secure permissions
        log("Generated .env with auto-generated secrets", prefix="✓")
        return True
    except Exception as e:
        log(f"Failed to create .env: {e}", prefix="✗")
        return False


def start_langfuse(langfuse_dir: Path) -> bool:
    """Start Langfuse Docker services."""
    log("Starting Langfuse Docker services...")

    # Download compose file if missing
    if not (langfuse_dir / "docker-compose.yml").exists():
        if not download_langfuse_compose(langfuse_dir):
            return False

    # Generate .env if missing
    env_file = langfuse_dir / ".env"
    if not env_file.exists():
        if not generate_langfuse_env(env_file):
            return False

    # Start Docker Compose
    try:
        result = subprocess.run(
            ["docker-compose", "up", "-d"],
            cwd=langfuse_dir,
            capture_output=True,
            timeout=120
        )

        if result.returncode == 0:
            log("Docker services started", prefix="✓")
            return True
        else:
            log(f"Failed to start Docker: {result.stderr.decode()}", prefix="✗")
            return False
    except FileNotFoundError:
        log("Docker Compose not found. Install Docker first.", prefix="✗")
        return False
    except Exception as e:
        log(f"Error starting Docker: {e}", prefix="✗")
        return False


def wait_for_langfuse_health(max_attempts: int = 60, delay: int = 5) -> bool:
    """Poll health endpoint until ready (5 minutes max)."""
    log("Waiting for Langfuse to be ready (up to 5 minutes)...")

    for attempt in range(max_attempts):
        try:
            req = urllib.request.Request('http://localhost:3000/api/public/health')
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    log("Langfuse is ready!", prefix="✓")
                    return True
        except:
            pass

        if attempt < max_attempts - 1:  # Don't sleep on last attempt
            time.sleep(delay)

    log("Timeout waiting for Langfuse health check", prefix="✗")
    return False


def check_langfuse_enabled(claude_dir: Path) -> bool:
    """Check if Langfuse is enabled in config."""
    config_path = claude_dir / "dev-plugin.yaml"
    if not config_path.exists():
        return False

    try:
        import yaml
        with open(config_path) as f:
            config = yaml.safe_load(f)

        return (
            config.get('observability', {})
            .get('langfuse', {})
            .get('enabled', False)
        )
    except ImportError:
        log("PyYAML not available, skipping Langfuse check", prefix="⚠")
        return False
    except Exception as e:
        log(f"Error reading config: {e}", prefix="⚠")
        return False


def setup_langfuse() -> Tuple[bool, str]:
    """Setup Langfuse Docker stack."""
    langfuse_dir = Path.home() / ".langfuse"

    # Start Langfuse
    if not start_langfuse(langfuse_dir):
        return False, "Failed to start Langfuse Docker services"

    # Wait for health check
    if not wait_for_langfuse_health():
        return False, "Langfuse started but health check timed out"

    instructions = """
Langfuse Docker Services Started:
  - langfuse-web (http://localhost:3000)
  - langfuse-worker
  - postgres, clickhouse, redis, minio

Next steps to enable observability:
  1. Visit http://localhost:3000 to create admin account
  2. Go to Settings → API Keys to generate:
     - Public Key (pk-lf-...)
     - Secret Key (sk-lf-...)
  3. Update .claude/.env:
     LANGFUSE_PUBLIC_KEY=pk-lf-YOUR-KEY
     LANGFUSE_SECRET_KEY=sk-lf-YOUR-KEY
  4. Restart claude to begin tracking sessions
"""

    return True, instructions


def generate_success_message(
    created_files: List[str],
    installed_deps: List[str],
    langfuse_setup: bool = False,
    langfuse_msg: str = "",
    scope: str = "project"
) -> str:
    """Generate success message for hookSpecificOutput."""
    lines = ["✨ Development environment initialized!"]

    if created_files:
        lines.append("\nCreated:")
        for file in created_files:
            lines.append(f"  - {file}")

    if installed_deps:
        lines.append("\nInstalled:")
        for dep in installed_deps:
            lines.append(f"  - {dep}")

    if langfuse_setup:
        lines.append(f"\n{langfuse_msg}")
    else:
        lines.append("\nNext steps:")

        if scope == 'global':
            lines.append("  1. Review ~/.claude/plugins/dev-plugin/dev-plugin.yaml")
            lines.append("  2. Add Langfuse credentials to ~/.claude/plugins/dev-plugin/.env (optional)")
            lines.append("  3. Start using Claude Code in ANY project - hooks are now active!")
            lines.append("\nTo add project-specific overrides:")
            lines.append("  Create .claude/dev-plugin.yaml in any project")

        elif scope == 'project':
            lines.append("  1. Review .claude/dev-plugin.yaml and customize as needed")
            lines.append("  2. Start using Claude Code - hooks are now active!")
            lines.append("\nTo use this config globally:")
            lines.append("  Run 'claude --init' and choose 'Migrate to global'")

        elif scope == 'both':
            lines.append("  1. Global defaults: ~/.claude/plugins/dev-plugin/dev-plugin.yaml")
            lines.append("  2. Project overrides: .claude/dev-plugin.yaml")
            lines.append("  3. Start using Claude Code - hooks are now active!")

        if scope in ['global', 'both']:
            lines.append("\nOptional: Enable Langfuse observability")
            lines.append("  1. Edit ~/.claude/plugins/dev-plugin/dev-plugin.yaml:")
            lines.append("     observability.langfuse.enabled: true")
            lines.append("  2. Add credentials to ~/.claude/plugins/dev-plugin/.env")
            lines.append("  3. Run 'claude --init' again to auto-setup Langfuse Docker")

    return "\n".join(lines)


def main() -> int:
    """Main setup logic with global/project/both support."""
    try:
        project_root = get_project_root()
        log(f"🚀 Initializing dev-plugin")
        log(f"Project: {project_root}")

        # Step 1: Check for misplaced configs
        config_warnings = validate_config_locations()
        if config_warnings:
            for warning in config_warnings:
                log(warning, prefix="⚠")
            log("Fix these issues before proceeding.", prefix="⚠")

        # Step 2: Detect existing configs
        existing = detect_existing_configs()

        # Step 3: Prompt for setup scope
        scope = prompt_setup_scope(existing)

        if scope == 'skip':
            log("Configuration already complete.", prefix="✓")
            # Still check if Langfuse needs setup even though config exists
            created_files = []
            installed_deps = []

        else:
            # Track what we create
            created_files = []

            # Step 4: Setup based on scope
            if scope in ['global', 'both']:
                log("Setting up global configuration...")
                global_success, global_files = setup_global_config()
                if global_success:
                    created_files.extend(global_files)

            if scope in ['project', 'both']:
                log("Setting up project configuration...")
                claude_dir = create_claude_directory(project_root)
                project_success, project_files = setup_config_files(claude_dir)
                if project_success:
                    created_files.extend(project_files)

            # Step 5: Install dependencies (only if not already installed)
            deps_success, installed_deps, failed_deps = setup_dependencies()

            # Check for critical failures
            if 'pyyaml' in failed_deps:
                error_output = {
                    "decision": "block",
                    "reason": "PyYAML installation failed",
                    "systemMessage": "⛔ Setup failed: PyYAML is required but installation failed. Install manually: pip install pyyaml"
                }
                print(json.dumps(error_output), file=sys.stderr)
                return 2

        # Step 6: Setup Langfuse (if enabled in final merged config)
        langfuse_setup_success = False
        langfuse_message = ""

        # Check if Langfuse is enabled (check global or project config)
        global_dir = get_global_config_dir()
        claude_dir = project_root / '.claude'

        langfuse_enabled = False
        if (global_dir / 'dev-plugin.yaml').exists():
            langfuse_enabled = check_langfuse_enabled(global_dir)
        if not langfuse_enabled and (claude_dir / 'dev-plugin.yaml').exists():
            langfuse_enabled = check_langfuse_enabled(claude_dir)

        if langfuse_enabled:
            log("Langfuse enabled in config, setting up Docker...")

            # Install langfuse dependency if not already installed
            if not check_dependency_installed('langfuse'):
                if install_dependency('langfuse'):
                    installed_deps.append('langfuse')
                else:
                    log("Warning: langfuse installation failed", prefix="⚠")

            # Setup Langfuse Docker
            langfuse_setup_success, langfuse_message = setup_langfuse()

            if not langfuse_setup_success:
                # Langfuse setup failed - warn but don't block
                warning_output = {
                    "systemMessage": f"⚠ Setup completed with warnings. Langfuse setup failed: {langfuse_message}",
                    "suppressOutput": False
                }
                print(json.dumps(warning_output))
                langfuse_message = f"⚠ Langfuse setup failed: {langfuse_message}\n\nYou can try again by running 'claude --init' or set up manually."

        # Generate success message
        success_message = generate_success_message(
            created_files,
            installed_deps,
            langfuse_setup_success,
            langfuse_message,
            scope
        )

        # Output JSON for Claude Code
        output = {
            "hookSpecificOutput": {
                "hookEventName": "Setup",
                "additionalContext": success_message
            }
        }
        print(json.dumps(output))

        return 0

    except Exception as e:
        error_output = {
            "decision": "block",
            "reason": f"Setup failed: {str(e)}",
            "systemMessage": f"⛔ Setup failed with error: {str(e)}"
        }
        print(json.dumps(error_output), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
