"""Unit tests for CharacterSkillTree, prerequisites, and talent unlocks."""

from src.data.characters import create_character
from src.data.skill_trees import create_character_skill_tree


def test_skill_tree_initialization():
    tree = create_character_skill_tree("rowan")
    assert tree.character_id == "rowan"
    assert "rowan_hp_1" in tree.nodes
    assert len(tree.unlocked_nodes) == 0


def test_skill_tree_prerequisite_and_sp_validation():
    char = create_character("rowan")
    char.skill_points = 1
    tree = create_character_skill_tree("rowan")

    # Tier 2 node with prerequisites cannot be unlocked without parent
    can, reason = tree.can_unlock("rowan_skill_1", available_sp=char.skill_points)
    assert can is False
    assert "prerequisite" in reason.lower()

    # Tier 1 node can be unlocked with 1 SP
    can_t1, _ = tree.can_unlock("rowan_def_1", available_sp=char.skill_points)
    assert can_t1 is True

    # Attempt unlock
    assert tree.unlock_node(char, "rowan_def_1") is True
    assert char.skill_points == 0
    assert "rowan_def_1" in tree.unlocked_nodes
    # Defense stat increased by 4
    assert char.base_stats.defense == 14 + 4

    # Now with 0 SP, cannot unlock Aegis Bash
    can_t2, reason_sp = tree.can_unlock("rowan_skill_1", available_sp=char.skill_points)
    assert can_t2 is False
    assert "not enough sp" in reason_sp.lower()

    # Give SP and unlock Aegis Bash (Tier 2 ability)
    char.skill_points = 2
    assert tree.unlock_node(char, "rowan_skill_1") is True
    assert "aegis_bash" in char.learned_abilities


def test_skill_tree_serialization():
    char = create_character("lyra")
    char.skill_points = 3
    tree = create_character_skill_tree("lyra")

    tree.unlock_node(char, "lyra_mp_1")
    data = tree.to_dict()

    # Restore from dict
    restored = tree.from_dict(data, tree.nodes)
    assert "lyra_mp_1" in restored.unlocked_nodes
