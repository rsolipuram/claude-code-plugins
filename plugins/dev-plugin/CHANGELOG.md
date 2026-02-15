# Changelog

All notable changes to the dev-plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] - 2026-02-15

### Added
- Global configuration support (`~/.claude/plugins/dev-plugin/`)
- Project-specific configuration overrides (`.claude/dev-plugin.yaml`)
- Configuration priority system (project > global > defaults)
- Interactive setup with scope selection (global/project/both)
- Configuration validation and misplaced config warnings
- Template-based configuration generation
- Enhanced documentation for configuration storage

### Changed
- Setup flow now prompts for configuration scope
- Configuration files stored in stable locations (not cache)
- Improved setup documentation in README

### Fixed
- Configuration loss on plugin updates (moved from cache to stable locations)

## [0.3.0] - 2026-02-14

### Added
- Session observability tracking
- Langfuse integration for analytics
- CLAUDE.md auto-management skill
- Git auto-checkpointing
- Code quality checks (TypeScript, Python, Go, Rust)
- Auto-formatting with Prettier
- Safety validations for destructive commands
- Desktop notifications and text-to-speech
- Comprehensive hook system

### Changed
- Restructured plugin directory layout
- Improved hook organization

## [0.2.0] - 2026-02-13

### Added
- Initial hook implementations
- Basic configuration system
- Setup automation script

## [0.1.0] - 2026-02-12

### Added
- Initial plugin structure
- Basic plugin manifest
- Core automation features

[0.4.0]: https://github.com/YOUR_USERNAME/claude-code-plugins/releases/tag/dev-plugin-v0.4.0
[0.3.0]: https://github.com/YOUR_USERNAME/claude-code-plugins/releases/tag/dev-plugin-v0.3.0
[0.2.0]: https://github.com/YOUR_USERNAME/claude-code-plugins/releases/tag/dev-plugin-v0.2.0
[0.1.0]: https://github.com/YOUR_USERNAME/claude-code-plugins/releases/tag/dev-plugin-v0.1.0
