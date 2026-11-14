"""Party manager managing active 4-member squad and reserve companions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.entities.character import Character

MAX_ACTIVE_PARTY_SIZE = 4


@dataclass
class Party:
    active_members: list[Character] = field(default_factory=list)
    reserve_members: list[Character] = field(default_factory=list)
    inventory: dict[str, int] = field(default_factory=dict)
    gold: int = 100
    quest_flags: dict[str, Any] = field(default_factory=dict)

    @property
    def is_party_defeated(self) -> bool:
        """True if all active characters have 0 HP."""
        if not self.active_members:
            return True
        return all(not member.is_alive for member in self.active_members)

    @property
    def alive_active_members(self) -> list[Character]:
        return [m for m in self.active_members if m.is_alive]

    def add_character(self, character: Character) -> bool:
        """Add character to active squad if space permits (<4), otherwise to reserve."""
        # Ensure no duplicate ID
        for m in self.active_members + self.reserve_members:
            if m.id == character.id:
                return False

        if len(self.active_members) < MAX_ACTIVE_PARTY_SIZE:
            self.active_members.append(character)
        else:
            self.reserve_members.append(character)
        return True

    def swap_active_with_reserve(self, active_idx: int, reserve_idx: int) -> bool:
        """Swap an active party member (slots 1..3) with a reserve member. Slot 0 is locked."""
        if active_idx == 0:
            return False
        if not (0 <= active_idx < len(self.active_members)):
            return False
        if not (0 <= reserve_idx < len(self.reserve_members)):
            return False

        active_char = self.active_members[active_idx]
        reserve_char = self.reserve_members[reserve_idx]

        self.active_members[active_idx] = reserve_char
        self.reserve_members[reserve_idx] = active_char
        return True

    def reorder_active(self, idx_a: int, idx_b: int) -> bool:
        """Swap two active party slots (slots 1..3). Slot 0 is permanently locked."""
        n = len(self.active_members)
        if not (1 <= idx_a < n and 1 <= idx_b < n) or idx_a == idx_b:
            return False
        self.active_members[idx_a], self.active_members[idx_b] = (
            self.active_members[idx_b],
            self.active_members[idx_a],
        )
        return True

    def bench_active(self, active_idx: int) -> bool:
        """Move an active member (slots 1..3) to reserve, keeping at least 1 active."""
        if active_idx <= 0 or active_idx >= len(self.active_members):
            return False
        if len(self.active_members) <= 1:
            return False
        char = self.active_members.pop(active_idx)
        self.reserve_members.append(char)
        return True

    def deploy_reserve(self, reserve_idx: int) -> bool:
        """Move a reserve member into an open active slot if party size < MAX_ACTIVE_PARTY_SIZE."""
        if len(self.active_members) >= MAX_ACTIVE_PARTY_SIZE:
            return False
        if not (0 <= reserve_idx < len(self.reserve_members)):
            return False
        char = self.reserve_members.pop(reserve_idx)
        self.active_members.append(char)
        return True

    def add_item(self, item_id: str, quantity: int = 1) -> None:
        if quantity <= 0:
            return
        self.inventory[item_id] = self.inventory.get(item_id, 0) + quantity

    def remove_item(self, item_id: str, quantity: int = 1) -> bool:
        if quantity <= 0:
            return False
        current = self.inventory.get(item_id, 0)
        if current < quantity:
            return False
        if current == quantity:
            del self.inventory[item_id]
        else:
            self.inventory[item_id] -= quantity
        return True

    def has_item(self, item_id: str, quantity: int = 1) -> bool:
        return self.inventory.get(item_id, 0) >= quantity

    def to_dict(self) -> dict[str, Any]:
        return {
            "active_members": [m.to_dict() for m in self.active_members],
            "reserve_members": [m.to_dict() for m in self.reserve_members],
            "inventory": dict(self.inventory),
            "gold": self.gold,
            "quest_flags": dict(self.quest_flags),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Party:
        party = cls(
            gold=int(data.get("gold", 100)),
            inventory=dict(data.get("inventory", {})),
            quest_flags=dict(data.get("quest_flags", {})),
        )
        party.active_members = [
            Character.from_dict(m) for m in data.get("active_members", [])
        ]
        party.reserve_members = [
            Character.from_dict(m) for m in data.get("reserve_members", [])
        ]
        return party
