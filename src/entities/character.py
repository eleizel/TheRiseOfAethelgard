"""Player character entity model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.core.math_utils import calculate_exp_threshold
from src.entities.actor import ActiveStatus, Stats


@dataclass
class Equipment:
    weapon: str | None = None
    armor: str | None = None
    accessory: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "weapon": self.weapon,
            "armor": self.armor,
            "accessory": self.accessory,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Equipment:
        return cls(
            weapon=data.get("weapon"),
            armor=data.get("armor"),
            accessory=data.get("accessory"),
        )


@dataclass
class Character:
    id: str
    name: str
    class_id: str
    level: int = 1
    current_exp: int = 0
    current_hp: int = 100
    current_mp: int = 30
    base_stats: Stats = field(default_factory=Stats)
    equipment: Equipment = field(default_factory=Equipment)
    learned_abilities: list[str] = field(default_factory=list)
    skill_points: int = 0
    statuses: list[ActiveStatus] = field(default_factory=list)

    @property
    def is_alive(self) -> bool:
        return self.current_hp > 0

    @property
    def effective_stats(self) -> Stats:
        """Combine base stats with all equipped items."""
        from src.data.items import ITEM_REGISTRY

        total = self.base_stats
        for item_id in (self.equipment.weapon, self.equipment.armor, self.equipment.accessory):
            if item_id and item_id in ITEM_REGISTRY:
                item_def = ITEM_REGISTRY[item_id]
                if item_def.stat_bonus:
                    total = total.add(item_def.stat_bonus)
        return total

    @property
    def exp_to_next_level(self) -> int:
        return calculate_exp_threshold(self.level)

    def gain_exp(self, amount: int) -> list[int]:
        """Add EXP and return list of levels gained (if any)."""
        if amount <= 0:
            return []

        self.current_exp += amount
        levels_gained: list[int] = []

        while self.current_exp >= self.exp_to_next_level:
            self.current_exp -= self.exp_to_next_level
            self.level += 1
            self.skill_points += 1
            levels_gained.append(self.level)

        return levels_gained

    def heal(self, amount: int) -> int:
        """Restore HP up to max_hp. Returns amount actually healed."""
        effective_max = self.base_stats.max_hp
        old_hp = self.current_hp
        self.current_hp = min(effective_max, self.current_hp + max(0, amount))
        return self.current_hp - old_hp

    def restore_mp(self, amount: int) -> int:
        """Restore MP up to max_mp. Returns amount actually restored."""
        effective_max = self.base_stats.max_mp
        old_mp = self.current_mp
        self.current_mp = min(effective_max, self.current_mp + max(0, amount))
        return self.current_mp - old_mp

    def take_damage(self, amount: int) -> int:
        """Apply damage clamped to 0. Returns damage taken."""
        actual = max(0, min(self.current_hp, amount))
        self.current_hp -= actual
        return actual

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "class_id": self.class_id,
            "level": self.level,
            "current_exp": self.current_exp,
            "current_hp": self.current_hp,
            "current_mp": self.current_mp,
            "base_stats": self.base_stats.to_dict(),
            "equipment": self.equipment.to_dict(),
            "learned_abilities": list(self.learned_abilities),
            "skill_points": self.skill_points,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Character:
        return cls(
            id=data["id"],
            name=data["name"],
            class_id=data["class_id"],
            level=int(data.get("level", 1)),
            current_exp=int(data.get("current_exp", 0)),
            current_hp=int(data.get("current_hp", 100)),
            current_mp=int(data.get("current_mp", 30)),
            base_stats=Stats.from_dict(data.get("base_stats", {})),
            equipment=Equipment.from_dict(data.get("equipment", {})),
            learned_abilities=list(data.get("learned_abilities", [])),
            skill_points=int(data.get("skill_points", 0)),
        )
