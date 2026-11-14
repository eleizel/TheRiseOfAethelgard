"""Unit tests for StateMachine and game modes."""

from src.core.fsm import GameMode
from src.core.session import GameSession


def test_state_machine_transitions():
    session = GameSession()
    fsm = session.fsm

    assert fsm.current_mode == GameMode.TITLE

    # Transition to exploration
    assert fsm.transition_to(GameMode.EXPLORATION, session) is True
    assert fsm.current_mode == GameMode.EXPLORATION

    # Transition to combat
    assert fsm.transition_to(GameMode.COMBAT, session) is True
    assert fsm.current_mode == GameMode.COMBAT

    # Combat cannot directly transition to title
    assert fsm.transition_to(GameMode.TITLE, session) is False
    assert fsm.current_mode == GameMode.COMBAT

    # Combat can transition to victory or exploration
    assert fsm.transition_to(GameMode.VICTORY, session) is True
    assert fsm.current_mode == GameMode.VICTORY
