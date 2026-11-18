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
