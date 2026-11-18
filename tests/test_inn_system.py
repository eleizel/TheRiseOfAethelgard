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
        assert member.current_hp == member.effective_stats.max_hp
        assert member.current_mp == member.effective_stats.max_mp


def test_inn_rest_insufficient_gold() -> None:
    session = GameSession()
    session.initialize_new_game()
    session.party.gold = 25

    success = session.rest_at_inn(50)
    assert success is False
    assert session.party.gold == 25


def test_inn_dialogue_integration() -> None:
    import os

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import pygame

    pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((640, 360))

    from src.core.fsm import GameMode

    session = GameSession()
    session.initialize_new_game()
    session.transition_to(GameMode.EXPLORATION)
    session.transition_to(GameMode.DIALOGUE)
    session.party.gold = 100
    for member in session.party.active_members:
        member.current_hp = 1

    dialogue_view = DialogueView(session)
    dialogue_view.start_dialogue("oakhaven_inn_open")
    assert dialogue_view.current_node is not None
    assert dialogue_view.current_node.id == "inn_welcome"

    # Rest success via action trigger
    dialogue_view._advance_to_node("inn_rest_attempt")
    dialogue_view._advance_node()
    assert dialogue_view.current_node is not None
    assert dialogue_view.current_node.id == "inn_rest_success"
    assert session.party.gold == 50
    assert all(m.current_hp == m.effective_stats.max_hp for m in session.party.active_members)

    # Rest failure when gold < 50
    session.party.gold = 10
    dialogue_view._advance_to_node("inn_rest_attempt")
    dialogue_view._advance_node()
    assert dialogue_view.current_node is not None
    assert dialogue_view.current_node.id == "inn_rest_failure"
    assert session.party.gold == 10

    # Party management transitions to GameMode.PARTY
    dialogue_view._advance_to_node("inn_party_mgmt")
    dialogue_view._advance_node()
    assert session.current_mode == GameMode.PARTY
