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
- Stateful reconstruction from local logs
- Duration-aware spans and generations
"""

import json
import os
import subprocess
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple
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

    # ========================================
    # SESSION START
    # ========================================

    def handle_session_start(self, hook_input: Dict) -> Dict:
        """Initialize session tracking and create Langfuse trace."""
        self._debug_log('SessionStart', hook_input)

        # Get session ID
        self.session_id = hook_input.get('session_id', self._generate_session_id())

        # Quick Langfuse health check
        if self.langfuse_config.get('enabled', False):
            if self._is_langfuse_healthy():
                self._connect_langfuse()
                if self.langfuse_client:
                    # Create trace immediately
                    trace = self._get_trace()
                    if trace:
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
                        "systemMessage": f"📊 Session tracking: {self.session_id[:8]} (Langfuse setup running)",
                        "suppressOutput": False
                    }

        return {
            "systemMessage": f"📊 Session tracking: {self.session_id[:8]} (local mode)",
            "suppressOutput": False
        }

    # ========================================
    # TOOL TRACKING
    # ========================================

    def handle_pre_tool_use(self, hook_input: Dict) -> Dict:
        """Start a span for tool execution (PreToolUse)."""
        self.session_id = hook_input.get('session_id')
        tool_use_id = hook_input.get('tool_use_id')
        if not self.session_id or not tool_use_id:
            return {"success": True, "suppressOutput": True}

        self._connect_langfuse()
        trace = self._get_trace()

        if trace:
            try:
                tool_name = hook_input.get('tool_name', 'Unknown')
                trace.span(
                    id=tool_use_id,
                    name=f"tool_{tool_name}",
                    start_time=datetime.now(),
                    input=hook_input.get('tool_input', {}),
                    metadata={
                        'tool': tool_name,
                        'tool_use_id': tool_use_id,
                        'cwd': hook_input.get('cwd')
                    }
                )
                self.langfuse_client.flush()
            except Exception as e:
                self._debug_log('PreToolSpanError', {'error': str(e)})

        return {"success": True, "suppressOutput": True}

    def handle_tool_use(self, hook_input: Dict) -> Dict:
        """Complete the span started in PreToolUse (PostToolUse)."""
        self.session_id = hook_input.get('session_id')
        tool_use_id = hook_input.get('tool_use_id')
        if not self.session_id or not tool_use_id:
            return {"success": True, "suppressOutput": True}

        self._connect_langfuse()
        trace = self._get_trace()

        if trace:
            try:
                # Reconstruct start_time from logs to ensure non-zero duration
                start_time, _ = self._find_event_info('PreToolUse', tool_use_id)
                
                tool_name = hook_input.get('tool_name', 'Unknown')
                tool_result = (
                    hook_input.get('tool_response') or
                    hook_input.get('tool_result') or
                    hook_input.get('output') or {}
                )
                is_error = isinstance(tool_result, dict) and tool_result.get('error')

                trace.span(
                    id=tool_use_id,
                    name=f"tool_{tool_name}",
                    start_time=start_time, # Historically accurate
                    end_time=datetime.now(),
                    output=tool_result,
                    level='ERROR' if is_error else 'DEFAULT',
                    status_message=str(tool_result.get('error')) if is_error else None
                )
                self.langfuse_client.flush()
            except Exception as e:
                self._debug_log('PostToolSpanError', {'error': str(e)})

        return {"success": True, "suppressOutput": True}

    # ========================================
    # PROMPT & SUBAGENT TRACKING
    # ========================================

    def handle_prompt(self, hook_input: Dict) -> Dict:
        """Track user prompt submission."""
        self.session_id = hook_input.get('session_id')
        if not self.session_id:
            return {"success": True, "suppressOutput": True}

        self._connect_langfuse()
        trace = self._get_trace()

        if trace:
            try:
                content = hook_input.get('prompt', hook_input.get('user_message', ''))
                trace.event(
                    name="user_prompt_submit",
                    input=content,
                    metadata={'prompt_length': len(content)}
                )
                self.langfuse_client.flush()
            except Exception as e:
                self._debug_log('PromptEventError', {'error': str(e)})

        return {"success": True, "suppressOutput": True}

    def handle_subagent_start(self, hook_input: Dict) -> Dict:
        """Create a child trace for subagent execution."""
        self.session_id = hook_input.get('session_id')
        agent_id = hook_input.get('agent_id')
        if not self.session_id or not agent_id:
            return {"success": True, "suppressOutput": True}

        self._connect_langfuse()
        if self.langfuse_client:
            try:
                agent_type = hook_input.get('agent_type', 'Unknown')
                self.langfuse_client.trace(
                    id=agent_id,
                    name=f"subagent_{agent_type}",
                    session_id=self.session_id,
                    input=hook_input.get('prompt', ''),
                    metadata={'agent_id': agent_id, 'agent_type': agent_type}
                )
                self.langfuse_client.flush()
            except Exception as e:
                self._debug_log('SubagentStartError', {'error': str(e)})

        return {"success": True, "suppressOutput": True}

    def handle_subagent_stop(self, hook_input: Dict) -> Dict:
        """Complete the subagent trace."""
        agent_id = hook_input.get('agent_id')
        if not agent_id:
            return {"success": True, "suppressOutput": True}

        self._connect_langfuse()
        if self.langfuse_client:
            try:
                start_time, _ = self._find_event_info('SubagentStart', agent_id)
                self.langfuse_client.trace(
                    id=agent_id,
                    start_time=start_time,
                    output={'status': 'completed'},
                    metadata={'transcript': hook_input.get('agent_transcript_path')}
                )
                self.langfuse_client.flush()
            except Exception as e:
                self._debug_log('SubagentStopError', {'error': str(e)})

        return {"success": True, "suppressOutput": True}

    # ========================================
    # SESSION FINALIZATION
    # ========================================

    def handle_stop(self, hook_input: Dict) -> Dict:
        """Finalize turn with a full-duration Generation."""
        self.session_id = hook_input.get('session_id')
        if not self.session_id:
            return {"success": True, "suppressOutput": True}

        self._connect_langfuse()
        trace = self._get_trace()

        if trace:
            try:
                # Find when the user first prompted in this turn
                prompt_time, prompt_text = self._find_event_info('UserPromptSubmit')
                
                transcript_path = hook_input.get('transcript_path')
                if transcript_path and Path(transcript_path).exists():
                    _, assistant_response = self._extract_last_conversation(transcript_path)

                    if assistant_response:
                        # Generation should span from prompt until now
                        trace.generation(
                            name="assistant_response",
                            start_time=prompt_time or datetime.now(),
                            end_time=datetime.now(),
                            input=prompt_text or "See transcript",
                            output=assistant_response
                        )

                # Aggregate metrics for the final summary
                metrics = self._compute_session_metrics_from_logs()
                trace.update(
                    output={'metrics': metrics},
                    metadata={'session_metrics': metrics}
                )
                self.langfuse_client.flush()
                
                return {
                    "systemMessage": f"📊 Session complete ({metrics.get('total_tools', 0)} tools)",
                    "suppressOutput": False
                }
            except Exception as e:
                self._debug_log('StopFinalizeError', {'error': str(e)})

        return {"systemMessage": "📊 Session complete", "suppressOutput": False}

    def handle_session_end(self, hook_input: Dict) -> Dict:
        """Handle final session termination."""
        self.session_id = hook_input.get('session_id')
        self._connect_langfuse()
        trace = self._get_trace()
        if trace:
            try:
                trace.update(output={'status': 'session_ended'})
                self.langfuse_client.flush()
            except Exception: pass
        return {"success": True, "suppressOutput": True}

    # ========================================
    # LOG-BASED RECONCILIATION
    # ========================================

    def _find_event_info(self, event_name: str, correlation_id: Optional[str] = None) -> Tuple[Optional[datetime], Optional[str]]:
        """Search local raw-events log for historical event data."""
        try:
            log_dir = self.project_dir / '.claude' / 'observability' / 'raw-events'
            log_file = log_dir / f"events-{datetime.now().strftime('%Y%m%d')}.jsonl"
            
            if not log_file.exists():
                return None, None

            # Read backwards to find the most recent matching event
            with open(log_file, 'r') as f:
                lines = f.readlines()
                for line in reversed(lines):
                    try:
                        entry = json.loads(line)
                        data = entry.get('data', {})
                        
                        # Verify session
                        if data.get('session_id') != self.session_id:
                            continue
                            
                        # Verify event and correlation ID (tool_use_id or agent_id)
                        if entry.get('event') == event_name:
                            if correlation_id:
                                if data.get('tool_use_id') == correlation_id or data.get('agent_id') == correlation_id:
                                    ts = datetime.fromisoformat(entry.get('timestamp'))
                                    text = data.get('prompt') or data.get('user_message') or ""
                                    return ts, text
                            else:
                                # Generic event (like UserPromptSubmit)
                                ts = datetime.fromisoformat(entry.get('timestamp'))
                                text = data.get('prompt') or data.get('user_message') or ""
                                return ts, text
                    except Exception: continue
        except Exception: pass
        return None, None

    def _compute_session_metrics_from_logs(self) -> Dict:
        """Reconstruct session statistics from local log file."""
        metrics = {'total_tools': 0, 'tool_errors': 0, 'subagent_count': 0, 'start_time': None, 'end_time': None}
        try:
            log_file = self.project_dir / '.claude' / 'observability' / 'raw-events' / f"events-{datetime.now().strftime('%Y%m%d')}.jsonl"
            if not log_file.exists(): return metrics

            with open(log_file, 'r') as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                        data = entry.get('data', {})
                        if data.get('session_id') != self.session_id: continue
                        
                        ts = datetime.fromisoformat(entry.get('timestamp'))
                        if not metrics['start_time']: metrics['start_time'] = ts
                        metrics['end_time'] = ts

                        ev = entry.get('event')
                        if ev == 'PreToolUse': metrics['total_tools'] += 1
                        elif ev == 'SubagentStart': metrics['subagent_count'] += 1
                        elif ev == 'PostToolUse':
                            res = data.get('tool_response') or data.get('tool_result') or {}
                            if isinstance(res, dict) and res.get('error'): metrics['tool_errors'] += 1
                    except Exception: continue
            
            if metrics['start_time'] and metrics['end_time']:
                metrics['duration_minutes'] = round((metrics['end_time'] - metrics['start_time']).total_seconds() / 60, 2)
        except Exception: pass
        return metrics

    # ========================================
    # UTILITIES
    # ========================================

    def _is_langfuse_healthy(self) -> bool:
        """Quick health check (<2s)."""
        try:
            host = self.langfuse_config.get('host', 'http://localhost:3000')
            with urllib.request.urlopen(f"{host}/api/public/health", timeout=2) as r:
                return r.status == 200
        except Exception: return False

    def _connect_langfuse(self) -> None:
        """Initialize Langfuse client."""
        if self.langfuse_client: return
        try:
            import langfuse
            pk = self.langfuse_config.get('public_key') or os.environ.get('LANGFUSE_PUBLIC_KEY')
            sk = self.langfuse_config.get('secret_key') or os.environ.get('LANGFUSE_SECRET_KEY')
            host = self.langfuse_config.get('host') or os.environ.get('LANGFUSE_HOST', 'http://localhost:3000')
            if pk and sk:
                self.langfuse_client = langfuse.Langfuse(public_key=pk, secret_key=sk, host=host)
        except Exception: pass

    def _get_trace(self):
        """Get/Create Trace object."""
        if not self.langfuse_client or not self.session_id: return None
        try:
            return self.langfuse_client.trace(
                id=self.session_id,
                name="claude-code-session",
                session_id=self.session_id,
                metadata={'project': self.project_dir.name}
            )
        except Exception: return None

    def _extract_last_conversation(self, path: str) -> tuple:
        """Get last turn from transcript."""
        try:
            lines = Path(path).read_text().strip().split('\n')
            user, assistant = None, None
            for line in reversed(lines):
                try:
                    entry = json.loads(line)
                    msg = entry.get('message', entry)
                    role, content = msg.get('role'), msg.get('content')
                    if role == 'assistant' and not assistant: assistant = content
                    elif role == 'user' and not user: user = content
                    if user and assistant: break
                except Exception: continue
            return user, assistant
        except Exception: return None, None

    def _spawn_async_setup(self):
        """Background setup."""
        script = Path(__file__).parent / 'langfuse-setup.py'
        if script.exists():
            subprocess.Popen(['uv', 'run', '--quiet', str(script)], 
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=self.project_dir)

    def _debug_log(self, event: str, data: Dict) -> None:
        """Debug logging to file."""
        if not self.debug_mode: return
        try:
            log_dir = self.project_dir / '.claude' / 'observability' / 'debug'
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"debug-{datetime.now().strftime('%Y%m%d')}.jsonl"
            with log_file.open('a') as f:
                f.write(json.dumps({'timestamp': datetime.now().isoformat(), 'event': event, 'data': data}) + '\n')
        except Exception: pass

    def _generate_session_id(self) -> str:
        return hashlib.sha256(f"{datetime.now().isoformat()}{os.urandom(8).hex()}".encode()).hexdigest()[:16]


def load_config(project_dir: Path) -> Dict:
    """Load settings."""
    config_path = project_dir / '.claude' / 'dev-plugin.local.md'
    if config_path.exists():
        try:
            content = config_path.read_text()
            if content.startswith('---'):
                import yaml
                parts = content.split('---', 2)
                if len(parts) >= 2: return yaml.safe_load(parts[1]) or {}
        except Exception: pass
    return {'observability': {'enabled': False}}


def main():
    try:
        try:
            stdin = sys.stdin.read().strip()
            hook_input = json.loads(stdin) if stdin else {}
        except Exception: hook_input = {}

        project_dir = Path(os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd()))

        # Raw logging for state reconstruction
        try:
            log_dir = project_dir / '.claude' / 'observability' / 'raw-events'
            log_dir.mkdir(parents=True, exist_ok=True)
            with open(log_dir / f"events-{datetime.now().strftime('%Y%m%d')}.jsonl", 'a') as f:
                f.write(json.dumps({'timestamp': datetime.now().isoformat(), 
                                    'event': hook_input.get('hook_event_name', 'unknown'), 
                                    'data': hook_input}) + '\n')
        except Exception: pass

        config = load_config(project_dir)
        if not config.get('observability', {}).get('enabled', False):
            print(json.dumps({"success": True, "suppressOutput": True}))
            sys.exit(0)

        tracker = ObservabilityTracker(project_dir, config)
        event = hook_input.get('hook_event_name', '')
        
        if event == 'SessionStart': res = tracker.handle_session_start(hook_input)
        elif event == 'PreToolUse': res = tracker.handle_pre_tool_use(hook_input)
        elif event == 'PostToolUse': res = tracker.handle_tool_use(hook_input)
        elif event == 'UserPromptSubmit': res = tracker.handle_prompt(hook_input)
        elif event == 'SubagentStart': res = tracker.handle_subagent_start(hook_input)
        elif event == 'SubagentStop': res = tracker.handle_subagent_stop(hook_input)
        elif event == 'Stop': res = tracker.handle_stop(hook_input)
        elif event == 'SessionEnd': res = tracker.handle_session_end(hook_input)
        else: res = {"success": True, "suppressOutput": True}

        print(json.dumps(res))
        sys.exit(0)
    except Exception as e:
        print(json.dumps({"systemMessage": f"⚠️ Observability error: {str(e)}", "suppressOutput": False}))
        sys.exit(0)

if __name__ == '__main__':
    main()
