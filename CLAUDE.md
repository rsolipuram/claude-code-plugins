# claude-code-plugins

Repository for Claude Code plugin development and experimentation, featuring the intelligent dev-plugin for development automation.

## Project Structure

```
claude-code-plugins/
  .claude/                # Claude Code settings
    observability/        # Session tracking data (dev-plugin)
    async-logs/          # Async operation logs
  plugins/
    dev-plugin/          # Main development automation plugin
      .claude-plugin/    # Plugin manifest
        plugin.json      # Plugin metadata
      hooks/             # Event-driven automation hooks
      skills/            # AI-powered skills
        claude-md-manager/  # CLAUDE.md management skill
      setup.sh           # Plugin setup automation
      README.md          # Plugin documentation
      dev-plugin.yaml.example  # Config template
  langfuse/              # Langfuse observability stack (optional)
```

## Plugin: dev-plugin

Development automation plugin providing code quality, git automation, observability, and CLAUDE.md management.

### Key Features

- **Code Quality**: Auto type-checking (TypeScript/Python/Go/Rust) at session end
- **Auto-Formatting**: Prettier for TypeScript/JavaScript after edits
- **Git Checkpointing**: Automatic commits with detailed summaries
- **Safety Validations**: Blocks destructive rm commands
- **Session Observability**: Tracks tool usage, files modified, with optional Langfuse integration
- **CLAUDE.md Management**: AI-driven creation and updates (not template-based)
- **Completion Notifications**: Mac desktop alerts + text-to-speech

### Setup

**Quick initialization** (recommended):
```bash
# Automated setup via Setup hook
claude --init
```

This creates:
- `.claude/dev-plugin.yaml` - Configuration
- `.claude/.env` - Environment variables template
- Installs dependencies (pyyaml, optionally langfuse)

**Manual setup**:
```bash
# Copy config template
cp plugins/dev-plugin/dev-plugin.yaml.example .claude/dev-plugin.yaml

# Edit configuration
vim .claude/dev-plugin.yaml
```

### Configuration

Edit `.claude/dev-plugin.yaml`:

```yaml
enabled: true

observability:
  enabled: true              # Local session tracking
  langfuse:
    enabled: false           # Langfuse integration
    auto_start: false        # Auto-start docker

quality_check:
  enabled: true              # Type checking at session end
  typescript:
    enabled: true
    command: "npx tsc --noEmit"

auto_format:
  enabled: true              # Auto-format after edits
  prettier:
    enabled: true

git_checkpoint:
  enabled: true              # Auto-commit at session end

safety_validations:
  enabled: true              # Block dangerous commands

notify_completion:
  enabled: true              # Desktop notifications
  tts:
    enabled: true            # Text-to-speech

claude_md_management:
  auto_init: true            # Create CLAUDE.md if missing
  auto_update: true          # Update with session learnings
```

### Skills

**claude-md-manager** - Intelligent CLAUDE.md management:
```bash
# Automatically triggered by hooks, or manual invoke:
/claude-md-manager [SessionStart|Stop]
```

- Creates CLAUDE.md by analyzing project (not templates)
- Updates with valuable session learnings
- Validates quality against 6-dimension rubric
- Target: 80+/100 quality score

## Observability

Session data tracked in `.claude/observability/sessions/`:
- Tool usage counts
- Files modified/created/deleted
- Session duration
- Error tracking

**Optional Langfuse integration**:
- Visual analytics dashboard
- Trace visualization
- Cross-session insights
- Requires docker or remote instance

## Development Workflow

### Plugin Development
```bash
# Edit plugin hooks
vim plugins/dev-plugin/hooks/PreToolUse.py

# Edit skills
vim plugins/dev-plugin/skills/claude-md-manager/claude-md-manager.md

# Test changes
claude  # Will auto-load from .claude-plugin/
```

### Managing Langfuse Stack
```bash
# Start observability stack (if enabled)
cd langfuse && docker-compose up -d

# Access dashboard
open http://localhost:3000
```

## Gotchas

- **Setup hook**: Only runs on `claude --init` or first session with new plugin
- **CLAUDE.md updates**: Conditional - only if valuable learnings exist
- **Langfuse auto-start**: Requires `compose_path` set in config
- **Quality checks**: Blocking - session won't end if type errors exist
- **Git checkpoint**: Only commits if files were modified

## Key Files

- `plugins/dev-plugin/.claude-plugin/plugin.json` - Plugin manifest
- `plugins/dev-plugin/dev-plugin.yaml.example` - Config template
- `plugins/dev-plugin/setup.sh` - Automated setup script
- `plugins/dev-plugin/hooks/` - Event-driven automation
- `plugins/dev-plugin/skills/claude-md-manager/` - CLAUDE.md skill

---

*Last updated: 2026-02-14*
*Managed by claude-md-manager skill. Quality target: 80+/100*
