#!/usr/bin/env python3
"""
Langfuse service manager for Claude Code observability.
Checks if Langfuse is configured, running, and optionally starts it.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional
import urllib.request
import urllib.error


class LangfuseManager:
    """Manages Langfuse service lifecycle."""

    def __init__(self, project_dir: Path, config: Dict):
        self.project_dir = project_dir
        self.config = config
        self.langfuse_config = config.get('observability', {}).get('langfuse', {})

    def check_and_start(self) -> Dict:
        """Check if Langfuse should be running and start if needed."""
        # Check if Langfuse is enabled
        if not self.langfuse_config.get('enabled', False):
            return {
                "success": True,
                "suppressOutput": True
            }

        # Get host URL
        host = self.langfuse_config.get('host', 'http://localhost:3000')

        # Check if already running
        if self._is_running(host):
            return {
                "success": True,
                "suppressOutput": True
            }

        # Try to start Langfuse
        started = self._start_langfuse()

        if started:
            # Wait and verify it started
            import time
            time.sleep(2)
            if self._is_running(host):
                return {
                    "systemMessage": "🚀 Langfuse started successfully",
                    "suppressOutput": False
                }
            else:
                return {
                    "systemMessage": "⚠️ Langfuse start attempted but service not responding",
                    "suppressOutput": False
                }
        else:
            return {
                "systemMessage": "⚠️ Langfuse not running (enable auto-start in config or start manually)",
                "suppressOutput": False
            }

    def _is_running(self, host: str) -> bool:
        """Check if Langfuse is running."""
        try:
            # Try health check endpoint
            health_url = f"{host}/api/public/health"
            req = urllib.request.Request(health_url, method='GET')
            with urllib.request.urlopen(req, timeout=2) as response:
                return response.status == 200
        except (urllib.error.URLError, urllib.error.HTTPError, Exception):
            return False

    def _start_langfuse(self) -> bool:
        """Attempt to start Langfuse service."""
        # Check if auto-start is enabled
        auto_start = self.langfuse_config.get('auto_start', False)
        if not auto_start:
            return False

        # Look for docker-compose file
        compose_path = self._find_compose_file()
        if not compose_path:
            return False

        try:
            # Start with docker-compose
            subprocess.run(
                ['docker-compose', 'up', '-d'],
                cwd=compose_path.parent,
                capture_output=True,
                timeout=30
            )
            return True
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            return False

    def _find_compose_file(self) -> Optional[Path]:
        """Find docker-compose file for Langfuse."""
        # Check for compose file path in config
        compose_path = self.langfuse_config.get('compose_path')
        if compose_path:
            path = Path(compose_path).expanduser()
            if path.exists():
                return path

        # Search common locations
        search_paths = [
            self.project_dir / 'langfuse' / 'docker-compose.yml',
            self.project_dir / 'docker-compose.yml',
            Path.home() / 'langfuse' / 'docker-compose.yml',
            Path.home() / '.langfuse' / 'docker-compose.yml',
        ]

        for path in search_paths:
            if path.exists():
                # Verify it's a Langfuse compose file
                content = path.read_text()
                if 'langfuse' in content.lower():
                    return path

        return None


def load_config(project_dir: Path) -> Dict:
    """Load configuration from .claude/dev-plugin.local.md."""
    config_paths = [
        project_dir / '.claude' / 'dev-plugin.local.md',
        Path.home() / '.claude' / 'plugins' / 'dev-plugin' / 'settings.local.md'
    ]

    for config_path in config_paths:
        if config_path.exists():
            try:
                content = config_path.read_text()
                if content.startswith('---'):
                    import yaml
                    parts = content.split('---', 2)
                    if len(parts) >= 2:
                        return yaml.safe_load(parts[1]) or {}
            except Exception:
                pass

    return {}


def main():
    """Main execution."""
    try:
        # Get project directory
        project_dir = Path(os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd()))

        # Load configuration
        config = load_config(project_dir)

        # Initialize manager
        manager = LangfuseManager(project_dir, config)

        # Check and start
        result = manager.check_and_start()

        # Output result
        print(json.dumps(result))
        sys.exit(0)

    except Exception as e:
        # Error handling - don't block Claude
        error_output = {
            "systemMessage": f"⚠️ Langfuse manager error: {str(e)}",
            "suppressOutput": False
        }
        print(json.dumps(error_output))
        sys.exit(0)


if __name__ == '__main__':
    main()
