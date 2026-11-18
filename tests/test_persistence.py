"""Unit tests for SaveManager and serialization."""

from src.core.persistence import MemoryStorageBackend
from src.core.save_manager import SaveManager
from src.core.session import GameSession


def test_session_save_and_load_memory():
    backend = MemoryStorageBackend()
    manager = SaveManager(backend=backend)

    session = GameSession(save_manager=manager, seed=42)
    session.initialize_new_game()
    session.party.gold = 550
    session.player_x = 24
    session.player_y = 18

    # Save to slot 1
    assert session.save_game(slot_id=1) is True

    # Check slot summary
    summary = manager.get_slot_summary(slot_id=1)
    assert summary.exists is True
    assert summary.party_leader_name == "Rowan"
    assert summary.party_count == 2

    # Restore in new session
    new_session = GameSession(save_manager=manager)
    assert new_session.load_game(slot_id=1) is True
    assert new_session.party.gold == 550
    assert new_session.player_x == 24
    assert new_session.player_y == 18
    assert new_session.party.active_members[0].name == "Rowan"


def test_corrupt_save_handling():
    backend = MemoryStorageBackend()
    manager = SaveManager(backend=backend)
    backend.save("save_slot_1", "{invalid json garbage}")

    loaded = manager.load_game(slot_id=1)
    assert loaded is None
    assert manager.last_load_error is not None


def test_load_slot_picker_and_exact_player_position_restore():
    import os

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import pygame

    pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((1280, 720))

    from src.core.fsm import GameMode
    from src.frontends.pygame_ce.ui_manager import GameUIManager
    from src.frontends.pygame_ce.views.exploration_view import ExplorationView
    from src.frontends.pygame_ce.views.title_view import TitleView

    backend = MemoryStorageBackend()
    manager = SaveManager(backend=backend)

    # Save in slot 2 while exploring briarwood_verge at exact pixel coords
    s1 = GameSession(save_manager=manager, seed=42)
    s1.initialize_new_game()
    s1.party.gold = 777
    s1.map_id = "briarwood_verge"
    s1.player_x = 12
    s1.player_y = 21
    s1.player_pixel_x = 412.5
    s1.player_pixel_y = 687.25
    assert s1.save_game(slot_id=2) is True

    # Fresh session starts at Title with ExplorationView initially on oakhaven_village
    s2 = GameSession(save_manager=manager, seed=1)
    ui_mgr = GameUIManager((1280, 720))
    ev = ExplorationView(s2, ui_manager=ui_mgr)
    tv = TitleView(s2, ui_manager=ui_mgr)
    tv.on_enter()

    # Select "Continue" -> opens slot picker -> pick Slot 2 -> loads slot 2
    tv.selected_index = tv.options.index("Continue")
    tv._choose_option()
    assert tv.load_slot_open is True
    tv.load_slot_index = 1  # Slot 2
    tv._confirm_load_slot()

    assert tv.load_slot_open is False
    assert s2.current_mode == GameMode.EXPLORATION
    assert s2.party.gold == 777

    # Entering ExplorationView syncs map & exact pixel coords instead of Rowan's doorstep
    ev.on_enter()
    assert ev.current_map.id == "briarwood_verge"
    assert (ev.player_x, ev.player_y) == (412.5, 687.25)
    ev.on_exit()
