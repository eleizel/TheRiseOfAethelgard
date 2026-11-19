"""Base actor models, stats, and status conditions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class StatusType(Enum):
    """Core status conditions."""
    POISON = auto()
    BLEED = auto()
    BURN = auto()
    STUN = auto()
    BLIND = auto()
    VULNERABLE = auto()
    WEAKEN = auto()
    REGEN = auto()
    ATTACK_UP = auto()
    DEFENSE_UP = auto()
    SPEED_UP = auto()
    THORNS = auto()
    SHIELD = auto()
    CRIT_UP = auto()
    MAGIC_DEFENSE_UP = auto()


NEGATIVE_STATUSES: frozenset[StatusType] = frozenset(
    {
        StatusType.POISON,
        StatusType.BLEED,
        StatusType.BURN,
        StatusType.STUN,
        StatusType.BLIND,
        StatusType.VULNERABLE,
        StatusType.WEAKEN,
    }
)

_STATUS_ALIASES: dict[str, StatusType] = {
    "armor_break": StatusType.VULNERABLE,
    "fortify": StatusType.DEFENSE_UP,
    "haste": StatusType.SPEED_UP,
    "regeneration": StatusType.REGEN,
    "mdef_up": StatusType.MAGIC_DEFENSE_UP,
    "magic_ward": StatusType.MAGIC_DEFENSE_UP,
    "retaliate": StatusType.THORNS,
}


def resolve_status_type(raw: str | None) -> StatusType | None:
    """Resolve an ability status_inflict string (any case or alias) to StatusType."""
    if not raw:
        return None
    key = raw.strip().lower()
    if key in _STATUS_ALIASES:
        return _STATUS_ALIASES[key]
    try:
        return StatusType[key.upper()]
    except KeyError:
        return None


@dataclass
class ActiveStatus:
    status: StatusType
    duration: int
    magnitude: int = 0


@dataclass
class Stats:
    """Core RPG attributes."""
    max_hp: int = 0
    max_mp: int = 0
    attack: int = 0
    defense: int = 0
    magic_attack: int = 0
    magic_defense: int = 0
    speed: int = 0
    crit_chance: float = 0.0

    def add(self, other: Stats) -> Stats:
        """Combine two stats objects (e.g. base stats + equipment bonuses)."""
        return Stats(
            max_hp=self.max_hp + other.max_hp,
            max_mp=self.max_mp + other.max_mp,
            attack=self.attack + other.attack,
            defense=self.defense + other.defense,
            magic_attack=self.magic_attack + other.magic_attack,
            magic_defense=self.magic_defense + other.magic_defense,
            speed=self.speed + other.speed,
            crit_chance=min(1.0, self.crit_chance + other.crit_chance),
        )

    def to_dict(self) -> dict:
        return {
            "max_hp": self.max_hp,
            "max_mp": self.max_mp,
            "attack": self.attack,
            "defense": self.defense,
            "magic_attack": self.magic_attack,
            "magic_defense": self.magic_defense,
            "speed": self.speed,
            "crit_chance": self.crit_chance,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Stats:
        return cls(
            max_hp=int(data.get("max_hp", 0)),
            max_mp=int(data.get("max_mp", 0)),
            attack=int(data.get("attack", 0)),
            defense=int(data.get("defense", 0)),
            magic_attack=int(data.get("magic_attack", 0)),
            magic_defense=int(data.get("magic_defense", 0)),
            speed=int(data.get("speed", 0)),
            crit_chance=float(data.get("crit_chance", 0.0)),
        )
