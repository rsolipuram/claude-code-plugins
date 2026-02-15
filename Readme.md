# Claude Code Plugins Marketplace

Development automation and productivity plugins for Claude Code.

## Available Plugins

### dev-plugin

**Intelligent development automation with observability**

Comprehensive development automation plugin providing code quality checks, auto-formatting, git checkpointing, safety validations, session tracking, and intelligent CLAUDE.md management.

**Key Features:**
- 🔍 **Code Quality**: Automatic type-checking for TypeScript, Python, Go, and Rust
- ✨ **Auto-Formatting**: Prettier integration for TypeScript/JavaScript
- 📝 **Git Automation**: Smart auto-checkpointing with detailed commit summaries
- 🛡️ **Safety**: Validation guards blocking dangerous commands
- 📊 **Observability**: Session tracking with optional Langfuse analytics
- 🤖 **CLAUDE.md Management**: AI-driven project documentation
- 🔔 **Notifications**: Desktop alerts and text-to-speech completion notifications

**Installation:**

```bash
# Add this marketplace (once GitHub repo is set up)
/plugin marketplace add YOUR_USERNAME/claude-code-plugins

# Install dev-plugin
/plugin install dev-plugin

# Run setup
claude --init
```

**Configuration:**

Choose your setup scope:
- **Global** - One-time setup for all projects
- **Project** - Just current project
- **Both** - Global defaults + project overrides

**Quick Start:**

```bash
# Initialize with interactive setup
claude --init

# Configure globally (edit defaults)
vim ~/.claude/plugins/dev-plugin/dev-plugin.yaml

# Configure per-project (overrides)
vim .claude/dev-plugin.yaml
```

**Version:** 0.4.0
**License:** MIT
**Category:** Productivity

---

## Adding This Marketplace

### From GitHub (Recommended)

Once the repository is published on GitHub:

```bash
# Add marketplace
/plugin marketplace add YOUR_USERNAME/claude-code-plugins

# Or with specific version/branch
/plugin marketplace add YOUR_USERNAME/claude-code-plugins --ref v1.0.0
```

### From Local Development

For testing during development:

```bash
# Add from local path
/plugin marketplace add /Users/ranjit/Documents/Projects/claude-code-plugins

# Install plugin
/plugin install dev-plugin
```

### For Teams (Private Repos)

Add to `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "company-plugins": {
      "source": {
        "source": "github",
        "repo": "YOUR_USERNAME/claude-code-plugins"
      }
    }
  },
  "enabledPlugins": {
    "dev-plugin@company-plugins": true
  }
}
```

Set authentication token for private repos:
```bash
export GITHUB_TOKEN="your_github_token"
```

## Plugin Development

Want to add your own plugin to this marketplace?

1. Create plugin in `plugins/your-plugin/`
2. Add `.claude-plugin/plugin.json` manifest
3. Update `.claude-plugin/marketplace.json`
4. Submit pull request

See [Plugin Development Guide](https://code.claude.com/docs/en/plugins.md) for details.

## Support

- 📖 Documentation: [README](./plugins/dev-plugin/README.md)
- 🐛 Issues: [GitHub Issues](https://github.com/YOUR_USERNAME/claude-code-plugins/issues)
- 💬 Discussions: [GitHub Discussions](https://github.com/YOUR_USERNAME/claude-code-plugins/discussions)

---

*Marketplace maintained by Developer*
