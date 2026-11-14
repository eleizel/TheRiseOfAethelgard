"""Dialogue domain models, branching nodes, and narrative choices."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DialogueChoice:
    text: str
    target_node_id: str


@dataclass
class DialogueNode:
    id: str
    speaker_name: str
    speaker_id: str  # "rowan", "lyra", "elder", "narrator", "treant"
    text: str
    next_node_id: str | None = None
    choices: list[DialogueChoice] = field(default_factory=list)
    action_trigger: str | None = None  # e.g. "START_BOSS_COMBAT", "RECRUIT_LYRA"


@dataclass
class DialogueTree:
    id: str
    nodes: dict[str, DialogueNode]
    start_node_id: str

    def get_node(self, node_id: str) -> DialogueNode | None:
        return self.nodes.get(node_id)
