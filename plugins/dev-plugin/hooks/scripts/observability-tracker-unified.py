#!/usr/bin/env python3
"""
Unified Observability Tracker for Claude Code sessions.
Handles Langfuse setup, session tracking, and data persistence.

Features:
- Auto-setup Langfuse environment (async)
- Track sessions, tools, files, prompts
- Persist data locally + sync to Langfuse
- Graceful fallback to local JSON
"""

import json
import os
import subprocess
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
import hashlib


class ObservabilityTracker:
    """Unified observability tracker with Langfuse management."""

    def __init__(self, project_dir: Path, config: Dict):
        self.project_dir = project_dir
        self.config = config
        self.obs_config = config.get('observability', {})
        self.langfuse_config = self.obs_config.get('langfuse', {})
        self.session_data = {}
        self.langfuse_client = None

    # ========================================
    # SESSION START: Quick Check + Async Setup
    # ========================================

    def handle_session_start(self, hook_input: Dict) -> Dict:
        """Initialize session tracking and check/start Langfuse."""

        # Initialize session (quick, <1s)
        session_id = self._initialize_session(hook_input)

        # Quick Langfuse health check
        if self.langfuse_config.get('enabled', False):
            if self._is_langfuse_healthy():
                self._connect_langfuse()
                return {
                    "systemMessage": f"📊 Session tracking: {session_id[:8]} (Langfuse ready)",
                    "suppressOutput": False
                }
            else:
                # Spawn async setup if auto_setup enabled
                if self.langfuse_config.get('auto_setup', False):
                    self._spawn_async_setup()
                    return {
                        "systemMessage": f"📊 Session tracking: {session_id[:8]} (Langfuse setup running in background)",
                        "suppressOutput": False
                    }
                elif self.langfuse_config.get('auto_start', False):
                    # Just try to start if already installed
                    self._try_start_langfuse()
                    return {
                        "systemMessage": f"📊 Session tracking: {session_id[:8]} (Langfuse starting)",
                        "suppressOutput": False
                    }
                else:
                    return {
                        "systemMessage": f"📊 Session tracking: {session_id[:8]} (local mode)",
                        "suppressOutput": False
                    }

        return {
            "systemMessage": f"📊 Session tracking initialized: {session_id[:8]}",
            "suppressOutput": False
        }

    def _initialize_session(self, hook_input: Dict) -> str:
        """Initialize session data structure."""
        session_id = hook_input.get('session_id', self._generate_session_id())

        self.session_data = {
            'session_id': session_id,
            'project_dir': str(self.project_dir),
            'project_name': self.project_dir.name,
            'start_time': datetime.now().isoformat(),
            'tools_used': [],
            'files_modified': [],
            'files_created': [],
            'files_deleted': [],
            'errors': [],
            'total_tool_calls': 0,
            'prompts_submitted': 0,
            'hook_event': 'SessionStart'
        }

        self._save_session()
        return session_id

    def _is_langfuse_healthy(self) -> bool:
        """Quick health check for Langfuse (<2s)."""
        try:
            host = self.langfuse_config.get('host', 'http://localhost:3000')
            health_url = f"{host}/api/public/health"
            req = urllib.request.Request(health_url, method='GET')
            with urllib.request.urlopen(req, timeout=2) as response:
                return response.status == 200
        except (urllib.error.URLError, urllib.error.HTTPError, Exception):
            return False

    def _connect_langfuse(self) -> None:
        """Connect to Langfuse (sets up client for later use)."""
        try:
            from langfuse import Langfuse
            self.langfuse_client = Langfuse(
                host=self.langfuse_config.get('host', 'http://localhost:3000'),
                public_key=self.langfuse_config.get('public_key', ''),
                secret_key=self.langfuse_config.get('secret_key', '')
            )
        except ImportError:
            self.langfuse_client = None

    def _spawn_async_setup(self) -> None:
        """Spawn background Langfuse setup process (non-blocking)."""
        setup_script = Path(__file__).parent / 'langfuse-setup.py'
        if setup_script.exists():
            subprocess.Popen(
                ['python3', str(setup_script)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=self.project_dir
            )

    def _try_start_langfuse(self) -> bool:
        """Try to start Langfuse if installed (quick attempt)."""
        compose_path = self._find_compose_file()
        if compose_path:
            try:
                subprocess.Popen(
                    ['docker-compose', 'up', '-d'],
                    cwd=compose_path.parent,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                return True
            except Exception:
                return False
        return False

    def _find_compose_file(self) -> Optional[Path]:
        """Find docker-compose file for Langfuse."""
        # Check config first
        compose_path = self.langfuse_config.get('compose_path')
        if compose_path:
            path = Path(compose_path).expanduser()
            if path.exists():
                return path

        # Search common locations
        search_paths = [
            self.project_dir / 'langfuse' / 'docker-compose.yml',
            Path.home() / 'langfuse-docker' / 'docker-compose.yml',
            Path.home() / '.langfuse' / 'docker-compose.yml',
        ]

        for path in search_paths:
            if path.exists():
                content = path.read_text()
                if 'langfuse' in content.lower():
                    return path

        return None

    # ========================================
    # TOOL TRACKING
    # ========================================

    def handle_tool_use(self, hook_input: Dict) -> Dict:
        """Track tool usage (PostToolUse hook)."""
        self._load_session()

        if not self.session_data:
            return {"success": True, "suppressOutput": True}

        # Extract tool info
        tool_name = hook_input.get('tool_name', 'Unknown')
        tool_input_data = hook_input.get('tool_input', {})
        tool_result = hook_input.get('tool_result', {})

        # Track tool
        tool_record = {
            'tool': tool_name,
            'timestamp': datetime.now().isoformat(),
            'success': not isinstance(tool_result, dict) or not tool_result.get('error')
        }

        # Track file operations
        if tool_name in ['Edit', 'Write']:
            file_path = tool_input_data.get('file_path', '')
            if file_path:
                if tool_name == 'Edit' and file_path not in self.session_data['files_modified']:
                    self.session_data['files_modified'].append(file_path)
                elif tool_name == 'Write' and file_path not in self.session_data['files_created']:
                    self.session_data['files_created'].append(file_path)

        self.session_data['tools_used'].append(tool_record)
        self.session_data['total_tool_calls'] += 1

        self._save_session()

        return {"success": True, "suppressOutput": True}

    # ========================================
    # PROMPT TRACKING
    # ========================================

    def handle_prompt(self, hook_input: Dict) -> Dict:
        """Track user prompt submission (UserPromptSubmit hook)."""
        self._load_session()

        if not self.session_data:
            # Initialize if needed
            self._initialize_session(hook_input)

        self.session_data['prompts_submitted'] += 1
        self.session_data['last_prompt_time'] = datetime.now().isoformat()

        self._save_session()

        return {"success": True, "suppressOutput": True}

    # ========================================
    # SESSION FINALIZATION
    # ========================================

    def handle_stop(self, hook_input: Dict) -> Dict:
        """Finalize session tracking (Stop hook)."""
        self._load_session()

        if not self.session_data:
            return {"success": True, "suppressOutput": True}

        # Add end time and duration
        self.session_data['end_time'] = datetime.now().isoformat()
        start = datetime.fromisoformat(self.session_data['start_time'])
        end = datetime.fromisoformat(self.session_data['end_time'])
        duration = (end - start).total_seconds()
        self.session_data['duration_seconds'] = duration

        # Calculate summary
        self.session_data['summary'] = {
            'total_tools': self.session_data['total_tool_calls'],
            'unique_tools': len(set(t['tool'] for t in self.session_data['tools_used'])),
            'files_modified': len(self.session_data['files_modified']),
            'files_created': len(self.session_data['files_created']),
            'errors': len(self.session_data['errors']),
            'duration_minutes': round(duration / 60, 2)
        }

        # Save final session
        self._save_session()

        # Send to Langfuse (with fallback)
        self._send_to_langfuse()

        # Archive locally
        self._archive_session()

        summary = self.session_data['summary']
        return {
            "systemMessage": f"📊 Session complete: {summary['total_tools']} tools, {summary['files_modified']} files modified, {summary['duration_minutes']}min",
            "suppressOutput": False
        }

    # ========================================
    # DATA PERSISTENCE
    # ========================================

    def _save_session(self) -> None:
        """Save session to local JSON (primary storage)."""
        obs_dir = self.project_dir / '.claude' / 'observability'
        obs_dir.mkdir(parents=True, exist_ok=True)

        session_file = obs_dir / 'current-session.json'
        session_file.write_text(json.dumps(self.session_data, indent=2))

    def _load_session(self) -> None:
        """Load current session from local JSON."""
        session_file = self.project_dir / '.claude' / 'observability' / 'current-session.json'
        if session_file.exists():
            try:
                self.session_data = json.loads(session_file.read_text())
            except Exception:
                self.session_data = {}

    def _archive_session(self) -> None:
        """Archive completed session to sessions/ directory."""
        obs_dir = self.project_dir / '.claude' / 'observability' / 'sessions'
        obs_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        session_id = self.session_data.get('session_id', 'unknown')[:8]
        archive_file = obs_dir / f'session-{timestamp}-{session_id}.json'

        archive_file.write_text(json.dumps(self.session_data, indent=2))

        # Clean up current session
        session_file = self.project_dir / '.claude' / 'observability' / 'current-session.json'
        if session_file.exists():
            session_file.unlink()

    def _send_to_langfuse(self) -> None:
        """Send session data to Langfuse (with graceful fallback)."""
        if not self.langfuse_config.get('enabled', False):
            return

        # Try to connect if not already connected
        if not self.langfuse_client:
            self._connect_langfuse()

        if not self.langfuse_client:
            return  # SDK not available

        try:
            # Create trace
            trace = self.langfuse_client.trace(
                name="claude-code-session",
                id=self.session_data['session_id'],
                user_id=self.langfuse_config.get('userId'),
                version=self.langfuse_config.get('version'),
                tags=self.langfuse_config.get('tags'),
                metadata={
                    'project': self.session_data['project_name'],
                    'project_dir': self.session_data['project_dir'],
                    'duration_seconds': self.session_data.get('duration_seconds', 0),
                    'summary': self.session_data.get('summary', {})
                },
                input={
                    'prompts_submitted': self.session_data.get('prompts_submitted', 0)
                },
                output={
                    'files_modified': self.session_data['files_modified'],
                    'files_created': self.session_data['files_created'],
                    'total_tools': self.session_data['total_tool_calls']
                }
            )

            # Add tool usage spans
            for tool_record in self.session_data['tools_used']:
                trace.span(
                    name=f"tool_{tool_record['tool']}",
                    start_time=datetime.fromisoformat(tool_record['timestamp']),
                    metadata={'success': tool_record['success']}
                )

            # Flush
            self.langfuse_client.flush()

        except Exception as e:
            # Graceful fallback - local JSON is source of truth
            self.session_data['langfuse_error'] = str(e)

    # ========================================
    # UTILITIES
    # ========================================

    def _generate_session_id(self) -> str:
        """Generate unique session ID."""
        timestamp = datetime.now().isoformat()
        random_data = os.urandom(8).hex()
        return hashlib.sha256(f"{timestamp}{random_data}".encode()).hexdigest()[:16]


# ========================================
# CONFIGURATION
# ========================================

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

    return {
        'observability': {
            'enabled': False,
            'langfuse': {
                'enabled': False,
                'auto_setup': False,
                'auto_start': False
            }
        }
    }


# ========================================
# MAIN ENTRY POINT
# ========================================

def main():
    """Main hook execution."""
    try:
        # Read hook input
        try:
            stdin_content = sys.stdin.read().strip()
            hook_input = json.loads(stdin_content) if stdin_content else {}
        except (json.JSONDecodeError, ValueError):
            hook_input = {}

        # Get project directory
        project_dir = Path(os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd()))

        # Load configuration
        config = load_config(project_dir)

        # Check if enabled
        if not config.get('observability', {}).get('enabled', False):
            print(json.dumps({"success": True, "suppressOutput": True}))
            sys.exit(0)

        # Initialize tracker
        tracker = ObservabilityTracker(project_dir, config)

        # Route by hook event
        hook_event = hook_input.get('hook_event_name', '')

        if hook_event == 'SessionStart':
            result = tracker.handle_session_start(hook_input)
        elif hook_event == 'PostToolUse':
            result = tracker.handle_tool_use(hook_input)
        elif hook_event == 'UserPromptSubmit':
            result = tracker.handle_prompt(hook_input)
        elif hook_event == 'Stop':
            result = tracker.handle_stop(hook_input)
        else:
            result = {"success": True, "suppressOutput": True}

        print(json.dumps(result))
        sys.exit(0)

    except Exception as e:
        error_output = {
            "systemMessage": f"⚠️ Observability error: {str(e)}",
            "suppressOutput": False
        }
        print(json.dumps(error_output))
        sys.exit(0)


if __name__ == '__main__':
    main()
