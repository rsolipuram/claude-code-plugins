#!/usr/bin/env python3
# /// script
# dependencies = [
#   "pyyaml",
# ]
# ///
"""
Completion notification hook for Claude Code.
Sends Mac notifications and text-to-speech when sessions complete.

Features:
- terminal-notifier support with 'sender' borrowing (true toast overlay)
- Native macOS notifications (via ctypes) 
- Bypass 'Script Editor' grouping and background suppression
- Optional 'True Overlay' via AppleScript Dialogs
"""

import json
import os
import subprocess
import sys
import random
import ctypes
import ctypes.util
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


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

    def sanitize_message(self, message: str) -> str:
        """Sanitize message for display."""
        if len(message) > 100:
            message = message[:100] + "..."
        return message.replace("\\", "").replace('"', "").replace("'", "")

    def send_mac_notification(self, message: str, title: str = "Claude Code") -> Tuple[bool, str]:
        """Send notification via terminal-notifier, native APIs, or AppleScript fallback."""
        try:
            safe_message = self.sanitize_message(message)
            timestamp = datetime.now().strftime("%H:%M:%S")
            notif_id = random.randint(1000, 9999)
            unique_title = f"{title} #{notif_id}"
            subtitle = f"Done at {timestamp}"

            # If 'force_dialog' is enabled in config, show a popup window
            notif_config = self.config.get('notifications', {})
            if notif_config.get('use_dialog', False):
                script = f'display dialog "{safe_message}" with title "{unique_title}" buttons {{"OK"}} default button "OK" with icon note giving up after 15'
                subprocess.run(['osascript', '-e', script], capture_output=True)
                return True, "Dialog displayed"

            # METHOD 1: terminal-notifier (Most reliable for 'Toast' if installed)
            # We borrow the ID of Claude Desktop or Terminal to ensure overlay permission.
            try:
                # Check for terminal-notifier
                tn_path = subprocess.check_output(['which', 'terminal-notifier']).decode().strip()
                if tn_path:
                    # Preferred sender ID: Claude Desktop
                    sender_id = "com.anthropic.claudefordesktop"
                    
                    # Fallback sender if Claude isn't installed: Terminal or VS Code
                    if not Path("/Applications/Claude.app").exists():
                        sender_id = os.environ.get('TERM_PROGRAM', 'com.apple.Terminal')
                        if sender_id == 'vscode':
                            sender_id = 'com.microsoft.VSCode'

                    subprocess.run([
                        tn_path,
                        "-title", title,
                        "-subtitle", subtitle,
                        "-message", safe_message,
                        "-sender", sender_id,
                        "-sound", "Glass"
                    ], capture_output=True)
                    return True, f"Notification sent via terminal-notifier ({sender_id})"
            except Exception:
                pass # Continue to native method

            # METHOD 2: Native Injection (via ctypes)
            try:
                objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library('objc'))
                objc.objc_getClass.restype = ctypes.c_void_p
                objc.sel_registerName.restype = ctypes.c_void_p
                objc.objc_msgSend.restype = ctypes.c_void_p
                objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

                def msg(obj, selector, *args):
                    s = objc.sel_registerName(selector.encode('ascii'))
                    return objc.objc_msgSend(obj, s, *args)

                def nsstring(s):
                    return msg(objc.objc_getClass('NSString'), 'stringWithUTF8String:', s.encode('utf8'))

                notif = msg(objc.objc_getClass('NSUserNotification'), 'alloc')
                notif = msg(notif, 'init')
                msg(notif, 'setTitle:', nsstring(unique_title))
                msg(notif, 'setSubtitle:', nsstring(subtitle))
                msg(notif, 'setInformativeText:', nsstring(safe_message))
                msg(notif, 'setSoundName:', nsstring('Hero'))

                center = msg(objc.objc_getClass('NSUserNotificationCenter'), 'defaultUserNotificationCenter')
                msg(center, 'deliverNotification:', notif)
                return True, "Native notification delivered"
            except Exception:
                pass

            # METHOD 3: tell application "Claude" trick (borrowing permissions via osascript)
            try:
                if Path("/Applications/Claude.app").exists():
                    script = f'tell application "Claude" to display notification "{safe_message}" with title "{title}" subtitle "{subtitle}"'
                    subprocess.run(['osascript', '-e', script], capture_output=True)
                    return True, "Notification sent via Claude app"
            except Exception:
                pass

            # METHOD 4: Final Fallback
            script = f'display notification "{safe_message}" with title "{unique_title}" subtitle "{subtitle}" sound name "Hero"'
            subprocess.run(['osascript', '-e', script], capture_output=True)
            return True, "Notification sent (fallback mode)"

        except Exception as e:
            return False, f"Error sending notification: {str(e)}"

    def speak_message(self, message: str) -> Tuple[bool, str]:
        """Speak message using macOS text-to-speech."""
        try:
            tts_message = message.split('.')[0]
            subprocess.run(['say', tts_message], capture_output=True, timeout=30)
            return True, "TTS completed"
        except Exception:
            return False, "TTS failed"

    def send_notifications(self) -> Tuple[bool, str]:
        """Send completion notifications based on configuration."""
        notif_config = self.config.get('notifications', {})

        if not notif_config.get('enabled', True):
            return True, "Notifications disabled"

        summary = self.get_session_summary()
        message = self.format_summary_message(summary)

        results = []

        if notif_config.get('mac_notification', True):
            success, msg = self.send_mac_notification(message)
            if success:
                results.append(f"✓ {msg}")
            else:
                results.append(f"⚠ Mac notification failed: {msg}")

        if notif_config.get('tts', False):
            self.speak_message(message)
            results.append("✓ TTS completed")

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

    return {'notifications': {'enabled': True, 'mac_notification': True, 'tts': False}}


def main():
    """Main hook execution."""
    try:
        project_dir = Path(os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd()))
        config = load_config(project_dir)
        notifier = CompletionNotifier(project_dir, config)
        _, message = notifier.send_notifications()

        if message:
            print(json.dumps({"systemMessage": message, "suppressOutput": False}))
        sys.exit(0)

    except Exception as e:
        print(json.dumps({"systemMessage": f"⚠ Notification error: {str(e)}", "suppressOutput": False}))
        sys.exit(0)


if __name__ == '__main__':
    main()
