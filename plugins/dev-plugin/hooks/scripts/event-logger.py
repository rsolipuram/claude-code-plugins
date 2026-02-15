#!/usr/bin/env python3
"""
Simple JSONL event logger for Claude Code hooks.
Logs all hook events to a timestamped JSONL file.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

def main():
    """Log hook event to JSONL file."""
    # Read hook input from stdin
    try:
        hook_input = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError):
        hook_input = {"error": "Failed to parse stdin"}

    # Get project directory
    project_dir = Path.cwd()

    # Create log directory
    log_dir = project_dir / '.claude' / 'observability' / 'hook-events'
    log_dir.mkdir(parents=True, exist_ok=True)

    # Log file: one per day
    today = datetime.now().strftime('%Y-%m-%d')
    log_file = log_dir / f'events-{today}.jsonl'

    # Create log entry
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'event': hook_input.get('hook_event_name', 'unknown'),
        'data': hook_input
    }

    # Append to JSONL file
    with log_file.open('a') as f:
        f.write(json.dumps(log_entry) + '\n')

    # Return success (don't suppress output)
    print(json.dumps({"success": True, "suppressOutput": True}))


if __name__ == '__main__':
    main()
