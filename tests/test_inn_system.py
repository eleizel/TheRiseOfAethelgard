"""Unit and integration tests for Inn Rest and Party Management systems."""

from __future__ import annotations

from src.core.session import GameSession
from src.frontends.pygame_ce.views.dialogue_view import DialogueView


def test_inn_rest_success() -> None:
    session = GameSession()
    session.initialize_new_game()
    session.party.gold = 100

    # Damage all active and reserve members
    for member in session.party.active_members + session.party.reserve_members:
        member.current_hp = 1
        member.current_mp = 0

    success = session.rest_at_inn(50)
    assert success is True
    assert session.party.gold == 50

    for member in session.party.active_members + session.party.reserve_members:
        assert member.current_hp == member.base_stats.max_hp
        assert member.current_mp == member.base_stats.max_mp


def test_inn_rest_insufficient_gold() -> None:
    session = GameSession()
    session.initialize_new_game()
    session.party.gold = 25

    success = session.rest_at_inn(50)
    assert success is False
    assert session.party.gold == 25


def test_inn_dialogue_integration() -> None:
    session = GameSession()
    session.initialize_new_game()
    session.party.gold = 100
    dialogue_view = DialogueView(session)
    dialogue_view.start_dialogue("oakhaven_inn_open")
    assert dialogue_view.current_node is not None
    assert dialogue_view.current_node.id == "inn_welcome"
