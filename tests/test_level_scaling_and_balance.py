from __future__ import annotations

from src.core.session import GameSession
from src.data.abilities import ABILITY_REGISTRY
from src.data.characters import create_character
from src.data.classes import CLASS_REGISTRY
from src.data.enemies import (
    ENEMY_TEMPLATES,
    MAP_LEVEL_BANDS,
    create_enemy,
    generate_encounter_for_map,
    scaled_boss_level,
)
from src.data.items import ITEM_REGISTRY
from src.frontends.pygame_ce.combat_background import CombatBackgroundManager


def test_character_gain_exp_applies_class_growth_per_level():
    rowan = create_character("rowan", level=1)
    growth = CLASS_REGISTRY["vanguard"].growth_per_level
    base_hp = rowan.base_stats.max_hp
    base_atk = rowan.base_stats.attack
    base_def = rowan.base_stats.defense

    levels = rowan.gain_exp(rowan.exp_to_next_level)
    assert levels == [2]
    assert rowan.level == 2
    assert rowan.skill_points == 1
    assert rowan.base_stats.max_hp == base_hp + growth.max_hp
    assert rowan.base_stats.attack == base_atk + growth.attack
    assert rowan.base_stats.defense == base_def + growth.defense
    assert rowan.current_hp == rowan.base_stats.max_hp


def test_heal_and_inn_rest_respect_equipment_bonuses():
    session = GameSession(seed=42)
    session.initialize_new_game()
    rowan = session.party.active_members[0]
    rowan.equipment.accessory = "silver_ring"  # +15 max_hp, +10 max_mp
    eff_max_hp = rowan.effective_stats.max_hp
    eff_max_mp = rowan.effective_stats.max_mp
    assert eff_max_hp > rowan.base_stats.max_hp

    rowan.current_hp = 10
    rowan.current_mp = 0
    rowan.heal(999)
    rowan.restore_mp(999)
    assert rowan.current_hp == eff_max_hp
    assert rowan.current_mp == eff_max_mp

    rowan.current_hp = 1
    rowan.current_mp = 0
    assert session.rest_at_inn(50) is True
    assert rowan.current_hp == eff_max_hp
    assert rowan.current_mp == eff_max_mp


def test_enemy_level_scaling_and_zone_caps():
    base_creeper = create_enemy("thornvein_creeper", "c_base")
    lvl4_creeper = create_enemy("thornvein_creeper", "c_lvl4", level=4)
    assert lvl4_creeper.level == 4
    assert lvl4_creeper.stats.max_hp > base_creeper.stats.max_hp
    assert lvl4_creeper.stats.attack > base_creeper.stats.attack
    assert lvl4_creeper.exp_reward > base_creeper.exp_reward
    assert lvl4_creeper.gold_reward > base_creeper.gold_reward

    # Briarwood caps at 4 even if party average is level 10
    min_bw, max_bw = MAP_LEVEL_BANDS["briarwood_verge"]
    for _ in range(15):
        enemies = generate_encounter_for_map("briarwood_verge", party_avg_level=10.0)
        assert all(min_bw <= e.level <= max_bw for e in enemies)

    # Rooted Hollows clamps to [4, 8]
    min_rh, max_rh = MAP_LEVEL_BANDS["rooted_hollows"]
    for _ in range(15):
        enemies_low = generate_encounter_for_map("rooted_hollows", party_avg_level=1.0)
        enemies_mid = generate_encounter_for_map("rooted_hollows", party_avg_level=6.0)
        assert all(min_rh <= e.level <= max_rh for e in enemies_low)
        assert all(min_rh <= e.level <= max_rh for e in enemies_mid)

    # Bosses scale upward within [base_level, base_level + 2]
    treant_base = ENEMY_TEMPLATES["corrupted_treant"]["level"]
    assert scaled_boss_level(treant_base, 1.0) == treant_base
    assert scaled_boss_level(treant_base, 3.0) == treant_base + 1
    assert scaled_boss_level(treant_base, 12.0) == treant_base + 2


def test_rooted_hollows_new_enemies_and_encounter_pool():
    new_ids = (
        "corrupt_bloom",
        "crystal_viper",
        "root_wraith",
        "shadow_fungus",
        "corrupt_geomancer_elite",
        "root_guardian_elite",
    )
    allowed_templates = {"root_crawler", *new_ids}
    expected_names = {ENEMY_TEMPLATES[tid]["name"] for tid in allowed_templates}

    for tid in new_ids:
        tmpl = ENEMY_TEMPLATES[tid]
        for ab_id in tmpl["abilities"]:
            assert ab_id in ABILITY_REGISTRY, f"{tid} references unknown ability {ab_id}"
        for item_id, _chance in tmpl["loot_drops"]:
            assert item_id in ITEM_REGISTRY, f"{tid} references unknown item {item_id}"

        base = create_enemy(tid, f"{tid}_base")
        scaled = create_enemy(tid, f"{tid}_lvl8", level=8)
        assert scaled.level == 8
        assert scaled.stats.max_hp > base.stats.max_hp
        assert scaled.exp_reward > base.exp_reward

    seen_names: set[str] = set()
    for _ in range(120):
        encounter = generate_encounter_for_map("rooted_hollows", party_avg_level=5.0)
        assert encounter
        for enemy in encounter:
            assert enemy.name in expected_names
            assert enemy.name not in {"Thornvein Creeper", "Spore Pod", "Bramble Hound"}
            seen_names.add(enemy.name)

    assert "Root Crawler" in seen_names
    assert seen_names.issubset(expected_names)


def test_rooted_hollows_combat_backgrounds_load():
    import pygame

    pygame.init()
    try:
        mgr = CombatBackgroundManager()
        bg = mgr.get_random_background("rooted_hollows", "Rooted Hollows")
        assert bg is not None
        assert bg.get_width() > 0
        assert bg.get_height() > 0
    finally:
        pygame.quit()
