"""Unit tests for Item catalog, equipment slots, and effective stats."""

from src.data.characters import create_character
from src.data.items import ITEM_REGISTRY, ItemType
from src.entities.character import Equipment


def test_item_registry_catalog():
    assert "healing_poultice" in ITEM_REGISTRY
    assert ITEM_REGISTRY["healing_poultice"].item_type == ItemType.CONSUMABLE
    assert "sunwarden_blade" in ITEM_REGISTRY
    assert ITEM_REGISTRY["sunwarden_blade"].item_type == ItemType.WEAPON


def test_effective_stats_with_equipment():
    char = create_character("rowan")
    base_atk = char.base_stats.attack
    base_def = char.base_stats.defense

    # Rowan starts with iron_broadsword (+8 atk) and guard_brigandine (+7 def, +15 hp)
    eff = char.effective_stats
    assert eff.attack == base_atk + 8
    assert eff.defense == base_def + 7

    # Upgrade weapon to sunwarden_blade (+18 atk, +3 def, +20 hp)
    char.equipment.weapon = "sunwarden_blade"
    new_eff = char.effective_stats
    assert new_eff.attack == base_atk + 18
    assert new_eff.defense == base_def + 7 + 3
    assert new_eff.max_hp == char.base_stats.max_hp + 15 + 20


def test_unequipped_character_effective_stats():
    char = create_character("caelen")
    char.equipment = Equipment()  # Empty
    eff = char.effective_stats
    assert eff.attack == char.base_stats.attack
    assert eff.defense == char.base_stats.defense
