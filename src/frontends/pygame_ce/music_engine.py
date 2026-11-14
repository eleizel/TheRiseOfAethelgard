"""Dynamic Music Engine for The Rise of Aethelgard Pygame-CE frontend."""

from __future__ import annotations

import json
import logging
import random
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Any, Final

import pygame

from src.core.fsm import GameMode
from src.core.persistence import FileStorageBackend, StorageBackend
from src.entities.enemy import EnemyTier
from src.frontends.pygame_ce.audio_track_loader import (
    AudioTrackLoader,
    get_default_music_dir,
    is_audio_available,
)

logger = logging.getLogger(__name__)


class MusicContext(Enum):
    """Contexts determining background music tracks."""
    WELCOME = auto()      # tracks: ["welcome_01", "welcome_02"]
    EXPLORATION = auto()  # tracks: ["exploration_01", "exploration_02"]
    COMBAT = auto()       # tracks: ["combat_01", "combat_02"]
    BOSS = auto()         # tracks: ["boss_01", "boss_02"]


CONTEXT_TRACKS: Final[dict[MusicContext, tuple[str, ...]]] = {
    MusicContext.WELCOME: ("welcome_01", "welcome_02"),
    MusicContext.EXPLORATION: ("exploration_01", "exploration_02"),
    MusicContext.COMBAT: ("combat_01", "combat_02"),
    MusicContext.BOSS: ("boss_01", "boss_02"),
}

DEFAULT_SETTINGS_KEY: Final[str] = "the_rise_of_aethelgard_settings"
SETTINGS_SCHEMA_VERSION: Final[int] = 1
DEFAULT_FADE_MS: Final[int] = 500


@dataclass
class AudioSettingsData:
    version: int = SETTINGS_SCHEMA_VERSION
    music_muted: bool = False
    music_volume: float = 1.0
    sfx_muted: bool = False
    sfx_volume: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": int(self.version),
            "music_muted": bool(self.music_muted),
            "music_volume": float(max(0.0, min(1.0, self.music_volume))),
            "sfx_muted": bool(self.sfx_muted),
            "sfx_volume": float(max(0.0, min(1.0, self.sfx_volume))),
        }

    @classmethod
    def from_dict(cls, data: Any) -> AudioSettingsData:
        if not isinstance(data, dict):
            return cls()
        return cls(
            version=int(data.get("version", SETTINGS_SCHEMA_VERSION)),
            music_muted=bool(data.get("music_muted", False)),
            music_volume=float(data.get("music_volume", 1.0)),
            sfx_muted=bool(data.get("sfx_muted", False)),
            sfx_volume=float(data.get("sfx_volume", 1.0)),
        )


class AudioSettingsManager:
    """Manages audio persistence."""

    def __init__(self, backend: StorageBackend | None = None) -> None:
        self.backend = backend or FileStorageBackend()
        self.settings: AudioSettingsData = AudioSettingsData()
        self.load()

    def load(self) -> None:
        raw = self.backend.load(DEFAULT_SETTINGS_KEY)
        if raw:
            try:
                data = json.loads(raw)
                self.settings = AudioSettingsData.from_dict(data)
            except Exception:
                self.settings = AudioSettingsData()

    def save(self) -> None:
        try:
            payload = json.dumps(self.settings.to_dict())
            self.backend.save(DEFAULT_SETTINGS_KEY, payload)
        except Exception as exc:
            logger.warning("Failed to persist audio settings: %s", exc)

    def is_music_muted(self) -> bool:
        return self.settings.music_muted

    def set_music_muted(self, muted: bool) -> None:
        self.settings.music_muted = muted
        self.save()

    def get_music_volume(self) -> float:
        return self.settings.music_volume

    def set_music_volume(self, volume: float) -> None:
        self.settings.music_volume = max(0.0, min(1.0, volume))
        self.save()


class DynamicMusicEngine:
    """Adaptive music engine controlling track selection and volume transitions."""

    def __init__(
        self,
        settings_manager: AudioSettingsManager | None = None,
        assets_dir: Path | str | None = None,
        loader: AudioTrackLoader | None = None,
    ) -> None:
        self.settings_manager = settings_manager or AudioSettingsManager()
        self.loader = loader or AudioTrackLoader(music_dir=assets_dir or get_default_music_dir())
        self.current_context: MusicContext | None = None
        self.current_track: str | None = None
        self._fade_ms = DEFAULT_FADE_MS

    def set_context(self, context: MusicContext, force_restart: bool = False) -> None:
        """Switch audio context, picking a random track from the context pool."""
        if self.current_context == context and not force_restart:
            return

        self.current_context = context
        tracks = CONTEXT_TRACKS.get(context, ())
        if not tracks:
            self.stop()
            return

        track_name = random.choice(tracks)
        self.play_track(track_name)

    def play_track(self, track_name: str) -> None:
        """Play a specific track with fade transition."""
        self.current_track = track_name
        if self.settings_manager.is_music_muted() or not is_audio_available():
            return

        if self.loader.load_track(track_name):
            try:
                pygame.mixer.music.set_volume(self.settings_manager.get_music_volume())
                pygame.mixer.music.play(-1, fade_ms=self._fade_ms)
            except Exception as exc:
                logger.warning("Failed to play audio track %s: %s", track_name, exc)

    def stop(self) -> None:
        if is_audio_available():
            try:
                pygame.mixer.music.fadeout(self._fade_ms)
            except Exception:
                pass
        self.current_context = None
        self.current_track = None

    def toggle_mute(self) -> bool:
        new_muted = not self.settings_manager.is_music_muted()
        self.set_muted(new_muted)
        return new_muted

    def set_muted(self, muted: bool) -> None:
        self.settings_manager.set_music_muted(muted)
        if not is_audio_available():
            return

        if muted:
            pygame.mixer.music.set_volume(0.0)
        else:
            pygame.mixer.music.set_volume(self.settings_manager.get_music_volume())
            if self.current_track and not pygame.mixer.music.get_busy():
                self.play_track(self.current_track)


def resolve_music_context(mode: GameMode, enemy_tier: EnemyTier | None = None) -> MusicContext:
    """Resolve active game mode into the appropriate MusicContext."""
    if mode in (GameMode.TITLE,):
        return MusicContext.WELCOME
    elif mode in (GameMode.EXPLORATION, GameMode.MENU, GameMode.SHOP, GameMode.DIALOGUE):
        return MusicContext.EXPLORATION
    elif mode == GameMode.COMBAT:
        if enemy_tier in (EnemyTier.BOSS, EnemyTier.ELITE):
            return MusicContext.BOSS
        return MusicContext.COMBAT
    return MusicContext.EXPLORATION
