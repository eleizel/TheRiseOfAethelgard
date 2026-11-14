"""Skill tree domain models, prerequisite validation, and progression unlocking."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from src.entities.actor import Stats
from src.entities.character import Character


class NodeType(Enum):
    ABILITY = auto()
    STAT_BOOST = auto()


@dataclass(frozen=True)
class SkillNode:
    """Individual talent node within an archetype skill tree."""
    id: str
    name: str
    description: str
    cost_sp: int = 1
    node_type: NodeType = NodeType.ABILITY
    unlocked_ability_id: str | None = None
    stat_boost: Stats | None = None
    prerequisites: list[str] = field(default_factory=list)
    tier: int = 1


@dataclass
class CharacterSkillTree:
    """Skill tree state for an individual character."""
    character_id: str
    nodes: dict[str, SkillNode] = field(default_factory=dict)
    unlocked_nodes: set[str] = field(default_factory=set)

    def can_unlock(self, node_id: str, available_sp: int) -> tuple[bool, str]:
        """Check whether node can be unlocked given SP and prerequisites."""
        if node_id not in self.nodes:
            return False, "Node does not exist"

        if node_id in self.unlocked_nodes:
            return False, "Node already unlocked"

        node = self.nodes[node_id]

        for prereq_id in node.prerequisites:
            if prereq_id not in self.unlocked_nodes:
                prereq_node = self.nodes.get(prereq_id)
                prereq_name = prereq_node.name if prereq_node else prereq_id
                return False, f"Requires prerequisite: {prereq_name}"

        if available_sp < node.cost_sp:
            return False, f"Not enough SP (requires {node.cost_sp}, have {available_sp})"

        return True, "Ready to unlock"

    def unlock_node(self, character: Character, node_id: str) -> bool:
        """Unlock node, deduct character SP, grant ability or stat boost."""
        can, _ = self.can_unlock(node_id, character.skill_points)
        if not can:
            return False

        node = self.nodes[node_id]
        character.skill_points -= node.cost_sp
        self.unlocked_nodes.add(node_id)

        if node.node_type == NodeType.ABILITY and node.unlocked_ability_id:
            if node.unlocked_ability_id not in character.learned_abilities:
                character.learned_abilities.append(node.unlocked_ability_id)

        elif node.node_type == NodeType.STAT_BOOST and node.stat_boost:
            character.base_stats = character.base_stats.add(node.stat_boost)
            character.heal(node.stat_boost.max_hp)
            character.restore_mp(node.stat_boost.max_mp)

        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "character_id": self.character_id,
            "unlocked_nodes": list(self.unlocked_nodes),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], catalog_nodes: dict[str, SkillNode]) -> CharacterSkillTree:
        return cls(
            character_id=data["character_id"],
            nodes=catalog_nodes,
            unlocked_nodes=set(data.get("unlocked_nodes", [])),
        )
