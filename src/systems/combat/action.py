"""Combat action definitions and types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class ActionType(Enum):
    ATTACK = auto()
    ABILITY = auto()
    ITEM = auto()
    DEFEND = auto()
    FLEE = auto()


@dataclass
class CombatAction:
    """An action queued for resolution in the combat round."""
    actor_id: str
    is_player: bool
    action_type: ActionType
    target_id: str | None = None
    ability_id: str | None = None
    item_id: str | None = None
    speed_initiative: float = 10.0
