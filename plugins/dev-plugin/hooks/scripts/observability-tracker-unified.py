#!/usr/bin/env python3
# /// script
# dependencies = [
#   "pyyaml",
#   "langfuse==2.60.10",
# ]
# ///
"""
Real-time Observability Tracker for Claude Code sessions.
Sends events to Langfuse immediately as they happen.

Features:
- Auto-setup Langfuse environment (async)
- Real-time event tracking to Langfuse
- Optional debug logging
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
    """Real-time observability tracker with Langfuse management."""

    def __init__(self, project_dir: Path, config: Dict):
        self.project_dir = project_dir
        self.config = config
        self.obs_config = config.get('observability', {})
        self.langfuse_config = self.obs_config.get('langfuse', {})
        self.langfuse_client = None
        self.session_id = None
        self.debug_mode = self.obs_config.get('debug', False)

        # NEW: State tracking for in-flight operations
        self.active_spans = {}  # tool_use_id -> span object
        self.subagent_traces = {}  # agent_id -> trace object

        # NEW: Session metrics aggregation
        self.session_metrics = {
            'tool_count': 0,
            'tool_errors': 0,
            'tool_successes': 0,
            'tools_by_name': {},
            'subagent_count': 0,
            'prompt_count': 0,
            'session_start_time': None,
            'first_tool_time': None,
            'last_tool_time': None
        }

    # ========================================
    # SESSION START: Quick Check + Async Setup
    # ========================================

    def handle_session_start(self, hook_input: Dict) -> Dict:
        """Initialize session tracking and create Langfuse trace."""
        self._debug_log('SessionStart', hook_input)

        # Get session ID
        self.session_id = hook_input.get('session_id', self._generate_session_id())

        # Initialize session start time
        self.session_metrics['session_start_time'] = datetime.now()

        # Quick Langfuse health check
        if self.langfuse_config.get('enabled', False):
            if self._is_langfuse_healthy():
                self._connect_langfuse()
                if self.langfuse_client:
                    # Create trace immediately
                    trace = self._get_trace()
                    if trace:
                        # Ensure data is flushed
                        self.langfuse_client.flush()
                        return {
                            "systemMessage": f"📊 Session tracking: {self.session_id[:8]} (Langfuse ready)",
                            "suppressOutput": False
                        }
            else:
                # Spawn async setup if auto_setup enabled
                if self.langfuse_config.get('auto_setup', False):
                    self._spawn_async_setup()
                    return {
                        "systemMessage": f"📊 Session tracking: {self.session_id[:8]} (Langfuse setup running in background)",
                        "suppressOutput": False
                    }
                elif self.langfuse_config.get('auto_start', False):
                    # Just try to start if already installed
                    self._try_start_langfuse()
                    return {
                        "systemMessage": f"📊 Session tracking: {self.session_id[:8]} (Langfuse starting)",
                        "suppressOutput": False
                    }

        return {
            "systemMessage": f"📊 Session tracking: {self.session_id[:8]} (local mode)",
            "suppressOutput": False
        }

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
        if self.langfuse_client:
            return

        try:
            import langfuse
            
            # Extract keys
            pk = self.langfuse_config.get('public_key') or os.environ.get('LANGFUSE_PUBLIC_KEY')
            sk = self.langfuse_config.get('secret_key') or os.environ.get('LANGFUSE_SECRET_KEY')
            host = self.langfuse_config.get('host') or os.environ.get('LANGFUSE_HOST', 'http://localhost:3000')

            if not pk or not sk:
                self._debug_log('ConnectSkip', {'reason': 'Missing keys'})
                return

            # Initialize client explicitly
            self.langfuse_client = langfuse.Langfuse(
                public_key=pk,
                secret_key=sk,
                host=host
            )
                
        except ImportError as e:
            self._debug_log('ConnectError', {'error': f'langfuse module not found: {str(e)}'})
            self.langfuse_client = None
        except Exception as e:
            self._debug_log('ConnectError', {'error': str(e)})
            self.langfuse_client = None

    def _get_trace(self):
        """Get or create trace for current session."""
        if not self.langfuse_client or not self.session_id:
            return None

        try:
            # Check for trace method
            trace_func = getattr(self.langfuse_client, 'trace', None)
            if callable(trace_func):
                return trace_func(
                    id=self.session_id,
                    name="claude-code-session",
                    user_id=self.langfuse_config.get('userId'),
                    session_id=self.session_id,
                    version=self.langfuse_config.get('version'),
                    tags=self.langfuse_config.get('tags'),
                    metadata={
                        'project': self.project_dir.name,
                        'project_dir': str(self.project_dir)
                    }
                )
            
            # Fallback
            self._debug_log('TraceFallback', {'reason': 'trace() method not found or not callable'})
            return None
            
        except Exception as e:
            self._debug_log('TraceGetError', {'error': str(e)})
            return None

    def _spawn_async_setup(self) -> None:
        """Spawn background Langfuse setup process (non-blocking)."""
        setup_script = Path(__file__).parent / 'langfuse-setup.py'
        if setup_script.exists():
            subprocess.Popen(
                ['uv', 'run', '--quiet', str(setup_script)],
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

    def handle_pre_tool_use(self, hook_input: Dict) -> Dict:
        """Start a span for tool execution (PreToolUse)."""
        self._debug_log('PreToolUse', hook_input)

        self.session_id = hook_input.get('session_id')
        if not self.session_id:
            return {"success": True, "suppressOutput": True}

        # Extract correlation ID
        tool_use_id = hook_input.get('tool_use_id')
        if not tool_use_id:
            self._debug_log('PreToolUseMissingID', {'warning': 'No tool_use_id'})
            return {"success": True, "suppressOutput": True}

        self._connect_langfuse()
        trace = self._get_trace()

        # Extract tool info
        tool_name = hook_input.get('tool_name', 'Unknown')
        tool_input_data = hook_input.get('tool_input', {})

        # Update metrics
        self.session_metrics['tool_count'] += 1
        self.session_metrics['tools_by_name'][tool_name] = \
            self.session_metrics['tools_by_name'].get(tool_name, 0) + 1

        if not self.session_metrics['first_tool_time']:
            self.session_metrics['first_tool_time'] = datetime.now()

        # Create and START span
        if trace:
            try:
                # Check if span() method exists (SDK compatibility)
                span_func = getattr(trace, 'span', None)
                if not callable(span_func):
                    self._debug_log('SpanNotSupported', {'fallback': 'using events'})
                    # Fallback to old event-based approach
                    trace.event(
                        name=f"pretool_{tool_name}",
                        start_time=datetime.now(),
                        input=tool_input_data,
                        metadata={'event': 'PreToolUse', 'tool': tool_name, 'tool_use_id': tool_use_id}
                    )
                    self.langfuse_client.flush()
                    return {"success": True, "suppressOutput": True}

                span = trace.span(
                    name=f"tool_{tool_name}",
                    input=tool_input_data,
                    metadata={
                        'event': 'ToolExecution',
                        'tool': tool_name,
                        'tool_use_id': tool_use_id,
                        'cwd': hook_input.get('cwd'),
                        'permission_mode': hook_input.get('permission_mode')
                    }
                )

                # Store for correlation in PostToolUse
                self.active_spans[tool_use_id] = span

                self.langfuse_client.flush()
                self._debug_log('SpanStarted', {'tool_use_id': tool_use_id, 'tool': tool_name})
            except Exception as e:
                self._debug_log('PreToolSpanError', {'error': str(e)})

        return {"success": True, "suppressOutput": True}

    def handle_tool_use(self, hook_input: Dict) -> Dict:
        """Complete the span started in PreToolUse (PostToolUse)."""
        self._debug_log('PostToolUse', hook_input)

        self.session_id = hook_input.get('session_id')
        if not self.session_id:
            return {"success": True, "suppressOutput": True}

        # Extract correlation ID
        tool_use_id = hook_input.get('tool_use_id')
        if not tool_use_id:
            self._debug_log('PostToolUseMissingID', {'warning': 'No tool_use_id'})
            return {"success": True, "suppressOutput": True}

        self._connect_langfuse()

        # Retrieve the span started in PreToolUse
        span = self.active_spans.get(tool_use_id)

        # Extract tool info
        tool_name = hook_input.get('tool_name', 'Unknown')
        tool_result = (
            hook_input.get('tool_response') or
            hook_input.get('tool_result') or
            hook_input.get('result') or
            hook_input.get('output') or
            {}
        )

        # Determine success/failure
        is_error = isinstance(tool_result, dict) and tool_result.get('error')
        if is_error:
            self.session_metrics['tool_errors'] += 1
        else:
            self.session_metrics['tool_successes'] += 1

        self.session_metrics['last_tool_time'] = datetime.now()

        # Update and END the span
        if span:
            try:
                span.end(
                    output=tool_result if tool_result else None,
                    metadata={
                        'success': not is_error,
                        'tool': tool_name
                    },
                    level='ERROR' if is_error else 'DEFAULT',
                    status_message=str(tool_result.get('error')) if is_error else None
                )

                # Remove from active spans
                del self.active_spans[tool_use_id]

                self.langfuse_client.flush()
                self._debug_log('SpanEnded', {'tool_use_id': tool_use_id, 'tool': tool_name, 'success': not is_error})
            except Exception as e:
                self._debug_log('PostToolSpanError', {'error': str(e)})
        else:
            # Span not found - possibly missed PreToolUse or orphaned PostToolUse
            self._debug_log('OrphanedPostToolUse', {
                'tool_use_id': tool_use_id,
                'tool_name': tool_name,
                'warning': 'No matching PreToolUse span found'
            })

        return {"success": True, "suppressOutput": True}

    # ========================================
    # PROMPT TRACKING
    # ========================================

    def handle_prompt(self, hook_input: Dict) -> Dict:
        """Track user prompt submission and send to Langfuse immediately."""
        self._debug_log('UserPromptSubmit', hook_input)

        # Get session ID and connect
        self.session_id = hook_input.get('session_id')
        if not self.session_id:
            return {"success": True, "suppressOutput": True}

        # Update metrics
        self.session_metrics['prompt_count'] += 1

        self._connect_langfuse()
        trace = self._get_trace()

        # Extract prompt content
        prompt_content = (
            hook_input.get('user_message') or
            hook_input.get('prompt') or
            hook_input.get('content') or
            hook_input.get('message') or
            hook_input.get('text') or
            ''
        )

        # Send to Langfuse immediately
        if trace:
            try:
                trace.event(
                    name="user_prompt_submit",
                    start_time=datetime.now(),
                    input=prompt_content,
                    metadata={
                        'event': 'UserPromptSubmit',
                        'prompt_length': len(prompt_content)
                    }
                )
                self.langfuse_client.flush()
            except Exception as e:
                self._debug_log('EventCreationError', {'error': str(e)})

        return {"success": True, "suppressOutput": True}

    # ========================================
    # SESSION FINALIZATION
    # ========================================

    def handle_subagent_start(self, hook_input: Dict) -> Dict:
        """Create a new child trace for subagent execution."""
        self._debug_log('SubagentStart', hook_input)

        self.session_id = hook_input.get('session_id')
        if not self.session_id:
            return {"success": True, "suppressOutput": True}

        self._connect_langfuse()
        parent_trace = self._get_trace()

        # Extract agent info
        agent_type = hook_input.get('agent_type', 'Unknown')
        agent_id = hook_input.get('agent_id')
        prompt = hook_input.get('prompt', '')

        self.session_metrics['subagent_count'] += 1

        # Create a NEW trace for the subagent, linked to parent
        if parent_trace and agent_id and self.langfuse_client:
            try:
                # Create child trace
                subagent_trace = self.langfuse_client.trace(
                    id=agent_id,
                    name=f"subagent_{agent_type}",
                    session_id=self.session_id,
                    metadata={
                        'event': 'SubagentExecution',
                        'agent_type': agent_type,
                        'agent_id': agent_id,
                        'parent_session_id': self.session_id,
                        'parent_trace_id': parent_trace.id if hasattr(parent_trace, 'id') else None
                    },
                    input=prompt
                )

                # Store for SubagentStop
                self.subagent_traces[agent_id] = subagent_trace

                self.langfuse_client.flush()
                self._debug_log('SubagentTraceCreated', {'agent_id': agent_id, 'agent_type': agent_type})
            except Exception as e:
                self._debug_log('SubagentStartError', {'error': str(e)})

        return {"success": True, "suppressOutput": True}

    def handle_subagent_stop(self, hook_input: Dict) -> Dict:
        """Complete the subagent trace started in SubagentStart."""
        self._debug_log('SubagentStop', hook_input)

        self.session_id = hook_input.get('session_id')
        if not self.session_id:
            return {"success": True, "suppressOutput": True}

        self._connect_langfuse()

        # Extract agent info
        agent_id = hook_input.get('agent_id')
        agent_transcript = hook_input.get('agent_transcript_path')

        # Retrieve the subagent trace
        subagent_trace = self.subagent_traces.get(agent_id)

        if subagent_trace:
            try:
                subagent_trace.update(
                    output={'status': 'completed'},
                    metadata={
                        'agent_transcript_path': agent_transcript
                    }
                )

                # Remove from active subagent traces
                del self.subagent_traces[agent_id]

                self.langfuse_client.flush()
                self._debug_log('SubagentTraceCompleted', {'agent_id': agent_id})
            except Exception as e:
                self._debug_log('SubagentStopError', {'error': str(e)})
        else:
            self._debug_log('OrphanedSubagentStop', {
                'agent_id': agent_id,
                'warning': 'No matching SubagentStart trace found'
            })

        return {"success": True, "suppressOutput": True}

    def handle_stop(self, hook_input: Dict) -> Dict:
        """Finalize session tracking with aggregated metrics and cleanup."""
        self._debug_log('Stop', hook_input)

        self.session_id = hook_input.get('session_id')
        if not self.session_id:
            return {"success": True, "suppressOutput": True}

        self._connect_langfuse()
        trace = self._get_trace()

        # Clean up any orphaned spans
        if self.active_spans:
            self._debug_log('OrphanedSpans', {
                'count': len(self.active_spans),
                'tool_use_ids': list(self.active_spans.keys())
            })
            for tool_use_id, span in list(self.active_spans.items()):
                try:
                    span.end(
                        status_message='Orphaned span - no PostToolUse received',
                        level='WARNING'
                    )
                    del self.active_spans[tool_use_id]
                except Exception:
                    pass

        # Calculate session metrics
        session_end_time = datetime.now()
        session_metrics = self._compute_session_metrics(session_end_time)

        if trace:
            try:
                # Extract conversation from transcript
                transcript_path = hook_input.get('transcript_path')
                if transcript_path and Path(transcript_path).exists():
                    user_prompt, assistant_response = self._extract_last_conversation(transcript_path)

                    if user_prompt and assistant_response:
                        trace.generation(
                            name="assistant_response",
                            start_time=datetime.now(),
                            input=user_prompt,
                            output=assistant_response,
                            metadata={'event': 'Stop', 'type': 'conversation_turn'}
                        )

                # Update trace with final metrics
                trace.update(
                    output={
                        'status': 'completed',
                        'metrics': session_metrics
                    },
                    metadata={
                        'session_metrics': session_metrics
                    }
                )
                self.langfuse_client.flush()
            except Exception as e:
                self._debug_log('TraceFinalizeError', {'error': str(e)})

        # Format message with key metrics
        message = f"📊 Session complete - {session_metrics['total_tools']} tools"
        if session_metrics['duration_minutes'] > 0:
            message += f", {session_metrics['duration_minutes']:.1f}min"
        if session_metrics['tool_errors'] > 0:
            message += f", {session_metrics['tool_errors']} errors"

        return {
            "systemMessage": message,
            "suppressOutput": False
        }

    def handle_session_end(self, hook_input: Dict) -> Dict:
        """Handle session end event."""
        self._debug_log('SessionEnd', hook_input)

        # Get session ID and connect
        self.session_id = hook_input.get('session_id')
        if not self.session_id:
            return {"success": True, "suppressOutput": True}

        self._connect_langfuse()
        trace = self._get_trace()

        # Finalize trace
        if trace:
            try:
                trace.update(
                    output={'status': 'session_ended'}
                )
                self.langfuse_client.flush()
            except Exception as e:
                self._debug_log('SessionEndError', {'error': str(e)})

        return {"success": True, "suppressOutput": True}

    def _extract_last_conversation(self, transcript_path: str) -> tuple:
        """Extract last user prompt and assistant response from transcript."""
        try:
            transcript_lines = Path(transcript_path).read_text().strip().split('\n')

            user_prompt = None
            assistant_response = None

            # Find the last user and assistant messages
            for line in reversed(transcript_lines):
                try:
                    entry = json.loads(line)
                    
                    # Handle both new and legacy transcript formats
                    message = entry.get('message', entry)
                    if not isinstance(message, dict):
                        continue
                        
                    role = message.get('role')
                    content = message.get('content')

                    if not content:
                        continue

                    # Extract assistant response
                    if role == 'assistant' and not assistant_response:
                        if isinstance(content, list):
                            # Content is array of text/tool_use blocks
                            text_parts = [
                                block.get('text', '')
                                for block in content
                                if isinstance(block, dict) and block.get('type') == 'text'
                            ]
                            if text_parts:
                                assistant_response = '\n'.join(text_parts)
                        elif isinstance(content, str):
                            assistant_response = content

                    # Extract user prompt
                    elif role == 'user' and not user_prompt:
                        if isinstance(content, list):
                            text_parts = [
                                block.get('text', '')
                                for block in content
                                if isinstance(block, dict) and block.get('type') == 'text'
                            ]
                            if text_parts:
                                user_prompt = '\n'.join(text_parts)
                        elif isinstance(content, str):
                            user_prompt = content

                    # Stop when we have both
                    if user_prompt and assistant_response:
                        break

                except (json.JSONDecodeError, KeyError):
                    continue

            return (user_prompt, assistant_response)
        except Exception as e:
            self._debug_log('TranscriptExtractionError', {'error': str(e)})
            return (None, None)

    def _compute_session_metrics(self, end_time: datetime) -> Dict:
        """Compute aggregated session metrics."""
        start_time = self.session_metrics.get('session_start_time')
        duration_seconds = 0
        if start_time:
            duration_seconds = (end_time - start_time).total_seconds()

        # Active session time (first tool to last tool)
        active_duration_seconds = 0
        first_tool = self.session_metrics.get('first_tool_time')
        last_tool = self.session_metrics.get('last_tool_time')
        if first_tool and last_tool:
            active_duration_seconds = (last_tool - first_tool).total_seconds()

        tool_count = self.session_metrics['tool_count']

        return {
            'total_tools': tool_count,
            'tool_successes': self.session_metrics['tool_successes'],
            'tool_errors': self.session_metrics['tool_errors'],
            'error_rate': (
                self.session_metrics['tool_errors'] / tool_count
                if tool_count > 0 else 0
            ),
            'tools_by_name': self.session_metrics['tools_by_name'],
            'subagent_count': self.session_metrics['subagent_count'],
            'prompt_count': self.session_metrics['prompt_count'],
            'duration_seconds': duration_seconds,
            'duration_minutes': round(duration_seconds / 60, 2),
            'active_duration_seconds': active_duration_seconds,
            'active_duration_minutes': round(active_duration_seconds / 60, 2)
        }

    # ========================================
    # UTILITIES
    # ========================================

    def _debug_log(self, event: str, data: Dict) -> None:
        """Log debug information to help diagnose issues."""
        if not self.debug_mode:
            return

        try:
            debug_dir = self.project_dir / '.claude' / 'observability' / 'debug'
            debug_dir.mkdir(parents=True, exist_ok=True)

            debug_file = debug_dir / f"debug-{datetime.now().strftime('%Y%m%d')}.jsonl"

            debug_entry = {
                'timestamp': datetime.now().isoformat(),
                'event': event,
                'data': data
            }

            with debug_file.open('a') as f:
                f.write(json.dumps(debug_entry) + '\n')
        except Exception:
            pass  # Don't fail if debug logging fails

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

        # ALWAYS log all incoming events first (before any filtering)
        try:
            raw_log_dir = project_dir / '.claude' / 'observability' / 'raw-events'
            raw_log_dir.mkdir(parents=True, exist_ok=True)
            raw_log_file = raw_log_dir / f"events-{datetime.now().strftime('%Y%m%d')}.jsonl"

            with raw_log_file.open('a') as f:
                f.write(json.dumps({
                    'timestamp': datetime.now().isoformat(),
                    'event': hook_input.get('hook_event_name', 'unknown'),
                    'data': hook_input
                }) + '\n')
        except Exception:
            pass  # Don't fail the hook if logging fails

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
        elif hook_event == 'PreToolUse':
            result = tracker.handle_pre_tool_use(hook_input)
        elif hook_event == 'PostToolUse':
            result = tracker.handle_tool_use(hook_input)
        elif hook_event == 'UserPromptSubmit':
            result = tracker.handle_prompt(hook_input)
        elif hook_event == 'SubagentStart':
            result = tracker.handle_subagent_start(hook_input)
        elif hook_event == 'SubagentStop':
            result = tracker.handle_subagent_stop(hook_input)
        elif hook_event == 'Stop':
            result = tracker.handle_stop(hook_input)
        elif hook_event == 'SessionEnd':
            result = tracker.handle_session_end(hook_input)
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
