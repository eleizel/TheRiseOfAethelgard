"""Enemy templates and encounter generator catalogs."""

from __future__ import annotations

import random
from typing import Final

from src.entities.actor import Stats
from src.entities.enemy import Enemy, EnemyTier

ENEMY_TEMPLATES: Final[dict[str, dict]] = {
    "thornvein_creeper": {
        "name": "Thornvein Creeper",
        "tier": EnemyTier.MINION,
        "level": 1,
        "max_hp": 45,
        "stats": Stats(
            max_hp=45,
            max_mp=20,
            attack=11,
            defense=7,
            magic_attack=8,
            magic_defense=8,
            speed=9,
            crit_chance=0.04,
        ),
        "weaknesses": ["FIRE"],
        "resistances": ["EARTH"],
        "abilities": ["basic_attack", "briar_thorn"],
        "exp_reward": 25,
        "gold_reward": 12,
        "loot_drops": [("healing_poultice", 0.40)],
    },
    "bramble_hound": {
        "name": "Bramble Hound",
        "tier": EnemyTier.MINION,
        "level": 1,
        "max_hp": 55,
        "stats": Stats(
            max_hp=55,
            max_mp=15,
            attack=13,
            defense=8,
            magic_attack=5,
            magic_defense=6,
            speed=13,
            crit_chance=0.08,
        ),
        "weaknesses": ["FIRE", "FROST"],
        "resistances": ["PHYSICAL"],
        "abilities": ["basic_attack", "twin_daggers"],
        "exp_reward": 30,
        "gold_reward": 18,
        "loot_drops": [("healing_poultice", 0.35), ("beast_fang", 0.60)],
    },
    "spore_pod": {
        "name": "Corrupted Spore Pod",
        "tier": EnemyTier.MINION,
        "level": 1,
        "max_hp": 40,
        "stats": Stats(
            max_hp=40,
            max_mp=30,
            attack=8,
            defense=6,
            magic_attack=12,
            magic_defense=10,
            speed=8,
            crit_chance=0.05,
        ),
        "weaknesses": ["FIRE"],
        "resistances": ["EARTH", "FROST"],
        "abilities": ["basic_attack", "smoke_screen"],
        "exp_reward": 28,
        "gold_reward": 15,
        "loot_drops": [("mana_draught", 0.45)],
    },
    "corrupted_treant": {
        "name": "Corrupted Treant",
        "tier": EnemyTier.ELITE,
        "level": 2,
        "max_hp": 160,
        "stats": Stats(
            max_hp=160,
            max_mp=40,
            attack=16,
            defense=14,
            magic_attack=10,
            magic_defense=12,
            speed=7,
            crit_chance=0.06,
        ),
        "weaknesses": ["FIRE"],
        "resistances": ["EARTH", "PHYSICAL"],
        "abilities": ["shield_slam", "briar_thorn"],
        "exp_reward": 90,
        "gold_reward": 55,
        "loot_drops": [("healing_poultice", 1.0), ("ancient_bark", 0.80)],
    },
    "mandragora_matron": {
        "name": "Mandragora Matron",
        "tier": EnemyTier.ELITE,
        "level": 2,
        "max_hp": 120,
        "stats": Stats(
            max_hp=120,
            max_mp=40,
            attack=18,
            defense=12,
            magic_attack=10,
            magic_defense=12,
            speed=8,
            crit_chance=0.06,
        ),
        "weaknesses": ["FIRE"],
        "resistances": ["EARTH", "PHYSICAL"],
        "abilities": ["shield_slam", "briar_thorn"],
        "exp_reward": 90,
        "gold_reward": 55,
        "loot_drops": [("healing_poultice", 1.0), ("ancient_bark", 0.80)],
    },
    "root_crawler": {
        "name": "Root Crawler",
        "tier": EnemyTier.MINION,
        "level": 5,
        "max_hp": 75,
        "stats": Stats(
            max_hp=75,
            max_mp=25,
            attack=22,
            defense=12,
            magic_attack=10,
            magic_defense=10,
            speed=14,
            crit_chance=0.08,
        ),
        "weaknesses": ["FIRE", "HOLY"],
        "resistances": ["EARTH"],
        "abilities": ["basic_attack", "briar_thorn"],
        "exp_reward": 55,
        "gold_reward": 40,
        "loot_drops": [("healing_poultice", 0.50)],
    },
    "root_goliath": {
        "name": "Root Goliath",
        "tier": EnemyTier.BOSS,
        "level": 6,
        "max_hp": 450,
        "stats": Stats(
            max_hp=450,
            max_mp=100,
            attack=34,
            defense=22,
            magic_attack=18,
            magic_defense=16,
            speed=12,
            crit_chance=0.08,
        ),
        "weaknesses": ["FIRE", "HOLY"],
        "resistances": ["EARTH", "PHYSICAL"],
        "abilities": ["root_slam", "spore_burst", "basic_attack"],
        "exp_reward": 180,
        "gold_reward": 220,
        "loot_drops": [("sunfire_blade", 1.0)],
    },
}


def create_enemy(template_id: str, instance_id: str | None = None) -> Enemy:
    """Create an enemy instance from template."""
    if template_id not in ENEMY_TEMPLATES:
        raise ValueError(f"Unknown enemy template: '{template_id}'")

    tmpl = ENEMY_TEMPLATES[template_id]
    uid = instance_id or f"{template_id}_{random.randint(100, 999)}"
    stats = tmpl["stats"]

    return Enemy(
        id=uid,
        name=tmpl["name"],
        tier=tmpl["tier"],
        level=tmpl["level"],
        current_hp=tmpl["max_hp"],
        stats=Stats(
            max_hp=stats.max_hp,
            max_mp=stats.max_mp,
            attack=stats.attack,
            defense=stats.defense,
            magic_attack=stats.magic_attack,
            magic_defense=stats.magic_defense,
            speed=stats.speed,
            crit_chance=stats.crit_chance,
        ),
        weaknesses=list(tmpl["weaknesses"]),
        resistances=list(tmpl["resistances"]),
        abilities=list(tmpl["abilities"]),
        exp_reward=tmpl["exp_reward"],
        gold_reward=tmpl["gold_reward"],
        loot_drops=list(tmpl["loot_drops"]),
        sprite_id=template_id,
    )


def generate_encounter_for_map(map_id: str, is_elite: bool = False) -> list[Enemy]:
    """Generate enemy troop suitable for the specified map."""
    if is_elite:
        return [create_enemy("corrupted_treant", "treant_boss")]

    if map_id in ("briarwood_edge", "briarwood_verge"):
        candidates = ["thornvein_creeper", "bramble_hound", "spore_pod"]
        # Troop of 1 to 3 enemies
        count = random.choice([1, 2, 2, 3])
        enemies = []
        for i in range(count):
            t_id = random.choice(candidates)
            enemies.append(create_enemy(t_id, f"enemy_{i + 1}"))
        return enemies

    if map_id == "rooted_hollows":
        candidates = ["root_crawler", "thornvein_creeper", "spore_pod"]
        count = random.choice([1, 2, 2, 3])
        enemies = []
        for i in range(count):
            t_id = random.choice(candidates)
            enemies.append(create_enemy(t_id, f"enemy_{i + 1}"))
        return enemies

    # Fallback
    return [create_enemy("thornvein_creeper", "enemy_1")]
