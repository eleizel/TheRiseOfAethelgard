"""Domain events and EventBus for reactive decoupling.

Allows domain systems (Combat, Party, Exploration, Dialogue) to emit signals
without depending on Pygame, hardware, audio drivers, or UI views.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, TypeVar

T = TypeVar("T", bound="DomainEvent")


class AudioCue(Enum):
    """Platform-agnostic sound effect trigger."""
    HIT = auto()
    CRIT = auto()
    HEAL = auto()
    SPELL_CAST = auto()
    DEFEND = auto()
    CLICK = auto()
    SELECT = auto()
    CANCEL = auto()
    VICTORY = auto()
    DEFEAT = auto()
    CHEST = auto()
    DOOR = auto()
    FOOTSTEP = auto()
    LEVEL_UP = auto()
    DIALOGUE_ADVANCE = auto()


@dataclass(frozen=True)
class DomainEvent:
    """Base marker class for all domain events."""
    pass


@dataclass(frozen=True)
class AudioCueEvent(DomainEvent):
    """Audio cue requested by domain logic."""
    cue: AudioCue


@dataclass(frozen=True)
class DamageDealtEvent(DomainEvent):
    """Event emitted whenever damage is resolved in combat."""
    source_id: str
    target_id: str
    amount: int
    is_crit: bool = False
    element: str = "physical"


@dataclass(frozen=True)
class HealthRestoredEvent(DomainEvent):
    """Event emitted whenever an actor recovers HP."""
    target_id: str
    amount: int
    current_hp: int = 0
    max_hp: int = 0


@dataclass(frozen=True)
class StatusAppliedEvent(DomainEvent):
    """Event emitted when a status effect is applied to an actor."""
    target_id: str
    status_id: str
    status_name: str = ""
    duration: int = 0


@dataclass(frozen=True)
class PartyMemberDownedEvent(DomainEvent):
    """Event emitted when a party member reaches 0 HP."""
    character_id: str
    character_name: str


@dataclass(frozen=True)
class StateChangedEvent(DomainEvent):
    """Event emitted on FSM state transition."""
    previous_mode: str
    new_mode: str


@dataclass(frozen=True)
class QuestUpdatedEvent(DomainEvent):
    """Event emitted when a quest starts or advances to a new step."""
    quest_id: str
    quest_title: str
    step_description: str
    is_new: bool = False


@dataclass(frozen=True)
class QuestCompletedEvent(DomainEvent):
    """Event emitted when a quest is completed and rewards are claimed."""
    quest_id: str
    quest_title: str
    reward_summary: str = ""


class EventBus:
    """Drainable domain event queue with immediate subscriptions."""

    def __init__(self) -> None:
        self._queue: list[DomainEvent] = []
        self._subscribers: dict[type, list[Callable[[Any], None]]] = {}

    def emit(self, event: DomainEvent) -> None:
        """Enqueue an event and notify immediate subscribers."""
        self._queue.append(event)
        handlers = self._subscribers.get(type(event), [])
        for handler in handlers:
            handler(event)

    def emit_audio(self, cue: AudioCue) -> None:
        """Convenience helper to emit an AudioCueEvent."""
        self.emit(AudioCueEvent(cue=cue))

    def drain(self) -> list[DomainEvent]:
        """Drain and return all queued events since last drain."""
        events = list(self._queue)
        self._queue.clear()
        return events

    def subscribe(self, event_type: type[T], handler: Callable[[T], None]) -> None:
        """Register a reactive listener for an event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: type[T], handler: Callable[[T], None]) -> None:
        """Remove a previously registered listener."""
        if event_type in self._subscribers and handler in self._subscribers[event_type]:
            self._subscribers[event_type].remove(handler)

    def clear(self) -> None:
        """Clear queued events without dispatching."""
        self._queue.clear()

    def __deepcopy__(self, memo: dict) -> EventBus:
        """Create an isolated EventBus copy."""
        bus = EventBus()
        memo[id(self)] = bus
        return bus


class CombatLogEntry(str):
    """String carrying structured metadata for UI views."""

    def __new__(
        cls,
        text: str,
        key: str = "",
        params: dict[str, Any] | None = None,
        category: str = "combat",
    ) -> CombatLogEntry:
        instance = super().__new__(cls, text)
        instance.key = key
        instance.params = params or {}
        instance.category = category
        return instance
