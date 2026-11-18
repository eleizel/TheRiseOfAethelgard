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
        "growth_per_level": Stats(max_hp=9, max_mp=2, attack=2, defense=1, magic_attack=2, magic_defense=1, speed=1, crit_chance=0.002),
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
        "growth_per_level": Stats(max_hp=10, max_mp=2, attack=2, defense=1, magic_attack=1, magic_defense=1, speed=2, crit_chance=0.004),
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
        "growth_per_level": Stats(max_hp=8, max_mp=4, attack=1, defense=1, magic_attack=2, magic_defense=2, speed=1, crit_chance=0.002),
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
        "growth_per_level": Stats(max_hp=26, max_mp=5, attack=3, defense=2, magic_attack=2, magic_defense=2, speed=1, crit_chance=0.003),
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
        "growth_per_level": Stats(max_hp=22, max_mp=5, attack=3, defense=2, magic_attack=2, magic_defense=2, speed=1, crit_chance=0.003),
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
        "growth_per_level": Stats(max_hp=12, max_mp=3, attack=3, defense=2, magic_attack=2, magic_defense=1, speed=2, crit_chance=0.003),
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
        "growth_per_level": Stats(max_hp=45, max_mp=10, attack=4, defense=3, magic_attack=2, magic_defense=2, speed=1, crit_chance=0.004),
    },
}


MAP_LEVEL_BANDS: Final[dict[str, tuple[int, int]]] = {
    "briarwood_verge": (1, 4),
    "rooted_hollows": (4, 8),
}


def compute_scaled_level(
    party_avg_level: float | None,
    min_level: int,
    max_level: int,
    rng: random.Random | None = None,
) -> int:
    """Compute an encounter enemy level near party_avg_level clamped to the zone band."""
    if party_avg_level is None:
        return min_level
    offset = (rng or random).choice([-1, 0, 0, 1])
    return max(min_level, min(max_level, round(party_avg_level) + offset))


def scaled_boss_level(base_level: int, party_avg_level: float | None) -> int:
    """Scale a scripted boss/elite within [base_level, base_level + 2]."""
    if party_avg_level is None:
        return base_level
    return max(base_level, min(base_level + 2, round(party_avg_level)))


def create_enemy(
    template_id: str,
    instance_id: str | None = None,
    level: int | None = None,
) -> Enemy:
    """Create an enemy instance from template, optionally scaled to target level."""
    if template_id not in ENEMY_TEMPLATES:
        raise ValueError(f"Unknown enemy template: '{template_id}'")

    tmpl = ENEMY_TEMPLATES[template_id]
    uid = instance_id or f"{template_id}_{random.randint(100, 999)}"
    base_stats: Stats = tmpl["stats"]
    base_level: int = tmpl["level"]
    target_level = max(1, int(level)) if level is not None else base_level
    delta = target_level - base_level
    growth: Stats = tmpl.get("growth_per_level", Stats())

    if delta != 0:
        scaled_stats = Stats(
            max_hp=max(10, base_stats.max_hp + growth.max_hp * delta),
            max_mp=max(0, base_stats.max_mp + growth.max_mp * delta),
            attack=max(1, base_stats.attack + growth.attack * delta),
            defense=max(1, base_stats.defense + growth.defense * delta),
            magic_attack=max(1, base_stats.magic_attack + growth.magic_attack * delta),
            magic_defense=max(1, base_stats.magic_defense + growth.magic_defense * delta),
            speed=max(1, base_stats.speed + growth.speed * delta),
            crit_chance=max(0.0, min(0.5, base_stats.crit_chance + growth.crit_chance * delta)),
        )
        reward_mult = max(0.5, 1.0 + 0.15 * delta)
        exp_reward = max(1, round(tmpl["exp_reward"] * reward_mult))
        gold_reward = max(1, round(tmpl["gold_reward"] * reward_mult))
    else:
        scaled_stats = Stats(
            max_hp=base_stats.max_hp,
            max_mp=base_stats.max_mp,
            attack=base_stats.attack,
            defense=base_stats.defense,
            magic_attack=base_stats.magic_attack,
            magic_defense=base_stats.magic_defense,
            speed=base_stats.speed,
            crit_chance=base_stats.crit_chance,
        )
        exp_reward = tmpl["exp_reward"]
        gold_reward = tmpl["gold_reward"]

    return Enemy(
        id=uid,
        name=tmpl["name"],
        tier=tmpl["tier"],
        level=target_level,
        current_hp=scaled_stats.max_hp,
        stats=scaled_stats,
        weaknesses=list(tmpl["weaknesses"]),
        resistances=list(tmpl["resistances"]),
        abilities=list(tmpl["abilities"]),
        exp_reward=exp_reward,
        gold_reward=gold_reward,
        loot_drops=list(tmpl["loot_drops"]),
        sprite_id=template_id,
    )


def generate_encounter_for_map(
    map_id: str,
    is_elite: bool = False,
    party_avg_level: float | None = None,
) -> list[Enemy]:
    """Generate enemy troop suitable for the specified map, scaled within zone level bands."""
    if is_elite:
        base_lvl = ENEMY_TEMPLATES["corrupted_treant"]["level"]
        return [create_enemy("corrupted_treant", "treant_boss", level=scaled_boss_level(base_lvl, party_avg_level))]

    min_lvl, max_lvl = MAP_LEVEL_BANDS.get(map_id, (1, 4))

    if map_id == "briarwood_verge":
        candidates = ["thornvein_creeper", "bramble_hound", "spore_pod"]
    elif map_id == "rooted_hollows":
        candidates = ["root_crawler", "thornvein_creeper", "spore_pod"]
    else:
        return [create_enemy("thornvein_creeper", "enemy_1")]

    count = random.choice([1, 2, 2, 3])
    enemies = []
    for i in range(count):
        t_id = random.choice(candidates)
        enemy_lvl = (
            compute_scaled_level(party_avg_level, min_lvl, max_lvl)
            if party_avg_level is not None
            else None
        )
        enemies.append(create_enemy(t_id, f"enemy_{i + 1}", level=enemy_lvl))
    return enemies
