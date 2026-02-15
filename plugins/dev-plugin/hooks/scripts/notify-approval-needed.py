#!/usr/bin/env python3
# /// script
# dependencies = [
#   "pyyaml",
# ]
# ///
"""
Notification hook for Claude Code - "Come Back!" notifications

Plays fun audio alerts when Claude needs user approval or attention.
Helps you multitask by alerting you when interaction is needed.

Features:
- Attention-grabbing sound effects
- Creative TTS voices (Trinoids, Bells)
- Configurable audio modes
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

# Import shared config loader
from config import load_config

# Import audio notification system
try:
    from audio_notify import AudioNotifier
    AUDIO_NOTIFY_AVAILABLE = True
except ImportError:
    AUDIO_NOTIFY_AVAILABLE = False


class ApprovalNotifier:
    """Manages approval-needed notifications."""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}

    def _parse_notification_context(self, hook_input: Dict) -> Dict[str, any]:
        """Parse context from hook input."""
        # Hook input may contain information about what needs approval
        context = {
            'event_type': 'approval_needed',
            'voice_profile': 'needs_input',
            'sound_category': 'notify',
            'is_success': True
        }

        # Try to detect if this is a critical approval
        notification_type = hook_input.get('type', '')
        if notification_type == 'error' or notification_type == 'critical':
            context['voice_profile'] = 'critical'
            context['sound_category'] = 'error'

        return context

    def _format_approval_message(self, hook_input: Dict) -> str:
        """Format message for approval notification."""
        # Default message
        default_message = "Approval needed, come back"

        # Try to extract more context from hook input
        message = hook_input.get('message', '')
        notification_type = hook_input.get('type', '')

        if message:
            # Shorten message for TTS
            if len(message) > 50:
                message = message[:50] + "..."
            return message
        elif notification_type:
            return f"{notification_type.title()} - {default_message}"

        return default_message

    def send_notification(self, hook_input: Optional[Dict] = None) -> Tuple[bool, str]:
        """Send approval notification."""
        hook_input = hook_input or {}
        notif_config = self.config.get('notifications', {})

        # Handle case where notifications is just a boolean
        if isinstance(notif_config, bool):
            if not notif_config:
                return True, "Notifications disabled"
            # If True, use default config (sound only, no speech)
            notif_config = {
                'enabled': True,
                'audio': {'mode': 'sound_only', 'sound_library': os.environ.get('CLAUDE_PLUGIN_ROOT', '') + '/hooks/audio' if os.environ.get('CLAUDE_PLUGIN_ROOT') else '~/.claude/audio'},
                'approval': {'enabled': True, 'sound': True, 'tts': False, 'voice': 'Trinoids', 'rate': 140},
                'tts': {'enabled': False, 'timeout': 30, 'rate_adjustment': 0}
            }

        # Check if notifications are enabled globally
        if not notif_config.get('enabled', True):
            return True, "Notifications disabled"

        # Check if approval notifications are enabled
        approval_config = notif_config.get('approval', {})
        if not approval_config.get('enabled', True):
            return True, "Approval notifications disabled"

        # Build notification
        context = self._parse_notification_context(hook_input)
        message = self._format_approval_message(hook_input)

        results = []

        # Use audio notification system
        if AUDIO_NOTIFY_AVAILABLE:
            try:
                # Create notifier with full config
                notifier = AudioNotifier(notif_config)

                # Override context with config settings if provided
                if 'voice' in approval_config:
                    # Map voice name to profile
                    voice_map = {
                        'Trinoids': 'needs_input',
                        'Bells': 'approval_needed',
                        'Superstar': 'critical',
                        'Wobble': 'waiting'
                    }
                    voice_name = approval_config.get('voice', 'Trinoids')
                    context['voice_profile'] = voice_map.get(voice_name, 'needs_input')

                # Determine mode based on config
                force_mode = None
                if approval_config.get('sound', True) and not approval_config.get('tts', True):
                    force_mode = 'sound_only'
                elif approval_config.get('tts', True) and not approval_config.get('sound', True):
                    force_mode = 'tts_only'
                elif approval_config.get('sound', True) and approval_config.get('tts', True):
                    force_mode = 'mixed'

                # Send notification
                success = notifier.notify(message, context, force_mode=force_mode)
                if success:
                    results.append("🔔 Approval alert sent")
                else:
                    results.append("⚠ Approval alert failed")
            except Exception as e:
                results.append(f"⚠ Audio error: {str(e)}")
        else:
            # Fallback to system alert sound
            try:
                import subprocess
                subprocess.run(['afplay', '/System/Library/Sounds/Glass.aiff'],
                             capture_output=True, timeout=5)
                results.append("✓ System alert played (fallback)")
            except Exception:
                results.append("⚠ Audio system unavailable")

        return True, ' | '.join(results) if results else "Approval notification sent"


def main():
    """Main hook execution."""
    try:
        # Read hook input from stdin
        hook_input = {}
        try:
            hook_input = json.loads(sys.stdin.read())
        except Exception:
            pass

        # Get project directory
        project_dir = Path(os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd()))

        # Load config
        config = load_config(project_dir)

        # Send notification
        notifier = ApprovalNotifier(config)
        _, message = notifier.send_notification(hook_input)

        # Output result (optional system message)
        if message:
            print(json.dumps({"systemMessage": message, "suppressOutput": False}))

        sys.exit(0)

    except Exception as e:
        print(json.dumps({"systemMessage": f"⚠ Approval notification error: {str(e)}",
                         "suppressOutput": False}))
        sys.exit(0)


if __name__ == '__main__':
    main()
