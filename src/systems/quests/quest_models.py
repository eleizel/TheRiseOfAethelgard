"""Domain models for declarative Main and Side quests."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class QuestCategory(Enum):
    """Distinguishes Main Story quests from optional Side quests."""

    MAIN = auto()
    SIDE = auto()


class ObjectiveType(Enum):
    """Supported objective triggers for sequential quest steps."""

    TALK_TO_NPC = auto()
    DIALOGUE_STARTED = auto()
    DIALOGUE_CHOICE = auto()
    REACH_PROXIMITY = auto()
    ENTER_MAP = auto()
    KILL_ENEMY = auto()
    COLLECT_ITEM = auto()
    FLAG_SET = auto()


@dataclass(frozen=True)
class QuestStep:
    """Single sequential step inside a quest."""

    id: str
    description: str
    objective_type: ObjectiveType
    target_id: str
    required_count: int = 1
    map_id: str | None = None
    node_id: str | None = None
    choice_index: int | None = None
    proximity_radius: float = 90.0
    target_pos: tuple[float, float] | None = None


@dataclass(frozen=True)
class QuestReward:
    """Rewards auto-claimed upon completing the final step of a quest."""

    exp: int = 0
    gold: int = 0
    items: dict[str, int] = field(default_factory=dict)
    flags: tuple[str, ...] = ()

    def summary_text(self) -> str:
        parts: list[str] = []
        if self.exp > 0:
            parts.append(f"{self.exp} EXP")
        if self.gold > 0:
            parts.append(f"{self.gold} Gold")
        for item_id, qty in self.items.items():
            label = item_id.replace("_", " ").title()
            parts.append(f"{qty}x {label}")
        return ", ".join(parts)


@dataclass(frozen=True)
class QuestDefinition:
    """Declarative blueprint for a Main or Side quest."""

    id: str
    title: str
    category: QuestCategory
    description: str
    steps: tuple[QuestStep, ...]
    reward: QuestReward = field(default_factory=QuestReward)
    auto_start: bool = False
    prereq_quests: tuple[str, ...] = ()
    unlock_proximity: tuple[str, str, float] | None = None
    unlock_dialogue_id: str | None = None


@dataclass
class QuestProgress:
    """Runtime progress for an active quest."""

    quest_id: str
    step_index: int = 0
    current_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "quest_id": self.quest_id,
            "step_index": self.step_index,
            "current_count": self.current_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QuestProgress:
        return cls(
            quest_id=str(data.get("quest_id", "")),
            step_index=int(data.get("step_index", 0)),
            current_count=int(data.get("current_count", 0)),
        )
