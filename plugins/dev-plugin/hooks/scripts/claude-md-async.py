#!/usr/bin/env python3
# /// script
# dependencies = []
# ///
"""
Async CLAUDE.md updater - invokes claude-md-manager skill in background.
Logs to .claude/async-logs/ for troubleshooting.

NOTE: Async hooks don't receive stdin input, so this script finds the
transcript file from the filesystem instead.
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def find_latest_transcript() -> tuple[str, Path] | None:
    """Find the most recently modified transcript file.

    Claude Code stores transcripts as *.jsonl files in ~/.claude/projects/.
    Returns (session_id, transcript_path) or None.
    """
    projects_dir = Path.home() / ".claude" / "projects"

    if not projects_dir.exists():
        return None

    latest_file = None
    latest_mtime = 0

    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue

        # Look for all .jsonl files (main transcripts, not agent-*.jsonl)
        for transcript_file in project_dir.glob("*.jsonl"):
            # Skip subagent transcripts
            if transcript_file.name.startswith("agent-"):
                continue

            mtime = transcript_file.stat().st_mtime
            if mtime > latest_mtime:
                latest_mtime = mtime
                latest_file = transcript_file

    if latest_file:
        # Extract session ID from the first line
        try:
            first_line = latest_file.read_text().split("\n")[0]
            first_msg = json.loads(first_line)
            session_id = first_msg.get("sessionId", latest_file.stem)
            return (session_id, latest_file)
        except (json.JSONDecodeError, IOError, IndexError):
            return None

    return None


def parse_transcript(transcript_path: Path) -> dict:
    """Parse transcript file and extract session data.

    Returns dict with:
    - messages: list of messages
    - tool_calls: list of tool calls
    - user_messages: count of user messages
    - assistant_messages: count of assistant messages
    """
    messages = []
    tool_calls = []
    user_count = 0
    assistant_count = 0

    try:
        content = transcript_path.read_text()
        for line in content.strip().split("\n"):
            if not line:
                continue

            try:
                msg = json.loads(line)
                messages.append(msg)

                # Count message types
                role = msg.get("message", {}).get("role")
                if role == "user":
                    user_count += 1
                elif role == "assistant":
                    assistant_count += 1

                # Extract tool calls
                msg_content = msg.get("message", {}).get("content", [])
                if isinstance(msg_content, list):
                    for item in msg_content:
                        if isinstance(item, dict) and item.get("type") == "tool_use":
                            tool_calls.append({
                                "name": item.get("name"),
                                "id": item.get("id"),
                            })
            except json.JSONDecodeError:
                continue
    except IOError:
        pass

    return {
        "messages": messages,
        "tool_calls": tool_calls,
        "user_messages": user_count,
        "assistant_messages": assistant_count,
    }


def build_transcript_summary(session_data: dict) -> str:
    """Build a summary of the session for the claude-md-manager skill."""
    messages = session_data["messages"]
    tool_calls = session_data["tool_calls"]

    # Build a simplified transcript with key messages
    summary_lines = []

    for msg in messages:
        role = msg.get("message", {}).get("role")
        content = msg.get("message", {}).get("content", [])

        if role == "user":
            # Extract user text
            text_parts = []
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
            user_text = "\n".join(text_parts)
            if user_text.strip():
                summary_lines.append(f"USER: {user_text[:500]}")  # Limit length

        elif role == "assistant":
            # Extract assistant text (skip tool results)
            text_parts = []
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
            assistant_text = "\n".join(text_parts)
            if assistant_text.strip():
                summary_lines.append(f"ASSISTANT: {assistant_text[:500]}")  # Limit length

    return "\n\n".join(summary_lines)


def main():
    """Invoke claude-md-manager skill to handle CLAUDE.md."""

    # Get project directory
    project_dir = Path(os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd()))

    # Setup logging
    log_dir = project_dir / '.claude' / 'async-logs'
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    log_file = log_dir / f'claude-md-{timestamp}.log'

    try:
        # Find the latest transcript
        result = find_latest_transcript()
        if not result:
            with open(log_file, 'w') as f:
                f.write(f"[{datetime.now()}] No transcript file found\n")
            sys.exit(0)

        session_id, transcript_path = result

        # Parse transcript
        session_data = parse_transcript(transcript_path)
        transcript_summary = build_transcript_summary(session_data)

        # Build prompt for claude-md-manager skill
        prompt = f"""Use the /claude-md-manager skill to handle CLAUDE.md for this Stop hook event.

**Session Context:**
- Session ID: {session_id}
- User messages: {session_data['user_messages']}
- Assistant messages: {session_data['assistant_messages']}
- Tool calls: {len(session_data['tool_calls'])}
- Tools used: {', '.join(set(tc['name'] for tc in session_data['tool_calls'][:10]))}

**Session Summary:**
{transcript_summary[:2000]}

**Instructions:**
The claude-md-manager skill will automatically:
1. Detect if CLAUDE.md exists
2. Analyze the session for valuable learnings
3. Update CLAUDE.md if significant insights found
4. Follow quality criteria (80+/100 target)

Invoke the skill now.
"""

        # Log start with context info
        with open(log_file, 'w') as f:
            f.write(f"[{datetime.now()}] Starting async CLAUDE.md analysis\n")
            f.write(f"Project: {project_dir}\n")
            f.write(f"Session: {session_id}\n")
            f.write(f"Transcript: {transcript_path}\n")
            f.write(f"User messages: {session_data['user_messages']}\n")
            f.write(f"Assistant messages: {session_data['assistant_messages']}\n")
            f.write(f"Tool calls: {len(session_data['tool_calls'])}\n")
            f.write(f"Using: /claude-md-manager skill\n")
            f.write("---\n")
            f.flush()

            # Launch claude with skill invocation
            result = subprocess.run(
                ['claude', '--plugin-dir', f'{project_dir}/plugins/dev-plugin', '--dangerously-skip-permissions'],
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
