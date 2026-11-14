"""Unit tests for DynamicMusicEngine, AudioSettingsManager, and context resolution."""

from src.core.fsm import GameMode
from src.core.persistence import MemoryStorageBackend
from src.entities.enemy import EnemyTier
from src.frontends.pygame_ce.music_engine import (
    AudioSettingsManager,
    DynamicMusicEngine,
    MusicContext,
    resolve_music_context,
)


def test_audio_settings_manager_persistence():
    backend = MemoryStorageBackend()
    mgr = AudioSettingsManager(backend=backend)

    assert mgr.is_music_muted() is False
    mgr.set_music_muted(True)
    assert mgr.is_music_muted() is True

    # Re-instantiate from same backend
    mgr2 = AudioSettingsManager(backend=backend)
    assert mgr2.is_music_muted() is True


def test_resolve_music_context():
    assert resolve_music_context(GameMode.TITLE) == MusicContext.WELCOME
    assert resolve_music_context(GameMode.EXPLORATION) == MusicContext.EXPLORATION
    assert resolve_music_context(GameMode.COMBAT, EnemyTier.MINION) == MusicContext.COMBAT
    assert resolve_music_context(GameMode.COMBAT, EnemyTier.BOSS) == MusicContext.BOSS
    assert resolve_music_context(GameMode.COMBAT, EnemyTier.ELITE) == MusicContext.BOSS


def test_dynamic_music_engine_context_change():
    backend = MemoryStorageBackend()
    settings = AudioSettingsManager(backend=backend)
    engine = DynamicMusicEngine(settings_manager=settings)

    engine.set_context(MusicContext.EXPLORATION)
    assert engine.current_context == MusicContext.EXPLORATION
    assert engine.current_track in ("exploration_01", "exploration_02")

    engine.set_context(MusicContext.COMBAT)
    assert engine.current_context == MusicContext.COMBAT
    assert engine.current_track in ("combat_01", "combat_02")
