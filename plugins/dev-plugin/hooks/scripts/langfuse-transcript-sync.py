#!/usr/bin/env python3
# /// script
# dependencies = [
#   "pyyaml",
#   "langfuse>=3.14.0",
# ]
# ///
"""
Sends Claude Code traces to Langfuse after each response.
Reads configuration from .claude/dev-plugin.local.md
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

# Import shared config loader
from config import load_config

# Check if Langfuse is available
try:
    from langfuse import Langfuse
except ImportError:
    print("Error: langfuse package not installed. Run: pip install langfuse", file=sys.stderr)
    sys.exit(0)


# ========================================
# LOGGING
# ========================================

class Logger:
    """Logger with configurable debug mode and log file."""

    def __init__(self, log_file: Path, debug_mode: bool = False):
        self.log_file = log_file
        self.debug_mode = debug_mode

    def log(self, level: str, message: str) -> None:
        """Log a message to the log file."""
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.log_file, "a") as f:
            f.write(f"{timestamp} [{level}] {message}\n")

    def debug(self, message: str) -> None:
        """Log a debug message (only if debug mode is enabled)."""
        if self.debug_mode:
            self.log("DEBUG", message)


# ========================================
# STATE MANAGEMENT
# ========================================

def load_state(state_file: Path) -> dict:
    """Load the state file containing session tracking info."""
    if not state_file.exists():
        return {}
    try:
        return json.loads(state_file.read_text())
    except (json.JSONDecodeError, IOError):
        return {}


def save_state(state_file: Path, state: dict) -> None:
    """Save the state file."""
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(state, indent=2))


# ========================================
# MESSAGE PARSING
# ========================================

def get_content(msg: dict) -> Any:
    """Extract content from a message."""
    if isinstance(msg, dict):
        if "message" in msg:
            return msg["message"].get("content")
        return msg.get("content")
    return None


def is_tool_result(msg: dict) -> bool:
    """Check if a message contains tool results."""
    content = get_content(msg)
    if isinstance(content, list):
        return any(
            isinstance(item, dict) and item.get("type") == "tool_result"
            for item in content
        )
    return False


def get_tool_calls(msg: dict) -> list:
    """Extract tool use blocks from a message."""
    content = get_content(msg)
    if isinstance(content, list):
        return [
            item for item in content
            if isinstance(item, dict) and item.get("type") == "tool_use"
        ]
    return []


def get_text_content(msg: dict) -> str:
    """Extract text content from a message."""
    content = get_content(msg)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(item.get("text", ""))
            elif isinstance(item, str):
                text_parts.append(item)
        return "\n".join(text_parts)
    return ""


def merge_assistant_parts(parts: list) -> dict:
    """Merge multiple assistant message parts into one."""
    if not parts:
        return {}

    merged_content = []
    for part in parts:
        content = get_content(part)
        if isinstance(content, list):
            merged_content.extend(content)
        elif content:
            merged_content.append({"type": "text", "text": str(content)})

    # Use the structure from the first part
    result = parts[0].copy()
    if "message" in result:
        result["message"] = result["message"].copy()
        result["message"]["content"] = merged_content
    else:
        result["content"] = merged_content

    return result


# ========================================
# TRANSCRIPT MANAGEMENT
# ========================================

def find_latest_transcript(logger: Logger) -> tuple[str, Path] | None:
    """Find the most recently modified transcript file.

    Claude Code stores transcripts as *.jsonl files directly in the project directory.
    Main conversation files have UUID names, agent files have agent-*.jsonl names.
    The session ID is stored inside each JSON line.
    """
    projects_dir = Path.home() / ".claude" / "projects"

    if not projects_dir.exists():
        logger.debug(f"Projects directory not found: {projects_dir}")
        return None

    latest_file = None
    latest_mtime = 0

    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue

        # Look for all .jsonl files directly in the project directory
        for transcript_file in project_dir.glob("*.jsonl"):
            mtime = transcript_file.stat().st_mtime
            if mtime > latest_mtime:
                latest_mtime = mtime
                latest_file = transcript_file

    if latest_file:
        # Extract session ID from the first line of the file
        try:
            first_line = latest_file.read_text().split("\n")[0]
            first_msg = json.loads(first_line)
            session_id = first_msg.get("sessionId", latest_file.stem)
            logger.debug(f"Found transcript: {latest_file}, session: {session_id}")
            return (session_id, latest_file)
        except (json.JSONDecodeError, IOError, IndexError) as e:
            logger.debug(f"Error reading transcript {latest_file}: {e}")
            return None

    logger.debug("No transcript files found")
    return None


def find_subagent_transcripts(
    session_transcript_path: Path,
    logger: Logger
) -> list[tuple[str, Path]]:
    """Find all subagent transcript files for a session.

    Returns list of (agent_id, transcript_path) tuples.
    """
    session_dir = session_transcript_path.parent
    session_id = session_transcript_path.stem
    subagents_dir = session_dir / session_id / "subagents"

    if not subagents_dir.exists():
        logger.debug(f"No subagents directory found: {subagents_dir}")
        return []

    subagent_files = []
    for transcript_file in subagents_dir.glob("agent-*.jsonl"):
        # Extract agent ID from filename: agent-a093c2c.jsonl -> a093c2c
        agent_id = transcript_file.stem.replace("agent-", "")
        subagent_files.append((agent_id, transcript_file))
        logger.debug(f"Found subagent: {agent_id} at {transcript_file}")

    logger.debug(f"Found {len(subagent_files)} subagent transcript(s)")
    return subagent_files


# ========================================
# LANGFUSE TRACING
# ========================================

def create_trace(
    langfuse: Langfuse,
    session_id: str,
    turn_num: int,
    user_msg: dict,
    assistant_msgs: list,
    tool_results: list,
    subagent_data: dict,
    logger: Logger,
) -> None:
    """Create a Langfuse trace for a single turn with subagent support."""
    # Extract user text
    user_text = get_text_content(user_msg)

    # Extract final assistant text
    final_output = ""
    if assistant_msgs:
        final_output = get_text_content(assistant_msgs[-1])

    # Get model info from first assistant message
    model = "claude"
    if assistant_msgs and isinstance(assistant_msgs[0], dict) and "message" in assistant_msgs[0]:
        model = assistant_msgs[0]["message"].get("model", "claude")

    # Get session ID short form (first 8 chars)
    session_id_short = session_id[:8]

    # Collect all tool calls and results
    all_tool_calls = []
    for assistant_msg in assistant_msgs:
        tool_calls = get_tool_calls(assistant_msg)
        for tool_call in tool_calls:
            tool_name = tool_call.get("name", "unknown")
            tool_input = tool_call.get("input", {})
            tool_id = tool_call.get("id", "")

            # Find matching tool result
            tool_output = None
            for tr in tool_results:
                tr_content = get_content(tr)
                if isinstance(tr_content, list):
                    for item in tr_content:
                        if isinstance(item, dict) and item.get("tool_use_id") == tool_id:
                            tool_output = item.get("content")
                            break

            all_tool_calls.append({
                "name": tool_name,
                "input": tool_input,
                "output": tool_output,
                "id": tool_id,
            })

    # Create trace using the latest Langfuse SDK API (v3+)
    # Session ID is included in metadata for grouping
    with langfuse.start_as_current_span(
        name=f"{session_id_short} - Turn {turn_num}",
        input={"role": "user", "content": user_text},
        metadata={
            "source": "claude-code",
            "turn_number": turn_num,
            "session_id": session_id,
            "session_id_short": session_id_short,
        },
    ) as trace_span:
            # Create generation for the LLM response
            langfuse.start_observation(
                name="Claude Response",
                as_type="generation",
                input={"role": "user", "content": user_text},
                output={"role": "assistant", "content": final_output},
                model=model,
                metadata={
                    "tool_count": len(all_tool_calls),
                },
            )

            # Create spans for tool calls
            for tool_call in all_tool_calls:
                with langfuse.start_as_current_span(
                    name=f"Tool: {tool_call['name']}",
                    input=tool_call["input"],
                    metadata={
                        "tool_name": tool_call["name"],
                        "tool_id": tool_call["id"],
                    },
                ) as tool_span:
                    # Check if this is a Task tool with subagent data
                    if tool_call["name"] == "Task" and tool_call["id"] in subagent_data:
                        agent_id, subagent_tools = subagent_data[tool_call["id"]]
                        logger.debug(f"Adding {len(subagent_tools)} subagent tool calls for agent {agent_id}")

                        # Create subagent container span
                        with langfuse.start_as_current_span(
                            name=f"Subagent: {agent_id}",
                            metadata={"agent_id": agent_id},
                        ):
                            # Create spans for each subagent tool call
                            for subtool in subagent_tools:
                                with langfuse.start_as_current_span(
                                    name=f"Tool: {subtool['name']}",
                                    input=subtool["input"],
                                    metadata={"tool_id": subtool["id"]},
                                ) as subtool_span:
                                    subtool_span.update(output=subtool["output"])

                    # Update main tool span
                    tool_span.update(output=tool_call["output"])
                logger.debug(f"Created span for tool: {tool_call['name']}")

            # Update trace with output
            trace_span.update(output={"role": "assistant", "content": final_output})

    logger.debug(f"Created trace for turn {turn_num}")


def process_transcript(
    langfuse: Langfuse,
    session_id: str,
    transcript_file: Path,
    state: dict,
    state_file: Path,
    subagent_data: dict,
    logger: Logger,
) -> int:
    """Process a transcript file and create traces for new turns."""
    # Get previous state for this session
    session_state = state.get(session_id, {})
    last_line = session_state.get("last_line", 0)
    turn_count = session_state.get("turn_count", 0)

    # Read transcript
    lines = transcript_file.read_text().strip().split("\n")
    total_lines = len(lines)

    if last_line >= total_lines:
        logger.debug(f"No new lines to process (last: {last_line}, total: {total_lines})")
        return 0

    # Parse new messages
    new_messages = []
    for i in range(last_line, total_lines):
        try:
            msg = json.loads(lines[i])
            new_messages.append(msg)
        except json.JSONDecodeError:
            continue

    if not new_messages:
        return 0

    logger.debug(f"Processing {len(new_messages)} new messages")

    # Build mapping of tool_id -> (agent_id, tool_calls) for Task tools
    subagent_tools_map = {}

    # Group messages into turns (user -> assistant(s) -> tool_results)
    turns = 0
    current_user = None
    current_assistants = []
    current_assistant_parts = []
    current_msg_id = None
    current_tool_results = []

    for msg in new_messages:
        role = msg.get("type") or (msg.get("message", {}).get("role"))

        if role == "user":
            # Check if this is a tool result
            if is_tool_result(msg):
                current_tool_results.append(msg)

                # Extract agent IDs from Task tool results
                # agentId is in toolUseResult field (if it's a dict), not in content
                tool_use_result = msg.get("toolUseResult")
                if isinstance(tool_use_result, dict):
                    agent_id = tool_use_result.get("agentId")

                    if agent_id and agent_id in subagent_data:
                        # Find the tool_use_id from the content
                        content = get_content(msg)
                        if isinstance(content, list):
                            for item in content:
                                if isinstance(item, dict) and item.get("type") == "tool_result":
                                    tool_id = item.get("tool_use_id")
                                    if tool_id:
                                        # Map tool_id -> (agent_id, tool_calls)
                                        subagent_tools_map[tool_id] = (agent_id, subagent_data[agent_id])
                                        logger.debug(f"Linked Task tool {tool_id} to subagent {agent_id}")

                continue

            # New user message - finalize previous turn
            if current_msg_id and current_assistant_parts:
                merged = merge_assistant_parts(current_assistant_parts)
                current_assistants.append(merged)
                current_assistant_parts = []
                current_msg_id = None

            if current_user and current_assistants:
                turns += 1
                turn_num = turn_count + turns
                create_trace(langfuse, session_id, turn_num, current_user, current_assistants, current_tool_results, subagent_tools_map, logger)

            # Start new turn
            current_user = msg
            current_assistants = []
            current_assistant_parts = []
            current_msg_id = None
            current_tool_results = []

        elif role == "assistant":
            msg_id = None
            if isinstance(msg, dict) and "message" in msg:
                msg_id = msg["message"].get("id")

            if not msg_id:
                # No message ID, treat as continuation
                current_assistant_parts.append(msg)
            elif msg_id == current_msg_id:
                # Same message ID, add to current parts
                current_assistant_parts.append(msg)
            else:
                # New message ID - finalize previous message
                if current_msg_id and current_assistant_parts:
                    merged = merge_assistant_parts(current_assistant_parts)
                    current_assistants.append(merged)

                # Start new assistant message
                current_msg_id = msg_id
                current_assistant_parts = [msg]

    # Process final turn
    if current_msg_id and current_assistant_parts:
        merged = merge_assistant_parts(current_assistant_parts)
        current_assistants.append(merged)

    if current_user and current_assistants:
        turns += 1
        turn_num = turn_count + turns
        create_trace(langfuse, session_id, turn_num, current_user, current_assistants, current_tool_results, subagent_tools_map, logger)

    # Update state
    state[session_id] = {
        "last_line": total_lines,
        "turn_count": turn_count + turns,
        "updated": datetime.now(timezone.utc).isoformat(),
    }
    save_state(state_file, state)

    return turns


def process_subagent_transcript(
    langfuse: Langfuse,
    session_id: str,
    agent_id: str,
    transcript_file: Path,
    state: dict,
    state_file: Path,
    logger: Logger,
) -> list[dict]:
    """Process a subagent transcript and return tool calls for nesting.

    Returns list of tool call dicts with {name, input, output, timestamp, id}.
    """
    # State key for this subagent
    state_key = f"{session_id}/agent-{agent_id}"

    # Get previous state
    subagent_state = state.get(state_key, {})
    last_line = subagent_state.get("last_line", 0)

    # Read transcript
    lines = transcript_file.read_text().strip().split("\n")
    total_lines = len(lines)

    if last_line >= total_lines:
        logger.debug(f"No new lines in subagent {agent_id}")
        return []

    # Parse new messages
    new_messages = []
    for i in range(last_line, total_lines):
        try:
            msg = json.loads(lines[i])
            new_messages.append(msg)
        except json.JSONDecodeError:
            logger.debug(f"Skipping invalid JSON at line {i} in subagent {agent_id}")
            continue

    if not new_messages:
        logger.debug(f"No valid messages in subagent {agent_id}")
        return []

    # Extract tool calls and results
    tool_calls = []
    pending_tools = {}  # tool_id -> tool_call

    for msg in new_messages:
        role = msg.get("type") or (msg.get("message", {}).get("role"))

        if role == "assistant":
            # Extract tool uses
            for tool_use in get_tool_calls(msg):
                tool_id = tool_use.get("id")
                pending_tools[tool_id] = {
                    "name": tool_use.get("name"),
                    "input": tool_use.get("input"),
                    "output": None,
                    "id": tool_id,
                    "timestamp": msg.get("timestamp"),
                }

        elif role == "user" and is_tool_result(msg):
            # Match tool result to pending tool
            content = get_content(msg)
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "tool_result":
                        tool_id = item.get("tool_use_id")
                        if tool_id in pending_tools:
                            pending_tools[tool_id]["output"] = item.get("content")
                            tool_calls.append(pending_tools[tool_id])
                            del pending_tools[tool_id]

    # Add any unmatched tools (no result yet)
    tool_calls.extend(pending_tools.values())

    # Update state
    state[state_key] = {
        "last_line": total_lines,
        "tool_count": len(tool_calls),
        "updated": datetime.now(timezone.utc).isoformat(),
    }
    save_state(state_file, state)

    logger.debug(f"Processed subagent {agent_id}: {len(tool_calls)} tool calls")
    return tool_calls


# ========================================
# MAIN ENTRY POINT
# ========================================

def main():
    """Main hook execution."""
    script_start = datetime.now()

    # Get project directory
    project_dir = Path(os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd()))

    # Load configuration
    config = load_config(project_dir)
    obs_config = config.get('observability', {})
    langfuse_config = obs_config.get('langfuse', {})

    # Initialize logger
    debug_mode = obs_config.get('debug', False)
    log_file = project_dir / '.claude' / 'observability' / 'langfuse-transcript-sync.log'
    logger = Logger(log_file, debug_mode)

    logger.debug("Hook started")

    # Check if tracing is enabled
    if not langfuse_config.get('enabled', False):
        logger.debug("Langfuse tracing disabled in config")
        sys.exit(0)

    # Get Langfuse credentials from config (with fallback to env vars)
    public_key = (
        langfuse_config.get('public_key') or
        os.environ.get("CC_LANGFUSE_PUBLIC_KEY") or
        os.environ.get("LANGFUSE_PUBLIC_KEY")
    )
    secret_key = (
        langfuse_config.get('secret_key') or
        os.environ.get("CC_LANGFUSE_SECRET_KEY") or
        os.environ.get("LANGFUSE_SECRET_KEY")
    )
    host = (
        langfuse_config.get('host') or
        os.environ.get("CC_LANGFUSE_HOST") or
        os.environ.get("LANGFUSE_HOST") or
        "https://cloud.langfuse.com"
    )

    if not public_key or not secret_key:
        logger.log("ERROR", "Langfuse API keys not configured (check .claude/dev-plugin.local.md)")
        sys.exit(0)

    # Initialize Langfuse client
    try:
        langfuse = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
        )
        logger.debug(f"Connected to Langfuse at {host}")
    except Exception as e:
        logger.log("ERROR", f"Failed to initialize Langfuse client: {e}")
        sys.exit(0)

    # State file location
    state_file = project_dir / '.claude' / 'observability' / 'langfuse_state.json'

    # Load state
    state = load_state(state_file)

    # Find the most recently modified transcript
    result = find_latest_transcript(logger)
    if not result:
        logger.debug("No transcript file found")
        sys.exit(0)

    session_id, transcript_file = result

    if not transcript_file:
        logger.debug("No transcript file found")
        sys.exit(0)

    logger.debug(f"Processing session: {session_id}")

    # Find and process subagent transcripts
    subagent_files = find_subagent_transcripts(transcript_file, logger)
    logger.debug(f"Found {len(subagent_files)} subagent transcript(s)")

    # Process subagent transcripts
    subagent_data = {}  # agent_id -> [tool_calls]
    for agent_id, subagent_file in subagent_files:
        tool_calls = process_subagent_transcript(
            langfuse, session_id, agent_id, subagent_file, state, state_file, logger
        )
        # Store tool calls indexed by agent_id
        subagent_data[agent_id] = tool_calls
        logger.debug(f"Subagent {agent_id}: {len(tool_calls)} tool calls")

    # Process the main transcript (with subagent data)
    try:
        turns = process_transcript(langfuse, session_id, transcript_file, state, state_file, subagent_data, logger)

        # Flush to ensure all data is sent
        langfuse.flush()

        # Log execution time
        duration = (datetime.now() - script_start).total_seconds()
        logger.log("INFO", f"Processed {turns} turns in {duration:.1f}s")

        if duration > 180:
            logger.log("WARN", f"Hook took {duration:.1f}s (>3min), consider optimizing")

    except Exception as e:
        logger.log("ERROR", f"Failed to process transcript: {e}")
        import traceback
        logger.debug(traceback.format_exc())
    finally:
        langfuse.shutdown()

    sys.exit(0)


if __name__ == "__main__":
    main()
