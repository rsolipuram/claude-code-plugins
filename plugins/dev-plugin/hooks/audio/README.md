# Claude Code Audio Library 🔊

This directory contains custom sound effects for Claude Code notifications.

## Directory Structure

```
~/.claude/audio/
├── success/     # Sounds for successful completions
├── error/       # Sounds for errors and failures
├── waiting/     # Sounds for processing/waiting states
└── notify/      # Sounds for notifications and alerts
```

## Supported Formats

- **MP3** (.mp3)
- **WAV** (.wav)
- **AIFF** (.aiff)
- **M4A** (.m4a)

## How to Add Custom Sounds

1. **Drop sound files into category folders:**
   ```bash
   # Example: Add a victory sound
   cp ~/Downloads/victory.mp3 ~/.claude/audio/success/

   # Example: Add notification ping
   cp ~/Downloads/ping.wav ~/.claude/audio/notify/
   ```

2. **Name files descriptively** (optional but helpful):
   - `mario-coin.mp3`
   - `zelda-fanfare.wav`
   - `victory-trumpet.mp3`

3. **Multiple sounds per category:**
   - When multiple sounds exist in a category, Claude Code will pick one randomly (in 'creative' mode) or use the first one (in 'mixed' mode)

## Sound Categories Explained

### success/
Played when sessions complete successfully, tasks finish without errors, or operations succeed.

**Good sounds for this:**
- Victory fanfares
- Coin collect sounds
- Power-up sounds
- Cheerful chimes
- "Level up" effects

### error/
Played when errors occur, operations fail, or critical issues are detected.

**Good sounds for this:**
- Game over sounds
- Error beeps
- Warning klaxons
- Sad trombones
- "Oops" effects

### waiting/
Played when Claude is processing, waiting for external operations, or needs time to complete a task.

**Good sounds for this:**
- Clock ticking
- Thinking sounds
- Processing beeps
- Ambient waiting music
- Hourglass effects

### notify/
Played when Claude needs your attention, approval is required, or immediate action is needed.

**Good sounds for this:**
- Notification pings
- Alert bells
- Attention getters
- Door chimes
- "Hey listen!" effects

## Fallback Behavior

If no custom sounds are found in a category, Claude Code automatically uses macOS system sounds:

- **success** → Hero.aiff (triumphant sound)
- **error** → Basso.aiff (low warning tone)
- **waiting** → Tink.aiff (gentle tick)
- **notify** → Glass.aiff (clear ping)

You can find these in `/System/Library/Sounds/` on your Mac.

## Finding Free Sound Effects

### Free Resources:
- **Freesound.org** - Community-uploaded sound effects (CC licenses)
- **Zapsplat.com** - Free sound effects library
- **Mixkit.co** - Free sound effects and music
- **YouTube Audio Library** - Royalty-free sounds

### Game Sound Packs:
Many classic game sounds are available for personal use. Search for:
- "Mario sound effects download"
- "Zelda fanfare sound effect"
- "Pac-Man sound effects"
- "Retro game audio pack"

**Note:** Always check licensing before using sounds commercially or in public projects!

## Testing Your Sounds

Test sounds directly with macOS `afplay`:

```bash
# Test a specific sound
afplay ~/.claude/audio/success/victory.mp3

# Test system sound
afplay /System/Library/Sounds/Hero.aiff
```

Or use the audio-notify.py script:

```bash
# Test with custom sound
cd /path/to/claude-code-plugins/plugins/dev-plugin/hooks/scripts
python3 audio-notify.py "Test notification" --mode sound_only --sound success

# Test with TTS + sound (mixed mode)
python3 audio-notify.py "Session completed successfully" --mode mixed --voice success --sound success
```

## Configuration

Enable audio notifications in `.claude/dev-plugin.local.md`:

```yaml
---
notifications:
  enabled: true
  audio:
    mode: 'mixed'  # 'tts_only', 'sound_only', 'mixed', 'creative'
    sound_library: '~/.claude/audio'

  completion:
    enabled: true
    sound: true
    tts: true
---
```

## Advanced: Sound Packs

You can create themed sound packs by organizing sounds into separate directories:

```bash
# Retro gaming pack
~/.claude/audio-retro/
  success/ (mario-coin.mp3, zelda-fanfare.wav)
  error/ (game-over.mp3)
  notify/ (mario-jump.wav)

# Sci-fi pack
~/.claude/audio-scifi/
  success/ (star-trek-comm.mp3)
  error/ (red-alert.wav)
  notify/ (door-chime.mp3)
```

Then switch packs in config:

```yaml
audio:
  sound_library: '~/.claude/audio-retro'  # Use retro pack
```

## Troubleshooting

**Sounds not playing?**
1. Check file permissions: `ls -la ~/.claude/audio/success/`
2. Test with afplay: `afplay ~/.claude/audio/success/yourfile.mp3`
3. Check audio mode in config (must be 'sound_only', 'mixed', or 'creative')
4. Verify file format is supported (MP3, WAV, AIFF, M4A)

**No custom sounds found?**
- Claude Code will fall back to macOS system sounds automatically
- Check that files are in correct category folders
- Verify `sound_library` path in config

**Want just TTS, no sounds?**
```yaml
audio:
  mode: 'tts_only'  # Disable sound effects
```

---

Have fun customizing your Claude Code audio experience! 🎮🔊
