"""Finite State Machine (FSM) for game flow and mode transitions."""

from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.session import GameSession


class GameMode(Enum):
    """Enumeration of all operational top-level game states."""
    TITLE = auto()
    EXPLORATION = auto()
    COMBAT = auto()
    DIALOGUE = auto()
    MENU = auto()
    PARTY = auto()
    SHOP = auto()
    GAME_OVER = auto()
    VICTORY = auto()


class ModeState:
    """Base class for all discrete operational states."""

    def __init__(self, mode: GameMode) -> None:
        self.mode = mode

    def can_open_menu(self, session: GameSession) -> bool:
        """Whether player can open the camp/pause menu."""
        return False

    def can_transition_to(self, target_mode: GameMode) -> bool:
        """Whether a direct transition from this state to target_mode is permitted."""
        return True

    def on_enter(self, session: GameSession, previous_mode: GameMode) -> None:
        """Hook called immediately upon entering this state."""
        pass

    def on_exit(self, session: GameSession, next_mode: GameMode) -> None:
        """Hook called immediately before exiting this state."""
        pass


class TitleState(ModeState):
    def can_open_menu(self, session: GameSession) -> bool:
        return False


class ExplorationState(ModeState):
    def can_open_menu(self, session: GameSession) -> bool:
        return True


class CombatState(ModeState):
    def can_open_menu(self, session: GameSession) -> bool:
        return False

    def can_transition_to(self, target_mode: GameMode) -> bool:
        # Can transition back to exploration, or to game over, or to victory
        return target_mode in {GameMode.EXPLORATION, GameMode.GAME_OVER, GameMode.VICTORY}


class DialogueState(ModeState):
    def can_open_menu(self, session: GameSession) -> bool:
        return False

    def can_transition_to(self, target_mode: GameMode) -> bool:
        return target_mode in {GameMode.EXPLORATION, GameMode.COMBAT, GameMode.PARTY}


class MenuState(ModeState):
    def can_open_menu(self, session: GameSession) -> bool:
        return True

    def can_transition_to(self, target_mode: GameMode) -> bool:
        return target_mode in {GameMode.EXPLORATION, GameMode.TITLE}


class PartyState(ModeState):
    def can_open_menu(self, session: GameSession) -> bool:
        return False

    def can_transition_to(self, target_mode: GameMode) -> bool:
        return target_mode in {GameMode.EXPLORATION, GameMode.DIALOGUE}


class ShopState(ModeState):
    def can_open_menu(self, session: GameSession) -> bool:
        return False

    def can_transition_to(self, target_mode: GameMode) -> bool:
        return target_mode in {GameMode.EXPLORATION}


class GameOverState(ModeState):
    def can_open_menu(self, session: GameSession) -> bool:
        return False

    def can_transition_to(self, target_mode: GameMode) -> bool:
        return target_mode in {GameMode.TITLE, GameMode.EXPLORATION}


class VictoryState(ModeState):
    def can_open_menu(self, session: GameSession) -> bool:
        return False

    def can_transition_to(self, target_mode: GameMode) -> bool:
        return target_mode in {GameMode.EXPLORATION, GameMode.TITLE}


class StateMachine:
    """Manages active mode state and validated lifecycle transitions."""

    def __init__(self, initial_mode: GameMode = GameMode.TITLE) -> None:
        self._states: dict[GameMode, ModeState] = {
            GameMode.TITLE: TitleState(GameMode.TITLE),
            GameMode.EXPLORATION: ExplorationState(GameMode.EXPLORATION),
            GameMode.COMBAT: CombatState(GameMode.COMBAT),
            GameMode.DIALOGUE: DialogueState(GameMode.DIALOGUE),
            GameMode.MENU: MenuState(GameMode.MENU),
            GameMode.PARTY: PartyState(GameMode.PARTY),
            GameMode.SHOP: ShopState(GameMode.SHOP),
            GameMode.GAME_OVER: GameOverState(GameMode.GAME_OVER),
            GameMode.VICTORY: VictoryState(GameMode.VICTORY),
        }
        self._current_mode = initial_mode
        self._previous_mode = initial_mode

    @property
    def current_mode(self) -> GameMode:
        return self._current_mode

    @property
    def previous_mode(self) -> GameMode:
        return self._previous_mode

    @property
    def current_state(self) -> ModeState:
        return self._states[self._current_mode]

    def transition_to(self, target_mode: GameMode, session: GameSession) -> bool:
        """Attempt to transition to target_mode. Returns True if transition succeeded."""
        if target_mode == self._current_mode:
            return True

        if not self.current_state.can_transition_to(target_mode):
            return False

        old_state = self.current_state
        old_mode = self._current_mode

        old_state.on_exit(session, target_mode)
        self._previous_mode = old_mode
        self._current_mode = target_mode
        self.current_state.on_enter(session, old_mode)
        return True
