#!/bin/bash
# Setup script for dev-plugin
# This script installs all dependencies and optionally sets up the plugin

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_NAME="dev-plugin"

echo "🚀 Setting up dev-plugin for Claude Code"
echo ""

# Check Python
echo "Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is not installed"
    echo "   Please install Python 3.7+ from https://www.python.org"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
echo "✓ Python $PYTHON_VERSION found"
echo ""

# Check pip
echo "Checking pip installation..."
if ! python3 -m pip --version &> /dev/null; then
    echo "❌ Error: pip is not installed"
    echo "   Install pip: python3 -m ensurepip --upgrade"
    exit 1
fi
echo "✓ pip found"
echo ""

# Install dependencies
echo "Installing dependencies..."
echo "  - pyyaml (required for configuration)"
echo "  - langfuse (optional, for observability)"
echo ""

read -p "Install all dependencies including optional ones? [Y/n] " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
    # Install all dependencies
    python3 -m pip install --upgrade pyyaml langfuse
    echo "✓ All dependencies installed"
else
    # Install only required dependencies
    python3 -m pip install --upgrade pyyaml
    echo "✓ Required dependencies installed"
    echo "⚠️  Skipped optional dependencies (langfuse)"
fi
echo ""

# Offer to install plugin globally
echo "Where would you like to install the plugin?"
echo "  1. Global (~/.claude/plugins) - available in all projects"
echo "  2. Project-specific (.claude-plugin) - only in current directory"
echo "  3. Skip installation (dependencies only)"
echo ""

read -p "Choose option [1/2/3]: " -n 1 -r INSTALL_CHOICE
echo ""
echo ""

case $INSTALL_CHOICE in
    1)
        # Global installation
        GLOBAL_DIR="$HOME/.claude/plugins/$PLUGIN_NAME"
        echo "Installing globally to $GLOBAL_DIR..."
        mkdir -p "$HOME/.claude/plugins"
        cp -r "$SCRIPT_DIR" "$GLOBAL_DIR"
        echo "✓ Plugin installed globally"
        echo ""
        echo "The plugin will be available in all projects."
        ;;
    2)
        # Project installation
        PROJECT_DIR=".claude-plugin/$PLUGIN_NAME"
        echo "Installing to current project at $PROJECT_DIR..."
        mkdir -p ".claude-plugin"
        cp -r "$SCRIPT_DIR" "$PROJECT_DIR"
        echo "✓ Plugin installed in current project"
        echo ""
        echo "The plugin is only available in this project."
        ;;
    3)
        echo "⏭️  Skipping plugin installation"
        echo ""
        echo "You can manually copy the plugin later:"
        echo "  Global:  cp -r $SCRIPT_DIR ~/.claude/plugins/"
        echo "  Project: cp -r $SCRIPT_DIR .claude-plugin/"
        ;;
    *)
        echo "Invalid choice. Skipping installation."
        ;;
esac

echo ""
echo "═══════════════════════════════════════════════"
echo "✨ Setup Complete!"
echo "═══════════════════════════════════════════════"
echo ""
echo "Next steps:"
echo "  1. Start Claude Code: claude"
echo "  2. (Optional) Configure features in .claude/dev-plugin.local.md"
echo "  3. Check README.md for configuration options"
echo ""
echo "Features available:"
echo "  ✓ Code quality checks (TypeScript, Python, Go, Rust)"
echo "  ✓ Auto-formatting (prettier for TS/JS)"
echo "  ✓ Git checkpointing (automatic commits)"
echo "  ✓ Safety validations (dangerous command blocking)"
echo "  ✓ Completion notifications (Mac alerts + TTS)"
echo "  ✓ Session observability (optional Langfuse integration)"
echo ""
echo "Happy coding! 🎉"
