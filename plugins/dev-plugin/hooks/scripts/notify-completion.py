#!/usr/bin/env python3
# /// script
# dependencies = [
#   "pyyaml",
# ]
# ///
"""
Completion notification hook for Claude Code.
Sends creative audio notifications when sessions complete.

Features:
- Creative TTS voices (contextual voice selection)
- Sound effects library support
- Multiple audio modes (TTS-only, sound-only, mixed, creative)
- Backwards compatible with existing config
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Import audio notification system
try:
    from audio_notify import AudioNotifier
    AUDIO_NOTIFY_AVAILABLE = True
except ImportError:
    AUDIO_NOTIFY_AVAILABLE = False


class CompletionNotifier:
    """Manages completion notifications for Claude Code sessions."""

    def __init__(self, project_dir: Path, config: Optional[Dict] = None):
        self.project_dir = project_dir
        self.config = config or {}

    def get_session_summary(self) -> Dict[str, any]:
        """Generate a summary of the session's changes."""
        summary = {
            'files_modified': [],
            'files_created': [],
            'files_deleted': [],
            'total_changes': 0
        }

        try:
            # Get git status if available
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if not line:
                        continue

                    status = line[:2]
                    filename = line[3:]

                    if 'M' in status:
                        summary['files_modified'].append(filename)
                    elif 'A' in status or '??' == status:
                        summary['files_created'].append(filename)
                    elif 'D' in status:
                        summary['files_deleted'].append(filename)

                summary['total_changes'] = (
                    len(summary['files_modified']) +
                    len(summary['files_created']) +
                    len(summary['files_deleted'])
                )

        except Exception:
            pass

        return summary

    def format_summary_message(self, summary: Dict[str, any]) -> str:
        """Format session summary into a readable message."""
        if summary['total_changes'] == 0:
            return "Claude Code session completed (no file changes detected)"

        parts = []
        if summary['files_modified']:
            parts.append(f"Modified: {len(summary['files_modified'])} files")
        if summary['files_created']:
            parts.append(f"Created: {len(summary['files_created'])} files")
        if summary['files_deleted']:
            parts.append(f"Deleted: {len(summary['files_deleted'])} files")

        return "Claude Code session completed. " + "; ".join(parts)

    def _build_notification_context(self, summary: Dict[str, any]) -> Dict[str, any]:
        """Build context for audio notification based on session summary."""
        context = {
            'event_type': 'completion',
            'has_errors': False,
            'has_warnings': False,
            'is_success': True
        }

        # Determine success based on changes
        # NOTE: All completion events should use 'success' category for sounds
        # The voice profile can vary, but the sound should always be from success/
        if summary['total_changes'] == 0:
            context['voice_profile'] = 'neutral'
            context['sound_category'] = 'success'  # Fixed: use success sounds even for no changes
        elif summary['files_deleted']:
            # Deletions might be intentional, but use cautious voice
            context['voice_profile'] = 'completion'
            context['sound_category'] = 'success'
        else:
            # Files created or modified - success!
            context['voice_profile'] = 'success'
            context['sound_category'] = 'success'

        return context

    def send_notifications(self) -> Tuple[bool, str]:
        """Send completion notifications based on configuration."""
        notif_config = self.config.get('notifications', {})

        # Handle case where notifications is just a boolean
        if isinstance(notif_config, bool):
            if not notif_config:
                return True, "Notifications disabled"
            # If True, use default config (sound only, no speech)
            notif_config = {
                'enabled': True,
                'audio': {'mode': 'sound_only', 'sound_library': '~/.claude/audio'},
                'completion': {'enabled': True, 'sound': True, 'tts': False, 'contextual_voice': False},
                'tts': {'enabled': False, 'timeout': 30, 'rate_adjustment': 0}
            }

        if not notif_config.get('enabled', True):
            return True, "Notifications disabled"

        # Get session summary
        summary = self.get_session_summary()
        message = self.format_summary_message(summary)
        context = self._build_notification_context(summary)

        results = []

        # Use new audio notification system if available
        if AUDIO_NOTIFY_AVAILABLE:
            # Check if audio is enabled (completion config)
            completion_config = notif_config.get('completion', {})
            audio_enabled = completion_config.get('enabled', True)

            if audio_enabled:
                try:
                    # Create notifier with full config
                    notifier = AudioNotifier(notif_config)

                    # Override voice profile if contextual_voice is enabled
                    if completion_config.get('contextual_voice', True):
                        # Use context-detected voice
                        pass  # AudioNotifier will auto-detect
                    else:
                        # Use explicit voice overrides if provided
                        voices = completion_config.get('voices', {})
                        if summary['total_changes'] == 0:
                            voice = voices.get('neutral', 'neutral')
                        elif summary['files_deleted']:
                            voice = voices.get('warning', 'warning')
                        else:
                            voice = voices.get('success', 'success')
                        context['voice_profile'] = voice

                    # Send notification
                    success = notifier.notify(message, context)
                    if success:
                        results.append("🔊 Audio notification sent")
                    else:
                        results.append("⚠ Audio notification failed")
                except Exception as e:
                    results.append(f"⚠ Audio error: {str(e)}")
            else:
                results.append("Audio notifications disabled in config")
        else:
            # Fallback to legacy TTS if audio-notify not available
            if notif_config.get('tts', False):
                try:
                    import subprocess
                    subprocess.run(['say', message.split('.')[0]], capture_output=True, timeout=30)
                    results.append("✓ TTS completed (legacy)")
                except Exception:
                    results.append("⚠ TTS failed")

        return True, ' | '.join(results) if results else "No notifications sent"


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
        'notifications': {
            'enabled': True,
            'audio': {
                'mode': 'sound_only',
                'sound_library': '~/.claude/audio'
            },
            'completion': {
                'enabled': True,
                'sound': True,
                'tts': False,
                'contextual_voice': False
            },
            'tts': {
                'enabled': False,
                'timeout': 30,
                'rate_adjustment': 0
            }
        }
    }


def main():
    """Main hook execution."""
    try:
        # Read stdin for hook event data
        stdin_data = None
        try:
            stdin_text = sys.stdin.read()
            if stdin_text:
                stdin_data = json.loads(stdin_text)
        except Exception:
            pass

        # Log to file for debugging
        project_dir = Path(os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd()))
        log_file = project_dir / '.claude' / 'hook-debug.log'
        log_file.parent.mkdir(parents=True, exist_ok=True)

        from datetime import datetime
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        with open(log_file, 'a') as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"STOP HOOK - {timestamp}\n")
            f.write(f"{'='*60}\n")
            f.write(f"STDIN: {json.dumps(stdin_data, indent=2) if stdin_data else 'None'}\n")
            f.write(f"ENV - CLAUDE_PROJECT_DIR: {os.environ.get('CLAUDE_PROJECT_DIR', 'not set')}\n")
            f.write(f"ENV - CLAUDE_PLUGIN_ROOT: {os.environ.get('CLAUDE_PLUGIN_ROOT', 'not set')}\n")
            f.write(f"CWD: {os.getcwd()}\n")
            f.write(f"{'='*60}\n\n")

        config = load_config(project_dir)
        notifier = CompletionNotifier(project_dir, config)
        _, message = notifier.send_notifications()

        if message:
            print(json.dumps({"systemMessage": message, "suppressOutput": False}))
        sys.exit(0)

    except Exception as e:
        # Log exception to file
        try:
            import traceback
            project_dir = Path(os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd()))
            log_file = project_dir / '.claude' / 'hook-debug.log'
            with open(log_file, 'a') as f:
                f.write(f"ERROR: {str(e)}\n")
                f.write(traceback.format_exc())
                f.write("\n")
        except Exception:
            pass
        print(json.dumps({"systemMessage": f"⚠ Notification error: {str(e)}", "suppressOutput": False}))
        sys.exit(0)


if __name__ == '__main__':
    main()
