"""Declarative item and equipment catalog."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Final

from src.entities.actor import Stats


class ItemType(Enum):
    CONSUMABLE = auto()
    WEAPON = auto()
    ARMOR = auto()
    ACCESSORY = auto()


@dataclass(frozen=True)
class ItemDefinition:
    id: str
    name: str
    description: str
    item_type: ItemType
    value: int = 10
    stat_bonus: Stats | None = None
    heal_hp: int = 0
    heal_mp: int = 0
    cleanse_status: bool = False
    revive: bool = False


ITEM_REGISTRY: Final[dict[str, ItemDefinition]] = {
    # Consumables
    "healing_poultice": ItemDefinition(
        id="healing_poultice",
        name="Healing Poultice",
        description="Restores 60 HP to a single ally.",
        item_type=ItemType.CONSUMABLE,
        value=15,
        heal_hp=60,
    ),
    "mana_draught": ItemDefinition(
        id="mana_draught",
        name="Mana Draught",
        description="Restores 35 MP to a single ally.",
        item_type=ItemType.CONSUMABLE,
        value=25,
        heal_mp=35,
    ),
    "panacea_herbs": ItemDefinition(
        id="panacea_herbs",
        name="Panacea Herbs",
        description="Cleanses all negative status conditions.",
        item_type=ItemType.CONSUMABLE,
        value=30,
        cleanse_status=True,
    ),
    "revival_balm": ItemDefinition(
        id="revival_balm",
        name="Revival Balm",
        description="Revives a fallen ally with 40% Max HP.",
        item_type=ItemType.CONSUMABLE,
        value=80,
        revive=True,
        heal_hp=50,
    ),
    # Weapons
    "iron_broadsword": ItemDefinition(
        id="iron_broadsword",
        name="Iron Broadsword",
        description="Standard infantry sword.",
        item_type=ItemType.WEAPON,
        value=40,
        stat_bonus=Stats(attack=8),
    ),
    "sunwarden_blade": ItemDefinition(
        id="sunwarden_blade",
        name="Sunwarden Blade",
        description="Polished golden steel blade bearing the royal crest.",
        item_type=ItemType.WEAPON,
        value=150,
        stat_bonus=Stats(attack=18, defense=3, max_hp=20),
    ),
    "cedar_staff": ItemDefinition(
        id="cedar_staff",
        name="Cedar Staff",
        description="Carved botanical staff channeling nature's currents.",
        item_type=ItemType.WEAPON,
        value=35,
        stat_bonus=Stats(attack=3, magic_attack=10, max_mp=10),
    ),
    "verdant_cane": ItemDefinition(
        id="verdant_cane",
        name="Verdant Cane",
        description="Ancient briarwood cane blossoming with healing buds.",
        item_type=ItemType.WEAPON,
        value=140,
        stat_bonus=Stats(attack=5, magic_attack=20, max_mp=25),
    ),
    "hunter_longbow": ItemDefinition(
        id="hunter_longbow",
        name="Hunter's Longbow",
        description="Supple yew longbow balanced for rapid, lethal draws.",
        item_type=ItemType.WEAPON,
        value=45,
        stat_bonus=Stats(attack=7, speed=3, crit_chance=0.04),
    ),
    "twin_stiletto": ItemDefinition(
        id="twin_stiletto",
        name="Twin Stiletto",
        description="Pair of needle-thin daggers forged for rapid thrusts.",
        item_type=ItemType.WEAPON,
        value=45,
        stat_bonus=Stats(attack=11, speed=4, crit_chance=0.06),
    ),
    "shadow_fang": ItemDefinition(
        id="shadow_fang",
        name="Shadow Fang",
        description="Smuggler's curved blade dipped in midnight oil.",
        item_type=ItemType.WEAPON,
        value=160,
        stat_bonus=Stats(attack=20, speed=6, crit_chance=0.10),
    ),
    "arcane_wand": ItemDefinition(
        id="arcane_wand",
        name="Arcane Wand",
        description="Crystalline conduit for channeling raw weave mana.",
        item_type=ItemType.WEAPON,
        value=40,
        stat_bonus=Stats(magic_attack=14, max_mp=15),
    ),
    "astral_spire": ItemDefinition(
        id="astral_spire",
        name="Astral Spire",
        description="Lyceum archmage rod pulsing with celestial energy.",
        item_type=ItemType.WEAPON,
        value=175,
        stat_bonus=Stats(magic_attack=25, max_mp=30),
    ),
    # Armor
    "guard_brigandine": ItemDefinition(
        id="guard_brigandine",
        name="Guard Brigandine",
        description="Steel-reinforced leather armor worn by city guards.",
        item_type=ItemType.ARMOR,
        value=50,
        stat_bonus=Stats(defense=7, max_hp=15),
    ),
    "sunwarden_plate": ItemDefinition(
        id="sunwarden_plate",
        name="Sunwarden Plate",
        description="Gleaming heavy armor crafted in the high capital.",
        item_type=ItemType.ARMOR,
        value=180,
        stat_bonus=Stats(defense=16, magic_defense=5, max_hp=45),
    ),
    "herbalist_tunic": ItemDefinition(
        id="herbalist_tunic",
        name="Herbalist Tunic",
        description="Light linen tunic offering free mobility.",
        item_type=ItemType.ARMOR,
        value=30,
        stat_bonus=Stats(defense=4, magic_defense=6),
    ),
    "grove_vestments": ItemDefinition(
        id="grove_vestments",
        name="Grove Vestments",
        description="Enchanted druidic robes warding against elemental blights.",
        item_type=ItemType.ARMOR,
        value=135,
        stat_bonus=Stats(defense=8, magic_defense=15, max_mp=20),
    ),
    "bloomweave_vestments": ItemDefinition(
        id="bloomweave_vestments",
        name="Bloomweave Vestments",
        description="Briarwood-threaded vestments woven for Lyra, channeling verdant vitality and arcane potency.",
        item_type=ItemType.ARMOR,
        value=165,
        stat_bonus=Stats(max_hp=35, magic_attack=6, defense=5),
    ),
    "shadow_leather": ItemDefinition(
        id="shadow_leather",
        name="Shadow Leather",
        description="Muffled leather armor suited for tunnel ambushes.",
        item_type=ItemType.ARMOR,
        value=40,
        stat_bonus=Stats(defense=5, speed=3),
    ),
    "whisper_tunic": ItemDefinition(
        id="whisper_tunic",
        name="Whisper Tunic",
        description="Silent cowl allowing swift evasions.",
        item_type=ItemType.ARMOR,
        value=150,
        stat_bonus=Stats(defense=10, speed=6, crit_chance=0.04),
    ),
    "scholar_robes": ItemDefinition(
        id="scholar_robes",
        name="Scholar Robes",
        description="Silk garments woven with warding threads.",
        item_type=ItemType.ARMOR,
        value=35,
        stat_bonus=Stats(defense=3, magic_defense=10, max_mp=15),
    ),
    "weave_mantle": ItemDefinition(
        id="weave_mantle",
        name="Weave Mantle",
        description="Grand robe radiating arcane containment wards.",
        item_type=ItemType.ARMOR,
        value=165,
        stat_bonus=Stats(defense=7, magic_defense=18, max_mp=30),
    ),
    # Accessories
    "silver_ring": ItemDefinition(
        id="silver_ring",
        name="Silver Ring",
        description="A polished ring offering minor vitality.",
        item_type=ItemType.ACCESSORY,
        value=50,
        stat_bonus=Stats(max_hp=15, max_mp=10),
    ),
    "swift_pendant": ItemDefinition(
        id="swift_pendant",
        name="Swift Pendant",
        description="Light feather talisman boosting turn speed.",
        item_type=ItemType.ACCESSORY,
        value=75,
        stat_bonus=Stats(speed=5),
    ),
}
