#!/usr/bin/env python3
"""
Dependency checker and auto-installer for dev-plugin.
Runs on SessionStart to ensure all required dependencies are available.
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Try to import yaml at module level
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

class DependencyChecker:
    """Check and optionally install plugin dependencies."""

    REQUIRED_DEPS = [
        ('yaml', 'pyyaml', 'Required for configuration file parsing')
    ]

    OPTIONAL_DEPS = [
        ('langfuse', 'langfuse', 'Optional for observability tracking with Langfuse integration')
    ]

    def __init__(self):
        self.plugin_root = Path(__file__).parent.parent.parent
        self.config = self._load_config()
        self.missing_required: List[Tuple[str, str, str]] = []
        self.missing_optional: List[Tuple[str, str, str]] = []

    def _load_config(self) -> Dict:
        """Load plugin configuration."""
        config_paths = [
            Path.cwd() / '.claude' / 'dev-plugin.local.md',
            Path.home() / '.claude' / 'dev-plugin.local.md'
        ]

        for config_path in config_paths:
            if config_path.exists():
                try:
                    content = config_path.read_text()
                    if '---' in content and YAML_AVAILABLE:
                        parts = content.split('---', 2)
                        if len(parts) >= 2:
                            return yaml.safe_load(parts[1]) or {}
                except Exception:
                    pass

        return {}

    def check_dependency(self, import_name: str, package_name: str) -> bool:
        """Check if a Python package is importable."""
        try:
            __import__(import_name)
            return True
        except ImportError:
            return False

    def check_all_dependencies(self) -> bool:
        """Check all dependencies and categorize missing ones."""
        all_present = True

        # Check required dependencies
        for import_name, package_name, description in self.REQUIRED_DEPS:
            if not self.check_dependency(import_name, package_name):
                self.missing_required.append((import_name, package_name, description))
                all_present = False

        # Check optional dependencies (only if features are enabled)
        observability_enabled = self.config.get('observability', {}).get('enabled', False)
        langfuse_enabled = self.config.get('observability', {}).get('langfuse', {}).get('enabled', False)

        if observability_enabled and langfuse_enabled:
            for import_name, package_name, description in self.OPTIONAL_DEPS:
                if not self.check_dependency(import_name, package_name):
                    self.missing_optional.append((import_name, package_name, description))

        return all_present

    def auto_install_dependencies(self) -> bool:
        """Automatically install missing dependencies."""
        auto_install = self.config.get('auto_install_dependencies', True)

        if not auto_install:
            return False

        # Only auto-install required dependencies
        if not self.missing_required:
            return True

        packages_to_install = [pkg for _, pkg, _ in self.missing_required]

        try:
            # Try to install using pip
            subprocess.run(
                [sys.executable, '-m', 'pip', 'install', '--quiet'] + packages_to_install,
                check=True,
                capture_output=True,
                timeout=60
            )
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return False

    def generate_report(self) -> Dict:
        """Generate a report of dependency status."""
        messages = []

        if self.missing_required:
            messages.append("\n⚠️  **Missing Required Dependencies**")
            messages.append("\nThe following dependencies are required for the dev-plugin to work:")
            for _, package_name, description in self.missing_required:
                messages.append(f"  • {package_name}: {description}")

            messages.append("\n**Installation:**")
            messages.append(f"  pip install {' '.join(pkg for _, pkg, _ in self.missing_required)}")
            messages.append("\nOr enable auto-install in `.claude/dev-plugin.local.md`:")
            messages.append("```yaml")
            messages.append("---")
            messages.append("auto_install_dependencies: true")
            messages.append("---")
            messages.append("```")

        if self.missing_optional:
            messages.append("\n📦 **Missing Optional Dependencies**")
            messages.append("\nThe following optional dependencies are needed for features you have enabled:")
            for _, package_name, description in self.missing_optional:
                messages.append(f"  • {package_name}: {description}")

            messages.append("\n**Installation:**")
            messages.append(f"  pip install {' '.join(pkg for _, pkg, _ in self.missing_optional)}")

        if not self.missing_required and not self.missing_optional:
            return {
                'success': True,
                'message': '✓ All dependencies are installed'
            }

        return {
            'success': False,
            'message': '\n'.join(messages)
        }

def main():
    """Main entry point."""
    try:
        # Read hook input (optional)
        try:
            stdin_content = sys.stdin.read().strip()
            hook_input = json.loads(stdin_content) if stdin_content else {}
        except (json.JSONDecodeError, ValueError):
            hook_input = {}

        checker = DependencyChecker()
        all_present = checker.check_all_dependencies()

        # Try to auto-install if enabled and dependencies are missing
        if not all_present and checker.missing_required:
            auto_install_success = checker.auto_install_dependencies()
            if auto_install_success:
                # Re-check after installation
                checker.missing_required = []
                all_present = checker.check_all_dependencies()

        # Generate report
        report = checker.generate_report()

        # Output result
        if not report['success']:
            print(json.dumps({
                'success': False,
                'message': report['message']
            }))
            sys.exit(2)  # Non-blocking error

        # Silent success (don't clutter output)
        print(json.dumps({'success': True}))
        sys.exit(0)

    except Exception as e:
        print(json.dumps({
            'success': False,
            'message': f'Dependency check error: {str(e)}'
        }))
        sys.exit(2)  # Non-blocking error

if __name__ == '__main__':
    main()
