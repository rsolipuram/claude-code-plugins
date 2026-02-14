#!/usr/bin/env python3
# /// script
# dependencies = []
# ///
"""
Async CLAUDE.md updater - invokes claude-md-manager skill in background.
Logs to .claude/async-logs/ for troubleshooting.
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def main():
    """Invoke claude-md-manager skill to handle CLAUDE.md."""

    # Read hook input from stdin
    try:
        stdin_content = sys.stdin.read().strip()
        hook_input = json.loads(stdin_content) if stdin_content else {}
    except (json.JSONDecodeError, ValueError):
        hook_input = {}

    # Get project directory
    project_dir = Path(os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd()))

    # Setup logging
    log_dir = project_dir / '.claude' / 'async-logs'
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    log_file = log_dir / f'claude-md-{timestamp}.log'

    # Extract context from hook input
    hook_event = hook_input.get('hook_event_name', 'unknown')
    transcript = hook_input.get('transcript', '')
    tool_calls = hook_input.get('tool_calls', [])

    # Use claude-md-manager skill with full session context
    prompt = f"""Use the /claude-md-manager skill to handle CLAUDE.md for this Stop hook event.

**Hook Context:**
- Event: {hook_event}
- Tool calls: {len(tool_calls)}
- Transcript length: {len(transcript)} chars

**Session Transcript:**
{transcript}

**Instructions:**
The claude-md-manager skill will automatically:
1. Detect if CLAUDE.md exists
2. Analyze the session for valuable learnings
3. Update CLAUDE.md if significant insights found
4. Follow quality criteria (80+/100 target)

Invoke the skill now.
"""

    try:
        # Log start with context info
        with open(log_file, 'w') as f:
            f.write(f"[{datetime.now()}] Starting async CLAUDE.md analysis\n")
            f.write(f"Project: {project_dir}\n")
            f.write(f"Hook event: {hook_event}\n")
            f.write(f"Transcript length: {len(transcript)} chars\n")
            f.write(f"Tool calls: {len(tool_calls)}\n")
            f.write(f"Using: /claude-md-manager skill\n")
            f.write("---\n")
            f.flush()

            # Launch claude with skill invocation
            result = subprocess.run(
                ['claude', '-p', '--plugin-dir', f'{project_dir}/plugins/dev-plugin', '--dangerously-skip-permissions'],
                input=prompt,
                text=True,
                stdout=f,
                stderr=subprocess.STDOUT,
                cwd=project_dir,
                timeout=300  # 5 minute timeout
            )

            # Log completion
            f.write("---\n")
            f.write(f"[{datetime.now()}] Async CLAUDE.md analysis complete\n")
            f.write(f"Exit code: {result.returncode}\n")

        # Exit with success
        sys.exit(0)

    except Exception as e:
        # Log error
        with open(log_file, 'a') as f:
            f.write(f"\n[ERROR] {str(e)}\n")
        sys.exit(1)


if __name__ == '__main__':
    main()
