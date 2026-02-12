---
# Master control
enabled: true

# Observability tracking
observability:
  enabled: true        # ✅ Track sessions locally
  langfuse:
    enabled: true      # ✅ Send data to Langfuse
    auto_setup: false  # 🔧 Auto-install Langfuse from scratch (git clone, docker, etc.)
    auto_start: true   # ✅ Auto-start Langfuse if already installed
    host: http://localhost:3000
    public_key: "pk-lf-eb1d1d22-c8de-41dd-8ee7-3b08bed31c49"
    secret_key: "sk-lf-c6b0c1c9-8230-4f08-bfeb-1f78f95acec4"
    userId: "ranjit"        # Optional: track by user
    version: "1.0.0"        # Optional: track plugin version
    tags: ["dev", "local"]  # Optional: categorize traces
    compose_path: "/Users/raghavendersolipuram/langfuse-docker/docker-compose.yml"

# Auto-formatting
autoformat:
  enabled: true

# Git checkpointing
git_checkpoint:
  enabled: true

# Completion notifications
notifications:
  enabled: true
  mac_notification: true
  tts: false

# CLAUDE.md management
claude_md_management:
  auto_init: true
  auto_update: true
  update_threshold: 3
  max_file_size: 10240
  backup_before_update: true
---

# Development Plugin Settings

Observability tracking is now **enabled**. Session data will be saved locally to:
- `.claude/observability/sessions/`

Each session will track:
- Tool usage and frequency
- Files modified/created
- Session duration
- Error counts
- Summary statistics

To enable Langfuse integration later, set `observability.langfuse.enabled: true` and configure the keys.
