# claude-code-plugins

Repository for Claude Code plugins focused on development automation, code quality, and observability.

## Project Structure

```
claude-code-plugins/
  plugins/
    dev-plugin/          # Main development automation plugin
      .claude-plugin/    # Plugin manifest
      hooks/            # Event hooks (Stop, PreToolUse, PostToolUse, etc.)
      skills/           # Claude skills (claude-md-manager, etc.)
  .claude/
    observability/      # Session tracking data
    async-logs/         # Async operation logs
  docker-compose.langfuse.yml  # Langfuse setup for observability
```

## Main Plugin: dev-plugin

Multi-feature development automation plugin (v0.5.0) providing:

- **Code Quality**: Auto-detects TypeScript/Python/Go/Rust, runs type checks at session end
- **Auto-Formatting**: Formats files after edits (prettier for TS/JS)
- **Git Checkpointing**: Auto-commits at session end with detailed summaries
- **Safety Validations**: Blocks dangerous `rm` commands via AI analysis
- **Notifications**: Mac desktop alerts + TTS on session completion
- **Observability**: Tracks sessions locally + optional Langfuse integration
- **CLAUDE.md Management**: AI-powered creation and intelligent updates

## Key Files

- `plugins/dev-plugin/.claude-plugin/plugin.json` - Plugin manifest
- `plugins/dev-plugin/README.md` - Complete documentation
- `plugins/dev-plugin/hooks/scripts/quality-check.py` - Multi-language quality checker
- `plugins/dev-plugin/hooks/scripts/observability-tracker-unified.py` - Session tracking
- `plugins/dev-plugin/skills/claude-md-manager/` - CLAUDE.md management skill
- `.claude/observability/sessions/` - Local session data storage

## Installation

**Global (all projects)**:
```bash
mkdir -p ~/.claude/plugins
cp -r plugins/dev-plugin ~/.claude/plugins/
```

**Project-specific**:
```bash
mkdir -p .claude-plugin
cp -r plugins/dev-plugin .claude-plugin/
```

**Dependencies** (auto-install on first use):
```bash
pip install pyyaml          # Required
pip install langfuse        # Optional, for observability
```

## Configuration

**New Format** (v0.5.0+): YAML + .env for better security

Create `.claude/dev-plugin.yaml`:

```yaml
# Code quality
typescript:
  command: npx tsc --noEmit

# Features
autoformat:
  enabled: true
git_checkpoint:
  enabled: true
notifications:
  enabled: true
  mac_notification: true
  tts: false

# Observability
observability:
  enabled: true
  langfuse:
    enabled: true
    host: ${LANGFUSE_HOST}
    public_key: ${LANGFUSE_PUBLIC_KEY}
    secret_key: ${LANGFUSE_SECRET_KEY}

# CLAUDE.md management
claude_md_management:
  auto_init: true
  auto_update: true
  update_threshold: 3
```

**Secrets** in `.claude/.env` (git-ignored):

```bash
LANGFUSE_PUBLIC_KEY=pk-lf-xxxxx
LANGFUSE_SECRET_KEY=sk-lf-xxxxx
LANGFUSE_HOST=http://localhost:3000
```

**Migration**: Run `python plugins/dev-plugin/migrate-config.py` to migrate from `.local.md` format.

## Langfuse Setup (Optional)

For session visualization:

```bash
# Start local Langfuse
docker compose -f docker-compose.langfuse.yml up -d

# Access at http://localhost:3000
# Get API keys from Settings → API Keys
# Add to .claude/.env file
```

## Development Workflow

1. **Plugin Development**: Work in `plugins/dev-plugin/`
2. **Hook Scripts**: Python scripts in `hooks/scripts/`
3. **Skills**: Markdown-based skills in `skills/`
4. **Testing**: Use `claude --plugin-dir plugins/dev-plugin` for testing
5. **Git Commits**: Auto-checkpointing creates commits at session end

## Gotchas

- **Config Migration** (v0.5.0): Use YAML + .env format for security. Legacy `.local.md` still works but deprecated.
- **Secrets**: Never commit `.env` files! API keys should be in `.env`, not in YAML files.
- Git auto-commits use prefix "Auto-checkpoint:" (see commit history)
- Observability data stored in `.claude/observability/` (not committed)
- CLAUDE.md manager skill requires session activity (threshold: 3+ tool calls)
- Langfuse requires Docker for local deployment
- Plugin auto-detects project type via indicator files (tsconfig.json, go.mod, etc.)

---

*Last updated: 2026-02-14*
*Managed by claude-md-manager skill. Quality target: 80+/100*
