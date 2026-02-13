# Unified Observability System ✅

## Overview

Single script handles all observability with async Langfuse setup:
- **Auto-setup** Langfuse from scratch (git clone, docker, deps)
- **Auto-start** Langfuse if already installed
- **Track sessions** across all hooks
- **Persist data** locally + sync to Langfuse
- **Graceful fallback** always works

## Architecture

```
SessionStart → observability-tracker-unified.py (async, <5s)
               ├─> Quick health check
               ├─> Initialize session tracking
               └─> [Background] Full setup if needed
                   ├─> Clone Langfuse repo
                   ├─> Install langfuse SDK
                   ├─> Start Docker
                   └─> Wait for health (5min max)

PostToolUse → observability-tracker-unified.py
              └─> Track tool usage + file operations

UserPromptSubmit → observability-tracker-unified.py
                   └─> Track prompt count

Stop → observability-tracker-unified.py
       ├─> Finalize session
       ├─> Send to Langfuse (if available)
       └─> Archive to local JSON
```

## Files

```
plugins/dev-plugin/hooks/scripts/
├── observability-tracker-unified.py  (main, handles all hooks)
├── langfuse-setup.py                 (background setup task)
├── langfuse-manager.py               (deprecated, merged)
└── observability-tracker.py          (deprecated, merged)

.claude/observability/
├── current-session.json              (active session)
├── sessions/                         (completed sessions archive)
│   └── session-*.json
└── setup.log                         (background setup log)
```

## Configuration

```yaml
# .claude/dev-plugin.local.md
observability:
  enabled: true
  langfuse:
    enabled: true          # Send to Langfuse
    auto_setup: false      # Auto-install from scratch (git clone, etc.)
    auto_start: true       # Auto-start if already installed
    host: http://localhost:3000
    public_key: "pk-..."
    secret_key: "sk-..."
    compose_path: "/path/to/docker-compose.yml"
```

### Configuration Modes

**Mode 1: Manual (default)**
```yaml
auto_setup: false
auto_start: false
# You manage Langfuse manually
```

**Mode 2: Auto-start**
```yaml
auto_setup: false
auto_start: true
# Starts Langfuse if docker-compose.yml exists
```

**Mode 3: Full auto (recommended)**
```yaml
auto_setup: true
auto_start: true
# Installs everything from scratch automatically
```

## Usage

### Normal Operation

Just use Claude Code normally:
```bash
claude --plugin-dir ./plugins/dev-plugin/
```

**SessionStart:**
```
📊 Session tracking: 934b4a61 (Langfuse ready)
```
or
```
📊 Session tracking: 934b4a61 (Langfuse setup running in background)
```

**Session End:**
```
📊 Session complete: 45 tools, 8 files modified, 12.5min
```

### Check Setup Progress

```bash
# View setup log
cat .claude/observability/setup.log

# Check if Langfuse is running
curl http://localhost:3000/api/public/health
```

### View Session Data

```bash
# Current session
cat .claude/observability/current-session.json

# Completed sessions
ls -lt .claude/observability/sessions/

# View latest session
cat .claude/observability/sessions/session-*.json | tail -1
```

## Data Persistence

### Local Storage (Primary)
```
.claude/observability/
├── current-session.json     (active)
└── sessions/
    └── session-*.json       (archive)
```

**Always works** - even if Langfuse never starts

### Langfuse Sync (Secondary)
```
When Langfuse available:
  → Sync from local JSON
  → Store in Langfuse DB (Docker volumes)
```

**Docker volumes persist** across restarts:
- `langfuse_postgres_data`
- `langfuse_minio_data`
- `langfuse_clickhouse_data`

## Async Setup Details

When `auto_setup: true` and Langfuse not found:

**Background script does:**
1. Clone `https://github.com/langfuse/langfuse` → `~/langfuse-docker/`
2. Generate secure `.env` with random secrets
3. Install `pip install langfuse` (Python SDK)
4. Run `docker-compose up -d`
5. Wait for health check (up to 5 minutes)
6. Log all progress to `.claude/observability/setup.log`

**Main session:**
- Continues immediately
- Uses local JSON tracking
- Switches to Langfuse when ready

## Graceful Degradation

```
Scenario                          → Behavior
──────────────────────────────────────────────────
Langfuse healthy                  → Sync to Langfuse ✓
Langfuse starting                 → Local JSON ✓
Langfuse failed                   → Local JSON ✓
Docker not installed              → Local JSON ✓
No internet                       → Local JSON ✓
SDK not installed (auto_setup on) → Install in background ✓
```

**Always works!** Observability never blocks Claude Code.

## Troubleshooting

**Check what's happening:**
```bash
# Setup log
cat .claude/observability/setup.log

# Current session
cat .claude/observability/current-session.json

# Langfuse health
curl http://localhost:3000/api/public/health
```

**Common issues:**

1. **Setup taking long?**
   - Check `.claude/observability/setup.log`
   - First-time setup downloads Docker images (2-5min)

2. **Docker not starting?**
   - Check Docker is installed: `docker --version`
   - Check Docker daemon running: `docker ps`

3. **SDK import error?**
   - Install manually: `pip install langfuse`
   - Or enable `auto_setup: true`

4. **Langfuse UI not loading?**
   - Check port 3000 not in use: `lsof -i :3000`
   - Check Docker logs: `docker-compose logs -f` (in langfuse-docker/)

## Migration from Old Scripts

**Old (2 scripts):**
```json
"hooks": [
  {"command": "langfuse-manager.py"},
  {"command": "observability-tracker.py"}
]
```

**New (1 unified):**
```json
"hooks": [
  {
    "command": "observability-tracker-unified.py",
    "async": true
  }
]
```

Old scripts still work but are deprecated.

## Performance

### Before (Synchronous)
```
SessionStart: 5-15s (blocked waiting for Langfuse check/start)
```

### After (Async)
```
SessionStart: <5s (spawns setup, continues immediately)
Background setup: 2-5min (first time), 30s (subsequent)
```

**Session start is instant!** 🚀

## Next Steps

1. **Enable auto_setup** if you want fully automatic installation
2. **Check logs** after first session to see setup progress
3. **Access Langfuse UI** at http://localhost:3000
4. **View traces** in "Claude Code Sessions" project

---

**Status:** ✅ Production ready
**KISS Principle:** Single script, smart defaults, graceful fallbacks
**Data Safety:** Local JSON is always source of truth
