"""Declarative character factory definitions."""

from __future__ import annotations

from src.data.classes import CLASS_REGISTRY
from src.entities.character import Character, Equipment


def create_character(char_id: str, level: int = 1) -> Character:
    """Instantiate a character initialized with their class base stats and starting kit."""
    catalog = {
        "rowan": {
            "name": "Rowan",
            "class_id": "vanguard",
            "equipment": Equipment(weapon="iron_broadsword", armor="guard_brigandine", accessory=None),
        },
        "lyra": {
            "name": "Lyra",
            "class_id": "botanist",
            "equipment": Equipment(weapon="cedar_staff", armor="herbalist_tunic", accessory=None),
        },
        "caelen": {
            "name": "Caelen",
            "class_id": "scout",
            "equipment": Equipment(weapon="twin_stiletto", armor="shadow_leather", accessory=None),
        },
        "melissa": {
            "name": "Melissa",
            "class_id": "weave_mage",
            "equipment": Equipment(weapon="arcane_wand", armor="scholar_robes", accessory=None),
        },
        "goran": {
            "name": "Goran",
            "class_id": "berserker",
            "equipment": Equipment(weapon="greataxe", armor="miner_harness", accessory=None),
        },
        "valora": {
            "name": "Sister Valora",
            "class_id": "inquisitor",
            "equipment": Equipment(weapon="judgment_mace", armor="templar_cuirass", accessory=None),
        },
        "zephyr": {
            "name": "Zephyr",
            "class_id": "bard",
            "equipment": Equipment(weapon="recurve_bow", armor="silk_gambeson", accessory=None),
        },
        "thaddeus": {
            "name": "Thaddeus",
            "class_id": "artificer",
            "equipment": Equipment(weapon="crystal_blunderbuss", armor="tinkerer_coat", accessory=None),
        },
        "jack": {
            "name": "Jack",
            "class_id": "hunter",
            "equipment": Equipment(weapon="hunter_longbow", armor="shadow_leather", accessory=None),
        },
        "rachel": {
            "name": "Rachel",
            "class_id": "witch",
            "equipment": Equipment(
                weapon="orchid_wand",
                armor="witchfire_shawl",
                accessory="orchid_hairpin",
            ),
        },
    }

    if char_id not in catalog:
        raise ValueError(f"Unknown character id: '{char_id}'")

    info = catalog[char_id]
    class_def = CLASS_REGISTRY[info["class_id"]]

    char = Character(
        id=char_id,
        name=info["name"],
        class_id=info["class_id"],
        level=1,
        current_exp=0,
        current_hp=class_def.base_stats.max_hp,
        current_mp=class_def.base_stats.max_mp,
        base_stats=class_def.base_stats,
        equipment=info["equipment"],
        learned_abilities=list(class_def.starting_abilities),
        skill_points=0,
    )

    # Scale to requested level
    if level > 1:
        for _ in range(level - 1):
            char.level += 1
            char.base_stats = char.base_stats.add(class_def.growth_per_level)
            char.current_hp = char.base_stats.max_hp
            char.current_mp = char.base_stats.max_mp
            char.skill_points += 1

    return char
