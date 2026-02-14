#!/bin/bash
# Setup script for dev-plugin
# This script ensures uv is installed and prepares the plugin

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_NAME="dev-plugin"

echo "🚀 Setting up dev-plugin for Claude Code"
echo ""

# Check uv
echo "Checking uv installation..."
if ! command -v uv &> /dev/null; then
    echo "⚠️  uv is not installed. It is recommended for best experience."
    echo "   Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo ""
    read -p "Continue without uv? (Dependencies will be managed globally) [y/N] " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo "✓ uv found"
fi
echo ""

# Install plugin
echo "Where would you like to install the plugin?"
echo "  1. Global (~/.claude/plugins) - available in all projects"
echo "  2. Project-specific (.claude-plugin) - only in current directory"
echo "  3. Skip installation"
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
        ;;
    2)
        # Project installation
        PROJECT_DIR=".claude-plugin/$PLUGIN_NAME"
        echo "Installing to current project at $PROJECT_DIR..."
        mkdir -p ".claude-plugin"
        cp -r "$SCRIPT_DIR" "$PROJECT_DIR"
        echo "✓ Plugin installed in current project"
        ;;
    *)
        echo "⏭️  Skipping plugin installation"
        ;;
esac

echo ""
echo "═══════════════════════════════════════════════"
echo "✨ Setup Complete!"
echo "═══════════════════════════════════════════════"
echo ""
echo "The plugin now uses 'uv run' to automatically manage dependencies."
echo "No manual pip install is required!"
echo ""
echo "Happy coding! 🎉"
