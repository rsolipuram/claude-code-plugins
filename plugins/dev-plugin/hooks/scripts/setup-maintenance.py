#!/usr/bin/env python3
"""
Setup Hook - Maintenance Mode
Validates dev-plugin environment without making changes.
Triggered by: claude --maintenance
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple


def log(message: str, prefix: str = "ℹ") -> None:
    """Print formatted log message to stderr."""
    print(f"{prefix} {message}", file=sys.stderr)


def get_project_root() -> Path:
    """Get project root (current working directory)."""
    return Path.cwd()


def check_config_files(claude_dir: Path) -> Tuple[bool, List[str]]:
    """Check if config files exist and are valid."""
    issues = []

    # Check dev-plugin.yaml
    config_path = claude_dir / "dev-plugin.yaml"
    if not config_path.exists():
        issues.append("Missing: .claude/dev-plugin.yaml (run 'claude --init')")
    else:
        # Try to validate YAML
        try:
            import yaml
            with open(config_path) as f:
                yaml.safe_load(f)
        except ImportError:
            issues.append("Warning: PyYAML not installed, cannot validate config")
        except Exception as e:
            issues.append(f"Invalid YAML in dev-plugin.yaml: {e}")

    # Check .env (optional, just warn if missing)
    env_path = claude_dir / ".env"
    if not env_path.exists():
        issues.append("Info: .claude/.env not found (optional for Langfuse)")

    return len(issues) == 0, issues


def check_dependencies() -> Tuple[bool, List[str]]:
    """Check if required dependencies are installed."""
    issues = []

    # Check PyYAML
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'show', 'pyyaml'],
            capture_output=True,
            timeout=10
        )
        if result.returncode != 0:
            issues.append("Missing: pyyaml (run 'claude --init')")
    except Exception as e:
        issues.append(f"Error checking pyyaml: {e}")

    return len(issues) == 0, issues


def main() -> int:
    """Main validation logic."""
    try:
        project_root = get_project_root()
        claude_dir = project_root / ".claude"

        all_issues = []

        # Check .claude directory exists
        if not claude_dir.exists():
            log("Setup required: .claude directory not found", prefix="⚠")
            output = {
                "systemMessage": "⚠ Setup required: Run 'claude --init' to initialize dev-plugin",
                "suppressOutput": False
            }
            print(json.dumps(output))
            return 1

        # Check config files
        config_ok, config_issues = check_config_files(claude_dir)
        all_issues.extend(config_issues)

        # Check dependencies
        deps_ok, deps_issues = check_dependencies()
        all_issues.extend(deps_issues)

        # Report results
        if not all_issues:
            # Silent success - no output needed
            return 0
        else:
            # Report issues as warnings
            issues_text = "\n".join([f"  - {issue}" for issue in all_issues])
            output = {
                "systemMessage": f"⚠ Environment issues detected:\n{issues_text}\n\nRun 'claude --init' to fix.",
                "suppressOutput": False
            }
            print(json.dumps(output))
            return 1

    except Exception as e:
        error_output = {
            "systemMessage": f"⛔ Maintenance check failed: {str(e)}",
            "suppressOutput": False
        }
        print(json.dumps(error_output))
        return 1


if __name__ == "__main__":
    sys.exit(main())
