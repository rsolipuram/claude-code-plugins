#!/usr/bin/env python3
"""
Creative Audio Notification System for Claude Code

Provides fun, contextual audio feedback using macOS TTS voices and sound effects.
Supports multiple modes: TTS-only, sound-only, mixed, and creative random sounds.
"""

import os
import sys
import subprocess
import json
import random
from pathlib import Path
from typing import Dict, Optional, List, Any


class TTSPlayer:
    """Text-to-speech player with creative voice profiles."""

    # Voice profiles mapped to different contexts
    VOICE_PROFILES = {
        # Success scenarios
        'success': {'voice': 'Good News', 'rate': 150},
        'completion': {'voice': 'Bubbles', 'rate': 160},
        'celebration': {'voice': 'Good News', 'rate': 140},

        # Failure scenarios
        'error': {'voice': 'Bad News', 'rate': 100},
        'critical': {'voice': 'Superstar', 'rate': 250},

        # Waiting/Interactive
        'waiting': {'voice': 'Wobble', 'rate': 100},
        'needs_input': {'voice': 'Trinoids', 'rate': 140},
        'approval_needed': {'voice': 'Bells', 'rate': 180},

        # Technical scenarios
        'technical': {'voice': 'Zarvox', 'rate': 130},
        'code_quality': {'voice': 'Zarvox', 'rate': 140},

        # Warnings
        'warning': {'voice': 'Whisper', 'rate': 120},

        # Fun/Casual
        'friendly': {'voice': 'Bubbles', 'rate': 160},
        'playful': {'voice': 'Jester', 'rate': 170},

        # Neutral fallback
        'neutral': {'voice': 'Samantha', 'rate': 180},
    }

    def __init__(self, timeout: int = 30, rate_adjustment: int = 0):
        """
        Initialize TTS player.

        Args:
            timeout: Maximum duration for TTS in seconds
            rate_adjustment: +/- WPM modifier for all voices
        """
        self.timeout = timeout
        self.rate_adjustment = rate_adjustment
        self.available_voices = self._get_available_voices()

    def _get_available_voices(self) -> List[str]:
        """Get list of available TTS voices on the system."""
        try:
            result = subprocess.run(
                ['say', '-v', '?'],
                capture_output=True,
                text=True,
                timeout=5
            )
            # Parse voice list (format: "VoiceName  language  # description")
            voices = []
            for line in result.stdout.split('\n'):
                if line.strip():
                    voice_name = line.split()[0]
                    voices.append(voice_name)
            return voices
        except Exception:
            return ['Samantha']  # Fallback to default voice

    def speak(self, message: str, voice_profile: str = 'neutral', async_mode: bool = False) -> bool:
        """
        Speak message with specified voice profile.

        Args:
            message: Text to speak
            voice_profile: Voice profile key from VOICE_PROFILES
            async_mode: If True, don't wait for completion

        Returns:
            True if successful, False otherwise
        """
        if not message:
            return False

        # Get voice configuration
        profile = self.VOICE_PROFILES.get(voice_profile, self.VOICE_PROFILES['neutral'])
        voice = profile['voice']
        rate = profile['rate'] + self.rate_adjustment

        # Check if voice is available, fallback to Samantha
        if voice not in self.available_voices:
            print(f"Voice '{voice}' not available, using Samantha", file=sys.stderr)
            voice = 'Samantha'

        # Build say command
        cmd = ['say', '-v', voice, '-r', str(rate), message]

        try:
            if async_mode:
                # Fire and forget
                subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                return True
            else:
                # Wait for completion with timeout
                result = subprocess.run(
                    cmd,
                    timeout=self.timeout,
                    capture_output=True
                )
                return result.returncode == 0
        except subprocess.TimeoutExpired:
            print(f"TTS timed out after {self.timeout}s", file=sys.stderr)
            return False
        except Exception as e:
            print(f"TTS error: {e}", file=sys.stderr)
            return False


class SoundEffectPlayer:
    """Play sound files for quick, recognizable alerts."""

    # System sounds fallback (macOS built-in)
    SYSTEM_SOUNDS = {
        'success': 'Hero.aiff',
        'error': 'Basso.aiff',
        'waiting': 'Tink.aiff',
        'notify': 'Glass.aiff',
        'ping': 'Ping.aiff',
    }

    SYSTEM_SOUNDS_DIR = '/System/Library/Sounds'

    def __init__(self, sound_library: Optional[str] = None):
        """
        Initialize sound effect player.

        Args:
            sound_library: Path to custom sound library directory
        """
        self.sound_library = Path(sound_library).expanduser() if sound_library else None
        self.system_sounds_dir = Path(self.SYSTEM_SOUNDS_DIR)

    def _find_sounds_in_category(self, category: str) -> List[Path]:
        """Find all sound files in a category folder."""
        sounds = []

        # Check custom library first
        if self.sound_library:
            category_dir = self.sound_library / category
            if category_dir.exists() and category_dir.is_dir():
                # Look for audio files (mp3, wav, aiff, m4a)
                for ext in ['*.mp3', '*.wav', '*.aiff', '*.m4a']:
                    sounds.extend(category_dir.glob(ext))

        return sounds

    def _get_system_sound(self, category: str) -> Optional[Path]:
        """Get system sound for category."""
        sound_name = self.SYSTEM_SOUNDS.get(category)
        if sound_name:
            sound_path = self.system_sounds_dir / sound_name
            if sound_path.exists():
                return sound_path
        return None

    def play(self, category: str, random_choice: bool = True, async_mode: bool = True) -> bool:
        """
        Play sound from category.

        Args:
            category: Sound category (success, error, waiting, notify)
            random_choice: If True, pick random sound from category; else first available
            async_mode: If True, don't wait for playback to complete

        Returns:
            True if sound was played, False otherwise
        """
        # Find custom sounds first
        sounds = self._find_sounds_in_category(category)

        # Select sound
        sound_path = None
        if sounds:
            sound_path = random.choice(sounds) if random_choice else sounds[0]
        else:
            # Fallback to system sound
            sound_path = self._get_system_sound(category)

        if not sound_path or not sound_path.exists():
            print(f"No sound found for category: {category}", file=sys.stderr)
            return False

        # Play with afplay (macOS)
        cmd = ['afplay', str(sound_path)]

        try:
            if async_mode:
                # Fire and forget
                subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                return True
            else:
                # Wait for completion
                result = subprocess.run(
                    cmd,
                    timeout=10,
                    capture_output=True
                )
                return result.returncode == 0
        except Exception as e:
            print(f"Sound playback error: {e}", file=sys.stderr)
            return False


class AudioNotifier:
    """Main audio notification orchestrator."""

    AUDIO_MODES = {
        'tts_only': 'Voice announcements only',
        'sound_only': 'Sound effects only',
        'mixed': 'Sound effect + voice (recommended)',
        'creative': 'Random fun sounds from library'
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize audio notifier.

        Args:
            config: Configuration dictionary from plugin config
        """
        self.config = config or {}

        # Audio settings
        audio_config = self.config.get('audio', {})
        # Handle legacy boolean config
        if not isinstance(audio_config, dict):
            audio_config = {}
        self.mode = audio_config.get('mode', 'sound_only')

        # Default to plugin's audio directory
        plugin_root = os.environ.get('CLAUDE_PLUGIN_ROOT', '')
        if plugin_root:
            default_audio_path = os.path.join(plugin_root, 'hooks', 'audio')
        else:
            default_audio_path = '~/.claude/audio'
        sound_library = audio_config.get('sound_library', default_audio_path)

        # TTS settings
        tts_config = self.config.get('tts', {})
        # Handle legacy boolean config
        if not isinstance(tts_config, dict):
            tts_config = {}
        timeout = tts_config.get('timeout', 30)
        rate_adjustment = tts_config.get('rate_adjustment', 0)

        # Initialize players
        self.tts = TTSPlayer(timeout=timeout, rate_adjustment=rate_adjustment)
        self.sound = SoundEffectPlayer(sound_library=sound_library)

    def _select_voice_profile(self, context: Dict[str, Any]) -> str:
        """
        Select appropriate voice profile based on context.

        Args:
            context: Context dictionary with event details

        Returns:
            Voice profile key
        """
        # Check for explicit voice profile
        if 'voice_profile' in context:
            return context['voice_profile']

        # Detect from context
        event_type = context.get('event_type', '')
        has_errors = context.get('has_errors', False)
        has_warnings = context.get('has_warnings', False)
        is_success = context.get('is_success', True)

        # Event-specific profiles
        if event_type == 'approval_needed':
            return 'needs_input'
        elif event_type == 'waiting':
            return 'waiting'
        elif event_type == 'code_quality':
            return 'code_quality'

        # Outcome-based profiles
        if has_errors:
            return 'error'
        elif has_warnings:
            return 'warning'
        elif is_success:
            return 'success'

        return 'neutral'

    def _select_sound_category(self, context: Dict[str, Any]) -> str:
        """
        Select appropriate sound category based on context.

        Args:
            context: Context dictionary with event details

        Returns:
            Sound category
        """
        # Check for explicit sound category
        if 'sound_category' in context:
            return context['sound_category']

        # Detect from context
        event_type = context.get('event_type', '')
        has_errors = context.get('has_errors', False)
        is_success = context.get('is_success', True)

        # Event-specific categories
        if event_type == 'approval_needed':
            return 'notify'
        elif event_type == 'waiting':
            return 'waiting'

        # Outcome-based categories
        if has_errors:
            return 'error'
        elif is_success:
            return 'success'

        return 'notify'

    def notify(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        force_mode: Optional[str] = None
    ) -> bool:
        """
        Send audio notification.

        Args:
            message: Message to announce (for TTS)
            context: Context dictionary with event details
            force_mode: Override configured audio mode for this notification

        Returns:
            True if notification was sent successfully
        """
        context = context or {}
        mode = force_mode or self.mode

        # Determine voice and sound
        voice_profile = self._select_voice_profile(context)
        sound_category = self._select_sound_category(context)

        success = False

        # Execute based on mode
        if mode == 'sound_only':
            success = self.sound.play(sound_category)

        elif mode == 'tts_only':
            success = self.tts.speak(message, voice_profile)

        elif mode == 'mixed':
            # Play sound first (quick feedback), then TTS (detailed)
            sound_played = self.sound.play(sound_category, async_mode=True)
            # Small delay to let sound start before TTS
            import time
            time.sleep(0.3)
            tts_spoken = self.tts.speak(message, voice_profile)
            success = sound_played or tts_spoken

        elif mode == 'creative':
            # Random fun sounds, no TTS
            success = self.sound.play(sound_category, random_choice=True)

        return success


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load configuration from file.

    Args:
        config_path: Path to config file (YAML or JSON)

    Returns:
        Configuration dictionary
    """
    if not config_path:
        return {}

    config_file = Path(config_path).expanduser()
    if not config_file.exists():
        return {}

    try:
        # Try loading as JSON first
        with open(config_file) as f:
            return json.load(f)
    except json.JSONDecodeError:
        # Try YAML if available
        try:
            import yaml
            with open(config_file) as f:
                return yaml.safe_load(f) or {}
        except ImportError:
            print("YAML parsing not available, install pyyaml", file=sys.stderr)
            return {}
        except Exception as e:
            print(f"Config load error: {e}", file=sys.stderr)
            return {}


def main():
    """Test the audio notification system."""
    import argparse

    parser = argparse.ArgumentParser(description='Audio notification system for Claude Code')
    parser.add_argument('message', help='Message to announce')
    parser.add_argument('--mode', choices=['tts_only', 'sound_only', 'mixed', 'creative'],
                       default='mixed', help='Audio mode')
    parser.add_argument('--voice', help='Voice profile (success, error, warning, etc.)')
    parser.add_argument('--sound', help='Sound category (success, error, waiting, notify)')
    parser.add_argument('--config', help='Path to config file')

    args = parser.parse_args()

    # Load config or use command-line args
    config = load_config(args.config)
    if not config:
        config = {
            'audio': {'mode': args.mode},
            'tts': {'timeout': 30, 'rate_adjustment': 0}
        }

    # Build context
    context = {}
    if args.voice:
        context['voice_profile'] = args.voice
    if args.sound:
        context['sound_category'] = args.sound

    # Send notification
    notifier = AudioNotifier(config)
    success = notifier.notify(args.message, context)

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
