"""Enemy entity model for combat encounters."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from src.entities.actor import ActiveStatus, Stats


class EnemyTier(Enum):
    MINION = auto()
    ELITE = auto()
    BOSS = auto()


@dataclass
class Enemy:
    id: str
    name: str
    tier: EnemyTier = EnemyTier.MINION
    level: int = 1
    current_hp: int = 50
    stats: Stats = field(default_factory=Stats)
    weaknesses: list[str] = field(default_factory=list)
    resistances: list[str] = field(default_factory=list)
    abilities: list[str] = field(default_factory=list)
    exp_reward: int = 25
    gold_reward: int = 15
    loot_drops: list[tuple[str, float]] = field(default_factory=list)  # (item_id, chance 0.0-1.0)
    statuses: list[ActiveStatus] = field(default_factory=list)
    sprite_id: str = ""

    @property
    def is_alive(self) -> bool:
        return self.current_hp > 0

    def take_damage(self, amount: int) -> int:
        actual = max(0, min(self.current_hp, amount))
        self.current_hp -= actual
        return actual

    def heal(self, amount: int) -> int:
        old_hp = self.current_hp
        self.current_hp = min(self.stats.max_hp, self.current_hp + max(0, amount))
        return self.current_hp - old_hp

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "tier": self.tier.name,
            "level": self.level,
            "current_hp": self.current_hp,
            "stats": self.stats.to_dict(),
            "weaknesses": list(self.weaknesses),
            "resistances": list(self.resistances),
            "abilities": list(self.abilities),
            "exp_reward": self.exp_reward,
            "gold_reward": self.gold_reward,
            "sprite_id": self.sprite_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Enemy:
        tier_str = data.get("tier", "MINION")
        tier = EnemyTier[tier_str] if tier_str in EnemyTier.__members__ else EnemyTier.MINION
        return cls(
            id=data["id"],
            name=data["name"],
            tier=tier,
            level=int(data.get("level", 1)),
            current_hp=int(data.get("current_hp", 50)),
            stats=Stats.from_dict(data.get("stats", {})),
            weaknesses=list(data.get("weaknesses", [])),
            resistances=list(data.get("resistances", [])),
            abilities=list(data.get("abilities", [])),
            exp_reward=int(data.get("exp_reward", 25)),
            gold_reward=int(data.get("gold_reward", 15)),
            sprite_id=data.get("sprite_id", ""),
        )
